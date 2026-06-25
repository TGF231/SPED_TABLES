# -*- coding: utf-8 -*-
"""
sped_editor.py
--------------
Editor visual de arquivos SPED (EFD ICMS/IPI e EFD Contribuições) em PyQt6.

A interface reproduz o comportamento do *Validador do SPED*:

    Janela
    └── QTabWidget  (uma aba por BLOCO: 0, A, C, D, E, ...)
        └── QTabWidget  (uma sub-aba por REGISTRO principal: C001, C100, ...)
            └── Master-Detail
                ├── grade editável (linhas = registros, colunas = campos)
                └── QTabWidget de filhos (Itens C170, Analítico C190, ...)
                    └── outro Master-Detail (recursivo)

O modelo de dados (parser, hierarquia, gravação e recálculo do bloco 9)
fica em `sped_model.py`; os nomes de campos/níveis em `sped_layouts.py`.

Como executar:
    pip install PyQt6
    python sped_editor.py
"""

import sys
import os

from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QColor, QFont, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QSplitter, QPushButton,
    QFileDialog, QMessageBox, QLabel, QHeaderView, QAbstractItemView,
    QToolBar, QStatusBar, QComboBox, QLineEdit, QMenu, QInputDialog,
    QStyledItemDelegate,
)

from sped_model import SpedDocument


# ---------------------------------------------------------------------------
# Delegate estilo planilha: setas ↑/↓ e Enter confirmam a edição e já reabrem
# a edição na célula vizinha (como no Excel), sem precisar de duplo-clique.
# ---------------------------------------------------------------------------
class GridDelegate(QStyledItemDelegate):
    def __init__(self, tabela):
        super().__init__(tabela)
        self.tabela = tabela

    def eventFilter(self, editor, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                       Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor)
                self._mover(-1 if key == Qt.Key.Key_Up else +1)
                return True
        return super().eventFilter(editor, event)

    def _mover(self, d):
        t = self.tabela
        nova = t.currentRow() + d
        col = t.currentColumn()
        if 0 <= nova < t.rowCount():
            def go():
                t.setCurrentCell(nova, col)
                idx = t.model().index(nova, col)
                if t.model().flags(idx) & Qt.ItemFlag.ItemIsEditable:
                    t.edit(idx)
            QTimer.singleShot(0, go)


# ---------------------------------------------------------------------------
# Widget Master-Detail (recursivo)
# ---------------------------------------------------------------------------
class MasterDetailWidget(QWidget):
    """
    Mostra uma grade de registros de um mesmo TIPO e, ao selecionar uma linha
    que possua registros-filho, exibe abaixo um QTabWidget com uma sub-aba
    por tipo de filho — cada uma contendo recursivamente outro
    MasterDetailWidget.

    Parâmetros
    ----------
    doc        : SpedDocument
    tipo       : str               -> tipo de registro desta grade (ex.: "C100")
    provider   : callable -> list  -> devolve a lista atual de registros
                                      (consultada de novo após inserir/remover)
    pai        : Registro | None   -> registro-pai comum a estes registros
                                      (usado ao inserir um novo)
    on_change  : callable | None   -> chamada quando o documento é alterado
    """

    def __init__(self, doc, tipo, provider, pai=None, on_change=None,
                 parent=None):
        super().__init__(parent)
        self.doc = doc
        self.tipo = tipo
        self.provider = provider
        self.pai = pai
        self.on_change = on_change
        self._registros = []          # todos os registros desta grade
        self._visiveis = []           # registros após o filtro (espelham a tabela)
        self._colunas = []
        self._idx_ind_oper = None     # coluna IND_OPER, se houver
        self._idx_cod_item = None     # coluna COD_ITEM, se houver
        self._idx_cod_mod = None      # coluna COD_MOD, se houver
        self._idx_num_doc = None      # coluna NUM_DOC, se houver
        self._filtro = "TODOS"        # TODOS | ENTRADAS | SAIDAS
        self._filtro_mod = ""         # COD_MOD selecionado ("" = todos)
        self._texto_busca = ""        # texto da pesquisa

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- barra de ações da grade ---
        barra = QHBoxLayout()
        self.lbl = QLabel()
        self.lbl.setStyleSheet("color:#444;")

        # rótulo central: nome do produto da linha selecionada (grades C170 etc.)
        self.lbl_item = QLabel("")
        self.lbl_item.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_item.setStyleSheet(
            "color:#2e7d32; font-weight:bold; padding:0 8px;")
        self.lbl_item.setVisible(False)

        # campo de pesquisa (nº do documento etc.) — visível quando há NUM_DOC
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("🔎 Nº do documento")
        self.busca.setClearButtonEnabled(True)
        self.busca.setMaximumWidth(240)
        self.busca.textChanged.connect(self._busca_mudou)
        self.busca.setVisible(False)

        # filtro por modelo do documento (COD_MOD) — visível quando há COD_MOD
        self.lbl_mod = QLabel("Modelo:")
        self.combo_mod = QComboBox()
        self.combo_mod.setMinimumWidth(90)
        self.combo_mod.currentIndexChanged.connect(self._mod_mudou)
        self.lbl_mod.setVisible(False)
        self.combo_mod.setVisible(False)

        # seletor Entradas/Saídas (visível só quando há IND_OPER)
        self.lbl_filtro = QLabel("Operação:")
        self.combo_filtro = QComboBox()
        self.combo_filtro.addItem("Todas", "TODOS")
        self.combo_filtro.addItem("↘ Entradas (0)", "ENTRADAS")
        self.combo_filtro.addItem("↗ Saídas (1)", "SAIDAS")
        self.combo_filtro.currentIndexChanged.connect(self._filtro_mudou)
        self.lbl_filtro.setVisible(False)
        self.combo_filtro.setVisible(False)

        btn_add = QPushButton("➕ Adicionar linha")
        btn_del = QPushButton("➖ Remover linha")
        btn_add.clicked.connect(self._adicionar)
        btn_del.clicked.connect(self._remover)

        # botão de recálculo do C190 (analítico) — só na grade C190 do ICMS,
        # quando ela é detalhe de um C100
        self.btn_recalc = QPushButton("🔄 Recalcular C190")
        self.btn_recalc.setToolTip(
            "Recalcula os C190 somando os itens C170 por CST + CFOP + alíquota")
        self.btn_recalc.clicked.connect(self._recalcular_c190)
        mostrar_recalc = (self.tipo == "C190" and self.doc.layout == "ICMS"
                          and self.pai is not None and self.pai.reg == "C100")
        self.btn_recalc.setVisible(mostrar_recalc)

        barra.addWidget(self.lbl)
        barra.addStretch(1)
        barra.addWidget(self.lbl_item, 2)
        barra.addStretch(1)
        barra.addWidget(self.busca)
        barra.addWidget(self.lbl_mod)
        barra.addWidget(self.combo_mod)
        barra.addSpacing(8)
        barra.addWidget(self.lbl_filtro)
        barra.addWidget(self.combo_filtro)
        barra.addSpacing(12)
        barra.addWidget(self.btn_recalc)
        barra.addWidget(btn_add)
        barra.addWidget(btn_del)
        layout.addLayout(barra)

        # --- splitter grade / detalhe ---
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter, 1)

        self.tabela = QTableWidget()
        # seleção de células múltiplas (Ctrl/Shift como no Excel)
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems)
        self.tabela.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        # começa a editar ao digitar (sem precisar de duplo-clique/F2)
        self.tabela.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked)
        self.tabela.setItemDelegate(GridDelegate(self.tabela))
        self.tabela.setAlternatingRowColors(True)
        # o detalhe segue a CÉLULA atual (não recria a cada extensão de seleção)
        self.tabela.currentCellChanged.connect(self._cel_atual_mudou)
        self.tabela.itemChanged.connect(self._celula_editada)
        self.tabela.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        # menu de contexto (preencher seleção / copiar / colar)
        self.tabela.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabela.customContextMenuRequested.connect(self._menu_contexto)
        # atalhos estilo planilha (locais ao grid com foco, p/ evitar conflito
        # entre as várias grades abertas)
        for seq, fn in ((QKeySequence.StandardKey.Copy, self._copiar),
                        (QKeySequence.StandardKey.Paste, self._colar),
                        (QKeySequence("Ctrl+D"), self._preencher_baixo)):
            sc = QShortcut(seq, self.tabela, fn)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.splitter.addWidget(self.tabela)

        # área de detalhe (preenchida sob demanda)
        self.area_detalhe = QTabWidget()
        self.area_detalhe.setVisible(False)
        self.area_detalhe.setMovable(False)
        self.splitter.addWidget(self.area_detalhe)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

        self._carregando = False
        self.recarregar()

    # ------------------------------------------------------------------ grade
    def recarregar(self):
        """Busca os registros do provider, detecta colunas especiais e
        repreenche a grade (respeitando o filtro de operação ativo)."""
        self._registros = list(self.provider())
        self._colunas = self.doc.colunas(self.tipo, self._registros) \
            if self._registros else self.doc.colunas(self.tipo, [])

        # localiza colunas especiais (IND_OPER p/ filtro; COD_ITEM p/ tooltip;
        # COD_MOD p/ filtro de modelo; NUM_DOC p/ pesquisa)
        def _idx(nome):
            return self._colunas.index(nome) if nome in self._colunas else None
        self._idx_ind_oper = _idx("IND_OPER")
        self._idx_cod_item = _idx("COD_ITEM")
        self._idx_cod_mod = _idx("COD_MOD")
        self._idx_num_doc = _idx("NUM_DOC")

        # mostra o seletor Entradas/Saídas apenas em grades com IND_OPER
        tem_filtro = self._idx_ind_oper is not None
        self.lbl_filtro.setVisible(tem_filtro)
        self.combo_filtro.setVisible(tem_filtro)

        # campo de pesquisa: grades de documento (que têm NUM_DOC)
        self.busca.setVisible(self._idx_num_doc is not None)

        # filtro por COD_MOD: popula com os modelos presentes
        tem_mod = self._idx_cod_mod is not None
        self.lbl_mod.setVisible(tem_mod)
        self.combo_mod.setVisible(tem_mod)
        if tem_mod:
            self.combo_mod.blockSignals(True)
            atual = self.combo_mod.currentData()
            self.combo_mod.clear()
            self.combo_mod.addItem("Todos", "")
            modelos = sorted({(r.valor(self._idx_cod_mod) or "").strip()
                              for r in self._registros
                              if (r.valor(self._idx_cod_mod) or "").strip()})
            for m in modelos:
                self.combo_mod.addItem(m, m)
            # tenta preservar a seleção anterior
            pos = self.combo_mod.findData(atual) if atual else 0
            self.combo_mod.setCurrentIndex(pos if pos >= 0 else 0)
            self._filtro_mod = self.combo_mod.currentData() or ""
            self.combo_mod.blockSignals(False)

        self._preencher()

    def _preencher(self):
        """Aplica os filtros ativos (operação, modelo, pesquisa) e popula a
        tabela."""
        self._carregando = True
        self.tabela.blockSignals(True)

        vis = self._registros
        # 1) filtro Entradas/Saídas (IND_OPER)
        if self._idx_ind_oper is not None and self._filtro != "TODOS":
            alvo = "0" if self._filtro == "ENTRADAS" else "1"
            vis = [r for r in vis
                   if (r.valor(self._idx_ind_oper) or "").strip() == alvo]
        # 2) filtro por modelo (COD_MOD)
        if self._idx_cod_mod is not None and self._filtro_mod:
            vis = [r for r in vis
                   if (r.valor(self._idx_cod_mod) or "").strip()
                   == self._filtro_mod]
        # 3) pesquisa textual (na coluna NUM_DOC quando houver; senão, geral)
        if self._texto_busca:
            t = self._texto_busca.lower()
            if self._idx_num_doc is not None:
                vis = [r for r in vis
                       if t in (r.valor(self._idx_num_doc) or "").lower()]
            else:
                vis = [r for r in vis
                       if any(t in (v or "").lower() for v in r.campos)]
        self._visiveis = list(vis)

        colunas = self._colunas
        self.tabela.clear()
        self.tabela.setColumnCount(len(colunas))
        self.tabela.setHorizontalHeaderLabels(colunas)
        self.tabela.setRowCount(len(self._visiveis))

        for i, r in enumerate(self._visiveis):
            for j in range(len(colunas)):
                item = QTableWidgetItem(r.valor(j))
                if j == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setForeground(QColor("#1565c0"))
                    item.setData(Qt.ItemDataRole.UserRole, r.uid)
                self.tabela.setItem(i, j, item)

        hdr = self.tabela.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabela.resizeColumnsToContents()
        for c in range(self.tabela.columnCount()):
            if self.tabela.columnWidth(c) > 320:
                self.tabela.setColumnWidth(c, 320)

        # rótulo: total e, se filtrado, a contagem visível
        filtrado = (len(self._visiveis) != len(self._registros))
        if filtrado:
            self.lbl.setText("%s — %d de %d (filtrado)" % (
                self.tipo, len(self._visiveis), len(self._registros)))
        else:
            self.lbl.setText("%s — %d registro(s)" % (self.tipo,
                                                      len(self._registros)))

        self.tabela.blockSignals(False)
        self._carregando = False
        self._atualizar_item_label(None)
        self._mostrar_detalhe(None)

    def _filtro_mudou(self, _idx):
        self._filtro = self.combo_filtro.currentData() or "TODOS"
        self._preencher()

    def _mod_mudou(self, _idx):
        self._filtro_mod = self.combo_mod.currentData() or ""
        self._preencher()

    def _busca_mudou(self, texto):
        self._texto_busca = (texto or "").strip()
        self._preencher()

    def _registro_da_linha(self, linha):
        if 0 <= linha < len(self._visiveis):
            return self._visiveis[linha]
        return None

    # --------------------------------------------------------------- edição
    def _celula_editada(self, item):
        if self._carregando:
            return
        r = self._registro_da_linha(item.row())
        if r is None:
            return
        r.set_valor(item.column(), item.text())
        # editar um 0200 muda as descrições -> invalida o cache de itens
        if r.reg == "0200":
            self.doc.invalidar_itens()
        if self.on_change:
            self.on_change()
        # editar o COD_ITEM atualiza o nome mostrado no topo
        if item.column() == self._idx_cod_item:
            self._atualizar_item_label(r)
        # se mexeu no IND_OPER com filtro ativo, a linha pode sair da vista
        if item.column() == self._idx_ind_oper and self._filtro != "TODOS":
            self._preencher()

    # ------------------------------------------------------------ detalhe
    def _cel_atual_mudou(self, cur_row, _cur_col, _prev_row, _prev_col):
        r = self._registro_da_linha(cur_row)
        self._atualizar_item_label(r)
        self._mostrar_detalhe(r)

    def _atualizar_item_label(self, registro):
        """Mostra, no topo centralizado, o nome do produto da linha selecionada
        (apenas em grades que têm COD_ITEM, ex.: C170)."""
        if self._idx_cod_item is None or registro is None:
            self.lbl_item.setText("")
            self.lbl_item.setVisible(False)
            return
        cod = registro.valor(self._idx_cod_item)
        desc = self.doc.descricao_item(cod)
        if desc:
            texto = "📦  %s — %s" % (cod, desc)
        elif cod:
            texto = "📦  %s — (não cadastrado no 0200)" % cod
        else:
            texto = ""
        self.lbl_item.setText(texto)
        self.lbl_item.setToolTip(texto)   # caso o nome seja maior que o espaço
        self.lbl_item.setVisible(bool(texto))

    # ----------------------------------------- seleção múltipla / clipboard
    def _menu_contexto(self, pos):
        sel = self.tabela.selectedIndexes()
        menu = QMenu(self)
        n = len([ix for ix in sel if ix.column() != 0])
        a_fill = menu.addAction(
            "Preencher seleção com um valor…  (%d célula%s)"
            % (n, "s" if n != 1 else ""))
        a_fill.setEnabled(n > 0)
        menu.addSeparator()
        a_copy = menu.addAction("Copiar\tCtrl+C")
        a_paste = menu.addAction("Colar\tCtrl+V")
        a_down = menu.addAction("Preencher para baixo\tCtrl+D")
        a_fill.triggered.connect(self._preencher_dialogo)
        a_copy.triggered.connect(self._copiar)
        a_paste.triggered.connect(self._colar)
        a_down.triggered.connect(self._preencher_baixo)
        menu.exec(self.tabela.viewport().mapToGlobal(pos))

    def _preencher_dialogo(self):
        valor, ok = QInputDialog.getText(
            self, "Preencher seleção",
            "Valor a aplicar em todas as células selecionadas:")
        if ok:
            self._aplicar_valor_em_selecao(valor)

    def _aplicar_valor_em_selecao(self, valor):
        """Escreve `valor` em todas as células selecionadas (exceto REG)."""
        sel = [ix for ix in self.tabela.selectedIndexes() if ix.column() != 0]
        if not sel:
            return
        self.tabela.blockSignals(True)
        mudou = False
        for ix in sel:
            r = self._registro_da_linha(ix.row())
            if r is None:
                continue
            r.set_valor(ix.column(), valor)
            it = self.tabela.item(ix.row(), ix.column())
            if it is not None:
                it.setText(valor)
            if r.reg == "0200":
                self.doc.invalidar_itens()
            mudou = True
        self.tabela.blockSignals(False)
        if mudou and self.on_change:
            self.on_change()

    def _copiar(self):
        """Copia a seleção como texto tabulado (linhas/colunas)."""
        sel = self.tabela.selectedIndexes()
        if not sel:
            return
        linhas = sorted({ix.row() for ix in sel})
        cols = sorted({ix.column() for ix in sel})
        matriz = []
        for lr in linhas:
            celulas = []
            for c in cols:
                it = self.tabela.item(lr, c)
                celulas.append(it.text() if it is not None else "")
            matriz.append("\t".join(celulas))
        QApplication.clipboard().setText("\n".join(matriz))

    def _colar(self):
        """Cola o conteúdo da área de transferência.
        - valor único  -> aplica a TODAS as células selecionadas;
        - bloco (TSV)  -> cola a partir da célula atual."""
        texto = QApplication.clipboard().text()
        if texto == "":
            return
        sel = [ix for ix in self.tabela.selectedIndexes() if ix.column() != 0]
        # valor único colado em vários campos selecionados
        if "\t" not in texto and "\n" not in texto.strip():
            if len(sel) > 1:
                self._aplicar_valor_em_selecao(texto.strip())
                return
        # bloco: cola a partir do canto superior esquerdo
        linha0 = self.tabela.currentRow()
        col0 = self.tabela.currentColumn()
        if linha0 < 0:
            linha0 = 0
        if col0 < 0:
            col0 = 1
        self.tabela.blockSignals(True)
        mudou = False
        for di, linha_txt in enumerate(texto.split("\n")):
            if linha_txt == "" and di == len(texto.split("\n")) - 1:
                continue
            for dj, val in enumerate(linha_txt.split("\t")):
                lr = linha0 + di
                c = col0 + dj
                if lr >= self.tabela.rowCount() or c >= self.tabela.columnCount():
                    continue
                if c == 0:        # não sobrescreve a coluna REG
                    continue
                r = self._registro_da_linha(lr)
                if r is None:
                    continue
                r.set_valor(c, val)
                it = self.tabela.item(lr, c)
                if it is not None:
                    it.setText(val)
                if r.reg == "0200":
                    self.doc.invalidar_itens()
                mudou = True
        self.tabela.blockSignals(False)
        if mudou and self.on_change:
            self.on_change()

    def _preencher_baixo(self):
        """Ctrl+D: copia o valor da célula de cima para as células abaixo
        dentro da seleção (ou para a célula atual)."""
        sel = [ix for ix in self.tabela.selectedIndexes() if ix.column() != 0]
        if not sel:
            return
        por_coluna = {}
        for ix in sel:
            por_coluna.setdefault(ix.column(), []).append(ix.row())
        self.tabela.blockSignals(True)
        mudou = False
        for c, rows in por_coluna.items():
            rows.sort()
            topo = rows[0]
            it_topo = self.tabela.item(topo, c)
            valor = it_topo.text() if it_topo is not None else ""
            for lr in rows[1:]:
                r = self._registro_da_linha(lr)
                if r is None:
                    continue
                r.set_valor(c, valor)
                it = self.tabela.item(lr, c)
                if it is not None:
                    it.setText(valor)
                mudou = True
        self.tabela.blockSignals(False)
        if mudou and self.on_change:
            self.on_change()

    def _mostrar_detalhe(self, registro):
        self.area_detalhe.clear()
        if registro is None or not self.doc.tem_detalhe(registro):
            self.area_detalhe.setVisible(False)
            return

        # uma sub-aba por tipo de filho
        for tipo_filho in self.doc.tipos_filhos(registro):
            def make_provider(reg=registro, t=tipo_filho):
                return lambda: self.doc.filhos_por_tipo(reg, t)

            sub = MasterDetailWidget(
                self.doc, tipo_filho, make_provider(),
                pai=registro, on_change=self.on_change)
            n = len(self.doc.filhos_por_tipo(registro, tipo_filho))
            rotulo = "%s (%d)" % (tipo_filho, n)
            self.area_detalhe.addTab(sub, rotulo)

        self.area_detalhe.setVisible(True)

    # ------------------------------------------------------- inserir/remover
    def _resolver_pai(self):
        """Pai a usar ao inserir um novo registro nesta grade."""
        if self.pai is not None:
            return self.pai
        if self._registros:
            return self._registros[0].pai
        return None

    def _adicionar(self):
        pai = self._resolver_pai()
        depois = self._registros[-1] if self._registros else pai
        novo = self.doc.novo_registro(self.tipo, pai=pai, depois=depois)
        # se há um filtro de operação ativo, já marca o IND_OPER do novo
        if self._idx_ind_oper is not None and self._filtro != "TODOS":
            novo.set_valor(self._idx_ind_oper,
                           "0" if self._filtro == "ENTRADAS" else "1")
        self.doc.atualizar_bloco9_inplace()
        self.recarregar()
        for i, r in enumerate(self._visiveis):
            if r.uid == novo.uid:
                self.tabela.selectRow(i)
                break
        if self.on_change:
            self.on_change()

    def _remover(self):
        linha = self.tabela.currentRow()
        r = self._registro_da_linha(linha)
        if r is None:
            QMessageBox.information(self, "Remover",
                                    "Selecione uma linha para remover.")
            return
        n_filhos = len(r.filhos)
        msg = "Remover o registro %s" % r.reg
        if n_filhos:
            msg += " e seus %d registro(s) filho(s)" % n_filhos
        msg += "?"
        if QMessageBox.question(self, "Confirmar remoção", msg) \
                != QMessageBox.StandardButton.Yes:
            return
        self.doc.remover_registro(r)
        self.doc.atualizar_bloco9_inplace()
        self.recarregar()
        if self.on_change:
            self.on_change()

    def _recalcular_c190(self):
        """Recalcula os C190 do C100 pai a partir dos itens C170."""
        if self.pai is None:
            return
        res = self.doc.consolidar_c190(self.pai)
        if res is None:
            QMessageBox.information(
                self, "Recalcular C190",
                "O recálculo automático do C190 só se aplica ao bloco C do "
                "EFD ICMS/IPI.")
            return
        if res.get("sem_c170"):
            QMessageBox.warning(
                self, "Recalcular C190",
                "Este documento (C100) não possui itens C170 para consolidar.")
            return
        self.recarregar()
        if self.on_change:
            self.on_change()
        QMessageBox.information(
            self, "Recalcular C190",
            "C190 recalculado a partir dos itens C170:\n\n"
            "• %d registro(s) C190 gerado(s), agrupados por "
            "CST + CFOP + alíquota\n"
            "• %d C190 anterior(es) substituído(s)\n\n"
            "Os valores de imposto (VL_BC_ICMS, VL_ICMS, VL_ICMS_ST, VL_IPI) "
            "são a soma exata dos itens. O VL_OPR inclui o rateio de frete, "
            "seguro e outras despesas do C100.\n\n"
            "Os totais C990 e 9900 foram atualizados."
            % (res["criados"], res["removidos"]))


# ---------------------------------------------------------------------------
# Aba de um BLOCO (lazy): QTabWidget com uma sub-aba por tipo principal
# ---------------------------------------------------------------------------
class BlocoWidget(QWidget):
    def __init__(self, doc, bloco, on_change=None, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.bloco = bloco
        self.on_change = on_change
        self._construido = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        lay.addWidget(self.tabs)

    def construir(self):
        """Cria as sub-abas de tipo só quando o bloco é aberto (lazy)."""
        if self._construido:
            return
        self._construido = True
        for tipo in self.doc.tipos_raiz_do_bloco(self.bloco):
            def make_provider(b=self.bloco, t=tipo):
                return lambda: self.doc.registros_raiz_por_tipo(b, t)

            w = MasterDetailWidget(self.doc, tipo, make_provider(),
                                   pai=None, on_change=self.on_change)
            n = len(self.doc.registros_raiz_por_tipo(self.bloco, tipo))
            self.tabs.addTab(w, "%s (%d)" % (tipo, n))


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------
class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.doc = None
        self.alterado = False
        self.setWindowTitle("Editor SPED")
        self.resize(1200, 760)

        self._criar_acoes()
        self._criar_barra()

        self.tabs_bloco = QTabWidget()
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs_bloco.currentChanged.connect(self._bloco_aberto)

        vazio = QLabel("Abra um arquivo SPED para começar  (Ctrl+O)")
        vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio.setStyleSheet("color:#888; font-size:16px;")
        self._placeholder = vazio
        self.setCentralWidget(vazio)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto.")

    # --------------------------------------------------------------- ações
    def _criar_acoes(self):
        self.act_abrir = QAction("Abrir…", self)
        self.act_abrir.setShortcut(QKeySequence.StandardKey.Open)
        self.act_abrir.triggered.connect(self.abrir)

        self.act_salvar = QAction("Salvar", self)
        self.act_salvar.setShortcut(QKeySequence.StandardKey.Save)
        self.act_salvar.triggered.connect(self.salvar)
        self.act_salvar.setEnabled(False)

        self.act_salvar_como = QAction("Salvar como…", self)
        self.act_salvar_como.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_salvar_como.triggered.connect(self.salvar_como)
        self.act_salvar_como.setEnabled(False)

        self.act_sair = QAction("Sair", self)
        self.act_sair.triggered.connect(self.close)

        self.act_recalc_totais = QAction("Recalcular totais (C990/9900)…", self)
        self.act_recalc_totais.triggered.connect(self.recalcular_totais)
        self.act_recalc_totais.setEnabled(False)

    def _criar_barra(self):
        menu = self.menuBar().addMenu("&Arquivo")
        menu.addAction(self.act_abrir)
        menu.addAction(self.act_salvar)
        menu.addAction(self.act_salvar_como)
        menu.addSeparator()
        menu.addAction(self.act_sair)

        menu_ferr = self.menuBar().addMenu("&Ferramentas")
        menu_ferr.addAction(self.act_recalc_totais)

        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.act_abrir)
        tb.addAction(self.act_salvar)
        tb.addAction(self.act_salvar_como)

    def recalcular_totais(self):
        """Recalcula as contagens (X990 e bloco 9) e atualiza a exibição."""
        if not self.doc:
            return
        self.doc.atualizar_bloco9_inplace()
        self._montar_abas()
        self.statusBar().showMessage(
            "Totais recalculados: X990 (por bloco) e 9900 (por tipo de "
            "registro) atualizados.")
        QMessageBox.information(
            self, "Recalcular totais",
            "As contagens foram atualizadas:\n\n"
            "• X990 (ex.: C990) = nº de linhas de cada bloco\n"
            "• 9900 = nº de registros de cada tipo (ex.: 9900|C190|<qtd>)\n"
            "• 9990 e 9999 = totais do bloco 9 e do arquivo\n\n"
            "Esses valores também são sempre recalculados ao salvar.")

    # ------------------------------------------------------------ abrir
    def abrir(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir arquivo SPED", "",
            "Arquivos SPED (*.txt);;Todos os arquivos (*)")
        if not caminho:
            return
        try:
            doc = SpedDocument.carregar(caminho)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao abrir",
                                 "Não foi possível ler o arquivo:\n%s" % e)
            return
        self.doc = doc
        self.alterado = False
        self._montar_abas()
        self.act_salvar.setEnabled(True)
        self.act_salvar_como.setEnabled(True)
        self.act_recalc_totais.setEnabled(True)
        nome = os.path.basename(caminho)
        tipo = "EFD Contribuições" if doc.layout == "CONTRIB" \
            else "EFD ICMS/IPI"
        self.setWindowTitle("Editor SPED — %s  [%s]" % (nome, tipo))
        self.statusBar().showMessage(
            "%s carregado: %d registros, layout %s."
            % (nome, len(doc.registros), tipo))

    def _montar_abas(self):
        self.tabs_bloco = QTabWidget()
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs_bloco.currentChanged.connect(self._bloco_aberto)
        self.setCentralWidget(self.tabs_bloco)

        nomes_bloco = {
            "0": "0 · Abertura/Identificação", "A": "A · Serviços",
            "B": "B · ISS", "C": "C · Mercadorias (ICMS/IPI)",
            "D": "D · Serviços (ICMS/Transporte)", "E": "E · Apuração ICMS/IPI",
            "F": "F · Demais Documentos/Operações", "G": "G · CIAP",
            "H": "H · Inventário", "I": "I · Outras informações",
            "K": "K · Produção/Estoque", "M": "M · Apuração PIS/COFINS",
            "P": "P · Apuração Previdenciária", "1": "1 · Outras",
            "9": "9 · Controle/Totais",
        }
        self._blocos = []
        for b in self.doc.blocos():
            w = BlocoWidget(self.doc, b, on_change=self._marcar_alterado)
            self._blocos.append(w)
            self.tabs_bloco.addTab(w, nomes_bloco.get(b, "Bloco %s" % b))
        if self._blocos:
            self.tabs_bloco.setCurrentIndex(0)
            self._bloco_aberto(0)

    def _bloco_aberto(self, idx):
        if 0 <= idx < len(getattr(self, "_blocos", [])):
            self._blocos[idx].construir()

    # ------------------------------------------------------------ salvar
    def _marcar_alterado(self):
        self.alterado = True
        t = self.windowTitle()
        if not t.endswith(" *"):
            self.setWindowTitle(t + " *")

    def salvar(self):
        if not self.doc:
            return
        if not self.doc.caminho:
            return self.salvar_como()
        self._gravar(self.doc.caminho)

    def salvar_como(self):
        if not self.doc:
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar arquivo SPED",
            self.doc.caminho or "", "Arquivos SPED (*.txt)")
        if not caminho:
            return
        self._gravar(caminho)

    def _gravar(self, caminho):
        try:
            self.doc.salvar(caminho)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar",
                                 "Não foi possível gravar:\n%s" % e)
            return
        self.alterado = False
        nome = os.path.basename(caminho)
        self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self.statusBar().showMessage(
            "Salvo em %s (bloco 9 recalculado)." % nome)
        QMessageBox.information(
            self, "Salvo",
            "Arquivo gravado com sucesso:\n%s\n\n"
            "Os registros de totalização (X990, 9900, 9990, 9999) "
            "foram recalculados automaticamente." % caminho)

    # ------------------------------------------------------------ fechar
    def closeEvent(self, event):
        if self.alterado:
            resp = QMessageBox.question(
                self, "Sair",
                "Há alterações não salvas. Deseja sair mesmo assim?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Editor SPED")
    # fonte um pouco menor deixa as grades mais densas (estilo planilha)
    f = QFont()
    f.setPointSize(max(8, f.pointSize() - 1))
    app.setFont(f)
    janela = JanelaPrincipal()
    janela.show()
    # abre direto se um caminho for passado na linha de comando
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        try:
            janela.doc = SpedDocument.carregar(sys.argv[1])
            janela.alterado = False
            janela._montar_abas()
            janela.act_salvar.setEnabled(True)
            janela.act_salvar_como.setEnabled(True)
        except Exception:  # noqa: BLE001
            pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

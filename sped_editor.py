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
import re
import datetime

from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QColor, QFont, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QSplitter, QPushButton,
    QFileDialog, QMessageBox, QLabel, QHeaderView, QAbstractItemView,
    QToolBar, QStatusBar, QComboBox, QLineEdit, QMenu, QInputDialog,
    QStyledItemDelegate, QDialog, QCheckBox, QFormLayout, QToolButton,
    QDoubleSpinBox, QGridLayout, QGroupBox,
)

from sped_model import SpedDocument
import xml_fiscal as xf
import conferencia as cf
import revisao as rev
import tabelas_rfb as trfb
from version import __version__, APP_NAME


def _br(v):
    """Formata número no padrão brasileiro: 1234.5 -> '1.234,50'."""
    try:
        return ("%0.2f" % float(v)).replace(".", "@").replace(",", ".").replace("@", ",")
    except (TypeError, ValueError):
        return str(v)


# número no padrão BR: inteiro, com pontos de milhar e/ou vírgula decimal.
# (evita tratar códigos como "3.1.1" ou datas como número)
_RE_NUM_BR = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$|^-?\d+(,\d+)?$")


def _num_celula(texto):
    """Converte o texto de uma célula em float se for um número BR; senão None.
    Ignora inteiros muito longos (ex.: chave de acesso de 44 dígitos), que não
    são valores somáveis e perderiam precisão."""
    s = (texto or "").strip()
    if not s or not _RE_NUM_BR.match(s):
        return None
    if len(s.replace("-", "").replace(".", "").replace(",", "")) > 15:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


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
class GerenciadorOrdemAbas:
    """Memoriza, apenas durante a sessão, a ordem em que o usuário arrastou as
    abas. Cada aba é identificada por um id estável (código do bloco ou tipo de
    registro), de modo que a ordem escolhida sobrevive às remontagens das grades.
    Não há persistência após fechar o programa — ao reabrir, tudo volta ao
    padrão."""

    def __init__(self):
        self._ordens = {}   # chave de contexto -> [ids na ordem desejada]

    def registrar(self, tabw, chave, ids):
        """Habilita o arrasto de abas, reaplica a ordem já escolhida para esta
        `chave` (se houver) e passa a memorizar novas reordenações.
        `ids[i]` é o identificador estável da aba de índice i."""
        tabw.setMovable(True)
        bar = tabw.tabBar()
        for i, ident in enumerate(ids):
            if i < bar.count():
                bar.setTabData(i, ident)
        self._aplicar(tabw, chave)
        # Conecta o memorizador UMA única vez por QTabWidget. NÃO desconectar
        # o sinal em geral: `tabMoved.disconnect()` removeria também o slot
        # interno do QTabWidget que sincroniza o conteúdo ao mover a aba —
        # era isso que fazia o conteúdo "ficar para trás" da aba arrastada.
        if not getattr(tabw, "_ordem_conectada", False):
            bar.tabMoved.connect(lambda *_: self._memorizar(tabw, chave))
            tabw._ordem_conectada = True

    def _memorizar(self, tabw, chave):
        bar = tabw.tabBar()
        self._ordens[chave] = [bar.tabData(i) for i in range(bar.count())]

    def _aplicar(self, tabw, chave):
        ordem = self._ordens.get(chave)
        if not ordem:
            return
        bar = tabw.tabBar()
        for destino, ident in enumerate(ordem):
            atual = next((i for i in range(bar.count())
                          if bar.tabData(i) == ident), None)
            if atual is not None and atual != destino:
                bar.moveTab(atual, destino)


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
                 parent=None, gerenciador=None):
        super().__init__(parent)
        self.doc = doc
        self.tipo = tipo
        self.provider = provider
        self.pai = pai
        self.on_change = on_change
        self._ger_abas = gerenciador
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
        self.tabela.itemSelectionChanged.connect(self._resumo_selecao)
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

        # campo de pesquisa: visível em qualquer grade com registros.
        # Em grades de documento foca o nº do documento; nas demais (0200,
        # H010, etc.) pesquisa em todas as colunas.
        self.busca.setVisible(bool(self._registros))
        if self._idx_num_doc is not None:
            self.busca.setPlaceholderText("🔎 Nº do documento")
        else:
            self.busca.setPlaceholderText("🔎 Pesquisar (todas as colunas)")

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

    def _resumo_selecao(self):
        """Como no Excel: ao selecionar várias células numéricas, mostra
        soma, média e contagem na barra de status."""
        itens = self.tabela.selectedItems()
        if len(itens) < 2:
            return
        nums = [n for n in (_num_celula(it.text()) for it in itens)
                if n is not None]
        if len(nums) < 2:
            return
        janela = self.window()
        if janela is None or not hasattr(janela, "statusBar"):
            return
        soma = sum(nums)
        media = soma / len(nums)
        janela.statusBar().showMessage(
            "Soma: %s     Média: %s     Contagem: %d"
            % (_br(soma), _br(media), len(nums)))

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
        tipos = list(self.doc.tipos_filhos(registro))
        for tipo_filho in tipos:
            def make_provider(reg=registro, t=tipo_filho):
                return lambda: self.doc.filhos_por_tipo(reg, t)

            sub = MasterDetailWidget(
                self.doc, tipo_filho, make_provider(),
                pai=registro, on_change=self.on_change,
                gerenciador=self._ger_abas)
            n = len(self.doc.filhos_por_tipo(registro, tipo_filho))
            rotulo = "%s (%d)" % (tipo_filho, n)
            self.area_detalhe.addTab(sub, rotulo)

        self.area_detalhe.setVisible(True)
        # permite reordenar as sub-abas de detalhe (ordem por tipo do master)
        if self._ger_abas is not None:
            self._ger_abas.registrar(
                self.area_detalhe, "det:%s" % self.tipo, tipos)

    # ----------------------------------------------------------- navegação
    def selecionar_uid(self, uid):
        """Limpa filtros, localiza a linha do registro `uid`, seleciona-a e
        garante que o detalhe seja exibido. Retorna True se encontrou."""
        self._texto_busca = ""
        self.busca.blockSignals(True)
        self.busca.clear()
        self.busca.blockSignals(False)
        if self._idx_ind_oper is not None:
            self.combo_filtro.blockSignals(True)
            self.combo_filtro.setCurrentIndex(0)
            self.combo_filtro.blockSignals(False)
            self._filtro = "TODOS"
        if self._idx_cod_mod is not None:
            self.combo_mod.blockSignals(True)
            self.combo_mod.setCurrentIndex(0)
            self.combo_mod.blockSignals(False)
            self._filtro_mod = ""
        self._preencher()
        for i, r in enumerate(self._visiveis):
            if r.uid == uid:
                self.tabela.setCurrentCell(i, 0)
                self.tabela.selectRow(i)
                it = self.tabela.item(i, 0)
                if it is not None:
                    self.tabela.scrollToItem(
                        it, QAbstractItemView.ScrollHint.PositionAtCenter)
                self._mostrar_detalhe(r)
                return True
        return False

    def subwidget_de_tipo(self, tipo):
        """Após o detalhe estar visível, seleciona a sub-aba do `tipo` filho e
        devolve o MasterDetailWidget correspondente (ou None)."""
        for i in range(self.area_detalhe.count()):
            w = self.area_detalhe.widget(i)
            if getattr(w, "tipo", None) == tipo:
                self.area_detalhe.setCurrentIndex(i)
                return w
        return None

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
    def __init__(self, doc, bloco, on_change=None, parent=None,
                 gerenciador=None):
        super().__init__(parent)
        self.doc = doc
        self.bloco = bloco
        self.on_change = on_change
        self._ger_abas = gerenciador
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
        tipos = list(self.doc.tipos_raiz_do_bloco(self.bloco))
        for tipo in tipos:
            def make_provider(b=self.bloco, t=tipo):
                return lambda: self.doc.registros_raiz_por_tipo(b, t)

            w = MasterDetailWidget(self.doc, tipo, make_provider(),
                                   pai=None, on_change=self.on_change,
                                   gerenciador=self._ger_abas)
            n = len(self.doc.registros_raiz_por_tipo(self.bloco, tipo))
            self.tabs.addTab(w, "%s (%d)" % (tipo, n))
        # permite reordenar as sub-abas de tipo dentro do bloco
        if self._ger_abas is not None:
            self._ger_abas.registrar(self.tabs, "bloco:%s" % self.bloco, tipos)

    def widget_do_tipo(self, tipo):
        """Garante o bloco construído, seleciona a sub-aba do `tipo` e devolve
        o MasterDetailWidget (ou None)."""
        self.construir()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "tipo", None) == tipo:
                self.tabs.setCurrentIndex(i)
                return w
        return None


# ---------------------------------------------------------------------------
# Diálogo de resultado da conferência de entradas (NF-e 55)
# ---------------------------------------------------------------------------
class DialogoConfC190(QDialog):
    """Resultado da conferência C190 × XML (agrupada pela classificação do
    C170). Mostra as divergências por grupo e permite exportar em CSV."""

    COLS = ["nNF", "Grupo (CFOP·CST·alíq)", "Campo", "Valor XML",
            "Valor SPED", "Diferença"]

    def __init__(self, resultado, parent=None):
        super().__init__(parent)
        self.resultado = resultado
        self.setWindowTitle("Conferência C190 × XML")
        self.resize(820, 560)
        lay = QVBoxLayout(self)

        r = resultado["resumo"]
        resumo = QLabel(
            "Documentos casados: %d   ·   Grupos conferidos: %d   ·   "
            "Divergências: %d\nGrupos só no C190: %d   ·   só no XML: %d   ·   "
            "docs sem XML: %d   ·   itens do XML sem C170: %d"
            % (r["docs_casados"], r["grupos_conferidos"], r["divergencias"],
               r["grupos_so_c190"], r["grupos_so_xml"], r["docs_sem_xml"],
               r["itens_sem_c170"]))
        lay.addWidget(resumo)

        self.tab = QTableWidget(0, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True)
        self.tab.setSortingEnabled(True)
        self.tab.horizontalHeader().setStretchLastSection(True)
        divs = resultado["divergencias"]
        self.tab.setRowCount(len(divs))
        for i, d in enumerate(divs):
            vals = [d.nnf, d.nitem, d.campo, _br(d.valor_xml),
                    _br(d.valor_sped), _br((d.valor_xml or 0) - (d.valor_sped or 0))]
            for c, v in enumerate(vals):
                self.tab.setItem(i, c, QTableWidgetItem(str(v)))
        self.tab.resizeColumnsToContents()
        lay.addWidget(self.tab, 1)

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(self._exportar)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.accept)
        rod.addWidget(b_csv)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    def _exportar(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar conferência C190", "conferencia_c190.csv",
            "CSV (*.csv)")
        if not caminho:
            return
        try:
            with open(caminho, "w", encoding="latin-1", newline="") as fh:
                fh.write(";".join(self.COLS) + "\r\n")
                for d in self.resultado["divergencias"]:
                    fh.write(";".join([
                        d.nnf or "", d.nitem or "", d.campo or "",
                        _br(d.valor_xml), _br(d.valor_sped),
                        _br((d.valor_xml or 0) - (d.valor_sped or 0))]) + "\r\n")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportar", str(exc))
            return
        QMessageBox.information(self, "Exportar", "Exportado:\n%s" % caminho)


class DialogoConferencia(QDialog):
    """Mostra o resultado da conferência item XML ↔ C170 e permite exportar."""

    COLS = ["Escopo", "nNF", "nItem", "Campo", "Valor XML", "Valor SPED",
            "Observação"]

    def __init__(self, resultado, parent=None):
        super().__init__(parent)
        self.resultado = resultado
        self.setWindowTitle("Conferência de entradas (NF-e modelo 55)")
        self.resize(900, 520)
        lay = QVBoxLayout(self)

        r = resultado["resumo"]
        resumo = (
            "XMLs modelo 55: %d   |   documentos casados: %d   |   "
            "itens conferidos: %d\n"
            "Divergências: %d   |   itens sem C170 (faltam no SPED): %d   |   "
            "C170 sem XML na pasta: %d\n"
            "XMLs sem C100 no SPED: %d"
            % (r["xml_55"], r["docs_casados"], r["itens_conferidos"],
               r["divergencias"], r["itens_sem_c170"], r["itens_sem_xml"],
               r["docs_sem_c100"]))
        lbl = QLabel(resumo)
        if r["divergencias"] == 0:
            lbl.setStyleSheet("color:#0a0; font-weight:bold;")
        else:
            lbl.setStyleSheet("color:#b00; font-weight:bold;")
        lay.addWidget(lbl)

        divs = resultado["divergencias"]
        tab = QTableWidget(len(divs), len(self.COLS))
        tab.setHorizontalHeaderLabels(self.COLS)
        tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, d in enumerate(divs):
            vals = [d.escopo, d.nnf, d.nitem or "", d.campo,
                    cf._fmt(d.valor_xml), cf._fmt(d.valor_sped), d.obs or ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j in (4, 5):
                    it.setForeground(QColor("#b00"))
                tab.setItem(i, j, it)
        tab.resizeColumnsToContents()
        tab.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(tab)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        b_csv = QPushButton("Exportar CSV…")
        b_csv.clicked.connect(self._exportar)
        b_csv.setEnabled(bool(divs))
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.accept)
        botoes.addWidget(b_csv)
        botoes.addWidget(b_fechar)
        lay.addLayout(botoes)

    def _exportar(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar divergências", "divergencias_entradas.csv",
            "Arquivos CSV (*.csv)")
        if not caminho:
            return
        cf.exportar_csv(self.resultado, caminho)
        QMessageBox.information(self, "Exportar",
                                "Divergências exportadas para:\n%s" % caminho)


# ---------------------------------------------------------------------------
# Página inicial: cabeçalho do arquivo e contagem de registros
# ---------------------------------------------------------------------------
def _data_br(s):
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return "%s/%s/%s" % (s[0:2], s[2:4], s[4:8])
    return s or "—"


class ResumoWidget(QWidget):
    """Aba inicial: dados do registro 0000, metadados do arquivo e contagem."""

    def __init__(self, doc, caminho, parent=None):
        super().__init__(parent)
        self.doc = doc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        def v(nome):
            i = doc._ix("0000", nome)
            r0 = next((r for r in doc.registros if r.reg == "0000"), None)
            return (r0.valor(i) if (r0 and i is not None) else "") or ""

        tipo = ("EFD Contribuições" if doc.layout == "CONTRIB"
                else "EFD ICMS/IPI")
        nome = v("NOME") or "—"
        cnpj = v("CNPJ")
        cnpj_fmt = ("%s.%s.%s/%s-%s" % (cnpj[0:2], cnpj[2:5], cnpj[5:8],
                                        cnpj[8:12], cnpj[12:14])
                    if len(cnpj) == 14 else (cnpj or "—"))
        ie = v("IE")
        uf = v("UF")
        periodo = "%s a %s" % (_data_br(v("DT_INI")), _data_br(v("DT_FIN")))

        mod = "—"
        if caminho and os.path.exists(caminho):
            ts = os.path.getmtime(caminho)
            mod = datetime.datetime.fromtimestamp(ts).strftime(
                "%d/%m/%Y %H:%M:%S")
        nome_arq = os.path.basename(caminho) if caminho else "(não salvo)"

        cab = QLabel(
            "<div style='font-size:20px;font-weight:bold;color:#1565c0'>%s</div>"
            "<div style='color:#555;margin-bottom:8px'>%s &nbsp;•&nbsp; %s</div>"
            "<table cellspacing='6'>"
            "<tr><td style='color:#888'>CNPJ</td><td><b>%s</b></td>"
            "<td style='color:#888;padding-left:24px'>IE</td><td><b>%s</b></td>"
            "<td style='color:#888;padding-left:24px'>UF</td><td><b>%s</b></td></tr>"
            "<tr><td style='color:#888'>Período</td><td><b>%s</b></td>"
            "<td style='color:#888;padding-left:24px'>Layout</td>"
            "<td colspan='3'><b>%s</b></td></tr>"
            "</table>"
            % (nome, tipo, "%s v%s" % (APP_NAME, __version__),
               cnpj_fmt, ie or "—", uf or "—", periodo, doc.layout))
        cab.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(cab)

        meta = QLabel(
            "<span style='color:#888'>Arquivo:</span> %s &nbsp;&nbsp;"
            "<span style='color:#888'>Modificado em:</span> %s &nbsp;&nbsp;"
            "<span style='color:#888'>Total de registros:</span> "
            "<b>%d</b>" % (nome_arq, mod, len(doc.registros)))
        meta.setTextFormat(Qt.TextFormat.RichText)
        meta.setWordWrap(True)
        lay.addWidget(meta)

        # contagem por tipo de registro
        from collections import Counter
        cont = Counter(r.reg for r in doc.registros)
        nomes_bloco = {
            "0": "Abertura", "A": "Serviços", "B": "ISS",
            "C": "Mercadorias", "D": "Transporte/Serviços", "E": "Apuração",
            "F": "Demais", "G": "CIAP", "H": "Inventário", "I": "Outras",
            "K": "Produção", "M": "PIS/COFINS", "P": "Previdenciária",
            "1": "Outras", "9": "Controle",
        }
        tab = QTableWidget(len(cont), 4)
        tab.setHorizontalHeaderLabels(["Bloco", "Registro", "Descrição bloco",
                                       "Quantidade"])
        tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tab.verticalHeader().setVisible(False)
        for i, reg in enumerate(sorted(cont)):
            vals = [reg[0], reg, nomes_bloco.get(reg[0], ""), str(cont[reg])]
            for j, val in enumerate(vals):
                it = QTableWidgetItem(val)
                if j == 3:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                        | Qt.AlignmentFlag.AlignVCenter)
                tab.setItem(i, j, it)
        tab.resizeColumnsToContents()
        tab.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(QLabel("<b>Contagem de registros</b>"))
        lay.addWidget(tab, 1)


# ---------------------------------------------------------------------------
# Diálogo de revisão de erros
# ---------------------------------------------------------------------------
class DialogoRevisao(QDialog):
    """Lista os problemas encontrados; duplo-clique navega até o registro."""

    COLS = ["Bloco", "Registro", "Regra", "Descrição"]

    def __init__(self, problemas, resumo, ir_callback, parent=None):
        super().__init__(parent)
        self.problemas = problemas
        self.ir_callback = ir_callback
        self.setWindowTitle("Revisão de erros")
        self.resize(820, 520)
        lay = QVBoxLayout(self)

        total = len(problemas)
        partes = "  |  ".join("%s: %d" % (rot, n) for rot, n in resumo)
        lbl = QLabel("%d ocorrência(s).   %s" % (total, partes))
        lbl.setStyleSheet("color:#0a0; font-weight:bold;" if total == 0
                          else "color:#b00; font-weight:bold;")
        lay.addWidget(lbl)
        dica = QLabel("Dê duplo-clique numa linha para ir ao registro.")
        dica.setStyleSheet("color:#666;")
        lay.addWidget(dica)

        self.tab = QTableWidget(total, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.verticalHeader().setVisible(False)
        for i, p in enumerate(problemas):
            vals = [p.bloco, p.reg, p.regra, p.descricao]
            for j, val in enumerate(vals):
                it = QTableWidgetItem(val)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, p.uid)
                self.tab.setItem(i, j, it)
        self.tab.resizeColumnsToContents()
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        b_ir = QPushButton("Ir para o registro")
        b_ir.clicked.connect(self._ir_selecionado)
        b_ir.setEnabled(total > 0)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.close)
        botoes.addWidget(b_ir)
        botoes.addWidget(b_fechar)
        lay.addLayout(botoes)

    def _ir(self, row, _col):
        it = self.tab.item(row, 0)
        if it is not None:
            uid = it.data(Qt.ItemDataRole.UserRole)
            self.ir_callback(uid)

    def _ir_selecionado(self):
        row = self.tab.currentRow()
        if row >= 0:
            self._ir(row, 0)


# ---------------------------------------------------------------------------
# Editor das correlações de CFOP (saída do fornecedor -> entrada do comprador)
# ---------------------------------------------------------------------------
class DialogoCorrelacoesCFOP(QDialog):
    """Tabela editável de CFOP de saída -> CFOPs de entrada válidos.

    Persiste em JSON (via conferencia.salvar_correlacoes) e devolve o novo
    mapa pelo callback `on_salvar`."""

    def __init__(self, mapa, caminho, on_salvar, parent=None):
        super().__init__(parent)
        self.caminho = caminho
        self.on_salvar = on_salvar
        self.setWindowTitle("Correlações de CFOP — entradas (NF-e 55)")
        self.resize(560, 560)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Para cada <b>CFOP de saída</b> do fornecedor (5xxx/6xxx), informe "
            "os <b>CFOPs de entrada</b> válidos no SPED (1xxx/2xxx), separados "
            "por vírgula.<br>Ex.: <b>5403</b> → <b>1401, 1403</b>. Itens cujo "
            "CFOP de entrada não estiver na lista são apontados na conferência.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(info)

        self.tab = QTableWidget(0, 2)
        self.tab.setHorizontalHeaderLabels(
            ["CFOP saída (fornecedor)", "CFOPs entrada válidos"])
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.verticalHeader().setVisible(False)
        lay.addWidget(self.tab, 1)
        self._preencher(mapa)

        linha_btn = QHBoxLayout()
        b_add = QPushButton("➕ Adicionar")
        b_add.clicked.connect(self._adicionar)
        b_del = QPushButton("➖ Remover")
        b_del.clicked.connect(self._remover)
        b_padrao = QPushButton("Restaurar padrão")
        b_padrao.clicked.connect(self._restaurar)
        linha_btn.addWidget(b_add)
        linha_btn.addWidget(b_del)
        linha_btn.addWidget(b_padrao)
        linha_btn.addStretch(1)
        lay.addLayout(linha_btn)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        b_salvar = QPushButton("Salvar")
        b_salvar.clicked.connect(self._salvar)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.reject)
        rodape.addWidget(b_salvar)
        rodape.addWidget(b_fechar)
        lay.addLayout(rodape)

    def _preencher(self, mapa):
        self.tab.setRowCount(0)
        for cfop in sorted(mapa):
            destinos = ", ".join(sorted(mapa[cfop]))
            self._nova_linha(cfop, destinos)

    def _nova_linha(self, saida="", entrada=""):
        i = self.tab.rowCount()
        self.tab.insertRow(i)
        self.tab.setItem(i, 0, QTableWidgetItem(saida))
        self.tab.setItem(i, 1, QTableWidgetItem(entrada))

    def _adicionar(self):
        self._nova_linha()
        self.tab.scrollToBottom()
        self.tab.editItem(self.tab.item(self.tab.rowCount() - 1, 0))

    def _remover(self):
        linhas = sorted({i.row() for i in self.tab.selectedItems()},
                        reverse=True)
        for r in linhas:
            self.tab.removeRow(r)

    def _restaurar(self):
        if QMessageBox.question(
                self, "Restaurar padrão",
                "Substituir a tabela atual pelas correlações padrão?") \
                == QMessageBox.StandardButton.Yes:
            self._preencher(cf.normalizar_correlacoes(
                cf.CORRELACOES_CFOP_PADRAO))

    def _coletar(self):
        d = {}
        for i in range(self.tab.rowCount()):
            s = self.tab.item(i, 0)
            e = self.tab.item(i, 1)
            saida = s.text() if s else ""
            entrada = e.text() if e else ""
            if saida.strip():
                d[saida] = entrada
        return cf.normalizar_correlacoes(d)

    def _salvar(self):
        mapa = self._coletar()
        try:
            cf.salvar_correlacoes(mapa, self.caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Salvar",
                                 "Não foi possível gravar:\n%s" % exc)
            return
        self.on_salvar(mapa)
        QMessageBox.information(
            self, "Correlações de CFOP",
            "Correlações salvas (%d CFOP de saída)." % len(mapa))
        self.accept()


# ---------------------------------------------------------------------------
# Diálogo: trocar alíquotas de PIS/COFINS (C175) e recalcular
# ---------------------------------------------------------------------------
class DialogoTrocarAliquotas(QDialog):
    """Pede as novas alíquotas de PIS/COFINS e recalcula (saídas/entradas)."""

    ESCOPOS = [("Saídas — débito (C175 + C170 de saída)", "saidas"),
               ("Entradas — crédito (C170)", "entradas"),
               ("Todos os itens (C170 e C175)", "todos")]

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Trocar alíquotas de PIS/COFINS")
        self.resize(480, 360)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Define novas alíquotas de PIS e COFINS e recalcula VL_PIS e "
            "VL_COFINS (base × alíquota), atualizando os totais dos C100. O "
            "escopo escolhe onde aplicar: saídas (C175 e C170 de saída), "
            "entradas (C170) ou todos os itens.")
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QFormLayout()
        self.combo_escopo = QComboBox()
        for rotulo, _ in self.ESCOPOS:
            self.combo_escopo.addItem(rotulo)
        self.combo_escopo.currentIndexChanged.connect(self._atualizar_sugestao)
        form.addRow("Aplicar em:", self.combo_escopo)

        self.sp_pis = QDoubleSpinBox()
        self.sp_pis.setDecimals(4)
        self.sp_pis.setRange(0, 100)
        self.sp_pis.setSuffix(" %")
        self.sp_cof = QDoubleSpinBox()
        self.sp_cof.setDecimals(4)
        self.sp_cof.setRange(0, 100)
        self.sp_cof.setSuffix(" %")
        self.chk_pis = QCheckBox("Alterar PIS")
        self.chk_pis.setChecked(True)
        self.chk_cof = QCheckBox("Alterar COFINS")
        self.chk_cof.setChecked(True)
        self.chk_pis.toggled.connect(self.sp_pis.setEnabled)
        self.chk_cof.toggled.connect(self.sp_cof.setEnabled)
        form.addRow(self.chk_pis, self.sp_pis)
        form.addRow(self.chk_cof, self.sp_cof)
        lay.addLayout(form)

        self.chk_trib = QCheckBox(
            "Somente registros tributados (base ou alíquota > 0)")
        self.chk_trib.setChecked(True)
        lay.addWidget(self.chk_trib)

        # filtro opcional: só corrigir onde a alíquota ATUAL for exatamente X
        self.chk_de = QCheckBox(
            "Trocar apenas onde a alíquota atual for:")
        lay.addWidget(self.chk_de)
        form_de = QFormLayout()
        self.sp_de_pis = QDoubleSpinBox()
        self.sp_de_pis.setDecimals(4)
        self.sp_de_pis.setRange(0, 100)
        self.sp_de_pis.setSuffix(" %")
        self.sp_de_cof = QDoubleSpinBox()
        self.sp_de_cof.setDecimals(4)
        self.sp_de_cof.setRange(0, 100)
        self.sp_de_cof.setSuffix(" %")
        self.sp_de_pis.setEnabled(False)
        self.sp_de_cof.setEnabled(False)
        self.chk_de.toggled.connect(self.sp_de_pis.setEnabled)
        self.chk_de.toggled.connect(self.sp_de_cof.setEnabled)
        form_de.addRow("PIS atual =", self.sp_de_pis)
        form_de.addRow("COFINS atual =", self.sp_de_cof)
        lay.addLayout(form_de)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        b_ok = QPushButton("Aplicar e recalcular")
        b_ok.clicked.connect(self.accept)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.reject)
        botoes.addWidget(b_ok)
        botoes.addWidget(b_cancel)
        lay.addLayout(botoes)

        self._atualizar_sugestao()

    def _atualizar_sugestao(self):
        """Pré-preenche com a alíquota predominante do escopo selecionado."""
        escopo = self.ESCOPOS[self.combo_escopo.currentIndex()][1]
        base = "entradas" if escopo == "entradas" else "saidas"
        ap = self.doc.aliquota_predominante("ALIQ_PIS", base) or 1.65
        ac = self.doc.aliquota_predominante("ALIQ_COFINS", base) or 7.6
        self.sp_pis.setValue(ap)
        self.sp_cof.setValue(ac)

    def valores(self):
        """(aliq_pis, aliq_cofins, apenas_trib, escopo, de_pis, de_cofins)."""
        ap = self.sp_pis.value() if self.chk_pis.isChecked() else None
        ac = self.sp_cof.value() if self.chk_cof.isChecked() else None
        escopo = self.ESCOPOS[self.combo_escopo.currentIndex()][1]
        de_pis = de_cof = None
        if self.chk_de.isChecked():
            de_pis = self.sp_de_pis.value()
            de_cof = self.sp_de_cof.value()
        return ap, ac, self.chk_trib.isChecked(), escopo, de_pis, de_cof


# ---------------------------------------------------------------------------
# Diálogo: verificar CST de PIS/COFINS por NCM (tabelas RFB)
# ---------------------------------------------------------------------------
class DialogoVerificarCST(QDialog):
    """Configura as tabelas da RFB (alíquota zero, monofásicos, gênero e, opc.,
    NCM vigente) e verifica o CST de PIS/COFINS dos itens C170 por NCM."""

    def __init__(self, doc, cfg, data_ref, on_cfg, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.cfg = dict(cfg or {})
        self.on_cfg = on_cfg
        self.setWindowTitle("Verificar CST de PIS/COFINS por NCM")
        self.resize(880, 620)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Classifica cada item (C170) pelo NCM usando as tabelas oficiais da "
            "RFB e aponta CST de PIS/COFINS incoerentes (ex.: entrada de produto "
            "monofásico com crédito, ou produto de alíquota zero tributado). O "
            "C175 (NFC-e consolidada) não é verificável por NCM.")
        info.setWordWrap(True)
        lay.addWidget(info)

        cfgbox = QGroupBox("Tabelas (pasta do PVA ou caminhos diretos)")
        gl = QGridLayout(cfgbox)

        def linha_arquivo(rot, chave, lin, pasta=False):
            gl.addWidget(QLabel(rot), lin, 0)
            ed = QLineEdit(self.cfg.get(chave, ""))
            gl.addWidget(ed, lin, 1)
            b = QPushButton("…")
            b.setMaximumWidth(32)
            if pasta:
                b.clicked.connect(lambda: self._pasta(ed))
            else:
                b.clicked.connect(lambda: self._arquivo(ed))
            gl.addWidget(b, lin, 2)
            return ed

        self.ed_pasta = linha_arquivo("Pasta das tabelas:", "pasta", 0, True)
        if not self.ed_pasta.text():
            self.ed_pasta.setText(trfb.PASTA_PADRAO)
        self.ed_zero = linha_arquivo("Alíquota zero (opcional):", "zero", 1)
        self.ed_mono = linha_arquivo("Monofásicos (opcional):", "mono", 2)
        self.ed_genero = linha_arquivo("Gênero (opcional):", "genero", 3)
        self.ed_ncm = linha_arquivo("NCM vigente XLSX (opc.):", "ncm", 4)

        gl.addWidget(QLabel("Data de referência:"), 5, 0)
        self.ed_data = QLineEdit(data_ref or "")
        self.ed_data.setPlaceholderText("DDMMAAAA")
        self.ed_data.setMaximumWidth(120)
        gl.addWidget(self.ed_data, 5, 1)
        lay.addWidget(cfgbox)

        acoes = QHBoxLayout()
        b_ver = QPushButton("Verificar")
        b_ver.clicked.connect(self._verificar)
        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(self._exportar)
        self.lbl = QLabel("—")
        acoes.addWidget(b_ver)
        acoes.addWidget(b_csv)
        acoes.addStretch(1)
        acoes.addWidget(self.lbl)
        lay.addLayout(acoes)

        self.COLS = ["Operação", "COD_ITEM", "NCM", "Gênero", "Classificação",
                     "CST PIS", "CST COFINS", "CST sugerido", "Observação"]
        self.tab = QTableWidget(0, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True)
        self.tab.setSortingEnabled(True)
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)
        self._uids = []

    def _pasta(self, ed):
        d = QFileDialog.getExistingDirectory(self, "Pasta das tabelas",
                                             ed.text() or "")
        if d:
            ed.setText(d)

    def _arquivo(self, ed):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo",
                                           ed.text() or "")
        if f:
            ed.setText(f)

    def _coletar_cfg(self):
        return {"pasta": self.ed_pasta.text().strip(),
                "zero": self.ed_zero.text().strip(),
                "mono": self.ed_mono.text().strip(),
                "genero": self.ed_genero.text().strip(),
                "ncm": self.ed_ncm.text().strip()}

    def _verificar(self):
        cfg = self._coletar_cfg()
        try:
            clf, achados = trfb.carregar_tudo(
                pasta=cfg["pasta"] or None,
                caminho_zero=cfg["zero"] or None,
                caminho_mono=cfg["mono"] or None,
                caminho_genero=cfg["genero"] or None,
                caminho_ncm=cfg["ncm"] or None)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Tabelas",
                                 "Falha ao carregar as tabelas:\n%s" % exc)
            return
        if not achados.get("zero") and not achados.get("mono"):
            QMessageBox.warning(
                self, "Tabelas",
                "Não encontrei as tabelas de alíquota zero/monofásicos na pasta "
                "informada. Verifique o caminho ou informe os arquivos "
                "diretamente.")
            return
        self.on_cfg(cfg)
        probs = trfb.verificar_cst_pis_cofins(
            self.doc, clf, data_ref=self.ed_data.text().strip() or None)
        self._preencher(probs)
        self.lbl.setText(
            "%d divergência(s) · tabelas: zero v%s, mono v%s"
            % (len(probs), clf.versao_zero, clf.versao_mono))

    def _preencher(self, probs):
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(len(probs))
        self._uids = []
        for i, p in enumerate(probs):
            self._uids.append(p["uid"])
            vals = ["Entrada" if p["op"] == "E" else "Saída", p["cod_item"],
                    p["ncm"], "%s %s" % (p["genero"], p["genero_desc"]),
                    p["classe_desc"], p["cst_pis"], p["cst_cofins"],
                    p["cst_sugerido"], p["detalhe"]]
            for c, v in enumerate(vals):
                self.tab.setItem(i, c, QTableWidgetItem(str(v)))
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()

    def _ir(self, row, _col):
        if 0 <= row < len(self._uids) and self.parent() is not None:
            self.parent().ir_para_registro(self._uids[row])

    def _exportar(self):
        if self.tab.rowCount() == 0:
            QMessageBox.information(self, "Exportar", "Nada para exportar.")
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar verificação", "verificacao_cst.csv", "CSV (*.csv)")
        if not caminho:
            return
        try:
            with open(caminho, "w", encoding="latin-1", newline="") as fh:
                fh.write(";".join(self.COLS) + "\r\n")
                for r in range(self.tab.rowCount()):
                    fh.write(";".join(
                        (self.tab.item(r, c).text() if self.tab.item(r, c)
                         else "") for c in range(self.tab.columnCount()))
                        + "\r\n")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportar", str(exc))
            return
        QMessageBox.information(self, "Exportar", "Exportado:\n%s" % caminho)


# ---------------------------------------------------------------------------
# Diálogo: alterar datas (emissão/saída) de documentos C100
# ---------------------------------------------------------------------------
class DialogoAlterarDatas(QDialog):
    """Filtra C100 por intervalo de datas (+ modelo e tipo) e altera a data de
    emissão (DT_DOC) e/ou de entrada/saída (DT_E_S)."""

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Alterar datas de emissão/saída (C100)")
        self.resize(480, 430)
        lay = QVBoxLayout(self)

        # ---- filtro -------------------------------------------------------
        g_filtro = QGroupBox("Selecionar documentos (filtro)")
        ff = QFormLayout(g_filtro)
        self.cb_campo_filtro = QComboBox()
        self.cb_campo_filtro.addItems([
            "Data de entrada/saída (DT_E_S)", "Data de emissão (DT_DOC)"])
        self.ed_ini = QLineEdit()
        self.ed_ini.setPlaceholderText("DDMMAAAA")
        self.ed_fim = QLineEdit()
        self.ed_fim.setPlaceholderText("DDMMAAAA")
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(["Todos", "Entrada", "Saída"])
        self.ed_modelos = QLineEdit()
        self.ed_modelos.setPlaceholderText("ex.: 55, 65 — vazio = todos")
        ff.addRow("Filtrar pela:", self.cb_campo_filtro)
        ff.addRow("Data inicial:", self.ed_ini)
        ff.addRow("Data final:", self.ed_fim)
        ff.addRow("Tipo de movimento:", self.cb_tipo)
        ff.addRow("Somente modelos:", self.ed_modelos)
        lay.addWidget(g_filtro)

        # ---- ação ---------------------------------------------------------
        g_acao = QGroupBox("Alterar")
        fa = QFormLayout(g_acao)
        self.cb_campos = QComboBox()
        self.cb_campos.addItems([
            "Data de entrada/saída (DT_E_S)", "Data de emissão (DT_DOC)",
            "Ambas (DT_DOC e DT_E_S)"])
        self.cb_modo = QComboBox()
        self.cb_modo.addItems(["Para data específica", "Deslocar em dias"])
        self.cb_modo.currentIndexChanged.connect(self._modo_mudou)
        self.ed_valor = QLineEdit()
        fa.addRow("Data(s) a alterar:", self.cb_campos)
        fa.addRow("Como:", self.cb_modo)
        fa.addRow("Valor:", self.ed_valor)
        lay.addWidget(g_acao)
        self._modo_mudou()

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_ok = QPushButton("Aplicar")
        b_ok.clicked.connect(self.accept)
        b_c = QPushButton("Cancelar")
        b_c.clicked.connect(self.reject)
        rod.addWidget(b_ok)
        rod.addWidget(b_c)
        lay.addLayout(rod)

    def _modo_mudou(self):
        if self.cb_modo.currentIndex() == 0:
            self.ed_valor.setPlaceholderText("DDMMAAAA")
        else:
            self.ed_valor.setPlaceholderText("dias, ex.: 1 ou -3")

    @staticmethod
    def _data(s):
        from datetime import datetime
        try:
            return datetime.strptime((s or "").strip(), "%d%m%Y").date()
        except ValueError:
            return None

    def valores(self):
        """Valida os campos e devolve os parâmetros para alterar_datas_c100;
        em caso de erro mostra a mensagem e devolve None."""
        di = self._data(self.ed_ini.text()) if self.ed_ini.text().strip() \
            else None
        dfim = self._data(self.ed_fim.text()) if self.ed_fim.text().strip() \
            else None
        if self.ed_ini.text().strip() and di is None:
            QMessageBox.critical(self, "Datas", "Data inicial inválida (DDMMAAAA).")
            return None
        if self.ed_fim.text().strip() and dfim is None:
            QMessageBox.critical(self, "Datas", "Data final inválida (DDMMAAAA).")
            return None
        if di and dfim and di > dfim:
            QMessageBox.critical(self, "Datas",
                                 "Data inicial maior que a final.")
            return None

        campo_filtro = "DT_E_S" if self.cb_campo_filtro.currentIndex() == 0 \
            else "DT_DOC"
        tipo = ["T", "E", "S"][self.cb_tipo.currentIndex()]
        modelos = [x.strip() for x in
                   self.ed_modelos.text().replace(";", ",").split(",")
                   if x.strip()]
        campos = [["DT_E_S"], ["DT_DOC"], ["DT_DOC", "DT_E_S"]][
            self.cb_campos.currentIndex()]

        if self.cb_modo.currentIndex() == 0:
            modo = "especifica"
            valor = self._data(self.ed_valor.text())
            if valor is None:
                QMessageBox.critical(self, "Nova data",
                                     "Informe a nova data (DDMMAAAA).")
                return None
        else:
            modo = "dias"
            try:
                valor = int(self.ed_valor.text().strip())
            except ValueError:
                QMessageBox.critical(self, "Deslocamento",
                                     "Informe um número inteiro de dias.")
                return None

        return {"campo_filtro": campo_filtro, "data_ini": di, "data_fim": dfim,
                "modelos": modelos, "tipo": tipo, "campos_alterar": campos,
                "modo": modo, "valor": valor}


# ---------------------------------------------------------------------------
# Modo Relatório — visão achatada dos itens (C170), com filtros do script SQL
# ---------------------------------------------------------------------------
class RelatorioWidget(QWidget):
    """Mostra os itens do SPED numa tabela achatada (uma linha por C170, com
    dados do C100 e do produto 0200), com os mesmos filtros/campos do relatório
    usado no banco do ERP — para comparação. A tabela é somente-leitura."""

    def __init__(self, doc=None, parent=None):
        super().__init__(parent)
        self.doc = doc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        # ---- seletor de fonte do relatório -------------------------------
        topo = QHBoxLayout()
        topo.addWidget(QLabel("Fonte:"))
        self.cb_fonte = QComboBox()
        self.cb_fonte.addItems([
            "Itens (C170)",
            "PIS/COFINS consolidado (C175) — NFC-e 65",
            "ICMS consolidado (C190) — NFC-e 65",
        ])
        self.cb_fonte.currentIndexChanged.connect(self._fonte_mudou)
        topo.addWidget(self.cb_fonte)
        topo.addStretch(1)
        lay.addLayout(topo)

        # ---- painel de filtros -------------------------------------------
        grupo = QGroupBox("Filtros")
        g = QGridLayout(grupo)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(4)

        def campo(rotulo, w, lin, col, tip=""):
            lb = QLabel(rotulo)
            if tip:
                w.setToolTip(tip)
                lb.setToolTip(tip)
            g.addWidget(lb, lin, col * 2)
            g.addWidget(w, lin, col * 2 + 1)
            return w

        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(["Todos", "Entradas", "Saídas"])
        self.ed_data_ini = QLineEdit()
        self.ed_data_ini.setPlaceholderText("AAAA-MM-DD")
        self.ed_data_fim = QLineEdit()
        self.ed_data_fim.setPlaceholderText("AAAA-MM-DD")
        self.ed_modelo = QLineEdit()
        self.ed_num = QLineEdit()
        self.ed_prod = QLineEdit()
        self.ed_item = QLineEdit()
        self.ed_ncm = QLineEdit()
        self.ed_ncm.setPlaceholderText("prefixo")
        self.ed_cfop = QLineEdit()
        self.ed_cst_icms = QLineEdit()
        self.ed_cst_icms.setPlaceholderText("ex.: 060, 020")
        self.ed_cst_pis = QLineEdit()
        self.ed_cst_pis.setPlaceholderText("ex.: 04, 06")
        self.ed_cst_cofins = QLineEdit()
        self.ed_cst_cofins.setPlaceholderText("ex.: 04, 06")
        self.ed_cst_ipi = QLineEdit()
        self.ed_aliq_pis = QLineEdit()
        self.ed_aliq_cofins = QLineEdit()
        self.ed_aliq_icms = QLineEdit()

        campo("Tipo:", self.cb_tipo, 0, 0)
        campo("Data ini.:", self.ed_data_ini, 0, 1)
        campo("Data fim:", self.ed_data_fim, 0, 2)
        campo("Modelo:", self.ed_modelo, 0, 3)
        campo("Nº nota:", self.ed_num, 1, 0)
        campo("Cód. prod.:", self.ed_prod, 1, 1)
        campo("Nº item:", self.ed_item, 1, 2)
        campo("NCM:", self.ed_ncm, 1, 3)
        campo("CFOP:", self.ed_cfop, 2, 0)
        campo("CST ICMS:", self.ed_cst_icms, 2, 1)
        campo("CST PIS:", self.ed_cst_pis, 2, 2)
        campo("CST COFINS:", self.ed_cst_cofins, 2, 3)
        campo("CST IPI:", self.ed_cst_ipi, 3, 0)
        campo("Alíq. ICMS:", self.ed_aliq_icms, 3, 1)
        campo("Alíq. PIS:", self.ed_aliq_pis, 3, 2)
        campo("Alíq. COFINS:", self.ed_aliq_cofins, 3, 3)
        lay.addWidget(grupo)

        # campos que só se aplicam a certas fontes (habilitados dinamicamente)
        self._especificos = {
            "prod": self.ed_prod, "item": self.ed_item, "ncm": self.ed_ncm,
            "cst_icms": self.ed_cst_icms, "cst_pis": self.ed_cst_pis,
            "cst_cofins": self.ed_cst_cofins, "cst_ipi": self.ed_cst_ipi,
            "aliq_icms": self.ed_aliq_icms, "aliq_pis": self.ed_aliq_pis,
            "aliq_cofins": self.ed_aliq_cofins,
        }
        self._aplic_por_fonte = {
            0: {"prod", "item", "ncm", "cst_icms", "cst_pis", "cst_cofins",
                "cst_ipi", "aliq_pis", "aliq_cofins"},          # C170
            1: {"cst_pis", "cst_cofins", "aliq_pis", "aliq_cofins"},  # C175
            2: {"cst_icms", "aliq_icms"},                       # C190
        }

        # ---- barra de ações ----------------------------------------------
        acoes = QHBoxLayout()
        b_gerar = QPushButton("Gerar relatório")
        b_gerar.clicked.connect(self.gerar)
        b_limpar = QPushButton("Limpar filtros")
        b_limpar.clicked.connect(self._limpar)
        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(self._exportar_csv)
        self.lbl_info = QLabel("—")
        acoes.addWidget(b_gerar)
        acoes.addWidget(b_limpar)
        acoes.addWidget(b_csv)
        acoes.addStretch(1)
        acoes.addWidget(self.lbl_info)
        lay.addLayout(acoes)

        # ---- tabela -------------------------------------------------------
        self.tabela = QTableWidget()
        # tabela editável (como uma "query" do SSMS): as colunas próprias do
        # registro-fonte podem ser editadas; produto/documento/calculadas ficam
        # somente-leitura.
        self.tabela.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSortingEnabled(True)
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems)
        self.tabela.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tabela.itemChanged.connect(self._celula_editada)
        self.tabela.itemSelectionChanged.connect(self._resumo_selecao)
        self._preenchendo = False
        self._uids = []
        self._edit_idx = {}          # índice de coluna -> campo no registro
        lay.addWidget(self.tabela, 1)
        self._fonte_mudou()

    def _resumo_selecao(self):
        itens = self.tabela.selectedItems()
        if len(itens) < 2:
            return
        nums = [n for n in (_num_celula(it.text()) for it in itens)
                if n is not None]
        if len(nums) < 2:
            return
        jan = self.window()
        if jan is not None and hasattr(jan, "statusBar"):
            jan.statusBar().showMessage(
                "Soma: %s     Média: %s     Contagem: %d"
                % (_br(sum(nums)), _br(sum(nums) / len(nums)), len(nums)))

    def _fonte_mudou(self):
        """Habilita apenas os filtros aplicáveis à fonte e regenera (se houver
        documento). Filtros de cabeçalho (tipo, data, modelo, nº nota, CFOP)
        valem para todas as fontes."""
        aplic = self._aplic_por_fonte.get(self.cb_fonte.currentIndex(), set())
        for chave, w in self._especificos.items():
            on = chave in aplic
            w.setEnabled(on)
            if not on:
                w.clear()
        if self.doc:
            self.gerar()

    # -------------------------------------------------------------- API
    def set_doc(self, doc):
        self.doc = doc
        self.tabela.setRowCount(0)
        self.tabela.setColumnCount(0)
        self.lbl_info.setText(
            "Clique em “Gerar relatório”." if doc else "—")

    def _limpar(self):
        for w in (self.ed_data_ini, self.ed_data_fim, self.ed_modelo,
                  self.ed_num, self.ed_prod, self.ed_item, self.ed_ncm,
                  self.ed_cfop, self.ed_cst_icms, self.ed_cst_pis,
                  self.ed_cst_cofins, self.ed_cst_ipi, self.ed_aliq_icms,
                  self.ed_aliq_pis, self.ed_aliq_cofins):
            w.clear()
        self.cb_tipo.setCurrentIndex(0)
        self.gerar()

    def _coletar_filtros(self):
        def txt(w):
            return w.text().strip() or None

        def lista(w):
            t = w.text().strip()
            return [x.strip() for x in t.replace(";", ",").split(",")
                    if x.strip()] or None

        def flt(w):
            t = w.text().strip().replace(",", ".")
            try:
                return float(t) if t else None
            except ValueError:
                return None

        return {
            "tipo": ["T", "E", "S"][self.cb_tipo.currentIndex()],
            "data_ini": (self.ed_data_ini.text().strip().replace("-", "")
                         or None),
            "data_fim": (self.ed_data_fim.text().strip().replace("-", "")
                         or None),
            "modelo": txt(self.ed_modelo), "num_nota": txt(self.ed_num),
            "cod_prod": txt(self.ed_prod), "nitem": txt(self.ed_item),
            "ncm": txt(self.ed_ncm), "cfop": txt(self.ed_cfop),
            "cst_icms": lista(self.ed_cst_icms),
            "cst_pis": lista(self.ed_cst_pis),
            "cst_cofins": lista(self.ed_cst_cofins),
            "cst_ipi": txt(self.ed_cst_ipi),
            "aliq_icms": flt(self.ed_aliq_icms),
            "aliq_pis": flt(self.ed_aliq_pis),
            "aliq_cofins": flt(self.ed_aliq_cofins),
        }

    def gerar(self):
        if not self.doc:
            self.tabela.setRowCount(0)
            self.lbl_info.setText("—")
            return
        filtros = self._coletar_filtros()
        idx = self.cb_fonte.currentIndex()
        if idx == 1:
            cols, linhas, uids, edit = self.doc.itens_relatorio_c175(filtros)
        elif idx == 2:
            cols, linhas, uids, edit = self.doc.itens_relatorio_c190(filtros)
        else:
            cols, linhas, uids, edit = self.doc.itens_relatorio(filtros)
        self._cols = cols
        self._uids = uids
        # mapeia índice de coluna -> campo do registro (colunas editáveis)
        self._edit_idx = {i: edit[c] for i, c in enumerate(cols) if c in edit}
        self._preenchendo = True
        self.tabela.setSortingEnabled(False)
        self.tabela.clear()
        self.tabela.setColumnCount(len(cols))
        self.tabela.setHorizontalHeaderLabels(cols)
        self.tabela.setRowCount(len(linhas))
        cinza = QColor(245, 245, 245)
        for r, linha in enumerate(linhas):
            for c, val in enumerate(linha):
                item = QTableWidgetItem(str(val))
                if c == 0:                           # guarda o uid na linha
                    item.setData(Qt.ItemDataRole.UserRole, uids[r])
                if c not in self._edit_idx:          # coluna somente-leitura
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(cinza)
                self.tabela.setItem(r, c, item)
        self.tabela.setSortingEnabled(True)
        self.tabela.resizeColumnsToContents()
        self._preenchendo = False
        self.lbl_info.setText(
            "%d itens · %d colunas editáveis" % (len(linhas), len(edit)))

    def _celula_editada(self, item):
        """Grava a edição de uma célula editável de volta no registro-fonte."""
        if self._preenchendo:
            return
        col = item.column()
        campo = self._edit_idx.get(col)
        if campo is None:
            return
        row = item.row()
        it0 = self.tabela.item(row, 0)
        uid = it0.data(Qt.ItemDataRole.UserRole) if it0 is not None else None
        if uid is None:
            return
        reg = next((x for x in self.doc.registros if x.uid == uid), None)
        if reg is None:
            return
        i_campo = self.doc._ix(reg.reg, campo)
        if i_campo is None:
            return
        reg.set_valor(i_campo, item.text().strip())
        jan = self.window()
        if jan is not None and hasattr(jan, "_marcar_alterado"):
            jan._marcar_alterado()
        if jan is not None and hasattr(jan, "statusBar"):
            jan.statusBar().showMessage(
                "%s do %s atualizado para “%s”."
                % (campo, reg.reg, item.text().strip()))

    def _exportar_csv(self):
        if self.tabela.rowCount() == 0:
            QMessageBox.information(self, "Exportar CSV",
                                    "Gere o relatório antes de exportar.")
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar relatório", "relatorio_sped.csv",
            "CSV (*.csv)")
        if not caminho:
            return
        cols = getattr(self, "_cols", [])
        try:
            with open(caminho, "w", encoding="latin-1", newline="") as fh:
                fh.write(";".join(cols) + "\r\n")
                for r in range(self.tabela.rowCount()):
                    vals = []
                    for c in range(self.tabela.columnCount()):
                        it = self.tabela.item(r, c)
                        vals.append(it.text() if it else "")
                    fh.write(";".join(vals) + "\r\n")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportar CSV", str(exc))
            return
        QMessageBox.information(self, "Exportar CSV",
                                "Relatório exportado:\n%s" % caminho)


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------
class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        # Carrega o ícone da janela
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "icon.ico")
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.doc = None
        self.caminho = None
        self.alterado = False
        self._offset_blocos = 0
        self._blocos = []
        # ordem de abas escolhida por arrasto (só durante a sessão)
        self._ger_abas = GerenciadorOrdemAbas()
        self.resize(1200, 760)

        # correlações de CFOP (saída -> entradas válidas), persistidas em JSON
        self._caminho_correl = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "correlacoes_cfop.json")
        self.correlacoes_cfop = cf.carregar_correlacoes(self._caminho_correl)

        # configuração das tabelas da RFB (verificação de CST por NCM)
        self._caminho_cfg_tabelas = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config_tabelas_rfb.json")
        self.cfg_tabelas = self._carregar_cfg_tabelas()

        # Carrega o layout do Qt Designer (sped_editor.ui) quando presente;
        # caso contrário, constrói a interface programaticamente (fallback).
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "sped_editor.ui")
        self._modo_ui = False
        if os.path.exists(ui_path):
            try:
                from PyQt6 import uic
                uic.loadUi(ui_path, self)
                self._modo_ui = True
            except Exception:  # noqa: BLE001
                self._modo_ui = False

        if self._modo_ui:
            self._conectar_ui()
        else:
            self._criar_acoes()
            self._criar_barra()
            self.tabs_bloco = QTabWidget()
            self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
            self.tabs_bloco.currentChanged.connect(self._bloco_aberto)
            self.setCentralWidget(self.tabs_bloco)
            self.setStatusBar(QStatusBar())

        self._montar_modo_topo()
        self.setWindowTitle("%s v%s" % (APP_NAME, __version__))
        self.statusBar().showMessage("Pronto. Abra um arquivo SPED (Ctrl+O).")

    def _montar_modo_topo(self):
        """Envolve as grades num QTabWidget de nível superior com dois modos:
        'Modo Tabela' (as abas de bloco atuais) e 'Modo Relatório' (visão
        achatada dos itens para comparação com o banco)."""
        self.tabs_topo = QTabWidget()
        self.tabs_topo.setTabPosition(QTabWidget.TabPosition.North)
        # Modo Tabela: reparenta o tabs_bloco para dentro de um container
        cont_tabela = QWidget()
        lt = QVBoxLayout(cont_tabela)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.addWidget(self.tabs_bloco)
        self.tabs_topo.addTab(cont_tabela, "📋 Modo Tabela")
        # Modo Relatório
        self.relatorio = RelatorioWidget()
        self.tabs_topo.addTab(self.relatorio, "📊 Modo Relatório")
        self.setCentralWidget(self.tabs_topo)

    def _conectar_ui(self):
        """Liga as QActions e widgets carregados do .ui aos slots."""
        self.act_abrir.setShortcut(QKeySequence.StandardKey.Open)
        self.act_abrir.triggered.connect(self.abrir)
        self.act_salvar.setShortcut(QKeySequence.StandardKey.Save)
        self.act_salvar.triggered.connect(self.salvar)
        self.act_salvar.setEnabled(False)
        self.act_salvar_como.triggered.connect(self.salvar_como)
        self.act_salvar_como.setEnabled(False)
        if hasattr(self, "act_sair"):
            self.act_sair.triggered.connect(self.close)
        self.act_importar_xml.triggered.connect(self.importar_xml_c175)
        self.act_importar_xml.setEnabled(False)
        self.act_recalc_m.triggered.connect(self.recalcular_bloco_m)
        self.act_recalc_m.setEnabled(False)
        self.act_conferir_55.triggered.connect(self.conferir_entradas_55)
        self.act_conferir_55.setEnabled(False)
        self.act_revisar.triggered.connect(self.revisar_erros)
        self.act_revisar.setEnabled(False)
        # ações que podem não vir num .ui antigo são criadas aqui
        if not hasattr(self, "act_conferir_c190"):
            self.act_conferir_c190 = QAction(
                "Conferir C190 (ICMS) com XMLs…", self)
        self.act_conferir_c190.triggered.connect(self.conferir_c190_xml)
        self.act_conferir_c190.setEnabled(False)
        if not hasattr(self, "act_correlacoes_cfop"):
            self.act_correlacoes_cfop = QAction(
                "Correlações de CFOP (entradas)…", self)
        self.act_correlacoes_cfop.triggered.connect(
            self.editar_correlacoes_cfop)
        if not hasattr(self, "act_trocar_aliquotas"):
            self.act_trocar_aliquotas = QAction(
                "Trocar alíquotas PIS/COFINS…", self)
        self.act_trocar_aliquotas.triggered.connect(self.trocar_aliquotas)
        self.act_trocar_aliquotas.setEnabled(False)
        if not hasattr(self, "act_alterar_datas"):
            self.act_alterar_datas = QAction(
                "Alterar datas emissão/saída (C100)…", self)
        self.act_alterar_datas.triggered.connect(self.alterar_datas)
        self.act_alterar_datas.setEnabled(False)
        if not hasattr(self, "act_verificar_cst"):
            self.act_verificar_cst = QAction(
                "Verificar CST por NCM (tabelas RFB)…", self)
        self.act_verificar_cst.triggered.connect(self.verificar_cst_ncm)
        self.act_verificar_cst.setEnabled(False)
        # a barra de menus é redundante com a toolbar: ocultar
        if hasattr(self, "menubar") and self.menubar is not None:
            self.menubar.setVisible(False)
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs_bloco.currentChanged.connect(self._bloco_aberto)
        # botão "Ferramentas" na toolbar (ao lado de Salvar como)
        tb = getattr(self, "toolbar", None)
        if tb is None:
            tb = QToolBar("Principal")
            tb.setMovable(False)
            self.addToolBar(tb)
            self.toolbar = tb
        self._montar_botao_ferramentas(tb)

    def _montar_botao_ferramentas(self, toolbar):
        """Cria o botão suspenso 'Ferramentas' e o posiciona na toolbar."""
        menu = QMenu(self)
        menu.addAction(self.act_importar_xml)
        menu.addAction(self.act_recalc_m)
        menu.addAction(self.act_trocar_aliquotas)
        menu.addAction(self.act_alterar_datas)
        menu.addSeparator()
        menu.addAction(self.act_conferir_55)
        menu.addAction(self.act_conferir_c190)
        menu.addAction(self.act_correlacoes_cfop)
        menu.addAction(self.act_verificar_cst)
        menu.addSeparator()
        menu.addAction(self.act_revisar)
        botao = QToolButton(self)
        botao.setText("Ferramentas ▾")
        botao.setMenu(menu)
        botao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        botao.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.addSeparator()
        toolbar.addWidget(botao)
        self._botao_ferramentas = botao

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

        self.act_importar_xml = QAction(
            "Importar XMLs → consolidar C175…", self)
        self.act_importar_xml.triggered.connect(self.importar_xml_c175)
        self.act_importar_xml.setEnabled(False)

        self.act_recalc_m = QAction("Recalcular bloco M (apuração)…", self)
        self.act_recalc_m.triggered.connect(self.recalcular_bloco_m)
        self.act_recalc_m.setEnabled(False)

        self.act_trocar_aliquotas = QAction(
            "Trocar alíquotas PIS/COFINS…", self)
        self.act_trocar_aliquotas.triggered.connect(self.trocar_aliquotas)
        self.act_trocar_aliquotas.setEnabled(False)

        self.act_alterar_datas = QAction(
            "Alterar datas emissão/saída (C100)…", self)
        self.act_alterar_datas.triggered.connect(self.alterar_datas)
        self.act_alterar_datas.setEnabled(False)

        self.act_verificar_cst = QAction(
            "Verificar CST por NCM (tabelas RFB)…", self)
        self.act_verificar_cst.triggered.connect(self.verificar_cst_ncm)
        self.act_verificar_cst.setEnabled(False)

        self.act_conferir_55 = QAction(
            "Conferir entradas (NF-e 55) com XMLs…", self)
        self.act_conferir_55.triggered.connect(self.conferir_entradas_55)
        self.act_conferir_55.setEnabled(False)

        self.act_conferir_c190 = QAction(
            "Conferir C190 (ICMS) com XMLs…", self)
        self.act_conferir_c190.triggered.connect(self.conferir_c190_xml)
        self.act_conferir_c190.setEnabled(False)

        self.act_revisar = QAction("Revisar erros…", self)
        self.act_revisar.triggered.connect(self.revisar_erros)
        self.act_revisar.setEnabled(False)

        self.act_correlacoes_cfop = QAction(
            "Correlações de CFOP (entradas)…", self)
        self.act_correlacoes_cfop.triggered.connect(
            self.editar_correlacoes_cfop)

    def _criar_barra(self):
        # sem barra de menus (redundante com a toolbar); apenas a toolbar
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.toolbar = tb
        tb.addAction(self.act_abrir)
        tb.addAction(self.act_salvar)
        tb.addAction(self.act_salvar_como)
        self._montar_botao_ferramentas(tb)

    def importar_xml_c175(self):
        """Importa XMLs de NFC-e (modelo 65) de uma pasta e consolida os C175
        dos C100 correspondentes (vínculo por mod + série + nNF)."""
        if not self.doc or self.doc.layout != "CONTRIB":
            QMessageBox.information(
                self, "Importar XMLs",
                "A consolidação de C175 a partir de XMLs aplica-se ao "
                "EFD Contribuições.")
            return
        pasta = QFileDialog.getExistingDirectory(
            self, "Selecione a pasta com os XMLs das NFC-e")
        if not pasta:
            return
        try:
            nfes, erros = xf.ler_pasta(pasta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Importar XMLs",
                                 "Erro ao ler a pasta:\n%s" % e)
            return
        if not nfes:
            QMessageBox.warning(
                self, "Importar XMLs",
                "Nenhum XML de NF-e/NFC-e válido foi encontrado na pasta.")
            return

        from sped_layouts import campos
        cols = campos("C100", self.doc.layout, 30)
        i_mod = cols.index("COD_MOD")
        i_ser = cols.index("SER")
        i_num = cols.index("NUM_DOC")
        c100s = [r for r in self.doc.registros if r.reg == "C100"]

        def ch_c100(r):
            return (xf.norm(r.valor(i_mod)), xf.norm(r.valor(i_ser)),
                    xf.norm(r.valor(i_num)))

        # apenas NFC-e (modelo 65) geram C175
        nfes65 = [n for n in nfes if xf.norm(n.mod) == "65"]
        n55 = sum(1 for n in nfes if xf.norm(n.mod) == "55")
        pares, so_xml, _ = xf.vincular(nfes65, xf.chave_doc, c100s, ch_c100)

        n_doc = n_c175 = 0
        for nfe, casados in pares:
            res = self.doc.consolidar_c175_de_itens(casados[0], nfe.itens)
            if res and not res.get("sem_itens"):
                n_doc += 1
                n_c175 += res["criados"]

        if n_doc:
            self._marcar_alterado()
            self._montar_abas()

        msg = ("Importação concluída:\n\n"
               "• %d XML(s) lido(s)  —  NFC-e (65): %d, NF-e (55): %d\n"
               "• %d documento(s) C100 consolidados\n"
               "• %d registro(s) C175 gerados\n"
               % (len(nfes), len(nfes65), n55, n_doc, n_c175))
        if so_xml:
            msg += "• %d NFC-e sem C100 correspondente no SPED\n" % len(so_xml)
        if n55:
            msg += ("• %d NF-e modelo 55 ignoradas (usam C170, não C175)\n"
                    % n55)
        if erros:
            msg += "• %d arquivo(s) com erro de leitura\n" % len(erros)
        msg += ("\nVL_PIS/VL_COFINS dos C100 e os totais (C990/9900) foram "
                "atualizados.")
        self.statusBar().showMessage(
            "Importação de XMLs: %d C100 consolidados, %d C175 gerados."
            % (n_doc, n_c175))
        QMessageBox.information(self, "Importar XMLs", msg)

    def recalcular_bloco_m(self):
        """Recalcula a apuração do bloco M (M200/M210 e M600/M610) conforme o
        regime declarado no registro 0110."""
        if not self.doc or self.doc.layout != "CONTRIB":
            QMessageBox.information(
                self, "Bloco M",
                "A apuração do bloco M aplica-se ao EFD Contribuições.")
            return
        res = self.doc.recalcular_bloco_m()
        if not res:
            QMessageBox.warning(self, "Bloco M",
                                "Não foi possível recalcular o bloco M.")
            return
        self._marcar_alterado()
        self._montar_abas()

        def linha(t, d):
            if isinstance(d, dict):
                return ("• %s: apurado R$ %s  |  a recolher R$ %s"
                        % (t, _br(d["apurado"]), _br(d["a_recolher"])))
            return "• %s: %s" % (t, d)

        msg = ("Apuração recalculada — regime %s.\n\n%s\n%s\n\n"
               "As bases e contribuições foram somadas das receitas "
               "tributadas de saída (C175/C170) por alíquota.\n\n"
               "Observação: os créditos (M100/M105/M500/M505) são "
               "preservados e apenas descontados na consolidação; "
               "este recálculo não recompõe os créditos."
               % (res.get("regime", "?"),
                  linha("PIS", res.get("PIS", "—")),
                  linha("COFINS", res.get("COFINS", "—"))))
        self.statusBar().showMessage("Bloco M recalculado (regime %s)."
                                     % res.get("regime", "?"))
        QMessageBox.information(self, "Bloco M", msg)

    def conferir_entradas_55(self):
        """Confere os itens das NF-e modelo 55 (entradas) de uma pasta de XMLs
        contra os C170 do SPED, vinculando por mod + série + nNF + nItem."""
        if not self.doc:
            return
        pasta = QFileDialog.getExistingDirectory(
            self, "Selecione a pasta com os XMLs das NF-e (modelo 55)")
        if not pasta:
            return
        try:
            nfes, erros = xf.ler_pasta(pasta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Conferir entradas",
                                 "Erro ao ler a pasta:\n%s" % e)
            return
        if not any(xf.norm(n.mod) == "55" for n in nfes):
            QMessageBox.warning(
                self, "Conferir entradas",
                "Nenhum XML de NF-e modelo 55 foi encontrado na pasta.")
            return
        resultado = cf.conferir_entradas_55(
            self.doc, nfes, correlacoes_cfop=self.correlacoes_cfop)
        self.statusBar().showMessage(
            "Conferência: %d itens, %d divergência(s)."
            % (resultado["resumo"]["itens_conferidos"],
               resultado["resumo"]["divergencias"]))
        DialogoConferencia(resultado, self).exec()

    def conferir_c190_xml(self):
        """Compara os C190 (ICMS analítico) com os XMLs, agrupando os itens do
        XML pela classificação do C170 (CFOP/CST/alíquota de entrada), casada
        por nItem — resolvendo a diferença de CFOP entre XML e SPED."""
        if not self.doc:
            return
        pasta = QFileDialog.getExistingDirectory(
            self, "Selecione a pasta com os XMLs (entradas/saídas)")
        if not pasta:
            return
        try:
            nfes, _erros = xf.ler_pasta(pasta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Conferir C190",
                                 "Erro ao ler a pasta:\n%s" % e)
            return
        if not nfes:
            QMessageBox.warning(self, "Conferir C190",
                                "Nenhum XML encontrado na pasta.")
            return
        resultado = cf.conferir_c190_com_xml(self.doc, nfes)
        r = resultado["resumo"]
        self.statusBar().showMessage(
            "C190 × XML: %d documentos, %d grupos, %d divergência(s)."
            % (r["docs_casados"], r["grupos_conferidos"], r["divergencias"]))
        DialogoConfC190(resultado, self).exec()

    def editar_correlacoes_cfop(self):
        """Abre o editor da tabela de correlações de CFOP (saída -> entrada)."""
        def aplicar(novo_mapa):
            self.correlacoes_cfop = novo_mapa
            self.statusBar().showMessage(
                "Correlações de CFOP atualizadas (%d CFOP de saída)."
                % len(novo_mapa))
        DialogoCorrelacoesCFOP(
            self.correlacoes_cfop, self._caminho_correl, aplicar, self).exec()

    def _carregar_cfg_tabelas(self):
        import json
        try:
            with open(self._caminho_cfg_tabelas, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:  # noqa: BLE001
            return {}

    def _salvar_cfg_tabelas(self, cfg):
        import json
        self.cfg_tabelas = cfg
        try:
            with open(self._caminho_cfg_tabelas, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, ensure_ascii=False, indent=2)
        except Exception:  # noqa: BLE001
            pass

    def _data_fin_doc(self):
        """DT_FIN do registro 0000 (DDMMAAAA), para referência de vigência."""
        if not self.doc:
            return ""
        i = self.doc._ix("0000", "DT_FIN")
        for r in self.doc.registros:
            if r.reg == "0000":
                return (r.valor(i) or "").strip() if i is not None else ""
        return ""

    def verificar_cst_ncm(self):
        """Verifica o CST de PIS/COFINS dos itens C170 por NCM, usando as
        tabelas oficiais da RFB (alíquota zero e monofásicos)."""
        if not self.doc or self.doc.layout != "CONTRIB":
            QMessageBox.information(
                self, "Verificar CST",
                "Esta verificação aplica-se ao EFD Contribuições (CST de "
                "PIS/COFINS por NCM).")
            return
        self._dlg_cst = DialogoVerificarCST(
            self.doc, self.cfg_tabelas, self._data_fin_doc(),
            self._salvar_cfg_tabelas, self)
        self._dlg_cst.show()

    def alterar_datas(self):
        """Altera datas de emissão/saída dos C100 conforme filtro de data."""
        if not self.doc:
            return
        dlg = DialogoAlterarDatas(self.doc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.valores()
        if p is None:
            return
        res = self.doc.alterar_datas_c100(**p)
        self._marcar_alterado()
        self._montar_abas()
        campos = " e ".join(p["campos_alterar"])
        self.statusBar().showMessage(
            "Datas alteradas em %d documento(s) C100 (%s)."
            % (res["c100"], campos))
        QMessageBox.information(
            self, "Alterar datas",
            "%d documento(s) no filtro; %d alterado(s) (%s).%s"
            % (res["no_filtro"], res["c100"], campos,
               ("\n%d sem data válida no campo de filtro." % res["sem_data"])
               if res["sem_data"] else ""))

    def trocar_aliquotas(self):
        """Troca alíquotas de PIS/COFINS (saídas C175 / entradas C170) e
        recalcula os valores."""
        if not self.doc or self.doc.layout != "CONTRIB":
            QMessageBox.information(
                self, "Trocar alíquotas",
                "Esta ferramenta aplica-se ao EFD Contribuições (registros "
                "C175 de saída e C170 de entrada).")
            return
        dlg = DialogoTrocarAliquotas(self.doc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        aliq_pis, aliq_cofins, apenas_trib, escopo, de_pis, de_cof = \
            dlg.valores()
        if aliq_pis is None and aliq_cofins is None:
            return
        res = self.doc.trocar_aliquotas_pis_cofins(
            aliq_pis=aliq_pis, aliq_cofins=aliq_cofins,
            apenas_tributados=apenas_trib, escopo=escopo,
            de_pis=de_pis, de_cofins=de_cof)
        if res.get("sem_alvo"):
            alvo = "C175/C170 de saída" if escopo == "saidas" else \
                ("C170 de entrada" if escopo == "entradas" else "C170/C175")
            QMessageBox.information(
                self, "Trocar alíquotas",
                "Nenhum registro %s foi encontrado neste arquivo." % alvo)
            return
        self._marcar_alterado()
        self._montar_abas()
        rot_escopo = {"saidas": "saídas (C175 + C170)",
                      "entradas": "entradas (C170)",
                      "todos": "todos os itens (C170 e C175)"}[escopo]
        partes = []
        if aliq_pis is not None:
            partes.append("PIS → %s%%" % ("%.4f" % aliq_pis).rstrip("0")
                          .rstrip("."))
        if aliq_cofins is not None:
            partes.append("COFINS → %s%%" % ("%.4f" % aliq_cofins).rstrip("0")
                          .rstrip("."))
        self.statusBar().showMessage(
            "Alíquotas atualizadas em %s (%s): %d registros, %d C100."
            % (rot_escopo, ", ".join(partes), res["itens"], res["c100"]))
        QMessageBox.information(
            self, "Trocar alíquotas",
            "Escopo: %s\n%s\n\n%d registro(s) recalculado(s) em %d "
            "documento(s) C100.\nNovos totais no escopo: VL_PIS = %s, "
            "VL_COFINS = %s\n\nSe necessário, rode 'Recalcular bloco M' para "
            "refletir a apuração."
            % (rot_escopo, ", ".join(partes), res["itens"], res["c100"],
               _br(res["vl_pis"]), _br(res["vl_cofins"])))

    def revisar_erros(self):
        """Executa as regras de revisão e abre o relatório (não-modal, para
        permitir navegar até os registros enquanto a lista fica aberta)."""
        if not self.doc:
            return
        problemas, resumo = rev.revisar(self.doc)
        self._dlg_revisao = DialogoRevisao(
            problemas, resumo, self.ir_para_registro, self)
        self._dlg_revisao.show()
        self.statusBar().showMessage(
            "Revisão: %d ocorrência(s)." % len(problemas))

    def ir_para_registro(self, uid):
        """Navega até o registro de `uid`: abre a aba do bloco, a sub-aba do
        tipo raiz de exibição e desce pela cadeia até o registro alvo.

        A "raiz de exibição" não é o topo absoluto da cadeia .pai, mas o
        ancestral principal mais próximo do alvo (aquele que vira sub-aba de
        topo do bloco). Ex.: para um C190, a raiz é o C100 (não o C001 de
        abertura); o C190 aparece no detalhe do C100.
        """
        if not self.doc:
            return False
        reg = next((r for r in self.doc.registros if r.uid == uid), None)
        if reg is None:
            return False

        # sobe do alvo até o topo, coletando os ancestrais
        sobe = []
        cur = reg
        while cur is not None:
            sobe.append(cur)
            cur = cur.pai
        # raiz de exibição = primeiro ancestral principal (subindo do alvo)
        raiz_idx = next((i for i, r in enumerate(sobe)
                         if SpedDocument._eh_principal(r)), len(sobe) - 1)
        cadeia = list(reversed(sobe[:raiz_idx + 1]))   # [raiz_exib, ..., alvo]
        raiz = cadeia[0]

        blocos = self.doc.blocos()
        if raiz.bloco not in blocos:
            return False
        # localiza a aba pelo widget do bloco (robusto à reordenação)
        alvo = next((w for w in self._blocos if w.bloco == raiz.bloco), None)
        if alvo is None:
            return False
        # garante que o Modo Tabela esteja visível antes de navegar
        if hasattr(self, "tabs_topo"):
            self.tabs_topo.setCurrentIndex(0)
        idx_aba = self.tabs_bloco.indexOf(alvo)
        if idx_aba < 0:
            return False
        self.tabs_bloco.setCurrentIndex(idx_aba)
        self._bloco_aberto(idx_aba)
        md = alvo.widget_do_tipo(raiz.reg)
        if md is None:
            return False
        md.selecionar_uid(raiz.uid)
        for prox in cadeia[1:]:
            sub = md.subwidget_de_tipo(prox.reg)
            if sub is None:
                break
            sub.selecionar_uid(prox.uid)
            md = sub
        self.raise_()
        self.activateWindow()
        return True

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
        self.caminho = caminho
        self.alterado = False
        self._montar_abas()
        self.act_salvar.setEnabled(True)
        self.act_salvar_como.setEnabled(True)
        self.act_importar_xml.setEnabled(doc.layout == "CONTRIB")
        self.act_recalc_m.setEnabled(doc.layout == "CONTRIB")
        self.act_trocar_aliquotas.setEnabled(doc.layout == "CONTRIB")
        self.act_alterar_datas.setEnabled(True)
        self.act_verificar_cst.setEnabled(doc.layout == "CONTRIB")
        self.act_conferir_55.setEnabled(True)
        self.act_conferir_c190.setEnabled(doc.layout == "ICMS")
        self.act_revisar.setEnabled(True)
        nome = os.path.basename(caminho)
        tipo = "EFD Contribuições" if doc.layout == "CONTRIB" \
            else "EFD ICMS/IPI"
        self.setWindowTitle("%s v%s — %s  [%s]"
                            % (APP_NAME, __version__, nome, tipo))
        self.statusBar().showMessage(
            "%s carregado: %d registros, layout %s."
            % (nome, len(doc.registros), tipo))

    def _montar_abas(self):
        # reutiliza o QTabWidget central (criado no __init__ ou vindo do .ui)
        self.tabs_bloco.blockSignals(True)
        self.tabs_bloco.clear()
        self.tabs_bloco.blockSignals(False)

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
        # aba inicial de resumo (cabeçalho + contagem)
        self.tabs_bloco.addTab(
            ResumoWidget(self.doc, self.caminho), "📋 Resumo")
        self._offset_blocos = 1
        ids = ["resumo"]
        for b in self.doc.blocos():
            w = BlocoWidget(self.doc, b, on_change=self._marcar_alterado,
                            gerenciador=self._ger_abas)
            self._blocos.append(w)
            self.tabs_bloco.addTab(w, nomes_bloco.get(b, "Bloco %s" % b))
            ids.append(b)
        # permite reordenar as abas de bloco (persistente na sessão)
        self._ger_abas.registrar(self.tabs_bloco, "blocos", ids)
        self.tabs_bloco.setCurrentIndex(0)
        # atualiza o Modo Relatório com o documento aberto
        if hasattr(self, "relatorio"):
            self.relatorio.set_doc(self.doc)

    def _bloco_aberto(self, idx):
        # robusto à reordenação: usa o widget da aba, não o índice na lista
        w = self.tabs_bloco.widget(idx)
        if isinstance(w, BlocoWidget):
            w.construir()

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
        self.caminho = caminho
        self.alterado = False
        nome = os.path.basename(caminho)
        self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self.statusBar().showMessage("Salvo em %s." % nome)
        QMessageBox.information(
            self, "Salvo",
            "Arquivo salvo com sucesso em\n%s" % caminho)

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

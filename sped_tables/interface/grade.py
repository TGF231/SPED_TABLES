# -*- coding: utf-8 -*-
"""A grade mestre-detalhe: um QTabWidget por bloco, uma sub-aba por registro principal e, embaixo, os filhos do registro selecionado — recursivo."""

from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QSplitter, QStyledItemDelegate, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from sped_tables.dominio import ajuda
from sped_tables.interface import tema
from sped_tables.interface.comum import _br, _num_celula, calcular
from sped_tables.interface.dialogos.ajuda import DialogoAjuda, dica_html
from sped_tables.interface.comum import abrir_janela, informar


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
        self._ordens = {}    # chave de contexto -> [ids na ordem desejada]
        self._fixada = {}    # chave -> id da aba a exibir primeiro ao trocar
        self._fechadas = {}  # chave -> set de ids ocultos até "resetar"

    # -- preferências por contexto (fixar / fechar / resetar) --------------
    def fixar(self, chave, ident):
        """Fixa (ou desfixa, se já fixada) a aba `ident` como a preferida do
        contexto — a que deve aparecer primeiro ao trocar de registro pai."""
        if self._fixada.get(chave) == ident:
            self._fixada.pop(chave, None)
        else:
            self._fixada[chave] = ident

    def fixada(self, chave):
        return self._fixada.get(chave)

    def fechar(self, chave, ident):
        self._fechadas.setdefault(chave, set()).add(ident)

    def fechadas(self, chave):
        return self._fechadas.get(chave, set())

    def resetar(self, chave):
        """Remove ordem, fixação e abas fechadas do contexto."""
        self._ordens.pop(chave, None)
        self._fixada.pop(chave, None)
        self._fechadas.pop(chave, None)

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
        self._idx_cod_part = None     # coluna COD_PART, se houver
        self._idx_cod_mod = None      # coluna COD_MOD, se houver
        self._idx_num_doc = None      # coluna NUM_DOC, se houver
        self._filtro = "TODOS"        # TODOS | ENTRADAS | SAIDAS
        self._filtro_mod = ""         # COD_MOD selecionado ("" = todos)
        self._texto_busca = ""        # texto da pesquisa
        self._dicas = {}              # dica do cabeçalho por (coluna, nome)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- barra de ações da grade ---
        barra = QHBoxLayout()
        self.lbl = QLabel()
        self.lbl.setProperty("role", "info")

        # rótulo central: nome do produto da linha selecionada (grades C170 etc.)
        self.lbl_item = QLabel("")
        self.lbl_item.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_item.setProperty("role", "produto")
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

        # botão de recálculo dos totais do C100 a partir dos itens C170,
        # só na grade de C100
        self.btn_recalc_totais = QPushButton("🔄 Recalcular totais")
        self.btn_recalc_totais.setToolTip(
            "Recalcula os totais do C100 selecionado (mercadorias, desconto, "
            "base e valor de ICMS, ICMS-ST, IPI, PIS/COFINS e VL_DOC) somando "
            "os itens C170")
        self.btn_recalc_totais.clicked.connect(self._recalcular_totais_c100)
        self.btn_recalc_totais.setVisible(self.tipo == "C100")

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
        barra.addWidget(self.btn_recalc_totais)
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
                        (QKeySequence("Ctrl+D"), self._preencher_baixo),
                        (QKeySequence("F1"), self.abrir_ajuda)):
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
        self._idx_cod_part = _idx("COD_PART")
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
        self._dicas_do_cabecalho(colunas)
        self.tabela.setRowCount(len(self._visiveis))

        for i, r in enumerate(self._visiveis):
            for j in range(len(colunas)):
                item = QTableWidgetItem(r.valor(j))
                if j == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setForeground(QColor(tema.atual().info))
                    item.setData(Qt.ItemDataRole.UserRole, r.uid)
                elif j == self._idx_cod_part:
                    # o cadastro inteiro do participante na dica da célula:
                    # a grade mostra "10" e ninguém sabe de quem se trata
                    self._marcar_celula_participante(item)
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
        # Grade de uma linha só: seleciona sozinha para já abrir o detalhe.
        # Sem isso o bloco H parecia vazio — o H005 é um único registro, e os
        # 11 mil H010 só apareciam depois de um clique que nada sugeria. Em
        # grade com várias linhas a seleção continua sendo do usuário, para
        # não deixar uma linha marcada sem querer nas ações em lote.
        if len(self._visiveis) == 1 and self.doc.tem_detalhe(self._visiveis[0]):
            self.tabela.setCurrentCell(0, 0)

    def _dicas_do_cabecalho(self, colunas):
        """A dica de cada coluna é o que o guia prático e o descritor do
        PVA dizem do campo — o "o que vai aqui?" sem sair da grade."""
        for j, nome in enumerate(colunas):
            item = self.tabela.horizontalHeaderItem(j)
            if item is None or nome.startswith("Campo "):
                continue
            # o texto é o mesmo para o registro: monta uma vez por grade, e
            # não a cada tecla da pesquisa (que repreenche a tabela)
            dica = self._dicas.get((j, nome))
            if dica is None:
                dica = self._dicas[(j, nome)] = dica_html(ajuda.do_campo(
                    self.doc.layout, self.tipo, j + 1, nome))
            item.setToolTip(dica)

    def abrir_ajuda(self):
        """F1: a ajuda do registro desta grade, rolada até a coluna atual."""
        col = self.tabela.currentColumn()
        campo = self._colunas[col] if 0 <= col < len(self._colunas) else None
        self._dlg_ajuda = abrir_janela(self, DialogoAjuda(
            self.doc.layout, self.tipo, campo, self))

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
        self.doc.alterar_campo(r, item.column(), item.text())
        if self.on_change:
            self.on_change()
        # editar o COD_ITEM atualiza o nome mostrado no topo
        if item.column() in (self._idx_cod_item, self._idx_cod_part):
            self._atualizar_item_label(r)
            self._marcar_celula_participante(item)
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
        """Mostra, no topo centralizado, o produto (COD_ITEM, ex.: C170) ou o
        participante (COD_PART, ex.: C100) da linha selecionada.

        Os dois códigos apontam para um cadastro do bloco 0 e o problema é o
        mesmo — a grade mostra `10` e ninguém sabe quem é. Quando a grade tem
        os dois campos, o produto tem preferência: é o que mais muda de linha
        para linha.
        """
        texto = ""
        if registro is not None and self._idx_cod_item is not None:
            cod = registro.valor(self._idx_cod_item)
            desc = self.doc.descricao_item(cod)
            if desc:
                texto = "📦  %s — %s" % (cod, desc)
            elif cod:
                texto = "📦  %s — (não cadastrado no 0200)" % cod
        elif registro is not None and self._idx_cod_part is not None:
            texto = self._texto_participante(registro.valor(
                self._idx_cod_part))
        self.lbl_item.setText(texto)
        self.lbl_item.setToolTip(texto)   # caso o nome seja maior que o espaço
        self.lbl_item.setVisible(bool(texto))

    def _marcar_celula_participante(self, item):
        """Põe o cadastro do 0150 na dica da célula de COD_PART.

        Participante não cadastrado fica em cor de aviso: o PVA recusa
        COD_PART que não exista no 0150, e ver isso na própria grade poupa
        uma ida ao validador.
        """
        if item is None:
            return
        cod = (item.text() or "").strip()
        if not cod:
            item.setToolTip("")
            return
        p = self.doc.participante(cod)
        if not p:
            item.setToolTip("Participante %s não está cadastrado no 0150."
                            % cod)
            item.setForeground(QColor(tema.atual().warn))
            return
        linhas = ["<b>%s</b>" % (p.get("NOME") or cod)]
        doc_fmt = self.doc.formatar_doc_participante(p)
        if doc_fmt:
            linhas.append("CNPJ/CPF: %s" % doc_fmt)
        if p.get("IE"):
            linhas.append("IE: %s" % p["IE"])
        end = " ".join(x for x in (p.get("END", ""), p.get("NUM", "")) if x)
        if end:
            linhas.append("Endereço: %s" % end)
        if p.get("BAIRRO"):
            linhas.append("Bairro: %s" % p["BAIRRO"])
        if p.get("COD_MUN"):
            linhas.append("Município (IBGE): %s" % p["COD_MUN"])
        item.setToolTip("<br>".join(linhas))

    def _texto_participante(self, cod):
        """Linha de identificação do participante a partir do 0150."""
        cod = (cod or "").strip()
        if not cod:
            return ""
        p = self.doc.participante(cod)
        if not p:
            return "👤  %s — (não cadastrado no 0150)" % cod
        partes = [p.get("NOME", "")]
        doc_fmt = self.doc.formatar_doc_participante(p)
        if doc_fmt:
            partes.append(doc_fmt)
        if p.get("IE"):
            partes.append("IE %s" % p["IE"])
        return "👤  %s — %s" % (cod, "  ·  ".join(x for x in partes if x))

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
        menu.addSeparator()
        a_ajuda = menu.addAction("📖 Ajuda do registro %s (guia prático)\tF1"
                                 % self.tipo)
        a_ajuda.triggered.connect(self.abrir_ajuda)
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
            self.doc.alterar_campo(r, ix.column(), valor)
            it = self.tabela.item(ix.row(), ix.column())
            if it is not None:
                it.setText(valor)
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
                self.doc.alterar_campo(r, c, val)
                it = self.tabela.item(lr, c)
                if it is not None:
                    it.setText(val)
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
                self.doc.alterar_campo(r, c, valor)
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

        chave_ctx = "det:%s" % self.tipo
        fechadas = (self._ger_abas.fechadas(chave_ctx)
                    if self._ger_abas is not None else set())
        # uma sub-aba por tipo de filho (exceto os tipos "fechados")
        todos = list(self.doc.tipos_filhos(registro))
        tipos = [t for t in todos if t not in fechadas]
        if not tipos:                      # todos fechados: mostra tudo
            tipos = todos
        for tipo_filho in tipos:
            def make_provider(reg=registro, t=tipo_filho):
                return lambda: self.doc.filhos_por_tipo(reg, t)

            sub = MasterDetailWidget(
                self.doc, tipo_filho, make_provider(),
                pai=registro, on_change=self.on_change,
                gerenciador=self._ger_abas)
            n = len(self.doc.filhos_por_tipo(registro, tipo_filho))
            self.area_detalhe.addTab(sub, "%s (%d)" % (tipo_filho, n))

        self.area_detalhe.setVisible(True)
        # permite reordenar as sub-abas de detalhe (ordem por tipo do master)
        if self._ger_abas is not None:
            self._ger_abas.registrar(self.area_detalhe, chave_ctx, tipos)
            # menu de contexto (fixar / fechar / resetar), ligado uma vez
            bar = self.area_detalhe.tabBar()
            if not getattr(self.area_detalhe, "_menu_conectado", False):
                bar.setContextMenuPolicy(
                    Qt.ContextMenuPolicy.CustomContextMenu)
                bar.customContextMenuRequested.connect(
                    lambda pos: self._menu_abas(pos, chave_ctx))
                self.area_detalhe._menu_conectado = True
            # exibe primeiro a aba fixada, se existir neste documento
            fix = self._ger_abas.fixada(chave_ctx)
            if fix is not None:
                for i in range(self.area_detalhe.tabBar().count()):
                    if self.area_detalhe.tabBar().tabData(i) == fix:
                        self.area_detalhe.setCurrentIndex(i)
                        break
            else:
                self.area_detalhe.setCurrentIndex(0)

    def _menu_abas(self, pos, chave_ctx):
        """Menu de contexto das sub-abas: fixar/desfixar, fechar, resetar."""
        bar = self.area_detalhe.tabBar()
        idx = bar.tabAt(pos)
        if idx < 0:
            return
        ident = bar.tabData(idx)
        menu = QMenu(self.area_detalhe)
        fixada = self._ger_abas.fixada(chave_ctx)
        act_fixar = menu.addAction(
            "Desafixar aba" if fixada == ident else "Fixar aba (exibir 1ª)")
        act_fechar = menu.addAction("Fechar aba")
        menu.addSeparator()
        act_reset = menu.addAction("Resetar abas")
        escolha = menu.exec(bar.mapToGlobal(pos))
        if escolha == act_fixar:
            self._ger_abas.fixar(chave_ctx, ident)
        elif escolha == act_fechar:
            self._ger_abas.fechar(chave_ctx, ident)
        elif escolha == act_reset:
            self._ger_abas.resetar(chave_ctx)
        else:
            return
        # reconstrói o detalhe do registro atual para refletir a mudança
        r = self._registro_da_linha(self.tabela.currentRow())
        self._mostrar_detalhe(r)

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
            informar(self, "Remover",
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

    def _recalcular_totais_c100(self):
        """Recalcula os totais do C100 selecionado (ou de todos) a partir dos
        itens C170."""
        row = self.tabela.currentRow()
        reg = self._registro_da_linha(row) if row >= 0 else None
        if reg is None or reg.reg != "C100":
            resp = QMessageBox.question(
                self, "Recalcular totais",
                "Nenhum documento C100 selecionado.\n\nDeseja recalcular os "
                "totais de TODOS os C100 com itens?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.Yes:
                ok, n = calcular(self, "Recalcular totais",
                                 self.doc.recalcular_totais_todos_c100)
                if not ok:
                    return
                self.recarregar()
                if self.on_change:
                    self.on_change()
                informar(
                    self, "Recalcular totais",
                    "Totais recalculados em %d documento(s) C100." % n)
            return
        if not any(f.reg == "C170" for f in reg.filhos):
            QMessageBox.warning(
                self, "Recalcular totais",
                "Este C100 não possui itens C170 para somar.")
            return
        ok, tot = calcular(self, "Recalcular totais",
                           self.doc.recalcular_totais_c100, reg)
        if not ok:
            return
        self.recarregar()
        if self.on_change:
            self.on_change()
        informar(
            self, "Recalcular totais",
            "Totais do C100 recalculados a partir dos itens C170:\n\n"
            "• Mercadorias (VL_MERC): %s\n"
            "• Base de ICMS (VL_BC_ICMS): %s\n"
            "• Valor do ICMS (VL_ICMS): %s\n"
            "• Valor do documento (VL_DOC): %s\n\n"
            "Frete, seguro e outras despesas do C100 foram mantidos no cálculo "
            "do VL_DOC."
            % (_br(tot.get("VL_MERC", 0.0)), _br(tot.get("VL_BC_ICMS", 0.0)),
               _br(tot.get("VL_ICMS", 0.0)), _br(tot.get("VL_DOC", 0.0))))

    def _recalcular_c190(self):
        """Recalcula os C190 do C100 pai a partir dos itens C170."""
        if self.pai is None:
            return
        ok, res = calcular(self, "Recalcular C190",
                           self.doc.consolidar_c190, self.pai)
        if not ok:
            return
        if res is None:
            informar(
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
        informar(
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
        w_inicial = None
        for tipo in tipos:
            def make_provider(b=self.bloco, t=tipo):
                return lambda: self.doc.registros_raiz_por_tipo(b, t)

            w = MasterDetailWidget(self.doc, tipo, make_provider(),
                                   pai=None, on_change=self.on_change,
                                   gerenciador=self._ger_abas)
            regs = self.doc.registros_raiz_por_tipo(self.bloco, tipo)
            self.tabs.addTab(w, "%s (%d)" % (tipo, len(regs)))
            # abre na primeira sub-aba com conteúdo: nível 1 é só abertura e
            # encerramento do bloco (C001, H001, H990…), um campo cada. Cair
            # no H001 fazia o inventário parecer inexistente.
            if w_inicial is None and regs and regs[0].nivel != 1:
                w_inicial = w
        # permite reordenar as sub-abas de tipo dentro do bloco
        if self._ger_abas is not None:
            self._ger_abas.registrar(self.tabs, "bloco:%s" % self.bloco, tipos)
        # depois do registrar, que pode ter reordenado as abas
        if w_inicial is not None:
            self.tabs.setCurrentIndex(self.tabs.indexOf(w_inicial))

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

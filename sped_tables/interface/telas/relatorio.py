# -*- coding: utf-8 -*-
"""Modo Relatório: visão achatada dos itens, com filtros e edição."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from sped_tables.interface.comum import linhas_da_tabela
from sped_tables.interface.comum import exportar_csv
from sped_tables.interface import tema
from sped_tables.interface.comum import _br, _num_celula


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
        grupo = QGroupBox("Filtros (vários valores por campo: separe com \";\")")
        grupo.setToolTip(
            "Cada campo aceita múltiplos valores separados por ponto e vírgula "
            "(;). Ex.: CFOP \"1101;1102\"  ·  Alíq. PIS \"1,65;0,65\".\n"
            "Use ; (e não vírgula) porque a vírgula é o separador decimal das "
            "alíquotas.")
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

        # atalhos estilo Excel (só quando o foco está na tabela do relatório)
        sc_d = QShortcut(QKeySequence("Ctrl+D"), self.tabela)
        sc_d.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_d.activated.connect(self._fill_down)
        sc_r = QShortcut(QKeySequence("Ctrl+R"), self.tabela)
        sc_r.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_r.activated.connect(self._fill_right)

        self._fonte_mudou()

    def _fill_down(self):
        """Ctrl+D: preenche as células selecionadas com o valor da primeira
        linha da seleção (ou, se só uma célula, com a de cima). Como no Excel."""
        self._preencher_selecao(horizontal=False)

    def _fill_right(self):
        """Ctrl+R: preenche à direita a partir da primeira coluna da seleção."""
        self._preencher_selecao(horizontal=True)

    def _preencher_selecao(self, horizontal):
        t = self.tabela
        ranges = t.selectedRanges()
        if not ranges:
            return
        total = sum((r.bottomRow() - r.topRow() + 1)
                    * (r.rightColumn() - r.leftColumn() + 1) for r in ranges)
        n = 0

        def aplicar(alvo, texto):
            nonlocal n
            if alvo is not None and (alvo.flags()
                                     & Qt.ItemFlag.ItemIsEditable):
                if alvo.text() != texto:
                    alvo.setText(texto)   # dispara _celula_editada -> grava
                    n += 1

        if total == 1:                    # uma célula: copia da vizinha
            rng = ranges[0]
            row, col = rng.topRow(), rng.leftColumn()
            if horizontal and col > 0:
                fonte = t.item(row, col - 1)
                if fonte is not None:
                    aplicar(t.item(row, col), fonte.text())
            elif not horizontal and row > 0:
                fonte = t.item(row - 1, col)
                if fonte is not None:
                    aplicar(t.item(row, col), fonte.text())
        else:
            for rng in ranges:
                if horizontal:
                    for row in range(rng.topRow(), rng.bottomRow() + 1):
                        base = t.item(row, rng.leftColumn())
                        if base is None:
                            continue
                        val = base.text()
                        for col in range(rng.leftColumn() + 1,
                                         rng.rightColumn() + 1):
                            aplicar(t.item(row, col), val)
                else:
                    for col in range(rng.leftColumn(), rng.rightColumn() + 1):
                        base = t.item(rng.topRow(), col)
                        if base is None:
                            continue
                        val = base.text()
                        for row in range(rng.topRow() + 1,
                                         rng.bottomRow() + 1):
                            aplicar(t.item(row, col), val)

        jan = self.window()
        if jan is not None and hasattr(jan, "statusBar"):
            jan.statusBar().showMessage(
                "%d célula(s) preenchida(s)." % n if n else
                "Nada preenchido (verifique se as células são editáveis).")

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
        # todos os filtros aceitam múltiplos valores separados por ';'
        def lista(w):
            t = w.text().strip()
            return [x.strip() for x in t.split(";") if x.strip()] or None

        def listaf(w):
            vals = []
            for x in w.text().strip().split(";"):
                x = x.strip().replace(",", ".")
                if not x:
                    continue
                try:
                    vals.append(float(x))
                except ValueError:
                    pass
            return vals or None

        return {
            "tipo": ["T", "E", "S"][self.cb_tipo.currentIndex()],
            "data_ini": (self.ed_data_ini.text().strip().replace("-", "")
                         or None),
            "data_fim": (self.ed_data_fim.text().strip().replace("-", "")
                         or None),
            "modelo": lista(self.ed_modelo), "num_nota": lista(self.ed_num),
            "cod_prod": lista(self.ed_prod), "nitem": lista(self.ed_item),
            "ncm": lista(self.ed_ncm), "cfop": lista(self.ed_cfop),
            "cst_icms": lista(self.ed_cst_icms),
            "cst_pis": lista(self.ed_cst_pis),
            "cst_cofins": lista(self.ed_cst_cofins),
            "cst_ipi": lista(self.ed_cst_ipi),
            "aliq_icms": listaf(self.ed_aliq_icms),
            "aliq_pis": listaf(self.ed_aliq_pis),
            "aliq_cofins": listaf(self.ed_aliq_cofins),
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
        self._reg_por_uid = {r.uid: r for r in self.doc.registros}
        # mapeia índice de coluna -> campo do registro (colunas editáveis)
        self._edit_idx = {i: edit[c] for i, c in enumerate(cols) if c in edit}
        self._preenchendo = True
        self.tabela.setSortingEnabled(False)
        self.tabela.clear()
        self.tabela.setColumnCount(len(cols))
        self.tabela.setHorizontalHeaderLabels(cols)
        self.tabela.setRowCount(len(linhas))
        cinza = QColor(tema.atual().somente_leitura)
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
        reg = getattr(self, "_reg_por_uid", {}).get(uid)
        if reg is None:
            return
        i_campo = self.doc._ix(reg.reg, campo)
        if i_campo is None:
            return
        self.doc.alterar_campo(reg, i_campo, item.text().strip())
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
        exportar_csv(self, "Exportar relatório", "relatorio_sped.csv",
                     getattr(self, "_cols", []),
                     linhas_da_tabela(self.tabela))

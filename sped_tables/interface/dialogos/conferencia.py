# -*- coding: utf-8 -*-
"""Conferência XML × SPED e correlações de CFOP."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from sped_tables.interface.comum import exportar_csv
from sped_tables.infra import cadastro
from sped_tables.dominio import conferencia as cf
from sped_tables.interface import tema
from sped_tables.interface.comum import _br


class DialogoDiscrepanciasC175(QDialog):
    """Relatório das discrepâncias entre os C170 fictícios (itens do XML da
    NFC-e modelo 65) e o C175 já escriturado, após a importação."""

    COLS = ["nNF", "Grupo (CFOP · CST/alíq.)", "Campo", "Valor itens (XML)",
            "Valor C175 (SPED)"]

    def __init__(self, resumo, divergencias, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Validação do C175 (modelo 65) por item")
        self.resize(820, 560)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Foram criados <b>%d</b> itens C170 fictícios em <b>%d</b> "
            "documento(s) modelo 65, a partir dos XMLs. Edite-os no <b>Modo "
            "Relatório</b> (fonte C170) se precisar corrigir algum item e, ao "
            "final, use <b>Ferramentas → Regenerar C175 (modelo 65)</b> para "
            "consolidar o C175 correto e remover os fictícios.<br>"
            "As linhas abaixo mostram onde a soma dos itens diverge do C175 "
            "atualmente escriturado." % (resumo.get("itens", 0),
                                         resumo.get("docs", 0)))
        info.setWordWrap(True)
        lay.addWidget(info)

        sem_xml = resumo.get("sem_xml") or []
        if sem_xml:
            aviso = QLabel("Documentos modelo 65 sem XML correspondente na "
                           "pasta: %d." % len(sem_xml))
            aviso.setProperty("role", "aviso")
            lay.addWidget(aviso)

        self.tab = QTableWidget(len(divergencias), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True)
        self.tab.setSortingEnabled(False)   # ligada só depois de preencher
        self.tab.horizontalHeader().setStretchLastSection(True)
        for i, d in enumerate(divergencias):
            vals = [d["nnf"], d["grupo"], d["campo"], d["xml"], d["sped"]]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c >= 3:
                    it.setForeground(QColor(tema.atual().bad))
                self.tab.setItem(i, c, it)
        # o indicador -1 precisa vir ANTES de ligar a ordenação: o
        # QTableWidget ordena o próprio modelo e, depois de ordenado,
        # não há como voltar à ordem de montagem (documento a documento).
        # O clique no cabeçalho continua ordenando normalmente.
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()
        lay.addWidget(self.tab, 1)

        lbl = QLabel("%d discrepância(s)." % len(divergencias))
        lbl.setProperty("role", "ok" if not divergencias else "erro")
        rod = QHBoxLayout()
        rod.addWidget(lbl)
        rod.addStretch(1)
        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(lambda: self._exportar(divergencias))
        b_csv.setEnabled(bool(divergencias))
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.accept)
        rod.addWidget(b_csv)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    def _exportar(self, divs):
        exportar_csv(self, "Exportar discrepâncias", "discrepancias_c175.csv",
                     self.COLS,
                     ([d["nnf"], d["grupo"], d["campo"], d["xml"], d["sped"]]
                      for d in divs))


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
        self.tab.setSortingEnabled(False)   # ligada só depois de preencher
        self.tab.horizontalHeader().setStretchLastSection(True)
        divs = resultado["divergencias"]
        self.tab.setRowCount(len(divs))
        for i, d in enumerate(divs):
            vals = [d.nnf, d.nitem, d.campo, _br(d.valor_xml),
                    _br(d.valor_sped), _br((d.valor_xml or 0) - (d.valor_sped or 0))]
            for c, v in enumerate(vals):
                self.tab.setItem(i, c, QTableWidgetItem(str(v)))
        # o indicador -1 precisa vir ANTES de ligar a ordenação: o
        # QTableWidget ordena o próprio modelo e, depois de ordenado,
        # não há como voltar à ordem de montagem (documento a documento).
        # O clique no cabeçalho continua ordenando normalmente.
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
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
        exportar_csv(self, "Exportar conferência C190",
                     "conferencia_c190.csv", self.COLS,
                     ([d.nnf or "", d.nitem or "", d.campo or "",
                       _br(d.valor_xml), _br(d.valor_sped),
                       _br((d.valor_xml or 0) - (d.valor_sped or 0))]
                      for d in self.resultado["divergencias"]))


class DialogoConferencia(QDialog):
    """Mostra o resultado da conferência item XML ↔ C170 e permite exportar."""

    COLS = ["Escopo", "nNF", "nItem", "Campo", "Valor XML", "Valor SPED",
            "Observação"]

    TRIBUTOS = {"ICMS": "ICMS/IPI", "PIS_COFINS": "PIS/COFINS"}
    MOVIMENTOS = [("entrada", "Entradas"), ("saida", "Saídas"),
                  ("ambos", "Ambas")]

    def __init__(self, resultado, parent=None, doc=None, nfes=None,
                 tributo="ICMS", correlacoes=None):
        super().__init__(parent)
        self.doc = doc
        self.nfes = nfes or []
        self.tributo = tributo
        self.correlacoes = correlacoes
        if resultado is None and doc is not None:
            resultado = cf.conferir_itens_xml(
                doc, self.nfes, movimento="entrada", tributo=tributo,
                correlacoes_cfop=correlacoes)
        self.resultado = resultado
        self.setWindowTitle("Conferência de itens com XMLs — %s"
                            % self.TRIBUTOS.get(tributo, tributo))
        self.resize(900, 520)
        lay = QVBoxLayout(self)

        if doc is not None:
            topo = QHBoxLayout()
            topo.addWidget(QLabel("Movimento:"))
            self.cb_mov = QComboBox()
            for chave, rotulo in self.MOVIMENTOS:
                self.cb_mov.addItem(rotulo, chave)
            self.cb_mov.currentIndexChanged.connect(self._movimento_mudou)
            topo.addWidget(self.cb_mov)
            campos = ", ".join(
                c[0] for c in cf.COMPARACOES_POR_TRIBUTO.get(tributo, []))
            dica = QLabel("Campos conferidos: %s" % campos)
            dica.setProperty("role", "dica")
            topo.addWidget(dica, 1)
            lay.addLayout(topo)

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
        self._lbl = lbl
        if r["divergencias"] == 0:
            lbl.setProperty("role", "ok")
        else:
            lbl.setProperty("role", "erro")
        lay.addWidget(lbl)

        divs = resultado["divergencias"]
        self._divs = divs
        tab = QTableWidget(len(divs), len(self.COLS))
        tab.setHorizontalHeaderLabels(self.COLS)
        tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tab.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        tab.setToolTip("Duplo clique numa linha para ir ao registro no SPED.")
        for i, d in enumerate(divs):
            vals = [d.escopo, d.nnf, d.nitem or "", d.campo,
                    cf._fmt(d.valor_xml), cf._fmt(d.valor_sped), d.obs or ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j in (4, 5):
                    it.setForeground(QColor(tema.atual().bad))
                tab.setItem(i, j, it)
        tab.resizeColumnsToContents()
        tab.horizontalHeader().setStretchLastSection(True)
        tab.cellDoubleClicked.connect(self._ir_registro)
        self._tab = tab
        lay.addWidget(tab)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        b_csv = QPushButton("Exportar CSV…")
        b_csv.clicked.connect(self._exportar)
        b_csv.setEnabled(bool(divs))
        self._b_csv = b_csv
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.accept)
        botoes.addWidget(b_csv)
        botoes.addWidget(b_fechar)
        lay.addLayout(botoes)

    def _movimento_mudou(self):
        """Refaz a conferência no movimento escolhido, reusando os XMLs.

        Os XMLs já estão lidos em memória: reler a pasta a cada troca de
        movimento seria desperdício num período com centenas de notas.
        """
        if self.doc is None:
            return
        self.resultado = cf.conferir_itens_xml(
            self.doc, self.nfes, movimento=self.cb_mov.currentData(),
            tributo=self.tributo, correlacoes_cfop=self.correlacoes)
        self._recarregar()

    def _recarregar(self):
        """Repinta resumo e tabela a partir de self.resultado."""
        r = self.resultado["resumo"]
        self._lbl.setText(
            "XMLs modelo 55: %d   |   documentos casados: %d   |   "
            "itens conferidos: %d\n"
            "Divergências: %d   |   itens sem C170 (faltam no SPED): %d   |   "
            "C170 sem XML na pasta: %d\n"
            "XMLs sem C100 no SPED: %d"
            % (r["xml_55"], r["docs_casados"], r["itens_conferidos"],
               r["divergencias"], r["itens_sem_c170"], r["itens_sem_xml"],
               r["docs_sem_c100"]))
        self._lbl.setProperty("role",
                              "ok" if r["divergencias"] == 0 else "erro")
        self._lbl.style().unpolish(self._lbl)
        self._lbl.style().polish(self._lbl)

        divs = self.resultado["divergencias"]
        self._divs = divs
        tab = self._tab
        # ordenação desligada durante o preenchimento (ver CLAUDE.md)
        tab.setSortingEnabled(False)
        tab.setRowCount(len(divs))
        vermelho = QColor(tema.atual().bad)
        for i, d in enumerate(divs):
            vals = [d.escopo, d.nnf, d.nitem or "", d.campo,
                    cf._fmt(d.valor_xml), cf._fmt(d.valor_sped), d.obs or ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j in (4, 5):
                    it.setForeground(vermelho)
                tab.setItem(i, j, it)
        tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        tab.setSortingEnabled(True)
        tab.resizeColumnsToContents()
        self._b_csv.setEnabled(bool(divs))

    def _ir_registro(self, row, _col):
        """Duplo clique: navega ao C170 correspondente à divergência."""
        if not (0 <= row < len(self._divs)):
            return
        uid = getattr(self._divs[row], "uid", None)
        jan = self.parent()
        if uid and jan is not None and hasattr(jan, "ir_para_registro"):
            jan.ir_para_registro(uid)
            self.accept()

    def _exportar(self):
        exportar_csv(self, "Salvar divergências", "divergencias_entradas.csv",
                     cf.CABECALHO_CSV, cf.linhas_csv(self.resultado))


class DialogoCorrelacoesCFOP(QDialog):
    """Tabela editável de CFOP de saída -> CFOPs de entrada válidos.

    Persiste em JSON (via `infra.cadastro`) e devolve o novo
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
            cadastro.salvar_correlacoes(mapa, self.caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Salvar",
                                 "Não foi possível gravar:\n%s" % exc)
            return
        self.on_salvar(mapa)
        QMessageBox.information(
            self, "Correlações de CFOP",
            "Correlações salvas (%d CFOP de saída)." % len(mapa))
        self.accept()

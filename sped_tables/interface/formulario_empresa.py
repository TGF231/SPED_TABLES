# -*- coding: utf-8 -*-
"""O formulário de uma `Empresa`, um só para as duas telas que o usam.

O painel de empresas e o diálogo de rotinas tinham cada um a sua cópia —
com campos diferentes (o painel não editava o CST sem crédito, o diálogo não
mostrava a UF) e com a normalização da alíquota tendo de ser consertada duas
vezes. Agora os dois montam este formulário e só decidem o que fazer ao
gravar.
"""

from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton,
)

from sped_tables.dominio import empresas as emp_mod


class FormularioEmpresa(QGroupBox):
    """Campos da empresa + botão Gravar (que chama `ao_gravar`)."""

    def __init__(self, titulo, ao_gravar, parent=None):
        super().__init__(titulo, parent)
        form = QFormLayout(self)

        self.ed_cnpj = QLineEdit()
        self.ed_cnpj.setReadOnly(True)
        form.addRow("CNPJ:", self.ed_cnpj)
        self.ed_nome = QLineEdit()
        form.addRow("Nome:", self.ed_nome)
        self.ed_uf = QLineEdit()
        self.ed_uf.setMaximumWidth(60)
        form.addRow("UF:", self.ed_uf)

        self.cb_federal = self._combo(emp_mod.REGIMES_FEDERAIS)
        self.cb_federal.currentIndexChanged.connect(self._federal_mudou)
        form.addRow("Regime federal:", self.cb_federal)
        self.cb_pc = self._combo(emp_mod.REGIMES_PIS_COFINS)
        self.cb_pc.currentIndexChanged.connect(self._regime_mudou)
        form.addRow("Regime PIS/COFINS:", self.cb_pc)
        self.cb_ativ = self._combo(emp_mod.ATIVIDADES)
        form.addRow("Atividade:", self.cb_ativ)

        self.ed_pis_s, self.ed_cof_s = QLineEdit(), QLineEdit()
        form.addRow("Alíquotas de saída:",
                    self._linha(("PIS", self.ed_pis_s),
                                ("COFINS", self.ed_cof_s)))
        self.ed_pis_c, self.ed_cof_c = QLineEdit(), QLineEdit()
        self.ed_cst_sem = QLineEdit()
        self.ed_cst_sem.setMaximumWidth(60)
        form.addRow("Alíquotas de crédito:",
                    self._linha(("PIS", self.ed_pis_c),
                                ("COFINS", self.ed_cof_c),
                                ("CST sem crédito", self.ed_cst_sem)))

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        b_gravar = QPushButton("Gravar cadastro")
        b_gravar.setProperty("role", "accent")
        b_gravar.clicked.connect(ao_gravar)
        botoes.addWidget(b_gravar)
        form.addRow("", botoes)

    # ------------------------------------------------------------- montagem
    @staticmethod
    def _combo(opcoes):
        cb = QComboBox()
        for chave, rotulo in opcoes:
            cb.addItem(rotulo, chave)
        return cb

    @staticmethod
    def _linha(*pares):
        lay = QHBoxLayout()
        for rotulo, ed in pares:
            if ed.maximumWidth() > 80:
                ed.setMaximumWidth(80)
            lay.addWidget(QLabel(rotulo))
            lay.addWidget(ed)
        lay.addStretch(1)
        return lay

    @staticmethod
    def _selecionar(combo, chave):
        i = combo.findData(chave)
        if i >= 0:
            combo.setCurrentIndex(i)

    # ---------------------------------------------------------- comportamento
    def _federal_mudou(self):
        """Sugere o regime de PIS/COFINS, sem impor: há exceções."""
        self._selecionar(self.cb_pc, emp_mod.sugerir_regime_pis_cofins(
            self.cb_federal.currentData()))

    def _regime_mudou(self):
        """Preenche as alíquotas nominais do regime escolhido."""
        padrao = emp_mod.ALIQUOTAS.get(self.cb_pc.currentData())
        if not padrao:
            return
        self.ed_pis_s.setText(padrao["pis_saida"])
        self.ed_cof_s.setText(padrao["cofins_saida"])
        self.ed_pis_c.setText(padrao["pis_credito"])
        self.ed_cof_c.setText(padrao["cofins_credito"])

    # -------------------------------------------------------------- dados
    def mostrar(self, empresa):
        """Preenche os campos com a `empresa`, sem disparar a troca de
        alíquotas que a mudança de regime faria."""
        self.cb_pc.blockSignals(True)
        self.cb_federal.blockSignals(True)
        try:
            self.ed_cnpj.setText(emp_mod.formatar_cnpj(empresa.cnpj)
                                 if empresa.cnpj else "")
            self.ed_nome.setText(empresa.nome)
            self.ed_uf.setText(empresa.uf)
            self._selecionar(self.cb_federal, empresa.regime_federal)
            self._selecionar(self.cb_pc, empresa.regime_pis_cofins)
            self._selecionar(self.cb_ativ, empresa.atividade)
            self.ed_pis_s.setText(empresa.aliq_pis_saida)
            self.ed_cof_s.setText(empresa.aliq_cofins_saida)
            self.ed_pis_c.setText(empresa.aliq_pis_credito)
            self.ed_cof_c.setText(empresa.aliq_cofins_credito)
            self.ed_cst_sem.setText(empresa.cst_entrada_sem_credito)
        finally:
            self.cb_pc.blockSignals(False)
            self.cb_federal.blockSignals(False)

    def aplicar(self, empresa):
        """Grava os campos na `empresa` e a devolve.

        A alíquota é normalizada aqui: o campo é texto livre e o que estiver
        nele acaba gravado no arquivo fiscal pela rotina de correção — `1.65`
        digitado com ponto ia para o SPED com ponto.
        """
        e = empresa
        e.nome = self.ed_nome.text().strip()
        e.uf = self.ed_uf.text().strip().upper()
        e.regime_federal = self.cb_federal.currentData()
        e.regime_pis_cofins = self.cb_pc.currentData()
        e.atividade = self.cb_ativ.currentData()
        n = emp_mod.normalizar_aliquota
        e.aliq_pis_saida = n(self.ed_pis_s.text())
        e.aliq_cofins_saida = n(self.ed_cof_s.text())
        e.aliq_pis_credito = n(self.ed_pis_c.text())
        e.aliq_cofins_credito = n(self.ed_cof_c.text())
        e.cst_entrada_sem_credito = self.ed_cst_sem.text().strip() or "70"
        return e

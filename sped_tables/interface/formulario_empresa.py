# -*- coding: utf-8 -*-
"""O formulário de uma `Empresa`, um só para as duas telas que o usam.

O painel de empresas e o diálogo de rotinas tinham cada um a sua cópia —
com campos diferentes (o painel não editava o CST sem crédito, o diálogo não
mostrava a UF) e com a normalização da alíquota tendo de ser consertada duas
vezes. Agora os dois montam este formulário e só decidem o que fazer ao
gravar.
"""

import datetime

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton,
)

from sped_tables.dominio import empresas as emp_mod
from sped_tables.dominio import referencias


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

        # ---- ICMS: código de receita do E116, da tabela da UF no PVA
        self.cb_cod_rec = QComboBox()
        self.cb_cod_rec.setEditable(True)
        self.cb_cod_rec.setMinimumWidth(320)
        self.ed_uf.editingFinished.connect(self._carregar_cod_rec)
        form.addRow("Código de receita ICMS (E116):", self.cb_cod_rec)

        # ---- ICMS das entradas: CSOSN do Simples no CST
        self.ck_csosn = QCheckBox("Converter o CSOSN do fornecedor do "
                                  "Simples no CST correspondente")
        form.addRow("Entradas do Simples:", self.ck_csosn)
        self.ed_origem = QLineEdit()
        self.ed_origem.setMaximumWidth(40)
        self.ed_cst_st = QLineEdit()
        self.ed_cst_st.setMaximumWidth(40)
        form.addRow("", self._linha(("Origem", self.ed_origem),
                                    ("Compra com ST (1403/2403): situação",
                                     self.ed_cst_st)))
        self.ed_csosn = QLineEdit()
        self.ed_csosn.setToolTip(
            "CSOSN=situação, separados por vírgula. Ex.: 101=00, 102=00, "
            "202=10, 500=60")
        form.addRow("CSOSN → situação:", self.ed_csosn)

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

    def _carregar_cod_rec(self, atual=None):
        """Códigos de receita vigentes da UF, da tabela do PVA. Sem PVA a
        lista vem vazia e o campo aceita digitação."""
        if atual is None:
            atual = self._cod_rec()
        hoje = datetime.date.today().strftime("%d%m%Y")
        cods = referencias.atual().codigos_receita_icms(
            self.ed_uf.text().strip(), hoje)
        self.cb_cod_rec.blockSignals(True)
        self.cb_cod_rec.clear()
        self.cb_cod_rec.addItem("", "")
        for cod in sorted(cods):
            self.cb_cod_rec.addItem("%s — %s" % (cod, cods[cod]), cod)
        i = self.cb_cod_rec.findData(atual)
        if i >= 0:
            self.cb_cod_rec.setCurrentIndex(i)
        else:
            self.cb_cod_rec.setEditText(atual or "")
        self.cb_cod_rec.blockSignals(False)

    def _cod_rec(self):
        texto = self.cb_cod_rec.currentText().strip()
        i = self.cb_cod_rec.findText(texto)
        if i >= 0 and self.cb_cod_rec.itemData(i) is not None:
            return self.cb_cod_rec.itemData(i)
        return texto.split(" ")[0] if texto else ""

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
            self._carregar_cod_rec(empresa.cod_rec_icms)
            self.ck_csosn.setChecked(empresa.converter_csosn)
            self.ed_origem.setText(empresa.origem_csosn)
            self.ed_cst_st.setText(empresa.cst_compra_st)
            self.ed_csosn.setText(emp_mod.tabela_csosn_texto(
                empresa.csosn_cst))
        finally:
            self.cb_pc.blockSignals(False)
            self.cb_federal.blockSignals(False)

    def aplicar(self, empresa):
        """Grava os campos na `empresa` e a devolve.

        A alíquota é normalizada aqui: o campo é texto livre e o que estiver
        nele acaba gravado no arquivo fiscal pela rotina de correção — `1.65`
        digitado com ponto ia para o SPED com ponto.

        A tabela CSOSN → situação é conferida antes de tocar na empresa: par
        mal escrito avisa e devolve None, e quem chamou não grava.
        """
        try:
            tabela = emp_mod.tabela_csosn_de_texto(self.ed_csosn.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Cadastro", str(exc))
            return None
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
        e.cod_rec_icms = self._cod_rec()
        e.converter_csosn = self.ck_csosn.isChecked()
        e.origem_csosn = self.ed_origem.text()
        e.cst_compra_st = self.ed_cst_st.text()
        e.csosn_cst = tabela
        e.__post_init__()          # o mesmo funil do cadastro gravado
        return e

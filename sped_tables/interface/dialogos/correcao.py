# -*- coding: utf-8 -*-
"""Correções em lote com parâmetros: alíquotas, datas, ICMS dos itens, CST por NCM."""

import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from sped_tables.interface.comum import linhas_da_tabela
from sped_tables.interface.comum import exportar_csv
from sped_tables.infra import cadastro
from sped_tables.dominio import empresas as emp_mod
from sped_tables.dominio import rotinas
from sped_tables.dominio import ncm
from sped_tables.dominio import referencias
from sped_tables.interface.comum import _br, calcular
from sped_tables.interface.comum import definir_papel, informar


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
    """Verifica o CST de PIS/COFINS dos itens C170 por NCM, com as tabelas de
    alíquota zero e de monofásicos que vêm da base de referência."""

    def __init__(self, doc, data_ref, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Verificar CST de PIS/COFINS por NCM")
        self.resize(880, 620)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Classifica cada item (C170) pelo NCM usando as tabelas oficiais da "
            "RFB (alíquota zero e monofásicos, da base de referência) e aponta "
            "CST de PIS/COFINS incoerentes (ex.: entrada de produto monofásico "
            "com crédito, ou produto de alíquota zero tributado). O C175 "
            "(NFC-e consolidada) não é verificável por NCM.")
        info.setWordWrap(True)
        lay.addWidget(info)

        cfgbox = QGroupBox("Vigência")
        gl = QGridLayout(cfgbox)
        gl.addWidget(QLabel("Data de referência:"), 0, 0)
        self.ed_data = QLineEdit(data_ref or "")
        self.ed_data.setPlaceholderText("DDMMAAAA")
        self.ed_data.setMaximumWidth(120)
        gl.addWidget(self.ed_data, 0, 1)
        lay.addWidget(cfgbox)

        acoes = QHBoxLayout()
        b_ver = QPushButton("Verificar")
        b_ver.clicked.connect(self._verificar)
        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(self._exportar)
        self.b_corrigir = QPushButton("Corrigir entradas sem crédito…")
        self.b_corrigir.setToolTip(
            "Nas entradas que estão tomando crédito num NCM monofásico ou de "
            "alíquota zero: troca o CST pelo sugerido e zera base, alíquota "
            "e valor. Saídas não são alteradas.")
        self.b_corrigir.clicked.connect(self._corrigir)
        self.b_corrigir.setEnabled(False)
        self.lbl = QLabel("—")
        acoes.addWidget(b_ver)
        acoes.addWidget(self.b_corrigir)
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

    def _verificar(self):
        clf = referencias.atual().classificador_ncm()
        if clf is None:
            QMessageBox.warning(
                self, "Tabelas",
                "A base de referência não tem as tabelas de alíquota zero e "
                "de monofásicos: a verificação não tem com o que comparar.")
            return
        probs = ncm.verificar_cst_pis_cofins(
            self.doc, clf, data_ref=self.ed_data.text().strip() or None)
        self._preencher(probs)
        self._probs = probs
        n_ent = sum(1 for p in probs if p["op"] == "E" and p["cst_sugerido"])
        self.b_corrigir.setEnabled(n_ent > 0)
        self.b_corrigir.setText("Corrigir %d entrada(s) sem crédito…" % n_ent)
        self.lbl.setText(
            "%d divergência(s) · tabelas: zero v%s, mono v%s"
            % (len(probs), clf.versao_zero, clf.versao_mono or "—"))

    def _corrigir(self):
        """Retira o crédito das entradas cujo NCM não o admite.

        A correção mora em `rotinas.corrigir_cst_ncm` — a mesma que o painel
        de rotinas usa —, para não existirem duas implementações da mesma
        regra fiscal divergindo com o tempo.
        """
        alvos = [p for p in getattr(self, "_probs", [])
                 if p["op"] == "E" and p["cst_sugerido"]]
        if not alvos:
            return
        ocs = [rotinas.Ocorrencia(
            uid=p["uid"], reg="C170", escopo="entrada", doc="",
            item=p["cod_item"], tributo="PIS/COFINS",
            campo="CST_PIS / CST_COFINS", atual=p["detalhe"],
            esperado=p["cst_sugerido"],
            detalhe="NCM %s — %s" % (p["ncm"], p["classe_desc"]))
            for p in alvos]
        classes = {}
        for p in alvos:
            classes[p["classe_desc"]] = classes.get(p["classe_desc"], 0) + 1
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Corrigir entradas sem direito a crédito")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Question)
        caixa.setText(
            "<b>%d</b> item(ns) de <b>entrada</b> estão com CST incoerente "
            "com o NCM:<br>&nbsp;&nbsp;%s<br><br>"
            "Nos que estiverem <b>tomando crédito</b> (CST 50-56 / 60-66), o "
            "CST será trocado pelo sugerido e <b>base, alíquota e valor serão "
            "zerados</b> — monofásico e alíquota zero não geram crédito na "
            "revenda.<br><br>Saídas não são alteradas: lá o CST depende de "
            "revenda ou produção própria.<br><br>Continuar?"
            % (len(alvos), "<br>&nbsp;&nbsp;".join(
                "• %s: %d" % (c, n) for c, n in sorted(classes.items()))))
        b_ok = caixa.addButton("Corrigir", QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_ok)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return

        # a empresa só serve de fallback para o CST de destino; se o cadastro
        # não estiver disponível, a sugestão do NCM basta
        emp = None
        try:
            emp, _ja = emp_mod.obter_ou_criar(cadastro.carregar_empresas(), self.doc)
        except Exception:  # noqa: BLE001
            pass
        n = rotinas.corrigir_cst_ncm(self.doc, emp, ocs)
        jan = self.parent()
        if jan is not None:
            if hasattr(jan, "_marcar_alterado"):
                jan._marcar_alterado()
            if hasattr(jan, "_montar_abas"):
                jan._montar_abas()
        informar(
            self, "Corrigir entradas sem direito a crédito",
            "%d lançamento(s) de PIS/COFINS corrigidos.\n\n"
            "Itens que já estavam num CST sem crédito não foram tocados: ali "
            "o código depende do motivo da vedação." % n)
        self._verificar()

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
        # o indicador -1 precisa vir ANTES de ligar a ordenação: o
        # QTableWidget ordena o próprio modelo e, depois de ordenado,
        # não há como voltar à ordem de montagem (entradas antes das saídas).
        # O clique no cabeçalho continua ordenando normalmente.
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()

    def _ir(self, row, _col):
        if 0 <= row < len(self._uids) and self.parent() is not None:
            self.parent().ir_para_registro(self._uids[row])

    def _exportar(self):
        if self.tab.rowCount() == 0:
            informar(self, "Exportar", "Nada para exportar.")
            return
        exportar_csv(self, "Exportar verificação", "verificacao_cst.csv",
                     self.COLS, linhas_da_tabela(self.tab))


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


class DialogoRecalcularICMS(QDialog):
    """Recalcula o ICMS dos itens C170 depois da correção no Modo Relatório.

    O fluxo que este diálogo fecha: o usuário corrige alíquota, base ou CST
    direto na grade do **Modo Relatório** — que já grava no registro — e aqui
    pede que os campos derivados voltem a bater entre si.

    Por padrão o escopo são **os itens que estão no relatório**, não o arquivo
    inteiro: é o conjunto que a pessoa acabou de revisar e tem na tela.
    """

    def __init__(self, doc, uids_relatorio, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.uids_relatorio = list(uids_relatorio or [])
        self.setWindowTitle("Recalcular ICMS")
        self.resize(560, 0)

        lay = QVBoxLayout(self)
        intro = QLabel(
            "Recalcula <b>VL_ICMS = base × alíquota</b> nos itens C170. "
            "Use depois de corrigir alíquota, base ou CST no Modo Relatório.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        cx_escopo = QGroupBox("Itens a recalcular")
        ve = QVBoxLayout(cx_escopo)
        self.rb_relatorio = QCheckBox(
            "Somente os itens do Modo Relatório (%d)"
            % len(self.uids_relatorio))
        self.rb_relatorio.setChecked(bool(self.uids_relatorio))
        self.rb_relatorio.setEnabled(bool(self.uids_relatorio))
        ve.addWidget(self.rb_relatorio)
        if not self.uids_relatorio:
            aviso = QLabel("Nenhum relatório gerado: o recálculo vale para "
                           "todos os itens C170 do arquivo.")
            aviso.setProperty("role", "dica")
            aviso.setWordWrap(True)
            ve.addWidget(aviso)
        lay.addWidget(cx_escopo)

        cx_opc = QGroupBox("O que recalcular")
        vo = QVBoxLayout(cx_opc)
        self.ck_base = QCheckBox(
            "Refazer a base a partir de VL_ITEM − VL_DESC")
        self.ck_base.toggled.connect(self._base_mudou)
        vo.addWidget(self.ck_base)

        linha_red = QHBoxLayout()
        linha_red.addSpacing(22)
        self.lbl_red = QLabel("Redução de base nos CST x20 e x70:")
        linha_red.addWidget(self.lbl_red)
        self.ed_reducao = QDoubleSpinBox()
        self.ed_reducao.setRange(0.0, 100.0)
        self.ed_reducao.setDecimals(2)
        self.ed_reducao.setSuffix(" %")
        self.ed_reducao.setValue(0.0)
        linha_red.addWidget(self.ed_reducao)
        linha_red.addStretch(1)
        vo.addLayout(linha_red)
        self._base_mudou(False)

        self.ck_zerar = QCheckBox(
            "Zerar base, alíquota e valor nos CST sem débito "
            "(x30, x40, x41, x50, x60)")
        self.ck_zerar.setChecked(True)
        vo.addWidget(self.ck_zerar)
        lay.addWidget(cx_opc)

        cx_dep = QGroupBox("Depois de recalcular")
        vd = QVBoxLayout(cx_dep)
        self.ck_c190 = QCheckBox(
            "Refazer o C190 e os totais do C100 dos documentos afetados")
        self.ck_c190.setChecked(True)
        vd.addWidget(self.ck_c190)
        nota = QLabel("O ICMS-ST não é tocado: tem base e alíquota próprias, "
                      "muitas vezes com MVA.")
        nota.setProperty("role", "dica")
        nota.setWordWrap(True)
        vd.addWidget(nota)
        lay.addWidget(cx_dep)

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_ok = QPushButton("Recalcular")
        b_ok.setProperty("role", "accent")
        b_ok.clicked.connect(self._executar)
        rod.addWidget(b_ok)
        b_cancelar = QPushButton("Cancelar")
        b_cancelar.clicked.connect(self.reject)
        rod.addWidget(b_cancelar)
        lay.addLayout(rod)

    def _base_mudou(self, ligado):
        self.lbl_red.setEnabled(bool(ligado))
        self.ed_reducao.setEnabled(bool(ligado))

    def _executar(self):
        uids = (self.uids_relatorio
                if self.rb_relatorio.isChecked() and self.uids_relatorio
                else None)
        ok, res = calcular(
            self, "Recalcular ICMS dos itens", self.doc.recalcular_icms_itens,
            uids=uids,
            recalcular_base=self.ck_base.isChecked(),
            reducao_pct=(self.ed_reducao.value()
                         if self.ck_base.isChecked() else None),
            zerar_sem_debito=self.ck_zerar.isChecked(),
            refazer_c190=self.ck_c190.isChecked())
        if not ok:
            return
        self.resultado = res
        docs = res.get("c190_refeitos", 0)

        jan = self.parent()
        if res.get("alterados") and jan is not None:
            if hasattr(jan, "_marcar_alterado"):
                jan._marcar_alterado()
            if hasattr(jan, "_montar_abas"):
                jan._montar_abas()

        sit = res.get("por_situacao", {})
        informar(
            self, "Recalcular ICMS",
            "Itens percorridos: <b>%d</b><br>"
            "Alterados: <b>%d</b> (valor %d, base %d, zerados %d)<br>"
            "Situação: tributado %d · reduzido %d · sem débito %d<br><br>"
            "Diferença no ICMS: <b>%s</b>%s"
            % (res.get("itens", 0), res.get("alterados", 0),
               res.get("valor_alterado", 0), res.get("base_alterada", 0),
               res.get("zerados", 0), sit.get("tributado", 0),
               sit.get("reduzido", 0), sit.get("sem_debito", 0),
               _br(res.get("delta_icms", 0.0)),
               "<br>C190 e totais refeitos em %d documento(s)." % docs
               if docs else ""))
        self.accept()


# ---------------------------------------------------------------------------
# Diálogo: registros de totais com a chave repetida
# ---------------------------------------------------------------------------
class DialogoChavesRepetidas(QDialog):
    """Prévia da fusão (`SpedDocument.chaves_repetidas`): um grupo por linha,
    com o que acontece com ele. Duplo-clique leva ao primeiro repetido;
    *Fundir* aceita, e quem grava é o controlador."""

    COLS = ["Registro", "Documento", "Chave", "Repetidos", "Situação"]

    def __init__(self, doc, grupos, ir_callback, parent=None):
        super().__init__(parent)
        self.ir_callback = ir_callback
        self.setWindowTitle("Fundir registros de chave repetida")
        self.resize(900, 520)
        lay = QVBoxLayout(self)
        info = QLabel(
            "Registros com a mesma chave no mesmo documento — o PVA recusa. "
            "Nos registros de totais (C175, C181, C190, D190…) a fusão deixa "
            "o primeiro com a soma dos valores e das quantidades e remove os "
            "outros: os totais do documento e da apuração não mudam. Os "
            "grupos que não podem ser fundidos dizem por quê. Duplo-clique "
            "leva ao registro.")
        info.setWordWrap(True)
        lay.addWidget(info)

        self.tab = QTableWidget(len(grupos), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setAlternatingRowColors(True)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setStretchLastSection(True)
        for i, g in enumerate(grupos):
            pai = g.pai
            num = pai.valor(doc._ix(pai.reg, "NUM_DOC")) if pai else ""
            documento = ("%s nº %s" % (pai.reg, num) if num else
                         pai.reg if pai else "—")
            valores = (
                g.reg, documento,
                " · ".join("%s %s" % (c, v or "(vazio)") for c, v in g.chave),
                str(len(g.registros)),
                "será fundido" if g.motivo is None else g.motivo)
            for j, v in enumerate(valores):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole,
                               g.registros[1].uid)
                self.tab.setItem(i, j, it)
        self.tab.resizeColumnsToContents()
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)

        fundiveis = [g for g in grupos if g.motivo is None]
        manuais = len(grupos) - len(fundiveis)
        resumo = QLabel(
            "%d grupo(s) serão fundidos (%d registro(s) saem); %d precisam "
            "de correção manual na grade."
            % (len(fundiveis), sum(len(g.registros) - 1 for g in fundiveis),
               manuais))
        definir_papel(resumo, "aviso" if manuais else "info")
        rod = QHBoxLayout()
        rod.addWidget(resumo, 1)
        self.b_fundir = QPushButton("Fundir")
        self.b_fundir.setEnabled(bool(fundiveis))
        self.b_fundir.clicked.connect(self.accept)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.reject)
        rod.addWidget(self.b_fundir)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    def _ir(self, row, _col):
        it = self.tab.item(row, 0)
        if it is not None and self.ir_callback is not None:
            self.ir_callback(it.data(Qt.ItemDataRole.UserRole))

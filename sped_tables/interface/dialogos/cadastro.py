# -*- coding: utf-8 -*-
"""Cadastros: empresa e rotinas, conta contábil, itens sem referência."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from sped_tables.interface.formulario_empresa import FormularioEmpresa
from sped_tables.interface.comum import exportar_csv
from sped_tables.infra import cadastro
from sped_tables.dominio import empresas as emp_mod
from sped_tables.dominio import referencias
from sped_tables.dominio import rotinas
from sped_tables.interface import tema
from sped_tables.interface.comum import (calcular, definir_papel,
                                         informar)


class DialogoItensNaoUsados(QDialog):
    """Itens do 0200 que nenhum outro registro referencia.

    O Guia Prático é explícito: *"Não informar item, se não referenciado em
    pelo menos um dos demais blocos"*. O painel mostra de onde vieram as
    referências — inclusive quais registros foram varridos **por valor**, por
    não terem leiaute mapeado — para que a remoção seja uma decisão informada
    e não um salto no escuro.
    """

    COLS = ["Código do item", "Descrição", "Registros filhos"]

    def __init__(self, doc, refs, nao_usados, ir_callback, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.refs = refs
        self.nao_usados = nao_usados
        self.ir_callback = ir_callback
        self.setWindowTitle("Itens do 0200 sem referência")
        self.resize(860, 560)
        lay = QVBoxLayout(self)

        total = len(refs["codigos"])
        usados = len(refs["referenciados"])
        self.lbl = QLabel(
            "Cadastro com <b>%d</b> item(ns): <b>%d</b> referenciados e "
            "<b>%d</b> sem nenhuma citação no arquivo.<br>"
            "<i>\"Não informar item, se não referenciado em pelo menos um dos "
            "demais blocos.\"</i>" % (total, usados, len(nao_usados)))
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)

        onde = ", ".join("%s (%d)" % (t, n) for t, n in
                         sorted(refs["por_registro"].items(),
                                key=lambda x: -x[1]))
        proc = QLabel(
            "Referências encontradas em: %s.<br>Os campos que apontam para o "
            "0200 vêm do <b>leiaute da versão do arquivo</b> na base de "
            "referência (28 registros no EFD ICMS/IPI, 14 no Contribuições, "
            "no leiaute atual) — não de uma lista escrita à mão. Sem o "
            "leiaute da versão, vale a varredura pelo valor do COD_ITEM."
            % (onde or "nenhum"))
        proc.setWordWrap(True)
        proc.setProperty("role", "info")
        lay.addWidget(proc)

        if refs["por_valor"]:
            av = QLabel(
                "⚠ %s não têm leiaute mapeado no programa e foram varridos "
                "<b>por valor</b> — qualquer campo com o código do item contou "
                "como referência. Isso preserva itens a mais, nunca a menos."
                % ", ".join(sorted(refs["por_valor"])))
            av.setWordWrap(True)
            av.setProperty("role", "aviso")
            lay.addWidget(av)

        dica = QLabel("Dê duplo-clique numa linha para ir ao registro.")
        dica.setProperty("role", "dica")
        lay.addWidget(dica)

        self.tab = QTableWidget(len(nao_usados), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.horizontalHeader().setResizeContentsPrecision(200)
        self.tab.setSortingEnabled(False)
        for i, (reg, cod, descr) in enumerate(nao_usados):
            for j, v in enumerate((cod, descr, str(len(reg.filhos)))):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, reg.uid)
                self.tab.setItem(i, j, it)
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)

        rod = QHBoxLayout()
        self.b_rem = QPushButton("Remover os %d itens sem referência"
                                 % len(nao_usados))
        self.b_rem.clicked.connect(self._remover)
        self.b_rem.setEnabled(bool(nao_usados))
        rod.addWidget(self.b_rem)
        rod.addStretch(1)
        b_ir = QPushButton("Ir para o registro")
        b_ir.clicked.connect(self._ir_selecionado)
        rod.addWidget(b_ir)
        b_exp = QPushButton("Exportar CSV…")
        b_exp.clicked.connect(self._exportar)
        rod.addWidget(b_exp)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.close)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    # -------------------------------------------------------------- ações
    def _remover(self):
        n = len(self.nao_usados)
        filhos = sum(len(r.filhos) for r, _c, _d in self.nao_usados)
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Remover itens sem referência")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Warning)
        caixa.setText(
            "Serão removidos <b>%d</b> registro(s) 0200%s.<br><br>"
            "A remoção apaga o cadastro do item e tudo o que pende dele. "
            "Confira a lista antes — <b>não há desfazer</b>; se errar, feche "
            "o arquivo sem salvar."
            % (n, " e %d registro(s) filho(s)" % filhos if filhos else ""))
        b_ok = caixa.addButton("Remover", QMessageBox.ButtonRole.DestructiveRole)
        b_cancel = caixa.addButton("Cancelar",
                                   QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_cancel)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return

        res = self.doc.remover_itens_0200([r for r, _c, _d in self.nao_usados])
        jan = self.parent()
        if jan is not None:
            if hasattr(jan, "_marcar_alterado"):
                jan._marcar_alterado()
            if hasattr(jan, "_montar_abas"):
                jan._montar_abas()
        informar(
            self, "Remover itens sem referência",
            "%d item(ns) removido(s) do 0200 — %d registro(s) ao todo, "
            "contando os filhos." % (res["itens"], res["registros"]))
        self.nao_usados = []
        self.tab.setRowCount(0)
        self.b_rem.setEnabled(False)
        self.lbl.setText(self.lbl.text() + "<br><b>Removidos.</b>")

    def _exportar(self):
        exportar_csv(self, "Exportar itens sem referência",
                     "itens_sem_referencia.csv", self.COLS,
                     ([cod, descr, len(reg.filhos)]
                      for reg, cod, descr in self.nao_usados))

    def _ir(self, row, _col):
        it = self.tab.item(row, 0)
        if it is not None and self.ir_callback is not None:
            self.ir_callback(it.data(Qt.ItemDataRole.UserRole))

    def _ir_selecionado(self):
        linhas = {i.row() for i in self.tab.selectedIndexes()}
        if linhas:
            self._ir(min(linhas), 0)


class DialogoCodCta(QDialog):
    """Preenche a conta contábil (COD_CTA) dos registros que estão sem ela.

    O PVA exige o campo nos perfis **A e B** — o erro típico é o H010, porque
    o cadastro do produto não tem conta de estoque vinculada no ERP. Cada tipo
    de registro leva a sua conta: estoque no H010, custo/receita no C170, e é
    por isso que o preenchimento é um tipo por vez.
    """

    NATUREZAS = [("01", "01 - Contas de ativo"),
                 ("02", "02 - Contas de passivo"),
                 ("03", "03 - Patrimônio líquido"),
                 ("04", "04 - Contas de resultado"),
                 ("05", "05 - Contas de compensação"),
                 ("09", "09 - Outras")]
    # natureza que faz sentido por registro: estoque é ativo, item de nota é
    # resultado. É só o padrão do diálogo; o usuário troca.
    NAT_PADRAO = {"H010": "01", "C170": "04", "D100": "04"}

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Preencher conta contábil (COD_CTA)")
        self.resize(620, 420)
        lay = QVBoxLayout(self)

        perfil = doc.perfil()
        info = QLabel(
            "O <b>COD_CTA</b> é obrigatório nos perfis <b>A</b> e <b>B</b>. "
            "Este arquivo é do perfil <b>%s</b>.<br>Cada registro leva a sua "
            "conta — estoque no H010, custo no C170 —, por isso o "
            "preenchimento é de um tipo por vez."
            % (perfil or "não declarado"))
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QFormLayout()
        self.cb_reg = QComboBox()
        self.faltantes = doc.registros_sem_cod_cta()
        for tipo in sorted(self.faltantes, key=lambda t: -len(
                self.faltantes[t])):
            self.cb_reg.addItem("%s — %d sem conta"
                                % (tipo, len(self.faltantes[tipo])), tipo)
        self.cb_reg.currentIndexChanged.connect(self._reg_mudou)
        form.addRow("Registro:", self.cb_reg)

        self.ed_cod = QLineEdit()
        self.ed_cod.setPlaceholderText("ex.: 1.1.03.01")
        form.addRow("Código da conta (COD_CTA):", self.ed_cod)
        self.ed_nome = QLineEdit()
        self.ed_nome.setPlaceholderText("ex.: ESTOQUE DE MERCADORIAS")
        form.addRow("Nome da conta (NOME_CTA):", self.ed_nome)
        self.cb_nat = QComboBox()
        for _c, rot in self.NATUREZAS:
            self.cb_nat.addItem(rot)
        form.addRow("Natureza (COD_NAT_CC):", self.cb_nat)
        self.ed_nivel = QLineEdit("1")
        self.ed_nivel.setMaximumWidth(60)
        form.addRow("Nível:", self.ed_nivel)
        lay.addLayout(form)

        self.chk_0500 = QCheckBox(
            "Cadastrar a conta no plano de contas (registro 0500) se ainda "
            "não existir")
        self.chk_0500.setChecked(True)
        lay.addWidget(self.chk_0500)

        contas = doc.contas_0500()
        if contas:
            self.cb_conta = QComboBox()
            self.cb_conta.addItem("(digitar outra)", "")
            for cod, nome, _nat, _ind, _niv in contas:
                self.cb_conta.addItem("%s — %s" % (cod, nome), cod)
            self.cb_conta.currentIndexChanged.connect(self._conta_escolhida)
            lay.addWidget(QLabel("Contas já cadastradas no 0500:"))
            lay.addWidget(self.cb_conta)
        else:
            aviso = QLabel(
                "Este arquivo não tem <b>nenhum registro 0500</b> (plano de "
                "contas). Deixe a opção acima marcada para criar a conta "
                "junto — informar uma conta que não existe no plano é o "
                "próximo erro a aparecer.")
            aviso.setWordWrap(True)
            aviso.setProperty("role", "aviso")
            lay.addWidget(aviso)

        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        self.lbl.setProperty("role", "dica")
        lay.addWidget(self.lbl)
        lay.addStretch(1)

        rod = QHBoxLayout()
        rod.addStretch(1)
        self.b_ok = QPushButton("Preencher")
        self.b_ok.clicked.connect(self._preencher)
        rod.addWidget(self.b_ok)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.close)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

        self._reg_mudou()

    def _reg_mudou(self):
        tipo = self.cb_reg.currentData()
        if not tipo:
            self.lbl.setText("Nenhum registro deste arquivo está sem conta.")
            self.b_ok.setEnabled(False)
            return
        n = len(self.faltantes.get(tipo, []))
        self.lbl.setText("%d registro(s) %s serão preenchidos. Registros que "
                         "já têm conta não são tocados." % (n, tipo))
        self.b_ok.setEnabled(n > 0)
        alvo = self.NAT_PADRAO.get(tipo)
        if alvo:
            for i, (c, _r) in enumerate(self.NATUREZAS):
                if c == alvo:
                    self.cb_nat.setCurrentIndex(i)
                    break

    def _conta_escolhida(self):
        cod = self.cb_conta.currentData()
        if cod:
            self.ed_cod.setText(cod)
            for c, nome, _n, _i, _v in self.doc.contas_0500():
                if c == cod:
                    self.ed_nome.setText(nome)
                    break

    def _preencher(self):
        tipo = self.cb_reg.currentData()
        cod = self.ed_cod.text().strip()
        if not cod:
            QMessageBox.warning(self, "Conta contábil",
                                "Informe o código da conta (COD_CTA).")
            return
        res = self.doc.preencher_cod_cta(
            tipo, cod, criar_0500=self.chk_0500.isChecked(),
            nome_cta=self.ed_nome.text().strip() or cod,
            nat_cc=self.NATUREZAS[self.cb_nat.currentIndex()][0],
            nivel=self.ed_nivel.text().strip() or "1")
        if res.get("erro"):
            QMessageBox.critical(self, "Conta contábil", res["erro"])
            return
        jan = self.parent()
        if jan is not None:
            if hasattr(jan, "_marcar_alterado"):
                jan._marcar_alterado()
            if hasattr(jan, "_montar_abas"):
                jan._montar_abas()
        informar(
            self, "Conta contábil",
            "%d registro(s) %s preenchidos com a conta %s.%s"
            % (res["registros"], res["tipo"], res["cod_cta"],
               "\n\nA conta foi cadastrada no plano de contas (0500)."
               if res["conta_criada"] else ""))
        self.faltantes = self.doc.registros_sem_cod_cta()
        self.cb_reg.blockSignals(True)
        self.cb_reg.clear()
        for t in sorted(self.faltantes, key=lambda x: -len(self.faltantes[x])):
            self.cb_reg.addItem("%s — %d sem conta" % (t,
                                                       len(self.faltantes[t])),
                                t)
        self.cb_reg.blockSignals(False)
        self._reg_mudou()


class DialogoEmpresa(QDialog):
    """Configuração por empresa: regime tributário e rotinas de correção.

    Duas metades. Em cima, o **cadastro** — o que a empresa declara ser, que o
    arquivo sozinho não diz (ou diz só em parte, no 0110). Embaixo, as
    **rotinas**, que usam esse cadastro para decidir o que está errado.

    A ordem importa: nenhuma rotina roda antes de o regime estar declarado,
    porque a mesma alíquota está certa num regime e errada no outro.
    """

    COLS = ["Escopo", "Doc.", "Item", "Tributo", "Campo", "Atual",
            "Esperado", "Detalhe"]

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Configuração da empresa e rotinas")
        self.resize(980, 700)
        self._ocorrencias = []
        self._rotina_atual = None

        self.mapa = cadastro.carregar_empresas()
        self.empresa, ja_cadastrada = emp_mod.obter_ou_criar(self.mapa, doc)

        lay = QVBoxLayout(self)
        if self.empresa is None:
            lay.addWidget(QLabel(
                "O arquivo não traz CNPJ no registro 0000 — sem ele não há "
                "como identificar a empresa."))
            return

        cab = QLabel(self.empresa.rotulo())
        cab.setProperty("role", "secao")
        lay.addWidget(cab)
        if not ja_cadastrada:
            aviso = QLabel("Empresa ainda não cadastrada — os campos abaixo "
                           "foram pré-preenchidos com o que o arquivo informa. "
                           "Confira e grave.")
            aviso.setProperty("role", "aviso")
            aviso.setWordWrap(True)
            lay.addWidget(aviso)

        divergencia = emp_mod.conferir_regime(doc, self.empresa)
        self.lbl_divergencia = QLabel(divergencia or "")
        self.lbl_divergencia.setProperty("role", "erro")
        self.lbl_divergencia.setWordWrap(True)
        self.lbl_divergencia.setVisible(bool(divergencia))
        lay.addWidget(self.lbl_divergencia)

        lay.addWidget(self._montar_cadastro())
        lay.addWidget(self._montar_rotinas(), 1)

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.accept)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    # ------------------------------------------------------------ cadastro
    def _montar_cadastro(self):
        self.form = FormularioEmpresa("Cadastro", self._gravar)
        self.form.mostrar(self.empresa)
        return self.form

    def _coletar(self):
        return self.form.aplicar(self.empresa)

    def _gravar(self):
        e = self._coletar()
        if e is None:
            return
        self.mapa[e.cnpj] = e
        try:
            caminho = cadastro.salvar_empresas(self.mapa)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Cadastro", str(exc))
            return
        divergencia = emp_mod.conferir_regime(self.doc, e)
        self.lbl_divergencia.setText(divergencia or "")
        self.lbl_divergencia.setVisible(bool(divergencia))
        self._listar_rotinas()
        informar(self, "Cadastro", "Gravado em:\n%s" % caminho)

    # ------------------------------------------------------------- rotinas
    def _montar_rotinas(self):
        cx = QGroupBox("Rotinas")
        v = QVBoxLayout(cx)

        topo = QHBoxLayout()
        self.cb_rotina = QComboBox()
        topo.addWidget(self.cb_rotina, 1)
        b_verificar = QPushButton("Verificar")
        b_verificar.clicked.connect(self._verificar)
        topo.addWidget(b_verificar)
        self.b_corrigir = QPushButton("Corrigir…")
        self.b_corrigir.setProperty("role", "accent")
        self.b_corrigir.setEnabled(False)
        self.b_corrigir.clicked.connect(self._corrigir)
        topo.addWidget(self.b_corrigir)
        v.addLayout(topo)

        self.lbl_desc = QLabel("")
        self.lbl_desc.setProperty("role", "dica")
        self.lbl_desc.setWordWrap(True)
        v.addWidget(self.lbl_desc)
        self.cb_rotina.currentIndexChanged.connect(self._rotina_mudou)

        self.lbl_res = QLabel("")
        v.addWidget(self.lbl_res)

        self.tab = QTableWidget(0, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.cellDoubleClicked.connect(self._ir)
        v.addWidget(self.tab, 1)

        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(self._exportar)
        rod = QHBoxLayout()
        rod.addStretch(1)
        rod.addWidget(b_csv)
        v.addLayout(rod)

        self._listar_rotinas()
        return cx

    def _listar_rotinas(self):
        self.cb_rotina.blockSignals(True)
        self.cb_rotina.clear()
        for r in rotinas.aplicaveis(self.doc, self.empresa):
            self.cb_rotina.addItem(r.nome, r.id)
        self.cb_rotina.blockSignals(False)
        if self.cb_rotina.count() == 0:
            self.lbl_desc.setText(
                "Nenhuma rotina se aplica a este leiaute.")
        else:
            self._rotina_mudou()

    def _rotina(self):
        rid = self.cb_rotina.currentData()
        for r in rotinas.ROTINAS:
            if r.id == rid:
                return r
        return None

    def _rotina_mudou(self):
        r = self._rotina()
        if r is None:
            return
        texto = r.descricao
        if r.corrigir is None:
            texto += "  (sem correção automática)"
        self.lbl_desc.setText(texto)
        self._ocorrencias = []
        self.tab.setRowCount(0)
        self.b_corrigir.setEnabled(False)
        self.lbl_res.setText("")

    def _verificar(self):
        r = self._rotina()
        if r is None:
            return
        if self._coletar() is None:
            return
        extra = {}
        if r.requer == "tabelas_ncm":
            clf = self._classificador()
            if clf is None:
                return
            extra["classificador"] = clf
        ocorrencias, erro = rotinas.executar(self.doc, self.empresa, r, **extra)
        if erro:
            QMessageBox.critical(self, r.nome, erro)
            return
        self._ocorrencias = ocorrencias
        self._rotina_atual = r
        self._preencher(ocorrencias)
        self.lbl_res.setText("%d ocorrência(s)." % len(ocorrencias))
        definir_papel(self.lbl_res, "ok" if not ocorrencias else "erro")
        self.b_corrigir.setEnabled(bool(ocorrencias) and r.corrigir is not None)
        if r.corrigir is not None:
            self.b_corrigir.setText("Corrigir %d…" % len(ocorrencias))

    def _classificador(self):
        """O classificador de NCM da base de referência (a mesma fonte das
        outras regras), ou None com o aviso."""
        clf = referencias.atual().classificador_ncm()
        if clf is None:
            QMessageBox.warning(
                self, "Tabelas de NCM",
                "A base de referência não tem as tabelas de alíquota zero e "
                "de monofásicos: esta rotina não pode rodar.")
        return clf

    def _preencher(self, ocorrencias):
        # a ordenação só é ligada depois de preencher (ver CLAUDE.md)
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(len(ocorrencias))
        pal = tema.atual()
        for i, o in enumerate(ocorrencias):
            vals = [o.escopo, o.doc, o.item, o.tributo, o.campo, o.atual,
                    o.esperado, o.detalhe]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c == 5:
                    it.setForeground(QColor(pal.bad))
                elif c == 6:
                    it.setForeground(QColor(pal.ok))
                self.tab.setItem(i, c, it)
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()

    def _corrigir(self):
        r = self._rotina_atual
        if r is None or r.corrigir is None or not self._ocorrencias:
            return
        resp = QMessageBox.question(
            self, r.nome,
            "%s\n\nSerão alterados %d registro(s).\n\nConfirma?"
            % (r.rotulo_correcao, len(self._ocorrencias)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        ok, n = calcular(self, r.nome, r.corrigir, self.doc,
                         self.empresa, self._ocorrencias)
        if not ok:
            return
        janela = self.parent()
        if janela is not None and hasattr(janela, "_marcar_alterado"):
            janela._marcar_alterado()
        informar(
            self, r.nome,
            "%d registro(s) alterado(s).\n\nO arquivo ainda NÃO foi salvo — "
            "revise e use Salvar como." % n)
        self._verificar()

    def _ir(self, row, _col):
        if 0 <= row < len(self._ocorrencias):
            janela = self.parent()
            if janela is not None and hasattr(janela, "ir_para_registro"):
                janela.ir_para_registro(self._ocorrencias[row].uid)

    def _exportar(self):
        if not self._ocorrencias:
            return
        rotina = self._rotina_atual.id if self._rotina_atual else "empresa"
        exportar_csv(self, "Exportar ocorrências", "rotina_%s.csv" % rotina,
                     self.COLS,
                     ([o.escopo, o.doc, o.item, o.tributo, o.campo, o.atual,
                       o.esperado, o.detalhe] for o in self._ocorrencias))

# -*- coding: utf-8 -*-
"""Gerar o SPED do período a partir dos XMLs (caso de uso
`aplicacao/geracao_xml.py`).

A tela não calcula nada: escolhe empresa, pasta e período, mostra o que o
gerador leu e o que ele não soube, e devolve as decisões da pessoa para a
memória da empresa. Enquanto houver ponto de revisão que **bloqueia** (o
arquivo sairia inválido), o leiaute não é gravado.
"""

import datetime
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from sped_tables.aplicacao.geracao_xml import GeracaoXml, empresas_com_memoria
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio.sped_model import so_digitos
from sped_tables.interface import tema
from sped_tables.interface.comum import _br, _num_celula

NOMES = {"ICMS": "EFD ICMS/IPI", "CONTRIB": "EFD Contribuições"}
MOVIMENTO = {"entradas": "Entrada", "saidas": "Saída",
             "fretes_entrada": "Frete tomado", "fretes_saida": "Frete prestado"}


def _cnpj_fmt(c):
    c = so_digitos(c)
    if len(c) != 14:
        return c
    return "%s.%s.%s/%s-%s" % (c[:2], c[2:5], c[5:8], c[8:12], c[12:])


def _data_iso(iso):
    iso = (iso or "").strip()
    return "%s/%s/%s" % (iso[8:10], iso[5:7], iso[:4]) if len(iso) >= 10 \
        else ""


def _tabela(colunas):
    t = QTableWidget(0, len(colunas))
    t.setHorizontalHeaderLabels(colunas)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.setWordWrap(False)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    return t


def _preencher(tabela, linhas, cores=None):
    tabela.setSortingEnabled(False)
    tabela.setRowCount(len(linhas))
    for i, ln in enumerate(linhas):
        for c, v in enumerate(ln):
            it = QTableWidgetItem(str(v))
            if cores and cores[i]:
                it.setForeground(QColor(cores[i]))
            tabela.setItem(i, c, it)
    tabela.horizontalHeader().setResizeContentsPrecision(200)
    tabela.resizeColumnsToContents()


# ---------------------------------------------------------------------------
class DialogoDecisao(QDialog):
    """Como escriturar um produto do fornecedor: a resposta vai para a
    memória da empresa e vale para as próximas gerações."""

    CAMPOS_ICMS = (("COD_ITEM", "Código próprio"), ("CFOP", "CFOP de entrada"),
                   ("CST_ICMS", "CST do ICMS"), ("CST_IPI", "CST do IPI"),
                   ("COD_NAT", "Natureza (COD_NAT)"))
    CAMPOS_CONTRIB = (("CST_PIS", "CST do PIS"), ("ALIQ_PIS", "Alíquota PIS"),
                      ("CST_COFINS", "CST da COFINS"),
                      ("ALIQ_COFINS", "Alíquota COFINS"),
                      ("COD_CTA", "Conta contábil"))

    def __init__(self, apontamento, contrib, atual=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Decidir a escrituração do produto")
        d = apontamento["dados"]
        atual = atual or {}
        lay = QVBoxLayout(self)
        cab = QLabel("<b>%s</b><br>Fornecedor %s, código dele %s — CFOP %s, "
                     "CST %s no XML" % (d.get("xprod", ""),
                                        _cnpj_fmt(d.get("fornecedor", "")),
                                        d.get("cprod", ""), d.get("cfop", ""),
                                        d.get("cst", "")))
        cab.setTextFormat(Qt.TextFormat.RichText)
        cab.setWordWrap(True)
        lay.addWidget(cab)
        motivo = QLabel(apontamento["detalhe"])
        motivo.setWordWrap(True)
        motivo.setProperty("role", "erro" if apontamento["bloqueia"]
                           else "aviso")
        lay.addWidget(motivo)

        form = QFormLayout()
        self.edits = {}
        campos = self.CAMPOS_ICMS + (self.CAMPOS_CONTRIB if contrib else ())
        for nome, rotulo in campos:
            e = QLineEdit()
            e.setPlaceholderText(atual.get(nome, ""))
            self.edits[nome] = e
            form.addRow(rotulo + ":", e)
        self.credito = QComboBox()
        self.credito.addItems(["(manter)", "Com crédito de ICMS",
                               "Sem crédito de ICMS"])
        form.insertRow(3, "Crédito:", self.credito)
        lay.addLayout(form)
        dica = QLabel("Campo em branco mantém o que a memória já sabe (em "
                      "cinza). A decisão vale para este produto quando ele "
                      "vier com o mesmo CFOP e CST do fornecedor.")
        dica.setWordWrap(True)
        dica.setProperty("role", "dica")
        lay.addWidget(dica)
        botoes = QDialogButtonBox()
        botoes.addButton("Gravar na memória",
                         QDialogButtonBox.ButtonRole.AcceptRole)
        botoes.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        botoes.accepted.connect(self._conferir)
        botoes.rejected.connect(self.reject)
        lay.addWidget(botoes)
        self.valores = {}

    def _campos(self):
        v = {n: e.text() for n, e in self.edits.items()}
        v["CREDITA_ICMS"] = {1: "S", 2: "N"}.get(self.credito.currentIndex(),
                                                 "")
        return v

    def _conferir(self):
        try:
            self.valores = mi.validar_decisao(self._campos())
        except ValueError as exc:
            QMessageBox.warning(self, "Decidir", str(exc))
            return
        if not self.valores:
            QMessageBox.information(self, "Decidir", "Nada foi informado.")
            return
        self.accept()


# ---------------------------------------------------------------------------
class DialogoGerarDeXml(QDialog):
    """Empresa, pasta e período → os dois SPED, com a revisão do que o
    gerador não soube."""

    COLS_DOC = ["Incluir", "Movimento", "Modelo", "Série/número", "Data",
                "Participante", "Valor", "Situação", "Chave"]
    COLS_REV = ["Leiaute", "Situação", "Tipo", "Documento", "Item",
                "Detalhe"]
    COLS_FORA = ["Chave ou arquivo", "Motivo"]

    def __init__(self, parent=None, empresas=None, correlacoes=None,
                 pasta_inicial=""):
        super().__init__(parent)
        self.setWindowTitle("Gerar SPED a partir dos XMLs")
        self.resize(1000, 680)
        self.correlacoes = correlacoes
        self.geracao = None
        self.pasta_lida = None
        self.excluir = set()
        self.revisao = []            # [(leiaute, apontamento)]
        self.abrir_depois = None     # caminho que a janela abre ao fechar
        lay = QVBoxLayout(self)

        # ---- empresa, pasta e período
        caixa = QGroupBox("Empresa e período")
        form = QFormLayout(caixa)
        self.empresa = QComboBox()
        self.empresa.setEditable(True)
        self.empresa.lineEdit().setPlaceholderText("CNPJ da empresa")
        nomes = {so_digitos(c): getattr(e, "nome", "")
                 for c, e in (empresas or {}).items()}
        for cnpj in sorted(set(nomes) | set(empresas_com_memoria())):
            rotulo = "%s  %s" % (_cnpj_fmt(cnpj), nomes.get(cnpj, ""))
            self.empresa.addItem(rotulo.strip(), cnpj)
        self.empresa.setCurrentIndex(-1)
        self.empresa.currentTextChanged.connect(self._trocar_empresa)
        form.addRow("Empresa:", self.empresa)

        linha_mem = QHBoxLayout()
        self.lbl_memoria = QLabel()
        self.lbl_memoria.setWordWrap(True)
        self.b_aprender = QPushButton("Aprender com SPED entregue…")
        self.b_aprender.clicked.connect(self._aprender)
        linha_mem.addWidget(self.lbl_memoria, 1)
        linha_mem.addWidget(self.b_aprender)
        form.addRow("Memória:", linha_mem)

        linha_pasta = QHBoxLayout()
        self.pasta = QLineEdit(pasta_inicial)
        b_pasta = QPushButton("Escolher…")
        b_pasta.clicked.connect(self._escolher_pasta)
        linha_pasta.addWidget(self.pasta, 1)
        linha_pasta.addWidget(b_pasta)
        form.addRow("Pasta dos XMLs:", linha_pasta)

        linha_per = QHBoxLayout()
        hoje = datetime.date.today().replace(day=1) - datetime.timedelta(1)
        self.periodo = QLineEdit(hoje.strftime("%m/%Y"))
        self.periodo.setInputMask("99/9999")
        self.periodo.setMaximumWidth(90)
        self.chk = {lay_: QCheckBox(NOMES[lay_]) for lay_ in NOMES}
        for c in self.chk.values():
            c.setChecked(True)
        self.saldo = QLineEdit()
        self.saldo.setPlaceholderText("o da memória")
        self.saldo.setMaximumWidth(130)
        linha_per.addWidget(self.periodo)
        for c in self.chk.values():
            linha_per.addWidget(c)
        linha_per.addWidget(QLabel("Saldo credor anterior (ICMS):"))
        linha_per.addWidget(self.saldo)
        linha_per.addStretch(1)
        self.b_gerar = QPushButton("Gerar")
        self.b_gerar.setDefault(True)
        self.b_gerar.clicked.connect(self._gerar)
        linha_per.addWidget(self.b_gerar)
        form.addRow("Período:", linha_per)
        lay.addWidget(caixa)

        # ---- abas
        self.abas = QTabWidget()
        self.t_doc = _tabela(self.COLS_DOC)
        self.t_doc.itemChanged.connect(self._marcar)
        self.t_rev = _tabela(self.COLS_REV)
        self.t_rev.itemSelectionChanged.connect(self._habilitar)
        self.t_rev.itemDoubleClicked.connect(lambda _it: self._decidir())
        self.t_fora = _tabela(self.COLS_FORA)
        aba_rev = QVBoxLayout()
        aba_rev.setContentsMargins(0, 0, 0, 0)
        aba_rev.addWidget(self.t_rev, 1)
        linha_rev = QHBoxLayout()
        dica = QLabel("Duplo clique num produto para decidir como ele é "
                      "escriturado — a decisão fica na memória da empresa.")
        dica.setProperty("role", "dica")
        linha_rev.addWidget(dica, 1)
        self.b_decidir = QPushButton("Decidir…")
        self.b_decidir.clicked.connect(self._decidir)
        linha_rev.addWidget(self.b_decidir)
        aba_rev.addLayout(linha_rev)
        w_rev = QWidget()
        w_rev.setLayout(aba_rev)
        self.abas.addTab(self.t_doc, "Documentos")
        self.abas.addTab(w_rev, "Revisão")
        self.abas.addTab(self.t_fora, "Fora do período e ignorados")
        lay.addWidget(self.abas, 1)

        # ---- rodapé
        rod = QHBoxLayout()
        self.lbl_estado = QLabel("Escolha a empresa, a pasta e o período.")
        self.lbl_estado.setWordWrap(True)
        rod.addWidget(self.lbl_estado, 1)
        self.b_salvar = {}
        for layout_ in NOMES:
            b = QPushButton("Salvar %s…" % NOMES[layout_])
            b.clicked.connect(lambda _c=False, x=layout_: self._salvar(x))
            self.b_salvar[layout_] = b
            rod.addWidget(b)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.reject)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)
        self._trocar_empresa()

    # ------------------------------------------------------------ empresa
    def _cnpj(self):
        i = self.empresa.currentIndex()
        if i >= 0 and self.empresa.itemText(i) == self.empresa.currentText():
            return self.empresa.itemData(i)
        return so_digitos(self.empresa.currentText())

    def _trocar_empresa(self, _texto=None):
        cnpj = self._cnpj()
        self.geracao = GeracaoXml(cnpj) if len(cnpj) == 14 else None
        self.pasta_lida = None
        self.excluir = set()
        self.b_aprender.setEnabled(self.geracao is not None)
        self._mostrar_memoria()
        self._limpar()

    def _mostrar_memoria(self):
        lbl = self.lbl_memoria
        if self.geracao is None:
            lbl.setText("informe o CNPJ (14 dígitos)")
            lbl.setProperty("role", "dica")
        else:
            r = self.geracao.resumo()
            if not r["periodos"]:
                lbl.setText("vazia — aprenda com um SPED entregue desta "
                            "empresa antes de gerar")
                lbl.setProperty("role", "aviso")
            else:
                per = ", ".join("%s/%s" % (p[4:], p[:4])
                                for p in r["periodos"][-4:])
                lbl.setText("%d produto(s), %d no cadastro, %d "
                            "participante(s) — aprendida de %s"
                            % (r["produtos"], r["cadastro"],
                               r["participantes"], per))
                lbl.setProperty("role", "ok")
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)
        sabe = self.geracao.leiautes_aprendidos() if self.geracao else ()
        for lay_, c in self.chk.items():
            c.setEnabled(lay_ in sabe)
            c.setChecked(lay_ in sabe)
            c.setToolTip("" if lay_ in sabe else
                         "A memória não tem um %s entregue desta empresa."
                         % NOMES[lay_])

    def _aprender(self):
        speds, _f = QFileDialog.getOpenFileNames(
            self, "SPED entregue (um de cada leiaute, do mesmo mês)", "",
            "Arquivos SPED (*.txt);;Todos os arquivos (*)")
        if not speds:
            return
        pasta = QFileDialog.getExistingDirectory(
            self, "Pasta dos XMLs do MESMO mês do SPED entregue",
            self.pasta.text())
        if not pasta:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.geracao.aprender(pasta, *speds)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Aprender", str(exc))
            return
        QApplication.restoreOverrideCursor()
        self._mostrar_memoria()
        QMessageBox.information(
            self, "Aprender",
            "Itens casados com o XML: %d\nItens sem XML: %d\nNotas de "
            "entrada sem XML na pasta: %d\n\nA memória tem %d produto(s)."
            % (res["itens_casados"], res["itens_sem_xml"],
               res["notas_sem_xml"], res["produtos"]))

    def _escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(
            self, "Pasta dos XMLs do período", self.pasta.text())
        if pasta:
            self.pasta.setText(os.path.normpath(pasta))

    # ------------------------------------------------------------- gerar
    def _periodo(self):
        mes, _b, ano = self.periodo.text().partition("/")
        if not (mes.isdigit() and ano.isdigit() and len(ano) == 4
                and 1 <= int(mes) <= 12):
            raise ValueError("Período inválido: use MM/AAAA.")
        return "%s%02d" % (ano, int(mes))

    def _saldo(self):
        texto = self.saldo.text().strip()
        if not texto:
            return None
        v = _num_celula(texto)
        if v is None or v < 0:
            raise ValueError("Saldo credor anterior inválido: \"%s\"." % texto)
        return v

    def _gerar(self):
        if self.geracao is None:
            QMessageBox.warning(self, "Gerar", "Informe o CNPJ da empresa.")
            return
        pasta = self.pasta.text().strip()
        leiautes = tuple(k for k, c in self.chk.items() if c.isChecked())
        try:
            periodo, saldo = self._periodo(), self._saldo()
            if not os.path.isdir(pasta):
                raise ValueError("A pasta dos XMLs não existe.")
            if not leiautes:
                raise ValueError("Marque ao menos um leiaute.")
        except ValueError as exc:
            QMessageBox.warning(self, "Gerar", str(exc))
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if self.pasta_lida != pasta:
                self.geracao.ler(pasta)
                self.pasta_lida = pasta
                self.excluir = set()
            grupos, previa = self.geracao.documentos(periodo)
            self.geracao.gerar(periodo, leiautes, excluir=self.excluir,
                               saldo_credor_anterior=saldo,
                               correlacoes=self.correlacoes)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Gerar", str(exc))
            return
        QApplication.restoreOverrideCursor()
        self._mostrar(grupos, previa)

    def _limpar(self):
        for t in (self.t_doc, self.t_rev, self.t_fora):
            t.setRowCount(0)
        for b in self.b_salvar.values():
            b.setEnabled(False)
        self.b_decidir.setEnabled(False)

    def _mostrar(self, grupos, previa):
        pal = tema.atual()
        # documentos: todos os do período, os desmarcados também (a
        # classificação não recebe o `excluir`), para poder voltar atrás
        self.t_doc.blockSignals(True)
        linhas, chaves = [], []
        for grupo, docs in grupos.items():
            for d in docs:
                cte = hasattr(d, "nct")
                outro = (d.toma if cte and grupo == "fretes_entrada"
                         else d.dest if grupo in ("saidas", "fretes_saida")
                         else d.emit)
                linhas.append(["", MOVIMENTO[grupo], d.mod or "",
                               "%s/%s" % (d.serie, d.nct if cte else d.nnf),
                               _data_iso(d.dhemi),
                               (outro.nome if outro else "") or "",
                               _br(d.vtprest if cte else d.vnf),
                               d.situacao, d.chave])
                chaves.append(d.chave)
        _preencher(self.t_doc, linhas)
        for i, chave in enumerate(chaves):
            it = self.t_doc.item(i, 0)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked if chave in self.excluir
                             else Qt.CheckState.Checked)
            it.setData(Qt.ItemDataRole.UserRole, chave)
        self.t_doc.blockSignals(False)

        # revisão: bloqueios primeiro
        self.revisao = [(lay_, r) for lay_, res in
                        self.geracao.resultados.items() for r in res.revisar]
        self.revisao.sort(key=lambda x: not x[1]["bloqueia"])
        _preencher(self.t_rev, [
            [NOMES[lay_], "bloqueia" if r["bloqueia"] else "revisar",
             r["tipo"], r["documento"], r["item"], r["detalhe"]]
            for lay_, r in self.revisao],
            [pal.bad if r["bloqueia"] else pal.warn
             for _l, r in self.revisao])

        # fora do período, ignorados e o que não foi lido
        lote = self.geracao.lote
        fora = ([[c, "fora do período (%s)" % ("%s/%s/%s" % (
            d[:2], d[2:4], d[4:]) if d else "sem data")]
            for c, d in previa.fora_periodo]
            + [[c, m] for c, m in previa.ignorados]
            + [[os.path.basename(a), m] for a, m in lote.erros]
            + [[os.path.basename(d.arquivo or ""), "sem chave de acesso "
                "(não é documento autorizado)"] for d in lote.sem_chave]
            + [[os.path.basename(a), "repetido (%s)" % c]
               for a, c in lote.repetidos])
        _preencher(self.t_fora, fora)
        self.abas.setTabText(1, "Revisão (%d)" % len(self.revisao))
        self.abas.setTabText(2, "Fora do período e ignorados (%d)"
                             % len(fora))
        self._estado()

    def _estado(self):
        partes, bloqueado = [], False
        for lay_, res in self.geracao.resultados.items():
            n = len(res.bloqueios)
            bloqueado = bloqueado or bool(n)
            partes.append("%s: %d registro(s), %d ponto(s) de revisão%s"
                          % (NOMES[lay_], len(res.doc.registros),
                             len(res.revisar),
                             ", %d bloqueia(m) a gravação" % n if n else ""))
            self.b_salvar[lay_].setEnabled(not n)
        for lay_, b in self.b_salvar.items():
            if lay_ not in self.geracao.resultados:
                b.setEnabled(False)
        self.lbl_estado.setText(" · ".join(partes))
        self.lbl_estado.setProperty("role", "erro" if bloqueado else "ok")
        self.lbl_estado.style().unpolish(self.lbl_estado)
        self.lbl_estado.style().polish(self.lbl_estado)
        self._habilitar()

    def _marcar(self, item):
        if item.column() != 0:
            return
        chave = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.excluir.discard(chave)
        else:
            self.excluir.add(chave)
        self.lbl_estado.setText("Documentos alterados — clique em Gerar "
                                "para refazer.")
        self.lbl_estado.setProperty("role", "aviso")
        self.lbl_estado.style().unpolish(self.lbl_estado)
        self.lbl_estado.style().polish(self.lbl_estado)
        for b in self.b_salvar.values():
            b.setEnabled(False)

    # ------------------------------------------------------------ decidir
    def _selecionado(self):
        linhas = {i.row() for i in self.t_rev.selectedIndexes()}
        if len(linhas) != 1:
            return None
        # a tabela não é ordenável: a linha é o índice na lista
        lay_, r = self.revisao[linhas.pop()]
        return (lay_, r) if r["dados"].get("fornecedor") else None

    def _habilitar(self):
        self.b_decidir.setEnabled(self._selecionado() is not None)

    def _decidir(self):
        sel = self._selecionado()
        if sel is None:
            return
        lay_, r = sel
        d = r["dados"]

        class _Item:
            cfop, icms_cst = d["cfop"], d["cst"]
        atual = dict(mi.escrituracao(self.geracao.memoria, d["fornecedor"],
                                     d["cprod"], _Item)
                     or d.get("usado") or {})
        cod, _amb = mi.codigo_proprio(self.geracao.memoria, d["fornecedor"],
                                      d["cprod"])
        if cod:
            atual["COD_ITEM"] = cod
        dlg = DialogoDecisao(r, "CONTRIB" in self.geracao.resultados, atual,
                             self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.geracao.decidir(r, **dlg.valores)
        except ValueError as exc:
            QMessageBox.warning(self, "Decidir", str(exc))
            return
        self._gerar()

    # ------------------------------------------------------------- salvar
    def _salvar(self, layout):
        res = self.geracao.resultados.get(layout)
        if res is None:
            return
        cnpj = self.geracao.cnpj
        sugestao = os.path.join(
            self.pasta.text().strip(),
            "SPED_%s_%s_%s.txt" % ("ICMS_IPI" if layout == "ICMS"
                                   else "Contribuicoes", cnpj,
                                   self._periodo()))
        caminho, _f = QFileDialog.getSaveFileName(
            self, "Salvar %s" % NOMES[layout], sugestao,
            "Arquivos SPED (*.txt)")
        if not caminho:
            return
        try:
            self.geracao.salvar(layout, caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Salvar", str(exc))
            return
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Salvar")
        caixa.setText("%s gravado em:\n%s\n\nAbrir no editor para conferir e "
                      "validar?" % (NOMES[layout], caminho))
        abrir = caixa.addButton("Abrir no editor",
                                QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Continuar aqui", QMessageBox.ButtonRole.RejectRole)
        caixa.exec()
        if caixa.clickedButton() is abrir:
            self.abrir_depois = caminho
            self.accept()

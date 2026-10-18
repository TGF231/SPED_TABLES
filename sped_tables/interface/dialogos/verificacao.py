# -*- coding: utf-8 -*-
"""Resultados de verificação: diagnóstico, revisão, validação de campos e a lista de ocorrências."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from sped_tables.dominio import diagnostico
from sped_tables.dominio import validacao
from sped_tables.interface import tema
from sped_tables.interface.comum import abrir_janela, informar


class DialogoValidacao(QDialog):
    """Campos fora do domínio do leiaute, em duas naturezas:

    o que tem **conserto mecânico** (zero à esquerda perdido, texto de vazio)
    é normalizado em lote pelo botão; o que exige **decisão fiscal** fica na
    lista, e o duplo-clique leva até o registro para corrigir à mão.
    """

    COLS = ["Bloco", "Registro", "Campo", "Valor", "Problema", "Sugestão"]
    LIMITE = 20000          # além disto a tabela vira peso morto

    def __init__(self, doc, achados, ir_callback, parent=None,
                 info_tabelas=""):
        super().__init__(parent)
        self.doc = doc
        self.achados = achados
        self.ir_callback = ir_callback
        self.setWindowTitle("Validar campos pelo leiaute")
        self.resize(940, 580)
        lay = QVBoxLayout(self)

        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)
        if info_tabelas:
            proc = QLabel(info_tabelas)
            proc.setWordWrap(True)
            proc.setProperty("role", "info")
            lay.addWidget(proc)

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Mostrar:"))
        self.cb_nat = QComboBox()
        self.cb_nat.addItem("Todos", "todos")
        self.cb_nat.addItem("Com conserto automático", "auto")
        self.cb_nat.addItem("Exigem correção manual", "manual")
        self.cb_nat.currentIndexChanged.connect(self._repovoar)
        filtros.addWidget(self.cb_nat)
        filtros.addSpacing(12)
        filtros.addWidget(QLabel("Campo:"))
        self.cb_campo = QComboBox()
        self.cb_campo.currentIndexChanged.connect(self._repovoar)
        filtros.addWidget(self.cb_campo, 1)
        lay.addLayout(filtros)

        dica = QLabel("Dê duplo-clique numa linha para ir ao registro.")
        dica.setProperty("role", "dica")
        lay.addWidget(dica)

        self.tab = QTableWidget(0, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.horizontalHeader().setResizeContentsPrecision(200)
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)

        rod = QHBoxLayout()
        self.b_norm = QPushButton()
        self.b_norm.clicked.connect(self._normalizar)
        rod.addWidget(self.b_norm)
        rod.addStretch(1)
        b_ir = QPushButton("Ir para o registro")
        b_ir.clicked.connect(self._ir_selecionado)
        rod.addWidget(b_ir)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.close)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

        self._montar_combo_campos()
        self._repovoar()

    # ------------------------------------------------------------ montagem
    def _montar_combo_campos(self):
        atual = self.cb_campo.currentData()
        self.cb_campo.blockSignals(True)
        self.cb_campo.clear()
        self.cb_campo.addItem("(todos)", "")
        vistos = {}
        for o in self.achados:
            vistos[o.campo] = vistos.get(o.campo, 0) + 1
        for campo, n in sorted(vistos.items(), key=lambda x: -x[1]):
            self.cb_campo.addItem("%s (%d)" % (campo, n), campo)
        if atual:
            i = self.cb_campo.findData(atual)
            if i >= 0:
                self.cb_campo.setCurrentIndex(i)
        self.cb_campo.blockSignals(False)

    def _filtrados(self):
        nat = self.cb_nat.currentData()
        campo = self.cb_campo.currentData()
        out = []
        for o in self.achados:
            if campo and o.campo != campo:
                continue
            if nat == "auto" and o.sugestao is None:
                continue
            if nat == "manual" and o.sugestao is not None:
                continue
            out.append(o)
        return out

    def _repovoar(self):
        pal = tema.atual()
        lista = self._filtrados()
        auto = sum(1 for o in self.achados if o.sugestao is not None)
        self.lbl.setText(
            "<b>%d</b> campo(s) fora do domínio do leiaute: <b>%d</b> com "
            "conserto automático e <b>%d</b> que dependem de decisão sua."
            % (len(self.achados), auto, len(self.achados) - auto))
        mostrados = lista[:self.LIMITE]
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(len(mostrados))
        for i, o in enumerate(mostrados):
            vals = [o.bloco, o.reg, o.campo, o.valor, o.motivo,
                    ("(esvaziar)" if o.sugestao == "" else o.sugestao)
                    if o.sugestao is not None else "—"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, o.uid)
                if j == 5:
                    it.setForeground(QColor(pal.ok if o.sugestao is not None
                                            else pal.warn))
                self.tab.setItem(i, j, it)
        # o indicador -1 antes de ligar preserva a ordem de montagem
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()
        if len(lista) > self.LIMITE:
            self.lbl.setText(self.lbl.text() +
                             "<br>Mostrando as %d primeiras de %d — use os "
                             "filtros para reduzir." % (self.LIMITE,
                                                        len(lista)))
        n_auto = sum(1 for o in lista if o.sugestao is not None)
        self.b_norm.setText("Normalizar %d campo(s) desta lista" % n_auto)
        self.b_norm.setEnabled(n_auto > 0)

    # -------------------------------------------------------------- ações
    def _normalizar(self):
        lista = [o for o in self._filtrados() if o.sugestao is not None]
        if not lista:
            return
        por_campo = {}
        for o in lista:
            por_campo[o.campo] = por_campo.get(o.campo, 0) + 1
        detalhe = ", ".join("%s (%d)" % (c, n) for c, n in
                            sorted(por_campo.items(), key=lambda x: -x[1]))
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Normalizar campos")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Question)
        caixa.setText("Serão corrigidos <b>%d</b> campo(s):<br><br>%s"
                      "<br><br>Continuar?" % (len(lista), detalhe))
        b_ok = caixa.addButton("Normalizar",
                               QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_ok)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return

        res = validacao.normalizar(self.doc, lista)
        jan = self.parent()
        if jan is not None:
            if hasattr(jan, "_marcar_alterado"):
                jan._marcar_alterado()
            if hasattr(jan, "_montar_abas"):
                jan._montar_abas()
        # revalida: o que sobrou é o que precisa de decisão humana
        dom, _i = validacao.dominios_do_documento(self.doc)
        self.achados = validacao.validar(self.doc, dominios_pva=dom)
        self._montar_combo_campos()
        self._repovoar()
        informar(
            self, "Normalizar campos",
            "%d campo(s) corrigido(s).\n\n%s"
            % (res["campos"],
               "\n".join("• %s: %d" % (c, n)
                         for c, n in sorted(res["por_campo"].items(),
                             key=lambda x: -x[1]))))

    def _ir(self, row, _col):
        it = self.tab.item(row, 0)
        if it is not None and self.ir_callback is not None:
            self.ir_callback(it.data(Qt.ItemDataRole.UserRole))

    def _ir_selecionado(self):
        linhas = {i.row() for i in self.tab.selectedIndexes()}
        if linhas:
            self._ir(min(linhas), 0)


# ---------------------------------------------------------------------------
# Diálogo de revisão de erros
# ---------------------------------------------------------------------------
class DialogoDiagnostico(QDialog):
    """Diagnóstico do arquivo, no mesmo desenho que o PVA usa para reprovar —
    e com o **atalho para o módulo que corrige** cada grupo.

    Roda sozinho ao abrir o arquivo: o valor de saber que faltam 13 mil campos
    está em saber antes de começar a trabalhar, não depois de transmitir.
    """

    COLS = ["", "O que corrige", "Problemas", "Onde fica"]
    DET = ["Registro", "Campo", "Problema", "Quantidade"]

    def __init__(self, achados, info, acoes, ir_callback, parent=None,
                 ao_revisar=None):
        super().__init__(parent)
        self.achados = achados
        self.acoes = acoes or {}
        self.ir_callback = ir_callback
        self.setWindowTitle("Diagnóstico do arquivo")
        self.resize(940, 600)
        lay = QVBoxLayout(self)

        pal = tema.atual()
        total = sum(a.quantidade for a in achados)
        # sem o leiaute do arquivo na base valeram só as regras embutidas:
        # "nenhum problema" não pode soar como aprovação (nem sair em verde)
        parcial = bool(info.get("fora_da_base") or info.get("sem_base"))
        if total:
            texto_cab, papel_cab = (
                "<b>%d</b> problema(s) em %d tipo(s) de verificação."
                % (total, len(achados)), "erro")
        elif parcial:
            texto_cab, papel_cab = (
                "Nenhum problema nas regras embutidas — a conferência pelo "
                "leiaute não rodou.", "aviso")
        else:
            texto_cab, papel_cab = (
                "Nenhum problema nas verificações automáticas.", "ok")
        cab = QLabel(texto_cab)
        cab.setProperty("role", papel_cab)
        lay.addWidget(cab)

        if info.get("fora_da_base") and info.get("mais_nova_que_a_base"):
            # o remédio é outro: não é arquivo velho, é base velha
            texto_origem = (
                "A versão %s do leiaute deste arquivo é mais nova que a base "
                "de referência em uso%s: valeram apenas as regras embutidas, "
                "que cobrem menos que o validador oficial. Importe uma base "
                "mais nova em Configurações → Base de referência…"
                % (info["fora_da_base"],
                   " (%s)" % info["base"] if info.get("base") else ""))
        elif info.get("fora_da_base"):
            texto_origem = (
                "A versão %s do leiaute deste arquivo não está na base de "
                "referência (ela guarda os últimos 5 anos): valeram apenas "
                "as regras embutidas, que cobrem menos que o validador "
                "oficial." % info["fora_da_base"])
        elif info.get("sem_base"):
            texto_origem = (
                "Base de referência indisponível: valeram apenas as regras "
                "embutidas no programa, que cobrem menos que o validador "
                "oficial.")
        else:
            texto_origem = (
                "Verificado com o leiaute da versão %s (%s registros) — o "
                "que o validador declara: tipo, tamanho, obrigatoriedade, "
                "enumerações, tabelas e referências entre registros."
                % (info.get("versao") or "?",
                   info.get("registros_descritor", "?")))
        origem = QLabel(texto_origem)
        origem.setWordWrap(True)
        origem.setProperty("role", "aviso" if parcial else "info")
        lay.addWidget(origem)

        self.resumo = QTableWidget(0, len(self.COLS))
        self.resumo.setHorizontalHeaderLabels(self.COLS)
        self.resumo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.resumo.verticalHeader().setVisible(False)
        self.resumo.horizontalHeader().setStretchLastSection(True)
        self.resumo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        grupos = diagnostico.resumo_por_modulo(achados)
        self.resumo.setRowCount(len(grupos))
        self._grupos = grupos
        for i, (mod, onde, n, _lst) in enumerate(grupos):
            it = QTableWidgetItem("●")
            it.setForeground(QColor(pal.bad))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.resumo.setItem(i, 0, it)
            self.resumo.setItem(i, 1, QTableWidgetItem(mod))
            itn = QTableWidgetItem("%d" % n)
            itn.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                 | Qt.AlignmentFlag.AlignVCenter)
            self.resumo.setItem(i, 2, itn)
            fn = self.acoes.get(mod)
            if fn:
                b = QPushButton("Abrir: %s" % mod)
                b.clicked.connect(lambda _=False, f=fn: f())
                self.resumo.setCellWidget(i, 3, b)
            else:
                self.resumo.setItem(i, 3, QTableWidgetItem(onde))
        self.resumo.resizeColumnsToContents()
        self.resumo.setColumnWidth(0, 28)
        self.resumo.currentCellChanged.connect(self._grupo_mudou)
        lay.addWidget(QLabel("<b>Correções sugeridas</b>"))
        lay.addWidget(self.resumo, 1)

        lay.addWidget(QLabel("<b>Detalhe</b> — duplo-clique leva ao registro"))
        self.det = QTableWidget(0, len(self.DET))
        self.det.setHorizontalHeaderLabels(self.DET)
        self.det.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.det.verticalHeader().setVisible(False)
        self.det.horizontalHeader().setStretchLastSection(True)
        self.det.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.det, 1)

        regras = info.get("regras_do_pva") or []
        if regras:
            nota = QLabel(
                "⚠ O PVA aplica ainda <b>%d regra(s) compostas</b> aos "
                "registros deste arquivo que este programa não reproduz "
                "(condições implementadas em Java, como "
                "<i>%s</i>). Validar no PVA continua sendo necessário."
                % (len(regras), ", ".join(regras[:3])))
            nota.setWordWrap(True)
            nota.setProperty("role", "aviso")
            lay.addWidget(nota)

        rod = QHBoxLayout()
        if ao_revisar is not None:
            # a lista ocorrência a ocorrência, para a correção manual; era
            # o item de menu *Revisar erros*, ao lado deste
            b_rev = QPushButton("Revisar ocorrências…")
            b_rev.setToolTip("Cada verificação com a lista das ocorrências "
                             "— para corrigir à mão, na grade.")
            b_rev.clicked.connect(lambda _=False: ao_revisar())
            rod.addWidget(b_rev)
        rod.addStretch(1)
        b = QPushButton("Fechar")
        b.clicked.connect(self.close)
        rod.addWidget(b)
        lay.addLayout(rod)
        if grupos:
            self.resumo.setCurrentCell(0, 1)

    def _grupo_mudou(self, linha, *_a):
        if not (0 <= linha < len(self._grupos)):
            return
        lst = sorted(self._grupos[linha][3], key=lambda a: -a.quantidade)
        self.det.setRowCount(len(lst))
        for i, a in enumerate(lst):
            vals = (a.reg, a.campo, a.detalhe, "%d" % a.quantidade)
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, a.uid)
                if j == 3:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                        | Qt.AlignmentFlag.AlignVCenter)
                self.det.setItem(i, j, it)
        self.det.resizeColumnsToContents()

    def _ir(self, row, _col):
        it = self.det.item(row, 0)
        uid = it.data(Qt.ItemDataRole.UserRole) if it else None
        if uid is not None and self.ir_callback is not None:
            self.ir_callback(uid)


class DialogoOcorrencias(QDialog):
    """Lista item a item de **uma** regra; duplo-clique navega até o registro.

    Fica atrás de um clique de propósito: a listagem completa só ajuda quando
    a correção é manual, registro a registro.
    """

    COLS = ["Bloco", "Registro", "Descrição"]

    def __init__(self, titulo, problemas, ir_callback, parent=None):
        super().__init__(parent)
        self.ir_callback = ir_callback
        self.setWindowTitle(titulo)
        self.resize(860, 520)
        lay = QVBoxLayout(self)
        dica = QLabel("%d ocorrência(s). Duplo-clique leva ao registro."
                      % len(problemas))
        dica.setProperty("role", "dica")
        lay.addWidget(dica)
        self.tab = QTableWidget(len(problemas), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.horizontalHeader().setResizeContentsPrecision(200)
        for i, p in enumerate(problemas):
            for j, v in enumerate((p.bloco, p.reg, p.descricao)):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, p.uid)
                self.tab.setItem(i, j, it)
        self.tab.resizeColumnsToContents()
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)
        rod = QHBoxLayout()
        rod.addStretch(1)
        b = QPushButton("Fechar")
        b.clicked.connect(self.close)
        rod.addWidget(b)
        lay.addLayout(rod)

    def _ir(self, row, _col):
        it = self.tab.item(row, 0)
        if it is not None and self.ir_callback is not None:
            self.ir_callback(it.data(Qt.ItemDataRole.UserRole))


class DialogoRevisao(QDialog):
    """Painel de revisão: **um resumo por regra**, com o atalho para a função
    que corrige cada uma.

    A versão anterior listava as ocorrências uma a uma — 1.887 linhas dizendo
    "COD_ITEM tal não é referenciado", numa tela onde não havia como corrigir
    nenhuma. O que a pessoa precisa saber ali é *quantos* e *qual função
    resolve*; a lista detalhada só interessa quando a correção é manual, e por
    isso ficou atrás do botão "Ver ocorrências".
    """

    COLS = ["", "Verificação", "Ocorrências", "Como corrigir"]

    def __init__(self, por_regra, ir_callback, parent=None, acoes=None):
        """`por_regra` é `[(rotulo, [problemas])]`; `acoes` mapeia o rótulo
        para (texto do botão, função)."""
        super().__init__(parent)
        problemas = [p for _r, ps in por_regra for p in ps]
        resumo = [(r, len(ps)) for r, ps in por_regra]
        self.por_regra = dict(por_regra)
        self.problemas = problemas
        self.ir_callback = ir_callback
        self.acoes = acoes or {}
        self.setWindowTitle("Revisão de erros")
        self.resize(860, 420)
        lay = QVBoxLayout(self)

        pal = tema.atual()
        total = len(problemas)
        lbl = QLabel("<b>%d</b> ocorrência(s) em %d verificação(ões)."
                     % (total, len(resumo)))
        lbl.setProperty("role", "ok" if total == 0 else "erro")
        lay.addWidget(lbl)
        dica = QLabel("Cada linha mostra quantos erros a verificação achou e "
                      "qual função resolve. Sem correção automática, "
                      "\"Ver ocorrências\" abre a lista para corrigir na grade.")
        dica.setWordWrap(True)
        dica.setProperty("role", "dica")
        lay.addWidget(dica)

        ordem = sorted(resumo, key=lambda x: -x[1])

        self.tab = QTableWidget(len(ordem), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setStretchLastSection(True)
        for i, (rotulo, n) in enumerate(ordem):
            marca = QTableWidgetItem("✔" if n == 0 else "●")
            marca.setForeground(QColor(pal.ok if n == 0 else pal.bad))
            marca.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tab.setItem(i, 0, marca)
            self.tab.setItem(i, 1, QTableWidgetItem(rotulo))
            it_n = QTableWidgetItem("%d" % n)
            it_n.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                  | Qt.AlignmentFlag.AlignVCenter)
            if n:
                it_n.setForeground(QColor(pal.bad))
            self.tab.setItem(i, 2, it_n)
            self.tab.setCellWidget(i, 3, self._acao(rotulo, n))
        self.tab.resizeColumnsToContents()
        self.tab.setColumnWidth(0, 28)
        lay.addWidget(self.tab, 1)

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.close)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    def _acao(self, rotulo, n):
        """Botão da linha: a correção em massa quando existe, senão a lista."""
        if not n:
            return QLabel("  —")
        par = self.acoes.get(rotulo)
        b = QPushButton(par[0] if par else "Ver ocorrências…")
        if par:
            b.clicked.connect(lambda _=False, fn=par[1]: fn())
        else:
            b.clicked.connect(
                lambda _=False, t=rotulo: self._ver(t, self.por_regra.get(t,
                                                                          [])))
        return b

    def _ver(self, titulo, problemas):
        if not problemas:
            informar(self, titulo,
                     "Sem ocorrências para listar.")
            return
        self._dlg = abrir_janela(self, DialogoOcorrencias(
            titulo, problemas, self.ir_callback, self))

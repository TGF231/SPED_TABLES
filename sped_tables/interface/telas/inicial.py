# -*- coding: utf-8 -*-
"""Tela inicial: acervo por empresa e período, pendências e arrastar-e-soltar."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from sped_tables.infra import cadastro
from sped_tables.dominio import empresas as emp_mod
from sped_tables.infra import arquivos as arq_mod
from sped_tables.infra import dados
from sped_tables.interface import tema
from sped_tables.version import APP_NAME


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------
class TelaInicial(QWidget):
    """O que a janela mostra enquanto nenhum arquivo está aberto.

    As abas *Modo Tabela* e *Modo Relatório* vazias não diziam nada. Esta tela
    usa o que o programa já sabe sem abrir arquivo — o histórico arquivado e o
    cadastro de empresas — para responder três perguntas de quem chega:
    *em que eu estava?*, *o que falta?* e *o que dá para fazer agora?*
    """

    MESES = 8

    def __init__(self, janela, parent=None):
        super().__init__(parent)
        self.janela = janela
        self.setAcceptDrops(True)
        self._recentes = []

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 14, 18, 14)
        raiz.setSpacing(12)

        # ---------------------------------------------------------- topo
        topo = QHBoxLayout()
        titulo = QLabel(APP_NAME)
        titulo.setProperty("role", "tituloInicial")
        topo.addWidget(titulo)
        self.lbl_acervo = QLabel("")
        self.lbl_acervo.setProperty("role", "dica")
        topo.addWidget(self.lbl_acervo)
        topo.addStretch(1)

        self.b_continuar = QPushButton("Continuar")
        self.b_continuar.setProperty("role", "accent")
        self.b_continuar.clicked.connect(self._continuar)
        topo.addWidget(self.b_continuar)
        b_abrir = QPushButton("Abrir arquivo…")
        b_abrir.clicked.connect(self.janela.abrir)
        topo.addWidget(b_abrir)
        raiz.addLayout(topo)

        self.lbl_solte = QLabel(
            "Arraste um arquivo SPED (.txt) para esta janela")
        self.lbl_solte.setProperty("role", "solte")
        self.lbl_solte.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raiz.addWidget(self.lbl_solte)

        # ------------------------------------------------------- matriz
        cx = QGroupBox("Períodos arquivados neste sistema")
        vcx = QVBoxLayout(cx)
        self.tab = QTableWidget(0, 0)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.tab.setAlternatingRowColors(True)
        self.tab.verticalHeader().setVisible(False)
        self.tab.cellDoubleClicked.connect(self._abrir_celula)
        vcx.addWidget(self.tab)
        legenda = QLabel(
            "Duplo clique numa célula abre o período.   "
            "\u25cf ICMS/IPI   \u25cf PIS/COFINS   "
            "— ausente (não arquivado aqui; não significa não entregue)")
        legenda.setProperty("role", "dica")
        legenda.setWordWrap(True)
        vcx.addWidget(legenda)
        raiz.addWidget(cx)

        # ------------------------------------------- pendências e atalhos
        base = QHBoxLayout()
        cx_pend = QGroupBox("Pendências")
        vp = QVBoxLayout(cx_pend)
        self.lbl_pend = QLabel("")
        self.lbl_pend.setWordWrap(True)
        self.lbl_pend.setAlignment(Qt.AlignmentFlag.AlignTop)
        vp.addWidget(self.lbl_pend, 1)
        base.addWidget(cx_pend, 2)

        cx_at = QGroupBox("Atalhos")
        va = QVBoxLayout(cx_at)
        for texto, slot in (
                ("Empresas e histórico",
                 lambda: self.janela.mostrar_empresas(True)),
                ("Correlações de CFOP",
                 lambda: self.janela.editar_correlacoes_cfop()),
                ("Alternar tema", lambda: self.janela.alternar_tema())):
            b = QPushButton(texto)
            b.clicked.connect(slot)
            va.addWidget(b)
        va.addStretch(1)
        base.addWidget(cx_at, 1)
        raiz.addLayout(base)
        # o conteúdo fica ancorado no topo: a matriz tem altura de conteúdo e
        # esticar as caixas só produziria vão no meio da tela
        raiz.addStretch(1)

        self.recarregar()

    # ------------------------------------------------------------ dados
    def recarregar(self):
        """Relê histórico e cadastro. Chamado ao voltar para esta tela."""
        cadastradas = cadastro.carregar_empresas()
        extras = {c: e.nome for c, e in cadastradas.items()}
        dados = arq_mod.cobertura(self.MESES, empresas_extras=extras)
        self._montar_matriz(dados)

        self._recentes = arq_mod.historico()
        atual = self._recentes[0] if self._recentes else None
        if atual:
            self.b_continuar.setEnabled(True)
            self.b_continuar.setText(
                "Continuar: %s · %s"
                % (atual.get("nome") or atual.get("cnpj"),
                   arq_mod.formatar_periodo(atual.get("periodo"))))
        else:
            self.b_continuar.setEnabled(False)
            self.b_continuar.setText("Continuar")

        n_emp, n_per, n_bytes = arq_mod.resumo_acervo()
        self.lbl_acervo.setText(
            "%d empresa(s) · %d período(s) · %.1f MB arquivados"
            % (n_emp, n_per, n_bytes / (1024.0 * 1024.0)))
        self._montar_pendencias(arq_mod.pendencias(cadastradas))

    def _montar_matriz(self, dados):
        periodos = dados["periodos"]
        linhas = dados["empresas"]
        pal = tema.atual()
        self.tab.setSortingEnabled(False)
        self.tab.setColumnCount(1 + len(periodos))
        self.tab.setHorizontalHeaderLabels(
            ["Empresa"] + [arq_mod.formatar_periodo(p) for p in periodos])
        self.tab.setRowCount(len(linhas))
        self._matriz = linhas
        self._periodos = periodos
        for i, emp in enumerate(linhas):
            it = QTableWidgetItem(emp["nome"] or emp["cnpj"])
            it.setToolTip(emp_mod.formatar_cnpj(emp["cnpj"]))
            self.tab.setItem(i, 0, it)
            for j, cel in enumerate(emp["celulas"], start=1):
                marca, cor, dica = self._marca(cel)
                item = QTableWidgetItem(marca)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(QColor(cor))
                item.setToolTip(dica)
                self.tab.setItem(i, j, item)
        # a matriz tem poucas linhas e colunas estreitas: deixar as colunas de
        # período dividirem a largura evita o vazio à direita, e limitar a
        # altura ao conteúdo impede que três empresas ocupem meia tela
        cab = self.tab.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        altura = cab.height() + 2
        for i in range(self.tab.rowCount()):
            altura += self.tab.rowHeight(i)
        self.tab.setMaximumHeight(max(120, altura + 4))

    @staticmethod
    def _marca(cel):
        pal = tema.atual()
        if cel["icms"] and cel["contrib"]:
            return "\u25cf\u25cf", pal.ok, "ICMS/IPI e PIS/COFINS arquivados"
        if cel["icms"]:
            return "\u25cf", pal.info, "só o EFD ICMS/IPI está arquivado"
        if cel["contrib"]:
            return "\u25cf", pal.warn, "só o EFD Contribuições está arquivado"
        return "—", pal.ink_3, "nada arquivado aqui neste período"

    def _montar_pendencias(self, pend):
        partes = []
        for cnpj, nome in pend["sem_cadastro"]:
            partes.append(
                "• <b>%s</b> tem arquivo mas não está cadastrada — sem o "
                "regime declarado, as rotinas de conferência não rodam para "
                "ela." % (nome or emp_mod.formatar_cnpj(cnpj)))
        for cnpj, nome in pend["sem_arquivo"]:
            partes.append(
                "• <b>%s</b> está cadastrada mas ainda não teve nenhum "
                "arquivo aberto aqui." % (nome or emp_mod.formatar_cnpj(cnpj)))
        if partes:
            self.lbl_pend.setText("<br>".join(partes))
            self.lbl_pend.setProperty("role", "aviso")
        else:
            self.lbl_pend.setText("Nada pendente: todas as empresas com "
                                  "arquivo estão cadastradas.")
            self.lbl_pend.setProperty("role", "ok")
        self.lbl_pend.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_pend.style().unpolish(self.lbl_pend)
        self.lbl_pend.style().polish(self.lbl_pend)

    # ------------------------------------------------------------ ações
    def _continuar(self):
        if self._recentes:
            h = self._recentes[0]
            if h.get("existe"):
                self.janela.abrir_caminho(h["caminho"])

    def _abrir_celula(self, linha, coluna):
        if coluna == 0 or not getattr(self, "_matriz", None):
            return
        emp = self._matriz[linha]
        periodo = self._periodos[coluna - 1]
        for h in arq_mod.historico(emp["cnpj"]):
            if h["periodo"] == periodo and h.get("existe"):
                self.janela.abrir_caminho(h["caminho"])
                return
        QMessageBox.information(
            self, "Período não arquivado",
            "Não há cópia de %s para %s neste sistema.\n\nIsso não significa "
            "que o arquivo não foi entregue — apenas que ele nunca foi aberto "
            "aqui." % (arq_mod.formatar_periodo(periodo),
                       emp["nome"] or emp["cnpj"]))

    # -------------------------------------------------- arrastar e soltar
    def dragEnterEvent(self, evento):
        if self._caminho_do_evento(evento):
            evento.acceptProposedAction()

    def dropEvent(self, evento):
        caminho = self._caminho_do_evento(evento)
        if caminho:
            evento.acceptProposedAction()
            self.janela.abrir_caminho(caminho)

    @staticmethod
    def _caminho_do_evento(evento):
        dados = evento.mimeData()
        if not dados.hasUrls():
            return ""
        for url in dados.urls():
            caminho = url.toLocalFile()
            if caminho.lower().endswith(".txt") and os.path.isfile(caminho):
                return caminho
        return ""

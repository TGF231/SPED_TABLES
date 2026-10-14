# -*- coding: utf-8 -*-
"""Painel de empresas: cadastro e histórico de arquivos."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from sped_tables.interface.formulario_empresa import FormularioEmpresa
from sped_tables.infra import cadastro
from sped_tables.dominio import empresas as emp_mod
from sped_tables.infra import arquivos as arq_mod
from sped_tables.interface import tema
from sped_tables.interface.comum import ajustes
from sped_tables.interface.comum import informar


class PainelEmpresas(QWidget):
    """Cadastro de empresas e histórico de arquivos arquivados.

    É um **painel da janela principal**, não um diálogo: como diálogo ficava
    apertado — lista, cadastro e histórico lado a lado pedem a largura inteira
    da janela. Fica numa página própria do widget central, fora das abas de
    bloco e dos modos Tabela/Relatório, e o botão *Empresas* da barra alterna
    entre ele e o editor.

    Funciona **sem nenhum arquivo aberto**: dá para cadastrar a empresa antes
    de importar o primeiro SPED. A lista reúne o que está em `empresas.json`
    com as empresas que já têm arquivo no histórico — uma empresa pode existir
    só no histórico (arquivo aberto sem cadastro) ou só no cadastro (cadastrada
    antes do primeiro arquivo).
    """

    COLS_HIST = ["Período", "Leiaute", "Atualizado em", "Origem", "Tamanho"]

    def __init__(self, janela, parent=None):
        super().__init__(parent)
        # referência explícita: como página de um QStackedWidget, `parent()`
        # não é a janela principal
        self.janela = janela
        self.mapa = cadastro.carregar_empresas()
        # a empresa escolhida é lembrada entre idas ao editor e entre sessões:
        # ler a seleção do widget na hora de recarregar falhava nos fluxos em
        # que a lista é remontada antes (cadastrar, remover, abrir do histórico)
        self._ultimo_cnpj = ajustes().value(
            "empresa_selecionada", "", type=str)

        lay = QVBoxLayout(self)
        corpo = QHBoxLayout()
        lay.addLayout(corpo, 1)

        # ------------------------------------------------ lista de empresas
        esq = QVBoxLayout()
        esq.addWidget(QLabel("Empresas cadastradas"))
        self.lista = QTableWidget(0, 3)
        self.lista.setHorizontalHeaderLabels(["CNPJ", "Nome", "Regime"])
        self.lista.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lista.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.lista.setAlternatingRowColors(True)
        self.lista.itemSelectionChanged.connect(self._empresa_mudou)
        esq.addWidget(self.lista, 1)

        botoes = QHBoxLayout()
        b_nova = QPushButton("Nova empresa…")
        b_nova.setProperty("role", "accent")
        b_nova.clicked.connect(self._nova)
        botoes.addWidget(b_nova)
        b_remover = QPushButton("Remover")
        b_remover.clicked.connect(self._remover)
        botoes.addWidget(b_remover)
        botoes.addStretch(1)
        esq.addLayout(botoes)
        corpo.addLayout(esq, 1)

        # ------------------------------------------------------- cadastro
        dir_ = QVBoxLayout()
        self.cx_cad = FormularioEmpresa("Dados da empresa", self._gravar)
        dir_.addWidget(self.cx_cad)

        # -------------------------------------------------------- histórico
        cx_hist = QGroupBox("Histórico de arquivos (cópias internas)")
        vh = QVBoxLayout(cx_hist)
        self.tab_hist = QTableWidget(0, len(self.COLS_HIST))
        self.tab_hist.setHorizontalHeaderLabels(self.COLS_HIST)
        self.tab_hist.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab_hist.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab_hist.setAlternatingRowColors(True)
        self.tab_hist.horizontalHeader().setStretchLastSection(True)
        self.tab_hist.cellDoubleClicked.connect(self._abrir_do_historico)
        vh.addWidget(self.tab_hist, 1)
        ah = QHBoxLayout()
        b_abrir = QPushButton("Abrir cópia selecionada")
        b_abrir.clicked.connect(lambda: self._abrir_do_historico(
            self.tab_hist.currentRow(), 0))
        ah.addWidget(b_abrir)
        b_excluir = QPushButton("Excluir do histórico")
        b_excluir.clicked.connect(self._excluir_historico)
        ah.addWidget(b_excluir)
        ah.addStretch(1)
        vh.addLayout(ah)
        dir_.addWidget(cx_hist, 1)
        corpo.addLayout(dir_, 2)

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_voltar = QPushButton("Voltar ao editor")
        b_voltar.clicked.connect(lambda: self.janela.mostrar_empresas(False))
        rod.addWidget(b_voltar)
        lay.addLayout(rod)

        self._carregar_lista(selecionar=self._ultimo_cnpj or None)

    def recarregar(self):
        """Relê o cadastro do disco e repinta, preservando a empresa atual."""
        self.mapa = cadastro.carregar_empresas()
        self._carregar_lista(selecionar=self._ultimo_cnpj or None)

    # ------------------------------------------------------------- lista
    def _carregar_lista(self, selecionar=None):
        # o histórico pode conter empresa ainda não cadastrada
        do_hist = arq_mod.empresas_no_historico()
        cnpjs = sorted(set(self.mapa) | set(do_hist))
        rot_pc = dict(emp_mod.REGIMES_PIS_COFINS)
        self.lista.setSortingEnabled(False)
        self.lista.setRowCount(len(cnpjs))
        for i, cnpj in enumerate(cnpjs):
            e = self.mapa.get(cnpj)
            nome = e.nome if e else do_hist.get(cnpj, "")
            regime = rot_pc.get(e.regime_pis_cofins, "") if e \
                else "(sem cadastro)"
            for c, v in enumerate((emp_mod.formatar_cnpj(cnpj), nome, regime)):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, cnpj)
                self.lista.setItem(i, c, it)
        self.lista.resizeColumnsToContents()
        if cnpjs:
            alvo = cnpjs.index(selecionar) if selecionar in cnpjs else 0
            self.lista.selectRow(alvo)
        else:
            self._empresa_mudou()

    def _cnpj_selecionado(self):
        row = self.lista.currentRow()
        if row < 0 or self.lista.item(row, 0) is None:
            return ""
        return self.lista.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _empresa_mudou(self):
        cnpj = self._cnpj_selecionado()
        if cnpj:
            self._ultimo_cnpj = cnpj
            ajustes().setValue("empresa_selecionada", cnpj)
        e = self.mapa.get(cnpj) or emp_mod.Empresa(cnpj=cnpj or "")
        self.cx_cad.setEnabled(bool(cnpj))
        self.cx_cad.mostrar(e)
        self._carregar_historico(cnpj)

    # ------------------------------------------------------------ cadastro
    def _nova(self):
        texto, ok = QInputDialog.getText(
            self, "Nova empresa", "CNPJ (só números ou formatado):")
        if not ok:
            return
        cnpj = emp_mod.so_digitos(texto)
        if len(cnpj) != 14:
            QMessageBox.warning(self, "Nova empresa",
                                "O CNPJ deve ter 14 dígitos.")
            return
        if cnpj in self.mapa:
            informar(self, "Nova empresa",
                     "Esta empresa já está cadastrada.")
        else:
            self.mapa[cnpj] = emp_mod.Empresa(cnpj=cnpj)
            cadastro.salvar_empresas(self.mapa)
        self._carregar_lista(selecionar=cnpj)

    def _gravar(self):
        cnpj = self._cnpj_selecionado()
        if not cnpj:
            return
        e = self.cx_cad.aplicar(
            self.mapa.get(cnpj) or emp_mod.Empresa(cnpj=cnpj))
        if e is None:
            return
        self.mapa[cnpj] = e
        try:
            cadastro.salvar_empresas(self.mapa)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Empresas", str(exc))
            return
        self._carregar_lista(selecionar=cnpj)
        informar(self, "Empresas", "Cadastro gravado.")

    def _remover(self):
        cnpj = self._cnpj_selecionado()
        if not cnpj or cnpj not in self.mapa:
            return
        resp = QMessageBox.question(
            self, "Remover empresa",
            "Remover %s do cadastro?\n\nO histórico de arquivos NÃO é "
            "apagado." % emp_mod.formatar_cnpj(cnpj),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        del self.mapa[cnpj]
        cadastro.salvar_empresas(self.mapa)
        self._carregar_lista()

    # ----------------------------------------------------------- histórico
    def _carregar_historico(self, cnpj):
        entradas = arq_mod.historico(cnpj) if cnpj else []
        self._hist = entradas
        self.tab_hist.setSortingEnabled(False)
        self.tab_hist.setRowCount(len(entradas))
        pal = tema.atual()
        for i, h in enumerate(entradas):
            vals = [arq_mod.formatar_periodo(h["periodo"]), h["layout"],
                    h["atualizado_em"], h.get("origem", ""),
                    "%.1f KB" % (h.get("tamanho", 0) / 1024.0)]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if not h.get("existe"):
                    it.setForeground(QColor(pal.bad))
                self.tab_hist.setItem(i, c, it)
        self.tab_hist.resizeColumnsToContents()

    def _abrir_do_historico(self, row, _col=0):
        if row is None or row < 0 or row >= len(getattr(self, "_hist", [])):
            return
        h = self._hist[row]
        if not h.get("existe"):
            QMessageBox.warning(self, "Histórico",
                                "A cópia interna não está mais na pasta:\n%s"
                                % h["caminho"])
            return
        if self.janela.abrir_caminho(h["caminho"]):
            # abriu: o lugar de olhar agora é o editor
            self.janela.mostrar_empresas(False)

    def _excluir_historico(self):
        row = self.tab_hist.currentRow()
        if row < 0 or row >= len(getattr(self, "_hist", [])):
            return
        h = self._hist[row]
        resp = QMessageBox.question(
            self, "Excluir do histórico",
            "Excluir a cópia interna de %s (%s)?\n\nO arquivo de origem "
            "não é afetado." % (arq_mod.formatar_periodo(h["periodo"]),
                                h["layout"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        arq_mod.remover(h["cnpj"], h["layout"], h["periodo"])
        self._carregar_historico(h["cnpj"])

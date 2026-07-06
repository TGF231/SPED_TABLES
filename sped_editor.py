# -*- coding: utf-8 -*-
"""
sped_editor.py
--------------
Editor visual de arquivos SPED (EFD ICMS/IPI e EFD Contribuições) em PyQt6.

A interface reproduz o comportamento do *Validador do SPED*:

    Janela
    └── QTabWidget  (uma aba por BLOCO: 0, A, C, D, E, ...)
        └── QTabWidget  (uma sub-aba por REGISTRO principal: C001, C100, ...)
            └── Master-Detail
                ├── grade editável (linhas = registros, colunas = campos)
                └── QTabWidget de filhos (Itens C170, Analítico C190, ...)
                    └── outro Master-Detail (recursivo)

O modelo de dados (parser, hierarquia, gravação e recálculo do bloco 9)
fica em `sped_model.py`; os nomes de campos/níveis em `sped_layouts.py`.

Como executar:
    pip install PyQt6
    python sped_editor.py
"""

import sys
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QSplitter, QPushButton,
    QFileDialog, QMessageBox, QLabel, QHeaderView, QAbstractItemView,
    QToolBar, QStatusBar,
)

from sped_model import SpedDocument


# ---------------------------------------------------------------------------
# Widget Master-Detail (recursivo)
# ---------------------------------------------------------------------------
class MasterDetailWidget(QWidget):
    """
    Mostra uma grade de registros de um mesmo TIPO e, ao selecionar uma linha
    que possua registros-filho, exibe abaixo um QTabWidget com uma sub-aba
    por tipo de filho — cada uma contendo recursivamente outro
    MasterDetailWidget.

    Parâmetros
    ----------
    doc        : SpedDocument
    tipo       : str               -> tipo de registro desta grade (ex.: "C100")
    provider   : callable -> list  -> devolve a lista atual de registros
                                      (consultada de novo após inserir/remover)
    pai        : Registro | None   -> registro-pai comum a estes registros
                                      (usado ao inserir um novo)
    on_change  : callable | None   -> chamada quando o documento é alterado
    """

    def __init__(self, doc, tipo, provider, pai=None, on_change=None,
                 parent=None):
        super().__init__(parent)
        self.doc = doc
        self.tipo = tipo
        self.provider = provider
        self.pai = pai
        self.on_change = on_change
        self._registros = []          # ordem espelhada na tabela
        self._detalhe_cache = {}      # uid -> widget de detalhe já criado

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- barra de ações da grade ---
        barra = QHBoxLayout()
        self.lbl = QLabel()
        self.lbl.setStyleSheet("color:#444;")
        btn_add = QPushButton("➕ Adicionar linha")
        btn_del = QPushButton("➖ Remover linha")
        btn_add.clicked.connect(self._adicionar)
        btn_del.clicked.connect(self._remover)
        barra.addWidget(self.lbl)
        barra.addStretch(1)
        barra.addWidget(btn_add)
        barra.addWidget(btn_del)
        layout.addLayout(barra)

        # --- splitter grade / detalhe ---
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter, 1)

        self.tabela = QTableWidget()
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.itemSelectionChanged.connect(self._sel_mudou)
        self.tabela.itemChanged.connect(self._celula_editada)
        self.tabela.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.splitter.addWidget(self.tabela)

        # área de detalhe (preenchida sob demanda)
        self.area_detalhe = QTabWidget()
        self.area_detalhe.setVisible(False)
        self.area_detalhe.setMovable(False)
        self.splitter.addWidget(self.area_detalhe)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

        self._carregando = False
        self.recarregar()

    # ------------------------------------------------------------------ grade
    def recarregar(self):
        """Repreenche a grade a partir do provider (após inserir/remover)."""
        self._carregando = True
        self.tabela.blockSignals(True)

        self._registros = list(self.provider())
        colunas = self.doc.colunas(self.tipo, self._registros) \
            if self._registros else self.doc.colunas(self.tipo, [])
        self.tabela.clear()
        self.tabela.setColumnCount(len(colunas))
        self.tabela.setHorizontalHeaderLabels(colunas)
        self.tabela.setRowCount(len(self._registros))

        for i, r in enumerate(self._registros):
            for j in range(len(colunas)):
                texto = r.valor(j)
                item = QTableWidgetItem(texto)
                if j == 0:
                    # coluna REG é fixa (não editável): muda a hierarquia
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                    item.setForeground(QColor("#1565c0"))
                # guarda o registro na 1ª coluna para referência rápida
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, r.uid)
                self.tabela.setItem(i, j, item)

        hdr = self.tabela.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabela.resizeColumnsToContents()
        # evita colunas exageradamente largas
        for c in range(self.tabela.columnCount()):
            if self.tabela.columnWidth(c) > 320:
                self.tabela.setColumnWidth(c, 320)

        self.lbl.setText("%s — %d registro(s)" % (self.tipo,
                                                  len(self._registros)))
        self.tabela.blockSignals(False)
        self._carregando = False
        self._detalhe_cache.clear()
        self._mostrar_detalhe(None)

    def _registro_da_linha(self, linha):
        if 0 <= linha < len(self._registros):
            return self._registros[linha]
        return None

    # --------------------------------------------------------------- edição
    def _celula_editada(self, item):
        if self._carregando:
            return
        r = self._registro_da_linha(item.row())
        if r is None:
            return
        r.set_valor(item.column(), item.text())
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------ detalhe
    def _sel_mudou(self):
        linha = self.tabela.currentRow()
        r = self._registro_da_linha(linha)
        self._mostrar_detalhe(r)

    def _mostrar_detalhe(self, registro):
        self.area_detalhe.clear()
        if registro is None or not self.doc.tem_detalhe(registro):
            self.area_detalhe.setVisible(False)
            return

        # uma sub-aba por tipo de filho
        for tipo_filho in self.doc.tipos_filhos(registro):
            # provider fecha sobre (registro, tipo_filho) atuais
            def make_provider(reg=registro, t=tipo_filho):
                return lambda: self.doc.filhos_por_tipo(reg, t)

            sub = MasterDetailWidget(
                self.doc, tipo_filho, make_provider(),
                pai=registro, on_change=self.on_change)
            n = len(self.doc.filhos_por_tipo(registro, tipo_filho))
            rotulo = "%s (%d)" % (tipo_filho, n)
            self.area_detalhe.addTab(sub, rotulo)

        self.area_detalhe.setVisible(True)

    # ------------------------------------------------------- inserir/remover
    def _resolver_pai(self):
        """Pai a usar ao inserir um novo registro nesta grade."""
        if self.pai is not None:
            return self.pai
        if self._registros:
            return self._registros[0].pai
        return None

    def _adicionar(self):
        pai = self._resolver_pai()
        depois = self._registros[-1] if self._registros else pai
        novo = self.doc.novo_registro(self.tipo, pai=pai, depois=depois)
        self.recarregar()
        # seleciona a linha recém-criada
        for i, r in enumerate(self._registros):
            if r.uid == novo.uid:
                self.tabela.selectRow(i)
                break
        if self.on_change:
            self.on_change()

    def _remover(self):
        linha = self.tabela.currentRow()
        r = self._registro_da_linha(linha)
        if r is None:
            QMessageBox.information(self, "Remover",
                                    "Selecione uma linha para remover.")
            return
        n_filhos = len(r.filhos)
        msg = "Remover o registro %s" % r.reg
        if n_filhos:
            msg += " e seus %d registro(s) filho(s)" % n_filhos
        msg += "?"
        if QMessageBox.question(self, "Confirmar remoção", msg) \
                != QMessageBox.StandardButton.Yes:
            return
        self.doc.remover_registro(r)
        self.recarregar()
        if self.on_change:
            self.on_change()


# ---------------------------------------------------------------------------
# Aba de um BLOCO (lazy): QTabWidget com uma sub-aba por tipo principal
# ---------------------------------------------------------------------------
class BlocoWidget(QWidget):
    def __init__(self, doc, bloco, on_change=None, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.bloco = bloco
        self.on_change = on_change
        self._construido = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        lay.addWidget(self.tabs)

    def construir(self):
        """Cria as sub-abas de tipo só quando o bloco é aberto (lazy)."""
        if self._construido:
            return
        self._construido = True
        for tipo in self.doc.tipos_raiz_do_bloco(self.bloco):
            def make_provider(b=self.bloco, t=tipo):
                return lambda: self.doc.registros_raiz_por_tipo(b, t)

            w = MasterDetailWidget(self.doc, tipo, make_provider(),
                                   pai=None, on_change=self.on_change)
            n = len(self.doc.registros_raiz_por_tipo(self.bloco, tipo))
            self.tabs.addTab(w, "%s (%d)" % (tipo, n))


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------
class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.doc = None
        self.alterado = False
        self.setWindowTitle("Editor SPED")
        self.resize(1200, 760)

        self._criar_acoes()
        self._criar_barra()

        self.tabs_bloco = QTabWidget()
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs_bloco.currentChanged.connect(self._bloco_aberto)

        vazio = QLabel("Abra um arquivo SPED para começar  (Ctrl+O)")
        vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio.setStyleSheet("color:#888; font-size:16px;")
        self._placeholder = vazio
        self.setCentralWidget(vazio)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Pronto.")

    # --------------------------------------------------------------- ações
    def _criar_acoes(self):
        self.act_abrir = QAction("Abrir…", self)
        self.act_abrir.setShortcut(QKeySequence.StandardKey.Open)
        self.act_abrir.triggered.connect(self.abrir)

        self.act_salvar = QAction("Salvar", self)
        self.act_salvar.setShortcut(QKeySequence.StandardKey.Save)
        self.act_salvar.triggered.connect(self.salvar)
        self.act_salvar.setEnabled(False)

        self.act_salvar_como = QAction("Salvar como…", self)
        self.act_salvar_como.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_salvar_como.triggered.connect(self.salvar_como)
        self.act_salvar_como.setEnabled(False)

        self.act_sair = QAction("Sair", self)
        self.act_sair.triggered.connect(self.close)

    def _criar_barra(self):
        menu = self.menuBar().addMenu("&Arquivo")
        menu.addAction(self.act_abrir)
        menu.addAction(self.act_salvar)
        menu.addAction(self.act_salvar_como)
        menu.addSeparator()
        menu.addAction(self.act_sair)

        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.act_abrir)
        tb.addAction(self.act_salvar)
        tb.addAction(self.act_salvar_como)

    # ------------------------------------------------------------ abrir
    def abrir(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir arquivo SPED", "",
            "Arquivos SPED (*.txt);;Todos os arquivos (*)")
        if not caminho:
            return
        try:
            doc = SpedDocument.carregar(caminho)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao abrir",
                                 "Não foi possível ler o arquivo:\n%s" % e)
            return
        self.doc = doc
        self.alterado = False
        self._montar_abas()
        self.act_salvar.setEnabled(True)
        self.act_salvar_como.setEnabled(True)
        nome = os.path.basename(caminho)
        tipo = "EFD Contribuições" if doc.layout == "CONTRIB" \
            else "EFD ICMS/IPI"
        self.setWindowTitle("Editor SPED — %s  [%s]" % (nome, tipo))
        self.statusBar().showMessage(
            "%s carregado: %d registros, layout %s."
            % (nome, len(doc.registros), tipo))

    def _montar_abas(self):
        self.tabs_bloco = QTabWidget()
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs_bloco.currentChanged.connect(self._bloco_aberto)
        self.setCentralWidget(self.tabs_bloco)

        nomes_bloco = {
            "0": "0 · Abertura/Identificação", "A": "A · Serviços",
            "B": "B · ISS", "C": "C · Mercadorias (ICMS/IPI)",
            "D": "D · Serviços (ICMS/Transporte)", "E": "E · Apuração ICMS/IPI",
            "F": "F · Demais Documentos/Operações", "G": "G · CIAP",
            "H": "H · Inventário", "I": "I · Outras informações",
            "K": "K · Produção/Estoque", "M": "M · Apuração PIS/COFINS",
            "P": "P · Apuração Previdenciária", "1": "1 · Outras",
            "9": "9 · Controle/Totais",
        }
        self._blocos = []
        for b in self.doc.blocos():
            w = BlocoWidget(self.doc, b, on_change=self._marcar_alterado)
            self._blocos.append(w)
            self.tabs_bloco.addTab(w, nomes_bloco.get(b, "Bloco %s" % b))
        if self._blocos:
            self.tabs_bloco.setCurrentIndex(0)
            self._bloco_aberto(0)

    def _bloco_aberto(self, idx):
        if 0 <= idx < len(getattr(self, "_blocos", [])):
            self._blocos[idx].construir()

    # ------------------------------------------------------------ salvar
    def _marcar_alterado(self):
        self.alterado = True
        t = self.windowTitle()
        if not t.endswith(" *"):
            self.setWindowTitle(t + " *")

    def salvar(self):
        if not self.doc:
            return
        if not self.doc.caminho:
            return self.salvar_como()
        self._gravar(self.doc.caminho)

    def salvar_como(self):
        if not self.doc:
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar arquivo SPED",
            self.doc.caminho or "", "Arquivos SPED (*.txt)")
        if not caminho:
            return
        self._gravar(caminho)

    def _gravar(self, caminho):
        try:
            self.doc.salvar(caminho)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar",
                                 "Não foi possível gravar:\n%s" % e)
            return
        self.alterado = False
        nome = os.path.basename(caminho)
        self.setWindowTitle(self.windowTitle().rstrip(" *"))
        self.statusBar().showMessage(
            "Salvo em %s (bloco 9 recalculado)." % nome)
        QMessageBox.information(
            self, "Salvo",
            "Arquivo gravado com sucesso:\n%s\n\n"
            "Os registros de totalização (X990, 9900, 9990, 9999) "
            "foram recalculados automaticamente." % caminho)

    # ------------------------------------------------------------ fechar
    def closeEvent(self, event):
        if self.alterado:
            resp = QMessageBox.question(
                self, "Sair",
                "Há alterações não salvas. Deseja sair mesmo assim?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Editor SPED")
    # fonte um pouco menor deixa as grades mais densas (estilo planilha)
    f = QFont()
    f.setPointSize(max(8, f.pointSize() - 1))
    app.setFont(f)
    janela = JanelaPrincipal()
    janela.show()
    # abre direto se um caminho for passado na linha de comando
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        try:
            janela.doc = SpedDocument.carregar(sys.argv[1])
            janela.alterado = False
            janela._montar_abas()
            janela.act_salvar.setEnabled(True)
            janela.act_salvar_como.setEnabled(True)
        except Exception:  # noqa: BLE001
            pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

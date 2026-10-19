# -*- coding: utf-8 -*-
"""A base de referência em uso e a importação de uma mais nova.

A base traz o leiaute de cada versão, as tabelas oficiais e os guias; ela
atualiza sem programa novo. Antes de aceitar um pacote, a tela mostra a
impressão digital para conferir com a publicada."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QVBoxLayout)

from sped_tables.infra import base_referencia
from sped_tables.interface.comum import definir_papel, informar

NOMES = {"ICMS": "EFD ICMS/IPI", "CONTRIB": "EFD Contribuições"}


def _texto(manifesto, origem, digital):
    # leiaute que este programa não conhece (base de um programa mais novo)
    # aparece pelo código, em vez de derrubar a tela
    leiautes = "; ".join(
        "%s %s" % (NOMES.get(l, l), ", ".join(v))
        for l, v in sorted(manifesto.get("leiautes", {}).items()) if v)
    return ("Versão %s, de %s (%s).\nLeiautes: %s.\n"
            "Impressão digital (SHA-256):\n%s"
            % (manifesto.get("versao", "?"), manifesto.get("data", "?"),
               origem, leiautes or "nenhum", digital))


class DialogoBaseReferencia(QDialog):

    def __init__(self, parent=None, ao_importar=None):
        super().__init__(parent)
        self.ao_importar = ao_importar
        self.setWindowTitle("Base de referência")
        self.resize(560, 260)
        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl, 1)
        botoes = QHBoxLayout()
        b_importar = QPushButton("Importar base mais nova…")
        b_importar.clicked.connect(self._importar)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.reject)
        botoes.addWidget(b_importar)
        botoes.addStretch(1)
        botoes.addWidget(b_fechar)
        lay.addLayout(botoes)
        self._mostrar()

    def _mostrar(self):
        base, origem = base_referencia.em_uso()
        if base is None:
            self.lbl.setText(
                "Nenhuma base de referência legível: as verificações que "
                "dependem do leiaute e das tabelas oficiais estão "
                "desligadas. Importe uma base.")
            definir_papel(self.lbl, "erro")
            return
        definir_papel(self.lbl, "info")
        self.lbl.setText(_texto(base.manifesto(), origem,
                                base_referencia.impressao_digital(
                                    base.caminho)))

    def _confirmar(self, manifesto, digital):
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Importar base de referência")
        caixa.setText(
            "Importar a base %s, de %s?\n\nImpressão digital (SHA-256):\n%s"
            "\n\nCompare com a publicada antes de confirmar."
            % (manifesto.get("versao", "?"), manifesto.get("data", "?"),
               digital))
        sim = caixa.addButton("Importar", QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.exec()
        return caixa.clickedButton() is sim

    def _importar(self):
        caminho, _f = QFileDialog.getOpenFileName(
            self, "Pacote da base de referência", "",
            "Base de referência (base_referencia-*.zip);;Todos (*)")
        if not caminho:
            return
        try:
            pacote = base_referencia.inspecionar(caminho)
            if not pacote["confere"]:
                raise base_referencia.BaseRecusada(
                    "A impressão digital do banco não confere com a do "
                    "manifesto: o arquivo foi alterado ou está corrompido.")
            if not self._confirmar(pacote["manifesto"], pacote["sha256"]):
                return
            manifesto = base_referencia.importar(caminho)
        except base_referencia.BaseRecusada as exc:
            QMessageBox.warning(self, "Base de referência", str(exc))
            return
        if self.ao_importar is not None:
            self.ao_importar()
        self._mostrar()
        informar(self, "Base de referência",
                 "Base %s importada: ela já vale para o próximo "
                 "diagnóstico." % manifesto["versao"])

# -*- coding: utf-8 -*-
"""Prévia de *Regenerar entradas pelos XMLs*: o que muda, campo a campo, o
que fica de fora e o que precisa de revisão — antes de tocar no arquivo."""

from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
)

from sped_tables.dominio.regeneracao import _chave


def _tabela(cabecalho, linhas):
    t = QTableWidget(len(linhas), len(cabecalho))
    t.setHorizontalHeaderLabels(cabecalho)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setStretchLastSection(True)
    for i, linha in enumerate(linhas):
        for j, v in enumerate(linha):
            t.setItem(i, j, QTableWidgetItem(str(v)))
    t.resizeColumnsToContents()
    return t


class DialogoRegenerarEntradas(QDialog):

    def __init__(self, doc, plano, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Regenerar entradas pelos XMLs")
        self.resize(820, 560)
        lay = QVBoxLayout(self)
        p = plano
        resumo = QLabel(
            "<b>%d</b> nota(s) de entrada regenerada(s) pelo XML · <b>%d</b> "
            "incluída(s) (o arquivo não tinha) · <b>%d</b> mantida(s) sem "
            "XML na pasta · <b>%d</b> cadastro(s) novo(s) (0150/0190/0200)."
            % (len(p.substituir), len(p.incluir), len(p.sem_xml),
               len(p.cadastro)))
        resumo.setWordWrap(True)
        lay.addWidget(resumo)
        if p.bloqueados:
            av = QLabel("⚠ %d nota(s) <b>não</b> serão regeneradas: algum "
                        "item ficaria inválido (veja a aba Fora). O original "
                        "fica como está." % len(p.bloqueados))
            av.setProperty("role", "aviso")
            av.setWordWrap(True)
            lay.addWidget(av)

        abas = QTabWidget()
        abas.addTab(_tabela(
            ["Campo", "Valores que mudam"],
            sorted(p.mudancas.items(), key=lambda x: (-x[1], x[0]))),
            "O que muda (%d)" % sum(p.mudancas.values()))
        abas.addTab(_tabela(
            ["Tipo", "Documento", "Item", "Detalhe"],
            [(a["tipo"], a["documento"], a["item"], a["detalhe"])
             for a in p.revisar]), "Revisar (%d)" % len(p.revisar))
        fora = ([("Não regenerada", onde, "; ".join(m))
                 for onde, m in p.bloqueados]
                + [("Sem XML na pasta (mantida)", _chave(doc, c), "")
                   for c in p.sem_xml]
                + [("XML de outro período", ch, "data %s" % d)
                   for ch, d in p.fora_periodo])
        abas.addTab(_tabela(["Situação", "Documento", "Motivo"], fora),
                    "Fora (%d)" % len(fora))
        lay.addWidget(abas, 1)

        nota = QLabel(
            "A escrituração de cada produto (código próprio, CFOP, CST, "
            "crédito) vem do próprio arquivo; quantidades, valores e "
            "impostos, do XML. Depois, recalcule a apuração (E110 no "
            "ICMS/IPI, bloco M no Contribuições).")
        nota.setWordWrap(True)
        nota.setProperty("role", "dica")
        lay.addWidget(nota)
        rod = QHBoxLayout()
        rod.addStretch(1)
        b_ok = QPushButton("Regenerar")
        b_ok.setEnabled(not p.vazio)
        b_ok.clicked.connect(self.accept)
        b_ca = QPushButton("Cancelar")
        b_ca.clicked.connect(self.reject)
        rod.addWidget(b_ok)
        rod.addWidget(b_ca)
        lay.addLayout(rod)

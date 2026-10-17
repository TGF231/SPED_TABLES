# -*- coding: utf-8 -*-
"""Ajuda do registro: o texto do guia prático e a declaração do PVA de cada
campo, numa janela que acompanha a grade (F1 ou menu de contexto)."""

import html

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout,
)

from sped_tables.dominio import ajuda

LIMITE_DICA = 700        # a dica do cabeçalho é um resumo; o resto é no F1


def _e(txt):
    return html.escape(txt or "")


def _curto(txt, limite):
    txt = txt or ""
    return txt if len(txt) <= limite else txt[:limite].rsplit(" ", 1)[0] + "…"


def _declaracao(c):
    partes = []
    if c["tipo"]:
        tam = c["tamanho"]
        if tam:
            partes.append("%s, %s %s" % (c["tipo"], "exatamente" if c["fixo"]
                                          else "até", tam))
        else:
            partes.append(c["tipo"])
    if c["decimais"]:
        partes.append("%s casas decimais" % c["decimais"])
    if c["obrigatorio"]:
        partes.append("obrigatório: %s" % c["obrigatorio"])
    return " · ".join(partes)


def _valores(c, limite=12):
    if not c["valores"]:
        return ""
    itens = ["%s%s" % (v, (" = %s" % s) if s else "")
             for v, s in c["valores"][:limite]]
    if len(c["valores"]) > limite:
        itens.append("…")
    return "; ".join(itens)


def _secoes(c, limite=None, valores=60):
    """As seções da ajuda de um campo, já em HTML: descrição (se diz mais
    que o rótulo), declaração, valores válidos, preenchimento e validação.
    `limite` corta os textos longos — a dica é um resumo, o F1 é inteiro."""
    def texto(t, n=limite):
        return _e(_curto(t, n) if n else t)
    if c["descricao"] and c["descricao"] != c["rotulo"]:
        yield _e(c["descricao"])
    decl = _declaracao(c)
    if decl:
        yield "<i>%s</i>" % _e(decl)
    val = _valores(c, limite=valores) or c["valores_guia"]
    if val:
        yield "<b>Valores válidos:</b> %s" % texto(val, limite and 300)
    if c["preenchimento"]:
        yield "<b>Preenchimento:</b> %s" % texto(c["preenchimento"])
    if c["validacao"]:
        yield "<b>Validação:</b> %s" % texto(c["validacao"])


def _titulo(c):
    return "%s%s" % (_e(c["nome"]), (" — %s" % _e(c["rotulo"]))
                     if c["rotulo"] else "")


def dica_html(c):
    """Dica do cabeçalho da coluna: nome, descrição, declaração e o começo
    do que o guia diz."""
    linhas = ["<b>%s</b>" % _titulo(c)]
    linhas += _secoes(c, LIMITE_DICA, valores=12)
    linhas.append("<i>F1: ajuda completa do registro</i>")
    return "<p>%s</p>" % "<br>".join(linhas)


def html_do_registro(r, campo_atual=None):
    """A página de ajuda do registro inteiro."""
    out = ["<h2>%s — %s</h2>" % (_e(r["reg"]), _e(r["titulo"]))]
    meta = []
    if r["nivel"] is not None:
        meta.append("nível %s" % r["nivel"])
    if r["ocorrencia"]:
        meta.append("ocorrência %s" % _e(r["ocorrencia"]))
    if meta:
        out.append("<p><i>%s</i></p>" % " · ".join(meta))
    if r["objetivo"]:
        out.append("<p>%s</p>" % _e(r["objetivo"]))
    if r["validacao_registro"]:
        out.append("<p><b>Validação do registro:</b> %s</p>"
                   % _e(r["validacao_registro"]))
    if r["observacoes"]:
        out.append("<p><b>Observações:</b> %s</p>" % _e(r["observacoes"]))
    for c in r["campos"]:
        marca = " ◀" if c["nome"] == campo_atual else ""
        out.append('<a name="campo_%s"></a><h3>%02d %s%s</h3>'
                   % (_e(c["nome"]), c["n"], _titulo(c), marca))
        out += ["<p>%s</p>" % s for s in _secoes(c)]
    if r["fonte"]:
        out.append("<p><i>Fonte: %s e descritor do PVA instalado.</i></p>"
                   % _e(r["fonte"]))
    return "\n".join(out)


class DialogoAjuda(QDialog):
    """Ajuda de um registro, rolada até o campo pedido. Não modal: a pessoa
    lê e continua editando a grade."""

    def __init__(self, layout, reg, campo=None, parent=None, versao=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuda do registro %s" % reg)
        self.resize(760, 640)
        lay = QVBoxLayout(self)
        r = ajuda.do_registro(layout, reg, versao)
        if not r["titulo"] and not any(c["preenchimento"] or c["validacao"]
                                       for c in r["campos"]):
            aviso = QLabel("O guia prático não está disponível para este "
                           "registro.")
            aviso.setProperty("role", "aviso")
            lay.addWidget(aviso)
        self.texto = QTextBrowser()
        self.texto.setOpenExternalLinks(False)
        self.texto.setHtml(html_do_registro(r, campo))
        lay.addWidget(self.texto, 1)
        botoes = QDialogButtonBox()
        fechar = botoes.addButton("Fechar",
                                  QDialogButtonBox.ButtonRole.RejectRole)
        fechar.clicked.connect(self.close)
        lay.addWidget(botoes)
        if campo:
            self.texto.scrollToAnchor("campo_%s" % campo)

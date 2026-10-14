# -*- coding: utf-8 -*-
"""Aba de resumo do arquivo aberto."""

import datetime
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from sped_tables.version import APP_NAME
from sped_tables.version import __version__
from sped_tables.interface import tema
from sped_tables.interface.comum import _br, _data_br


class ResumoWidget(QWidget):
    """Aba inicial: dados do 0000, metadados, lista de registros e a apuração
    do período (ICMS: entradas, saídas e E110; Contribuições: por CST)."""

    def __init__(self, doc, caminho, parent=None):
        super().__init__(parent)
        self.doc = doc
        ext = QVBoxLayout(self)
        ext.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        ext.addWidget(scroll)
        cont = QWidget()
        scroll.setWidget(cont)
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        def v(nome):
            i = doc._ix("0000", nome)
            r0 = next((r for r in doc.registros if r.reg == "0000"), None)
            return (r0.valor(i) if (r0 and i is not None) else "") or ""

        tipo = ("EFD Contribuições" if doc.layout == "CONTRIB"
                else "EFD ICMS/IPI")
        nome = v("NOME") or "—"
        cnpj = v("CNPJ")
        cnpj_fmt = ("%s.%s.%s/%s-%s" % (cnpj[0:2], cnpj[2:5], cnpj[5:8],
                                        cnpj[8:12], cnpj[12:14])
                    if len(cnpj) == 14 else (cnpj or "—"))
        periodo = "%s a %s" % (_data_br(v("DT_INI")), _data_br(v("DT_FIN")))
        mod = "—"
        if caminho and os.path.exists(caminho):
            ts = os.path.getmtime(caminho)
            mod = datetime.datetime.fromtimestamp(ts).strftime(
                "%d/%m/%Y %H:%M:%S")
        nome_arq = os.path.basename(caminho) if caminho else "(não salvo)"

        # cor do HTML também sai do tema: literal some no tema escuro
        pal = tema.atual()
        rot = "color:%s" % pal.ink_2
        cab = QLabel(
            ("<div style='font-size:20px;font-weight:bold;color:{info}'>%s</div>"
             "<div style='{rot};margin-bottom:8px'>%s &nbsp;•&nbsp; %s</div>"
             "<table cellspacing='6'>"
             "<tr><td style='{rot}'>CNPJ</td><td><b>%s</b></td>"
             "<td style='{rot};padding-left:24px'>IE</td><td><b>%s</b></td>"
             "<td style='{rot};padding-left:24px'>UF</td>"
             "<td><b>%s</b></td></tr>"
             "<tr><td style='{rot}'>Período</td><td><b>%s</b></td>"
             "<td style='{rot};padding-left:24px'>Layout</td>"
             "<td colspan='3'><b>%s</b></td></tr></table>"
             ).format(info=pal.info, rot=rot)
            % (nome, tipo, "%s v%s" % (APP_NAME, __version__),
               cnpj_fmt, v("IE") or "—", v("UF") or "—", periodo, doc.layout))
        cab.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(cab)

        meta = QLabel(
            ("<span style='{0}'>Arquivo:</span> %s &nbsp;&nbsp;"
             "<span style='{0}'>Modificado em:</span> %s &nbsp;&nbsp;"
             "<span style='{0}'>Total de registros:</span> <b>%d</b>"
             ).format(rot)
            % (nome_arq, mod, len(doc.registros)))
        meta.setTextFormat(Qt.TextFormat.RichText)
        meta.setWordWrap(True)
        lay.addWidget(meta)

        # ---- apuração do período (conforme o layout) ---------------------
        if doc.layout == "ICMS":
            self._painel_icms(lay)
        else:
            self._painel_contrib(lay)

        # ---- lista simples de registros (agrupada por bloco) -------------
        from collections import Counter
        cont_reg = Counter(r.reg for r in doc.registros)
        nomes_bloco = {
            "0": "Abertura", "A": "Serviços", "B": "ISS", "C": "Mercadorias",
            "D": "Transporte/Serviços", "E": "Apuração ICMS/IPI", "F": "Demais",
            "G": "CIAP", "H": "Inventário", "I": "Outras", "K": "Produção",
            "M": "PIS/COFINS", "P": "Previdenciária", "1": "Outras",
            "9": "Controle",
        }
        por_bloco = {}
        for reg in sorted(cont_reg):
            por_bloco.setdefault(reg[0], []).append(
                "%s&nbsp;(%d)" % (reg, cont_reg[reg]))
        linhas_html = []
        for b in sorted(por_bloco):
            rot = nomes_bloco.get(b, "")
            linhas_html.append(
                "<div style='margin:3px 0'><b>Bloco %s</b>"
                "<span style='color:%s'> — %s:</span> %s</div>"
                % (b, tema.atual().ink_2, rot, ", ".join(por_bloco[b])))
        lst = QLabel("<div style='font-weight:bold;margin-bottom:4px'>"
                     "Registros</div>" + "".join(linhas_html))
        lst.setTextFormat(Qt.TextFormat.RichText)
        lst.setWordWrap(True)
        lay.addWidget(lst)
        lay.addStretch(1)

    # ---------------------------------------------------------- helpers UI
    @staticmethod
    def _tabela_html(titulo, colunas, linhas, total=None, aligns=None):
        aligns = aligns or (["left"] + ["right"] * (len(colunas) - 1))
        borda = tema.atual().border_2
        th = "".join("<th style='text-align:%s;padding:2px 10px;"
                     "border-bottom:1px solid %s'>%s</th>" % (a, borda, c)
                     for a, c in zip(aligns, colunas))
        trs = []
        for ln in linhas:
            tds = "".join("<td style='text-align:%s;padding:1px 10px'>%s</td>"
                          % (a, x) for a, x in zip(aligns, ln))
            trs.append("<tr>%s</tr>" % tds)
        tot_html = ""
        if total is not None:
            tds = "".join("<td style='text-align:%s;padding:3px 10px;"
                          "border-top:1px solid %s;font-weight:bold'>%s</td>"
                          % (a, borda, x) for a, x in zip(aligns, total))
            tot_html = "<tr>%s</tr>" % tds
        return ("<div style='font-weight:bold;margin:10px 0 2px'>%s</div>"
                "<table cellspacing='0' style='font-size:12px'>"
                "<tr>%s</tr>%s%s</table>"
                % (titulo, th, "".join(trs), tot_html))

    def _painel_icms(self, lay):
        doc = self.doc
        cols = ["CST", "CFOP", "Alíq.", "Valor Operação", "BC ICMS",
                "Valor ICMS", "BC ST", "ICMS ST"]

        def montar(op, titulo):
            linhas, tot = doc.resumo_c190(op)
            corpo = [[c, f, _br(a), _br(vo), _br(vb), _br(vi), _br(vbs),
                      _br(vis)] for (c, f, a, vo, vb, vi, vbs, vis) in linhas]
            total = ["TOTAL", "", "", _br(tot[0]), _br(tot[1]), _br(tot[2]),
                     _br(tot[3]), _br(tot[4])]
            return self._tabela_html(titulo, cols, corpo, total)

        html = (montar("0", "Entradas — resumo por CST / CFOP / alíquota")
                + montar("1", "Saídas — resumo por CST / CFOP / alíquota"))

        ap = doc.apuracao_e110()
        if ap:
            itens = [
                ("Saídas com débito do imposto", "VL_TOT_DEBITOS"),
                ("Créditos por entradas e aquisições", "VL_TOT_CREDITOS"),
                ("Ajustes a débito", "VL_TOT_AJ_DEBITOS"),
                ("Ajustes a crédito", "VL_TOT_AJ_CREDITOS"),
                ("Saldo credor do período anterior", "VL_SLD_CREDOR_ANT"),
                ("Saldo devedor apurado", "VL_SLD_APURADO"),
                ("ICMS a recolher", "VL_ICMS_RECOLHER"),
                ("Saldo credor a transportar", "VL_SLD_CREDOR_TRANSPORTAR"),
            ]
            linhas = [[rot, _br(ap.get(k, 0.0))] for rot, k in itens]
            html += self._tabela_html(
                "Apuração do ICMS — operações próprias (E110)",
                ["Descrição", "Valor R$"], linhas,
                aligns=["left", "right"])

        w = QLabel(html)
        w.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(w)

    def _painel_contrib(self, lay):
        c = self.doc.consolidacao_cst_pis_cofins()
        cols = ["CST", "Valor Total do Item", "BC PIS/Pasep", "BC COFINS"]

        def corpo(linhas):
            return [[cst, _br(vi), _br(bp), _br(bc)]
                    for (cst, vi, bp, bc) in linhas]

        html = self._tabela_html(
            "Receitas / Saídas", cols, corpo(c["receitas"]),
            ["TOTAL RECEITAS/SAÍDAS", _br(c["tot_receitas"][0]),
             _br(c["tot_receitas"][1]), _br(c["tot_receitas"][2])])
        html += self._tabela_html(
            "Aquisições / Custos / Despesas", cols, corpo(c["aquisicoes"]),
            ["TOTAL AQUISIÇÕES/CUSTOS", _br(c["tot_aquisicoes"][0]),
             _br(c["tot_aquisicoes"][1]), _br(c["tot_aquisicoes"][2])])
        if c["outras"]:
            html += self._tabela_html("Outras operações (CST 99)", cols,
                                      corpo(c["outras"]))
        w = QLabel(html)
        w.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(w)

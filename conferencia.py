# -*- coding: utf-8 -*-
"""
conferencia.py
--------------
Conferência de **entradas modelo 55** (NF-e de compra): compara cada item do
XML do fornecedor com o registro **C170** correspondente do SPED.

O vínculo usa o motor genérico `xml_fiscal.vincular`, casando **item XML ↔ C170**
pela chave **(mod, série, nNF, nItem)**. A ordem do item (nItem) é a chave porque
o **código do produto muda** entre a saída do fornecedor e a entrada do
comprador (cProd ≠ COD_ITEM) e o **CFOP também muda** (saída 5xxx → entrada
1xxx/2xxx). Por isso esses campos não servem de chave nem são conferidos por
igualdade; o que se confere é o **valor** do item.

Este módulo orquestra xml_fiscal (parsing/vínculo) + o SpedDocument (índices de
campo por layout); não depende de PyQt.
"""

from sped_model import _to_num
import xml_fiscal as xf


class Divergencia:
    __slots__ = ("mod", "serie", "nnf", "nitem", "escopo", "campo",
                 "valor_xml", "valor_sped", "obs")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))

    def linha_csv(self):
        return [self.mod, self.serie, self.nnf, self.nitem or "",
                self.escopo, self.campo,
                _fmt(self.valor_xml), _fmt(self.valor_sped), self.obs or ""]


def _fmt(v):
    if isinstance(v, float):
        return ("%0.2f" % v).replace(".", ",")
    return "" if v is None else str(v)


# comparações padrão item XML ↔ C170:
#   (rótulo, função-valor-do-item-XML, nome-do-campo-C170, tolerância)
COMPARACOES_PADRAO = [
    ("VL_ITEM", lambda it: it.vprod, "VL_ITEM", 0.01),
    ("VL_DESC", lambda it: it.vdesc, "VL_DESC", 0.01),
]


def conferir_entradas_55(doc, nfes, comparacoes=None, tol_doc=0.01):
    """
    Confere as entradas modelo 55 do documento SPED `doc` contra os XMLs `nfes`.

    Retorna um dicionário com:
      * resumo: contadores gerais;
      * divergencias: lista de Divergencia (valores que não batem);
      * sem_c170: itens do XML sem C170 correspondente (faltam no SPED);
      * sem_xml: C170 de entradas 55 sem item no XML (sobrando / sem XML);
      * docs_sem_xml: C100 modelo 55 (entrada) sem XML na pasta;
      * docs_sem_c100: XMLs modelo 55 sem C100 no SPED.
    """
    if comparacoes is None:
        comparacoes = COMPARACOES_PADRAO

    iC_mod = doc._ix("C100", "COD_MOD")
    iC_ser = doc._ix("C100", "SER")
    iC_num = doc._ix("C100", "NUM_DOC")
    iC_op = doc._ix("C100", "IND_OPER")
    iC_vdoc = doc._ix("C100", "VL_DOC")
    i170_item = doc._ix("C170", "NUM_ITEM")
    idx_cmp = [(rot, fn, doc._ix("C170", campo), t)
               for (rot, fn, campo, t) in comparacoes]

    nfes55 = [n for n in nfes if xf.norm(n.mod) == "55"]

    # --- nível documento: VL_DOC (C100) x vNF (XML) ----------------------
    c100_55 = [r for r in doc.registros
               if r.reg == "C100" and r.valor(iC_mod) == "55"
               and (r.valor(iC_op) or "").strip() == "0"]

    def ch_doc_c100(r):
        return (xf.norm(r.valor(iC_mod)), xf.norm(r.valor(iC_ser)),
                xf.norm(r.valor(iC_num)))

    pares_doc, docs_sem_c100, docs_sem_xml = xf.vincular(
        nfes55, xf.chave_doc, c100_55, ch_doc_c100)

    divergencias = []
    for nfe, c100s in pares_doc:
        c100 = c100s[0]
        vdoc = _to_num(c100.valor(iC_vdoc))
        if abs(vdoc - (nfe.vnf or 0.0)) > tol_doc:
            divergencias.append(Divergencia(
                mod=nfe.mod, serie=nfe.serie, nnf=nfe.nnf, nitem=None,
                escopo="documento", campo="VL_DOC x vNF",
                valor_xml=nfe.vnf, valor_sped=vdoc,
                obs="total do documento difere"))

    # --- nível item: item XML ↔ C170 por (mod, série, nNF, nItem) --------
    # Confere apenas os itens das notas que casaram no nível de documento,
    # para que "itens sem XML" signifique item a mais dentro de uma nota
    # efetivamente conferida (e não nota inteira sem XML na pasta).
    nfes_casadas = [nfe for nfe, _ in pares_doc]
    c100_casados = {id(c100s[0]) for _, c100s in pares_doc}
    itens_xml = [(nfe, it) for nfe in nfes_casadas for it in nfe.itens]
    c170s = [r for r in doc.registros
             if r.reg == "C170" and r.pai is not None
             and id(r.pai) in c100_casados]

    def ch_item_xml(par):
        nfe, it = par
        return xf.chave_item(nfe, it)

    def ch_item_c170(r):
        c = r.pai
        return (xf.norm(c.valor(iC_mod)), xf.norm(c.valor(iC_ser)),
                xf.norm(c.valor(iC_num)), xf.norm(r.valor(i170_item)))

    pares, sem_c170, sem_xml = xf.vincular(
        itens_xml, ch_item_xml, c170s, ch_item_c170)

    itens_conferidos = 0
    for (nfe, it), c170list in pares:
        c170 = c170list[0]
        itens_conferidos += 1
        for rot, fn_xml, idx, t in idx_cmp:
            if idx is None:
                continue
            vx = fn_xml(it) or 0.0
            vs = _to_num(c170.valor(idx))
            if abs(vx - vs) > t:
                divergencias.append(Divergencia(
                    mod=nfe.mod, serie=nfe.serie, nnf=nfe.nnf, nitem=it.nitem,
                    escopo="item", campo=rot, valor_xml=vx, valor_sped=vs,
                    obs="cProd XML=%s / COD_ITEM=%s"
                        % (it.cprod, c170.valor(doc._ix("C170", "COD_ITEM")))))

    resumo = {
        "xml_55": len(nfes55),
        "docs_casados": len(pares_doc),
        "docs_sem_c100": len(docs_sem_c100),
        "docs_sem_xml": len(docs_sem_xml),
        "itens_conferidos": itens_conferidos,
        "itens_sem_c170": len(sem_c170),
        "itens_sem_xml": len(sem_xml),
        "divergencias": len(divergencias),
    }
    return {
        "resumo": resumo,
        "divergencias": divergencias,
        "sem_c170": sem_c170,   # [(nfe, item)]
        "sem_xml": sem_xml,     # [c170]
        "docs_sem_c100": docs_sem_c100,  # [nfe]
        "docs_sem_xml": docs_sem_xml,    # [c100]
    }


def exportar_csv(resultado, caminho):
    """Grava as divergências em CSV (separador ';', compatível com Excel-BR)."""
    import csv
    cab = ["mod", "serie", "nNF", "nItem", "escopo", "campo",
           "valor_XML", "valor_SPED", "observacao"]
    with open(caminho, "w", newline="", encoding="latin-1") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cab)
        for d in resultado["divergencias"]:
            w.writerow(d.linha_csv())
    return caminho

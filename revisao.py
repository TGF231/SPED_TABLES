# -*- coding: utf-8 -*-
"""
revisao.py
----------
Revisão de erros simples no arquivo SPED. Cada regra recebe o SpedDocument e
devolve uma lista de `Problema`. O conjunto é facilmente extensível: basta
escrever uma função `verificar_*(doc) -> list[Problema]` e registrá-la em
`REGRAS`.

Cada Problema carrega o `uid` do registro, o que permite à interface navegar
até ele ao clicar no relatório.
"""

from collections import Counter

from sped_model import _to_num


class Problema:
    __slots__ = ("uid", "reg", "bloco", "regra", "descricao", "gravidade")

    def __init__(self, uid, reg, bloco, regra, descricao, gravidade="erro"):
        self.uid = uid
        self.reg = reg
        self.bloco = bloco
        self.regra = regra
        self.descricao = descricao
        self.gravidade = gravidade


# --------------------------------------------------------------------- regras
def verificar_num_campos(doc):
    """Registros cujo número de campos destoa dos demais do mesmo tipo.

    A referência é a *moda* (quantidade de campos mais comum) entre os
    registros do mesmo tipo no próprio arquivo — não o layout embutido, que
    pode estar numa versão diferente da do arquivo. Assim a regra aponta o erro
    real (um registro editado com um campo a mais ou a menos) sem gerar falso
    positivo por diferença de versão de layout. Tipos com um único registro são
    ignorados (não há base de comparação).
    """
    por_tipo = {}
    for r in doc.registros:
        por_tipo.setdefault(r.reg, []).append(r)

    problemas = []
    for reg, lista in por_tipo.items():
        if len(lista) < 2:
            continue
        contagem = Counter(len(r.campos) for r in lista)
        moda, _freq = contagem.most_common(1)[0]
        for r in lista:
            n = len(r.campos)
            if n != moda:
                problemas.append(Problema(
                    uid=r.uid, reg=r.reg, bloco=r.bloco,
                    regra="Número de campos",
                    descricao="%s tem %d campos; os demais %s têm %d."
                              % (r.reg, n, r.reg, moda)))
    return problemas


def verificar_c190_reducao(doc):
    """C190 com CST x20/x70 (redução de base) e VL_RED_BC zerado."""
    if doc.layout != "ICMS":
        return []
    problemas = []
    i_cst = doc._ix("C190", "CST_ICMS")
    i_red = doc._ix("C190", "VL_RED_BC")
    if i_cst is None or i_red is None:
        return []
    for r in doc.registros:
        if r.reg != "C190":
            continue
        cst = (r.valor(i_cst) or "").strip()
        if cst[-2:] in ("20", "70") and _to_num(r.valor(i_red)) == 0:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="C190 redução de BC",
                descricao="CST %s exige redução de base, mas VL_RED_BC está "
                          "zerado." % cst))
    return problemas


# Registro central de regras. Para adicionar uma nova verificação, escreva a
# função acima e inclua aqui o par (rótulo, função).
REGRAS = [
    ("Número de campos divergente do layout", verificar_num_campos),
    ("C190 CST x20/x70 com VL_RED_BC zerado", verificar_c190_reducao),
]


def revisar(doc, regras=None):
    """Executa as regras e devolve (lista_de_problemas, resumo_por_regra)."""
    regras = regras if regras is not None else REGRAS
    problemas = []
    resumo = []
    for rotulo, fn in regras:
        achados = fn(doc)
        resumo.append((rotulo, len(achados)))
        problemas.extend(achados)
    return problemas, resumo

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

from sped_model import _to_num, TIPOS_ITEM_0200


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
def verificar_0200_nao_utilizados(doc):
    """Aponta registros 0200 (cadastro de item) cujo COD_ITEM:
      * não é referenciado por nenhum outro registro (C170, H010, etc.); ou
      * está duplicado (mesmo COD_ITEM em mais de um 0200).

    As referências são coletadas de qualquer registro (≠ 0200) que possua o
    campo COD_ITEM no layout — não apenas C170/H010 —, evitando marcar como
    "não utilizado" um item citado em outro bloco.
    """
    i0 = doc._ix("0200", "COD_ITEM")
    if i0 is None:
        return []
    # a varredura vive no modelo: registro sem leiaute mapeado (o bloco K
    # inteiro, por exemplo) é procurado por valor, senão item referenciado lá
    # apareceria aqui como não utilizado
    referenciados = doc.referencias_de_itens()["referenciados"]

    problemas = []
    vistos = set()
    for r in doc.registros:
        if r.reg != "0200":
            continue
        cod = (r.valor(i0) or "").strip()
        if cod and cod in vistos:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="0200 duplicado",
                descricao="COD_ITEM %s já cadastrado em outro 0200." % cod,
                gravidade="aviso"))
        else:
            vistos.add(cod)
        if cod and cod not in referenciados:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="0200 não utilizado",
                descricao="COD_ITEM %s não é referenciado por nenhum registro "
                          "(C170, H010, ...)." % cod,
                gravidade="aviso"))
    return problemas


def verificar_c170_sem_c190(doc):
    """C170 (item) sem um C190 (analítico) compatível no mesmo documento — ou
    seja, cuja combinação de CST_ICMS, CFOP e ALIQ_ICMS não aparece em nenhum
    C190 do C100. Indica que o item não foi consolidado no analítico."""
    if doc.layout != "ICMS":
        return []
    ic = doc._ix("C170", "CST_ICMS")
    iff = doc._ix("C170", "CFOP")
    ia = doc._ix("C170", "ALIQ_ICMS")
    inum = doc._ix("C170", "NUM_ITEM")
    jc = doc._ix("C190", "CST_ICMS")
    jf = doc._ix("C190", "CFOP")
    ja = doc._ix("C190", "ALIQ_ICMS")
    if None in (ic, iff, ia, jc, jf, ja):
        return []

    def chave(r, i_cst, i_cfop, i_aliq):
        return ((r.valor(i_cst) or "").strip(), (r.valor(i_cfop) or "").strip(),
                "%.2f" % _to_num(r.valor(i_aliq)))

    problemas = []
    for c100 in doc.registros:
        if c100.reg != "C100":
            continue
        c170s = [f for f in c100.filhos if f.reg == "C170"]
        if not c170s:
            continue
        chaves_190 = {chave(f, jc, jf, ja) for f in c100.filhos
                      if f.reg == "C190"}
        for f in c170s:
            if chave(f, ic, iff, ia) not in chaves_190:
                problemas.append(Problema(
                    uid=f.uid, reg=f.reg, bloco=f.bloco,
                    regra="C170 sem C190 compatível",
                    descricao="Item %s (CST %s, CFOP %s, alíq. %s) não possui "
                              "C190 correspondente no documento."
                              % ((f.valor(inum) or "").strip(),
                                 (f.valor(ic) or "").strip(),
                                 (f.valor(iff) or "").strip(),
                                 (f.valor(ia) or "").strip())))
    return problemas


def verificar_tipo_item_0200(doc):
    """TIPO_ITEM fora da tabela oficial do 0200.

    O campo só aceita 00 a 10 e 99. ERPs que exportam a coluna errada
    despejam ali a origem da mercadoria ou um "N" de nacional — num arquivo
    real eram 10.312 itens, todos recusados pelo PVA. Item por item a
    correção é inviável; a grade do 0200 aplica valor na seleção inteira.
    """
    if doc.layout != "ICMS":
        return []
    i_tipo = doc._ix("0200", "TIPO_ITEM")
    i_cod = doc._ix("0200", "COD_ITEM")
    if i_tipo is None:
        return []
    problemas = []
    for r in doc.registros:
        if r.reg != "0200":
            continue
        v = (r.valor(i_tipo) or "").strip()
        if v and v not in TIPOS_ITEM_0200:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="TIPO_ITEM fora da tabela",
                descricao="Item %s tem TIPO_ITEM %r, que não existe na "
                          "tabela do 0200 (00 a 10 e 99)."
                          % ((r.valor(i_cod) or "").strip(), v)))
    return problemas


def verificar_cod_gen_0200(doc):
    """COD_GEN que não é o capítulo do NCM (Tabela 4.2.1).

    O gênero são os dois primeiros dígitos do NCM. Vazio é o caso comum
    depois de limpar um `NULL` herdado do ERP; errado costuma ser planilha
    que cortou os dois primeiros dígitos de um NCM já sem o zero à esquerda
    (`04012010` vira `4012010`, e o gênero sai `40` em vez de `04`).
    """
    if doc.layout != "ICMS":
        return []
    problemas = []
    for r, cod, ncm, atual, novo in doc.divergencias_cod_gen():
        problemas.append(Problema(
            uid=r.uid, reg=r.reg, bloco=r.bloco,
            regra="COD_GEN x NCM",
            descricao="Item %s: NCM %s pede COD_GEN %s, mas está %s."
                      % (cod, ncm, novo, ("%r" % atual) if atual else "vazio"),
            gravidade="erro" if atual else "aviso"))
    return problemas


REGRAS = [
    ("Número de campos divergente do layout", verificar_num_campos),
    ("C190 CST x20/x70 com VL_RED_BC zerado", verificar_c190_reducao),
    ("C170 sem C190 compatível", verificar_c170_sem_c190),
    ("0200 não utilizados / duplicados", verificar_0200_nao_utilizados),
    ("TIPO_ITEM fora da tabela (0200)", verificar_tipo_item_0200),
    ("COD_GEN incoerente com o NCM (0200)", verificar_cod_gen_0200),
]


def revisar_por_regra(doc, regras=None):
    """Executa as regras e devolve `[(rotulo, [problemas])]`.

    Manter o vínculo entre a regra e os seus achados é o que permite ao painel
    oferecer, em cada linha, a função que corrige **aquela** regra: o texto do
    `Problema.regra` é mais curto que o rótulo da lista e não serve de chave.
    """
    regras = regras if regras is not None else REGRAS
    return [(rotulo, fn(doc)) for rotulo, fn in regras]


def revisar(doc, regras=None):
    """Executa as regras e devolve (lista_de_problemas, resumo_por_regra)."""
    por_regra = revisar_por_regra(doc, regras)
    problemas = [p for _r, ps in por_regra for p in ps]
    resumo = [(r, len(ps)) for r, ps in por_regra]
    return problemas, resumo

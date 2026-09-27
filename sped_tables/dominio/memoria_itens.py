# -*- coding: utf-8 -*-
"""Memória de uma empresa para gerar o SPED a partir dos XMLs.

O XML de entrada traz o produto **do fornecedor** — o código dele, a
descrição dele, o CFOP de saída dele, o CST dele. O SPED pede o produto **da
empresa**: o código do cadastro próprio (0200), o CFOP de entrada, o CST que
ela escritura e o crédito que ela toma. Num mês real, 322 de 323 produtos
tinham código próprio diferente do código do fornecedor, e o mesmo CFOP de
fornecedor virava três CFOPs de entrada conforme o produto (revenda, ST, uso e
consumo). Não há regra geral: a decisão é **por produto**.

Por isso a memória guarda, por empresa:

* **produtos do fornecedor** — `(CNPJ do fornecedor, código dele)` → código
  próprio, e **como a empresa escritura** aquele produto em cada situação
  (CFOP e CST de origem → CFOP, CST de ICMS, crédito, CST e alíquota de
  PIS/COFINS);
* **cadastro próprio** — o 0200 da empresa (descrição, unidade, tipo, NCM…),
  que difere do XML em boa parte dos itens;
* **participantes** — CNPJ/CPF → código de participante (a empresa usa os
  seus, sequenciais);
* **unidades** — o 0190.

Ela é **aprendida**: `aprender()` casa o SPED entregue com os XMLs do mesmo
mês pela chave da nota e pelo número do item. O que ela não sabe é
respondido com None — quem gera decide se usa uma regra e **aponta para
revisão**; nunca grava um palpite como se fosse aprendido.

Tudo aqui é dado puro (dicts e listas), para caber num JSON; quem lê e grava
o arquivo é `infra/memoria.py`.
"""

from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.sped_model import so_digitos

VERSAO = 1
CAMPOS_0200 = ("DESCR_ITEM", "COD_BARRA", "UNID_INV", "TIPO_ITEM", "COD_NCM",
               "EX_IPI", "COD_GEN", "CEST", "ALIQ_ICMS")
# a escrituração de um item de entrada, na ordem em que fica guardada
ESCRITURACAO = ("CFOP", "CST_ICMS", "CREDITA_ICMS", "CST_PIS", "ALIQ_PIS",
                "CST_COFINS", "ALIQ_COFINS")


def nova(cnpj):
    return {"versao": VERSAO, "cnpj": so_digitos(cnpj), "periodos": [],
            "produtos": {}, "cadastro": {}, "participantes": {},
            "unidades": {}}


def chave_produto(cnpj_fornecedor, cod_fornecedor):
    return "%s|%s" % (so_digitos(cnpj_fornecedor),
                      (cod_fornecedor or "").strip())


def _contexto(item):
    """Situação do item no XML do fornecedor que decide a escrituração."""
    return "%s|%s" % ((item.cfop or "").strip(), (item.icms_cst or "").strip())


def _conta(dic, chave, n=1):
    dic[chave] = dic.get(chave, 0) + n


def _mais_frequente(contagem):
    if not contagem:
        return None
    return max(sorted(contagem), key=lambda k: contagem[k])


# ------------------------------------------------------------- consultas
def codigo_proprio(memoria, cnpj_fornecedor, cod_fornecedor):
    """`(código próprio, ambíguo?)`, ou `(None, False)` se nunca visto."""
    p = memoria["produtos"].get(chave_produto(cnpj_fornecedor,
                                              cod_fornecedor))
    if not p:
        return None, False
    return _mais_frequente(p["codigos"]), len(p["codigos"]) > 1


def escrituracao(memoria, cnpj_fornecedor, cod_fornecedor, item):
    """`{campo: valor}` de como a empresa escritura este item nesta
    situação (mesmo CFOP e CST do fornecedor), ou None.

    Sem a situação exata, **não** cai para outra: o mesmo produto com outro
    CFOP de origem pode ser outra operação (bonificação, devolução)."""
    p = memoria["produtos"].get(chave_produto(cnpj_fornecedor,
                                              cod_fornecedor))
    if not p:
        return None
    visto = _mais_frequente(p["escrituracao"].get(_contexto(item), {}))
    if visto is None:
        return None
    return dict(zip(ESCRITURACAO, visto.split("|")))


def cod_participante(memoria, documento):
    return memoria["participantes"].get(so_digitos(documento))


def proximo_cod_participante(memoria):
    """Próximo código numérico livre — a empresa numera os seus."""
    numeros = [int(c) for c in memoria["participantes"].values()
               if str(c).isdigit()]
    return str(max(numeros) + 1 if numeros else 1)


# ------------------------------------------------------------ aprendizado
def aprender(memoria, lote, doc_icms=None, doc_contrib=None):
    """Aprende com o SPED entregue e os XMLs do mesmo período.

    Casa cada C170 de entrada com o item do XML pela **chave da NF-e** e
    pelo **número do item** (é o que se mantém da saída do fornecedor para a
    entrada do comprador). Devolve um resumo com o que casou e o que não.
    """
    base = doc_icms or doc_contrib
    if base is None:
        raise ValueError("Informe ao menos um SPED entregue.")
    por_chave = {n.chave: n for n in lote.nfes}
    res = {"itens_casados": 0, "itens_sem_xml": 0, "notas_sem_xml": 0,
           "produtos": 0, "cadastro": 0, "participantes": 0}

    def c100s(doc):
        if doc is None:
            return {}
        i = doc._ix("C100", "CHV_NFE")
        return {r.valor(i): r for r in doc.registros if r.reg == "C100"}

    icms, contrib = c100s(doc_icms), c100s(doc_contrib)
    ia = _indices(doc_icms, "C170", ("NUM_ITEM", "COD_ITEM", "CFOP",
                                     "CST_ICMS", "VL_ICMS"))
    ip = _indices(doc_contrib, "C170", ("NUM_ITEM", "COD_ITEM", "CFOP",
                                        "CST_PIS", "ALIQ_PIS", "CST_COFINS",
                                        "ALIQ_COFINS"))
    i_oper = base._ix("C100", "IND_OPER")
    chaves = [k for k, r in (icms or contrib).items()
              if (r.valor(i_oper) or "").strip() == "0"]
    for chave in chaves:
        nfe = por_chave.get(chave)
        if nfe is None or nfe.emit is None:
            res["notas_sem_xml"] += 1
            continue
        itens_xml = {xf.norm(i.nitem): i for i in nfe.itens}
        a = _filhos(icms.get(chave), ia, "NUM_ITEM")
        p = _filhos(contrib.get(chave), ip, "NUM_ITEM")
        for num in sorted(set(a) | set(p)):
            item = itens_xml.get(num)
            if item is None:
                res["itens_sem_xml"] += 1
                continue
            res["itens_casados"] += 1
            fa, fp = a.get(num), p.get(num)
            cod = (fa or fp)["COD_ITEM"]
            prod = memoria["produtos"].setdefault(
                chave_produto(nfe.emit.cnpj, item.cprod),
                {"codigos": {}, "escrituracao": {}, "descr": "",
                 "cean": "", "ncm": ""})
            _conta(prod["codigos"], cod)
            prod.update(descr=item.xprod or "", cean=item.cean or "",
                        ncm=item.ncm or "")
            vals = [(fa or fp).get("CFOP", ""),
                    (fa or {}).get("CST_ICMS", ""),
                    "S" if fa and _positivo(fa.get("VL_ICMS")) else "N",
                    (fp or {}).get("CST_PIS", ""),
                    (fp or {}).get("ALIQ_PIS", ""),
                    (fp or {}).get("CST_COFINS", ""),
                    (fp or {}).get("ALIQ_COFINS", "")]
            _conta(prod["escrituracao"].setdefault(_contexto(item), {}),
                   "|".join(vals))
    res["produtos"] = len(memoria["produtos"])

    # cadastro próprio, participantes e unidades: do SPED, como a empresa
    # os declarou (vale o mais recente)
    for doc in (doc_icms, doc_contrib):
        if doc is None:
            continue
        i2 = _indices(doc, "0200", ("COD_ITEM",) + CAMPOS_0200)
        for r in doc.registros:
            if r.reg == "0200":
                v = {c: (r.valor(i) or "").strip() for c, i in i2.items()
                     if i is not None}
                memoria["cadastro"][v.pop("COD_ITEM")] = v
        i150 = _indices(doc, "0150", ("COD_PART", "CNPJ", "CPF"))
        for r in doc.registros:
            if r.reg == "0150":
                documento = so_digitos(r.valor(i150["CNPJ"])
                                       or r.valor(i150["CPF"]))
                if documento:
                    memoria["participantes"][documento] = \
                        (r.valor(i150["COD_PART"]) or "").strip()
        i190 = _indices(doc, "0190", ("UNID", "DESCR"))
        for r in doc.registros:
            if r.reg == "0190":
                memoria["unidades"][(r.valor(i190["UNID"]) or "").strip()] = \
                    (r.valor(i190["DESCR"]) or "").strip()
    res["cadastro"] = len(memoria["cadastro"])
    res["participantes"] = len(memoria["participantes"])
    periodo = base.data_final()[4:] + base.data_final()[2:4]
    if periodo not in memoria["periodos"]:
        memoria["periodos"].append(periodo)
        memoria["periodos"].sort()
    return res


def _indices(doc, reg, campos):
    if doc is None:
        return {}
    return {c: doc._ix(reg, c) for c in campos}


def _filhos(c100, indices, chave):
    """`{nº do item normalizado: {campo: valor}}` dos C170 do documento."""
    if c100 is None:
        return {}
    saida = {}
    for f in c100.filhos:
        if f.reg != "C170":
            continue
        v = {c: (f.valor(i) or "").strip() for c, i in indices.items()
             if i is not None}
        saida[xf.norm(v.get(chave))] = v
    return saida


def _positivo(v):
    v = (v or "").replace(".", "").replace(",", ".")
    try:
        return float(v) > 0
    except ValueError:
        return False


def resumo(memoria):
    """Contagens para mostrar ao usuário."""
    ambiguos = sum(1 for p in memoria["produtos"].values()
                   if len(p["codigos"]) > 1)
    return {"periodos": list(memoria["periodos"]),
            "produtos": len(memoria["produtos"]), "ambiguos": ambiguos,
            "cadastro": len(memoria["cadastro"]),
            "participantes": len(memoria["participantes"]),
            "unidades": len(memoria["unidades"])}

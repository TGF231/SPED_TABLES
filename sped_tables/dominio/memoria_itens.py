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

import re

from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.sped_model import _fmt_aliq, so_digitos

VERSAO = 3
CAMPOS_0200 = ("DESCR_ITEM", "COD_BARRA", "UNID_INV", "TIPO_ITEM", "COD_NCM",
               "EX_IPI", "COD_GEN", "CEST", "ALIQ_ICMS")
# a escrituração de um item de entrada, na ordem em que fica guardada
ESCRITURACAO = ("CFOP", "CST_ICMS", "CREDITA_ICMS", "CST_PIS", "ALIQ_PIS",
                "CST_COFINS", "ALIQ_COFINS", "CST_IPI", "COD_NAT", "COD_CTA")
# Registros que não saem dos XMLs: são decisões da empresa (quem é o
# contabilista, o código de receita do ICMS, o perfil, o que ela declara no
# 1010). A memória guarda a última versão entregue como **modelo**, por
# leiaute; o gerador copia e ajusta só o período.
MODELOS = {
    "ICMS": ("0000", "0001", "0002", "0005", "0100", "E116", "E200", "E210",
             "E300", "E310", "E500", "E520", "1010"),
    "CONTRIB": ("0000", "0001", "0100", "0110", "0140", "C010", "M205",
                "M605"),
}


def nova(cnpj):
    return {"versao": VERSAO, "cnpj": so_digitos(cnpj), "periodos": [],
            "produtos": {}, "cadastro": {}, "participantes": {},
            "unidades": {}, "modelos": {}, "blocos_vazios": {},
            "saldos": {}, "padroes": {}}


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


def pratica(memoria, item):
    """Como a empresa **costuma** escriturar esta situação (CFOP e CST do
    fornecedor), somando todos os produtos — para produto que ela nunca
    comprou. `(campos, parcela)`: a parcela diz quão dominante é a escolha
    (1,0 = sempre a mesma); None se a situação nunca apareceu."""
    cont = memoria.get("praticas", {}).get(_contexto(item))
    if not cont:
        return None
    visto = _mais_frequente(cont)
    return (dict(zip(ESCRITURACAO, visto.split("|"))),
            cont[visto] / float(sum(cont.values())))


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


# peso de uma decisão da pessoa: passa à frente do que foi aprendido do SPED
# (a contagem de um mês raramente chega a isso para o mesmo produto)
PESO_DECISAO = 1000


# o que a pessoa pode digitar numa decisão, e como tem de estar
_FORMATOS = {
    "CFOP": (re.compile(r"^[123]\d{3}$"), "4 dígitos, de entrada (1, 2 ou 3)"),
    "CST_ICMS": (re.compile(r"^\d{3}$"), "3 dígitos (origem + situação)"),
    "CREDITA_ICMS": (re.compile(r"^[SN]$"), "S ou N"),
    "CST_PIS": (re.compile(r"^\d{2}$"), "2 dígitos"),
    "CST_COFINS": (re.compile(r"^\d{2}$"), "2 dígitos"),
    "CST_IPI": (re.compile(r"^\d{2}$"), "2 dígitos"),
    "ALIQ_PIS": (re.compile(r"^\d{1,3}([.,]\d{1,4})?$"), "percentual"),
    "ALIQ_COFINS": (re.compile(r"^\d{1,3}([.,]\d{1,4})?$"), "percentual"),
    "COD_NAT": (re.compile(r"^[^|]{1,10}$"), "até 10 caracteres, sem |"),
    "COD_CTA": (re.compile(r"^[^|]{1,255}$"), "sem |"),
    "COD_ITEM": (re.compile(r"^[^|]{1,60}$"), "até 60 caracteres, sem |"),
}


def validar_decisao(campos):
    """O que a pessoa digitou, conferido e no formato do SPED; campo vazio
    fica de fora (quer dizer "não mexer"). Levanta ValueError com todos os
    problemas de uma vez — a decisão errada iria para a memória e dali para
    todo mês seguinte."""
    limpos, erros = {}, []
    for nome, valor in campos.items():
        valor = (valor or "").strip()
        if not valor:
            continue
        if nome not in _FORMATOS:
            raise KeyError(nome)
        padrao, dica = _FORMATOS[nome]
        if not padrao.match(valor):
            erros.append("%s \"%s\": %s" % (nome, valor, dica))
            continue
        if nome.startswith("ALIQ_"):
            valor = _fmt_aliq(float(valor.replace(",", ".")))
        limpos[nome] = valor
    if erros:
        raise ValueError("Valores inválidos:\n" + "\n".join(erros))
    return limpos


def ensinar(memoria, fornecedor, cod_fornecedor, cfop_origem, cst_origem,
            campos, cod_proprio=None, usado=None):
    """Grava a decisão da pessoa para este produto nesta situação.

    `campos` sobrepõe a escrituração (CFOP, CST_ICMS, CREDITA_ICMS…); o que
    ele não traz vem do que a memória já sabia do produto, da prática da
    empresa ou, sem nenhum dos dois, do que a geração usou (`usado`, a
    correlação de CFOP). `cod_proprio`, se dado, passa a ser o código do
    produto. Escrituração sem CFOP ou sem CST do ICMS é recusada: iria para
    todo mês seguinte com o campo em branco, e sem bloqueio — a memória
    responde "sei".
    """
    campos = validar_decisao(dict(campos, **(
        {"COD_ITEM": cod_proprio} if cod_proprio else {})))
    cod_proprio = campos.pop("COD_ITEM", None)

    class _Item:
        cfop, icms_cst = cfop_origem, cst_origem
    base = (escrituracao(memoria, fornecedor, cod_fornecedor, _Item)
            or (pratica(memoria, _Item) or ({}, 0))[0]
            or dict(usado or {}))
    # sem nada aprendido, o CST do fornecedor e sem crédito — como a
    # geração faz quando não sabe
    if not base.get("CST_ICMS") and len((cst_origem or "").strip()) == 3:
        base["CST_ICMS"] = cst_origem.strip()
    base.setdefault("CREDITA_ICMS", "N")
    base.update(campos)
    faltam = [c for c in ("CFOP", "CST_ICMS") if campos and not base.get(c)]
    if faltam:
        raise ValueError("Informe também: %s." % ", ".join(faltam))

    prod = memoria["produtos"].setdefault(
        chave_produto(fornecedor, cod_fornecedor),
        {"codigos": {}, "escrituracao": {}, "fatores": {},
         "descr": "", "cean": "", "ncm": ""})
    if campos:
        valores = "|".join(base.get(c, "") for c in ESCRITURACAO)
        _decide(prod["escrituracao"].setdefault(_contexto(_Item), {}),
                valores)
    if cod_proprio:
        _decide(prod["codigos"], cod_proprio)


def _decide(contagem, escolha):
    """A escolha passa à frente de tudo o que já foi contado — inclusive de
    uma decisão anterior, que a nova substitui."""
    contagem[escolha] = max(contagem.values(), default=0) + PESO_DECISAO


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
                                     "CST_ICMS", "VL_ICMS", "CST_IPI",
                                     "COD_NAT", "QTD", "UNID"))
    ip = _indices(doc_contrib, "C170", ("NUM_ITEM", "COD_ITEM", "CFOP",
                                        "CST_PIS", "ALIQ_PIS", "CST_COFINS",
                                        "ALIQ_COFINS", "COD_CTA"))
    i_oper = base._ix("C100", "IND_OPER")
    chaves = [k for k, r in (icms or contrib).items()
              if (r.valor(i_oper) or "").strip() == "0"]
    datas, fretes = {}, {}
    i_dts = base._ix("C100", "DT_E_S")
    i_frt = base._ix("C100", "VL_FRT")
    for chave in chaves:
        nfe = por_chave.get(chave)
        if nfe is None or nfe.emit is None:
            res["notas_sem_xml"] += 1
            continue
        _aprender_entrada(icms.get(chave) or contrib.get(chave), nfe,
                          i_dts, i_frt, datas, fretes)
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
                {"codigos": {}, "escrituracao": {}, "fatores": {},
                 "descr": "", "cean": "", "ncm": ""})
            _conta(prod["codigos"], cod)
            # a unidade escriturada é a do cadastro próprio: um fardo de 2
            # no XML pode ser 12 unidades no SPED
            fator = _fator(fa, item)
            if fator is not None:
                _conta(prod["fatores"], fator)
            prod.update(descr=item.xprod or "", cean=item.cean or "",
                        ncm=item.ncm or "")
            vals = [(fa or fp).get("CFOP", ""),
                    (fa or {}).get("CST_ICMS", ""),
                    "S" if fa and _positivo(fa.get("VL_ICMS")) else "N",
                    (fp or {}).get("CST_PIS", ""),
                    (fp or {}).get("ALIQ_PIS", ""),
                    (fp or {}).get("CST_COFINS", ""),
                    (fp or {}).get("ALIQ_COFINS", ""),
                    (fa or {}).get("CST_IPI", ""),
                    (fa or fp).get("COD_NAT", ""),
                    (fp or {}).get("COD_CTA", "")]
            _conta(prod["escrituracao"].setdefault(_contexto(item), {}),
                   "|".join(vals))
            # a prática da empresa, somando todos os produtos: é a segunda
            # opção para produto que ela nunca comprou
            _conta(memoria.setdefault("praticas", {}).setdefault(
                _contexto(item), {}), "|".join(vals))
    res["produtos"] = len(memoria["produtos"])
    # como a empresa data e totaliza a entrada: só vale o que os documentos
    # mostram sem exceção — na dúvida, fica o padrão do SPED
    padroes = memoria.setdefault("padroes", {}).setdefault("entrada", {})
    if datas:
        padroes["DT_E_S"] = _mais_frequente(datas)
    if fretes:
        padroes["VL_FRT"] = _mais_frequente(fretes)

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
        i400 = _indices(doc, "0400", ("COD_NAT", "DESCR_NAT"))
        for r in doc.registros:
            if r.reg == "0400":
                cod_nat = (r.valor(i400["COD_NAT"]) or "").strip()
                memoria.setdefault("naturezas", {})[cod_nat] = (
                    r.valor(i400["DESCR_NAT"]) or "").strip()
        i190 = _indices(doc, "0190", ("UNID", "DESCR"))
        for r in doc.registros:
            if r.reg == "0190":
                memoria["unidades"][(r.valor(i190["UNID"]) or "").strip()] = \
                    (r.valor(i190["DESCR"]) or "").strip()
        _aprender_modelos(memoria, doc)
    res["cadastro"] = len(memoria["cadastro"])
    res["participantes"] = len(memoria["participantes"])
    periodo = base.data_final()[4:] + base.data_final()[2:4]
    if periodo not in memoria["periodos"]:
        memoria["periodos"].append(periodo)
        memoria["periodos"].sort()
    return res


def _aprender_modelos(memoria, doc):
    """Modelos por leiaute, blocos que a empresa entrega sem movimento e o
    saldo credor de ICMS que passa para o mês seguinte."""
    tipos = MODELOS.get(doc.layout, ())
    modelos = {}
    for r in doc.registros:
        if r.reg in tipos and r.reg not in modelos:
            modelos[r.reg] = list(r.campos)
    memoria["modelos"][doc.layout] = modelos
    # largura de cada registro na versão de leiaute que a empresa entrega
    larguras = {}
    for r in doc.registros:
        _conta(larguras.setdefault(r.reg, {}), str(len(r.campos)))
    memoria.setdefault("larguras", {})[doc.layout] = {
        reg: int(_mais_frequente(c)) for reg, c in larguras.items()}
    # bloco sem movimento: só abertura (X001 com 1) e encerramento
    por_bloco = {}
    for r in doc.registros:
        por_bloco.setdefault(r.bloco, []).append(r.reg)
    memoria["blocos_vazios"][doc.layout] = sorted(
        b for b, regs in por_bloco.items()
        if b != "9" and sorted(set(regs)) == sorted({b + "001", b + "990"}))
    # indicadores do C100 que a empresa preenche sempre igual, por modelo e
    # operação (pagamento, frete): o XML não os traz no formato do SPED
    ic = {c: doc._ix("C100", c) for c in ("COD_MOD", "IND_OPER",
                                          "IND_PGTO", "IND_FRT")}
    contagem = {}
    for r in doc.registros:
        if r.reg == "C100":
            k = "%s|%s" % (r.valor(ic["COD_MOD"]), r.valor(ic["IND_OPER"]))
            for c in ("IND_PGTO", "IND_FRT"):
                if ic[c] is not None:
                    _conta(contagem.setdefault(k, {}).setdefault(c, {}),
                           (r.valor(ic[c]) or "").strip())
    memoria.setdefault("padroes", {})[doc.layout] = {
        k: {c: _mais_frequente(v) for c, v in campos.items()}
        for k, campos in contagem.items()}
    # plano de contas (0500), inteiro, pela conta
    for r in doc.registros:
        if r.reg == "0500":
            conta = (r.valor(doc._ix("0500", "COD_CTA")) or "").strip()
            memoria.setdefault("contas", {})[conta] = list(r.campos)
    if doc.layout == "CONTRIB":
        # a alíquota do regime nas saídas, por CST — o XML da empresa pode
        # vir com outra (num mês real, 1,65/7,60 num contribuinte
        # cumulativo que escritura 0,65/3)
        cont = {}
        c175 = {c: doc._ix("C175", c) for c in (
            "CST_PIS", "ALIQ_PIS", "CST_COFINS", "ALIQ_COFINS")}
        for r in doc.registros:
            if r.reg == "C175":
                v = [(r.valor(i) or "").strip() for i in c175.values()]
                _conta(cont.setdefault(v[0], {}), "|".join(v[1:]))
        memoria["aliquotas_saida"] = {
            cst: dict(zip(("ALIQ_PIS", "CST_COFINS", "ALIQ_COFINS"),
                          _mais_frequente(c).split("|")))
            for cst, c in cont.items()}
        # receitas sem contribuição (M400/M410 e M800/M810): a natureza que
        # a empresa usa em cada CST e a conta de cada registro — o que não
        # se acha pelo NCM do produto sai daqui
        nats, contas = {}, {}
        for pai, filho, campo in (("M400", "M410", "CST_PIS"),
                                  ("M800", "M810", "CST_COFINS")):
            i_cst = doc._ix(pai, campo)
            i_nat = doc._ix(filho, "NAT_REC")
            i_cp, i_cf = doc._ix(pai, "COD_CTA"), doc._ix(filho, "COD_CTA")
            for r in doc.registros:
                if r.reg != pai:
                    continue
                cst = (r.valor(i_cst) or "").strip()
                conta = (r.valor(i_cp) or "").strip()
                if conta:
                    contas["%s|%s" % (pai, cst)] = conta
                for f in r.filhos:
                    if f.reg != filho:
                        continue
                    nat = (f.valor(i_nat) or "").strip()
                    _conta(nats.setdefault(cst, {}), nat)
                    conta = (f.valor(i_cf) or "").strip()
                    if conta:
                        contas["%s|%s|%s" % (filho, cst, nat)] = conta
        memoria["naturezas_receita"] = nats
        memoria["contas_receita"] = contas
    if doc.layout == "ICMS":
        i = doc._ix("E110", "VL_SLD_CREDOR_TRANSPORTAR")
        e110 = next((r for r in doc.registros if r.reg == "E110"), None)
        if e110 is not None and i is not None:
            periodo = doc.data_final()[4:] + doc.data_final()[2:4]
            memoria["saldos"][periodo] = (e110.valor(i) or "0").strip()


def _aprender_entrada(c100, nfe, i_dts, i_frt, datas, fretes):
    """Data de entrada (emissão ou saída do XML?) e frete (o do XML ou
    zero?) — só nas notas em que as duas hipóteses dão resultado diferente,
    senão não ensinam nada."""
    dts = (c100.valor(i_dts) or "").strip()
    emissao, saida = _ddmmaaaa(nfe.dhemi), _ddmmaaaa(nfe.dhsaient)
    if saida and saida != emissao:
        if dts == emissao:
            _conta(datas, "emissao")
        elif dts == saida:
            _conta(datas, "saida")
    if nfe.vfrete:
        frt = _numero(c100.valor(i_frt)) or 0.0
        _conta(fretes, "xml" if abs(frt - nfe.vfrete) < 0.005 else "zero")


def _ddmmaaaa(iso):
    iso = (iso or "").strip()
    return iso[8:10] + iso[5:7] + iso[0:4] if len(iso) >= 10 else ""


def _fator(c170, item):
    """Quantidade escriturada ÷ quantidade do XML, como texto (chave de
    contagem), ou None se não der para saber."""
    if not c170 or not item.qtd:
        return None
    q = _numero(c170.get("QTD"))
    if q is None:
        return None
    return "%.6g" % (q / item.qtd)


def _numero(v):
    v = (v or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def fator_conversao(memoria, cnpj_fornecedor, cod_fornecedor):
    """`(fator, ambíguo?)` da quantidade do XML para a do SPED; `(None,
    False)` se nunca visto."""
    p = memoria["produtos"].get(chave_produto(cnpj_fornecedor,
                                              cod_fornecedor))
    if not p or not p.get("fatores"):
        return None, False
    return float(_mais_frequente(p["fatores"])), len(p["fatores"]) > 1


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
    n = _numero(v)
    return n is not None and n > 0


def resumo(memoria):
    """Contagens para mostrar ao usuário."""
    ambiguos = sum(1 for p in memoria["produtos"].values()
                   if len(p["codigos"]) > 1)
    return {"periodos": list(memoria["periodos"]),
            "produtos": len(memoria["produtos"]), "ambiguos": ambiguos,
            "cadastro": len(memoria["cadastro"]),
            "participantes": len(memoria["participantes"]),
            "unidades": len(memoria["unidades"])}

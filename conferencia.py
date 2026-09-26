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
1xxx/2xxx). Por isso esses campos não servem de chave.

Conferem-se: o **valor** do item (VL_ITEM/VL_DESC) e o **total do documento**
(VL_DOC); e, quando há uma tabela de correlações, a **coerência do CFOP** — o
CFOP de saída do XML deve mapear para um CFOP de entrada válido no C170 (a
tabela é editável e fica em correlacoes_cfop.json).

Este módulo orquestra xml_fiscal (parsing/vínculo) + o SpedDocument (índices de
campo por layout); não depende de PyQt.
"""

from sped_model import _to_num
import xml_fiscal as xf


class Divergencia:
    __slots__ = ("mod", "serie", "nnf", "nitem", "escopo", "campo",
                 "valor_xml", "valor_sped", "obs", "uid")

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


def _so_digitos(s):
    return "".join(c for c in (s or "") if c.isdigit())


# --------------------------------------------------------- correlação de CFOP
# Numa COMPRA, o XML do fornecedor traz o CFOP de SAÍDA (5xxx mesma UF, 6xxx
# outra UF). O comprador escritura no C170 o CFOP de ENTRADA correspondente
# (1xxx / 2xxx), que deve preservar a natureza da operação (comercialização,
# industrialização, ST, ativo, uso/consumo, etc.). Esta tabela define, para
# cada CFOP de saída, os CFOPs de entrada considerados VÁLIDOS.
#
# A base abaixo é por "miolo" (3 últimos dígitos) e é expandida para 5→1 e
# 6→2. A tabela é apenas o ponto de partida: pode ser editada na interface e
# salva em JSON (ver carregar/salvar_correlacoes).
_BASE_CFOP = {
    # venda / compra (sem ST)
    "101": ["101", "401"],
    "102": ["102", "101", "403", "401"],
    "103": ["101"],
    "104": ["102"],
    "105": ["101"],
    "106": ["102"],
    "109": ["101", "102"],
    "110": ["101", "102"],
    "111": ["101"],
    "113": ["101"],
    "114": ["102"],
    "116": ["101"],
    "117": ["102"],
    "118": ["101"],
    "119": ["102"],
    "120": ["101"],
    "122": ["102"],
    "123": ["101"],
    "124": ["101"],
    "125": ["101"],
    # transferências
    "151": ["151"],
    "152": ["152"],
    # com substituição tributária
    "401": ["401"],
    "402": ["401"],
    "403": ["403", "401"],
    "405": ["403"],
    "408": ["408"],
    "409": ["409"],
    # industrialização por encomenda
    "124": ["101"],
    "125": ["101"],
    "901": ["901"],
    "902": ["902"],
    # ativo imobilizado e uso/consumo
    "551": ["551"],
    "552": ["552"],
    "553": ["553"],
    "556": ["556"],
    "557": ["557"],
    # remessas / retornos / outras
    "910": ["910"],
    "911": ["911"],
    "912": ["912"],
    "913": ["913"],
    "914": ["914"],
    "915": ["915"],
    "916": ["916"],
    "917": ["917"],
    "918": ["918"],
    "919": ["919"],
    "920": ["920"],
    "921": ["921"],
    "949": ["949"],
}


def _expandir_base(base):
    out = {}
    for miolo, destinos in base.items():
        out["5" + miolo] = ["1" + d for d in destinos]
        out["6" + miolo] = ["2" + d for d in destinos]
    return out


CORRELACOES_CFOP_PADRAO = _expandir_base(_BASE_CFOP)


def normalizar_correlacoes(d):
    """Converte um dict {cfop_saida: [cfops_entrada]} num dict de conjuntos,
    com tudo reduzido a dígitos. Aceita valores em lista, set, ou string com
    separadores (vírgula/espaço)."""
    out = {}
    for k, v in (d or {}).items():
        chave = _so_digitos(k)
        if not chave:
            continue
        if isinstance(v, str):
            itens = v.replace(";", ",").replace(" ", ",").split(",")
        else:
            itens = list(v)
        out[chave] = {_so_digitos(x) for x in itens if _so_digitos(x)}
    return out


def carregar_correlacoes(caminho):
    """Lê as correlações de um JSON; se o arquivo não existir, devolve o
    padrão. Sempre retorna um dict {cfop: set(cfops)}."""
    import json
    import os
    if caminho and os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as fh:
                return normalizar_correlacoes(json.load(fh))
        except Exception:  # noqa: BLE001 - arquivo corrompido cai no padrão
            pass
    return normalizar_correlacoes(CORRELACOES_CFOP_PADRAO)


def salvar_correlacoes(mapa, caminho):
    """Grava as correlações num JSON legível (listas ordenadas), de forma
    atômica."""
    import dados
    serial = {k: sorted(v) for k, v in sorted(mapa.items())}
    return dados.gravar_json(caminho, serial)


# despesas acessórias que a NF-e traz por item e o C170 não tem onde guardar
ACESSORIOS_ITEM = ("voutro", "vfrete", "vseg")


def acessorios_do_item(it):
    """Soma de vOutro + vFrete + vSeg do item do XML."""
    return sum((getattr(it, nome, 0.0) or 0.0) for nome in ACESSORIOS_ITEM)


def valor_item_xml(it, somar_acessorios=True):
    """Valor do item do XML no critério do C170.

    O C170 não tem campo de despesa acessória por item, então o que a NF-e traz
    em `det/prod/vOutro`, `vFrete` e `vSeg` precisa ir para algum lugar — e há
    **duas** escriturações legítimas, que só o arquivo revela:

    * o ERP soma a despesa **dentro do VL_ITEM** (e o C100 não repete o valor);
    * o ERP mantém `VL_ITEM = vProd` e lança a despesa em **VL_OUT_DA / VL_FRT
      / VL_SEG do C100**, que é o que o leiaute prevê.

    Assumir só a primeira produzia centenas de falsos positivos num arquivo
    real, em que o C100 trazia `VL_OUT_DA` exatamente igual à soma dos vOutro
    dos itens. Por isso quem decide é `acessorios_no_documento()`, documento a
    documento.
    """
    base = it.vprod or 0.0
    return base + acessorios_do_item(it) if somar_acessorios else base


def acessorios_no_documento(doc, c100, nfe, tol=0.02):
    """O documento lança as despesas acessórias no **C100**?

    Compara `VL_OUT_DA + VL_FRT + VL_SEG` do C100 com a soma das mesmas
    despesas nos itens do XML. Batendo, elas já estão no documento e **não**
    devem ser somadas ao item; caso contrário, presume-se que foram embutidas
    no VL_ITEM.
    """
    soma_itens = sum(acessorios_do_item(it) for it in (nfe.itens or []))
    if soma_itens <= 0:
        return True          # nada a somar: o critério não muda nada
    total = 0.0
    for campo in ("VL_OUT_DA", "VL_FRT", "VL_SEG"):
        i = doc._ix("C100", campo)
        if i is not None:
            total += _to_num(c100.valor(i))
    return abs(total - soma_itens) <= max(tol, soma_itens * 0.005)


def _num_xml(s):
    """Número vindo do XML (ponto decimal). O SPED usa vírgula; o XML, não."""
    try:
        return float(str(s).strip()) if s not in (None, "") else 0.0
    except ValueError:
        return 0.0


# comparações item XML ↔ C170:
#   (rótulo, função-valor-do-item-XML, nome-do-campo-C170, tolerância)
#
# Os conjuntos são separados por tributo porque cada leiaute do SPED escritura
# um imposto: cobrar PIS/COFINS num arquivo de ICMS/IPI só produziria ruído,
# já que o C170 do leiaute de ICMS sequer traz esses campos preenchidos.
COMPARACOES_ICMS = [
    ("VL_ITEM", valor_item_xml, "VL_ITEM", 0.01),
    ("VL_DESC", lambda it: it.vdesc, "VL_DESC", 0.01),
    ("VL_BC_ICMS", lambda it: it.icms_vbc or 0.0, "VL_BC_ICMS", 0.01),
    ("VL_ICMS", lambda it: it.icms_vicms or 0.0, "VL_ICMS", 0.01),
    ("VL_BC_ICMS_ST", lambda it: it.icms_vbcst or 0.0, "VL_BC_ICMS_ST", 0.01),
    ("VL_ICMS_ST", lambda it: it.icms_vicmsst or 0.0, "VL_ICMS_ST", 0.01),
    ("VL_IPI", lambda it: it.vipi or 0.0, "VL_IPI", 0.01),
]

COMPARACOES_PIS_COFINS = [
    ("VL_ITEM", valor_item_xml, "VL_ITEM", 0.01),
    ("VL_DESC", lambda it: it.vdesc, "VL_DESC", 0.01),
    ("VL_BC_PIS", lambda it: it.pis_vbc or 0.0, "VL_BC_PIS", 0.01),
    ("ALIQ_PIS", lambda it: _num_xml(it.pis_aliq), "ALIQ_PIS", 0.0001),
    ("VL_PIS", lambda it: it.pis_vpis or 0.0, "VL_PIS", 0.01),
    ("VL_BC_COFINS", lambda it: it.cofins_vbc or 0.0, "VL_BC_COFINS", 0.01),
    ("ALIQ_COFINS", lambda it: _num_xml(it.cofins_aliq), "ALIQ_COFINS",
     0.0001),
    ("VL_COFINS", lambda it: it.cofins_vcofins or 0.0, "VL_COFINS", 0.01),
]

# mantido pelo nome antigo (era só ICMS)
COMPARACOES_PADRAO = COMPARACOES_ICMS

# CST conferido em cada modo: (campo no C170, atributo do item do XML)
CST_POR_TRIBUTO = {
    "ICMS": [("CST_ICMS", "icms_cst")],
    "PIS_COFINS": [("CST_PIS", "pis_cst"), ("CST_COFINS", "cofins_cst")],
}

COMPARACOES_POR_TRIBUTO = {
    "ICMS": COMPARACOES_ICMS,
    "PIS_COFINS": COMPARACOES_PIS_COFINS,
}

# IND_OPER do C100
MOVIMENTOS = {"entrada": "0", "saida": "1"}


def conferir_entradas_55(doc, nfes, comparacoes=None, tol_doc=0.01,
                         correlacoes_cfop=None, avisar_cfop_sem_regra=False):
    """Compatibilidade: entradas modelo 55 conferidas pelos campos de ICMS."""
    return conferir_itens_xml(
        doc, nfes, movimento="entrada", tributo="ICMS",
        comparacoes=comparacoes, tol_doc=tol_doc,
        correlacoes_cfop=correlacoes_cfop,
        avisar_cfop_sem_regra=avisar_cfop_sem_regra)


def conferir_itens_xml(doc, nfes, movimento="entrada", tributo="ICMS",
                       comparacoes=None, tol_doc=0.01,
                       correlacoes_cfop=None, avisar_cfop_sem_regra=False,
                       modelo="55"):
    """
    Confere os itens modelo 55 do documento SPED `doc` contra os XMLs `nfes`.

    `movimento` é "entrada", "saida" ou "ambos" (IND_OPER do C100) e `tributo`
    é "ICMS" ou "PIS_COFINS" — cada leiaute do SPED escritura um imposto, e
    conferir o outro só geraria divergência onde o campo nem é preenchido.

    A **correlação de CFOP** só se aplica às entradas: ela compara o CFOP de
    saída do fornecedor com o de entrada do comprador. Numa saída própria, o
    CFOP do XML é o mesmo que o escriturado, e a comparação viraria identidade.

    Se `correlacoes_cfop` for fornecido (dict {cfop_saida: iterável de
    cfops_entrada} ou já normalizado), confere também a **correlação de CFOP**:
    o CFOP do item no XML (saída do fornecedor) deve corresponder a um CFOP de
    entrada válido no C170. Quando o CFOP de saída não tem regra cadastrada, a
    divergência só é apontada se `avisar_cfop_sem_regra` for True.

    Retorna um dicionário com:
      * resumo: contadores gerais;
      * divergencias: lista de Divergencia (valores que não batem);
      * sem_c170: itens do XML sem C170 correspondente (faltam no SPED);
      * sem_xml: C170 de entradas 55 sem item no XML (sobrando / sem XML);
      * docs_sem_xml: C100 modelo 55 (entrada) sem XML na pasta;
      * docs_sem_c100: XMLs modelo 55 sem C100 no SPED.
    """
    if comparacoes is None:
        comparacoes = COMPARACOES_POR_TRIBUTO.get(tributo, COMPARACOES_ICMS)

    iC_mod = doc._ix("C100", "COD_MOD")
    iC_ser = doc._ix("C100", "SER")
    iC_num = doc._ix("C100", "NUM_DOC")
    iC_op = doc._ix("C100", "IND_OPER")
    iC_vdoc = doc._ix("C100", "VL_DOC")
    i170_item = doc._ix("C170", "NUM_ITEM")
    i170_cfop = doc._ix("C170", "CFOP")
    # CST conferido conforme o tributo: (índice no C170, atributo do item XML)
    idx_cst = [(doc._ix("C170", campo), attr, campo)
               for campo, attr in CST_POR_TRIBUTO.get(tributo, [])]
    idx_cmp = [(rot, fn, doc._ix("C170", campo), t)
               for (rot, fn, campo, t) in comparacoes]
    # a correlação de CFOP pressupõe saída do fornecedor -> entrada; nas
    # saídas próprias o CFOP do XML é o mesmo do SPED
    correl = (normalizar_correlacoes(correlacoes_cfop)
              if correlacoes_cfop and movimento == "entrada" else None)

    ind_oper = MOVIMENTOS.get(movimento)   # None em "ambos"
    nfes55 = [n for n in nfes if xf.norm(n.mod) == modelo]

    # --- nível documento: VL_DOC (C100) x vNF (XML) ----------------------
    c100_55 = [r for r in doc.registros
               if r.reg == "C100" and r.valor(iC_mod) == modelo
               and (ind_oper is None
                    or (r.valor(iC_op) or "").strip() == ind_oper)]

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
    csosn = 0                 # itens de fornecedor do Simples, não comparáveis
    # cache por documento: a decisão sobre as despesas acessórias é do C100
    criterio = {}
    for (nfe, it), c170list in pares:
        c170 = c170list[0]
        itens_conferidos += 1
        chave = id(c170.pai)
        if chave not in criterio:
            criterio[chave] = not acessorios_no_documento(doc, c170.pai, nfe)
        somar = criterio[chave]
        for rot, fn_xml, idx, t in idx_cmp:
            if idx is None:
                continue
            # a auto-detecção de acessórios só vale para a função padrão:
            # quem passa a própria função em `comparacoes` manda nela
            vx = (valor_item_xml(it, somar) if fn_xml is valor_item_xml
                  else fn_xml(it)) or 0.0
            vs = _to_num(c170.valor(idx))
            if abs(vx - vs) > t:
                divergencias.append(Divergencia(
                    mod=nfe.mod, serie=nfe.serie, nnf=nfe.nnf, nitem=it.nitem, uid=c170.uid,
                    escopo="item", campo=rot, valor_xml=vx, valor_sped=vs,
                    obs="cProd XML=%s / COD_ITEM=%s"
                        % (it.cprod, c170.valor(doc._ix("C170", "COD_ITEM")))))

        # correlação de CFOP (saída do fornecedor -> entrada do comprador)
        if correl is not None and i170_cfop is not None:
            cfop_x = _so_digitos(it.cfop)
            cfop_s = _so_digitos(c170.valor(i170_cfop))
            validos = correl.get(cfop_x)
            if validos:
                if cfop_s not in validos:
                    divergencias.append(Divergencia(
                        mod=nfe.mod, serie=nfe.serie, nnf=nfe.nnf,
                        nitem=it.nitem, uid=c170.uid, escopo="item", campo="CFOP",
                        valor_xml=cfop_x, valor_sped=cfop_s,
                        obs="entrada deveria ser: %s"
                            % " ou ".join(sorted(validos))))
            elif avisar_cfop_sem_regra and cfop_x:
                divergencias.append(Divergencia(
                    mod=nfe.mod, serie=nfe.serie, nnf=nfe.nnf,
                    nitem=it.nitem, uid=c170.uid, escopo="item", campo="CFOP (sem regra)",
                    valor_xml=cfop_x, valor_sped=cfop_s,
                    obs="sem correlação cadastrada para o CFOP de saída %s"
                        % cfop_x))

        # CST: deve ser o mesmo no XML e no C170 — a situação tributária da
        # mercadoria não muda entre a saída do fornecedor e a entrada. Quais
        # CST são conferidos depende do tributo (ICMS ou PIS/COFINS).
        for i170_cst, attr_xml, campo_cst in idx_cst:
            if i170_cst is None:
                continue
            cst_x = _so_digitos(getattr(it, attr_xml, None))
            cst_s = _so_digitos(c170.valor(i170_cst))
            # Fornecedor do Simples Nacional emite **CSOSN** (origem + 3
            # dígitos) e o comprador escritura um CST normal (origem + 2): são
            # tabelas diferentes, e comparar dígito a dígito só produz ruído.
            # Num arquivo real isso gerava 7 divergências inteiramente falsas.
            if len(cst_x) >= 4:
                csosn += 1
                continue
            if cst_x and cst_s and cst_x != cst_s:
                divergencias.append(Divergencia(
                    mod=nfe.mod, serie=nfe.serie, nnf=nfe.nnf,
                    nitem=it.nitem, uid=c170.uid, escopo="item",
                    campo=campo_cst, valor_xml=cst_x, valor_sped=cst_s,
                    obs="%s divergente entre XML e SPED" % campo_cst))

    resumo = {
        "xml_55": len(nfes55),
        "docs_casados": len(pares_doc),
        "docs_sem_c100": len(docs_sem_c100),
        "docs_sem_xml": len(docs_sem_xml),
        "itens_conferidos": itens_conferidos,
        "cst_csosn_ignorados": csosn,
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


def conferir_c190_com_xml(doc, nfes, tol=0.01):
    """
    Compara os registros **C190** (analítico de ICMS) com os **XMLs**, para
    entradas e saídas.

    O ponto central: o CFOP do XML é o de SAÍDA do fornecedor (5xxx/6xxx),
    diferente do CFOP de ENTRADA escriturado no SPED. Por isso o agrupamento dos
    itens do XML NÃO usa o CFOP do XML — usa a classificação do **C170** do SPED
    (CST_ICMS, CFOP, ALIQ_ICMS), casando XML ↔ C170 por **nItem**. Assim os
    grupos do C190 (ex.: CFOP 1101 e 1102, quando o XML só traz 5102) são
    reconstruídos a partir do XML preservando a correlação de cada item.

    Compara, por grupo, VL_OPR, VL_BC_ICMS e VL_ICMS (valores vindos do XML)
    contra o C190 do SPED. Retorna um dicionário com resumo e divergências.
    """
    i_num = doc._ix("C170", "NUM_ITEM")
    i_cfop = doc._ix("C170", "CFOP")
    i_cst = doc._ix("C170", "CST_ICMS")
    i_aliq = doc._ix("C170", "ALIQ_ICMS")
    j_cst = doc._ix("C190", "CST_ICMS")
    j_cfop = doc._ix("C190", "CFOP")
    j_aliq = doc._ix("C190", "ALIQ_ICMS")
    j_opr = doc._ix("C190", "VL_OPR")
    j_bc = doc._ix("C190", "VL_BC_ICMS")
    j_icms = doc._ix("C190", "VL_ICMS")
    i_mod = doc._ix("C100", "COD_MOD")
    i_ser = doc._ix("C100", "SER")
    i_num100 = doc._ix("C100", "NUM_DOC")

    idx_xml = xf.indexar(nfes, xf.chave_doc)

    divergencias = []
    grupos_so_c190 = []
    grupos_so_xml = []
    docs_sem_xml = []
    itens_sem_c170 = 0
    docs_casados = 0
    grupos_conf = 0

    def _grp(k):
        return "CFOP %s · CST %s · %s%%" % (k[1], k[0], k[2].replace(".", ","))

    for c100 in doc.registros:
        if c100.reg != "C100":
            continue
        c190s = [f for f in c100.filhos if f.reg == "C190"]
        if not c190s:
            continue
        mod = xf.norm(c100.valor(i_mod))
        ser = xf.norm(c100.valor(i_ser))
        num = xf.norm(c100.valor(i_num100))
        achados = idx_xml.get((mod, ser, num))
        if not achados:
            docs_sem_xml.append((mod, ser, num))
            continue
        nfe = achados[0]
        docs_casados += 1

        c170_por_item = {xf.norm(f.valor(i_num)): f
                         for f in c100.filhos if f.reg == "C170"}

        # agrupa os itens do XML pela classificação do C170 (por nItem)
        acess = (nfe.vfrete or 0.0) + (nfe.vseg or 0.0) + (nfe.voutro or 0.0)
        soma_vprod = sum((it.vprod or 0.0) for it in nfe.itens) or 1.0
        grupos = {}
        valor_acum = 0.0
        rateio_acum = 0.0
        for it in nfe.itens:
            c170 = c170_por_item.get(xf.norm(it.nitem))
            if c170 is None:
                itens_sem_c170 += 1
                continue
            gk = (c170.valor(i_cst), c170.valor(i_cfop),
                  "%.2f" % _to_num(c170.valor(i_aliq)))
            g = grupos.setdefault(gk, {"VL_OPR": 0.0, "VL_BC": 0.0,
                                       "VL_ICMS": 0.0})
            vprod = it.vprod or 0.0
            if acess:
                valor_acum += vprod
                ideal = round(acess * valor_acum / soma_vprod, 2)
                rateio = round(ideal - rateio_acum, 2)
                rateio_acum = ideal
            else:
                rateio = 0.0
            g["VL_OPR"] += (vprod - (it.vdesc or 0.0) + rateio
                            + (it.vipi or 0.0) + (it.icms_vicmsst or 0.0))
            g["VL_BC"] += it.icms_vbc or 0.0
            g["VL_ICMS"] += it.icms_vicms or 0.0

        c190_por_key = {
            (c.valor(j_cst), c.valor(j_cfop),
             "%.2f" % _to_num(c.valor(j_aliq))): c for c in c190s}

        for gk, g in grupos.items():
            grupos_conf += 1
            c = c190_por_key.get(gk)
            if c is None:
                grupos_so_xml.append((mod, num, _grp(gk)))
                continue
            comps = [("VL_OPR", g["VL_OPR"], _to_num(c.valor(j_opr))),
                     ("VL_BC_ICMS", g["VL_BC"], _to_num(c.valor(j_bc))),
                     ("VL_ICMS", g["VL_ICMS"], _to_num(c.valor(j_icms)))]
            for campo, vx, vs in comps:
                if abs(round(vx, 2) - round(vs, 2)) > tol:
                    divergencias.append(Divergencia(
                        mod=mod, serie=ser, nnf=num, nitem=_grp(gk),
                        escopo="C190", campo=campo, valor_xml=round(vx, 2),
                        valor_sped=round(vs, 2),
                        obs="dif %s" % _fmt(round(vx - vs, 2))))

        for k, c in c190_por_key.items():
            if k not in grupos:
                grupos_so_c190.append((mod, num, _grp(k)))

    resumo = {
        "docs_casados": docs_casados,
        "grupos_conferidos": grupos_conf,
        "divergencias": len(divergencias),
        "grupos_so_c190": len(grupos_so_c190),
        "grupos_so_xml": len(grupos_so_xml),
        "docs_sem_xml": len(docs_sem_xml),
        "itens_sem_c170": itens_sem_c170,
    }
    return {
        "resumo": resumo,
        "divergencias": divergencias,
        "grupos_so_c190": grupos_so_c190,
        "grupos_so_xml": grupos_so_xml,
        "docs_sem_xml": docs_sem_xml,
    }

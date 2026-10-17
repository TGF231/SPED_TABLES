# -*- coding: utf-8 -*-
"""
tabelas_oficiais.py
-------------------
Domínios de campo e consultas sobre as **tabelas oficiais** (as que os PVAs
publicam), lidas de **texto**: quem entrega o conjunto
`{chave: (texto, versao)}` é a base de referência (ou, no consolidador, a
pasta do PVA). Aqui só se interpreta o formato.

A motivação é direta: enquanto a lista de códigos válidos mora no código, ela
envelhece e diverge do validador oficial. Um caso real: o NCM `34011190` era
monofásico numa tabela que o programa não lia, e o PVA acusava algo que aqui
passava limpo. Lendo as tabelas oficiais, a verificação passa a ser a **mesma**
que o fisco aplica, e acompanha as atualizações sem mexer no código.

Formato das tabelas (idêntico nos dois PVAs, `latin-1`):

    versão=14 CFOP, DESC_CFOP, DT_INI, DT_FIM
    1101|Compra para industrialização|01012009|
    ...

O nome do arquivo carrega a versão: `GRUPO$TABELA$versao$id`. Quando há mais
de uma versão, vale a maior.

Três cuidados que o código incorpora:

* **Vigência.** Cada código traz DT_INI/DT_FIM. Códigos revogados não podem
  valer para um período posterior, nem os novos para um anterior — a
  validação usa a data final do arquivo.
* **Códigos compostos.** O CST do ICMS deixou de ter tabela única em 2012:
  hoje é origem (`SIT_TRIB_ICMS_A`) + situação (`SIT_TRIB_ICMS_B`). Validar
  contra a tabela antiga reprovaria o arquivo inteiro.
* **Tabelas por UF.** Códigos de ajuste (E111, E116) mudam de estado para
  estado; a UF vem do 0000 do arquivo.
"""

import os
import re

from sped_tables.infra import tabelas_ncm


# Tabela **única** do CST do ICMS publicada pelo PVA Fiscal (140 códigos com
# vigência). É ela que vale quando existe: além do par origem+situação, traz os
# códigos do Simples Nacional (101, 102, 201, 202, 900) e os de tributação
# monofásica de combustíveis criados em 01/04/2023 (final 02, 15, 53 e 61) —
# nenhum deles sai do produto cartesiano A × B, cuja tabela B é de 2009.
#
# Sem ela, um arquivo real de supermercado acusava 186 CST inválidos que o PVA
# aceita sem uma palavra: 107 CSOSN 101, 43 CSOSN 201, 25 CSOSN 102, 6 CSOSN
# 202 e 5 CST 061.
TABELA_CST_ICMS = "SPEDFISCAL_ST$SIT_TRIB_ICMS"

# Campos cujo código é a junção de duas tabelas (prefixo + sufixo). Só entram
# em cena quando a tabela única acima não está instalada.
COMPOSTOS = {
    ("ICMS", "CST_ICMS"): ("SPEDFISCAL_ST$SIT_TRIB_ICMS_A",
                           "SPEDFISCAL_ST$SIT_TRIB_ICMS_B"),
    ("CONTRIB", "CST_ICMS"): ("SPEDFISCAL_ST$SIT_TRIB_ICMS_A",
                              "SPEDFISCAL_ST$SIT_TRIB_ICMS_B"),
}

# rótulo amigável por campo, usado na mensagem de erro
ROTULOS = {
    "CFOP": "CFOP", "COD_MOD": "modelo do documento",
    "COD_SIT": "situação do documento", "IND_EMIT": "indicador do emitente",
    "CST_ICMS": "CST do ICMS", "CST_IPI": "CST do IPI",
    "CST_PIS": "CST de PIS", "CST_COFINS": "CST de COFINS",
    "COD_MUN": "município (IBGE)", "COD_PAIS": "país",
    "CEST": "CEST", "COD_GEN": "gênero do item",
    "TP_CT-e": "tipo do CT-e", "COD_AJ_APUR": "código de ajuste da apuração",
    "COD_REC": "código de receita", "COD_INF_ADIC": "informação adicional",
    "NAT_BC_CRED": "natureza da base de crédito",
    "COD_CRED": "tipo de crédito", "COD_AJ": "código de ajuste",
    "IND_NAT_PROC": "natureza da ação judicial",
}


# Datasource declarado no descritor do PVA -> tabela externa correspondente.
# O nome do datasource nem sempre é o do arquivo (`TP_CTE` x `TP_CT_E`), e
# datasource terminado em `_SV` aponta para dados do próprio arquivo (o combo
# do 0200, do 0150...), não para tabela — esses ficam de fora.
DATASOURCE_ICMS = {
    "CFOP": "SPEDFISCAL_GLOBAL$CFOP",
    "COD_MUN": "SPEDFISCAL_GLOBAL$MUNICIPIOS",
    "COD_PAIS": "SPEDFISCAL_GLOBAL$PAISES",
    "COD_GEN": "SPEDFISCAL_GLOBAL$GEN_ITEM_MERC_SERV",
    "CEST": "SPEDFISCAL_GLOBAL$COD_CEST",
    "COD_SIT": "SPEDFISCAL_CARDOC$COD_SIT",
    "COD_MOD": "SPEDFISCAL_CARDOC$MOD_DOC",
    "COD_MOD_ECF": "SPEDFISCAL_CARDOC$MOD_DOC",
    "CST_IPI": "SPEDFISCAL_ST$SIT_TRIB_IPI",
    "CST_PIS": "SPEDFISCAL_ST$SIT_TRIB_PIS",
    "CST_COFINS": "SPEDFISCAL_ST$SIT_TRIB_COFINS",
    "TP_CTE": "SPEDFISCAL_GLOBAL$TP_CT_E",
    "UF_SIGLA_NOME": "SPEDFISCAL_GLOBAL$UF_SIG_NOM",
    "COD_INF_ADIC": "SPEDFISCAL_{UF}$INF_ADIC_APUR",
    "COD_PROD_USINAS": "SPEDFISCAL_{UF}$COD_PROD_USINAS",
    "COD_MOT_REST_COMPL": "SPEDFISCAL_{UF}$COD_MOT_REST_COMPL_ST",
}
# códigos de ajuste e de receita: o nome do datasource varia com a versão da
# regra (COD_AJ_APURACAO_A7E1V1, COD_REC_E316_V3...), então casa por prefixo
PREFIXOS_DATASOURCE_ICMS = (
    ("COD_AJ_APURACAO", "SPEDFISCAL_{UF}$AJ_APUR_DED"),
    ("COD_REC", "SPEDFISCAL_{UF}$REC_REF_OBRIGACAO"),
    # obrigações do ICMS a recolher (000, 003, 090...): COD_OR no E116,
    # E250 e 1926, COD_OR_E316 no E316. Até a 1.0.0-rc.1 apontava para a
    # tabela de códigos de RECEITA da UF e não acusava nada só porque o
    # descritor trazia, num comentário XML, uma enumeração lida como se
    # valesse
    ("COD_OR", "SPEDFISCAL_GLOBAL$OBR_ICMS_RECOL"),
)
# CST do ICMS é o par origem+situação, tratado à parte
DATASOURCE_COMPOSTO = {"CST_ICMS": ("SPEDFISCAL_ST$SIT_TRIB_ICMS_A",
                                    "SPEDFISCAL_ST$SIT_TRIB_ICMS_B")}


def tabela_do_datasource(ds, layout):
    """Chave da tabela externa para um datasource do descritor, ou None.

    No **EFD Contribuições** nenhum datasource é tratado como tabela de
    validação: lá eles alimentam as listas de seleção da edição, e cobrar o
    conteúdo produziria erro que o PVA não acusa — o `CST_ICMS` do C170 é o
    caso que motivou a regra.
    """
    if not ds or layout != "ICMS" or ds.endswith("_SV"):
        return None
    if ds in DATASOURCE_ICMS:
        return DATASOURCE_ICMS[ds]
    for pref, chave in PREFIXOS_DATASOURCE_ICMS:
        if ds.startswith(pref):
            return chave
    return None


# nome de arquivo de tabela do PVA: GRUPO$TABELA$versao$id
RE_ARQUIVO = re.compile(r"^(.*?)\$(\d+)\$\d+$")


def tabelas_da_pasta(pasta, encoding="latin-1"):
    """`{chave: (texto, versao)}` das tabelas de uma pasta do PVA, cada uma
    na **maior versão**. Arquivo fora do padrão `GRUPO$TABELA$versao$id`
    (o `metadados`, binário) fica de fora."""
    out = {}
    if not pasta or not os.path.isdir(pasta):
        return out
    for nome in sorted(os.listdir(pasta)):
        m = RE_ARQUIVO.match(nome)
        caminho = os.path.join(pasta, nome)
        if not m or not os.path.isfile(caminho):
            continue
        chave, versao = m.group(1), int(m.group(2))
        if chave in out and out[chave][1] >= versao:
            continue
        with open(caminho, encoding=encoding) as fh:
            out[chave] = (fh.read(), versao)
    return out


def chave_data(ddmmaaaa):
    """DDMMAAAA -> AAAAMMDD, para comparar como texto."""
    d = "".join(c for c in (ddmmaaaa or "") if c.isdigit())
    return d[4:8] + d[2:4] + d[0:2] if len(d) == 8 else ""


def carregar_codigos(texto, data_ref=None):
    """Lê uma tabela de códigos no formato do PVA. Devolve `{"versao",
    "codigos"}`, com `codigos` = `{codigo: descricao}` **vigentes** em
    `data_ref`.

    Sem `data_ref`, entra tudo — útil para inspeção, não para validar.
    """
    codigos = {}
    versao = None
    linhas = (texto or "").splitlines()
    if linhas:
        m = re.search(r"vers[\u00e3a]o=(\S+)", linhas[0])
        versao = m.group(1) if m else None
    alvo = chave_data(data_ref)
    for l in linhas[1:]:
        if not l.strip():
            continue
        p = l.split("|")
        cod = p[0].strip()
        if not cod:
            continue
        if alvo and len(p) >= 4:
            ini = chave_data(p[2]) or "00000000"
            fim = chave_data(p[3]) or "99999999"
            if not (ini <= alvo <= fim):
                continue
        # a mesma tabela pode trazer o código mais de uma vez (redações
        # diferentes por período); a primeira vigente basta
        codigos.setdefault(cod, (p[1].strip() if len(p) > 1 else ""))
    return {"versao": versao, "codigos": codigos}


def dominio_cst_icms(tabs, data_ref=None):
    """Domínio do CST do ICMS: tabela única do PVA, ou o par A × B.

    Devolve `(codigos, versao, nome)` ou `(None, None, None)`.
    """
    alvo = tabs.get(TABELA_CST_ICMS)
    if alvo:
        t = carregar_codigos(alvo[0], data_ref)
        if t["codigos"]:
            return (set(t["codigos"]), t["versao"],
                    TABELA_CST_ICMS.split("$")[-1])
    par = COMPOSTOS.get(("ICMS", "CST_ICMS"))
    a, b = (tabs.get(par[0]), tabs.get(par[1])) if par else (None, None)
    if a and b:
        ta = carregar_codigos(a[0], data_ref)
        tb = carregar_codigos(b[0], data_ref)
        if ta["codigos"] and tb["codigos"]:
            return ({x + y for x in ta["codigos"] for y in tb["codigos"]},
                    "%s+%s" % (ta["versao"], tb["versao"]),
                    "%s + %s" % (par[0].split("$")[-1], par[1].split("$")[-1]))
    return None, None, None


def cfops_com_credito(tabs, data_ref=None):
    """CFOP que admitem crédito de PIS/COFINS, pela tabela do PVA.

    `SPEDPISCOFINS_CFOP_CREDITO` (4.3.7) lista os 89 CFOP de entrada que geram
    crédito, cada um com a natureza da base (`NAT_BC_CRE`). O PVA usa essa
    tabela na regra `REGRA_COMPATIBILIDADE_CFOP_CRED`: CST de creditamento num
    CFOP fora dela é advertência (`MSG_COMPATIBILIDADE_CFOP_CRED`).

    Devolve `(codigos, versao)`; `(None, None)` se a tabela não estiver
    instalada — sem ela a verificação não roda, em vez de aprovar no escuro.
    """
    return codigos_de("SPEDPISCOFINS_OPER_CREDITO$SPEDPISCOFINS_CFOP_CREDITO",
                      tabs, None, data_ref)


# Tabela da natureza da receita (NAT_REC do M410/M810) pelo CST do M400/M800
TABELAS_NAT_REC = {
    "04": ("PROD_MONO_ALIQ_DIFER", "PROD_MONO_ALIQ_UNID"),   # 4.3.10/4.3.11
    "05": ("PROD_ST",),                                     # 4.3.12
    "06": ("PROD_ALIQ_ZERO",),                              # 4.3.13
    "07": ("OPER_COM_ISENCAO",),                            # 4.3.14
    "08": ("OPER_SEM_INCIDENCIA",),                         # 4.3.15
    "09": ("OPER_COM_SUSPENSAO",),                          # 4.3.16
}


def naturezas_receita(tabs, cst, data_ref=None):
    """Códigos de natureza da receita válidos para o CST do M400/M800, ou
    None quando o CST não tem tabela (ou ela não está instalada)."""
    nomes = TABELAS_NAT_REC.get((cst or "").strip())
    if not nomes:
        return None
    out = set()
    achou = False
    for nome in nomes:
        alvo = tabs.get("SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_" + nome)
        if alvo:
            achou = True
            out |= set(carregar_codigos(alvo[0], data_ref)["codigos"])
    return out if achou else None


def tabela_natureza_receita(tabs, cst):
    """`[(código, [prefixos de NCM], ex_ipi)]` das tabelas de natureza da
    receita do CST (4.3.10 a 4.3.16) — para achar a natureza de um produto
    pelo NCM. Natureza sem NCM na tabela (a 918 das bebidas frias, por
    exemplo, que só o texto descreve) vem com a lista vazia."""
    nomes = TABELAS_NAT_REC.get((cst or "").strip(), ())
    out = []
    for nome in nomes:
        alvo = tabs.get("SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_" + nome)
        if not alvo:
            continue
        tabela = tabelas_ncm.carregar_tabela_produtos(alvo[0])
        for reg in tabela["registros"]:
            if reg["dt_fim"]:
                continue                  # natureza que já saiu da tabela
            out.append((reg["codigo"], [n for n in reg["ncm"] if n],
                        reg.get("ex_ipi", "")))
    return out


def ncms_da_natureza(tabs, codigo):
    """Prefixos de NCM que as tabelas de natureza da receita (4.3.10 a
    4.3.16) associam ao `codigo` — o produto de que a receita é."""
    out = set()
    for nomes in TABELAS_NAT_REC.values():
        for nome in nomes:
            alvo = tabs.get("SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_" + nome)
            if not alvo:
                continue
            tabela = tabelas_ncm.carregar_tabela_produtos(alvo[0])
            for reg in tabela["registros"]:
                if reg["codigo"] == codigo:
                    out.update(reg["ncm"])
    out.discard("")
    return out


def naturezas_cfop_credito(tabs, data_ref=None):
    """`{cfop: NAT_BC_CRED}` — a natureza da base do crédito por CFOP.

    A quinta coluna de `SPEDPISCOFINS_CFOP_CREDITO` traz `NAT_BC_CRE`: é ela
    que diz se a entrada é aquisição para revenda (01), insumo (02) e assim
    por diante. Num arquivo real, agrupar os C170 por essa coluna reproduziu
    exatamente o rateio que o contribuinte tinha no M105 — inclusive o único
    item de natureza 02.

    Devolve `{}` quando a tabela não está instalada: sem ela não dá para
    refazer o crédito, e chutar a natureza seria pior que não mexer.
    """
    alvo = tabs.get("SPEDPISCOFINS_OPER_CREDITO$SPEDPISCOFINS_CFOP_CREDITO")
    if not alvo:
        return {}
    fim = chave_data(data_ref)
    out = {}
    linhas = alvo[0].splitlines()
    for l in linhas[1:]:
        p = l.split("|")
        if len(p) < 5 or not p[0].strip():
            continue
        if fim:
            ini = chave_data(p[2]) or "00000000"
            f = chave_data(p[3]) or "99999999"
            if not (ini <= fim <= f):
                continue
        out.setdefault(p[0].strip(), p[4].strip())
    return out


def prazo_entrega(tabs, mes_ano):
    """Data limite de entrega da EFD Contribuições do período `MMAAAA`.

    Vem de `SPEDPISCOFINS_DATA_LIMITE_ENTREGA`, a mesma tabela que o PVA cita
    ao pedir o registro 0900. Devolve `DDMMAAAA` ou `""`.
    """
    alvo = tabs.get("SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_DATA_LIMITE_ENTREGA")
    if not alvo:
        return ""
    t = carregar_codigos(alvo[0])
    return t["codigos"].get(mes_ano, "")


def codigos_receita_icms(tabs, uf, data_ref=None):
    """`{código: descrição}` da tabela de receitas da UF
    (`SPEDFISCAL_{UF}$REC_REF_OBRIGACAO`, o datasource do COD_REC do E116),
    só os vigentes em `data_ref`."""
    if not uf:
        return {}
    alvo = tabs.get("SPEDFISCAL_%s$REC_REF_OBRIGACAO" % uf.upper())
    if alvo is None:
        return {}
    return carregar_codigos(alvo[0], data_ref)["codigos"]


def codigos_de(chave, tabs, uf=None, data_ref=None):
    """Conjunto de códigos vigentes de uma tabela, resolvendo `{UF}`."""
    if "{UF}" in chave:
        if not uf:
            return None, None
        chave = chave.replace("{UF}", uf.upper())
    alvo = tabs.get(chave)
    if alvo is None:
        return None, None
    t = carregar_codigos(alvo[0], data_ref)
    return (set(t["codigos"]) or None), t["versao"]


def dominios_por_datasource(tabs, estrutura, layout, uf=None, data_ref=None):
    """Domínios de tabela externa, **na granularidade do descritor**:
    `{(registro, campo): {...}}`.

    É por registro porque o PVA é por registro — no EFD Contribuições o
    `CST_PIS` tem tabela diferente no C175, no C181 e no C191. Validar por
    nome de campo, como antes, achatava essas diferenças.
    """
    cache = {}
    out = {}
    faltando = set()
    for reg, d in estrutura.items():
        for campo, c in d["campos"].items():
            ds = c.get("datasource")
            if campo in DATASOURCE_COMPOSTO and layout == "ICMS" and ds:
                if campo not in cache:
                    c, v, nome = dominio_cst_icms(tabs, data_ref)
                    cache[campo] = (c, v, nome)
                cods, versao, nome_tab = cache[campo]
            else:
                chave = tabela_do_datasource(ds, layout)
                if not chave:
                    continue
                if chave not in cache:
                    cache[chave] = codigos_de(chave, tabs, uf, data_ref)
                cods, versao = cache[chave]
                nome_tab = chave.replace("{UF}", uf or "")
            if not cods:
                faltando.add(nome_tab)
                continue
            out[(reg, campo)] = {"codigos": cods,
                                 "rotulo": ROTULOS.get(campo, campo),
                                 "tabela": nome_tab, "versao": versao}
    return out, sorted(faltando)

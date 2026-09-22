# -*- coding: utf-8 -*-
"""
tabelas_pva.py
--------------
Domínios de campo lidos das **tabelas dos próprios PVAs** — EFD ICMS/IPI
(`Fiscal/recursos/TabelasExternas`) e EFD Contribuições
(`EFD-Contribuicoes/recursos/tabelas`).

A motivação é direta: enquanto a lista de códigos válidos mora no código, ela
envelhece e diverge do validador oficial. Um caso real: o NCM `34011190` era
monofásico numa tabela que o programa não lia, e o PVA acusava algo que aqui
passava limpo. Lendo as tabelas do PVA, a verificação passa a ser a **mesma**
que o fisco aplica, e acompanha as atualizações do programa sem mexer no
código.

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
import glob

PASTA_FISCAL = (r"C:\Arquivos de Programas RFB\Programas SPED"
                r"\Fiscal\recursos\TabelasExternas")
PASTA_CONTRIB = (r"C:\Arquivos de Programas RFB\Programas SPED"
                 r"\EFD-Contribuicoes\recursos\tabelas")

# Campo do leiaute -> tabela do PVA. `{UF}` é trocado pela UF do arquivo.
# Só entram campos cujo domínio é uma tabela fechada de códigos.
MAPA_ICMS = {
    "CFOP": "SPEDFISCAL_GLOBAL$CFOP",
    "COD_MOD": "SPEDFISCAL_CARDOC$MOD_DOC",
    "COD_SIT": "SPEDFISCAL_CARDOC$COD_SIT",
    "IND_EMIT": "SPEDFISCAL_CARDOC$IND_EMIT",
    "CST_IPI": "SPEDFISCAL_ST$SIT_TRIB_IPI",
    "CST_PIS": "SPEDFISCAL_ST$SIT_TRIB_PIS",
    "CST_COFINS": "SPEDFISCAL_ST$SIT_TRIB_COFINS",
    "COD_MUN": "SPEDFISCAL_GLOBAL$MUNICIPIOS",
    "COD_PAIS": "SPEDFISCAL_GLOBAL$PAISES",
    "CEST": "SPEDFISCAL_GLOBAL$COD_CEST",
    "COD_GEN": "SPEDFISCAL_GLOBAL$GEN_ITEM_MERC_SERV",
    "TP_CT-e": "SPEDFISCAL_GLOBAL$TP_CT_E",
    "COD_AJ_APUR": "SPEDFISCAL_{UF}$AJ_APUR_DED",
    "COD_REC": "SPEDFISCAL_{UF}$REC_REF_OBRIGACAO",
    "COD_INF_ADIC": "SPEDFISCAL_{UF}$INF_ADIC_APUR",
}

MAPA_CONTRIB = {
    "CFOP": "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_CFOP",
    "CST_PIS": "SPEDPISCOFINS_CST$SPEDPISCOFINS_CST_PIS",
    "CST_COFINS": "SPEDPISCOFINS_CST$SPEDPISCOFINS_CST_COFINS",
    "CST_IPI": "SPEDPISCOFINS_CST$SPEDPISCOFINS_CST_IPI",
    "COD_MOD": "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_MODELOS",
    "COD_MUN": "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_MUNICIPIOS",
    "COD_PAIS": "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_PAISES",
    "NAT_BC_CRED": "SPEDPISCOFINS_APURACAO$SPEDPISCOFINS_BC_CRED",
    "COD_CRED": "SPEDPISCOFINS_APURACAO$SPEDPISCOFINS_TIPO_CRED",
    "COD_AJ": "SPEDPISCOFINS_APURACAO$SPEDPISCOFINS_AJ_CONTRIB_CRED",
    "IND_NAT_PROC": "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_NATUREZA_ACAO_JUDICIAL",
}

# Campos cujo código é a junção de duas tabelas (prefixo + sufixo).
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
    ("COD_OR", "SPEDFISCAL_{UF}$REC_REF_OBRIGACAO"),
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


def _chave_sem_versao(nome):
    """`GRUPO$TABELA$12$34` -> (`GRUPO$TABELA`, 12)."""
    m = re.match(r"^(.*?)\$(\d+)\$\d+$", nome)
    if m:
        return m.group(1), int(m.group(2))
    return nome, 0


def listar_tabelas(pasta):
    """Tabelas da pasta, já resolvidas para a **maior versão** de cada uma.
    Devolve `{chave: (caminho, versao)}`."""
    out = {}
    if not pasta or not os.path.isdir(pasta):
        return out
    for caminho in glob.glob(os.path.join(pasta, "*")):
        if os.path.isdir(caminho):
            continue
        chave, versao = _chave_sem_versao(os.path.basename(caminho))
        if chave not in out or versao > out[chave][1]:
            out[chave] = (caminho, versao)
    return out


def _chave_data(s):
    """DDMMAAAA -> AAAAMMDD, para comparar como texto."""
    d = "".join(c for c in (s or "") if c.isdigit())
    return d[4:8] + d[2:4] + d[0:2] if len(d) == 8 else ""


def carregar_codigos(caminho, data_ref=None, encoding="latin-1"):
    """Lê uma tabela de códigos do PVA. Devolve `{"versao", "codigos"}`,
    com `codigos` = `{codigo: descricao}` **vigentes** em `data_ref`.

    Sem `data_ref`, entra tudo — útil para inspeção, não para validar.
    """
    codigos = {}
    versao = None
    try:
        with open(caminho, encoding=encoding) as fh:
            linhas = fh.read().splitlines()
    except OSError:
        return {"versao": None, "codigos": {}}
    if linhas:
        m = re.search(r"vers[\u00e3a]o=(\S+)", linhas[0])
        versao = m.group(1) if m else None
    alvo = _chave_data(data_ref)
    for l in linhas[1:]:
        if not l.strip():
            continue
        p = l.split("|")
        cod = p[0].strip()
        if not cod:
            continue
        if alvo and len(p) >= 4:
            ini = _chave_data(p[2]) or "00000000"
            fim = _chave_data(p[3]) or "99999999"
            if not (ini <= alvo <= fim):
                continue
        # a mesma tabela pode trazer o código mais de uma vez (redações
        # diferentes por período); a primeira vigente basta
        codigos.setdefault(cod, (p[1].strip() if len(p) > 1 else ""))
    return {"versao": versao, "codigos": codigos}


def carregar_dominios(layout, pasta_fiscal=None, pasta_contrib=None, uf=None,
                      data_ref=None):
    """Monta `{campo: dominio}` a partir das tabelas do PVA do `layout`.

    Cada domínio é `{"codigos": set, "rotulo": str, "tabela": str,
    "versao": str}`. Devolve `(dominios, info)`, com `info` listando o que foi
    encontrado e o que faltou — silêncio sobre tabela ausente é pior que erro,
    porque a validação passaria a aprovar o que não conferiu.
    """
    pasta_fiscal = pasta_fiscal or PASTA_FISCAL
    pasta_contrib = pasta_contrib or PASTA_CONTRIB
    # o CST do ICMS vem sempre das tabelas do PVA Fiscal, mesmo no arquivo de
    # Contribuições: é o mesmo domínio, e só o Fiscal o publica separado
    tabs = dict(listar_tabelas(pasta_fiscal))
    tabs.update(listar_tabelas(pasta_contrib))

    mapa = MAPA_ICMS if layout == "ICMS" else MAPA_CONTRIB
    dominios = {}
    usadas = {}
    faltando = []

    def resolver(chave):
        if "{UF}" in chave:
            if not uf:
                return None
            chave = chave.replace("{UF}", uf.upper())
        return tabs.get(chave)

    for campo, chave in mapa.items():
        alvo = resolver(chave)
        if alvo is None:
            faltando.append(chave.replace("{UF}", uf or "UF"))
            continue
        caminho, _v = alvo
        t = carregar_codigos(caminho, data_ref)
        if not t["codigos"]:
            faltando.append(os.path.basename(caminho))
            continue
        dominios[campo] = {"codigos": set(t["codigos"]),
                           "rotulo": ROTULOS.get(campo, campo),
                           "tabela": chave.replace("{UF}", uf or ""),
                           "versao": t["versao"]}
        usadas[campo] = os.path.basename(caminho)

    # compostos: origem + situação
    par = COMPOSTOS.get((layout, "CST_ICMS"))
    if par:
        a, b = tabs.get(par[0]), tabs.get(par[1])
        if a and b:
            ta = carregar_codigos(a[0], data_ref)
            tb = carregar_codigos(b[0], data_ref)
            if ta["codigos"] and tb["codigos"]:
                dominios["CST_ICMS"] = {
                    "codigos": {x + y for x in ta["codigos"]
                                for y in tb["codigos"]},
                    "rotulo": ROTULOS["CST_ICMS"],
                    "tabela": "%s + %s" % (par[0].split("$")[-1],
                                           par[1].split("$")[-1]),
                    "versao": "%s+%s" % (ta["versao"], tb["versao"])}
                usadas["CST_ICMS"] = "%s + %s" % (os.path.basename(a[0]),
                                                  os.path.basename(b[0]))
        else:
            faltando.extend(p for p in par if p not in tabs)

    return dominios, {"usadas": usadas, "faltando": sorted(set(faltando)),
                      "pasta_fiscal": pasta_fiscal,
                      "pasta_contrib": pasta_contrib,
                      "tabelas_vistas": len(tabs)}


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


def dominios_por_datasource(estrutura, layout, pasta_fiscal=None,
                            pasta_contrib=None, uf=None, data_ref=None):
    """Domínios de tabela externa, **na granularidade do descritor**:
    `{(registro, campo): {...}}`.

    É por registro porque o PVA é por registro — no EFD Contribuições o
    `CST_PIS` tem tabela diferente no C175, no C181 e no C191. Validar por
    nome de campo, como antes, achatava essas diferenças.
    """
    tabs = dict(listar_tabelas(pasta_fiscal or PASTA_FISCAL))
    tabs.update(listar_tabelas(pasta_contrib or PASTA_CONTRIB))
    cache = {}
    out = {}
    faltando = set()
    for reg, d in estrutura.items():
        for campo, c in d["campos"].items():
            ds = c.get("datasource")
            if campo in DATASOURCE_COMPOSTO and layout == "ICMS" and ds:
                par = DATASOURCE_COMPOSTO[campo]
                if par not in cache:
                    a, va = codigos_de(par[0], tabs, uf, data_ref)
                    b, vb = codigos_de(par[1], tabs, uf, data_ref)
                    cache[par] = ({x + y for x in a for y in b}
                                  if a and b else None,
                                  "%s+%s" % (va, vb))
                cods, versao = cache[par]
                nome_tab = "%s + %s" % (par[0].split("$")[-1],
                                        par[1].split("$")[-1])
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


def disponivel(pasta_fiscal=None, pasta_contrib=None):
    """Há tabelas de PVA instaladas? Usado para decidir se a validação por
    tabela pode ser oferecida."""
    return bool(listar_tabelas(pasta_fiscal or PASTA_FISCAL)
                or listar_tabelas(pasta_contrib or PASTA_CONTRIB))

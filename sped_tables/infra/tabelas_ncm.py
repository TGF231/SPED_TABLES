# -*- coding: utf-8 -*-
"""Tabelas de produtos da EFD Contribuições usadas na conferência de CST por
NCM, lidas de **texto**:

  * Tabela 4.3.13 — Produtos sujeitos à **alíquota zero** (CST 06);
  * Tabela 4.3.10 — Produtos monofásicos de **alíquotas diferenciadas**
    (`PROD_MONO_ALIQ_DIFER`): perfumaria, higiene pessoal, medicamentos,
    veículos, autopeças — a Lei 10.147/2000 e afins;
  * Tabela 4.3.11 — Produtos monofásicos de **alíquota por unidade de medida**
    (`PROD_MONO_ALIQ_UNID`): combustíveis, bebidas frias;
  * Tabela de **gênero do item** (2 primeiros dígitos do NCM = capítulo).

Quem entrega o texto é o conjunto `{chave: (texto, versao)}` das tabelas
oficiais (ver `tabelas_oficiais`); as chaves são `GRUPO$TABELA`, na maior
versão.
"""

import re

from sped_tables.dominio.ncm import ClassificadorNCM, normalizar_ex
from sped_tables.dominio.sped_model import so_digitos

# chave completa (`GRUPO$TABELA`) de cada tabela no conjunto
CHAVE_ALIQ_ZERO = "SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_PROD_ALIQ_ZERO"
# São DUAS tabelas de monofásico, e ler só uma esconde metade dos produtos:
# o NCM 34011190 (sabonete) só existe na de alíquotas diferenciadas, e sem ela
# o programa não via nada que o PVA via.
CHAVE_MONO = "SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_PROD_MONO_ALIQ_UNID"
CHAVE_MONO_DIFER = ("SPEDPISCOFINS_OPER_CONTRIB$"
                    "SPEDPISCOFINS_PROD_MONO_ALIQ_DIFER")
CHAVE_GENERO = "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_GENERO_ITEM"


def _ler_versao_cabecalho(linha):
    m = re.search(r"vers[\u00e3a]o=(\S+)", linha)
    return m.group(1) if m else None


def carregar_tabela_produtos(texto):
    """Lê uma tabela de produtos (4.3.11 ou 4.3.13). Devolve dict com 'versao'
    e 'registros' (lista). Cada registro traz codigo, desc, dt_ini, dt_fim,
    ncm (lista de prefixos, só dígitos), ncm_ex (exceções) e, na 4.3.11,
    unid/aliq_pis/aliq_cofins."""
    linhas = (texto or "").splitlines()
    if not linhas:
        return {"versao": None, "registros": []}
    versao = _ler_versao_cabecalho(linhas[0])
    registros = []
    for l in linhas[1:]:
        if not l.strip():
            continue
        p = l.split("|")
        if len(p) < 5:
            continue
        reg = {
            "codigo": p[0].strip(),
            "desc": p[1].strip(),
            "dt_ini": p[2].strip(),
            "dt_fim": p[3].strip(),
            "ncm": [so_digitos(x) for x in p[4].split(";") if x.strip()],
            "ncm_ex": [so_digitos(x) for x in
                       (p[5].split(";") if len(p) > 5 else []) if x.strip()],
            # "Ex" da TIPI: a linha só vale para o produto com esse EX_IPI
            # no 0200 (o 21069010 com Ex 02 é o concentrado para
            # refrigerante, não toda preparação alimentícia)
            "ex_ipi": normalizar_ex(p[6]) if len(p) > 6 else "",
        }
        if len(p) >= 10:            # 4.3.11: ...|EX_IPI|UNID|ALIQ_PIS|ALIQ_COFINS
            reg["unid"] = p[7].strip()
            reg["aliq_pis"] = p[8].strip()
            reg["aliq_cofins"] = p[9].strip()
        elif len(p) >= 9:           # 4.3.10: ...|EX_IPI|ALIQ_PIS|ALIQ_COFINS
            reg["aliq_pis"] = p[7].strip()
            reg["aliq_cofins"] = p[8].strip()
        registros.append(reg)
    return {"versao": versao, "registros": registros}


def carregar_genero(texto):
    """Lê a tabela de gênero do item. Devolve dict {codigo_2dig: descricao}."""
    linhas = (texto or "").splitlines()
    genero = {}
    for l in linhas[1:]:
        p = l.split("|")
        if len(p) >= 2 and p[0].strip():
            genero[p[0].strip().zfill(2)] = p[1].strip()
    return genero


def _unir_tabelas(*tabelas):
    """Funde tabelas de produtos numa só, para o classificador tratar as duas
    listas de monofásico como uma. A versão vira `a+b`, para aparecer na
    interface qual par foi carregado."""
    regs = []
    versoes = []
    for t in tabelas:
        if not t:
            continue
        regs.extend(t.get("registros", []))
        if t.get("versao"):
            versoes.append(str(t["versao"]))
    if not regs and not versoes:
        return None
    return {"versao": "+".join(versoes) or None, "registros": regs}


def classificador(tabs, ncm_vigente=None):
    """`ClassificadorNCM` das tabelas de alíquota zero, das duas de
    monofásico e do gênero do item, mais o conjunto de NCM vigente (ou
    None). Sem nenhuma das tabelas de produto, devolve None: a regra se
    abstém em vez de aprovar no escuro."""
    def produtos(chave):
        alvo = tabs.get(chave)
        return carregar_tabela_produtos(alvo[0]) if alvo else None

    tab_zero = produtos(CHAVE_ALIQ_ZERO)
    # as duas tabelas de monofásico viram uma só para o classificador
    tab_mono = _unir_tabelas(produtos(CHAVE_MONO), produtos(CHAVE_MONO_DIFER))
    if tab_zero is None and tab_mono is None:
        return None
    gen = tabs.get(CHAVE_GENERO)
    return ClassificadorNCM(tab_zero, tab_mono,
                            carregar_genero(gen[0]) if gen else None,
                            ncm_vigente or None)

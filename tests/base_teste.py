# -*- coding: utf-8 -*-
"""Fontes de base de referência inventadas (no formato de `base/`), para
testar compilação, importação e o adaptador sem PVA nem a base real."""

import json
import os

from sped_tables.infra import base_referencia

TABELA_CFOP = ("versão=14 CFOP, DESC_CFOP, DT_INI, DT_FIM\n"
               "1102|Compra para comercialização|01012009|\n"
               "5102|Venda de mercadoria|01012009|\n"
               "1999|Revogado|01012009|31122010\n")


def campo(tipo="C", tamanho="", valores=None, obrigatorio="0",
          datasource=None, referencia=None, n=None):
    return {"n": n, "tipo": tipo, "tamanho": tamanho, "decimais": "",
            "obrigatorio": obrigatorio, "valores": valores,
            "datasource": datasource, "referencia": referencia,
            "rotulo": "", "descricao": "", "significados": {}}


def registro(campos, nivel=2):
    return {"nivel": nivel, "ocorrencia": "1:N", "obrigatorio": "0",
            "chave": "", "rotulo": "", "descricao": "", "validadores": [],
            "campos": campos}


def estrutura_c100(ind_emit):
    """Um C100 de três campos, com o IND_EMIT aceitando `ind_emit`."""
    return {"C100": registro({
        "REG": campo(tamanho="[4]", n=1),
        "IND_OPER": campo(tamanho="[1]", valores=["0", "1"], n=2),
        "IND_EMIT": campo(tamanho="[1]", valores=list(ind_emit), n=3)})}


def _json(caminho, objeto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(objeto, fh, ensure_ascii=False, indent=1)


def _texto(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)


def escrever(pasta, versao="2026.10.1", leiautes=None, tabelas=None,
             guias=None, ncm=None, esquema=base_referencia.ESQUEMA):
    """Escreve fontes em `pasta`, no formato de `base/`, e devolve a pasta.

    `leiautes`: `{layout: {cod: (dt_ini, dt_fim, estrutura)}}`;
    `tabelas`: `{chave: (texto, versao)}`. O padrão tem o ICMS/IPI em 019
    (IND_EMIT 0 ou 1) e 020 (só 0) e o Contribuições em 006."""
    if leiautes is None:
        leiautes = {
            "ICMS": {"019": ("01012025", "31122025", estrutura_c100("01")),
                     "020": ("01012026", "", estrutura_c100("0"))},
            "CONTRIB": {"006": ("01012020", "", estrutura_c100("01"))}}
    if tabelas is None:
        tabelas = {"SPEDFISCAL_GLOBAL$CFOP": (TABELA_CFOP, 14)}
    if guias is None:
        guias = {"ICMS": {"guia": "EFD ICMS/IPI", "versao": "9.9",
                          "registros": {}}}
    for layout, versoes in leiautes.items():
        for cod, (ini, fim, est) in versoes.items():
            _json(os.path.join(pasta, "leiaute", layout, cod + ".json"),
                  {"versao": cod, "descritor": "teste/%s/%s" % (layout, cod),
                   "dt_ini": ini, "dt_fim": fim, "estrutura": est})
    for chave, (texto, _v) in tabelas.items():
        _texto(os.path.join(pasta, "tabelas",
                            base_referencia.arquivo_da_tabela(chave)), texto)
    for layout, g in guias.items():
        _json(os.path.join(pasta, "guias", layout + ".json"), g)
    if ncm is not None:
        _texto(os.path.join(pasta, "ncm", "vigente.txt"),
               "\n".join(ncm) + "\n")
    _json(os.path.join(pasta, "manifesto.json"), {
        "esquema": esquema, "versao": versao, "data": "2026-10-15",
        "origem": {"teste": True},
        "leiautes": {l: sorted(v) for l, v in leiautes.items()},
        "tabelas": {c: v for c, (_t, v) in tabelas.items()}})
    return pasta


def compilada(pasta, **k):
    """Fontes em `pasta/fontes-<versao>`, compiladas em
    `pasta/base-<versao>.db`; devolve o caminho do banco."""
    versao = k.get("versao", "2026.10.1")
    fontes = escrever(os.path.join(pasta, "fontes-" + versao), **k)
    destino = os.path.join(pasta, "base-%s.db" % versao)
    base_referencia.compilar(fontes, destino)
    return destino

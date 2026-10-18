# -*- coding: utf-8 -*-
"""Regrava `base/` a partir de uma `InstalacaoPVA`. A revisão do que mudou
é o `git diff base/`."""

import hashlib
import json
import os

from sped_tables.dominio.sped_model import so_digitos
from sped_tables.infra import base_referencia


def _gravar_texto(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(texto.splitlines()) + "\n")


def _gravar_json(caminho, objeto, ordenar=False):
    # o leiaute NÃO é ordenado: a ordem dos campos é a posição
    _gravar_texto(caminho, json.dumps(objeto, ensure_ascii=False, indent=1,
                                      sort_keys=ordenar))


def _limpar(pasta, extensao):
    if os.path.isdir(pasta):
        for nome in os.listdir(pasta):
            if nome.endswith(extensao):
                os.remove(os.path.join(pasta, nome))


def proxima_versao(anterior, data):
    """`AAAA.MM.n`: n + 1 no mesmo mês da anterior, 1 num mês novo."""
    a = base_referencia.chave_da_versao(anterior or "")
    if len(a) == 3 and a[:2] == (data.year, data.month):
        return "%04d.%02d.%d" % (data.year, data.month, a[2] + 1)
    return "%04d.%02d.1" % (data.year, data.month)


def ler_ncm_vigente(caminho_xlsx):
    """NCM de 8 dígitos da planilha de NCM vigente do Portal Siscomex."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho_xlsx, read_only=True,
                                data_only=True)
    ncms = set()
    for row in wb.active.iter_rows(values_only=True):
        cod = row[0] if row else None
        d = so_digitos(cod if isinstance(cod, str) else str(cod or ""))
        if len(d) == 8:
            ncms.add(d)
    return ncms


def _sha_curto(caminho):
    with open(caminho, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def extrair(instalacao, destino, versao=None, ncm_xlsx=None):
    """Regrava `destino` (a pasta `base/`) com o que a instalação publica e
    devolve o manifesto. Guias ficam como estão (`py -m consolidador
    guia`); o NCM só muda com `ncm_xlsx`."""
    from consolidador.instalacao import jar_descritor
    anterior = {}
    caminho_manifesto = os.path.join(destino, "manifesto.json")
    if os.path.exists(caminho_manifesto):
        with open(caminho_manifesto, encoding="utf-8") as fh:
            anterior = json.load(fh)
    origem = {}
    for layout in base_referencia.LEIAUTES:
        pasta = os.path.join(destino, "leiaute", layout)
        _limpar(pasta, ".json")
        for cod, (ini, fim, caminho) in instalacao.versoes(layout).items():
            _gravar_json(os.path.join(pasta, cod + ".json"), {
                "versao": cod, "descritor": caminho, "dt_ini": ini,
                "dt_fim": fim,
                "estrutura": instalacao.estrutura(layout, cod)})
        jar = jar_descritor(instalacao.raiz, layout)
        origem[layout] = {"descritor": os.path.basename(jar),
                          "sha256_descritor": _sha_curto(jar)}
    tabs = instalacao.tabelas()
    pasta = os.path.join(destino, "tabelas")
    _limpar(pasta, ".txt")
    for chave, (texto, _v) in sorted(tabs.items()):
        _gravar_texto(os.path.join(
            pasta, base_referencia.arquivo_da_tabela(chave)), texto)
    if ncm_xlsx:
        _gravar_texto(os.path.join(destino, "ncm", "vigente.txt"),
                      "\n".join(sorted(ler_ncm_vigente(ncm_xlsx))))
        origem["ncm"] = os.path.basename(ncm_xlsx)
    else:
        origem["ncm"] = anterior.get("origem", {}).get("ncm")
    origem["guias"] = {l: "%s %s" % (instalacao.guia(l).get("guia", ""),
                                     instalacao.guia(l).get("versao", ""))
                       for l in base_referencia.LEIAUTES}
    origem["tabelas"] = len(tabs)
    manifesto = {
        "esquema": base_referencia.ESQUEMA,
        "versao": versao or proxima_versao(anterior.get("versao"),
                                           instalacao.data),
        "data": instalacao.data.isoformat(),
        "origem": origem,
        "leiautes": {l: sorted(instalacao.versoes(l))
                     for l in base_referencia.LEIAUTES},
        "tabelas": {c: v for c, (_t, v) in sorted(tabs.items())},
    }
    _gravar_json(caminho_manifesto, manifesto, ordenar=True)
    return manifesto

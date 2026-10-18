# -*- coding: utf-8 -*-
"""Regrava `base/` a partir de uma `InstalacaoPVA`. A revisão do que mudou
é o `git diff base/`."""

import hashlib
import json
import os

from consolidador.instalacao import ConsolidadorErro, jar_descritor
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
    try:
        ncms = set()
        for row in wb.active.iter_rows(values_only=True):
            cod = row[0] if row else None
            d = so_digitos(cod if isinstance(cod, str) else str(cod or ""))
            if len(d) == 8:
                ncms.add(d)
        return ncms
    finally:
        wb.close()      # no modo de leitura o arquivo fica aberto


def _sha_curto(caminho):
    with open(caminho, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def _levantar(instalacao, ncm_xlsx):
    """Tudo o que vai para `base/`, lido e conferido **sem tocar em disco**:
    `(leiautes, tabs, ncms, origem)`. Quem recusa (versão sem descritor,
    tabela ausente, planilha ilegível) recusa aqui, antes de a primeira
    gravação apagar o `base/` que já existia."""
    leiautes, origem = {}, {}
    for layout in base_referencia.LEIAUTES:
        versoes = instalacao.versoes(layout)
        if not versoes:
            raise ConsolidadorErro(
                "O leiaute %s ficou sem nenhuma versão na janela de "
                "retenção: a tabela de versões do PVA só traz versões "
                "antigas, e uma base sem esse leiaute não vale." % layout)
        leiautes[layout] = {
            cod: {"versao": cod, "descritor": caminho, "dt_ini": ini,
                  "dt_fim": fim, "estrutura": instalacao.estrutura(layout,
                                                                   cod)}
            for cod, (ini, fim, caminho) in versoes.items()}
        jar = jar_descritor(instalacao.raiz, layout)
        origem[layout] = {"descritor": os.path.basename(jar),
                          "sha256_descritor": _sha_curto(jar)}
    tabs = instalacao.tabelas()
    if not tabs:
        raise ConsolidadorErro(
            "Nenhuma tabela de códigos lida da instalação do PVA em %s: "
            "base sem tabelas não vale. PVA recém-instalado? Rode o "
            "Atualizar Tabelas nele e extraia de novo." % instalacao.raiz)
    ncms = None
    if ncm_xlsx:
        try:
            ncms = ler_ncm_vigente(ncm_xlsx)
        except Exception as exc:                           # noqa: BLE001
            raise ConsolidadorErro(
                "Não consegui ler a planilha de NCM %s (%s)."
                % (ncm_xlsx, str(exc) or type(exc).__name__)) from exc
        if not ncms:
            raise ConsolidadorErro(
                "A planilha de NCM %s não traz nenhum NCM de 8 dígitos "
                "na primeira coluna." % ncm_xlsx)
    return leiautes, tabs, ncms, origem


def extrair(instalacao, destino, versao=None, ncm_xlsx=None):
    """Regrava `destino` (a pasta `base/`) com o que a instalação publica e
    devolve o manifesto. Guias ficam como estão (`py -m consolidador
    guia`); o NCM só muda com `ncm_xlsx`.

    Valida tudo antes de gravar: uma extração recusada deixa o `base/` como
    estava, e não uma pasta de leiaute esvaziada com o manifesto antigo."""
    anterior = {}
    caminho_manifesto = os.path.join(destino, "manifesto.json")
    if os.path.exists(caminho_manifesto):
        with open(caminho_manifesto, encoding="utf-8") as fh:
            anterior = json.load(fh)
    leiautes, tabs, ncms, origem = _levantar(instalacao, ncm_xlsx)
    origem["ncm"] = (os.path.basename(ncm_xlsx) if ncm_xlsx
                     else anterior.get("origem", {}).get("ncm"))
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
        "leiautes": {l: sorted(v) for l, v in leiautes.items()},
        "tabelas": {c: v for c, (_t, v) in sorted(tabs.items())},
    }
    # daqui em diante só se grava
    for layout, versoes in leiautes.items():
        pasta = os.path.join(destino, "leiaute", layout)
        _limpar(pasta, ".json")
        for cod, conteudo in versoes.items():
            _gravar_json(os.path.join(pasta, cod + ".json"), conteudo)
    pasta = os.path.join(destino, "tabelas")
    _limpar(pasta, ".txt")
    for chave, (texto, _v) in sorted(tabs.items()):
        _gravar_texto(os.path.join(
            pasta, base_referencia.arquivo_da_tabela(chave)), texto)
    if ncms is not None:
        _gravar_texto(os.path.join(destino, "ncm", "vigente.txt"),
                      "\n".join(sorted(ncms)))
    _gravar_json(caminho_manifesto, manifesto, ordenar=True)
    return manifesto

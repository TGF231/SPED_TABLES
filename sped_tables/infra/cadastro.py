# -*- coding: utf-8 -*-
"""Cadastro do usuário gravado em disco: empresas e correlações de CFOP.

As regras (o que é uma `Empresa`, como se normaliza uma correlação) ficam no
domínio; aqui só se lê e grava o JSON na pasta de dados (`dados`). Até a
0.52.0 essa leitura morava dentro dos próprios módulos de regra, que por
isso dependiam do disco.

Arquivo ausente ou corrompido nunca impede o programa de abrir: vira
cadastro vazio (empresas) ou a tabela padrão (correlações). A gravação é
atômica (`dados.gravar_json`).
"""

import json
import os

from sped_tables.dominio import conferencia
from sped_tables.dominio import empresas
from sped_tables.infra import dados

ARQUIVO_EMPRESAS = "empresas.json"
ARQUIVO_CORRELACOES = "correlacoes_cfop.json"


def _ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------- empresas
def caminho_empresas(caminho=None):
    """Onde fica o cadastro. Empacotado, em %APPDATA% (ver `dados`)."""
    return caminho or dados.caminho(ARQUIVO_EMPRESAS)


def carregar_empresas(caminho=None):
    """`{cnpj: Empresa}`; vazio se o arquivo faltar ou estiver corrompido."""
    bruto = _ler_json(caminho_empresas(caminho))
    if not isinstance(bruto, dict):
        return {}
    mapa = {}
    for cnpj, registro in bruto.items():
        emp = empresas.de_registro(cnpj, registro)
        if emp is not None:
            mapa[emp.cnpj] = emp
    return mapa


def salvar_empresas(mapa, caminho=None):
    cam = caminho_empresas(caminho)
    serial = {cnpj: empresas.para_registro(mapa[cnpj])
              for cnpj in sorted(mapa)}
    dados.gravar_json(cam, serial)
    return cam


# ------------------------------------------------------ correlações CFOP
def caminho_correlacoes(caminho=None):
    return caminho or dados.caminho(ARQUIVO_CORRELACOES)


def carregar_correlacoes(caminho=None):
    """`{cfop_saida: {cfops_entrada}}`; a tabela padrão se não houver
    arquivo (ou se ele estiver corrompido)."""
    cam = caminho_correlacoes(caminho)
    bruto = _ler_json(cam) if os.path.exists(cam) else None
    # JSON válido no formato errado (uma lista, por exemplo) impedia a
    # janela principal de nascer: o programa simplesmente não abria
    if not isinstance(bruto, dict):
        bruto = conferencia.CORRELACOES_CFOP_PADRAO
    return conferencia.normalizar_correlacoes(bruto)


def salvar_correlacoes(mapa, caminho=None):
    """Grava num JSON legível (listas ordenadas)."""
    serial = {k: sorted(v) for k, v in sorted(mapa.items())}
    return dados.gravar_json(caminho_correlacoes(caminho), serial)

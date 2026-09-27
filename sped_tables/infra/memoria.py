# -*- coding: utf-8 -*-
"""Onde fica a memória de cada empresa (`dominio/memoria_itens.py`).

Um arquivo por CNPJ, na pasta de dados: `memoria/<CNPJ>.json`. Separado do
cadastro e do acervo de propósito — pode passar de milhares de produtos, e
só é lido quando a geração a partir dos XMLs precisa dele, nunca na
abertura do programa.

Ilegível, o arquivo é guardado à parte e avisado (`dados.ler_json_do_usuario`)
— a memória recomeça vazia em vez de ser sobrescrita por cima do que havia.
"""

import os

from sped_tables.dominio import memoria_itens
from sped_tables.dominio.sped_model import so_digitos
from sped_tables.infra import dados

PASTA = "memoria"


def caminho(cnpj):
    return os.path.join(dados.pasta_dados(), PASTA,
                        "%s.json" % so_digitos(cnpj))


def carregar(cnpj):
    """A memória da empresa; vazia (`memoria_itens.nova`) se não houver."""
    conteudo = dados.ler_json_do_usuario(caminho(cnpj), dict)
    if not conteudo or conteudo.get("versao") != memoria_itens.VERSAO:
        return memoria_itens.nova(cnpj)
    return conteudo


def salvar(memoria):
    cam = caminho(memoria["cnpj"])
    os.makedirs(os.path.dirname(cam), exist_ok=True)
    dados.gravar_json(cam, memoria)
    return cam


def cnpjs():
    """CNPJ das empresas que já têm memória gravada."""
    pasta = os.path.join(dados.pasta_dados(), PASTA)
    if not os.path.isdir(pasta):
        return []
    return sorted(n[:-5] for n in os.listdir(pasta)
                  if n.endswith(".json") and n[:-5].isdigit())

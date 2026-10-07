# -*- coding: utf-8 -*-
"""Ler pastas de XMLs com o trabalho repartido entre processos.

O domínio (`xml_fiscal`) sabe ler e montar o lote; aqui ele recebe o leitor
paralelo (`infra.paralelo`). Toda leitura de pasta do programa passa por
este módulo — a tela, a geração pelos XMLs e as conferências —, com
andamento (`progresso(feitos, total)`) e cancelamento (`cancelar()`, que
levanta `paralelo.Cancelado`).
"""

from sped_tables.dominio import xml_fiscal as xf
from sped_tables.infra import paralelo


def _leitor(progresso, cancelar):
    def ler(caminhos):
        return paralelo.em_lotes(xf.ler_arquivos, caminhos,
                                 progresso=progresso, cancelar=cancelar)
    return ler


def ler_pasta_fiscal(pasta, progresso=None, cancelar=None, recursivo=True):
    """`xml_fiscal.Lote` da pasta e das subpastas."""
    return xf.ler_pasta_fiscal(pasta, recursivo,
                               ler=_leitor(progresso, cancelar))


def ler_pasta(pasta, progresso=None, cancelar=None):
    """`(nfes, erros)` dos XMLs da pasta, sem subpastas."""
    return xf.ler_pasta(pasta, ler=_leitor(progresso, cancelar))

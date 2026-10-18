# -*- coding: utf-8 -*-
"""Linha de comando do consolidador.

    py -m consolidador extrair [--pva PASTA] [--data AAAA-MM-DD]
                               [--versao AAAA.MM.n] [--ncm planilha.xlsx]
        lê os PVAs desta máquina e regrava base/ (revise com git diff)
    py -m consolidador guia ICMS|CONTRIB arquivo.pdf
        extrai o guia prático para base/guias/
    py -m consolidador compilar [--saida arquivo.db]
        compila base/ (rodando do código-fonte, o programa faz isso sozinho)
    py -m consolidador publicar [--saida PASTA]
        compila e gera o pacote base_referencia-AAAA.MM.n.zip
"""

import argparse
import datetime
import os
import sys
import tempfile

from consolidador import extracao, guias
from consolidador.instalacao import ConsolidadorErro, InstalacaoPVA
from sped_tables.infra import base_referencia


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -m consolidador")
    sub = p.add_subparsers(dest="comando", required=True)
    e = sub.add_parser("extrair")
    e.add_argument("--pva")
    e.add_argument("--data", type=datetime.date.fromisoformat)
    e.add_argument("--versao")
    e.add_argument("--ncm")
    g = sub.add_parser("guia")
    g.add_argument("layout", choices=("ICMS", "CONTRIB"))
    g.add_argument("pdf")
    c = sub.add_parser("compilar")
    c.add_argument("--saida", default=base_referencia.caminho_embutido())
    u = sub.add_parser("publicar")
    u.add_argument("--saida", default="dist")
    a = p.parse_args(argv)
    fontes = base_referencia.pasta_fontes()
    try:
        if a.comando == "extrair":
            pva = InstalacaoPVA(a.pva, data=a.data, fontes=fontes)
            m = extracao.extrair(pva, fontes, versao=a.versao,
                                 ncm_xlsx=a.ncm)
            for aviso in pva.avisos:
                print("aviso:", aviso)
            print("base %s: %s; %d tabelas. Revise com: git diff base/"
                  % (m["versao"], m["leiautes"], len(m["tabelas"])))
        elif a.comando == "guia":
            print("guia gravado em", guias.gravar(a.layout, a.pdf, fontes))
        elif a.comando == "compilar":
            m = base_referencia.compilar(fontes, a.saida)
            print("base %s compilada em %s (%.1f MB)" % (
                m["versao"], a.saida, os.path.getsize(a.saida) / 1e6))
        else:
            os.makedirs(a.saida, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp:
                banco = os.path.join(tmp, base_referencia.ARQUIVO)
                m = base_referencia.compilar(fontes, banco)
                destino = os.path.join(
                    a.saida, "base_referencia-%s.zip" % m["versao"])
                base_referencia.empacotar(banco, destino)
            print("pacote:", destino)
            print("SHA-256 do banco:",
                  base_referencia.inspecionar(destino)["sha256"])
    except ConsolidadorErro as exc:
        print("erro:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Testes contra arquivos SPED reais — que **nunca** entram no repositório.

Rodam só quando a variável de ambiente aponta para a pasta com os arquivos:

    set SPED_TABLES_ARQUIVOS_REAIS=C:\\caminho\\para\\a\\pasta
    py -m unittest tests.test_reais

Sem ela, são pulados. A pasta pode ter subpastas; todo `.txt` que começa
por `|0000|` entra.

Duas camadas:

* **invariantes**, que valem para qualquer arquivo: carregar e gravar não
  perde registro, recalcular é idempotente, nenhuma verificação levanta
  exceção;
* **gabarito**, opcional: um `gabarito.json` na mesma pasta com os números
  exatos esperados por arquivo (quantos achados por regra de revisão e por
  tipo de diagnóstico). É o "validar contra arquivos reais com números
  exatos" do CLAUDE.md, sem pôr dado de cliente no git. Para gerar a partir
  do estado atual (depois de conferir os números à mão):

    py -m tests.test_reais gerar
"""

import json
import os
import sys
import unittest

import diagnostico
import revisao
import validacao
from sped_model import SpedDocument
from tests.fabrica import PastaTemporaria

VARIAVEL = "SPED_TABLES_ARQUIVOS_REAIS"
PASTA = os.environ.get(VARIAVEL, "")
GABARITO = "gabarito.json"


def arquivos_reais(pasta=PASTA):
    if not pasta or not os.path.isdir(pasta):
        return []
    achados = []
    for raiz, _d, nomes in os.walk(pasta):
        for nome in sorted(nomes):
            if not nome.lower().endswith(".txt"):
                continue
            caminho = os.path.join(raiz, nome)
            try:
                with open(caminho, "rb") as fh:
                    if fh.read(6) == b"|0000|":
                        achados.append(caminho)
            except OSError:
                pass
    return achados


def numeros(doc):
    """O que o gabarito guarda de cada arquivo."""
    rev = {rotulo: len(ps) for rotulo, ps in revisao.revisar_por_regra(doc)}
    achados, _info = diagnostico.verificar(doc)
    diag = {}
    for a in achados:
        diag[a.tipo] = diag.get(a.tipo, 0) + a.quantidade
    return {"layout": doc.layout, "registros": len(doc.registros),
            "revisao": rev, "diagnostico": diag}


def _chave(caminho, pasta=PASTA):
    return os.path.relpath(caminho, pasta).replace("\\", "/")


@unittest.skipUnless(arquivos_reais(), "defina %s para rodar" % VARIAVEL)
class TestArquivosReais(unittest.TestCase):

    def test_gravar_nao_perde_registro_e_estabiliza(self):
        for caminho in arquivos_reais():
            with self.subTest(arquivo=_chave(caminho)), \
                    PastaTemporaria() as p:
                doc = SpedDocument.carregar(caminho)
                fora_do_9 = sum(1 for r in doc.registros if r.bloco != "9")
                copia = os.path.join(p, "copia.txt")
                doc.salvar(copia)
                relido = SpedDocument.carregar(copia)
                self.assertEqual(
                    sum(1 for r in relido.registros if r.bloco != "9"),
                    fora_do_9)
                self.assertEqual(relido.gerar_texto(), doc.gerar_texto())

    def test_recalculo_do_bloco_m_e_idempotente(self):
        for caminho in arquivos_reais():
            doc = SpedDocument.carregar(caminho)
            if doc.layout != "CONTRIB":
                continue
            with self.subTest(arquivo=_chave(caminho)):
                doc.recalcular_bloco_m()
                uma = doc.gerar_texto()
                doc.recalcular_bloco_m()
                self.assertEqual(doc.gerar_texto(), uma)

    def test_verificacoes_nao_levantam_excecao(self):
        for caminho in arquivos_reais():
            with self.subTest(arquivo=_chave(caminho)):
                doc = SpedDocument.carregar(caminho)
                revisao.revisar_por_regra(doc)
                validacao.validar(doc)
                diagnostico.verificar(doc)

    def test_gabarito(self):
        cam = os.path.join(PASTA, GABARITO)
        if not os.path.isfile(cam):
            self.skipTest("sem %s na pasta" % GABARITO)
        with open(cam, encoding="utf-8") as fh:
            esperado = json.load(fh)
        for caminho in arquivos_reais():
            chave = _chave(caminho)
            if chave not in esperado:
                continue
            with self.subTest(arquivo=chave):
                obtido = numeros(SpedDocument.carregar(caminho))
                self.assertEqual(obtido, esperado[chave])


def gerar_gabarito(pasta=PASTA):
    saida = {_chave(c, pasta): numeros(SpedDocument.carregar(c))
             for c in arquivos_reais(pasta)}
    cam = os.path.join(pasta, GABARITO)
    with open(cam, "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return cam, len(saida)


if __name__ == "__main__":
    if sys.argv[1:] == ["gerar"]:
        if not arquivos_reais():
            sys.exit("defina %s com a pasta dos arquivos" % VARIAVEL)
        print("gravado: %s (%d arquivos)" % gerar_gabarito())
    else:
        unittest.main()

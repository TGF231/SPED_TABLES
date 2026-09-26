# -*- coding: utf-8 -*-
"""Memória persistente de arquivos (cópia por período + índice)."""

import os
import unittest

from sped_tables.infra import arquivos
from sped_tables.infra import dados
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import CNPJ_TESTE, PastaTemporaria, icms_basico, ler


class TestArquivar(unittest.TestCase):

    def setUp(self):
        # cada teste com a sua pasta de dados
        self._pasta = PastaTemporaria()
        self._anterior = os.environ.get("SPED_TABLES_DADOS")
        os.environ["SPED_TABLES_DADOS"] = self._pasta.__enter__()

    def tearDown(self):
        os.environ["SPED_TABLES_DADOS"] = self._anterior or ""
        self._pasta.__exit__(None, None, None)

    def test_pasta_de_dados_vem_do_ambiente(self):
        self.assertEqual(dados.pasta_dados(),
                         os.path.abspath(os.environ["SPED_TABLES_DADOS"]))

    def test_copia_por_periodo_e_indice(self):
        with PastaTemporaria() as p:
            origem = icms_basico().gravar(p)
            doc = SpedDocument.carregar(origem)
            e = arquivos.arquivar(doc, origem)
            self.assertEqual((e["cnpj"], e["layout"], e["periodo"]),
                             (CNPJ_TESTE, "ICMS", "202608"))
            copia = arquivos.caminho_copia(CNPJ_TESTE, "ICMS", "202608")
            self.assertEqual(ler(copia), ler(origem))
            # arquivar de novo o mesmo período substitui, não duplica
            arquivos.arquivar(doc, origem, motivo="salvamento")
        hist = arquivos.historico(CNPJ_TESTE)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["motivo"], "salvamento")

    def test_abrir_do_historico_nao_trunca(self):
        with PastaTemporaria() as p:
            origem = icms_basico().gravar(p)
            doc = SpedDocument.carregar(origem)
            arquivos.arquivar(doc, origem)
        copia = arquivos.caminho_copia(CNPJ_TESTE, "ICMS", "202608")
        conteudo = ler(copia)
        arquivos.arquivar(SpedDocument.carregar(copia), copia)
        self.assertEqual(ler(copia), conteudo)

    def test_indice_corrompido_vira_vazio(self):
        os.makedirs(os.path.dirname(arquivos._caminho_indice()),
                    exist_ok=True)
        with open(arquivos._caminho_indice(), "w", encoding="utf-8") as fh:
            fh.write("[{quebrado")
        self.assertEqual(arquivos.carregar_indice(), [])

    def test_remover(self):
        with PastaTemporaria() as p:
            origem = icms_basico().gravar(p)
            arquivos.arquivar(SpedDocument.carregar(origem), origem)
        self.assertEqual(arquivos.remover(CNPJ_TESTE, "ICMS", "202608"), 1)
        self.assertEqual(arquivos.historico(), [])
        self.assertFalse(os.path.exists(
            arquivos.caminho_copia(CNPJ_TESTE, "ICMS", "202608")))


if __name__ == "__main__":
    unittest.main()

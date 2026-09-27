# -*- coding: utf-8 -*-
"""Memória de itens por empresa: aprender com o SPED entregue e os XMLs,
responder o que sabe e **não** inventar o que não sabe."""

import os
import unittest

from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import CNPJ_TESTE, PastaTemporaria, icms_basico, nfe_xml

FORNECEDOR = "11444777000161"


def _lote(pasta, itens):
    with open(os.path.join(pasta, "n.xml"), "w", encoding="utf-8") as fh:
        fh.write(nfe_xml(itens=itens))
    return xf.ler_pasta_fiscal(pasta)


class TestMemoria(unittest.TestCase):

    def setUp(self):
        self._p = PastaTemporaria()
        p = self._p.__enter__()
        # o SPED escritura P1..P3 (código próprio); o XML traz F1..F3 (do
        # fornecedor), com CFOP 5102 e CST 000
        self.doc = SpedDocument.carregar(icms_basico().gravar(p))
        pasta_xml = os.path.join(p, "xml")
        os.makedirs(pasta_xml)
        self.lote = _lote(pasta_xml, [
            {"cProd": "F1"}, {"cProd": "F2"}, {"cProd": "F3"}])
        self.m = mi.nova(CNPJ_TESTE)
        self.res = mi.aprender(self.m, self.lote, doc_icms=self.doc)

    def tearDown(self):
        self._p.__exit__(None, None, None)

    def test_aprende_pelo_numero_do_item(self):
        self.assertEqual(self.res["itens_casados"], 3)
        self.assertEqual(mi.codigo_proprio(self.m, FORNECEDOR, "F2"),
                         ("P2", False))
        item = self.lote.nfes[0].itens[1]
        e = mi.escrituracao(self.m, FORNECEDOR, "F2", item)
        self.assertEqual((e["CFOP"], e["CST_ICMS"], e["CREDITA_ICMS"]),
                         ("1102", "000", "S"))

    def test_nao_sabe_nao_inventa(self):
        self.assertEqual(mi.codigo_proprio(self.m, FORNECEDOR, "XX"),
                         (None, False))
        # mesmo produto noutra situação (outro CFOP de origem): outra
        # operação, sem resposta
        item = self.lote.nfes[0].itens[0]
        item.cfop = "5910"
        self.assertIsNone(mi.escrituracao(self.m, FORNECEDOR, "F1", item))

    def test_cadastro_participantes_e_periodo(self):
        self.assertIn("P1", self.m["cadastro"])
        self.assertEqual(self.m["cadastro"]["P1"]["UNID_INV"], "UN")
        self.assertEqual(mi.cod_participante(self.m, FORNECEDOR), "F1")
        self.assertEqual(self.m["periodos"], ["202608"])

    def test_codigo_ambiguo_e_apontado(self):
        # outro mês em que F1 foi escriturado como P9
        self.m["produtos"][mi.chave_produto(FORNECEDOR, "F1")][
            "codigos"]["P9"] = 1
        self.assertEqual(mi.codigo_proprio(self.m, FORNECEDOR, "F1"),
                         ("P1", True))

    def test_codigo_de_participante_novo(self):
        self.m["participantes"] = {"1": "1", "2": "7", "3": "F1"}
        self.assertEqual(mi.proximo_cod_participante(self.m), "8")

    def test_grava_e_le_na_pasta_de_dados(self):
        from sped_tables.infra import memoria
        with PastaTemporaria() as p:
            antes = os.environ.get("SPED_TABLES_DADOS")
            os.environ["SPED_TABLES_DADOS"] = p
            try:
                cam = memoria.salvar(self.m)
                self.assertTrue(cam.endswith(CNPJ_TESTE + ".json"))
                self.assertEqual(memoria.carregar(CNPJ_TESTE), self.m)
                self.assertEqual(memoria.carregar("99999999000199")
                                 ["produtos"], {})
            finally:
                os.environ["SPED_TABLES_DADOS"] = antes


if __name__ == "__main__":
    unittest.main()

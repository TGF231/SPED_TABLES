# -*- coding: utf-8 -*-
"""Regenerar as entradas do arquivo pelos XMLs (`dominio/regeneracao.py`):
a escrituração vem do próprio arquivo, os valores do XML; nota sem XML
fica, nota nova entra, e item que sairia inválido barra só a sua nota."""

import os
import unittest

from sped_tables.dominio import regeneracao
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import (PastaTemporaria, contrib_basico, icms_basico,
                           nfe_xml)

CHAVE_1 = "31260811444777000161550010000001231000001238"
CHAVE_2 = "31260811444777000161550010000001241000001240"
CHAVE_3 = "31260899888777000166550010000009991000009990"


def _lote(*xmls):
    with PastaTemporaria() as p:
        for n, x in enumerate(xmls):
            with open(os.path.join(p, "%d.xml" % n), "w",
                      encoding="utf-8") as fh:
                fh.write(x)
        return xf.ler_pasta_fiscal(p)


def _linhas(doc, reg):
    return [l for l in doc.gerar_texto().splitlines()
            if l.startswith("|%s|" % reg)]


class TestRegenerarIcms(unittest.TestCase):

    def setUp(self):
        self.doc = SpedDocument.de_texto(icms_basico().texto())

    def test_troca_inclui_e_recalcula(self):
        lote = _lote(
            nfe_xml(itens=[{}, {"vProd": "12.00", "vBC": "12.00",
                                "vICMS": "2.16"}, {}]),
            nfe_xml(nnf="124", chave=CHAVE_2, itens=[{"cProd": "P9"}]))
        plano = regeneracao.planejar(self.doc, lote)
        self.assertEqual((len(plano.substituir), len(plano.incluir),
                          len(plano.sem_xml)), (1, 1, 0))
        # só o que mudou de verdade: "0" e "0,00" são o mesmo valor
        self.assertEqual(plano.mudancas["C170.VL_ITEM"], 1)
        self.assertNotIn("C170.VL_DESC", plano.mudancas)
        self.assertEqual([r.reg for r in plano.cadastro], ["0200"])
        self.assertTrue(any(a["tipo"] == "produto sem código próprio"
                            for a in plano.revisar))
        res = regeneracao.aplicar(self.doc, plano)
        self.assertEqual(res, {"substituidos": 1, "incluidos": 1,
                               "cadastro": 1})
        c100 = _linhas(self.doc, "C100")
        self.assertEqual(len(c100), 2)
        self.assertIn("|32,00|", c100[0])                 # VL_DOC
        c170 = _linhas(self.doc, "C170")
        self.assertIn("|2|P2||1|UN|12,00|", c170[1])
        # a escrituração veio do arquivo: CFOP 1102 e CST 000, não 5102
        self.assertTrue(all("|000|1102|" in l for l in c170))
        c190 = _linhas(self.doc, "C190")
        self.assertIn("|000|1102|18,00|32,00|32,00|5,76|", c190[0])
        self.assertIn("|9900|C100|2|", self.doc.gerar_texto())
        self.assertEqual(len(_linhas(self.doc, "0200")), 4)

    def test_nota_sem_xml_fica_e_item_invalido_barra_a_nota(self):
        # nota de outro fornecedor, CFOP e CST nunca vistos, sem correlação
        nova = nfe_xml(nnf="999", chave=CHAVE_3, cfop="6403",
                       emit=("99888777000166", "OUTRO"),
                       itens=[{"cProd": "X1", "CST": "60"}])
        plano = regeneracao.planejar(self.doc, _lote(nova))
        self.assertEqual(len(plano.sem_xml), 1)           # a do arquivo
        self.assertEqual(plano.incluir, [])
        (onde, motivos), = plano.bloqueados
        self.assertEqual(onde, "NF 1/999")
        self.assertIn("CFOP de entrada desconhecido", motivos[0])
        self.assertTrue(plano.vazio)
        antes = self.doc.gerar_texto()
        regeneracao.aplicar(self.doc, plano)
        self.assertEqual(self.doc.gerar_texto(), antes)

    def test_arquivo_igual_ao_xml_nao_muda_valores(self):
        plano = regeneracao.planejar(self.doc, _lote(nfe_xml()))
        self.assertEqual(len(plano.substituir), 1)
        self.assertEqual({k: v for k, v in plano.mudancas.items()
                          if k.startswith("C170")}, {})


class TestRegenerarContrib(unittest.TestCase):

    def test_pis_cofins_pela_escrituracao_do_arquivo(self):
        m = contrib_basico().alterar("C100", 0, NUM_DOC="123",
                                     CHV_NFE=CHAVE_1)
        doc = SpedDocument.de_texto(m.texto())
        xml = nfe_xml(itens=[{"cProd": "P1", "vProd": "120.00",
                              "vBC": "120.00", "vICMS": "21.60",
                              "CFOP": "5102"}])
        plano = regeneracao.planejar(doc, _lote(xml))
        self.assertEqual(len(plano.substituir), 1)
        regeneracao.aplicar(doc, plano)
        (c170,) = [l for l in _linhas(doc, "C170") if "|1102|" in l]
        campos = c170.split("|")
        i = {n: doc._ix("C170", n) + 1 for n in (
            "VL_ITEM", "CST_PIS", "ALIQ_PIS", "VL_BC_PIS", "VL_PIS")}
        self.assertEqual(campos[i["VL_ITEM"]], "120,00")
        self.assertEqual(campos[i["CST_PIS"]], "50")
        self.assertEqual(campos[i["ALIQ_PIS"]], "1,65")
        # base sem o ICMS (como o gerador faz): 120 - 21,60
        self.assertEqual(campos[i["VL_BC_PIS"]], "98,40")
        # a saída não é tocada
        self.assertTrue(any("|5102|" in l for l in _linhas(doc, "C170")))


if __name__ == "__main__":
    unittest.main()

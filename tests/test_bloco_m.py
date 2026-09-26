# -*- coding: utf-8 -*-
"""Apuração e crédito do bloco M (EFD Contribuições)."""

import unittest

from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico

# o pedaço da tabela 4.3.7 do PVA que os arquivos de teste usam
NATUREZAS = {"1102": "01"}


def _doc(**kw):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(contrib_basico(**kw).gravar(p))


def _linhas(doc, prefixo):
    return [l for l in doc.gerar_texto().splitlines()
            if l.startswith("|" + prefixo)]


class TestApuracao(unittest.TestCase):

    def test_debito_sai_das_saidas(self):
        doc = _doc()
        r = doc.recalcular_bloco_m(naturezas=NATUREZAS)
        self.assertEqual(r["PIS"]["apurado"], 4.95)
        self.assertEqual(r["COFINS"]["apurado"], 22.80)
        (m210,) = _linhas(doc, "M210|")
        self.assertTrue(m210.startswith("|M210|01|300,00|300,00|"))

    def test_ordem_do_leiaute(self):
        doc = _doc()
        doc.recalcular_bloco_m(naturezas=NATUREZAS)
        tipos = [l.split("|")[1] for l in _linhas(doc, "M")]
        self.assertEqual(tipos, ["M001", "M100", "M105", "M200", "M210",
                                 "M500", "M505", "M600", "M610", "M990"])

    def test_recalculo_e_idempotente(self):
        doc = _doc()
        doc.recalcular_bloco_m(naturezas=NATUREZAS)
        antes = doc.gerar_texto()
        doc.recalcular_bloco_m(naturezas=NATUREZAS)
        self.assertEqual(doc.gerar_texto(), antes)

    def test_conferencia_concorda_com_a_geracao(self):
        doc = _doc()
        doc.recalcular_bloco_m(naturezas=NATUREZAS)
        conf = doc.conferir_apuracao_m()
        for tributo in ("PIS", "COFINS"):
            self.assertFalse(conf[tributo]["difere_rec"])
            self.assertFalse(conf[tributo]["difere_bc"])
        self.assertEqual(doc.conferir_creditos_m(), [])


class TestCredito(unittest.TestCase):

    def test_credito_refeito_das_entradas(self):
        doc = _doc()
        r = doc.recalcular_bloco_m(naturezas=NATUREZAS)
        self.assertEqual(r["creditos"]["PIS"]["descontado"], 1.65)
        self.assertEqual(r["PIS"]["a_recolher"], 3.30)
        (m100,) = _linhas(doc, "M100|")
        # COD_CRED = tipo (1 = alíquota básica) + vinculação (01)
        self.assertTrue(m100.startswith("|M100|101|0|100,00|1,65|"))
        (m105,) = _linhas(doc, "M105|")
        self.assertTrue(m105.startswith("|M105|01|50|100,00|"))

    def test_sem_refazer_mantem_o_credito(self):
        doc = _doc()
        r = doc.recalcular_bloco_m(refazer_creditos=False,
                                   naturezas=NATUREZAS)
        self.assertNotIn("creditos", r)
        (m100,) = _linhas(doc, "M100|")
        self.assertIn("|90,00|", m100)

    def test_cumulativo_nao_gera_credito(self):
        doc = _doc(cod_inc_trib="2")
        r = doc.recalcular_bloco_m(naturezas=NATUREZAS)
        self.assertNotIn("creditos", r)
        self.assertEqual(r["regime"], "cumulativo")
        (m200,) = _linhas(doc, "M200|")
        # contribuição nos campos cumulativos, nada no não-cumulativo
        campos = m200.split("|")
        self.assertEqual(campos[2], "0")
        self.assertEqual(campos[9], "4,95")


if __name__ == "__main__":
    unittest.main()

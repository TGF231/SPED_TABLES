# -*- coding: utf-8 -*-
"""Diagnóstico ao abrir e a pré-checagem antes de mandar ao PVA."""

import unittest

import diagnostico
from sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


class TestImpedemImportacao(unittest.TestCase):

    def test_obrigatorio_nao_impede(self):
        A = diagnostico.Achado
        achados = [A("obrigatorio", "C100", "COD_PART", "", 25),
                   A("formato", "0200", "COD_NCM", "", 3),
                   A("nulo", "0200", "CEST", "", 7),
                   A("formato", "C170", "VL_ITEM", "", 2)]
        self.assertEqual(diagnostico.impedem_importacao(achados),
                         [("nulo", 7), ("formato", 5)])

    def test_todo_achado_tem_modulo_ou_cai_na_grade(self):
        grupos = diagnostico.resumo_por_modulo(
            [diagnostico.Achado("tipo_inventado", "X", "", "", 1)])
        self.assertEqual(grupos[0][0], "Correção manual na grade")


class TestVerificar(unittest.TestCase):
    """Roda com ou sem o PVA instalado; o que muda é a fonte dos domínios."""

    def test_roda_nos_dois_leiautes(self):
        for m in (icms_basico(), contrib_basico()):
            with self.subTest(layout=m.layout):
                achados, info = diagnostico.verificar(_doc(m))
                self.assertIsInstance(achados, list)
                self.assertIn("sem_pva", info)

    def test_null_aparece_como_nulo(self):
        m = icms_basico()
        linha = next(c for c in m.linhas if c[0] == "0200")
        linha[m.tabela["0200"].index("CEST")] = "NULL"
        achados, _info = diagnostico.verificar(_doc(m))
        self.assertIn("nulo", {a.tipo for a in achados})
        self.assertIn("nulo", dict(diagnostico.impedem_importacao(achados)))


if __name__ == "__main__":
    unittest.main()

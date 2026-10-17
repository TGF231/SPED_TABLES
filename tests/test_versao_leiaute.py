# -*- coding: utf-8 -*-
"""A versão do leiaute é a do arquivo: quem tem o documento pede à porta a
estrutura do COD_VER dele, nunca "a mais recente"."""

import unittest

from sped_tables.dominio import diagnostico, geracao, referencias, validacao
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico


class FonteQueAnota(referencias.Referencias):
    """Anota cada versão pedida e responde "fora da base"."""

    def __init__(self):
        self.pedidas = []

    def estrutura(self, layout, versao=None):
        self.pedidas.append((layout, versao))
        return {}, {"descritor": None, "versao": versao,
                    "fora_da_base": True, "erro": "fora da base"}

    def versao_vigente(self, layout, data):
        return "020" if data.endswith("2026") else None


def _doc(m):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(m.gravar(p))


class TestVersaoDoArquivo(unittest.TestCase):

    def setUp(self):
        self.fonte = FonteQueAnota()
        self._antes = referencias.definir(self.fonte)

    def tearDown(self):
        referencias.definir(self._antes)

    def test_versao_do_leiaute(self):
        self.assertEqual(referencias.versao_do_leiaute(_doc(icms_basico())),
                         "020")
        self.assertEqual(
            referencias.versao_do_leiaute(_doc(contrib_basico())), "006")
        for ruim in ("", "19", "abc"):
            m = icms_basico()
            m.alterar("0000", COD_VER=ruim)
            self.assertIsNone(referencias.versao_do_leiaute(_doc(m)), ruim)

    def test_documento_sem_0000_nao_tem_versao(self):
        doc = _doc(icms_basico())
        doc.registros = [r for r in doc.registros if r.reg != "0000"]
        self.assertIsNone(referencias.versao_do_leiaute(doc))

    def test_diagnostico_pede_a_versao_do_arquivo(self):
        _achados, info = diagnostico.verificar(_doc(icms_basico()))
        self.assertTrue(self.fonte.pedidas)
        self.assertEqual({v for _l, v in self.fonte.pedidas}, {"020"})
        self.assertEqual(info["fora_da_base"], "020")
        self.assertTrue(info["sem_base"])

    def test_validacao_pede_a_versao_do_arquivo(self):
        validacao.dominios_do_documento(_doc(contrib_basico()))
        self.assertEqual(self.fonte.pedidas, [("CONTRIB", "006")])

    def test_cod_ver_ruim_pede_a_mais_recente(self):
        m = icms_basico()
        m.alterar("0000", COD_VER="19")
        validacao.dominios_do_documento(_doc(m))
        self.assertEqual(self.fonte.pedidas, [("ICMS", None)])

    def test_geracao_pede_a_versao_do_periodo(self):
        geracao._larguras({}, "ICMS", "31082026")
        self.assertEqual(self.fonte.pedidas, [("ICMS", "020")])


if __name__ == "__main__":
    unittest.main()

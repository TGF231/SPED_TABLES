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

    def test_diagnostico_repassa_que_o_arquivo_e_mais_novo_que_a_base(self):
        """O que a porta diz sobre a versão (mais nova que a base, e qual
        é a base) chega ao `info` do Diagnóstico — é dele que a tela tira o
        remédio. Sem a chave, o `info` diz `False`/`None`, nunca falta."""
        class Nova(FonteQueAnota):
            def estrutura(self, layout, versao=None):
                return {}, {"descritor": None, "versao": versao,
                            "fora_da_base": True, "base": "2026.10.1",
                            "mais_nova_que_a_base": True}
        referencias.definir(Nova())
        _achados, info = diagnostico.verificar(_doc(icms_basico()))
        self.assertEqual(info["fora_da_base"], "020")
        self.assertTrue(info["mais_nova_que_a_base"])
        self.assertEqual(info["base"], "2026.10.1")
        referencias.definir(self.fonte)
        _achados, info = diagnostico.verificar(_doc(icms_basico()))
        self.assertFalse(info["mais_nova_que_a_base"])
        self.assertIsNone(info["base"])

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


class TestVersaoPelaBaseEntregue(unittest.TestCase):
    """O arquivo é conferido pelo leiaute do próprio COD_VER **na base
    entregue com o programa** (não numa base inventada): a 019 e a 020 do
    ICMS/IPI diferem de verdade, e a mesma linha é acusada numa e não na
    outra. Nas duas, o `COD_VER` do 0000 é o único que muda no arquivo."""

    @classmethod
    def setUpClass(cls):
        from sped_tables.aplicacao import montagem
        cls._antes = referencias.atual()
        montagem.configurar()

    @classmethod
    def tearDownClass(cls):
        referencias.definir(cls._antes)

    def _achados(self, cod_ver, montar):
        m = icms_basico()
        m.alterar("0000", COD_VER=cod_ver)
        montar(m)
        achados, info = diagnostico.verificar(_doc(m))
        self.assertEqual(info["versao"], cod_ver)
        self.assertFalse(info["sem_base"])
        return achados

    def test_c120_duimp_so_vale_na_020(self):
        """`C120.COD_DOC_IMP` aceita 0 e 1 na 019 e 0, 1 e 2 na 020 (a
        DUIMP): o mesmo `2` é fora do domínio num arquivo 019 e válido num
        020."""
        def montar(m):
            m.reg("C120", COD_DOC_IMP="2", NUM_DOC_IMP="123456")
        antigo = [a for a in self._achados("019", montar)
                  if (a.reg, a.campo) == ("C120", "COD_DOC_IMP")]
        novo = [a for a in self._achados("020", montar)
                if (a.reg, a.campo) == ("C120", "COD_DOC_IMP")]
        self.assertEqual([a.tipo for a in antigo], ["dominio"])
        self.assertEqual(novo, [])

    def test_1310_tem_dez_campos_na_019_e_onze_na_020(self):
        """O `1310` ganhou o `CAP_TANQUE` na 020: a linha de 11 campos tem um
        a mais que o leiaute na 019 e está certa na 020."""
        def montar(m):
            m.reg("1300", COD_ITEM="P1", DT_FECH="31082026",
                  ESTQ_ABERT="0", VOL_ENTR="0", VOL_DISP="0",
                  VOL_SAIDAS="0", ESTQ_ESCR="0", VAL_AJ_PERDA="0",
                  VAL_AJ_GANHO="0", FECH_FISICO="0")
            m.reg("1310", NUM_TANQUE="1", ESTQ_ABERT="0", VOL_ENTR="0",
                  VOL_DISP="0", VOL_SAIDAS="0", ESTQ_ESCR="0",
                  VAL_AJ_PERDA="0", VAL_AJ_GANHO="0", FECH_FISICO="0",
                  CAP_TANQUE="1000")
        antigo = [a for a in self._achados("019", montar)
                  if a.tipo == "num_campos" and a.reg == "1310"]
        novo = [a for a in self._achados("020", montar)
                if a.tipo == "num_campos" and a.reg == "1310"]
        self.assertEqual(len(antigo), 1)
        self.assertEqual(novo, [])


if __name__ == "__main__":
    unittest.main()

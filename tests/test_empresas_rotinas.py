# -*- coding: utf-8 -*-
"""Cadastro de empresas e as rotinas de conferência por regime."""

import os
import unittest

from sped_tables.infra import cadastro
from sped_tables.dominio import empresas as emp_mod
from sped_tables.dominio import rotinas
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import CNPJ_TESTE, PastaTemporaria, contrib_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


class TestAliquotaDoCadastro(unittest.TestCase):
    """O cadastro é texto livre e acaba gravado no arquivo fiscal."""

    def test_normaliza_para_o_formato_do_sped(self):
        for entrada, saida in (("1.65", "1,65"), ("7.6", "7,6"), ("3", "3"),
                               ("3,00", "3"), ("0,65", "0,65"), ("", ""),
                               ("abc", "abc")):
            with self.subTest(entrada=entrada):
                self.assertEqual(emp_mod.normalizar_aliquota(entrada), saida)

    def test_empresa_nasce_normalizada(self):
        e = emp_mod.Empresa(cnpj=CNPJ_TESTE, aliq_pis_saida="1.65",
                            aliq_cofins_saida="7.60")
        self.assertEqual((e.aliq_pis_saida, e.aliq_cofins_saida),
                         ("1,65", "7,6"))

    def test_salvar_e_carregar(self):
        with PastaTemporaria() as p:
            cam = os.path.join(p, "empresas.json")
            e = emp_mod.Empresa(cnpj=CNPJ_TESTE, nome="TESTE",
                                regime_pis_cofins="nao_cumulativo")
            cadastro.salvar_empresas({CNPJ_TESTE: e}, cam)
            lido = cadastro.carregar_empresas(cam)
        self.assertEqual(lido[CNPJ_TESTE].nome, "TESTE")
        self.assertTrue(lido[CNPJ_TESTE].nao_cumulativo)

    def test_cadastro_corrompido_vira_vazio(self):
        with PastaTemporaria() as p:
            cam = os.path.join(p, "empresas.json")
            with open(cam, "w", encoding="utf-8") as fh:
                fh.write("{isto não é json")
            self.assertEqual(cadastro.carregar_empresas(cam), {})

    def test_correlacoes_no_formato_errado_viram_a_padrao(self):
        """JSON válido mas no formato errado derrubava a janela principal
        na criação — o programa não abria (achado no autoteste do pacote)."""
        from sped_tables.dominio import conferencia
        padrao = conferencia.normalizar_correlacoes(
            conferencia.CORRELACOES_CFOP_PADRAO)
        with PastaTemporaria() as p:
            cam = os.path.join(p, "correlacoes_cfop.json")
            for conteudo in ('[{"saida": "5102"}]', '"5102"', "{isto não"):
                with open(cam, "w", encoding="utf-8") as fh:
                    fh.write(conteudo)
                self.assertEqual(cadastro.carregar_correlacoes(cam), padrao)
            # valor que não é lista de CFOP é ignorado, o resto vale
            with open(cam, "w", encoding="utf-8") as fh:
                fh.write('{"5102": ["1102"], "5405": 7}')
            self.assertEqual(cadastro.carregar_correlacoes(cam),
                             {"5102": {"1102"}})


class TestRotinas(unittest.TestCase):

    def _empresa(self, regime):
        return emp_mod.Empresa(cnpj=CNPJ_TESTE,
                               regime_pis_cofins=regime) \
            .aplicar_aliquotas_do_regime()

    def test_cumulativo_nao_toma_credito(self):
        doc = _doc(contrib_basico("2"))
        emp = self._empresa("cumulativo")
        oc = rotinas.verificar_credito_indevido(doc, emp)
        self.assertEqual({o.tributo for o in oc}, {"PIS", "COFINS"})
        rotinas.corrigir_credito_indevido(doc, emp, oc)
        self.assertEqual(rotinas.verificar_credito_indevido(doc, emp), [])
        c170 = next(r for r in doc.registros if r.reg == "C170")
        self.assertEqual(c170.valor(doc._ix("C170", "CST_PIS")), "70")
        self.assertEqual(c170.valor(doc._ix("C170", "VL_PIS")), "0,00")

    def test_aliquota_de_saida_do_regime(self):
        doc = _doc(contrib_basico("2"))
        emp = self._empresa("cumulativo")
        oc = rotinas.verificar_aliquota_saida(doc, emp)
        self.assertEqual(sorted(o.esperado for o in oc), ["0,65", "3"])
        rotinas.corrigir_aliquota(doc, emp, oc)
        saida = [r for r in doc.registros if r.reg == "C170"][1]
        self.assertEqual(saida.valor(doc._ix("C170", "ALIQ_PIS")), "0,65")
        self.assertEqual(saida.valor(doc._ix("C170", "VL_PIS")), "1,95")

    def test_regime_ambos_se_abstem(self):
        doc = _doc(contrib_basico("3"))
        self.assertEqual(
            rotinas.verificar_aliquota_saida(doc, self._empresa("ambos")), [])

    def test_executar_nao_propaga_excecao(self):
        def quebrada(doc, empresa):
            raise TypeError("defeito dentro da verificação")
        rot = rotinas.Rotina(id="x", nome="x", descricao="", layouts=(),
                             verificar=quebrada)
        achados, erro = rotinas.executar(_doc(contrib_basico()), None, rot,
                                         classificador=object())
        self.assertEqual(achados, [])
        self.assertIn("defeito", erro)


if __name__ == "__main__":
    unittest.main()

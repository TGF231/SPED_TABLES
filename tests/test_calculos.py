# -*- coding: utf-8 -*-
"""Cálculos fiscais que já regrediram uma vez — ver "Regras fiscais já
implementadas (não regredir)" no CLAUDE.md."""

import unittest

from sped_tables.dominio.sped_model import (SpedDocument, _fmt_aliq, _fmt_qtd, _fmt_val,
                        _gtin_corrigido, _texto_planilha, _to_num,
                        _zero_a_esquerda)
from tests.fabrica import PastaTemporaria, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


class TestFormatos(unittest.TestCase):

    def test_numero_sped(self):
        self.assertEqual(_to_num("1.234,56"), 1234.56)
        self.assertEqual(_to_num(""), 0.0)
        self.assertEqual(_to_num("abc"), 0.0)
        self.assertEqual(_fmt_val(1234.5), "1234,50")
        self.assertEqual(_fmt_val(0.005), "0,01")

    def test_aliquota_sem_zeros_a_direita(self):
        self.assertEqual(_fmt_aliq(1.65), "1,65")
        self.assertEqual(_fmt_aliq(7.6), "7,6")
        self.assertEqual(_fmt_aliq(3.0), "3")
        self.assertEqual(_fmt_aliq(0), "0")

    def test_quantidade(self):
        self.assertEqual(_fmt_qtd(155.7), "155,7")
        self.assertEqual(_fmt_qtd("x"), "")


class TestPlanilha(unittest.TestCase):
    """A célula numérica do Excel come o zero à esquerda."""

    def test_repoe_um_zero_so(self):
        self.assertEqual(_zero_a_esquerda("4012010", 8), "04012010")
        self.assertEqual(_zero_a_esquerda("200420", 7), "0200420")
        # faltando dois dígitos já é dado ruim: não inventa
        self.assertEqual(_zero_a_esquerda("401201", 8), "401201")

    def test_gtin_so_com_digito_verificador(self):
        self.assertEqual(_gtin_corrigido("7891234567895"), "7891234567895")
        # 11 dígitos que, com o zero, formam um GTIN-12 válido
        self.assertEqual(_gtin_corrigido("36000291452"), "036000291452")
        # 11 dígitos cujo zero não fecha o dígito verificador: intocado
        self.assertEqual(_gtin_corrigido("36000291453"), "36000291453")

    def test_nulo_do_erp_vira_vazio(self):
        for nulo in ("NULL", "null", "(NULL)", "#N/A", None):
            self.assertEqual(_texto_planilha(nulo), "")
        # `-` e `N/A` podem ser descrição legítima
        self.assertEqual(_texto_planilha("-"), "-")
        self.assertEqual(_texto_planilha("N/A"), "N/A")


class TestRateioAcessorios(unittest.TestCase):
    """Diferença de acumulados arredondados: a soma fecha com o total."""

    def test_um_real_entre_tres(self):
        q = SpedDocument.rateio_acessorios(1.00, [10, 10, 10])
        self.assertEqual(q, [0.33, 0.34, 0.33])
        self.assertAlmostEqual(sum(q), 1.00, places=9)

    def test_valores_desiguais_fecham(self):
        q = SpedDocument.rateio_acessorios(7.77, [3, 11, 5, 2, 19, 7])
        self.assertAlmostEqual(sum(q), 7.77, places=9)

    def test_sem_total_e_sem_base(self):
        self.assertEqual(SpedDocument.rateio_acessorios(0, [5, 5]),
                         [0.0, 0.0])
        self.assertAlmostEqual(
            sum(SpedDocument.rateio_acessorios(3.00, [0, 0])), 3.00)


class TestC190(unittest.TestCase):

    def _c190(self, doc):
        c100 = next(r for r in doc.registros if r.reg == "C100")
        doc.consolidar_c190(c100)
        return [f for f in c100.filhos if f.reg == "C190"]

    def test_frete_entra_no_vl_opr(self):
        doc = _doc(icms_basico(frete="1,00"))
        (c190,) = self._c190(doc)
        self.assertEqual(c190.valor(doc._ix("C190", "VL_OPR")), "31,00")

    def test_um_grupo_por_cst_cfop_aliquota(self):
        doc = _doc(icms_basico(itens=[
            {"COD_ITEM": "P1"},
            {"COD_ITEM": "P2", "CFOP": "1403", "CST_ICMS": "060",
             "VL_BC_ICMS": "0", "ALIQ_ICMS": "0", "VL_ICMS": "0"},
            {"COD_ITEM": "P3"}]))
        grupos = {(r.valor(1), r.valor(2)) for r in self._c190(doc)}
        self.assertEqual(grupos, {("000", "1102"), ("060", "1403")})

    def test_reducao_x20(self):
        doc = _doc(icms_basico(itens=[
            {"COD_ITEM": "P1", "CST_ICMS": "020", "VL_BC_ICMS": "6,00",
             "VL_ICMS": "1,08"}]))
        (c190,) = self._c190(doc)
        self.assertEqual(c190.valor(doc._ix("C190", "VL_RED_BC")), "4,00")

    def test_x70_usa_base_de_pis_cofins(self):
        doc = _doc(icms_basico(itens=[
            {"COD_ITEM": "P1", "CST_ICMS": "070", "VL_BC_ICMS": "0",
             "ALIQ_ICMS": "0", "VL_ICMS": "0", "VL_BC_PIS": "7,00"}]))
        (c190,) = self._c190(doc)
        self.assertEqual(c190.valor(doc._ix("C190", "VL_RED_BC")), "3,00")
        # a base de ICMS do C190 continua zero
        self.assertEqual(c190.valor(doc._ix("C190", "VL_BC_ICMS")), "0,00")

    def test_c190_sai_com_a_largura_do_arquivo(self):
        doc = _doc(icms_basico())
        for c190 in self._c190(doc):
            self.assertEqual(len(c190.campos), 12)

    def test_situacao_pelos_dois_ultimos_digitos(self):
        s = SpedDocument.situacao_icms
        self.assertEqual(s("020"), "reduzido")
        self.assertEqual(s("170"), "reduzido")
        self.assertEqual(s("060"), "sem_debito")
        self.assertEqual(s("241"), "sem_debito")
        self.assertEqual(s("000"), "tributado")


if __name__ == "__main__":
    unittest.main()

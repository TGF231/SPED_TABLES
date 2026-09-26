# -*- coding: utf-8 -*-
"""Validação por domínio de campo (domínios embutidos, sem o PVA)."""

import unittest

import validacao
from sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


def _com(tipo, **valores):
    """ICMS básico com campos trocados no primeiro registro `tipo`."""
    m = icms_basico()
    nomes = m.tabela[tipo]
    alvo = next(c for c in m.linhas if c[0] == tipo)
    for nome, v in valores.items():
        alvo[nomes.index(nome)] = v
    return _doc(m)


def _achados(doc, campo):
    return [o for o in validacao.validar(doc) if o.campo == campo]


class TestDominios(unittest.TestCase):

    def test_arquivo_limpo_nao_acusa(self):
        self.assertEqual(validacao.validar(_doc(icms_basico())), [])

    def test_ncm_sem_um_digito_tem_sugestao(self):
        (o,) = _achados(_com("0200", COD_NCM="4012010"), "COD_NCM")
        self.assertEqual(o.sugestao, "04012010")

    def test_ncm_sem_dois_digitos_nao_inventa(self):
        (o,) = _achados(_com("0200", COD_NCM="401201"), "COD_NCM")
        self.assertIsNone(o.sugestao)

    def test_null_do_erp_sugere_esvaziar(self):
        (o,) = _achados(_com("0200", COD_NCM="NULL"), "COD_NCM")
        self.assertEqual(o.sugestao, "")

    def test_numero_com_ponto(self):
        (o,) = _achados(_com("C170", VL_ITEM="11.24"), "VL_ITEM")
        self.assertEqual(o.sugestao, "11,24")

    def test_cst_icms_aponta_mas_nao_sugere(self):
        (o,) = _achados(_com("C170", CST_ICMS="999"), "CST_ICMS")
        self.assertIsNone(o.sugestao)

    def test_csosn_de_tres_digitos_e_aceito(self):
        # a tabela única do PVA lista 101/102/201/202/900 como válidos
        self.assertEqual(_achados(_com("C170", CST_ICMS="102"), "CST_ICMS"),
                         [])

    def test_cst_de_combustivel_de_2023_e_aceito(self):
        for cst in ("002", "015", "053", "061"):
            with self.subTest(cst=cst):
                self.assertEqual(
                    _achados(_com("C170", CST_ICMS=cst), "CST_ICMS"), [])

    def test_cfop_e_data(self):
        self.assertTrue(_achados(_com("C170", CFOP="4102"), "CFOP"))
        self.assertTrue(_achados(_com("C100", DT_DOC="31022026"), "DT_DOC"))

    def test_vazio_nao_e_erro_de_dominio(self):
        self.assertEqual(_achados(_com("0200", COD_NCM=""), "COD_NCM"), [])


class TestNormalizar(unittest.TestCase):

    def test_grava_so_o_que_tem_conserto(self):
        doc = _com("0200", COD_NCM="4012010", CEST="12")
        achados = validacao.validar(doc)
        r = validacao.normalizar(doc, achados)
        self.assertEqual(r["por_campo"], {"COD_NCM": 1})
        self.assertEqual(validacao.validar(doc)[0].campo, "CEST")

    def test_campo_mudado_depois_da_verificacao_fica(self):
        doc = _com("0200", COD_NCM="4012010")
        achados = validacao.validar(doc)
        reg = next(r for r in doc.registros if r.reg == "0200")
        reg.set_valor(doc._ix("0200", "COD_NCM"), "12345678")
        self.assertEqual(validacao.normalizar(doc, achados)["campos"], 0)
        self.assertEqual(reg.valor(doc._ix("0200", "COD_NCM")), "12345678")


if __name__ == "__main__":
    unittest.main()

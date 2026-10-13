# -*- coding: utf-8 -*-
"""Compra para revenda com ICMS retido por ST (CFOP 1403/2403) e CST x10/x70:
o ICMS próprio do fornecedor não é crédito do adquirente. A função zera base,
alíquota e valor do item e refaz C190, C100 e E110."""

import unittest

from sped_tables.dominio.sped_model import SpedDocument, _to_num
from tests.fabrica import icms_basico


def _doc():
    m = icms_basico(itens=[
        {"COD_ITEM": "P1", "CFOP": "1403", "CST_ICMS": "010"},
        {"COD_ITEM": "P2", "CFOP": "2403", "CST_ICMS": "070"},
        {"COD_ITEM": "P3"}])                       # 1102 / 000: crédito ok
    m.reg("E110", VL_TOT_DEBITOS="0", VL_AJ_DEBITOS="0",
          VL_TOT_AJ_DEBITOS="0", VL_ESTORNOS_CRED="0",
          VL_TOT_CREDITOS="5,40", VL_AJ_CREDITOS="0",
          VL_TOT_AJ_CREDITOS="0", VL_ESTORNOS_DEB="0",
          VL_SLD_CREDOR_ANT="0", VL_SLD_APURADO="0", VL_TOT_DED="0",
          VL_ICMS_RECOLHER="0", VL_SLD_CREDOR_TRANSPORTAR="5,40",
          DEB_ESP="0")
    return SpedDocument.de_texto(m.texto())


class TestCreditoST(unittest.TestCase):

    def test_previa_e_zerar(self):
        doc = _doc()
        p = doc.previa_credito_icms_st()
        self.assertEqual(p, {"itens": 2, "documentos": 1, "vl_bc": 20.0,
                             "vl_icms": 3.6})
        doc.zerar_credito_icms_st()
        i = {c: doc._ix("C170", c) for c in ("COD_ITEM", "VL_BC_ICMS",
                                             "ALIQ_ICMS", "VL_ICMS")}
        valores = {r.valor(i["COD_ITEM"]): (r.valor(i["VL_BC_ICMS"]),
                                             r.valor(i["ALIQ_ICMS"]),
                                             r.valor(i["VL_ICMS"]))
                   for r in doc.registros if r.reg == "C170"}
        self.assertEqual(valores["P1"], ("0", "0", "0"))
        self.assertEqual(valores["P2"], ("0", "0", "0"))
        self.assertEqual(valores["P3"], ("10,00", "18", "1,80"))
        c190 = {(r.valor(doc._ix("C190", "CST_ICMS")),
                 r.valor(doc._ix("C190", "CFOP"))):
                _to_num(r.valor(doc._ix("C190", "VL_ICMS")))
                for r in doc.registros if r.reg == "C190"}
        self.assertEqual(c190[("010", "1403")], 0)
        self.assertEqual(c190[("070", "2403")], 0)
        self.assertEqual(c190[("000", "1102")], 1.8)
        c100 = next(r for r in doc.registros if r.reg == "C100")
        self.assertEqual(c100.valor(doc._ix("C100", "VL_ICMS")), "1,80")
        self.assertEqual(c100.valor(doc._ix("C100", "VL_BC_ICMS")), "10,00")
        e110 = next(r for r in doc.registros if r.reg == "E110")
        self.assertEqual(e110.valor(doc._ix("E110", "VL_TOT_CREDITOS")),
                         "1,80")
        self.assertEqual(e110.valor(doc._ix(
            "E110", "VL_SLD_CREDOR_TRANSPORTAR")), "1,80")
        # de novo: nada mais a zerar
        self.assertEqual(doc.previa_credito_icms_st()["itens"], 0)

    def test_so_entrada_e_so_x10_x70(self):
        m = icms_basico(itens=[
            {"COD_ITEM": "P1", "CFOP": "1403", "CST_ICMS": "060"},
            {"COD_ITEM": "P2", "CFOP": "1403", "CST_ICMS": "010",
             "VL_BC_ICMS": "0", "ALIQ_ICMS": "0", "VL_ICMS": "0"}])
        doc = SpedDocument.de_texto(m.texto())
        self.assertEqual(doc.previa_credito_icms_st()["itens"], 0)
        doc = _doc()
        c100 = next(r for r in doc.registros if r.reg == "C100")
        c100.set_valor(doc._ix("C100", "IND_OPER"), "1")
        self.assertEqual(doc.previa_credito_icms_st()["itens"], 0)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""As tabelas oficiais lidas de texto: o formato do PVA, com vigência,
independente de onde o texto veio (pasta do PVA, base de referência)."""

import os
import unittest

from sped_tables.infra import tabelas_ncm, tabelas_oficiais as T
from tests.fabrica import PastaTemporaria

CFOP = ("versão=14 CFOP, DESC_CFOP, DT_INI, DT_FIM\n"
        "1102|Compra para comercialização|01012009|\n"
        "1999|Revogado|01012009|31122010\n")
CREDITO = ("versão=9 CFOP, DESC, DT_INI, DT_FIM, NAT_BC_CRE\n"
           "1102|Compra|01012009||01\n")
PRAZO = ("versão=51 MES_ANO, DATA\n"
         "082026|14102026|01012009|\n")
ZERO = ("versão=52 COD, DESC, DT_INI, DT_FIM, NCM, EXC, EX_IPI\n"
        "101|Hortícolas|01012009||0702;0703||\n")
MONO = ("versão=40 COD, DESC, DT_INI, DT_FIM, NCM, EXC, EX_IPI, UNID, "
        "ALIQ_PIS, ALIQ_COFINS\n"
        "201|Cerveja|01012009||2203||UN|1,00|2,00\n")


class TestLeitura(unittest.TestCase):

    def test_codigos_respeitam_a_vigencia(self):
        t = T.carregar_codigos(CFOP, "31082026")
        self.assertEqual(t["versao"], "14")
        self.assertEqual(set(t["codigos"]), {"1102"})
        self.assertEqual(set(T.carregar_codigos(CFOP)["codigos"]),
                         {"1102", "1999"})

    def test_pasta_fica_com_a_maior_versao_e_ignora_metadados(self):
        with PastaTemporaria() as p:
            for nome, texto in (("SPEDFISCAL_GLOBAL$CFOP$13$1", "antigo"),
                                ("SPEDFISCAL_GLOBAL$CFOP$14$1", CFOP),
                                ("metadados", "\x00\x01")):
                with open(os.path.join(p, nome), "w",
                          encoding="latin-1") as fh:
                    fh.write(texto)
            tabs = T.tabelas_da_pasta(p)
        self.assertEqual(list(tabs), ["SPEDFISCAL_GLOBAL$CFOP"])
        self.assertEqual(tabs["SPEDFISCAL_GLOBAL$CFOP"], (CFOP, 14))

    def test_funcoes_sobre_o_conjunto(self):
        tabs = {
            "SPEDPISCOFINS_OPER_CREDITO$SPEDPISCOFINS_CFOP_CREDITO":
                (CREDITO, 9),
            "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_DATA_LIMITE_ENTREGA":
                (PRAZO, 51),
        }
        self.assertEqual(T.naturezas_cfop_credito(tabs, "31082026"),
                         {"1102": "01"})
        self.assertEqual(T.cfops_com_credito(tabs)[0], {"1102"})
        self.assertEqual(T.prazo_entrega(tabs, "082026"), "14102026")
        self.assertEqual(T.prazo_entrega({}, "082026"), "")

    def test_dominio_pelo_datasource_do_descritor(self):
        estrutura = {"C170": {"campos": {"CFOP": {"datasource": "CFOP"}}}}
        tabs = {"SPEDFISCAL_GLOBAL$CFOP": (CFOP, 14)}
        dom, faltando = T.dominios_por_datasource(
            tabs, estrutura, "ICMS", uf="MG", data_ref="31082026")
        self.assertEqual(dom[("C170", "CFOP")]["codigos"], {"1102"})
        self.assertEqual(faltando, [])

    def test_classificador_das_tabelas_de_ncm(self):
        tabs = {tabelas_ncm.CHAVE_ALIQ_ZERO: (ZERO, 52),
                tabelas_ncm.CHAVE_MONO: (MONO, 40)}
        clf = tabelas_ncm.classificador(tabs)
        self.assertTrue(clf.eh_aliquota_zero("07031019"))
        self.assertTrue(clf.eh_monofasico("22030000"))
        self.assertIsNone(tabelas_ncm.classificador({}))


if __name__ == "__main__":
    unittest.main()

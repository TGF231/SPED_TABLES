# -*- coding: utf-8 -*-
"""Conferência XML × SPED, NCM × CST e totais do C100 (com XML sintético)."""

import os
import unittest

from sped_tables.dominio import conferencia, ncm, xml_fiscal
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import (PastaTemporaria, contrib_basico, icms_basico,
                           nfe_xml)


def _doc(m):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(m.gravar(p))


def _nfes(texto):
    with PastaTemporaria() as p:
        with open(os.path.join(p, "nota.xml"), "w", encoding="utf-8") as fh:
            fh.write(texto)
        nfes, erros = xml_fiscal.ler_pasta(p)
    return nfes


class TestLeituraXml(unittest.TestCase):

    def test_campos_do_documento_e_do_item(self):
        (n,) = _nfes(nfe_xml())
        self.assertEqual((n.mod, n.serie, n.nnf), ("55", "1", "123"))
        self.assertEqual(len(n.itens), 3)
        it = n.itens[0]
        self.assertEqual((it.nitem, it.cfop, it.icms_cst), ("1", "5102",
                                                            "000"))
        self.assertEqual(it.icms_vicms, 1.80)

    def test_xml_quebrado_nao_derruba_a_leitura(self):
        with PastaTemporaria() as p:
            with open(os.path.join(p, "ruim.xml"), "w",
                      encoding="utf-8") as fh:
                fh.write("<isto não é xml")
            nfes, _erros = xml_fiscal.ler_pasta(p)
        self.assertEqual(nfes, [])


class TestConferirEntradas(unittest.TestCase):

    def test_nota_igual_nao_acusa(self):
        r = conferencia.conferir_entradas_55(_doc(icms_basico()),
                                             _nfes(nfe_xml()))
        self.assertEqual(r["resumo"]["docs_casados"], 1)
        self.assertEqual(r["resumo"]["itens_conferidos"], 3)
        self.assertEqual(r["divergencias"], [])

    def test_icms_diferente_e_apontado_no_item(self):
        xml = nfe_xml(itens=[{}, {"vICMS": "2.00"}, {}])
        r = conferencia.conferir_entradas_55(_doc(icms_basico()), _nfes(xml))
        (d,) = r["divergencias"]
        self.assertEqual(d.nitem, "2")
        self.assertIn("ICMS", d.campo)

    def test_csosn_do_simples_nao_e_comparado(self):
        xml = nfe_xml(itens=[{"CSOSN": "102"}, {}, {}])
        r = conferencia.conferir_entradas_55(_doc(icms_basico()), _nfes(xml))
        self.assertEqual(r["resumo"]["cst_csosn_ignorados"], 1)
        self.assertFalse([d for d in r["divergencias"] if "CST" in d.campo])

    def test_nota_sem_c100_e_c100_sem_nota(self):
        r = conferencia.conferir_entradas_55(_doc(icms_basico()),
                                             _nfes(nfe_xml(nnf="999")))
        self.assertEqual(r["resumo"]["docs_sem_c100"], 1)
        self.assertEqual(r["resumo"]["docs_sem_xml"], 1)

    def test_linhas_do_csv(self):
        xml = nfe_xml(itens=[{}, {"vICMS": "2.00"}, {}])
        r = conferencia.conferir_entradas_55(_doc(icms_basico()), _nfes(xml))
        (linha,) = conferencia.linhas_csv(r)
        self.assertEqual(len(linha), len(conferencia.CABECALHO_CSV))


def _tabela(*prefixos):
    return {"versao": "1", "registros": [
        {"ncm": list(prefixos), "ncm_ex": [], "dt_ini": "", "dt_fim": ""}]}


class TestNcm(unittest.TestCase):

    def test_classificacao_por_prefixo_e_excecao(self):
        tab = _tabela("2202", "2106")
        tab["registros"][0]["ncm_ex"] = ["21069010"]
        clf = ncm.ClassificadorNCM(tab_mono=tab)
        self.assertTrue(clf.eh_monofasico("22021000"))
        self.assertTrue(clf.eh_monofasico("21069090"))
        self.assertFalse(clf.eh_monofasico("21069010"))     # exceção
        self.assertFalse(clf.eh_aliquota_zero("22021000"))

    def test_linha_com_ex_da_tipi_so_vale_para_o_mesmo_ex(self):
        """21069010 Ex 02 é o concentrado para refrigerante, não toda
        preparação alimentícia: sem o EX_IPI no 0200, não é monofásico."""
        tab = _tabela("21069010")
        tab["registros"][0]["ex_ipi"] = "02"
        clf = ncm.ClassificadorNCM(tab_mono=tab)
        self.assertFalse(clf.eh_monofasico("21069010"))
        self.assertFalse(clf.eh_monofasico("21069010", ex_ipi="01"))
        self.assertTrue(clf.eh_monofasico("21069010", ex_ipi="2"))

    def test_vigencia(self):
        tab = _tabela("2202")
        tab["registros"][0]["dt_fim"] = "31122020"
        clf = ncm.ClassificadorNCM(tab_mono=tab)
        self.assertTrue(clf.eh_monofasico("22021000", "01012020"))
        self.assertFalse(clf.eh_monofasico("22021000", "01082026"))

    def test_entrada_de_monofasico_com_credito(self):
        doc = _doc(contrib_basico())           # item P1, NCM 21069090
        clf = ncm.ClassificadorNCM(tab_mono=_tabela("2106"))
        probs = ncm.verificar_cst_pis_cofins(doc, clf)
        entradas = [p for p in probs if p["op"] == "E"]
        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0]["cst_sugerido"], "73")

    def test_sem_classificacao_nada_a_apontar(self):
        doc = _doc(contrib_basico())
        clf = ncm.ClassificadorNCM()
        self.assertEqual([p for p in ncm.verificar_cst_pis_cofins(doc, clf)
                          if p["op"] == "E"], [])


class TestTotaisC100(unittest.TestCase):

    def test_totais_somam_os_itens_e_mantem_o_frete(self):
        m = icms_basico(frete="2,00")
        for c in m.linhas:                     # C100 com totais errados
            if c[0] == "C100":
                c[m.tabela["C100"].index("VL_MERC")] = "99,00"
        doc = _doc(m)
        c100 = next(r for r in doc.registros if r.reg == "C100")
        tot = doc.recalcular_totais_c100(c100)
        self.assertEqual(tot["VL_MERC"], 30.0)
        self.assertEqual(tot["VL_ICMS"], 5.4)
        self.assertEqual(c100.valor(doc._ix("C100", "VL_DOC")), "32,00")


def _contrib_nfce(frete="0"):
    """EFD Contribuições com uma NFC-e (modelo 65) consolidada num C175."""
    m = contrib_basico(bloco_m=False)
    m.linhas = [c for c in m.linhas if c[0] not in ("C100", "C170")]
    m.reg("C100", IND_OPER="1", IND_EMIT="0", COD_MOD="65", COD_SIT="00",
          SER="1", NUM_DOC="123", DT_DOC="05082026", VL_DOC="30,00",
          IND_PGTO="0", VL_MERC="30,00", IND_FRT="9", VL_FRT=frete)
    m.reg("C175", CFOP="5102", VL_OPR="30,00", CST_PIS="01",
          VL_BC_PIS="30,00", ALIQ_PIS="1,65", VL_PIS="0,50",
          CST_COFINS="01", VL_BC_COFINS="30,00", ALIQ_COFINS="7,6",
          VL_COFINS="2,28")
    return m


class TestNfce65(unittest.TestCase):
    """Validar C175 por item (C170 fictícios) e regenerar."""

    def test_ficticios_somem_e_a_estrutura_volta(self):
        doc = _doc(_contrib_nfce())
        antes = len(doc.registros)
        nfes = _nfes(nfe_xml(mod="65"))
        doc.gerar_c170_ficticios_65(nfes)
        c100 = next(r for r in doc.registros if r.reg == "C100")
        self.assertEqual(len([f for f in c100.filhos if f.reg == "C170"]), 3)
        doc.regenerar_c175_de_c170_65()
        self.assertEqual([f for f in c100.filhos if f.reg == "C170"], [])
        c175 = [f for f in c100.filhos if f.reg == "C175"]
        self.assertEqual(len(c175), 1)
        self.assertEqual(c175[0].valor(doc._ix("C175", "VL_OPR")), "30,00")
        self.assertEqual(len(doc.registros), antes)

    def test_frete_do_documento_entra_no_c175_rateado(self):
        doc = _doc(_contrib_nfce(frete="1,00"))
        doc.gerar_c170_ficticios_65(_nfes(nfe_xml(mod="65")))
        # conferência e geração usam o mesmo rateio: as duas dizem 31,00
        (d,) = doc.discrepancias_c175_65()
        self.assertEqual(d["xml"], "31,00")
        doc.regenerar_c175_de_c170_65()
        (c175,) = [r for r in doc.registros if r.reg == "C175"]
        self.assertEqual(c175.valor(doc._ix("C175", "VL_OPR")), "31,00")


def icms_nfce():
    """EFD ICMS/IPI com uma NFC-e (65) sem itens e um C190 de CST 070 com a
    redução de base zerada — o caso que o recálculo em massa não alcançava,
    porque não havia C170 de onde refazer o analítico."""
    m = icms_basico()
    m.linhas = [c for c in m.linhas if c[0] not in ("C100", "C170", "C190")]
    m.reg("C100", IND_OPER="1", IND_EMIT="0", COD_MOD="65", COD_SIT="00",
          SER="1", NUM_DOC="123", DT_DOC="05082026", VL_DOC="30,00",
          IND_PGTO="0", VL_MERC="30,00", IND_FRT="9")
    m.reg("C190", CST_ICMS="070", CFOP="5405", ALIQ_ICMS="0",
          VL_OPR="30,00", VL_BC_ICMS="0", VL_ICMS="0", VL_BC_ICMS_ST="0",
          VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
    return m


def xml_nfce_st():
    """Os três itens da NFC-e: CST 70, sem base própria de ICMS, com base
    de PIS de R$ 8,00 cada."""
    item = {"CST": "70", "vBC": "0.00", "pICMS": "0.00", "vICMS": "0.00",
            "CFOP": "5405", "pis": ("01", "8.00", "1.65", "0.13")}
    return nfe_xml(mod="65", itens=[dict(item) for _ in range(3)], dest=None)


class TestNfce65Icms(unittest.TestCase):
    """No EFD ICMS/IPI o andaime serve ao C190: gerar os fictícios,
    refazer o analítico em massa, remover os fictícios."""

    def test_c190_refeito_pelos_itens_do_xml(self):
        doc = _doc(icms_nfce())
        antes = len(doc.registros)
        res = doc.gerar_c170_ficticios_65(_nfes(xml_nfce_st()))
        self.assertEqual((res["docs"], res["itens"], res["csosn"]), (1, 3, 0))
        self.assertEqual(len(doc.documentos_65_com_c170()), 1)

        tot = doc.consolidar_c190_em_massa()
        self.assertEqual((tot["documentos"], tot["corrigidos"],
                          tot["base_pis_cofins"]), (1, 1, 1))
        (c190,) = [r for r in doc.registros if r.reg == "C190"]
        # x70 sem base de ICMS: 30,00 da operação − 24,00 da base de PIS
        self.assertEqual(c190.valor(doc._ix("C190", "VL_RED_BC")), "6,00")
        self.assertEqual(c190.valor(doc._ix("C190", "VL_OPR")), "30,00")

        self.assertEqual(doc.remover_c170_ficticios_65(),
                         {"docs": 1, "itens": 3})
        self.assertEqual(doc.documentos_65_com_c170(), [])
        self.assertEqual(len(doc.registros), antes)

    def test_csosn_do_simples_e_contado(self):
        doc = _doc(icms_nfce())
        res = doc.gerar_c170_ficticios_65(_nfes(nfe_xml(
            mod="65", dest=None, itens=[{"CSOSN": "102"}])))
        self.assertEqual(res["csosn"], 1)


if __name__ == "__main__":
    unittest.main()

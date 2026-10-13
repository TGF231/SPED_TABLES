# -*- coding: utf-8 -*-
"""Gerar o EFD Contribuições a partir dos XMLs e da memória da empresa.

O "entregue" é montado aqui: um contribuinte **cumulativo** com uma entrada
sem crédito (CST 70) e uma NFC-e com C175 a 0,65/3. O XML da NFC-e vem com
1,65/7,60 — como no mês real, em que o ERP emitia a alíquota do
não-cumulativo —, e a escrituração tem de sair com a do regime.
"""

import os
import unittest

from sped_tables.aplicacao import montagem
from sped_tables.dominio import diagnostico, geracao
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.sped_model import SpedDocument, _to_num
from tests.fabrica import CNPJ_TESTE, Montador, PastaTemporaria, nfe_xml

CHAVE_ENTRADA = "31260811444777000161550010000001231000001238"
CHAVE_NFCE = "31260811222333000181650010000000011000000019"


def _entregue():
    m = Montador("CONTRIB")
    m.reg("0000", COD_VER="006", TIPO_ESCRIT="0", DT_INI="01082026",
          DT_FIN="31082026", NOME="EMPRESA TESTE LTDA", CNPJ=CNPJ_TESTE,
          UF="MG", COD_MUN="3106200", IND_NAT_PJ="00", IND_ATIV="2")
    m.reg("0110", COD_INC_TRIB="2", COD_TIPO_CONT="1", IND_REG_CUM="9")
    m.reg("0140", COD_EST="1", NOME="EMPRESA TESTE LTDA", CNPJ=CNPJ_TESTE,
          UF="MG", COD_MUN="3106200")
    m.reg("0150", COD_PART="7", NOME="FORNECEDOR TESTE", COD_PAIS="1058",
          CNPJ="11444777000161", COD_MUN="3106200")
    m.reg("0190", UNID="UN", DESCR="UNIDADE")
    m.reg("0200", COD_ITEM="P1", DESCR_ITEM="PRODUTO P1", UNID_INV="UN",
          TIPO_ITEM="00", COD_NCM="21069090")
    m.reg("0500", DT_ALT="01012020", COD_NAT_CC="04", IND_CTA="A",
          NIVEL="1", COD_CTA="3.1.1", NOME_CTA="RECEITA")
    m.reg("C010", CNPJ=CNPJ_TESTE, IND_ESCRI="2")
    m.reg("C100", IND_OPER="0", IND_EMIT="1", COD_PART="7", COD_MOD="55",
          COD_SIT="00", SER="1", NUM_DOC="123", CHV_NFE=CHAVE_ENTRADA,
          DT_DOC="05082026", DT_E_S="05082026", VL_DOC="10,00",
          IND_PGTO="2", VL_MERC="10,00", IND_FRT="9")
    m.reg("C170", NUM_ITEM="1", COD_ITEM="P1", QTD="1", UNID="UN",
          VL_ITEM="10,00", IND_MOV="0", CST_ICMS="000", CFOP="1102",
          CST_PIS="70", VL_BC_PIS="0", ALIQ_PIS="0", VL_PIS="0",
          CST_COFINS="70", VL_BC_COFINS="0", ALIQ_COFINS="0",
          VL_COFINS="0", COD_CTA="3.1.1")
    m.reg("C100", IND_OPER="1", IND_EMIT="0", COD_MOD="65", COD_SIT="00",
          SER="1", NUM_DOC="1", CHV_NFE="3126081122233300018165001000"
          "0000021000000027", DT_DOC="05082026", DT_E_S="05082026",
          VL_DOC="100,00", IND_PGTO="2", VL_MERC="100,00", IND_FRT="9")
    m.reg("C175", CFOP="5102", VL_OPR="100,00", CST_PIS="01",
          VL_BC_PIS="82,00", ALIQ_PIS="0,65", VL_PIS="0,53",
          CST_COFINS="01", VL_BC_COFINS="82,00", ALIQ_COFINS="3",
          VL_COFINS="2,46")
    m.reg("M200", VL_TOT_CONT_CUM_PER="0,53", VL_CONT_CUM_REC="0,53",
          VL_TOT_CONT_REC="0,53")
    m.reg("M205", NUM_CAMPO="12", COD_REC="810902", VL_DEBITO="0,53")
    m.reg("M210", COD_CONT="51", VL_REC_BRT="100,00", VL_BC_CONT="82,00",
          ALIQ_PIS="0,65", VL_CONT_APUR="0,53", VL_CONT_PER="0,53")
    m.reg("M600", VL_TOT_CONT_CUM_PER="2,46", VL_CONT_CUM_REC="2,46",
          VL_TOT_CONT_REC="2,46")
    m.reg("M605", NUM_CAMPO="12", COD_REC="217201", VL_DEBITO="2,46")
    m.reg("M610", COD_CONT="51", VL_REC_BRT="100,00", VL_BC_CONT="82,00",
          ALIQ_COFINS="3", VL_CONT_APUR="2,46", VL_CONT_PER="2,46")
    return m


class TestContribuicoes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        montagem.configurar()

    def setUp(self):
        self._p = PastaTemporaria()
        self.pasta = self._p.__enter__()
        entregue = SpedDocument.carregar(_entregue().gravar(self.pasta))
        self.xmls = os.path.join(self.pasta, "xml")
        os.makedirs(self.xmls)
        self._grava("entrada.xml", nfe_xml(itens=[{"cProd": "F1"}]))
        self.memoria = mi.nova(CNPJ_TESTE)
        mi.aprender(self.memoria, xf.ler_pasta_fiscal(self.xmls),
                    doc_contrib=entregue)
        # a NFC-e do mês a gerar: base sem o ICMS, alíquota errada no XML
        self._grava("nfce.xml", nfe_xml(
            mod="65", chave=CHAVE_NFCE, nnf="1",
            emit=(CNPJ_TESTE, "EMPRESA TESTE LTDA"), dest=None,
            itens=[{"cProd": "P1", "vProd": "200.00", "vBC": "200.00",
                    "vICMS": "36.00",
                    "pis": ("01", "164.00", "1.65", "2.71"),
                    "cofins": ("01", "164.00", "7.60", "12.46")}]))

    def tearDown(self):
        self._p.__exit__(None, None, None)

    def _grava(self, nome, texto):
        with open(os.path.join(self.xmls, nome), "w",
                  encoding="utf-8") as fh:
            fh.write(texto)

    def gerar(self):
        res = geracao.gerar_contrib(self.memoria,
                                    xf.ler_pasta_fiscal(self.xmls), "202608")
        cam = os.path.join(self.pasta, "gerado.txt")
        res.doc.salvar(cam)
        return res, SpedDocument.carregar(cam)

    def val(self, doc, reg, campo, r=None):
        r = r or next(x for x in doc.registros if x.reg == reg)
        return r.valor(doc._ix(reg, campo))

    def test_extemporaneo_marcado_fica_no_mes(self):
        """No Contribuições o PVA recusa data de outro mês: o cupom
        extemporâneo marcado entra com COD_SIT 01 e o primeiro dia."""
        self._grava("nfce.xml", nfe_xml(
            mod="65", chave=CHAVE_NFCE, nnf="1",
            emit=(CNPJ_TESTE, "EMPRESA TESTE LTDA"), dest=None,
            dhemi="2026-07-31T23:50:00-03:00",
            itens=[{"cProd": "P1", "vProd": "200.00"}]))
        lote = xf.ler_pasta_fiscal(self.xmls)
        res = geracao.gerar_contrib(self.memoria, lote, "202608")
        self.assertEqual(res.fora_periodo, [(CHAVE_NFCE, "31072026")])
        res = geracao.gerar_contrib(self.memoria, lote, "202608",
                                    incluir={CHAVE_NFCE})
        doc = res.doc
        nfce = next(r for r in doc.registros if r.reg == "C100"
                    and self.val(doc, "C100", "COD_MOD", r) == "65")
        self.assertEqual((self.val(doc, "C100", "COD_SIT", nfce),
                          self.val(doc, "C100", "DT_DOC", nfce)),
                         ("01", "01082026"))

    def test_nfce_com_a_aliquota_do_regime(self):
        res, doc = self.gerar()
        self.assertIn("alíquota do XML trocada",
                      {r["tipo"] for r in res.revisar})
        c175 = next(r for r in doc.registros if r.reg == "C175")
        self.assertEqual((self.val(doc, "C175", "CST_PIS", c175),
                          _to_num(self.val(doc, "C175", "VL_BC_PIS", c175)),
                          _to_num(self.val(doc, "C175", "ALIQ_PIS", c175)),
                          _to_num(self.val(doc, "C175", "VL_PIS", c175))),
                         ("01", 164.0, 0.65, 1.07))

    def test_bloco_m_e_codigo_de_receita(self):
        _res, doc = self.gerar()
        self.assertAlmostEqual(_to_num(self.val(doc, "M210",
                                                "VL_CONT_APUR")), 1.07)
        self.assertEqual(self.val(doc, "M210", "COD_CONT"), "51")
        self.assertEqual(self.val(doc, "M205", "COD_REC"), "810902")
        self.assertAlmostEqual(_to_num(self.val(doc, "M605",
                                                "VL_DEBITO")), 4.92)

    def test_entrada_pela_memoria_e_largura_do_entregue(self):
        _res, doc = self.gerar()
        c170 = next(r for r in doc.registros if r.reg == "C170")
        self.assertEqual((self.val(doc, "C170", "COD_ITEM", c170),
                          self.val(doc, "C170", "CST_PIS", c170),
                          self.val(doc, "C170", "COD_CTA", c170)),
                         ("P1", "70", "3.1.1"))
        # sem crédito, sem base
        self.assertEqual(_to_num(self.val(doc, "C170", "VL_BC_PIS", c170)),
                         0.0)
        self.assertTrue(any(r.reg == "0500" for r in doc.registros))
        # a largura aprendida do "entregue" (13, do leiaute do programa) é
        # limitada pela do descritor do PVA quando ele está instalado
        larg = geracao._larguras(self.memoria, "CONTRIB").get(
            "0200", self.memoria["larguras"]["CONTRIB"]["0200"])
        self.assertEqual(len(next(r for r in doc.registros
                                  if r.reg == "0200").campos), larg)
        achados, _i = diagnostico.verificar(doc)
        self.assertEqual(diagnostico.impedem_importacao(achados), [])


if __name__ == "__main__":
    unittest.main()

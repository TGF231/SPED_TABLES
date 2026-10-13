# -*- coding: utf-8 -*-
"""Gerar o EFD ICMS/IPI a partir dos XMLs e da memória da empresa.

Tudo sintético: o SPED "entregue" é o `icms_basico` da fábrica, os XMLs são
montados na hora. O que se confere é o que o mês real ensinou — código
próprio pela memória, entrada datada e escriturada como a empresa faz,
NFC-e sem C170 e com ST/IPI vazios no C100, C190 fechando com o VL_DOC,
cancelada só com a chave, CT-e tomado no D100, e o que não se sabe
apontado (ou bloqueado, quando o arquivo sairia inválido).
"""

import os
import unittest

from sped_tables.aplicacao import montagem
from sped_tables.dominio import comparacao_sped as cs
from sped_tables.dominio import diagnostico, geracao
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.sped_model import SpedDocument, _to_num
from tests.fabrica import (CNPJ_TESTE, PastaTemporaria, cte_xml,
                           evento_cancelamento_xml, icms_basico, nfe_xml)

CHAVE_ENTRADA = "31260811444777000161550010000001231000001238"
CHAVE_NFCE = "31260811222333000181650010000000011000000019"


def _grava(pasta, nome, texto):
    cam = os.path.join(pasta, nome)
    with open(cam, "w", encoding="utf-8") as fh:
        fh.write(texto)


class Base(unittest.TestCase):
    """Memória aprendida do `icms_basico` (entrada de P1..P3, que o
    fornecedor chama de F1..F3), e uma pasta de XMLs do mesmo mês."""

    ITENS = [{"cProd": "F1"}, {"cProd": "F2"}, {"cProd": "F3"}]

    @classmethod
    def setUpClass(cls):
        montagem.configurar()

    def setUp(self):
        self._p = PastaTemporaria()
        self.pasta = self._p.__enter__()
        self.entregue = SpedDocument.carregar(icms_basico().gravar(self.pasta))
        self.xmls = os.path.join(self.pasta, "xml")
        os.makedirs(self.xmls)
        _grava(self.xmls, "entrada.xml", nfe_xml(itens=self.ITENS))
        self.memoria = mi.nova(CNPJ_TESTE)
        mi.aprender(self.memoria, xf.ler_pasta_fiscal(self.xmls),
                    doc_icms=self.entregue)

    def tearDown(self):
        self._p.__exit__(None, None, None)

    def gerar(self, **k):
        return geracao.gerar_icms(self.memoria,
                                  xf.ler_pasta_fiscal(self.xmls), "202608",
                                  saldo_credor_anterior=0, **k)

    def reler(self, res):
        """O gerado passa pela gravação e pela leitura do programa."""
        cam = os.path.join(self.pasta, "gerado.txt")
        res.doc.salvar(cam)
        return SpedDocument.carregar(cam)


class TestEntrada(Base):

    def test_reproduz_a_entrada_escriturada(self):
        res = self.gerar()
        gerado = self.reler(res)
        comp = cs.comparar(gerado, self.entregue)
        self.assertEqual(comp["C100"]["so_gerado"], [])
        self.assertEqual(comp["C100"]["so_entregue"], [])
        itens = [x for x in comp["C170"]["diferencas"]]
        self.assertEqual(itens, [])
        self.assertEqual(comp["C170"]["iguais"], 3)
        i = {c: gerado._ix("C170", c) for c in ("COD_ITEM", "CFOP",
                                                 "CST_ICMS")}
        self.assertEqual(
            [(r.valor(i["COD_ITEM"]), r.valor(i["CFOP"]),
              r.valor(i["CST_ICMS"])) for r in gerado.registros
             if r.reg == "C170"],
            [("P1", "1102", "000"), ("P2", "1102", "000"),
             ("P3", "1102", "000")])
        self.assertEqual(res.bloqueios, [])

    def test_arquivo_bem_formado_e_apuracao(self):
        gerado = self.reler(self.gerar())
        achados, _i = diagnostico.verificar(gerado)
        self.assertEqual(diagnostico.impedem_importacao(achados), [])
        e110 = next(r for r in gerado.registros if r.reg == "E110")
        self.assertAlmostEqual(_to_num(e110.valor(
            gerado._ix("E110", "VL_TOT_CREDITOS"))), 5.40)
        # o C190 soma o VL_DOC do C100
        c100 = next(r for r in gerado.registros if r.reg == "C100")
        opr = sum(_to_num(f.valor(gerado._ix("C190", "VL_OPR")))
                  for f in c100.filhos if f.reg == "C190")
        self.assertAlmostEqual(opr, _to_num(c100.valor(
            gerado._ix("C100", "VL_DOC"))))

    def test_produto_novo_usa_a_pratica_da_empresa(self):
        _grava(self.xmls, "entrada.xml", nfe_xml(itens=[
            {"cProd": "F1"}, {"cProd": "NOVO"}, {"cProd": "F3"}]))
        res = self.gerar()
        tipos = sorted({r["tipo"] for r in res.revisar})
        self.assertIn("produto sem código próprio", tipos)
        self.assertIn("escrituração pela prática da empresa", tipos)
        gerado = self.reler(res)
        i = gerado._ix("C170", "CFOP")
        self.assertEqual({r.valor(i) for r in gerado.registros
                          if r.reg == "C170"}, {"1102"})

    def test_cfop_impossivel_bloqueia(self):
        _grava(self.xmls, "entrada.xml", nfe_xml(
            itens=[{"cProd": "NOVO", "CFOP": "5908"}]))
        res = self.gerar(correlacoes={})
        self.assertEqual([b["tipo"] for b in res.bloqueios],
                         ["CFOP de entrada desconhecido"])

    def test_nota_desmarcada_fica_de_fora(self):
        res = self.gerar(excluir={CHAVE_ENTRADA})
        self.assertEqual(res.ignorados, [(CHAVE_ENTRADA, "desmarcado")])
        self.assertFalse(any(r.reg == "C100" for r in res.doc.registros))


class TestSaidasECancelamento(Base):

    def test_nfce_sem_c170_com_st_e_ipi_vazios(self):
        _grava(self.xmls, "nfce.xml", nfe_xml(
            mod="65", chave=CHAVE_NFCE, nnf="1", cfop="5102",
            emit=(CNPJ_TESTE, "EMPRESA TESTE LTDA"), dest=None,
            itens=[{"cProd": "P1", "vProd": "20.00", "vBC": "20.00",
                    "vICMS": "3.60"}]))
        gerado = self.reler(self.gerar())
        nfce = next(r for r in gerado.registros if r.reg == "C100"
                    and r.valor(gerado._ix("C100", "COD_MOD")) == "65")
        self.assertEqual([f.reg for f in nfce.filhos], ["C190"])
        for campo in geracao.NFCE_C100_VAZIOS:
            self.assertEqual(nfce.valor(gerado._ix("C100", campo)), "")
        self.assertEqual(nfce.valor(gerado._ix("C100", "COD_PART")), "")
        e110 = next(r for r in gerado.registros if r.reg == "E110")
        self.assertAlmostEqual(_to_num(e110.valor(
            gerado._ix("E110", "VL_TOT_DEBITOS"))), 3.60)

    def test_fora_do_periodo_so_entra_marcado_e_vai_extemporaneo(self):
        """Cupom de julho transmitido em agosto: sem a escolha da pessoa
        fica de fora (e é listado); marcado, entra com COD_SIT 01, a data do
        XML, e o ICMS dele vai para o DEB_ESP — não para os débitos."""
        _grava(self.xmls, "nfce.xml", nfe_xml(
            mod="65", chave=CHAVE_NFCE, nnf="1", cfop="5102",
            emit=(CNPJ_TESTE, "EMPRESA TESTE LTDA"), dest=None,
            dhemi="2026-07-31T23:50:00-03:00",
            itens=[{"cProd": "P1", "vProd": "20.00", "vBC": "20.00",
                    "vICMS": "3.60"}]))
        res = self.gerar()
        self.assertEqual(res.fora_periodo, [(CHAVE_NFCE, "31072026")])
        self.assertFalse(any(r.reg == "C100" and r.valor(
            res.doc._ix("C100", "COD_MOD")) == "65"
            for r in res.doc.registros))
        res = self.gerar(incluir={CHAVE_NFCE})
        self.assertEqual(res.fora_periodo, [])
        self.assertEqual(res.extemporaneos, {CHAVE_NFCE})
        gerado = self.reler(res)
        ic = {c: gerado._ix("C100", c) for c in ("COD_MOD", "COD_SIT",
                                                  "DT_DOC")}
        nfce = next(r for r in gerado.registros if r.reg == "C100"
                    and r.valor(ic["COD_MOD"]) == "65")
        self.assertEqual((nfce.valor(ic["COD_SIT"]), nfce.valor(ic["DT_DOC"])),
                         ("01", "31072026"))
        e110 = next(r for r in gerado.registros if r.reg == "E110")
        ie = {c: gerado._ix("E110", c) for c in ("VL_TOT_DEBITOS",
                                                 "DEB_ESP")}
        self.assertAlmostEqual(_to_num(e110.valor(ie["VL_TOT_DEBITOS"])), 0)
        self.assertAlmostEqual(_to_num(e110.valor(ie["DEB_ESP"])), 3.60)
        # o que o recálculo do botão espera é o que a geração gravou
        self.assertEqual(gerado.recalcular_e110(), {})

    def test_cancelada_so_com_a_chave(self):
        _grava(self.xmls, "canc.xml",
               evento_cancelamento_xml(CHAVE_ENTRADA))
        gerado = self.reler(self.gerar())
        c100 = next(r for r in gerado.registros if r.reg == "C100")
        self.assertEqual(c100.valor(gerado._ix("C100", "COD_SIT")), "02")
        self.assertEqual(c100.valor(gerado._ix("C100", "VL_DOC")), "")
        self.assertEqual(c100.filhos, [])


class TestCTe(Base):

    def test_frete_tomado_vira_d100_de_entrada(self):
        _grava(self.xmls, "cte.xml", cte_xml())      # tomador = empresa
        res = self.gerar()
        gerado = self.reler(res)
        d100 = next(r for r in gerado.registros if r.reg == "D100")
        v = {c: d100.valor(gerado._ix("D100", c)) for c in (
            "IND_OPER", "IND_EMIT", "COD_MOD", "IND_FRT", "COD_MUN_ORIG",
            "COD_MUN_DEST")}
        self.assertEqual(v, {"IND_OPER": "0", "IND_EMIT": "1",
                             "COD_MOD": "57", "IND_FRT": "1",
                             "COD_MUN_ORIG": "3550308",
                             "COD_MUN_DEST": "3106200"})
        d190 = next(r for r in gerado.registros if r.reg == "D190")
        # transportadora de MG, empresa de MG: CFOP estadual
        self.assertEqual(d190.valor(gerado._ix("D190", "CFOP")), "1353")
        self.assertIn("frete sem memória", {r["tipo"] for r in res.revisar})
        achados, _i = diagnostico.verificar(gerado)
        self.assertEqual(diagnostico.impedem_importacao(achados), [])

    def test_cte_de_terceiros_nao_entra(self):
        _grava(self.xmls, "cte.xml", cte_xml(toma="0"))   # tomador: rem
        res = self.gerar()
        self.assertFalse(any(r.reg == "D100" for r in res.doc.registros))
        self.assertTrue(any("tomadora" in m for _c, m in res.ignorados))


if __name__ == "__main__":
    unittest.main()

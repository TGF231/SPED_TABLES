# -*- coding: utf-8 -*-
"""Regras de revisão (as que reproduzem mensagens do PVA)."""

import unittest

import revisao
from sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


def _alterar(m, tipo, **valores):
    nomes = m.tabela[tipo]
    alvo = next(c for c in m.linhas if c[0] == tipo)
    for nome, v in valores.items():
        alvo[nomes.index(nome)] = v
    return m


class TestTodasAsRegras(unittest.TestCase):
    """Nenhuma regra pode levantar exceção — exceção num slot do Qt derruba
    o programa."""

    def test_rodam_nos_dois_leiautes(self):
        for m in (icms_basico(), contrib_basico(), contrib_basico("2")):
            doc = _doc(m)
            for rotulo, problemas in revisao.revisar_por_regra(doc):
                with self.subTest(layout=doc.layout, regra=rotulo):
                    self.assertIsInstance(problemas, list)


class TestRegras(unittest.TestCase):

    def test_saida_fora_do_periodo(self):
        m = _alterar(icms_basico(), "C100", IND_OPER="1", IND_EMIT="0",
                     DT_E_S="01092026")
        (p,) = revisao.verificar_data_fora_periodo(_doc(m))
        self.assertIn("01092026", p.descricao)

    def test_entrada_fora_do_periodo_e_legitima(self):
        m = _alterar(icms_basico(), "C100", DT_E_S="01072026")
        self.assertEqual(revisao.verificar_data_fora_periodo(_doc(m)), [])

    def test_cst_02_sem_aliquota(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "CST_ICMS": "102",
                                "ALIQ_ICMS": "0", "VL_ICMS": "0"}])
        (p,) = revisao.verificar_cst_combustivel_sem_aliquota(_doc(m))
        self.assertIn("102", p.descricao)

    def test_cst_02_com_aliquota_passa(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "CST_ICMS": "002"}])
        self.assertEqual(
            revisao.verificar_cst_combustivel_sem_aliquota(_doc(m)), [])

    def test_ind_emit_de_terceiro_na_saida(self):
        m = _alterar(icms_basico(), "C100", IND_OPER="1", IND_EMIT="1")
        (p,) = revisao.verificar_ind_emit(_doc(m))
        # a chave do documento é de outro CNPJ
        self.assertIn("entrada", p.descricao)

    def test_0900_so_depois_do_prazo(self):
        import tabelas_pva
        if not tabelas_pva.prazo_entrega("082026"):
            self.skipTest("tabela de prazos do PVA não instalada")
        doc = _doc(contrib_basico())
        self.assertEqual(revisao.verificar_0900_ausente(doc, hoje="20260901"),
                         [])
        (p,) = revisao.verificar_0900_ausente(doc, hoje="20300101")
        self.assertEqual(p.gravidade, "aviso")

    def test_resumo_por_regra(self):
        problemas, resumo = revisao.revisar(_doc(icms_basico()))
        self.assertEqual(len(resumo), len(revisao.REGRAS))
        self.assertEqual(sum(n for _r, n in resumo), len(problemas))


if __name__ == "__main__":
    unittest.main()

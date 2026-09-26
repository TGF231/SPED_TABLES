# -*- coding: utf-8 -*-
"""As correções que **gravam** no arquivo, uma a uma.

Cada teste confere três coisas: o conserto acontece, a segunda passada não
mexe em mais nada (idempotência) e o arquivo continua bem formado — mesma
largura de registro e bloco 9 fechando depois de salvar e reabrir.
"""

import datetime
import os
import unittest

from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


def _alterar(m, tipo, **valores):
    nomes = m.tabela[tipo]
    alvo = next(c for c in m.linhas if c[0] == tipo)
    for nome, v in valores.items():
        alvo[nomes.index(nome)] = v
    return m


class Base(unittest.TestCase):

    def assertBemFormado(self, doc):
        """Largura estável por tipo e ida-e-volta sem perda."""
        larguras = {}
        for r in doc.registros:
            larguras.setdefault(r.reg, set()).add(len(r.campos))
        variaveis = {t: l for t, l in larguras.items() if len(l) > 1}
        self.assertEqual(variaveis, {})
        with PastaTemporaria() as p:
            cam = os.path.join(p, "saida.txt")
            doc.salvar(cam)
            relido = SpedDocument.carregar(cam)
        self.assertEqual(relido.gerar_texto(), doc.gerar_texto())


class TestLimparNulos(Base):

    def test_esvazia_e_para(self):
        m = _alterar(icms_basico(), "0200", CEST="NULL", COD_GEN="#N/A")
        doc = _doc(m)
        achados = doc.campos_nulos()
        self.assertEqual(sorted(a[2] for a in achados), ["CEST", "COD_GEN"])
        doc.limpar_campos_nulos(achados)
        self.assertEqual(doc.campos_nulos(), [])
        self.assertBemFormado(doc)


class TestCodGen(Base):

    def test_genero_vem_do_ncm_normalizado(self):
        m = _alterar(icms_basico(), "0200", COD_NCM="4012010", COD_GEN="40")
        doc = _doc(m)
        ocs = doc.divergencias_cod_gen()
        oc = next(o for o in ocs if o[1] == "P1")
        self.assertEqual(oc[4], "04")                   # não "40"
        # os outros itens (sem gênero) recebem o capítulo 21
        self.assertEqual({o[4] for o in ocs if o[1] != "P1"}, {"21"})
        doc.preencher_cod_gen(ocs)
        self.assertEqual(doc.divergencias_cod_gen(), [])
        self.assertBemFormado(doc)


class TestCodCta(Base):

    def test_preenche_so_o_vazio_e_cria_o_0500(self):
        doc = _doc(icms_basico())
        sem = doc.registros_sem_cod_cta("C170")
        self.assertEqual(len(sem), 3)
        doc.preencher_cod_cta("C170", "1.1.03.01", nome_cta="ESTOQUE")
        self.assertEqual(doc.registros_sem_cod_cta("C170"), [])
        contas = [r for r in doc.registros if r.reg == "0500"]
        self.assertEqual(len(contas), 1)
        # na posição do leiaute: depois do 0200, antes do 0990
        tipos = [l.split("|")[1] for l in doc.gerar_texto().splitlines()
                 if l.startswith("|0")]
        self.assertLess(tipos.index("0200"), tipos.index("0500"))
        self.assertLess(tipos.index("0500"), tipos.index("0990"))
        # segunda passada: nada a fazer, nenhum 0500 duplicado
        doc.preencher_cod_cta("C170", "1.1.03.01", nome_cta="ESTOQUE")
        self.assertEqual(len([r for r in doc.registros if r.reg == "0500"]),
                         1)
        self.assertBemFormado(doc)


class TestItensSemReferencia(Base):

    def test_remove_so_o_orfao(self):
        m = icms_basico()
        m.linhas.insert(4, ["0200", "ORFAO", "SEM USO", "", "", "UN", "00",
                            "21069090", "", "", "", "", ""])
        doc = _doc(m)
        orfaos = doc.itens_0200_nao_utilizados()
        self.assertEqual([o[1] for o in orfaos], ["ORFAO"])
        doc.remover_itens_0200([o[0] for o in orfaos])
        self.assertEqual(doc.itens_0200_nao_utilizados(), [])
        self.assertEqual(len([r for r in doc.registros if r.reg == "0200"]),
                         3)
        self.assertBemFormado(doc)


class TestRecalcularIcms(Base):

    def test_valor_sai_da_base_e_da_aliquota(self):
        doc = _doc(icms_basico(itens=[
            {"COD_ITEM": "P1", "VL_ICMS": "9,99"},          # errado
            {"COD_ITEM": "P2"}, {"COD_ITEM": "P3"}]))
        doc.recalcular_icms_itens()
        i = doc._ix("C170", "VL_ICMS")
        self.assertEqual({r.valor(i) for r in doc.registros
                          if r.reg == "C170"}, {"1,80"})
        antes = doc.gerar_texto()
        doc.recalcular_icms_itens()
        self.assertEqual(doc.gerar_texto(), antes)
        self.assertBemFormado(doc)

    def test_icms_st_nao_e_tocado(self):
        doc = _doc(icms_basico(itens=[
            {"COD_ITEM": "P1", "VL_BC_ICMS_ST": "12,00",
             "VL_ICMS_ST": "0,50"}]))
        doc.recalcular_icms_itens()
        r = next(r for r in doc.registros if r.reg == "C170")
        self.assertEqual(r.valor(doc._ix("C170", "VL_ICMS_ST")), "0,50")


class TestC190EmMassa(Base):

    def test_so_os_documentos_com_reducao_zerada(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "CST_ICMS": "020",
                                "VL_BC_ICMS": "6,00", "VL_ICMS": "1,08"}])
        _alterar(m, "C190", CST_ICMS="020", VL_OPR="10,00",
                 VL_BC_ICMS="6,00", VL_ICMS="1,08", VL_RED_BC="0")
        doc = _doc(m)
        self.assertEqual(len(doc.documentos_c190_com_reducao_zerada()), 1)
        doc.consolidar_c190_em_massa()
        self.assertEqual(doc.documentos_c190_com_reducao_zerada(), [])
        c190 = next(r for r in doc.registros if r.reg == "C190")
        self.assertEqual(c190.valor(doc._ix("C190", "VL_RED_BC")), "4,00")
        self.assertBemFormado(doc)


class TestAlterarDatas(Base):

    def test_data_fixa_so_no_filtro(self):
        doc = _doc(icms_basico())
        doc.alterar_datas_c100(
            campo_filtro="DT_E_S", data_ini=datetime.date(2026, 8, 1),
            data_fim=datetime.date(2026, 8, 31),
            campos_alterar=("DT_E_S",), modo="especifica",
            valor=datetime.date(2026, 8, 10))
        c100 = next(r for r in doc.registros if r.reg == "C100")
        self.assertEqual(c100.valor(doc._ix("C100", "DT_E_S")), "10082026")
        self.assertEqual(c100.valor(doc._ix("C100", "DT_DOC")), "05082026")
        self.assertBemFormado(doc)

    def test_fora_do_intervalo_nao_muda(self):
        doc = _doc(icms_basico())
        doc.alterar_datas_c100(
            campo_filtro="DT_E_S", data_ini=datetime.date(2026, 9, 1),
            data_fim=datetime.date(2026, 9, 30),
            campos_alterar=("DT_E_S",), modo="dias", valor=3)
        c100 = next(r for r in doc.registros if r.reg == "C100")
        self.assertEqual(c100.valor(doc._ix("C100", "DT_E_S")), "06082026")


class TestCadeiaIcms(Base):
    """O recálculo de ICMS refaz C190 e totais **só** de quem mudou."""

    def test_so_o_documento_alterado(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "VL_ICMS": "9,99"},
                               {"COD_ITEM": "P2"}, {"COD_ITEM": "P3"}])
        # segundo documento, correto, com C190 propositalmente diferente
        # do que o recálculo produziria (VL_RED_BC "0" em vez de "0,00")
        nomes = m.tabela
        c100 = next(c for c in m.linhas if c[0] == "C100")
        idx = max(i for i, c in enumerate(m.linhas) if c[0] == "C190")
        novo_c100 = list(c100)
        novo_c100[nomes["C100"].index("NUM_DOC")] = "124"
        # o item correto (P2), não o P1 com o ICMS errado
        c170 = [c for c in m.linhas if c[0] == "C170"][1]
        c190 = next(c for c in m.linhas if c[0] == "C190")
        c190_b = list(c190)
        c190_b[nomes["C190"].index("VL_OPR")] = "10,00"
        c190_b[nomes["C190"].index("VL_BC_ICMS")] = "10,00"
        c190_b[nomes["C190"].index("VL_ICMS")] = "1,80"
        m.linhas[idx + 1:idx + 1] = [novo_c100, list(c170), c190_b]
        doc = _doc(m)
        segundo = [r for r in doc.registros if r.reg == "C100"][1]
        antes = [f.linha_sped() for f in segundo.filhos]
        r = doc.recalcular_icms_itens(refazer_c190=True)
        self.assertEqual(r["c190_refeitos"], 1)
        self.assertEqual([f.linha_sped() for f in segundo.filhos], antes)
        primeiro = [r for r in doc.registros if r.reg == "C100"][0]
        (c190_1,) = [f for f in primeiro.filhos if f.reg == "C190"]
        self.assertEqual(c190_1.valor(doc._ix("C190", "VL_ICMS")), "5,40")
        self.assertBemFormado(doc)


if __name__ == "__main__":
    unittest.main()

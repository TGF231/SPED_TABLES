# -*- coding: utf-8 -*-
"""As correções que **gravam** no arquivo, uma a uma.

Cada teste confere três coisas: o conserto acontece, a segunda passada não
mexe em mais nada (idempotência) e o arquivo continua bem formado — mesma
largura de registro e bloco 9 fechando depois de salvar e reabrir.
"""

import datetime
import os
import unittest

from sped_tables.dominio import validacao
from sped_tables.dominio.sped_model import CamposInvalidos, SpedDocument
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


class TestNulos(Base):
    """O "vazio" por extenso é erro de leiaute em qualquer campo, e quem
    corrige é o normalizar — desde a 0.56.0 não há ação à parte."""

    def _nulos(self, doc):
        return sorted((o.reg, o.campo) for o in validacao.validar(doc)
                      if o.sugestao == "" and "vazio" in o.motivo)

    def test_validacao_acusa_e_normalizar_esvazia(self):
        m = _alterar(icms_basico(), "0200", CEST="NULL", COD_GEN="#N/A",
                     DESCR_ITEM="NULL")
        doc = _doc(m)
        # a descrição é texto livre: o domínio dela aceitaria "NULL"
        self.assertEqual(self._nulos(doc), [("0200", "CEST"),
                                            ("0200", "COD_GEN"),
                                            ("0200", "DESCR_ITEM")])
        validacao.normalizar(doc)
        self.assertEqual(self._nulos(doc), [])
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


class TestPlanilhaDeInventario(Base):
    """Célula numérica que não é número recusa a importação inteira, antes
    de mexer no arquivo — até a 0.56.0 virava zero e o item entrava com
    quantidade zerada."""

    def test_numero_de_celula(self):
        from sped_tables.dominio.sped_model import num_planilha_estrito
        for v, esperado in ((None, 0.0), ("", 0.0), (3, 3.0), (2.5, 2.5),
                            ("12,5", 12.5), ("1.234,56", 1234.56),
                            ("12.5", 12.5), (" -3 ", -3.0)):
            self.assertEqual(num_planilha_estrito(v), esperado, v)
        for v in ("abc", "1.2.3", "NULL", "12,5,1", "1,234.56", True,
                  float("nan")):
            with self.assertRaises(ValueError, msg=repr(v)):
                num_planilha_estrito(v)

    def test_importacao_recusa_e_nao_mexe(self):
        from sped_tables.dominio.sped_model import CelulasInvalidas
        doc = _doc(icms_basico())
        antes = doc.gerar_texto()
        linhas = [{"cod_item": "P1", "qtd": "10", "vl_item": "100,00",
                   "_linha": 2},
                  {"cod_item": "P2", "qtd": "abc", "vl_item": "5",
                   "_linha": 3},
                  {"cod_item": "P3", "qtd": "1", "vl_item": "1",
                   "aliq_icms": "NULL", "_linha": 7}]
        with self.assertRaises(CelulasInvalidas) as ctx:
            doc.importar_inventario_h010(linhas, "31122025")
        self.assertEqual(ctx.exception.celulas,
                         [(3, "qtd", "abc"), (7, "aliq_icms", "NULL")])
        self.assertIn("linha 3, qtd = 'abc'", str(ctx.exception))
        self.assertEqual(doc.gerar_texto(), antes)
        # corrigida a planilha, importa
        linhas[1]["qtd"], linhas[2]["aliq_icms"] = "2", "18"
        res = doc.importar_inventario_h010(linhas, "31122025")
        self.assertEqual(res["itens"], 3)
        self.assertBemFormado(doc)


class TestNumerosInvalidos(Base):
    """Cálculo que grava recusa campo numérico que não é número do SPED —
    antes de mexer em qualquer coisa. Até a 0.55.0 o `NULL` num VL_ITEM era
    lido como zero e o total gravado saía errado, com cara de certo."""

    def _recusa_sem_mexer(self, doc, calculo):
        antes = doc.gerar_texto()
        with self.assertRaises(CamposInvalidos) as ctx:
            calculo()
        self.assertEqual(doc.gerar_texto(), antes)
        return ctx.exception

    def test_icms_recusa_nos_calculos_que_gravam(self):
        doc = _doc(_alterar(icms_basico(), "C170", VL_ITEM="NULL"))
        c100 = next(r for r in doc.registros if r.reg == "C100")
        exc = self._recusa_sem_mexer(doc, lambda: doc.consolidar_c190(c100))
        self.assertEqual([(r.reg, n, v) for r, n, v in exc.campos],
                         [("C170", "VL_ITEM", "NULL")])
        self.assertIn("C170 VL_ITEM = 'NULL'", str(exc))
        for calculo in (lambda: doc.consolidar_c190_em_massa([c100]),
                        lambda: doc.recalcular_totais_c100(c100),
                        doc.recalcular_totais_todos_c100,
                        lambda: doc.recalcular_icms_itens(refazer_c190=True)):
            self._recusa_sem_mexer(doc, calculo)

    def test_icms_dos_itens_confere_o_documento_inteiro(self):
        """Com `refazer_c190`, o C190 e os totais leem todos os itens do
        documento — inclusive os que não foram escolhidos."""
        doc = _doc(_alterar(icms_basico(), "C100", VL_FRT="1.5.0"))
        c170 = next(r for r in doc.registros if r.reg == "C170")
        self._recusa_sem_mexer(doc, lambda: doc.recalcular_icms_itens(
            uids={c170.uid}, refazer_c190=True))
        # sem refazer o C190, o C100 não é lido: segue
        doc.recalcular_icms_itens(uids={c170.uid})

    def test_contribuicoes_recusa(self):
        doc = _doc(_alterar(contrib_basico(), "C170", VL_BC_PIS="12a"))
        self._recusa_sem_mexer(doc, doc.recalcular_bloco_m)
        self._recusa_sem_mexer(doc, lambda: doc.trocar_aliquotas_pis_cofins(
            aliq_pis=1.65, escopo="ambos"))

    def test_numero_valido_e_vazio_passam(self):
        doc = _doc(icms_basico())
        self.assertEqual(doc.numeros_invalidos(doc.registros), [])
        c100 = next(r for r in doc.registros if r.reg == "C100")
        self.assertIsNotNone(doc.consolidar_c190(c100))


if __name__ == "__main__":
    unittest.main()

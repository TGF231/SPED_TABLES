# -*- coding: utf-8 -*-
"""O adaptador da porta lendo a base de referência: versão do arquivo,
fora da base, vigência e tabelas."""

import unittest

from sped_tables.dominio import referencias, validacao
from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import base_referencia, tabelas_ncm
from sped_tables.infra.referencias_base import ReferenciasBase
from tests import base_teste
from tests.fabrica import PastaTemporaria, icms_basico

ZERO = ("versão=52 COD, DESC, DT_INI, DT_FIM, NCM, EXC, EX_IPI\n"
        "101|Hortícolas|01012009||0702;0703||\n")
MONO = ("versão=40 COD, DESC, DT_INI, DT_FIM, NCM, EXC, EX_IPI, UNID, "
        "ALIQ_PIS, ALIQ_COFINS\n"
        "201|Cerveja|01012009||2203||UN|1,00|2,00\n")


class TestReferenciasBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = PastaTemporaria()
        pasta = cls._tmp.__enter__()
        cls.origem = base_referencia.Base(base_teste.compilada(pasta))
        cls.fonte = ReferenciasBase(cls.origem)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def setUp(self):
        self._antes = referencias.definir(self.fonte)

    def tearDown(self):
        referencias.definir(self._antes)

    def test_estrutura_por_versao(self):
        est, info = self.fonte.estrutura("ICMS", "019")
        self.assertEqual(est["C100"]["campos"]["IND_EMIT"]["valores"],
                         ["0", "1"])
        self.assertEqual(info["versao"], "019")
        self.assertEqual(info["descritor"], "teste/ICMS/019")
        self.assertEqual(info["base"], "2026.10.1")
        self.assertEqual(info["registros"], 1)

    def test_sem_versao_vale_a_mais_recente(self):
        _est, info = self.fonte.estrutura("ICMS")
        self.assertEqual(info["versao"], "020")

    def test_fora_da_base(self):
        est, info = self.fonte.estrutura("ICMS", "014")
        self.assertEqual(est, {})
        self.assertTrue(info["fora_da_base"])
        self.assertIn("014", info["erro"])

    def test_versao_vigente(self):
        self.assertEqual(self.fonte.versao_vigente("ICMS", "31082026"), "020")
        self.assertEqual(self.fonte.versao_vigente("ICMS", "31082025"), "019")
        self.assertIsNone(self.fonte.versao_vigente("ICMS", "31082020"))

    def test_tabelas_pela_base(self):
        est = {"C170": {"campos": {"CFOP": {"datasource": "CFOP"}}}}
        dom, _f = self.fonte.dominios_por_datasource(est, "ICMS", "MG",
                                                     "31082026")
        self.assertEqual(dom[("C170", "CFOP")]["codigos"], {"1102", "5102"})
        self.assertIsNone(self.fonte.classificador_ncm())
        self.assertEqual(self.fonte.guia("ICMS")["versao"], "9.9")

    def test_manifesto_e_descricao(self):
        self.assertEqual(self.fonte.manifesto()["versao"], "2026.10.1")
        self.assertIn("2026.10.1", self.fonte.descricao())
        self.assertEqual(self.fonte.nome, "base de referência")

    def _ind_emit(self, cod_ver):
        """Ocorrências de domínio no IND_EMIT de um C100 com IND_EMIT=1."""
        m = icms_basico()
        m.alterar("0000", COD_VER=cod_ver)
        m.alterar("C100", IND_EMIT="1")
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(m.gravar(p))
        dominios, _info = validacao.dominios_do_documento(doc)
        return [o for o in validacao.validar(doc, dominios_pva=dominios)
                if o.reg == "C100" and o.campo == "IND_EMIT"]

    def test_arquivo_conferido_pela_propria_versao(self):
        """Na 020 inventada o IND_EMIT só aceita 0; na 019, 0 ou 1. O
        arquivo que declara 019 — mesmo com o período de 2026 — é conferido
        pela 019 e não é acusado."""
        self.assertEqual(self._ind_emit("019"), [])
        self.assertTrue(self._ind_emit("020"))

    def test_mutar_o_resultado_nao_contamina_a_base(self):
        """`Base.estrutura()` entrega o dicionário do próprio cache: o
        adaptador trabalha numa cópia, e quem mexer no que recebeu não
        altera a base nem as leituras de outro adaptador sobre ela."""
        mexida = ReferenciasBase(self.origem)
        est, _info = mexida.estrutura("ICMS", "019")
        est["C100"]["campos"]["IND_EMIT"]["valores"].append("9")
        est["C100"]["campos"]["IND_OPER"]["tamanho"] = "[7]"
        est.pop("C100")
        cru = self.origem.estrutura("ICMS", "019")
        self.assertEqual(cru["C100"]["campos"]["IND_EMIT"]["valores"],
                         ["0", "1"])
        self.assertEqual(cru["C100"]["campos"]["IND_OPER"]["tamanho"], "[1]")
        outro, _info = ReferenciasBase(self.origem).estrutura("ICMS", "019")
        self.assertEqual(outro["C100"]["campos"]["IND_EMIT"]["valores"],
                         ["0", "1"])
        # e a base continua com os nomes do descritor, sem alinhamento
        self.assertNotIn("id_pva", cru["C100"]["campos"]["IND_EMIT"])

    def test_a_estrutura_vem_alinhada_ao_leiaute(self):
        est, _info = self.fonte.estrutura("ICMS", "019")
        campo = est["C100"]["campos"]["IND_EMIT"]
        self.assertEqual(campo["pos"], 3)
        self.assertEqual(campo["id_pva"], "IND_EMIT")

    def test_a_estrutura_pedida_de_novo_e_a_mesma(self):
        a, _ = self.fonte.estrutura("ICMS", "019")
        b, _ = self.fonte.estrutura("ICMS", "019")
        self.assertIs(a, b)


class TestBaseIncompleta(unittest.TestCase):

    def test_leiaute_que_a_base_nao_tem(self):
        with PastaTemporaria() as p:
            fonte = ReferenciasBase(base_referencia.Base(base_teste.compilada(
                p, leiautes={"ICMS": {"020": ("01012026", "",
                                              base_teste.estrutura_c100("0"))
                                      }})))
            est, info = fonte.estrutura("CONTRIB", "006")
            self.assertEqual(est, {})
            self.assertIsNone(info["descritor"])
            self.assertIn("CONTRIB", info["erro"])
            self.assertEqual(fonte.estrutura("CONTRIB")[0], {})
            self.assertIsNone(fonte.versao_vigente("CONTRIB", "31082026"))

    def test_versoes_sobrepostas_vale_a_mais_nova(self):
        """Versão antiga sem data final continua "vigente" para sempre; a
        que começou depois dela é quem vale."""
        est = base_teste.estrutura_c100("0")
        with PastaTemporaria() as p:
            fonte = ReferenciasBase(base_referencia.Base(base_teste.compilada(
                p, leiautes={"ICMS": {"019": ("01012025", "", est),
                                      "020": ("01012026", "", est)}})))
            self.assertEqual(fonte.versao_vigente("ICMS", "30062025"), "019")
            self.assertEqual(fonte.versao_vigente("ICMS", "30062026"), "020")
            self.assertIsNone(fonte.versao_vigente("ICMS", "31122024"))
            self.assertIsNone(fonte.versao_vigente("ICMS", ""))

    def test_classificador_ncm_com_as_tabelas_da_base(self):
        tabelas = {tabelas_ncm.CHAVE_ALIQ_ZERO: (ZERO, 52),
                   tabelas_ncm.CHAVE_MONO: (MONO, 40)}
        with PastaTemporaria() as p:
            fonte = ReferenciasBase(base_referencia.Base(base_teste.compilada(
                p, tabelas=tabelas, ncm=["07031019", "22030000"])))
            clf = fonte.classificador_ncm()
            self.assertTrue(clf.eh_aliquota_zero("07031019"))
            self.assertTrue(clf.eh_monofasico("22030000"))
            # montar custa a leitura das tabelas: uma vez só
            self.assertIs(fonte.classificador_ncm(), clf)


class OrigemQueConta:
    """Qualquer origem com a interface da base: conta as leituras."""

    def __init__(self):
        self.lidas = {"tabelas": 0, "ncm_vigente": 0}

    def manifesto(self):
        return {"versao": "9.9.9", "data": "2026-01-01"}

    def versoes(self, layout):
        return {}

    def estrutura(self, layout, versao):
        return None

    def tabelas(self):
        self.lidas["tabelas"] += 1
        return {tabelas_ncm.CHAVE_ALIQ_ZERO: (ZERO, 52)}

    def guia(self, layout):
        return {}

    def ncm_vigente(self):
        self.lidas["ncm_vigente"] += 1
        return None


class TestOrigemQualquer(unittest.TestCase):

    def test_funciona_sobre_qualquer_origem_com_a_interface(self):
        origem = OrigemQueConta()
        fonte = ReferenciasBase(origem, nome="pva de ensaio")
        self.assertEqual(fonte.nome, "pva de ensaio")
        self.assertIn("9.9.9", fonte.descricao())
        self.assertEqual(fonte.estrutura("ICMS")[0], {})
        clf = fonte.classificador_ncm()
        self.assertTrue(clf.eh_aliquota_zero("07031019"))
        fonte.classificador_ncm()
        self.assertEqual(origem.lidas, {"tabelas": 1, "ncm_vigente": 1})

    def test_naturezas_da_receita_ficam_guardadas(self):
        origem = OrigemQueConta()
        fonte = ReferenciasBase(origem)
        primeiro = fonte.ncms_da_natureza("999")
        tabela = fonte.tabela_natureza_receita("04")
        antes = origem.lidas["tabelas"]
        # a rotina pergunta por ocorrência: a segunda vez não relê a base
        self.assertIs(fonte.ncms_da_natureza("999"), primeiro)
        self.assertIs(fonte.tabela_natureza_receita("04"), tabela)
        self.assertEqual(origem.lidas["tabelas"], antes)


if __name__ == "__main__":
    unittest.main()

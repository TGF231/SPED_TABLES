# -*- coding: utf-8 -*-
"""Regras do guia prático com as condições e tolerâncias do PVA
(`dominio.regras_guia`)."""

import unittest

from sped_tables.dominio import diagnostico
from sped_tables.dominio import revisao
from sped_tables.dominio import regras_guia as G
from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import descritor_pva
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


def _regra(rid):
    return next(r for r in G.REGRAS if r.id == rid)


def _achados(rid, doc):
    return _regra(rid).verificar(doc)


class TestArquivoLimpo(unittest.TestCase):

    def test_fabrica_passa_em_todas(self):
        doc = _doc(icms_basico())
        for r in G.regras("ICMS"):
            with self.subTest(regra=r.id):
                self.assertEqual(r.verificar(doc), [])


class TestCfop(unittest.TestCase):

    def test_saida_em_documento_de_entrada(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "CFOP": "5102"}])
        m.alterar("C190", CFOP="5102", VL_BC_ICMS="10,00", VL_ICMS="1,80",
                 VL_OPR="10,00")
        ps = _achados("cfop_operacao", _doc(m))
        self.assertEqual({p.reg for p in ps}, {"C170", "C190"})

    def test_so_documento_regular_ou_extemporaneo(self):
        """A consulta do PVA confere CFOP só com COD_SIT 00/01."""
        m = icms_basico(itens=[{"COD_ITEM": "P1", "CFOP": "5102"}])
        m.alterar("C100", COD_SIT="08")
        self.assertEqual(_achados("cfop_operacao", _doc(m)), [])

    def test_itens_com_primeiro_digito_diferente(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "CFOP": "1102"},
                               {"COD_ITEM": "P2", "CFOP": "2102"}])
        ps = _achados("cfop_operacao", _doc(m))
        self.assertEqual([p.reg for p in ps], ["C100"])

    def test_nfce_so_com_5(self):
        m = icms_basico()
        m.alterar("C100", IND_OPER="1", IND_EMIT="0", COD_MOD="65",
                 COD_SIT="08")
        m.alterar("C190", CFOP="6102")
        (p,) = [x for x in _achados("cfop_operacao", _doc(m))
                if x.reg == "C190"]
        self.assertIn("NFC-e", p.descricao)


class TestAnaliticoEItens(unittest.TestCase):

    def test_combinacao_sem_par_nos_dois_sentidos(self):
        m = icms_basico()
        m.alterar("C190", ALIQ_ICMS="12")
        ps = _achados("c190_c170", _doc(m))
        self.assertEqual(sorted(p.reg for p in ps),
                         ["C170", "C170", "C170", "C190"])

    def test_nfe_de_emissao_propria_fica_fora(self):
        m = icms_basico()
        m.alterar("C100", IND_EMIT="0")
        m.alterar("C190", ALIQ_ICMS="12")
        self.assertEqual(_achados("c190_c170", _doc(m)), [])

    def test_soma_com_a_tolerancia_do_pva(self):
        """R$ 0,40 de diferença passa (TOLERANCIA = 0,5); R$ 0,60 não."""
        m = icms_basico()
        m.alterar("C190", VL_ICMS="5,80")
        self.assertEqual(_achados("c190_soma", _doc(m)), [])
        m.alterar("C190", VL_ICMS="6,00")
        (p,) = _achados("c190_soma", _doc(m))
        self.assertIn("VL_ICMS 6,00 (itens: 5,40)", p.descricao)

    def test_totais_do_c100(self):
        m = icms_basico()
        m.alterar("C100", VL_ICMS="6,00")
        (p,) = _achados("soma_analiticos", _doc(m))
        self.assertEqual(p.reg, "C100")

    def test_vl_merc_so_abaixo_da_soma(self):
        m = icms_basico()
        m.alterar("C100", VL_MERC="31,00")
        self.assertEqual(_achados("c100_vl_merc", _doc(m)), [])
        m.alterar("C100", VL_MERC="29,00")
        self.assertEqual(len(_achados("c100_vl_merc", _doc(m))), 1)

    def test_quantidade_zero(self):
        m = icms_basico(itens=[{"COD_ITEM": "P1", "QTD": "0"}])
        m.alterar("C190", VL_BC_ICMS="10,00", VL_ICMS="1,80")
        self.assertEqual(len(_achados("qtd_item", _doc(m))), 1)
        m.alterar("C100", COD_SIT="06")
        self.assertEqual(_achados("qtd_item", _doc(m)), [])


class TestIdentificacao(unittest.TestCase):

    def test_digitos_e_brasil_sem_documento(self):
        m = icms_basico()
        m.alterar("0150", CNPJ="11444777000162")
        self.assertIn("CNPJ com dígito inválido",
                      _achados("identificacao", _doc(m))[0].descricao)
        m.alterar("0150", CNPJ="")
        self.assertIn("sem CNPJ nem CPF",
                      _achados("identificacao", _doc(m))[0].descricao)

    def test_municipio_de_outra_uf(self):
        m = icms_basico()
        m.alterar("0000", COD_MUN="3550308")          # São Paulo, UF MG
        (p,) = _achados("identificacao", _doc(m))
        self.assertIn("não é da UF MG", p.descricao)

    def test_validadores_de_dv(self):
        self.assertTrue(G.cpf_valido("52998224725"))
        self.assertFalse(G.cpf_valido("52998224724"))
        self.assertFalse(G.cnpj_valido("11111111111111"))


class TestChave(unittest.TestCase):

    def test_digito_e_coerencia(self):
        m = icms_basico()
        m.alterar("C100", CHV_NFE="31260811444777000161550010000001231000001230")
        self.assertIn("dígito verificador",
                      _achados("chave_nfe", _doc(m))[0].descricao)
        m.alterar("C100", NUM_DOC="124",
                 CHV_NFE="31260811444777000161550010000001231000001238")
        self.assertIn("número da chave 123",
                      _achados("chave_nfe", _doc(m))[0].descricao)

    def test_emissao_propria_e_do_informante(self):
        """A chave do fornecedor num documento declarado como emissão
        própria: o CNPJ da chave não é o do 0000."""
        m = icms_basico()
        m.alterar("C100", IND_EMIT="0")
        self.assertIn("CNPJ do emitente",
                      _achados("chave_nfe", _doc(m))[0].descricao)

    def test_obrigatoria_nos_modelos_55_e_65(self):
        m = icms_basico()
        m.alterar("C100", CHV_NFE="")
        self.assertIn("sem a chave",
                      _achados("chave_nfe", _doc(m))[0].descricao)


class TestPeriodoEDatas(unittest.TestCase):

    def test_data_depois_do_fim(self):
        m = icms_basico()
        m.alterar("C100", DT_DOC="01092026", DT_E_S="01092026")
        self.assertEqual(len(_achados("datas_fim", _doc(m))), 2)

    def test_meses_diferentes_no_0000(self):
        m = icms_basico()
        m.alterar("0000", DT_FIN="30092026")
        self.assertEqual(len(_achados("periodo_0000", _doc(m))), 1)


class TestContagens(unittest.TestCase):

    def test_9999_e_9900(self):
        doc = _doc(icms_basico())
        r9999 = next(r for r in doc.registros if r.reg == "9999")
        r9999.set_valor(doc._ix("9999", "QTD_LIN"), "1")
        r9900 = next(r for r in doc.registros if r.reg == "9900"
                     and r.valor(1) == "C170")
        r9900.set_valor(2, "9")
        textos = [p.descricao for p in _achados("bloco9", doc)]
        self.assertTrue(any("9999 informa 1" in t for t in textos))
        self.assertTrue(any("9900 do C170 informa 9" in t for t in textos))


class TestApuracao(unittest.TestCase):

    def _com_e110(self, **campos):
        m = icms_basico()
        base = dict.fromkeys(SpedDocument.CAMPOS_E110, "0")
        base.update(VL_TOT_DEBITOS="0", VL_TOT_CREDITOS="5,40",
                    VL_SLD_CREDOR_TRANSPORTAR="5,40")
        base.update(campos)
        m.reg("E110", **base)
        return m

    def test_e110_coerente(self):
        self.assertEqual(_achados("apuracao_e110", _doc(self._com_e110())),
                         [])

    def test_saldo_e_e116(self):
        m = self._com_e110(VL_TOT_DEBITOS="100,00",
                           VL_SLD_CREDOR_TRANSPORTAR="0")
        textos = [p.descricao for p in _achados("apuracao_e110", _doc(m))]
        self.assertTrue(any(t.startswith("VL_SLD_APURADO 0,00") for t in
                            textos), textos)
        # nada a recolher declarado: o E116 vazio está coerente com o E110
        self.assertEqual(_achados("e116", _doc(m)), [])
        m = self._com_e110(VL_TOT_DEBITOS="100,00", VL_SLD_APURADO="94,60",
                           VL_ICMS_RECOLHER="94,60",
                           VL_SLD_CREDOR_TRANSPORTAR="0")
        self.assertEqual(_achados("apuracao_e110", _doc(m)), [])
        (p,) = _achados("e116", _doc(m))
        self.assertIn("E116 soma 0,00", p.descricao)

    def test_recalculo_corrige_o_que_a_regra_acusa(self):
        """Total de ajuste diferente dos E111: o recálculo grava a soma, e a
        regra que o acusava deixa de acusar — a mesma função nos dois."""
        m = self._com_e110(VL_TOT_AJ_DEBITOS="10,00",
                           VL_SLD_CREDOR_TRANSPORTAR="0")
        doc = _doc(m)
        self.assertTrue(_achados("apuracao_e110", doc))
        mudou = doc.recalcular_e110()
        self.assertEqual(mudou["VL_TOT_AJ_DEBITOS"], (10.0, 0.0))
        self.assertEqual(_achados("apuracao_e110", doc), [])

    def test_deducao_maior_que_o_saldo_vai_para_o_credor(self):
        """Saldo 100, dedução 150: recolhe 0 e transporta 50 (campo 14 do
        guia). Até a 1.0.0-rc.1 o recálculo transportava 0."""
        v = dict.fromkeys(SpedDocument.CAMPOS_E110, 0.0)
        v.update(VL_TOT_DEBITOS=100.0, VL_TOT_DED=150.0)
        self.assertEqual(SpedDocument.saldos_e110(v), {
            "VL_SLD_APURADO": 100.0, "VL_ICMS_RECOLHER": 0.0,
            "VL_SLD_CREDOR_TRANSPORTAR": 50.0})


class TestInventario(unittest.TestCase):

    def test_vl_inv(self):
        m = icms_basico()
        m.reg("H005", DT_INV="31072026", VL_INV="100,00", MOT_INV="01")
        m.reg("H010", COD_ITEM="P1", UNID="UN", QTD="1", VL_UNIT="90",
              VL_ITEM="90,00", IND_PROP="0")
        self.assertEqual(len(_achados("inventario", _doc(m))), 1)
        m.alterar("H005", VL_INV="90,30")              # tolerância 0,5
        self.assertEqual(_achados("inventario", _doc(m)), [])


class TestContribuicoes(unittest.TestCase):

    def test_valor_com_a_tolerancia_e_como_advertencia(self):
        m = contrib_basico()
        m.alterar("C170", 1, VL_PIS="5,45")       # calculado 4,95
        self.assertEqual(_achados("valor_contribuicao", _doc(m)), [])
        m.alterar("C170", 1, VL_PIS="6,00")
        (p,) = _achados("valor_contribuicao", _doc(m))
        self.assertEqual(p.gravidade, "aviso")

    def test_unidade_com_descricao_igual(self):
        m = contrib_basico()
        m.reg("0190", UNID="UN", DESCR="UN")
        self.assertEqual(len(_achados("unidade_0190", _doc(m))), 1)


class TestDiagnostico(unittest.TestCase):

    def test_achado_com_o_modulo_da_regra(self):
        m = icms_basico()
        m.alterar("C190", VL_ICMS="6,00")
        achados, _info = diagnostico.verificar(_doc(m))
        a = next(a for a in achados if a.tipo == "guia_c190_soma")
        self.assertEqual(diagnostico.MODULOS[a.tipo][0],
                         "Recalcular C190 (analítico)")


class TestRevisaoDeCodigo(unittest.TestCase):
    """Achados da revisão de código da 1.0.0-rc.2."""

    def test_largura_pela_posicao_nao_pelo_n(self):
        """O 0220 do PVA declara `n=3` duas vezes; a largura é 4."""
        est = {"0220": {"campos": {
            "REG": {"n": 1, "pos": 1}, "UNID_CONV": {"n": 2, "pos": 2},
            "FAT_CONV": {"n": 3, "pos": 3}, "COD_BARRA": {"n": 3, "pos": 4}}}}
        self.assertEqual(diagnostico._num_campos_descritor(est),
                         {"0220": 4})

    def test_diagnostico_sem_pva_roda_as_regras_do_guia(self):
        from sped_tables.dominio import referencias
        antes = referencias.definir(None)          # fonte vazia: sem PVA
        try:
            m = icms_basico()
            m.alterar("C190", VL_ICMS="6,00")
            achados, info = diagnostico.verificar(_doc(m))
        finally:
            referencias.definir(antes)
        self.assertTrue(info["sem_pva"])
        self.assertIn("guia_c190_soma", {a.tipo for a in achados})

    def test_saida_depois_do_periodo_conta_uma_vez(self):
        """O limite superior é da regra do guia (todo C100, extemporâneo
        inclusive); o inferior da saída, da verificação própria."""
        for sit in ("00", "01"):
            m = icms_basico()
            m.alterar("C100", IND_OPER="1", IND_EMIT="0", COD_SIT=sit,
                     DT_E_S="01092026")
            doc = _doc(m)
            self.assertEqual(len(_achados("datas_fim", doc)), 1, sit)
            self.assertEqual(revisao.verificar_data_fora_periodo(doc), [])

    def test_chave_de_terceiro_de_outro_emitente(self):
        m = icms_basico()
        m.alterar("0150", CNPJ="11222333000181")        # outro CNPJ
        (p,) = _achados("chave_nfe", _doc(m))
        self.assertIn("não é o participante F1", p.descricao)
        m.alterar("C100", COD_SIT="08")                 # regime especial
        self.assertEqual(_achados("chave_nfe", _doc(m)), [])

    def test_chave_propria_da_filial_no_contribuicoes(self):
        """Nota própria da filial noutra UF: UF e CNPJ são os do
        estabelecimento (C010/0140), não os do 0000."""
        filial = "11444777000242"
        self.assertTrue(G.cnpj_valido(filial))
        base = "3526081144477700024255001000000002100000002"
        chave = next(base + d for d in "0123456789"
                     if G.chave_dfe_valida(base + d))
        m = contrib_basico(bloco_m=False)
        m.reg("0140", COD_EST="2", NOME="FILIAL", CNPJ=filial, UF="SP",
              COD_MUN="3550308")
        m.reg("C010", CNPJ=filial, IND_ESCRI="2")
        m.reg("C100", IND_OPER="1", IND_EMIT="0", COD_MOD="55", COD_SIT="00",
              SER="1", NUM_DOC="2", CHV_NFE=chave, DT_DOC="05082026",
              DT_E_S="05082026", VL_DOC="1,00", IND_PGTO="0",
              VL_MERC="1,00", IND_FRT="9")
        doc = _doc(m)
        c100 = [r for r in doc.registros if r.reg == "C100"][-1]
        self.assertEqual(c100.pai.reg, "C010")
        ps = [p for p in _achados("chave_nfe", doc) if p.uid == c100.uid]
        self.assertEqual(ps, [])

    def test_debitos_do_e110_5605_1605_e_periodo(self):
        m = icms_basico()
        m.alterar("C100", IND_OPER="1", IND_EMIT="0")
        m.alterar("C170", 0, CFOP="5605")
        m.alterar("C170", 1, CFOP="5605")
        m.alterar("C170", 2, CFOP="5605")
        m.alterar("C190", CFOP="5605")
        m.reg("C100", IND_OPER="0", IND_EMIT="1", COD_PART="F1", COD_MOD="01",
              COD_SIT="00", SER="1", NUM_DOC="9", DT_DOC="10082026",
              DT_E_S="10082026", VL_DOC="0", IND_PGTO="0")
        m.reg("C190", CST_ICMS="090", CFOP="1605", ALIQ_ICMS="0",
              VL_OPR="0", VL_BC_ICMS="0", VL_ICMS="7,00")
        doc = _doc(m)
        # a 5605 sai dos débitos; a 1605 entra
        self.assertEqual(doc.debitos_icms_por_situacao(), (7.0, 0.0))
        # fora do período do E100, o documento regular não entra
        self.assertEqual(doc.debitos_icms_por_situacao(
            ("20260801", "20260805")), (0.0, 0.0))

    def test_recalculo_com_dois_periodos_de_apuracao(self):
        m = icms_basico()
        m.alterar("C100", IND_OPER="1", IND_EMIT="0")
        for k in range(3):
            m.alterar("C170", k, CFOP="5102")
        m.alterar("C190", CFOP="5102")
        zero = dict.fromkeys(SpedDocument.CAMPOS_E110, "0")
        m.linhas = [c for c in m.linhas if c[0] != "E100"]
        m.reg("E100", DT_INI="01082026", DT_FIN="15082026")
        m.reg("E110", **zero)
        m.reg("E100", DT_INI="16082026", DT_FIN="31082026")
        m.reg("E110", **zero)
        doc = _doc(m)
        mudou = doc.recalcular_e110()
        # o documento é de 06/08: o débito vai para o primeiro período só
        self.assertEqual(mudou["01/08–15/08 VL_TOT_DEBITOS"], (0.0, 5.4))
        self.assertFalse(any(k.startswith("16/08") and "DEBITOS" in k
                             for k in mudou))
        self.assertEqual(revisao.verificar_e110_debitos(doc), [])

    def test_documentos_que_o_recalcular_c190_refaz(self):
        m = icms_basico()
        m.alterar("C190", VL_ICMS="6,00")
        doc = _doc(m)
        (c100,) = G.documentos_c190_divergentes(doc)
        self.assertEqual(c100.reg, "C100")
        doc.consolidar_c190_em_massa([c100])
        self.assertEqual(G.documentos_c190_divergentes(doc), [])


@unittest.skipUnless(descritor_pva.disponivel(), "PVA não instalado")
class TestValidadoresDoPva(unittest.TestCase):

    def test_ids_existem_no_descritor(self):
        """Todo id em `pva` existe no descritor de algum leiaute — erro de
        digitação ali faria o diagnóstico continuar listando a regra como
        "só o PVA verifica"."""
        todos = set()
        for layout in ("ICMS", "CONTRIB"):
            est, _info = descritor_pva.carregar(layout)
            for d in est.values():
                todos |= set(d.get("validadores", ()))
        self.assertEqual(G.validadores_reproduzidos() - todos, set())


if __name__ == "__main__":
    unittest.main()

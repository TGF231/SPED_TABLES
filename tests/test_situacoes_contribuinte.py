# -*- coding: utf-8 -*-
"""Situações do contribuinte que um supermercado real trouxe (cliente B,
setembro) e que o programa não tratava — tudo sintético aqui:

* CSOSN do fornecedor do Simples no CST do ICMS das entradas, convertido
  pela tabela do cadastro da empresa (o C190 acompanha);
* código de receita em branco no E116 (do cadastro) e no M205/M605 (da
  regra do regime);
* NFC-e emitida no mês anterior e autorizada neste: data do XML, situação
  01 e o ICMS dela como débito especial no E110.
"""

import os
import unittest

from sped_tables.dominio import conferencia as cf
from sped_tables.dominio import empresas, revisao, rotinas
from sped_tables.dominio import xml_fiscal
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import (CNPJ_TESTE, Montador, PastaTemporaria,
                           contrib_basico, icms_basico, nfe_xml)


def _doc(m):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(m.gravar(p))


def _rotina(rid):
    return next(r for r in rotinas.ROTINAS if r.id == rid)


def _val(doc, reg, campo, r=None):
    r = r or next(x for x in doc.registros if x.reg == reg)
    return r.valor(doc._ix(reg, campo))


class TestCadastro(unittest.TestCase):

    def test_csosn_pela_tabela_e_compra_com_st(self):
        e = empresas.Empresa(cnpj=CNPJ_TESTE)
        self.assertEqual(e.cst_do_csosn("102", "1102"), "000")
        self.assertEqual(e.cst_do_csosn("202", "1403"), "060")
        self.assertEqual(e.cst_do_csosn("999", "1102"), None)
        e.origem_csosn, e.cst_compra_st = "2", ""
        self.assertEqual(e.cst_do_csosn("202", "1403"), "210")

    def test_tabela_digitada_e_cadastro_antigo(self):
        t = empresas.tabela_csosn_de_texto("102=0, 202 = 10")
        self.assertEqual(t, {"102": "00", "202": "10"})
        self.assertEqual(empresas.tabela_csosn_de_texto(
            empresas.tabela_csosn_texto(t)), t)
        with self.assertRaises(ValueError):
            empresas.tabela_csosn_de_texto("102-00")
        # empresas.json de antes destes campos: valem os padrões
        e = empresas.de_registro(CNPJ_TESTE, {"nome": "X"})
        self.assertTrue(e.converter_csosn)
        self.assertEqual(e.csosn_cst["102"], "00")


def _icms_simples():
    """Entrada com dois itens do fornecedor do Simples (CSOSN 102 copiado)
    e um C190 de CST 070 que já é válido e não pode ser tocado."""
    m = icms_basico(itens=[
        {"COD_ITEM": "P1", "CST_ICMS": "102", "VL_BC_ICMS": "0",
         "ALIQ_ICMS": "0", "VL_ICMS": "0"},
        {"COD_ITEM": "P2", "CST_ICMS": "102", "CFOP": "1102",
         "VL_BC_ICMS": "0", "ALIQ_ICMS": "0", "VL_ICMS": "0"},
        {"COD_ITEM": "P3", "CST_ICMS": "070", "CFOP": "1403",
         "VL_BC_ICMS": "0", "ALIQ_ICMS": "0", "VL_ICMS": "0"}])
    m.linhas = [c for c in m.linhas if c[0] != "C190"]
    # o ERP gravou dois C190 com o CSOSN (um por alíquota escrita de jeito
    # diferente) — depois da troca eles têm a mesma chave e viram um só
    for aliq, opr in (("0", "15,00"), ("0,00", "5,00")):
        m.reg("C190", CST_ICMS="102", CFOP="1102", ALIQ_ICMS=aliq,
              VL_OPR=opr, VL_BC_ICMS="0", VL_ICMS="0", VL_BC_ICMS_ST="0",
              VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
    m.reg("C190", CST_ICMS="070", CFOP="1403", ALIQ_ICMS="0",
          VL_OPR="10,00", VL_BC_ICMS="0", VL_ICMS="0", VL_BC_ICMS_ST="0",
          VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
    return m


class TestCsosn(unittest.TestCase):

    def test_troca_no_c170_e_no_c190(self):
        doc = _doc(_icms_simples())
        e = empresas.Empresa(cnpj=CNPJ_TESTE)
        r = _rotina("csosn_cst")
        oc, erro = rotinas.executar(doc, e, r)
        self.assertEqual(erro, "")
        self.assertEqual(sorted((o.reg, o.atual, o.esperado) for o in oc),
                         [("C170", "102", "000")] * 2
                         + [("C190", "102", "000")] * 2)
        self.assertEqual(r.corrigir(doc, e, oc), 4)
        c190 = [x for x in doc.registros if x.reg == "C190"]
        # os dois C190 de CSOSN viraram um só, somado; o 070 ficou
        self.assertEqual(sorted((_val(doc, "C190", "CST_ICMS", x),
                                 _val(doc, "C190", "VL_OPR", x))
                                for x in c190),
                         [("000", "20,00"), ("070", "10,00")])
        self.assertEqual(revisao.verificar_cst_combustivel_sem_aliquota(doc),
                         [])
        self.assertEqual(revisao.verificar_chave_duplicada(doc), [])

    def test_sem_conversao_no_cadastro_so_aponta(self):
        doc = _doc(_icms_simples())
        e = empresas.Empresa(cnpj=CNPJ_TESTE, converter_csosn=False)
        oc, _erro = rotinas.executar(doc, e, _rotina("csosn_cst"))
        self.assertTrue(oc)
        self.assertEqual({o.esperado for o in oc}, {""})
        self.assertEqual(_rotina("csosn_cst").corrigir(doc, e, oc), 0)


class TestCodigoDeReceita(unittest.TestCase):

    def test_e116_pelo_cadastro(self):
        m = icms_basico()
        m.reg("E110", VL_TOT_DEBITOS="0")
        m.reg("E116", COD_OR="000", VL_OR="10,00", DT_VCTO="10092026",
              COD_REC="", MES_REF="082026")
        doc = _doc(m)
        e = empresas.Empresa(cnpj=CNPJ_TESTE, cod_rec_icms="1206")
        oc, _erro = rotinas.executar(doc, e, _rotina("cod_rec"))
        self.assertEqual([o.esperado for o in oc], ["1206"])
        _rotina("cod_rec").corrigir(doc, e, oc)
        self.assertEqual(_val(doc, "E116", "COD_REC"), "1206")

    def test_m205_m605_pela_regra(self):
        m = contrib_basico()
        m.reg("M205", NUM_CAMPO="08", COD_REC="", VL_DEBITO="1,00")
        m.reg("M605", NUM_CAMPO="08", COD_REC="", VL_DEBITO="2,00")
        doc = _doc(m)
        oc, _erro = rotinas.executar(doc, None, _rotina("cod_rec"))
        self.assertEqual(sorted((o.reg, o.esperado) for o in oc),
                         [("M205", "691201"), ("M605", "585601")])


class TestReducaoPeloXmlDeCompra(unittest.TestCase):
    """Entrada com CST 070: ICMS por ST, sem base própria no arquivo. A
    redução sai do XML do fornecedor (a base reduzida de cada item)."""

    def test_c190_x70_pela_base_do_xml(self):
        x70 = {"CST_ICMS": "070", "CFOP": "1403", "VL_BC_ICMS": "0",
               "ALIQ_ICMS": "0", "VL_ICMS": "0"}
        m = icms_basico(itens=[dict(x70, COD_ITEM="P%d" % i)
                               for i in (1, 2, 3)])
        m.linhas = [c for c in m.linhas if c[0] != "C190"]
        m.reg("C190", CST_ICMS="070", CFOP="1403", ALIQ_ICMS="0",
              VL_OPR="30,00", VL_BC_ICMS="0", VL_ICMS="0",
              VL_BC_ICMS_ST="0", VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
        doc = _doc(m)
        self.assertEqual(len(revisao.verificar_c190_reducao(doc)), 1)
        with PastaTemporaria() as p:
            with open(os.path.join(p, "n.xml"), "w", encoding="utf-8") as f:
                f.write(nfe_xml(itens=[{"CST": "70", "vBC": "8.00",
                                        "pICMS": "18.00", "vICMS": "1.44"}]
                                * 3))
            nfes = xml_fiscal.ler_pasta_fiscal(p).nfes
        achados = cf.reducao_c190_pelo_xml(doc, nfes)
        self.assertEqual([a["esperado"] for a in achados], ["6,00"])
        self.assertEqual(cf.corrigir_reducao_c190(doc, achados), 1)
        self.assertEqual(_val(doc, "C190", "VL_RED_BC"), "6,00")
        self.assertEqual(revisao.verificar_c190_reducao(doc), [])


class TestEntradaExportadaPeloErp(unittest.TestCase):
    """O XML que o ERP exporta da entrada: sem chave, o fornecedor no
    `dest`, e a redução só no percentual (`pRedBC`), com `vBC` zerado."""

    def test_casa_pelo_fornecedor_e_valor_e_usa_o_percentual(self):
        x70 = {"CST_ICMS": "070", "CFOP": "1403", "VL_BC_ICMS": "0",
               "ALIQ_ICMS": "0", "VL_ICMS": "0"}
        m = icms_basico(itens=[dict(x70, COD_ITEM="P1")])
        m.linhas = [c for c in m.linhas if c[0] != "C190"]
        c100 = next(c for c in m.linhas if c[0] == "C100")
        nomes = m.tabela["C100"]
        c100[nomes.index("VL_DOC")] = "10,00"
        c100[nomes.index("CHV_NFE")] = ""
        m.reg("C190", CST_ICMS="070", CFOP="1403", ALIQ_ICMS="0",
              VL_OPR="10,00", VL_BC_ICMS="0", VL_ICMS="0",
              VL_BC_ICMS_ST="0", VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
        doc = _doc(m)
        xml = nfe_xml(itens=[{"CST": "70", "vBC": "0.00"}],
                      emit=(CNPJ_TESTE, "EMPRESA TESTE LTDA"),
                      dest=("11444777000161", "FORNECEDOR TESTE"))
        xml = xml.replace(
            'Id="NFe31260811444777000161550010000001231000001238"',
            'Id="NFe"').replace(
            "<vBC>0.00</vBC>", "<pRedBC>33.33</pRedBC><vBC>0.00</vBC>")
        with PastaTemporaria() as p:
            with open(os.path.join(p, "84336.xml"), "w",
                      encoding="utf-8") as f:
                f.write(xml)
            lote = xml_fiscal.ler_pasta_fiscal(p)
        self.assertEqual((len(lote.nfes), len(lote.sem_chave)), (0, 1))
        achados = cf.reducao_c190_pelo_xml(doc, lote.sem_chave)
        self.assertEqual([a["esperado"] for a in achados], ["3,33"])


class TestBlocoMCodigoDeReceita(unittest.TestCase):

    def test_m205_acompanha_o_valor_a_recolher(self):
        """O recálculo do M200 deixava o M205 com o débito antigo, e o PVA
        acusava MSG_VALIDA_DET_RECEITA_DCTF."""
        m = contrib_basico()
        m.reg("M205", NUM_CAMPO="08", COD_REC="691201", VL_DEBITO="999,99")
        doc = _doc(m)
        doc.recalcular_bloco_m(naturezas={"1102": "01"})
        i = doc._ix("M200", "VL_CONT_NC_REC")
        m200 = next(r for r in doc.registros if r.reg == "M200")
        self.assertEqual(_val(doc, "M205", "VL_DEBITO"), m200.valor(i))


class TestBebidasFrias(unittest.TestCase):
    """Cerveja vendida pelo varejista: CST 06 com natureza 918 (Lei
    13.097/2015). O ERP gravou 423/424 — códigos da tabela de monofásicos,
    da venda do fabricante — sob o CST 06."""

    def _doc_e_fonte(self):
        from sped_tables.dominio import referencias

        class Fonte(referencias.Referencias):
            def naturezas_receita(self, cst, data_ref=None):
                return {"06": {"918", "105"}, "04": {"423", "424"}}.get(cst)

            def ncms_da_natureza(self, codigo):
                return {"423": {"2203"}, "424": {"2203"}}.get(codigo, set())
        m = contrib_basico()
        m.reg("M400", CST_PIS="06", VL_TOT_REC="30,00")
        m.reg("M410", NAT_REC="918", VL_REC="20,00")
        m.reg("M410", NAT_REC="423", VL_REC="7,00")
        m.reg("M410", NAT_REC="424", VL_REC="3,00")
        return _doc(m), Fonte()

    def test_varejista_vai_para_918_somando(self):
        from sped_tables.dominio import referencias
        doc, fonte = self._doc_e_fonte()
        antes = referencias.definir(fonte)
        try:
            e = empresas.Empresa(cnpj=CNPJ_TESTE, atividade="comercio")
            oc, erro = rotinas.executar(doc, e, _rotina("nat_rec"))
            self.assertEqual([(o.atual, o.esperado) for o in oc],
                             [("423", "918"), ("424", "918")])
            self.assertEqual(_rotina("nat_rec").corrigir(doc, e, oc), 2)
            m410 = [(_val(doc, "M410", "NAT_REC", r),
                     _val(doc, "M410", "VL_REC", r))
                    for r in doc.registros if r.reg == "M410"]
            self.assertEqual(m410, [("918", "30,00")])
            self.assertEqual(revisao.verificar_nat_rec(doc), [])
        finally:
            referencias.definir(antes)

    def test_industria_so_aponta(self):
        from sped_tables.dominio import referencias
        doc, fonte = self._doc_e_fonte()
        antes = referencias.definir(fonte)
        try:
            e = empresas.Empresa(cnpj=CNPJ_TESTE, atividade="industria")
            oc, _erro = rotinas.executar(doc, e, _rotina("nat_rec"))
            self.assertEqual({o.esperado for o in oc}, {""})
        finally:
            referencias.definir(antes)


class TestVerificacoesDoPva(unittest.TestCase):

    def test_saida_antes_da_emissao(self):
        m = icms_basico()
        c100 = next(c for c in m.linhas if c[0] == "C100")
        c100[m.tabela["C100"].index("DT_E_S")] = "01082026"
        c100[m.tabela["C100"].index("DT_DOC")] = "05082026"
        self.assertEqual(len(revisao.verificar_data_es_antes_emissao(
            _doc(m))), 1)

    def test_natureza_da_receita_fora_da_tabela_do_cst(self):
        from sped_tables.dominio import referencias

        class Fonte(referencias.Referencias):
            def naturezas_receita(self, cst, data_ref=None):
                return {"06": {"105", "110"}, "04": {"423"}}.get(cst)
        m = contrib_basico()
        m.reg("M400", CST_PIS="06", VL_TOT_REC="10,00")
        m.reg("M410", NAT_REC="423", VL_REC="10,00")
        doc = _doc(m)
        antes = referencias.definir(Fonte())
        try:
            probs = revisao.verificar_nat_rec(doc)
        finally:
            referencias.definir(antes)
        self.assertEqual([p.descricao[:30] for p in probs],
                         ["M410 com NAT_REC 423, que não "])


CHAVE_AGOSTO = "31260811222333000181650010000000501000000500"


def _icms_nfce_extemporanea():
    """Setembro, com uma NFC-e emitida em agosto e o ERP pondo a data de
    setembro: ICMS 1,80 que tem de sair do débito do período."""
    m = Montador("ICMS")
    m.reg("0000", COD_VER="020", COD_FIN="0", DT_INI="01092026",
          DT_FIN="30092026", NOME="EMPRESA TESTE LTDA", CNPJ=CNPJ_TESTE,
          UF="MG", IE="0012345670012", COD_MUN="3106200", IND_PERFIL="A",
          IND_ATIV="1")
    m.reg("C100", IND_OPER="1", IND_EMIT="0", COD_MOD="65", COD_SIT="00",
          SER="1", NUM_DOC="50", CHV_NFE=CHAVE_AGOSTO, DT_DOC="02092026",
          DT_E_S="02092026", VL_DOC="10,00", IND_PGTO="0", VL_MERC="10,00",
          IND_FRT="9", VL_BC_ICMS="10,00", VL_ICMS="1,80")
    m.reg("C190", CST_ICMS="000", CFOP="5102", ALIQ_ICMS="18",
          VL_OPR="10,00", VL_BC_ICMS="10,00", VL_ICMS="1,80",
          VL_BC_ICMS_ST="0", VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
    m.reg("E100", DT_INI="01092026", DT_FIN="30092026")
    m.reg("E110", VL_TOT_DEBITOS="1,80", VL_AJ_DEBITOS="0",
          VL_TOT_AJ_DEBITOS="0", VL_ESTORNOS_CRED="0", VL_TOT_CREDITOS="0",
          VL_AJ_CREDITOS="0", VL_TOT_AJ_CREDITOS="0", VL_ESTORNOS_DEB="0",
          VL_SLD_CREDOR_ANT="0", VL_SLD_APURADO="1,80", VL_TOT_DED="0",
          VL_ICMS_RECOLHER="1,80", VL_SLD_CREDOR_TRANSPORTAR="0",
          DEB_ESP="0")
    return m


class TestExtemporanea(unittest.TestCase):

    def _nfes(self):
        with PastaTemporaria() as p:
            with open(os.path.join(p, "n.xml"), "w", encoding="utf-8") as f:
                f.write(nfe_xml(mod="65", chave=CHAVE_AGOSTO, nnf="50",
                                itens=[{}], dest=None,
                                dhemi="2026-08-30T21:00:00-03:00"))
            return xml_fiscal.ler_pasta_fiscal(p).nfes

    def test_data_do_xml_situacao_01_e_debito_especial(self):
        doc = _doc(_icms_nfce_extemporanea())
        achados = cf.datas_pelo_xml(doc, self._nfes())
        self.assertEqual(sorted((a["campo"], a["esperado"]) for a in achados),
                         [("COD_SIT", "01"), ("DT_DOC", "30082026"),
                          ("DT_E_S", "30082026")])
        self.assertEqual(cf.corrigir_datas_pelo_xml(doc, achados), (3, 1))
        self.assertEqual(cf.datas_pelo_xml(doc, self._nfes()), [])
        # o E110 do ERP ficou com o ICMS no débito do período
        self.assertEqual(len(revisao.verificar_e110_debitos(doc)), 2)
        mudou = doc.recalcular_e110()
        self.assertEqual(mudou["VL_TOT_DEBITOS"], (1.8, 0.0))
        self.assertEqual(mudou["DEB_ESP"], (0.0, 1.8))
        self.assertEqual(_val(doc, "E110", "VL_ICMS_RECOLHER"), "0,00")
        self.assertEqual(revisao.verificar_e110_debitos(doc), [])
        # e o recálculo num arquivo certo não muda nada
        self.assertEqual(doc.recalcular_e110(), {})


if __name__ == "__main__":
    unittest.main()

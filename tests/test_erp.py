# -*- coding: utf-8 -*-
"""Integração com o banco do ERP: o perfil (tabela e coluna de cada
informação), os adaptadores (SQLite e DBF aqui, de verdade; Firebird, SQL
Server e MySQL pelo SQL que montam) e o caminho até o SPED — 0200, 0150,
inventário e XMLs, pelos mesmos cálculos da planilha e da pasta.

Bancos de verdade dos outros tipos entram quando o ambiente aponta um
(`SPED_TABLES_ERP_FIREBIRD`, `SPED_TABLES_ERP_SQLSERVER`): ver TESTES.md.
"""

import base64
import contextlib
import datetime
import gzip
import json
import os
import sqlite3
import struct
import sys
import unittest
import zlib
from unittest import mock

from sped_tables.aplicacao import erp as caso
from sped_tables.dominio import erp, participantes
from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import bancos, segredos, sistemas_erp
from tests.fabrica import (CNPJ_TESTE, PastaTemporaria, icms_basico,
                           nfe_xml)

CHAVE_1 = "31260811444777000161550010000001231000001238"
CHAVE_2 = "31260811444777000161550010000001241000001240"


# ---------------------------------------------------------------- DBF
def gravar_dbf(caminho, campos, linhas, apagadas=(), memos=None):
    """DBF dBase III mínimo. `campos` = [(nome, tipo, tamanho, decimais)];
    `memos` = {texto: bloco} já gravados no .dbt ao lado."""
    tam_reg = 1 + sum(c[2] for c in campos)
    cab_tam = 32 + 32 * len(campos) + 1
    tipo_versao = 0x83 if any(c[1] == "M" for c in campos) else 0x03
    cab = struct.pack("<B3BIHH20x", tipo_versao, 126, 8, 1, len(linhas),
                      cab_tam, tam_reg)
    desc = b""
    for nome, tipo, tam, dec in campos:
        desc += struct.pack("<11sc4xBB14x", nome.encode("ascii"),
                            tipo.encode("ascii"), tam, dec)
    corpo = b""
    for n, ln in enumerate(linhas):
        reg = b"*" if n in apagadas else b" "
        for (nome, tipo, tam, dec), v in zip(campos, ln):
            if tipo == "N":
                s = ("%.*f" % (dec, v) if v is not None else "").rjust(tam)
            elif tipo == "D":
                s = v.strftime("%Y%m%d") if v else " " * 8
            elif tipo == "L":
                s = "T" if v else "F"
            elif tipo == "M":
                s = str(memos[v]).rjust(tam) if v else " " * tam
            else:
                s = (v or "").ljust(tam)
            reg += s.encode("cp850")[:tam].ljust(tam)
        corpo += reg
    with open(caminho, "wb") as fh:
        fh.write(cab + desc + b"\r" + corpo + b"\x1a")


def gravar_dbt(caminho, textos):
    """Memo dBase III: blocos de 512 bytes, texto terminado em 1A 1A.
    Devolve {texto: bloco}."""
    blocos, conteudo = {}, bytearray(512)
    for t in textos:
        blocos[t] = len(conteudo) // 512
        dado = t.encode("cp850") + b"\x1a\x1a"
        dado += b"\x00" * (-len(dado) % 512)
        conteudo += dado
    struct.pack_into("<I", conteudo, 0, len(conteudo) // 512)
    with open(caminho, "wb") as fh:
        fh.write(bytes(conteudo))
    return blocos


def _sistema_dbf():
    return erp.Sistema("ERP Clipper", "dbf", {
        "produtos": {"tabela": "PRODUTOS", "coluna_empresa": "EMPRESA",
                     "colunas": {"cod_item": "CODIGO", "descr_item": "DESCRI",
                                 "cod_ncm": "NCM", "unid": "UNID",
                                 "cod_barra": "EAN"}},
        "estoque": {"tabela": "PRODUTOS", "coluna_empresa": "EMPRESA",
                    "colunas": {"cod_item": "CODIGO", "qtd": "ESTOQUE",
                                "vl_unit": "CUSTO", "data": "DTSALDO"}},
        "xmls": {"tabela": "NOTAS",
                 "colunas": {"xml": "XML", "chave": "CHAVE",
                             "data": "EMISSAO"}},
    })


def _pasta_dbf(p):
    gravar_dbf(os.path.join(p, "PRODUTOS.DBF"),
               [("EMPRESA", "N", 3, 0), ("CODIGO", "C", 10, 0),
                ("DESCRI", "C", 30, 0), ("NCM", "C", 8, 0),
                ("UNID", "C", 3, 0), ("EAN", "C", 14, 0),
                ("ESTOQUE", "N", 12, 3), ("CUSTO", "N", 12, 2),
                ("DTSALDO", "D", 8, 0), ("ATIVO", "L", 1, 0)],
               [(1, "P1", "PRODUTO AÇÚCAR", "4012010", "UN", "", 5, 2.5,
                 datetime.date(2026, 8, 31), True),
                (1, "P2", "PRODUTO DOIS", "21069090", "UN", "7891234567895",
                 10, 1.0, datetime.date(2026, 8, 31), True),
                (2, "P1", "OUTRA EMPRESA", "99999999", "KG", "", 1, 1,
                 datetime.date(2026, 8, 31), True),
                (1, "P9", "APAGADO", "11111111", "UN", "", 1, 1, None,
                 False)],
               apagadas={3})
    xml1 = nfe_xml(chave=CHAVE_1)
    memos = gravar_dbt(os.path.join(p, "NOTAS.DBT"), [xml1])
    gravar_dbf(os.path.join(p, "NOTAS.DBF"),
               [("CHAVE", "C", 44, 0), ("EMISSAO", "D", 8, 0),
                ("XML", "M", 10, 0)],
               [(CHAVE_1, datetime.date(2026, 8, 5), xml1),
                ("", datetime.date(2026, 7, 31), xml1)], memos=memos)


class TestPerfil(unittest.TestCase):

    def test_sugere_pelo_nome_sem_pegar_pedaco_curto(self):
        cols = ["CODIGO", "DESCRICAO", "CLASFISCAL", "EAN", "UNIDADE",
                "CEST", "FUNCIONARIO", "TIPO"]
        s = erp.sugerir("produtos", cols)
        self.assertEqual(s["cod_item"], "CODIGO")
        self.assertEqual(s["descr_item"], "DESCRICAO")
        self.assertEqual(s["cod_ncm"], "CLASFISCAL")
        self.assertEqual(s["cod_barra"], "EAN")
        self.assertEqual(s["unid"], "UNIDADE")
        self.assertEqual(s["cest"], "CEST")
        self.assertNotIn("FUNCIONARIO", s.values())
        # contém (palavra de 4+ letras): "estoque_atual" -> quantidade
        self.assertEqual(erp.sugerir("estoque", ["COD", "ESTOQUE_ATUAL"])[
            "qtd"], "ESTOQUE_ATUAL")

    def test_problemas_e_ida_e_volta(self):
        s = _sistema_dbf()
        self.assertEqual(erp.problemas(s, "produtos"), [])
        self.assertTrue(erp.problemas(s, "participantes"))
        s.entidades["xmls"].colunas.pop("data")
        self.assertIn("Data de emissão", erp.problemas(s, "xmls")[0])
        volta = erp.Sistema.de_dict(json.loads(json.dumps(s.para_dict())))
        self.assertEqual(volta.para_dict(), s.para_dict())
        self.assertEqual(volta.ident, "erp_clipper")

    def test_consulta_propria_so_select(self):
        for ok in ("SELECT a FROM b", "  with x as (select 1) select * "
                   "from x;", "select * from t where a = ';'"[:22]):
            self.assertTrue(erp.sql_so_leitura(ok), ok)
        for ruim in ("DELETE FROM PRODUTOS", "SELECT 1; DROP TABLE X",
                     "SELECT 1 -- x", "SELECT /* */ 1", "", "UPDATE t"):
            self.assertFalse(erp.sql_so_leitura(ruim), ruim)
        s = erp.Sistema("X", "sqlite", {"produtos": {
            "sql": "DELETE FROM P", "colunas": {"cod_item": "C"}}})
        self.assertIn("um único SELECT", erp.problemas(s, "produtos")[0])

    def test_filtros_da_consulta(self):
        s = _sistema_dbf()
        q = erp.consulta(s, "estoque", "001", data_fim=datetime.date(
            2026, 8, 31))
        self.assertEqual([(f.coluna, f.operador) for f in q.filtros],
                         [("EMPRESA", "="), ("DTSALDO", "<=")])
        sem = erp.consulta(s, "produtos", "")
        self.assertEqual(sem.filtros, [])
        with self.assertRaises(ValueError):
            erp.consulta(s, "participantes")

    def test_valores_do_banco(self):
        import decimal
        ln = erp.linhas("produtos", [
            {"cod_item": " P1 ", "aliq_icms": decimal.Decimal("18.00"),
             "descr_item": None},
            {"cod_item": "", "descr_item": "sem código"},
            {"cod_item": 7, "descr_item": datetime.datetime(2026, 8, 5, 10)},
        ])
        self.assertEqual(len(ln), 2)
        self.assertEqual(ln[0]["cod_item"], "P1")
        self.assertEqual(ln[0]["aliq_icms"], 18.0)
        self.assertEqual(ln[1]["descr_item"], "05082026")

    def test_estoque_na_data(self):
        linhas = [
            {"cod_item": "A", "qtd": 1, "data": "31072026"},
            {"cod_item": "A", "qtd": 2, "data": "31082026"},
            {"cod_item": "A", "qtd": 9, "data": "30092026"},   # depois
            {"cod_item": "B", "qtd": 3, "vl_item": 3},          # sem data:
            {"cod_item": "B", "qtd": 4, "vl_item": 4},          # soma
        ]
        r = {ln["cod_item"]: ln for ln in erp.estoque_na_data(linhas,
                                                              "31082026")}
        self.assertEqual(r["A"]["qtd"], 2)
        self.assertEqual((r["B"]["qtd"], r["B"]["vl_item"]), (7.0, 7.0))
        com = erp.com_cadastro([{"cod_item": "A", "qtd": 2, "unid": ""}],
                               [{"cod_item": "A", "descr_item": "X",
                                 "unid": "UN", "qtd": 99}])
        self.assertEqual(com, [{"cod_item": "A", "qtd": 2,
                                "descr_item": "X", "unid": "UN"}])

    def test_conteudo_xml_como_o_erp_guarda(self):
        xml = nfe_xml().encode("utf-8")
        formas = {
            "texto": xml.decode("utf-8"), "bytes": xml,
            "bom": b"\xef\xbb\xbf" + xml, "gzip": gzip.compress(xml),
            "zlib": zlib.compress(xml), "base64": base64.b64encode(xml),
            "base64 de gzip": base64.b64encode(gzip.compress(xml)).decode(),
        }
        for nome, v in formas.items():
            with self.subTest(nome):
                self.assertTrue(erp.conteudo_xml(v).lstrip(
                    b"\xef\xbb\xbf").startswith(b"<?xml"))
        for ruim in (None, b"", "não é xml", b"\x1f\x8bquebrado"):
            self.assertIsNone(erp.conteudo_xml(ruim))
        lidos = erp.ler_xmls([("a", gzip.compress(xml)), ("b", "lixo")])
        self.assertEqual(lidos[0][0].chave, CHAVE_1)
        self.assertIn("não é XML", lidos[1][1])


class TestDBF(unittest.TestCase):

    def test_pasta_dbf(self):
        with PastaTemporaria() as p:
            _pasta_dbf(p)
            con = erp.Conexao("Loja", "erp_clipper", base=p, empresa="001")
            ad = bancos.adaptador(_sistema_dbf(), con)
            self.assertEqual(ad.tabelas(), ["NOTAS", "PRODUTOS"])
            self.assertIn("DESCRI", ad.colunas({"tabela": "produtos"}))
            cols, amostra = ad.amostra({"tabela": "PRODUTOS"})
            self.assertEqual(len(amostra), 3)          # o apagado some
            self.assertEqual(amostra[0][cols.index("DESCRI")],
                             "PRODUTO AÇÚCAR")          # cp850
            self.assertEqual(amostra[0][cols.index("ESTOQUE")], 5.0)
            self.assertIs(amostra[0][cols.index("ATIVO")], True)
            q = erp.consulta(_sistema_dbf(), "produtos", con.empresa)
            linhas = erp.linhas("produtos", ad.ler(q))
            # "001" casa com o número 1; a empresa 2 fica de fora
            self.assertEqual([l["cod_item"] for l in linhas], ["P1", "P2"])
            q = erp.consulta(_sistema_dbf(), "xmls",
                             data_ini=datetime.date(2026, 8, 1),
                             data_fim=datetime.date(2026, 8, 31))
            notas = list(ad.ler(q))
            self.assertEqual(len(notas), 1)
            self.assertTrue(notas[0]["xml"].startswith("<?xml"))
            with self.assertRaises(bancos.ErroDeBanco):
                ad.colunas({"sql": "SELECT 1"})
            with self.assertRaises(bancos.ErroDeBanco):
                ad.colunas({"tabela": "NAO_EXISTE"})

    def test_caso_de_uso_pela_pasta_dbf(self):
        with PastaTemporaria() as p:
            _pasta_dbf(p)
            cfg = sistemas_erp.Configuracao(
                {"erp_clipper": _sistema_dbf()},
                [erp.Conexao("Loja", "erp_clipper", base=p, empresa="1",
                             cnpjs=[CNPJ_TESTE])])
            con = cfg.conexoes[0]
            est = caso.estoque(cfg, con, "31082026")
            p1 = next(l for l in est if l["cod_item"] == "P1")
            self.assertEqual((p1["qtd"], p1["descr_item"]),
                             (5.0, "PRODUTO AÇÚCAR"))
            lote = caso.xmls(cfg, con, "01082026", "31082026")
            self.assertEqual([n.chave for n in lote.nfes], [CHAVE_1])
            self.assertEqual(
                [c.nome for c in caso.conexoes_da_empresa(cfg, CNPJ_TESTE,
                                                          "xmls")], ["Loja"])
            self.assertEqual(caso.conexoes_da_empresa(cfg, CNPJ_TESTE,
                                                      "participantes"), [])


# ------------------------------------------------------------- SQLite
def _banco_sqlite(caminho):
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE TB_PRODUTO (ID TEXT, NOME TEXT, CLASFISCAL TEXT,
            CEST TEXT, GTIN TEXT, ALIQ NUMERIC);
        CREATE TABLE TB_PESSOA (CODIGO TEXT, RAZAO TEXT, CNPJ_CPF TEXT,
            INSCRICAO TEXT, IBGE INTEGER, RUA TEXT, BAIRRO TEXT);
        CREATE TABLE TB_XML (CHAVE TEXT, DT_EMISSAO TEXT, CONTEUDO BLOB);
        CREATE TABLE TB_SALDO (PRODUTO TEXT, QTD NUMERIC, CUSTO NUMERIC);
    """)
    con.executemany("INSERT INTO TB_PRODUTO VALUES (?,?,?,?,?,?)", [
        ("P1", "PRODUTO UM ERP", "04012010", "0200400", "7891234567895", 18),
        ("P2", "PRODUTO DOIS", "21069090", "", "", 12),
        ("P3", "PRODUTO TRES", "21069090", "", "", 0)])
    con.executemany("INSERT INTO TB_PESSOA VALUES (?,?,?,?,?,?,?)", [
        ("F1", "FORNECEDOR | ERP", "11.444.777/0001-61", "ISENTO",
         3106200, "RUA DO ERP", "CENTRO"),
        ("C9", "CLIENTE FISICA", "529.982.247-25", "", 3106200, "", "")])
    con.executemany("INSERT INTO TB_XML VALUES (?,?,?)", [
        (CHAVE_1, "2026-08-05", gzip.compress(nfe_xml().encode())),
        (CHAVE_2, "2026-08-20", nfe_xml(chave=CHAVE_2, nnf="124")),
        ("", "2026-08-21", b"lixo"),
        ("X", "2026-09-02", nfe_xml(chave=CHAVE_2))])
    con.executemany("INSERT INTO TB_SALDO VALUES (?,?,?)", [
        ("P1", 2, 3.5), ("P4", 1, 10)])
    con.commit()
    con.close()


def _sistema_sqlite():
    return erp.Sistema("ERP SQL", "sqlite", {
        "produtos": {"tabela": "TB_PRODUTO", "colunas": {
            "cod_item": "ID", "descr_item": "NOME", "cod_ncm": "CLASFISCAL",
            "cest": "CEST", "cod_barra": "GTIN", "aliq_icms": "ALIQ"}},
        "participantes": {"tabela": "TB_PESSOA", "colunas": {
            "cod_part": "CODIGO", "nome": "RAZAO", "cnpj": "CNPJ_CPF",
            "ie": "INSCRICAO", "cod_mun": "IBGE", "end": "RUA",
            "bairro": "BAIRRO"}},
        "xmls": {"tabela": "TB_XML", "colunas": {
            "chave": "CHAVE", "data": "DT_EMISSAO", "xml": "CONTEUDO"}},
        # consulta própria: o saldo com a unidade do cadastro
        "estoque": {"sql": "SELECT S.PRODUTO, S.QTD, S.CUSTO, 'UN' AS UN "
                           "FROM TB_SALDO S", "colunas": {
            "cod_item": "PRODUTO", "qtd": "QTD", "vl_unit": "CUSTO",
            "unid": "UN"}},
    })


class TestSQLite(unittest.TestCase):

    def setUp(self):
        self._p = PastaTemporaria()
        p = self._p.__enter__()
        self.addCleanup(self._p.__exit__, None, None, None)
        self.banco = os.path.join(p, "erp.db")
        _banco_sqlite(self.banco)
        self.cfg = sistemas_erp.Configuracao(
            {"erp_sql": _sistema_sqlite()},
            [erp.Conexao("Matriz", "erp_sql", base=self.banco,
                         cnpjs=[CNPJ_TESTE])])
        self.con = self.cfg.conexoes[0]
        self.sistema = _sistema_sqlite()

    def test_descobre_tabelas_e_colunas(self):
        self.assertIn("SQLite", caso.testar(self.sistema, self.con))
        self.assertEqual(caso.tabelas(self.sistema, self.con),
                         ["TB_PESSOA", "TB_PRODUTO", "TB_SALDO", "TB_XML"])
        self.assertEqual(caso.colunas(self.sistema, self.con,
                                      {"tabela": "TB_SALDO"}),
                         ["PRODUTO", "QTD", "CUSTO"])
        self.assertEqual(caso.colunas(
            self.sistema, self.con,
            self.sistema.mapeamento("estoque").origem)[-1], "UN")
        cols, linhas = caso.amostra(self.sistema, self.con,
                                    {"tabela": "TB_PRODUTO"}, 2)
        self.assertEqual((cols[0], len(linhas)), ("ID", 2))
        prev = caso.previa(self.sistema, self.con, "produtos", 1)
        self.assertEqual(prev[0]["cod_ncm"], "04012010")

    def test_so_leitura(self):
        ad = bancos.adaptador(self.sistema, self.con)
        with self.assertRaises(bancos.ErroDeBanco):
            ad.amostra({"sql": "DELETE FROM TB_PRODUTO"})
        # o arquivo é aberto em modo somente leitura
        with self.assertRaises(bancos.ErroDeBanco):
            ad.amostra({"sql": "SELECT * FROM TB_PRODUTO WHERE 1 = "
                               "(SELECT 1 FROM NAO_EXISTE)"})
        with contextlib.closing(sqlite3.connect(self.banco)) as c:
            n = c.execute("SELECT COUNT(*) FROM TB_PRODUTO").fetchone()[0]
        self.assertEqual(n, 3)

    def test_banco_ausente(self):
        con = erp.Conexao("X", "erp_sql", base=self.banco + ".nao")
        with self.assertRaises(bancos.ErroDeBanco):
            caso.testar(self.sistema, con)

    def test_xmls_do_periodo(self):
        lote = caso.xmls(self.cfg, self.con, "01082026", "31082026")
        self.assertEqual([n.chave for n in lote.nfes], [CHAVE_1, CHAVE_2])
        self.assertEqual(len(lote.erros), 1)            # o "lixo"
        self.assertIn("não é XML", lote.erros[0][1])

    def test_atualiza_o_0200_pelo_erp(self):
        doc = SpedDocument.de_texto(icms_basico().texto())
        linhas = caso.produtos(self.cfg, self.con)
        prev = doc.previa_atualizacao_0200(linhas)
        self.assertEqual(prev["COD_NCM"][0], ("P1", "21069090", "04012010"))
        self.assertIn("CEST", prev)
        contagem, itens = doc.atualizar_0200(linhas, {"COD_NCM", "CEST"})
        self.assertEqual(contagem, {"COD_NCM": 1, "CEST": 1})
        self.assertEqual(itens, {"P1"})
        i = doc._ix("0200", "COD_NCM")
        p1 = next(r for r in doc.registros if r.reg == "0200"
                  and r.valor(doc._ix("0200", "COD_ITEM")) == "P1")
        self.assertEqual(p1.valor(i), "04012010")
        self.assertEqual(p1.valor(doc._ix("0200", "COD_BARRA")), "")
        self.assertEqual(doc.previa_atualizacao_0200(linhas).get("COD_NCM"),
                         None)

    def test_atualiza_o_0150_pelo_erp(self):
        doc = SpedDocument.de_texto(icms_basico().texto())
        linhas = caso.participantes(self.cfg, self.con)
        prev = participantes.previa(doc, linhas)
        self.assertEqual(prev["NOME"], [("F1", "FORNECEDOR TESTE",
                                         "FORNECEDOR ERP")])
        self.assertEqual(prev["END"][0][2], "RUA DO ERP")
        self.assertNotIn("IE", prev)                    # ISENTO não é IE
        self.assertNotIn("CNPJ", prev)                  # já igual
        self.assertNotIn("COD_MUN", prev)               # 3106200 = 3106200
        self.assertEqual(participantes.avisos(prev), {})
        mudou = participantes.atualizar(doc, linhas, {"NOME", "END"})
        self.assertEqual(mudou, {"NOME": 1, "END": 1})
        texto = doc.gerar_texto() if hasattr(doc, "gerar_texto") else ""
        self.assertNotIn("FORNECEDOR | ERP", texto)

    def test_0150_casa_pelo_cnpj_e_avisa_o_invalido(self):
        doc = SpedDocument.de_texto(icms_basico().texto())
        linhas = [{"cod_part": "9999", "cnpj": "11444777000161",
                   "cod_mun": "310620", "nome": "PELO CNPJ"}]
        prev = participantes.previa(doc, linhas)
        self.assertEqual(prev["NOME"][0][0], "F1")
        av = participantes.avisos(prev)
        self.assertTrue(av["COD_MUN"][2])               # nasce desmarcado
        av = participantes.avisos({"CNPJ": [("F1", "", "11444777000162")]})
        self.assertTrue(av["CNPJ"][2])
        # CNPJ repetido na fonte: não casa por documento
        dois = linhas + [dict(linhas[0], cod_part="8888")]
        self.assertEqual(participantes.previa(doc, dois), {})

    def test_estoque_por_consulta_propria_vira_inventario(self):
        doc = SpedDocument.de_texto(icms_basico().texto())
        linhas = caso.estoque(self.cfg, self.con, "31082026")
        self.assertEqual({l["cod_item"] for l in linhas}, {"P1", "P4"})
        p1 = next(l for l in linhas if l["cod_item"] == "P1")
        self.assertEqual(p1["descr_item"], "PRODUTO UM ERP")
        res = doc.importar_inventario_h010(linhas, "31082026")
        self.assertEqual((res["itens"], res["novos_0200"]), (2, 1))
        self.assertEqual(res["vl_inv"], 17.0)


class TestDialetos(unittest.TestCase):
    """O SQL que cada adaptador monta (sem servidor)."""

    def _q(self):
        s = erp.Sistema("X", "firebird", {"produtos": {
            "tabela": "dbo.PRODUTO", "coluna_empresa": "EMPRESA",
            "colunas": {"cod_item": "CODIGO", "cod_ncm": "NCM"}}})
        return erp.consulta(s, "produtos", "1")

    def test_firebird(self):
        sql, params, chaves = bancos.Firebird(erp.Conexao()).montar(self._q())
        self.assertEqual(sql, 'SELECT "CODIGO", "NCM" FROM "dbo"."PRODUTO" '
                              'WHERE "EMPRESA" = ?')
        self.assertEqual((params, chaves), (["1"], ["cod_item", "cod_ncm"]))
        self.assertEqual(bancos.Firebird(erp.Conexao())._limitar(
            "SELECT * FROM T", 5), "SELECT FIRST 5 * FROM T")

    def test_sql_server(self):
        ad = bancos.SqlServer(erp.Conexao(host="srv\\SQL2019", base="ERP"))
        sql, _p, _c = ad.montar(self._q())
        self.assertEqual(sql, "SELECT [CODIGO], [NCM] FROM [dbo].[PRODUTO] "
                              "WHERE [EMPRESA] = ?")
        self.assertTrue(ad._limitar("SELECT *", 3).startswith("SELECT TOP 3"))
        cad = ad.cadeia("ODBC Driver 18 for SQL Server")
        self.assertIn("Trusted_Connection=yes", cad)
        self.assertIn("TrustServerCertificate=yes", cad)
        com = bancos.SqlServer(erp.Conexao(host="srv", porta="1433",
                                           usuario="leitor", senha="a}b"))
        cad = com.cadeia("ODBC Driver 17 for SQL Server")
        self.assertIn("SERVER=srv,1433", cad)
        self.assertIn("PWD={a}}b}", cad)
        self.assertNotIn("Trusted_Connection", cad)

    def test_mysql(self):
        sql, _p, _c = bancos.MySQL(erp.Conexao()).montar(self._q())
        self.assertEqual(sql, "SELECT `CODIGO`, `NCM` FROM `dbo`.`PRODUTO` "
                              "WHERE `EMPRESA` = %s")

    def test_sem_driver_mysql_explica(self):
        with mock.patch.dict(sys.modules, {"pymysql": None}):
            with self.assertRaises(bancos.ErroDeBanco) as cm:
                bancos.MySQL(erp.Conexao()).testar()
        self.assertIn("pymysql", str(cm.exception))


@unittest.skipUnless(sys.platform == "win32", "DPAPI só no Windows")
class TestGuardar(unittest.TestCase):

    def test_senha_cifrada(self):
        guardado = segredos.cifrar("s3nh@ forte")
        self.assertTrue(guardado.startswith("dpapi:"))
        self.assertNotIn("s3nh@", guardado)
        self.assertEqual(segredos.decifrar(guardado), "s3nh@ forte")
        self.assertEqual(segredos.cifrar(""), "")
        for ruim in ("texto puro", "dpapi:@@@", "dpapi:" + base64.b64encode(
                b"nao cifrado").decode()):
            with self.assertRaises(segredos.SegredoIndisponivel):
                segredos.decifrar(ruim)

    def test_configuracao_em_disco(self):
        with PastaTemporaria() as p:
            arq = os.path.join(p, "sistemas_erp.json")
            cfg = sistemas_erp.Configuracao(
                {"erp_sql": _sistema_sqlite()},
                [erp.Conexao("Matriz", "erp_sql", host="srv", base="X",
                             usuario="leitor", senha="segredo",
                             cnpjs=["11.222.333/0001-81"])])
            sistemas_erp.salvar(cfg, arq)
            with open(arq, encoding="utf-8") as fh:
                texto = fh.read()
            self.assertNotIn("segredo", texto)
            volta = sistemas_erp.carregar(arq)
            self.assertEqual(volta.conexoes[0].senha, "segredo")
            self.assertEqual(volta.da_empresa(CNPJ_TESTE)[0].nome, "Matriz")
            self.assertEqual(volta.sistemas["erp_sql"].para_dict(),
                             _sistema_sqlite().para_dict())
            # JSON de outra máquina: a conexão vem, a senha não
            bruto = json.loads(texto)
            bruto["conexoes"][0]["senha"] = "dpapi:" + base64.b64encode(
                b"de outra maquina").decode()
            with open(arq, "w", encoding="utf-8") as fh:
                json.dump(bruto, fh)
            volta = sistemas_erp.carregar(arq)
            self.assertEqual(volta.conexoes[0].senha, "")
            self.assertEqual(volta.senhas_perdidas, ["Matriz"])

    def test_nome_livre(self):
        cfg = sistemas_erp.Configuracao()
        self.assertEqual(cfg.nome_livre("ERP", ["erp", "ERP (2)"]),
                         "ERP (3)")


def _de_ambiente(variavel):
    """`servidor;porta;base;usuario;senha` da variável, ou None."""
    v = os.environ.get(variavel)
    if not v:
        return None
    host, porta, base, usuario, senha = (v.split(";") + [""] * 5)[:5]
    return erp.Conexao("teste", host=host, porta=porta, base=base,
                       usuario=usuario, senha=senha)


class TestServidores(unittest.TestCase):
    """Bancos de verdade, quando o ambiente aponta um (TESTES.md)."""

    def _conferir(self, banco, variavel):
        con = _de_ambiente(variavel)
        if con is None:
            self.skipTest("defina %s para testar contra um servidor"
                          % variavel)
        s = erp.Sistema("X", banco)
        ad = bancos.adaptador(s, con)
        self.assertTrue(ad.testar())
        tabelas = ad.tabelas()
        self.assertTrue(tabelas)
        cols, _linhas = ad.amostra({"tabela": tabelas[0]}, 1)
        self.assertTrue(cols)

    def test_firebird(self):
        self._conferir("firebird", "SPED_TABLES_ERP_FIREBIRD")

    def test_sql_server(self):
        self._conferir("sqlserver", "SPED_TABLES_ERP_SQLSERVER")

    def test_mysql(self):
        self._conferir("mysql", "SPED_TABLES_ERP_MYSQL")


if __name__ == "__main__":
    unittest.main()

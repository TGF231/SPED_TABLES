# -*- coding: utf-8 -*-
"""Achados menores da revisão de código (0.52.0) — um teste por achado."""

import os
import unittest
from unittest import mock

from sped_tables.infra import cadastro
from sped_tables.infra import arquivos
from sped_tables.infra import config
from sped_tables.infra import dados
from sped_tables.infra import descritor_pva
from sped_tables.dominio import empresas as emp_mod
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import (CNPJ_TESTE, PastaTemporaria, contrib_basico,
                           icms_basico)


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


def _ordem(doc, prefixo):
    return [l.split("|")[1] for l in doc.gerar_texto().splitlines()
            if l.startswith("|" + prefixo)]


class TestIndiceNone(unittest.TestCase):
    """8 — `_ix` devolve None para campo que o leiaute não tem."""

    def test_ler_e_gravar_campo_inexistente(self):
        doc = _doc(icms_basico())
        r = next(x for x in doc.registros if x.reg == "C100")
        largura = len(r.campos)
        self.assertEqual(r.valor(None), "")
        self.assertFalse(r.set_valor(None, "x"))
        self.assertEqual(len(r.campos), largura)


class TestLargura(unittest.TestCase):
    """9 — registro gerado não encolhe quando o arquivo é mais largo."""

    def test_c190_mais_largo_que_o_leiaute(self):
        m = icms_basico()
        for campos in m.linhas:
            if campos[0] == "C190":
                campos.append("EXTRA")            # versão futura do leiaute
        doc = _doc(m)
        c100 = next(r for r in doc.registros if r.reg == "C100")
        doc.consolidar_c190(c100)
        (c190,) = [f for f in c100.filhos if f.reg == "C190"]
        self.assertEqual(len(c190.campos), 13)
        self.assertEqual(c190.campos[-1], "")

    def test_m210_conserva_a_largura(self):
        doc = _doc(contrib_basico())
        antes = next(len(r.campos) for r in doc.registros if r.reg == "M210")
        doc.recalcular_bloco_m(naturezas={"1102": "01"})
        depois = next(len(r.campos) for r in doc.registros if r.reg == "M210")
        self.assertEqual(depois, antes)


class TestPosicaoNoLeiaute(unittest.TestCase):
    """10 — 0190/0200 novos entram na posição do leiaute."""

    def _sem_0190_nem_0200(self):
        m = icms_basico()
        m.linhas = [c for c in m.linhas if c[0] not in ("0190", "0200")]
        return _doc(m)

    def test_inventario_cria_0190_e_0200_depois_do_0150(self):
        doc = self._sem_0190_nem_0200()
        doc.importar_inventario_h010(
            [{"cod_item": "NOVO1", "unid": "KG", "qtd": "2",
              "vl_unit": "5", "vl_item": "10", "descr_item": "NOVO"}],
            "31082026")
        tipos = _ordem(doc, "0")
        self.assertEqual(tipos, sorted(tipos[:-1]) + ["0990"])
        self.assertLess(tipos.index("0150"), tipos.index("0190"))
        self.assertLess(tipos.index("0190"), tipos.index("0200"))


class TestTrocaDeAliquotas(unittest.TestCase):
    """11 — C100 com C175 e C170 somava os dois no VL_PIS."""

    def test_c100_consolidado_soma_so_o_c175(self):
        m = contrib_basico(bloco_m=False)
        # a saída ganha um C175 (como no fluxo da NFC-e com C170 fictício)
        idx = max(i for i, c in enumerate(m.linhas) if c[0] == "C170")
        nomes = m.tabela["C175"]
        c175 = [""] * len(nomes)
        for k, v in {"REG": "C175", "CFOP": "5102", "VL_OPR": "300,00",
                     "CST_PIS": "01", "VL_BC_PIS": "300,00",
                     "ALIQ_PIS": "1,65", "VL_PIS": "4,95",
                     "CST_COFINS": "01", "VL_BC_COFINS": "300,00",
                     "ALIQ_COFINS": "7,6", "VL_COFINS": "22,80"}.items():
            c175[nomes.index(k)] = v
        m.linhas.insert(idx + 1, c175)
        doc = _doc(m)
        doc.trocar_aliquotas_pis_cofins(aliq_pis=0.65, aliq_cofins=3.0,
                                        escopo="saidas")
        saida = [r for r in doc.registros if r.reg == "C100"][1]
        self.assertEqual(saida.valor(doc._ix("C100", "VL_PIS")), "1,95")
        self.assertEqual(saida.valor(doc._ix("C100", "VL_COFINS")), "9,00")


class TestGravacoesJson(unittest.TestCase):
    """14 — cadastro, índice e correlações gravam de forma atômica."""

    def test_falha_no_meio_preserva_o_anterior(self):
        with PastaTemporaria() as p:
            cam = os.path.join(p, "empresas.json")
            cadastro.salvar_empresas({CNPJ_TESTE: emp_mod.Empresa(cnpj=CNPJ_TESTE,
                                                         nome="A")}, cam)
            novo = {CNPJ_TESTE: emp_mod.Empresa(cnpj=CNPJ_TESTE, nome="B")}
            # a troca final falha (antivírus segurando o arquivo, disco cheio)
            with mock.patch("os.replace", side_effect=OSError("ocupado")):
                with self.assertRaises(OSError):
                    cadastro.salvar_empresas(novo, cam)
            self.assertEqual(cadastro.carregar_empresas(cam)[CNPJ_TESTE].nome, "A")
            self.assertEqual([n for n in os.listdir(p) if n.endswith(".tmp")],
                             [])

    def test_correlacoes_ida_e_volta(self):
        with PastaTemporaria() as p:
            cam = os.path.join(p, "correlacoes.json")
            cadastro.salvar_correlacoes({"5102": ["1102"]}, cam)
            self.assertEqual(cadastro.carregar_correlacoes(cam)["5102"],
                             {"1102"})


class TestConfiguracao(unittest.TestCase):
    """Ponto único de configuração dos caminhos do PVA."""

    def setUp(self):
        self._pasta = PastaTemporaria()
        self._anterior = dict(os.environ)
        os.environ["SPED_TABLES_DADOS"] = self._pasta.__enter__()
        os.environ.pop(config.VARIAVEL, None)
        config.esquecer()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._anterior)
        config.esquecer()
        self._pasta.__exit__(None, None, None)

    def _pva_falso(self, raiz):
        for layout, cfg in config.PVAS.items():
            os.makedirs(os.path.join(raiz, cfg["pasta"], cfg["tabelas"]))
        return raiz

    def test_variavel_de_ambiente_manda(self):
        with PastaTemporaria() as p:
            os.environ[config.VARIAVEL] = self._pva_falso(p)
            config.esquecer()
            self.assertEqual(config.raiz_pva(), p)
            self.assertEqual(config.pasta_tabelas("ICMS"),
                             os.path.join(p, "Fiscal", "recursos",
                                          "TabelasExternas"))

    def test_escolha_gravada_vale_na_proxima_vez(self):
        with PastaTemporaria() as p:
            self._pva_falso(p)
            config.definir_raiz_pva(p)
            config.esquecer()
            self.assertEqual(config.raiz_pva(), p)
            self.assertEqual(config.ler()["raiz_pva"], p)

    def test_tabelas_rfb_migram_do_arquivo_antigo(self):
        with open(dados.caminho(config.ARQUIVO_ANTIGO_RFB), "w",
                  encoding="utf-8") as fh:
            fh.write('{"zero": "C:/tabelas/zero.txt"}')
        self.assertEqual(config.tabelas_rfb()["zero"], "C:/tabelas/zero.txt")
        config.gravar_tabelas_rfb({"mono": "C:/m.txt"})
        self.assertEqual(config.tabelas_rfb()["mono"], "C:/m.txt")
        self.assertEqual(config.tabelas_rfb()["zero"], "")

    def test_descritor_e_lido_uma_vez(self):
        if not descritor_pva.disponivel():
            self.skipTest("PVA não instalado")
        a = descritor_pva.carregar("ICMS")
        b = descritor_pva.carregar("ICMS")
        self.assertIs(a, b)


class TestIndiceDoAcervo(unittest.TestCase):
    """16 — `carregar_indice` não sombreia mais o módulo `dados`."""

    def test_indice_le_e_grava(self):
        anterior = os.environ["SPED_TABLES_DADOS"]
        try:
            with PastaTemporaria() as p:
                os.environ["SPED_TABLES_DADOS"] = p
                origem = icms_basico().gravar(p, "x.txt")
                arquivos.arquivar(SpedDocument.carregar(origem), origem)
                self.assertEqual(len(arquivos.carregar_indice()), 1)
        finally:
            os.environ["SPED_TABLES_DADOS"] = anterior


class TestExportacaoCsv(unittest.TestCase):
    """Um exportador só: `;` na descrição e travessão não quebram o CSV."""

    def test_ponto_e_virgula_e_caractere_fora_do_latin1(self):
        import csv
        from sped_tables.infra import exportacao
        with PastaTemporaria() as p:
            cam = os.path.join(p, "x.csv")
            _c, n = exportacao.gravar_csv(
                cam, ["cod", "descr", "valor"],
                [["1", "ARROZ; TIPO 1", "10,00"],
                 ["2", "FEIJÃO — PRETO", None]])
            self.assertEqual(n, 2)
            with open(cam, encoding="latin-1", newline="") as fh:
                linhas = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(linhas[1], ["1", "ARROZ; TIPO 1", "10,00"])
        self.assertEqual(linhas[2], ["2", "FEIJÃO ? PRETO", ""])


if __name__ == "__main__":
    unittest.main()

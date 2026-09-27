# -*- coding: utf-8 -*-
"""Leitura do banco do PVA e a comparação do roteiro de validação.

Os bytes daqui imitam o registro dinâmico do MyISAM (textos com prefixo de
tamanho) — nenhum banco real, que teria dado de cliente, entra no teste.
"""

import importlib.util
import os
import sys
import unittest
from unittest import mock

from sped_tables.infra import banco_pva, config
from tests.fabrica import PastaTemporaria

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _txt(s):
    b = s.encode("latin-1")
    return bytes([len(b)]) + b


def _linha(msg, reg, conteudo):
    """Um registro de `inconsistencia` como o MyISAM grava."""
    return (b"\x03\x00<\x00\x16" + _txt(msg) + b"\x00\x00" + _txt("0900")
            + b"\x00" + _txt(reg) + bytes([len(conteudo)])
            + conteudo.encode("latin-1") + b"\x00\x00\x00")


class TestBancoPva(unittest.TestCase):

    def setUp(self):
        self._pasta = PastaTemporaria()
        self.raiz = self._pasta.__enter__()
        self.dados = os.path.join(self.raiz, "EFD-Contribuicoes", "mysql",
                                  "data")
        os.makedirs(os.path.join(self.dados, "master"))

    def tearDown(self):
        self._pasta.__exit__(None, None, None)

    def _banco(self, nome, conteudo):
        os.makedirs(os.path.join(self.dados, nome))
        with open(os.path.join(self.dados, nome, "inconsistencia.MYD"),
                  "wb") as fh:
            fh.write(conteudo)

    def test_contagem_por_mensagem_e_registro(self):
        self._banco("bd20260926100000",
                    _linha("MSG_COMPATIBILIDADE_NCM_ALIQ_ZERO", "C170",
                           "|C170|1|X|")
                    + _linha("MSG_COMPATIBILIDADE_NCM_ALIQ_ZERO", "C170",
                             "|C170|2|Y|")
                    + b"\x03\x00\x16" + _txt("MSG_PREENCHIMENTO_0900")
                    + b"\x00\x00")
        c = banco_pva.inconsistencias("CONTRIB", "bd20260926100000",
                                      self.raiz)
        self.assertEqual(c[("MSG_COMPATIBILIDADE_NCM_ALIQ_ZERO", "C170")], 2)
        # sem linha do arquivo, o registro fica em branco — e não é roubado
        # da mensagem seguinte
        self.assertEqual(c[("MSG_PREENCHIMENTO_0900", "")], 1)
        self.assertEqual(banco_pva.por_mensagem(c)[
            "MSG_COMPATIBILIDADE_NCM_ALIQ_ZERO"], 2)

    def test_validacao_sem_erro_e_banco_ausente(self):
        self._banco("bd20260926110000", b"")
        self.assertEqual(banco_pva.inconsistencias(
            "CONTRIB", "bd20260926110000", self.raiz), {})
        self.assertIsNone(banco_pva.inconsistencias(
            "CONTRIB", "bd20990101000000", self.raiz))
        self.assertEqual(banco_pva.bancos("CONTRIB", self.raiz),
                         ["bd20260926110000"])

    def test_master_liga_banco_ao_arquivo(self):
        cam = os.path.join(self.raiz, "SPED_teste.txt")
        dados = (b"\x00" + _txt("11222333000181") + b"\x10"
                 + b"bd20260926120000" + b"\x00"
                 + _txt(cam.replace("\\", "/")) + b"(ABCDEF")
        with open(os.path.join(self.dados, "master", "escrituracao.MYD"),
                  "wb") as fh:
            fh.write(dados)
        (e,) = banco_pva.escrituracoes("CONTRIB", self.raiz)
        self.assertEqual((e["bd"], e["cnpj"]),
                         ("bd20260926120000", "11222333000181"))
        self.assertEqual(banco_pva.banco_do_arquivo("CONTRIB", cam,
                                                    self.raiz),
                         "bd20260926120000")


@unittest.skipUnless(sys.platform == "win32", "Win32")
class TestTravaDeInstalacao(unittest.TestCase):
    """A automação só dirige janela do executável da instalação certa."""

    def test_processo_dentro_e_fora_da_pasta(self):
        from sped_tables.infra import pva
        eu = os.getpid()
        exe = pva.caminho_do_processo(eu)
        self.assertTrue(exe.lower().endswith(".exe"))
        self.assertTrue(pva._da_instalacao(eu, os.path.dirname(
            os.path.dirname(exe))))
        self.assertFalse(pva._da_instalacao(eu, config.RAIZ_PADRAO))

    def test_janela_de_outra_instalacao_e_ignorada(self):
        from sped_tables.infra import pva
        titulo = pva.INSTALACOES["ICMS"]["titulo"]
        with PastaTemporaria() as p:
            pasta = os.path.join(p, "Fiscal")
            os.makedirs(pasta)
            open(os.path.join(pasta, "SpedEFD.exe"), "w").close()
            falsa = [(111, titulo, os.getpid())]   # processo fora da pasta
            with mock.patch.object(pva, "_janelas",
                                   lambda exigir_titulo=True: falsa):
                self.assertEqual(pva.janela("ICMS", p), (None, None))


class TestComparacaoDoRoteiro(unittest.TestCase):

    def setUp(self):
        cam = os.path.join(RAIZ, "ferramentas", "validar_no_pva.py")
        spec = importlib.util.spec_from_file_location("validar_no_pva", cam)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_nova_pior_e_melhor(self):
        orig = {"MSG_A|C190": 63, "MSG_B|C170": 25}
        corr = {"MSG_A|C190": 37, "MSG_B|C170": 26, "MSG_C|E110": 1}
        novas, piores, melhores = self.mod.comparar(orig, corr)
        self.assertEqual(novas, [("MSG_C|E110", 1)])
        self.assertEqual(piores, [("MSG_B|C170", 25, 26)])
        self.assertEqual(melhores, [("MSG_A|C190", 63, 37)])

    @unittest.skipUnless(sys.platform == "win32", "Win32")
    def test_falha_interna_do_pva_para_sem_tecla(self):
        """A tela de falha interna ("Erro durante a validacao no banco")
        tem o botão de enviar relatório à Receita: nenhuma tecla vai para
        ela, e a rodada para."""
        teclas = []
        janelas = [(10, "Sped Fiscal", 99), (11, "Erro", 99)]
        with mock.patch.object(self.mod.pva, "janela",
                               lambda layout, raiz=None: (10, 99)), \
                mock.patch.object(self.mod.pva, "_janelas",
                                  lambda exigir_titulo=True: janelas), \
                mock.patch.object(self.mod.pva, "_tecla",
                                  lambda vk, ctrl=False: teclas.append(vk)), \
                mock.patch.object(self.mod.pva, "_focar",
                                  lambda h, p, **k: h), \
                mock.patch.object(self.mod, "_altura", lambda h: 474):
            with self.assertRaises(self.mod.FalhaDoPva) as ctx:
                self.mod._dispensar_conclusao("ICMS", "x", limite=2)
        self.assertEqual(teclas, [])
        self.assertIn("Não Enviar", str(ctx.exception))

    def test_importado_sem_validar_nao_conta_como_zero_erros(self):
        """O banco existe e a tabela está vazia quando a validação não
        rodou: isso não é "0 inconsistências"."""
        item = {"layout": "ICMS", "arquivo": "x.txt"}
        bancos = iter([["bd1"], ["bd1", "bd2"]])
        with mock.patch.object(self.mod, "_dispensar_conclusao",
                               lambda *a, **k: (True, set())), \
                mock.patch.object(self.mod.banco_pva, "bancos",
                                  lambda *a: next(bancos)), \
                mock.patch.object(self.mod.banco_pva, "inconsistencias",
                                  lambda *a: {}), \
                mock.patch.object(self.mod.pva, "abrir",
                                  lambda *a, **k: {"estado": "importado"}), \
                mock.patch.object(self.mod.time, "sleep", lambda s: None):
            r = self.mod._validar_um(item, "raiz")
        self.assertEqual(r["bd"], "bd2")
        self.assertIsNone(r["inconsistencias"])

    def test_recusa_na_importacao(self):
        estrutura = {"MSG_ERRO_TIPO_CAMPO|0200": 634,
                     "MSG_ERRO_TAMANHO_CAMPO|0200": 366}
        self.assertTrue(self.mod._recusado({"recusado": True}))
        self.assertTrue(self.mod._recusado({"estado": "erro_pva"}))
        # resultado antigo, sem a marca: só erro de estrutura é recusa
        self.assertTrue(self.mod._recusado(
            {"estado": "confirmar", "inconsistencias": estrutura}))
        self.assertFalse(self.mod._recusado(
            {"estado": "validando", "recusado": False,
             "inconsistencias": estrutura}))
        self.assertFalse(self.mod._recusado(
            {"estado": "confirmar", "inconsistencias": {}}))

    def test_relatorio_e_o_teto(self):
        import json
        teto = {"MSG_A|H010": 997, "MSG_B|0150": 3}
        itens = [
            {"rotulo": "x", "fluxo": "original", "estado": "validando",
             "recusado": False, "inconsistencias": teto},
            # os dois no teto: troca de erros não é conclusão
            {"rotulo": "x", "fluxo": "f1", "estado": "validando",
             "recusado": False,
             "inconsistencias": {"MSG_C|0200": 997, "MSG_B|0150": 3}},
            # abaixo do teto: o que aparece pode estar escondido no original
            {"rotulo": "x", "fluxo": "f2", "estado": "validando",
             "recusado": False, "inconsistencias": {"MSG_D|C190": 35}},
        ]
        with PastaTemporaria() as p:
            with open(os.path.join(p, self.mod.RESULTADOS), "w",
                      encoding="utf-8") as fh:
                json.dump(itens, fh)
            with mock.patch("builtins.print"):
                falhas = self.mod.relatorio(p)
            with open(os.path.join(p, "relatorio.md"),
                      encoding="utf-8") as fh:
                texto = fh.read()
        self.assertEqual(falhas, 0)
        self.assertIn("inconclusivo", texto)
        self.assertIn("a conferir no original", texto)

    def test_regua_importavel(self):
        from sped_tables.aplicacao import montagem
        from sped_tables.dominio.sped_model import SpedDocument
        from tests.fabrica import icms_basico
        montagem.configurar()
        m = icms_basico(itens=[{"COD_ITEM": "P1"}])
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(m.gravar(p))
            i = doc._ix("0200", "TIPO_ITEM")
            r0200 = next(r for r in doc.registros if r.reg == "0200")
            r0200.set_valor(i, "N")               # o que o ERP gravou
            j = doc._ix("C170", "CST_ICMS")
            c170 = next(r for r in doc.registros if r.reg == "C170")
            c170.set_valor(j, "0")
            self.assertEqual(self.mod._preparar_importacao(doc), 2)
            self.assertEqual(r0200.valor(i), "00")
            self.assertEqual(c170.valor(j), "000")
            self.assertEqual(self.mod._preparar_importacao(doc), 0)

    def test_saida_dentro_do_repositorio_e_recusada(self):
        with self.assertRaises(SystemExit):
            self.mod._fora_do_repositorio(os.path.join(RAIZ, "saida"))


if __name__ == "__main__":
    unittest.main()

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

    def test_saida_dentro_do_repositorio_e_recusada(self):
        with self.assertRaises(SystemExit):
            self.mod._fora_do_repositorio(os.path.join(RAIZ, "saida"))


if __name__ == "__main__":
    unittest.main()

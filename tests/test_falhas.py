# -*- coding: utf-8 -*-
"""Fallback para exceções não tratadas (`falhas`)."""

import os
import subprocess
import sys
import textwrap
import unittest

import falhas
from sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, icms_basico

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTratar(unittest.TestCase):

    def setUp(self):
        self._estado = dict(falhas._estado)
        falhas.configurar_registro()

    def tearDown(self):
        falhas._estado.update(self._estado)

    def _levantar(self):
        try:
            raise ValueError("defeito de teste")
        except ValueError:
            return sys.exc_info()

    def test_registra_copia_e_avisa(self):
        avisos = []
        falhas._estado["avisar"] = lambda *a: avisos.append(a)
        falhas._estado["salvar_emergencia"] = lambda: "C:/copia.txt"
        falhas.tratar(*self._levantar())
        (tipo, valor, detalhe, copia), = avisos
        self.assertIs(tipo, ValueError)
        self.assertIn("defeito de teste", detalhe)
        self.assertEqual(copia, "C:/copia.txt")
        with open(falhas.caminho_log(), encoding="utf-8") as fh:
            self.assertIn("defeito de teste", fh.read())

    def test_erro_dentro_do_aviso_nao_empilha(self):
        chamadas = []

        def aviso_que_quebra(*a):
            chamadas.append(a)
            falhas.tratar(*self._levantar())      # erro dentro do aviso
            raise RuntimeError("o aviso também quebrou")

        falhas._estado["avisar"] = aviso_que_quebra
        falhas._estado["salvar_emergencia"] = None
        falhas.tratar(*self._levantar())
        self.assertEqual(len(chamadas), 1)
        self.assertFalse(falhas._estado["mostrando"])

    def test_copia_de_emergencia_vai_para_a_pasta_de_dados(self):
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(icms_basico().gravar(p))
        destino = falhas.gravar_emergencia(doc, "C:/clientes/ARQUIVO.txt")
        self.assertTrue(destino.startswith(
            os.path.join(os.environ["SPED_TABLES_DADOS"], "recuperacao")))
        self.assertIn("ARQUIVO_", os.path.basename(destino))
        with open(destino, "rb") as fh:
            self.assertTrue(fh.read().startswith(b"|0000|"))


class TestProcessoSobrevive(unittest.TestCase):
    """Sem o gancho, o PyQt6 encerra o processo numa exceção de slot."""

    SCRIPT = textwrap.dedent("""
        import os, sys
        sys.path.insert(0, %r)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["SPED_TABLES_DADOS"] = %r
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        import falhas
        app = QApplication([])
        if sys.argv[1] == "com":
            falhas.instalar(avisar=lambda *a: print("avisado"))
        def slot():
            raise RuntimeError("slot quebrado")
        QTimer.singleShot(0, slot)
        QTimer.singleShot(200, app.quit)
        app.exec()
        print("vivo")
    """)

    def _rodar(self, modo):
        with PastaTemporaria() as p:
            r = subprocess.run(
                [sys.executable, "-c", self.SCRIPT % (RAIZ, p), modo],
                capture_output=True, text=True, timeout=60)
        return r

    def test_com_o_gancho_o_programa_continua(self):
        try:
            import PyQt6  # noqa: F401
        except ImportError:
            self.skipTest("PyQt6 não instalado")
        r = self._rodar("com")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("avisado", r.stdout)
        self.assertIn("vivo", r.stdout)

    def test_sem_o_gancho_o_processo_morreria(self):
        """Controle: prova que o teste acima mede alguma coisa."""
        try:
            import PyQt6  # noqa: F401
        except ImportError:
            self.skipTest("PyQt6 não instalado")
        r = self._rodar("sem")
        self.assertNotIn("vivo", r.stdout)


if __name__ == "__main__":
    unittest.main()

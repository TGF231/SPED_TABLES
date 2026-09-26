# -*- coding: utf-8 -*-
"""Automação do PVA — só o que dá para testar sem abrir o PVA de verdade.

Nenhum teste daqui manda tecla nem abre janela: as funções que olham o
Windows são trocadas por falsas. Abrir o PVA do usuário só para testar
cancelamento seria justamente o tipo de efeito colateral que a automação
existe para evitar.
"""

import sys
import time
import unittest
from unittest import mock

if sys.platform == "win32":
    import pva


@unittest.skipUnless(sys.platform == "win32", "automação Win32")
class TestCancelamento(unittest.TestCase):

    def _cancela_rapido(self, fn):
        t = time.time()
        with self.assertRaises(pva.Cancelado):
            fn()
        self.assertLess(time.time() - t, 1.0)

    def test_esperas_cancelam(self):
        sempre = lambda: True                                    # noqa: E731
        self._cancela_rapido(lambda: pva._dormir(60, sempre))
        self._cancela_rapido(lambda: pva._esperar_pronta(
            0, 999999, limite=60, cancelar=sempre))
        self._cancela_rapido(lambda: pva._janela_com_titulo(
            999999, "x", 60, cancelar=sempre))

    def test_decisao_do_usuario_espera_e_cancela(self):
        falsa = [(1, "Atualizar Tabelas", 999999)]
        with mock.patch.object(pva, "_janelas",
                               lambda exigir_titulo=True: falsa):
            self._cancela_rapido(lambda: pva._esperar_livre(
                999999, limite=60, cancelar=lambda: True))
            # sem cancelar, espera até o limite e devolve False
            self.assertFalse(pva._esperar_livre(999999, limite=0.6))

    def test_abrir_devolve_cancelado(self):
        with mock.patch.object(pva, "janela",
                               lambda layout, raiz=None: (123456, 999999)), \
                mock.patch.object(pva, "_copiar", lambda texto: True):
            r = pva.abrir(__file__, "ICMS", cancelar=lambda: True)
        self.assertEqual(r["estado"], "cancelado")
        self.assertIn("Ctrl+I", r["mensagem"])


@unittest.skipUnless(sys.platform == "win32", "automação Win32")
class TestSemPva(unittest.TestCase):

    def test_arquivo_inexistente(self):
        r = pva.abrir("Z:/nao/existe.txt", "ICMS")
        self.assertEqual(r["estado"], "sem_arquivo")

    def test_classificar_telas_do_pva(self):
        self.assertIn("carregar", pva._classificar([(1, "Aguarde...")]))
        self.assertIn("transferindo",
                      pva._classificar([(1, "Transferindo Tabelas")]))
        self.assertIn("resposta",
                      pva._classificar([(1, "Atualizar Tabelas")]))
        # janela que não é do caminho não segura a automação
        self.assertEqual(pva._classificar([(1, "Resultado")]), "")


if __name__ == "__main__":
    unittest.main()

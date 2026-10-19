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
    from sped_tables.infra import pva


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
        # a suíte roda com a pasta do PVA vazia: a instalação é de mentira
        falsa = {"exe": "PVA.exe", "pasta": ".", "titulo": "Sped Fiscal",
                 "nome": "PVA Fiscal"}
        janela = lambda layout, raiz=None: (123456, 999999)      # noqa: E731
        with mock.patch.object(pva, "instalacao",
                               lambda layout, raiz=None: falsa), \
                mock.patch.object(pva, "janela", janela), \
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


@unittest.skipUnless(sys.platform == "win32", "automação Win32")
class TestConfirmacao(unittest.TestCase):
    """Sequências de janelas observadas no PVA Fiscal (ensaio, 26/09/2026).

    Escrituração existente: ... Validando assinaturas → **Aviso**
    (substituir?) → Aguarde → Importando → Aviso (validar?) → Validando.
    Escrituração nova: ... Validando assinaturas → Aguarde → Importando →
    Aviso (validar?) — **sem** o primeiro aviso.
    """

    PID = 999999

    def _roteiro(self, quadros):
        """`_janelas` falso que devolve um quadro por chamada (o último se
        repete)."""
        fila = list(quadros)

        def janelas(exigir_titulo=True):
            q = fila.pop(0) if len(fila) > 1 else fila[0]
            return [(n + 1, t, self.PID) for n, t in enumerate(q)]
        return janelas

    def _confirmar(self, quadros):
        teclas = []
        with mock.patch.object(pva, "_janelas", self._roteiro(quadros)), \
                mock.patch.object(pva, "_focar", lambda h, p, **k: h), \
                mock.patch.object(pva, "_tecla",
                                  lambda vk, ctrl=False: teclas.append(vk)):
            r = pva._confirmar_aviso(self.PID, pva.TITULO_IMPORTANDO,
                                     limite_aviso=2, limite_efeito=2)
        return r, teclas

    def test_escrituracao_nova_nao_responde_aviso(self):
        imp = "Importando a escrituração selecionada - Descritor 20001v2"
        r, teclas = self._confirmar([["Aguarde..."], [imp], [imp],
                                     ["Aviso"]])
        self.assertTrue(r)
        self.assertEqual(teclas, [])     # o "validar?" não foi respondido

    def test_importacao_que_passou_durante_a_espera(self):
        r, teclas = self._confirmar([["Aguarde..."],
                                     ["Importando a escrituração"], [],
                                     ["Aviso"]])
        self.assertIs(r, True)
        self.assertEqual(teclas, [])

    def test_escrituracao_existente_responde_e_confere(self):
        r, teclas = self._confirmar([[], ["Aviso"], ["Aviso"],
                                     ["Importando a escrituração"]])
        self.assertTrue(r)
        self.assertEqual(teclas, [pva.VK_RETURN])

    def test_recusa_encerra_a_espera(self):
        # o `Importando…` passou sem ser visto; o relatório da recusa, não
        r, teclas = self._confirmar([["Aguarde..."],
                                     ["Erro", "Resultado da Importação"]])
        self.assertIs(r, True)
        self.assertEqual(teclas, [])

    def test_sem_aviso_nem_progresso(self):
        r, teclas = self._confirmar([[]])
        self.assertIsNone(r)
        self.assertEqual(teclas, [])


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""A janela nasce, abre um arquivo e **cada ação do menu roda sem exceção**.

Teste de ação de menu chama a ação, não o diálogo: foi pulando o método do
menu que o "Validar campos pelo leiaute" passou três versões derrubando o
programa sem que nenhum teste visse (CLAUDE.md, "Como o PVA valida").

Os diálogos modais são neutralizados — `exec` devolve "aceito", as
perguntas respondem "sim" e os seletores de arquivo voltam vazios —, de modo
que cada ação percorre o caminho inteiro sobre um SPED sintético.
"""

import sys
import unittest
from unittest import mock

from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico

try:
    from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog,
                                 QInputDialog, QMessageBox)
    from PyQt6.QtCore import QTimer, QEventLoop
    TEM_QT = True
except ImportError:                                  # pragma: no cover
    TEM_QT = False

# ações que saem do programa: abrir o PVA do usuário ou fechar a janela
FORA_DO_TESTE = ("act_abrir_pva", "act_sair")
# ações que tiram o arquivo da tela vão por último, senão desabilitam as
# demais e o teste passaria sem ter disparado nada
POR_ULTIMO = ("act_empresas", "act_fechar")


def _app():
    return QApplication.instance() or QApplication([])


def _esperar(ms=250):
    """Deixa rodar os `QTimer.singleShot` pendentes (diagnóstico ao abrir)."""
    laco = QEventLoop()
    QTimer.singleShot(ms, laco.quit)
    laco.exec()


@unittest.skipUnless(TEM_QT, "PyQt6 não instalado")
class TestJanela(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app()
        import sped_editor
        cls.ed = sped_editor
        Sim = QMessageBox.StandardButton.Yes
        cls._patches = [
            mock.patch.object(QDialog, "exec", lambda self: 1),
            mock.patch.object(QMessageBox, "exec", lambda self: 0),
            mock.patch.object(QMessageBox, "question",
                              staticmethod(lambda *a, **k: Sim)),
            mock.patch.object(QMessageBox, "information",
                              staticmethod(lambda *a, **k: Sim)),
            mock.patch.object(QMessageBox, "warning",
                              staticmethod(lambda *a, **k: Sim)),
            mock.patch.object(QMessageBox, "critical",
                              staticmethod(lambda *a, **k: Sim)),
            mock.patch.object(QFileDialog, "getOpenFileName",
                              staticmethod(lambda *a, **k: ("", ""))),
            mock.patch.object(QFileDialog, "getSaveFileName",
                              staticmethod(lambda *a, **k: ("", ""))),
            mock.patch.object(QFileDialog, "getExistingDirectory",
                              staticmethod(lambda *a, **k: "")),
            mock.patch.object(QInputDialog, "getText",
                              staticmethod(lambda *a, **k: ("", False))),
            mock.patch.object(QInputDialog, "getItem",
                              staticmethod(lambda *a, **k: ("", False))),
        ]
        for p in cls._patches:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls._patches:
            p.stop()

    def setUp(self):
        self.erros = []
        self._gancho = sys.excepthook
        sys.excepthook = lambda t, v, tb: self.erros.append((t, v, tb))

    def tearDown(self):
        sys.excepthook = self._gancho

    def _falhas(self):
        import traceback
        return "\n".join("".join(traceback.format_exception(t, v, tb))
                         for t, v, tb in self.erros)

    def test_janela_nasce(self):
        j = self.ed.JanelaPrincipal()
        self.assertTrue(hasattr(j, "act_abrir_pva"))
        j.close()

    def test_todas_as_acoes_nos_dois_leiautes(self):
        for montador in (icms_basico(), contrib_basico()):
            with self.subTest(layout=montador.layout), \
                    PastaTemporaria() as p:
                del self.erros[:]
                j = self.ed.JanelaPrincipal()
                self.assertTrue(j.abrir_caminho(montador.gravar(p)))
                _esperar()
                acoes = sorted(n for n in vars(j)
                               if n.startswith("act_")
                               and n not in FORA_DO_TESTE + POR_ULTIMO)
                acoes += list(POR_ULTIMO)
                disparadas = 0
                for nome in acoes:
                    acao = getattr(j, nome)
                    if acao.isEnabled():
                        acao.trigger()
                        disparadas += 1
                        _esperar(50)
                    self.assertEqual(self.erros, [],
                                     "%s:\n%s" % (nome, self._falhas()))
                # o leiaute habilita a maior parte do menu
                self.assertGreater(disparadas, 20)
                for dlg in QApplication.topLevelWidgets():
                    if dlg is not j:
                        dlg.close()
                j.alterado = False
                j.close()


if __name__ == "__main__":
    unittest.main()

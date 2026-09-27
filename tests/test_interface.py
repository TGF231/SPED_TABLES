# -*- coding: utf-8 -*-
"""A janela nasce, abre um arquivo e **cada ação do menu roda sem exceção**.

Teste de ação de menu chama a ação, não o diálogo: foi pulando o método do
menu que o "Validar campos pelo leiaute" passou três versões derrubando o
programa sem que nenhum teste visse (CLAUDE.md, "Como o PVA valida").

Os diálogos modais são neutralizados — `exec` devolve "aceito", as
perguntas respondem "sim" e os seletores de arquivo voltam vazios —, de modo
que cada ação percorre o caminho inteiro sobre um SPED sintético.
"""

import os
import subprocess
import sys
import textwrap
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


_APLICACAO = []


def _app():
    """O QApplication da suíte, **com referência guardada**: sem ela o
    coletor de lixo leva o objeto antes de o widget nascer e o processo morre
    com exit 127 e nenhum traceback (CLAUDE.md, "Ao adicionar ações")."""
    if not _APLICACAO:
        _APLICACAO.append(QApplication.instance() or QApplication([]))
    return _APLICACAO[0]


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
        from sped_tables.interface import janela
        cls.ed = janela
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

    def test_calculo_recusado_mostra_os_campos_e_nao_segue(self):
        from sped_tables.dominio.sped_model import CamposInvalidos
        from sped_tables.interface.comum import calcular

        class R:
            reg, ordem = "C170", 9

        def recusa():
            raise CamposInvalidos([(R(), "VL_ITEM", "NULL")])
        with mock.patch.object(QMessageBox, "warning") as aviso:
            self.assertEqual(calcular(None, "T", recusa), (False, None))
            self.assertEqual(calcular(None, "T", lambda x: x + 1, 1),
                             (True, 2))
        self.assertEqual(aviso.call_count, 1)
        self.assertIn("C170 VL_ITEM = 'NULL' (linha 10)",
                      aviso.call_args[0][2])

    def test_soltar_um_txt_na_tela_inicial_abre(self):
        """O gesto de arrastar do Explorador é do roteiro 2.3; aqui, o que a
        tela faz com o que recebe: `.txt` abre, o resto é recusado."""
        from PyQt6.QtCore import QMimeData, QPointF, QUrl
        from PyQt6.QtGui import QDropEvent
        from PyQt6.QtCore import Qt
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            tela = j.tela_inicial
            outro = os.path.join(p, "planilha.xlsx")
            open(outro, "w").close()
            for caminho, abre in ((outro, False),
                                  (icms_basico().gravar(p), True)):
                dados = QMimeData()
                dados.setUrls([QUrl.fromLocalFile(caminho)])
                ev = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction,
                                dados, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier)
                tela.dropEvent(ev)
                _esperar()
                self.assertEqual(j.doc is not None, abre, caminho)
            self.assertEqual(j.doc.layout, "ICMS")
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_abrir_outro_pergunta_pelas_alteracoes(self):
        """Até a 0.58.0 abrir outro arquivo (menu, histórico, arrastar)
        por cima de um alterado descartava as alterações sem perguntar."""
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            doc = j.doc
            j.alterado = True
            outro = os.path.join(p, "outro")
            os.makedirs(outro)
            segundo = contrib_basico().gravar(outro)
            with mock.patch.object(type(j), "_perguntar_salvar",
                                   lambda *a: "cancelar"):
                self.assertFalse(j.abrir_caminho(segundo))
            self.assertIs(j.doc, doc)
            with mock.patch.object(type(j), "_perguntar_salvar",
                                   lambda *a: "descartar"):
                self.assertTrue(j.abrir_caminho(segundo))
            self.assertEqual(j.doc.layout, "CONTRIB")
            _esperar()
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

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
                # o leiaute habilita a maior parte do menu (desde a 0.56.0
                # sem *Limpar NULL* e *Validar campos*, absorvidos pelo
                # Diagnóstico)
                self.assertGreater(disparadas, 18)
                for dlg in QApplication.topLevelWidgets():
                    if dlg is not j:
                        dlg.close()
                j.alterado = False
                j.close()


@unittest.skipUnless(TEM_QT, "PyQt6 não instalado")
class TestTabelaDeAcoes(unittest.TestCase):
    """Uma ação é uma linha de `acoes.ACOES` — e a linha tem de valer."""

    @classmethod
    def setUpClass(cls):
        cls.app = _app()
        from sped_tables.interface import acoes, janela
        cls.acoes = acoes
        cls.janela = janela.JanelaPrincipal()

    @classmethod
    def tearDownClass(cls):
        cls.janela.close()

    def test_todo_metodo_existe(self):
        for a in self.acoes.ACOES + (self.acoes.ACAO_TEMA,):
            with self.subTest(acao=a.atributo):
                self.assertTrue(callable(getattr(self.janela, a.metodo, None)))

    def test_toda_acao_visivel_esta_num_menu_ou_na_barra(self):
        alcancaveis = set()
        for menu in (self.janela.menu_icms, self.janela.menu_contrib,
                     self.janela.menu_gerais):
            alcancaveis |= set(menu.actions())
        alcancaveis |= set(self.janela.toolbar.actions())
        for a in self.acoes.ACOES:
            if a.onde == self.acoes.OCULTA:
                continue
            with self.subTest(acao=a.atributo):
                self.assertIn(getattr(self.janela, a.atributo), alcancaveis)

    def test_sem_arquivo_so_o_que_nao_precisa_de_arquivo(self):
        for a in self.acoes.ACOES:
            with self.subTest(acao=a.atributo):
                self.assertEqual(getattr(self.janela, a.atributo).isEnabled(),
                                 a.quando == self.acoes.SEMPRE)

    def test_habilitacao_por_leiaute(self):
        h = self.acoes.habilitada
        icms = next(a for a in self.acoes.ACOES
                    if a.atributo == "act_recalc_icms")
        contrib = next(a for a in self.acoes.ACOES
                       if a.atributo == "act_recalc_m")
        pva = next(a for a in self.acoes.ACOES
                   if a.atributo == "act_abrir_pva")
        self.assertTrue(h(icms, "ICMS"))
        self.assertFalse(h(icms, "CONTRIB"))
        self.assertTrue(h(contrib, "CONTRIB"))
        self.assertFalse(h(pva, "ICMS", tem_pva=False))
        self.assertTrue(h(pva, "ICMS", tem_pva=True))
        self.assertFalse(h(pva, None, tem_pva=True))


@unittest.skipUnless(TEM_QT, "PyQt6 não instalado")
class TestFormularioEmpresa(unittest.TestCase):
    """O formulário único do painel e do diálogo de empresa."""

    def test_mostrar_e_aplicar(self):
        _app()
        from sped_tables.dominio import empresas as emp_mod
        from sped_tables.interface.formulario_empresa import FormularioEmpresa
        gravou = []
        f = FormularioEmpresa("Cadastro", lambda: gravou.append(1))
        e = emp_mod.Empresa(cnpj="11222333000181", nome="X", uf="mg",
                            regime_pis_cofins="nao_cumulativo",
                            aliq_pis_saida="1,65", aliq_cofins_saida="7,6",
                            cst_entrada_sem_credito="73")
        f.mostrar(e)
        # mostrar não pode trocar as alíquotas pelo padrão do regime
        self.assertEqual(f.ed_pis_s.text(), "1,65")
        self.assertEqual(f.ed_cnpj.text(), "11.222.333/0001-81")
        f.ed_pis_s.setText("1.65")          # digitado com ponto
        f.ed_uf.setText("sp")
        novo = f.aplicar(emp_mod.Empresa(cnpj=e.cnpj))
        self.assertEqual((novo.aliq_pis_saida, novo.uf,
                          novo.cst_entrada_sem_credito), ("1,65", "SP", "73"))
        # trocar o regime propõe as alíquotas nominais dele
        f._selecionar(f.cb_pc, "cumulativo")
        self.assertEqual((f.ed_pis_s.text(), f.ed_cof_s.text()), ("0,65", "3"))
        f.close()


@unittest.skipUnless(TEM_QT, "PyQt6 não instalado")
class TestInicializacao(unittest.TestCase):
    """`main()` inteiro, em subprocesso: tradução, tema, fallback, janela e
    abertura pela linha de comando — até o laço de eventos e de volta."""

    SCRIPT = textwrap.dedent("""
        import os, sys
        sys.path.insert(0, %r)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["SPED_TABLES_DADOS"] = %r
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        import runpy
        from sped_tables.interface import app
        from sped_tables.interface.janela import JanelaPrincipal
        exec_original = QApplication.exec
        def exec_curto(app):
            QTimer.singleShot(500, app.quit)
            return exec_original()
        QApplication.exec = exec_curto
        abrir = JanelaPrincipal.abrir_caminho
        def abrir_e_contar(self, caminho):
            ok = abrir(self, caminho)
            print("aberto", ok, self.doc.layout, len(self.doc.registros))
            return ok
        JanelaPrincipal.abrir_caminho = abrir_e_contar
        # erro vira linha na saída em vez da caixa modal, que travaria o teste
        app.avisar_erro = lambda t, v, d, c: print("ERRO", t.__name__, v)
        sys.argv = ["sped_editor.py", %r]
        try:
            # o lançador de verdade, como o usuário roda
            runpy.run_path(os.path.join(%r, "sped_editor.py"),
                           run_name="__main__")
        except SystemExit as fim:
            print("saiu", fim.code)
    """)

    def test_main_abre_o_arquivo_da_linha_de_comando(self):
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with PastaTemporaria() as p:
            arq = icms_basico().gravar(p)
            r = subprocess.run(
                [sys.executable, "-c", self.SCRIPT % (raiz, p, arq, raiz)],
                capture_output=True, text=True, timeout=120)
        self.assertNotIn("ERRO", r.stdout)
        self.assertIn("aberto True ICMS", r.stdout, r.stderr)
        self.assertIn("saiu 0", r.stdout, r.stderr)


@unittest.skipUnless(TEM_QT, "PyQt6 não instalado")
class TestAutoteste(unittest.TestCase):
    """`--autoteste`: o roteiro 2.2 que o executável roda sobre si mesmo.
    Aqui, do código-fonte, pelo lançador de verdade."""

    def test_autoteste_pelo_lancador(self):
        import json
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with PastaTemporaria() as p:
            arq = contrib_basico().gravar(p)
            rel = os.path.join(p, "relatorio.json")
            dados = os.path.join(p, "dados")
            ambiente = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                            SPED_TABLES_DADOS=dados)
            r = subprocess.run(
                [sys.executable, os.path.join(raiz, "sped_editor.py"),
                 "--autoteste", rel, arq],
                capture_output=True, text=True, timeout=120, env=ambiente)
            with open(rel, encoding="utf-8") as fh:
                saida = json.load(fh)
            self.assertTrue(os.path.isdir(os.path.join(dados, "logs")))
        falhou = [i for i in saida["itens"] if not i["ok"]]
        self.assertEqual(falhou, [], r.stderr)
        self.assertEqual(r.returncode, 0)
        nomes = [i["nome"] for i in saida["itens"]]
        self.assertIn("tradução pt-BR do Qt", nomes)
        self.assertIn("abrir, salvar e reabrir", nomes)

    def test_sem_pasta_indicada_isola_os_dados(self):
        from sped_tables.interface import autoteste
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SPED_TABLES_DADOS", None)
            pasta = autoteste._isolar_dados()
            try:
                self.assertEqual(os.environ["SPED_TABLES_DADOS"], pasta)
                self.assertIn("autoteste", pasta)
            finally:
                os.rmdir(pasta)
        # com a pasta indicada, é ela que vale
        self.assertIsNone(autoteste._isolar_dados())


if __name__ == "__main__":
    unittest.main()

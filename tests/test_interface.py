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

    def test_gravar_com_c170_em_nfce_pergunta(self):
        """NFC-e com C170 fictícios é estrutura inválida: gravar pergunta, e
        no ICMS/IPI oferece remover o andaime antes."""
        from tests.test_conferencia import _nfes, icms_nfce, xml_nfce_st

        def escolhe(rotulo):
            return lambda caixa: next(
                (b for b in caixa.buttons() if b.text() == rotulo), None)
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_nfce().gravar(p)))
            j.doc.gerar_c170_ficticios_65(_nfes(xml_nfce_st()))
            destino = os.path.join(p, "saida.txt")
            with mock.patch.object(QMessageBox, "clickedButton",
                                   escolhe("Cancelar")):
                j._gravar(destino)
            self.assertFalse(os.path.exists(destino))
            with mock.patch.object(QMessageBox, "clickedButton",
                                   escolhe("Remover e gravar")):
                j._gravar(destino)
            with open(destino, encoding="latin-1") as fh:
                self.assertNotIn("|C170|", fh.read())
            self.assertEqual(j.doc.documentos_65_com_c170(), [])
            _esperar()
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_ajuda_do_guia_na_grade(self):
        """O cabeçalho da coluna traz o que o guia diz do campo, e o F1 abre
        a ajuda do registro rolada até a coluna atual."""
        from sped_tables.interface.grade import MasterDetailWidget
        from sped_tables.interface.dialogos.ajuda import DialogoAjuda
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            from sped_tables.interface.grade import BlocoWidget
            bloco = next(w for w in j.findChildren(BlocoWidget)
                         if w.bloco == "C")
            g = bloco.widget_do_tipo("C100")
            self.assertIsInstance(g, MasterDetailWidget)
            nome = g._colunas[1]
            self.assertIn(nome, g.tabela.horizontalHeaderItem(1).toolTip())
            g.tabela.setCurrentCell(0, 1)
            g.abrir_ajuda()
            self.assertIsInstance(g._dlg_ajuda, DialogoAjuda)
            self.assertIn(nome, g._dlg_ajuda.texto.toPlainText())
            g._dlg_ajuda.close()
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_leitura_de_xmls_em_segundo_plano(self):
        """A ação que lê uma pasta de XMLs passa pela barra de andamento
        (leitura fora da thread da interface) e chega ao resultado; erro e
        cancelamento do trabalho voltam para a thread da interface. Os XMLs
        ficam na sessão: a segunda função não pergunta a pasta de novo, e
        *XMLs do período* pergunta."""
        from sped_tables.infra.paralelo import Cancelado
        from sped_tables.interface.comum import em_segundo_plano
        from tests.fabrica import nfe_xml
        with PastaTemporaria() as p:
            pasta = os.path.join(p, "xmls")
            os.makedirs(pasta)
            with open(os.path.join(pasta, "n.xml"), "w",
                      encoding="utf-8") as fh:
                fh.write(nfe_xml())
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            with mock.patch.object(QFileDialog, "getExistingDirectory",
                                   staticmethod(lambda *a, **k: pasta)):
                j.conferir_itens_xml()
            resultado = j._dlg_conferencia.resultado
            self.assertEqual(resultado["resumo"]["itens_conferidos"], 3)
            self.assertIn(pasta, j.sessao.origem_xmls)
            # a segunda não pergunta (o diálogo de pasta devolveria "")
            perguntas = []
            with mock.patch.object(
                    QFileDialog, "getExistingDirectory",
                    staticmethod(lambda *a, **k: perguntas.append(1) or "")):
                j.conferir_itens_xml()
                self.assertEqual(perguntas, [])
                self.assertEqual(j._dlg_conferencia.resultado["resumo"]
                                 ["itens_conferidos"], 3)
                j.escolher_xmls()
                self.assertEqual(perguntas, [1])
            # fechar o arquivo esquece os XMLs
            j.alterado = False
            j.fechar_arquivo()
            self.assertIsNone(j.sessao.xmls)
            j.close()

        def andando(progresso, cancelar):
            progresso(1, 2)
            progresso(2, 2)
            return "feito"
        self.assertEqual(em_segundo_plano(None, "t", "x", andando), "feito")

        def quebra(_p, _c):
            raise ValueError("defeito")
        with self.assertRaises(ValueError):
            em_segundo_plano(None, "t", "x", quebra)

        def cancela(_p, cancelar):
            raise Cancelado()
        with self.assertRaises(Cancelado):
            em_segundo_plano(None, "t", "x", cancela)
        self.assertEqual(self.erros, [], self._falhas())

    def test_janelas_soltas_nao_bloqueiam(self):
        """Ferramentas abertas ao mesmo tempo, nenhuma modal: a janela
        principal continua clicável. Reabrir substitui a anterior, e o aviso
        de resultado leva à etapa seguinte pelo botão."""
        from PyQt6.QtWidgets import QMessageBox as Caixa
        from sped_tables.interface.comum import informar
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            j.diagnosticar()
            j.configurar_empresa()
            j.alterar_datas()
            abertas = dict(j._janelas)
            self.assertGreaterEqual(len(abertas), 3)
            for dlg in abertas.values():
                self.assertFalse(dlg.isModal(), type(dlg).__name__)
                self.assertTrue(dlg.isVisible(), type(dlg).__name__)
            self.assertIsNone(QApplication.activeModalWidget())
            self.assertTrue(j.isEnabled())
            # reabrir fecha a anterior em vez de empilhar duas
            antigo = j._janelas["DialogoDiagnostico"]
            j.diagnosticar()
            self.assertIsNot(j._janelas["DialogoDiagnostico"], antigo)
            self.assertFalse(antigo.isVisible())
            # o botão da etapa seguinte no aviso
            chamou = []
            caixa = informar(j, "Feito", "ok",
                             proximos=(("Seguir", lambda: chamou.append(1)),))
            botao = next(b for b in caixa.buttons()
                         if caixa.buttonRole(b)
                         == Caixa.ButtonRole.ActionRole)
            botao.click()
            self.assertEqual(chamou, [1])
            for dlg in list(j._janelas.values()):
                dlg.close()
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_regenerar_c175_com_ficticios(self):
        """Com C170 em documento modelo 65 a ação monta a prévia e regenera
        (até a 1.1.0-dev.9 levantava NameError: o teste das ações nunca
        chegava aqui, porque sem fictícios ela sai antes)."""
        from PyQt6.QtWidgets import QMessageBox as Caixa
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(contrib_basico().gravar(p)))
            _esperar()
            i_mod = j.doc._ix("C100", "COD_MOD")
            c100 = next(r for r in j.doc.registros if r.reg == "C100")
            c100.set_valor(i_mod, "65")
            self.assertEqual(len(j.doc.documentos_65_com_c170()), 1)
            # clica em "Regenerar" (o primeiro botão da caixa)
            with mock.patch.object(Caixa, "exec", lambda cx: 0), \
                    mock.patch.object(Caixa, "clickedButton",
                                      lambda cx: cx.buttons()[0]):
                j.regenerar_c175_65()
            self.assertEqual(j.doc.documentos_65_com_c170(), [])
            self.assertTrue(any(r.reg == "C175" for r in c100.filhos))
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_corrigir_itens_pelo_xml_na_conferencia(self):
        from tests.fabrica import nfe_xml
        with PastaTemporaria() as p:
            pasta = os.path.join(p, "xmls")
            os.makedirs(pasta)
            with open(os.path.join(pasta, "n.xml"), "w",
                      encoding="utf-8") as fh:
                fh.write(nfe_xml(itens=[{}, {"vICMS": "2.00"}, {}]))
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            with mock.patch.object(QFileDialog, "getExistingDirectory",
                                   staticmethod(lambda *a, **k: pasta)):
                j.conferir_itens_xml("ICMS")
            dlg = j._dlg_conferencia
            self.assertTrue(dlg._b_corr.isEnabled())
            dlg.corrigir()
            i = j.doc._ix("C170", "VL_ICMS")
            self.assertEqual([r.valor(i) for r in j.doc.registros
                              if r.reg == "C170"], ["1,80", "2,00", "1,80"])
            self.assertEqual(dlg.resultado["resumo"]["divergencias"], 0)
            self.assertTrue(j.alterado)
            dlg.close()
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_fundir_chaves_repetidas_pela_acao(self):
        """C175 repetido na NFC-e: a ação mostra a prévia e, aceita, funde."""
        from sped_tables.dominio import referencias
        from tests.test_correcoes import FonteComChaves, _nfce_com_c175
        antes = referencias.definir(FonteComChaves())
        try:
            with PastaTemporaria() as p:
                j = self.ed.JanelaPrincipal()
                self.assertTrue(j.abrir_caminho(
                    _nfce_com_c175({}, {}).gravar(p)))
                _esperar()
                j.act_fundir_chaves.trigger()
                dlg = j._janelas["DialogoChavesRepetidas"]
                self.assertEqual(dlg.tab.rowCount(), 1)
                self.assertTrue(dlg.b_fundir.isEnabled())
                dlg.accept()
                self.assertEqual(len([r for r in j.doc.registros
                                      if r.reg == "C175"]), 1)
                self.assertTrue(j.alterado)
                j.alterado = False
                j.close()
        finally:
            referencias.definir(antes)
        self.assertEqual(self.erros, [], self._falhas())

    def test_cst_por_ncm_usa_a_fonte_de_referencias(self):
        """O diálogo não pede mais pasta nem arquivos: o classificador vem
        da porta, a mesma fonte das outras regras."""
        from sped_tables.dominio import referencias
        from sped_tables.dominio.ncm import ClassificadorNCM

        class Fonte(referencias.Referencias):
            def classificador_ncm(self):
                return ClassificadorNCM()

        antes = referencias.definir(Fonte())
        try:
            with PastaTemporaria() as p:
                j = self.ed.JanelaPrincipal()
                self.assertTrue(j.abrir_caminho(contrib_basico().gravar(p)))
                _esperar()
                j.verificar_cst_ncm()
                dlg = j._janelas["DialogoVerificarCST"]
                self.assertFalse(hasattr(dlg, "ed_pasta"))
                dlg._verificar()
                self.assertEqual(dlg.tab.rowCount(), 0)
                j.close()
        finally:
            referencias.definir(antes)
        self.assertEqual(self.erros, [], self._falhas())

    def test_diagnostico_mostra_a_versao_do_leiaute_da_base(self):
        """A base entrega a versão do leiaute que valeu para o arquivo: o
        texto de origem do Diagnóstico a mostra (sem ela saía "versão ?")."""
        from PyQt6.QtWidgets import QLabel
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            j.diagnosticar()
            textos = [l.text() for l in
                      j._janelas["DialogoDiagnostico"].findChildren(QLabel)]
            self.assertTrue(any("leiaute da versão 020 (" in t
                                for t in textos), textos)
            self.assertFalse(any("versão ?" in t for t in textos), textos)
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_resumo_da_validacao_cita_a_versao_e_a_base(self):
        """"Validar campos" diz de onde veio a validação: o leiaute da
        versão do arquivo, na base de referência em uso. Sem o leiaute do
        arquivo, diz que valeram só as regras embutidas."""
        from sped_tables.dominio import validacao
        from sped_tables.dominio.sped_model import SpedDocument
        from sped_tables.interface.controladores.gerais import (
            ControladorGerais)
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(icms_basico().gravar(p))
        dominios, info = validacao.dominios_do_documento(doc)
        self.assertEqual(info["versao"], "020")
        texto = ControladorGerais._resumo_tabelas(dominios, info)
        self.assertIn("leiaute da versão 020 (base de referência ", texto)
        self.assertNotIn("PVA", texto)
        self.assertIn("Base de referência sem o leiaute deste arquivo",
                      ControladorGerais._resumo_tabelas({}, {}))

    def test_cst_por_ncm_sem_tabelas_avisa_e_nao_acusa(self):
        """Fonte sem classificador (`None`): o diálogo recusa com o aviso em
        vez de comparar com uma tabela vazia, que tributaria todo NCM."""
        from sped_tables.dominio import referencias

        class FonteSemTabelas(referencias.Referencias):
            def classificador_ncm(self):
                return None

        antes = referencias.definir(FonteSemTabelas())
        try:
            with PastaTemporaria() as p:
                j = self.ed.JanelaPrincipal()
                self.assertTrue(j.abrir_caminho(contrib_basico().gravar(p)))
                _esperar()
                j.verificar_cst_ncm()
                dlg = j._janelas["DialogoVerificarCST"]
                with mock.patch.object(QMessageBox, "warning") as aviso:
                    dlg._verificar()
                self.assertEqual(aviso.call_count, 1)
                self.assertIn("base de referência", aviso.call_args[0][2])
                self.assertEqual(dlg.tab.rowCount(), 0)
                self.assertFalse(dlg.b_corrigir.isEnabled())
                self.assertEqual(dlg.lbl.text(), "—")
                j.close()
        finally:
            referencias.definir(antes)
        self.assertEqual(self.erros, [], self._falhas())

    def test_regenerar_entradas_pela_tela(self):
        from tests.fabrica import nfe_xml
        with PastaTemporaria() as p:
            pasta = os.path.join(p, "xmls")
            os.makedirs(pasta)
            with open(os.path.join(pasta, "n.xml"), "w",
                      encoding="utf-8") as fh:
                fh.write(nfe_xml(itens=[{}, {"vProd": "12.00"}, {}]))
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            with mock.patch.object(QFileDialog, "getExistingDirectory",
                                   staticmethod(lambda *a, **k: pasta)):
                j.regenerar_entradas()
            # a prévia é janela solta: nada muda até a pessoa confirmar
            self.assertFalse(j.alterado)
            j._janelas["DialogoRegenerarEntradas"].accept()
            i = j.doc._ix("C170", "VL_ITEM")
            valores = [r.valor(i) for r in j.doc.registros
                       if r.reg == "C170"]
            self.assertEqual(valores, ["10,00", "12,00", "10,00"])
            self.assertTrue(j.alterado)
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_erp_pela_tela(self):
        """Com uma conexão de ERP (SQLite) vinculada à empresa: o perfil
        abre e lê a estrutura, 0200 e 0150 são corrigidos pela prévia, o
        inventário lê o estoque e as conferências leem os XMLs do banco."""
        from sped_tables.infra import sistemas_erp
        from sped_tables.interface import comum
        from sped_tables.interface.dialogos import erp as dlg_erp
        from sped_tables.interface.dialogos.inventario import (
            DialogoImportarInventario)
        from tests.fabrica import CNPJ_TESTE
        from tests.test_erp import _banco_sqlite, _sistema_sqlite
        from sped_tables.dominio import erp
        with PastaTemporaria() as p:
            banco = os.path.join(p, "erp.db")
            _banco_sqlite(banco)
            cfg = sistemas_erp.Configuracao(
                {"erp_sql": _sistema_sqlite()},
                [erp.Conexao("Matriz", "erp_sql", base=banco,
                             cnpjs=[CNPJ_TESTE])])
            arq_cfg = sistemas_erp.salvar(cfg)
            self.addCleanup(os.remove, arq_cfg)
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            doc = j.doc

            def valor(reg, chave, campo):
                i_cod = doc._ix(reg, "COD_ITEM" if reg == "0200"
                                else "COD_PART")
                r = next(r for r in doc.registros if r.reg == reg
                         and r.valor(i_cod) == chave)
                return r.valor(doc._ix(reg, campo))

            j.atualizar_0200_erp()
            j._janelas["erp:0200"].accept()
            self.assertEqual(valor("0200", "P1", "COD_NCM"), "04012010")
            self.assertEqual(valor("0200", "P1", "CEST"), "0200400")
            j.atualizar_0150_erp()
            j._janelas["erp:0150"].accept()
            self.assertEqual(valor("0150", "F1", "NOME"), "FORNECEDOR ERP")
            self.assertTrue(j.alterado)

            # as conferências leem os XMLs do banco, no período do arquivo
            with mock.patch.object(comum, "escolher_origem_xml",
                                   lambda *a: cfg.conexoes[0]):
                j.conferir_itens_xml()
            self.assertEqual(j._dlg_conferencia.resultado["resumo"]
                             ["itens_conferidos"], 3)
            self.assertIn("ERP", j.sessao.origem_xmls)

            inv = DialogoImportarInventario(doc, "31082026", j)
            inv._do_erp()
            self.assertEqual(len(inv.linhas_brutas), 2)
            inv._importar()
            previa = getattr(inv, "_janelas", {}).get("DialogoAtualizar0200")
            if previa is not None:
                previa.accept()
            self.assertEqual(sum(1 for r in doc.registros
                                 if r.reg == "H010"), 2)

            # o perfil: tabelas, colunas e prévia pela conexão
            d = dlg_erp.DialogoSistemasERP(j, doc=doc)
            self.assertEqual(d.lst_con.count(), 1)
            d.carregar_tabelas()
            ed = d.editores["produtos"]
            self.assertEqual(ed.cb_tabela.count(), 4)
            ed.ler_colunas()
            self.assertIn("CLASFISCAL", ed._colunas)
            self.assertIn("ex.:", ed.exemplos["cod_ncm"].text())
            ed.previsualizar()
            self.assertIn("DialogoPrevia", ed._janelas)
            d.novo_sistema()
            self.assertEqual(d.lst_sis.count(), 2)
            self.assertTrue(d.salvar())
            self.assertEqual(len(sistemas_erp.carregar().sistemas), 2)
            d.close()
            j.alterado = False
            j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_base_de_referencia_mostra_a_versao_e_importa(self):
        from sped_tables.dominio import referencias
        from sped_tables.infra import base_referencia
        from tests import base_teste
        j = self.ed.JanelaPrincipal()
        j.act_base_referencia.trigger()
        dlg = j._janelas["DialogoBaseReferencia"]
        base, _origem = base_referencia.em_uso()
        self.assertIn(base.manifesto()["versao"], dlg.lbl.text())
        with PastaTemporaria() as p:
            pacote = base_referencia.empacotar(
                base_teste.compilada(p, versao="2999.01.1"),
                os.path.join(p, "pacote.zip"))
            with mock.patch.object(
                    QFileDialog, "getOpenFileName",
                    staticmethod(lambda *a, **k: (pacote, ""))), \
                    mock.patch.object(dlg, "_confirmar", lambda m, d: True):
                dlg._importar()
            try:
                self.assertIn("2999.01.1", dlg.lbl.text())
                self.assertIn("2999.01.1", referencias.atual().nome)
            finally:
                os.remove(base_referencia.caminho_importado())
                from sped_tables.aplicacao import montagem
                montagem.configurar()
        j.close()
        self.assertEqual(self.erros, [], self._falhas())

    def test_diagnostico_sem_base_avisa_pela_acao(self):
        """O último elo do "sem base": a fonte vazia chega à tela. Com a
        fonte vazia, a ação do Diagnóstico (disparada pela tabela de ações,
        não o diálogo montado à mão) mostra o rótulo "Base de referência
        indisponível" com o papel `aviso` (não `info`), não mostra o texto
        "Verificado com o leiaute" e não tem nenhum rótulo `ok` (verde)."""
        from PyQt6.QtWidgets import QLabel
        from sped_tables.dominio import referencias
        antes = referencias.definir(None)              # fonte vazia: sem base
        try:
            with PastaTemporaria() as p:
                j = self.ed.JanelaPrincipal()
                self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
                _esperar()
                j.act_diagnostico.trigger()
                rotulos = j._janelas["DialogoDiagnostico"].findChildren(
                    QLabel)
                textos = [l.text() for l in rotulos]
                indisponivel = [l for l in rotulos if
                                "Base de referência indisponível" in l.text()]
                self.assertEqual([l.property("role") for l in indisponivel],
                                 ["aviso"], textos)
                self.assertFalse(any("Verificado com o leiaute" in t
                                     for t in textos), textos)
                self.assertEqual([l.text() for l in rotulos
                                  if l.property("role") == "ok"], [])
                j.alterado = False
                j.close()
        finally:
            referencias.definir(antes)
        self.assertEqual(self.erros, [], self._falhas())

    def test_diagnostico_sem_achados_nao_aprova_sem_a_base(self):
        """Sem achados, mas sem a base (ou com a versão do arquivo fora
        dela), valeram só as regras embutidas: o cabeçalho tem o papel
        `aviso`, diz que a conferência pelo leiaute não rodou, a origem
        também é `aviso` e nenhum rótulo é `ok`. Com a base e a versão nela,
        nada muda: "Nenhum problema…" em `ok` e a origem em `info`."""
        from PyQt6.QtWidgets import QLabel
        from sped_tables.interface.controladores import gerais
        casos = (
            ({"sem_base": True}, "aviso"),
            ({"fora_da_base": "015"}, "aviso"),
            ({"versao": "020", "registros_descritor": 10}, "ok"),
        )
        with PastaTemporaria() as p:
            j = self.ed.JanelaPrincipal()
            self.assertTrue(j.abrir_caminho(icms_basico().gravar(p)))
            _esperar()
            for info, papel in casos:
                with self.subTest(info=info), mock.patch.object(
                        gerais.diagnostico, "verificar",
                        lambda doc, info=info: ([], info)):
                    j.act_diagnostico.trigger()
                    rotulos = j._janelas["DialogoDiagnostico"].findChildren(
                        QLabel)
                    textos = [l.text() for l in rotulos]
                    cab = [l for l in rotulos
                           if l.text().startswith("Nenhum problema")]
                    self.assertEqual(len(cab), 1, textos)
                    self.assertEqual(cab[0].property("role"), papel, textos)
                    origem = [l for l in rotulos if l.wordWrap()]
                    self.assertEqual(len(origem), 1, textos)
                    self.assertEqual(origem[0].property("role"),
                                     "info" if papel == "ok" else "aviso",
                                     textos)
                    if papel == "aviso":
                        self.assertIn("a conferência pelo leiaute não rodou",
                                      cab[0].text())
                        self.assertEqual(
                            [l.text() for l in rotulos
                             if l.property("role") == "ok"], [])
                    else:
                        self.assertEqual(
                            cab[0].text(),
                            "Nenhum problema nas verificações automáticas.")
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
        for menu in self.janela._menus.values():
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
        self.assertIn("leitura paralela de XMLs", nomes)

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

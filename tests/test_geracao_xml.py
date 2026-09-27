# -*- coding: utf-8 -*-
"""O caso de uso da geração pelos XMLs: memória gravada por empresa,
aprendizado com o SPED entregue e a decisão da pessoa voltando para a
memória — o bloqueio resolvido uma vez não volta no mês seguinte."""

import os
import unittest

from sped_tables.aplicacao import montagem
from sped_tables.aplicacao.geracao_xml import GeracaoXml
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import memoria as memoria_infra
from tests.fabrica import CNPJ_TESTE, PastaTemporaria, icms_basico, nfe_xml


def _grava(pasta, nome, texto):
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as fh:
        fh.write(texto)


class TestEnsinar(unittest.TestCase):

    def test_decisao_passa_a_frente_e_substitui_a_anterior(self):
        m = mi.nova(CNPJ_TESTE)

        class Item:
            cfop, icms_cst = "5908", "000"
        mi.ensinar(m, "11444777000161", "X", "5908", "000", {"CFOP": "1949"})
        esc = mi.escrituracao(m, "11444777000161", "X", Item)
        # sem nada aprendido: o CST do fornecedor e sem crédito
        self.assertEqual((esc["CFOP"], esc["CST_ICMS"], esc["CREDITA_ICMS"]),
                         ("1949", "000", "N"))
        mi.ensinar(m, "11444777000161", "X", "5908", "000", {"CFOP": "1556"},
                   cod_proprio="P9")
        self.assertEqual(
            mi.escrituracao(m, "11444777000161", "X", Item)["CFOP"], "1556")
        self.assertEqual(mi.codigo_proprio(m, "11444777000161", "X"),
                         ("P9", False))

    def test_decisao_parte_do_que_a_geracao_usou(self):
        """Só o CST de PIS informado, num produto escriturado pela
        correlação de CFOP: o CFOP usado vai junto, senão a memória
        guardaria CFOP vazio e a próxima geração não bloquearia."""
        m = mi.nova(CNPJ_TESTE)

        class Item:
            cfop, icms_cst = "5102", "000"
        usado = {"CFOP": "1102", "CST_ICMS": "000", "CREDITA_ICMS": "S"}
        mi.ensinar(m, "11444777000161", "X", "5102", "000",
                   {"CST_PIS": "70", "CST_COFINS": "70"}, usado=usado)
        esc = mi.escrituracao(m, "11444777000161", "X", Item)
        self.assertEqual((esc["CFOP"], esc["CREDITA_ICMS"], esc["CST_PIS"]),
                         ("1102", "S", "70"))
        # sem o que foi usado, não há CFOP: recusa, e nada gravado
        m = mi.nova(CNPJ_TESTE)
        with self.assertRaises(ValueError):
            mi.ensinar(m, "11444777000161", "X", "5102", "000",
                       {"CST_PIS": "70"})
        self.assertEqual(m["produtos"], {})

    def test_decisao_invalida_nao_entra_na_memoria(self):
        m = mi.nova(CNPJ_TESTE)
        with self.assertRaises(ValueError) as ctx:
            mi.ensinar(m, "11444777000161", "X", "5102", "000",
                       {"CFOP": "5102", "CST_PIS": "5"})
        # as duas de uma vez, e nada gravado
        self.assertIn("CFOP", str(ctx.exception))
        self.assertIn("CST_PIS", str(ctx.exception))
        self.assertEqual(m["produtos"], {})
        # alíquota no formato do SPED, venha com ponto ou vírgula
        self.assertEqual(mi.validar_decisao({"ALIQ_PIS": "1.650",
                                             "ALIQ_COFINS": "7,6",
                                             "CST_IPI": ""}),
                         {"ALIQ_PIS": "1,65", "ALIQ_COFINS": "7,6"})


class _ComPasta(unittest.TestCase):
    """Pasta de dados própria (a memória é gravada nela), o SPED entregue
    e os XMLs do mês."""

    @classmethod
    def setUpClass(cls):
        montagem.configurar()

    def setUp(self):
        self._p = PastaTemporaria()
        self.pasta = self._p.__enter__()
        self._dados = os.environ.get("SPED_TABLES_DADOS")
        os.environ["SPED_TABLES_DADOS"] = os.path.join(self.pasta, "dados")
        self.sped = icms_basico().gravar(self.pasta)
        self.xmls = os.path.join(self.pasta, "xml")
        os.makedirs(self.xmls)
        _grava(self.xmls, "entrada.xml", nfe_xml(
            itens=[{"cProd": "F1"}, {"cProd": "F2"}, {"cProd": "F3"}]))

    def tearDown(self):
        os.environ["SPED_TABLES_DADOS"] = self._dados or ""
        self._p.__exit__(None, None, None)


class TestCasoDeUso(_ComPasta):

    def test_aprende_gera_decide_e_grava(self):
        g = GeracaoXml(CNPJ_TESTE)
        self.assertEqual(g.memoria["produtos"], {})
        g.aprender(self.xmls, self.sped)
        self.assertTrue(os.path.exists(memoria_infra.caminho(CNPJ_TESTE)))

        # mês seguinte: um produto com CFOP que ninguém sabe escriturar
        _grava(self.xmls, "entrada.xml", nfe_xml(
            itens=[{"cProd": "NOVO", "CFOP": "5908"}]))
        g = GeracaoXml(CNPJ_TESTE)           # a memória vem do disco
        g.ler(self.xmls)
        grupos, _previa = g.documentos("202608")
        self.assertEqual(len(grupos["entradas"]), 1)
        g.gerar("202608", leiautes=("ICMS",), saldo_credor_anterior=0,
                correlacoes={})
        self.assertIsNotNone(g.resultados["ICMS"].doc)  # sai mesmo bloqueado
        bloqueios = g.bloqueios()
        self.assertEqual([b["tipo"] for b in bloqueios],
                         ["CFOP de entrada desconhecido"])
        with self.assertRaises(ValueError):
            g.salvar("ICMS", os.path.join(self.pasta, "saida.txt"))

        g.decidir(bloqueios[0], CFOP="1949", COD_ITEM="P9")
        g = GeracaoXml(CNPJ_TESTE)
        g.ler(self.xmls)
        g.gerar("202608", leiautes=("ICMS",), saldo_credor_anterior=0,
                correlacoes={})
        self.assertEqual(g.bloqueios(), [])
        cam = g.salvar("ICMS", os.path.join(self.pasta, "saida.txt"))
        doc = SpedDocument.carregar(cam)
        c170 = next(r for r in doc.registros if r.reg == "C170")
        self.assertEqual((c170.valor(doc._ix("C170", "COD_ITEM")),
                          c170.valor(doc._ix("C170", "CFOP"))), ("P9", "1949"))

    def test_recusa_sped_de_outra_empresa(self):
        g = GeracaoXml("11444777000161")
        with self.assertRaises(ValueError):
            g.aprender(self.xmls, self.sped)

    def test_gerar_sem_ler_a_pasta(self):
        with self.assertRaises(ValueError):
            GeracaoXml(CNPJ_TESTE).gerar("202608")


if __name__ == "__main__":
    unittest.main()


try:
    from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox
    TEM_QT = True
except ImportError:                                  # pragma: no cover
    TEM_QT = False


@unittest.skipUnless(TEM_QT, "PyQt6 não instalado")
class TestTela(_ComPasta):
    """O diálogo percorre o caminho da pessoa: gerar, ver o bloqueio,
    decidir, gerar de novo e gravar.

    Nenhuma caixa de mensagem chega à tela: todas são anotadas, e o teste
    que não espera nenhuma confere que a lista ficou vazia."""

    def setUp(self):
        from unittest import mock
        super().setUp()
        self.mensagens = []

        def anota(*a, **k):
            self.mensagens.append(a[1:3])
        self._caixas = [mock.patch.object(QMessageBox, nome,
                                          staticmethod(anota))
                        for nome in ("warning", "information", "critical",
                                     "question")]
        self._caixas.append(mock.patch.object(QDialog, "exec",
                                              lambda self: 0))
        for c in self._caixas:
            c.start()

    def tearDown(self):
        for c in self._caixas:
            c.stop()
        super().tearDown()

    def test_aprende_gera_decide_e_grava(self):
        from unittest import mock
        from tests.test_interface import _app
        from sped_tables.interface.dialogos import geracao as tela
        _app()
        GeracaoXml(CNPJ_TESTE).aprender(self.xmls, self.sped)
        _grava(self.xmls, "entrada.xml", nfe_xml(
            itens=[{"cProd": "NOVO", "CFOP": "5908"}]))

        dlg = tela.DialogoGerarDeXml(correlacoes={})
        dlg.empresa.setEditText(CNPJ_TESTE)
        self.assertIsNotNone(dlg.geracao)
        self.assertIn("produto", dlg.lbl_memoria.text())
        dlg.pasta.setText(self.xmls)
        dlg.periodo.setText("08/2026")
        dlg.saldo.setText("0")
        dlg._gerar()
        self.assertEqual(self.mensagens, [])
        self.assertEqual(dlg.t_doc.rowCount(), 1)
        self.assertEqual(dlg.t_rev.item(0, 1).text(), "bloqueia")
        self.assertFalse(dlg.b_salvar["ICMS"].isEnabled())

        dlg.t_rev.selectRow(0)
        self.assertTrue(dlg.b_decidir.isEnabled())

        def decidir(janela):
            janela.edits["CFOP"].setText("1949")
            janela.edits["COD_ITEM"].setText("P9")
            janela._conferir()
            return QDialog.DialogCode.Accepted
        with mock.patch.object(tela.DialogoDecisao, "exec", decidir):
            dlg._decidir()
        self.assertTrue(dlg.b_salvar["ICMS"].isEnabled())

        destino = os.path.join(self.pasta, "gerado.txt")
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               staticmethod(lambda *a, **k: (destino, ""))), \
                mock.patch.object(QMessageBox, "exec", lambda self: 0):
            dlg._salvar("ICMS")
        doc = SpedDocument.carregar(destino)
        c170 = next(r for r in doc.registros if r.reg == "C170")
        self.assertEqual(c170.valor(doc._ix("C170", "CFOP")), "1949")

    def test_documento_desmarcado_fica_de_fora(self):
        from tests.test_interface import _app
        from sped_tables.interface.dialogos import geracao as tela
        _app()
        GeracaoXml(CNPJ_TESTE).aprender(self.xmls, self.sped)
        dlg = tela.DialogoGerarDeXml(correlacoes={})
        dlg.empresa.setEditText(CNPJ_TESTE)
        dlg.pasta.setText(self.xmls)
        dlg.periodo.setText("08/2026")
        dlg.saldo.setText("0")
        dlg._gerar()
        self.assertEqual(self.mensagens, [])
        from PyQt6.QtCore import Qt
        dlg.t_doc.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(dlg.b_salvar["ICMS"].isEnabled())
        dlg._gerar()
        res = dlg.geracao.resultados["ICMS"]
        self.assertFalse(any(r.reg == "C100" for r in res.doc.registros))
        # continua na lista, desmarcado, para poder voltar atrás
        self.assertEqual(dlg.t_doc.rowCount(), 1)
        self.assertEqual(dlg.t_doc.item(0, 0).checkState(),
                         Qt.CheckState.Unchecked)

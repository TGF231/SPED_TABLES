# -*- coding: utf-8 -*-
"""Leitura de XMLs repartida entre processos (`infra.paralelo`,
`aplicacao.leitura_xml`): o resultado tem de ser **o mesmo** da leitura um
por um, na mesma ordem — é ela que decide qual de dois XMLs repetidos vale."""

import os
import unittest
from unittest import mock

from sped_tables.aplicacao import leitura_xml
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.infra import paralelo
from tests.fabrica import PastaTemporaria, evento_cancelamento_xml, nfe_xml

QTD = 300            # acima de paralelo.MINIMO_PROCESSOS: sobe processos


def _chave(i):
    return "3126081144477700016165001%09d1%08d" % (i + 1, i)


def _gravar(pasta, nome, texto):
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as fh:
        fh.write(texto)


def _pasta_com_xmls(p):
    sub = os.path.join(p, "sub")
    os.makedirs(sub)
    for i in range(QTD):
        _gravar(sub if i % 3 == 0 else p, "%04d.xml" % i,
                nfe_xml(nnf=str(i + 1), mod="65", chave=_chave(i)))
    _gravar(p, "ruim.xml", "<isto nao fecha")
    _gravar(p, "texto.xml", "<?xml version='1.0'?><outra/>")
    _gravar(p, "repetido.xml", nfe_xml(nnf="1", mod="65", chave=_chave(0)))
    _gravar(p, "cancelamento.xml", evento_cancelamento_xml(_chave(7)))


def _resumo(lote):
    return ([(n.chave, n.nnf, len(n.itens), n.cancelada) for n in lote.nfes],
            sorted(lote.erros), sorted(lote.repetidos), len(lote.eventos))


def _falha(_itens):
    raise ValueError("defeito no trabalho")


class TestLeituraParalela(unittest.TestCase):

    def test_igual_a_leitura_um_por_um(self):
        with PastaTemporaria() as p:
            _pasta_com_xmls(p)
            serial = xf.ler_pasta_fiscal(p)
            paralela = leitura_xml.ler_pasta_fiscal(p)
        self.assertEqual(_resumo(paralela), _resumo(serial))
        self.assertEqual(len(paralela.nfes), QTD)
        self.assertEqual(len(paralela.erros), 2)        # ruim e texto
        self.assertTrue(next(n for n in paralela.nfes
                             if n.chave == _chave(7)).cancelada)

    def test_ler_pasta_sem_subpastas(self):
        with PastaTemporaria() as p:
            _pasta_com_xmls(p)
            serial = xf.ler_pasta(p)
            paralela = leitura_xml.ler_pasta(p)
        self.assertEqual([n.chave for n in paralela[0]],
                         [n.chave for n in serial[0]])
        self.assertEqual(sorted(paralela[1]), sorted(serial[1]))
        self.assertEqual(len(paralela[0]), QTD - QTD // 3 + 1)

    def test_andamento_e_cancelamento(self):
        vistos = []
        with PastaTemporaria() as p:
            _pasta_com_xmls(p)
            leitura_xml.ler_pasta_fiscal(
                p, progresso=lambda f, t: vistos.append((f, t)))
            with self.assertRaises(paralelo.Cancelado):
                leitura_xml.ler_pasta_fiscal(p, cancelar=lambda: True)
        total = QTD + 4
        self.assertEqual(vistos[-1], (total, total))
        self.assertEqual([f for f, _t in vistos], sorted(f for f, _t in vistos))

    def test_sem_processos_segue_com_threads(self):
        quebrado = mock.Mock(side_effect=OSError("sem permissão"))
        with PastaTemporaria() as p:
            _pasta_com_xmls(p)
            serial = xf.ler_pasta_fiscal(p)
            with mock.patch.object(paralelo.cf, "ProcessPoolExecutor",
                                   quebrado),                     self.assertLogs(paralelo.log, "WARNING"):
                paralela = leitura_xml.ler_pasta_fiscal(p)
        quebrado.assert_called_once()
        self.assertEqual(_resumo(paralela), _resumo(serial))

    def test_erro_do_trabalho_sobe(self):
        for qtd in (10, 2 * paralelo.PEDACO, QTD):       # série, threads, processos
            with self.subTest(qtd=qtd), self.assertRaises(ValueError):
                paralelo.em_lotes(_falha, range(qtd))

    def test_quantos_trabalhadores(self):
        with mock.patch.object(paralelo.config, "ler",
                               return_value={"trabalhadores": 3}):
            self.assertEqual(paralelo.trabalhadores(), 3)
        for valor in ({}, {"trabalhadores": "abc"}, {"trabalhadores": 0}):
            with mock.patch.object(paralelo.config, "ler",
                                   return_value=valor):
                n = paralelo.trabalhadores()
            self.assertTrue(1 <= n <= paralelo.MAXIMO, valor)

    def test_um_trabalhador_le_em_serie(self):
        with mock.patch.object(paralelo, "trabalhadores", return_value=1), \
                mock.patch.object(paralelo.cf, "ThreadPoolExecutor") as th, \
                mock.patch.object(paralelo.cf, "ProcessPoolExecutor") as pr:
            self.assertEqual(paralelo.em_lotes(sorted, [3, 1, 2], pedaco=2),
                             [1, 3, 2])
        th.assert_not_called()
        pr.assert_not_called()


if __name__ == "__main__":
    unittest.main()

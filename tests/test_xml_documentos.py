# -*- coding: utf-8 -*-
"""Leitura de documentos fiscais para gerar o SPED do zero: NF-e com
participantes e protocolo, CT-e (modelo 57) e eventos de cancelamento.

XML sintético, montado na fábrica — nenhum documento de cliente.
"""

import os
import unittest

from sped_tables.dominio import xml_fiscal as xf
from tests.fabrica import (CNPJ_TESTE, PastaTemporaria, cte_xml,
                           evento_cancelamento_xml, nfe_xml)


def _grava(pasta, nome, texto):
    cam = os.path.join(pasta, nome)
    os.makedirs(os.path.dirname(cam), exist_ok=True)
    with open(cam, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return cam


class TestCTe(unittest.TestCase):

    def _ler(self, **k):
        with PastaTemporaria() as p:
            return xf.ler_cte(_grava(p, "cte.xml", cte_xml(**k)))

    def test_campos_do_d100(self):
        c = self._ler()
        self.assertEqual((c.mod, c.serie, c.nct, c.cfop), ("57", "1", "456",
                                                           "6352"))
        self.assertEqual(c.chave[20:22], "57")
        self.assertEqual((c.cmun_ini, c.uf_ini, c.cmun_fim, c.uf_fim),
                         ("3550308", "SP", "3106200", "MG"))
        self.assertEqual(c.vtprest, 100.0)
        self.assertEqual((c.icms_cst, c.icms_vbc, c.icms_aliq, c.icms_vicms),
                         ("00", 100.0, "12.00", 12.0))
        self.assertEqual(c.situacao, "autorizada")
        self.assertEqual(c.chaves_nfe,
                         ["31260811444777000161550010000001231000001238"])
        self.assertEqual(c.emit.cnpj, "99888777000166")
        self.assertEqual(c.emit.cod_mun, "3106200")

    def test_tomador_pelo_toma3(self):
        """O tomador decide o papel da empresa: emitente = saída;
        tomador = entrada."""
        for cod, cnpj in (("0", "11444777000161"), ("3", CNPJ_TESTE)):
            c = self._ler(toma=cod)
            self.assertEqual(c.toma.cnpj, cnpj, cod)
        c = self._ler(toma="0")
        self.assertEqual(c.papel_toma, "rem")

    def test_tomador_terceiro_no_toma4(self):
        c = self._ler(toma4=("55666777000188", "OUTRO TOMADOR"))
        self.assertEqual((c.papel_toma, c.toma.cnpj, c.toma.nome),
                         ("toma", "55666777000188", "OUTRO TOMADOR"))

    def test_grupos_de_icms(self):
        c = self._ler(icms="<ICMS45><CST>40</CST></ICMS45>")
        self.assertEqual((c.icms_cst, c.icms_vbc, c.icms_vicms),
                         ("40", 0.0, 0.0))
        c = self._ler(icms="<ICMSOutraUF><CST>90</CST><pRedBCOutraUF>10.00"
                           "</pRedBCOutraUF><vBCOutraUF>90.00</vBCOutraUF>"
                           "<pICMSOutraUF>12.00</pICMSOutraUF><vICMSOutraUF>"
                           "10.80</vICMSOutraUF></ICMSOutraUF>")
        self.assertEqual((c.icms_cst, c.icms_vbc, c.icms_vicms, c.icms_red),
                         ("90", 90.0, 10.8, 10.0))
        c = self._ler(icms="<ICMSSN><CST>90</CST><indSN>1</indSN></ICMSSN>")
        self.assertTrue(c.simples)


class TestNFeParaGerar(unittest.TestCase):

    def test_participantes_e_protocolo(self):
        texto = nfe_xml(dest=None).replace(
            "<ide>", "<ide><finNFe>1</finNFe>").replace(
            "</NFe>", "</NFe><protNFe><infProt><cStat>100</cStat>"
            "</infProt></protNFe>")
        with PastaTemporaria() as p:
            n = xf.ler_nfe(_grava(p, "n.xml", texto))
        self.assertEqual((n.emit.cnpj, n.emit.nome, n.emit.cod_mun),
                         ("11444777000161", "FORNECEDOR TESTE", "3106200"))
        self.assertIsNone(n.dest)
        self.assertEqual((n.fin, n.situacao), ("1", "autorizada"))
        with PastaTemporaria() as p:
            n = xf.ler_nfe(_grava(p, "n.xml", nfe_xml()))
        self.assertEqual(n.dest.cnpj, CNPJ_TESTE)


class TestPasta(unittest.TestCase):

    def test_le_tudo_aplica_cancelamento_e_nao_descarta_nada(self):
        chave_nfe = "31260811444777000161550010000001231000001238"
        chave_cte = "31260899888777000166570010000004561000004560"
        with PastaTemporaria() as p:
            _grava(p, "nfe/n1.xml", nfe_xml())
            _grava(p, "nfe/copia/n1.xml", nfe_xml())         # repetido
            _grava(p, "cte/c1.xml", cte_xml())
            _grava(p, "eventos/canc.xml",
                   evento_cancelamento_xml(chave_cte, "cte"))
            _grava(p, "outros/lixo.xml", "<nada/>")
            _grava(p, "outros/quebrado.xml", "<abc")
            _grava(p, "leia-me.txt", "não é xml")
            lote = xf.ler_pasta_fiscal(p)
        self.assertEqual([n.chave for n in lote.nfes], [chave_nfe])
        self.assertEqual([c.chave for c in lote.ctes], [chave_cte])
        self.assertEqual(lote.ctes[0].situacao, "cancelada")
        self.assertEqual(lote.nfes[0].situacao, "sem protocolo")
        self.assertEqual(len(lote.repetidos), 1)
        self.assertEqual(sorted(os.path.basename(a) for a, _m in lote.erros),
                         ["lixo.xml", "quebrado.xml"])

    def test_evento_sem_registro_nao_cancela(self):
        chave = "31260811444777000161550010000001231000001238"
        with PastaTemporaria() as p:
            _grava(p, "n.xml", nfe_xml())
            _grava(p, "e.xml", evento_cancelamento_xml(chave, cstat="573"))
            lote = xf.ler_pasta_fiscal(p)
        self.assertFalse(lote.nfes[0].cancelada)


if __name__ == "__main__":
    unittest.main()

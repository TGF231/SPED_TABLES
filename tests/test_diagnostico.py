# -*- coding: utf-8 -*-
"""Diagnóstico ao abrir e a pré-checagem antes de mandar ao PVA."""

import unittest

from sped_tables.dominio import diagnostico
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico


def _doc(montador):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(montador.gravar(p))


class TestImpedemImportacao(unittest.TestCase):

    def test_obrigatorio_nao_impede(self):
        A = diagnostico.Achado
        achados = [A("obrigatorio", "C100", "COD_PART", "", 25),
                   A("formato", "0200", "COD_NCM", "", 3),
                   A("nulo", "0200", "CEST", "", 7),
                   A("formato", "C170", "VL_ITEM", "", 2)]
        self.assertEqual(diagnostico.impedem_importacao(achados),
                         [("nulo", 7), ("formato", 5)])

    def test_todo_achado_tem_modulo_ou_cai_na_grade(self):
        grupos = diagnostico.resumo_por_modulo(
            [diagnostico.Achado("tipo_inventado", "X", "", "", 1)])
        self.assertEqual(grupos[0][0], "Correção manual na grade")


class TestVerificar(unittest.TestCase):
    """Roda com ou sem o PVA instalado; o que muda é a fonte dos domínios."""

    def test_roda_nos_dois_leiautes(self):
        for m in (icms_basico(), contrib_basico()):
            with self.subTest(layout=m.layout):
                achados, info = diagnostico.verificar(_doc(m))
                self.assertIsInstance(achados, list)
                self.assertIn("sem_pva", info)

    def test_null_aparece_como_nulo(self):
        m = icms_basico()
        linha = next(c for c in m.linhas if c[0] == "0200")
        linha[m.tabela["0200"].index("CEST")] = "NULL"
        achados, _info = diagnostico.verificar(_doc(m))
        self.assertIn("nulo", {a.tipo for a in achados})
        self.assertIn("nulo", dict(diagnostico.impedem_importacao(achados)))

    def test_municipio_zerado_vai_para_o_cadastro_no_erp(self):
        """Participante com CNPJ e município 0000000: o PVA importa e acusa
        na validação. Esvaziar não conserta — o normalizar deixa como está e
        o diagnóstico manda corrigir o cadastro no ERP."""
        from sped_tables.dominio import validacao
        m = icms_basico()
        linha = next(c for c in m.linhas if c[0] == "0150")
        linha[m.tabela["0150"].index("COD_MUN")] = "0000000"
        doc = _doc(m)
        achados, info = diagnostico.verificar(doc)
        if info.get("sem_pva"):
            self.skipTest("o domínio do município vem da tabela do PVA")
        mun = [a for a in achados if a.reg == "0150" and a.campo == "COD_MUN"]
        self.assertEqual([a.tipo for a in mun], ["municipio"])
        self.assertNotIn("municipio",
                         dict(diagnostico.impedem_importacao(achados)))
        validacao.normalizar(doc)
        self.assertEqual(doc.registros[[r.reg for r in doc.registros]
                                       .index("0150")].valor(
            doc._ix("0150", "COD_MUN")), "0000000")

    def test_cancelada_so_leva_a_identificacao(self):
        """NF-e cancelada (COD_SIT 02) no formato do Guia: só identificação.
        Não é "campo obrigatório em branco" — mas a identificação continua
        cobrada."""
        m = icms_basico()
        m.linhas = [c for c in m.linhas if c[0] not in ("C170", "C190")]
        c100 = next(c for c in m.linhas if c[0] == "C100")
        nomes = m.tabela["C100"]
        for i, nome in enumerate(nomes):
            if nome not in diagnostico.IDENTIFICACAO["C100"] | {"REG"}:
                c100[i] = ""
        c100[nomes.index("COD_SIT")] = "02"
        achados, info = diagnostico.verificar(_doc(m))
        if info.get("sem_pva"):
            self.skipTest("obrigatoriedade vem do descritor do PVA")
        obr = {(a.reg, a.campo) for a in achados if a.tipo == "obrigatorio"}
        self.assertFalse({x for x in obr if x[0] == "C100"}, obr)
        c100[nomes.index("NUM_DOC")] = ""
        achados, _info = diagnostico.verificar(_doc(m))
        self.assertIn(("C100", "NUM_DOC"), {(a.reg, a.campo) for a in achados
                                             if a.tipo == "obrigatorio"})


if __name__ == "__main__":
    unittest.main()

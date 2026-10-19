# -*- coding: utf-8 -*-
"""O teste central da migração: a base compilada de `base/` responde igual
ao PVA instalado nesta máquina — dado a dado e pela porta.

Falhou depois de o PVA ser atualizado? A base ficou para trás: rode
`py -m consolidador extrair`, revise o `git diff base/` e faça o commit."""

import datetime
import json
import os
import unittest

import tests
from consolidador.instalacao import InstalacaoPVA
from sped_tables.infra import base_referencia
from sped_tables.infra.referencias_base import ReferenciasBase

# a suíte roda com a pasta do PVA vazia; a instalação de verdade, quando
# existe, é a que `tests/__init__.py` guardou antes de isolá-la
PVA = tests.PVA_REAL


@unittest.skipUnless(PVA, "PVA não instalado nesta máquina")
class TestBaseReproduzOPva(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fontes = base_referencia.pasta_fontes()
        with open(os.path.join(fontes, "manifesto.json"),
                  encoding="utf-8") as fh:
            data = datetime.date.fromisoformat(json.load(fh)["data"])
        cls.pva = InstalacaoPVA(PVA, data=data, fontes=fontes)
        cls.base, _origem = base_referencia.em_uso()

    def test_mesmas_versoes(self):
        for layout in base_referencia.LEIAUTES:
            self.assertEqual(self.pva.versoes(layout),
                             self.base.versoes(layout), layout)

    def test_mesma_estrutura(self):
        for layout in base_referencia.LEIAUTES:
            for versao in self.pva.versoes(layout):
                self.assertEqual(self.pva.estrutura(layout, versao),
                                 self.base.estrutura(layout, versao),
                                 "%s %s" % (layout, versao))

    def test_mesmas_tabelas(self):
        a, b = self.pva.tabelas(), self.base.tabelas()
        self.assertEqual(sorted(a), sorted(b))
        for chave in a:
            self.assertEqual(a[chave][1], b[chave][1], chave)
            self.assertEqual(a[chave][0].splitlines(),
                             b[chave][0].splitlines(), chave)

    def test_mesmas_respostas_da_porta(self):
        antigo = _referencia_pva()
        nova = ReferenciasBase(self.base)
        for layout in base_referencia.LEIAUTES:
            ea, _i = antigo.estrutura(layout)
            eb, _i = nova.estrutura(layout)
            self.assertEqual(ea, eb, layout)
            for uf in ("MG", "SP"):
                self.assertEqual(
                    antigo.dominios_por_datasource(ea, layout, uf,
                                                   "31082026"),
                    nova.dominios_por_datasource(eb, layout, uf, "31082026"),
                    "%s %s" % (layout, uf))
        self.assertEqual(antigo.naturezas_cfop_credito("31082026"),
                         nova.naturezas_cfop_credito("31082026"))
        self.assertEqual(antigo.cfops_com_credito("31082026"),
                         nova.cfops_com_credito("31082026"))
        self.assertEqual(antigo.prazo_entrega("082026"),
                         nova.prazo_entrega("082026"))
        for cst in ("04", "05", "06", "07", "08", "09"):
            self.assertEqual(antigo.naturezas_receita(cst, "31082026"),
                             nova.naturezas_receita(cst, "31082026"), cst)
            self.assertEqual(antigo.tabela_natureza_receita(cst),
                             nova.tabela_natureza_receita(cst), cst)
        self.assertEqual(antigo.codigos_receita_icms("MG", "31082026"),
                         nova.codigos_receita_icms("MG", "31082026"))
        for layout in base_referencia.LEIAUTES:
            self.assertEqual(antigo.guia(layout), nova.guia(layout))


def _referencia_pva():
    """O lado "PVA" da comparação pela porta: o mesmo adaptador, lendo a
    instalação em vez da base."""
    return ReferenciasBase(TestBaseReproduzOPva.pva)


if __name__ == "__main__":
    unittest.main()

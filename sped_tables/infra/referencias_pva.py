# -*- coding: utf-8 -*-
"""Adaptador: a porta `dominio.referencias` lida da instalação dos PVAs.

É a única ponte entre as regras fiscais e os arquivos do PVA. Onde eles
estão é decisão do `config`; como se leem, de `descritor_pva` (o `.jar` com o
descritor de validação) e `tabelas_pva` (as tabelas externas de códigos).
"""

from sped_tables.dominio.referencias import Referencias
from sped_tables.infra import descritor_pva
from sped_tables.infra import tabelas_pva


class ReferenciasPVA(Referencias):
    """Tabelas oficiais tiradas dos PVAs instalados na máquina."""

    nome = "PVA instalado"

    def estrutura(self, layout):
        return descritor_pva.carregar(layout)

    def dominios_por_datasource(self, estrutura, layout, uf=None,
                                data_ref=None):
        return tabelas_pva.dominios_por_datasource(
            estrutura, layout, uf=uf, data_ref=data_ref)

    def rotulo(self, campo):
        return tabelas_pva.ROTULOS.get(campo, campo)

    def naturezas_cfop_credito(self, data_ref=None):
        return tabelas_pva.naturezas_cfop_credito(data_ref=data_ref)

    def cfops_com_credito(self, data_ref=None):
        return tabelas_pva.cfops_com_credito(data_ref=data_ref)

    def prazo_entrega(self, mes_ano):
        return tabelas_pva.prazo_entrega(mes_ano)

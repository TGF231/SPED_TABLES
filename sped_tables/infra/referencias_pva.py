# -*- coding: utf-8 -*-
"""Adaptador: a porta `dominio.referencias` lida da instalação dos PVAs.

É a única ponte entre as regras fiscais e os arquivos do PVA. Onde eles
estão é decisão do `config`; como se leem, de `descritor_pva` (o `.jar` com o
descritor de validação) e `tabelas_pva` (as tabelas externas de códigos).
"""

from sped_tables.dominio import referencias
from sped_tables.dominio.referencias import Referencias
from sped_tables.infra import descritor_pva
from sped_tables.infra import guias
from sped_tables.infra import tabelas_pva


class ReferenciasPVA(Referencias):
    """Tabelas oficiais tiradas dos PVAs instalados na máquina."""

    nome = "PVA instalado"

    def __init__(self):
        # as tabelas não mudam durante a sessão: o que custa ler fica aqui
        self._alinhadas = {}     # (leiaute, id do descritor) -> alinhada
        self._guias = {}         # leiaute -> guia prático
        self._ncms_natureza = {}  # natureza da receita -> NCM
        self._tab_natureza = {}   # CST -> tabela da natureza da receita
        self._clf = None
        self._clf_lido = False

    def estrutura(self, layout):
        # o descritor é lido uma vez por .jar (cache do descritor_pva); o
        # alinhamento aos nomes do leiaute, uma vez por leitura
        bruta, info = descritor_pva.carregar(layout)
        chave = (layout, id(bruta))
        if chave not in self._alinhadas:
            self._alinhadas[chave] = referencias.alinhar_ao_leiaute(bruta,
                                                                   layout)
        return self._alinhadas[chave], info

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

    def naturezas_receita(self, cst, data_ref=None):
        return tabelas_pva.naturezas_receita(cst, data_ref=data_ref)

    def ncms_da_natureza(self, codigo):
        # cada consulta lê até 7 tabelas, e a rotina pergunta por ocorrência
        if codigo not in self._ncms_natureza:
            self._ncms_natureza[codigo] = tabelas_pva.ncms_da_natureza(codigo)
        return self._ncms_natureza[codigo]

    def tabela_natureza_receita(self, cst):
        if cst not in self._tab_natureza:
            self._tab_natureza[cst] = tabelas_pva.tabela_natureza_receita(cst)
        return self._tab_natureza[cst]

    def classificador_ncm(self):
        # montar custa a leitura de três arquivos
        if not self._clf_lido:
            self._clf_lido = True
            try:
                from sped_tables.infra import tabelas_rfb
                self._clf = tabelas_rfb.carregar_tudo()[0]
            except Exception:                               # noqa: BLE001
                self._clf = None
        return self._clf

    def codigos_receita_icms(self, uf, data_ref=None):
        return tabelas_pva.codigos_receita_icms(uf, data_ref=data_ref)

    def guia(self, layout):
        # o guia não é do PVA: viaja com o programa, em recursos/. Mora
        # aqui porque é a fonte de referências que a montagem liga
        if layout not in self._guias:
            self._guias[layout] = guias.carregar(layout)
        return self._guias[layout]

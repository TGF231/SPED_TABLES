# -*- coding: utf-8 -*-
"""Adaptador: a porta `dominio.referencias` lida da instalação dos PVAs.

É a única ponte entre as regras fiscais e os arquivos do PVA. Onde eles
estão é decisão do `config`; como se leem, de `descritor_pva` (o `.jar` com o
descritor de validação) e `tabelas_oficiais` (as tabelas externas de códigos).
"""

from sped_tables.dominio import referencias
from sped_tables.dominio.referencias import Referencias
from sped_tables.infra import config, descritor_pva, guias
from sped_tables.infra import tabelas_ncm, tabelas_oficiais


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
        self._tabs = None        # {chave: (texto, versao)} das duas pastas
        self._pastas_lidas = None

    def _tabelas(self):
        # as duas pastas, como `dominios_por_datasource` sempre leu. A leitura
        # fica guardada enquanto as pastas forem as mesmas: apontar outra
        # instalação (Pasta dos PVAs…) passa a valer na próxima consulta,
        # como valia quando cada consulta listava a pasta de novo
        pastas = (config.pasta_tabelas("ICMS"), config.pasta_tabelas("CONTRIB"))
        if self._tabs is None or pastas != self._pastas_lidas:
            tabs = tabelas_oficiais.tabelas_da_pasta(pastas[0])
            tabs.update(tabelas_oficiais.tabelas_da_pasta(pastas[1]))
            self._tabs, self._pastas_lidas = tabs, pastas
        return self._tabs

    def estrutura(self, layout, versao=None):
        # só o descritor mais recente: a versão do arquivo passa a contar
        # com a base de referência (este adaptador sai na mesma série).
        # O descritor é lido uma vez por .jar (cache do descritor_pva); o
        # alinhamento aos nomes do leiaute, uma vez por leitura
        bruta, info = descritor_pva.carregar(layout)
        chave = (layout, id(bruta))
        if chave not in self._alinhadas:
            self._alinhadas[chave] = referencias.alinhar_ao_leiaute(bruta,
                                                                   layout)
        return self._alinhadas[chave], info

    def dominios_por_datasource(self, estrutura, layout, uf=None,
                                data_ref=None):
        return tabelas_oficiais.dominios_por_datasource(
            self._tabelas(), estrutura, layout, uf=uf, data_ref=data_ref)

    def rotulo(self, campo):
        return tabelas_oficiais.ROTULOS.get(campo, campo)

    def naturezas_cfop_credito(self, data_ref=None):
        return tabelas_oficiais.naturezas_cfop_credito(
            self._tabelas(), data_ref=data_ref)

    def cfops_com_credito(self, data_ref=None):
        return tabelas_oficiais.cfops_com_credito(
            self._tabelas(), data_ref=data_ref)

    def prazo_entrega(self, mes_ano):
        return tabelas_oficiais.prazo_entrega(self._tabelas(), mes_ano)

    def naturezas_receita(self, cst, data_ref=None):
        return tabelas_oficiais.naturezas_receita(
            self._tabelas(), cst, data_ref=data_ref)

    def ncms_da_natureza(self, codigo):
        # cada consulta lê até 7 tabelas, e a rotina pergunta por ocorrência
        if codigo not in self._ncms_natureza:
            self._ncms_natureza[codigo] = tabelas_oficiais.ncms_da_natureza(
                self._tabelas(), codigo)
        return self._ncms_natureza[codigo]

    def tabela_natureza_receita(self, cst):
        if cst not in self._tab_natureza:
            self._tab_natureza[cst] = tabelas_oficiais.tabela_natureza_receita(
                self._tabelas(), cst)
        return self._tab_natureza[cst]

    def classificador_ncm(self):
        # montar custa a leitura de três arquivos
        if not self._clf_lido:
            self._clf_lido = True
            # `None` sem nenhuma das tabelas de produto: vazio trataria todo
            # NCM como tributado, e quem recebe `None` se abstém
            self._clf = tabelas_ncm.classificador(self._tabelas())
        return self._clf

    def codigos_receita_icms(self, uf, data_ref=None):
        return tabelas_oficiais.codigos_receita_icms(
            self._tabelas(), uf, data_ref=data_ref)

    def guia(self, layout):
        # o guia não é do PVA: viaja com o programa, em recursos/. Mora
        # aqui porque é a fonte de referências que a montagem liga
        if layout not in self._guias:
            self._guias[layout] = guias.carregar(layout)
        return self._guias[layout]

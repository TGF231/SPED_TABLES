# -*- coding: utf-8 -*-
"""Adaptador: a porta `dominio.referencias` lida da **base de referência**.

Nada aqui lê a instalação do PVA. A origem é qualquer objeto com a
interface de `base_referencia.Base` (`manifesto`, `versoes`, `estrutura`,
`tabelas`, `guia`, `ncm_vigente`): o banco compilado, no programa; a
instalação do PVA, no consolidador — que é como se confere que a base
responde igual ao PVA de onde saiu.
"""

import copy

from sped_tables.dominio import referencias
from sped_tables.dominio.referencias import Referencias
from sped_tables.infra import tabelas_ncm, tabelas_oficiais


def _numero(cod_ver):
    """O COD_VER como número, para comparar versões; -1 quando não é um
    (nunca levanta: a comparação só decide qual mensagem dar)."""
    try:
        return int(cod_ver)
    except (TypeError, ValueError):
        return -1


class ReferenciasBase(Referencias):

    def __init__(self, origem, nome="base de referência"):
        self.origem = origem
        self.nome = nome
        # a base não muda durante a sessão: o que custa montar fica aqui
        self._alinhadas = {}       # (leiaute, versão) -> estrutura alinhada
        self._ncms_natureza = {}   # natureza da receita -> NCM
        self._tab_natureza = {}    # CST -> tabela da natureza da receita
        self._clf = None
        self._clf_lido = False

    def manifesto(self):
        return self.origem.manifesto()

    def descricao(self):
        m = self.manifesto()
        return "base de referência %s, de %s" % (m.get("versao", "?"),
                                                  m.get("data", "?"))

    def estrutura(self, layout, versao=None):
        versoes = self.origem.versoes(layout)
        if not versoes:
            return {}, {"descritor": None, "erro": "a base de referência "
                        "não tem o leiaute %s" % layout}
        if versao is None:
            versao = max(versoes, key=int)
        if versao not in versoes:
            base = self.manifesto().get("versao")
            info = {"descritor": None, "versao": versao,
                    "fora_da_base": True, "base": base,
                    "erro": "a versão %s do leiaute não está na base de "
                            "referência %s" % (versao, base)}
            # acima da maior guardada o remédio é outro (importar uma base
            # mais nova) que o da versão velha demais (saiu da retenção)
            if _numero(versao) > max(_numero(v) for v in versoes):
                info["mais_nova_que_a_base"] = True
            return {}, info
        chave = (layout, versao)
        if chave not in self._alinhadas:
            # a origem entrega o dicionário do próprio cache e o alinhamento
            # reaproveita as listas de dentro dele: sem a cópia, quem mexesse
            # em `valores` do que recebeu estragaria as leituras seguintes
            # da base. O resultado é somente leitura e compartilhado (a
            # montagem custa uma cópia por versão, não uma por consulta)
            self._alinhadas[chave] = referencias.alinhar_ao_leiaute(
                copy.deepcopy(self.origem.estrutura(layout, versao)), layout)
        est = self._alinhadas[chave]
        return est, {"descritor": versoes[versao][2], "registros": len(est),
                     "versao": versao,
                     "base": self.manifesto().get("versao")}

    def versao_vigente(self, layout, data):
        alvo = tabelas_oficiais.chave_data(data)
        if not alvo:
            return None
        # da mais nova para a mais antiga: versão sem data final continua
        # "vigente" para sempre, e a que começou depois dela é quem vale
        for versao, (ini, fim, _d) in sorted(
                self.origem.versoes(layout).items(), reverse=True):
            if ((tabelas_oficiais.chave_data(ini) or "00000000") <= alvo
                    <= (tabelas_oficiais.chave_data(fim) or "99999999")):
                return versao
        return None

    def dominios_por_datasource(self, estrutura, layout, uf=None,
                                data_ref=None):
        return tabelas_oficiais.dominios_por_datasource(
            self.origem.tabelas(), estrutura, layout, uf=uf,
            data_ref=data_ref)

    def rotulo(self, campo):
        return tabelas_oficiais.ROTULOS.get(campo, campo)

    def naturezas_cfop_credito(self, data_ref=None):
        return tabelas_oficiais.naturezas_cfop_credito(
            self.origem.tabelas(), data_ref=data_ref)

    def cfops_com_credito(self, data_ref=None):
        return tabelas_oficiais.cfops_com_credito(self.origem.tabelas(),
                                                  data_ref=data_ref)

    def prazo_entrega(self, mes_ano):
        return tabelas_oficiais.prazo_entrega(self.origem.tabelas(), mes_ano)

    def naturezas_receita(self, cst, data_ref=None):
        return tabelas_oficiais.naturezas_receita(
            self.origem.tabelas(), cst, data_ref=data_ref)

    def ncms_da_natureza(self, codigo):
        # cada consulta lê até 7 tabelas, e a rotina pergunta por ocorrência
        if codigo not in self._ncms_natureza:
            self._ncms_natureza[codigo] = tabelas_oficiais.ncms_da_natureza(
                self.origem.tabelas(), codigo)
        return self._ncms_natureza[codigo]

    def tabela_natureza_receita(self, cst):
        if cst not in self._tab_natureza:
            self._tab_natureza[cst] = (
                tabelas_oficiais.tabela_natureza_receita(
                    self.origem.tabelas(), cst))
        return self._tab_natureza[cst]

    def classificador_ncm(self):
        if not self._clf_lido:
            self._clf_lido = True
            self._clf = tabelas_ncm.classificador(
                self.origem.tabelas(), self.origem.ncm_vigente())
        return self._clf

    def codigos_receita_icms(self, uf, data_ref=None):
        return tabelas_oficiais.codigos_receita_icms(
            self.origem.tabelas(), uf, data_ref=data_ref)

    def guia(self, layout):
        return self.origem.guia(layout)

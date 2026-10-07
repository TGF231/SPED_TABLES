# -*- coding: utf-8 -*-
"""Casos de uso da integração com o ERP: testar a conexão, descobrir
tabelas e colunas para o mapeamento, e trazer cada entidade já nas chaves
do SPED Tables — produtos e estoque como a planilha entrega, participantes
para o 0150 e os XMLs como o `Lote` da leitura de pasta.

O perfil (`erp.Sistema`) diz de onde vem cada informação; o adaptador
(`infra/bancos.py`) fala com o banco; aqui só se junta uma coisa à outra.
"""

import datetime

from sped_tables.dominio import erp
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.dominio.empresas import dados_do_arquivo
from sped_tables.infra import bancos, paralelo, sistemas_erp
from sped_tables.infra.bancos import ErroDeBanco

__all__ = ["ErroDeBanco"]


def carregar():
    return sistemas_erp.carregar()


def salvar(cfg):
    return sistemas_erp.salvar(cfg)


def _par(cfg, conexao):
    sistema = cfg.sistema_da(conexao)
    if sistema is None:
        raise ErroDeBanco("A conexão \"%s\" aponta para um sistema que não "
                          "existe mais." % conexao.nome)
    return sistema, bancos.adaptador(sistema, conexao)


# ------------------------------------------------- para montar o perfil
def testar(sistema, conexao):
    """Texto com a versão do servidor; `ErroDeBanco` se não conectar."""
    return bancos.adaptador(sistema, conexao).testar()


def tabelas(sistema, conexao):
    return bancos.adaptador(sistema, conexao).tabelas()


def colunas(sistema, conexao, origem):
    return bancos.adaptador(sistema, conexao).colunas(origem)


def amostra(sistema, conexao, origem, n=bancos.AMOSTRA):
    return bancos.adaptador(sistema, conexao).amostra(origem, n)


def previa(sistema, conexao, entidade, n=bancos.AMOSTRA):
    """As primeiras `n` linhas da entidade como o programa vai recebê-las
    — é o "funciona?" do mapeamento."""
    ad = bancos.adaptador(sistema, conexao)
    q = erp.consulta(sistema, entidade, conexao.empresa)
    saida = []
    linhas = ad.ler(q)
    try:
        for reg in linhas:
            saida.append(reg)
            if len(saida) >= n:
                break
    finally:
        linhas.close()          # devolve a conexão já, sem esperar o coletor
    return erp.linhas(entidade, saida)


# --------------------------------------------------- as entidades
def ler(cfg, conexao, entidade, data_ini=None, data_fim=None, cancelar=None):
    """Linhas da entidade nas chaves canônicas."""
    sistema, ad = _par(cfg, conexao)
    q = erp.consulta(sistema, entidade, conexao.empresa, data_ini, data_fim)
    return erp.linhas(entidade, ad.ler(q, cancelar))


def produtos(cfg, conexao, cancelar=None):
    return ler(cfg, conexao, "produtos", cancelar=cancelar)


def participantes(cfg, conexao, cancelar=None):
    return ler(cfg, conexao, "participantes", cancelar=cancelar)


def estoque(cfg, conexao, dt_inv, cancelar=None):
    """O estoque de cada item na data do inventário (DDMMAAAA), completado
    com o cadastro de produtos quando o sistema o tiver mapeado — é dali que
    saem descrição e NCM dos itens que o 0200 ainda não tem."""
    sistema, _ad = _par(cfg, conexao)
    fim = _data(dt_inv)
    linhas = erp.estoque_na_data(
        ler(cfg, conexao, "estoque", data_fim=fim, cancelar=cancelar), dt_inv)
    if sistema.oferece("produtos"):
        linhas = erp.com_cadastro(linhas, produtos(cfg, conexao, cancelar))
    return linhas


def xmls(cfg, conexao, dt_ini, dt_fin, progresso=None, cancelar=None):
    """O `xml_fiscal.Lote` dos XMLs guardados no banco entre `dt_ini` e
    `dt_fin` (DDMMAAAA) — o mesmo que a leitura de uma pasta devolve, lido
    em paralelo. O conteúdo pode vir como texto, bytes, gzip, zlib ou
    base64."""
    linhas = ler(cfg, conexao, "xmls", _data(dt_ini), _data(dt_fin),
                 cancelar)
    itens = [(_nome(ln, n), ln.get("xml")) for n, ln in enumerate(linhas, 1)]
    lidos = paralelo.em_lotes(erp.ler_xmls, itens, progresso=progresso,
                              cancelar=cancelar)
    return xf.montar_lote((nome, doc, erro)
                          for (nome, _x), (doc, erro) in zip(itens, lidos))


def _nome(ln, n):
    chave = str(ln.get("chave") or "").strip()
    return "%s.xml" % chave if chave else "registro %d do banco" % n


def _data(ddmmaaaa):
    s = str(ddmmaaaa or "")
    if len(s) != 8 or not s.isdigit():
        return None
    return datetime.date(int(s[4:]), int(s[2:4]), int(s[:2]))


def cnpj(doc):
    """CNPJ do 0000 do arquivo aberto."""
    return dados_do_arquivo(doc)[0]


def periodo(doc):
    """`(DT_INI, DT_FIN)` do 0000, DDMMAAAA."""
    i = doc._ix("0000", "DT_INI")
    r0 = next((r for r in doc.registros if r.reg == "0000"), None)
    ini = (r0.valor(i) or "").strip() if r0 is not None and i is not None \
        else ""
    return ini, doc.data_final()


def conexoes_da_empresa(cfg, cnpj, entidade):
    """As conexões vinculadas ao CNPJ cujo sistema oferece a entidade."""
    return [c for c in cfg.da_empresa(cnpj)
            if cfg.sistema_da(c) is not None
            and cfg.sistema_da(c).oferece(entidade)]

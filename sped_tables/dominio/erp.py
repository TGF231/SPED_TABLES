# -*- coding: utf-8 -*-
"""Integração com o banco do ERP: **o que** o SPED Tables sabe receber e
**como** cada sistema guarda isso.

Cada ERP grava o cadastro do seu jeito — o NCM do produto pode estar na
coluna `NCM`, `CLASFISCAL` ou `COD_NCM`, numa tabela `PRODUTOS`, `ESTOQUE`
ou `TB_ITEM`. Em vez de um conector programado por ERP, o programa
declara as **informações** que entende (`ENTIDADES`) e a pessoa aponta, uma
vez por sistema, a tabela e a coluna de cada uma (`Sistema`, um perfil
declarativo). O perfil vale para todos os clientes que usam o mesmo ERP; o
que muda de um cliente para outro — servidor, arquivo, senha, código da
empresa no ERP — é a **conexão** (`infra/sistemas_erp.py`).

As chaves das informações são as mesmas da importação por planilha
(`SpedDocument.CAMPOS_INVENTARIO`, `CAMPOS_0200`): o que vem do ERP entra
pelos mesmos cálculos, com as mesmas prévias e as mesmas recusas.

Este módulo não fala com banco nenhum. Ele monta o pedido (`Consulta`) e
converte as linhas que voltam; quem executa é o adaptador do banco
(`infra/bancos.py`).
"""

import base64
import binascii
import datetime
import decimal
import gzip
import re
import unicodedata
import zlib

from sped_tables.dominio import xml_fiscal

# --------------------------------------------------------------- bancos
BANCOS = {
    "firebird": "Firebird (2.5, 3, 4 ou 5)",
    "sqlserver": "SQL Server",
    "mysql": "MySQL / MariaDB",
    "dbf": "Arquivos DBF (dBase, Clipper, FoxPro)",
    "sqlite": "SQLite",
}


class Informacao:
    """Uma informação que o SPED Tables entende: a chave canônica, o rótulo
    da tela, se é obrigatória e as palavras que sugerem a coluna."""
    __slots__ = ("chave", "rotulo", "obrigatoria", "palavras", "dica")

    def __init__(self, chave, rotulo, obrigatoria=False, palavras=(),
                 dica=""):
        self.chave = chave
        self.rotulo = rotulo
        self.obrigatoria = obrigatoria
        self.palavras = palavras
        self.dica = dica


class Entidade:
    __slots__ = ("chave", "rotulo", "descricao", "informacoes", "usa_data",
                 "registro")

    def __init__(self, chave, rotulo, descricao, informacoes, usa_data=False,
                 registro=""):
        self.chave = chave
        self.rotulo = rotulo
        self.descricao = descricao
        self.informacoes = informacoes
        self.usa_data = usa_data
        self.registro = registro

    def informacao(self, chave):
        return next((i for i in self.informacoes if i.chave == chave), None)

    @property
    def obrigatorias(self):
        return [i for i in self.informacoes if i.obrigatoria]


I = Informacao
ENTIDADES = {e.chave: e for e in (
    Entidade(
        "produtos", "Produtos",
        "Cadastro de itens: corrige o 0200 (NCM, CEST, código de barras, "
        "tipo, unidade) e completa os itens novos do inventário.",
        [I("cod_item", "Código do item (COD_ITEM)", True,
           ("cod_item", "codigo", "cod_produto", "codproduto", "codprod",
            "id_produto", "produto", "cod")),
         I("descr_item", "Descrição", False,
           ("descr_item", "descricao", "descr", "nome", "desc")),
         I("unid", "Unidade", False,
           ("unid", "unidade", "und", "un", "unid_inv", "unidade_venda")),
         I("cod_ncm", "NCM", False,
           ("cod_ncm", "ncm", "clasfiscal", "classificacao_fiscal",
            "clas_fiscal")),
         I("cest", "CEST", False, ("cest", "cod_cest")),
         I("cod_barra", "Código de barras (GTIN/EAN)", False,
           ("cod_barra", "gtin", "ean", "codbarra", "codigo_barras",
            "cod_barras", "barras")),
         I("tipo_item", "Tipo do item (00 a 10, 99)", False,
           ("tipo_item", "tipoitem", "tipo_sped", "tipo")),
         I("ex_ipi", "EX da TIPI", False, ("ex_ipi", "exipi", "ex_tipi")),
         I("cod_gen", "Gênero do item", False, ("cod_gen", "genero")),
         I("aliq_icms", "Alíquota de ICMS", False,
           ("aliq_icms", "aliquota_icms", "icms", "aliquota")),
         ], registro="0200"),
    Entidade(
        "participantes", "Participantes",
        "Clientes e fornecedores: corrige o 0150 (CNPJ/CPF, IE, município, "
        "endereço) pelo cadastro do ERP.",
        [I("cod_part", "Código do participante (COD_PART)", True,
           ("cod_part", "codigo", "cod_cliente", "cod_fornecedor",
            "codcli", "codfor", "id")),
         I("nome", "Nome / razão social", False,
           ("nome", "razao_social", "razao", "razaosocial", "nome_razao")),
         I("cnpj", "CNPJ", False, ("cnpj", "cgc", "cnpj_cpf", "cpf_cnpj",
                                   "documento")),
         I("cpf", "CPF", False, ("cpf",)),
         I("ie", "Inscrição estadual", False,
           ("ie", "inscricao_estadual", "insc_estadual", "inscricao",
            "rg_ie")),
         I("cod_mun", "Município (código IBGE)", False,
           ("cod_mun", "codigo_ibge", "cod_ibge", "ibge", "cod_municipio",
            "codmun")),
         I("suframa", "SUFRAMA", False, ("suframa",)),
         I("end", "Endereço", False,
           ("end", "endereco", "logradouro", "rua")),
         I("num", "Número", False, ("num", "numero", "nro")),
         I("compl", "Complemento", False, ("compl", "complemento")),
         I("bairro", "Bairro", False, ("bairro",)),
         I("cod_pais", "País (código do BACEN)", False,
           ("cod_pais", "pais", "codigo_pais")),
         ], registro="0150"),
    Entidade(
        "xmls", "XMLs de NF-e, NFC-e e CT-e",
        "O XML que o ERP guarda no banco: lido no lugar da pasta, filtrado "
        "pelo período do arquivo aberto.",
        [I("xml", "Conteúdo do XML", True,
           ("xml", "xml_nfe", "xmlnfe", "arquivo_xml", "conteudo", "xml_doc",
            "xml_autorizado", "xmlproc")),
         I("chave", "Chave de acesso", False,
           ("chave", "chave_acesso", "chave_nfe", "chavenfe", "chnfe",
            "chave_xml")),
         # obrigatória: sem ela a leitura traria todos os XMLs de todos os
         # anos guardados no banco
         I("data", "Data de emissão (filtra o período)", True,
           ("data", "data_emissao", "dt_emissao", "dtemissao", "emissao",
            "dt_doc", "data_doc", "dhemi")),
         ], usa_data=True),
    Entidade(
        "estoque", "Estoque (inventário)",
        "Quantidade e valor de cada item para o bloco H. Com a coluna de "
        "data, vale a posição mais recente até a data do inventário.",
        [I("cod_item", "Código do item (COD_ITEM)", True,
           ("cod_item", "codigo", "cod_produto", "codproduto", "codprod",
            "produto", "cod")),
         I("qtd", "Quantidade", True,
           ("qtd", "quantidade", "estoque", "saldo", "qtde", "qtd_estoque",
            "estoque_atual")),
         I("vl_unit", "Valor unitário (custo)", False,
           ("vl_unit", "custo", "custo_medio", "preco_custo", "valor_unitario",
            "vlr_custo", "custo_unitario")),
         I("vl_item", "Valor total", False,
           ("vl_item", "valor_total", "total", "vlr_total")),
         I("unid", "Unidade", False, ("unid", "unidade", "und", "un")),
         I("data", "Data da posição", False,
           ("data", "data_posicao", "dt_estoque", "data_inventario",
            "dt_inventario", "data_saldo")),
         I("ind_prop", "Propriedade (IND_PROP)", False,
           ("ind_prop", "propriedade", "posse")),
         I("cod_cta", "Conta contábil", False,
           ("cod_cta", "conta_contabil", "conta")),
         ], usa_data=True, registro="H010"),
)}
del I


# ---------------------------------------------------------- o perfil
class Mapeamento:
    """De onde sai uma entidade num sistema: uma tabela (ou uma consulta
    própria, para quem precisa juntar tabelas) e a coluna de cada
    informação. `coluna_empresa` filtra os ERPs que guardam várias empresas
    no mesmo banco — o código de cada uma fica na conexão."""

    def __init__(self, tabela="", sql="", colunas=None, coluna_empresa=""):
        self.tabela = (tabela or "").strip()
        self.sql = (sql or "").strip()
        self.colunas = {k: v for k, v in (colunas or {}).items() if v}
        self.coluna_empresa = (coluna_empresa or "").strip()

    @property
    def origem(self):
        return {"sql": self.sql} if self.sql else {"tabela": self.tabela}

    @property
    def vazio(self):
        return not (self.tabela or self.sql)

    def para_dict(self):
        d = {"tabela": self.tabela, "colunas": dict(self.colunas)}
        if self.sql:
            d["sql"] = self.sql
        if self.coluna_empresa:
            d["coluna_empresa"] = self.coluna_empresa
        return d

    @classmethod
    def de_dict(cls, d):
        d = d or {}
        return cls(d.get("tabela"), d.get("sql"), d.get("colunas"),
                   d.get("coluna_empresa"))


class Sistema:
    """O perfil de um ERP: o tipo de banco e o mapeamento de cada entidade."""

    def __init__(self, nome, banco, entidades=None, ident=""):
        self.ident = ident or _identificador(nome)
        self.nome = nome
        self.banco = banco
        self.entidades = {k: (v if isinstance(v, Mapeamento)
                              else Mapeamento.de_dict(v))
                          for k, v in (entidades or {}).items()
                          if k in ENTIDADES}

    def mapeamento(self, entidade):
        return self.entidades.get(entidade) or Mapeamento()

    def oferece(self, entidade):
        """A entidade está mapeada o bastante para ser lida."""
        return not problemas(self, entidade)

    def para_dict(self):
        return {"id": self.ident, "nome": self.nome, "banco": self.banco,
                "entidades": {k: m.para_dict()
                              for k, m in sorted(self.entidades.items())
                              if not m.vazio}}

    @classmethod
    def de_dict(cls, d):
        return cls(d.get("nome", ""), d.get("banco", ""),
                   d.get("entidades"), d.get("id", ""))


class Conexao:
    """O banco de um cliente: onde está, como entrar, qual perfil
    (`sistema`) o descreve e de quais empresas (CNPJ) ele é. `base` é o
    arquivo `.fdb`, o nome do banco (SQL Server, MySQL) ou a pasta dos DBF;
    `empresa` é o código da empresa dentro do ERP, para os bancos que
    guardam várias."""

    def __init__(self, nome="", sistema="", host="", porta="", base="",
                 usuario="", senha="", codificacao="", empresa="", cnpjs=(),
                 ident=""):
        self.ident = ident or _identificador(nome)
        self.nome = nome
        self.sistema = sistema
        self.host = (host or "").strip()
        self.porta = str(porta or "").strip()
        self.base = (base or "").strip()
        self.usuario = (usuario or "").strip()
        self.senha = senha or ""
        self.codificacao = (codificacao or "").strip()
        self.empresa = str(empresa or "").strip()
        self.cnpjs = sorted({re.sub(r"\D", "", c) for c in cnpjs
                             if re.sub(r"\D", "", c)})

    def atende(self, cnpj):
        return re.sub(r"\D", "", cnpj or "") in self.cnpjs


def _identificador(nome):
    s = _sem_acento(nome).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "sistema"


def problemas(sistema, entidade):
    """O que falta para ler a entidade: `[texto]`, vazio se está pronta."""
    ent = ENTIDADES[entidade]
    m = sistema.mapeamento(entidade)
    if m.vazio:
        return ["%s: falta a tabela" % ent.rotulo]
    faltam = [i.rotulo for i in ent.obrigatorias if i.chave not in m.colunas]
    if faltam:
        return ["%s: falta a coluna de %s" % (ent.rotulo, ", ".join(faltam))]
    if m.sql and not sql_so_leitura(m.sql):
        return ["%s: a consulta própria precisa ser um único SELECT"
                % ent.rotulo]
    return []


def sql_so_leitura(sql):
    """Consulta própria só pode ser **um** SELECT (ou WITH … SELECT): o
    programa nunca grava no banco do ERP. Comentário e ponto e vírgula no
    meio são recusados — é por eles que um segundo comando entraria."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s or ";" in s or "--" in s or "/*" in s:
        return False
    primeira = s.split(None, 1)[0].upper()
    return primeira in ("SELECT", "WITH")


# -------------------------------------------------- o pedido ao banco
class Filtro:
    """`coluna` `operador` `valor` — operadores: `=`, `>=`, `<=`."""
    __slots__ = ("coluna", "operador", "valor")

    def __init__(self, coluna, operador, valor):
        if operador not in ("=", ">=", "<="):
            raise ValueError("operador inválido: %r" % operador)
        self.coluna, self.operador, self.valor = coluna, operador, valor

    def __repr__(self):
        return "Filtro(%r %s %r)" % (self.coluna, self.operador, self.valor)


class Consulta:
    """O que pedir ao banco: a origem (tabela ou SQL próprio), as colunas
    (`{chave: coluna}`) e os filtros. O adaptador transforma em SQL do
    dialeto dele — ou, no DBF, filtra em Python."""

    def __init__(self, origem, colunas, filtros=()):
        self.origem = origem
        self.colunas = dict(colunas)
        self.filtros = list(filtros)


def consulta(sistema, entidade, empresa="", data_ini=None, data_fim=None):
    """A `Consulta` da entidade no sistema. `empresa` é o código da empresa
    no ERP (só filtra se o perfil tiver a coluna); `data_ini`/`data_fim`
    (`datetime.date`) só filtram se a informação `data` estiver mapeada."""
    erros = problemas(sistema, entidade)
    if erros:
        raise ValueError("; ".join(erros))
    m = sistema.mapeamento(entidade)
    filtros = []
    if m.coluna_empresa and str(empresa or "").strip():
        filtros.append(Filtro(m.coluna_empresa, "=", str(empresa).strip()))
    col_data = m.colunas.get("data")
    if col_data:
        if data_ini is not None:
            filtros.append(Filtro(col_data, ">=", data_ini))
        if data_fim is not None:
            filtros.append(Filtro(col_data, "<=", data_fim))
    return Consulta(m.origem, m.colunas, filtros)


# ---------------------------------------------- sugestão de colunas
def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or ""))
                   if not unicodedata.combining(c))


def _normal(nome):
    return re.sub(r"[^a-z0-9]", "", _sem_acento(nome).lower())


def sugerir(entidade, colunas):
    """`{chave: coluna}` pelo nome das colunas da tabela: primeiro nome
    igual a uma das palavras, depois nome que **contém** a palavra (só para
    palavras de 4 letras ou mais — `un` dentro de `FUNCIONARIO` não é
    unidade). Cada coluna vai para uma informação só."""
    normais = [(_normal(c), c) for c in colunas]
    usadas, sug = set(), {}
    infos = ENTIDADES[entidade].informacoes
    for exato in (True, False):
        for info in infos:
            if info.chave in sug:
                continue
            for p in info.palavras:
                p = _normal(p)
                achou = next(
                    (c for n, c in normais if c not in usadas
                     and (n == p if exato else (len(p) >= 4 and p in n))),
                    None)
                if achou:
                    sug[info.chave] = achou
                    usadas.add(achou)
                    break
    return sug


# ------------------------------------------------- as linhas que voltam
def valor(v):
    """Valor do banco no formato que os cálculos da planilha aceitam: texto
    aparado, número (`Decimal` vira `float`), data DDMMAAAA. Bytes ficam
    bytes (é o XML) — exceto em coluna de texto, que o adaptador já
    decodificou."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, datetime.datetime):
        v = v.date()
    if isinstance(v, datetime.date):
        return v.strftime("%d%m%Y")
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v)
    return str(v).strip()


def linhas(entidade, registros):
    """Converte as linhas do banco (`{chave: valor bruto}`) para as chaves
    canônicas, como a planilha entrega. Linha sem a informação obrigatória
    (código vazio) é descartada."""
    obrig = [i.chave for i in ENTIDADES[entidade].obrigatorias]
    saida = []
    for reg in registros:
        d = {k: valor(v) for k, v in reg.items()}
        if all(_preenchido(d.get(k)) for k in obrig):
            saida.append(d)
    return saida


def _preenchido(v):
    if v is None:
        return False
    if isinstance(v, (bytes, str)):
        return bool(v.strip())
    return True


def estoque_na_data(registros, dt_inv):
    """A posição de cada item **na data do inventário**: com a coluna de
    data, a linha mais recente até `dt_inv` (DDMMAAAA); sem ela, a única.
    Item repetido sem data soma as quantidades e os valores (estoque por
    depósito, por lote)."""
    def aaaammdd(ddmmaaaa):
        s = str(ddmmaaaa or "")
        return s[4:8] + s[2:4] + s[0:2] if len(s) == 8 else ""
    limite = aaaammdd(dt_inv)
    por_item = {}
    for ln in registros:
        cod = str(ln.get("cod_item") or "").strip()
        if not cod:
            continue
        data = aaaammdd(ln.get("data"))
        if data and limite and data > limite:
            continue
        atual = por_item.get(cod)
        if atual is None:
            por_item[cod] = (data, dict(ln))
        elif data > atual[0]:
            por_item[cod] = (data, dict(ln))
        elif data == atual[0] and not data:
            soma = atual[1]
            for k in ("qtd", "vl_item"):
                soma[k] = _num(soma.get(k)) + _num(ln.get(k))
    return [ln for _d, ln in por_item.values()]


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v or "0").replace(",", "."))
    except ValueError:
        return 0.0


def com_cadastro(estoque, produtos):
    """Completa cada linha do estoque com o cadastro do produto (descrição,
    NCM, unidade…) — é o que o inventário precisa para criar o 0200 dos
    itens novos. O que o estoque já trouxer prevalece."""
    cad = {str(p.get("cod_item") or "").strip(): p for p in produtos}
    saida = []
    for ln in estoque:
        p = cad.get(str(ln.get("cod_item") or "").strip()) or {}
        d = {k: v for k, v in p.items() if _preenchido(v)}
        d.update({k: v for k, v in ln.items() if _preenchido(v)})
        saida.append(d)
    return saida


# ------------------------------------------------------------- XML
def conteudo_xml(v):
    """Os bytes do XML como o ERP os guardou: texto, bytes, compactado
    (gzip ou zlib) ou em base64 — cada ERP faz de um jeito. None se não
    der para chegar a um XML."""
    if v is None:
        return None
    if isinstance(v, str):
        bruto = v.strip().encode("utf-8")
    else:
        bruto = bytes(v).strip()
    for _ in range(3):                  # base64 de um gzip, por exemplo
        if bruto[:1] == b"<" or bruto[:3] == b"\xef\xbb\xbf":
            return bruto
        if bruto[:2] == b"\x1f\x8b":
            try:
                bruto = gzip.decompress(bruto).strip()
                continue
            except (OSError, EOFError):
                return None
        if bruto[:1] == b"\x78":
            try:
                bruto = zlib.decompress(bruto).strip()
                continue
            except zlib.error:
                pass
        try:
            bruto = base64.b64decode(bruto, validate=True).strip()
        except (ValueError, binascii.Error):
            return None
    return None


def ler_xmls(itens):
    """`[(documento, erro)]` de `[(nome, conteúdo como o banco guardou)]`
    — a unidade de trabalho da leitura em paralelo (`infra/paralelo.py`):
    função de módulo, que vai para outro processo pelo nome."""
    saida = []
    for nome, bruto in itens:
        xml = conteudo_xml(bruto)
        if xml is None:
            saida.append((None, "o conteúdo do banco não é XML (nem "
                                "compactado, nem em base64)"))
        else:
            saida += xml_fiscal.ler_conteudos([(nome, xml)])
    return saida

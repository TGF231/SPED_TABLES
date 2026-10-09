# -*- coding: utf-8 -*-
"""Adaptadores dos bancos dos ERPs: Firebird (2.5 a 5), SQL Server, MySQL,
SQLite e pastas de DBF — **só leitura**.

Todos respondem às mesmas perguntas: `testar()`, `tabelas()`,
`colunas(origem)`, `amostra(origem)` e `ler(consulta)`. A `Consulta` vem do
domínio (`dominio/erp.py`) sem uma linha de SQL; o dialeto é daqui — aspas
de identificador, o `FIRST`/`TOP`/`LIMIT`, o marcador de parâmetro.

Nada é gravado no banco do ERP. Além de o programa só montar `SELECT`, cada
adaptador abre a transação como somente leitura onde o driver deixa
(Firebird, MySQL, SQLite) e nunca confirma nada; a consulta própria do
perfil passa por `erp.sql_so_leitura`. Mesmo assim, o certo é a conexão usar
um usuário do banco que só tenha permissão de leitura.

Drivers: `firebirdsql` (puro Python, fala o protocolo do 2.5 ao 5), `pyodbc`
com o driver ODBC do SQL Server, `pymysql` (opcional) e `sqlite3`. Os DBF
são lidos por `infra/dbf.py`.
"""

import contextlib
import datetime
import os

from sped_tables.dominio import erp
from sped_tables.infra import dbf

LOTE = 500                      # linhas por ida ao banco
AMOSTRA = 20
ESPERA = 10                     # segundos para conectar


class ErroDeBanco(Exception):
    """Falha ao falar com o banco do ERP, com a mensagem para a pessoa."""


def adaptador(sistema, conexao):
    """O adaptador do tipo de banco do `sistema` para a `conexao`."""
    classe = {"firebird": Firebird, "sqlserver": SqlServer, "mysql": MySQL,
              "sqlite": SQLite, "dbf": PastaDBF}.get(sistema.banco)
    if classe is None:
        raise ErroDeBanco("Tipo de banco desconhecido: %r." % sistema.banco)
    return classe(conexao)


# ================================================================ SQL
class _BancoSQL:
    marcador = "?"

    def __init__(self, conexao):
        self.c = conexao

    # --- o que cada dialeto define
    def _conectar(self):                                # pragma: no cover
        raise NotImplementedError

    def _sql_tabelas(self):                             # pragma: no cover
        raise NotImplementedError

    def _sql_versao(self):                              # pragma: no cover
        raise NotImplementedError

    def _limitar(self, sql, n):
        return "%s LIMIT %d" % (sql, n)

    def _aspas(self, nome):
        return '"%s"' % nome.replace('"', '""')

    def _parametro(self, v):
        return v

    def _erros(self):
        return (Exception,)

    # --- comum
    @contextlib.contextmanager
    def _cursor(self):
        try:
            con = self._conectar()
        except ErroDeBanco:
            raise
        except self._erros() as exc:
            raise ErroDeBanco("Não foi possível conectar: %s"
                              % _mensagem(exc)) from exc
        try:
            cur = con.cursor()
            try:
                yield cur
            except ErroDeBanco:
                raise
            except self._erros() as exc:
                raise ErroDeBanco("O banco recusou a consulta: %s"
                                  % _mensagem(exc)) from exc
            finally:
                with contextlib.suppress(Exception):
                    cur.close()
        finally:
            with contextlib.suppress(Exception):
                con.rollback()
            with contextlib.suppress(Exception):
                con.close()

    def _tabela(self, nome):
        """Nome da tabela entre aspas, parte a parte (`esquema.tabela`)."""
        return ".".join(self._aspas(p) for p in nome.split("."))

    def _de(self, origem):
        if origem.get("sql"):
            if not erp.sql_so_leitura(origem["sql"]):
                raise ErroDeBanco("A consulta própria precisa ser um único "
                                  "SELECT.")
            return "(%s) q" % origem["sql"].strip().rstrip(";")
        if not origem.get("tabela"):
            raise ErroDeBanco("Escolha a tabela.")
        return self._tabela(origem["tabela"])

    def testar(self):
        with self._cursor() as cur:
            cur.execute(self._sql_versao())
            linha = cur.fetchone()
        return str(linha[0]).strip() if linha else "conectado"

    def tabelas(self):
        with self._cursor() as cur:
            cur.execute(self._sql_tabelas())
            return [_texto(l[0]) for l in cur.fetchall()]

    def colunas(self, origem):
        with self._cursor() as cur:
            cur.execute("SELECT * FROM %s WHERE 1 = 0" % self._de(origem))
            return [_texto(d[0]).strip() for d in cur.description]

    def amostra(self, origem, n=AMOSTRA):
        with self._cursor() as cur:
            cur.execute(self._limitar("SELECT * FROM %s" % self._de(origem),
                                      n))
            nomes = [_texto(d[0]).strip() for d in cur.description]
            return nomes, [tuple(l) for l in cur.fetchmany(n)]

    def montar(self, consulta):
        """`(sql, parâmetros, chaves)` da consulta — `chaves` na ordem das
        colunas do SELECT."""
        chaves = list(consulta.colunas)
        if not chaves:
            raise ErroDeBanco("Nenhuma coluna mapeada.")
        campos = ", ".join(self._aspas(consulta.colunas[k]) for k in chaves)
        sql = "SELECT %s FROM %s" % (campos, self._de(consulta.origem))
        params = []
        if consulta.filtros:
            sql += " WHERE " + " AND ".join(
                "%s %s %s" % (self._aspas(f.coluna), f.operador,
                              self.marcador) for f in consulta.filtros)
            params = [self._parametro(f.valor) for f in consulta.filtros]
        return sql, params, chaves

    def ler(self, consulta, cancelar=None):
        """Gera `{chave: valor}` de cada linha, em lotes de `LOTE`."""
        sql, params, chaves = self.montar(consulta)
        with self._cursor() as cur:
            cur.execute(sql, params)
            while True:
                if cancelar and cancelar():
                    return
                lote = cur.fetchmany(LOTE)
                if not lote:
                    return
                for linha in lote:
                    yield dict(zip(chaves, linha))


class Firebird(_BancoSQL):
    """Firebird 2.5 a 5. O 3+ autentica por SRP com o canal cifrado; o 2.5
    só conhece o `Legacy_Auth` — a conexão tenta os dois, nessa ordem."""

    def _erros(self):
        import firebirdsql
        return (firebirdsql.Error, OSError)

    def _conectar(self):
        try:
            import firebirdsql
        except ImportError as exc:                      # pragma: no cover
            raise ErroDeBanco("Falta o pacote firebirdsql.") from exc
        base = dict(
            host=self.c.host or "localhost", database=self.c.base,
            port=int(self.c.porta or 3050), user=self.c.usuario or "SYSDBA",
            password=self.c.senha, charset=self.c.codificacao or "WIN1252",
            timeout=ESPERA, readonly=True)
        primeiro = None
        for plugin, cifra in (("Srp256", True), ("Srp", True),
                              ("Legacy_Auth", False)):
            try:
                return firebirdsql.connect(auth_plugin_name=plugin,
                                           wire_crypt=cifra, **base)
            except OSError:
                raise                   # servidor fora do ar: não insiste
            except firebirdsql.Error as exc:
                primeiro = primeiro or exc
        raise primeiro

    def _sql_tabelas(self):
        return ("SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS "
                "WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0 ORDER BY 1")

    def _sql_versao(self):
        return ("SELECT RDB$GET_CONTEXT('SYSTEM', 'ENGINE_VERSION') "
                "FROM RDB$DATABASE")

    def _limitar(self, sql, n):
        return sql.replace("SELECT ", "SELECT FIRST %d " % n, 1)


class SqlServer(_BancoSQL):
    """SQL Server pelo ODBC. Sem usuário, entra com a conta do Windows."""

    DRIVERS = ("ODBC Driver 18 for SQL Server",
               "ODBC Driver 17 for SQL Server",
               "ODBC Driver 13 for SQL Server",
               "ODBC Driver 11 for SQL Server",
               "SQL Server Native Client 11.0", "SQL Server")

    def _erros(self):
        import pyodbc
        return (pyodbc.Error,)

    def _driver(self, pyodbc):
        instalados = set(pyodbc.drivers())
        for d in self.DRIVERS:
            if d in instalados:
                return d
        raise ErroDeBanco("Nenhum driver ODBC do SQL Server instalado. "
                          "Instale o \"ODBC Driver 18 for SQL Server\" da "
                          "Microsoft.")

    def cadeia(self, driver):
        servidor = self.c.host or "localhost"
        if self.c.porta:
            servidor += "," + self.c.porta
        partes = ["DRIVER={%s}" % driver, "SERVER=%s" % servidor,
                  "DATABASE=%s" % self.c.base, "APP=SPED Tables"]
        if self.c.usuario:
            partes += ["UID=%s" % self.c.usuario,
                       "PWD={%s}" % self.c.senha.replace("}", "}}")]
        else:
            partes.append("Trusted_Connection=yes")
        if driver.startswith("ODBC Driver 18"):
            # o 18 cifra por padrão e recusa o certificado próprio que todo
            # servidor de loja usa
            partes.append("TrustServerCertificate=yes")
        return ";".join(partes)

    def _conectar(self):
        try:
            import pyodbc
        except ImportError as exc:                      # pragma: no cover
            raise ErroDeBanco("Falta o pacote pyodbc.") from exc
        return pyodbc.connect(self.cadeia(self._driver(pyodbc)),
                              timeout=ESPERA, autocommit=False)

    def _sql_tabelas(self):
        return ("SELECT CASE WHEN TABLE_SCHEMA = 'dbo' THEN TABLE_NAME "
                "ELSE TABLE_SCHEMA + '.' + TABLE_NAME END "
                "FROM INFORMATION_SCHEMA.TABLES ORDER BY 1")

    def _sql_versao(self):
        return "SELECT CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(50))"

    def _limitar(self, sql, n):
        return sql.replace("SELECT ", "SELECT TOP %d " % n, 1)

    def _aspas(self, nome):
        return "[%s]" % nome.replace("]", "]]")


class MySQL(_BancoSQL):
    marcador = "%s"

    def _erros(self):
        import pymysql
        return (pymysql.Error,)

    def _conectar(self):
        try:
            import pymysql
        except ImportError as exc:
            raise ErroDeBanco(
                "O suporte a MySQL precisa do pacote pymysql "
                "(py -m pip install pymysql).") from exc
        try:
            con = pymysql.connect(
                host=self.c.host or "localhost",
                port=int(self.c.porta or 3306), user=self.c.usuario,
                password=self.c.senha, database=self.c.base,
                # `utf8` e não `utf8mb4`: o MySQL 5.1 dos ERPs antigos não
                # conhece o segundo e recusa a conexão
                charset=self.c.codificacao or "utf8",
                connect_timeout=ESPERA, autocommit=False)
        except RuntimeError as exc:
            # MySQL 8 com caching_sha2_password: sem canal cifrado, o
            # PyMySQL precisa do pacote cryptography, que o executável não
            # leva (o MySQL 5.x dos ERPs usa mysql_native_password)
            if "cryptography" in str(exc):
                raise ErroDeBanco(
                    "O MySQL pede autenticação caching_sha2_password (MySQL "
                    "8). Crie o usuário de leitura com "
                    "mysql_native_password: ALTER USER 'leitor'@'%' "
                    "IDENTIFIED WITH mysql_native_password BY '...'."
                ) from exc
            raise
        # transação somente leitura só existe a partir do MySQL 5.6.5; antes
        # disso fica a transação comum, que nunca é confirmada
        try:
            with con.cursor() as cur:
                cur.execute("START TRANSACTION READ ONLY")
        except pymysql.Error:
            with con.cursor() as cur:
                cur.execute("START TRANSACTION")
        return con

    def _sql_tabelas(self):
        return ("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() ORDER BY 1")

    def _sql_versao(self):
        return "SELECT VERSION()"

    def _aspas(self, nome):
        return "`%s`" % nome.replace("`", "``")


class SQLite(_BancoSQL):
    def _erros(self):
        import sqlite3
        return (sqlite3.Error,)

    def _conectar(self):
        import sqlite3
        if not os.path.isfile(self.c.base):
            raise ErroDeBanco("Arquivo não encontrado: %s" % self.c.base)
        caminho = os.path.abspath(self.c.base).replace("\\", "/")
        return sqlite3.connect("file:%s?mode=ro" % caminho, uri=True,
                               timeout=ESPERA)

    def _sql_tabelas(self):
        return ("SELECT name FROM sqlite_master WHERE type IN "
                "('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY 1")

    def _sql_versao(self):
        return "SELECT 'SQLite ' || sqlite_version()"

    def _parametro(self, v):
        # o sqlite3 não converte mais data sozinho (3.12): ISO, como grava
        return v.isoformat() if isinstance(v, datetime.date) else v


# ================================================================ DBF
class PastaDBF:
    """Uma pasta de DBF. Sem SQL: o filtro roda aqui, linha a linha."""

    def __init__(self, conexao):
        self.c = conexao

    def _pasta(self):
        if not os.path.isdir(self.c.base):
            raise ErroDeBanco("Pasta não encontrada: %s" % self.c.base)
        return self.c.base

    def _abrir(self, origem):
        if origem.get("sql"):
            raise ErroDeBanco("Arquivos DBF não aceitam consulta própria: "
                              "escolha a tabela.")
        try:
            return dbf.TabelaDBF(dbf.caminho_da_tabela(
                self._pasta(), origem.get("tabela") or ""),
                self.c.codificacao or None)
        except (OSError, dbf.ErroDBF) as exc:
            raise ErroDeBanco(str(exc)) from exc

    def testar(self):
        n = len(self.tabelas())
        if not n:
            raise ErroDeBanco("Nenhum arquivo .dbf na pasta.")
        return "%d tabela(s) DBF" % n

    def tabelas(self):
        return dbf.tabelas(self._pasta())

    def colunas(self, origem):
        with self._abrir(origem) as t:
            return t.colunas

    def amostra(self, origem, n=AMOSTRA):
        with self._abrir(origem) as t:
            linhas = []
            for reg in t.registros():
                linhas.append(tuple(reg.values()))
                if len(linhas) >= n:
                    break
            return t.colunas, linhas

    def ler(self, consulta, cancelar=None):
        chaves = list(consulta.colunas)
        with self._abrir(consulta.origem) as t:
            existentes = set(t.colunas)
            faltam = [c for c in list(consulta.colunas.values())
                      + [f.coluna for f in consulta.filtros]
                      if c.upper() not in existentes]
            if faltam:
                raise ErroDeBanco("Coluna(s) fora da tabela: %s"
                                  % ", ".join(sorted(set(faltam))))
            for n, reg in enumerate(t.registros()):
                if cancelar and n % LOTE == 0 and cancelar():
                    return
                if all(_passa(reg.get(f.coluna.upper()), f)
                       for f in consulta.filtros):
                    yield {k: reg.get(consulta.colunas[k].upper())
                           for k in chaves}


def _passa(valor, filtro):
    alvo = filtro.valor
    if isinstance(alvo, datetime.date):
        if isinstance(valor, datetime.datetime):
            valor = valor.date()
        if not isinstance(valor, datetime.date):
            return False
    else:
        valor, alvo = _comparavel(valor), _comparavel(alvo)
        if type(valor) is not type(alvo):
            valor, alvo = str(valor), str(alvo)
    if filtro.operador == "=":
        return valor == alvo
    if filtro.operador == ">=":
        return valor >= alvo
    return valor <= alvo


def _comparavel(v):
    """`"001"` e `1` são a mesma empresa."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v if v is not None else "").strip()
    try:
        return float(s)
    except ValueError:
        return s


def _texto(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


def _mensagem(exc):
    texto = " ".join(str(a) for a in getattr(exc, "args", ()) if a) \
        or str(exc) or type(exc).__name__
    return texto.strip()

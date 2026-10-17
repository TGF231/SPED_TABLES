# -*- coding: utf-8 -*-
"""A **base de referência**: tudo o que o programa sabe do SPED fora do
próprio código — leiaute de cada versão, tabelas oficiais, guias práticos
e NCM vigente —, montado na compilação e nunca lido do PVA da máquina de
quem usa (ver `docs/adr/0001-base-de-referencia-compilada.md`).

As fontes ficam em `base/`, em texto, versionadas no git e regravadas pelo
consolidador (`py -m consolidador extrair`); `compilar` as transforma num
SQLite que viaja com o executável. Uma base mais nova pode ser importada
sem trocar de programa (`importar`); vale a mais nova entre a embutida e a
importada (`em_uso`).

Fontes (`base/`):

    manifesto.json                    versão, data, origem, leiautes, tabelas
    leiaute/<LEIAUTE>/<COD_VER>.json  {"versao", "descritor", "dt_ini",
                                       "dt_fim", "estrutura"}
    tabelas/<GRUPO@TABELA>.txt        a tabela no formato do PVA, em UTF-8
    guias/<LEIAUTE>.json              o guia prático extraído
    ncm/vigente.txt                   um NCM por linha (opcional)

A `estrutura` guarda os nomes do descritor e **a ordem dos campos é a
posição** no registro: não ordene o JSON do leiaute.
"""

import contextlib
import hashlib
import json
import os
import pathlib
import sqlite3
import zipfile
import zlib

from sped_tables.infra import dados

ESQUEMA = 1
ARQUIVO = "base_referencia.db"
LEIAUTES = ("ICMS", "CONTRIB")
# membro do pacote maior que isto não é base de referência: é engano ou
# bomba de zip
LIMITE_PACOTE = 64 * 1024 * 1024


class BaseInvalida(Exception):
    """O arquivo não é uma base de referência legível."""


class EsquemaNovo(BaseInvalida):
    """A base foi feita para um programa mais novo."""


class BaseRecusada(Exception):
    """O pacote não pode substituir a base em uso; a mensagem diz por quê."""


def chave_da_versao(versao):
    """`"2026.10.1"` -> `(2026, 10, 1)`, para comparar; inválida -> `()`."""
    try:
        return tuple(int(p) for p in str(versao).split("."))
    except ValueError:
        return ()


def arquivo_da_tabela(chave):
    """`GRUPO$TABELA` -> nome do arquivo em `base/tabelas` (o `$` atrapalha
    no terminal)."""
    return chave.replace("$", "@") + ".txt"


def impressao_digital(caminho):
    """SHA-256 do arquivo, em hexadecimal."""
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# --------------------------------------------------------------- compilar
def _texto(caminho):
    # o git pode trocar o fim de linha no checkout: normaliza, para a
    # compilação dar o mesmo banco em qualquer máquina
    with open(caminho, encoding="utf-8") as fh:
        return "\n".join(fh.read().splitlines())


def _json(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


def _comprimir(texto):
    return zlib.compress(texto.encode("utf-8"), 9)


def compilar(fontes, destino):
    """Compila `fontes` (a pasta `base/`) num SQLite em `destino`, com o
    SHA-256 em `destino.sha256`, e devolve o manifesto.

    Mesmas fontes, mesmo banco, byte a byte: nada de data de compilação, e
    tudo é inserido em ordem fixa."""
    manifesto = _json(os.path.join(fontes, "manifesto.json"))
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    temporario = destino + ".compilando"
    if os.path.exists(temporario):
        os.remove(temporario)
    con = sqlite3.connect(temporario)
    try:
        con.executescript("""
            PRAGMA page_size = 4096;
            CREATE TABLE manifesto (conteudo TEXT NOT NULL);
            CREATE TABLE leiaute (layout TEXT, versao TEXT, dt_ini TEXT,
                                  dt_fim TEXT, descritor TEXT,
                                  estrutura BLOB,
                                  PRIMARY KEY (layout, versao));
            CREATE TABLE tabela (chave TEXT PRIMARY KEY, versao INTEGER,
                                 texto BLOB);
            CREATE TABLE guia (layout TEXT PRIMARY KEY, conteudo BLOB);
            CREATE TABLE ncm_vigente (ncm TEXT PRIMARY KEY);
        """)
        con.execute("PRAGMA user_version = %d" % int(manifesto["esquema"]))
        con.execute("INSERT INTO manifesto VALUES (?)", (json.dumps(
            manifesto, ensure_ascii=False, sort_keys=True),))
        for layout in LEIAUTES:
            for versao in sorted(manifesto.get("leiautes", {})
                                 .get(layout, [])):
                d = _json(os.path.join(fontes, "leiaute", layout,
                                       versao + ".json"))
                con.execute(
                    "INSERT INTO leiaute VALUES (?, ?, ?, ?, ?, ?)",
                    (layout, versao, d.get("dt_ini", ""),
                     d.get("dt_fim", ""), d.get("descritor", ""),
                     _comprimir(json.dumps(d["estrutura"],
                                           ensure_ascii=False))))
        for chave in sorted(manifesto.get("tabelas", {})):
            texto = _texto(os.path.join(fontes, "tabelas",
                                        arquivo_da_tabela(chave)))
            con.execute("INSERT INTO tabela VALUES (?, ?, ?)",
                        (chave, int(manifesto["tabelas"][chave]),
                         _comprimir(texto)))
        for layout in LEIAUTES:
            caminho = os.path.join(fontes, "guias", layout + ".json")
            if os.path.exists(caminho):
                con.execute("INSERT INTO guia VALUES (?, ?)",
                            (layout, _comprimir(_texto(caminho))))
        caminho = os.path.join(fontes, "ncm", "vigente.txt")
        if os.path.exists(caminho):
            ncms = sorted({l.strip() for l in _texto(caminho).splitlines()
                           if l.strip()})
            con.executemany("INSERT INTO ncm_vigente VALUES (?)",
                            [(n,) for n in ncms])
        con.commit()
        con.execute("VACUUM")
    finally:
        con.close()
    os.replace(temporario, destino)
    with open(destino + ".sha256", "w", encoding="ascii",
              newline="\n") as fh:
        fh.write(impressao_digital(destino) + "\n")
    return manifesto


# ------------------------------------------------------------------- ler
class Base:
    """Um banco compilado. Cada consulta abre e fecha a conexão (o `sqlite3`
    não divide conexão entre threads) e o que é lido fica em memória: a base
    não muda enquanto o programa roda."""

    def __init__(self, caminho):
        self.caminho = caminho
        self._cache = {}
        if not os.path.isfile(caminho):
            raise BaseInvalida("%s não existe" % caminho)
        try:
            with self._conectar() as con:
                esquema = con.execute("PRAGMA user_version").fetchone()[0]
                (texto,) = con.execute(
                    "SELECT conteudo FROM manifesto").fetchone()
            manifesto = json.loads(texto)
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise BaseInvalida(str(exc))
        if esquema > ESQUEMA:
            raise EsquemaNovo("esquema %d; este programa entende até o %d"
                              % (esquema, ESQUEMA))
        if not isinstance(manifesto, dict) or not chave_da_versao(
                manifesto.get("versao")):
            raise BaseInvalida("manifesto sem versão")
        self._manifesto = manifesto

    def _conectar(self):
        uri = pathlib.Path(self.caminho).resolve().as_uri() + "?mode=ro"
        return contextlib.closing(sqlite3.connect(uri, uri=True))

    def _uma_vez(self, chave, ler):
        if chave not in self._cache:
            with self._conectar() as con:
                self._cache[chave] = ler(con)
        return self._cache[chave]

    def manifesto(self):
        return self._manifesto

    def versoes(self, layout):
        """`{COD_VER: (dt_ini, dt_fim, descritor)}` das versões guardadas."""
        return self._uma_vez(("versoes", layout), lambda con: {
            v: (i, f, d) for v, i, f, d in con.execute(
                "SELECT versao, dt_ini, dt_fim, descritor FROM leiaute "
                "WHERE layout = ? ORDER BY versao", (layout,))})

    def estrutura(self, layout, versao):
        """Estrutura da versão com os nomes do descritor, ou None."""
        def ler(con):
            linha = con.execute(
                "SELECT estrutura FROM leiaute WHERE layout = ? AND "
                "versao = ?", (layout, versao)).fetchone()
            return (json.loads(zlib.decompress(linha[0]).decode("utf-8"))
                    if linha else None)
        return self._uma_vez(("estrutura", layout, versao), ler)

    def tabelas(self):
        """`{chave: (texto, versao)}` — o mesmo formato de
        `tabelas_oficiais.tabelas_da_pasta`."""
        return self._uma_vez("tabelas", lambda con: {
            c: (zlib.decompress(t).decode("utf-8"), v)
            for c, v, t in con.execute(
                "SELECT chave, versao, texto FROM tabela")})

    def guia(self, layout):
        def ler(con):
            linha = con.execute("SELECT conteudo FROM guia WHERE layout = ?",
                                (layout,)).fetchone()
            return (json.loads(zlib.decompress(linha[0]).decode("utf-8"))
                    if linha else {})
        return self._uma_vez(("guia", layout), ler)

    def ncm_vigente(self):
        """Conjunto de NCM vigentes, ou None quando a base não traz."""
        return self._uma_vez("ncm", lambda con: {
            n for (n,) in con.execute("SELECT ncm FROM ncm_vigente")}
            or None)


# ------------------------------------------------------------ qual vale
def pasta_fontes():
    """`base/` do repositório — só existe rodando do código-fonte."""
    return dados.recurso("base")


def caminho_embutido():
    return dados.recurso(os.path.join("recursos", ARQUIVO))


def caminho_importado():
    return dados.caminho(ARQUIVO)


def _mais_recente(pasta):
    m = 0.0
    for raiz, _d, nomes in os.walk(pasta):
        for n in nomes:
            m = max(m, os.path.getmtime(os.path.join(raiz, n)))
    return m


def compilar_se_preciso():
    """Rodando do código-fonte, recompila a base embutida quando ela falta
    ou quando `base/` mudou depois dela. Empacotado, não há fontes."""
    fontes, destino = pasta_fontes(), caminho_embutido()
    if dados.empacotado() or not os.path.isfile(
            os.path.join(fontes, "manifesto.json")):
        return False
    if (os.path.exists(destino)
            and os.path.getmtime(destino) >= _mais_recente(fontes)):
        return False
    compilar(fontes, destino)
    return True


def em_uso():
    """`(Base, "embutida" | "importada")` da base que vale — a mais nova
    entre as duas —, ou `(None, motivo)` quando nenhuma é legível.

    Importada ilegível é avisada e ignorada; nunca apagada."""
    try:
        compilar_se_preciso()
    except Exception as exc:                               # noqa: BLE001
        dados.avisar("Não foi possível compilar a base de referência de "
                     "base/ (%s); segue a última compilada." % exc)
    candidatas = []
    for origem, caminho in (("embutida", caminho_embutido()),
                            ("importada", caminho_importado())):
        if not os.path.exists(caminho):
            continue
        try:
            candidatas.append((Base(caminho), origem))
        except BaseInvalida as exc:
            dados.avisar("A base de referência %s está ilegível (%s) e foi "
                         "ignorada." % (origem, exc))
    if not candidatas:
        return None, "nenhuma base de referência legível"
    return max(candidatas,
               key=lambda c: chave_da_versao(c[0].manifesto()["versao"]))


# ------------------------------------------------------------- importar
def empacotar(caminho_banco, destino_zip):
    """O pacote que se distribui: o banco e o manifesto com a impressão
    digital do banco."""
    base = Base(caminho_banco)
    with open(caminho_banco, "rb") as fh:
        banco = fh.read()
    manifesto = dict(base.manifesto(),
                     sha256=hashlib.sha256(banco).hexdigest())
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(ARQUIVO, banco)
        z.writestr("manifesto.json", json.dumps(
            manifesto, ensure_ascii=False, indent=1, sort_keys=True))
    return destino_zip


def inspecionar(caminho_zip):
    """Lê o pacote sem instalar nada: `{"manifesto", "sha256", "confere",
    "banco"}`. Pacote que não serve levanta `BaseRecusada`."""
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            nomes = set(z.namelist())
            if ARQUIVO not in nomes or "manifesto.json" not in nomes:
                raise BaseRecusada("O pacote não tem o banco e o manifesto "
                                   "da base de referência.")
            if (z.getinfo(ARQUIVO).file_size > LIMITE_PACOTE
                    or z.getinfo("manifesto.json").file_size > 1 << 20):
                raise BaseRecusada("O pacote é grande demais para ser uma "
                                   "base de referência.")
            banco = z.read(ARQUIVO)
            manifesto = json.loads(z.read("manifesto.json").decode("utf-8"))
    except (zipfile.BadZipFile, OSError, ValueError, KeyError) as exc:
        raise BaseRecusada("O arquivo não é um pacote de base de referência "
                           "legível (%s)." % exc)
    if not isinstance(manifesto, dict):
        raise BaseRecusada("O manifesto do pacote está ilegível.")
    digital = hashlib.sha256(banco).hexdigest()
    return {"manifesto": manifesto, "sha256": digital,
            "confere": digital == manifesto.get("sha256"), "banco": banco}


def importar(caminho_zip):
    """Instala a base do pacote na pasta de dados, se ela for íntegra,
    legível por este programa e mais nova que a em uso. Devolve o
    manifesto; o que não serve levanta `BaseRecusada` sem tocar na base em
    uso."""
    pacote = inspecionar(caminho_zip)
    if not pacote["confere"]:
        raise BaseRecusada(
            "A impressão digital do banco (%s…) não confere com a do "
            "manifesto: o arquivo foi alterado ou está corrompido."
            % pacote["sha256"][:16])
    destino = caminho_importado()
    temporario = destino + ".importando"
    dados.gravar_atomico(temporario, pacote["banco"])
    try:
        try:
            nova = Base(temporario)
        except EsquemaNovo as exc:
            raise BaseRecusada("Esta base foi feita para um programa mais "
                               "novo (%s). Atualize o programa." % exc)
        except BaseInvalida as exc:
            raise BaseRecusada("O banco do pacote está ilegível (%s)." % exc)
        versao = nova.manifesto()["versao"]
        if versao != pacote["manifesto"].get("versao"):
            raise BaseRecusada("O manifesto do pacote não corresponde ao "
                               "banco.")
        atual, _origem = em_uso()
        if atual is not None and (chave_da_versao(versao)
                                  <= chave_da_versao(
                                      atual.manifesto()["versao"])):
            raise BaseRecusada("A base %s não é mais nova que a em uso (%s)."
                               % (versao, atual.manifesto()["versao"]))
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
    return nova.manifesto()

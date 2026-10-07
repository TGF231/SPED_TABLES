# -*- coding: utf-8 -*-
"""Leitura de arquivos DBF (dBase III/IV, Clipper, FoxPro, Visual FoxPro),
só leitura e sem dependência externa.

O "banco" de um ERP em DBF é uma **pasta**: cada `.dbf` é uma tabela, e o
campo memo mora ao lado, no `.dbt` (dBase/Clipper) ou no `.fpt` (FoxPro).
Registro marcado como apagado (`*` no primeiro byte) não existe — é assim
que o próprio ERP o enxerga.

A codificação vem do byte 29 do cabeçalho quando o arquivo a declara; os
sistemas em Clipper quase nunca declaram, e ali o padrão é a página de
código do DOS (cp850) — a conexão pode trocar.
"""

import datetime
import os
import struct

# byte 29 do cabeçalho -> codificação (as que aparecem em ERP brasileiro)
PAGINAS = {0x01: "cp437", 0x02: "cp850", 0x03: "cp1252", 0x57: "cp1252",
           0x58: "cp1252", 0x59: "cp1252", 0x64: "cp852", 0x65: "cp866",
           0x66: "cp865", 0x7d: "cp1255", 0xc8: "cp1250", 0xc9: "cp1251"}
PADRAO = "cp850"


class ErroDBF(Exception):
    pass


class Campo:
    __slots__ = ("nome", "tipo", "tamanho", "decimais", "deslocamento")

    def __init__(self, nome, tipo, tamanho, decimais, deslocamento):
        self.nome, self.tipo = nome, tipo
        self.tamanho, self.decimais = tamanho, decimais
        self.deslocamento = deslocamento


class TabelaDBF:
    """Uma tabela DBF aberta para leitura. Use com `with`."""

    def __init__(self, caminho, codificacao=None):
        self.caminho = caminho
        self._fh = open(caminho, "rb")
        try:
            self._ler_cabecalho(codificacao)
        except Exception:
            self._fh.close()
            raise
        self._memo = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.fechar()

    def fechar(self):
        self._fh.close()
        if self._memo is not None:
            self._memo.close()

    # ------------------------------------------------------- cabeçalho
    def _ler_cabecalho(self, codificacao):
        cab = self._fh.read(32)
        if len(cab) < 32:
            raise ErroDBF("arquivo curto demais para ser DBF")
        self.versao = cab[0]
        (self.quantidade,) = struct.unpack("<I", cab[4:8])
        self.tamanho_cabecalho, self.tamanho_registro = struct.unpack(
            "<HH", cab[8:12])
        if self.tamanho_cabecalho < 33 or self.tamanho_registro < 1:
            raise ErroDBF("cabeçalho DBF inválido")
        self.codificacao = (codificacao or PAGINAS.get(cab[29]) or PADRAO)
        self.campos = []
        desloc = 1                      # o byte de "apagado" vem primeiro
        while True:
            d = self._fh.read(32)
            if not d or d[0] == 0x0D:
                break
            if len(d) < 32:
                raise ErroDBF("descritor de campo truncado")
            nome = d[:11].split(b"\x00", 1)[0].decode("ascii", "replace")
            tipo = chr(d[11])
            tamanho, decimais = d[16], d[17]
            if tipo == "C" and self.versao not in (0x30, 0x31, 0x32):
                tamanho += decimais << 8    # Clipper: texto acima de 255
                decimais = 0
            self.campos.append(Campo(nome.strip().upper(), tipo, tamanho,
                                     decimais, desloc))
            desloc += tamanho
        # campo de sistema do Visual FoxPro (marca de nulos): não é coluna
        self._visiveis = [c for c in self.campos if c.tipo != "0"]

    @property
    def colunas(self):
        return [c.nome for c in self._visiveis]

    # ------------------------------------------------------- registros
    def registros(self):
        """Gera `{coluna: valor}` de cada registro não apagado."""
        self._fh.seek(self.tamanho_cabecalho)
        for _ in range(self.quantidade):
            bruto = self._fh.read(self.tamanho_registro)
            if len(bruto) < self.tamanho_registro or bruto[:1] == b"\x1a":
                break
            if bruto[:1] == b"*":
                continue
            yield {c.nome: self._valor(c, bruto[c.deslocamento:
                                                c.deslocamento + c.tamanho])
                   for c in self._visiveis}

    def _texto(self, b):
        return b.decode(self.codificacao, "replace").rstrip(" \x00")

    def _valor(self, c, b):
        t = c.tipo
        if t in ("C", "V", "W", "Q"):
            return self._texto(b).strip()
        if t in ("N", "F"):
            s = b.decode("ascii", "replace").strip().replace(",", ".")
            if not s or s.strip("*") == "":
                return None
            try:
                return float(s) if (c.decimais or "." in s) else int(s)
            except ValueError:
                return None
        if t == "D":
            s = b.decode("ascii", "replace").strip()
            try:
                return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
            except ValueError:
                return None
        if t == "L":
            return {"T": True, "Y": True, "S": True, "F": False,
                    "N": False}.get(b.decode("ascii", "replace").upper())
        if t == "I":
            return struct.unpack("<i", b)[0]
        if t == "Y":
            return struct.unpack("<q", b)[0] / 10000.0
        if t == "B" and c.tamanho == 8 and self.versao in (0x30, 0x31, 0x32):
            return struct.unpack("<d", b)[0]
        if t == "T" and c.tamanho == 8:
            dia, ms = struct.unpack("<ii", b)
            if not dia:
                return None
            data = datetime.date.fromordinal(dia - 1721425)
            return datetime.datetime.combine(data, datetime.time()) + \
                datetime.timedelta(milliseconds=ms)
        if t in ("M", "G", "B"):
            return self._memo_de(c, b)
        return self._texto(b).strip()

    # ------------------------------------------------------------ memo
    def _memo_de(self, c, b):
        if c.tamanho == 4:
            (bloco,) = struct.unpack("<I", b)
        else:
            s = b.decode("ascii", "replace").strip()
            if not s.isdigit():
                return None
            bloco = int(s)
        if not bloco:
            return None
        bruto = self._ler_memo(bloco)
        if bruto is None:
            return None
        return self._texto(bruto) if c.tipo == "M" else bruto

    def _abrir_memo(self):
        if self._memo is None:
            base = os.path.splitext(self.caminho)[0]
            for ext in (".fpt", ".FPT", ".dbt", ".DBT"):
                if os.path.isfile(base + ext):
                    self._memo = open(base + ext, "rb")
                    self._memo_fox = ext.lower() == ".fpt"
                    cab = self._memo.read(32)
                    if self._memo_fox:      # tamanho do bloco: big-endian
                        self._bloco = struct.unpack(">H", cab[6:8])[0] or 64
                    elif self.versao in (0x8b, 0x8e) and len(cab) >= 22:
                        self._bloco = struct.unpack("<H", cab[20:22])[0] or 512
                    else:                   # dBase III / Clipper: fixo
                        self._bloco = 512
                    break
            else:
                self._memo = False
        return self._memo

    def _ler_memo(self, bloco):
        fh = self._abrir_memo()
        if not fh:
            return None
        fh.seek(bloco * self._bloco)
        if self._memo_fox:
            cab = fh.read(8)
            if len(cab) < 8:
                return None
            _tipo, tam = struct.unpack(">II", cab)
            return fh.read(tam)
        inicio = fh.read(8)
        if inicio[:4] == b"\xff\xff\x08\x00":       # dBase IV
            (tam,) = struct.unpack("<I", inicio[4:8])
            return fh.read(max(tam - 8, 0))
        partes = [inicio]                           # dBase III: até 1A 1A
        while True:
            pedaco = fh.read(512)
            partes.append(pedaco)
            junto = b"".join(partes)
            fim = junto.find(b"\x1a")
            if fim >= 0:
                return junto[:fim]
            if not pedaco:
                return junto


def tabelas(pasta):
    """Nomes das tabelas (os `.dbf` da pasta, sem extensão, em maiúsculas)."""
    return sorted(os.path.splitext(n)[0].upper() for n in os.listdir(pasta)
                  if n.lower().endswith(".dbf"))


def caminho_da_tabela(pasta, tabela):
    alvo = tabela.strip().upper()
    for n in os.listdir(pasta):
        if n.lower().endswith(".dbf") and os.path.splitext(n)[0].upper() == alvo:
            return os.path.join(pasta, n)
    raise ErroDBF("a tabela %s não está na pasta" % tabela)

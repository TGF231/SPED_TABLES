# -*- coding: utf-8 -*-
"""Senha guardada sem ficar legível no disco: DPAPI do Windows.

A senha do banco do ERP vai para o `sistemas_erp.json` cifrada com a chave
**do usuário do Windows** (`CryptProtectData`): só a mesma conta, na mesma
máquina, a decifra. Copiar o JSON para outro computador leva a conexão sem a
senha — ela é pedida de novo, em vez de viajar legível.

Estruturas e `argtypes` definidos uma vez, no import (CLAUDE.md, "Ao mexer
na barra de título"): ctypes compara tipos por identidade.
"""

import base64
import ctypes
import sys

PREFIXO = "dpapi:"
_ENTROPIA = b"SPED Tables / sistemas ERP"
_SEM_INTERFACE = 0x1                  # CRYPTPROTECT_UI_FORBIDDEN


class SegredoIndisponivel(Exception):
    """Não deu para cifrar ou decifrar (outra conta, outra máquina, outro
    sistema operacional)."""


if sys.platform == "win32":
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_Blob)]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_Blob)]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p

    def _blob(dados):
        buf = ctypes.create_string_buffer(dados, len(dados))
        return _Blob(len(dados), ctypes.cast(buf, ctypes.POINTER(
            ctypes.c_char))), buf

    def _chamar(funcao, dados):
        entrada, _b1 = _blob(dados)
        entropia, _b2 = _blob(_ENTROPIA)
        saida = _Blob()
        args = [ctypes.byref(entrada), None, ctypes.byref(entropia), None,
                None, _SEM_INTERFACE, ctypes.byref(saida)]
        if not funcao(*args):
            raise SegredoIndisponivel(
                "o Windows recusou (erro %d)" % ctypes.get_last_error())
        try:
            return ctypes.string_at(saida.pbData, saida.cbData)
        finally:
            _kernel32.LocalFree(saida.pbData)

    def _cifrar(dados):
        return _chamar(_crypt32.CryptProtectData, dados)

    def _decifrar(dados):
        return _chamar(_crypt32.CryptUnprotectData, dados)
else:                                                   # pragma: no cover
    def _cifrar(dados):
        raise SegredoIndisponivel("cifra disponível só no Windows")

    _decifrar = _cifrar


def cifrar(texto):
    """`"dpapi:<base64>"`; texto vazio fica vazio."""
    if not texto:
        return ""
    return PREFIXO + base64.b64encode(
        _cifrar(texto.encode("utf-8"))).decode("ascii")


def decifrar(guardado):
    """A senha de volta. Levanta `SegredoIndisponivel` quando o JSON veio
    de outra conta ou máquina, ou não é algo que `cifrar` produziu."""
    if not guardado:
        return ""
    if not guardado.startswith(PREFIXO):
        raise SegredoIndisponivel("senha guardada em formato desconhecido")
    try:
        bruto = base64.b64decode(guardado[len(PREFIXO):], validate=True)
    except ValueError as exc:
        raise SegredoIndisponivel("senha guardada ilegível") from exc
    return _decifrar(bruto).decode("utf-8")

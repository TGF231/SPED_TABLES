# -*- coding: utf-8 -*-
"""Memória persistente: cópia interna dos arquivos SPED, por empresa.

Mesma ideia do PVA, que guarda no banco interno o que foi importado — só que
aqui a "base" é a própria pasta do programa, o que combina com um editor que
trabalha o arquivo texto o tempo todo:

    arquivos/
      22763092000102/
        CONTRIB_202608.txt
        ICMS_202608.txt
      indice.json

**Uma cópia por empresa + leiaute + período**, sempre substituída pela mais
recente. O histórico da interface lista um item por período e aponta para essa
cópia — abrir do histórico é abrir a cópia, não o arquivo de origem, que pode
ter sido movido ou apagado.

A cópia é feita a partir do **arquivo em disco**, nunca de um texto gerado na
memória: assim ela é byte a byte o que o usuário tem, incluindo o encoding
latin-1 e as quebras de linha originais.

Sem dependência de GUI.
"""

import json
import os
import re
import shutil
from datetime import datetime

PASTA = "arquivos"
INDICE = "indice.json"

MOTIVOS = {
    "abertura": "aberto no sistema",
    "salvamento": "salvo pelo sistema",
}


def _base():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), PASTA)


def _caminho_indice():
    return os.path.join(_base(), INDICE)


def so_digitos(txt):
    return re.sub(r"\D", "", txt or "")


def periodo_do_doc(doc):
    """Período AAAAMM a partir da DT_INI do 0000 (formato SPED DDMMAAAA)."""
    i = doc._ix("0000", "DT_INI")
    for r in doc.registros:
        if r.reg == "0000":
            dt = so_digitos(r.valor(i)) if i is not None else ""
            if len(dt) == 8:
                return dt[4:] + dt[2:4]        # AAAA + MM
            return ""
    return ""


def identificar(doc):
    """(cnpj, nome, layout, periodo) do documento aberto."""
    i_cnpj = doc._ix("0000", "CNPJ")
    i_nome = doc._ix("0000", "NOME")
    cnpj = nome = ""
    for r in doc.registros:
        if r.reg == "0000":
            cnpj = so_digitos(r.valor(i_cnpj)) if i_cnpj is not None else ""
            nome = (r.valor(i_nome) or "").strip() if i_nome is not None else ""
            break
    return cnpj, nome, doc.layout or "", periodo_do_doc(doc)


def nome_copia(layout, periodo):
    return "%s_%s.txt" % (layout or "SPED", periodo or "sem_periodo")


def caminho_copia(cnpj, layout, periodo):
    return os.path.join(_base(), cnpj, nome_copia(layout, periodo))


# ----------------------------------------------------------------- índice
def carregar_indice():
    cam = _caminho_indice()
    if not os.path.exists(cam):
        return []
    try:
        with open(cam, encoding="utf-8") as fh:
            dados = json.load(fh)
    except Exception:  # noqa: BLE001
        return []
    return dados if isinstance(dados, list) else []


def _salvar_indice(entradas):
    os.makedirs(_base(), exist_ok=True)
    with open(_caminho_indice(), "w", encoding="utf-8") as fh:
        json.dump(entradas, fh, ensure_ascii=False, indent=2)


def _chave(e):
    return (e.get("cnpj", ""), e.get("layout", ""), e.get("periodo", ""))


# -------------------------------------------------------------- operações
def arquivar(doc, caminho_origem=None, motivo="abertura"):
    """Copia o arquivo para a pasta interna e atualiza o índice.

    Devolve a entrada do índice, ou None quando não há como identificar a
    empresa (sem CNPJ no 0000) ou o arquivo de origem não existe.
    """
    origem = caminho_origem or getattr(doc, "caminho", "")
    if not origem or not os.path.isfile(origem):
        return None
    cnpj, nome, layout, periodo = identificar(doc)
    if not cnpj:
        return None

    destino = caminho_copia(cnpj, layout, periodo)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    # se a origem já é a própria cópia (arquivo aberto do histórico), não há
    # o que copiar — copyfile com origem == destino truncaria o arquivo
    if os.path.abspath(origem) != os.path.abspath(destino):
        shutil.copyfile(origem, destino)

    entradas = [e for e in carregar_indice()
                if _chave(e) != (cnpj, layout, periodo)]
    entrada = {
        "cnpj": cnpj,
        "nome": nome,
        "layout": layout,
        "periodo": periodo,
        "arquivo": os.path.relpath(destino, _base()).replace("\\", "/"),
        "origem": os.path.abspath(origem),
        "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": motivo,
        "tamanho": os.path.getsize(destino),
        "registros": len(getattr(doc, "registros", []) or []),
    }
    entradas.append(entrada)
    _salvar_indice(entradas)
    return entrada


def historico(cnpj=None):
    """Entradas do histórico, mais recentes primeiro. Filtra por CNPJ."""
    entradas = carregar_indice()
    if cnpj:
        alvo = so_digitos(cnpj)
        entradas = [e for e in entradas if e.get("cnpj") == alvo]
    entradas.sort(key=lambda e: (e.get("periodo", ""),
                                 e.get("atualizado_em", "")), reverse=True)
    for e in entradas:
        e["caminho"] = os.path.join(_base(), e.get("arquivo", ""))
        e["existe"] = os.path.isfile(e["caminho"])
    return entradas


def empresas_no_historico():
    """{cnpj: nome} das empresas que já têm arquivo arquivado."""
    mapa = {}
    for e in carregar_indice():
        cnpj = e.get("cnpj")
        if cnpj:
            mapa.setdefault(cnpj, e.get("nome", ""))
    return mapa


def remover(cnpj, layout, periodo, apagar_arquivo=True):
    """Tira o período do histórico (e apaga a cópia, por padrão)."""
    alvo = (so_digitos(cnpj), layout, periodo)
    restantes, removidas = [], []
    for e in carregar_indice():
        (removidas if _chave(e) == alvo else restantes).append(e)
    if not removidas:
        return 0
    if apagar_arquivo:
        for e in removidas:
            cam = os.path.join(_base(), e.get("arquivo", ""))
            try:
                if os.path.isfile(cam):
                    os.remove(cam)
            except OSError:
                pass
    _salvar_indice(restantes)
    return len(removidas)


def formatar_periodo(periodo):
    """202608 -> 08/2026."""
    p = so_digitos(periodo)
    return "%s/%s" % (p[4:], p[:4]) if len(p) == 6 else (periodo or "")

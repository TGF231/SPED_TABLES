# -*- coding: utf-8 -*-
"""Leitura do banco embutido do PVA: que arquivo virou qual escrituração e
o que a validação acusou.

Cada escrituração importada vira um banco `mysql/data/bd<AAAAMMDDhhmmss>`
na pasta do PVA, com uma tabela `inconsistencia` preenchida pela validação
(`ID_MENSAGEM`, `ID_CAMPO`, `VALOR_CAMPO`, `NOME_REGISTRO`,
`CONTEUDO_LINHA`, `NUMERO_LINHA`…). O `master/escrituracao` (EFD
Contribuições) ou `master/escrituracaofiscal` (EFD ICMS/IPI) liga cada banco
ao CNPJ e ao **caminho do arquivo** importado.

As tabelas são MyISAM e ficam legíveis em disco sem subir o servidor; aqui
só se **lê**, e só o necessário: o identificador de cada mensagem (sempre
`MSG_…`) e, quando dá para reconhecer, o registro. É o que basta para
comparar "erros antes × depois" de uma correção — o texto das mensagens
fica no PVA.
"""

import os
import re
from collections import Counter

from sped_tables.infra import config

MASTER = {"ICMS": "escrituracaofiscal.MYD", "CONTRIB": "escrituracao.MYD"}

_RE_BD = re.compile(rb"bd(\d{14})")
_RE_CNPJ = re.compile(rb"(\d{14})")
_RE_CAMINHO = re.compile(rb"[A-Za-z]:[\\/][^\x00-\x1f(]+?\.txt", re.I)
_RE_MSG = re.compile(rb"MSG_[A-Z0-9_]+")
# registro: 4 caracteres com prefixo de tamanho, seguidos da linha do arquivo
# que começa por |REG|
_RE_MSG_REG = re.compile(rb"(MSG_[A-Z0-9_]+)((?:(?!MSG_).){0,600}?)"
                         rb"\x04([0-9A-Z]{4}).{1,2}\|\3\|", re.S)


def pasta_dados(layout, raiz=None):
    pasta = config.pasta_pva(layout, raiz)
    return os.path.join(pasta, "mysql", "data") if pasta else None


def bancos(layout, raiz=None):
    """Nomes dos bancos de escrituração (`bd…`), do mais antigo ao novo."""
    pasta = pasta_dados(layout, raiz)
    if not pasta or not os.path.isdir(pasta):
        return []
    return sorted(n for n in os.listdir(pasta)
                  if n.startswith("bd") and os.path.isdir(
                      os.path.join(pasta, n)))


def escrituracoes(layout, raiz=None):
    """`[{"bd", "cnpj", "caminho"}]` do master, na ordem em que aparecem.

    Leitura por padrão, não por esquema: o registro dinâmico do MyISAM
    guarda os textos com prefixo de tamanho, e o que interessa (CNPJ, nome
    do banco, caminho do `.txt`) tem forma inconfundível.
    """
    pasta = pasta_dados(layout, raiz)
    if not pasta:
        return []
    cam = os.path.join(pasta, "master", MASTER[layout])
    try:
        with open(cam, "rb") as fh:
            dados = fh.read()
    except OSError:
        return []
    saida = []
    marcas = list(_RE_BD.finditer(dados))
    for i, m in enumerate(marcas):
        antes = dados[max(0, m.start() - 40):m.start()]
        cnpjs = _RE_CNPJ.findall(antes)
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(dados)
        caminho = _RE_CAMINHO.search(dados, m.end(), fim)
        saida.append({
            "bd": "bd" + m.group(1).decode(),
            "cnpj": cnpjs[-1].decode() if cnpjs else "",
            "caminho": (caminho.group(0).decode("latin-1")
                        if caminho else ""),
        })
    return saida


def banco_do_arquivo(layout, caminho, raiz=None):
    """O banco mais recente em que `caminho` foi importado, ou None.

    Melhor esforço: linha do master que foi atualizada fica partida em
    blocos no MyISAM, e o caminho pode não ser reconhecível. Quem importa e
    quer o banco certo compara `bancos()` antes e depois.
    """
    alvo = os.path.normcase(os.path.abspath(caminho)).replace("\\", "/")
    achado = None
    for e in escrituracoes(layout, raiz):
        cam = os.path.normcase(e["caminho"]).replace("\\", "/")
        if cam and cam == alvo:
            achado = e["bd"] if achado is None else max(achado, e["bd"])
    return achado


def inconsistencias(layout, bd, raiz=None):
    """`Counter({(mensagem, registro): quantidade})` do que a validação
    gravou no banco `bd`. Registro que não deu para reconhecer vem `""`.

    Devolve None quando o banco não existe (ainda não validado, por exemplo)
    — diferente de um `Counter()` vazio, que é validação sem erro.
    """
    pasta = pasta_dados(layout, raiz)
    cam = os.path.join(pasta or "", bd, "inconsistencia.MYD")
    try:
        with open(cam, "rb") as fh:
            dados = fh.read()
    except OSError:
        return None
    contagem = Counter()
    vistos = set()
    for m in _RE_MSG_REG.finditer(dados):
        contagem[(m.group(1).decode(), m.group(3).decode())] += 1
        vistos.add(m.start(1))
    for m in _RE_MSG.finditer(dados):
        if m.start() not in vistos:
            contagem[(m.group(0).decode(), "")] += 1
    return contagem


def por_mensagem(contagem):
    """Soma um `inconsistencias()` por mensagem, sem o registro."""
    saida = Counter()
    for (msg, _reg), n in (contagem or {}).items():
        saida[msg] += n
    return saida

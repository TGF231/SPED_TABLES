# -*- coding: utf-8 -*-
"""Trabalho repartido entre processos: muitos arquivos de uma vez.

Medido com 5.000 NFC-e (10 KB cada) num processador de 16 núcleos:

    ==========  ================  =========
    modo        primeira leitura  com cache
    ==========  ================  =========
    um por vez  24,7 s            2,5 s
    threads     4,3 s             2,7 s
    processos   4,2 s             0,8 s
    ==========  ================  =========

Na primeira leitura o tempo é espera — de disco e do antivírus, que examina
cada arquivo ao abrir —, e threads já resolvem. Com cache, o tempo é a
análise do XML, que no Python só processos dividem (o GIL serializa as
threads). Por isso processos, com threads de reserva: se o sistema não
deixar subir processos, o trabalho continua, mais devagar, em vez de parar.

A função que vai para os processos precisa ser **de módulo** — o processo
filho a encontra pelo nome — e o que ela devolve atravessa por `pickle`.
No executável, o lançador chama `multiprocessing.freeze_support()` antes de
qualquer outro import: o processo filho é o próprio executável.
"""

import concurrent.futures as cf
import logging
import os
from concurrent.futures.process import BrokenProcessPool

from sped_tables.infra import config

log = logging.getLogger(__name__)

PEDACO = 64              # itens por tarefa: menos e o envio entre processos pesa
MINIMO_PROCESSOS = 256   # abaixo disso, subir processos custa mais do que rende
MAXIMO = 16              # mais que isso não rendeu nada na medição


class Cancelado(Exception):
    """A pessoa cancelou no meio; o que já tinha sido feito é descartado."""


def trabalhadores():
    """Quantos processos: `trabalhadores` no `configuracao.json` (0 ou
    ausente = automático: um a menos que os núcleos, para a janela continuar
    respondendo, até `MAXIMO`)."""
    try:
        pedido = int(config.ler().get("trabalhadores") or 0)
    except (TypeError, ValueError):
        pedido = 0
    if pedido > 0:
        return min(pedido, 61)          # teto do Windows para processos
    return max(1, min((os.cpu_count() or 2) - 1, MAXIMO))


def em_lotes(fn, itens, progresso=None, cancelar=None, pedaco=PEDACO):
    """`fn(lista) -> lista` aplicada a pedaços de `itens` em paralelo; devolve
    a concatenação **na ordem de `itens`**, como se fosse `fn(itens)`.

    `progresso(feitos, total)` e `cancelar()` são chamados na thread de quem
    chamou, a cada pedaço concluído; `cancelar()` verdadeiro levanta
    `Cancelado`. Erro dentro de `fn` sobe como veio."""
    itens = list(itens)
    total = len(itens)
    if not total:
        return []
    pedacos = [itens[i:i + pedaco] for i in range(0, total, pedaco)]
    n = min(trabalhadores(), len(pedacos))
    if n <= 1:
        return _em_serie(fn, pedacos, total, progresso, cancelar)
    if total >= MINIMO_PROCESSOS:
        try:
            with cf.ProcessPoolExecutor(n) as ex:
                return _distribuir(ex, fn, pedacos, total, progresso, cancelar)
        except (BrokenProcessPool, OSError) as exc:
            log.warning("processos indisponíveis (%s); seguindo com threads",
                        exc)
    with cf.ThreadPoolExecutor(n) as ex:
        return _distribuir(ex, fn, pedacos, total, progresso, cancelar)


def _em_serie(fn, pedacos, total, progresso, cancelar):
    saida, feitos = [], 0
    for p in pedacos:
        _conferir(cancelar)
        saida += fn(p)
        feitos += len(p)
        if progresso:
            progresso(feitos, total)
    return saida


def _distribuir(ex, fn, pedacos, total, progresso, cancelar):
    futuros = {ex.submit(fn, p): i for i, p in enumerate(pedacos)}
    resultados = [None] * len(pedacos)
    feitos = 0
    try:
        for f in cf.as_completed(futuros):
            i = futuros[f]
            resultados[i] = f.result()
            feitos += len(pedacos[i])
            if progresso:
                progresso(feitos, total)
            _conferir(cancelar)
    except BaseException:
        # o `with` do executor espera o que já está rodando; o resto não começa
        for f in futuros:
            f.cancel()
        raise
    return [x for r in resultados for x in r]


def _conferir(cancelar):
    if cancelar and cancelar():
        raise Cancelado()

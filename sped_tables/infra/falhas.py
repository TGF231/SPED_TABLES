# -*- coding: utf-8 -*-
"""Rede de proteção para o que ninguém previu.

O PyQt6 **encerra o processo** quando uma exceção escapa de um slot e o
`sys.excepthook` é o padrão. Foi isso que transformou um `TypeError` no
resumo da tela de validação em "o programa fecha sozinho" durante três
versões. Este módulo troca o encerramento por quatro coisas:

1. **registro** — o traceback completo vai para `logs/sped_tables.log` na
   pasta de dados (com rodízio, para não crescer sem fim);
2. **cópia de emergência** — se havia alteração não salva, o documento é
   gravado em `recuperacao/` antes de qualquer outra coisa;
3. **aviso** — uma caixa diz o que aconteceu, onde está o registro e onde
   ficou a cópia; o programa continua aberto;
4. **falha nativa** — `faulthandler` grava o rastro das quedas que não são
   exceção Python (Win32, ctypes, barra de título), que antes morriam sem
   deixar nada.

A parte de registro não depende do Qt; a caixa de aviso é importada só
quando o gancho é instalado pela interface.
"""

import datetime
import faulthandler
import logging
import logging.handlers
import os
import sys
import threading
import traceback

from sped_tables.infra import dados

NOME_LOG = "sped_tables.log"
NOME_NATIVO = "falhas_nativas.log"
PASTA_LOG = "logs"
PASTA_RECUPERACAO = "recuperacao"

log = logging.getLogger("sped_tables")

_estado = {"configurado": False, "nativo": None, "mostrando": False,
           "salvar_emergencia": None, "avisar": None}


# ------------------------------------------------------------------ registro
def pasta_logs():
    caminho = os.path.join(dados.pasta_dados(), PASTA_LOG)
    os.makedirs(caminho, exist_ok=True)
    return caminho


def caminho_log():
    return os.path.join(pasta_logs(), NOME_LOG)


def configurar_registro(nivel=logging.INFO):
    """Liga o registro em arquivo. Pode ser chamada mais de uma vez."""
    if _estado["configurado"]:
        return log
    try:
        manipulador = logging.handlers.RotatingFileHandler(
            caminho_log(), maxBytes=1_000_000, backupCount=5,
            encoding="utf-8")
    except OSError:
        manipulador = logging.StreamHandler()
    manipulador.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    log.addHandler(manipulador)
    log.setLevel(nivel)
    log.propagate = False
    _estado["configurado"] = True
    return log


def ativar_falha_nativa():
    """Grava o rastro das quedas nativas (acesso inválido, abort do Qt)."""
    if _estado["nativo"] is not None:
        return
    try:
        fh = open(os.path.join(pasta_logs(), NOME_NATIVO), "a",
                  encoding="utf-8")
        fh.write("\n=== sessão iniciada em %s ===\n"
                 % datetime.datetime.now().isoformat(timespec="seconds"))
        fh.flush()
        faulthandler.enable(file=fh, all_threads=True)
        _estado["nativo"] = fh             # precisa ficar aberto
    except (OSError, RuntimeError, ValueError):
        pass


def texto_do_erro(tipo, valor, tb):
    return "".join(traceback.format_exception(tipo, valor, tb))


# ------------------------------------------------------ cópia de emergência
def caminho_recuperacao(nome_original):
    pasta = os.path.join(dados.pasta_dados(), PASTA_RECUPERACAO)
    os.makedirs(pasta, exist_ok=True)
    base = os.path.splitext(os.path.basename(nome_original or "sped"))[0]
    carimbo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(pasta, "%s_%s.txt" % (base, carimbo))


def gravar_emergencia(doc, nome_original=None):
    """Grava uma cópia do documento na pasta de recuperação.

    Nunca sobrescreve o arquivo do usuário: o estado da memória pode estar
    inconsistente justamente por causa do erro, e decidir se a cópia presta
    é com ele. Devolve o caminho, ou None se não deu para gravar.
    """
    try:
        destino = caminho_recuperacao(nome_original or doc.caminho)
        texto = doc.gerar_texto()
        with open(destino, "wb") as fh:
            fh.write(texto.encode(doc.encoding, errors="replace"))
        return destino
    except Exception:                                       # noqa: BLE001
        log.exception("a cópia de emergência também falhou")
        return None


# ------------------------------------------------------------------ ganchos
def tratar(tipo, valor, tb, origem="interface"):
    """O que fazer com uma exceção que ninguém tratou."""
    if issubclass(tipo, KeyboardInterrupt):
        sys.__excepthook__(tipo, valor, tb)
        return
    detalhe = texto_do_erro(tipo, valor, tb)
    log.error("exceção não tratada (%s):\n%s", origem, detalhe)

    copia = None
    salvar = _estado["salvar_emergencia"]
    if salvar is not None:
        try:
            copia = salvar()
        except Exception:                                   # noqa: BLE001
            log.exception("falha ao preparar a cópia de emergência")
    if copia:
        log.warning("cópia de emergência gravada em %s", copia)

    avisar = _estado["avisar"]
    if avisar is None or _estado["mostrando"]:
        # sem interface (ou já há um aviso na tela): registro basta — mostrar
        # outra caixa dentro da primeira empilharia avisos sem fim
        if avisar is None:
            sys.__excepthook__(tipo, valor, tb)
        return
    _estado["mostrando"] = True
    try:
        avisar(tipo, valor, detalhe, copia)
    except Exception:                                       # noqa: BLE001
        log.exception("falha ao exibir o aviso de erro")
    finally:
        _estado["mostrando"] = False


def _gancho_thread(args):
    if args.exc_type is SystemExit:
        return
    log.error("exceção não tratada na thread %s:\n%s",
              getattr(args.thread, "name", "?"),
              texto_do_erro(args.exc_type, args.exc_value,
                            args.exc_traceback))


def _gancho_nao_levantavel(args):
    log.warning("exceção ignorada (%s):\n%s", args.err_msg or "",
                texto_do_erro(args.exc_type, args.exc_value,
                              args.exc_traceback))


def instalar(avisar=None, salvar_emergencia=None):
    """Liga tudo. `avisar(tipo, valor, detalhe, copia)` mostra o erro ao
    usuário; `salvar_emergencia()` devolve o caminho da cópia (ou None)."""
    configurar_registro()
    ativar_falha_nativa()
    _estado["avisar"] = avisar
    _estado["salvar_emergencia"] = salvar_emergencia
    sys.excepthook = tratar
    threading.excepthook = _gancho_thread
    sys.unraisablehook = _gancho_nao_levantavel
    log.info("sessão iniciada")


def definir_salvar_emergencia(funcao):
    _estado["salvar_emergencia"] = funcao

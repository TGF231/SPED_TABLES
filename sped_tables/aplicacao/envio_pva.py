# -*- coding: utf-8 -*-
"""Caso de uso: mandar o arquivo salvo ao PVA — importar e validar.

A automação da janela do PVA é da infraestrutura (`infra.pva`); o que fica
aqui é a decisão em volta dela, que antes estava misturada com a tela:

* **pré-checagem** — o PVA recusa a importação inteira por erro de
  estrutura, e só diz isso depois de abrir, importar e falhar. O diagnóstico
  já conhece esses campos (`diagnostico.impedem_importacao`), então a
  pergunta vem antes;
* **desfecho** — cada estado devolvido por `pva.abrir` pede uma forma de
  mostrar: só a barra de status (deu certo, ou o usuário cancelou), uma
  caixa informativa (falta um passo manual) ou um alerta (o PVA recusou).
"""

import os

from sped_tables.dominio import diagnostico
from sped_tables.infra import config
from sped_tables.infra import pva

# como apresentar cada estado de `pva.abrir`
STATUS = "status"          # barra de status basta
INFORMAR = "informar"      # caixa informativa: há um passo manual
ALERTAR = "alertar"        # caixa de alerta: não deu certo

DESFECHOS = {
    "validando": STATUS, "importado": STATUS, "importando": STATUS,
    "cancelado": STATUS,
    "caminho_colado": INFORMAR, "pva_aberto": INFORMAR,
    "pva_ocupado": INFORMAR, "confirmar": INFORMAR,
}


def instalacao(layout):
    """`{exe, pasta, titulo, nome}` do PVA do leiaute, ou None."""
    return pva.instalacao(layout)


def onde_procurei():
    return config.raiz_pva()


def problema_do_arquivo(caminho):
    """Texto do que impede o envio (arquivo não salvo), ou `""`."""
    if not caminho or not os.path.isfile(caminho):
        return "Salve o arquivo antes de mandá-lo para o PVA."
    return ""


def _aviso_sem_leiaute(info):
    """O que a pré-checagem não conferiu, quando o diagnóstico rodou sem a
    estrutura do leiaute do arquivo: os achados que o PVA recusa na
    importação (tipo, tamanho, domínio, quantidade de campos) vêm todos dela,
    e sem ela a lista vazia não quer dizer "nada a recusar". `""` quando a
    estrutura valeu."""
    if info.get("fora_da_base") and info.get("mais_nova_que_a_base"):
        base = " (%s)" % info["base"] if info.get("base") else ""
        return ("A versão %s do leiaute deste arquivo é mais nova que a base "
                "de referência em uso%s: a conferência prévia pelo leiaute "
                "não rodou. Para conferir antes de abrir o PVA, importe uma "
                "base mais nova em Configurações → Base de referência…"
                % (info["fora_da_base"], base))
    if info.get("fora_da_base"):
        return ("A versão %s do leiaute deste arquivo não está na base de "
                "referência (ela guarda os últimos 5 anos): a conferência "
                "prévia pelo leiaute não rodou." % info["fora_da_base"])
    if info.get("sem_base"):
        return ("A base de referência está indisponível: a conferência "
                "prévia pelo leiaute não rodou.")
    return ""


def pre_checagem_com_aviso(doc):
    """`([(tipo, quantidade)], aviso)`: o que o PVA recusaria já na
    importação e, à parte, o aviso de que a conferência **não rodou** pelo
    leiaute (`""` quando rodou). O aviso não impede nada — o PVA valida de
    qualquer jeito —, só evita que a lista vazia soe como aprovação.

    Nunca levanta: se o diagnóstico falhar, o envio segue — a pré-checagem
    é para poupar uma volta, não para impedir o usuário de tentar.
    """
    try:
        achados, info = diagnostico.verificar(doc)
        return (diagnostico.impedem_importacao(achados),
                _aviso_sem_leiaute(info))
    except Exception:                                       # noqa: BLE001
        return [], ""


def pre_checagem(doc):
    """`[(tipo, quantidade)]` do que o PVA recusaria já na importação."""
    return pre_checagem_com_aviso(doc)[0]


def enviar(caminho, layout, progresso=None, cancelar=None):
    """Roda a automação (bloqueia — chame fora da thread da interface).
    Devolve o dicionário de `pva.abrir`; exceção vira estado `erro`."""
    try:
        return pva.abrir(caminho, layout, progresso=progresso,
                         cancelar=cancelar)
    except Exception as exc:                                # noqa: BLE001
        return {"estado": "erro", "mensagem": str(exc)}


def desfecho(resultado):
    """`(forma, mensagem)` para apresentar o resultado de `enviar`."""
    estado = (resultado or {}).get("estado")
    msg = (resultado or {}).get("mensagem", "")
    forma = DESFECHOS.get(estado, ALERTAR)
    if forma == ALERTAR and not msg:
        msg = "Não foi possível abrir o PVA."
    return forma, msg

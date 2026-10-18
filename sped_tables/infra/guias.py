# -*- coding: utf-8 -*-
"""Os **guias práticos** da EFD ICMS/IPI e da EFD Contribuições, extraídos
para `base/guias/` por `py -m consolidador guia`.

São o texto oficial de cada registro e de cada campo — "Preenchimento",
"Validação", "Valores válidos" —, que o programa mostra como ajuda e cita
quando acusa uma regra. O PVA diz *se* o arquivo passa; o guia diz *por
quê*.
"""

import json
import logging
import os

from sped_tables.infra import dados

log = logging.getLogger("sped_tables")

ARQUIVOS = {"ICMS": "ICMS.json", "CONTRIB": "CONTRIB.json"}


def caminho(layout):
    return dados.recurso(os.path.join("base", "guias", ARQUIVOS[layout]))


def carregar(layout):
    """O guia do leiaute, ou `{}` quando o arquivo não viajou com o
    programa — a ajuda some, nada mais."""
    if layout not in ARQUIVOS:
        return {}
    try:
        with open(caminho(layout), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        log.warning("guia prático de %s indisponível", layout)
        return {}

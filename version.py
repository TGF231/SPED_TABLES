# -*- coding: utf-8 -*-
"""Versão central do aplicativo.

Esquema: Semantic Versioning (https://semver.org) — MAJOR.MINOR.PATCH
  * MAJOR: mudanças incompatíveis (ex.: formato de projeto que quebra o anterior)
  * MINOR: novas funcionalidades compatíveis com as anteriores
  * PATCH: correções compatíveis

Enquanto MAJOR for 0, a API/UI ainda é considerada em evolução (0.y.z).
"""

__version__ = "0.14.0"
APP_NAME = "SPED Tables"


def titulo_completo():
    return "%s v%s" % (APP_NAME, __version__)

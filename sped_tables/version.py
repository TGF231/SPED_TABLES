# -*- coding: utf-8 -*-
"""Versão central do aplicativo.

Esquema: Semantic Versioning (https://semver.org) — MAJOR.MINOR.PATCH
  * MAJOR: mudanças incompatíveis (ex.: formato de projeto que quebra o anterior)
  * MINOR: novas funcionalidades compatíveis com as anteriores
  * PATCH: correções compatíveis

Enquanto MAJOR for 0, a API/UI ainda é considerada em evolução (0.y.z).

**A versão declara o canal** (ver ROADMAP.md). Sufixo de pré-release SemVer
— `1.1.0-dev.3`, `1.1.0-alpha.1`, `1.1.0-beta.2`, `1.1.0-rc.1` — é versão de
desenvolvimento; sem sufixo e com MAJOR ≥ 1 é **release**, e numa release só
aparece o que cumpriu o critério de aceite (`acoes.Acao.pronta`). Toda a
série 0.y.z é desenvolvimento.
"""

import re

__version__ = "1.1.0-dev.2"
APP_NAME = "SPED Tables"

CANAIS = ("dev", "alpha", "beta", "rc")


def canal(versao=None):
    """`"release"`, `"dev"`, `"alpha"`, `"beta"` ou `"rc"`.

    Versão 0.y.z sem sufixo conta como `"dev"`: antes da 1.0.0 nada é
    release. Sufixo desconhecido (`-nightly`, `-preview`…) também é
    desenvolvimento — na dúvida, nunca release.
    """
    versao = versao or __version__
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$", versao)
    if not m:
        return "dev"
    if m.group(4):
        rotulo = m.group(4).split(".")[0].lower()
        return rotulo if rotulo in CANAIS else "dev"
    return "release" if int(m.group(1)) >= 1 else "dev"


def e_release(versao=None):
    return canal(versao) == "release"

# -*- coding: utf-8 -*-
"""SPED Tables — editor de arquivos SPED (EFD ICMS/IPI e EFD Contribuições).

O pacote é dividido em camadas; ver ARQUITETURA.md na raiz do projeto.
"""

import os

from sped_tables.version import APP_NAME, __version__  # noqa: F401

# raiz do projeto (a pasta que contém este pacote). Rodando do código-fonte,
# é onde ficam os dados do usuário e os recursos (ícone, correlações).
RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -*- coding: utf-8 -*-
"""Suíte de testes do SPED Tables.

Rodar da raiz do projeto, com o interpretador que tem o PyQt6:

    py -m unittest discover -s tests -t .

(ou `py -m pytest tests`, se o pytest estiver instalado — os testes são
`unittest` puro e o pytest os roda sem adaptação.)

Nada aqui depende de arquivo de cliente: os SPED de teste são montados pela
`fabrica`. Os testes contra arquivos reais ficam em `test_reais.py` e só rodam
quando `SPED_TABLES_ARQUIVOS_REAIS` aponta para uma pasta com eles — e essa
pasta nunca entra no git.
"""

import os
import sys
import tempfile

# a interface roda sem tela; precisa estar definido antes de o Qt carregar
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# cadastro de empresas e cópias de SPED que os testes gerarem vão para uma
# pasta temporária, nunca para a pasta de dados de verdade
if not os.environ.get("SPED_TABLES_DADOS"):
    os.environ["SPED_TABLES_DADOS"] = tempfile.mkdtemp(prefix="sped_dados_")

# a saída dos testes tem acento; o console do Windows não é UTF-8 por padrão
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

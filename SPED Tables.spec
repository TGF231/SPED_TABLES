# -*- mode: python ; coding: utf-8 -*-
"""Empacotamento do SPED Tables (PyInstaller, arquivo único).

O que precisa viajar junto com o executável e não é código:

* **Tradução pt-BR do Qt** (`qtbase_pt_BR.qm`). Sem ela, os botões dos
  diálogos voltam ao inglês ("Save", "Discard", "Cancel") — o PyInstaller não
  a inclui sozinho. Vai para a pasta `traducoes/` do pacote, onde
  `sped_tables.interface.app.instalar_traducao()` procura antes do caminho
  do sistema.
  O `qt_pt_BR.qm` **não** é empacotado de propósito: ele é um meta-catálogo que
  só carrega se os `.qm` irmãos (qtdeclarative, qtmultimedia…) estiverem na
  mesma pasta. É o `qtbase` que traz as strings de diálogo.
* **`icon.ico`**, que além de ícone do executável é carregado em tempo de
  execução pela barra de título própria e pelo `setWindowIcon`.
* **`correlacoes_cfop.json`**, o conjunto inicial de correlações CFOP
  saída→entrada. Na primeira execução, `dados.instalar()` copia daqui para
  `%APPDATA%\SPED Tables` o que ainda não existir lá — os dados do usuário
  **nunca** ficam junto do executável, porque no modo onefile essa pasta é
  temporária e some ao sair.

Gerar com:  pyinstaller "SPED Tables.spec"
"""

import os

import PyQt6

# ------------------------------------------------- traduções do próprio Qt
_traducoes_qt = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6",
                             "translations")
_qm = [
    (os.path.join(_traducoes_qt, nome), "traducoes")
    for nome in ("qtbase_pt_BR.qm",)
    if os.path.isfile(os.path.join(_traducoes_qt, nome))
]
if not _qm:
    # falhar aqui é melhor que descobrir o inglês só depois de distribuir
    raise SystemExit(
        "qtbase_pt_BR.qm não encontrado em %s — o executável sairia com os "
        "diálogos em inglês." % _traducoes_qt)

_recursos = [("icon.ico", ".")]
_opcionais = [("correlacoes_cfop.json", ".")]
_recursos += [(o, d) for o, d in _opcionais if os.path.isfile(o)]

a = Analysis(
    ['sped_editor.py'],
    pathex=[],
    binaries=[],
    datas=_qm + _recursos,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SPED Tables',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)

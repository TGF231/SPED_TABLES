# -*- mode: python ; coding: utf-8 -*-
r"""Empacotamento do SPED Tables (PyInstaller, arquivo único).

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
* **`recursos/base_referencia.db`**, a base de referência compilada de
  `base/` por `ferramentas/gerar_executavel.py`: leiaute de cada versão,
  tabelas oficiais e guias práticos. Sem ela as validações pelo leiaute se
  desligam.
* **`correlacoes_cfop.json`**, o conjunto inicial de correlações CFOP
  saída→entrada. Na primeira execução, `dados.instalar()` copia daqui para
  `%APPDATA%\SPED Tables` o que ainda não existir lá — os dados do usuário
  **nunca** ficam junto do executável, porque no modo onefile essa pasta é
  temporária e some ao sair.

**Só o que o programa usa.** Gere pelo ambiente mínimo do uv
(`ferramentas/gerar_executavel.py`, com `requirements-executavel.txt`): do
Python do sistema, o PyInstaller arrasta o que mais estiver instalado lá. E
mesmo no ambiente mínimo o gancho do PyQt6 junta o Qt inteiro que o pacote
traz; `_desnecessario()` tira o que este programa não carrega:

* `opengl32sw.dll` (20 MB, OpenGL por software — a interface é Widgets, que
  desenha sem OpenGL), `Qt6Pdf`, `Qt6Network`, `Qt6Svg` e os plugins que
  dependem deles;
* dos plugins, ficam só `platforms/qwindows`, `styles/qmodernwindowsstyle`
  e `imageformats/qico` (o ícone `.ico`; PNG o Qt lê sem plugin);
* as traduções do Qt em ~40 línguas: a pt-BR vai à parte, em `traducoes/`;
* do Python, o que nenhum caminho do programa usa: `ssl` (e o `libssl`),
  `_hashlib` (e o `libcrypto`: o SHA-1/SHA-256 do login do Firebird vem do
  próprio Python), `lzma`, `bz2` e `zstd` (o XLSX é zip com deflate).

O que saiu fica listado em `build/manifesto_executavel.txt`, com o tamanho,
para conferir a cada versão; o `--autoteste` do executável confere que o
que ficou basta.

Gerar com:  python ferramentas/gerar_executavel.py
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

_recursos = [("icon.ico", "."),
             # a base de referência compilada (gerar_executavel.py a gera
             # de base/ antes do PyInstaller): leiautes, tabelas e guias
             ("recursos/base_referencia.db", "recursos")]
_opcionais = [("correlacoes_cfop.json", ".")]
_recursos += [(o, d) for o, d in _opcionais if os.path.isfile(o)]

# módulos do Python e do PyQt6 que o programa não importa em caminho nenhum
_EXCLUIR = [
    "ssl", "_ssl", "_hashlib", "lzma", "_lzma", "bz2", "_bz2",
    "compression.zstd", "_zstd", "tkinter", "_tkinter", "unittest",
    "pydoc", "pydoc_data", "doctest", "lib2to3", "idlelib", "turtle",
    "turtledemo", "ensurepip", "venv", "curses", "_curses",
    "PyQt6.QtNetwork", "PyQt6.QtSvg", "PyQt6.QtPdf", "PyQt6.QtDBus",
    "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets", "PyQt6.QtPrintSupport",
    "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtMultimedia", "PyQt6.QtSql",
    "PyQt6.QtXml", "PyQt6.QtTest", "PyQt6.QtWebEngineCore",
]

# Qt: DLLs que nenhum módulo usado carrega, e os plugins que ficam
_QT_FORA = ("opengl32sw.dll", "d3dcompiler_47.dll", "qt6pdf", "qt6network",
            "qt6svg", "qt6qml", "qt6quick", "qt6opengl", "qt6dbus",
            "qt6virtualkeyboard")
_PLUGINS_FICAM = {"platforms/qwindows.dll",
                  "styles/qmodernwindowsstyle.dll",
                  "imageformats/qico.dll"}
_PYTHON_FORA = ("libssl-", "libcrypto-")


def _desnecessario(destino):
    d = destino.replace("\\", "/").lower()
    nome = d.rsplit("/", 1)[-1]
    if "/qt6/translations/" in d:
        return True
    if "/qt6/plugins/" in d:
        return d.split("/qt6/plugins/", 1)[1] not in _PLUGINS_FICAM
    if nome.startswith(_QT_FORA) or nome in _QT_FORA:
        return True
    return nome.startswith(_PYTHON_FORA)


a = Analysis(
    ['sped_editor.py'],
    pathex=[],
    binaries=[],
    datas=_qm + _recursos,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUIR,
    noarchive=False,
    optimize=0,
)
_fora = [t for t in a.binaries + a.datas if _desnecessario(t[0])]
a.binaries = [t for t in a.binaries if not _desnecessario(t[0])]
a.datas = [t for t in a.datas if not _desnecessario(t[0])]


def _manifesto():
    def tam(t):
        return os.path.getsize(t[1]) if os.path.isfile(t[1]) else 0
    ficam = sorted(a.binaries + a.datas, key=lambda t: -tam(t))
    linhas = ["# gerado pelo SPED Tables.spec — o que vai e o que saiu", "",
              "## ficam (%.1f MB)" % (sum(map(tam, ficam)) / 1e6)]
    linhas += ["%9.1f KB  %s" % (tam(t) / 1e3, t[0]) for t in ficam]
    linhas += ["", "## saíram (%.1f MB)" % (sum(map(tam, _fora)) / 1e6)]
    linhas += ["%9.1f KB  %s" % (tam(t) / 1e3, t[0])
               for t in sorted(_fora, key=lambda t: -tam(t))]
    os.makedirs("build", exist_ok=True)
    with open(os.path.join("build", "manifesto_executavel.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(linhas) + "\n")


_manifesto()
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
    upx=False,          # UPX corrompe plugin do Qt e dispara antivírus
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

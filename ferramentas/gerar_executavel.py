# -*- coding: utf-8 -*-
"""Gera o executável a partir de um ambiente mínimo e confere.

    python ferramentas/gerar_executavel.py [--recriar] [--sem-autoteste]

1. cria (ou reaproveita) `.venv-exe` com o Python do `.python-version`
   (pyenv) e instala, com o uv, **só** `requirements-executavel.txt` — do
   ambiente de desenvolvimento, o PyInstaller arrastaria tudo o que
   estivesse instalado lá;
2. compila a base de referência de `base/` para `recursos/base_referencia.db`
   — a que vai dentro do executável é sempre a de agora, nunca a que
   estiver por acaso em `recursos/`;
3. roda o PyInstaller com o `SPED Tables.spec`, que ainda tira do pacote as
   DLLs e os plugins do Qt que o programa não carrega
   (`build/manifesto_executavel.txt` lista o que ficou e o que saiu);
4. roda o `--autoteste` do executável numa pasta de dados temporária, sobre
   um SPED sintético — o pacote enxuto precisa continuar inteiro, inclusive
   a base de referência.

Precisa do pyenv (pyenv-win) e do `uv` no PATH.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(RAIZ, ".venv-exe")
PYTHON = os.path.join(VENV, "Scripts", "python.exe")
REQUISITOS = os.path.join(RAIZ, "requirements-executavel.txt")
EXE = os.path.join(RAIZ, "dist", "SPED Tables.exe")


def _rodar(*cmd, **k):
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=RAIZ, **k)


def _python_do_pyenv():
    """O Python fixado no `.python-version` da raiz, instalado pelo pyenv.
    O `.venv-exe` só guarda o caminho dele: os pacotes do executável ficam
    no ambiente, nunca no Python do pyenv."""
    if shutil.which("pyenv") is None:
        raise SystemExit("O pyenv (pyenv-win) não está no PATH.")
    with open(os.path.join(RAIZ, ".python-version"), encoding="ascii") as fh:
        versao = fh.read().strip()
    r = subprocess.run(["pyenv", "which", "python"], capture_output=True,
                       text=True, cwd=RAIZ, shell=True)
    caminho = r.stdout.strip()
    if r.returncode != 0 or not os.path.isfile(caminho):
        raise SystemExit("O pyenv não tem o Python %s do .python-version "
                         "(instale com: pyenv install %s)." % (versao, versao))
    return caminho


def _ambiente_do_compilador():
    """Variáveis do compilador C do Visual Studio (vcvars64), ou None.

    O `pyodbc` ainda não publica pacote pronto para o Python 3.15 e é
    compilado na instalação; o setuptools não reconhece sozinho as
    Ferramentas de Build do Visual Studio 2026 ("Unable to find a
    compatible Visual Studio installation"). Com o ambiente do vcvars e
    `DISTUTILS_USE_SDK`, ele usa o compilador que já está no PATH."""
    vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                           "Microsoft Visual Studio", "Installer",
                           "vswhere.exe")
    if not os.path.isfile(vswhere):
        return None
    r = subprocess.run([vswhere, "-latest", "-products", "*", "-requires",
                        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                        "-property", "installationPath"],
                       capture_output=True, text=True)
    vcvars = os.path.join(r.stdout.strip(), "VC", "Auxiliary", "Build",
                          "vcvars64.bat")
    if r.returncode != 0 or not os.path.isfile(vcvars):
        return None
    # o `set` do cmd sai na página de código do console (cp850 aqui): o
    # padrão do Python 3.15 é UTF-8, e uma variável com acento derrubava a
    # leitura — o sync seguia sem compilador
    r = subprocess.run('"%s" >nul && set' % vcvars, shell=True,
                       capture_output=True, encoding="oem")
    if r.returncode != 0:
        return None
    amb = dict(linha.split("=", 1) for linha in r.stdout.splitlines()
               if "=" in linha)
    amb.update(DISTUTILS_USE_SDK="1", MSSdk="1")
    return amb


def _saudavel():
    """O `.venv-exe` existe **e** o Python de base dele ainda está lá.
    O ambiente guarda só o caminho do Python do pyenv (`pyvenv.cfg`): se esse
    Python sumir ou for reinstalado noutro lugar, o `python.exe` do
    ambiente continua no disco e falha ao rodar ("did not find executable
    at …")."""
    if not os.path.isfile(PYTHON):
        return False
    r = subprocess.run([PYTHON, "-c", "import sys"], capture_output=True)
    return r.returncode == 0


def ambiente(recriar=False):
    if shutil.which("uv") is None:
        raise SystemExit("O uv não está no PATH.")
    if os.path.isdir(VENV) and (recriar or not _saudavel()):
        print("recriando %s" % VENV, flush=True)
        shutil.rmtree(VENV)
    if not os.path.isfile(PYTHON):
        _rodar("uv", "venv", VENV, "--python", _python_do_pyenv())
    # sync: instala o que falta e **tira** o que não está na lista
    _rodar("uv", "pip", "sync", "--python", PYTHON, REQUISITOS,
           env=_ambiente_do_compilador())


def compilar_base():
    """A base de referência vai dentro do executável, compilada de base/
    agora — nunca a que estiver por acaso em recursos/."""
    sys.path.insert(0, RAIZ)
    from sped_tables.infra import base_referencia
    m = base_referencia.compilar(base_referencia.pasta_fontes(),
                                 base_referencia.caminho_embutido())
    tamanho = os.path.getsize(base_referencia.caminho_embutido()) / 1e6
    print("base de referência %s compilada (%.1f MB)"
          % (m["versao"], tamanho))


def empacotar():
    _rodar(PYTHON, "-m", "PyInstaller", "--noconfirm", "--clean",
           "SPED Tables.spec")
    print("executável: %.1f MB" % (os.path.getsize(EXE) / 1e6))


def autoteste():
    sys.path.insert(0, RAIZ)
    from tests.fabrica import contrib_basico
    pasta = tempfile.mkdtemp(prefix="sped_exe_")
    try:
        arq = contrib_basico().gravar(pasta)
        rel = os.path.join(pasta, "relatorio.json")
        amb = dict(os.environ, SPED_TABLES_DADOS=os.path.join(pasta, "dados"))
        # o pacote `tests` liga o Qt "offscreen" para a suíte; o executável
        # só leva o plugin do Windows, e com ele no ambiente nem abriria
        amb.pop("QT_QPA_PLATFORM", None)
        subprocess.run([EXE, "--autoteste", rel, arq], env=amb, timeout=300)
        with open(rel, encoding="utf-8") as fh:
            saida = json.load(fh)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    for item in saida["itens"]:
        print("  %s %s — %s" % ("ok   " if item["ok"] else "FALHA",
                                item["nome"], str(item["detalhe"])[:100]))
    if not saida["passou"]:
        raise SystemExit("O autoteste do executável falhou.")
    print("autoteste: passou (versão %s)" % saida["versao"])


if __name__ == "__main__":
    ambiente("--recriar" in sys.argv)
    compilar_base()
    empacotar()
    if "--sem-autoteste" not in sys.argv:
        autoteste()

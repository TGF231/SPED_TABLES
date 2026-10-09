# -*- coding: utf-8 -*-
"""Gera o executável a partir de um ambiente mínimo do uv e confere.

    py ferramentas/gerar_executavel.py [--recriar] [--sem-autoteste]

1. cria (ou reaproveita) `.venv-exe` com um Python do uv e instala **só**
   `requirements-executavel.txt` — do Python do sistema, o PyInstaller
   arrastava tudo o que estivesse instalado lá;
2. roda o PyInstaller com o `SPED Tables.spec`, que ainda tira do pacote as
   DLLs e os plugins do Qt que o programa não carrega
   (`build/manifesto_executavel.txt` lista o que ficou e o que saiu);
3. roda o `--autoteste` do executável numa pasta de dados temporária, sobre
   um SPED sintético — o pacote enxuto precisa continuar inteiro.

Precisa do `uv` no PATH (https://docs.astral.sh/uv/).
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
VERSAO_PYTHON = "3.14"


def _rodar(*cmd, **k):
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=RAIZ, **k)


def _uv_find():
    r = subprocess.run(["uv", "python", "find", "--managed-python",
                        VERSAO_PYTHON], capture_output=True, text=True,
                       cwd=RAIZ)
    caminho = r.stdout.strip()
    return caminho if r.returncode == 0 and os.path.isfile(caminho) else None


def _pasta_versionada():
    """A pasta `cpython-3.14.X-…` do uv, sem passar pelo atalho da versão
    menor (`cpython-3.14-…`), que já ficou inacessível para o próprio uv
    depois de uma instalação interrompida."""
    base = subprocess.run(["uv", "python", "dir"], capture_output=True,
                          text=True, check=True).stdout.strip()
    if not os.path.isdir(base):
        return None
    achados = [os.path.join(base, n, "python.exe") for n in os.listdir(base)
               if n.startswith("cpython-%s." % VERSAO_PYTHON)
               and "freethreaded" not in n]
    achados = [c for c in achados if os.path.isfile(c)]
    achados.sort(key=lambda c: [int(x) for x in os.path.basename(
        os.path.dirname(c)).split("-")[1].split(".")])
    return achados[-1] if achados else None


def _python_do_uv():
    """O executável do Python gerenciado pelo uv; instala se faltar."""
    caminho = _uv_find() or _pasta_versionada()
    if caminho:
        return caminho
    _rodar("uv", "python", "install", VERSAO_PYTHON)
    caminho = _uv_find() or _pasta_versionada()
    if not caminho:
        raise SystemExit("Não achei o Python %s do uv depois de instalar."
                         % VERSAO_PYTHON)
    return caminho


def _saudavel():
    """O `.venv-exe` existe **e** o Python de base dele ainda está lá.
    O ambiente guarda só o caminho do Python do uv (`pyvenv.cfg`): se esse
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
        _rodar("uv", "venv", VENV, "--python", _python_do_uv())
    # sync: instala o que falta e **tira** o que não está na lista
    _rodar("uv", "pip", "sync", "--python", PYTHON, REQUISITOS)


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
    empacotar()
    if "--sem-autoteste" not in sys.argv:
        autoteste()

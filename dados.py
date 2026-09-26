# -*- coding: utf-8 -*-
"""Onde o programa guarda o que é do usuário — e a instalação na primeira vez.

O problema que este módulo resolve: rodando do código-fonte, gravar ao lado do
módulo funciona. Num executável **onefile** do PyInstaller, o mesmo caminho
aponta para a pasta temporária de extração, **apagada ao sair** — o cadastro de
empresas e todo o histórico de arquivos se perderiam a cada fechamento, sem
nenhum erro visível.

Por isso o caminho depende de como o programa está rodando:

* **empacotado** → ``%APPDATA%\\SPED Tables`` (ou `~/.sped_tables` fora do
  Windows), que persiste entre execuções e sobrevive à atualização do
  executável;
* **do código-fonte** → a própria pasta do projeto, como sempre foi, para não
  espalhar arquivo de teste pelo perfil do usuário durante o desenvolvimento.

Sem dependência de GUI: a interface só chama `pasta_dados()` e
`criar_atalho_area_trabalho()`.
"""

import os
import shutil
import subprocess
import sys

from version import APP_NAME

# arquivos e pastas que são do usuário e vivem na pasta de dados
ITENS = ("empresas.json", "correlacoes_cfop.json", "config_tabelas_rfb.json",
         "arquivos")

MARCA_INSTALACAO = ".instalado"


def empacotado():
    """True quando rodando a partir do executável do PyInstaller."""
    return getattr(sys, "frozen", False)


def pasta_programa():
    """Pasta do executável (empacotado) ou do código-fonte."""
    if empacotado():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def pasta_dados(criar=True):
    """Pasta onde ficam cadastro, configurações e cópias dos SPED.

    `SPED_TABLES_DADOS` no ambiente tem precedência sobre tudo: é o que a
    suíte de testes usa para não gravar cadastro nem cópia de SPED na pasta
    do projeto, e serve a quem quiser os dados num disco de rede.
    """
    forcada = os.environ.get("SPED_TABLES_DADOS")
    if forcada:
        caminho = os.path.abspath(forcada)
    elif empacotado():
        if sys.platform == "win32":
            raiz = os.environ.get("APPDATA") or os.path.expanduser("~")
            caminho = os.path.join(raiz, APP_NAME)
        else:
            caminho = os.path.join(os.path.expanduser("~"), ".sped_tables")
    else:
        caminho = os.path.dirname(os.path.abspath(__file__))
    if criar:
        try:
            os.makedirs(caminho, exist_ok=True)
        except OSError:
            pass
    return caminho


def caminho(nome):
    """Caminho completo de um arquivo de dados do usuário."""
    return os.path.join(pasta_dados(), nome)


def primeira_execucao():
    """Ainda não há marca de instalação na pasta de dados?"""
    return not os.path.exists(os.path.join(pasta_dados(), MARCA_INSTALACAO))


def marcar_instalado():
    try:
        with open(os.path.join(pasta_dados(), MARCA_INSTALACAO), "w",
                  encoding="utf-8") as fh:
            fh.write("SPED Tables\n")
        return True
    except OSError:
        return False


def instalar(origem=None):
    """Prepara a pasta de dados na primeira execução.

    Copia para `%APPDATA%` o que veio junto do executável (as correlações de
    CFOP padrão, por exemplo) **sem sobrescrever** o que o usuário já tenha —
    atualizar o programa não pode apagar cadastro.

    Devolve a lista do que foi copiado.
    """
    destino = pasta_dados()
    if not empacotado() or os.path.abspath(origem or pasta_programa()) == \
            os.path.abspath(destino):
        return []
    base = origem or getattr(sys, "_MEIPASS", pasta_programa())
    copiados = []
    for nome in ITENS:
        alvo = os.path.join(destino, nome)
        if os.path.exists(alvo):
            continue                      # já é do usuário: não tocar
        fonte = os.path.join(base, nome)
        try:
            if os.path.isdir(fonte):
                shutil.copytree(fonte, alvo)
                copiados.append(nome)
            elif os.path.isfile(fonte):
                shutil.copyfile(fonte, alvo)
                copiados.append(nome)
        except OSError:
            pass
    return copiados


# ------------------------------------------------------------------ atalho
def _area_de_trabalho():
    """Caminho da área de trabalho, considerando redirecionamento do OneDrive."""
    candidatos = []
    perfil = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive:
        candidatos.append(os.path.join(onedrive, "Desktop"))
        candidatos.append(os.path.join(onedrive, "Área de Trabalho"))
    candidatos.append(os.path.join(perfil, "Desktop"))
    candidatos.append(os.path.join(perfil, "Área de Trabalho"))
    for c in candidatos:
        if os.path.isdir(c):
            return c
    return ""


def atalho_existe():
    mesa = _area_de_trabalho()
    return bool(mesa) and os.path.isfile(
        os.path.join(mesa, "%s.lnk" % APP_NAME))


def criar_atalho_area_trabalho():
    """Cria o atalho na área de trabalho. Devolve (ok, mensagem).

    Usa WScript.Shell pelo PowerShell em vez de pywin32: o executável não
    precisa carregar uma dependência inteira só para gravar um .lnk.
    """
    if sys.platform != "win32":
        return False, "Atalho na área de trabalho só no Windows."
    mesa = _area_de_trabalho()
    if not mesa:
        return False, "Não foi possível localizar a área de trabalho."

    link = os.path.join(mesa, "%s.lnk" % APP_NAME)
    if empacotado():
        destino, argumentos = sys.executable, ""
    else:
        script = os.path.join(pasta_programa(), "sped_editor.py")
        destino = sys.executable.replace("python.exe", "pythonw.exe")
        argumentos = '"%s"' % script

    def esc(t):
        return t.replace("'", "''")

    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s'); "
        "$s.TargetPath = '%s'; "
        "$s.Arguments = '%s'; "
        "$s.WorkingDirectory = '%s'; "
        "$s.Description = 'Editor de arquivos SPED'; "
        % (esc(link), esc(destino), esc(argumentos), esc(pasta_programa()))
    )
    icone = os.path.join(pasta_programa(), "icon.ico")
    if os.path.isfile(icone):
        ps += "$s.IconLocation = '%s'; " % esc(icone)
    ps += "$s.Save()"

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if r.returncode != 0 or not os.path.isfile(link):
        return False, (r.stderr or r.stdout or "").strip()[:300] \
            or "O Windows recusou a criação do atalho."
    return True, link

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

import datetime
import json
import logging
import os
import shutil
import subprocess
import sys

from sped_tables import RAIZ_PROJETO
from sped_tables.version import APP_NAME

# arquivos e pastas que são do usuário e vivem na pasta de dados
ITENS = ("empresas.json", "correlacoes_cfop.json",
         "arquivos")

MARCA_INSTALACAO = ".instalado"


def empacotado():
    """True quando rodando a partir do executável do PyInstaller."""
    return getattr(sys, "frozen", False)


def pasta_programa():
    """Pasta do executável (empacotado) ou a raiz do projeto (código-fonte).

    Não é a pasta deste módulo: desde a 0.53.0 ele mora dentro do pacote
    (`sped_tables/infra`), e os dados do usuário continuam na raiz.
    """
    if empacotado():
        return os.path.dirname(os.path.abspath(sys.executable))
    return RAIZ_PROJETO


def recurso(nome):
    """Arquivo que viaja com o programa (ícone, correlações padrão).

    Empacotado, fica na pasta de extração do PyInstaller; do código-fonte,
    na raiz do projeto.
    """
    base = getattr(sys, "_MEIPASS", None) if empacotado() else None
    return os.path.join(base or RAIZ_PROJETO, nome)


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
        caminho = RAIZ_PROJETO
    if criar:
        try:
            os.makedirs(caminho, exist_ok=True)
        except OSError:
            pass
    return caminho


def caminho(nome):
    """Caminho completo de um arquivo de dados do usuário."""
    return os.path.join(pasta_dados(), nome)


def gravar_atomico(caminho_destino, conteudo):
    """Grava `conteudo` (bytes) sem nunca deixar o destino pela metade.

    Escreve num `.tmp` ao lado e só então troca (`os.replace`, atômico no
    mesmo volume). Abrir o destino em modo `"w"` o trunca na hora: uma falha
    no meio — disco cheio, antivírus segurando o arquivo — deixava o
    cadastro de empresas ou o índice do acervo vazios.
    """
    pasta = os.path.dirname(os.path.abspath(caminho_destino))
    os.makedirs(pasta, exist_ok=True)
    temporario = "%s.tmp" % caminho_destino
    try:
        with open(temporario, "wb") as fh:
            fh.write(conteudo)
        os.replace(temporario, caminho_destino)
    except Exception:
        try:
            os.remove(temporario)
        except OSError:
            pass
        raise
    return caminho_destino


def gravar_json(caminho_destino, objeto):
    """JSON legível (UTF-8, indentado), gravado de forma atômica."""
    texto = json.dumps(objeto, ensure_ascii=False, indent=2)
    return gravar_atomico(caminho_destino, texto.encode("utf-8"))


# ------------------------------------------------- JSON do usuário ilegível
# Até a 0.55.0, cadastro, correlações, acervo e configuração ilegíveis viravam
# "vazio" sem aviso — e o próximo salvamento gravava por cima: bastava
# cadastrar uma empresa para o cadastro inteiro sumir. Agora o arquivo é
# guardado à parte e quem usa o programa é avisado.
_avisos = []
_ao_avisar = [None]


def ao_avisar(funcao):
    """Liga quem mostra os avisos (a interface) e entrega os pendentes."""
    _ao_avisar[0] = funcao
    while funcao is not None and _avisos:
        funcao(_avisos.pop(0))


def _avisar(texto):
    logging.getLogger("sped_tables").warning(texto)
    if _ao_avisar[0] is not None:
        _ao_avisar[0](texto)
    else:
        _avisos.append(texto)


def preservar_corrompido(caminho_arquivo, motivo):
    """Renomeia o arquivo ilegível para `<nome>.corrompido-<data>` — assim
    ele não é sobrescrito — e avisa. Devolve o novo caminho (ou None)."""
    base = "%s.corrompido-%s" % (
        caminho_arquivo, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    # dois no mesmo segundo não podem ter o mesmo nome: o segundo apagaria
    # o primeiro guardado
    destino, n = base, 1
    while os.path.exists(destino):
        n += 1
        destino = "%s-%d" % (base, n)
    try:
        os.replace(caminho_arquivo, destino)
    except OSError:
        destino = None
    _avisar("O arquivo %s está ilegível (%s). %s O programa segue sem ele."
            % (os.path.basename(caminho_arquivo), motivo,
               "Ele foi guardado como %s, sem nada apagado."
               % os.path.basename(destino) if destino
               else "Não foi possível guardá-lo à parte: não salve nada "
                    "desse tipo antes de recuperá-lo."))
    return destino


def ler_json_do_usuario(caminho_arquivo, tipo):
    """O conteúdo do JSON, ou None se o arquivo não existe. Arquivo que não
    é JSON — ou é JSON do tipo errado (uma lista onde se espera objeto) —
    é preservado e avisado (`preservar_corrompido`), e também dá None."""
    if not os.path.exists(caminho_arquivo):
        return None
    try:
        with open(caminho_arquivo, encoding="utf-8") as fh:
            conteudo = json.load(fh)
    except OSError:
        return None                    # sem acesso: não é corrupção
    except ValueError as exc:
        preservar_corrompido(caminho_arquivo, "não é JSON válido: %s" % exc)
        return None
    if not isinstance(conteudo, tipo):
        preservar_corrompido(
            caminho_arquivo, "esperava %s e encontrou %s"
            % ("uma lista" if tipo is list else "um objeto",
               type(conteudo).__name__))
        return None
    return conteudo


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

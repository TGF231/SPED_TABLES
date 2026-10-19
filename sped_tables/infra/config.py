# -*- coding: utf-8 -*-
"""Ponto único de configuração: onde estão os PVAs — que o programa só usa
para o *Abrir no PVA* (as tabelas e o leiaute vêm da base de referência).

Até a 0.51.0 o caminho `C:\\Arquivos de Programas RFB\\Programas SPED`
estava escrito em quatro módulos. PVA instalado noutro disco, ou noutra
pasta, desligava em silêncio metade das verificações — e trocar exigia
editar quatro arquivos.

Agora todo caminho do PVA sai daqui, decidido nesta ordem:

1. a variável de ambiente ``SPED_TABLES_PVA`` — quando definida, **é** a
   raiz, tenha PVA dentro ou não (é o que isola a suíte de testes da
   instalação da máquina);
2. ``raiz_pva`` no ``configuracao.json`` da pasta de dados (o que a
   interface grava quando o usuário escolhe a pasta);
3. a primeira pasta **existente** entre as conhecidas (a padrão da RFB,
   Arquivos de Programas e Arquivos de Programas (x86), em qualquer disco
   comum);
4. a padrão da RFB, mesmo inexistente — para a mensagem de "não encontrei"
   dizer onde procurou.

Onde ficam o descritor e as tabelas dentro de cada PVA é assunto do
consolidador (`consolidador.instalacao.SUBPASTAS`), que é quem os lê.
"""

import os

from sped_tables.infra import dados

VARIAVEL = "SPED_TABLES_PVA"
ARQUIVO = "configuracao.json"
RAIZ_PADRAO = r"C:\Arquivos de Programas RFB\Programas SPED"

# A pasta de cada PVA dentro da raiz.
PVAS = {
    "ICMS": {"pasta": "Fiscal"},
    "CONTRIB": {"pasta": "EFD-Contribuicoes"},
}

_cache = {}


# --------------------------------------------------------------- arquivo
def caminho_arquivo():
    return dados.caminho(ARQUIVO)


def ler():
    """Conteúdo do `configuracao.json` (vazio se ausente). Ilegível, é
    guardado à parte e avisado, e não é sobrescrito pelo próximo `gravar`."""
    return dados.ler_json_do_usuario(caminho_arquivo(), dict) or {}


def gravar(**valores):
    """Atualiza chaves do `configuracao.json` (gravação atômica)."""
    conteudo = ler()
    for chave, valor in valores.items():
        if valor in (None, ""):
            conteudo.pop(chave, None)
        else:
            conteudo[chave] = valor
    dados.gravar_json(caminho_arquivo(), conteudo)
    _cache.clear()
    return conteudo


# ------------------------------------------------------------------- PVA
def _tem_pva(raiz):
    return any(os.path.isdir(os.path.join(raiz, c["pasta"]))
               for c in PVAS.values())


def candidatos_raiz():
    """Raízes na ordem de preferência (explícitas primeiro)."""
    explicitas = [os.environ.get(VARIAVEL, ""), ler().get("raiz_pva", "")]
    conhecidas = [RAIZ_PADRAO]
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(var)
        if base:
            conhecidas.append(os.path.join(base, "Programas RFB",
                                           "Programas SPED"))
            conhecidas.append(os.path.join(base, "Arquivos de Programas RFB",
                                           "Programas SPED"))
    for disco in "DE":
        conhecidas.append("%s:\\Arquivos de Programas RFB\\Programas SPED"
                          % disco)
    vistos, saida = set(), []
    for c in explicitas + conhecidas:
        c = (c or "").strip()
        if c and c.lower() not in vistos:
            vistos.add(c.lower())
            saida.append(c)
    return saida


def raiz_pva():
    """Raiz das instalações dos PVAs (ver a ordem no topo do módulo)."""
    if "raiz" not in _cache:
        forcada = (os.environ.get(VARIAVEL) or "").strip()
        _cache["raiz"] = (forcada
                          or next((c for c in candidatos_raiz()
                                   if _tem_pva(c)), None)
                          or _explicita_ou_padrao())
    return _cache["raiz"]


def _explicita_ou_padrao():
    return ler().get("raiz_pva") or RAIZ_PADRAO


def definir_raiz_pva(caminho):
    """Grava a raiz escolhida pelo usuário. `""` volta à detecção."""
    gravar(raiz_pva=caminho or None)
    return raiz_pva()


def esquecer():
    """Descarta o que foi detectado (após instalar/mover o PVA)."""
    _cache.clear()


def pasta_pva(layout, raiz=None):
    cfg = PVAS.get(layout)
    if not cfg:
        return None
    return os.path.join(raiz or raiz_pva(), cfg["pasta"])

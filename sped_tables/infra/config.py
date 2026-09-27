# -*- coding: utf-8 -*-
"""Ponto único de configuração: onde estão os PVAs e as tabelas deles.

Até a 0.51.0 o caminho `C:\\Arquivos de Programas RFB\\Programas SPED`
estava escrito em quatro módulos (`pva`, `tabelas_pva`, `descritor_pva`,
`tabelas_rfb`). PVA instalado noutro disco, ou noutra pasta, desligava em
silêncio metade das verificações — e trocar exigia editar quatro arquivos.

Agora todo caminho do PVA sai daqui, decidido nesta ordem:

1. a variável de ambiente ``SPED_TABLES_PVA``;
2. ``raiz_pva`` no ``configuracao.json`` da pasta de dados (o que a
   interface grava quando o usuário escolhe a pasta);
3. a primeira pasta **existente** entre as conhecidas (a padrão da RFB,
   Arquivos de Programas e Arquivos de Programas (x86), em qualquer disco
   comum);
4. a padrão da RFB, mesmo inexistente — para a mensagem de "não encontrei"
   dizer onde procurou.

O leiaute de cada PVA dentro da raiz (pasta, tabelas, `.jar` do descritor)
também mora aqui, uma vez só.
"""

import json
import os

from sped_tables.infra import dados

VARIAVEL = "SPED_TABLES_PVA"
ARQUIVO = "configuracao.json"
RAIZ_PADRAO = r"C:\Arquivos de Programas RFB\Programas SPED"

# Onde fica cada coisa dentro da raiz. `pasta` é a do PVA; `tabelas`, as
# tabelas externas (códigos válidos); `descritor`, o .jar com o descritor
# de validação de cada versão de leiaute.
PVAS = {
    "ICMS": {
        "pasta": "Fiscal",
        "tabelas": os.path.join("recursos", "TabelasExternas"),
        "descritor": os.path.join("lib", "br.gov.serpro.sped.fiscalpva",
                                  "fiscalpva-dominio.jar"),
    },
    "CONTRIB": {
        "pasta": "EFD-Contribuicoes",
        "tabelas": os.path.join("recursos", "tabelas"),
        "descritor": os.path.join("lib", "br.gov.serpro.sped.piscofinspva",
                                  "piscofinspva-infra.jar"),
    },
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
        _cache["raiz"] = next((c for c in candidatos_raiz() if _tem_pva(c)),
                              None) or _explicita_ou_padrao()
    return _cache["raiz"]


def _explicita_ou_padrao():
    return (os.environ.get(VARIAVEL) or ler().get("raiz_pva")
            or RAIZ_PADRAO)


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


def pasta_tabelas(layout, raiz=None):
    """Tabelas externas do PVA do leiaute (códigos válidos, com vigência)."""
    pasta = pasta_pva(layout, raiz)
    return os.path.join(pasta, PVAS[layout]["tabelas"]) if pasta else None


def jar_descritor(layout, raiz=None):
    """O `.jar` com o descritor de validação do PVA do leiaute."""
    pasta = pasta_pva(layout, raiz)
    return os.path.join(pasta, PVAS[layout]["descritor"]) if pasta else None


def pasta_tabelas_rfb():
    """As tabelas de NCM da RFB (alíquota zero, monofásico) vêm com o PVA
    do EFD Contribuições."""
    return pasta_tabelas("CONTRIB")


# ----------------------------------------------------- tabelas da RFB
# Caminhos que o usuário escolheu no diálogo de CST por NCM. Moravam num
# `config_tabelas_rfb.json` próprio — que, rodando do código-fonte, era um
# arquivo versionado sendo regravado pelo programa. Agora ficam no
# `configuracao.json`; o arquivo antigo ainda é lido, uma vez, para não
# perder o que já estava escolhido.
CHAVES_TABELAS_RFB = ("pasta", "zero", "mono", "mono_difer", "genero", "ncm")
ARQUIVO_ANTIGO_RFB = "config_tabelas_rfb.json"


def tabelas_rfb():
    """`{pasta, zero, mono, mono_difer, genero, ncm}` escolhidos (ou vazios)."""
    atual = ler().get("tabelas_rfb")
    if not isinstance(atual, dict):
        try:
            with open(dados.caminho(ARQUIVO_ANTIGO_RFB),
                      encoding="utf-8") as fh:
                atual = json.load(fh)
        except (OSError, ValueError):
            atual = {}
    atual = atual if isinstance(atual, dict) else {}
    return {k: str(atual.get(k) or "") for k in CHAVES_TABELAS_RFB}


def gravar_tabelas_rfb(cfg):
    limpo = {k: str((cfg or {}).get(k) or "") for k in CHAVES_TABELAS_RFB}
    # a pasta padrão não precisa ser lembrada: é o que `config` já detecta
    if os.path.normcase(limpo["pasta"]) == os.path.normcase(
            pasta_tabelas_rfb() or ""):
        limpo["pasta"] = ""
    gravar(tabelas_rfb=limpo if any(limpo.values()) else None)
    return limpo

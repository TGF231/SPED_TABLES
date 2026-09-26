# -*- coding: utf-8 -*-
"""Leitura das tabelas oficiais da EFD Contribuições usadas para conferência de
CST por NCM:

  * Tabela 4.3.13 — Produtos sujeitos à **alíquota zero** (CST 06);
  * Tabela 4.3.10 — Produtos monofásicos de **alíquotas diferenciadas**
    (`PROD_MONO_ALIQ_DIFER`): perfumaria, higiene pessoal, medicamentos,
    veículos, autopeças — a Lei 10.147/2000 e afins;
  * Tabela 4.3.11 — Produtos monofásicos de **alíquota por unidade de medida**
    (`PROD_MONO_ALIQ_UNID`): combustíveis, bebidas frias;
  * Tabela de **gênero do item** (2 primeiros dígitos do NCM = capítulo);
  * Tabela **NCM vigente** (XLSX do Portal Siscomex), para validar/expandir NCMs.

As tabelas do PVA ficam na pasta de tabelas do EFD Contribuições (ver
`config.pasta_tabelas_rfb`), com nomes versionados, por exemplo
``SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_PROD_ALIQ_ZERO$51$166``.
O número após o nome da tabela é a **versão**; `localizar_tabela` escolhe a maior.
Também é possível informar o caminho de cada arquivo diretamente.
"""

import os
import re
import glob

from sped_tables.dominio.ncm import ClassificadorNCM
from sped_tables.dominio.sped_model import so_digitos
from sped_tables.infra import config


def pasta_padrao():
    """Onde o PVA do EFD Contribuições guarda as tabelas de NCM (`config`)."""
    return config.pasta_tabelas_rfb()


# fragmento que identifica cada tabela no nome do arquivo
CHAVE_ALIQ_ZERO = "PROD_ALIQ_ZERO"
# São DUAS tabelas de monofásico, e ler só uma esconde metade dos produtos:
# o NCM 34011190 (sabonete) só existe na de alíquotas diferenciadas, e sem ela
# o programa não via nada que o PVA via.
CHAVE_MONO = "PROD_MONO_ALIQ_UNID"
CHAVE_MONO_DIFER = "PROD_MONO_ALIQ_DIFER"
CHAVE_GENERO = "GENERO_ITEM"


def _versao_do_nome(nome, chave):
    """Extrai a versão (inteiro) que segue a `chave` no nome do arquivo.
    Aceita '$' (formato oficial) ou '_' como separador. None se não achar."""
    m = re.search(re.escape(chave) + r"[$_](\d+)", nome)
    return int(m.group(1)) if m else None


def localizar_tabela(pasta, chave):
    """Na `pasta`, devolve o caminho do arquivo da tabela `chave` com a MAIOR
    versão (ou None se nenhum). Ignora extensão e prefixos."""
    if not pasta or not os.path.isdir(pasta):
        return None
    melhor = None
    melhor_v = -1
    for caminho in glob.glob(os.path.join(pasta, "*")):
        nome = os.path.basename(caminho)
        if chave not in nome:
            continue
        v = _versao_do_nome(nome, chave)
        v = v if v is not None else 0
        if v > melhor_v:
            melhor_v, melhor = v, caminho
    return melhor


def _ler_versao_cabecalho(linha):
    m = re.search(r"vers[\u00e3a]o=(\S+)", linha)
    return m.group(1) if m else None


def carregar_tabela_produtos(caminho, encoding="latin-1"):
    """Lê uma tabela de produtos (4.3.11 ou 4.3.13). Devolve dict com 'versao'
    e 'registros' (lista). Cada registro traz codigo, desc, dt_ini, dt_fim,
    ncm (lista de prefixos, só dígitos), ncm_ex (exceções) e, na 4.3.11,
    unid/aliq_pis/aliq_cofins."""
    with open(caminho, encoding=encoding) as fh:
        linhas = fh.read().splitlines()
    if not linhas:
        return {"versao": None, "registros": []}
    versao = _ler_versao_cabecalho(linhas[0])
    registros = []
    for l in linhas[1:]:
        if not l.strip():
            continue
        p = l.split("|")
        if len(p) < 5:
            continue
        reg = {
            "codigo": p[0].strip(),
            "desc": p[1].strip(),
            "dt_ini": p[2].strip(),
            "dt_fim": p[3].strip(),
            "ncm": [so_digitos(x) for x in p[4].split(";") if x.strip()],
            "ncm_ex": [so_digitos(x) for x in
                       (p[5].split(";") if len(p) > 5 else []) if x.strip()],
        }
        if len(p) >= 10:            # 4.3.11: ...|EX_IPI|UNID|ALIQ_PIS|ALIQ_COFINS
            reg["unid"] = p[7].strip()
            reg["aliq_pis"] = p[8].strip()
            reg["aliq_cofins"] = p[9].strip()
        elif len(p) >= 9:           # 4.3.10: ...|EX_IPI|ALIQ_PIS|ALIQ_COFINS
            reg["aliq_pis"] = p[7].strip()
            reg["aliq_cofins"] = p[8].strip()
        registros.append(reg)
    return {"versao": versao, "registros": registros}


def carregar_genero(caminho, encoding="latin-1"):
    """Lê a tabela de gênero do item. Devolve dict {codigo_2dig: descricao}."""
    with open(caminho, encoding=encoding) as fh:
        linhas = fh.read().splitlines()
    genero = {}
    for l in linhas[1:]:
        p = l.split("|")
        if len(p) >= 2 and p[0].strip():
            genero[p[0].strip().zfill(2)] = p[1].strip()
    return genero


def carregar_ncm_vigente(caminho_xlsx):
    """Lê a planilha de NCM vigente (Siscomex). Devolve o conjunto de NCMs de 8
    dígitos vigentes. Requer openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho_xlsx, read_only=True, data_only=True)
    ws = wb.active
    ncms = set()
    for row in ws.iter_rows(values_only=True):
        cod = row[0] if row else None
        d = so_digitos(cod if isinstance(cod, str) else str(cod or ""))
        if len(d) == 8:
            ncms.add(d)
    return ncms


def _unir_tabelas(*tabelas):
    """Funde tabelas de produtos numa só, para o classificador tratar as duas
    listas de monofásico como uma. A versão vira `a+b`, para aparecer na
    interface qual par foi carregado."""
    regs = []
    versoes = []
    for t in tabelas:
        if not t:
            continue
        regs.extend(t.get("registros", []))
        if t.get("versao"):
            versoes.append(str(t["versao"]))
    if not regs and not versoes:
        return None
    return {"versao": "+".join(versoes) or None, "registros": regs}


def carregar_tudo(pasta=None, caminho_zero=None, caminho_mono=None,
                  caminho_genero=None, caminho_ncm=None,
                  caminho_mono_difer=None):
    """Conveniência: localiza (na `pasta`) e/ou carrega as tabelas pelos caminhos
    informados e devolve um ClassificadorNCM pronto. Caminhos explícitos têm
    prioridade sobre a detecção por nome na pasta.

    Sem pasta, vale a do PVA (`config`): antes, o cadastro de empresas sem
    configuração salva montava um classificador **vazio**, e a rotina de
    CST por NCM não acusava nada.
    """
    pasta = pasta or pasta_padrao()
    czero = caminho_zero or localizar_tabela(pasta, CHAVE_ALIQ_ZERO)
    cmono = caminho_mono or localizar_tabela(pasta, CHAVE_MONO)
    cdifer = caminho_mono_difer or localizar_tabela(pasta, CHAVE_MONO_DIFER)
    cgen = caminho_genero or localizar_tabela(pasta, CHAVE_GENERO)
    tab_zero = carregar_tabela_produtos(czero) if czero else None
    # as duas tabelas de monofásico viram uma só para o classificador
    tab_mono = _unir_tabelas(
        carregar_tabela_produtos(cmono) if cmono else None,
        carregar_tabela_produtos(cdifer) if cdifer else None)
    genero = carregar_genero(cgen) if cgen else None
    ncm_vig = carregar_ncm_vigente(caminho_ncm) if caminho_ncm else None
    return ClassificadorNCM(tab_zero, tab_mono, genero, ncm_vig), {
        "zero": czero, "mono": cmono, "mono_difer": cdifer, "genero": cgen,
        "ncm": caminho_ncm}


def classificador(cfg=None):
    """O classificador a partir da configuração escolhida pelo usuário
    (`config.tabelas_rfb()`). Um caminho só para os dois diálogos que o
    montavam — e o do cadastro de empresas esquecia a tabela 4.3.10.

    Devolve `(classificador, caminhos_usados)`.
    """
    cfg = cfg if cfg is not None else config.tabelas_rfb()
    return carregar_tudo(
        pasta=cfg.get("pasta") or None,
        caminho_zero=cfg.get("zero") or None,
        caminho_mono=cfg.get("mono") or None,
        caminho_mono_difer=cfg.get("mono_difer") or None,
        caminho_genero=cfg.get("genero") or None,
        caminho_ncm=cfg.get("ncm") or None)

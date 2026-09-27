# -*- coding: utf-8 -*-
"""Memória persistente: cópia interna dos arquivos SPED, por empresa.

Mesma ideia do PVA, que guarda no banco interno o que foi importado — só que
aqui a "base" é a própria pasta do programa, o que combina com um editor que
trabalha o arquivo texto o tempo todo:

    arquivos/
      11222333000181/
        CONTRIB_202608.txt
        ICMS_202608.txt
      indice.json

**Uma cópia por empresa + leiaute + período**, sempre substituída pela mais
recente. O histórico da interface lista um item por período e aponta para essa
cópia — abrir do histórico é abrir a cópia, não o arquivo de origem, que pode
ter sido movido ou apagado.

A cópia é feita a partir do **arquivo em disco**, nunca de um texto gerado na
memória: assim ela é byte a byte o que o usuário tem, incluindo o encoding
latin-1 e as quebras de linha originais.

Sem dependência de GUI.
"""

import os
import shutil

from sped_tables.dominio.sped_model import so_digitos
from sped_tables.infra import dados
from datetime import datetime

PASTA = "arquivos"
INDICE = "indice.json"

MOTIVOS = {
    "abertura": "aberto no sistema",
    "salvamento": "salvo pelo sistema",
}


def _base():
    """Raiz das cópias internas. Empacotado, vai para %APPDATA% (ver `dados`)."""
    return os.path.join(dados.pasta_dados(), PASTA)


def _caminho_indice():
    return os.path.join(_base(), INDICE)


def periodo_do_doc(doc):
    """Período AAAAMM a partir da DT_INI do 0000 (formato SPED DDMMAAAA)."""
    i = doc._ix("0000", "DT_INI")
    for r in doc.registros:
        if r.reg == "0000":
            dt = so_digitos(r.valor(i)) if i is not None else ""
            if len(dt) == 8:
                return dt[4:] + dt[2:4]        # AAAA + MM
            return ""
    return ""


def identificar(doc):
    """(cnpj, nome, layout, periodo) do documento aberto."""
    i_cnpj = doc._ix("0000", "CNPJ")
    i_nome = doc._ix("0000", "NOME")
    cnpj = nome = ""
    for r in doc.registros:
        if r.reg == "0000":
            cnpj = so_digitos(r.valor(i_cnpj)) if i_cnpj is not None else ""
            nome = (r.valor(i_nome) or "").strip() if i_nome is not None else ""
            break
    return cnpj, nome, doc.layout or "", periodo_do_doc(doc)


def nome_copia(layout, periodo):
    return "%s_%s.txt" % (layout or "SPED", periodo or "sem_periodo")


def caminho_copia(cnpj, layout, periodo):
    return os.path.join(_base(), cnpj, nome_copia(layout, periodo))


# ----------------------------------------------------------------- índice
def carregar_indice():
    # ilegível, é guardado à parte e avisado: o próximo arquivamento
    # gravaria um índice novo por cima do antigo
    return dados.ler_json_do_usuario(_caminho_indice(), list) or []


def _salvar_indice(entradas):
    # atômico: o índice truncado no meio da gravação apagava o histórico
    # inteiro da tela, embora as cópias continuassem no disco
    dados.gravar_json(_caminho_indice(), entradas)


def _chave(e):
    return (e.get("cnpj", ""), e.get("layout", ""), e.get("periodo", ""))


# -------------------------------------------------------------- operações
def arquivar(doc, caminho_origem=None, motivo="abertura"):
    """Copia o arquivo para a pasta interna e atualiza o índice.

    Devolve a entrada do índice, ou None quando não há como identificar a
    empresa (sem CNPJ no 0000) ou o arquivo de origem não existe.
    """
    origem = caminho_origem or getattr(doc, "caminho", "")
    if not origem or not os.path.isfile(origem):
        return None
    cnpj, nome, layout, periodo = identificar(doc)
    if not cnpj:
        return None

    destino = caminho_copia(cnpj, layout, periodo)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    # se a origem já é a própria cópia (arquivo aberto do histórico), não há
    # o que copiar — copyfile com origem == destino truncaria o arquivo
    if os.path.abspath(origem) != os.path.abspath(destino):
        shutil.copyfile(origem, destino)

    entradas = [e for e in carregar_indice()
                if _chave(e) != (cnpj, layout, periodo)]
    entrada = {
        "cnpj": cnpj,
        "nome": nome,
        "layout": layout,
        "periodo": periodo,
        "arquivo": os.path.relpath(destino, _base()).replace("\\", "/"),
        "origem": os.path.abspath(origem),
        "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": motivo,
        "tamanho": os.path.getsize(destino),
        "registros": len(getattr(doc, "registros", []) or []),
    }
    entradas.append(entrada)
    _salvar_indice(entradas)
    return entrada


def historico(cnpj=None):
    """Entradas do histórico, mais recentes primeiro. Filtra por CNPJ."""
    entradas = carregar_indice()
    if cnpj:
        alvo = so_digitos(cnpj)
        entradas = [e for e in entradas if e.get("cnpj") == alvo]
    entradas.sort(key=lambda e: (e.get("periodo", ""),
                                 e.get("atualizado_em", "")), reverse=True)
    for e in entradas:
        e["caminho"] = os.path.join(_base(), e.get("arquivo", ""))
        e["existe"] = os.path.isfile(e["caminho"])
    return entradas


def empresas_no_historico():
    """{cnpj: nome} das empresas que já têm arquivo arquivado."""
    mapa = {}
    for e in carregar_indice():
        cnpj = e.get("cnpj")
        if cnpj:
            mapa.setdefault(cnpj, e.get("nome", ""))
    return mapa


def remover(cnpj, layout, periodo, apagar_arquivo=True):
    """Tira o período do histórico (e apaga a cópia, por padrão)."""
    alvo = (so_digitos(cnpj), layout, periodo)
    restantes, removidas = [], []
    for e in carregar_indice():
        (removidas if _chave(e) == alvo else restantes).append(e)
    if not removidas:
        return 0
    if apagar_arquivo:
        for e in removidas:
            cam = os.path.join(_base(), e.get("arquivo", ""))
            try:
                if os.path.isfile(cam):
                    os.remove(cam)
            except OSError:
                pass
    _salvar_indice(restantes)
    return len(removidas)


def _periodos_ate(quantidade, fim=None):
    """Lista dos últimos N períodos AAAAMM, do mais antigo ao mais recente."""
    hoje = fim or datetime.now()
    ano, mes = hoje.year, hoje.month
    saida = []
    for _ in range(quantidade):
        saida.append("%04d%02d" % (ano, mes))
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return list(reversed(saida))


def cobertura(meses=8, empresas_extras=None, fim=None):
    """Matriz empresa × período: que leiautes estão arquivados em cada mês.

    Serve à tela inicial. "Ausente" aqui significa **não arquivado neste
    sistema** — nunca "não entregue": o arquivo pode ter sido transmitido sem
    jamais passar por aqui, e o programa não tem como saber. O rótulo na
    interface precisa refletir isso.

    `empresas_extras` é um {cnpj: nome} de empresas cadastradas que ainda não
    têm nenhum arquivo — elas aparecem na matriz com a linha inteira vazia, que
    é justamente a informação útil.
    """
    periodos = _periodos_ate(meses, fim)
    indice = carregar_indice()

    nomes = dict(empresas_extras or {})
    por_empresa = {}
    for e in indice:
        cnpj = e.get("cnpj")
        if not cnpj:
            continue
        nomes.setdefault(cnpj, e.get("nome", ""))
        if e.get("nome"):
            nomes[cnpj] = e["nome"]
        por_empresa.setdefault(cnpj, {}).setdefault(e.get("periodo", ""), set()).add(
            e.get("layout", ""))

    linhas = []
    for cnpj in sorted(nomes, key=lambda c: (nomes.get(c) or "", c)):
        celulas = []
        for p in periodos:
            leiautes = por_empresa.get(cnpj, {}).get(p, set())
            celulas.append({
                "periodo": p,
                "icms": "ICMS" in leiautes,
                "contrib": "CONTRIB" in leiautes,
            })
        linhas.append({"cnpj": cnpj, "nome": nomes.get(cnpj, ""),
                       "celulas": celulas,
                       "total": sum(1 for c in celulas
                                    if c["icms"] or c["contrib"])})
    return {"periodos": periodos, "empresas": linhas}


def pendencias(cadastradas):
    """Avisos acionáveis da tela inicial.

    `cadastradas` é o {cnpj: Empresa} do cadastro. Só apontamos o que dá para
    saber **sem abrir arquivo**: empresa com arquivo mas sem cadastro (as
    rotinas por regime não funcionam para ela) e o inverso, cadastro que nunca
    recebeu arquivo.
    """
    do_hist = empresas_no_historico()
    sem_cadastro = [(c, n) for c, n in sorted(do_hist.items())
                    if c not in cadastradas]
    sem_arquivo = [(c, e.nome) for c, e in sorted(cadastradas.items())
                   if c not in do_hist]
    return {"sem_cadastro": sem_cadastro, "sem_arquivo": sem_arquivo}


def resumo_acervo():
    """(empresas, períodos, bytes) do que está arquivado."""
    indice = carregar_indice()
    return (len({e.get("cnpj") for e in indice if e.get("cnpj")}),
            len(indice),
            sum(int(e.get("tamanho") or 0) for e in indice))


def formatar_periodo(periodo):
    """202608 -> 08/2026."""
    p = so_digitos(periodo)
    return "%s/%s" % (p[4:], p[:4]) if len(p) == 6 else (periodo or "")

# -*- coding: utf-8 -*-
"""Ajuda de registro e de campo: o que o **guia prático** e o **descritor do
PVA** dizem de cada um, juntos.

O descritor dá a declaração (tipo, tamanho, obrigatoriedade, os valores
válidos com o significado de cada um); o guia dá o texto — como preencher e
como o validador confere. Nenhum dos dois sozinho responde "o que vai
neste campo?".
"""

from sped_tables.dominio import referencias
from sped_tables.dominio.sped_layouts import campos as campos_do_leiaute


def citacao(layout):
    """"Guia Prático EFD ICMS/IPI 3.2.4" — para citar a fonte."""
    g = referencias.atual().guia(layout)
    if not g:
        return ""
    return "Guia Prático %s %s" % (g.get("guia", ""), g.get("versao", ""))


def do_campo(layout, reg, n, nome, est=None, guia=None):
    """Ajuda do campo `n` (1 = REG) do registro, chamado `nome` no leiaute.

    `{"nome", "rotulo", "descricao", "tipo", "tamanho", "decimais",
    "obrigatorio", "valores": [(código, significado)], "valores_guia",
    "preenchimento", "validacao"}` — o que não houver fica vazio. `est` e
    `guia` poupam a consulta à fonte quando o chamador já os tem."""
    if est is None:
        est, _info = referencias.atual().estrutura(layout)
    if guia is None:
        guia = referencias.atual().guia(layout)
    c = ((est.get(reg) or {}).get("campos") or {}).get(nome) or {}
    g = referencias.texto_do_campo(guia, reg, n, nome)
    significados = c.get("significados") or {}
    valores = [(v, significados.get(v, "")) for v in (c.get("valores") or [])]
    return {
        "nome": nome,
        "n": n,
        "rotulo": c.get("rotulo", ""),
        "descricao": c.get("descricao", ""),
        "tipo": {"C": "texto", "N": "número", "D": "data"}.get(
            c.get("tipo", ""), c.get("tipo", "")),
        "tamanho": (c.get("tamanho") or "").strip("[]"),
        "fixo": (c.get("tamanho") or "").startswith("["),
        "decimais": c.get("decimais", ""),
        "obrigatorio": {"1": "sim", "0": "não"}.get(
            c.get("obrigatorio", ""), ""),
        "valores": valores,
        "valores_guia": g.get("valores", ""),
        "preenchimento": g.get("preenchimento", "") or g.get("texto", ""),
        "validacao": g.get("validacao", ""),
    }


def do_registro(layout, reg):
    """Ajuda do registro inteiro: título, objetivo, validação do registro e a
    ajuda de cada campo do leiaute."""
    est, _info = referencias.atual().estrutura(layout)
    guia = referencias.atual().guia(layout)
    d = est.get(reg) or {}
    g = (guia.get("registros") or {}).get(reg) or {}
    nomes = list(campos_do_leiaute(reg, layout, 0))
    return {
        "reg": reg,
        "titulo": g.get("titulo") or d.get("descricao") or d.get("rotulo")
        or "",
        "objetivo": g.get("objetivo", ""),
        "validacao_registro": g.get("validacao_registro", ""),
        "observacoes": g.get("observacoes", ""),
        "nivel": g.get("nivel", d.get("nivel")),
        "ocorrencia": g.get("ocorrencia", ""),
        "fonte": citacao(layout),
        "campos": [do_campo(layout, reg, i + 1, nome, est, guia)
                   for i, nome in enumerate(nomes)],
    }

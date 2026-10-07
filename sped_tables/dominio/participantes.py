# -*- coding: utf-8 -*-
"""Corrigir o cadastro de participantes (0150) por uma fonte de fora — o
banco do ERP.

Mesmo contrato da atualização do 0200 pela planilha: primeiro a **prévia**
(`{campo: [(COD_PART, atual, novo)]}`, sem mexer em nada), depois a
aplicação só dos campos que a pessoa marcou. Valor vazio na fonte nunca
apaga o que o arquivo tem, e valor objetivamente inválido (CNPJ com dígito
errado, município sem 7 dígitos) nasce desmarcado.

O casamento é pelo `COD_PART`; quando o ERP não usa o mesmo código que foi
para o SPED, vale o CNPJ/CPF — desde que um só participante tenha aquele
documento dos dois lados.
"""

import re

from sped_tables.dominio.regras_guia import cnpj_valido, cpf_valido

# chave da fonte -> campo do 0150, na ordem do registro
CAMPOS_0150 = (("nome", "NOME"), ("cod_pais", "COD_PAIS"), ("cnpj", "CNPJ"),
               ("cpf", "CPF"), ("ie", "IE"), ("cod_mun", "COD_MUN"),
               ("suframa", "SUFRAMA"), ("end", "END"), ("num", "NUM"),
               ("compl", "COMPL"), ("bairro", "BAIRRO"))
_NUMERICOS = {"COD_PAIS", "COD_MUN"}      # 1058 e 01058 são o mesmo país


def _digitos(v):
    return re.sub(r"\D", "", _texto(v))


def _texto(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    # o pipe é o separador do SPED: dentro de um campo, quebraria a linha
    return re.sub(r"\s+", " ", str(v).replace("|", " ")).strip()


def normalizar(ln):
    """`{campo do 0150: valor}` de uma linha da fonte, já no formato do SPED.
    CNPJ e CPF numa coluna só (`cnpj` com 11 dígitos) vão para o CPF; IE
    "ISENTO" é IE vazia (o PVA valida a inscrição pela UF)."""
    v = {}
    doc = _digitos(ln.get("cnpj"))
    cpf = _digitos(ln.get("cpf"))
    if len(doc) == 11 and not cpf:
        doc, cpf = "", doc
    v["CNPJ"] = doc
    v["CPF"] = cpf
    ie = re.sub(r"[^0-9A-Za-z]", "", _texto(ln.get("ie"))).upper()
    v["IE"] = "" if "ISENT" in ie else ie
    v["COD_MUN"] = _digitos(ln.get("cod_mun"))
    v["COD_PAIS"] = _digitos(ln.get("cod_pais"))
    v["SUFRAMA"] = _digitos(ln.get("suframa"))
    for chave in ("nome", "end", "num", "compl", "bairro"):
        v[chave.upper()] = _texto(ln.get(chave))
    return v


def _iguais(campo, a, b):
    if campo in _NUMERICOS and a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return a == b


def _casamento(doc, linhas):
    """`[(registro 0150, valores normalizados)]` dos participantes que a
    fonte conhece."""
    ix = {c: doc._ix("0150", c) for c in ("COD_PART", "CNPJ", "CPF")}
    por_cod, por_doc, repetidos = {}, {}, set()
    for ln in linhas:
        cod = _texto(ln.get("cod_part"))
        v = normalizar(ln)
        if cod and cod not in por_cod:
            por_cod[cod] = v
        documento = v["CNPJ"] or v["CPF"]
        if documento:
            if documento in por_doc:
                repetidos.add(documento)
            por_doc[documento] = v
    registros = [r for r in doc.registros if r.reg == "0150"]
    no_arquivo = {}
    for r in registros:
        d = _digitos(r.valor(ix["CNPJ"])) or _digitos(r.valor(ix["CPF"]))
        no_arquivo[d] = no_arquivo.get(d, 0) + 1
    pares = []
    for r in registros:
        v = por_cod.get(_texto(r.valor(ix["COD_PART"])))
        if v is None:
            d = _digitos(r.valor(ix["CNPJ"])) or _digitos(r.valor(ix["CPF"]))
            if d and d not in repetidos and no_arquivo.get(d) == 1:
                v = por_doc.get(d)
        if v is not None:
            pares.append((r, v))
    return pares


def _mudancas(doc, r, v):
    out = []
    atuais = {}
    for _chave, campo in CAMPOS_0150:
        i = doc._ix("0150", campo)
        if i is not None and i < len(r.campos):
            atuais[campo] = (i, (r.valor(i) or "").strip())
    for _chave, campo in CAMPOS_0150:
        novo = v.get(campo, "")
        if campo not in atuais or not novo:
            continue
        # CNPJ e CPF se excluem: participante que é pessoa física no
        # arquivo e jurídica no ERP (ou o contrário) não se troca às cegas
        outro = {"CNPJ": "CPF", "CPF": "CNPJ"}.get(campo)
        if outro and atuais.get(outro, (None, ""))[1]:
            continue
        i, atual = atuais[campo]
        if not _iguais(campo, atual, novo):
            out.append((campo, i, atual, novo))
    return out


def previa(doc, linhas):
    """O que a fonte mudaria no 0150, **sem alterar nada**:
    `{campo: [(COD_PART, atual, novo)]}`."""
    i_cod = doc._ix("0150", "COD_PART")
    prev = {}
    for r, v in _casamento(doc, linhas):
        for campo, _i, atual, novo in _mudancas(doc, r, v):
            prev.setdefault(campo, []).append(
                ((r.valor(i_cod) or "").strip(), atual, novo))
    return prev


def avisos(previa_):
    """`{campo: (quantidade, texto, desmarcar)}` — o formato do diálogo de
    atualização do 0200."""
    out = {}
    maus = [c for c, _a, n in previa_.get("CNPJ", []) if not cnpj_valido(n)]
    if maus:
        out["CNPJ"] = (len(maus), "CNPJ com dígito verificador errado no "
                       "ERP (ex.: %s): o PVA recusa" % maus[0], True)
    maus = [c for c, _a, n in previa_.get("CPF", []) if not cpf_valido(n)]
    if maus:
        out["CPF"] = (len(maus), "CPF com dígito verificador errado no ERP "
                      "(ex.: %s)" % maus[0], True)
    maus = [c for c, _a, n in previa_.get("COD_MUN", [])
            if len(n) != 7 and n != "9999999"]
    if maus:
        out["COD_MUN"] = (len(maus), "código de município sem os 7 dígitos "
                          "do IBGE (ex.: %s)" % maus[0], True)
    troca = [c for c, a, n in previa_.get("CNPJ", []) if a and a != n]
    if troca and "CNPJ" not in out:
        out["CNPJ"] = (len(troca), "trocaria o CNPJ de participante que já "
                       "tem um — confira se é a mesma pessoa jurídica", False)
    return out


def atualizar(doc, linhas, campos):
    """Grava no 0150 os campos escolhidos (`campos`, nomes do 0150).
    Devolve `{campo: quantos participantes mudaram}`."""
    contagem = {}
    for r, v in _casamento(doc, linhas):
        for campo, i, _atual, novo in _mudancas(doc, r, v):
            if campo in campos:
                r.set_valor(i, novo)
                contagem[campo] = contagem.get(campo, 0) + 1
    return contagem

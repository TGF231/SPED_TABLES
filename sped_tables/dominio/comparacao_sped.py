# -*- coding: utf-8 -*-
"""Comparar dois SPED do mesmo período, documento a documento.

Feito para julgar o SPED gerado dos XMLs contra o entregue, mas serve a
qualquer par: casa o C100/D100 pela **chave de acesso**, o item pelo
**número do item**, o analítico pela **chave do registro** (CST, CFOP,
alíquota) e compara **números como números** (`3565,6` e `3565,60` são o
mesmo valor). Participante é comparado pelo CNPJ/CPF, não pelo código, que
cada arquivo numera do seu jeito.
"""

from sped_tables.dominio.sped_model import _to_num

C100 = ("COD_SIT", "DT_DOC", "DT_E_S", "VL_DOC", "IND_PGTO", "VL_DESC",
        "VL_MERC", "IND_FRT", "VL_FRT", "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI", "VL_PIS",
        "VL_COFINS")
C170 = ("COD_ITEM", "QTD", "UNID", "VL_ITEM", "VL_DESC", "CST_ICMS", "CFOP",
        "COD_NAT", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_ICMS_ST",
        "CST_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA")
C175 = ("VL_OPR", "VL_DESC", "VL_BC_PIS", "VL_PIS", "VL_BC_COFINS",
        "VL_COFINS")
C190 = ("VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST",
        "VL_RED_BC", "VL_IPI")
D100 = ("COD_SIT", "DT_DOC", "VL_DOC", "IND_FRT", "VL_SERV", "VL_BC_ICMS",
        "VL_ICMS")


def _numero(v):
    t = (v or "").strip()
    return t.replace(",", "").replace("-", "").isdigit() and "," in t


def _igual(a, b):
    a, b = (a or "").strip(), (b or "").strip()
    if a == b:
        return True
    # zero e vazio valem o mesmo aqui: a comparação é de valores (formato,
    # como o vazio que a NFC-e exige, é o PVA que julga)
    zero = ("", "0", "0,0", "0,00")
    if a in zero and b in zero:
        return True
    if _numero(a) or _numero(b):
        return abs(_to_num(a) - _to_num(b)) < 0.005
    return False


def _campos(doc, reg, r, nomes):
    return {n: r.valor(doc._ix(reg, n)) for n in nomes
            if doc._ix(reg, n) is not None}


def _docs(doc, reg, campo_chave):
    i = doc._ix(reg, campo_chave)
    return {r.valor(i): r for r in doc.registros if r.reg == reg}


def comparar(gerado, entregue):
    """`{secao: {"so_gerado", "so_entregue", "diferencas", "iguais"}}` e,
    em `diferencas`, `(chave, campo, gerado, entregue)`."""
    out = {}
    for reg, chave, nomes in (("C100", "CHV_NFE", C100),
                              ("D100", "CHV_CTE", D100)):
        g, e = _docs(gerado, reg, chave), _docs(entregue, reg, chave)
        sec = {"so_gerado": sorted(set(g) - set(e)),
               "so_entregue": sorted(set(e) - set(g)),
               "diferencas": [], "iguais": 0}
        itens = {"so_gerado": [], "so_entregue": [], "diferencas": [],
                 "iguais": 0}
        anal = {"so_gerado": [], "so_entregue": [], "diferencas": [],
                "iguais": 0}
        for k in sorted(set(g) & set(e)):
            _dif(sec, k, _campos(gerado, reg, g[k], nomes),
                 _campos(entregue, reg, e[k], nomes))
            _dif_part(sec, k, gerado, g[k], entregue, e[k], reg)
            if reg == "C100":
                _filhos(itens, k, gerado, g[k], entregue, e[k], "C170",
                        ("NUM_ITEM",), C170)
                if gerado.layout == "CONTRIB":
                    _filhos(anal, k, gerado, g[k], entregue, e[k], "C175",
                            ("CFOP", "CST_PIS", "ALIQ_PIS"), C175)
                else:
                    _filhos(anal, k, gerado, g[k], entregue, e[k], "C190",
                            ("CST_ICMS", "CFOP", "ALIQ_ICMS"), C190)
            else:
                _filhos(anal, k, gerado, g[k], entregue, e[k], "D190",
                        ("CST_ICMS", "CFOP", "ALIQ_ICMS"), C190[:3])
        out[reg] = sec
        out[reg[0] + ("170" if reg == "C100" else "_itens")] = itens
        out[reg[0] + ("175" if reg == "C100" and gerado.layout == "CONTRIB"
                      else "190")] = anal
    for unico in (("E110",) if gerado.layout == "ICMS" else
                  ("M200", "M205", "M210", "M600", "M605", "M610")):
        out[unico] = _unico(gerado, entregue, unico)
    out["0150"] = _cadastro(gerado, entregue, "0150", ("CNPJ", "CPF"))
    out["0200"] = _cadastro(gerado, entregue, "0200", ("COD_ITEM",))
    return out


def _dif(sec, chave, g, e):
    iguais = True
    for campo in g:
        if not _igual(g.get(campo), e.get(campo)):
            sec["diferencas"].append((chave, campo, g.get(campo),
                                      e.get(campo)))
            iguais = False
    if iguais:
        sec["iguais"] += 1


def _dif_part(sec, chave, gerado, rg, entregue, re_, reg):
    """COD_PART pelo documento do participante, não pelo código."""
    def documento(doc, r):
        cod = r.valor(doc._ix(reg, "COD_PART"))
        if not cod:
            return ""
        for p in doc.registros:
            if p.reg == "0150" and p.valor(doc._ix("0150", "COD_PART")) == cod:
                return (p.valor(doc._ix("0150", "CNPJ"))
                        or p.valor(doc._ix("0150", "CPF")))
        return "?" + cod
    a, b = documento(gerado, rg), documento(entregue, re_)
    if a != b:
        sec["diferencas"].append((chave, "COD_PART (documento)", a, b))


def _filhos(sec, chave, gerado, rg, entregue, re_, tipo, campos_chave,
            nomes):
    def mapa(doc, r):
        ix = [doc._ix(tipo, c) for c in campos_chave]
        out = {}
        for f in r.filhos:
            if f.reg == tipo:
                k = tuple(_norm_chave(f.valor(i)) for i in ix)
                out[k] = f
        return out
    g, e = mapa(gerado, rg), mapa(entregue, re_)
    sec["so_gerado"] += [(chave, k) for k in sorted(set(g) - set(e))]
    sec["so_entregue"] += [(chave, k) for k in sorted(set(e) - set(g))]
    for k in sorted(set(g) & set(e)):
        _dif(sec, (chave, k), _campos(gerado, tipo, g[k], nomes),
             _campos(entregue, tipo, e[k], nomes))


def _norm_chave(v):
    """Chave de casamento: número vale pelo valor ("0" e "0,00", "060" e
    "60" casam); texto, como está."""
    v = (v or "").strip()
    if v.replace(",", "").replace(".", "").isdigit():
        return "%.4f" % _to_num(v)
    return v


def _unico(gerado, entregue, reg):
    def um(doc):
        return next((r for r in doc.registros if r.reg == reg), None)
    g, e = um(gerado), um(entregue)
    sec = {"so_gerado": [], "so_entregue": [], "diferencas": [], "iguais": 0}
    if g is None or e is None:
        return sec
    from sped_tables.dominio.sped_layouts import campos
    nomes = campos(reg, gerado.layout, len(g.campos))[1:]
    _dif(sec, reg, _campos(gerado, reg, g, nomes),
         _campos(entregue, reg, e, nomes))
    return sec


def _cadastro(gerado, entregue, reg, chaves):
    def mapa(doc):
        ix = [doc._ix(reg, c) for c in chaves]
        return {next((r.valor(i) for i in ix if r.valor(i)), ""): r
                for r in doc.registros if r.reg == reg}
    g, e = mapa(gerado), mapa(entregue)
    return {"so_gerado": sorted(set(g) - set(e)),
            "so_entregue": sorted(set(e) - set(g)), "diferencas": [],
            "iguais": len(set(g) & set(e))}

# -*- coding: utf-8 -*-
"""Regenerar as **entradas** do arquivo aberto pelos XMLs.

O XML diz o que foi comprado (quantidades, valores, impostos destacados); o
**próprio arquivo** diz como a empresa escritura cada produto — código
próprio, CFOP de entrada, CST, crédito, conta. Por isso a regeneração:

1. aprende a escrituração com o arquivo aberto (`memoria_itens.aprender`,
   sobre uma **cópia** da memória da empresa: nada é gravado nela);
2. gera o período pelo gerador de sempre (`geracao.gerar_icms` /
   `gerar_contrib`) — C170, C190 e totais do C100 pelos mesmos cálculos
   dos botões;
3. troca, no arquivo, cada C100 de entrada que tem XML pelo gerado (casando
   pela chave), inclui os que o arquivo não tinha e **mantém** os que não
   têm XML na pasta, dizendo quais.

Tudo começa por um `Plano` (a prévia: o que muda, campo a campo, e o que
precisa de revisão) e só `aplicar` mexe no arquivo. Documento cujo item
ficaria inválido (CFOP de entrada desconhecido, CST de PIS ausente) não
entra: é listado em `bloqueados`, e o original fica como está.

Fora do escopo, por ora: CT-e (D100) e as saídas — que são da empresa e já
saem do ERP dela.
"""

import copy

from sped_tables.dominio import geracao
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio.empresas import dados_do_arquivo
from sped_tables.dominio.sped_layouts import campos as campos_do_leiaute
from sped_tables.dominio.sped_model import RE_NUM_SPED, _to_num

# cadastro que o documento gerado pode trazer de novo, pela chave de cada um
CADASTRO = {"0150": "COD_PART", "0190": "UNID", "0200": "COD_ITEM",
            "0400": "COD_NAT", "0500": "COD_CTA"}


class Plano:
    """O que a regeneração faria — a prévia, e o que `aplicar` usa."""

    def __init__(self):
        self.substituir = []     # [(C100 do arquivo, C100 gerado)]
        self.incluir = []        # [C100 gerado sem par no arquivo]
        self.sem_xml = []        # [C100 de entrada mantidos: sem XML]
        self.fora_periodo = []   # [(chave, data)] XML com data de outro mês
        self.bloqueados = []     # [(documento, [motivos])] não regenerados
        self.cadastro = []       # [registro gerado] 0150/0190/0200/0400/0500
        self.mudancas = {}       # "C170.VL_ITEM" -> quantos valores mudam
        self.revisar = []        # apontamentos do gerador nos documentos
        self.gerado = None       # o SPED gerado (fonte dos registros)

    @property
    def vazio(self):
        return not (self.substituir or self.incluir)


def _chave(doc, c100):
    return (c100.valor(doc._ix("C100", "CHV_NFE")) or "").strip()


def _onde(doc, c100):
    """O "NF série/número" com que o gerador aponta o documento."""
    return "NF %s/%s" % ((c100.valor(doc._ix("C100", "SER")) or "").strip(),
                         (c100.valor(doc._ix("C100", "NUM_DOC")) or "")
                         .strip())


def _entradas(doc):
    i_op = doc._ix("C100", "IND_OPER")
    i_emit = doc._ix("C100", "IND_EMIT")
    return [r for r in doc.registros if r.reg == "C100"
            and (r.valor(i_op) or "").strip() == "0"
            and (r.valor(i_emit) or "").strip() == "1"]


def planejar(doc, lote, memoria=None, correlacoes=None):
    """O `Plano` de regenerar as entradas de `doc` pelos XMLs do `lote`.

    `memoria` é a da empresa (`memoria_itens`), se houver — o arquivo
    aberto ensina por cima dela, numa cópia."""
    if doc.layout not in ("ICMS", "CONTRIB"):
        raise ValueError("Leiaute não suportado: %s." % doc.layout)
    cnpj = dados_do_arquivo(doc)[0]
    mem = copy.deepcopy(memoria) if memoria else mi.nova(cnpj)
    mem["cnpj"] = cnpj
    mi.aprender(mem, lote, doc_icms=doc if doc.layout == "ICMS" else None,
                doc_contrib=doc if doc.layout == "CONTRIB" else None)
    fim = doc.data_final()
    periodo = fim[4:] + fim[2:4]
    gerar = geracao.gerar_icms if doc.layout == "ICMS" else \
        geracao.gerar_contrib
    res = gerar(mem, lote, periodo, correlacoes=correlacoes)
    gen = res.doc

    plano = Plano()
    plano.gerado = gen
    plano.fora_periodo = list(res.fora_periodo)
    bloqueio = {}
    for a in res.bloqueios:
        bloqueio.setdefault(a["documento"], []).append(
            "%s (item %s)" % (a["tipo"], a["item"]))

    atuais = {}
    for c in _entradas(doc):
        atuais.setdefault(_chave(doc, c), c)
    usados = set()
    ondes = set()
    for novo in _entradas(gen):
        chave = _chave(gen, novo)
        onde = _onde(gen, novo)
        if onde in bloqueio:
            plano.bloqueados.append((onde, bloqueio[onde]))
            usados.add(chave)              # o original fica como está
            continue
        ondes.add(onde)
        antigo = atuais.get(chave)
        if antigo is None:
            plano.incluir.append(novo)
        else:
            usados.add(chave)
            plano.substituir.append((antigo, novo))
            _comparar(doc, antigo, gen, novo, plano.mudancas)
    plano.sem_xml = [c for k, c in atuais.items() if k not in usados]
    plano.revisar = [a for a in res.revisar if not a["bloqueia"]
                     and (a["documento"] in ondes
                          or a["documento"] in CADASTRO)]
    plano.cadastro = _cadastro_novo(doc, gen, plano)
    return plano


def _comparar(doc, antigo, gen, novo, mudancas):
    """Conta, campo a campo, o que muda no C100 e nos C170 (pelo número do
    item) — é o que a prévia mostra."""
    def valores(d, r):
        out = {}
        for nome in _nomes(d, r.reg):
            i = d._ix(r.reg, nome)
            if i is not None and i < len(r.campos):
                out[nome] = (r.valor(i) or "").strip()
        return out

    def conta(reg, a, b):
        for nome in set(a) | set(b):
            if not _iguais(a.get(nome, ""), b.get(nome, "")):
                k = "%s.%s" % (reg, nome)
                mudancas[k] = mudancas.get(k, 0) + 1

    conta("C100", valores(doc, antigo), valores(gen, novo))
    i_doc, i_gen = doc._ix("C170", "NUM_ITEM"), gen._ix("C170", "NUM_ITEM")

    def itens(d, c, i):
        return {(f.valor(i) or "").strip().lstrip("0"): f for f in c.filhos
                if f.reg == "C170"}
    a, b = itens(doc, antigo, i_doc), itens(gen, novo, i_gen)
    for num in set(a) | set(b):
        if num not in a or num not in b:
            k = "C170 (itens %s)" % ("novos" if num not in a else "retirados")
            mudancas[k] = mudancas.get(k, 0) + 1
            continue
        conta("C170", valores(doc, a[num]), valores(gen, b[num]))


def _iguais(a, b):
    """`0`, `0,00` e vazio são o mesmo valor; texto compara como texto."""
    if a == b:
        return True
    if RE_NUM_SPED.match(a or "0") and RE_NUM_SPED.match(b or "0"):
        return abs(_to_num(a) - _to_num(b)) < 0.0005
    return False


def _nomes(doc, reg):
    return [n for n in campos_do_leiaute(reg, doc.layout, 0)[1:]
            if not n.startswith("Campo ")]


def _cadastro_novo(doc, gen, plano):
    """Registros de cadastro que os documentos regenerados usam e o arquivo
    ainda não tem."""
    existentes = {}
    for reg, chave in CADASTRO.items():
        i = doc._ix(reg, chave)
        existentes[reg] = {(r.valor(i) or "").strip() for r in doc.registros
                           if r.reg == reg and i is not None}
    usado = {"0150": set(), "0200": set(), "0190": set(), "0400": set(),
             "0500": set()}
    i_part = gen._ix("C100", "COD_PART")
    i7 = {c: gen._ix("C170", c) for c in ("COD_ITEM", "UNID", "COD_NAT",
                                         "COD_CTA")}
    novos = [n for _a, n in plano.substituir] + plano.incluir
    for c100 in novos:
        usado["0150"].add((c100.valor(i_part) or "").strip())
        for f in c100.filhos:
            if f.reg != "C170":
                continue
            for reg, campo in (("0200", "COD_ITEM"), ("0190", "UNID"),
                               ("0400", "COD_NAT"), ("0500", "COD_CTA")):
                if i7[campo] is not None:
                    usado[reg].add((f.valor(i7[campo]) or "").strip())
    i_unid_0200 = gen._ix("0200", "UNID_INV")
    i_cod_0200 = gen._ix("0200", "COD_ITEM")
    for r in gen.registros:
        if r.reg == "0200" and (r.valor(i_cod_0200) or "").strip() in \
                usado["0200"]:
            usado["0190"].add((r.valor(i_unid_0200) or "").strip())
    saida = []
    for reg, chave in CADASTRO.items():
        i = gen._ix(reg, chave)
        for r in gen.registros:
            if r.reg != reg or i is None:
                continue
            k = (r.valor(i) or "").strip()
            if k and k in usado[reg] and k not in existentes[reg]:
                saida.append(r)
                existentes[reg].add(k)
    return saida


# ---------------------------------------------------------------- aplicar
def aplicar(doc, plano):
    """Grava o plano no arquivo. Devolve `{"substituidos", "incluidos",
    "cadastro"}`."""
    if plano.vazio:
        return {"substituidos": 0, "incluidos": 0, "cadastro": 0}
    with doc.lote():
        r0001 = next((r for r in doc.registros if r.reg == "0001"), None)
        for g in plano.cadastro:
            if r0001 is None:
                break
            irmaos = [f for f in r0001.filhos if f.reg == g.reg]
            depois = max(irmaos, key=lambda x: x.ordem) if irmaos else \
                doc._ancora_antes(r0001, g.reg)
            _copiar(doc, g, r0001, depois)
        for antigo, novo in plano.substituir:
            _copiar(doc, novo, antigo.pai, antigo)
            doc.remover_registro(antigo)
        if plano.incluir:
            pai, depois = _onde_incluir(doc)
            for novo in plano.incluir:
                depois = _copiar(doc, novo, pai, depois)
    return {"substituidos": len(plano.substituir),
            "incluidos": len(plano.incluir), "cadastro": len(plano.cadastro)}


def _onde_incluir(doc):
    """Documento novo entra depois do último C100 — dentro do C010 no EFD
    Contribuições, do C001 no ICMS/IPI."""
    c100 = [r for r in doc.registros if r.reg == "C100"]
    if c100:
        ultimo = max(c100, key=lambda x: x.ordem)
        return ultimo.pai, ultimo
    pai = next((r for r in doc.registros if r.reg == "C010"), None) or \
        next((r for r in doc.registros if r.reg == "C001"), None)
    if pai is None:
        raise ValueError("O arquivo não tem o bloco C aberto.")
    i = doc._ix(pai.reg, "IND_MOV")
    if pai.reg == "C001" and i is not None:
        pai.set_valor(i, "0")
    return pai, doc._ancora_antes(pai, "C100")


def _copiar(doc, origem, pai, depois):
    """Copia o registro gerado (e a subárvore) para o arquivo; devolve o
    novo. A largura é a do arquivo: o que sobrar vazio no fim cai."""
    novo = doc.novo_registro(origem.reg, pai=pai, depois=depois)
    vals = list(origem.campos)
    while len(vals) > len(novo.campos) and vals[-1] == "":
        vals.pop()
    doc._preencher(novo, vals)
    ant = novo
    for f in sorted(origem.filhos, key=lambda x: x.ordem):
        ant = _copiar(doc, f, novo, ant)
    return novo

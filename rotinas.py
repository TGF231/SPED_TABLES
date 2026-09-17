# -*- coding: utf-8 -*-
"""Rotinas de conferência e correção baseadas no regime da empresa.

Extensível como `revisao.REGRAS`: cada rotina é um objeto `Rotina` na lista
`ROTINAS`, com uma função de **verificação** (nunca altera o arquivo) e, quando
a correção é objetiva, uma de **correção** que recebe as ocorrências já
apuradas. A GUI sempre mostra o relatório antes de deixar corrigir.

Por que a correção recebe as ocorrências em vez de varrer de novo: o usuário
revisa a lista, e o que for aplicado tem de ser exatamente o que ele viu — não
um segundo diagnóstico feito num arquivo que pode ter mudado no meio.

## As regras fiscais codificadas aqui

- **Cumulativo** (em regra, Lucro Presumido e Simples): PIS 0,65%, COFINS 3,00%
  e **sem direito a crédito** nas entradas.
- **Não-cumulativo** (em regra, Lucro Real): PIS 1,65%, COFINS 7,6%, com
  crédito nas entradas.
- **Ambos**: a empresa tem receita nos dois regimes; a alíquota sozinha não
  identifica erro, então as rotinas que dependem dela se abstêm.

A verificação de alíquota só olha **CST 01** (tributável à alíquota básica).
CST 02 é justamente "alíquota diferenciada", e 03 é por quantidade — cobrar
deles a alíquota nominal produziria falso positivo.
"""

from dataclasses import dataclass, field

from sped_model import _to_num, _fmt_val, _fmt_aliq

# ------------------------------------------------------------ conjuntos CST
# Saída tributada à alíquota básica: é onde a alíquota nominal se aplica.
CST_SAIDA_ALIQ_BASICA = {"01"}
# Entrada com apropriação de crédito (vinculado a receita, presumido…).
CST_ENTRADA_COM_CREDITO = {"50", "51", "52", "53", "54", "55", "56",
                           "60", "61", "62", "63", "64", "65", "66"}
# Entrada que **não** dá direito a crédito: 70-75 (aquisição sem direito),
# 98 (outras operações de entrada) e 99 (outras operações).
CST_ENTRADA_SEM_CREDITO = {"70", "71", "72", "73", "74", "75", "98", "99"}


@dataclass
class Ocorrencia:
    """Um ponto do arquivo que contraria o regime da empresa."""
    uid: int
    reg: str
    escopo: str          # "entrada" ou "saída"
    doc: str             # número do documento (C100)
    item: str            # NUM_ITEM (C170) ou CFOP (C175)
    tributo: str         # "PIS" ou "COFINS"
    campo: str           # campo que será alterado pela correção
    atual: str
    esperado: str
    detalhe: str = ""


@dataclass
class Rotina:
    id: str
    nome: str
    descricao: str
    layouts: tuple
    verificar: object
    corrigir: object = None
    rotulo_correcao: str = ""
    # rotinas que dependem de recurso externo (tabelas da RFB) declaram aqui
    requer: str = ""


# --------------------------------------------------------------- utilidades
def _idx(doc, tipo, *nomes):
    return tuple(doc._ix(tipo, n) for n in nomes)


def _itens_por_operacao(doc):
    """Percorre os C170 devolvendo (c170, c100, entrada?) e os C175 idem.

    O tipo de operação mora no **C100 pai** (IND_OPER), não no item — por isso
    a varredura é feita a partir do documento, e não filtrando registros soltos.
    """
    i_op = doc._ix("C100", "IND_OPER")
    i_num = doc._ix("C100", "NUM_DOC")
    for c100 in doc.registros:
        if c100.reg != "C100":
            continue
        entrada = (c100.valor(i_op) or "").strip() == "0"
        num = (c100.valor(i_num) or "").strip() if i_num is not None else ""
        for filho in getattr(c100, "filhos", []) or []:
            if filho.reg in ("C170", "C175"):
                yield filho, num, entrada


def _aliq_igual(a, b):
    """Compara alíquotas pelo valor, não pelo texto: '7,60' == '7,6'."""
    return abs(_to_num(a) - _to_num(b)) < 0.0001


def _par_tributo(doc, tipo, tributo):
    """(cst, vl_bc, aliq, vl) do tributo no registro, por nome."""
    if tributo == "PIS":
        return _idx(doc, tipo, "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS")
    return _idx(doc, tipo, "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS",
                "VL_COFINS")


def _rotulo_item(reg, doc_num, registro, doc):
    if reg == "C170":
        i = doc._ix("C170", "NUM_ITEM")
        return (registro.valor(i) or "").strip() if i is not None else ""
    i = doc._ix("C175", "CFOP")
    return "CFOP %s" % ((registro.valor(i) or "").strip()
                        if i is not None else "")


# ================================================================ rotina 1
def verificar_aliquota_saida(doc, empresa):
    """Saída tributada com alíquota fora do regime declarado."""
    if doc.layout != "CONTRIB" or empresa is None or empresa.ambos_regimes:
        return []
    esperado = {"PIS": empresa.aliq_pis_saida,
                "COFINS": empresa.aliq_cofins_saida}
    achados = []
    for reg, num, entrada in _itens_por_operacao(doc):
        if entrada:
            continue
        for tributo in ("PIS", "COFINS"):
            i_cst, _i_bc, i_aliq, _i_vl = _par_tributo(doc, reg.reg, tributo)
            if i_cst is None or i_aliq is None:
                continue
            cst = (reg.valor(i_cst) or "").strip()
            if cst not in CST_SAIDA_ALIQ_BASICA:
                continue
            atual = (reg.valor(i_aliq) or "").strip()
            alvo = esperado[tributo]
            if not alvo or not atual or _aliq_igual(atual, alvo):
                continue
            achados.append(Ocorrencia(
                uid=reg.uid, reg=reg.reg, escopo="saída", doc=num,
                item=_rotulo_item(reg.reg, num, reg, doc), tributo=tributo,
                campo="ALIQ_%s" % tributo, atual=atual, esperado=alvo,
                detalhe="CST %s (alíquota básica) no regime %s"
                        % (cst, empresa.regime_pis_cofins)))
    return achados


def corrigir_aliquota(doc, empresa, ocorrencias):
    """Grava a alíquota esperada e recalcula o valor (base × alíquota)."""
    n = 0
    por_uid = {r.uid: r for r in doc.registros}
    for oc in ocorrencias:
        reg = por_uid.get(oc.uid)
        if reg is None:
            continue
        _i_cst, i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, oc.tributo)
        if i_aliq is None:
            continue
        reg.set_valor(i_aliq, oc.esperado)
        if i_bc is not None and i_vl is not None:
            base = _to_num(reg.valor(i_bc))
            reg.set_valor(i_vl, _fmt_val(round(base * _to_num(oc.esperado)
                                               / 100.0, 2)))
        n += 1
    return n


# ================================================================ rotina 2
def verificar_credito_indevido(doc, empresa):
    """Crédito apropriado na entrada por empresa do regime cumulativo.

    No cumulativo não há direito a crédito: CST de creditamento com valor
    lançado é apropriação indevida.
    """
    if doc.layout != "CONTRIB" or empresa is None or not empresa.cumulativo:
        return []
    achados = []
    for reg, num, entrada in _itens_por_operacao(doc):
        if not entrada or reg.reg != "C170":
            continue
        for tributo in ("PIS", "COFINS"):
            i_cst, i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, tributo)
            if i_cst is None:
                continue
            cst = (reg.valor(i_cst) or "").strip()
            if cst not in CST_ENTRADA_COM_CREDITO:
                continue
            valor = _to_num(reg.valor(i_vl)) if i_vl is not None else 0.0
            aliq = _to_num(reg.valor(i_aliq)) if i_aliq is not None else 0.0
            if valor <= 0 and aliq <= 0:
                continue        # CST de crédito mas sem valor: nada a retirar
            achados.append(Ocorrencia(
                uid=reg.uid, reg=reg.reg, escopo="entrada", doc=num,
                item=_rotulo_item(reg.reg, num, reg, doc), tributo=tributo,
                campo="CST_%s" % tributo, atual=cst,
                esperado=empresa.cst_entrada_sem_credito,
                detalhe="crédito de %s lançado (%s) em empresa cumulativa"
                        % (_fmt_val(valor), "alíq. %s" % _fmt_aliq(aliq))))
    return achados


def corrigir_credito_indevido(doc, empresa, ocorrencias):
    """Retira o crédito: zera base, alíquota e valor, e troca o CST.

    O CST de destino vem do cadastro (`cst_entrada_sem_credito`, 70 por padrão
    — "operação de aquisição sem direito a crédito"), porque o código correto
    varia com o motivo da vedação.
    """
    n = 0
    por_uid = {r.uid: r for r in doc.registros}
    for oc in ocorrencias:
        reg = por_uid.get(oc.uid)
        if reg is None:
            continue
        i_cst, i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, oc.tributo)
        if i_cst is None:
            continue
        reg.set_valor(i_cst, oc.esperado)
        for idx, zero in ((i_bc, _fmt_val(0)), (i_aliq, ""),
                          (i_vl, _fmt_val(0))):
            if idx is not None:
                reg.set_valor(idx, zero)
        n += 1
    return n


# ================================================================ rotina 3
def verificar_aliquota_credito(doc, empresa):
    """Entrada com crédito a alíquota diferente da do regime não-cumulativo.

    O erro típico é a entrada ficar com a alíquota de saída (ou com a do
    fornecedor) em vez da alíquota de crédito do comprador.
    """
    if doc.layout != "CONTRIB" or empresa is None or not empresa.nao_cumulativo:
        return []
    esperado = {"PIS": empresa.aliq_pis_credito,
                "COFINS": empresa.aliq_cofins_credito}
    achados = []
    for reg, num, entrada in _itens_por_operacao(doc):
        if not entrada or reg.reg != "C170":
            continue
        for tributo in ("PIS", "COFINS"):
            i_cst, _i_bc, i_aliq, _i_vl = _par_tributo(doc, reg.reg, tributo)
            if i_cst is None or i_aliq is None:
                continue
            cst = (reg.valor(i_cst) or "").strip()
            if cst not in CST_ENTRADA_COM_CREDITO:
                continue
            atual = (reg.valor(i_aliq) or "").strip()
            alvo = esperado[tributo]
            # alíquota vazia/zero com CST de crédito é outro problema (crédito
            # não apropriado), fora do escopo desta rotina
            if not alvo or not atual or _to_num(atual) <= 0:
                continue
            if _aliq_igual(atual, alvo):
                continue
            achados.append(Ocorrencia(
                uid=reg.uid, reg=reg.reg, escopo="entrada", doc=num,
                item=_rotulo_item(reg.reg, num, reg, doc), tributo=tributo,
                campo="ALIQ_%s" % tributo, atual=atual, esperado=alvo,
                detalhe="CST %s (crédito) fora da alíquota do regime" % cst))
    return achados


# ================================================================ rotina 4
def verificar_cst_ncm(doc, empresa, classificador=None, data_ref=None):
    """CST incoerente com a classificação do NCM (monofásico / alíquota zero).

    Reaproveita `tabelas_rfb.verificar_cst_pis_cofins`. Não tem correção
    automática: o CST correto depende do produto e do motivo, e o próprio
    módulo só **sugere** um valor.
    """
    if doc.layout != "CONTRIB" or classificador is None:
        return []
    import tabelas_rfb as trfb
    achados = []
    for p in trfb.verificar_cst_pis_cofins(doc, classificador,
                                           data_ref=data_ref):
        achados.append(Ocorrencia(
            uid=p["uid"], reg="C170",
            escopo="entrada" if p["op"] == "E" else "saída",
            doc="", item=p["cod_item"], tributo="PIS/COFINS",
            campo="CST_PIS / CST_COFINS", atual=p["detalhe"],
            esperado=p.get("cst_sugerido", ""),
            detalhe="NCM %s — %s" % (p["ncm"], p["classe_desc"])))
    return achados


# ================================================================ rotina 5
def verificar_credito_em_cst_sem_direito(doc, empresa):
    """Entrada com CST sem direito a crédito, mas com base/valor lançados.

    Achado em arquivo real: 256 itens com **CST 70** ("operação de aquisição
    sem direito a crédito") trazendo base de cálculo, alíquota e valor de
    PIS/COFINS preenchidos. Os dois não podem conviver — ou há direito ao
    crédito, e o CST deveria ser 50-56, ou não há, e os campos de valor
    deveriam estar zerados.

    Na prática o crédito não é aproveitado, porque a apuração soma pelos CST
    de creditamento; o problema é de **coerência da escrituração**, e é o tipo
    de coisa que o fisco pergunta. Vale para qualquer regime: nem o
    não-cumulativo aproveita crédito num CST 70.
    """
    if doc.layout != "CONTRIB":
        return []
    achados = []
    for reg, num, entrada in _itens_por_operacao(doc):
        if not entrada or reg.reg != "C170":
            continue
        for tributo in ("PIS", "COFINS"):
            i_cst, i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, tributo)
            if i_cst is None:
                continue
            cst = (reg.valor(i_cst) or "").strip()
            if cst not in CST_ENTRADA_SEM_CREDITO:
                continue
            base = _to_num(reg.valor(i_bc)) if i_bc is not None else 0.0
            valor = _to_num(reg.valor(i_vl)) if i_vl is not None else 0.0
            if base <= 0 and valor <= 0:
                continue
            achados.append(Ocorrencia(
                uid=reg.uid, reg=reg.reg, escopo="entrada", doc=num,
                item=_rotulo_item(reg.reg, num, reg, doc), tributo=tributo,
                campo="VL_BC_%s / VL_%s" % (tributo, tributo),
                atual="base %s / valor %s" % (_fmt_val(base), _fmt_val(valor)),
                esperado="0,00",
                detalhe="CST %s não dá direito a crédito" % cst))
    return achados


def corrigir_zerar_credito(doc, empresa, ocorrencias):
    """Zera base, alíquota e valor, preservando o CST informado.

    Ao contrário da rotina de crédito indevido, aqui o **CST não é alterado**:
    ele já diz que não há crédito; o que está sobrando são os valores.
    """
    n = 0
    por_uid = {r.uid: r for r in doc.registros}
    for oc in ocorrencias:
        reg = por_uid.get(oc.uid)
        if reg is None:
            continue
        _i_cst, i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, oc.tributo)
        for idx, zero in ((i_bc, _fmt_val(0)), (i_aliq, ""),
                          (i_vl, _fmt_val(0))):
            if idx is not None:
                reg.set_valor(idx, zero)
        n += 1
    return n


# ------------------------------------------------------------------- lista
ROTINAS = [
    Rotina(
        id="aliq_saida",
        nome="Alíquota de saída fora do regime",
        descricao="Itens de saída com CST 01 (alíquota básica) cuja alíquota "
                  "de PIS/COFINS não é a do regime declarado.",
        layouts=("CONTRIB",),
        verificar=verificar_aliquota_saida,
        corrigir=corrigir_aliquota,
        rotulo_correcao="Aplicar a alíquota do regime e recalcular o valor",
    ),
    Rotina(
        id="credito_indevido",
        nome="Crédito indevido na entrada (regime cumulativo)",
        descricao="Entradas com CST de creditamento (50-56, 60-66) e valor "
                  "lançado numa empresa do regime cumulativo, que não dá "
                  "direito a crédito.",
        layouts=("CONTRIB",),
        verificar=verificar_credito_indevido,
        corrigir=corrigir_credito_indevido,
        rotulo_correcao="Retirar o crédito (zera base/alíquota/valor e troca "
                        "o CST)",
    ),
    Rotina(
        id="aliq_credito",
        nome="Alíquota de crédito fora do regime (entradas)",
        descricao="Entradas com CST de crédito cuja alíquota difere da do "
                  "regime não-cumulativo — tipicamente ficaram com a "
                  "alíquota de saída.",
        layouts=("CONTRIB",),
        verificar=verificar_aliquota_credito,
        corrigir=corrigir_aliquota,
        rotulo_correcao="Aplicar a alíquota de crédito e recalcular o valor",
    ),
    Rotina(
        id="cst_sem_direito",
        nome="Valor lançado em CST sem direito a crédito (entradas)",
        descricao="Entradas cujo CST de PIS/COFINS é de aquisição sem direito "
                  "a crédito (70-75, 98, 99), mas que trazem base e valor "
                  "preenchidos. Vale para qualquer regime.",
        layouts=("CONTRIB",),
        verificar=verificar_credito_em_cst_sem_direito,
        corrigir=corrigir_zerar_credito,
        rotulo_correcao="Zerar base, alíquota e valor (mantendo o CST)",
    ),
    Rotina(
        id="cst_ncm",
        nome="CST incoerente com o NCM (monofásico / alíquota zero)",
        descricao="Confere o CST de PIS/COFINS contra a classificação do NCM "
                  "nas tabelas da RFB. Sem correção automática: o CST correto "
                  "depende do produto.",
        layouts=("CONTRIB",),
        verificar=verificar_cst_ncm,
        corrigir=None,
        requer="tabelas_rfb",
    ),
]


def aplicaveis(doc, empresa):
    """Rotinas que fazem sentido para este arquivo e esta empresa."""
    if doc is None:
        return []
    return [r for r in ROTINAS if doc.layout in r.layouts]


def executar(doc, empresa, rotina, **extra):
    """Roda a verificação de uma rotina, tolerando recurso externo ausente."""
    try:
        return rotina.verificar(doc, empresa, **extra), ""
    except TypeError:
        # rotina que não aceita os extras (ex.: classificador)
        return rotina.verificar(doc, empresa), ""
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)

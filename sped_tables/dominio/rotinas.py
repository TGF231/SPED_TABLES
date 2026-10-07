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

import inspect
from dataclasses import dataclass

from sped_tables.dominio import ncm
from sped_tables.dominio import referencias, revisao
from sped_tables.dominio.sped_model import _to_num, _fmt_val, _fmt_aliq

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
    i = doc._ix(reg if reg in ("C175", "C190") else "C175", "CFOP")
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
        # ultima barreira: o valor vem do cadastro (texto livre) e vai
        # direto para o campo do arquivo
        reg.set_valor(i_aliq, _fmt_aliq(_to_num(oc.esperado))
                      if oc.esperado else "")
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

    Reaproveita `ncm.verificar_cst_pis_cofins`. Não tem correção
    automática: o CST correto depende do produto e do motivo, e o próprio
    módulo só **sugere** um valor.
    """
    if doc.layout != "CONTRIB" or classificador is None:
        return []
    achados = []
    for p in ncm.verificar_cst_pis_cofins(doc, classificador,
                                          data_ref=data_ref):
        achados.append(Ocorrencia(
            uid=p["uid"], reg="C170",
            escopo="entrada" if p["op"] == "E" else "saída",
            doc="", item=p["cod_item"], tributo="PIS/COFINS",
            campo="CST_PIS / CST_COFINS", atual=p["detalhe"],
            esperado=p.get("cst_sugerido", ""),
            detalhe="NCM %s — %s" % (p["ncm"], p["classe_desc"])))
    return achados


def corrigir_cst_ncm(doc, empresa, ocorrencias):
    """Retira o crédito das **entradas** cujo NCM não o admite.

    Só age onde o crédito está de fato sendo tomado: para cada tributo, se o
    CST atual é de creditamento (50-56, 60-66), troca pelo CST sugerido pela
    classificação do NCM e zera base, alíquota e valor. Monofásico e alíquota
    zero não geram crédito na revenda — manter o CST de crédito com valor é a
    apropriação indevida clássica.

    O que já está num CST sem crédito não é tocado: ali o CST pode ser 70, 73
    ou 98 conforme o motivo da vedação, e trocar um pelo outro sem saber o
    motivo seria palpite. Quem zera valores sobrando nesses casos é a rotina
    `cst_sem_direito`.

    **Saídas ficam de fora.** A sugestão existe (04, 06, 01), mas lá o CST
    depende de o produto ser revenda ou produção própria, e alíquota
    diferenciada (02/03) é legítima — corrigir em massa erraria.
    """
    n = 0
    por_uid = {r.uid: r for r in doc.registros}
    for oc in ocorrencias:
        if oc.escopo != "entrada":
            continue
        reg = por_uid.get(oc.uid)
        if reg is None:
            continue
        destino = (oc.esperado or "").strip()
        if not destino and empresa is not None:
            destino = empresa.cst_entrada_sem_credito
        if not destino:
            continue
        for tributo in ("PIS", "COFINS"):
            i_cst, i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, tributo)
            if i_cst is None:
                continue
            cst = (reg.valor(i_cst) or "").strip()
            if cst not in CST_ENTRADA_COM_CREDITO:
                continue
            reg.set_valor(i_cst, destino)
            for i in (i_bc, i_vl):
                if i is not None:
                    reg.set_valor(i, _fmt_val(0))
            if i_aliq is not None:
                reg.set_valor(i_aliq, "")
            n += 1
    return n


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


# ================================================================ rotina 6
def verificar_cfop_sem_credito(doc, empresa=None, data_ref=None):
    """Crédito tomado num **CFOP que não admite crédito**.

    O PVA publica a tabela `CFOP_CREDITO` (4.3.7) com os 89 CFOP de entrada
    que geram crédito de PIS/COFINS, cada um com a natureza da base. Crédito
    lançado fora dessa lista é advertência do validador
    (`MSG_COMPATIBILIDADE_CFOP_CRED`). Num arquivo real de supermercado foram
    **20 ocorrências** — 10 itens, PIS e COFINS —, todas em CFOP 1910
    (bonificação, doação ou brinde) e 1949 (outra entrada não especificada):
    mercadoria que entrou sem custo não gera crédito.

    Sem a tabela instalada a rotina não roda: aprovar no escuro seria pior.
    """
    if doc.layout != "CONTRIB":
        return []
    if data_ref is None:
        data_ref = doc.data_final()
    cfops, _versao = referencias.atual().cfops_com_credito(data_ref)
    if not cfops:
        return []
    sem_credito = (getattr(empresa, "cst_entrada_sem_credito", "") or "70") \
        if empresa is not None else "70"

    achados = []
    for reg, num, entrada in _itens_por_operacao(doc):
        if not entrada:
            continue
        i_cfop = doc._ix(reg.reg, "CFOP")
        if i_cfop is None:
            continue
        cfop = (reg.valor(i_cfop) or "").strip()
        if not cfop or cfop in cfops:
            continue
        for tributo in ("PIS", "COFINS"):
            i_cst, _i_bc, i_aliq, i_vl = _par_tributo(doc, reg.reg, tributo)
            if i_cst is None:
                continue
            cst = (reg.valor(i_cst) or "").strip()
            if cst not in CST_ENTRADA_COM_CREDITO:
                continue
            valor = _to_num(reg.valor(i_vl)) if i_vl is not None else 0.0
            aliq = _to_num(reg.valor(i_aliq)) if i_aliq is not None else 0.0
            achados.append(Ocorrencia(
                uid=reg.uid, reg=reg.reg, escopo="entrada", doc=num,
                item=_rotulo_item(reg.reg, num, reg, doc), tributo=tributo,
                campo="CST_%s" % tributo, atual=cst, esperado=sem_credito,
                detalhe="CFOP %s não consta da tabela de CFOP com direito a "
                        "crédito (crédito de %s, alíq. %s)"
                        % (cfop, _fmt_val(valor), _fmt_aliq(aliq))))
    return achados


# ================================================================ rotina 7
# CSOSN que não é CST: inválidos como situação (101 → origem 1 + "01", que
# não existe) ou lidos como monofásico de combustível (x02) sem alíquota —
# exatamente o que o PVA recusa (MSG_VALIDA_CST_ALIQ_ICMS_C170_CST_FINAL_2).
# 300, 400 e 500 também são CST válidos (origem 3/4/5 + 00) e ficam de fora:
# ali a leitura como CSOSN seria palpite.
CSOSN_INVALIDOS_COMO_CST = {"101", "103", "201", "203", "900"}
CSOSN_LIDOS_COMO_X02 = {"102", "202"}


def _e_csosn(cst, aliq):
    if cst in CSOSN_INVALIDOS_COMO_CST:
        return True
    return cst in CSOSN_LIDOS_COMO_X02 and not _to_num(aliq)


def verificar_csosn_no_cst(doc, empresa):
    """Entradas com o **CSOSN do fornecedor do Simples** no `CST_ICMS`.

    O CST que a empresa escritura sai do cadastro: a tabela CSOSN → situação,
    a origem padrão e a situação da compra com ST (CFOP 1403/2403). Valem os
    C170 e, no ICMS/IPI, os C190 do mesmo documento — que agrupam pelo mesmo
    CST e precisam acompanhar a troca. Sem a conversão ligada no cadastro, a
    rotina só aponta.
    """
    i_oper = doc._ix("C100", "IND_OPER")
    i_num = doc._ix("C100", "NUM_DOC")
    idx = {reg: tuple(doc._ix(reg, c) for c in ("CST_ICMS", "CFOP",
                                                 "ALIQ_ICMS"))
           for reg in ("C170", "C190")}
    achados = []
    for c100 in doc.registros:
        if c100.reg != "C100" or (c100.valor(i_oper) or "").strip() != "0":
            continue
        num = (c100.valor(i_num) or "").strip()
        for f in c100.filhos:
            ix = idx.get(f.reg)
            if ix is None or None in ix:
                continue
            i_cst, i_cfop, i_aliq = ix
            cst = (f.valor(i_cst) or "").strip()
            if not _e_csosn(cst, f.valor(i_aliq)):
                continue
            cfop = (f.valor(i_cfop) or "").strip()
            esperado = ""
            if empresa is not None and empresa.converter_csosn:
                esperado = empresa.cst_do_csosn(cst, cfop) or ""
            achados.append(Ocorrencia(
                uid=f.uid, reg=f.reg, escopo="entrada", doc=num,
                item=_rotulo_item(f.reg, num, f, doc), tributo="ICMS",
                campo="CST_ICMS", atual=cst, esperado=esperado,
                detalhe="CSOSN do fornecedor do Simples no lugar do CST "
                        "(CFOP %s)%s" % (cfop, "" if esperado else
                                         " — sem regra no cadastro")))
    return achados


def corrigir_csosn_no_cst(doc, empresa, ocorrencias):
    """Troca o CSOSN pelo CST do cadastro. No ICMS/IPI, C190 que passarem a
    ter a mesma chave (CST, CFOP, alíquota) no documento são somados num só —
    dois C190 de mesma chave o PVA recusa. Devolve quantos registros mudaram.
    """
    por_uid = {r.uid: r for r in doc.registros}
    i_cst = {reg: doc._ix(reg, "CST_ICMS") for reg in ("C170", "C190")}
    mudou = 0
    pais = []
    for o in ocorrencias:
        r = por_uid.get(o.uid)
        if r is None or not o.esperado or r.reg not in i_cst:
            continue
        if (r.valor(i_cst[r.reg]) or "").strip() != o.atual:
            continue                      # o arquivo mudou desde a verificação
        r.set_valor(i_cst[r.reg], o.esperado)
        mudou += 1
        if r.reg == "C190" and r.pai is not None and r.pai not in pais:
            pais.append(r.pai)
    for c100 in pais:
        _fundir_c190(doc, c100)
    if mudou:
        doc.atualizar_bloco9_inplace()
    return mudou


C190_SOMAS = ("VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
              "VL_ICMS_ST", "VL_RED_BC", "VL_IPI")


def _fundir_c190(doc, c100):
    soma_ix = [doc._ix("C190", c) for c in C190_SOMAS]
    vistos = {}
    for f in [x for x in c100.filhos if x.reg == "C190"]:
        k = doc.chave_c190(f)
        if k not in vistos:
            vistos[k] = f
            continue
        alvo = vistos[k]
        for i in soma_ix:
            if i is not None:
                alvo.set_valor(i, _fmt_val(_to_num(alvo.valor(i))
                                           + _to_num(f.valor(i))))
        doc.remover_registro(f)


# ================================================================ rotina 8
# Código de receita do PIS/COFINS a recolher (M205/M605) pelo campo do M200
# que o originou: 08 = contribuição não cumulativa, 12 = cumulativa. São os
# códigos de DARF da pessoa jurídica em geral (6912-01/5856-01 e
# 8109-02/2172-01), com a variação de 2 dígitos que o leiaute pede.
COD_REC_CONTRIB = {
    ("M205", "08"): "691201", ("M605", "08"): "585601",
    ("M205", "12"): "810902", ("M605", "12"): "217201",
}


def verificar_cod_rec(doc, empresa):
    """Código de receita **em branco** no débito a recolher: E116 (ICMS),
    M205/M605 (PIS/COFINS). O PVA cobra o campo (`MSG_CAMPO_OBRIGATORIO`).

    No ICMS o código depende da UF e da atividade — vem do **cadastro da
    empresa** (seletor com a tabela da UF tirada do PVA); sem ele, a rotina
    só aponta. No PIS/COFINS, sai do campo do M200 de origem."""
    achados = []
    if doc.layout == "ICMS":
        i_rec = doc._ix("E116", "COD_REC")
        i_or = doc._ix("E116", "COD_OR")
        esperado = (getattr(empresa, "cod_rec_icms", "") or "") \
            if empresa is not None else ""
        for r in doc.registros:
            if r.reg != "E116" or i_rec is None:
                continue
            if (r.valor(i_rec) or "").strip():
                continue
            achados.append(Ocorrencia(
                uid=r.uid, reg="E116", escopo="apuração", doc="E116",
                item="COD_OR %s" % (r.valor(i_or) or "").strip(),
                tributo="ICMS", campo="COD_REC", atual="",
                esperado=esperado,
                detalhe="" if esperado else
                "informe o código de receita no cadastro da empresa"))
        return achados
    for reg, tributo in (("M205", "PIS"), ("M605", "COFINS")):
        i_rec = doc._ix(reg, "COD_REC")
        i_campo = doc._ix(reg, "NUM_CAMPO")
        if i_rec is None or i_campo is None:
            continue
        for r in doc.registros:
            if r.reg != reg or (r.valor(i_rec) or "").strip():
                continue
            campo = (r.valor(i_campo) or "").strip()
            esperado = COD_REC_CONTRIB.get((reg, campo), "")
            achados.append(Ocorrencia(
                uid=r.uid, reg=reg, escopo="apuração", doc=reg,
                item="NUM_CAMPO %s" % campo, tributo=tributo,
                campo="COD_REC", atual="", esperado=esperado,
                detalhe="" if esperado else
                "campo %s do M200/M600 sem código conhecido" % campo))
    return achados


def corrigir_campo(doc, empresa, ocorrencias):
    """Grava `esperado` no `campo` de cada ocorrência que tenha esperado."""
    por_uid = {r.uid: r for r in doc.registros}
    n = 0
    for o in ocorrencias:
        r = por_uid.get(o.uid)
        i = doc._ix(r.reg, o.campo) if r is not None else None
        if i is None or not o.esperado:
            continue
        r.set_valor(i, o.esperado)
        n += 1
    return n


# ================================================================ rotina 9
# Bebidas frias (Lei 13.097/2015): na venda pelo **varejista** a alíquota é
# zero — CST 06 com a natureza 918 da tabela 4.3.13. Os códigos 4xx da
# tabela de monofásicos (423/424 da cerveja) são da venda do fabricante, e
# sob o CST 06 o PVA os recusa (MSG_EXISTE_NAT_REC). Num arquivo real: as
# cervejas que o PDV emitiu com CST 02/CFOP 5101 entraram no C175 como 06,
# certo, mas o M410 ficou com 423/424.
NAT_REC_BEBIDAS_FRIAS_VAREJO = "918"
NCM_BEBIDAS_FRIAS = ("210690", "2201", "2202", "2203")


def verificar_nat_rec(doc, empresa):
    """Natureza da receita (M410/M810) fora da tabela do CST do M400/M800.
    A correção só é proposta quando a regra é afirmável: receita de bebida
    fria no CST 06 de empresa de comércio → 918. O resto fica apontado."""
    if doc.layout != "CONTRIB":
        return []
    varejo = empresa is not None and empresa.atividade == "comercio"
    por_uid = {r.uid: r for r in doc.registros}
    achados = []
    for p in revisao.verificar_nat_rec(doc):
        r = por_uid.get(p.uid)
        i_nat = doc._ix(r.reg, "NAT_REC")
        nat = (r.valor(i_nat) or "").strip()
        i_cst = doc._ix(r.pai.reg, "CST_PIS" if r.pai.reg == "M400"
                        else "CST_COFINS")
        cst = (r.pai.valor(i_cst) or "").strip()
        ncms = referencias.atual().ncms_da_natureza(nat)
        bebida = bool(ncms) and all(n.startswith(NCM_BEBIDAS_FRIAS)
                                    for n in ncms)
        esperado = NAT_REC_BEBIDAS_FRIAS_VAREJO \
            if (cst == "06" and bebida and varejo) else ""
        detalhe = ("bebida fria vendida pelo varejista: natureza 918 da "
                   "tabela 4.3.13" if esperado else
                   "a natureza é de outra tabela — confira o CST da venda "
                   "no cadastro do ERP/PDV")
        achados.append(Ocorrencia(
            uid=r.uid, reg=r.reg, escopo="saída", doc=r.pai.reg,
            item="CST %s" % cst,
            tributo="PIS" if r.reg == "M410" else "COFINS",
            campo="NAT_REC", atual=nat, esperado=esperado, detalhe=detalhe))
    return achados


def corrigir_nat_rec(doc, empresa, ocorrencias):
    """Troca a natureza e soma na linha que já tenha a nova natureza sob o
    mesmo M400/M800 — duas linhas de mesma natureza o PVA recusa."""
    por_uid = {r.uid: r for r in doc.registros}
    n = 0
    for o in ocorrencias:
        r = por_uid.get(o.uid)
        if r is None or not o.esperado:
            continue
        i_nat = doc._ix(r.reg, "NAT_REC")
        i_vl = doc._ix(r.reg, "VL_REC")
        if (r.valor(i_nat) or "").strip() != o.atual:
            continue
        irma = next((f for f in r.pai.filhos if f is not r
                     and f.reg == r.reg
                     and (f.valor(i_nat) or "").strip() == o.esperado), None)
        if irma is not None:
            irma.set_valor(i_vl, _fmt_val(_to_num(irma.valor(i_vl))
                                          + _to_num(r.valor(i_vl))))
            doc.remover_registro(r)
        else:
            r.set_valor(i_nat, o.esperado)
        n += 1
    if n:
        doc.atualizar_bloco9_inplace()
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
                  "nas tabelas da RFB. A correção age só nas **entradas** que "
                  "estão tomando crédito num NCM que não o admite; saídas e "
                  "CST sem crédito ficam para conferência manual.",
        layouts=("CONTRIB",),
        verificar=verificar_cst_ncm,
        corrigir=corrigir_cst_ncm,
        rotulo_correcao="Retirar o crédito das entradas (troca o CST e zera "
                        "base/alíquota/valor)",
        requer="tabelas_rfb",
    ),
    Rotina(
        id="cfop_credito",
        nome="Crédito em CFOP que não dá direito (entradas)",
        descricao="Entradas com CST de creditamento num CFOP fora da tabela "
                  "de CFOP com direito a crédito do PVA (4.3.7) — "
                  "bonificação, doação, brinde e outras entradas que não "
                  "geram crédito.",
        layouts=("CONTRIB",),
        verificar=verificar_cfop_sem_credito,
        corrigir=corrigir_credito_indevido,
        rotulo_correcao="Retirar o crédito (zera base/alíquota/valor e troca "
                        "o CST)",
        requer="tabelas_pva",
    ),
    Rotina(
        id="csosn_cst",
        nome="CSOSN do Simples no CST do ICMS (entradas)",
        descricao="Itens e analíticos de entrada com o CSOSN do fornecedor "
                  "do Simples copiado para o CST_ICMS — o PVA lê 102 como "
                  "monofásico de combustível e o recusa sem alíquota. O CST "
                  "certo sai do cadastro da empresa (tabela CSOSN → CST, "
                  "origem e compra com ST).",
        layouts=("ICMS", "CONTRIB"),
        verificar=verificar_csosn_no_cst,
        corrigir=corrigir_csosn_no_cst,
        rotulo_correcao="Trocar o CSOSN pelo CST do cadastro (no ICMS/IPI, "
                        "o C190 acompanha)",
    ),
    Rotina(
        id="cod_rec",
        nome="Código de receita em branco (E116 / M205 / M605)",
        descricao="Débito a recolher sem código de receita. No ICMS o código "
                  "vem do cadastro da empresa; no PIS/COFINS, do campo do "
                  "M200/M600 que gerou o débito.",
        layouts=("ICMS", "CONTRIB"),
        verificar=verificar_cod_rec,
        corrigir=corrigir_campo,
        rotulo_correcao="Preencher o código de receita",
    ),
    Rotina(
        id="nat_rec",
        nome="Natureza da receita fora da tabela do CST (M410/M810)",
        descricao="Natureza da receita que não existe na tabela do CST do "
                  "M400/M800. Bebida fria vendida pelo varejista (empresa "
                  "de comércio) com CST 06 vai para a 918 (Lei 13.097/2015); "
                  "o resto é apontado para conferir o CST no ERP/PDV.",
        layouts=("CONTRIB",),
        verificar=verificar_nat_rec,
        corrigir=corrigir_nat_rec,
        rotulo_correcao="Trocar a natureza (somando na linha que já existir)",
    ),
]


def aplicaveis(doc, empresa):
    """Rotinas que fazem sentido para este arquivo e esta empresa."""
    if doc is None:
        return []
    return [r for r in ROTINAS if doc.layout in r.layouts]


def executar(doc, empresa, rotina, **extra):
    """Roda a verificação de uma rotina, tolerando recurso externo ausente.

    Só os extras que a verificação declara são passados. A versão anterior
    tentava com todos e, num `TypeError`, repetia sem nenhum — mas o
    `TypeError` podia vir de **dentro** da verificação, e a segunda chamada,
    fora do `try`, levava a exceção até o slot do Qt, que derruba o programa.
    """
    try:
        aceitos = inspect.signature(rotina.verificar).parameters
        if not any(p.kind is p.VAR_KEYWORD for p in aceitos.values()):
            extra = {k: v for k, v in extra.items() if k in aceitos}
    except (TypeError, ValueError):
        extra = {}
    try:
        return rotina.verificar(doc, empresa, **extra), ""
    except Exception as exc:  # noqa: BLE001
        return [], "%s: %s" % (type(exc).__name__, exc)

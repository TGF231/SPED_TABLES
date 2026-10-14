# -*- coding: utf-8 -*-
"""
regras_guia.py
--------------
Regras de validação **escritas no guia prático**, reproduzidas com as
condições e as tolerâncias **do próprio PVA**.

Até a 1.0.0-rc.1 o diagnóstico dividia o que o PVA confere em "fiel" (o
declarado no descritor) e "não reproduzido" (as ~1.400 regras compostas).
Boa parte das compostas está escrita por extenso no guia — "a soma dos
valores do campo VL_BC_ICMS dos registros analíticos (C190) deve ser igual
ao valor informado neste campo" —, e o PVA guarda a condição exata em
lugar legível:

* as regras de soma e de existência do EFD ICMS/IPI são **consultas SQL**
  em `descritor/comum/queries/queries.xml`, dentro do `.jar` do descritor.
  É dali que vêm as condições que o guia não diz: o VL_MERC só é cobrado
  quando fica **abaixo** da soma dos itens; a NF-e de emissão própria e a
  NFC-e ficam fora da conferência C190 × C170; o CFOP só é conferido em
  documento regular ou extemporâneo (COD_SIT 00/01);
* a **tolerância** é constante das classes: `TOLERANCIA = 0,5` nas somas do
  ICMS/IPI (`EnumComparadoresSql`) e `0,99` no VL_PIS/VL_COFINS do
  Contribuições (`RegraVlPisCofinsAbstrata`), que além disso é só
  **advertência**.

Cada regra diz de onde vem (registro/campo do guia, a ajuda F1 mostra o
texto), quais validadores do PVA reproduz (`pva`, ids do descritor — o
diagnóstico deixa de listá-los como "só o PVA verifica") e quem corrige.
Todas foram passadas nos arquivos reais que o PVA validou: regra que acusa
o que o PVA aceita é pior que regra nenhuma.
"""

from sped_tables.dominio import referencias
from sped_tables.dominio.revisao import Problema
from sped_tables.dominio.sped_model import (_fmt_val, _to_num,
                                            data_aaaammdd, so_digitos)

# tolerâncias do PVA (ver o cabeçalho)
TOLERANCIA_ICMS = 0.5
TOLERANCIA_PIS_COFINS = 0.99
# comparação "exata" de valores de duas casas: meio centavo absorve o
# resíduo de ponto flutuante
TOLERANCIA_CENTAVO = 0.005

# documento regular ou extemporâneo: o único em que o PVA confere CFOP e as
# combinações do analítico
SITUACOES_CONFERIDAS = ("00", "01")

# códigos de UF do IBGE (os dois primeiros dígitos do município e da chave)
UF_IBGE = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16",
    "TO": "17", "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25",
    "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
    "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50",
    "MT": "51", "GO": "52", "DF": "53",
}
PAIS_BRASIL = ("1058", "01058")


class Regra:
    """Uma validação do guia. `fn(doc, regra) -> [Problema]`."""

    __slots__ = ("id", "layouts", "campo", "rotulo", "fn", "pva",
                 "gravidade", "modulo", "onde")

    def __init__(self, id, layouts, campo, rotulo, fn, pva=(),
                 gravidade="erro", modulo="Correção manual na grade",
                 onde=""):
        self.id = id
        self.layouts = layouts
        self.campo = campo
        self.rotulo = rotulo
        self.fn = fn
        self.pva = tuple(pva)
        self.gravidade = gravidade
        self.modulo = modulo
        self.onde = onde

    def verificar(self, doc):
        if doc.layout not in self.layouts:
            return []
        return self.fn(doc, self)

    def problema(self, r, descricao, gravidade=None):
        return Problema(r.uid, r.reg, r.bloco, self.rotulo, descricao,
                        gravidade or self.gravidade)


# ------------------------------------------------------------- utilitários
def _texto(doc, r, nome):
    """Valor do campo, sem espaços; "" sem registro ou sem o campo."""
    i = doc._ix(r.reg, nome) if r is not None else None
    return (r.valor(i) or "").strip() if i is not None else ""


def _num(doc, r, nome):
    return _to_num(_texto(doc, r, nome))


def _tem(doc, r, nome):
    i = doc._ix(r.reg, nome)
    return i is not None and i < len(r.campos)


def _de(doc, *regs):
    alvo = set(regs)
    return [r for r in doc.registros if r.reg in alvo]


def _filhos(r, reg):
    return [f for f in r.filhos if f.reg == reg]


def _difere(a, b, tolerancia=TOLERANCIA_CENTAVO):
    return abs(a - b) > tolerancia + 1e-9


def _abertura(doc):
    return next((r for r in doc.registros if r.reg == "0000"), None)


def _periodo(doc):
    r = _abertura(doc)
    return (data_aaaammdd(_texto(doc, r, "DT_INI")),
            data_aaaammdd(_texto(doc, r, "DT_FIN")))


def _conferido(doc, r):
    return _texto(doc, r, "COD_SIT") in SITUACOES_CONFERIDAS


def _nfe_propria(doc, c100):
    return (_texto(doc, c100, "COD_MOD") == "55"
            and _texto(doc, c100, "IND_EMIT") == "0")


def registros_com_validador(doc, ids, padrao=()):
    """Registros em que o descritor do PVA declara algum dos validadores
    `ids` — a regra vale onde o PVA a aplica. Sem descritor, `padrao`."""
    est, _info = referencias.atual().estrutura(doc.layout)
    if not est:
        return tuple(padrao)
    ids = set(ids)
    return tuple(reg for reg, d in est.items()
                 if ids & set(d.get("validadores", ())))


# ------------------------------------------------------- dígito verificador
def cnpj_valido(v):
    d = so_digitos(v)
    if len(d) != 14 or d == d[0] * 14:
        return False

    def dv(base, pesos):
        s = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return "0" if s < 2 else str(11 - s)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    return d[12] == dv(d[:12], p1) and d[13] == dv(d[:13], p2)


def cpf_valido(v):
    d = so_digitos(v)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for k in (9, 10):
        s = sum(int(d[i]) * (k + 1 - i) for i in range(k)) % 11
        if d[k] != ("0" if s < 2 else str(11 - s)):
            return False
    return True


def chave_dfe_valida(chave):
    """Dígito verificador (módulo 11) da chave de 44 dígitos de NF-e,
    NFC-e e CT-e."""
    if len(chave) != 44 or not chave.isdigit():
        return False
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    s = sum(int(c) * pesos[i % 8] for i, c in enumerate(reversed(chave[:43])))
    resto = s % 11
    return int(chave[43]) == (0 if resto < 2 else 11 - resto)


# ================================================================== regras
PARES_CFOP = {"ICMS": {"C100": ("C170", "C190"), "C500": ("C590",),
                       "D100": ("D190",), "D500": ("D590",)},
              "CONTRIB": {"C100": ("C170",)}}


def _cfop_operacao(doc, regra):
    """O primeiro dígito do CFOP segue o IND_OPER do documento (1/2/3 na
    entrada, 5/6/7 na saída) — só em documento regular ou extemporâneo,
    como na consulta do PVA. NFC-e: o C190 só com CFOP 5, em qualquer
    situação. E os itens de um documento começam todos pelo mesmo dígito
    (aí o PVA acusa o documento)."""
    out = []
    for pai_reg, filhos in PARES_CFOP[doc.layout].items():
        for pai in _de(doc, pai_reg):
            oper = _texto(doc, pai, "IND_OPER")
            esperado = {"0": "123", "1": "567"}.get(oper) \
                if _conferido(doc, pai) else None
            nfce = pai_reg == "C100" and _texto(doc, pai, "COD_MOD") == "65"
            primeiros = set()
            for f in pai.filhos:
                if f.reg not in filhos:
                    continue
                cfop = _texto(doc, f, "CFOP")
                if not cfop:
                    continue
                if f.reg == "C170":
                    primeiros.add(cfop[0])
                if nfce and f.reg == "C190" and cfop[0] != "5":
                    out.append(regra.problema(
                        f, "CFOP %s numa NFC-e: só se admite CFOP iniciado "
                           "com 5" % cfop))
                elif esperado and cfop[0] not in esperado:
                    out.append(regra.problema(
                        f, "CFOP %s em documento de %s: deve começar com %s"
                           % (cfop, "saída" if oper == "1" else "entrada",
                              ", ".join(esperado))))
            if len(primeiros) > 1:
                out.append(regra.problema(
                    pai, "documento %s com itens de CFOP iniciados por %s: "
                         "todos devem começar pelo mesmo dígito"
                         % (_texto(doc, pai, "NUM_DOC"),
                            " e ".join(sorted(primeiros)))))
    return out


def _cfop_nfce_contrib(doc, regra):
    """C175 (NFC-e): só CFOP iniciado com 5."""
    out = []
    for r in _de(doc, "C175"):
        cfop = _texto(doc, r, "CFOP")
        if cfop and cfop[0] != "5":
            out.append(regra.problema(
                r, "CFOP %s numa NFC-e: só se admite CFOP iniciado com 5"
                   % cfop))
    return out


C190_SOMAS = ("VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST")


def _analise_c190(doc):
    """Uma passada pelos C100 do ICMS/IPI, com as condições do PVA:
    `[(c100, sem par, somas divergentes)]`, cada lista com `(registro,
    texto)`.

    * **combinação sem par** (`REGRA_CHAVE_EXISTE_NO_REGISTRO_ITEM`): C190
      sem item da mesma chave e item sem C190 — só documento regular ou
      extemporâneo, e o sentido C190 → C170 não vale para a NFC-e;
    * **soma** (`REGRA_CAMPO_ANALITICO_NO_REGISTRO_ITEM_C190`): base, ICMS,
      base ST e ICMS ST do C190 contra os itens, com a tolerância do PVA.

    NF-e de emissão própria fica fora das duas. As duas regras e o
    *Recalcular C190* leem daqui: as mesmas condições, uma varredura."""
    ix = {reg: [(c, doc._ix(reg, c)) for c in C190_SOMAS]
          for reg in ("C170", "C190")}

    def valores(r):
        return {c: _to_num(r.valor(i)) for c, i in ix[r.reg]}
    out = []
    for c100 in _de(doc, "C100"):
        if _nfe_propria(doc, c100):
            continue
        itens = _filhos(c100, "C170")
        analiticos = _filhos(c100, "C190")
        if not itens and not analiticos:
            continue
        conferido = _conferido(doc, c100)
        sem_par, somas_dif = [], []
        somas = {}
        for f in itens:
            s = somas.setdefault(doc.chave_c190(f),
                                 dict.fromkeys(C190_SOMAS, 0.0))
            for campo, v in valores(f).items():
                s[campo] += v
        de_analiticos = set()
        for a in analiticos:
            k = doc.chave_c190(a)
            de_analiticos.add(k)
            s = somas.get(k)
            if s is None:
                if conferido and _texto(doc, c100, "COD_MOD") != "65":
                    sem_par.append((a, "C190 CST %s / CFOP %s / alíquota %s "
                                       "sem item (C170) dessa combinação"
                                       % (k[0], k[1], _fmt_val(k[2]))))
                continue
            declarado = valores(a)
            difs = ["%s %s (itens: %s)" % (c, _fmt_val(declarado[c]),
                                           _fmt_val(s[c]))
                    for c in C190_SOMAS
                    if _difere(declarado[c], s[c], TOLERANCIA_ICMS)]
            if difs:
                somas_dif.append((a, "; ".join(difs)))
        if conferido:
            for f in itens:
                k = doc.chave_c190(f)
                if k not in de_analiticos:
                    sem_par.append((f, "item %s (CST %s, CFOP %s, alíquota "
                                       "%s) sem C190 dessa combinação" % (
                                           _texto(doc, f, "NUM_ITEM"), k[0],
                                           k[1], _fmt_val(k[2]))))
        out.append((c100, sem_par, somas_dif))
    return out


def _combinacao_c190_c170(doc, regra):
    """Combinação CST/CFOP/alíquota sem par entre C170 e C190."""
    return [regra.problema(r, texto) for _c, sem_par, _s in _analise_c190(doc)
            for r, texto in sem_par]


def _c190_soma_c170(doc, regra):
    """C190 diferente da soma dos itens da mesma combinação."""
    return [regra.problema(r, texto) for _c, _p, somas in _analise_c190(doc)
            for r, texto in somas]


def documentos_c190_divergentes(doc):
    """C100 **com itens** cujo C190 não confere com eles — combinação sem
    par ou soma fora da tolerância. É o que o *Recalcular C190* refaz pelos
    C170; documento sem item fica de fora, porque não há de onde refazer."""
    return [c100 for c100, sem_par, somas in _analise_c190(doc)
            if (sem_par or somas) and _filhos(c100, "C170")]


SOMAS_DO_ANALITICO = (("C100", "C190", ("VL_BC_ICMS", "VL_ICMS",
                                         "VL_BC_ICMS_ST", "VL_ICMS_ST",
                                         "VL_IPI")),
                      ("D100", "D190", ("VL_BC_ICMS", "VL_ICMS")))


def _soma_dos_analiticos(doc, regra):
    """Totais de ICMS, ST e IPI do documento = soma dos analíticos (C100 ←
    C190, D100 ← D190), com a tolerância do PVA."""
    out = []
    for pai_reg, filho, campos in SOMAS_DO_ANALITICO:
        for pai in _de(doc, pai_reg):
            analiticos = _filhos(pai, filho)
            if not analiticos:
                continue
            difs = []
            for campo in campos:
                if not _tem(doc, pai, campo):
                    continue
                soma = sum(_num(doc, a, campo) for a in analiticos)
                if _difere(_num(doc, pai, campo), soma, TOLERANCIA_ICMS):
                    difs.append("%s %s (%s: %s)" % (
                        campo, _fmt_val(_num(doc, pai, campo)), filho,
                        _fmt_val(soma)))
            if difs:
                out.append(regra.problema(
                    pai, "documento %s: %s" % (_texto(doc, pai, "NUM_DOC"),
                                               "; ".join(difs))))
    return out


def _c100_vl_merc(doc, regra):
    """VL_MERC abaixo da soma do VL_ITEM dos C170 (mais que a tolerância),
    em documento regular/extemporâneo que não seja NF-e de emissão
    própria. Acima não é cobrado: é o que diz a consulta do PVA."""
    out = []
    for c100 in _de(doc, "C100"):
        itens = _filhos(c100, "C170")
        if not itens or _nfe_propria(doc, c100) or not _conferido(doc, c100):
            continue
        soma = sum(_num(doc, f, "VL_ITEM") for f in itens)
        if _num(doc, c100, "VL_MERC") - soma < -TOLERANCIA_ICMS:
            out.append(regra.problema(
                c100, "documento %s: VL_MERC %s; soma dos itens %s" % (
                    _texto(doc, c100, "NUM_DOC"),
                    _fmt_val(_num(doc, c100, "VL_MERC")), _fmt_val(soma))))
    return out


DATAS_ATE_O_FIM = {"C100": ("DT_DOC", "DT_E_S"), "D100": ("DT_DOC", "DT_A_P"),
                   "H005": ("DT_INV",)}


def _datas_ate_o_fim(doc, regra):
    """Datas que não podem passar do DT_FIN do 0000: emissão e entrada/
    saída do C100, emissão e aquisição do D100, data do inventário.

    O limite é um só para entrada, saída e extemporâneo, como o validador
    do PVA (que não olha IND_OPER nem COD_SIT). O limite **inferior** da
    saída é da verificação própria (`revisao.verificar_data_fora_periodo`):
    dividir pelo limite, e não pela operação, é o que impede o mesmo
    documento de ser contado duas vezes — ou nenhuma."""
    _ini, fim = _periodo(doc)
    if not fim:
        return []
    dt_fin = _texto(doc, _abertura(doc), "DT_FIN")
    out = []
    for reg, nomes in DATAS_ATE_O_FIM.items():
        for r in _de(doc, reg):
            for nome in nomes:
                d = data_aaaammdd(_texto(doc, r, nome))
                if d and d > fim:
                    out.append(regra.problema(
                        r, "%s %s depois do fim do período (%s)" % (
                            nome, _texto(doc, r, nome), dt_fin)))
    return out


def _periodo_0000(doc, regra):
    """DT_FIN no mesmo mês de DT_INI, e não antes dela."""
    r = _abertura(doc)
    if r is None:
        return []
    ini, fim = _periodo(doc)
    if not ini or not fim:
        return []
    if fim < ini:
        return [regra.problema(r, "DT_FIN anterior a DT_INI")]
    if fim[:6] != ini[:6]:
        return [regra.problema(r, "DT_INI e DT_FIN em meses diferentes")]
    return []


def _documentos(doc, regra, r, quem, excludentes=True):
    """CNPJ e CPF de `r` com dígito válido e, se `excludentes`, não os
    dois juntos."""
    cnpj, cpf = _texto(doc, r, "CNPJ"), _texto(doc, r, "CPF")
    out = []
    if excludentes and cnpj and cpf:
        out.append(regra.problema(r, "%s: CNPJ e CPF preenchidos (são "
                                     "mutuamente excludentes)" % quem))
    for nome, v, ok in (("CNPJ", cnpj, cnpj_valido), ("CPF", cpf, cpf_valido)):
        if v and not ok(v):
            out.append(regra.problema(r, "%s: %s com dígito inválido"
                                         % (quem, nome)))
    return out


def _identificacao(doc, regra):
    """CNPJ/CPF com dígito válido e mutuamente excludentes (0000, 0150; no
    0100 só o dígito); participante do Brasil com um dos dois; município
    do informante na UF dele."""
    out = []
    r0 = _abertura(doc)
    if r0 is not None:
        out += _documentos(doc, regra, r0, "informante")
        uf, mun = _texto(doc, r0, "UF"), _texto(doc, r0, "COD_MUN")
        if uf in UF_IBGE and len(mun) == 7 and mun[:2] != UF_IBGE[uf]:
            out.append(regra.problema(r0, "COD_MUN %s não é da UF %s"
                                          % (mun, uf)))
    for r in _de(doc, "0100"):
        out += _documentos(doc, regra, r, "contabilista", excludentes=False)
    for r in _de(doc, "0150"):
        quem = "participante %s" % _texto(doc, r, "COD_PART")
        out += _documentos(doc, regra, r, quem)
        if _texto(doc, r, "COD_PAIS") in PAIS_BRASIL and \
                not (_texto(doc, r, "CNPJ") or _texto(doc, r, "CPF")):
            out.append(regra.problema(r, "%s do Brasil sem CNPJ nem CPF"
                                         % quem))
    return out


def _emitente_proprio(doc):
    """`f(c100) -> (cnpj, cpf, código da UF, só a raiz?)` de quem emite os
    documentos próprios do C100.

    No ICMS/IPI é o informante (0000), e o PVA compara só a **raiz** do
    CNPJ. No Contribuições é o **estabelecimento** do bloco (o C010 pai do
    C100, com a UF do 0140 do mesmo CNPJ), comparado por inteiro — com a do
    0000, toda nota de filial noutra UF era acusada."""
    r0 = _abertura(doc)
    cnpj0 = so_digitos(_texto(doc, r0, "CNPJ"))
    cpf0 = so_digitos(_texto(doc, r0, "CPF"))
    uf0 = UF_IBGE.get(_texto(doc, r0, "UF"))
    if doc.layout != "CONTRIB":
        return lambda c100: (cnpj0, cpf0, uf0, True)
    uf_estab = {so_digitos(_texto(doc, r, "CNPJ")):
                UF_IBGE.get(_texto(doc, r, "UF")) for r in _de(doc, "0140")}

    def emitente(c100):
        pai = c100.pai
        if pai is None or pai.reg != "C010":
            return cnpj0, cpf0, uf0, False
        cnpj = so_digitos(_texto(doc, pai, "CNPJ"))
        return cnpj, "", uf_estab.get(cnpj, uf0), False
    return emitente


def _participantes(doc):
    """`{COD_PART: emitente esperado na chave (14 dígitos)}` do 0150 — o
    CNPJ, ou o CPF com três zeros à frente."""
    out = {}
    for r in _de(doc, "0150"):
        cnpj = so_digitos(_texto(doc, r, "CNPJ"))
        cpf = so_digitos(_texto(doc, r, "CPF"))
        if cnpj or cpf:
            out[_texto(doc, r, "COD_PART")] = cnpj.zfill(14) if cnpj \
                else "000" + cpf
    return out


def _chave_nfe(doc, regra):
    """CHV_NFE do C100 (modelos 55 e 65): obrigatória, com dígito válido e
    coerente com o documento — modelo, série e número. Na emissão própria,
    o CNPJ e a UF são os de quem emite (`_emitente_proprio`); na de
    terceiros, o CNPJ (ou CPF) é o do participante do 0150 — no ICMS/IPI
    também vale o do próprio informante, como na consulta do PVA. Regime
    especial (COD_SIT 08) fica fora das duas comparações."""
    emitente = _emitente_proprio(doc)
    participantes = _participantes(doc)
    cnpj_informante = so_digitos(_texto(doc, _abertura(doc), "CNPJ"))
    out = []
    for c100 in _de(doc, "C100"):
        mod = _texto(doc, c100, "COD_MOD")
        if mod not in ("55", "65"):
            continue
        chave = _texto(doc, c100, "CHV_NFE")
        num = _texto(doc, c100, "NUM_DOC")
        if not chave:
            if _texto(doc, c100, "COD_SIT") != "05":
                out.append(regra.problema(c100, "documento %s modelo %s sem "
                                                "a chave" % (num, mod)))
            continue
        if not chave_dfe_valida(chave):
            out.append(regra.problema(c100, "documento %s: chave com "
                                            "dígito verificador inválido"
                                            % num))
            continue
        erros = []
        if chave[20:22] != mod:
            erros.append("modelo da chave %s" % chave[20:22])
        ser = _texto(doc, c100, "SER")
        if ser.isdigit() and int(chave[22:25]) != int(ser):
            erros.append("série da chave %s" % chave[22:25])
        if num.isdigit() and int(chave[25:34]) != int(num):
            erros.append("número da chave %s" % int(chave[25:34]))
        emit = chave[6:20]
        regime_especial = _texto(doc, c100, "COD_SIT") == "08"
        if _texto(doc, c100, "IND_EMIT") == "0" and not regime_especial:
            cnpj, cpf, uf, raiz = emitente(c100)
            if cnpj and (emit[:8] != cnpj[:8] if raiz else emit != cnpj):
                erros.append("o CNPJ do emitente na chave não é o de quem "
                             "escritura o documento")
            elif cpf and not cnpj and emit != cpf.zfill(14):
                erros.append("o CPF do emitente na chave não é o do "
                             "informante")
            if uf and chave[:2] != uf:
                erros.append("UF da chave %s" % chave[:2])
        elif _texto(doc, c100, "IND_EMIT") == "1" and not regime_especial:
            esperado = participantes.get(_texto(doc, c100, "COD_PART"))
            aceitos = {esperado}
            if doc.layout == "ICMS":
                aceitos.add(cnpj_informante)
            if esperado and emit not in aceitos:
                erros.append("o emitente da chave não é o participante %s"
                             % _texto(doc, c100, "COD_PART"))
        if erros:
            out.append(regra.problema(c100, "documento %s: %s" % (
                num, "; ".join(erros))))
    return out


def _qtd_linhas(doc, r):
    """O valor de quantidade de linhas do X990 (QTD_LIN_C, QTD_LIN_0…)."""
    for nome in ("QTD_LIN_%s" % r.reg[0], "QTD_LIN"):
        if doc._ix(r.reg, nome) is not None:
            return _texto(doc, r, nome)
    return (r.valor(1) or "").strip()


def _bloco9(doc, regra):
    """Contagens do arquivo: X990 (linhas do bloco), 9900 (registros de
    cada tipo, um 9900 por tipo) e 9999 (linhas do arquivo)."""
    por_tipo, por_bloco = {}, {}
    for r in doc.registros:
        por_tipo[r.reg] = por_tipo.get(r.reg, 0) + 1
        por_bloco[r.bloco] = por_bloco.get(r.bloco, 0) + 1
    out = []
    declarados = set()
    for r in doc.registros:
        if len(r.reg) == 4 and r.reg.endswith("990"):
            qtd = _qtd_linhas(doc, r)
            n = por_bloco.get(r.reg[0], 0)
            if qtd.isdigit() and int(qtd) != n:
                out.append(regra.problema(r, "%s informa %s linhas; o bloco "
                                             "tem %d" % (r.reg, qtd, n)))
        elif r.reg == "9900":
            tipo = _texto(doc, r, "REG_BLC")
            qtd = _texto(doc, r, "QTD_REG_BLC")
            if tipo in declarados:
                out.append(regra.problema(r, "9900 repetido para o %s"
                                             % tipo))
            declarados.add(tipo)
            if qtd.isdigit() and int(qtd) != por_tipo.get(tipo, 0):
                out.append(regra.problema(r, "9900 do %s informa %s; o "
                                             "arquivo tem %d" % (
                                                 tipo, qtd,
                                                 por_tipo.get(tipo, 0))))
        elif r.reg == "9999":
            qtd = _texto(doc, r, "QTD_LIN")
            if qtd.isdigit() and int(qtd) != len(doc.registros):
                out.append(regra.problema(r, "9999 informa %s linhas; o "
                                             "arquivo tem %d" % (
                                                 qtd, len(doc.registros))))
    alvo = next((r for r in doc.registros if r.reg == "9001"), None)
    faltam = sorted(set(por_tipo) - declarados)
    if declarados and faltam and alvo is not None:
        out.append(regra.problema(alvo, "sem 9900 para: %s"
                                        % ", ".join(faltam)))
    return out


def _e110(doc, regra):
    """Apuração do ICMS próprio (E110): os totais de ajuste contra os E111
    (3º e 4º caracteres do código) e os saldos pelas expressões do guia
    sobre os valores declarados — as mesmas funções do recálculo
    (`SpedDocument._ajustes_e111`, `saldos_e110`), que corrige os dois."""
    out = []
    for e110 in _de(doc, "E110"):
        v = doc.valores_e110(e110)
        for campo, soma in doc._ajustes_e111(e110).items():
            if _difere(v[campo], soma, TOLERANCIA_ICMS):
                out.append(regra.problema(
                    e110, "%s %s; soma dos E111 desse tipo %s"
                          % (campo, _fmt_val(v[campo]), _fmt_val(soma))))
        for campo, esperado in doc.saldos_e110(v).items():
            if _difere(v[campo], esperado):
                out.append(regra.problema(
                    e110, "%s %s; pela expressão do guia %s"
                          % (campo, _fmt_val(v[campo]), _fmt_val(esperado))))
    return out


def _e116(doc, regra):
    """E116 (obrigações a recolher) soma o VL_ICMS_RECOLHER mais o DEB_ESP
    do E110. Não se recalcula: o que dividir em cada obrigação é do
    contribuinte."""
    out = []
    for e110 in _de(doc, "E110"):
        v = doc.valores_e110(e110)
        e116 = _filhos(e110, "E116")
        devido = v["VL_ICMS_RECOLHER"] + v["DEB_ESP"]
        soma = sum(_num(doc, r, "VL_OR") for r in e116)
        if _difere(soma, devido, TOLERANCIA_ICMS):
            out.append(regra.problema(
                e116[0] if e116 else e110,
                "E116 soma %s; VL_ICMS_RECOLHER + DEB_ESP do E110 é %s"
                % (_fmt_val(soma), _fmt_val(devido))))
    return out


def _inventario(doc, regra):
    """H005 com valor e itens: VL_INV = soma do VL_ITEM dos H010. H010 de
    posse ou propriedade de terceiros exige o participante."""
    out = []
    for h005 in _de(doc, "H005"):
        itens = _filhos(h005, "H010")
        vl_inv = _num(doc, h005, "VL_INV")
        soma = sum(_num(doc, f, "VL_ITEM") for f in itens)
        if itens and vl_inv > 0 and _difere(vl_inv, soma, TOLERANCIA_ICMS):
            out.append(regra.problema(h005, "VL_INV %s; soma dos H010 %s" % (
                _fmt_val(vl_inv), _fmt_val(soma))))
        for f in itens:
            if _texto(doc, f, "IND_PROP") in ("1", "2") and \
                    not _texto(doc, f, "COD_PART"):
                out.append(regra.problema(
                    f, "item %s de terceiros sem COD_PART"
                       % _texto(doc, f, "COD_ITEM")))
    return out


def _qtd_item(doc, regra):
    """QTD do C170 maior que zero, exceto em documento complementar ou com
    redução de valores (COD_SIT 06, 07, 09, 10)."""
    out = []
    for c100 in _de(doc, "C100"):
        if _texto(doc, c100, "COD_SIT") in ("06", "07", "09", "10"):
            continue
        for f in _filhos(c100, "C170"):
            if _texto(doc, f, "QTD") and _num(doc, f, "QTD") <= 0:
                out.append(regra.problema(
                    f, "item %s com quantidade zero"
                       % _texto(doc, f, "NUM_ITEM")))
    return out


GRUPOS_CONTRIBUICAO = (
    # (valor, base em valor, alíquota %, base em quantidade, alíq. em R$)
    ("VL_PIS", "VL_BC_PIS", "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT"),
    ("VL_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
     "ALIQ_COFINS_QUANT"),
)
VALIDADORES_CONTRIBUICAO = ("REGRA_VL_PIS", "REGRA_VL_COFINS",
                            "REGRA_VL_QUANT_PIS", "REGRA_VL_QUANT_COFINS")


def _valor_contribuicao(doc, regra):
    """VL_PIS (VL_COFINS) = base × alíquota ÷ 100, ou quantidade × alíquota
    em reais — nos registros em que o descritor declara a regra, com a
    tolerância de R$ 0,99 do PVA, que acusa como advertência."""
    regs = registros_com_validador(doc, VALIDADORES_CONTRIBUICAO,
                                   ("C170", "C175"))
    # (valor, base, alíquota, quantidade, alíquota em R$) por registro,
    # resolvidos uma vez: a regra lê cinco campos de dezenas de milhares
    grupos = {reg: [(g[0], tuple(doc._ix(reg, c) for c in g))
                    for g in GRUPOS_CONTRIBUICAO
                    if doc._ix(reg, g[0]) is not None]
              for reg in regs}
    out = []
    for r in _de(doc, *regs):
        difs = []
        for nome, (i_vl, i_bc, i_aliq, i_qt, i_aliq_q) in grupos[r.reg]:
            texto = (r.valor(i_vl) or "").strip()
            if not texto:
                continue
            vl = _to_num(texto)
            calc = (_to_num(r.valor(i_bc)) * _to_num(r.valor(i_aliq)) / 100.0
                    + _to_num(r.valor(i_qt)) * _to_num(r.valor(i_aliq_q)))
            if _difere(vl, calc, TOLERANCIA_PIS_COFINS):
                difs.append("%s %s (calculado %s)" % (
                    nome, _fmt_val(vl), _fmt_val(calc)))
        if difs:
            out.append(regra.problema(r, "; ".join(difs)))
    return out


def _unidade_0190(doc, regra):
    """0190: UNID e DESCR não podem ter o mesmo conteúdo."""
    return [regra.problema(r, "unidade %s com a descrição igual ao código"
                              % _texto(doc, r, "UNID"))
            for r in _de(doc, "0190")
            if _texto(doc, r, "UNID") and
            _texto(doc, r, "UNID") == _texto(doc, r, "DESCR")]


# ------------------------------------------------------------------- lista
ICMS, CONTRIB, AMBOS = ("ICMS",), ("CONTRIB",), ("ICMS", "CONTRIB")
# módulos que corrigem: `diagnostico.MODULOS` usa os mesmos, e a interface
# liga o botão pelo rótulo — uma grafia só
RECALCULAR_C190 = ("Recalcular C190 (analítico)",
                   "Ferramentas → Recalcular → C190 em massa")
RECALCULAR_TOTAIS = ("Recalcular totais do C100",
                     "Grade do C100 → 🔄 Recalcular totais")
RECALCULAR_E110 = ("Recalcular apuração do ICMS (E110)",
                   "Ferramentas → Recalcular → Apuração do ICMS "
                   "(E110)")
ALTERAR_DATAS = ("Alterar datas emissão/saída (C100)",
                 "Ferramentas → Corrigir → Alterar datas")

REGRAS = [
    Regra("cfop_operacao", AMBOS, "CFOP",
          "CFOP incompatível com a operação do documento",
          _cfop_operacao,
          pva=("REGRA_CFOP_C100", "REGRA_CFOP_NFCE", "REGRA_CFOP_D190",
               "REGRA_COERENCIA_CFOP_C170", "REGRA_COERENCIA_CFOP")),
    Regra("cfop_nfce", CONTRIB, "CFOP",
          "CFOP de NFC-e que não começa com 5 (C175)", _cfop_nfce_contrib,
          pva=("REGRA_CFOP_NFCE_CFE",)),
    Regra("c190_c170", ICMS, "CST_ICMS",
          "Combinação CST/CFOP/alíquota sem par entre C170 e C190",
          _combinacao_c190_c170,
          pva=("REGRA_CHAVE_EXISTE_NO_REGISTRO_ITEM_A8E1V1",),
          modulo=RECALCULAR_C190[0], onde=RECALCULAR_C190[1]),
    Regra("c190_soma", ICMS, "VL_BC_ICMS",
          "C190 diferente da soma dos itens (C170)", _c190_soma_c170,
          pva=("REGRA_VL_BC_ICMS_NO_REGISTRO_ITEM",
               "REGRA_VL_ICMS_NO_REGISTRO_ITEM",
               "REGRA_VL_BC_ICMS_ST_NO_REGISTRO_ITEM",
               "REGRA_VL_ICMS_ST_NO_REGISTRO_ITEM"),
          modulo=RECALCULAR_C190[0], onde=RECALCULAR_C190[1]),
    Regra("soma_analiticos", ICMS, "VL_ICMS",
          "Totais do documento diferentes dos analíticos (C190/D190)",
          _soma_dos_analiticos,
          pva=("REGRA_VL_BC_ICMS_ANALIT", "REGRA_VL_ICMS_ANALIT",
               "REGRA_VL_BC_ICMS_ST_ANALIT", "REGRA_VL_ICMS_ST_ANALIT",
               "REGRA_VL_IPI_C190"),
          modulo=RECALCULAR_TOTAIS[0], onde=RECALCULAR_TOTAIS[1]),
    Regra("c100_vl_merc", ICMS, "VL_MERC",
          "VL_MERC abaixo da soma dos itens (C170)", _c100_vl_merc,
          pva=("REGRA_VL_MERC_C170",),
          modulo=RECALCULAR_TOTAIS[0], onde=RECALCULAR_TOTAIS[1]),
    Regra("datas_fim", ICMS, "DT_DOC",
          "Data depois do fim do período (C100, D100, H005)",
          _datas_ate_o_fim,
          pva=("REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_DOC_C100",
               "REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_ES",
               "REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_DOC",
               "REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_A_P",
               "REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_INV"),
          modulo=ALTERAR_DATAS[0], onde=ALTERAR_DATAS[1]),
    Regra("periodo_0000", AMBOS, "DT_FIN",
          "Período do 0000 fora do mesmo mês", _periodo_0000,
          pva=("REGRA_MES_ESCRITURACAO",)),
    Regra("identificacao", AMBOS, "CNPJ",
          "CNPJ/CPF inválido ou ausente (0000, 0100, 0150)", _identificacao,
          pva=("REGRA_DIGITO_CNPJ", "REGRA_DIGITO_CPF", "REGRA_VALIDA_CNPJ",
               "REGRA_VALIDA_CPF", "REGRA_CNPJ_EXCLUDENTE",
               "REGRA_OBRIGATORIO_CPF_BRA_V2",
               "REGRA_OBRIGATORIO_PARA_BRASIL_A10E3V4",
               "REGRA_OBRIGATORIO_PARA_BRASIL_3002V1",
               "REGRA_OBRIGATORIO_CPF_EXCLUDENTE_0000_CONTEUDO",
               "REGRA_OBRIGATORIO_CPF_EXCLUDENTE_BRA_CNPJ",
               "REGRA_OBRIGATORIO_CPF_EXCLUDENTE_BRA_CPF",
               "REGRA_COD_MUN_EM_UF_V2", "REGRA_COD_MUN_EM_UF"),
          modulo="Cadastro do participante no ERP",
          onde="corrija o cadastro no ERP (ou na grade do 0150) e gere o "
               "arquivo de novo"),
    Regra("chave_nfe", AMBOS, "CHV_NFE",
          "Chave da NF-e/NFC-e ausente, inválida ou incoerente (C100)",
          _chave_nfe,
          pva=("REGRA_VALIDA_CHV_NFE_CTE", "REGRA_VALIDA_CHV_NFE",
               "REGRA_COMPARA_CNPJ_NFE_CTE_12001_V1",
               "REGRA_COMPARA_NUM_DOC_NFE_CTE_C100_V4",
               "REGRA_COMPARA_NUM_DOC_NFE",
               "REGRA_COMPARA_UF_NFE_CTE_13001_V1",
               "REGRA_COMPARA_CODIGO_MODELO", "REGRA_VALIDA_SERIE_CHAVE",
               "REGRA_OBRIGATORIO_CHV_NFE_CTE_A13E1V2",
               "REGRA_OBRIGATORIO_CHVE_NFCE_A7E2V1",
               "REGRA_OBRIGATORIO_CHV_NFE_1003_V2",
               "REGRA_OBRIGATORIO_CHVE_NFCE",
               "REGRA_COMPARA_MODELO_DOCUMENTO_NFE",
               "REGRA_COMPARA_CNPJ_NFE_6001_V2",
               "REGRA_COMPARA_CNPJ_NFE_PARTICIPANTE_12001_V1"),
          modulo="Conferir com os XMLs",
          onde="Ferramentas → Conferir → Itens com XMLs (a chave "
               "certa vem do XML)"),
    Regra("bloco9", AMBOS, "QTD_REG_BLC",
          "Contagem de linhas/registros (X990, 9900, 9999)", _bloco9,
          pva=("REGRA_QTD_REG_BLC_OBRIGATORIO", "REGRA_QTD_LIN_ARQUIVO",
               "REGRA_REGISTRO_DUPLICADO_9900"),
          modulo="Salvar", onde="Arquivo → Salvar refaz as contagens"),
    Regra("apuracao_e110", ICMS, "VL_SLD_APURADO",
          "Apuração do ICMS (E110) fora das expressões do guia", _e110,
          pva=("REGRA_VL_TOT_AJ_DEBITOS_E110", "REGRA_VL_ESTORNOS_CRED_E110",
               "REGRA_VL_TOT_AJ_CREDITOS_E110", "REGRA_VL_ESTORNOS_DEB_E110",
               "REGRA_SLD_DEVEDOR_E110", "REGRA_SLD_CREDOR_E110",
               "REGRA_ICMS_RECOLHER"),
          modulo=RECALCULAR_E110[0], onde=RECALCULAR_E110[1]),
    Regra("e116", ICMS, "VL_OR",
          "E116 diferente do ICMS a recolher mais o débito especial",
          _e116, pva=("REGRA_ICMS_REC_E116",),
          onde="o E116 tem de somar VL_ICMS_RECOLHER + DEB_ESP do E110; a "
               "divisão entre obrigações é do contribuinte"),
    Regra("inventario", ICMS, "VL_INV",
          "Inventário (H005/H010) incoerente", _inventario,
          pva=("REGRA_VL_INV", "REGRA_IND_PROP")),
    Regra("qtd_item", ICMS, "QTD",
          "Item (C170) com quantidade zero", _qtd_item,
          pva=("REGRA_MAIOR_ZERO_CONDICAO_COD_SIT",)),
    Regra("valor_contribuicao", CONTRIB, "VL_PIS",
          "VL_PIS/VL_COFINS diferente de base × alíquota (mais de R$ 0,99)",
          _valor_contribuicao,
          pva=VALIDADORES_CONTRIBUICAO, gravidade="aviso"),
    Regra("unidade_0190", CONTRIB, "DESCR",
          "Unidade (0190) com a descrição igual ao código", _unidade_0190),
]


def regras(layout):
    return [r for r in REGRAS if layout in r.layouts]


def como_regras_da_revisao():
    """`[(rótulo, função)]` no formato da lista `revisao.REGRAS`."""
    return [(r.rotulo, r.verificar) for r in REGRAS]


def validadores_reproduzidos():
    """Ids `REGRA_…` do descritor que as regras daqui reproduzem."""
    return {v for r in REGRAS for v in r.pva}

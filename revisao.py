# -*- coding: utf-8 -*-
"""
revisao.py
----------
Revisão de erros simples no arquivo SPED. Cada regra recebe o SpedDocument e
devolve uma lista de `Problema`. O conjunto é facilmente extensível: basta
escrever uma função `verificar_*(doc) -> list[Problema]` e registrá-la em
`REGRAS`.

Cada Problema carrega o `uid` do registro, o que permite à interface navegar
até ele ao clicar no relatório.
"""

from collections import Counter

from sped_model import _to_num, _fmt_val, TIPOS_ITEM_0200


class Problema:
    __slots__ = ("uid", "reg", "bloco", "regra", "descricao", "gravidade")

    def __init__(self, uid, reg, bloco, regra, descricao, gravidade="erro"):
        self.uid = uid
        self.reg = reg
        self.bloco = bloco
        self.regra = regra
        self.descricao = descricao
        self.gravidade = gravidade


# --------------------------------------------------------------------- regras
def verificar_num_campos(doc):
    """Registros cujo número de campos destoa dos demais do mesmo tipo.

    A referência é a *moda* (quantidade de campos mais comum) entre os
    registros do mesmo tipo no próprio arquivo — não o layout embutido, que
    pode estar numa versão diferente da do arquivo. Assim a regra aponta o erro
    real (um registro editado com um campo a mais ou a menos) sem gerar falso
    positivo por diferença de versão de layout. Tipos com um único registro são
    ignorados (não há base de comparação).
    """
    por_tipo = {}
    for r in doc.registros:
        por_tipo.setdefault(r.reg, []).append(r)

    problemas = []
    for reg, lista in por_tipo.items():
        if len(lista) < 2:
            continue
        contagem = Counter(len(r.campos) for r in lista)
        moda, _freq = contagem.most_common(1)[0]
        for r in lista:
            n = len(r.campos)
            if n != moda:
                problemas.append(Problema(
                    uid=r.uid, reg=r.reg, bloco=r.bloco,
                    regra="Número de campos",
                    descricao="%s tem %d campos; os demais %s têm %d."
                              % (r.reg, n, r.reg, moda)))
    return problemas


def verificar_c190_reducao(doc):
    """C190 com CST x20/x70 (redução de base) e VL_RED_BC zerado."""
    if doc.layout != "ICMS":
        return []
    problemas = []
    i_cst = doc._ix("C190", "CST_ICMS")
    i_red = doc._ix("C190", "VL_RED_BC")
    if i_cst is None or i_red is None:
        return []
    for r in doc.registros:
        if r.reg != "C190":
            continue
        cst = (r.valor(i_cst) or "").strip()
        if cst[-2:] in ("20", "70") and _to_num(r.valor(i_red)) == 0:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="C190 redução de BC",
                descricao="CST %s exige redução de base, mas VL_RED_BC está "
                          "zerado." % cst))
    return problemas


# Registro central de regras. Para adicionar uma nova verificação, escreva a
# função acima e inclua aqui o par (rótulo, função).
def verificar_0200_nao_utilizados(doc):
    """Aponta registros 0200 (cadastro de item) cujo COD_ITEM:
      * não é referenciado por nenhum outro registro (C170, H010, etc.); ou
      * está duplicado (mesmo COD_ITEM em mais de um 0200).

    As referências são coletadas de qualquer registro (≠ 0200) que possua o
    campo COD_ITEM no layout — não apenas C170/H010 —, evitando marcar como
    "não utilizado" um item citado em outro bloco.
    """
    i0 = doc._ix("0200", "COD_ITEM")
    if i0 is None:
        return []
    # a varredura vive no modelo: registro sem leiaute mapeado (o bloco K
    # inteiro, por exemplo) é procurado por valor, senão item referenciado lá
    # apareceria aqui como não utilizado
    referenciados = doc.referencias_de_itens()["referenciados"]

    problemas = []
    vistos = set()
    for r in doc.registros:
        if r.reg != "0200":
            continue
        cod = (r.valor(i0) or "").strip()
        if cod and cod in vistos:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="0200 duplicado",
                descricao="COD_ITEM %s já cadastrado em outro 0200." % cod,
                gravidade="aviso"))
        else:
            vistos.add(cod)
        if cod and cod not in referenciados:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="0200 não utilizado",
                descricao="COD_ITEM %s não é referenciado por nenhum registro "
                          "(C170, H010, ...)." % cod,
                gravidade="aviso"))
    return problemas


def verificar_c170_sem_c190(doc):
    """C170 (item) sem um C190 (analítico) compatível no mesmo documento — ou
    seja, cuja combinação de CST_ICMS, CFOP e ALIQ_ICMS não aparece em nenhum
    C190 do C100. Indica que o item não foi consolidado no analítico."""
    if doc.layout != "ICMS":
        return []
    ic = doc._ix("C170", "CST_ICMS")
    iff = doc._ix("C170", "CFOP")
    ia = doc._ix("C170", "ALIQ_ICMS")
    inum = doc._ix("C170", "NUM_ITEM")
    jc = doc._ix("C190", "CST_ICMS")
    jf = doc._ix("C190", "CFOP")
    ja = doc._ix("C190", "ALIQ_ICMS")
    if None in (ic, iff, ia, jc, jf, ja):
        return []

    def chave(r, i_cst, i_cfop, i_aliq):
        return ((r.valor(i_cst) or "").strip(), (r.valor(i_cfop) or "").strip(),
                "%.2f" % _to_num(r.valor(i_aliq)))

    problemas = []
    for c100 in doc.registros:
        if c100.reg != "C100":
            continue
        c170s = [f for f in c100.filhos if f.reg == "C170"]
        if not c170s:
            continue
        chaves_190 = {chave(f, jc, jf, ja) for f in c100.filhos
                      if f.reg == "C190"}
        for f in c170s:
            if chave(f, ic, iff, ia) not in chaves_190:
                problemas.append(Problema(
                    uid=f.uid, reg=f.reg, bloco=f.bloco,
                    regra="C170 sem C190 compatível",
                    descricao="Item %s (CST %s, CFOP %s, alíq. %s) não possui "
                              "C190 correspondente no documento."
                              % ((f.valor(inum) or "").strip(),
                                 (f.valor(ic) or "").strip(),
                                 (f.valor(iff) or "").strip(),
                                 (f.valor(ia) or "").strip())))
    return problemas


def verificar_tipo_item_0200(doc):
    """TIPO_ITEM fora da tabela oficial do 0200.

    O campo só aceita 00 a 10 e 99. ERPs que exportam a coluna errada
    despejam ali a origem da mercadoria ou um "N" de nacional — num arquivo
    real eram 10.312 itens, todos recusados pelo PVA. Item por item a
    correção é inviável; a grade do 0200 aplica valor na seleção inteira.
    """
    if doc.layout != "ICMS":
        return []
    i_tipo = doc._ix("0200", "TIPO_ITEM")
    i_cod = doc._ix("0200", "COD_ITEM")
    if i_tipo is None:
        return []
    problemas = []
    for r in doc.registros:
        if r.reg != "0200":
            continue
        v = (r.valor(i_tipo) or "").strip()
        if v and v not in TIPOS_ITEM_0200:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="TIPO_ITEM fora da tabela",
                descricao="Item %s tem TIPO_ITEM %r, que não existe na "
                          "tabela do 0200 (00 a 10 e 99)."
                          % ((r.valor(i_cod) or "").strip(), v)))
    return problemas


def verificar_cod_gen_0200(doc):
    """COD_GEN que não é o capítulo do NCM (Tabela 4.2.1).

    O gênero são os dois primeiros dígitos do NCM. Vazio é o caso comum
    depois de limpar um `NULL` herdado do ERP; errado costuma ser planilha
    que cortou os dois primeiros dígitos de um NCM já sem o zero à esquerda
    (`04012010` vira `4012010`, e o gênero sai `40` em vez de `04`).
    """
    if doc.layout != "ICMS":
        return []
    problemas = []
    for r, cod, ncm, atual, novo in doc.divergencias_cod_gen():
        problemas.append(Problema(
            uid=r.uid, reg=r.reg, bloco=r.bloco,
            regra="COD_GEN x NCM",
            descricao="Item %s: NCM %s pede COD_GEN %s, mas está %s."
                      % (cod, ncm, novo, ("%r" % atual) if atual else "vazio"),
            gravidade="erro" if atual else "aviso"))
    return problemas


def verificar_chave_duplicada(doc):
    """Registros irmãos com a mesma **chave** declarada no descritor do PVA.

    A chave é por registro (`C190` = CST_ICMS+CFOP+ALIQ_ICMS, `C170` =
    NUM_ITEM) e vale **entre irmãos do mesmo pai** — dois C190 iguais em
    documentos diferentes são normais; no mesmo documento, não. O PVA acusa
    com `MSG_CHAVE_EXISTE_NO_REGISTRO_ITEM`; num arquivo real do usuário foram
    130 ocorrências, todas no C190.

    A regra é genérica porque a chave vem do descritor: vale para os 154
    registros que a declaram no EFD ICMS/IPI e os 145 no Contribuições.
    """
    try:
        import descritor_pva
        estrutura, _i = descritor_pva.carregar(doc.layout)
    except Exception:                                       # noqa: BLE001
        return []
    if not estrutura:
        return []
    chaves = {}
    for reg, d in estrutura.items():
        campos = [c.strip() for c in (d.get("chave") or "").split(",")
                  if c.strip()]
        if campos:
            chaves[reg] = campos

    problemas = []
    vistos_por_pai = {}
    idx = {}
    for r in doc.registros:
        campos = chaves.get(r.reg)
        if not campos:
            continue
        if r.reg not in idx:
            i = [doc._ix(r.reg, c) for c in campos]
            idx[r.reg] = [x for x in i if x is not None]
        indices = idx[r.reg]
        if not indices:
            continue
        pai = r.pai.uid if r.pai is not None else None
        chave = tuple((r.valor(i) or "").strip() for i in indices)
        marca = (pai, r.reg, chave)
        if marca in vistos_por_pai:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco,
                regra="Chave duplicada",
                descricao="%s repetido no mesmo %s: %s = %s"
                          % (r.reg, r.pai.reg if r.pai else "nível",
                             "+".join(campos), "|".join(chave))))
        else:
            vistos_por_pai[marca] = r.uid
    return problemas


def verificar_data_fora_periodo(doc):
    """Saída cuja **data de saída** está fora do período da escrituração.

    O PVA acusa com `MSG_PERIODO_INCOMPATIVEL_SAIDA` (campo `11 - DT_E_S` do
    C100); num arquivo real foram 132 ocorrências. Só as **saídas** são
    cobradas: numa entrada, a data do documento pode ser anterior ao período
    (documento recebido depois), e a escrituração extemporânea é legítima.
    """
    i_ini = doc._ix("0000", "DT_INI")
    i_fim = doc._ix("0000", "DT_FIN")
    i_op = doc._ix("C100", "IND_OPER")
    i_es = doc._ix("C100", "DT_E_S")
    i_num = doc._ix("C100", "NUM_DOC")
    if None in (i_ini, i_fim, i_op, i_es):
        return []

    def chave(v):
        d = "".join(c for c in (v or "") if c.isdigit())
        return d[4:8] + d[2:4] + d[0:2] if len(d) == 8 else ""

    ini = fim = ""
    for r in doc.registros:
        if r.reg == "0000":
            ini, fim = chave(r.valor(i_ini)), chave(r.valor(i_fim))
            break
    if not ini or not fim:
        return []

    problemas = []
    for r in doc.registros:
        if r.reg != "C100" or (r.valor(i_op) or "").strip() != "1":
            continue
        v = (r.valor(i_es) or "").strip()
        k = chave(v)
        if not k or ini <= k <= fim:
            continue
        problemas.append(Problema(
            uid=r.uid, reg=r.reg, bloco=r.bloco,
            regra="Data de saída fora do período",
            descricao="Documento %s com DT_E_S %s, fora do período do arquivo."
                      % ((r.valor(i_num) or "").strip()
                         if i_num is not None else "", v)))
    return problemas


def _data_chave(v):
    """DDMMAAAA -> AAAAMMDD, para comparar data como texto."""
    d = "".join(c for c in (v or "") if c.isdigit())
    return d[4:8] + d[2:4] + d[0:2] if len(d) == 8 else ""


def _registro_0000(doc):
    for r in doc.registros:
        if r.reg == "0000":
            return r
    return None


def verificar_cst_combustivel_sem_aliquota(doc):
    """CST do ICMS terminado em **02** com alíquota zerada.

    Desde 01/04/2023 o CST com final 02 é *tributação monofásica própria sobre
    combustíveis*, que tem alíquota por unidade de medida — e por isso o PVA
    exige `ALIQ_ICMS > 0` (`MSG_VALIDA_CST_ALIQ_ICMS_C170_CST_FINAL_2`).

    Na prática quase nunca é combustível: é o **CSOSN 102/202 do fornecedor
    do Simples** copiado do documento de entrada, que o PVA lê como origem +
    CST 02. Num arquivo real de supermercado eram 25 itens, exatamente os 25
    que o validador oficial acusou. Não há correção automática: trocar o CSOSN
    pelo CST da própria operação exige saber a origem da mercadoria.
    """
    if doc.layout != "ICMS":
        return []
    r0 = _registro_0000(doc)
    i_ini = doc._ix("0000", "DT_INI")
    if r0 is None or i_ini is None:
        return []
    if _data_chave(r0.valor(i_ini)) < "20230401":
        return []
    i_cst = doc._ix("C170", "CST_ICMS")
    i_al = doc._ix("C170", "ALIQ_ICMS")
    i_item = doc._ix("C170", "COD_ITEM")
    if i_cst is None or i_al is None:
        return []
    problemas = []
    for r in doc.registros:
        if r.reg != "C170":
            continue
        cst = (r.valor(i_cst) or "").strip()
        if len(cst) != 3 or cst[-2:] != "02":
            continue
        if _to_num(r.valor(i_al)) > 0:
            continue
        problemas.append(Problema(
            uid=r.uid, reg=r.reg, bloco=r.bloco,
            regra="CST 02 sem alíquota",
            descricao="Item %s com CST %s (o PVA lê como tributação "
                      "monofásica de combustível e exige alíquota > 0). "
                      "Costuma ser o CSOSN do fornecedor do Simples."
                      % ((r.valor(i_item) or "").strip()
                         if i_item is not None else "", cst)))
    return problemas


def verificar_ind_emit(doc):
    """Saída escriturada como documento de **emissão de terceiros**.

    O PVA cobra a coerência entre `IND_OPER` e `IND_EMIT`
    (`MSG_IND_EMIT`): saída é documento próprio. Quando há chave de NF-e, o
    CNPJ dentro dela diz qual dos dois campos está errado — se a chave é do
    próprio contribuinte, o errado é o `IND_EMIT`; se é de outro, o documento
    é de entrada e o errado é o `IND_OPER`. Por isso a regra aponta e não
    corrige: os dois consertos levam o arquivo para lados opostos.
    """
    if doc.layout != "ICMS":
        return []
    i_op = doc._ix("C100", "IND_OPER")
    i_emit = doc._ix("C100", "IND_EMIT")
    i_chv = doc._ix("C100", "CHV_NFE")
    i_num = doc._ix("C100", "NUM_DOC")
    if i_op is None or i_emit is None:
        return []
    r0 = _registro_0000(doc)
    i_cnpj = doc._ix("0000", "CNPJ")
    cnpj = ""
    if r0 is not None and i_cnpj is not None:
        cnpj = "".join(c for c in (r0.valor(i_cnpj) or "") if c.isdigit())

    problemas = []
    for r in doc.registros:
        if r.reg != "C100" or (r.valor(i_op) or "").strip() != "1":
            continue
        emit = (r.valor(i_emit) or "").strip()
        if emit in ("", "0"):
            continue
        chave = ""
        if i_chv is not None:
            chave = "".join(c for c in (r.valor(i_chv) or "") if c.isdigit())
        if len(chave) == 44 and cnpj:
            saida = ("a chave é do próprio CNPJ: corrija o IND_EMIT"
                     if chave[6:20] == cnpj
                     else "a chave é de outro CNPJ: o documento é de entrada")
        else:
            saida = "sem chave para decidir qual dos dois campos está errado"
        problemas.append(Problema(
            uid=r.uid, reg=r.reg, bloco=r.bloco,
            regra="IND_EMIT em documento de saída",
            descricao="Documento %s é saída (IND_OPER 1) com IND_EMIT %s — %s."
                      % ((r.valor(i_num) or "").strip()
                         if i_num is not None else "", emit, saida)))
    return problemas


def _problemas_apuracao(doc, chave, campo, rotulo):
    """Divergência de um campo do M210/M610 contra os documentos."""
    conf = doc.conferir_apuracao_m() if doc.layout == "CONTRIB" else None
    if not conf:
        return []
    parcial = conf["parcial"]
    problemas = []
    for tributo in ("PIS", "COFINS"):
        d = conf[tributo]
        if not d["difere_%s" % chave]:
            continue
        dec = d["declarado_%s" % chave]
        calc = d["calculado_%s" % chave]
        obs = (" (conferência parcial: há receita em %s)" % ", ".join(parcial)
               if parcial else "")
        for r in d["registros"]:
            problemas.append(Problema(
                uid=r.uid, reg=r.reg, bloco=r.bloco, regra=rotulo,
                descricao="%s: %s declarado %s, documentos somam %s "
                          "(diferença %s)%s"
                          % (d["registro"], campo, _fmt_val(dec),
                             _fmt_val(calc), _fmt_val(round(dec - calc, 2)),
                             obs),
                gravidade="aviso" if parcial else "erro"))
    return problemas


def verificar_m210_receita_bruta(doc):
    """`VL_REC_BRT` do M210/M610 diferente da receita dos documentos.

    O PVA recalcula a apuração a partir dos registros de receita e compara
    (`MSG_VL_REC_BRT`); num arquivo real a apuração trazia R$ 262.591,48 onde
    os documentos somavam R$ 431,64. Quem corrige é *Recalcular bloco M*, que
    usa exatamente este somatório.
    """
    return _problemas_apuracao(doc, "rec", "VL_REC_BRT",
                               "M210/M610 receita bruta")


def verificar_m210_base_calculo(doc):
    """`VL_BC_CONT` do M210/M610 diferente da base dos documentos.

    Mesma conferência da receita bruta, no campo da base de cálculo
    (`MSG_VL_BC_CONT_IND_NAT_PJ`).
    """
    return _problemas_apuracao(doc, "bc", "VL_BC_CONT",
                               "M210/M610 base de cálculo")


def verificar_m400_sem_lastro(doc):
    """M400/M800 sem receita correspondente nos documentos.

    O M400 (PIS) e o M800 (COFINS) declaram a receita isenta, não alcançada,
    a alíquota zero ou com suspensão, por CST. O PVA soma os documentos pelo
    mesmo CST e, não achando nada, acusa o registro como sobrando
    (`MSG_M400_NAO_DEVE_EXISTIR`). Valor diferente de zero mas divergente é
    apontado como aviso: o registro existe, o número é que não fecha.
    """
    if doc.layout != "CONTRIB":
        return []
    parcial = doc.receita_parcial()
    problemas = []
    for r, tributo, cst, dec, calc in doc.conferir_receitas_isentas():
        if calc <= 0:
            texto = ("%s com CST %s (%s) declara %s, mas nenhum documento tem "
                     "esse CST — para o PVA o registro não deveria existir"
                     % (r.reg, cst, tributo, _fmt_val(dec)))
            grav = "aviso" if parcial else "erro"
        else:
            texto = ("%s com CST %s (%s): declarado %s, documentos somam %s"
                     % (r.reg, cst, tributo, _fmt_val(dec), _fmt_val(calc)))
            grav = "aviso"
        problemas.append(Problema(uid=r.uid, reg=r.reg, bloco=r.bloco,
                                  regra="M400/M800 sem lastro",
                                  descricao=texto, gravidade=grav))
    return problemas


def verificar_credito_m105(doc):
    """M105/M505 diferente da base de crédito dos documentos.

    O PVA soma as entradas por natureza da base, CST e alíquota e cobra o
    M105 igual a isso; sobrando um M105 sem correspondência, ele acusa que o
    registro não deveria existir. É o que aparece **depois de corrigir CST ou
    alíquota das entradas**: a base muda e o lado do crédito continua como o
    ERP gravou. Quem conserta é *Recalcular bloco M*, que agora refaz também
    o M100/M105 e o M500/M505.
    """
    if doc.layout != "CONTRIB":
        return []
    problemas = []
    for r, tributo, nat, cst, dec, calc in doc.conferir_creditos_m():
        if calc <= 0:
            texto = ("%s natureza %s / CST %s (%s) declara %s, e nenhum "
                     "documento tem essa combinação na alíquota do %s"
                     % (r.reg, nat, cst, tributo, _fmt_val(dec),
                        r.pai.reg if r.pai else "M100"))
        else:
            texto = ("%s natureza %s / CST %s (%s): declarado %s, documentos "
                     "somam %s" % (r.reg, nat, cst, tributo, _fmt_val(dec),
                                   _fmt_val(calc)))
        problemas.append(Problema(uid=r.uid, reg=r.reg, bloco=r.bloco,
                                  regra="M105/M505 x documentos",
                                  descricao=texto))
    return problemas


def verificar_0900_ausente(doc, hoje=None):
    """Registro 0900 ausente numa escrituração já fora do prazo.

    O 0900 (composição da receita bruta do período) foi o que o PVA cobrou em
    `MSG_PREENCHIMENTO_0900`, trazendo na mensagem a **data limite de entrega**
    do período — 15/05/2026 para uma escrituração de 03/2026. A cobrança
    apareceu só na escrituração validada depois dessa data; as validadas
    dentro do prazo, sem 0900, passaram limpas. A regra reproduz essa condição
    e usa a tabela de prazos do próprio PVA.
    """
    if doc.layout != "CONTRIB":
        return []
    if any(r.reg == "0900" for r in doc.registros):
        return []
    r0 = _registro_0000(doc)
    i_ini = doc._ix("0000", "DT_INI")
    if r0 is None or i_ini is None:
        return []
    ini = "".join(c for c in (r0.valor(i_ini) or "") if c.isdigit())
    if len(ini) != 8:
        return []
    try:
        import tabelas_pva
        prazo = tabelas_pva.prazo_entrega(ini[2:8])
    except Exception:                                       # noqa: BLE001
        prazo = ""
    if not prazo:
        return []
    if hoje is None:
        from datetime import date
        hoje = date.today().strftime("%Y%m%d")
    if hoje <= _data_chave(prazo):
        return []
    return [Problema(
        uid=r0.uid, reg="0000", bloco="0",
        regra="Registro 0900 ausente",
        descricao="Escrituração de %s/%s sem registro 0900; o prazo de "
                  "entrega (%s/%s/%s) já passou."
                  % (ini[2:4], ini[4:8], prazo[:2], prazo[2:4], prazo[4:8]),
        gravidade="aviso")]


REGRAS = [
    ("Número de campos divergente do layout", verificar_num_campos),
    ("C190 CST x20/x70 com VL_RED_BC zerado", verificar_c190_reducao),
    ("C170 sem C190 compatível", verificar_c170_sem_c190),
    ("0200 não utilizados / duplicados", verificar_0200_nao_utilizados),
    ("TIPO_ITEM fora da tabela (0200)", verificar_tipo_item_0200),
    ("COD_GEN incoerente com o NCM (0200)", verificar_cod_gen_0200),
    ("Chave duplicada no mesmo registro-pai", verificar_chave_duplicada),
    ("Data de saída fora do período", verificar_data_fora_periodo),
    ("CST 02 (monofásico) sem alíquota (C170)",
     verificar_cst_combustivel_sem_aliquota),
    ("IND_EMIT de terceiro em documento de saída", verificar_ind_emit),
    ("M210/M610 com receita bruta divergente", verificar_m210_receita_bruta),
    ("M210/M610 com base de cálculo divergente", verificar_m210_base_calculo),
    ("M400/M800 sem lastro nos documentos", verificar_m400_sem_lastro),
    ("Registro 0900 ausente fora do prazo", verificar_0900_ausente),
    ("M105/M505 fora da base de crédito dos documentos",
     verificar_credito_m105),
]


def revisar_por_regra(doc, regras=None):
    """Executa as regras e devolve `[(rotulo, [problemas])]`.

    Manter o vínculo entre a regra e os seus achados é o que permite ao painel
    oferecer, em cada linha, a função que corrige **aquela** regra: o texto do
    `Problema.regra` é mais curto que o rótulo da lista e não serve de chave.
    """
    regras = regras if regras is not None else REGRAS
    return [(rotulo, fn(doc)) for rotulo, fn in regras]


def revisar(doc, regras=None):
    """Executa as regras e devolve (lista_de_problemas, resumo_por_regra)."""
    por_regra = revisar_por_regra(doc, regras)
    problemas = [p for _r, ps in por_regra for p in ps]
    resumo = [(r, len(ps)) for r, ps in por_regra]
    return problemas, resumo

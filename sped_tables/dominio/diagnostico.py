# -*- coding: utf-8 -*-
"""
diagnostico.py
--------------
Passa o arquivo pelas mesmas camadas de verificação que o PVA aplica e diz,
para cada problema, **qual módulo do programa o corrige**.

O que é fiel e o que não é — a distinção importa:

* **é fiel** tudo o que o PVA valida de forma *declarativa*, porque a
  declaração vem do descritor do próprio PVA: quantidade de campos do
  registro, obrigatoriedade de campo, tipo/tamanho/casas decimais, enumeração,
  tabela externa, referência de um campo a outro registro
  (`COD_ITEM` → 0200, `COD_PART` → 0150, `UNID` → 0190, `COD_CTA` → 0500) e
  chave duplicada;
* **não é** o conjunto de regras compostas (`REGRA_CST_ICMS_CAMPOS_ICMS_C170`
  e outras ~1.400), implementadas em Java sobre o banco embutido do PVA. As
  classes não carregam as condições no bytecode, e adivinhá-las produziria
  divergência silenciosa com o validador oficial. Elas são **listadas** como
  "só o PVA verifica", com o nome, para não passarem a impressão de que o
  arquivo está limpo.

Uma terceira origem entrou depois: as mensagens que o PVA **já gravou** no
banco de cada validação (tabela `inconsistencia`). Elas não trazem a regra,
mas trazem o valor encontrado e o esperado — o bastante para reconstruir a
condição e, melhor, para conferir a reimplementação contra o que o validador
oficial acusou nos mesmos arquivos.

Também não são cobertas as obrigatoriedades **condicionais** — o `COD_CTA` do
H010, por exemplo, é opcional no descritor e vira obrigatório no perfil A/B
por uma regra à parte. Essas continuam nas verificações próprias do programa.
"""

import logging
from collections import Counter

from sped_tables.dominio import referencias
from sped_tables.dominio import regras_guia
from sped_tables.dominio import validacao

log = logging.getLogger("sped_tables")


# Achado -> módulo que corrige. O texto é o nome do item de menu, para a
# pessoa saber exatamente onde clicar.
MODULOS = {
    # os três pela mesma tela, aberta daqui: é a validação de leiaute, e o
    # botão de normalizar dela esvazia o "NULL" e completa o zero que falta
    "nulo": ("Corrigir campos pelo leiaute",
             "Diagnóstico → Corrigir campos pelo leiaute (normalizar)"),
    "dominio": ("Corrigir campos pelo leiaute",
                "Diagnóstico → Corrigir campos pelo leiaute"),
    "formato": ("Corrigir campos pelo leiaute",
                "Diagnóstico → Corrigir campos pelo leiaute (normalizar)"),
    "linha_invalida": ("Correção no arquivo de origem",
                       "linha sem o | inicial: não é registro, e salvar "
                       "pergunta antes de descartá-la"),
    "sem_pipe_final": ("Salvar",
                       "linha sem o | final: lida inteira, e o | é "
                       "acrescentado ao salvar — confira o último campo"),
    "item_orfao": ("Itens do 0200 sem referência",
                   "Ferramentas → Conferir → Itens do 0200 sem referência"),
    "ref_ausente": ("Correção manual na grade",
                    "o código citado não existe no cadastro correspondente"),
    "cod_cta": ("Preencher conta contábil (COD_CTA)",
                "Ferramentas → Corrigir → Preencher conta contábil"),
    "cod_gen": ("Preencher COD_GEN pelo NCM",
                "Ferramentas → Corrigir → Preencher COD_GEN pelo NCM"),
    "municipio": ("Cadastro do participante no ERP",
                  "corrija a cidade no cadastro do participante no ERP "
                  "(o município do CNPJ está na consulta pública do "
                  "Sintegra) e gere o arquivo de novo"),
    "red_bc": regras_guia.RECALCULAR_C190,
    "obrigatorio": ("Correção manual na grade",
                    "campo obrigatório em branco"),
    "num_campos": ("Correção manual na grade",
                   "o registro tem mais ou menos campos que o leiaute"),
    "chave_c190": regras_guia.RECALCULAR_C190,
    "chave": ("Correção manual na grade", "chave repetida no mesmo nível"),
    "data_periodo": regras_guia.ALTERAR_DATAS,
    "bloco": ("Correção manual na grade", "bloco aberto sem encerramento"),
    "cst_aliq_02": ("Empresa e rotinas",
                    "Ferramentas → Corrigir → Empresa e rotinas → CSOSN do "
                    "Simples no CST do ICMS (a conversão é configurada no "
                    "cadastro da empresa)"),
    # x02 que a rotina do CSOSN não toca: saída, ou combustível de verdade
    "cst_aliq_02_manual": ("Correção manual na grade",
                           "CST x02 (monofásico de combustível) sem "
                           "alíquota: informe a alíquota ou corrija o CST"),
    "nat_rec": ("Empresa e rotinas",
                "Ferramentas → Corrigir → Empresa e rotinas → Natureza da "
                "receita fora da tabela do CST (bebida fria do varejista → "
                "918; o resto, conferir o CST no ERP/PDV)"),
    "data_es": ("Datas e extemporâneos pelos XMLs",
                "Ferramentas → Corrigir → Datas e extemporâneos pelos XMLs "
                "(ou Alterar datas)"),
    "credito_ncm": ("Empresa e rotinas",
                    "Ferramentas → Corrigir → Empresa e rotinas → CST "
                    "incoerente com o NCM (retira o crédito das entradas)"),
    "apuracao_icms": regras_guia.RECALCULAR_E110,
    "ind_emit": ("Correção manual na grade",
                 "saída escriturada como documento de terceiro"),
    "cfop_credito": ("Empresa e rotinas",
                     "Ferramentas → Corrigir → Empresa e rotinas → Crédito em "
                     "CFOP que não dá direito"),
    "apuracao_m": ("Recalcular bloco M (apuração PIS/COFINS)",
                   "Ferramentas → Recalcular → Bloco M"),
    "credito_m": ("Recalcular bloco M (apuração PIS/COFINS)",
                  "Ferramentas → Recalcular → Bloco M"),
    "m400": ("Correção manual na grade",
             "M400/M800 sem receita correspondente nos documentos"),
    "reg_0900": ("Correção manual na grade",
                 "registro 0900 ausente numa escrituração fora do prazo"),
}
# as regras do guia prático: uma entrada por regra, com o módulo dela
MODULOS.update({
    "guia_" + r.id: (r.modulo, r.onde or "regra do guia prático — na grade, "
                                          "F1 mostra o texto do campo")
    for r in regras_guia.REGRAS})


# Obrigatoriedade que o descritor declara como fixa, mas que o PVA dispensa
# por condição. O descritor não carrega a condição (ela vive numa regra Java),
# então as poucas que dá para afirmar com segurança ficam aqui, nominalmente.
#
# `C100.COD_PART`: o Guia dispensa o participante nos documentos de venda a
# consumidor — NFC-e (65), cupom (2D) e afins. Sem esta entrada, um arquivo de
# supermercado acusava 4.377 "campos obrigatórios em branco" que o PVA aceita,
# e os 5 casos reais (modelo 55) sumiam no meio.
MODELOS_SEM_PARTICIPANTE = {"65", "2D", "59", "60"}


def _dispensa_cod_part(doc, r):
    i = doc._ix(r.reg, "COD_MOD")
    if i is None or i >= len(r.campos):
        return False
    return (r.valor(i) or "").strip() in MODELOS_SEM_PARTICIPANTE


DISPENSAS = {("C100", "COD_PART"): _dispensa_cod_part,
             ("C500", "COD_PART"): _dispensa_cod_part,
             ("D100", "COD_PART"): _dispensa_cod_part}

# Documento cancelado (02, 03), denegado (04) ou numeração inutilizada (05):
# o Guia manda informar **só** a identificação, e todo o resto vai em branco
# (exceção 1 do C100; idem D100). O descritor declara DT_DOC, VL_DOC,
# IND_PGTO… como obrigatórios, e sem esta exceção cada NF-e cancelada
# gerava cinco "campos obrigatórios em branco" que o PVA não acusa.
SITUACOES_SO_IDENTIFICACAO = {"02", "03", "04", "05"}
IDENTIFICACAO = {
    "C100": {"IND_OPER", "IND_EMIT", "COD_MOD", "COD_SIT", "SER", "NUM_DOC",
             "CHV_NFE"},
    "D100": {"IND_OPER", "IND_EMIT", "COD_MOD", "COD_SIT", "SER", "SUB",
             "NUM_DOC", "CHV_CTE"},
}


def _so_identificacao(doc, r):
    """Documento que, pela situação, só leva os campos de identificação."""
    if r.reg not in IDENTIFICACAO:
        return False
    i = doc._ix(r.reg, "COD_SIT")
    return (i is not None and i < len(r.campos)
            and (r.valor(i) or "").strip() in SITUACOES_SO_IDENTIFICACAO)


class Achado:
    __slots__ = ("tipo", "reg", "campo", "detalhe", "quantidade", "uid",
                 "gravidade")

    def __init__(self, tipo, reg, campo, detalhe, quantidade=1, uid=None,
                 gravidade="erro"):
        self.tipo = tipo
        self.reg = reg
        self.campo = campo
        self.detalhe = detalhe
        self.quantidade = quantidade
        self.uid = uid
        self.gravidade = gravidade


def _cadastros(doc, estrutura):
    """Índice `{(registro, campo): set(valores)}` dos registros que servem de
    cadastro, para conferir as referências declaradas no descritor."""
    alvos = set()
    for (_reg, _campo), (alvo, campo_alvo) in \
            referencias.do_descritor(estrutura).items():
        alvos.add((alvo, campo_alvo))
    indice = {}
    for alvo, campo_alvo in alvos:
        i = doc._ix(alvo, campo_alvo)
        if i is None:
            continue
        vals = set()
        for r in doc.registros:
            if r.reg == alvo:
                v = (r.valor(i) or "").strip()
                if v:
                    vals.add(v)
        indice[(alvo, campo_alvo)] = vals
    return indice


def _num_campos_descritor(estrutura):
    """Largura de cada registro segundo o descritor: a posição do último
    campo (`pos`, a ordem dos `<campo>` no XML), não o atributo `n` — que tem
    erros de digitação (0220 e C890 repetem o `n`, K300, 1710 e M800 o têm
    a mais). Pelo `n`, o 0220 tinha 3 campos e todo 0220 com código de barras
    virava "mais campos que o leiaute", achado que impede a importação."""
    return {reg: max((c.get("pos") or c["n"] or 0)
                     for c in d["campos"].values())
            for reg, d in estrutura.items() if d["campos"]}


def verificar(doc):
    """Roda as camadas e devolve `(achados, info)`.

    `achados` é uma lista de `Achado` já **agregada por tipo/registro/campo**:
    o objetivo é dizer o que fazer, não repetir a mesma frase mil vezes.
    """
    estrutura, info_desc = referencias.atual().estrutura(doc.layout)
    achados = []
    info = {"descritor": info_desc.get("descritor"),
            "registros_descritor": info_desc.get("registros", 0),
            "sem_pva": not estrutura}

    # ---- o que a leitura não conseguiu ler como registro ------------------
    # vem antes de tudo e não depende do PVA: é o arquivo que está quebrado
    invalidas = getattr(doc, "linhas_invalidas", [])
    if invalidas:
        achados.append(Achado(
            "linha_invalida", "", "",
            "linha fora do formato SPED, sem o | inicial (a primeira é a "
            "linha %d)" % invalidas[0][0], len(invalidas)))
    sem_fim = Counter(reg for _n, reg in getattr(doc, "sem_pipe_final", []))
    for reg, n in sem_fim.items():
        achados.append(Achado("sem_pipe_final", reg, "",
                              "linha sem o | final", n))

    # ---- domínio, tipo e tamanho (o grosso, já implementado) -------------
    dominios, info_dom = validacao.dominios_do_documento(doc)
    ocorrencias = validacao.validar(doc, dominios_pva=dominios)
    info.update({k: info_dom.get(k) for k in
                 ("por_enum", "por_tabela", "por_formato", "faltando")})
    grupos = {}
    for o in ocorrencias:
        tipo = "nulo" if o.sugestao == "" else (
            "dominio" if o.sugestao is None else "formato")
        if (o.reg, o.campo) in validacao.CADASTRO_NO_ERP:
            tipo = "municipio"       # conserto é o cadastro no ERP
        grupos.setdefault((tipo, o.reg, o.campo, o.motivo), []).append(o)
    for (tipo, reg, campo, motivo), lista in grupos.items():
        achados.append(Achado(tipo, reg, campo, motivo, len(lista),
                              lista[0].uid))

    # ---- regras do guia e verificações próprias --------------------------
    # antes do retorno sem descritor: nenhuma delas depende do PVA instalado
    # (as que usam tabela dele se abstêm sozinhas)
    achados.extend(_achados_do_guia(doc))
    achados.extend(_achados_proprios(doc))

    if not estrutura:
        return achados, info

    # ---- quantidade de campos por registro -------------------------------
    esperado = _num_campos_descritor(estrutura)
    fora = Counter()
    exemplo = {}
    for r in doc.registros:
        n = esperado.get(r.reg)
        # o leiaute do arquivo pode ser anterior ao do PVA: campo a menos no
        # fim é omissão legítima. A mais, não: aí sobra pipe.
        if n and len(r.campos) > n:
            fora[r.reg] += 1
            exemplo.setdefault(r.reg, r.uid)
    for reg, n in fora.items():
        achados.append(Achado(
            "num_campos", reg, "",
            "registro com mais campos que o leiaute (%d previstos)"
            % esperado[reg], n, exemplo[reg]))

    # os dois laços abaixo percorriam o arquivo inteiro uma vez **por tipo de
    # registro do descritor** (~270 no ICMS): num arquivo de 45 mil linhas,
    # 12 milhões de comparações só para achar os registros de cada tipo
    por_tipo = {}
    for r in doc.registros:
        por_tipo.setdefault(r.reg, []).append(r)

    # ---- campo obrigatório em branco -------------------------------------
    faltando = Counter()
    ex_obr = {}
    for reg, d in estrutura.items():
        if reg not in por_tipo:
            continue
        obrigatorios = [(c["id"] if "id" in c else nome)
                        for nome, c in d["campos"].items()
                        if c.get("obrigatorio") == "1" and nome != "REG"]
        if not obrigatorios:
            continue
        idx = [(nome, doc._ix(reg, nome)) for nome in obrigatorios]
        idx = [(nome, i) for nome, i in idx if i is not None]
        if not idx:
            continue
        for r in por_tipo[reg]:
            so_id = _so_identificacao(doc, r)
            for nome, i in idx:
                if i >= len(r.campos) or (r.valor(i) or "").strip():
                    continue
                if so_id and nome not in IDENTIFICACAO[reg]:
                    continue
                dispensa = DISPENSAS.get((reg, nome))
                if dispensa is not None and dispensa(doc, r):
                    continue
                faltando[(reg, nome)] += 1
                ex_obr.setdefault((reg, nome), r.uid)
    for (reg, campo), n in faltando.items():
        achados.append(Achado("obrigatorio", reg, campo,
                              "campo obrigatório em branco", n,
                              ex_obr[(reg, campo)]))

    # ---- referências declaradas no descritor -----------------------------
    indice = _cadastros(doc, estrutura)
    refs = referencias.do_descritor(estrutura)
    ausentes = Counter()
    ex_ref = {}
    usados = {}
    for (reg, campo), (alvo, campo_alvo) in refs.items():
        i = doc._ix(reg, campo)
        cadastro = indice.get((alvo, campo_alvo))
        if i is None or cadastro is None:
            continue
        for r in por_tipo.get(reg, ()):
            if i >= len(r.campos):
                continue
            v = (r.valor(i) or "").strip()
            if not v:
                continue
            usados.setdefault((alvo, campo_alvo), set()).add(v)
            if v not in cadastro:
                ausentes[(reg, campo, alvo)] += 1
                ex_ref.setdefault((reg, campo, alvo), r.uid)
    for (reg, campo, alvo), n in ausentes.items():
        achados.append(Achado(
            "cod_cta" if campo == "COD_CTA" else "ref_ausente", reg, campo,
            "código informado não existe no %s" % alvo, n,
            ex_ref[(reg, campo, alvo)]))

    # ---- cadastro sem uso (o outro lado da referência) -------------------
    for (alvo, campo_alvo), vistos in usados.items():
        cadastro = indice.get((alvo, campo_alvo)) or set()
        orfaos = cadastro - vistos
        if orfaos:
            achados.append(Achado(
                "item_orfao" if alvo == "0200" else "ref_ausente", alvo,
                campo_alvo,
                "cadastrado mas não referenciado em nenhum registro",
                len(orfaos), None, "aviso"))

    # ---- bloco aberto sem encerramento -----------------------------------
    blocos = {r.bloco for r in doc.registros}
    tem = {r.reg for r in doc.registros}
    for b in sorted(blocos):
        if b == "9":
            continue
        if "%s001" % b in tem and "%s990" % b not in tem:
            achados.append(Achado("bloco", "%s990" % b, "",
                                  "bloco %s aberto sem o registro de "
                                  "encerramento" % b, 1))

    achados.sort(key=lambda a: -a.quantidade)
    info["regras_do_pva"] = regras_nao_cobertas(doc, estrutura)
    return achados, info


def _verificacoes_proprias():
    """`(tipo, registro, campo, texto, função, gravidade)` das verificações
    próprias que têm módulo de correção — o PVA também as acusa, por regra
    composta. Registro `None` é o do primeiro problema; gravidade `None`, a
    dele."""
    from sped_tables.dominio import revisao, rotinas
    return (
        ("red_bc", "C190", "VL_RED_BC",
         "CST x20/x70 com redução de base zerada",
         revisao.verificar_c190_reducao, None),
        ("data_periodo", "C100", "DT_E_S",
         "saída com data fora do período do arquivo",
         revisao.verificar_data_fora_periodo, None),
        ("nat_rec", "M410", "NAT_REC",
         "natureza da receita fora da tabela do CST do M400/M800",
         revisao.verificar_nat_rec, None),
        ("data_es", "C100", "DT_E_S",
         "data de entrada/saída anterior à data de emissão",
         revisao.verificar_data_es_antes_emissao, None),
        ("credito_ncm", "C170", "CST_PIS/CST_COFINS",
         "crédito na entrada de produto monofásico ou de alíquota zero",
         revisao.verificar_credito_ncm, "aviso"),
        ("apuracao_icms", "E110", "VL_TOT_DEBITOS/DEB_ESP",
         "débitos do E110 diferentes dos analíticos de saída",
         revisao.verificar_e110_debitos, None),
        ("ind_emit", "C100", "IND_EMIT",
         "saída com documento de emissão de terceiro",
         revisao.verificar_ind_emit, None),
        ("apuracao_m", None, "VL_REC_BRT",
         "apuração diverge da receita dos documentos",
         revisao.verificar_m210_receita_bruta, None),
        ("apuracao_m", None, "VL_BC_CONT",
         "apuração diverge da receita dos documentos",
         revisao.verificar_m210_base_calculo, None),
        ("credito_m", None, "VL_BC_TOT",
         "base de crédito declarada diferente da dos documentos",
         revisao.verificar_credito_m105, None),
        ("m400", None, "VL_TOT_REC",
         "receita isenta declarada sem lastro nos documentos",
         revisao.verificar_m400_sem_lastro, None),
        ("cfop_credito", "C170", "CST_PIS/CST_COFINS",
         "crédito tomado em CFOP que não consta da tabela de CFOP com "
         "direito a crédito", rotinas.verificar_cfop_sem_credito, "aviso"),
    )


def _achados_proprios(doc):
    """As verificações próprias, cada uma no seu `try`: exceção numa delas
    (a que carrega as tabelas da RFB, por exemplo) não some com as outras."""
    from sped_tables.dominio import revisao, rotinas
    achados = []

    def tentar(fn):
        try:
            return fn(doc)
        except Exception:                                   # noqa: BLE001
            log.exception("diagnóstico: %s interrompida", fn.__name__)
            return []

    for tipo, reg, campo, texto, fn, grav in _verificacoes_proprias():
        ps = tentar(fn)
        if ps:
            achados.append(Achado(
                tipo, reg or ps[0].reg, campo, texto, len(ps), ps[0].uid,
                grav or getattr(ps[0], "gravidade", "erro")))
    # chave repetida: o C190 vai para o recálculo, o resto é manual
    dup = tentar(revisao.verificar_chave_duplicada)
    for reg, n in Counter(x.reg for x in dup).items():
        achados.append(Achado(
            "chave_c190" if reg == "C190" else "chave", reg, "",
            "chave repetida no mesmo registro-pai", n,
            next(x.uid for x in dup if x.reg == reg)))
    # gênero diferente do NCM é erro; vazio, só aviso — o PVA não o cobra
    # (num arquivo real, 1.355 vazios e nenhuma mensagem)
    gen = tentar(revisao.verificar_cod_gen_0200)
    for grav, texto in (("erro", "gênero diferente do capítulo do NCM"),
                        ("aviso", "gênero em branco")):
        lista = [p for p in gen if p.gravidade == grav]
        if lista:
            achados.append(Achado("cod_gen", "0200", "COD_GEN", texto,
                                  len(lista), lista[0].uid, gravidade=grav))
    # CST x02 sem alíquota: o CSOSN de entrada vai para a rotina que o
    # converte, pelo mesmo critério dela; o resto é correção manual
    por_uid = {r.uid: r for r in doc.registros}
    i_cst = doc._ix("C170", "CST_ICMS")
    i_aliq = doc._ix("C170", "ALIQ_ICMS")
    i_oper = doc._ix("C100", "IND_OPER")

    def da_rotina(p):
        r = por_uid.get(p.uid)
        return (r is not None and r.pai is not None
                and (r.pai.valor(i_oper) or "").strip() == "0"
                and rotinas._e_csosn((r.valor(i_cst) or "").strip(),
                                     r.valor(i_aliq)))
    cst02 = tentar(revisao.verificar_cst_combustivel_sem_aliquota)
    for tipo, lista in (("cst_aliq_02", [p for p in cst02 if da_rotina(p)]),
                        ("cst_aliq_02_manual",
                         [p for p in cst02 if not da_rotina(p)])):
        if lista:
            achados.append(Achado(
                tipo, "C170", "ALIQ_ICMS", "CST terminado em 02 (monofásico "
                "de combustível) com alíquota zerada", len(lista),
                lista[0].uid))
    r0900 = tentar(revisao.verificar_0900_ausente)
    if r0900:
        achados.append(Achado("reg_0900", "0900", "",
                              "registro 0900 ausente e prazo de entrega "
                              "vencido", 1, r0900[0].uid, "aviso"))
    return achados


def _achados_do_guia(doc):
    """Um achado por regra de `regras_guia` que acusou alguma coisa."""
    achados = []
    for regra in regras_guia.regras(doc.layout):
        try:
            ps = regra.verificar(doc)
        except Exception:                                   # noqa: BLE001
            log.exception("diagnóstico: regra %s interrompida", regra.id)
            continue
        if ps:
            achados.append(Achado(
                "guia_" + regra.id, ps[0].reg, regra.campo, regra.rotulo,
                len(ps), ps[0].uid,
                "erro" if any(p.gravidade == "erro" for p in ps)
                else "aviso"))
    return achados


def regras_nao_cobertas(doc, estrutura):
    """Validadores que o PVA aplica aos registros **presentes neste arquivo** e
    que aqui não são reproduzidos. Listar é mais honesto que omitir: sem isso,
    "nenhum erro" pareceria aprovação."""
    presentes = {r.reg for r in doc.registros}
    reproduzidas = validadores_reproduzidos()
    regras = Counter()
    for reg in presentes:
        d = estrutura.get(reg)
        if not d:
            continue
        for v in d.get("validadores", ()):
            if v not in reproduzidas:
                regras[v] += 1
    return sorted(regras)


def validadores_reproduzidos():
    """Os validadores do descritor que o programa reproduz: os das regras do
    guia e os das verificações próprias. O painel e o `COBERTURA.md` contam
    por aqui."""
    return regras_guia.validadores_reproduzidos() | REPRODUZIDAS


# validadores do descritor que as verificações próprias (fora de
# `regras_guia`) reproduzem: conferidos um a um contra o banco de
# inconsistências do PVA nos arquivos reais
REPRODUZIDAS = {
    "REGRA_CST_ICMS_RED_BC_COM_COD_SIT_C190",       # red_bc
    "REGRA_IND_EMIT",                               # ind_emit
    "REGRA_VL_TOT_DEBITOS_E110_17002_V1",           # apuracao_icms
    "REGRA_DEB_ESP_E110_17002_V1",
    "REGRA_PERIODO_INCOMPATIVEL_SAIDA",             # data_periodo (CONTRIB)
    "REGRA_DT_E_S_MAIOR_IGUAL_DT_DOC",              # data_es
    "REGRA_DATA_MAIOR_IGUAL_DT_DOC_DT_E_S",
    "REGRA_VL_REC_BRT_7003_V1",                     # apuracao_m
    "REGRA_VL_BC_CONT_IND_NAT_PJ_7003_V1",
    "REGRA_EXISTE_COD_ITEM", "REGRA_EXISTE_COD_ITEM_V2",   # referências
    "REGRA_EXISTE_COD_PART", "REGRA_EXISTE_COD_PART_V2",
    "REGRA_EXISTE_UNID", "REGRA_EXISTE_UNID_V2",
    "REGRA_EXISTE_COD_NAT", "REGRA_EXISTE_COD_NAT_V2",
    "REGRA_EXISTE_COD_CTA",
}


# Achados que o PVA recusa **na importação**, antes de validar: são os que
# ele acusa com `MSG_ERRO_TIPO_CAMPO`, `MSG_ERRO_TAMANHO_CAMPO`,
# `MSG_VALORES_VALIDOS_IMPORTACAO` e afins, e que fazem a tela terminar em
# "Importação não realizada. Ocorreram erros na estrutura do arquivo".
#
# `obrigatorio` fica **de fora** de propósito: num arquivo real do EFD
# Contribuições havia 25 campos obrigatórios em branco pelo descritor e o PVA
# importou sem reclamar — são as obrigatoriedades condicionais que ele
# dispensa. Avisar por causa delas seria assustar à toa.
TIPOS_QUE_IMPEDEM_IMPORTACAO = ("nulo", "formato", "num_campos", "bloco",
                                "dominio", "linha_invalida",
                                "sem_pipe_final")


def impedem_importacao(achados):
    """`[(tipo, quantidade)]` do que faz o PVA recusar o arquivo na
    importação, do maior para o menor."""
    por_tipo = {}
    for a in achados:
        if a.tipo in TIPOS_QUE_IMPEDEM_IMPORTACAO:
            por_tipo[a.tipo] = por_tipo.get(a.tipo, 0) + a.quantidade
    return sorted(por_tipo.items(), key=lambda x: -x[1])


def resumo_por_modulo(achados):
    """Agrupa os achados pelo módulo que os corrige.
    `[(modulo, onde, total, [achados])]`, do maior para o menor."""
    por_mod = {}
    onde_de = {}
    for a in achados:
        mod, onde = MODULOS.get(a.tipo, ("Correção manual na grade", ""))
        por_mod.setdefault(mod, []).append(a)
        onde_de.setdefault(mod, onde)
    saida = [(m, onde_de[m], sum(x.quantidade for x in lst), lst)
             for m, lst in por_mod.items()]
    saida.sort(key=lambda x: -x[2])
    return saida

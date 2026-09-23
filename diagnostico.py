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

from collections import Counter

import descritor_pva
import validacao
from sped_model import _to_num


# Achado -> módulo que corrige. O texto é o nome do item de menu, para a
# pessoa saber exatamente onde clicar.
MODULOS = {
    "nulo": ("Limpar campos com NULL",
             "Ferramentas → Gerais → Limpar campos com NULL"),
    "dominio": ("Validar campos pelo leiaute",
                "Ferramentas → Gerais → Validar campos pelo leiaute"),
    "formato": ("Validar campos pelo leiaute",
                "Ferramentas → Gerais → Validar campos pelo leiaute"),
    "item_orfao": ("Itens do 0200 sem referência",
                   "Ferramentas → Gerais → Itens do 0200 sem referência"),
    "ref_ausente": ("Correção manual na grade",
                    "o código citado não existe no cadastro correspondente"),
    "cod_cta": ("Preencher conta contábil (COD_CTA)",
                "Ferramentas → Gerais → Preencher conta contábil"),
    "cod_gen": ("Preencher COD_GEN pelo NCM",
                "Ferramentas → EFD ICMS/IPI → Preencher COD_GEN pelo NCM"),
    "red_bc": ("Recalcular C190 (analítico)",
               "Ferramentas → EFD ICMS/IPI → Recalcular C190"),
    "obrigatorio": ("Correção manual na grade",
                    "campo obrigatório em branco"),
    "num_campos": ("Correção manual na grade",
                   "o registro tem mais ou menos campos que o leiaute"),
    "chave_c190": ("Recalcular C190 (analítico)",
                   "Ferramentas → EFD ICMS/IPI → Recalcular C190"),
    "chave": ("Correção manual na grade", "chave repetida no mesmo nível"),
    "data_periodo": ("Alterar datas emissão/saída (C100)",
                     "Ferramentas → Gerais → Alterar datas"),
    "bloco": ("Correção manual na grade", "bloco aberto sem encerramento"),
    "cst_aliq_02": ("Correção manual na grade",
                    "CST terminado em 02 exige alíquota; costuma ser CSOSN "
                    "do fornecedor do Simples"),
    "ind_emit": ("Correção manual na grade",
                 "saída escriturada como documento de terceiro"),
    "cfop_credito": ("Rotinas de conferência (PIS/COFINS)",
                     "Ferramentas → EFD Contribuições → Rotinas → Crédito em "
                     "CFOP que não dá direito"),
    "apuracao_m": ("Recalcular bloco M (apuração PIS/COFINS)",
                   "Ferramentas → EFD Contribuições → Recalcular bloco M"),
    "credito_m": ("Recalcular bloco M (apuração PIS/COFINS)",
                  "Ferramentas → EFD Contribuições → Recalcular bloco M"),
    "m400": ("Correção manual na grade",
             "M400/M800 sem receita correspondente nos documentos"),
    "reg_0900": ("Correção manual na grade",
                 "registro 0900 ausente numa escrituração fora do prazo"),
}


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
            descritor_pva.referencias(estrutura).items():
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
    return {reg: max((c["n"] or 0) for c in d["campos"].values())
            for reg, d in estrutura.items() if d["campos"]}


def verificar(doc, pasta_fiscal=None, pasta_contrib=None):
    """Roda as camadas e devolve `(achados, info)`.

    `achados` é uma lista de `Achado` já **agregada por tipo/registro/campo**:
    o objetivo é dizer o que fazer, não repetir a mesma frase mil vezes.
    """
    estrutura, info_desc = descritor_pva.carregar(doc.layout)
    achados = []
    info = {"descritor": info_desc.get("descritor"),
            "registros_descritor": info_desc.get("registros", 0),
            "sem_pva": not estrutura}

    # ---- domínio, tipo e tamanho (o grosso, já implementado) -------------
    dominios, info_dom = validacao.dominios_do_documento(
        doc, pasta_fiscal, pasta_contrib)
    ocorrencias = validacao.validar(doc, dominios_pva=dominios)
    info.update({k: info_dom.get(k) for k in
                 ("por_enum", "por_tabela", "por_formato", "faltando")})
    grupos = {}
    for o in ocorrencias:
        tipo = "nulo" if o.sugestao == "" else (
            "dominio" if o.sugestao is None else "formato")
        grupos.setdefault((tipo, o.reg, o.campo, o.motivo), []).append(o)
    for (tipo, reg, campo, motivo), lista in grupos.items():
        achados.append(Achado(tipo, reg, campo, motivo, len(lista),
                              lista[0].uid))

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

    # ---- campo obrigatório em branco -------------------------------------
    faltando = Counter()
    ex_obr = {}
    for reg, d in estrutura.items():
        obrigatorios = [(c["id"] if "id" in c else nome)
                        for nome, c in d["campos"].items()
                        if c.get("obrigatorio") == "1" and nome != "REG"]
        if not obrigatorios:
            continue
        idx = [(nome, doc._ix(reg, nome)) for nome in obrigatorios]
        idx = [(nome, i) for nome, i in idx if i is not None]
        if not idx:
            continue
        for r in doc.registros:
            if r.reg != reg:
                continue
            for nome, i in idx:
                if i >= len(r.campos) or (r.valor(i) or "").strip():
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
    refs = descritor_pva.referencias(estrutura)
    ausentes = Counter()
    ex_ref = {}
    usados = {}
    for (reg, campo), (alvo, campo_alvo) in refs.items():
        i = doc._ix(reg, campo)
        cadastro = indice.get((alvo, campo_alvo))
        if i is None or cadastro is None:
            continue
        for r in doc.registros:
            if r.reg != reg or i >= len(r.campos):
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

    # ---- verificações próprias que têm módulo de correção ----------------
    # entram aqui porque o PVA também as acusa, por regra composta: são as
    # que o programa sabe consertar sozinho
    try:
        import revisao
        red = revisao.verificar_c190_reducao(doc)
        if red:
            achados.append(Achado("red_bc", "C190", "VL_RED_BC",
                                  "CST x20/x70 com redução de base zerada",
                                  len(red), red[0].uid))
        dup = revisao.verificar_chave_duplicada(doc)
        if dup:
            por_reg = Counter(x.reg for x in dup)
            for reg, n in por_reg.items():
                achados.append(Achado(
                    "chave_c190" if reg == "C190" else "chave", reg, "",
                    "chave repetida no mesmo registro-pai", n,
                    next(x.uid for x in dup if x.reg == reg)))
        fora = revisao.verificar_data_fora_periodo(doc)
        if fora:
            achados.append(Achado("data_periodo", "C100", "DT_E_S",
                                  "saída com data fora do período do arquivo",
                                  len(fora), fora[0].uid))
        gen = revisao.verificar_cod_gen_0200(doc)
        if gen:
            achados.append(Achado("cod_gen", "0200", "COD_GEN",
                                  "gênero ausente ou diferente do capítulo "
                                  "do NCM", len(gen), gen[0].uid))
        # ---- regras tiradas do banco de inconsistências do próprio PVA ----
        cst02 = revisao.verificar_cst_combustivel_sem_aliquota(doc)
        if cst02:
            achados.append(Achado(
                "cst_aliq_02", "C170", "ALIQ_ICMS",
                "CST terminado em 02 (monofásico de combustível) com "
                "alíquota zerada", len(cst02), cst02[0].uid))
        emit = revisao.verificar_ind_emit(doc)
        if emit:
            achados.append(Achado(
                "ind_emit", "C100", "IND_EMIT",
                "saída com documento de emissão de terceiro", len(emit),
                emit[0].uid))
        for fn, campo in ((revisao.verificar_m210_receita_bruta,
                           "VL_REC_BRT"),
                          (revisao.verificar_m210_base_calculo,
                           "VL_BC_CONT")):
            ps = fn(doc)
            if ps:
                achados.append(Achado(
                    "apuracao_m", ps[0].reg, campo,
                    "apuração diverge da receita dos documentos", len(ps),
                    ps[0].uid, ps[0].gravidade))
        cred = revisao.verificar_credito_m105(doc)
        if cred:
            achados.append(Achado(
                "credito_m", cred[0].reg, "VL_BC_TOT",
                "base de crédito declarada diferente da dos documentos",
                len(cred), cred[0].uid))
        isentas = revisao.verificar_m400_sem_lastro(doc)
        if isentas:
            achados.append(Achado(
                "m400", isentas[0].reg, "VL_TOT_REC",
                "receita isenta declarada sem lastro nos documentos",
                len(isentas), isentas[0].uid, isentas[0].gravidade))
        r0900 = revisao.verificar_0900_ausente(doc)
        if r0900:
            achados.append(Achado(
                "reg_0900", "0900", "",
                "registro 0900 ausente e prazo de entrega vencido", 1,
                r0900[0].uid, "aviso"))
    except Exception:                                       # noqa: BLE001
        pass

    # ---- crédito em CFOP que não dá direito (tabela 4.3.7 do PVA) --------
    try:
        import rotinas
        cfop = rotinas.verificar_cfop_sem_credito(doc)
        if cfop:
            achados.append(Achado("cfop_credito", "C170", "CST_PIS/CST_COFINS",
                                  "crédito tomado em CFOP que não consta da "
                                  "tabela de CFOP com direito a crédito",
                                  len(cfop), cfop[0].uid, "aviso"))
    except Exception:                                       # noqa: BLE001
        pass

    achados.sort(key=lambda a: -a.quantidade)
    info["regras_do_pva"] = regras_nao_cobertas(doc, estrutura)
    return achados, info


def regras_nao_cobertas(doc, estrutura):
    """Validadores que o PVA aplica aos registros **presentes neste arquivo** e
    que aqui não são reproduzidos. Listar é mais honesto que omitir: sem isso,
    "nenhum erro" pareceria aprovação."""
    presentes = {r.reg for r in doc.registros}
    regras = Counter()
    for reg in presentes:
        d = estrutura.get(reg)
        if not d:
            continue
        for v in d.get("validadores", ()):
            regras[v] += 1
    return sorted(regras)


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

# -*- coding: utf-8 -*-
"""
validacao.py
------------
Validação dos campos pelo **domínio do leiaute**.

Em vez de uma regra por situação (como em `revisao.py`), aqui há uma tabela de
domínios **por nome de campo**, aplicada a qualquer registro que possua aquele
campo. Isso é possível porque no SPED o nome carrega o domínio: `CFOP` é CFOP
no C170, no C190 e no D190; `DT_DOC` é data em todo lugar.

Duas saídas, como o usuário precisa:
  * **normalizáveis** — o valor está certo mas perdeu o zero à esquerda numa
    planilha ou num banco (`CEST` com 6 dígitos, `TIPO_ITEM` com 1). Aqui há
    `sugestao` preenchida e `normalizar()` grava em lote;
  * **não normalizáveis** — o valor é inválido e a correção exige decisão
    humana (`CST_ICMS` incompleto, CFOP inexistente, data impossível). Esses
    entram na lista que navega até o registro.

Princípio: **só o que está preenchido é validado**. Obrigatoriedade depende do
registro e da operação, não do nome do campo, e cobrá-la aqui geraria uma
enxurrada de falso positivo.
"""

import re

from sped_tables.dominio import referencias
from sped_tables.dominio.sped_layouts import campos
from sped_tables.dominio.sped_model import TIPOS_ITEM_0200, VALORES_NULOS

# --------------------------------------------------------------------- tabelas
# CST do ICMS = origem (0 a 8) + situação tributária
# Situação tributária do ICMS. Os quatro últimos entraram em 01/04/2023 com a
# tributação monofásica de combustíveis (02 própria, 15 própria e por
# responsabilidade, 53 com diferimento, 61 cobrada anteriormente) — a tabela
# `SIT_TRIB_ICMS_B` do PVA é de 2009 e não os traz, mas a tabela única
# `SIT_TRIB_ICMS` (versão 4) sim, e o validador oficial os aceita.
SITUACOES_ICMS = {"00", "10", "20", "30", "40", "41", "50", "51", "60", "70",
                  "90", "02", "15", "53", "61"}
# CSOSN, do Simples Nacional: origem + 3 dígitos. Não é o leiaute do EFD
# ICMS/IPI, mas aparece em arquivo de quem migrou de regime — aceitar evita
# falso positivo (a conferência com XML já trata o caso à parte).
CSOSN = {"101", "102", "103", "201", "202", "203", "300", "400", "500", "900"}
ORIGENS = set("012345678")

CST_PIS_COFINS = (
    {"%02d" % n for n in range(1, 10)} | {"49"}
    | {"%02d" % n for n in range(50, 57)} | {"%02d" % n for n in range(60, 68)}
    | {"%02d" % n for n in range(70, 76)} | {"98", "99"})

# primeiro dígito do CFOP: 1/2/3 entradas, 5/6/7 saídas
INICIAIS_CFOP = set("123567")

RE_NUM_SPED = re.compile(r"^-?\d{1,18}(,\d{1,8})?$")
RE_SO_DIGITOS = re.compile(r"^\d+$")


class Ocorrencia:
    """Um campo com valor fora do domínio."""

    __slots__ = ("uid", "reg", "bloco", "campo", "indice", "valor", "motivo",
                 "sugestao")

    def __init__(self, uid, reg, bloco, campo, indice, valor, motivo,
                 sugestao=None):
        self.uid = uid
        self.reg = reg
        self.bloco = bloco
        self.campo = campo
        self.indice = indice
        self.valor = valor
        self.motivo = motivo
        self.sugestao = sugestao      # None = exige decisão humana


# ---------------------------------------------------------------- domínios
class Dominio:
    """Um domínio de campo: sabe dizer se o valor serve e, quando o conserto
    é mecânico, qual seria o valor certo.

    `tamanho` só habilita a sugestão quando falta **exatamente um** dígito:
    repor dois zeros já seria inventar.
    """

    def __init__(self, rotulo, tamanho=None, conjunto=None, digitos=True,
                 normaliza=True, validador=None):
        self.rotulo = rotulo
        self.tamanho = tamanho
        self.conjunto = conjunto
        self.digitos = digitos
        self.normaliza = normaliza
        self.validador = validador

    def _serve(self, v):
        if self.validador is not None:
            return self.validador(v)
        if self.digitos and not RE_SO_DIGITOS.match(v):
            return False
        if self.tamanho is not None and len(v) != self.tamanho:
            return False
        if self.conjunto is not None and v not in self.conjunto:
            return False
        return True

    def avaliar(self, v):
        """Devolve `(motivo, sugestao)`; motivo None quer dizer que está ok.
        Sugestão `""` significa "esvaziar o campo"; `None`, "não sei
        consertar" — por isso a distinção é feita com `is None`."""
        if self._serve(v):
            return None, None
        # lixo textual de exportação: o conserto é esvaziar
        if v.upper() in VALORES_NULOS:
            return "texto de vazio gravado como valor (%s)" % v, ""
        sugestao = None
        if (self.normaliza and self.tamanho and RE_SO_DIGITOS.match(v)
                and len(v) == self.tamanho - 1):
            tentativa = v.zfill(self.tamanho)
            if self._serve(tentativa):
                sugestao = tentativa
        return self.diagnostico(v), sugestao

    def diagnostico(self, _v):
        """Motivo específico do valor; por padrão, o rótulo do domínio."""
        return self.rotulo


class DominioTabela(Dominio):
    """Domínio vindo de uma **tabela do PVA**, e não do código.

    É a forma preferida: a lista de códigos válidos acompanha a atualização do
    validador oficial sem ninguém mexer aqui. A sugestão só nasce quando o
    valor com o zero à esquerda reposto **existe na tabela** — nunca por
    palpite de formato.
    """

    # campo de decisão fiscal: aponta, mas nunca sugere (ver
    # `CAMPOS_DE_DECISAO`)
    sugere = True

    def __init__(self, rotulo, codigos, tabela="", versao="", sugere=None):
        Dominio.__init__(self, rotulo, normaliza=True, digitos=False)
        self.codigos = codigos
        self.tabela = tabela
        self.versao = versao
        self._tamanhos = sorted({len(c) for c in codigos})
        if sugere is not None:
            self.sugere = sugere

    def _equivalente(self, v):
        """O mesmo código, com **zeros à esquerda sobrando**.

        `COD_PAIS 01058` é o `1058` da tabela com um zero a mais — o PVA
        aceita, e apontar isso como erro produziria 141 falsos positivos num
        arquivo real. Falta de dígito é outra coisa: essa vira sugestão.
        """
        if not v.isdigit():
            return None
        nu = v.lstrip("0")
        for tam in self._tamanhos:
            if len(v) > tam:
                cand = nu.zfill(tam)
                if cand in self.codigos:
                    return cand
        return None

    def _serve(self, v):
        return v in self.codigos or self._equivalente(v) is not None

    def avaliar(self, v):
        motivo, sugestao = self._avaliar(v)
        return motivo, (sugestao if self.sugere else None)

    def _avaliar(self, v):
        if self._serve(v):
            return None, None
        if v.upper() in VALORES_NULOS:
            return "texto de vazio gravado como valor (%s)" % v, ""
        # código só de zeros é o "sem valor" do ERP noutra forma
        if v.isdigit() and not v.strip("0"):
            return ("%s preenchido só com zeros — é campo vazio disfarçado"
                    % self.rotulo), ""
        sugestao = None
        if v.isdigit():
            for tam in self._tamanhos:
                if tam > len(v) and v.zfill(tam) in self.codigos:
                    sugestao = v.zfill(tam)
                    break
        return ("%s fora da tabela oficial %s (v%s)"
                % (self.rotulo, self.tabela, self.versao or "?")), sugestao


class DominioCstIcms(Dominio):
    """O CST do ICMS merece diagnóstico próprio: o erro mais comum não é lixo,
    é o **CSOSN do fornecedor do Simples copiado sem o dígito de origem**.
    Dizer isso poupa o usuário de descobrir sozinho."""

    def diagnostico(self, v):
        if len(v) == 3 and v in CSOSN:
            return ("CSOSN do Simples (%s) sem o dígito de origem — informe o "
                    "CST da sua própria operação" % v)
        return self.rotulo


def _valida_cst_icms(v):
    if not RE_SO_DIGITOS.match(v):
        return False
    if len(v) == 3:
        # origem + situação, ou o CSOSN de três dígitos — a tabela única do
        # PVA lista 101, 102, 103, 201, 202, 203, 300, 400, 500 e 900 como
        # códigos válidos, e o validador oficial não reclama deles. Recusá-los
        # produzia 186 falsos positivos num arquivo real de supermercado.
        return v in CSOSN or (v[0] in ORIGENS and v[1:] in SITUACOES_ICMS)
    if len(v) == 4:                      # origem + CSOSN do Simples
        return v[0] in ORIGENS and v[1:] in CSOSN
    return False


def _valida_cfop(v):
    return (RE_SO_DIGITOS.match(v) is not None and len(v) == 4
            and v[0] in INICIAIS_CFOP)


def _valida_data(v):
    if not RE_SO_DIGITOS.match(v) or len(v) != 8:
        return False
    dia, mes, ano = int(v[:2]), int(v[2:4]), int(v[4:])
    if not (1 <= mes <= 12) or ano < 1900:
        return False
    dias = [31, 29 if (ano % 4 == 0 and (ano % 100 or ano % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= dia <= dias[mes - 1]


def _valida_numero(v):
    return RE_NUM_SPED.match(v) is not None


def _num_sugerido(v):
    """`11.24` -> `11,24`; `1.234,56` -> `1234,56`. Só quando o resultado é
    número válido no formato do SPED."""
    if "." not in v:
        return None
    t = v.replace(".", ",") if "," not in v else v.replace(".", "")
    return t if RE_NUM_SPED.match(t) else None


# Domínio por NOME de campo. Vale em qualquer registro que tenha o campo.
DOMINIOS = {
    "COD_NCM": Dominio("NCM deve ter 8 dígitos", tamanho=8),
    "CEST": Dominio("CEST deve ter 7 dígitos", tamanho=7),
    "COD_GEN": Dominio("gênero deve ter 2 dígitos", tamanho=2),
    "TIPO_ITEM": Dominio("tipo do item fora da tabela (00 a 10, 99)",
                         tamanho=2, conjunto=TIPOS_ITEM_0200),
    "CST_PIS": Dominio("CST de PIS fora da tabela", tamanho=2,
                       conjunto=CST_PIS_COFINS),
    "CST_COFINS": Dominio("CST de COFINS fora da tabela", tamanho=2,
                          conjunto=CST_PIS_COFINS),
    "COD_SIT": Dominio("situação do documento fora da tabela (00 a 08)",
                       tamanho=2, conjunto={"%02d" % n for n in range(0, 9)}),
    "IND_OPER": Dominio("indicador de operação deve ser 0 ou 1", tamanho=1,
                        conjunto={"0", "1"}, normaliza=False),
    "IND_EMIT": Dominio("indicador de emitente deve ser 0 ou 1", tamanho=1,
                        conjunto={"0", "1"}, normaliza=False),
    "IND_MOV": Dominio("indicador de movimento deve ser 0 ou 1", tamanho=1,
                       conjunto={"0", "1"}, normaliza=False),
    "IND_PROP": Dominio("indicador de propriedade deve ser 0, 1 ou 2",
                        tamanho=1, conjunto={"0", "1", "2"}, normaliza=False),
    # origem da mercadoria é decisão fiscal: aponta, mas não sugere
    "CST_ICMS": DominioCstIcms("CST do ICMS deve ser origem (0-8) + situação "
                               "(%s), ou um CSOSN do Simples"
                               % ",".join(sorted(SITUACOES_ICMS)),
                               validador=_valida_cst_icms, normaliza=False),
    "CFOP": Dominio("CFOP deve ter 4 dígitos começando por 1,2,3,5,6 ou 7",
                    validador=_valida_cfop, normaliza=False),
}
for _dt in ("DT_DOC", "DT_E_S", "DT_INV", "DT_INI", "DT_FIN", "DT_A_P",
            "DT_VCTO", "DT_DOC_INI", "DT_DOC_FIN"):
    DOMINIOS[_dt] = Dominio("data inválida (esperado DDMMAAAA)",
                            validador=_valida_data, normaliza=False)

# campos numéricos são reconhecidos pelo prefixo do nome
PREFIXOS_NUMERICOS = ("VL_", "ALIQ_", "QTD", "PERC_", "VL")
DOMINIO_NUMERO = Dominio("valor fora do formato numérico do SPED",
                         validador=_valida_numero, normaliza=False)


def _dominio_do_campo(nome):
    d = DOMINIOS.get(nome)
    if d is not None:
        return d
    if nome.startswith(PREFIXOS_NUMERICOS):
        return DOMINIO_NUMERO
    return None


# ------------------------------------------------------------------ varredura
class DominioTabelaCstIcms(DominioTabela):
    """Tabela do PVA para o CST do ICMS, com o diagnóstico que a tabela não
    dá: o erro mais comum não é código inexistente, é **CSOSN do fornecedor
    do Simples copiado sem o dígito de origem**.

    Nunca sugere: nem completar o zero (seria escolher a origem da
    mercadoria), nem esvaziar o `0` (o CST é obrigatório no C170 e no C190 —
    a normalização em lote apagava o campo e trocava um erro por outro).
    """

    sugere = False

    def avaliar(self, v):
        motivo, _sugestao = DominioTabela.avaliar(self, v)
        if motivo and len(v) == 3 and v in CSOSN:
            motivo = ("CSOSN do Simples (%s) sem o dígito de origem — informe "
                      "o CST da sua própria operação" % v)
        return motivo, None


class DominioFormato(Dominio):
    """Tipo e tamanho como o **descritor do PVA** os declara.

    O descritor diz, campo a campo: `tipo` (C texto, N numérico, D data),
    `tamanho` (`[3]` fixo, `60` máximo) e `casasdecimais`. Isso substitui a
    heurística por prefixo (`VL_`, `ALIQ_`), que errava nos dois sentidos —
    campo numérico sem prefixo conhecido passava, e campo de texto começando
    por `VL` era cobrado como número.
    """

    def __init__(self, campo, tipo, tamanho, decimais):
        self.campo = campo
        self.tipo = (tipo or "").upper()
        self.decimais = int(decimais) if str(decimais).isdigit() else 0
        self.fixo = None
        self.maximo = None
        t = (tamanho or "").strip()
        if t.startswith("[") and t.strip("[]").isdigit():
            self.fixo = int(t.strip("[]"))
        elif t.isdigit():
            self.maximo = int(t)
        Dominio.__init__(self, self._rotulo(), normaliza=True, digitos=False)

    def _rotulo(self):
        if self.tipo == "D":
            return "data inválida (esperado DDMMAAAA)"
        if self.tipo == "N":
            if self.decimais:
                return "valor fora do formato numérico do SPED"
            if self.fixo:
                return "deve ter exatamente %d dígitos" % self.fixo
            return "deve ser numérico"
        if self.fixo:
            return "deve ter exatamente %d caracteres" % self.fixo
        return "excede o tamanho de %s caracteres" % self.maximo

    def _serve(self, v):
        if self.tipo == "D":
            return _valida_data(v)
        if self.tipo == "N":
            if self.decimais:
                return _valida_numero(v)
            if not RE_SO_DIGITOS.match(v):
                return False
            if self.fixo is not None:
                return len(v) == self.fixo
            return self.maximo is None or len(v) <= self.maximo
        if self.fixo is not None:
            return len(v) == self.fixo
        return self.maximo is None or len(v) <= self.maximo

    def avaliar(self, v):
        if self._serve(v):
            return None, None
        if v.upper() in VALORES_NULOS:
            return "texto de vazio gravado como valor (%s)" % v, ""
        sugestao = None
        if (self.fixo and self.tipo == "N" and RE_SO_DIGITOS.match(v)
                and len(v) == self.fixo - 1):
            sugestao = v.zfill(self.fixo)
        return "%s: %s" % (self.campo, self.rotulo), sugestao


# Campos em que o conserto é decisão fiscal, não mecânica: apontados, nunca
# corrigidos em lote. Vale para o domínio embutido (`normaliza=False`) e para
# o que vem das tabelas do PVA.
CAMPOS_DE_DECISAO = frozenset(("CST_ICMS", "CFOP"))


def dominio_de_tabela(campo, rotulo, codigos, tabela="", versao=""):
    """O domínio certo para um campo validado contra tabela do PVA."""
    if campo == "CST_ICMS":
        return DominioTabelaCstIcms(rotulo, codigos, tabela, versao)
    return DominioTabela(rotulo, codigos, tabela, versao,
                         sugere=campo not in CAMPOS_DE_DECISAO)


def dominios_do_documento(doc):
    """Domínios **por (registro, campo)**, na granularidade em que o PVA
    valida. Três fontes, nesta ordem de preferência:

    1. **enumeração declarada no descritor** do PVA (`0=Entrada;1=Saída`) —
       inequívoca e específica do registro;
    2. **tabela externa**, quando o descritor aponta um datasource que
       corresponde a uma tabela instalada;
    3. **tipo e tamanho** do descritor, para todo campo que não caia em 1 ou 2.

    Campo que o descritor não declara não é validado. Era daí que vinha o
    falso positivo do `CST_ICMS` no EFD Contribuições: a regra global cobrava
    um domínio que aquele PVA não cobra.

    Devolve `(dominios, info)`; `({}, info)` quando o PVA não está instalado —
    aí a varredura cai nos domínios embutidos.

    O descritor e as tabelas vêm da porta `referencias`.
    """
    fonte = referencias.atual()
    i_uf = doc._ix("0000", "UF")
    i_fin = doc._ix("0000", "DT_FIN")
    uf = dt = ""
    for r in doc.registros:
        if r.reg == "0000":
            uf = (r.valor(i_uf) or "").strip() if i_uf is not None else ""
            dt = (r.valor(i_fin) or "").strip() if i_fin is not None else ""
            break

    estrutura, info_desc = fonte.estrutura(doc.layout)
    if not estrutura:
        return {}, {"descritor": None, "erro": info_desc.get("erro"),
                    "por_tabela": 0, "por_enum": 0, "por_formato": 0,
                    "faltando": []}

    por_tabela, faltando = fonte.dominios_por_datasource(
        estrutura, doc.layout, uf, dt)

    dominios = {}
    n_enum = n_tab = n_fmt = 0
    for reg, d in estrutura.items():
        for campo, c in d["campos"].items():
            chave = (reg, campo)
            if c.get("valores"):
                dominios[chave] = dominio_de_tabela(
                    campo, fonte.rotulo(campo), set(c["valores"]),
                    "descritor do PVA", info_desc.get("registros", ""))
                n_enum += 1
            elif chave in por_tabela:
                d2 = por_tabela[chave]
                dominios[chave] = dominio_de_tabela(
                    campo, d2["rotulo"], d2["codigos"], d2["tabela"],
                    d2["versao"])
                n_tab += 1
            elif c.get("tipo"):
                dominios[chave] = DominioFormato(campo, c["tipo"],
                                                 c["tamanho"], c["decimais"])
                n_fmt += 1
    return dominios, {"descritor": info_desc.get("descritor"),
                      "registros": info_desc.get("registros"),
                      "por_enum": n_enum, "por_tabela": n_tab,
                      "por_formato": n_fmt, "faltando": faltando,
                      "uf": uf, "data": dt}


def validar(doc, tipos=None, dominios_pva=None):
    """Varre o documento e devolve a lista de `Ocorrencia`. **Não altera nada.**

    `tipos` restringe a certos registros (ex.: `{"0200"}`); por padrão vale
    para o arquivo inteiro.

    `dominios_pva` são os domínios do PVA, por (registro, campo)
    (`dominios_do_documento`). Eles **substituem** os embutidos nos
    campos que cobrem: a tabela oficial é a fonte melhor, e os embutidos
    passam a valer só onde o PVA não tem tabela — ou quando ele não está
    instalado.
    """
    achados = []
    # chave (registro, campo) vem do descritor; chave só-campo, da versão
    # anterior por tabela; nenhuma das duas, dos domínios embutidos
    por_reg = {}
    extras = {}
    for chave, d in (dominios_pva or {}).items():
        if isinstance(chave, tuple):
            por_reg[chave] = (d if isinstance(d, Dominio)
                              else DominioTabela(d.get("rotulo", chave[1]),
                                                 d["codigos"],
                                                 d.get("tabela", ""),
                                                 d.get("versao", "")))
        else:
            extras[chave] = (d if isinstance(d, Dominio)
                             else DominioTabela(d.get("rotulo", chave),
                                                d["codigos"],
                                                d.get("tabela", ""),
                                                d.get("versao", "")))
    # com o descritor disponível, ele é a única fonte: campo que ele não
    # declara é campo que o PVA não cobra
    so_descritor = bool(por_reg)
    cache = {}                    # tipo -> [(indice, nome, dominio)]
    for r in doc.registros:
        if tipos and r.reg not in tipos:
            continue
        plano = cache.get((r.reg, len(r.campos)))
        if plano is None:
            nomes = campos(r.reg, doc.layout, len(r.campos))
            plano = []
            for i, nome in enumerate(nomes):
                if i == 0:
                    continue
                d = por_reg.get((r.reg, nome)) or extras.get(nome)
                if d is None and not so_descritor:
                    d = _dominio_do_campo(nome)
                if d is not None:
                    plano.append((i, nome, d))
            cache[(r.reg, len(r.campos))] = plano
        for i, nome, dom in plano:
            if i >= len(r.campos):
                continue
            v = (r.campos[i] or "").strip()
            if not v:                       # vazio não é erro de domínio
                continue
            motivo, sugestao = dom.avaliar(v)
            if motivo is None:
                continue
            if sugestao is None and dom is DOMINIO_NUMERO:
                sugestao = _num_sugerido(v)
            achados.append(Ocorrencia(r.uid, r.reg, r.bloco, nome, i, v,
                                      motivo, sugestao))
    return achados


def resumo(achados):
    """Agrupa por (registro, campo, motivo) para exibir o panorama.
    Devolve `[(reg, campo, motivo, total, com_sugestao, exemplo)]`."""
    grupos = {}
    for o in achados:
        chave = (o.reg, o.campo, o.motivo)
        g = grupos.setdefault(chave, [0, 0, o.valor])
        g[0] += 1
        if o.sugestao is not None:
            g[1] += 1
    return sorted(((k[0], k[1], k[2], v[0], v[1], v[2])
                   for k, v in grupos.items()), key=lambda x: -x[3])


def normalizar(doc, achados=None, campos_alvo=None):
    """Grava as sugestões — só as ocorrências que têm conserto mecânico.

    Recebe a lista já exibida ao usuário, para corrigir exatamente o que ele
    viu. `campos_alvo` restringe a certos nomes de campo.
    """
    if achados is None:
        # os mesmos domínios do diagnóstico: normalizar pelo embutido deixava
        # de fora o que o diagnóstico acusava pelas tabelas do PVA
        achados = validar(doc, dominios_pva=dominios_do_documento(doc)[0])
    por_uid = {r.uid: r for r in doc.registros}
    por_campo = {}
    n = 0
    for o in achados:
        if o.sugestao is None:
            continue
        if campos_alvo and o.campo not in campos_alvo:
            continue
        r = por_uid.get(o.uid)
        if r is None or o.indice >= len(r.campos):
            continue
        if (r.campos[o.indice] or "").strip() != o.valor:
            continue                      # mudou desde a verificação
        r.set_valor(o.indice, o.sugestao)
        por_campo[o.campo] = por_campo.get(o.campo, 0) + 1
        n += 1
    if por_campo:
        doc._cad_itens = None
    return {"campos": n, "por_campo": por_campo}

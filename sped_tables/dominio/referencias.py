# -*- coding: utf-8 -*-
"""Porta: o que o domínio precisa das **tabelas oficiais**.

Parte das regras fiscais depende de dados que não são do arquivo nem do
programa: a estrutura declarada de cada versão de leiaute, as tabelas de
códigos válidos com vigência, a tabela de CFOP com direito a crédito, o
prazo de entrega de cada período.

O domínio não sabe **onde** isso está nem **como** se lê: pede a esta porta,
e a versão do leiaute que pede é a do arquivo (`versao_do_leiaute`). Quem
liga a porta a uma implementação é a montagem da aplicação
(`sped_tables.aplicacao.montagem`), no início do programa; a implementação
de verdade é a base de referência (`sped_tables.infra.referencias_base`). A
porta em si não lê instalação nenhuma.

Sem nada ligado vale `Referencias` desta página, que não tem tabela
nenhuma: cada regra que depende dela se abstém, como já fazia quando o PVA
não estava instalado. É também o que permite testar uma regra com uma
tabela inventada, sem PVA nenhum na máquina.
"""


class Referencias:
    """Fonte de referências **vazia** — e a interface que as outras seguem."""

    nome = "nenhuma"

    def estrutura(self, layout, versao=None):
        """Estrutura do leiaute: `(estrutura, info)`.

        `versao` é a versão que o arquivo declara (`versao_do_leiaute`);
        `None` pede a mais recente da fonte — é o que vale para arquivo sem
        COD_VER legível. Versão que a fonte não guarda devolve estrutura
        vazia e `info["fora_da_base"]`: nada se cobra por estrutura de
        outra versão."""
        return {}, {"descritor": None,
                    "erro": "nenhuma base de referência ligada"}

    def versao_vigente(self, layout, data):
        """COD_VER vigente na data (DDMMAAAA), entre as versões que a fonte
        guarda; None quando nenhuma cobre a data."""
        return None

    def descricao(self):
        """De onde vêm as referências, numa linha, para as telas."""
        return "nenhuma base de referência"

    def dominios_por_datasource(self, estrutura, layout, uf=None,
                                data_ref=None):
        """Códigos válidos por (registro, campo): `(dominios, faltando)`."""
        return {}, []

    def rotulo(self, campo):
        """Nome legível do domínio de um campo, para as mensagens."""
        return campo

    def naturezas_cfop_credito(self, data_ref=None):
        """`{CFOP: NAT_BC_CRED}` da tabela 4.3.7 do EFD Contribuições."""
        return {}

    def cfops_com_credito(self, data_ref=None):
        """`(conjunto de CFOP que admitem crédito, versão da tabela)`."""
        return set(), ""

    def prazo_entrega(self, mes_ano):
        """Data limite (DDMMAAAA) da EFD Contribuições do período MMAAAA."""
        return ""

    def naturezas_receita(self, cst, data_ref=None):
        """Códigos de NAT_REC válidos para o CST do M400/M800 (tabelas
        4.3.10 a 4.3.16), ou None para "não sei" — a regra se abstém."""
        return None

    def ncms_da_natureza(self, codigo):
        """Prefixos de NCM do produto a que a natureza da receita `codigo`
        se refere, pelas tabelas 4.3.10 a 4.3.16."""
        return set()

    def tabela_natureza_receita(self, cst):
        """`[(código, [prefixos de NCM], ex_ipi)]` das naturezas da receita
        do CST (tabelas 4.3.10 a 4.3.16), ou vazio."""
        return []

    def classificador_ncm(self):
        """`ncm.ClassificadorNCM` com as tabelas de alíquota zero e
        monofásico do PVA, ou None."""
        return None

    def codigos_receita_icms(self, uf, data_ref=None):
        """`{código: descrição}` dos códigos de receita do ICMS da UF — o
        domínio do `COD_REC` do E116."""
        return {}

    def guia(self, layout):
        """O **guia prático** do leiaute, já extraído (ver
        `consolidador/guias.py`): `{"guia", "versao", "atualizacao",
        "registros": {reg: {"titulo", "objetivo", "validacao_registro",
        "observacoes", "nivel", "ocorrencia", "campos": {"n": {"nome",
        "valores", "preenchimento", "validacao"}}}}}`. Vazio quando não há."""
        return {}


def texto_do_campo(guia, reg, n, nome=""):
    """O que o guia diz do campo `n` (1 = REG) do registro: `{"nome",
    "valores", "preenchimento", "validacao", "texto"}`, ou `{}`.

    Quando o parágrafo do guia traz o nome e ele é outro, o texto não é
    deste campo — acontece quando o guia já descreve um leiaute mais novo
    que o do arquivo (o IND_BENEFICIO do E111) — e o retorno é vazio, em
    vez de ajuda errada."""
    d = (guia.get("registros") or {}).get(reg) or {}
    c = (d.get("campos") or {}).get(str(n)) or {}
    nome_guia = c.get("nome_no_paragrafo") or ""
    if nome and nome_guia and nome_guia != nome:
        return {}
    return c


def versao_do_leiaute(doc):
    """A versão do leiaute que o arquivo declara (COD_VER do 0000, ex.:
    "020"), ou None quando falta ou não tem três dígitos — aí vale a mais
    recente da fonte, como antes de a versão contar."""
    i = doc._ix("0000", "COD_VER")
    if i is None:
        return None
    for r in doc.registros:
        if r.reg == "0000":
            v = (r.valor(i) or "").strip()
            return v if len(v) == 3 and v.isdigit() else None
    return None


_atual = [Referencias()]


def atual():
    """A fonte ligada agora (a vazia, se ninguém ligou nenhuma)."""
    return _atual[0]


def definir(fonte):
    """Liga uma fonte; `None` volta à vazia. Devolve a anterior, para quem
    precisar restaurar (os testes)."""
    anterior = _atual[0]
    _atual[0] = fonte if fonte is not None else Referencias()
    return anterior


def alinhar_ao_leiaute(estrutura, layout):
    """O descritor com os campos **renomeados para os nomes do leiaute**,
    pela posição no registro.

    O PVA dá aos campos nomes internos que nem sempre são os do guia:
    `ENDERECO` no lugar de `END` (0150), `ALIQ_PIS_PERC` no de `ALIQ_PIS`
    (C170 do ICMS/IPI), `VL_OPER` no de `VL_OPR` (C175), `VL_COFIS` (sic) no
    C350. Quem consulta o arquivo pelo nome do descritor — obrigatoriedade,
    domínio, chave, referência — recebia `None` do `_ix` e **pulava o campo
    em silêncio**. O nome original fica em `id_pva`.

    A posição é a ordem dos `<campo>` no XML, não o atributo `n`, que tem
    erros de digitação (`n="17'"`, `n` repetido no 0220 e no C890). Campo
    além da largura do leiaute mantém o nome do PVA.
    """
    from sped_tables.dominio import sped_layouts
    tabela = (sped_layouts.CAMPOS_CONTRIB if layout == "CONTRIB"
              else sped_layouts.CAMPOS_ICMS)
    nomes_por_reg = {}
    out = {}
    for reg, d in estrutura.items():
        nomes = tabela.get(reg) or []
        traducao = {}
        campos = {}
        for i, (id_pva, c) in enumerate(d.get("campos", {}).items()):
            nome = nomes[i] if i < len(nomes) else id_pva
            traducao[id_pva] = nome
            campos[nome] = dict(c, id_pva=id_pva, pos=i + 1)
        nomes_por_reg[reg] = traducao
        out[reg] = dict(d, campos=campos)
    for reg, d in out.items():
        traducao = nomes_por_reg[reg]
        if d.get("chave"):
            d["chave"] = ",".join(traducao.get(c.strip(), c.strip())
                                  for c in d["chave"].split(","))
        for c in d["campos"].values():
            ref = c.get("referencia")
            if ref and ";" in ref:
                alvo, campo_alvo = (x.strip() for x in ref.split(";", 1))
                campo_alvo = nomes_por_reg.get(alvo, {}).get(campo_alvo,
                                                             campo_alvo)
                c["referencia"] = "%s;%s" % (alvo, campo_alvo)
    return out


def do_descritor(estrutura):
    """`{(registro, campo): (registro_alvo, campo_alvo)}` — de onde o PVA
    cobra que o código exista. É o mapa que faz "COD_ITEM do C170 tem de
    estar no 0200" deixar de ser regra escrita à mão.

    Leitura pura da estrutura do descritor: vale para qualquer fonte.
    """
    out = {}
    for reg, d in estrutura.items():
        for nome, c in d["campos"].items():
            ref = c.get("referencia")
            if not ref or ";" not in ref:
                continue
            alvo, campo_alvo = ref.split(";", 1)
            out[(reg, nome)] = (alvo.strip(), campo_alvo.strip())
    return out

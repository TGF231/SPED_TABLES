# -*- coding: utf-8 -*-
"""Gerar o SPED de um período só com os XMLs e a memória da empresa.

O XML diz **o que aconteceu** (quem vendeu o quê, por quanto, com que
imposto destacado); a memória (`memoria_itens`) diz **como a empresa
escritura** — o código próprio do produto, o CFOP de entrada, o CST, o
crédito, a unidade do cadastro, o contabilista, o código de receita. O que
nenhum dos dois responde vai para `Resultado.revisar`, com o motivo: o
gerador usa uma regra para não parar, mas **aponta**, e quem decide é a
pessoa.

O cálculo que já passou no PVA não é refeito aqui. Os itens (C170) de todos
os documentos são montados primeiro — inclusive os da NFC-e e da NF-e
própria, que o EFD ICMS/IPI não quer —, o C190 sai de
`SpedDocument.consolidar_c190` (o mesmo do botão, com o rateio de frete e a
redução de base) e só depois os C170 que o leiaute não pede são retirados.
Cálculo que gera e cálculo que confere continuam sendo o mesmo código.
"""

import calendar

from sped_tables.dominio import diagnostico, referencias
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio.sped_layouts import CAMPOS_CONTRIB, CAMPOS_ICMS
from sped_tables.dominio.sped_model import (SpedDocument, _fmt_aliq_pct,
                                            _fmt_qtd, _fmt_val, _to_num,
                                            so_digitos)

# ---------------------------------------------------------------- situação
# CST do ICMS (dois últimos dígitos) sem débito próprio: nada de crédito
SEM_CREDITO_ICMS = ("30", "40", "41", "50", "60")
# campos do C100 que a NFC-e (65) deixa vazios — o PVA acusa
# MSG_NFE_CONSUMIDOR em cada um que vier preenchido, mesmo com zero
NFCE_C100_VAZIOS = ("VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI")
# CST de PIS/COFINS de entrada com crédito: só neles o item tem base
CST_COM_CREDITO = {"50", "51", "52", "53", "54", "55", "56",
                   "60", "61", "62", "63", "64", "65", "66"}


class Resultado:
    """O SPED gerado e tudo o que a pessoa precisa ver antes de usá-lo."""

    def __init__(self):
        self.doc = None
        self.revisar = []        # [{"tipo", "documento", "item", "detalhe"}]
        self.fora_periodo = []   # [(chave, data)]
        self.ignorados = []      # [(chave, motivo)]
        self.participantes_novos = {}   # documento -> código atribuído
        self.contagem = {}
        # chaves fora do período que a pessoa mandou incluir: documentos
        # extemporâneos (COD_SIT 01/07; o ICMS da saída vai para o DEB_ESP)
        self.extemporaneos = set()

    def apontar(self, tipo, documento, item, detalhe, bloqueia=False,
                dados=None):
        """`bloqueia`: o arquivo sairia inválido (um CFOP em branco, por
        exemplo) — a tela não deixa gravar enquanto houver algum. `dados`
        identifica o produto (fornecedor, código dele, CFOP e CST de
        origem), para a decisão da pessoa voltar para a memória."""
        self.revisar.append({"tipo": tipo, "documento": documento,
                             "item": item, "detalhe": detalhe,
                             "bloqueia": bloqueia, "dados": dados or {}})

    @property
    def bloqueios(self):
        return [r for r in self.revisar if r["bloqueia"]]


def _data(iso):
    """`2026-06-01T10:00:00-03:00` → `01062026`."""
    iso = (iso or "").strip()
    return iso[8:10] + iso[5:7] + iso[0:4] if len(iso) >= 10 else ""


def _periodo_de(ddmmaaaa):
    return ddmmaaaa[4:8] + ddmmaaaa[2:4] if len(ddmmaaaa) == 8 else ""


def limites(periodo):
    """`AAAAMM` → (`01MMAAAA`, `ddMMAAAA` do último dia)."""
    ano, mes = int(periodo[:4]), int(periodo[4:6])
    ultimo = calendar.monthrange(ano, mes)[1]
    return ("01%02d%04d" % (mes, ano), "%02d%02d%04d" % (ultimo, mes, ano))


class _Linhas:
    """Registros montados pelo **nome** dos campos, na largura do leiaute."""

    def __init__(self, layout, larguras=None):
        self.tabela = CAMPOS_CONTRIB if layout == "CONTRIB" else CAMPOS_ICMS
        self.linhas = []
        # largura de cada registro na versão de leiaute que a empresa usa
        # (aprendida do SPED entregue): o 0200 do EFD Contribuições tem 12
        # campos no PVA, e o leiaute do programa, 13 — a mais é recusa
        self.larguras = larguras or {}

    def reg(self, tipo, **valores):
        nomes = self.tabela[tipo]
        sobra = set(valores) - set(nomes)
        if sobra:
            raise KeyError("%s não tem %s" % (tipo, sorted(sobra)))
        campos = [valores.get(n, "") for n in nomes]
        campos[0] = tipo
        self.linhas.append(campos)

    def bloco_vazio(self, bloco):
        """Abertura "sem dados" e encerramento, pelo nome que o leiaute dá
        ao primeiro campo (IND_MOV, ou IND_DAD no bloco B)."""
        abre = self.tabela[bloco + "001"][1]
        fecha = self.tabela[bloco + "990"][1]
        self.reg(bloco + "001", **{abre: "1"})
        self.reg(bloco + "990", **{fecha: "0"})

    def modelo(self, campos, **troca):
        """Registro copiado de um modelo da memória, com campos trocados."""
        tipo = campos[0]
        nomes = self.tabela[tipo]
        c = list(campos) + [""] * (len(nomes) - len(campos))
        for nome, v in troca.items():
            c[nomes.index(nome)] = v
        self.linhas.append(c)

    def texto(self):
        linhas = []
        for c in self.linhas:
            n = self.larguras.get(c[0])
            if n:
                c = (list(c) + [""] * n)[:n]
            linhas.append("|" + "|".join(c) + "|")
        return "\r\n".join(linhas) + "\r\n"


# ---------------------------------------------------------- classificação
def classificar(lote, cnpj, periodo, res, regra_data=None, excluir=(),
                incluir=()):
    """Separa o que é da empresa no período: `{"entradas", "saidas",
    "fretes_entrada", "fretes_saida"}` — e diz o que ficou de fora.

    Documento com data de outro mês vai para `res.fora_periodo` — **a não
    ser** que a chave esteja em `incluir`: aí é a pessoa dizendo que é
    extemporâneo (o cupom em contingência transmitido no mês seguinte), e
    ele entra, anotado em `res.extemporaneos`. Nunca se decide isso
    sozinho."""
    cnpj = so_digitos(cnpj)
    data_entrada = regra_data or "saida"
    grupos = {"entradas": [], "saidas": [], "fretes_entrada": [],
              "fretes_saida": []}

    def no_periodo(ddmmaaaa):
        return _periodo_de(ddmmaaaa) == periodo

    for n in lote.nfes:
        if n.chave in excluir:
            res.ignorados.append((n.chave, "desmarcado"))
            continue
        emit = so_digitos(n.emit.documento) if n.emit else ""
        dest = so_digitos(n.dest.documento) if n.dest else ""
        if emit == cnpj:
            grupo, data = "saidas", _data(n.dhemi)
        elif dest == cnpj:
            grupo = "entradas"
            data = (_data(n.dhemi) if data_entrada == "emissao"
                    else _data(n.dhsaient or n.dhemi))
        else:
            res.ignorados.append((n.chave, "a empresa não é emitente nem "
                                           "destinatária"))
            continue
        if n.situacao == "cancelada":
            data = _data(n.dhemi)
        if not no_periodo(data):
            if n.chave not in incluir:
                res.fora_periodo.append((n.chave, data))
                continue
            res.extemporaneos.add(n.chave)
        grupos[grupo].append(n)
    for c in lote.ctes:
        if c.chave in excluir:
            res.ignorados.append((c.chave, "desmarcado"))
            continue
        emit = so_digitos(c.emit.documento) if c.emit else ""
        toma = so_digitos(c.toma.documento) if c.toma else ""
        if emit == cnpj:
            grupo = "fretes_saida"
        elif toma == cnpj:
            grupo = "fretes_entrada"
        else:
            res.ignorados.append((c.chave, "a empresa não é emitente nem "
                                           "tomadora do CT-e"))
            continue
        data = _data(c.dhemi)
        if not no_periodo(data):
            if c.chave not in incluir:
                res.fora_periodo.append((c.chave, data))
                continue
            res.extemporaneos.add(c.chave)
        grupos[grupo].append(c)
    return grupos


def _cod_sit(doc, extemporaneos=()):
    if doc.situacao == "cancelada":
        return "02"
    if doc.situacao == "denegada":
        return "04"
    complementar = getattr(doc, "fin", None) == "2"
    if doc.chave in extemporaneos:
        return "07" if complementar else "01"
    return "06" if complementar else "00"


# ------------------------------------------------------------ participante
class _Participantes:
    def __init__(self, memoria, res):
        self.m, self.res = memoria, res
        self.usados = {}           # documento -> (código, Participante)

    def codigo(self, p):
        documento = so_digitos(p.documento)
        if documento in self.usados:
            return self.usados[documento][0]
        cod = mi.cod_participante(self.m, documento) \
            or self.res.participantes_novos.get(documento)
        if not cod:
            ja = dict(self.m["participantes"])
            ja.update(self.res.participantes_novos)
            cod = mi.proximo_cod_participante({"participantes": ja})
            self.res.participantes_novos[documento] = cod
        self.usados[documento] = (cod, p)
        return cod

    def registros(self, linhas):
        for documento, (cod, p) in sorted(self.usados.items(),
                                          key=lambda x: x[1][0]):
            linhas.reg("0150", COD_PART=cod, NOME=p.nome[:100],
                       COD_PAIS="1058", CNPJ=p.cnpj, CPF=p.cpf, IE=p.ie,
                       COD_MUN=p.cod_mun, SUFRAMA=p.suframa or "",
                       END=p.lgr[:60], NUM=p.nro[:10], COMPL=p.compl[:60],
                       BAIRRO=p.bairro[:60])


# ------------------------------------------------------------------ itens
class _Itens:
    """Código, unidade e escrituração de cada item de entrada, pela memória
    — e o que ela não sabe, apontado."""

    def __init__(self, memoria, res, correlacoes, uf_empresa,
                 contrib=False):
        self.m, self.res = memoria, res
        self.correlacoes = correlacoes or {}
        self.uf = uf_empresa
        self.contrib = contrib       # EFD Contribuições: PIS/COFINS e conta
        self.cadastro_usado = {}     # código -> campos do 0200
        self.unidades = {}           # unidade -> descrição
        self.naturezas = {}          # COD_NAT -> descrição (0400)
        self.contas = set()          # COD_CTA usadas (0500)
        self._atual = {}             # o produto em escrituração agora
        self.vendidos_novos = []     # produtos próprios fora da memória

    def _apontar(self, *args, **k):
        # o mesmo dict em todos os apontamentos do item: a escrituração
        # usada ("usado") só se conhece depois, e entra em todos eles
        self.res.apontar(*args, dados=self._atual, **k)

    def entrada(self, nfe, item):
        """Campos do C170 de um item comprado."""
        onde = "NF %s/%s" % (nfe.serie, nfe.nnf)
        emit = nfe.emit.documento
        self._atual = {"fornecedor": so_digitos(emit), "cprod": item.cprod,
                       "xprod": item.xprod, "cfop": item.cfop or "",
                       "cst": item.icms_cst or ""}
        cod, ambiguo = mi.codigo_proprio(self.m, emit, item.cprod)
        if cod is None:
            cod = ("%s-%s" % (so_digitos(emit)[:8], item.cprod))[:60]
            self._apontar("produto sem código próprio", onde, item.nitem,
                             "%s (código do fornecedor %s): usei %s"
                             % (item.xprod, item.cprod, cod))
        elif ambiguo:
            self._apontar("código próprio ambíguo", onde, item.nitem,
                             "%s: a empresa já usou mais de um código; usei "
                             "o mais frequente, %s" % (item.xprod, cod))
        fator, fator_amb = mi.fator_conversao(self.m, emit, item.cprod)
        if fator_amb:
            self._apontar("conversão de unidade ambígua", onde,
                             item.nitem, "%s: usei o fator %s"
                             % (item.xprod, _fmt_qtd(fator)))
        esc = mi.escrituracao(self.m, emit, item.cprod, item)
        if esc is None:
            esc = self._regra(nfe, item, onde)
        # a decisão da pessoa parte do que foi usado aqui
        self._atual["usado"] = {k: v for k, v in esc.items()
                                if k in mi.ESCRITURACAO}
        cad = self._cadastro(cod, item)
        nat = esc.get("COD_NAT", "")
        if nat:
            self.naturezas.setdefault(
                nat, self.m.get("naturezas", {}).get(nat, ""))
            if not self.naturezas[nat]:
                self._apontar("natureza sem descrição", "0400", nat,
                                 "a memória não tem a descrição do COD_NAT")
        unid = cad.get("UNID_INV") or item.unid or ""
        self.unidades.setdefault(unid, self.m["unidades"].get(unid, unid))
        credita = esc.get("CREDITA_ICMS") == "S"
        campos = {
            "COD_ITEM": cod, "QTD": _fmt_qtd((item.qtd or 0) * (fator or 1)),
            "UNID": unid, "VL_ITEM": _fmt_val(item.vprod or 0),
            "VL_DESC": _fmt_val(item.vdesc or 0), "IND_MOV": "0",
            "CST_ICMS": esc.get("CST_ICMS", ""), "CFOP": esc.get("CFOP", ""),
            "COD_NAT": esc.get("COD_NAT", ""),
            "VL_BC_ICMS": _fmt_val(item.icms_vbc if credita else 0),
            "ALIQ_ICMS": (_fmt_aliq_pct(item.icms_aliq) or "0")
            if credita else "0",
            "VL_ICMS": _fmt_val(item.icms_vicms if credita else 0),
            "VL_BC_ICMS_ST": "0", "ALIQ_ST": "0", "VL_ICMS_ST": "0",
            "IND_APUR": "0", "CST_IPI": esc.get("CST_IPI", ""),
            "VL_BC_IPI": "0", "ALIQ_IPI": "0", "VL_IPI": "0",
        }
        if self.contrib:
            # No EFD Contribuições o item vale com as outras despesas dele,
            # e o ICMS do item é o do documento (informativo): é o valor da
            # operação que forma a base do PIS/COFINS. Assim estava no mês
            # real — e o ICMS/IPI do mesmo mês, com a escrituração do ICMS
            # da empresa e o item sem as despesas.
            campos.update(
                VL_ITEM=_fmt_val((item.vprod or 0) + (item.voutro or 0)),
                # CSOSN do fornecedor do Simples (origem + 3) não cabe no
                # CST: aí vale o da escrituração da empresa
                CST_ICMS=(item.icms_cst if len(item.icms_cst or "") == 3
                          else esc.get("CST_ICMS", "")),
                VL_BC_ICMS=_fmt_val(item.icms_vbc or 0),
                ALIQ_ICMS=_fmt_aliq_pct(item.icms_aliq) or "0",
                VL_ICMS=_fmt_val(item.icms_vicms or 0))
            campos.update(self._pis_cofins(esc, item, onde))
        return campos

    def _pis_cofins(self, esc, item, onde):
        """PIS/COFINS do item de entrada como a empresa escritura: CST e
        alíquota da memória. A base, só nas entradas **com crédito**, é o
        valor do item menos o ICMS (o ICMS fora da base, como decidiu o
        STF); sem crédito, zero."""
        valor = ((item.vprod or 0) + (item.voutro or 0) - (item.vdesc or 0))
        out = {}
        for trib in ("PIS", "COFINS"):
            cst = esc.get("CST_" + trib, "")
            aliq = esc.get("ALIQ_" + trib, "") or "0"
            base = (round(valor - (item.icms_vicms or 0), 2)
                    if cst in CST_COM_CREDITO else 0.0)
            if not cst:
                self._apontar(
                    "CST de %s desconhecido" % trib, onde, item.nitem,
                    "%s: nem a memória nem a prática da empresa dizem o CST "
                    "de %s desta entrada" % (item.xprod, trib), bloqueia=True)
            out.update({
                "CST_" + trib: cst, "VL_BC_" + trib: _fmt_val(base),
                "ALIQ_" + trib: aliq,
                "VL_" + trib: _fmt_val(round(base * _to_num(aliq) / 100,
                                             2))})
        conta = esc.get("COD_CTA", "")
        if conta:
            self.contas.add(conta)
        out["COD_CTA"] = conta
        return out

    def _regra(self, nfe, item, onde):
        """Sem memória do produto nesta situação. Primeiro, a **prática da
        empresa** para o mesmo CFOP e CST de fornecedor (aprendida de todos
        os produtos); sem ela, a correlação de CFOP e o CST do fornecedor.
        Nos dois casos, apontado."""
        vista = mi.pratica(self.m, item)
        if vista is not None:
            esc, parcela = vista
            self._apontar(
                "escrituração pela prática da empresa", onde, item.nitem,
                "%s (CFOP %s, CST %s do fornecedor, produto nunca "
                "escriturado): usei CFOP %s e CST %s, como em %d%% dos "
                "casos iguais" % (item.xprod, item.cfop, item.icms_cst,
                                  esc["CFOP"], esc["CST_ICMS"],
                                  round(parcela * 100)))
            return esc
        opcoes = sorted(self.correlacoes.get(item.cfop or "", ()))
        if item.cfop and nfe.emit and nfe.emit.uf and self.uf:
            prefixo = "1" if nfe.emit.uf == self.uf else "2"
            opcoes = [c for c in opcoes if c.startswith(prefixo)] or opcoes
        cfop = opcoes[0] if opcoes else ""
        cst = item.icms_cst or ""
        credita = (bool(item.icms_vicms)
                   and cst[-2:] not in SEM_CREDITO_ICMS and len(cst) == 3)
        if not cfop:
            # nem memória, nem prática, nem correlação: não há de onde tirar
            # o CFOP, e em branco o PVA recusa o item
            self._apontar(
                "CFOP de entrada desconhecido", onde, item.nitem,
                "%s: o CFOP %s do fornecedor nunca apareceu nesta empresa e "
                "não está nas correlações de CFOP — informe o CFOP de "
                "entrada" % (item.xprod, item.cfop), bloqueia=True)
        else:
            self._apontar(
                "escrituração sem memória", onde, item.nitem,
                "%s (CFOP %s, CST %s do fornecedor): usei CFOP %s, CST %s, "
                "%scrédito" % (item.xprod, item.cfop, item.icms_cst, cfop,
                               cst or "?", "com " if credita else "sem "))
        return {"CFOP": cfop, "CST_ICMS": cst,
                "CREDITA_ICMS": "S" if credita else "N"}

    def _cadastro(self, cod, item, apontar=True):
        if cod in self.cadastro_usado:
            return self.cadastro_usado[cod]
        cad = self.m["cadastro"].get(cod)
        if cad is None:
            cad = _cadastro_do_xml(item)
            if apontar:
                self._apontar("produto fora do cadastro", "0200", cod,
                              "cadastro montado do XML (tipo 00 — mercadoria "
                              "para revenda); confira")
            else:
                self.vendidos_novos.append(cod)
        self.cadastro_usado[cod] = cad
        return cad

    def saida(self, item):
        """Cadastra no 0200 (e a unidade no 0190) o produto de um documento
        **emitido pela empresa** — NF-e e NFC-e de venda. O código já é o
        próprio (`cProd`); o cadastro é o que a empresa declarou no SPED
        entregue e, para produto que a memória não conhece, o do XML. O
        0200 precisa listar o que a empresa movimentou, mesmo quando o
        documento não leva C170 (a NFC-e)."""
        cod = (item.cprod or "").strip()[:60]
        if not cod:
            return
        cad = self._cadastro(cod, item, apontar=False)
        unid = cad.get("UNID_INV") or item.unid or ""
        if unid:
            self.unidades.setdefault(unid, self.m["unidades"].get(unid, unid))

    def registros(self, linhas):
        if self.vendidos_novos:
            novos = sorted(set(self.vendidos_novos))
            self.res.apontar(
                "produtos vendidos fora do cadastro", "0200",
                "%d produto(s)" % len(novos),
                "a memória não tem o cadastro de %d produto(s) vendido(s) "
                "(%s%s): o 0200 foi montado do XML (tipo 00 — mercadoria "
                "para revenda); confira" % (
                    len(novos), ", ".join(novos[:10]),
                    "…" if len(novos) > 10 else ""))
            self.vendidos_novos = []
        for unid in sorted(self.unidades):
            linhas.reg("0190", UNID=unid, DESCR=self.unidades[unid] or unid)
        for cod in sorted(self.cadastro_usado):
            cad = self.cadastro_usado[cod]
            linhas.reg("0200", COD_ITEM=cod,
                       **{c: cad.get(c, "") for c in mi.CAMPOS_0200})
        for nat in sorted(self.naturezas):
            linhas.reg("0400", COD_NAT=nat,
                       DESCR_NAT=self.naturezas[nat] or nat)


def _cadastro_do_xml(item):
    """Os campos do 0200 que o XML do produto diz."""
    return {"DESCR_ITEM": (item.xprod or "")[:255],
            "COD_BARRA": item.cean or "",
            "UNID_INV": item.unid or "", "TIPO_ITEM": "00",
            "COD_NCM": item.ncm or "",
            "CEST": getattr(item, "cest", "") or ""}


# --------------------------------------------------------------- ICMS/IPI
def gerar_icms(memoria, lote, periodo, saldo_credor_anterior=None,
               correlacoes=None, excluir=(), incluir=()):
    """O EFD ICMS/IPI do período (`AAAAMM`). Devolve `Resultado`.

    `saldo_credor_anterior` é o do E110 do mês anterior; sem ele, vale o que
    a memória guardou daquele mês (e, sem nada, zero — apontado).
    """
    res = Resultado()
    modelos = memoria.get("modelos", {}).get("ICMS")
    if not modelos or "0000" not in modelos:
        raise ValueError(
            "A memória desta empresa ainda não tem o cabeçalho do EFD "
            "ICMS/IPI: aprenda primeiro com um SPED entregue.")
    ini, fim = limites(periodo)
    entrada_pad = memoria.get("padroes", {}).get("entrada", {})
    grupos = classificar(lote, memoria["cnpj"], periodo, res,
                         entrada_pad.get("DT_E_S"), set(excluir or ()),
                         set(incluir or ()))
    uf = _modelo_valor(modelos["0000"], "UF", "ICMS")
    part = _Participantes(memoria, res)
    itens = _Itens(memoria, res, correlacoes, uf)
    padroes = memoria.get("padroes", {}).get("ICMS", {})

    # ---- bloco C: documentos (com C170 de todos, por enquanto)
    c = _Linhas("ICMS")
    docs = sorted(grupos["entradas"] + grupos["saidas"],
                  key=lambda n: (_data(n.dhemi)[4:] + _data(n.dhemi)[2:4]
                                 + _data(n.dhemi)[:2], n.mod, n.serie,
                                 int(n.nnf or 0)))
    for n in docs:
        entrada = n in grupos["entradas"]
        oper = "0" if entrada else "1"
        sit = _cod_sit(n, res.extemporaneos)
        base = dict(IND_OPER=oper, IND_EMIT="1" if entrada else "0",
                    COD_MOD=n.mod, COD_SIT=sit, SER=n.serie or "",
                    NUM_DOC=n.nnf, CHV_NFE=n.chave)
        if sit in ("02", "04"):
            c.reg("C100", **base)
            continue
        pad = padroes.get("%s|%s" % (n.mod, oper), {})
        # no ICMS/IPI o extemporâneo vai com a data real do XML
        data_doc = _data(n.dhemi)
        if entrada:
            data_es = (data_doc if entrada_pad.get("DT_E_S") == "emissao"
                       else _data(n.dhsaient) or data_doc)
            frete = 0.0 if entrada_pad.get("VL_FRT") == "zero" else n.vfrete
        else:
            data_es = ((_data(n.dhsaient) or data_doc) if n.mod == "55"
                       else data_doc)
            frete = n.vfrete
        c.reg("C100", **base,
              COD_PART=part.codigo(n.emit) if entrada else (
                  part.codigo(n.dest) if n.dest and n.mod == "55" else ""),
              DT_DOC=data_doc,
              DT_E_S=data_es,
              VL_DOC=_fmt_val(n.vnf), IND_PGTO=pad.get("IND_PGTO", "2"),
              VL_DESC=_fmt_val(n.vdesc), VL_ABAT_NT="0",
              VL_MERC=_fmt_val(n.vprod), IND_FRT=pad.get("IND_FRT", "9"),
              VL_FRT=_fmt_val(frete), VL_SEG=_fmt_val(n.vseg),
              VL_OUT_DA=_fmt_val(n.voutro), VL_BC_ICMS="0", VL_ICMS="0",
              VL_BC_ICMS_ST="0", VL_ICMS_ST="0", VL_IPI="0")
        for k, it in enumerate(n.itens, 1):
            if entrada:
                campos = itens.entrada(n, it)
            else:
                campos = _item_proprio(it)
                itens.saida(it)
            c.reg("C170", NUM_ITEM=str(it.nitem or k), **campos)

    # ---- bloco D: CT-e
    d = _Linhas("ICMS")
    for ct in sorted(grupos["fretes_entrada"] + grupos["fretes_saida"],
                     key=lambda x: (_data(x.dhemi), int(x.nct or 0))):
        _cte_icms(d, ct, ct in grupos["fretes_entrada"], part, res, uf)
    if res.extemporaneos:
        res.apontar("documento extemporâneo", "C100", "",
                    "%d documento(s) de outro mês incluído(s) por escolha, "
                    "com COD_SIT 01 (07 no complementar); o ICMS das saídas "
                    "vai para o DEB_ESP do E110 e para o E116"
                    % len(res.extemporaneos))

    # ---- o documento, montado e calculado pelo código de sempre
    _apontar_leiaute_do_periodo(res, "ICMS", fim)
    t = _Linhas("ICMS", _larguras(memoria, "ICMS", fim))
    t.modelo(modelos["0000"], DT_INI=ini, DT_FIN=fim, COD_FIN="0")
    t.reg("0001", IND_MOV="0")
    for tipo in ("0002", "0005", "0100"):
        if tipo in modelos:
            t.modelo(modelos[tipo])
    part.registros(t)
    itens.registros(t)
    t.reg("0990", QTD_LIN_0="0")
    vazios = memoria.get("blocos_vazios", {}).get("ICMS", [])
    if "B" in vazios:
        t.bloco_vazio("B")
    t.reg("C001", IND_MOV="0" if c.linhas else "1")
    t.linhas += c.linhas
    t.reg("C990", QTD_LIN_C="0")
    t.reg("D001", IND_MOV="0" if d.linhas else "1")
    t.linhas += d.linhas
    t.reg("D990", QTD_LIN_D="0")
    doc = SpedDocument.de_texto(t.texto())
    _calcular_c(doc)

    # ---- apuração
    e = _apuracao_icms(doc, memoria, modelos, periodo, ini, fim,
                       saldo_credor_anterior, res)
    for bloco in ("G", "H", "K"):
        if bloco in vazios:
            e.bloco_vazio(bloco)
    e.reg("1001", IND_MOV="0")
    if "1010" in modelos:
        e.modelo(modelos["1010"])
    e.reg("1990", QTD_LIN_1="0")
    doc = SpedDocument.de_texto(doc.gerar_texto() + e.texto())
    # gerar_texto refaz o bloco 9 e os X990 na ordem certa
    res.doc = SpedDocument.de_texto(doc.gerar_texto())
    res.contagem = {k: len(v) for k, v in grupos.items()}
    return res


def _apontar_leiaute_do_periodo(res, layout, fim):
    """Período que nenhuma versão do leiaute da base cobre (`fim`,
    DDMMAAAA): `_larguras` segue na versão mais recente, como sempre fez, e
    isto **diz** que foi assim — apontamento que não bloqueia. Sem base
    ligada não há versão que tenha valido, e nada se aponta."""
    fonte = referencias.atual()
    if fonte.versao_vigente(layout, fim) is not None:
        return
    estrutura, info = fonte.estrutura(layout, None)
    if not estrutura:
        return
    res.apontar(
        "leiaute do período fora da base", "0000", "",
        "O período %s/%s não está coberto por nenhuma versão do leiaute %s "
        "da base de referência: a largura dos registros veio da versão mais "
        "recente (%s). Confira o COD_VER do arquivo e, se ele for de um "
        "leiaute mais novo, importe uma base mais nova em Configurações → "
        "Base de referência…"
        % (fim[2:4], fim[4:], "ICMS/IPI" if layout == "ICMS"
           else "Contribuições", info.get("versao") or "?"))


def _larguras(memoria, layout, fim):
    """Largura de cada registro: a do SPED que a empresa entregou, limitada
    pela do descritor da versão vigente no fim do período (`fim`,
    DDMMAAAA) — vale a menor, que é o que o PVA aceita (o 0200 do EFD
    Contribuições tem 12 campos lá e 13 no leiaute do programa)."""
    larguras = dict(memoria.get("larguras", {}).get(layout) or {})
    fonte = referencias.atual()
    estrutura, _info = fonte.estrutura(layout,
                                       fonte.versao_vigente(layout, fim))
    if estrutura:
        for reg, n in diagnostico._num_campos_descritor(estrutura).items():
            larguras[reg] = min(larguras.get(reg, n), n)
    return larguras


def _modelo_valor(campos, nome, layout):
    tabela = CAMPOS_CONTRIB if layout == "CONTRIB" else CAMPOS_ICMS
    i = tabela[campos[0]].index(nome)
    return campos[i] if i < len(campos) else ""


def _item_proprio(it):
    """C170 provisório de documento emitido pela empresa: o código já é o
    próprio, e o CST, o CFOP e o imposto são os do XML."""
    return {
        "COD_ITEM": it.cprod or "", "QTD": _fmt_qtd(it.qtd or 0),
        "UNID": it.unid or "", "VL_ITEM": _fmt_val(it.vprod or 0),
        "VL_DESC": _fmt_val(it.vdesc or 0), "IND_MOV": "0",
        "CST_ICMS": it.icms_cst or "", "CFOP": it.cfop or "",
        "VL_BC_ICMS": _fmt_val(it.icms_vbc or 0),
        "ALIQ_ICMS": _fmt_aliq_pct(it.icms_aliq) or "0",
        "VL_ICMS": _fmt_val(it.icms_vicms or 0),
        "VL_BC_ICMS_ST": _fmt_val(it.icms_vbcst or 0),
        "ALIQ_ST": _fmt_aliq_pct(it.icms_aliqst) or "0",
        "VL_ICMS_ST": _fmt_val(it.icms_vicmsst or 0), "IND_APUR": "0",
        "VL_BC_IPI": "0", "ALIQ_IPI": "0", "VL_IPI": _fmt_val(it.vipi or 0),
    }


def _calcular_c(doc):
    """C190 pelo recálculo de sempre; totais do C100 pela soma do C190; e
    retira os C170 que o EFD ICMS/IPI não quer (NFC-e e NF-e própria).

    A soma do VL_OPR do C190 tem de dar o VL_DOC. O que compõe o documento e
    não está nos itens nem nos campos do C100 — frete que a empresa não
    separa, ICMS-ST e IPI que ela não escritura no item — entra no rateio do
    C190 como outras despesas **só durante o cálculo**; depois o VL_OUT_DA
    volta ao que o XML diz. No mês real, era exatamente o que o SPED
    entregue fazia (frete de R$ 13,55 e ST de R$ 22,14 no VL_OPR).
    """
    ic = {c: doc._ix("C100", c) for c in (
        "IND_EMIT", "COD_SIT", "COD_MOD", "VL_BC_ICMS", "VL_ICMS",
        "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI", "VL_DOC", "VL_FRT",
        "VL_SEG", "VL_OUT_DA")}
    i9 = {c: doc._ix("C190", c) for c in (
        "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI")}
    i7 = {c: doc._ix("C170", c) for c in (
        "VL_ITEM", "VL_DESC", "VL_IPI", "VL_ICMS_ST")}
    for c100 in [r for r in doc.registros if r.reg == "C100"]:
        if c100.valor(ic["COD_SIT"]) in ("02", "04"):
            continue
        itens = sum(_to_num(f.valor(i7["VL_ITEM"]))
                    - _to_num(f.valor(i7["VL_DESC"]))
                    + _to_num(f.valor(i7["VL_IPI"]))
                    + _to_num(f.valor(i7["VL_ICMS_ST"]))
                    for f in c100.filhos if f.reg == "C170")
        outras = c100.valor(ic["VL_OUT_DA"])
        resto = round(_to_num(c100.valor(ic["VL_DOC"])) - itens
                      - _to_num(c100.valor(ic["VL_FRT"]))
                      - _to_num(c100.valor(ic["VL_SEG"])), 2)
        c100.set_valor(ic["VL_OUT_DA"], _fmt_val(resto))
        doc.consolidar_c190(c100)
        c100.set_valor(ic["VL_OUT_DA"], outras)
        c190 = [f for f in c100.filhos if f.reg == "C190"]
        for campo in i9:
            soma = sum(_to_num(f.valor(i9[campo])) for f in c190)
            c100.set_valor(ic[campo], _fmt_val(soma))
        if c100.valor(ic["COD_MOD"]) == "65":
            # NFC-e: ST e IPI do C100 ficam **vazios** — preenchidos, mesmo
            # com zero, o PVA acusa MSG_NFE_CONSUMIDOR em cada um
            for campo in NFCE_C100_VAZIOS:
                c100.set_valor(ic[campo], "")
        if c100.valor(ic["IND_EMIT"]) == "0":
            for f in [f for f in c100.filhos if f.reg == "C170"]:
                doc.remover_registro(f)


def _cte_icms(d, ct, entrada, part, res, uf):
    """D100 + D190 de um CT-e."""
    onde = "CT-e %s/%s" % (ct.serie, ct.nct)
    sit = _cod_sit(ct, res.extemporaneos)
    base = dict(IND_OPER="0" if entrada else "1",
                IND_EMIT="1" if entrada else "0", COD_MOD="57",
                COD_SIT=sit, SER=ct.serie or "", NUM_DOC=ct.nct,
                CHV_CTE=ct.chave)
    if sit in ("02", "04"):
        d.reg("D100", **base)
        return
    cst = "0" + (ct.icms_cst or "")[-2:] if ct.icms_cst else ""
    if entrada:
        prefixo = "1" if ct.emit and ct.emit.uf == uf else "2"
        cfop = prefixo + "353"
        credita = bool(ct.icms_vicms) and cst[-2:] not in SEM_CREDITO_ICMS
        res.apontar("frete sem memória", onde, "",
                    "CFOP %s (aquisição de transporte por estabelecimento "
                    "comercial) e %s — confira" % (
                        cfop, "com crédito" if credita else "sem crédito"))
        cod_part = part.codigo(ct.emit)
        ind_frt = {"rem": "0", "dest": "1"}.get(ct.papel_toma, "2")
    else:
        cfop, credita = ct.cfop or "", True
        cod_part = part.codigo(ct.toma) if ct.toma else ""
        ind_frt = "0"
    bc = ct.icms_vbc if credita else 0
    icms = ct.icms_vicms if credita else 0
    d.reg("D100", **base, COD_PART=cod_part, DT_DOC=_data(ct.dhemi),
          DT_A_P=_data(ct.dhemi), **{"TP_CT-E": ct.tpcte or "0"},
          CHV_CTE_REF=ct.chave_ref or "", VL_DOC=_fmt_val(ct.vtprest),
          VL_DESC="0", IND_FRT=ind_frt, VL_SERV=_fmt_val(ct.vtprest),
          VL_BC_ICMS=_fmt_val(bc), VL_ICMS=_fmt_val(icms),
          VL_NT=_fmt_val(ct.vtprest - bc), COD_MUN_ORIG=ct.cmun_ini or "",
          COD_MUN_DEST=ct.cmun_fim or "")
    d.reg("D190", CST_ICMS=cst, CFOP=cfop,
          ALIQ_ICMS=_fmt_aliq_pct(ct.icms_aliq) if credita else "0",
          VL_OPR=_fmt_val(ct.vtprest), VL_BC_ICMS=_fmt_val(bc),
          VL_ICMS=_fmt_val(icms),
          VL_RED_BC=_fmt_val(ct.vtprest - bc if ct.icms_red else 0))


def _apuracao_icms(doc, memoria, modelos, periodo, ini, fim,
                   saldo_credor_anterior, res):
    """Bloco E: ICMS próprio pela soma dos analíticos; ST e DIFAL sem
    movimento (do modelo); IPI pelos itens de entrada."""
    e = _Linhas("ICMS", _larguras(memoria, "ICMS", fim))
    debitos = creditos = deb_esp = 0.0
    for reg in ("C190", "D190"):
        i = doc._ix(reg, "VL_ICMS")
        io = doc._ix(reg[0] + "100", "IND_OPER")
        isit = doc._ix(reg[0] + "100", "COD_SIT")
        for r in doc.registros:
            if r.reg == reg and r.pai is not None:
                v = _to_num(r.valor(i))
                if (r.pai.valor(io) or "") == "1":
                    # saída extemporânea: não é débito do período, é débito
                    # especial (o PVA confere em MSG_DEB_ESP_E110)
                    if (r.pai.valor(isit) or "") in ("01", "07"):
                        deb_esp += v
                    else:
                        debitos += v
                else:
                    creditos += v
    if saldo_credor_anterior is None:
        ano, mes = int(periodo[:4]), int(periodo[4:6])
        anterior = "%04d%02d" % (ano - (mes == 1), 12 if mes == 1
                                 else mes - 1)
        guardado = memoria.get("saldos", {}).get(anterior)
        if guardado is None:
            res.apontar("saldo credor anterior", "E110", "",
                        "não há o E110 de %s na memória: usei zero; informe "
                        "o saldo credor do mês anterior" % anterior)
            saldo_credor_anterior = 0.0
        else:
            saldo_credor_anterior = _to_num(guardado)
    apurado = round(debitos - creditos - saldo_credor_anterior, 2)
    e.reg("E001", IND_MOV="0")
    e.reg("E100", DT_INI=ini, DT_FIN=fim)
    recolher = _positivo(apurado)
    e.reg("E110", VL_TOT_DEBITOS=_fmt_val(debitos), VL_AJ_DEBITOS="0",
          VL_TOT_AJ_DEBITOS="0", VL_ESTORNOS_CRED="0",
          VL_TOT_CREDITOS=_fmt_val(creditos), VL_AJ_CREDITOS="0",
          VL_TOT_AJ_CREDITOS="0", VL_ESTORNOS_DEB="0",
          VL_SLD_CREDOR_ANT=_fmt_val(saldo_credor_anterior),
          VL_SLD_APURADO=_fmt_val(recolher), VL_TOT_DED="0",
          VL_ICMS_RECOLHER=_fmt_val(recolher),
          VL_SLD_CREDOR_TRANSPORTAR=_fmt_val(_positivo(-apurado)),
          DEB_ESP=_fmt_val(round(deb_esp, 2)))
    # o E116 soma o ICMS a recolher e o débito especial
    a_pagar = round(recolher + deb_esp, 2)
    if a_pagar and "E116" in modelos:
        e.modelo(modelos["E116"], VL_OR=_fmt_val(a_pagar),
                 DT_VCTO=_vencimento(modelos["E116"], periodo),
                 MES_REF=periodo[4:] + periodo[:4])
    elif a_pagar:
        res.apontar("E116", "E110", "", "há ICMS a recolher e a memória não "
                    "tem o modelo do E116 (código de receita, vencimento)")
    for reg, filho in (("E200", "E210"), ("E300", "E310")):
        if reg in modelos:
            e.modelo(modelos[reg], DT_INI=ini, DT_FIN=fim)
            zeros = modelos.get(filho, [filho])
            e.linhas.append([filho] + ["0"] * (len(zeros) - 1))
    if "E500" in modelos:
        e.modelo(modelos["E500"], DT_INI=ini, DT_FIN=fim)
        _apuracao_ipi(doc, e)
    e.reg("E990", QTD_LIN_E="0")
    return e


def _vencimento(e116, periodo):
    """Mesmo dia do modelo; no mês do período se o modelo vencia no próprio
    mês de referência, senão no seguinte."""
    dt = _modelo_valor(e116, "DT_VCTO", "ICMS")
    ref = _modelo_valor(e116, "MES_REF", "ICMS")
    ano, mes = int(periodo[:4]), int(periodo[4:6])
    if dt[2:8] != ref:                         # vencia no mês seguinte
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    dia = min(int(dt[:2] or 1), calendar.monthrange(ano, mes)[1])
    return "%02d%02d%04d" % (dia, mes, ano)


def _apuracao_ipi(doc, e):
    """E510 por CFOP e CST do IPI dos itens; E520 com débito e crédito."""
    i = {c: doc._ix("C170", c) for c in ("CFOP", "CST_IPI", "VL_ITEM",
                                         "VL_DESC", "VL_BC_IPI", "VL_IPI")}
    io = doc._ix("C100", "IND_OPER")
    grupos, deb, cred = {}, 0.0, 0.0
    for r in doc.registros:
        # item sem CST de IPI não entra na apuração do IPI (como no entregue)
        if r.reg != "C170" or not (r.valor(i["CST_IPI"]) or "").strip():
            continue
        k = (r.valor(i["CFOP"]), r.valor(i["CST_IPI"]))
        g = grupos.setdefault(k, [0.0, 0.0, 0.0])
        vipi = _to_num(r.valor(i["VL_IPI"]))
        g[0] += _to_num(r.valor(i["VL_ITEM"])) - _to_num(r.valor(i["VL_DESC"])) \
            + vipi
        g[1] += _to_num(r.valor(i["VL_BC_IPI"]))
        g[2] += vipi
        if (r.pai.valor(io) if r.pai else "") == "1":
            deb += vipi
        else:
            cred += vipi
    for (cfop, cst), (cont, bc, vipi) in sorted(grupos.items()):
        e.reg("E510", CFOP=cfop, CST_IPI=cst, VL_CONT_IPI=_fmt_val(cont),
              VL_BC_IPI=_fmt_val(bc), VL_IPI=_fmt_val(vipi))
    saldo = round(deb - cred, 2)
    e.reg("E520", VL_SD_ANT_IPI="0", VL_DEB_IPI=_fmt_val(deb),
          VL_CRED_IPI=_fmt_val(cred), VL_OD_IPI="0", VL_OC_IPI="0",
          VL_SC_IPI=_fmt_val(_positivo(-saldo)),
          VL_SD_IPI=_fmt_val(_positivo(saldo)))


def _positivo(v):
    """max(v, 0) sem o zero negativo, que sairia "-0,00" no arquivo."""
    return v if v > 0 else 0.0


# ---------------------------------------------------------- Contribuições
def gerar_contrib(memoria, lote, periodo, correlacoes=None, excluir=(),
                  incluir=()):
    """O EFD Contribuições do período (`AAAAMM`). Devolve `Resultado`.

    Entradas com C170 (PIS/COFINS e conta pela memória); NFC-e com C175
    consolidado pelo `consolidar_c175_de_itens` e a alíquota trocada para a
    do regime pelo `trocar_aliquotas_pis_cofins` — os dois do programa, o
    segundo já validado no PVA —; e o bloco M pelo `recalcular_bloco_m`.
    """
    res = Resultado()
    modelos = memoria.get("modelos", {}).get("CONTRIB")
    if not modelos or "0000" not in modelos:
        raise ValueError(
            "A memória desta empresa ainda não tem o cabeçalho do EFD "
            "Contribuições: aprenda primeiro com um SPED entregue.")
    ini, fim = limites(periodo)
    entrada_pad = memoria.get("padroes", {}).get("entrada", {})
    grupos = classificar(lote, memoria["cnpj"], periodo, res,
                         entrada_pad.get("DT_E_S"), set(excluir or ()),
                         set(incluir or ()))
    uf = _modelo_valor(memoria.get("modelos", {}).get("ICMS", {}).get(
        "0000", ["0000"]), "UF", "ICMS") if "ICMS" in memoria.get(
        "modelos", {}) else ""
    part = _Participantes(memoria, res)
    itens = _Itens(memoria, res, correlacoes, uf, contrib=True)
    padroes = memoria.get("padroes", {}).get("CONTRIB", {})

    c = _Linhas("CONTRIB")
    docs = sorted(grupos["entradas"] + grupos["saidas"],
                  key=lambda n: (_data(n.dhemi)[4:] + _data(n.dhemi)[2:4]
                                 + _data(n.dhemi)[:2], n.mod, n.serie,
                                 int(n.nnf or 0)))
    xml_nfce = {}
    for n in docs:
        entrada = n in grupos["entradas"]
        oper = "0" if entrada else "1"
        sit = _cod_sit(n, res.extemporaneos)
        base = dict(IND_OPER=oper, IND_EMIT="1" if entrada else "0",
                    COD_MOD=n.mod, COD_SIT=sit, SER=n.serie or "",
                    NUM_DOC=n.nnf, CHV_NFE=n.chave)
        if sit in ("02", "04"):
            c.reg("C100", **base)
            continue
        pad = padroes.get("%s|%s" % (n.mod, oper), {})
        data_doc = _data(n.dhemi)
        if entrada:
            data_es = (data_doc if entrada_pad.get("DT_E_S") == "emissao"
                       else _data(n.dhsaient) or data_doc)
            frete = 0.0 if entrada_pad.get("VL_FRT") == "zero" else n.vfrete
        else:
            data_es = data_doc
            frete = n.vfrete
        if n.chave in res.extemporaneos:
            # no EFD Contribuições o documento fica no mês: o PVA de lá
            # recusa data de outro mês mesmo com COD_SIT 01
            # (MSG_PERIODO_INCOMPATIVEL_SAIDA); vai o primeiro dia
            data_doc = data_es = ini
        zeros = {k: "0" for k in (
            "VL_ABAT_NT", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI",
            "VL_PIS_ST", "VL_COFINS_ST")}
        c.reg("C100", **base, **zeros,
              COD_PART=part.codigo(n.emit) if entrada else "",
              DT_DOC=data_doc, DT_E_S=data_es, VL_DOC=_fmt_val(n.vnf),
              IND_PGTO=pad.get("IND_PGTO", "2"), VL_DESC=_fmt_val(n.vdesc),
              VL_MERC=_fmt_val(n.vprod), IND_FRT=pad.get("IND_FRT", "9"),
              VL_FRT=_fmt_val(frete), VL_SEG=_fmt_val(n.vseg),
              VL_OUT_DA=_fmt_val(n.voutro),
              VL_BC_ICMS=_fmt_val(n.vbc), VL_ICMS=_fmt_val(n.vicms),
              VL_PIS="0", VL_COFINS="0")
        if entrada:
            for k, it in enumerate(n.itens, 1):
                c.reg("C170", NUM_ITEM=str(it.nitem or k),
                      **itens.entrada(n, it))
        else:
            xml_nfce[n.chave] = n
            for it in n.itens:
                itens.saida(it)

    _apontar_leiaute_do_periodo(res, "CONTRIB", fim)
    t = _Linhas("CONTRIB", _larguras(memoria, "CONTRIB", fim))
    t.modelo(modelos["0000"], DT_INI=ini, DT_FIN=fim, TIPO_ESCRIT="0",
             IND_SIT_ESP="", NUM_REC_ANTERIOR="")
    t.reg("0001", IND_MOV="0")
    for tipo in ("0100", "0110", "0140"):
        if tipo in modelos:
            t.modelo(modelos[tipo])
    part.registros(t)
    itens.registros(t)
    for conta in sorted(itens.contas):
        campos = memoria.get("contas", {}).get(conta)
        if campos:
            t.modelo(campos)
        else:
            res.apontar("conta sem cadastro", "0500", conta,
                        "a memória não tem esta conta do plano de contas")
    t.reg("0990", QTD_LIN_0="0")
    vazios = memoria.get("blocos_vazios", {}).get("CONTRIB", [])
    if "A" in vazios:
        t.bloco_vazio("A")
    t.reg("C001", IND_MOV="0" if c.linhas else "1")
    if "C010" in modelos:
        t.modelo(modelos["C010"])
    t.linhas += c.linhas
    t.reg("C990", QTD_LIN_C="0")
    for bloco in ("D", "F", "I"):
        if bloco in vazios:
            t.bloco_vazio(bloco)
    t.reg("M001", IND_MOV="0")
    # o recálculo refaz um bloco M existente: abre-se o M200/M600 zerado e
    # ele preenche (e cria o M210/M610)
    for reg in ("M200", "M600"):
        t.reg(reg, **{n: "0" for n in t.tabela[reg][1:]})
    t.reg("M990", QTD_LIN_M="0")
    for bloco in ("P", "1"):
        if bloco in vazios:
            t.bloco_vazio(bloco)
    doc = SpedDocument.de_texto(t.texto())

    # C100 de entrada: mercadorias e PIS/COFINS pela soma dos itens (que
    # aqui já trazem as outras despesas de cada um)
    ic = {k: doc._ix("C100", k) for k in ("CHV_NFE", "VL_PIS", "VL_COFINS",
                                           "VL_MERC")}
    i7 = {k: doc._ix("C170", k) for k in ("VL_PIS", "VL_COFINS", "VL_ITEM")}
    for c100 in [r for r in doc.registros if r.reg == "C100"]:
        filhos = [f for f in c100.filhos if f.reg == "C170"]
        if filhos:
            for campo, de in (("VL_PIS", "VL_PIS"),
                              ("VL_COFINS", "VL_COFINS"),
                              ("VL_MERC", "VL_ITEM")):
                c100.set_valor(ic[campo], _fmt_val(sum(
                    _to_num(f.valor(i7[de])) for f in filhos)))
        nfe = xml_nfce.get(c100.valor(ic["CHV_NFE"]))
        if nfe is not None:
            doc.consolidar_c175_de_itens(c100, nfe.itens)
    _aliquota_do_regime(doc, memoria, res)
    doc.recalcular_bloco_m()
    _codigos_de_receita(doc, modelos)
    _receitas_sem_contribuicao(doc, list(xml_nfce.values()), memoria, res)
    res.doc = SpedDocument.de_texto(doc.gerar_texto())
    res.contagem = {k: len(v) for k, v in grupos.items()}
    return res


def _aliquota_do_regime(doc, memoria, res):
    """Troca, nas saídas, a alíquota que veio do XML pela do regime — pela
    mesma função do botão *Trocar alíquotas*. Só onde o XML trouxe outra."""
    regime = memoria.get("aliquotas_saida", {}).get("01")
    if not regime:
        res.apontar("alíquota do regime", "C175", "",
                    "a memória não tem a alíquota de saída do regime: "
                    "ficou a do XML")
        return
    i = {k: doc._ix("C175", k) for k in ("CST_PIS", "ALIQ_PIS",
                                          "ALIQ_COFINS")}
    vistas = {(r.valor(i["ALIQ_PIS"]), r.valor(i["ALIQ_COFINS"]))
              for r in doc.registros
              if r.reg == "C175" and r.valor(i["CST_PIS"]) == "01"}
    alvo = (_to_num(regime["ALIQ_PIS"]), _to_num(regime["ALIQ_COFINS"]))
    for ap, ac in vistas:
        de = (_to_num(ap), _to_num(ac))
        if de != alvo:
            doc.trocar_aliquotas_pis_cofins(
                aliq_pis=alvo[0], aliq_cofins=alvo[1], escopo="saidas",
                de_pis=de[0], de_cofins=de[1])
            res.apontar("alíquota do XML trocada", "C175", "",
                        "as NFC-e vieram com %s/%s; o regime da empresa é "
                        "%s/%s" % (ap, ac, regime["ALIQ_PIS"],
                                   regime["ALIQ_COFINS"]))


# CST de saída sem contribuição: a receita vai para o M400/M800, detalhada
# por natureza no M410/M810 (tabelas 4.3.10 a 4.3.16)
CST_SEM_CONTRIBUICAO = ("04", "05", "06", "07", "08", "09")


def _natureza_pelo_ncm(tabela, ncm, ex_ipi=""):
    """A natureza cujo prefixo de NCM mais longo casa com o produto."""
    ncm = so_digitos(ncm)
    melhor, tam = None, -1
    for codigo, prefixos, ex in tabela:
        if ex and ex != (ex_ipi or ""):
            continue
        for p in prefixos:
            if ncm.startswith(p) and len(p) > tam:
                melhor, tam = codigo, len(p)
    return melhor


def _receitas_sem_contribuicao(doc, saidas, memoria, res):
    """M400/M410 (PIS) e M800/M810 (COFINS) — filhos obrigatórios do bloco
    M quando há receita com CST 04 a 09.

    O total de cada CST é a receita que o PVA confere
    (`receita_por_cst`, o mesmo da `conferir_receitas_isentas`). A
    natureza vem do NCM de cada item do XML pela tabela do CST (o prefixo
    mais longo); sem casamento, a natureza que a empresa usou no SPED
    entregue naquele CST (apontado); sem nenhuma das duas, a linha sai sem
    natureza e **bloqueia** — o PVA recusaria. O total do CST é repartido
    entre as naturezas pela proporção dos itens, com o rateio de sempre
    (`rateio_acessorios`): o M410 fecha com o M400 ao centavo."""
    m001 = next((r for r in doc.registros if r.reg == "M001"), None)
    if m001 is None:
        return
    vistas = memoria.get("naturezas_receita", {})
    contas = memoria.get("contas_receita", {})
    no_0500 = {(r.valor(doc._ix("0500", "COD_CTA")) or "").strip()
               for r in doc.registros if r.reg == "0500"}

    def conta(chave):
        c = contas.get(chave, "")
        return c if c in no_0500 else ""

    for trib, pai, filho, campo, attr in (
            ("PIS", "M400", "M410", "CST_PIS", "pis_cst"),
            ("COFINS", "M800", "M810", "CST_COFINS", "cofins_cst")):
        totais = {cst: round(v, 2)
                  for cst, v in doc.receita_por_cst(trib).items()
                  if cst in CST_SEM_CONTRIBUICAO and round(v, 2)}
        if not totais:
            continue
        partes = {}
        for n in saidas:
            for it in n.itens:
                cst = (getattr(it, attr) or "").strip()
                if cst not in totais:
                    continue
                tabela = referencias.atual().tabela_natureza_receita(cst)
                nat = _natureza_pelo_ncm(tabela, it.ncm)
                if nat is None:
                    ja = vistas.get(cst) or {}
                    nat = max(ja, key=ja.get) if ja else ""
                    res.apontar(
                        "natureza da receita pela prática", filho, cst,
                        "%s (NCM %s, CST %s): %s" % (
                            it.xprod, it.ncm, cst,
                            "usei a natureza %s, a que a empresa usa neste "
                            "CST" % nat if nat else "nenhuma tabela nem a "
                            "memória dizem a natureza"),
                        bloqueia=not nat)
                v = (it.vprod or 0.0) - (it.vdesc or 0.0)
                partes.setdefault(cst, {})
                partes[cst][nat] = partes[cst].get(nat, 0.0) + v
        with doc.lote():
            for cst in sorted(totais):
                depois = doc._ancora_antes(m001, pai)
                reg = doc.novo_registro(pai, pai=m001, depois=depois)
                doc._preencher(reg, [pai, cst, _fmt_val(totais[cst]),
                                     conta("%s|%s" % (pai, cst)), ""])
                nats = sorted(partes.get(cst, {}).items()) or [
                    (max(vistas.get(cst) or {"": 1},
                         key=(vistas.get(cst) or {"": 1}).get), 1.0)]
                if not any(n for n, _v in nats):
                    res.apontar("natureza da receita desconhecida", filho,
                                cst, "receita de CST %s sem natureza: "
                                     "informe no M410/M810" % cst,
                                bloqueia=True)
                valores = SpedDocument.rateio_acessorios(
                    totais[cst], [v for _n, v in nats])
                ant = reg
                for (nat, _v), vl in zip(nats, valores):
                    f = doc.novo_registro(filho, pai=reg, depois=ant)
                    doc._preencher(f, [filho, nat, _fmt_val(vl), conta(
                        "%s|%s|%s" % (filho, cst, nat)), ""])
                    ant = f


def _codigos_de_receita(doc, modelos):
    """M205/M605 (código de receita do débito) pelos modelos da memória,
    com o valor do campo do M200/M600 que o modelo aponta."""
    for pai, filho in (("M200", "M205"), ("M600", "M605")):
        m = next((r for r in doc.registros if r.reg == pai), None)
        modelo = modelos.get(filho)
        if m is None or not modelo:
            continue
        num = _modelo_valor(modelo, "NUM_CAMPO", "CONTRIB")
        try:
            valor = m.campos[int(num) - 1]           # o Guia conta o REG
        except (ValueError, IndexError):
            continue
        if not _to_num(valor):
            continue
        novo = doc.novo_registro(filho, pai=m)
        novo.campos = list(modelo)
        novo.set_valor(doc._ix(filho, "VL_DEBITO"), valor)

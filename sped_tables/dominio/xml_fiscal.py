# -*- coding: utf-8 -*-
"""
xml_fiscal.py
-------------
Leitura de XML de NF-e / NFC-e (modelos 55 e 65) e **vínculo genérico** com
registros do SPED.

O vínculo é a parte reaproveitável: `vincular()` casa duas coleções por uma
*chave* calculada por funções fornecidas pelo chamador. Assim o mesmo motor
serve para diferentes procedimentos:

* consolidar **C175** (saída, NFC-e 65): casa **documento XML ↔ C100** pela
  chave (mod, série, nNF);
* conferir **entradas (NF-e 55)**: casa **item XML ↔ C170** pela chave
  (mod, série, nNF, nItem) — necessário porque o código do produto muda entre
  a saída do fornecedor e a entrada do comprador, mas a ordem do item (nItem)
  se mantém.

Não depende de PyQt nem de sped_model (apenas da biblioteca padrão).
"""

import os
import re
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------- utilidades
def _strip_ns(texto):
    """Remove namespaces e prefixos para simplificar as buscas."""
    texto = re.sub(r'\sxmlns(:\w+)?="[^"]+"', "", texto)
    texto = re.sub(r"(</?)[A-Za-z0-9_]+:", r"\1", texto)
    return texto


def _num(s):
    s = (s or "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def norm(s):
    """Normaliza uma parte de chave (mod/série/nNF/nItem) para comparação:
    números perdem zeros à esquerda; o resto é apenas aparado."""
    s = (s or "").strip()
    return str(int(s)) if s.isdigit() else s


# ------------------------------------------------------------------ modelos
class Participante:
    """Quem aparece no documento (emitente, destinatário, tomador…), com o
    que o 0150 do SPED pede."""
    __slots__ = ("cnpj", "cpf", "ie", "nome", "lgr", "nro", "compl",
                 "bairro", "cod_mun", "mun", "uf", "cep", "cod_pais",
                 "suframa")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))

    @property
    def documento(self):
        return self.cnpj or self.cpf or ""


def _participante(el):
    """Lê `<emit>`, `<dest>`, `<rem>`… e o endereço que vier dentro (o nome do
    grupo muda: enderEmit, enderDest, enderReme, enderToma…)."""
    if el is None:
        return None
    end = next((f for f in el if f.tag.startswith("ender")), None)

    def e(tag):
        return (end.findtext(tag) or "").strip() if end is not None else ""
    return Participante(
        cnpj=(el.findtext("CNPJ") or "").strip(),
        cpf=(el.findtext("CPF") or "").strip(),
        ie=(el.findtext("IE") or "").strip(),
        nome=(el.findtext("xNome") or "").strip(),
        lgr=e("xLgr"), nro=e("nro"), compl=e("xCpl"), bairro=e("xBairro"),
        cod_mun=e("cMun"), mun=e("xMun"), uf=e("UF"), cep=e("CEP"),
        cod_pais=e("cPais"),
        suframa=(el.findtext("ISUF") or "").strip())


def _raiz(caminho):
    """Elemento raiz do XML, sem namespaces; None se não for XML legível."""
    with open(caminho, "rb") as fh:
        return _raiz_de_bytes(fh.read())


def _raiz_de_bytes(bruto):
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    try:
        return ET.fromstring(_strip_ns(texto))
    except ET.ParseError:
        return None


# situação do protocolo de autorização (NF-e e CT-e)
CSTAT_AUTORIZADO = {"100", "150"}
CSTAT_CANCELADO = {"101", "151"}
CSTAT_DENEGADO = {"110", "205", "301", "302", "303"}
# evento de cancelamento, e os status que dizem que ele foi registrado
EVENTO_CANCELAMENTO = "110111"
CSTAT_EVENTO_OK = {"135", "136", "155"}


class ItemNFe:
    __slots__ = ("nitem", "cprod", "xprod", "cfop", "vprod", "vdesc",
                 "voutro", "vfrete", "vseg", "qtd", "unid", "ncm", "cean",
                 "pis_cst", "pis_vbc", "pis_aliq", "pis_vpis",
                 "cofins_cst", "cofins_vbc", "cofins_aliq", "cofins_vcofins",
                 "icms_cst", "icms_vbc", "icms_aliq", "icms_vicms",
                 "icms_vbcst", "icms_aliqst", "icms_vicmsst", "icms_predbc",
                 "ipi_cst", "ipi_vbc", "ipi_aliq", "vipi")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))


class NFe:
    __slots__ = ("chave", "mod", "serie", "nnf", "dhemi", "tpnf",
                 "vnf", "vprod", "vdesc", "vfrete", "vseg", "voutro",
                 "itens", "arquivo",
                 # para gerar o SPED do zero
                 "dhsaient", "fin", "emit", "dest", "cstat", "nprot",
                 "cancelada", "refs", "vbc", "vicms", "vbcst", "vst",
                 "vipi", "vpis", "vcofins")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))
        if self.itens is None:
            self.itens = []
        if self.refs is None:
            self.refs = []

    @property
    def situacao(self):
        """"autorizada", "cancelada", "denegada" ou "sem protocolo"."""
        return _situacao(self.cstat, self.cancelada)


def _situacao(cstat, cancelada):
    if cancelada or cstat in CSTAT_CANCELADO:
        return "cancelada"
    if cstat in CSTAT_DENEGADO:
        return "denegada"
    if cstat in CSTAT_AUTORIZADO:
        return "autorizada"
    return "sem protocolo"


# ------------------------------------------------------------------ leitura
def ler_nfe(caminho):
    """Lê um arquivo XML de NF-e/NFC-e e devolve um objeto NFe (ou None)."""
    root = _raiz(caminho)
    if root is None:
        return None
    return _nfe_de(root, caminho)


def _nfe_de(root, caminho):
    inf = root.find(".//infNFe")
    if inf is None:
        return None
    ide = inf.find("ide")
    if ide is None:
        return None
    total = inf.find(".//total/ICMSTot")

    nfe = NFe(
        chave=(inf.get("Id") or "").replace("NFe", "").strip(),
        mod=ide.findtext("mod"), serie=ide.findtext("serie"),
        nnf=ide.findtext("nNF"),
        dhemi=ide.findtext("dhEmi") or ide.findtext("dEmi"),
        tpnf=ide.findtext("tpNF"),
        vnf=_num(total.findtext("vNF")) if total is not None else 0.0,
        vprod=_num(total.findtext("vProd")) if total is not None else 0.0,
        vdesc=_num(total.findtext("vDesc")) if total is not None else 0.0,
        vfrete=_num(total.findtext("vFrete")) if total is not None else 0.0,
        vseg=_num(total.findtext("vSeg")) if total is not None else 0.0,
        voutro=_num(total.findtext("vOutro")) if total is not None else 0.0,
        arquivo=os.path.basename(caminho), itens=[],
        dhsaient=ide.findtext("dhSaiEnt") or ide.findtext("dSaiEnt"),
        fin=ide.findtext("finNFe"),
        emit=_participante(inf.find("emit")),
        dest=_participante(inf.find("dest")),
        cstat=(root.findtext(".//protNFe/infProt/cStat") or "").strip(),
        nprot=(root.findtext(".//protNFe/infProt/nProt") or "").strip(),
        cancelada=False,
        refs=[(r.text or "").strip() for r in ide.findall(".//refNFe")],
        vbc=_num(total.findtext("vBC")) if total is not None else 0.0,
        vicms=_num(total.findtext("vICMS")) if total is not None else 0.0,
        vbcst=_num(total.findtext("vBCST")) if total is not None else 0.0,
        vst=_num(total.findtext("vST")) if total is not None else 0.0,
        vipi=_num(total.findtext("vIPI")) if total is not None else 0.0,
        vpis=_num(total.findtext("vPIS")) if total is not None else 0.0,
        vcofins=(_num(total.findtext("vCOFINS"))
                 if total is not None else 0.0))

    for det in inf.findall("det"):
        prod = det.find("prod")
        if prod is None:
            continue
        pis = det.find(".//PIS/*")
        cof = det.find(".//COFINS/*")
        # grupo de ICMS do item: o elemento dentro de <ICMS> varia (ICMS00,
        # ICMS20, ICMS60, ICMSSN..., etc.); lê o primeiro filho, seja qual for.
        icms = det.find(".//ICMS/*")
        orig = (icms.findtext("orig") if icms is not None else None) or ""
        cst_ic = (icms.findtext("CST") or icms.findtext("CSOSN")) \
            if icms is not None else None
        icms_cst = (orig + cst_ic) if cst_ic else None
        # grupo IPI (pode ser IPITrib ou IPINT)
        ipi = det.find(".//IPI")
        ipi_trib = ipi.find(".//IPITrib") if ipi is not None else None
        ipi_nt = ipi.find(".//IPINT") if ipi is not None else None
        ipi_cst = None
        ipi_vbc = ipi_aliq = None
        vipi = 0.0
        if ipi_trib is not None:
            ipi_cst = ipi_trib.findtext("CST")
            ipi_vbc = _num(ipi_trib.findtext("vBC"))
            ipi_aliq = ipi_trib.findtext("pIPI")
            vipi = _num(ipi_trib.findtext("vIPI"))
        elif ipi_nt is not None:
            ipi_cst = ipi_nt.findtext("CST")
        nfe.itens.append(ItemNFe(
            nitem=det.get("nItem"),
            cprod=prod.findtext("cProd"), xprod=prod.findtext("xProd"),
            cfop=prod.findtext("CFOP"), vprod=_num(prod.findtext("vProd")),
            vdesc=_num(prod.findtext("vDesc")),
            voutro=_num(prod.findtext("vOutro")),
            vfrete=_num(prod.findtext("vFrete")),
            vseg=_num(prod.findtext("vSeg")),
            qtd=_num(prod.findtext("qCom")), unid=prod.findtext("uCom"),
            ncm=prod.findtext("NCM"),
            cean=_gtin(prod.findtext("cEAN")),
            icms_cst=icms_cst,
            icms_vbc=_num(icms.findtext("vBC")) if icms is not None else 0.0,
            # percentual de redução da base (ICMS20/70/51…): é o que sobra
            # quando o XML vem com a base zerada, como na entrada exportada
            # pelo ERP
            icms_predbc=(_num(icms.findtext("pRedBC"))
                         if icms is not None else 0.0),
            icms_aliq=(icms.findtext("pICMS") if icms is not None else None),
            icms_vicms=_num(icms.findtext("vICMS")) if icms is not None else 0.0,
            icms_vbcst=_num(icms.findtext("vBCST")) if icms is not None else 0.0,
            icms_aliqst=(icms.findtext("pICMSST")
                         if icms is not None else None),
            icms_vicmsst=(_num(icms.findtext("vICMSST"))
                          if icms is not None else 0.0),
            ipi_cst=ipi_cst, ipi_vbc=ipi_vbc, ipi_aliq=ipi_aliq, vipi=vipi,
            pis_cst=(pis.findtext("CST") if pis is not None else None),
            pis_vbc=_num(pis.findtext("vBC")) if pis is not None else 0.0,
            pis_aliq=(pis.findtext("pPIS") if pis is not None else None),
            pis_vpis=_num(pis.findtext("vPIS")) if pis is not None else 0.0,
            cofins_cst=(cof.findtext("CST") if cof is not None else None),
            cofins_vbc=_num(cof.findtext("vBC")) if cof is not None else 0.0,
            cofins_aliq=(cof.findtext("pCOFINS") if cof is not None else None),
            cofins_vcofins=(_num(cof.findtext("vCOFINS"))
                            if cof is not None else 0.0)))
    return nfe


def _gtin(v):
    """cEAN do XML, ou "" quando o emitente declarou que não há."""
    v = (v or "").strip()
    return "" if v.upper() in ("SEM GTIN", "SEMGTIN") else v


# --------------------------------------------------------------- CT-e (57)
# quem é o tomador pelo código do <toma3>/<toma4>
PAPEL_TOMADOR = {"0": "rem", "1": "exped", "2": "receb", "3": "dest",
                 "4": "toma"}


class CTe:
    """Conhecimento de transporte eletrônico (modelo 57): o que o D100/D190
    (ICMS/IPI) e o D100/D101/D105 (Contribuições) pedem."""
    __slots__ = ("chave", "mod", "serie", "nct", "dhemi", "tpcte", "cfop",
                 "natop", "cmun_ini", "uf_ini", "cmun_fim", "uf_fim",
                 "emit", "rem", "exped", "receb", "dest", "toma",
                 "papel_toma", "vtprest", "vrec", "icms_cst", "icms_vbc",
                 "icms_aliq", "icms_vicms", "icms_red", "simples",
                 "cstat", "nprot", "cancelada", "chaves_nfe", "chave_ref",
                 "arquivo")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))
        if self.chaves_nfe is None:
            self.chaves_nfe = []

    @property
    def situacao(self):
        return _situacao(self.cstat, self.cancelada)


def ler_cte(caminho):
    """Lê um XML de CT-e (modelo 57). Devolve `CTe` ou None."""
    root = _raiz(caminho)
    if root is None:
        return None
    return _cte_de(root, caminho)


def _icms_do_cte(imp):
    """(cst de 2 dígitos, base, alíquota, valor, % redução, simples) do grupo
    de ICMS do CT-e — o elemento muda com a situação (ICMS00, ICMS20,
    ICMS45, ICMS60, ICMS90, ICMSOutraUF, ICMSSN)."""
    grupo = imp.find("ICMS/*") if imp is not None else None
    if grupo is None:
        return None, 0.0, None, 0.0, 0.0, False
    if grupo.tag == "ICMSSN":
        return (grupo.findtext("CST") or "90"), 0.0, None, 0.0, 0.0, True
    sufixo = "OutraUF" if grupo.tag == "ICMSOutraUF" else ""
    return ((grupo.findtext("CST") or "").strip(),
            _num(grupo.findtext("vBC" + sufixo)),
            (grupo.findtext("pICMS" + sufixo) or None),
            _num(grupo.findtext("vICMS" + sufixo)),
            _num(grupo.findtext("pRedBC" + sufixo)), False)


def _cte_de(root, caminho):
    inf = root.find(".//infCte")
    if inf is None:
        return None
    ide = inf.find("ide")
    if ide is None:
        return None
    partes = {tag: _participante(inf.find(tag))
              for tag in ("emit", "rem", "exped", "receb", "dest")}
    # o tomador: um dos quatro, pelo código; ou um quinto, com dados próprios
    toma3 = ide.find("toma3")
    if toma3 is None:
        toma3 = ide.find("toma03")                 # leiaute 3.00
    toma4 = ide.find("toma4")
    if toma4 is not None:
        papel, toma = "toma", _participante(toma4)
    else:
        cod = (toma3.findtext("toma") if toma3 is not None else "") or ""
        papel = PAPEL_TOMADOR.get(cod.strip(), "")
        toma = partes.get(papel)
    cst, vbc, aliq, vicms, red, simples = _icms_do_cte(inf.find("imp"))
    ref = (inf.findtext(".//infCteComp/chCTe")
           or inf.findtext(".//infCteComp/chave")
           or inf.findtext(".//infCteAnu/chCte")
           or inf.findtext(".//infCteSub/chCte") or "")
    return CTe(
        chave=(inf.get("Id") or "").replace("CTe", "").strip(),
        mod=ide.findtext("mod"), serie=ide.findtext("serie"),
        nct=ide.findtext("nCT"), dhemi=ide.findtext("dhEmi"),
        tpcte=(ide.findtext("tpCTe") or "0").strip(),
        cfop=ide.findtext("CFOP"), natop=ide.findtext("natOp"),
        cmun_ini=ide.findtext("cMunIni"), uf_ini=ide.findtext("UFIni"),
        cmun_fim=ide.findtext("cMunFim"), uf_fim=ide.findtext("UFFim"),
        toma=toma, papel_toma=papel,
        vtprest=_num(inf.findtext("vPrest/vTPrest")),
        vrec=_num(inf.findtext("vPrest/vRec")),
        icms_cst=cst, icms_vbc=vbc, icms_aliq=aliq, icms_vicms=vicms,
        icms_red=red, simples=simples,
        cstat=(root.findtext(".//protCTe/infProt/cStat") or "").strip(),
        nprot=(root.findtext(".//protCTe/infProt/nProt") or "").strip(),
        cancelada=False,
        chaves_nfe=[(c.text or "").strip()
                    for c in inf.findall(".//infDoc/infNFe/chave")],
        chave_ref=ref.strip(), arquivo=os.path.basename(caminho),
        **partes)


# ------------------------------------------------------------ eventos
class Evento:
    """Evento registrado sobre um documento (o que interessa ao SPED é o
    cancelamento)."""
    __slots__ = ("chave", "tipo", "cstat", "arquivo")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))

    @property
    def cancela(self):
        return (self.tipo == EVENTO_CANCELAMENTO
                and self.cstat in CSTAT_EVENTO_OK)


def _evento_de(root, caminho):
    inf = root.find(".//evento/infEvento")
    if inf is None:
        return None
    return Evento(
        chave=(inf.findtext("chNFe") or inf.findtext("chCTe") or "").strip(),
        tipo=(inf.findtext("tpEvento") or "").strip(),
        cstat=(root.findtext(".//retEvento/infEvento/cStat") or "").strip(),
        arquivo=os.path.basename(caminho))


def ler_documento(caminho):
    """NFe, CTe ou Evento, conforme o XML; None se não for nenhum deles."""
    return _documento(_raiz(caminho), caminho)


def documento_de_bytes(bruto, nome):
    """O mesmo que `ler_documento`, para o XML que não está em arquivo — o
    que o ERP guarda no banco. `nome` faz o papel do nome do arquivo."""
    return _documento(_raiz_de_bytes(bruto), nome)


def _documento(root, caminho):
    if root is None:
        return None
    if root.find(".//evento/infEvento") is not None:
        return _evento_de(root, caminho)
    if root.find(".//infCte") is not None:
        return _cte_de(root, caminho)
    if root.find(".//infNFe") is not None:
        return _nfe_de(root, caminho)
    return None


class Lote:
    """O que saiu de uma pasta de XMLs, já com os cancelamentos aplicados.

    Documento repetido (o mesmo XML em duas subpastas, ou o XML da nota e o
    do `nfeProc`) conta uma vez só, pela chave; os repetidos ficam listados.
    """

    def __init__(self):
        self.nfes, self.ctes, self.eventos = [], [], []
        self.erros = []              # [(arquivo, motivo)]
        self.repetidos = []          # [(arquivo, chave)]
        # NF-e sem chave de acesso: não é documento autorizado, mas é o que o
        # ERP exporta da entrada como ele a escriturou (o fornecedor no
        # `dest`). Só serve a conferências que casam pelo conteúdo.
        self.sem_chave = []

    @property
    def documentos(self):
        return self.nfes + self.ctes


def listar_xmls(pasta, recursivo=True):
    """Os `.xml` da pasta (e das subpastas), em ordem — a ordem decide qual
    de dois XMLs repetidos vale."""
    if not recursivo:
        return [os.path.join(pasta, n) for n in sorted(os.listdir(pasta))
                if n.lower().endswith(".xml")]
    caminhos = []
    for raiz, _d, nomes in os.walk(pasta):
        caminhos += [os.path.join(raiz, n) for n in sorted(nomes)
                     if n.lower().endswith(".xml")]
    return caminhos


def ler_arquivos(caminhos):
    """`[(documento ou None, erro ou None)]` de cada caminho, na ordem.

    É a unidade de trabalho da leitura em paralelo (`infra.paralelo`):
    função de módulo, porque vai para outro processo pelo nome, e devolve
    o erro como texto em vez de levantar — um XML ruim não derruba os 63
    que vieram no mesmo pedaço."""
    saida = []
    for cam in caminhos:
        try:
            saida.append((ler_documento(cam), None))
        except Exception as exc:                            # noqa: BLE001
            saida.append((None, "não foi possível ler: %s" % exc))
    return saida


def ler_conteudos(itens):
    """`ler_arquivos` para XMLs em memória: `itens` = `[(nome, bytes)]`."""
    saida = []
    for nome, bruto in itens:
        try:
            saida.append((documento_de_bytes(bruto, nome), None))
        except Exception as exc:                            # noqa: BLE001
            saida.append((None, "não foi possível ler: %s" % exc))
    return saida


def montar_lote(lidos):
    """O `Lote` de `[(nome, documento, erro)]`, na ordem: o primeiro de dois
    documentos com a mesma chave é o que vale, e o cancelamento por evento
    marca o documento. Serve à pasta e ao banco do ERP."""
    lote = Lote()
    vistos = {}
    for nome, doc, erro in lidos:
        if erro:
            lote.erros.append((nome, erro))
            continue
        if doc is None:
            lote.erros.append((nome, "não é NF-e, NFC-e, CT-e nem evento"))
            continue
        if isinstance(doc, Evento):
            lote.eventos.append(doc)
            continue
        if not doc.chave:
            if isinstance(doc, NFe):
                lote.sem_chave.append(doc)
            else:
                lote.erros.append((nome, "documento sem chave de acesso"))
            continue
        if doc.chave in vistos:
            lote.repetidos.append((nome, doc.chave))
            continue
        vistos[doc.chave] = doc
        (lote.ctes if isinstance(doc, CTe) else lote.nfes).append(doc)
    for ev in lote.eventos:
        if ev.cancela and ev.chave in vistos:
            vistos[ev.chave].cancelada = True
    return lote


def nfes_de(lidos):
    """`(nfes, erros)` de `[(nome, documento, erro)]`: só NF-e/NFC-e com
    número, na ordem; o resto vai para os erros."""
    nfes, erros = [], []
    for nome, doc, erro in lidos:
        if erro:
            erros.append((nome, erro))
        elif isinstance(doc, NFe) and doc.nnf:
            nfes.append(doc)
        else:
            erros.append((nome, "XML sem infNFe/nNF (não é NF-e?)"))
    return nfes, erros


def ler_pasta_fiscal(pasta, recursivo=True, ler=ler_arquivos):
    """Lê NF-e, NFC-e, CT-e e eventos de uma pasta (e subpastas).

    Nada é descartado em silêncio: o que não é documento fiscal vai para
    `erros`, com o motivo, e o documento cancelado por evento continua na
    lista com `cancelada=True` — o SPED o escritura com COD_SIT 02.

    `ler` lê a lista de caminhos (`ler_arquivos`, ou ela repartida entre
    processos — `aplicacao.leitura_xml`).
    """
    caminhos = listar_xmls(pasta, recursivo)
    return montar_lote((os.path.relpath(cam, pasta), doc, erro)
                       for cam, (doc, erro) in zip(caminhos, ler(caminhos)))


def ler_pasta(pasta, ler=ler_arquivos):
    """Lê os .xml de uma pasta (sem subpastas). Devolve (lista_de_NFe,
    lista_de_erros) — só NF-e/NFC-e com número; o resto vai para os erros."""
    caminhos = listar_xmls(pasta, recursivo=False)
    return nfes_de((os.path.basename(cam), doc, erro)
                   for cam, (doc, erro) in zip(caminhos, ler(caminhos)))


# --------------------------------------------------- chaves e vínculo genérico
def chave_doc(nfe):
    """Chave de vínculo no nível do documento: (mod, série, nNF)."""
    return (norm(nfe.mod), norm(nfe.serie), norm(nfe.nnf))


def chave_item(nfe, item):
    """Chave de vínculo no nível do item: (mod, série, nNF, nItem)."""
    return (norm(nfe.mod), norm(nfe.serie), norm(nfe.nnf), norm(item.nitem))


def indexar(itens, fn_chave):
    """Agrupa `itens` por chave (chave -> lista de itens)."""
    idx = {}
    for it in itens:
        idx.setdefault(fn_chave(it), []).append(it)
    return idx


def vincular(esquerda, fn_esq, direita, fn_dir):
    """
    Casa duas coleções por chave. Genérico e reaproveitável.

    Retorna (pares, so_esquerda, so_direita):
      * pares        -> lista de (item_esquerda, [itens_direita_casados])
      * so_esquerda  -> itens da esquerda sem correspondente na direita
      * so_direita   -> itens da direita sem correspondente na esquerda
    """
    idx = indexar(direita, fn_dir)
    pares, so_esq, usados = [], [], set()
    for e in esquerda:
        k = fn_esq(e)
        achados = idx.get(k)
        if achados:
            pares.append((e, achados))
            usados.add(k)
        else:
            so_esq.append(e)
    so_dir = [d for d in direita if fn_dir(d) not in usados]
    return pares, so_esq, so_dir

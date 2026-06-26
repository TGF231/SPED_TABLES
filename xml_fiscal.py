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
class ItemNFe:
    __slots__ = ("nitem", "cprod", "xprod", "cfop", "vprod", "vdesc",
                 "pis_cst", "pis_vbc", "pis_aliq", "pis_vpis",
                 "cofins_cst", "cofins_vbc", "cofins_aliq", "cofins_vcofins")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))


class NFe:
    __slots__ = ("chave", "mod", "serie", "nnf", "dhemi", "tpnf",
                 "vnf", "vprod", "vdesc", "vfrete", "vseg", "voutro",
                 "itens", "arquivo")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))
        if self.itens is None:
            self.itens = []


# ------------------------------------------------------------------ leitura
def ler_nfe(caminho):
    """Lê um arquivo XML de NF-e/NFC-e e devolve um objeto NFe (ou None)."""
    with open(caminho, "rb") as fh:
        bruto = fh.read()
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    texto = _strip_ns(texto)
    try:
        root = ET.fromstring(texto)
    except ET.ParseError:
        return None
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
        arquivo=os.path.basename(caminho), itens=[])

    for det in inf.findall("det"):
        prod = det.find("prod")
        if prod is None:
            continue
        pis = det.find(".//PIS/*")
        cof = det.find(".//COFINS/*")
        nfe.itens.append(ItemNFe(
            nitem=det.get("nItem"),
            cprod=prod.findtext("cProd"), xprod=prod.findtext("xProd"),
            cfop=prod.findtext("CFOP"), vprod=_num(prod.findtext("vProd")),
            vdesc=_num(prod.findtext("vDesc")),
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


def ler_pasta(pasta):
    """Lê todos os .xml de uma pasta. Devolve (lista_de_NFe, lista_de_erros)."""
    nfes, erros = [], []
    for nome in sorted(os.listdir(pasta)):
        if not nome.lower().endswith(".xml"):
            continue
        cam = os.path.join(pasta, nome)
        try:
            nfe = ler_nfe(cam)
            if nfe is not None and nfe.nnf:
                nfes.append(nfe)
            else:
                erros.append((nome, "XML sem infNFe/nNF (não é NF-e?)"))
        except Exception as e:  # noqa: BLE001
            erros.append((nome, str(e)))
    return nfes, erros


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

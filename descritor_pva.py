# -*- coding: utf-8 -*-
"""
descritor_pva.py
----------------
Lê os **descritores de escrituração** que os PVAs usam para validar — a fonte
mais próxima que existe do "como o PVA valida".

Cada PVA embarca, dentro de um `.jar`, um XML por versão de leiaute com a
estrutura completa: registros (nível, ocorrência, obrigatoriedade, chave),
campos (tipo, tamanho, casas decimais, obrigatoriedade) e, o que mais
interessa aqui:

* `<valores-validos valores="0=Entrada;1=Saída"/>` — **enumeração do próprio
  campo**, que nenhuma tabela externa traz;
* `<valores-validos datasource="UF_SIGLA_NOME"/>` — o campo é validado contra
  uma tabela externa, e o descritor diz **qual**;
* `referenciaPesquisa="0200;COD_ITEM"` — o campo referencia outro registro,
  que é como o PVA sabe que um `COD_ITEM` do C170 tem de existir no 0200;
* `<validador id="..."/>` — regras compostas (ex.: `REGRA_CST_ICMS_CAMPOS_ICMS_C170`),
  implementadas em Java. Aqui só se registra **que existem**: reimplementá-las
  às cegas produziria divergência silenciosa com o validador oficial.

Por que isso importa: a validação por tabela sozinha erra nos dois sentidos.
Aponta o que o PVA não cobra — o `CST_ICMS` do EFD Contribuições, por exemplo,
não tem `valores-validos` lá — e deixa passar o que ele cobra por enumeração
inline.
"""

import os
import re
import zipfile

JAR_ICMS = (r"C:\Arquivos de Programas RFB\Programas SPED\Fiscal"
            r"\lib\br.gov.serpro.sped.fiscalpva\fiscalpva-dominio.jar")
JAR_CONTRIB = (r"C:\Arquivos de Programas RFB\Programas SPED"
               r"\EFD-Contribuicoes\lib\br.gov.serpro.sped.piscofinspva"
               r"\piscofinspva-infra.jar")

RE_REGISTRO = re.compile(r"<registro\b([^>]*)>", re.S)
RE_CAMPO = re.compile(r"<campo\b([^>]*?)(/?)>", re.S)
RE_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
RE_VALORES = re.compile(r"<valores-validos\b([^>]*)/?>", re.S)


def _attrs(txt):
    return dict(RE_ATTR.findall(txt or ""))


def descritor_mais_recente(jar):
    """Caminho interno do descritor de escrituração de maior versão.

    "Maior" é medido pelo par (ato/estrutura, versão) lido do próprio caminho;
    quando empatam, vence o arquivo maior, que é o que traz mais registros.
    """
    if not os.path.exists(jar):
        return None, None
    z = zipfile.ZipFile(jar)
    alvos = [n for n in z.namelist()
             if n.endswith("descritor.xml") and "escrituracao" in n]
    if not alvos:
        return None, None

    def chave(n):
        nums = [int(x) for x in re.findall(r"(\d+)", n)]
        return (nums, z.getinfo(n).file_size)

    return z, max(alvos, key=chave)


def carregar(layout, jar=None):
    """Estrutura do leiaute segundo o PVA.

    Devolve `{registro: {"nivel", "ocorrencia", "obrigatorio", "chave",
    "validadores": [...], "campos": {nome: {...}}}}` e um dict de informação.
    """
    jar = jar or (JAR_ICMS if layout == "ICMS" else JAR_CONTRIB)
    z, caminho = descritor_mais_recente(jar)
    if z is None:
        return {}, {"jar": jar, "descritor": None, "erro": "PVA não instalado"}
    xml = z.read(caminho).decode("utf-8", "replace")

    # corta o XML nos limites de cada <registro ...> ... próximo <registro
    pos = [(m.start(), _attrs(m.group(1))) for m in RE_REGISTRO.finditer(xml)]
    out = {}
    for k, (ini, at) in enumerate(pos):
        fim = pos[k + 1][0] if k + 1 < len(pos) else len(xml)
        trecho = xml[ini:fim]
        reg = at.get("id", "")
        if not reg:
            continue
        campos = {}
        for m in RE_CAMPO.finditer(trecho):
            ca = _attrs(m.group(1))
            nome = ca.get("id")
            if not nome:
                continue
            # o <valores-validos> do campo vem antes do próximo <campo
            prox = trecho.find("<campo", m.end())
            corpo = trecho[m.end():prox if prox > 0 else len(trecho)]
            vv = RE_VALORES.search(corpo)
            va = _attrs(vv.group(1)) if vv else {}
            valores = None
            if va.get("valores"):
                valores = [p.split("=")[0].strip()
                           for p in va["valores"].split(";") if p.strip()]
            campos[nome] = {
                "n": int(ca["n"]) if ca.get("n", "").isdigit() else None,
                "tipo": ca.get("tipo", ""),
                "tamanho": ca.get("tamanho", ""),
                "decimais": ca.get("casasdecimais", ""),
                "obrigatorio": ca.get("obrigatorio", ""),
                "valores": valores,
                "datasource": va.get("datasource"),
                "referencia": ca.get("referenciaPesquisa"),
            }
        out[reg] = {
            "nivel": int(at["nivel"]) if at.get("nivel", "").isdigit() else None,
            "ocorrencia": at.get("ocorrencia", ""),
            "obrigatorio": at.get("obrigatorio", ""),
            "chave": at.get("chave", ""),
            "validadores": re.findall(r'<validador\s+id\s*=\s*"([^"]+)"',
                                      trecho),
            "campos": campos,
        }
    info = {"jar": jar, "descritor": caminho, "registros": len(out)}
    return out, info


def campos_com_valores(estrutura):
    """`{campo: set(valores)}` das enumerações declaradas no descritor.

    Um campo pode aparecer em vários registros com a mesma enumeração; quando
    divergem, a união seria frouxa e a interseção, arriscada — então o campo é
    descartado e fica para a validação por registro.
    """
    por_campo = {}
    conflito = set()
    for reg, d in estrutura.items():
        for nome, c in d["campos"].items():
            if not c["valores"]:
                continue
            v = frozenset(c["valores"])
            if nome in por_campo and por_campo[nome] != v:
                conflito.add(nome)
            por_campo[nome] = v
    return {k: set(v) for k, v in por_campo.items() if k not in conflito}


def valores_por_registro(estrutura):
    """`{(registro, campo): set(valores)}` — a forma exata como o PVA cobra."""
    out = {}
    for reg, d in estrutura.items():
        for nome, c in d["campos"].items():
            if c["valores"]:
                out[(reg, nome)] = set(c["valores"])
    return out


def referencias(estrutura):
    """`{(registro, campo): (registro_alvo, campo_alvo)}` — de onde o PVA
    cobra que o código exista. É o mapa que faz "COD_ITEM do C170 tem de estar
    no 0200" deixar de ser regra escrita à mão."""
    out = {}
    for reg, d in estrutura.items():
        for nome, c in d["campos"].items():
            ref = c.get("referencia")
            if not ref or ";" not in ref:
                continue
            alvo, campo_alvo = ref.split(";", 1)
            out[(reg, nome)] = (alvo.strip(), campo_alvo.strip())
    return out


def datasources(estrutura):
    """`{campo: datasource}` dos campos validados contra tabela externa."""
    out = {}
    for _reg, d in estrutura.items():
        for nome, c in d["campos"].items():
            if c.get("datasource"):
                out.setdefault(nome, c["datasource"])
    return out


def disponivel():
    return os.path.exists(JAR_ICMS) or os.path.exists(JAR_CONTRIB)

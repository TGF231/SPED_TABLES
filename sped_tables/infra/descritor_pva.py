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

import html
import os
import re
import zipfile

from sped_tables.infra import config

# o descritor é pedido a cada abertura de arquivo por três módulos
# (diagnóstico, validação, revisão); o .jar é lido uma vez por versão dele
_cache = {}

RE_REGISTRO = re.compile(r"<registro\b([^>]*)>", re.S)
RE_CAMPO = re.compile(r"<campo\b([^>]*?)(/?)>", re.S)
RE_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
RE_VALORES = re.compile(r"<valores-validos\b([^>]*)/?>", re.S)
RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)


def _attrs(txt):
    # os textos vêm com entidades XML (&quot;, &#8220;): o rótulo e a
    # descrição aparecem na ajuda do campo
    return {k: html.unescape(v) for k, v in RE_ATTR.findall(txt or "")}


def descritor_mais_recente(jar):
    """Caminho interno do descritor de escrituração de maior versão.

    "Maior" é medido pelo par (ato/estrutura, versão) lido do próprio caminho;
    quando empatam, vence o arquivo maior, que é o que traz mais registros.
    """
    if not jar or not os.path.exists(jar):
        return None, None
    z = zipfile.ZipFile(jar)
    alvos = [n for n in z.namelist()
             if n.endswith("descritor.xml") and "escrituracao" in n]
    if not alvos:
        z.close()
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
    jar = jar or config.jar_descritor(layout)
    try:
        st = os.stat(jar)
        marca = (jar, st.st_mtime, st.st_size)
    except (OSError, TypeError):
        marca = None
    if marca is not None and marca in _cache:
        return _cache[marca]
    resultado = _ler(jar)
    if marca is not None:
        _cache[marca] = resultado
    return resultado


def _ler(jar):
    """Lê e interpreta o descritor mais recente do `.jar`."""
    z, caminho = descritor_mais_recente(jar)
    if z is None:
        return {}, {"jar": jar, "descritor": None, "erro": "PVA não instalado"}
    with z:
        xml = z.read(caminho).decode("utf-8", "replace")
    # o descritor guarda campos excluídos do leiaute dentro de comentário
    # ("Campo excluído devido à exclusão do registro" — o IND_ST do 1010, com
    # o mesmo n=4 do IND_COMB). Lidos como campos, viravam obrigatórios
    # fantasmas e desalinhavam a posição dos demais.
    xml = RE_COMENTARIO.sub("", xml)

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
            significados = {}
            if va.get("valores"):
                valores = [p.split("=")[0].strip()
                           for p in va["valores"].split(";") if p.strip()]
                significados = {p.split("=")[0].strip(): p.split("=", 1)[1]
                                for p in va["valores"].split(";")
                                if "=" in p}
            # n="17'" (D750.DED): o número vale, a aspa é erro de digitação
            num = re.match(r"\s*(\d+)", ca.get("n", ""))
            campos[nome] = {
                "n": int(num.group(1)) if num else None,
                "tipo": ca.get("tipo", ""),
                "tamanho": ca.get("tamanho", ""),
                "decimais": ca.get("casasdecimais", ""),
                "obrigatorio": ca.get("obrigatorio", ""),
                "valores": valores,
                "datasource": va.get("datasource"),
                "referencia": ca.get("referenciaPesquisa"),
                "rotulo": ca.get("rotulo", ""),
                "descricao": ca.get("descricao", ""),
                "significados": significados,
            }
        out[reg] = {
            "nivel": int(at["nivel"]) if at.get("nivel", "").isdigit() else None,
            "ocorrencia": at.get("ocorrencia", ""),
            "obrigatorio": at.get("obrigatorio", ""),
            "chave": at.get("chave", ""),
            "rotulo": at.get("rotulo", ""),
            "descricao": at.get("descricao", ""),
            "validadores": re.findall(r'<validador\s+id\s*=\s*"([^"]+)"',
                                      trecho),
            "campos": campos,
        }
    info = {"jar": jar, "descritor": caminho, "registros": len(out)}
    return out, info


def disponivel():
    return any(os.path.exists(config.jar_descritor(layout) or "")
               for layout in config.PVAS)

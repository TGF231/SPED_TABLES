# -*- coding: utf-8 -*-
"""
descritor.py
------------
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

Só entram na estrutura os **fatos do leiaute** (ADR 0001): o que o campo e o
registro declaram. Nada da edição na tela, das mensagens nem do SQL do PVA é
lido daqui.

Por que isso importa: a validação por tabela sozinha erra nos dois sentidos.
Aponta o que o PVA não cobra — o `CST_ICMS` do EFD Contribuições, por exemplo,
não tem `valores-validos` lá — e deixa passar o que ele cobra por enumeração
inline.

Este é o parser que, até a base de referência, morava em
`sped_tables/infra/descritor_pva.py`: agora ele só roda na máquina de quem
compila.
"""

import html
import re
import zipfile

RE_REGISTRO = re.compile(r"<registro\b([^>]*)>", re.S)
RE_CAMPO = re.compile(r"<campo\b([^>]*?)(/?)>", re.S)
RE_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
RE_VALORES = re.compile(r"<valores-validos\b([^>]*)/?>", re.S)
RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)


def _attrs(txt):
    # os textos vêm com entidades XML (&quot;, &#8220;): o rótulo e a
    # descrição aparecem na ajuda do campo
    return {k: html.unescape(v) for k, v in RE_ATTR.findall(txt or "")}


def _caminhos(z):
    return [n for n in z.namelist()
            if n.endswith("descritor.xml") and "escrituracao" in n]


def _numeros(caminho):
    return [int(x) for x in re.findall(r"(\d+)", caminho)]


def mais_recente(jar):
    """Caminho interno do descritor de maior versão: maior (ato/estrutura,
    versão) lido do próprio caminho; no empate, o arquivo maior."""
    with zipfile.ZipFile(jar) as z:
        alvos = _caminhos(z)
        if not alvos:
            return None
        return max(alvos, key=lambda n: (_numeros(n), z.getinfo(n).file_size))


def por_versao(jar, layout, tabela_versoes):
    """`{COD_VER: caminho interno}`.

    No ICMS/IPI a pasta diz a versão: `ato020` é o COD_VER 020; dentro do
    ato vale a maior (estrutura, versão). No Contribuições as pastas
    (`estrutura7007`…) não dizem a versão: só a versão **em aberto** da
    tabela (DT_FIM vazio) é ligada, ao descritor mais recente."""
    with zipfile.ZipFile(jar) as z:
        alvos = _caminhos(z)
        tam = {n: z.getinfo(n).file_size for n in alvos}
    if not alvos:
        return {}
    if layout == "CONTRIB":
        abertas = [c for c, (_i, fim) in tabela_versoes.items() if not fim]
        if len(abertas) != 1:
            return {}
        return {abertas[0]: max(alvos, key=lambda n: (_numeros(n), tam[n]))}
    out = {}
    for n in alvos:
        m = re.search(r"/ato(\d+)/", n)
        if not m:
            continue
        cod = "%03d" % int(m.group(1))
        if cod not in out or ((_numeros(n), tam[n])
                              > (_numeros(out[cod]), tam[out[cod]])):
            out[cod] = n
    return out


def ler(jar, caminho):
    """Estrutura do descritor `caminho` do `.jar`:
    `{registro: {"nivel", "ocorrencia", "obrigatorio", "chave", "rotulo",
    "descricao", "validadores", "campos": {nome: {...}}}}`, na ordem do
    XML (a ordem dos campos é a posição)."""
    with zipfile.ZipFile(jar) as z:
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
    return out

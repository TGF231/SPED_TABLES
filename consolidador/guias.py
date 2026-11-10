# -*- coding: utf-8 -*-
"""Extrai os **guias práticos** (EFD ICMS/IPI e EFD Contribuições) para
`base/guias/`, que o programa usa como texto de ajuda e como a fonte
escrita das regras que reproduz.

    python -m consolidador guia ICMS    "Guia Prático EFD - Versão 3.2.4.pdf"
    python -m consolidador guia CONTRIB "Guia_Pratico_EFD_Contribuicoes_Versao_1_35.pdf"

Precisa do `pdftotext` (vem com o Git para Windows, em `mingw64/bin`, e com
o poppler). O texto sai com `-layout`: no modo corrido o PDF embaralha
algumas tabelas de campos ("Nº Campo 01 REG 02 IND_OPER 03…" numa linha só,
no C100), e com o leiaute preservado cada campo da tabela fica na sua
linha. Os parágrafos, quebrados em várias linhas, são juntados aqui.

O que se extrai de cada registro: título, objetivo, a *Validação do
Registro*, observações, nível e ocorrência; e, de cada campo, o número, o
nome e os trechos de *Valores válidos*, *Preenchimento* e *Validação*.

O que **não** se extrai, de propósito: tipo, tamanho, decimais e
obrigatoriedade da tabela de campos. O PDF quebra as colunas sem ordem, e
essas declarações vêm melhor do **descritor do PVA**, que é o que valida.
Da tabela fica só o número e o nome de cada campo, para conferir a largura
do registro contra o leiaute (`tests/test_guias.py`).

Registro que o guia descreve mais de uma vez (versões por período, como o
E310 do ICMS/IPI) fica com a **última** descrição, que é a vigente.
"""

import json
import os
import re
import shutil
import subprocess
import unicodedata

CABECALHO = re.compile(
    r"^\s*(Guia Pr[áa]tico.*Vers[ãa]o.*|Atualiza[çc][ãa]o:.*|"
    r"P[áa]gina \d+ de \d+|\d{1,3})\s*$")
INICIO = {
    "ICMS": re.compile(r"^REGISTRO ([0-9A-Z]{4})\s*:\s*(\S.*)$"),
    "CONTRIB": re.compile(r"^Registro ([0-9A-Z]{4})\s*:\s*(\S.*)$"),
}
FIM_DE_SECAO = re.compile(
    r"^(BLOCO [0-9A-Z]\b|Bloco [0-9A-Z]\s*[:–-]|Se[çc][ãa]o \d+\s*[-–]|"
    r"CAP[ÍI]TULO [IVX]+|Cap[íi]tulo [IVX]+\s*[-–])")
LINHA_DA_TABELA = re.compile(r"^(\d{2,3})\s+([A-Z][A-Z0-9_]*)\b")
# "Campo 06 (VL_BC_ICMS) - ", "Campos 04 a 06 - ", "Campo 03 – "
MARCA_CAMPO = re.compile(
    r"Campos?\s+(\d{2,3})((?:\s*(?:,|a|e)\s*\d{2,3})*)\s*"
    r"(?:\(([^)]{1,60})\))?\s*[-–—:]\s*")
ROTULO = re.compile(r"(Valor(?:es)?\s+[Vv][áa]lido(?:s)?|Preenchimento|"
                    r"Valida[çc][ãa]o)\s*:")
INICIO_DE_TEXTO = re.compile(r"(Valor|Preench|Valida|Observa|Aten)")


def texto_do_pdf(pdf):
    exe = shutil.which("pdftotext")
    if exe is None:
        alt = r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"
        exe = alt if os.path.isfile(alt) else None
    if exe is None:
        raise SystemExit("pdftotext não encontrado (Git para Windows ou "
                         "poppler)")
    out = subprocess.run([exe, "-enc", "UTF-8", "-layout", pdf, "-"],
                         check=True,
                         capture_output=True).stdout
    return out.decode("utf-8")


def _identificacao(texto, layout):
    """`(versão, atualização)` do cabeçalho de página do guia — "Atualização:
    30 de julho de 2026" no ICMS/IPI, "Atualização em 18/06/2021" no
    Contribuições."""
    v = re.search(r"Vers[ãa]o\s+([\d.]+)", texto)
    a = re.search(r"Atualiza[çc][ãa]o:\s*([^\n]+)" if layout == "ICMS"
                  else r"Atualiza[çc][ãa]o em\s*([\d/]+)", texto)
    return (v.group(1) if v else ""), (a.group(1).strip() if a else "")


def _linhas(texto):
    return [l.rstrip() for l in texto.replace("\f", "\n").splitlines()
            if not CABECALHO.match(l)]


def _juntar(linhas):
    return re.sub(r"\s+", " ", " ".join(l.strip() for l in linhas)).strip()


def _blocos(linhas, layout):
    rx = INICIO[layout]
    marcas = [(i, m.group(1), m.group(2)) for i, l in enumerate(linhas)
              for m in [rx.match(l)] if m and "....." not in l
              and not m.group(2).startswith("Campo")]
    for k, (i, reg, titulo) in enumerate(marcas):
        fim = marcas[k + 1][0] if k + 1 < len(marcas) else len(linhas)
        for j in range(i + 1, fim):
            if FIM_DE_SECAO.match(linhas[j]):
                fim = j
                break
        yield reg, titulo, linhas[i + 1:fim]


def _segmentar(texto):
    """Divide o parágrafo de um campo pelos rótulos do guia."""
    marcas = list(ROTULO.finditer(texto))
    partes = {}
    if not marcas:
        return {"texto": texto} if texto else {}
    if texto[:marcas[0].start()].strip():
        partes["texto"] = texto[:marcas[0].start()].strip(" .-–")
    for k, m in enumerate(marcas):
        ate = marcas[k + 1].start() if k + 1 < len(marcas) else len(texto)
        r = m.group(1).lower()
        chave = ("valores" if r.startswith("valor") else
                 "preenchimento" if r.startswith("preench") else "validacao")
        trecho = texto[m.end():ate].strip()
        partes[chave] = ("%s %s" % (partes[chave], trecho)).strip() \
            if chave in partes else trecho
    return partes


def _numeros(primeiro, resto):
    nums = [int(primeiro)]
    if not resto:
        return nums
    ultimos = [int(x) for x in re.findall(r"\d{2,3}", resto)]
    if re.search(r"\ba\b", resto) and ultimos:
        return list(range(nums[0], ultimos[-1] + 1))
    return nums + ultimos


def _paragrafos(linhas):
    """`{n: (nome, texto)}` dos parágrafos "Campo NN" depois da tabela."""
    texto = "\n".join(linhas)
    aceitas = []
    for m in MARCA_CAMPO.finditer(texto):
        antes = texto[texto.rfind("\n", 0, m.start()) + 1:m.start()]
        no_inicio = not antes.strip()
        seguinte = texto[m.end():m.end() + 12]
        # no meio da linha, só quando segue um rótulo do guia: "o campo 03
        # dos 10 registros" é menção, não começo de parágrafo
        if no_inicio or INICIO_DE_TEXTO.match(seguinte):
            aceitas.append(m)
    out = {}
    for k, m in enumerate(aceitas):
        ate = aceitas[k + 1].start() if k + 1 < len(aceitas) else len(texto)
        corpo = _juntar(texto[m.end():ate].splitlines())
        nome = (m.group(3) or "").strip()
        for n in _numeros(m.group(1), m.group(2)):
            ant = out.get(n)
            out[n] = (nome or (ant[0] if ant else ""),
                      ("%s %s" % (ant[1], corpo)).strip() if ant else corpo)
    return out, (texto[:aceitas[0].start()] if aceitas else texto)


def _nome(txt):
    """Nome de campo como o leiaute o escreve: o guia tem `COD_ NAT_CC` com
    espaço e `NÍVEL`, `SAÍDAS` com acento."""
    sem_acento = unicodedata.normalize("NFKD", txt)
    return "".join(c for c in sem_acento
                   if not unicodedata.combining(c) and not c.isspace())


def _linha_da_tabela(linha, margem=0):
    """`(número, nome)` de uma linha da tabela de campos, ou `(None, "")`.

    A linha do campo começa na margem da tabela (a do "Nº", que pode vir
    toda recuada, como no C114); a continuação da descrição vem
    recuada — e é ela que pode começar com dois dígitos ("01 - Bagaço de
    cana", na lista de códigos do 1391). O nome pode ter ido para outra
    linha (C165, K275) ou vir com minúscula (`CHV_DOCe`): então fica vazio,
    e o parágrafo do campo o completa."""
    m = re.match(r"^(\s*)(\d{2,3})(?:\s+(\S+))?", linha)
    if not m or len(m.group(1)) > margem + 2:
        return None, ""
    token = (m.group(3) or "").rstrip("*")      # "MES_REF*" (nota de rodapé)
    if not (re.fullmatch(r"[A-ZÀ-Ý][A-ZÀ-Ý0-9_]*", token) or
            re.fullmatch(r"[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]*", token)):
        token = ""
    return int(m.group(2)), _nome(token).upper()


def _tabela(linhas):
    """Campos `{n: {"nome"}}` da tabela que começa em `linhas[0]` (a linha
    "Nº Campo…") e o índice da linha em que ela termina.

    O fim é o "Observações:" **da margem**: recuado, é a descrição de um
    campo que se chama assim (o OBS do 1391)."""
    margem = len(linhas[0]) - len(linhas[0].lstrip())
    fim = next((k for k, l in enumerate(linhas)
                if k and len(l) - len(l.lstrip()) <= margem + 2 and
                re.match(r"\s*(Observa[çc]|N[íi]vel hier|Campos?\s+\d)", l)),
               len(linhas))
    campos = {}
    for l in linhas[1:fim]:
        n, nome = _linha_da_tabela(l, margem)
        esperado = len(campos) + 1
        if n == esperado + 1 and esperado > 1:
            # número que o PDF não pôs na margem: fica a vaga, e o
            # parágrafo do campo diz o nome
            campos[esperado] = {"nome": ""}
            esperado += 1
        if n == esperado:
            campos[n] = {"nome": nome}
    return campos, fim


def _registro(titulo, corpo):
    d = {"titulo": titulo.strip()}
    i = 0
    # título que continua na linha seguinte, em maiúsculas
    while i < len(corpo) and corpo[i].strip() and \
            corpo[i].strip() == corpo[i].strip().upper() and \
            not corpo[i].lstrip().startswith("Nº") and \
            not LINHA_DA_TABELA.match(corpo[i].strip()):
        d["titulo"] += " " + corpo[i].strip()
        i += 1
    corpo = corpo[i:]
    i_tab = next((k for k, l in enumerate(corpo)
                  if l.lstrip().startswith("Nº")), None)
    if i_tab is None:
        return None
    cabeca = "\n".join(corpo[:i_tab])
    m = re.search(r"Valida[çc][ãa]o do [Rr]egistro\s*:(.*)", cabeca, re.S)
    if m:
        d["validacao_registro"] = _juntar(m.group(1).splitlines())
        cabeca = cabeca[:m.start()]
    d["objetivo"] = _juntar(cabeca.splitlines())

    # o registro pode trazer mais de uma tabela — "Leiaute do Registro M210
    # aplicável aos fatos geradores até 31/12/2018" e outra "a partir de
    # 01/01/2019". Vale a maior; no empate, a última (a vigente)
    melhor = None
    for k, l in enumerate(corpo):
        if k < i_tab or not l.lstrip().startswith("Nº"):
            continue
        campos, fim = _tabela(corpo[k:])
        if campos and (melhor is None or len(campos) >= len(melhor[0])):
            melhor = (campos, k + fim)
    if melhor is None:
        return None
    campos, fim_tab = melhor
    resto = corpo[fim_tab:]
    proxima = next((k for k, l in enumerate(resto)
                    if l.lstrip().startswith("Nº")), len(resto))
    paragrafos, observacoes = _paragrafos(resto[:proxima])
    # parágrafo de campo que a tabela não tem é de outro assunto: no X111 do
    # Contribuições, "Campo 01: Identificação do registro…" descreve o
    # processo referenciado, não os campos do registro
    paragrafos = {n: p for n, p in paragrafos.items() if n <= len(campos)}
    m = re.search(r"N[íi]vel hier[áa]rquico\s*[-–:]\s*(\d)", observacoes)
    if m:
        d["nivel"] = int(m.group(1))
    m = re.search(r"Ocorr[êe]ncia\s*[-–:]\s*([^\n]+)", observacoes)
    if m:
        d["ocorrencia"] = m.group(1).strip()
    obs = _juntar(re.sub(r"N[íi]vel hier[áa]rquico\s*[-–:]\s*\d|"
                         r"Ocorr[êe]ncia\s*[-–:]\s*[^\n]+", "",
                         observacoes).splitlines())
    obs = re.sub(r"^Observa[çc][õo]es\s*:\s*", "", obs)
    if obs:
        d["observacoes"] = obs
    for n, (nome, texto) in paragrafos.items():
        alvo = campos[n]
        nome = _nome(nome) if re.fullmatch(r"[A-ZÀ-Ý0-9_ ]+", nome) else ""
        if nome and not alvo["nome"]:
            alvo["nome"] = nome
        if nome:
            alvo["nome_no_paragrafo"] = nome
        alvo.update(_segmentar(texto))
    d["campos"] = {str(n): c for n, c in sorted(campos.items())}
    return d


def extrair(texto, layout):
    versao, atualizacao = _identificacao(texto, layout)
    registros = {}
    for reg, titulo, corpo in _blocos(_linhas(texto), layout):
        d = _registro(titulo, corpo)
        if d is not None:
            registros[reg] = d          # vale a última descrição
    return {"guia": ("EFD ICMS/IPI" if layout == "ICMS"
                     else "EFD Contribuições"),
            "versao": versao, "atualizacao": atualizacao,
            "registros": registros}


def gravar(layout, pdf, fontes):
    """Extrai o guia do PDF para `fontes/guias/<layout>.json` e devolve o
    caminho."""
    if layout not in ("ICMS", "CONTRIB"):
        raise ValueError("leiaute: ICMS ou CONTRIB")
    guia = extrair(texto_do_pdf(pdf), layout)
    destino = os.path.join(fontes, "guias", layout + ".json")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(guia, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return destino

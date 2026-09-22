# -*- coding: utf-8 -*-
"""Leitura das tabelas oficiais da EFD Contribuições usadas para conferência de
CST por NCM:

  * Tabela 4.3.13 — Produtos sujeitos à **alíquota zero** (CST 06);
  * Tabela 4.3.10 — Produtos monofásicos de **alíquotas diferenciadas**
    (`PROD_MONO_ALIQ_DIFER`): perfumaria, higiene pessoal, medicamentos,
    veículos, autopeças — a Lei 10.147/2000 e afins;
  * Tabela 4.3.11 — Produtos monofásicos de **alíquota por unidade de medida**
    (`PROD_MONO_ALIQ_UNID`): combustíveis, bebidas frias;
  * Tabela de **gênero do item** (2 primeiros dígitos do NCM = capítulo);
  * Tabela **NCM vigente** (XLSX do Portal Siscomex), para validar/expandir NCMs.

As tabelas do PVA ficam, por padrão, em
``C:\\Arquivos de Programas RFB\\Programas SPED\\EFD-Contribuicoes\\recursos\\tabelas``
com nomes versionados, por exemplo
``SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_PROD_ALIQ_ZERO$51$166``.
O número após o nome da tabela é a **versão**; `localizar_tabela` escolhe a maior.
Também é possível informar o caminho de cada arquivo diretamente.
"""

import os
import re
import glob

PASTA_PADRAO = (r"C:\Arquivos de Programas RFB\Programas SPED"
                r"\EFD-Contribuicoes\recursos\tabelas")

# fragmento que identifica cada tabela no nome do arquivo
CHAVE_ALIQ_ZERO = "PROD_ALIQ_ZERO"
# São DUAS tabelas de monofásico, e ler só uma esconde metade dos produtos:
# o NCM 34011190 (sabonete) só existe na de alíquotas diferenciadas, e sem ela
# o programa não via nada que o PVA via.
CHAVE_MONO = "PROD_MONO_ALIQ_UNID"
CHAVE_MONO_DIFER = "PROD_MONO_ALIQ_DIFER"
CHAVE_GENERO = "GENERO_ITEM"


def _so_digitos(s):
    return "".join(c for c in (s or "") if c.isdigit())


def _versao_do_nome(nome, chave):
    """Extrai a versão (inteiro) que segue a `chave` no nome do arquivo.
    Aceita '$' (formato oficial) ou '_' como separador. None se não achar."""
    m = re.search(re.escape(chave) + r"[$_](\d+)", nome)
    return int(m.group(1)) if m else None


def localizar_tabela(pasta, chave):
    """Na `pasta`, devolve o caminho do arquivo da tabela `chave` com a MAIOR
    versão (ou None se nenhum). Ignora extensão e prefixos."""
    if not pasta or not os.path.isdir(pasta):
        return None
    melhor = None
    melhor_v = -1
    for caminho in glob.glob(os.path.join(pasta, "*")):
        nome = os.path.basename(caminho)
        if chave not in nome:
            continue
        v = _versao_do_nome(nome, chave)
        v = v if v is not None else 0
        if v > melhor_v:
            melhor_v, melhor = v, caminho
    return melhor


def _ler_versao_cabecalho(linha):
    m = re.search(r"vers[\u00e3a]o=(\S+)", linha)
    return m.group(1) if m else None


def carregar_tabela_produtos(caminho, encoding="latin-1"):
    """Lê uma tabela de produtos (4.3.11 ou 4.3.13). Devolve dict com 'versao'
    e 'registros' (lista). Cada registro traz codigo, desc, dt_ini, dt_fim,
    ncm (lista de prefixos, só dígitos), ncm_ex (exceções) e, na 4.3.11,
    unid/aliq_pis/aliq_cofins."""
    with open(caminho, encoding=encoding) as fh:
        linhas = fh.read().splitlines()
    if not linhas:
        return {"versao": None, "registros": []}
    versao = _ler_versao_cabecalho(linhas[0])
    registros = []
    for l in linhas[1:]:
        if not l.strip():
            continue
        p = l.split("|")
        if len(p) < 5:
            continue
        reg = {
            "codigo": p[0].strip(),
            "desc": p[1].strip(),
            "dt_ini": p[2].strip(),
            "dt_fim": p[3].strip(),
            "ncm": [_so_digitos(x) for x in p[4].split(";") if x.strip()],
            "ncm_ex": [_so_digitos(x) for x in
                       (p[5].split(";") if len(p) > 5 else []) if x.strip()],
        }
        if len(p) >= 10:            # 4.3.11: ...|EX_IPI|UNID|ALIQ_PIS|ALIQ_COFINS
            reg["unid"] = p[7].strip()
            reg["aliq_pis"] = p[8].strip()
            reg["aliq_cofins"] = p[9].strip()
        elif len(p) >= 9:           # 4.3.10: ...|EX_IPI|ALIQ_PIS|ALIQ_COFINS
            reg["aliq_pis"] = p[7].strip()
            reg["aliq_cofins"] = p[8].strip()
        registros.append(reg)
    return {"versao": versao, "registros": registros}


def carregar_genero(caminho, encoding="latin-1"):
    """Lê a tabela de gênero do item. Devolve dict {codigo_2dig: descricao}."""
    with open(caminho, encoding=encoding) as fh:
        linhas = fh.read().splitlines()
    genero = {}
    for l in linhas[1:]:
        p = l.split("|")
        if len(p) >= 2 and p[0].strip():
            genero[p[0].strip().zfill(2)] = p[1].strip()
    return genero


def carregar_ncm_vigente(caminho_xlsx):
    """Lê a planilha de NCM vigente (Siscomex). Devolve o conjunto de NCMs de 8
    dígitos vigentes. Requer openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho_xlsx, read_only=True, data_only=True)
    ws = wb.active
    ncms = set()
    for row in ws.iter_rows(values_only=True):
        cod = row[0] if row else None
        d = _so_digitos(cod if isinstance(cod, str) else str(cod or ""))
        if len(d) == 8:
            ncms.add(d)
    return ncms


class ClassificadorNCM:
    """Classifica um NCM (8 dígitos) como alíquota zero e/ou monofásico, casando
    o NCM do produto com os prefixos das tabelas (posição/capítulo). Considera as
    exceções (NCM_EX) e, opcionalmente, a vigência numa data (DDMMAAAA)."""

    def __init__(self, tab_zero=None, tab_mono=None, genero=None,
                 ncm_vigente=None):
        self.genero = genero or {}
        self.ncm_vigente = ncm_vigente or set()
        self._zero = self._indexar(tab_zero)
        self._mono = self._indexar(tab_mono)
        self.versao_zero = (tab_zero or {}).get("versao")
        self.versao_mono = (tab_mono or {}).get("versao")

    @staticmethod
    def _indexar(tab):
        """Indexa prefixos por tamanho + exceções, com a vigência de cada."""
        por_tam = {}          # tamanho -> {prefixo: [(dt_ini, dt_fim), ...]}
        exc = set()
        for reg in (tab or {}).get("registros", []):
            vig = (reg.get("dt_ini", ""), reg.get("dt_fim", ""))
            for n in reg["ncm"]:
                por_tam.setdefault(len(n), {}).setdefault(n, []).append(vig)
            for n in reg.get("ncm_ex", []):
                exc.add(n)
        return {"por_tam": por_tam, "exc": exc}

    @staticmethod
    def _vigente(vigencias, data):
        if not data:
            return True
        for dt_ini, dt_fim in vigencias:
            ini = dt_ini or "00000000"
            fim = dt_fim or "99999999"
            # datas em DDMMAAAA -> chave AAAAMMDD para comparar
            def key(s):
                s = _so_digitos(s)
                return s[4:8] + s[2:4] + s[0:2] if len(s) == 8 else s
            if key(ini) <= key(data) <= (key(fim) if fim != "99999999"
                                         else "99999999"):
                return True
        return False

    def _casa(self, idx, ncm, data=None):
        d = _so_digitos(ncm)
        if d in idx["exc"]:
            return False
        for t, prefixos in idx["por_tam"].items():
            if len(d) >= t and d[:t] in prefixos:
                if self._vigente(prefixos[d[:t]], data):
                    return True
        return False

    def eh_aliquota_zero(self, ncm, data=None):
        return self._casa(self._zero, ncm, data)

    def eh_monofasico(self, ncm, data=None):
        return self._casa(self._mono, ncm, data)

    def genero_do(self, ncm):
        d = _so_digitos(ncm)
        cap = d[:2]
        return cap, self.genero.get(cap, "")

    def classificar(self, ncm, data=None):
        d = _so_digitos(ncm)
        cap, gen = self.genero_do(d)
        return {
            "ncm": d,
            "aliquota_zero": self.eh_aliquota_zero(d, data),
            "monofasico": self.eh_monofasico(d, data),
            "vigente_ncm": (d in self.ncm_vigente) if self.ncm_vigente else None,
            "genero_cod": cap,
            "genero_desc": gen,
        }


def _unir_tabelas(*tabelas):
    """Funde tabelas de produtos numa só, para o classificador tratar as duas
    listas de monofásico como uma. A versão vira `a+b`, para aparecer na
    interface qual par foi carregado."""
    regs = []
    versoes = []
    for t in tabelas:
        if not t:
            continue
        regs.extend(t.get("registros", []))
        if t.get("versao"):
            versoes.append(str(t["versao"]))
    if not regs and not versoes:
        return None
    return {"versao": "+".join(versoes) or None, "registros": regs}


def carregar_tudo(pasta=None, caminho_zero=None, caminho_mono=None,
                  caminho_genero=None, caminho_ncm=None,
                  caminho_mono_difer=None):
    """Conveniência: localiza (na `pasta`) e/ou carrega as tabelas pelos caminhos
    informados e devolve um ClassificadorNCM pronto. Caminhos explícitos têm
    prioridade sobre a detecção por nome na pasta."""
    czero = caminho_zero or localizar_tabela(pasta, CHAVE_ALIQ_ZERO)
    cmono = caminho_mono or localizar_tabela(pasta, CHAVE_MONO)
    cdifer = caminho_mono_difer or localizar_tabela(pasta, CHAVE_MONO_DIFER)
    cgen = caminho_genero or localizar_tabela(pasta, CHAVE_GENERO)
    tab_zero = carregar_tabela_produtos(czero) if czero else None
    # as duas tabelas de monofásico viram uma só para o classificador
    tab_mono = _unir_tabelas(
        carregar_tabela_produtos(cmono) if cmono else None,
        carregar_tabela_produtos(cdifer) if cdifer else None)
    genero = carregar_genero(cgen) if cgen else None
    ncm_vig = carregar_ncm_vigente(caminho_ncm) if caminho_ncm else None
    return ClassificadorNCM(tab_zero, tab_mono, genero, ncm_vig), {
        "zero": czero, "mono": cmono, "mono_difer": cdifer, "genero": cgen,
        "ncm": caminho_ncm}


# ---------------------------------------------------------------------------
# Verificação de CST de PIS/COFINS por NCM (itens C170: entradas e saídas)
# ---------------------------------------------------------------------------
# CSTs coerentes por operação (E=entrada, S=saída) e classificação do NCM,
# na ótica de comércio/revenda. Ajustáveis conforme a atividade da empresa.
CST_ACEITOS = {
    ("S", "mono"): {"02", "03", "04", "05"},
    ("S", "aliq_zero"): {"06"},
    ("S", "tributado"): {"01", "02", "03", "05", "07", "08", "09", "49", "99"},
    ("E", "mono"): {"70", "71", "72", "73", "74", "75", "98"},
    ("E", "aliq_zero"): {"70", "73", "98"},
    # ("E","tributado") fica fora: há muitos CST de crédito válidos (50-56,
    # 60-66, 70-75, 98) e a escolha depende do direito a crédito.
}
CST_SUGERIDO = {
    ("S", "mono"): "04", ("S", "aliq_zero"): "06", ("S", "tributado"): "01",
    ("E", "mono"): "73", ("E", "aliq_zero"): "73",
}
_ROTULO_CLASSE = {"mono": "monofásico", "aliq_zero": "alíquota zero",
                  "tributado": "tributado"}


def verificar_cst_pis_cofins(doc, classificador, data_ref=None):
    """Confere o CST de PIS/COFINS dos itens **C170** contra a classificação do
    NCM (monofásico / alíquota zero / tributado) obtida das tabelas da RFB.

    Só o C170 é verificável por NCM — o C175 (NFC-e consolidada) não traz
    COD_ITEM. Para cada item, resolve o NCM pelo 0200, classifica e compara o
    CST informado com o conjunto coerente para a operação (entrada/saída).
    Retorna a lista de divergências (dicts).
    """
    i0c = doc._ix("0200", "COD_ITEM")
    i0n = doc._ix("0200", "COD_NCM")
    ncm_de = {}
    for r in doc.registros:
        if r.reg == "0200":
            ncm_de[(r.valor(i0c) or "").strip()] = (r.valor(i0n) or "").strip()

    c_item = doc._ix("C170", "COD_ITEM")
    c_cstp = doc._ix("C170", "CST_PIS")
    c_cstc = doc._ix("C170", "CST_COFINS")
    i_op = doc._ix("C100", "IND_OPER")
    if c_item is None or c_cstp is None:
        return []

    problemas = []
    for r in doc.registros:
        if r.reg != "C170":
            continue
        pai = r.pai
        oper = (pai.valor(i_op) or "").strip() \
            if (pai is not None and i_op is not None) else ""
        op = "E" if oper == "0" else "S"
        cod = (r.valor(c_item) or "").strip()
        ncm = ncm_de.get(cod, "")
        if not ncm:
            continue
        info = classificador.classificar(ncm, data_ref)
        if info["monofasico"]:
            classe = "mono"
        elif info["aliquota_zero"]:
            classe = "aliq_zero"
        else:
            classe = "tributado"
        aceitos = CST_ACEITOS.get((op, classe))
        if aceitos is None:
            continue                       # combinação não verificada

        cst_pis = (r.valor(c_cstp) or "").strip()
        cst_cof = (r.valor(c_cstc) or "").strip() if c_cstc is not None else ""
        fora = []
        if cst_pis and cst_pis not in aceitos:
            fora.append("PIS=%s" % cst_pis)
        if cst_cof and cst_cof not in aceitos:
            fora.append("COFINS=%s" % cst_cof)
        if not fora:
            continue
        problemas.append({
            "uid": r.uid, "op": op, "cod_item": cod, "ncm": ncm,
            "classe": classe, "classe_desc": _ROTULO_CLASSE[classe],
            "genero": info["genero_cod"], "genero_desc": info["genero_desc"],
            "cst_pis": cst_pis, "cst_cofins": cst_cof,
            "cst_sugerido": CST_SUGERIDO.get((op, classe), ""),
            "detalhe": ", ".join(fora),
        })
    return problemas

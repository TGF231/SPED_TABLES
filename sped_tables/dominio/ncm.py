# -*- coding: utf-8 -*-
"""Classificação do NCM (alíquota zero, monofásico, gênero) e a conferência
do CST de PIS/COFINS contra ela.

É regra fiscal, e por isso mora no domínio. As tabelas que a alimentam — as
da RFB que vêm com o PVA do EFD Contribuições — são lidas por
`sped_tables.infra.tabelas_rfb`, que entrega um `ClassificadorNCM` pronto.
"""

from sped_tables.dominio.sped_model import so_digitos


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
                s = so_digitos(s)
                return s[4:8] + s[2:4] + s[0:2] if len(s) == 8 else s
            if key(ini) <= key(data) <= (key(fim) if fim != "99999999"
                                         else "99999999"):
                return True
        return False

    def _casa(self, idx, ncm, data=None):
        d = so_digitos(ncm)
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
        d = so_digitos(ncm)
        cap = d[:2]
        return cap, self.genero.get(cap, "")

    def classificar(self, ncm, data=None):
        d = so_digitos(ncm)
        cap, gen = self.genero_do(d)
        return {
            "ncm": d,
            "aliquota_zero": self.eh_aliquota_zero(d, data),
            "monofasico": self.eh_monofasico(d, data),
            "vigente_ncm": (d in self.ncm_vigente) if self.ncm_vigente else None,
            "genero_cod": cap,
            "genero_desc": gen,
        }


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

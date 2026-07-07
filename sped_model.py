# -*- coding: utf-8 -*-
"""
sped_model.py
-------------
Modelo de dados do SPED em árvore.

* Cada linha do arquivo vira um `Registro`.
* A relação pai/filho é montada na leitura, usando os níveis de `sped_layouts`.
* O modelo preserva a ORDEM ORIGINAL das linhas, de modo que ao salvar o
  arquivo é reconstruído fielmente (com os totais dos blocos, 9900 e 9999
  recalculados).
"""

import itertools
from sped_layouts import nivel, campos, detectar_layout

_id_seq = itertools.count(1)


def _to_num(s):
    """Converte um valor SPED (decimal com vírgula) para float."""
    s = (s or "").strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _fmt_val(v):
    """Formata um número no padrão SPED (2 casas, vírgula decimal)."""
    return ("%.2f" % round(v, 2)).replace(".", ",")


def _fmt_aliq(a):
    """Formata uma alíquota no padrão SPED (vírgula, sem zeros à direita)."""
    s = ("%.4f" % round(float(a), 4)).rstrip("0").rstrip(".")
    return (s or "0").replace(".", ",")



class Registro:
    __slots__ = ("uid", "reg", "bloco", "nivel", "campos", "pai", "filhos",
                 "ordem")

    def __init__(self, partes, layout, ordem):
        self.uid = next(_id_seq)
        self.reg = partes[1] if len(partes) > 1 else ""
        self.bloco = self.reg[0] if self.reg else "?"
        self.nivel = nivel(self.reg, layout)
        # 'campos' = todos os campos da linha, incluindo o REG (índice 0)
        # As listas do SPED começam com '' (antes do 1º '|') e terminam com ''
        # (após o último '|'); removemos esses vazios das pontas.
        self.campos = partes[1:-1] if len(partes) >= 2 else partes[:]
        self.pai = None
        self.filhos = []
        self.ordem = ordem

    def valor(self, idx):
        return self.campos[idx] if 0 <= idx < len(self.campos) else ""

    def set_valor(self, idx, v):
        while len(self.campos) <= idx:
            self.campos.append("")
        self.campos[idx] = v

    def linha_sped(self):
        """Reconstrói a linha no formato |c1|c2|...|"""
        return "|" + "|".join(self.campos) + "|"

    def __repr__(self):
        return "<Reg %s uid=%d nivel=%d filhos=%d>" % (
            self.reg, self.uid, self.nivel, len(self.filhos))


class SpedDocument:
    """Documento SPED completo: lista ordenada + floresta hierárquica."""

    def __init__(self):
        self.layout = "ICMS"
        self.registros = []      # todos, na ordem do arquivo
        self.raizes = []         # registros sem pai (topo de cada bloco)
        self.encoding = "latin-1"
        self.caminho = None
        self._cad_itens = None   # cache COD_ITEM -> DESCR_ITEM (registros 0200)

    # ------------------------------------------------------------------ load
    @classmethod
    def carregar(cls, caminho):
        doc = cls()
        doc.caminho = caminho
        # SPED costuma ser latin-1; tentamos utf-8 como alternativa.
        dados = None
        for enc in ("latin-1", "utf-8", "cp1252"):
            try:
                with open(caminho, "r", encoding=enc) as f:
                    dados = f.read()
                doc.encoding = enc
                break
            except UnicodeDecodeError:
                continue
        if dados is None:
            with open(caminho, "r", encoding="latin-1", errors="replace") as f:
                dados = f.read()
            doc.encoding = "latin-1"

        linhas = [l for l in dados.replace("\r\n", "\n").split("\n")]
        # remove linha final vazia
        linhas = [l for l in linhas if l.strip() != ""]
        doc.layout = detectar_layout(linhas)
        doc._montar(linhas)
        return doc

    def _montar(self, linhas):
        self.registros.clear()
        self.raizes.clear()
        # pilha de ancestrais (apenas dentro do MESMO bloco)
        pilha = []
        bloco_atual = None
        for i, ln in enumerate(linhas):
            if not ln.startswith("|"):
                continue
            partes = ln.split("|")
            r = Registro(partes, self.layout, i)
            self.registros.append(r)

            # ao mudar de bloco, zera a pilha -> nenhum pai cruza blocos
            if r.bloco != bloco_atual:
                pilha = []
                bloco_atual = r.bloco

            # remove da pilha tudo com nível >= ao atual (não pode ser pai)
            while pilha and pilha[-1].nivel >= r.nivel:
                pilha.pop()

            if pilha:
                r.pai = pilha[-1]
                pilha[-1].filhos.append(r)
            else:
                self.raizes.append(r)
            pilha.append(r)

    # ---------------------------------------------------------------- estrutura
    @staticmethod
    def _eh_principal(r):
        """
        Um registro é 'principal' (vira aba/grade de topo do bloco) quando
        não tem pai, ou quando seu pai é apenas um registro administrativo
        de abertura de bloco (nível <= 1, ex.: 0001, C001, M001).
        Registros cujo pai tem nível >= 2 são 'filhos' exibidos em sub-abas.
        """
        return r.pai is None or r.pai.nivel <= 1

    def blocos(self):
        """Lista de blocos presentes, na ordem natural do SPED."""
        presentes = []
        vistos = set()
        for r in self.registros:
            if r.bloco not in vistos:
                vistos.add(r.bloco)
                presentes.append(r.bloco)
        ordem_blocos = "0ABCDEFGHIJKMP19"
        presentes.sort(key=lambda b: (ordem_blocos.index(b)
                                      if b in ordem_blocos else 99, b))
        return presentes

    def tipos_raiz_do_bloco(self, bloco):
        """Tipos de registro PRINCIPAIS do bloco, na ordem de surgimento."""
        tipos = []
        vistos = set()
        for r in self.registros:
            if r.bloco != bloco or not self._eh_principal(r):
                continue
            if r.reg not in vistos:
                vistos.add(r.reg)
                tipos.append(r.reg)
        return tipos

    def registros_raiz_por_tipo(self, bloco, tipo):
        """Registros principais de um tipo dentro do bloco."""
        out = [r for r in self.registros
               if r.bloco == bloco and r.reg == tipo and self._eh_principal(r)]
        out.sort(key=lambda x: x.ordem)
        return out

    @staticmethod
    def tem_detalhe(r):
        """Um registro mostra sub-abas de filhos quando é nível >= 2 e tem filhos."""
        return r.nivel >= 2 and len(r.filhos) > 0

    @staticmethod
    def tipos_filhos(registro):
        """Tipos de registro-filho de um registro, na ordem de surgimento."""
        tipos = []
        vistos = set()
        for f in registro.filhos:
            if f.reg not in vistos:
                vistos.add(f.reg)
                tipos.append(f.reg)
        return tipos

    @staticmethod
    def filhos_por_tipo(registro, tipo):
        return [f for f in registro.filhos if f.reg == tipo]

    # ----------------------------------------------- cadastro de itens (0200)
    def _reindexar_itens(self):
        """(Re)constrói o índice COD_ITEM -> DESCR_ITEM a partir dos 0200."""
        d = {}
        for r in self.registros:
            if r.reg == "0200":
                cod = (r.valor(1) or "").strip()
                if cod:
                    d[cod] = (r.valor(2) or "").strip()
        self._cad_itens = d

    def descricao_item(self, cod):
        """Descrição do item (DESCR_ITEM do 0200) para um COD_ITEM, ou ''."""
        if self._cad_itens is None:
            self._reindexar_itens()
        return self._cad_itens.get((cod or "").strip(), "")

    def invalidar_itens(self):
        """Marca o índice de itens para ser reconstruído (após editar 0200)."""
        self._cad_itens = None

    # ------------------------------------------------- relatório (visão flat)
    COLUNAS_RELATORIO = [
        "TIPO", "NOTA_DATA", "NOTA_N", "NOTA_SERIE", "NOTA_MODELO",
        "NOTA_ITEM", "PROD_COD", "PROD_DESCRICAO", "PROD_NCM",
        "PROD_QTDE", "PROD_VL_UN", "PROD_VL_SUBTOTAL", "PROD_VL_DESC",
        "PROD_VL_TOTAL", "CFOP", "ICMS_CST", "ICMS_BC", "ICMS_ALIQ", "ICMS_VL",
        "ICMSST_BC", "ICMSST_ALIQ", "ICMSST_VL",
        "PIS_CST", "PIS_BC", "PIS_ALIQ", "PIS_VL",
        "COFINS_CST", "COFINS_BC", "COFINS_ALIQ", "COFINS_VL",
        "IPI_CST", "IPI_VL", "CHAVE_ACESSO",
    ]
    # colunas do relatório editáveis -> campo no registro-fonte (C170).
    # As demais (produto/documento/calculadas) são somente-leitura.
    EDIT_C170 = {
        "NOTA_ITEM": "NUM_ITEM", "PROD_COD": "COD_ITEM", "PROD_QTDE": "QTD",
        "PROD_VL_SUBTOTAL": "VL_ITEM", "PROD_VL_DESC": "VL_DESC",
        "CFOP": "CFOP", "ICMS_CST": "CST_ICMS", "ICMS_BC": "VL_BC_ICMS",
        "ICMS_ALIQ": "ALIQ_ICMS", "ICMS_VL": "VL_ICMS",
        "ICMSST_BC": "VL_BC_ICMS_ST", "ICMSST_ALIQ": "ALIQ_ST",
        "ICMSST_VL": "VL_ICMS_ST", "PIS_CST": "CST_PIS", "PIS_BC": "VL_BC_PIS",
        "PIS_ALIQ": "ALIQ_PIS", "PIS_VL": "VL_PIS", "COFINS_CST": "CST_COFINS",
        "COFINS_BC": "VL_BC_COFINS", "COFINS_ALIQ": "ALIQ_COFINS",
        "COFINS_VL": "VL_COFINS", "IPI_CST": "CST_IPI", "IPI_VL": "VL_IPI",
    }

    def itens_relatorio(self, filtros=None):
        """Achata os itens (C170) numa tabela — uma linha por item, com dados do
        C100 pai e do produto (0200) — aplicando os filtros do Modo Relatório.
        Espelha o SELECT usado no banco do ERP, para comparação. Devolve
        (colunas, linhas) com valores já como texto no padrão do arquivo."""
        f = filtros or {}
        C = {c: self._ix("C170", c) for c in (
            "NUM_ITEM", "COD_ITEM", "QTD", "VL_ITEM", "VL_DESC", "CST_ICMS",
            "CFOP", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
            "ALIQ_ST", "VL_ICMS_ST", "CST_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS",
            "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS",
            "VL_COFINS")}
        c_oper = self._ix("C100", "IND_OPER")
        c_mod = self._ix("C100", "COD_MOD")
        c_ser = self._ix("C100", "SER")
        c_num = self._ix("C100", "NUM_DOC")
        c_chv = self._ix("C100", "CHV_NFE")
        c_dtdoc = self._ix("C100", "DT_DOC")
        c_dtes = self._ix("C100", "DT_E_S")

        i0c = self._ix("0200", "COD_ITEM")
        i0d = self._ix("0200", "DESCR_ITEM")
        i0n = self._ix("0200", "COD_NCM")
        prod = {}
        for r in self.registros:
            if r.reg == "0200":
                cod = (r.valor(i0c) or "").strip()
                prod[cod] = (
                    (r.valor(i0d) or "").strip() if i0d is not None else "",
                    (r.valor(i0n) or "").strip() if i0n is not None else "")

        def dkey(s):
            s = (s or "").strip()
            return (s[4:8] + s[2:4] + s[0:2]) if len(s) == 8 else ""

        di = f.get("data_ini") or None      # 'AAAAMMDD'
        dfim = f.get("data_fim") or None
        tipo = f.get("tipo", "T")
        cfop = f.get("cfop")
        ncm = f.get("ncm")
        modelo = f.get("modelo")
        num = f.get("num_nota")
        nitem = f.get("nitem")
        cod_prod = f.get("cod_prod")
        cst_icms = {str(x) for x in (f.get("cst_icms") or [])}
        cst_pis = {str(x) for x in (f.get("cst_pis") or [])}
        cst_cofins = {str(x) for x in (f.get("cst_cofins") or [])}
        cst_ipi = f.get("cst_ipi")
        aliq_pis = f.get("aliq_pis")
        aliq_cofins = f.get("aliq_cofins")

        linhas = []
        uids = []
        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            oper = (c100.valor(c_oper) or "").strip() if c_oper is not None else ""
            tp = "E" if oper == "0" else "S"
            if tipo != "T" and tp != tipo:
                continue
            mod = (c100.valor(c_mod) or "").strip() if c_mod is not None else ""
            if modelo and mod != str(modelo):
                continue
            ndoc = (c100.valor(c_num) or "").strip() if c_num is not None else ""
            if num and ndoc != str(num):
                continue
            dt = (c100.valor(c_dtdoc) or "").strip() if c_dtdoc is not None else ""
            if not dt and c_dtes is not None:
                dt = (c100.valor(c_dtes) or "").strip()
            dk = dkey(dt)
            if di and dk and dk < di:
                continue
            if dfim and dk and dk > dfim:
                continue
            chave = (c100.valor(c_chv) or "").strip() if c_chv is not None else ""
            ser = (c100.valor(c_ser) or "").strip() if c_ser is not None else ""
            data_br = ("%s/%s/%s" % (dt[0:2], dt[2:4], dt[4:8])) \
                if len(dt) == 8 else dt

            for it in c100.filhos:
                if it.reg != "C170":
                    continue

                def v(campo, _it=it):
                    idx = C.get(campo)
                    return (_it.valor(idx) or "").strip() if idx is not None \
                        else ""

                if cfop and v("CFOP") != str(cfop):
                    continue
                if cst_icms and v("CST_ICMS") not in cst_icms:
                    continue
                if cst_pis and v("CST_PIS") not in cst_pis:
                    continue
                if cst_cofins and v("CST_COFINS") not in cst_cofins:
                    continue
                if cst_ipi and v("CST_IPI") != str(cst_ipi):
                    continue
                if nitem and v("NUM_ITEM") != str(nitem):
                    continue
                cod = v("COD_ITEM")
                if cod_prod and cod != str(cod_prod):
                    continue
                descr, ncm_prod = prod.get(cod, ("", ""))
                if ncm and not ncm_prod.startswith(str(ncm)):
                    continue
                if aliq_pis is not None and _to_num(v("ALIQ_PIS")) != aliq_pis:
                    continue
                if aliq_cofins is not None and \
                        _to_num(v("ALIQ_COFINS")) != aliq_cofins:
                    continue

                vl_item = _to_num(v("VL_ITEM"))
                vl_desc = _to_num(v("VL_DESC"))
                qtd = _to_num(v("QTD"))
                vl_un = (vl_item / qtd) if qtd else 0.0
                uids.append(it.uid)
                linhas.append([
                    tp, data_br, ndoc, ser, mod,
                    v("NUM_ITEM"), cod, descr, ncm_prod,
                    v("QTD"), _fmt_val(vl_un), v("VL_ITEM"), v("VL_DESC"),
                    _fmt_val(vl_item - vl_desc),
                    v("CFOP"), v("CST_ICMS"), v("VL_BC_ICMS"), v("ALIQ_ICMS"),
                    v("VL_ICMS"), v("VL_BC_ICMS_ST"), v("ALIQ_ST"),
                    v("VL_ICMS_ST"),
                    v("CST_PIS"), v("VL_BC_PIS"), v("ALIQ_PIS"), v("VL_PIS"),
                    v("CST_COFINS"), v("VL_BC_COFINS"), v("ALIQ_COFINS"),
                    v("VL_COFINS"),
                    v("CST_IPI"), v("VL_IPI"), chave])
        return self.COLUNAS_RELATORIO, linhas, uids, self.EDIT_C170

    # -- consolidados (sem C170): NFC-e mod 65 e afins ----------------------
    COLUNAS_RELATORIO_C175 = [
        "TIPO", "NOTA_DATA", "NOTA_N", "NOTA_SERIE", "NOTA_MODELO",
        "CFOP", "VL_OPR", "VL_DESC",
        "PIS_CST", "PIS_BC", "PIS_ALIQ", "PIS_VL",
        "COFINS_CST", "COFINS_BC", "COFINS_ALIQ", "COFINS_VL",
        "COD_CTA", "INFO_COMPL", "CHAVE_ACESSO",
    ]
    EDIT_C175 = {
        "CFOP": "CFOP", "VL_OPR": "VL_OPR", "VL_DESC": "VL_DESC",
        "PIS_CST": "CST_PIS", "PIS_BC": "VL_BC_PIS", "PIS_ALIQ": "ALIQ_PIS",
        "PIS_VL": "VL_PIS", "COFINS_CST": "CST_COFINS",
        "COFINS_BC": "VL_BC_COFINS", "COFINS_ALIQ": "ALIQ_COFINS",
        "COFINS_VL": "VL_COFINS", "COD_CTA": "COD_CTA",
        "INFO_COMPL": "INFO_COMPL",
    }
    COLUNAS_RELATORIO_C190 = [
        "TIPO", "NOTA_DATA", "NOTA_N", "NOTA_SERIE", "NOTA_MODELO",
        "ICMS_CST", "CFOP", "ICMS_ALIQ", "VL_OPR", "ICMS_BC", "ICMS_VL",
        "ICMSST_BC", "ICMSST_VL", "VL_RED_BC", "VL_IPI", "COD_OBS",
        "CHAVE_ACESSO",
    ]
    EDIT_C190 = {
        "ICMS_CST": "CST_ICMS", "CFOP": "CFOP", "ICMS_ALIQ": "ALIQ_ICMS",
        "VL_OPR": "VL_OPR", "ICMS_BC": "VL_BC_ICMS", "ICMS_VL": "VL_ICMS",
        "ICMSST_BC": "VL_BC_ICMS_ST", "ICMSST_VL": "VL_ICMS_ST",
        "VL_RED_BC": "VL_RED_BC", "VL_IPI": "VL_IPI", "COD_OBS": "COD_OBS",
    }

    def _c100_filtrados(self, f):
        """Gera (c100, tp, data_br, num, serie, modelo, chave) para os C100 que
        passam nos filtros de cabeçalho (data, tipo, modelo, nº nota). Base
        comum aos relatórios de C170, C175 e C190."""
        c_oper = self._ix("C100", "IND_OPER")
        c_mod = self._ix("C100", "COD_MOD")
        c_ser = self._ix("C100", "SER")
        c_num = self._ix("C100", "NUM_DOC")
        c_chv = self._ix("C100", "CHV_NFE")
        c_dt = self._ix("C100", "DT_DOC")
        c_es = self._ix("C100", "DT_E_S")
        di = f.get("data_ini") or None
        dfim = f.get("data_fim") or None
        tipo = f.get("tipo", "T")
        modelo = f.get("modelo")
        num = f.get("num_nota")

        def dkey(s):
            s = (s or "").strip()
            return (s[4:8] + s[2:4] + s[0:2]) if len(s) == 8 else ""

        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            oper = (c100.valor(c_oper) or "").strip() if c_oper is not None else ""
            tp = "E" if oper == "0" else "S"
            if tipo != "T" and tp != tipo:
                continue
            mod = (c100.valor(c_mod) or "").strip() if c_mod is not None else ""
            if modelo and mod != str(modelo):
                continue
            ndoc = (c100.valor(c_num) or "").strip() if c_num is not None else ""
            if num and ndoc != str(num):
                continue
            dt = (c100.valor(c_dt) or "").strip() if c_dt is not None else ""
            if not dt and c_es is not None:
                dt = (c100.valor(c_es) or "").strip()
            dk = dkey(dt)
            if di and dk and dk < di:
                continue
            if dfim and dk and dk > dfim:
                continue
            chave = (c100.valor(c_chv) or "").strip() if c_chv is not None else ""
            ser = (c100.valor(c_ser) or "").strip() if c_ser is not None else ""
            data_br = ("%s/%s/%s" % (dt[0:2], dt[2:4], dt[4:8])) \
                if len(dt) == 8 else dt
            yield c100, tp, data_br, ndoc, ser, mod, chave

    def itens_relatorio_c175(self, filtros=None):
        """Relatório do C175 (PIS/COFINS consolidado por CFOP/CST/alíquota),
        típico de NFC-e (modelo 65), que não possui C170."""
        f = filtros or {}
        I = {c: self._ix("C175", c) for c in (
            "CFOP", "VL_OPR", "VL_DESC", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
            "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS",
            "COD_CTA", "INFO_COMPL")}
        cfop = f.get("cfop")
        cst_pis = {str(x) for x in (f.get("cst_pis") or [])}
        cst_cofins = {str(x) for x in (f.get("cst_cofins") or [])}
        aliq_pis = f.get("aliq_pis")
        aliq_cofins = f.get("aliq_cofins")
        linhas = []
        uids = []
        for c100, tp, data, ndoc, ser, mod, chave in self._c100_filtrados(f):
            for r in c100.filhos:
                if r.reg != "C175":
                    continue

                def v(campo, _r=r):
                    idx = I.get(campo)
                    return (_r.valor(idx) or "").strip() if idx is not None \
                        else ""

                if cfop and v("CFOP") != str(cfop):
                    continue
                if cst_pis and v("CST_PIS") not in cst_pis:
                    continue
                if cst_cofins and v("CST_COFINS") not in cst_cofins:
                    continue
                if aliq_pis is not None and _to_num(v("ALIQ_PIS")) != aliq_pis:
                    continue
                if aliq_cofins is not None and \
                        _to_num(v("ALIQ_COFINS")) != aliq_cofins:
                    continue
                linhas.append([
                    tp, data, ndoc, ser, mod,
                    v("CFOP"), v("VL_OPR"), v("VL_DESC"),
                    v("CST_PIS"), v("VL_BC_PIS"), v("ALIQ_PIS"), v("VL_PIS"),
                    v("CST_COFINS"), v("VL_BC_COFINS"), v("ALIQ_COFINS"),
                    v("VL_COFINS"), v("COD_CTA"), v("INFO_COMPL"), chave])
                uids.append(r.uid)
        return self.COLUNAS_RELATORIO_C175, linhas, uids, self.EDIT_C175

    def itens_relatorio_c190(self, filtros=None):
        """Relatório do C190 (ICMS consolidado por CST/CFOP/alíquota), usado por
        NFC-e (modelo 65) e outros documentos sem detalhamento de itens."""
        f = filtros or {}
        I = {c: self._ix("C190", c) for c in (
            "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS",
            "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC", "VL_IPI", "COD_OBS")}
        cfop = f.get("cfop")
        cst_icms = {str(x) for x in (f.get("cst_icms") or [])}
        aliq_icms = f.get("aliq_icms")
        linhas = []
        uids = []
        for c100, tp, data, ndoc, ser, mod, chave in self._c100_filtrados(f):
            for r in c100.filhos:
                if r.reg != "C190":
                    continue

                def v(campo, _r=r):
                    idx = I.get(campo)
                    return (_r.valor(idx) or "").strip() if idx is not None \
                        else ""

                if cfop and v("CFOP") != str(cfop):
                    continue
                if cst_icms and v("CST_ICMS") not in cst_icms:
                    continue
                if aliq_icms is not None and \
                        _to_num(v("ALIQ_ICMS")) != aliq_icms:
                    continue
                linhas.append([
                    tp, data, ndoc, ser, mod,
                    v("CST_ICMS"), v("CFOP"), v("ALIQ_ICMS"), v("VL_OPR"),
                    v("VL_BC_ICMS"), v("VL_ICMS"), v("VL_BC_ICMS_ST"),
                    v("VL_ICMS_ST"), v("VL_RED_BC"), v("VL_IPI"), v("COD_OBS"),
                    chave])
                uids.append(r.uid)
        return self.COLUNAS_RELATORIO_C190, linhas, uids, self.EDIT_C190

    # ----------------------------------------------- consolidação do C190
    def _ix(self, tipo, nome):
        """Índice da coluna `nome` no layout atual para o registro `tipo`."""
        cols = campos(tipo, self.layout, 40)
        return cols.index(nome) if nome in cols else None

    def consolidar_c190(self, c100):
        """
        (Apenas EFD ICMS/IPI) Recalcula os registros **C190** (analítico) de um
        documento **C100** a partir dos seus itens **C170**, agrupando por
        (CST_ICMS, CFOP, ALIQ_ICMS) e somando os valores.

        Frete, seguro e outras despesas acessórias do C100 são rateados entre
        os itens proporcionalmente ao VL_ITEM e entram no VL_OPR. Os C190
        antigos são substituídos pelos novos, posicionados logo após os itens
        (mantendo a sequência correta dentro do C100). Por fim, os totais
        (X990 e bloco 9) são reajustados.

        Retorna um dicionário-resumo, ou None se não se aplicar.
        """
        if self.layout != "ICMS" or c100.reg != "C100":
            return None
        c170 = [f for f in c100.filhos if f.reg == "C170"]
        if not c170:
            return {"grupos": 0, "removidos": 0, "criados": 0, "sem_c170": True}

        # índices dos campos do C170
        i_item = self._ix("C170", "VL_ITEM")
        i_desc = self._ix("C170", "VL_DESC")
        i_cst = self._ix("C170", "CST_ICMS")
        i_cfop = self._ix("C170", "CFOP")
        i_bc = self._ix("C170", "VL_BC_ICMS")
        i_aliq = self._ix("C170", "ALIQ_ICMS")
        i_icms = self._ix("C170", "VL_ICMS")
        i_bcst = self._ix("C170", "VL_BC_ICMS_ST")
        i_icmsst = self._ix("C170", "VL_ICMS_ST")
        i_ipi = self._ix("C170", "VL_IPI")

        # despesas acessórias do documento, rateadas entre os itens pelo valor.
        # O rateio usa DIFERENÇA DE ACUMULADOS ARREDONDADOS: o quinhão de cada
        # item é a variação do total rateado arredondado, de modo que a soma dos
        # quinhões feche EXATAMENTE com `acess` (sem sobrar/faltar centavos).
        acess = (_to_num(c100.valor(self._ix("C100", "VL_FRT")))
                 + _to_num(c100.valor(self._ix("C100", "VL_SEG")))
                 + _to_num(c100.valor(self._ix("C100", "VL_OUT_DA"))))
        soma_item = sum(_to_num(it.valor(i_item)) for it in c170) or 1.0

        grupos = {}
        valor_acum = 0.0
        rateio_acum = 0.0
        for it in c170:
            cst = it.valor(i_cst)
            cfop = it.valor(i_cfop)
            aliq = _to_num(it.valor(i_aliq))
            chave = (cst, cfop, "%.2f" % aliq)
            g = grupos.get(chave)
            if g is None:
                g = {"cst": cst, "cfop": cfop, "aliq": aliq,
                     "VL_OPR": 0.0, "VL_BC": 0.0, "VL_ICMS": 0.0,
                     "VL_BCST": 0.0, "VL_ICMSST": 0.0, "VL_IPI": 0.0}
                grupos[chave] = g
            vit = _to_num(it.valor(i_item))
            if acess:
                valor_acum += vit
                ideal = round(acess * valor_acum / soma_item, 2)
                rateio = round(ideal - rateio_acum, 2)
                rateio_acum = ideal
            else:
                rateio = 0.0
            g["VL_OPR"] += (vit - _to_num(it.valor(i_desc)) + rateio
                            + _to_num(it.valor(i_ipi))
                            + _to_num(it.valor(i_icmsst)))
            g["VL_BC"] += _to_num(it.valor(i_bc))
            g["VL_ICMS"] += _to_num(it.valor(i_icms))
            g["VL_BCST"] += _to_num(it.valor(i_bcst))
            g["VL_ICMSST"] += _to_num(it.valor(i_icmsst))
            g["VL_IPI"] += _to_num(it.valor(i_ipi))

        chaves = sorted(grupos.keys(),
                        key=lambda k: (k[0], k[1], float(k[2])))

        # remove os C190 antigos do documento
        antigos = [f for f in c100.filhos if f.reg == "C190"]
        n_rem = len(antigos)
        for a in antigos:
            self.remover_registro(a)

        # âncora: último filho cujo número de registro seja anterior ao 190
        def numreg(r):
            try:
                return int(r.reg[1:])
            except ValueError:
                return 999
        anteriores = [f for f in sorted(c100.filhos, key=lambda x: x.ordem)
                      if numreg(f) < 190]
        ancora = anteriores[-1] if anteriores else c100

        n_cri = 0
        for chave in chaves:
            g = grupos[chave]
            novo = self.novo_registro("C190", pai=c100, depois=ancora)
            novo.campos = ["C190", g["cst"], g["cfop"], _fmt_val(g["aliq"]),
                           _fmt_val(g["VL_OPR"]), _fmt_val(g["VL_BC"]),
                           _fmt_val(g["VL_ICMS"]), _fmt_val(g["VL_BCST"]),
                           _fmt_val(g["VL_ICMSST"]), _fmt_val(0.0),
                           _fmt_val(g["VL_IPI"]), ""]
            ancora = novo
            n_cri += 1

        self.atualizar_bloco9_inplace()
        return {"grupos": len(chaves), "removidos": n_rem, "criados": n_cri}

    def consolidar_c175_de_itens(self, c100, itens, atualizar_c100=True):
        """
        (Apenas EFD Contribuições) Gera os registros **C175** de um **C100** a
        partir de uma lista de itens (tipicamente vinda dos XMLs dos cupons),
        agrupando por (CFOP, CST_PIS, ALIQ_PIS, CST_COFINS, ALIQ_COFINS) e
        somando os valores de PIS/COFINS. Atualiza também VL_PIS/VL_COFINS do
        C100. Os C175 antigos são substituídos.

        `itens` é qualquer sequência de objetos com os atributos: cfop, vprod,
        vdesc, pis_cst, pis_vbc, pis_aliq, pis_vpis, cofins_cst, cofins_vbc,
        cofins_aliq, cofins_vcofins (ver xml_fiscal.ItemNFe). Por ser neutro
        quanto à origem, o método não depende de XML.
        """
        if self.layout != "CONTRIB" or c100.reg != "C100":
            return None
        if not itens:
            return {"grupos": 0, "removidos": 0, "criados": 0,
                    "sem_itens": True}

        def c100v(nome):
            i = self._ix("C100", nome)
            return _to_num(c100.valor(i)) if i is not None else 0.0
        acess = c100v("VL_FRT") + c100v("VL_SEG") + c100v("VL_OUT_DA")
        soma_prod = sum((getattr(it, "vprod", 0.0) or 0.0)
                        for it in itens) or 1.0

        def fmt_aliq(a):
            return _fmt_val(_to_num((a or "").replace(".", ","))) if a else ""

        grupos, ordem = {}, []
        tot_pis = tot_cof = 0.0
        for it in itens:
            cfop = (it.cfop or "").strip()
            cstp = (it.pis_cst or "").strip()
            cstc = (it.cofins_cst or "").strip()
            ap = _to_num((it.pis_aliq or "").replace(".", ","))
            ac = _to_num((it.cofins_aliq or "").replace(".", ","))
            chave = (cfop, cstp, "%.4f" % ap, cstc, "%.4f" % ac)
            g = grupos.get(chave)
            if g is None:
                g = {"cfop": cfop, "cstp": cstp, "cstc": cstc,
                     "aliq_pis": it.pis_aliq, "aliq_cof": it.cofins_aliq,
                     "VL_OPR": 0.0, "VL_DESC": 0.0, "VL_BC_PIS": 0.0,
                     "VL_PIS": 0.0, "VL_BC_COF": 0.0, "VL_COF": 0.0}
                grupos[chave] = g
                ordem.append(chave)
            vprod = getattr(it, "vprod", 0.0) or 0.0
            vdesc = getattr(it, "vdesc", 0.0) or 0.0
            rateio = round(acess * vprod / soma_prod, 2) if acess else 0.0
            g["VL_OPR"] += vprod - vdesc + rateio
            g["VL_DESC"] += vdesc
            g["VL_BC_PIS"] += it.pis_vbc or 0.0
            g["VL_PIS"] += it.pis_vpis or 0.0
            g["VL_BC_COF"] += it.cofins_vbc or 0.0
            g["VL_COF"] += it.cofins_vcofins or 0.0
            tot_pis += it.pis_vpis or 0.0
            tot_cof += it.cofins_vcofins or 0.0

        antigos = [f for f in c100.filhos if f.reg == "C175"]
        n_rem = len(antigos)
        for a in antigos:
            self.remover_registro(a)

        def numreg(r):
            try:
                return int(r.reg[1:])
            except ValueError:
                return 999
        ant = [f for f in sorted(c100.filhos, key=lambda x: x.ordem)
               if numreg(f) < 175]
        ancora = ant[-1] if ant else c100

        n_cri = 0
        for chave in ordem:
            g = grupos[chave]
            novo = self.novo_registro("C175", pai=c100, depois=ancora)
            novo.campos = ["C175", g["cfop"], _fmt_val(g["VL_OPR"]),
                           _fmt_val(g["VL_DESC"]), g["cstp"],
                           _fmt_val(g["VL_BC_PIS"]), fmt_aliq(g["aliq_pis"]),
                           "", "", _fmt_val(g["VL_PIS"]), g["cstc"],
                           _fmt_val(g["VL_BC_COF"]), fmt_aliq(g["aliq_cof"]),
                           "", "", _fmt_val(g["VL_COF"]), "", ""]
            ancora = novo
            n_cri += 1

        if atualizar_c100:
            ip = self._ix("C100", "VL_PIS")
            ic = self._ix("C100", "VL_COFINS")
            if ip is not None:
                c100.set_valor(ip, _fmt_val(tot_pis))
            if ic is not None:
                c100.set_valor(ic, _fmt_val(tot_cof))

        self.atualizar_bloco9_inplace()
        return {"grupos": len(ordem), "removidos": n_rem, "criados": n_cri,
                "vl_pis": tot_pis, "vl_cofins": tot_cof}

    def _registros_aliq_escopo(self, escopo):
        """Registros-alvo da troca de alíquotas conforme o escopo:
        'saidas'   → C175 + C170 de documentos de saída (IND_OPER=1);
        'entradas' → C170 de documentos de entrada (IND_OPER=0);
        'ambos'/'todos' → todos os C170 e C175 (qualquer operação)."""
        i_op = self._ix("C100", "IND_OPER")

        def oper(r):
            p = r.pai
            if p is not None and p.reg == "C100" and i_op is not None:
                return (p.valor(i_op) or "").strip()
            return ""

        c175 = [r for r in self.registros if r.reg == "C175"]
        c170 = [r for r in self.registros if r.reg == "C170"]
        alvos = []
        if escopo in ("saidas", "ambos", "todos"):
            alvos += c175
        if escopo == "saidas":
            alvos += [r for r in c170 if oper(r) == "1"]
        elif escopo == "entradas":
            alvos += [r for r in c170 if oper(r) == "0"]
        elif escopo in ("ambos", "todos"):
            alvos += c170
        return alvos

    def aliquota_predominante(self, campo, escopo="saidas"):
        """Alíquota mais comum (>0) entre os registros do escopo, p/ sugerir."""
        from collections import Counter
        c = Counter()
        for r in self._registros_aliq_escopo(escopo):
            i = self._ix(r.reg, campo)
            if i is not None:
                a = _to_num(r.valor(i))
                if a > 0:
                    c[a] += 1
        return c.most_common(1)[0][0] if c else None

    def aliquota_predominante_c175(self, campo):
        """Compatibilidade: alíquota predominante nas saídas (C175)."""
        return self.aliquota_predominante(campo, "saidas")

    def trocar_aliquotas_pis_cofins(self, aliq_pis=None, aliq_cofins=None,
                                    apenas_tributados=True, escopo="saidas",
                                    de_pis=None, de_cofins=None):
        """Substitui as alíquotas de PIS e/ou COFINS e recalcula VL_PIS /
        VL_COFINS (base × alíquota / 100), atualizando os totais dos C100.

        `escopo` define onde aplicar: 'saidas' → C175 + C170 de saída (débito);
        'entradas' → C170 de entrada (crédito); 'ambos'/'todos' → todos os C170
        e C175. `aliq_pis` e `aliq_cofins` são percentuais (ex.: 1.65); None
        mantém o tributo inalterado. Com `apenas_tributados=True`, só mexe onde
        há base ou alíquota positiva.

        `de_pis` / `de_cofins`, se informados, restringem a troca aos registros
        cuja alíquota **atual** seja exatamente aquele valor — útil para corrigir
        apenas uma alíquota preenchida errada, sem tocar nas demais.
        """
        # C170 e C175 têm os campos de PIS/COFINS em posições diferentes
        idx = {}
        for tipo in ("C170", "C175"):
            idx[tipo] = (self._ix(tipo, "VL_BC_PIS"),
                         self._ix(tipo, "ALIQ_PIS"), self._ix(tipo, "VL_PIS"),
                         self._ix(tipo, "VL_BC_COFINS"),
                         self._ix(tipo, "ALIQ_COFINS"),
                         self._ix(tipo, "VL_COFINS"))
        alvos = self._registros_aliq_escopo(escopo)
        if not alvos:
            return {"itens": 0, "c100": 0, "sem_alvo": True}

        n = 0
        c100s = set()
        for r in alvos:
            i_bcp, i_ap, i_vp, i_bcc, i_ac, i_vc = idx[r.reg]
            if i_ap is None or i_ac is None:
                continue
            mudou = False
            if aliq_pis is not None:
                bc = _to_num(r.valor(i_bcp))
                al = _to_num(r.valor(i_ap))
                ok = (not apenas_tributados) or bc > 0 or al > 0
                if de_pis is not None:
                    ok = ok and abs(al - de_pis) < 1e-9
                if ok:
                    r.set_valor(i_ap, _fmt_aliq(aliq_pis))
                    r.set_valor(i_vp, _fmt_val(round(bc * aliq_pis / 100, 2)))
                    mudou = True
            if aliq_cofins is not None:
                bc = _to_num(r.valor(i_bcc))
                al = _to_num(r.valor(i_ac))
                ok = (not apenas_tributados) or bc > 0 or al > 0
                if de_cofins is not None:
                    ok = ok and abs(al - de_cofins) < 1e-9
                if ok:
                    r.set_valor(i_ac, _fmt_aliq(aliq_cofins))
                    r.set_valor(i_vc, _fmt_val(round(bc * aliq_cofins / 100, 2)))
                    mudou = True
            if mudou:
                n += 1
                if r.pai is not None:
                    c100s.add(r.pai)

        icp = self._ix("C100", "VL_PIS")
        icc = self._ix("C100", "VL_COFINS")
        tot_pis = tot_cof = 0.0
        for c100 in c100s:
            sp = sc = 0.0
            for f in c100.filhos:
                if f.reg in ("C170", "C175"):
                    _, _, fvp, _, _, fvc = idx[f.reg]
                    if fvp is not None:
                        sp += _to_num(f.valor(fvp))
                    if fvc is not None:
                        sc += _to_num(f.valor(fvc))
            tot_pis += sp
            tot_cof += sc
            if icp is not None:
                c100.set_valor(icp, _fmt_val(sp))
            if icc is not None:
                c100.set_valor(icc, _fmt_val(sc))
        return {"itens": n, "c100": len(c100s),
                "vl_pis": tot_pis, "vl_cofins": tot_cof}

    def alterar_datas_c100(self, campo_filtro="DT_E_S", data_ini=None,
                           data_fim=None, modelos=None, tipo="T",
                           campos_alterar=("DT_E_S",), modo="especifica",
                           valor=None):
        """Altera a data de emissão (DT_DOC) e/ou de entrada/saída (DT_E_S) dos
        documentos C100 que passam no filtro.

        Filtro: intervalo [data_ini, data_fim] avaliado sobre `campo_filtro`
        ('DT_DOC' ou 'DT_E_S'); `modelos` = conjunto de COD_MOD a incluir (vazio
        = todos); `tipo` = 'T'/'E'/'S' (IND_OPER). As datas de filtro/valor são
        objetos date; no arquivo o formato é DDMMAAAA.

        Ação: `campos_alterar` lista quais datas mudar; `modo='especifica'` grava
        `valor` (date) fixo; `modo='dias'` desloca cada data em `valor` dias
        (inteiro, pode ser negativo). Retorna resumo com contagens.
        """
        from datetime import datetime, timedelta

        i_oper = self._ix("C100", "IND_OPER")
        i_mod = self._ix("C100", "COD_MOD")
        i_dtdoc = self._ix("C100", "DT_DOC")
        i_dtes = self._ix("C100", "DT_E_S")
        i_filtro = i_dtdoc if campo_filtro == "DT_DOC" else i_dtes
        alvos = []
        if "DT_DOC" in campos_alterar and i_dtdoc is not None:
            alvos.append(i_dtdoc)
        if "DT_E_S" in campos_alterar and i_dtes is not None:
            alvos.append(i_dtes)
        modelos = {str(m).strip() for m in (modelos or []) if str(m).strip()}

        def parse(s):
            s = (s or "").strip()
            try:
                return datetime.strptime(s, "%d%m%Y").date()
            except ValueError:
                return None

        n_alterados = 0
        n_no_filtro = 0
        sem_data = 0
        for r in self.registros:
            if r.reg != "C100":
                continue
            if tipo != "T":
                oper = (r.valor(i_oper) or "").strip() if i_oper is not None \
                    else ""
                if ("E" if oper == "0" else "S") != tipo:
                    continue
            if modelos:
                mod = (r.valor(i_mod) or "").strip() if i_mod is not None else ""
                if mod not in modelos:
                    continue
            dref = parse(r.valor(i_filtro)) if i_filtro is not None else None
            if dref is None:
                sem_data += 1
                continue
            if data_ini and dref < data_ini:
                continue
            if data_fim and dref > data_fim:
                continue
            n_no_filtro += 1

            mudou = False
            for idx in alvos:
                if modo == "especifica":
                    nova = valor
                else:  # deslocamento em dias
                    atual = parse(r.valor(idx))
                    if atual is None:
                        continue
                    nova = atual + timedelta(days=int(valor))
                if nova is not None:
                    r.set_valor(idx, nova.strftime("%d%m%Y"))
                    mudou = True
            if mudou:
                n_alterados += 1
        return {"c100": n_alterados, "no_filtro": n_no_filtro,
                "sem_data": sem_data}

    # --------------------------------------------- totais (in-place, p/ tela)
    def recalcular_bloco_m(self):
        """
        (Apenas EFD Contribuições) Recalcula a APURAÇÃO de PIS (M200/M210) e
        COFINS (M600/M610) a partir das receitas tributadas de saída
        (C175 e C170), agrupando por alíquota.

        Regra validada nos arquivos reais:
          VL_REC_BRT  = Σ VL_OPR do grupo;
          VL_BC_CONT  = Σ VL_BC do grupo;
          VL_CONT_APUR = VL_BC_CONT × alíquota.

        O REGIME (registro 0110, COD_INC_TRIB) é respeitado:
          * cumulativo (2)  -> a contribuição vai para os campos CUM e os
            registros de crédito M100/M105/M500/M505 NÃO são usados nem criados;
          * não-cumulativo (1) ou ambos (3) -> contribuição nos campos NC; os
            créditos já existentes (M100/M500) são preservados e apenas
            descontados no M200/M600 (este método não recalcula créditos).

        Retorna um resumo, ou None se não se aplicar.
        """
        if self.layout != "CONTRIB":
            return None
        r0110 = [r for r in self.registros if r.reg == "0110"]
        cod_inc = "1"
        if r0110:
            i = self._ix("0110", "COD_INC_TRIB")
            cod_inc = (r0110[0].valor(i) or "1").strip()
        cumulativo = (cod_inc == "2")
        cod_cont = "51" if cumulativo else "01"

        i_op = self._ix("C100", "IND_OPER")
        saidas = [r for r in self.registros
                  if r.reg == "C100" and (r.valor(i_op) or "").strip() == "1"]

        def coletar(tributo):
            """Agrupa (alíquota -> {rec, bc, aliq_str}) da receita tributada."""
            if tributo == "PIS":
                c175 = (4, 5, 2, 6)      # cst, bc, opr, aliq
                c170 = (24, 25, 6, 26)
            else:
                c175 = (10, 11, 2, 12)
                c170 = (30, 31, 6, 32)
            grupos = {}
            for c100 in saidas:
                for f in c100.filhos:
                    if f.reg == "C175":
                        i_cst, i_bc, i_opr, i_al = c175
                    elif f.reg == "C170":
                        i_cst, i_bc, i_opr, i_al = c170
                    else:
                        continue
                    bc = _to_num(f.valor(i_bc))
                    al = _to_num(f.valor(i_al))
                    if bc <= 0 or al <= 0:
                        continue
                    k = "%.4f" % al
                    g = grupos.setdefault(k, {"aliq": f.valor(i_al),
                                             "rec": 0.0, "bc": 0.0})
                    g["rec"] += _to_num(f.valor(i_opr))
                    g["bc"] += bc
            return grupos

        resumo = {}
        for tributo, reg_cons, reg_det in (("PIS", "M200", "M210"),
                                           ("COFINS", "M600", "M610")):
            grupos = coletar(tributo)
            cons = next((r for r in self.registros if r.reg == reg_cons), None)
            if cons is None:
                resumo[tributo] = "sem %s" % reg_cons
                continue

            # remove os M210/M610 atuais e recria por alíquota, PRESERVANDO a
            # ordem do leiaute (M200 -> M205 -> M210 -> ...). A âncora correta é
            # o último M205/M605 (que precede os M210); se não houver, o registro
            # anterior ao 1º M210 atual; por fim, o próprio M200/M600. Isso
            # conserta inclusive arquivos onde o M210 ficou à frente do M205.
            antigos = [f for f in cons.filhos if f.reg == reg_det]
            reg_rec = "M205" if reg_det == "M210" else "M605"
            recs = [f for f in cons.filhos if f.reg == reg_rec]
            if recs:
                ancora = max(recs, key=lambda x: x.ordem)
            elif antigos:
                filhos_ord = sorted(cons.filhos, key=lambda x: x.ordem)
                pos = filhos_ord.index(min(antigos, key=lambda x: x.ordem))
                ancora = filhos_ord[pos - 1] if pos > 0 else cons
            else:
                ancora = cons
            for a in antigos:
                self.remover_registro(a)

            total_apur = 0.0
            for k in sorted(grupos.keys(), key=float):
                g = grupos[k]
                al = float(k)
                apur = round(g["bc"] * al / 100.0, 2)
                total_apur += apur
                novo = self.novo_registro(reg_det, pai=cons, depois=ancora)
                # campos de M210/M610 (mesma ordem). Zeros como "0" (formato do
                # arquivo original); QUANT_BC e ALIQ_QUANT ficam "0"/"".
                novo.campos = [reg_det, cod_cont, _fmt_val(g["rec"]),
                               _fmt_val(g["bc"]), "0", "0",
                               _fmt_val(g["bc"]), g["aliq"], "0", "",
                               _fmt_val(apur), "0", "0",
                               "0", "0", _fmt_val(apur)]
                ancora = novo

            # atualiza a consolidação M200/M600
            cred = _to_num(cons.valor(2))           # VL_TOT_CRED_DESC (mantido)
            ret_nc = _to_num(cons.valor(5))
            ded_nc = _to_num(cons.valor(6))
            ret_cum = _to_num(cons.valor(9))
            ded_cum = _to_num(cons.valor(10))
            if cumulativo:
                nc_per = 0.0
                cred = 0.0
                cum_per = total_apur
            else:
                nc_per = total_apur
                cum_per = 0.0
            nc_dev = max(nc_per - cred, 0.0)
            nc_rec = max(nc_dev - ret_nc - ded_nc, 0.0)
            cum_rec = max(cum_per - ret_cum - ded_cum, 0.0)
            def z(v):
                return _fmt_val(v) if abs(v) > 1e-9 else "0"
            cons.set_valor(1, z(nc_per))
            cons.set_valor(2, z(cred))
            cons.set_valor(4, z(nc_dev))
            cons.set_valor(7, z(nc_rec))
            cons.set_valor(8, z(cum_per))
            cons.set_valor(11, z(cum_rec))
            cons.set_valor(12, z(nc_rec + cum_rec))
            resumo[tributo] = {"grupos": len(grupos),
                               "apurado": round(total_apur, 2),
                               "a_recolher": round(nc_rec + cum_rec, 2)}

        self.atualizar_bloco9_inplace()
        resumo["regime"] = ("cumulativo" if cumulativo
                            else "não-cumulativo" if cod_inc == "1"
                            else "ambos")
        return resumo

    def atualizar_bloco9_inplace(self):
        """
        Atualiza, sem alterar a estrutura, os registros de contagem para que a
        interface reflita a realidade atual:
          * X990  -> nº de linhas do bloco (inclui o próprio X990);
          * 9900  -> nº de registros de cada tipo (ex.: 9900|C190|<qtd>);
          * 9990  -> nº de linhas do bloco 9;
          * 9999  -> total de linhas do arquivo.
        A gravação (gerar_texto) reconstrói o bloco 9 do zero e continua sendo
        a fonte definitiva; este método serve para exibição imediata.
        """
        base = [r for r in self.registros if r.bloco != "9"]
        cont_bloco = {}
        for r in base:
            cont_bloco[r.bloco] = cont_bloco.get(r.bloco, 0) + 1
        for r in self.registros:
            if len(r.reg) == 4 and r.reg.endswith("990") and r.reg != "9990":
                r.set_valor(1, str(cont_bloco.get(r.reg[0], 0)))

        cont_tipo = {}
        for r in self.registros:
            cont_tipo[r.reg] = cont_tipo.get(r.reg, 0) + 1
        for r in self.registros:
            if r.reg == "9900":
                t = r.valor(1)
                if t in cont_tipo:
                    r.set_valor(2, str(cont_tipo[t]))

        n_bloco9 = sum(1 for r in self.registros if r.bloco == "9")
        total = len(self.registros)
        for r in self.registros:
            if r.reg == "9990":
                r.set_valor(1, str(n_bloco9))
            elif r.reg == "9999":
                r.set_valor(1, str(total))

    def colunas(self, tipo, registros):
        """Nomes de coluna para um conjunto de registros do mesmo tipo."""
        max_campos = max((len(r.campos) for r in registros), default=1)
        return campos(tipo, self.layout, max_campos)

    # ------------------------------------------------------------- edição CRUD
    def novo_registro(self, tipo, pai=None, depois=None):
        """
        Cria um novo registro vazio do `tipo` informado.
        `pai`    -> Registro pai (None = raiz)
        `depois` -> Registro após o qual inserir (controla a ordem do arquivo)
        """
        partes = ["", tipo, ""]   # vira campos = [tipo]
        r = Registro(partes, self.layout, 0)
        r.campos = [tipo]
        r.pai = pai
        # ordem de inserção
        if depois is not None:
            r.ordem = depois.ordem + 0.5
        elif pai is not None:
            r.ordem = pai.ordem + 0.5
        else:
            r.ordem = (self.registros[-1].ordem + 1) if self.registros else 0

        if pai is not None:
            pai.filhos.append(r)
            pai.filhos.sort(key=lambda x: x.ordem)
        else:
            self.raizes.append(r)
            self.raizes.sort(key=lambda x: x.ordem)
        self.registros.append(r)
        self._reordenar()
        if tipo == "0200":
            self._cad_itens = None
        return r

    def remover_registro(self, r):
        """Remove o registro e toda a sua subárvore."""
        def coletar(x):
            ids = {x.uid}
            for f in x.filhos:
                ids |= coletar(f)
            return ids
        remover = coletar(r)
        if r.pai is not None:
            r.pai.filhos = [c for c in r.pai.filhos if c.uid != r.uid]
        else:
            self.raizes = [c for c in self.raizes if c.uid != r.uid]
        self.registros = [x for x in self.registros if x.uid not in remover]
        self._cad_itens = None

    def _reordenar(self):
        """Recalcula 'ordem' inteira percorrendo a árvore em profundidade."""
        contador = itertools.count(0)

        def visitar(r):
            r.ordem = next(contador)
            for f in sorted(r.filhos, key=lambda x: x.ordem):
                visitar(f)

        for raiz in sorted(self.raizes, key=lambda x: x.ordem):
            visitar(raiz)
        self.registros.sort(key=lambda x: x.ordem)

    # ------------------------------------------------------------------- save
    def _linhas_em_ordem(self):
        """Devolve registros na ordem da árvore (profundidade)."""
        out = []

        def visitar(r):
            out.append(r)
            for f in sorted(r.filhos, key=lambda x: x.ordem):
                visitar(f)

        for raiz in sorted(self.raizes, key=lambda x: x.ordem):
            visitar(raiz)
        return out

    def recalcular_totais(self):
        """
        Recalcula os registros de totalização:
          * X990  -> quantidade de linhas do bloco X (inclui o próprio X990)
          * 9900  -> um por tipo de registro, com a contagem
          * 9990  -> linhas do bloco 9
          * 9999  -> total de linhas do arquivo
        Atualiza valores in-place quando os registros existem.
        """
        ordenados = self._linhas_em_ordem()

        # contagem por tipo de registro
        cont_tipo = {}
        for r in ordenados:
            cont_tipo[r.reg] = cont_tipo.get(r.reg, 0) + 1

        # contagem por bloco
        cont_bloco = {}
        for r in ordenados:
            cont_bloco[r.bloco] = cont_bloco.get(r.bloco, 0) + 1

        # atualiza X990 (campo 2 = qtd de linhas do bloco)
        for r in ordenados:
            if r.reg.endswith("990") and len(r.reg) == 4 and r.reg != "9990":
                bloco = r.reg[0]
                r.set_valor(1, str(cont_bloco.get(bloco, 0)))

        # 9900: precisa existir um por tipo. Recriaremos no momento de gerar
        # o texto (mais simples e seguro). Aqui só garantimos 9990/9999.
        if "9990" in cont_tipo:
            for r in ordenados:
                if r.reg == "9990":
                    # bloco 9 inclui 9001 + (todos os 9900) + 9990
                    qtd9 = 2 + len(cont_tipo)  # 9001 + 9900s + 9990 ; 9999 é bloco 9? não
                    # cont_bloco['9'] já reflete os 9900 atuais; recalculamos:
                    r.set_valor(1, str(self._qtd_bloco9(cont_tipo)))
        return cont_tipo

    def _qtd_bloco9(self, cont_tipo):
        # 9001 (1) + um 9900 por tipo + 9990 (1)
        return 1 + len(cont_tipo) + 1

    def gerar_texto(self):
        """
        Gera o conteúdo textual completo do SPED, recriando o bloco 9
        (9001, 9900 por tipo, 9990, 9999) de forma consistente.
        """
        # registros que NÃO pertencem ao bloco 9 (serão regravados como estão)
        base = [r for r in self._linhas_em_ordem() if r.bloco != "9"]

        # recalcula X990 dos demais blocos
        cont_bloco = {}
        for r in base:
            cont_bloco[r.bloco] = cont_bloco.get(r.bloco, 0) + 1
        for r in base:
            if r.reg.endswith("990") and len(r.reg) == 4:
                r.set_valor(1, str(cont_bloco.get(r.bloco, 0)))

        linhas = [r.linha_sped() for r in base]

        # ---- monta bloco 9 ----
        # conta tipos considerando o próprio bloco 9
        cont_tipo = {}
        for r in base:
            cont_tipo[r.reg] = cont_tipo.get(r.reg, 0) + 1
        # tipos do bloco 9 que serão criados:
        cont_tipo["9001"] = cont_tipo.get("9001", 0) + 1
        cont_tipo["9990"] = cont_tipo.get("9990", 0) + 1
        cont_tipo["9999"] = cont_tipo.get("9999", 0) + 1
        # haverá um 9900 por tipo distinto -> inclusive o 9900
        # (o 9900 conta a si próprio)
        n_tipos_sem_9900 = len(cont_tipo)
        cont_tipo["9900"] = n_tipos_sem_9900 + 1  # +1 por causa do próprio 9900

        # ordena tipos para saída estável
        tipos_ordenados = sorted(cont_tipo.keys())

        linhas.append("|9001|0|")
        for t in tipos_ordenados:
            linhas.append("|9900|%s|%d|" % (t, cont_tipo[t]))
        # qtd de linhas do bloco 9 = 9001 + (n 9900) + 9990 + 9999
        # (esta escrituração conta o 9999 dentro do bloco 9)
        qtd_bloco9 = 1 + len(tipos_ordenados) + 1 + 1
        linhas.append("|9990|%d|" % qtd_bloco9)
        total = len(linhas) + 1  # +1 do próprio 9999
        linhas.append("|9999|%d|" % total)

        return "\r\n".join(linhas) + "\r\n"

    def salvar(self, caminho=None):
        caminho = caminho or self.caminho
        texto = self.gerar_texto()
        with open(caminho, "w", encoding=self.encoding, newline="") as f:
            f.write(texto)
        self.caminho = caminho
        return caminho

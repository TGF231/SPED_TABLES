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

        # despesas acessórias do documento (rateadas pelo valor do item)
        acess = (_to_num(c100.valor(self._ix("C100", "VL_FRT")))
                 + _to_num(c100.valor(self._ix("C100", "VL_SEG")))
                 + _to_num(c100.valor(self._ix("C100", "VL_OUT_DA"))))
        soma_item = sum(_to_num(it.valor(i_item)) for it in c170) or 1.0

        grupos = {}
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
            rateio = round(acess * vit / soma_item, 2) if acess else 0.0
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

    def aliquota_predominante_c175(self, campo):
        """Alíquota mais comum entre os C175 tributados (para sugerir na UI)."""
        from collections import Counter
        i = self._ix("C175", campo)
        if i is None:
            return None
        c = Counter()
        for r in self.registros:
            if r.reg == "C175":
                a = _to_num(r.valor(i))
                if a > 0:
                    c[a] += 1
        return c.most_common(1)[0][0] if c else None

    def trocar_aliquotas_pis_cofins(self, aliq_pis=None, aliq_cofins=None,
                                    apenas_tributados=True):
        """Substitui as alíquotas de PIS e/ou COFINS nos registros C175 e
        recalcula VL_PIS / VL_COFINS (base × alíquota / 100). Atualiza os
        totais VL_PIS / VL_COFINS dos C100 afetados.

        `aliq_pis` e `aliq_cofins` são percentuais (ex.: 1.65); None mantém o
        tributo inalterado. Com `apenas_tributados=True`, só mexe nos C175 que
        já têm base ou alíquota positiva (preserva CST não tributados).
        """
        i_bcp = self._ix("C175", "VL_BC_PIS")
        i_ap = self._ix("C175", "ALIQ_PIS")
        i_vp = self._ix("C175", "VL_PIS")
        i_bcc = self._ix("C175", "VL_BC_COFINS")
        i_ac = self._ix("C175", "ALIQ_COFINS")
        i_vc = self._ix("C175", "VL_COFINS")
        if i_ap is None or i_ac is None:
            return {"c175": 0, "c100": 0, "sem_c175": True}

        n175 = 0
        c100s = set()
        for r in self.registros:
            if r.reg != "C175":
                continue
            mudou = False
            if aliq_pis is not None:
                bc = _to_num(r.valor(i_bcp))
                al = _to_num(r.valor(i_ap))
                if (not apenas_tributados) or bc > 0 or al > 0:
                    r.set_valor(i_ap, _fmt_aliq(aliq_pis))
                    r.set_valor(i_vp, _fmt_val(round(bc * aliq_pis / 100, 2)))
                    mudou = True
            if aliq_cofins is not None:
                bc = _to_num(r.valor(i_bcc))
                al = _to_num(r.valor(i_ac))
                if (not apenas_tributados) or bc > 0 or al > 0:
                    r.set_valor(i_ac, _fmt_aliq(aliq_cofins))
                    r.set_valor(i_vc, _fmt_val(round(bc * aliq_cofins / 100, 2)))
                    mudou = True
            if mudou:
                n175 += 1
                if r.pai is not None:
                    c100s.add(r.pai)

        icp = self._ix("C100", "VL_PIS")
        icc = self._ix("C100", "VL_COFINS")
        tot_pis = tot_cof = 0.0
        for c100 in c100s:
            sp = sum(_to_num(f.valor(i_vp))
                     for f in c100.filhos if f.reg == "C175")
            sc = sum(_to_num(f.valor(i_vc))
                     for f in c100.filhos if f.reg == "C175")
            tot_pis += sp
            tot_cof += sc
            if icp is not None:
                c100.set_valor(icp, _fmt_val(sp))
            if icc is not None:
                c100.set_valor(icc, _fmt_val(sc))
        return {"c175": n175, "c100": len(c100s),
                "vl_pis": tot_pis, "vl_cofins": tot_cof}

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

            # remove os M210/M610 atuais e recria por alíquota
            antigos = [f for f in cons.filhos if f.reg == reg_det]
            for a in antigos:
                self.remover_registro(a)

            total_apur = 0.0
            ancora = cons
            for k in sorted(grupos.keys(), key=float):
                g = grupos[k]
                al = float(k)
                apur = round(g["bc"] * al / 100.0, 2)
                total_apur += apur
                novo = self.novo_registro(reg_det, pai=cons, depois=ancora)
                # campos comuns a M210 e M610 (mesma ordem)
                novo.campos = [reg_det, cod_cont, _fmt_val(g["rec"]),
                               _fmt_val(g["bc"]), _fmt_val(0.0), _fmt_val(0.0),
                               _fmt_val(g["bc"]), g["aliq"], _fmt_val(0.0), "",
                               _fmt_val(apur), _fmt_val(0.0), _fmt_val(0.0),
                               _fmt_val(0.0), _fmt_val(0.0), _fmt_val(apur)]
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
            cons.set_valor(1, _fmt_val(nc_per))
            cons.set_valor(2, _fmt_val(cred))
            cons.set_valor(4, _fmt_val(nc_dev))
            cons.set_valor(7, _fmt_val(nc_rec))
            cons.set_valor(8, _fmt_val(cum_per))
            cons.set_valor(11, _fmt_val(cum_rec))
            cons.set_valor(12, _fmt_val(nc_rec + cum_rec))
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

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

import contextlib
import itertools
import os
import re
from sped_tables.dominio import referencias
from sped_tables.dominio.sped_layouts import (nivel, campos, detectar_layout,
                          num_campos_esperado)

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


def so_digitos(texto):
    """Só os dígitos (CNPJ, NCM, CFOP, data). `None` vira `""`; número vindo
    de planilha é aceito. Havia quatro cópias desta função, duas por regex e
    duas por `isdigit`."""
    return "".join(c for c in str(texto or "") if c.isdigit())


def data_aaaammdd(ddmmaaaa):
    """DDMMAAAA -> AAAAMMDD, para comparar data como texto; "" quando não é
    data (8 dígitos, com dia e mês possíveis). Separadores são ignorados.
    Havia seis cópias, uma delas estrita e as outras não — e duas regras
    discordavam sobre o mesmo DT_E_S malformado."""
    d = so_digitos(ddmmaaaa)
    if len(d) != 8 or not (1 <= int(d[2:4]) <= 12 and 1 <= int(d[:2]) <= 31):
        return ""
    return d[4:] + d[2:4] + d[:2]


def _fmt_val(v):
    """Formata um número no padrão SPED (2 casas, vírgula decimal)."""
    return ("%.2f" % round(v, 2)).replace(".", ",")


def _fmt_aliq(a):
    """Formata uma alíquota no padrão SPED (vírgula, sem zeros à direita)."""
    s = ("%.4f" % round(float(a), 4)).rstrip("0").rstrip(".")
    return (s or "0").replace(".", ",")


def _set_str(v):
    """Normaliza um filtro em conjunto de strings. Aceita lista/tupla, valor
    único ou None. Devolve None (= sem filtro) para vazio."""
    if v is None:
        return None
    itens = v if isinstance(v, (list, tuple, set)) else [v]
    s = {str(x).strip() for x in itens if str(x).strip()}
    return s or None


def _set_float(v):
    """Normaliza um filtro numérico em conjunto de floats (ou None)."""
    if v is None:
        return None
    itens = v if isinstance(v, (list, tuple, set)) else [v]
    out = set()
    for x in itens:
        try:
            out.add(round(float(x), 4))
        except (TypeError, ValueError):
            pass
    return out or None


def _casa_float(valor, conjunto):
    """True se `valor` casa com algum do conjunto (tolerância p/ arredondamento);
    True também quando não há filtro (conjunto None)."""
    if conjunto is None:
        return True
    return any(abs(valor - c) < 1e-6 for c in conjunto)


def _fmt_aliq_pct(s):
    """Formata no padrão SPED uma alíquota vinda do XML (aceita '1.65' ou
    '1,65'); '' para vazio."""
    if not s:
        return ""
    try:
        return _fmt_aliq(float(str(s).replace(",", ".")))
    except ValueError:
        return ""


def _fmt_qtd(v):
    """Formata quantidade no padrão SPED (vírgula decimal, sem zeros à direita)."""
    try:
        s = ("%.5f" % float(v)).rstrip("0").rstrip(".")
        return (s or "0").replace(".", ",")
    except (TypeError, ValueError):
        return ""


def _to_num_planilha(v):
    """Número vindo de planilha: a célula pode chegar como número nativo do
    openpyxl ou como texto no padrão brasileiro."""
    if isinstance(v, (int, float)):
        return float(v)
    return _to_num(v)


# Texto que ERP e planilha escrevem no lugar de "campo vazio" ao exportar de
# um banco. Nenhum deles é conteúdo válido de campo do SPED — o PVA acusa
# "Conteúdo de Campo inválido". Fora da lista ficam de propósito `-` e `N/A`,
# que podem ser descrição legítima de produto.
VALORES_NULOS = frozenset((
    "NULL", "(NULL)", "NONE", "NAN", "NIL", "UNDEFINED",
    "#N/A", "#N/D", "#VALOR!", "#VALUE!", "#REF!", "#DIV/0!"))


def _texto_planilha(v):
    """Texto de uma célula, já sem o 'vazio' que o ERP escreveu por extenso."""
    s = "" if v is None else str(v).strip()
    return "" if s.upper() in VALORES_NULOS else s


# CST de PIS/COFINS que apropriam crédito na entrada (vinculado a receita,
# presumido…). O mesmo conjunto de `rotinas.CST_ENTRADA_COM_CREDITO`.
CST_CREDITO = {"%02d" % n for n in list(range(50, 57)) + list(range(60, 67))}

# Tabela oficial do campo TIPO_ITEM do 0200 (EFD ICMS/IPI). Serve para não
# deixar a planilha plantar lixo no cadastro: num arquivo real, 10.312 itens
# tinham "N", que não existe na tabela.
TIPOS_ITEM_0200 = frozenset(("00", "01", "02", "03", "04", "05", "06", "07",
                             "08", "09", "10", "99"))

# Campos do 0200 que a planilha de inventário alimenta: (chave, campo).
CAMPOS_0200 = (("descr_item", "DESCR_ITEM"), ("unid", "UNID_INV"),
               ("tipo_item", "TIPO_ITEM"), ("cod_barra", "COD_BARRA"),
               ("cod_ncm", "COD_NCM"), ("ex_ipi", "EX_IPI"),
               ("cod_gen", "COD_GEN"), ("aliq_icms", "ALIQ_ICMS"),
               ("cest", "CEST"))


def _valor_0200(chave, ln):
    """Valor da planilha para um campo do 0200, já normalizado: códigos de
    tamanho fixo recuperam o zero à esquerda e a alíquota sai no formato do
    SPED. Criar e atualizar passam por aqui — senão o item novo e o item
    corrigido sairiam com NCM de tamanhos diferentes."""
    v = _texto_planilha(ln.get(chave))
    # célula numérica vazia chega como 0, e `0` não é NCM, CEST, gênero nem
    # código de barras — é o "sem valor" do ERP outra vez. Alíquota fica de
    # fora: ali o zero é alíquota zero, valor legítimo.
    if (chave in ("cod_ncm", "cest", "cod_gen", "cod_barra", "ex_ipi")
            and v.isdigit() and not v.strip("0")):
        return ""
    if chave == "cod_ncm":
        return _zero_a_esquerda(v, 8)
    if chave == "cest":
        return _zero_a_esquerda(v, 7)
    # códigos de dois dígitos digitados como número: a célula com "00" vira o
    # número 0 e chega como "0", que o PVA não aceita. Tabela só tem códigos
    # de dois dígitos, então um dígito só pode ser o zero à esquerda perdido.
    if chave in ("tipo_item", "cod_gen") and v.isdigit() and len(v) == 1:
        return v.zfill(2)
    if chave == "cod_barra":
        return _gtin_corrigido(v)
    if chave == "aliq_icms" and v:
        # a prévia mostra o valor como veio; quem grava recusa antes
        # (`importar_inventario_h010` confere a coluna)
        try:
            return _fmt_aliq(num_planilha_estrito(ln.get(chave)))
        except ValueError:
            return v
    return v


def _zero_a_esquerda(valor, tamanho):
    """Repõe o zero que a planilha comeu ao tratar o código como número:
    o NCM `04012010` volta da célula como `4012010`.

    Só age quando falta **exatamente um** dígito e o conteúdo é todo numérico —
    nem NCM nem CEST começam com `00` (não existe capítulo 00 nem segmento 00),
    então um único zero é tudo o que pode ter se perdido. Qualquer outro
    comprimento é dado ruim de origem e fica como está, para não inventar.
    """
    v = str(valor or "").strip()
    if v.isdigit() and len(v) == tamanho - 1:
        return v.zfill(tamanho)
    return v


def _gtin_valido(v):
    """Confere o dígito verificador de um GTIN-8/12/13/14."""
    if not v.isdigit() or len(v) not in (8, 12, 13, 14):
        return False
    d = [int(c) for c in v]
    corpo = d[:-1][::-1]
    soma = sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(corpo))
    return (10 - soma % 10) % 10 == d[-1]


def _gtin_corrigido(valor):
    """Mesmo problema do NCM, agora no código de barras — mas aqui o
    comprimento não basta para decidir, porque 8, 12, 13 e 14 são todos
    válidos. Só repõe o zero quando o **dígito verificador** confirma o
    palpite; caso contrário devolve o valor intocado."""
    v = str(valor or "").strip()
    if not v.isdigit() or len(v) in (8, 12, 13, 14):
        return v
    alvo = {7: 8, 11: 12}.get(len(v))
    if alvo:
        tentativa = v.zfill(alvo)
        if _gtin_valido(tentativa):
            return tentativa
    return v


class _ItemC170View:
    """Expõe um registro C170 com a interface de "item" (atributos vprod, vdesc,
    cfop e pis_*/cofins_*) esperada por `consolidar_c175_de_itens`, permitindo
    reconsolidar o C175 a partir dos C170 fictícios já corrigidos."""

    def __init__(self, doc, reg):
        def g(campo):
            i = doc._ix("C170", campo)
            return (reg.valor(i) or "").strip() if i is not None else ""
        self.cfop = g("CFOP")
        self.vprod = _to_num(g("VL_ITEM"))
        self.vdesc = _to_num(g("VL_DESC"))
        self.pis_cst = g("CST_PIS")
        self.pis_vbc = _to_num(g("VL_BC_PIS"))
        self.pis_aliq = g("ALIQ_PIS")
        self.pis_vpis = _to_num(g("VL_PIS"))
        self.cofins_cst = g("CST_COFINS")
        self.cofins_vbc = _to_num(g("VL_BC_COFINS"))
        self.cofins_aliq = g("ALIQ_COFINS")
        self.cofins_vcofins = _to_num(g("VL_COFINS"))



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
        """Conteúdo do campo; `""` fora da linha **ou com índice None**.

        `_ix` devolve None quando o leiaute não tem o campo, e o
        `0 <= None` levantava `TypeError` — num slot do Qt, isso derruba o
        programa. Campo que não existe se lê como vazio.
        """
        if idx is None:
            return ""
        return self.campos[idx] if 0 <= idx < len(self.campos) else ""

    def set_valor(self, idx, v):
        """Grava o campo, alargando a linha se preciso. Índice None (campo
        fora do leiaute) não grava nada e devolve False."""
        if idx is None:
            return False
        while len(self.campos) <= idx:
            self.campos.append("")
        self.campos[idx] = v
        return True

    def linha_sped(self):
        """Reconstrói a linha no formato |c1|c2|...|"""
        return "|" + "|".join(self.campos) + "|"

    def __repr__(self):
        return "<Reg %s uid=%d nivel=%d filhos=%d>" % (
            self.reg, self.uid, self.nivel, len(self.filhos))


# Número no formato do SPED: vírgula decimal, sem separador de milhar. É a
# mesma regra da validação de leiaute (`validacao` importa daqui), para que o
# que ela acusa seja exatamente o que os cálculos recusam.
RE_NUM_SPED = re.compile(r"^-?\d{1,18}(,\d{1,8})?$")
PREFIXOS_NUMERICOS = ("VL_", "ALIQ_", "QTD", "PERC_", "VL")


class EntradaInvalida(ValueError):
    """Dado que não é o que o campo exige, achado **antes** de qualquer
    alteração. Quem grava recusa com uma destas em vez de ler lixo como
    zero; a interface mostra a mensagem (`comum.calcular`)."""


# Número numa célula de planilha, como texto: brasileiro (1.234,56 / 12,5)
# ou com ponto decimal (12.5). Número nativo do Excel dispensa a regra.
RE_NUM_PLANILHA = re.compile(
    r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$|^-?\d+\.\d+$")


def num_planilha_estrito(v):
    """Número de uma célula de planilha, ou `ValueError`. Célula vazia é
    zero; `abc`, `1.2.3` e `NULL` **não** são — `_to_num_planilha` os lia
    como zero, e o item entrava no inventário com quantidade zerada."""
    if v is None or isinstance(v, bool):
        if v is None:
            return 0.0
        raise ValueError(v)
    if isinstance(v, (int, float)):
        if v != v:                                  # NaN
            raise ValueError(v)
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    if not RE_NUM_PLANILHA.match(s):
        raise ValueError(v)
    return _to_num(s) if "," in s else float(s)


class CelulasInvalidas(EntradaInvalida):
    """Células numéricas da planilha que não são número.
    `celulas` = `[(linha, coluna, valor)]`."""

    def __init__(self, ruins):
        self.celulas = list(ruins)
        amostra = "\n".join("linha %s, %s = %r" % c for c in self.celulas[:5])
        mais = len(self.celulas) - 5
        super().__init__(
            "A planilha não foi importada: %d célula(s) numéricas com valor "
            "que não é número — seriam lidas como zero, e o item entraria "
            "no inventário com quantidade ou valor zerado.\n%s%s\n\nCorrija "
            "a planilha e importe de novo."
            % (len(self.celulas), amostra,
               "\n… e mais %d." % mais if mais > 0 else ""))


class CamposInvalidos(EntradaInvalida):
    """Um cálculo que grava encontrou campo numérico que não é número do
    SPED. `campos` = `[(registro, nome_do_campo, valor)]`.

    O `_to_num` lê lixo como zero — `NULL` e `12a` viram 0,0 —, e um
    recálculo que gravasse com isso transformaria um erro detectável num
    total plausível e errado. Por isso quem grava confere antes e recusa,
    sem ter mexido em nada."""

    def __init__(self, ruins):
        self.campos = list(ruins)
        amostra = "\n".join(
            "%s %s = %r (linha %d)" % (r.reg, nome, v, r.ordem + 1)
            for r, nome, v in self.campos[:5])
        mais = len(self.campos) - 5
        super().__init__(
            "O cálculo não foi feito: %d campo(s) numéricos com valor que "
            "não é número no formato do SPED — seriam lidos como zero e o "
            "resultado sairia errado sem aviso.\n%s%s\n\nCorrija pelo "
            "Diagnóstico (Corrigir campos pelo leiaute) e repita."
            % (len(self.campos), amostra,
               "\n… e mais %d." % mais if mais > 0 else ""))


# espaço, tab e CR no fim da linha não contam para o pipe final
_BRANCOS_FIM = " \t\r"


class LinhasInvalidas(ValueError):
    """O arquivo lido tinha linhas fora do formato SPED; gravá-lo as
    perderia. `linhas` = `[(nº da linha, texto)]`."""

    def __init__(self, linhas):
        self.linhas = list(linhas)
        amostra = "\n".join("linha %d: %s" % (n, (t or "")[:80])
                            for n, t in self.linhas[:5])
        mais = len(self.linhas) - 5
        super().__init__(
            "O arquivo tem %d linha(s) fora do formato SPED (sem o | "
            "inicial), que não podem ser gravadas:\n%s%s"
            % (len(self.linhas), amostra,
               "\n… e mais %d." % mais if mais > 0 else ""))


class SpedDocument:
    """Documento SPED completo: lista ordenada + floresta hierárquica."""

    def __init__(self):
        self.layout = "ICMS"
        self.registros = []      # todos, na ordem do arquivo
        self.raizes = []         # registros sem pai (topo de cada bloco)
        self.encoding = "latin-1"      # sempre, na gravação
        self.encoding_lido = "latin-1"  # o que o arquivo de origem usava
        self.caminho = None
        self._cad_itens = None   # cache COD_ITEM -> DESCR_ITEM (registros 0200)
        self._cad_part = None    # cache COD_PART -> dados do 0150
        # o que a leitura não conseguiu ler como registro — nunca descartado
        # em silêncio (ver `_montar`)
        self.linhas_invalidas = []   # [(nº da linha, texto)] sem o | inicial
        self.sem_pipe_final = []     # [(nº da linha, REG)]
        self._lote = None            # ver `lote()`

    # ------------------------------------------------------------------ load
    @classmethod
    def carregar(cls, caminho):
        doc = cls()
        doc.caminho = caminho
        # O SPED é latin-1, mas há ERP que exporta UTF-8. A ordem importa:
        # **latin-1 nunca falha** (todo byte é válido), então tentá-lo
        # primeiro tornava os demais código morto — o arquivo UTF-8 era lido
        # com a acentuação corrompida e regravado assim. UTF-8 primeiro
        # resolve sem risco: texto latin-1 com acento não é UTF-8 válido
        # (`ç` é 0xE7 sozinho) e cai no `except`.
        dados = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(caminho, "r", encoding=enc) as f:
                    dados = f.read()
                doc.encoding_lido = enc
                break
            except UnicodeDecodeError:
                continue
        if dados is None:
            with open(caminho, "r", encoding="latin-1", errors="replace") as f:
                dados = f.read()
            doc.encoding_lido = "latin-1"
        # a GRAVAÇÃO é sempre latin-1: é o que o leiaute manda e o que o PVA
        # aceita. Abrir um SPED em UTF-8 e salvar aqui conserta o arquivo.
        doc.encoding = "latin-1"

        doc._de_texto(dados)
        return doc

    @classmethod
    def de_texto(cls, texto, caminho=None):
        """Documento a partir do texto de um SPED (quem gera do zero monta o
        texto e passa por aqui: a leitura é a mesma do arquivo)."""
        doc = cls()
        doc.caminho = caminho
        doc._de_texto(texto)
        return doc

    def _de_texto(self, dados):
        linhas = [l for l in dados.replace("\r\n", "\n").split("\n")]
        # remove linha final vazia
        linhas = [l for l in linhas if l.strip() != ""]
        self.layout = detectar_layout(linhas)
        self._montar(linhas)

    def _montar(self, linhas):
        """Monta a árvore. **Nada do arquivo some sem aviso.**

        Até a 0.55.0 a linha que não começava por `|` era pulada — e sumia
        ao salvar — e a que não terminava por `|` perdia o **último campo**
        (o `[1:-1]` do `Registro` supõe o pipe final): num 0200 assim, o NCM
        ia embora e o diagnóstico nem notava. Agora a primeira fica em
        `linhas_invalidas` (e salvar exige decisão explícita) e a segunda é
        lida inteira e anotada em `sem_pipe_final`.
        """
        self.registros.clear()
        self.raizes.clear()
        self.linhas_invalidas = []
        self.sem_pipe_final = []
        # pilha de ancestrais (apenas dentro do MESMO bloco)
        pilha = []
        bloco_atual = None
        for i, ln in enumerate(linhas):
            if not ln.startswith("|"):
                self.linhas_invalidas.append((i + 1, ln))
                continue
            partes = ln.split("|")
            if not ln.rstrip(_BRANCOS_FIM).endswith("|"):
                partes = ln.rstrip(_BRANCOS_FIM).split("|") + [""]
                self.sem_pipe_final.append((i + 1, partes[1]))
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

    # ------------------------------------------------ cadastro de participantes
    def _reindexar_participantes(self):
        """(Re)constrói o índice COD_PART -> dados do 0150.

        Os índices vêm por nome porque o 0150 é igual nos dois leiautes mas o
        código não deve depender disso.
        """
        ix = {c: self._ix("0150", c) for c in
              ("COD_PART", "NOME", "CNPJ", "CPF", "IE", "COD_MUN", "UF",
               "END", "NUM", "BAIRRO")}
        d = {}
        for r in self.registros:
            if r.reg != "0150":
                continue
            cod = (r.valor(ix["COD_PART"]) or "").strip()
            if not cod:
                continue
            d[cod] = {c: (r.valor(i) or "").strip()
                      for c, i in ix.items() if i is not None}
            d[cod]["uid"] = r.uid
        self._cad_part = d

    def participante(self, cod):
        """Dados do participante (0150) para um COD_PART, ou `{}`."""
        if getattr(self, "_cad_part", None) is None:
            self._reindexar_participantes()
        return self._cad_part.get((cod or "").strip(), {})

    def alterar_campo(self, registro, idx, valor):
        """Grava um campo e descarta os caches que dependem dele.

        É o caminho único das edições feitas na grade (digitar, colar,
        aplicar à seleção, Ctrl+D). Cada um deles invalidava os caches à sua
        maneira — colar num 0150 não invalidava o de participantes, e o nome
        mostrado no topo da grade continuava o antigo.
        """
        ok = registro.set_valor(idx, valor)
        if registro.reg == "0200":
            self._cad_itens = None
        elif registro.reg == "0150":
            self._cad_part = None
        return ok

    def invalidar_participantes(self):
        """Marca o índice de participantes para ser reconstruído."""
        self._cad_part = None

    @staticmethod
    def formatar_doc_participante(p):
        """CNPJ ou CPF do participante já pontuado, ou ''."""
        cnpj = "".join(c for c in p.get("CNPJ", "") if c.isdigit())
        if len(cnpj) == 14:
            return "%s.%s.%s/%s-%s" % (cnpj[:2], cnpj[2:5], cnpj[5:8],
                                       cnpj[8:12], cnpj[12:])
        cpf = "".join(c for c in p.get("CPF", "") if c.isdigit())
        if len(cpf) == 11:
            return "%s.%s.%s-%s" % (cpf[:3], cpf[3:6], cpf[6:9], cpf[9:])
        return cnpj or cpf

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
        cfop = _set_str(f.get("cfop"))
        ncm = _set_str(f.get("ncm"))
        modelo = _set_str(f.get("modelo"))
        num = _set_str(f.get("num_nota"))
        nitem = _set_str(f.get("nitem"))
        cod_prod = _set_str(f.get("cod_prod"))
        cst_icms = _set_str(f.get("cst_icms"))
        cst_pis = _set_str(f.get("cst_pis"))
        cst_cofins = _set_str(f.get("cst_cofins"))
        cst_ipi = _set_str(f.get("cst_ipi"))
        aliq_pis = _set_float(f.get("aliq_pis"))
        aliq_cofins = _set_float(f.get("aliq_cofins"))

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
            if modelo and mod not in modelo:
                continue
            ndoc = (c100.valor(c_num) or "").strip() if c_num is not None else ""
            if num and ndoc not in num:
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

                if cfop and v("CFOP") not in cfop:
                    continue
                if cst_icms and v("CST_ICMS") not in cst_icms:
                    continue
                if cst_pis and v("CST_PIS") not in cst_pis:
                    continue
                if cst_cofins and v("CST_COFINS") not in cst_cofins:
                    continue
                if cst_ipi and v("CST_IPI") not in cst_ipi:
                    continue
                if nitem and v("NUM_ITEM") not in nitem:
                    continue
                cod = v("COD_ITEM")
                if cod_prod and cod not in cod_prod:
                    continue
                descr, ncm_prod = prod.get(cod, ("", ""))
                if ncm and not any(ncm_prod.startswith(p) for p in ncm):
                    continue
                if not _casa_float(_to_num(v("ALIQ_PIS")), aliq_pis):
                    continue
                if not _casa_float(_to_num(v("ALIQ_COFINS")), aliq_cofins):
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
        modelo = _set_str(f.get("modelo"))
        num = _set_str(f.get("num_nota"))

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
            if modelo and mod not in modelo:
                continue
            ndoc = (c100.valor(c_num) or "").strip() if c_num is not None else ""
            if num and ndoc not in num:
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
        cfop = _set_str(f.get("cfop"))
        cst_pis = _set_str(f.get("cst_pis"))
        cst_cofins = _set_str(f.get("cst_cofins"))
        aliq_pis = _set_float(f.get("aliq_pis"))
        aliq_cofins = _set_float(f.get("aliq_cofins"))
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

                if cfop and v("CFOP") not in cfop:
                    continue
                if cst_pis and v("CST_PIS") not in cst_pis:
                    continue
                if cst_cofins and v("CST_COFINS") not in cst_cofins:
                    continue
                if not _casa_float(_to_num(v("ALIQ_PIS")), aliq_pis):
                    continue
                if not _casa_float(_to_num(v("ALIQ_COFINS")), aliq_cofins):
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
        cfop = _set_str(f.get("cfop"))
        cst_icms = _set_str(f.get("cst_icms"))
        aliq_icms = _set_float(f.get("aliq_icms"))
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

                if cfop and v("CFOP") not in cfop:
                    continue
                if cst_icms and v("CST_ICMS") not in cst_icms:
                    continue
                if not _casa_float(_to_num(v("ALIQ_ICMS")), aliq_icms):
                    continue
                linhas.append([
                    tp, data, ndoc, ser, mod,
                    v("CST_ICMS"), v("CFOP"), v("ALIQ_ICMS"), v("VL_OPR"),
                    v("VL_BC_ICMS"), v("VL_ICMS"), v("VL_BC_ICMS_ST"),
                    v("VL_ICMS_ST"), v("VL_RED_BC"), v("VL_IPI"), v("COD_OBS"),
                    chave])
                uids.append(r.uid)
        return self.COLUNAS_RELATORIO_C190, linhas, uids, self.EDIT_C190

    # ------------------------------------------------- apuração / resumos
    def resumo_c190(self, operacao):
        """Consolida os C190 por (CST_ICMS, CFOP, ALIQ_ICMS) para a operação
        ('0'=entrada, '1'=saída). Devolve (linhas, totais); cada linha é
        (cst, cfop, aliq, vl_opr, vl_bc, vl_icms, vl_bc_st, vl_icms_st)."""
        from collections import defaultdict
        i_op = self._ix("C100", "IND_OPER")
        jc = self._ix("C190", "CST_ICMS")
        jf = self._ix("C190", "CFOP")
        ja = self._ix("C190", "ALIQ_ICMS")
        jo = self._ix("C190", "VL_OPR")
        jb = self._ix("C190", "VL_BC_ICMS")
        ji = self._ix("C190", "VL_ICMS")
        jbs = self._ix("C190", "VL_BC_ICMS_ST")
        jis = self._ix("C190", "VL_ICMS_ST")
        g = defaultdict(lambda: [0.0] * 5)
        for c in self.registros:
            if c.reg != "C100":
                continue
            if (c.valor(i_op) or "").strip() != operacao:
                continue
            for f in c.filhos:
                if f.reg != "C190":
                    continue
                k = (f.valor(jc), f.valor(jf), "%.2f" % _to_num(f.valor(ja)))
                v = g[k]
                v[0] += _to_num(f.valor(jo))
                v[1] += _to_num(f.valor(jb))
                v[2] += _to_num(f.valor(ji))
                v[3] += _to_num(f.valor(jbs))
                v[4] += _to_num(f.valor(jis))
        linhas = []
        tot = [0.0] * 5
        for k in sorted(g, key=lambda x: (x[0], x[1], float(x[2]))):
            v = g[k]
            linhas.append((k[0], k[1], float(k[2]), v[0], v[1], v[2],
                           v[3], v[4]))
            for i in range(5):
                tot[i] += v[i]
        return linhas, tot

    CAMPOS_E110 = ("VL_TOT_DEBITOS", "VL_AJ_DEBITOS", "VL_TOT_AJ_DEBITOS",
                   "VL_ESTORNOS_CRED", "VL_TOT_CREDITOS", "VL_AJ_CREDITOS",
                   "VL_TOT_AJ_CREDITOS", "VL_ESTORNOS_DEB",
                   "VL_SLD_CREDOR_ANT", "VL_SLD_APURADO", "VL_TOT_DED",
                   "VL_ICMS_RECOLHER", "VL_SLD_CREDOR_TRANSPORTAR",
                   "DEB_ESP")

    @staticmethod
    def saldos_e110(v):
        """Os três saldos do E110 pelas expressões do guia (campos 11, 13 e
        14), a partir dos débitos, créditos, ajustes e deduções em `v`.

        O saldo credor a transportar inclui a **dedução** que sobra: com
        saldo apurado 100 e dedução 150, recolhe-se 0 e transportam-se 50.
        Até a 1.0.0-rc.1 o recálculo transportava só o saldo negativo e
        perdia a dedução excedente. Quem recalcula e quem confere usam esta
        mesma função."""
        saldo = (v["VL_TOT_DEBITOS"] + v["VL_AJ_DEBITOS"]
                 + v["VL_TOT_AJ_DEBITOS"] + v["VL_ESTORNOS_CRED"]
                 - v["VL_TOT_CREDITOS"] - v["VL_AJ_CREDITOS"]
                 - v["VL_TOT_AJ_CREDITOS"] - v["VL_ESTORNOS_DEB"]
                 - v["VL_SLD_CREDOR_ANT"])
        apurado = max(round(saldo, 2), 0.0)
        liquido = round(saldo - v["VL_TOT_DED"], 2)
        return {"VL_SLD_APURADO": apurado,
                "VL_ICMS_RECOLHER": max(round(apurado - v["VL_TOT_DED"], 2),
                                        0.0),
                "VL_SLD_CREDOR_TRANSPORTAR": max(-liquido, 0.0)}

    def valores_e110(self, e110):
        """`{campo: número}` de um E110 (os de `CAMPOS_E110` que o leiaute
        tem)."""
        out = {}
        for c in self.CAMPOS_E110:
            ix = self._ix("E110", c)
            if ix is not None:
                out[c] = _to_num(e110.valor(ix))
        return out

    def apuracao_e110(self):
        """Campos do primeiro E110 (apuração do ICMS de operações próprias),
        como dicionário nomeado; None se não houver E110."""
        e = next((r for r in self.registros if r.reg == "E110"), None)
        return None if e is None else self.valores_e110(e)

    # E111 por tipo de ajuste: 3º caractere do COD_AJ_APUR 0 (ICMS próprio)
    # e o 4º diz qual total do E110 ele compõe (guia, E110 campos 04 a 09)
    E111_POR_TIPO = {"0": "VL_TOT_AJ_DEBITOS", "1": "VL_ESTORNOS_CRED",
                     "2": "VL_TOT_AJ_CREDITOS", "3": "VL_ESTORNOS_DEB"}

    def _ajustes_e111(self, e110):
        """Os quatro totais de ajuste do E110 pela soma dos seus E111."""
        i_cod = self._ix("E111", "COD_AJ_APUR")
        i_vl = self._ix("E111", "VL_AJ_APUR")
        tot = dict.fromkeys(self.E111_POR_TIPO.values(), 0.0)
        if i_cod is None or i_vl is None:
            return tot
        for f in e110.filhos:
            cod = (f.valor(i_cod) or "").strip() if f.reg == "E111" else ""
            if len(cod) >= 4 and cod[2] == "0" and cod[3] in self.E111_POR_TIPO:
                tot[self.E111_POR_TIPO[cod[3]]] += _to_num(f.valor(i_vl))
        return {k: round(v, 2) for k, v in tot.items()}

    def e110_esperado(self, e110, primeiro=True):
        """O E110 como o arquivo o determina: débitos e débito especial pelos
        analíticos do período do E100 (o extemporâneo, que não tem período,
        no `primeiro`), os quatro totais de ajuste pelos E111, e os saldos
        pelas expressões do guia sobre esses valores. Créditos, ajustes de
        documento (C197…), deduções e saldo anterior ficam como declarados.

        É a fonte única: `recalcular_e110` grava isto, e as verificações
        (`revisao.verificar_e110_debitos`, a regra do guia) comparam com
        isto — verificação e correção que discordam acusariam o que o botão
        acabou de gravar."""
        novo = self.valores_e110(e110)
        deb, ext = self.debitos_icms_por_situacao(self.periodo_e110(e110))
        novo["VL_TOT_DEBITOS"] = deb
        novo["DEB_ESP"] = round((ext if primeiro else 0.0)
                                + self._ajustes_debito_especial(e110), 2)
        novo.update(self._ajustes_e111(e110))
        novo.update(self.saldos_e110(novo))
        return novo

    # analíticos que somam no E110 (os que existem no arquivo entram)
    ANALITICOS_ICMS = ("C190", "C320", "C390", "C490", "C590", "C690",
                       "C790", "C850", "C890", "D190", "D300", "D390",
                       "D410", "D590", "D690", "D696")
    # documento extemporâneo: o ICMS da saída é débito **especial**
    # (extra-apuração), não débito do período
    SITUACOES_EXTEMPORANEAS = ("01", "07")

    @staticmethod
    def _cfop_de_debito(cfop):
        """CFOP que entra no VL_TOT_DEBITOS (guia, E110 campo 02, e a
        consulta do PVA): saídas 5/6/7, **menos** a 5605 (transferência de
        saldo devedor, que sai do estabelecimento) e **mais** a 1605 (o saldo
        devedor recebido de outro estabelecimento)."""
        return cfop == "1605" or (cfop[:1] in ("5", "6", "7")
                                  and cfop != "5605")

    def _data_do_documento(self, doc):
        """`aaaammdd` da data em que o documento entra na apuração —
        DT_E_S, DT_A_P ou DT_DOC, o primeiro preenchido —, ou ""."""
        for nome in ("DT_E_S", "DT_A_P", "DT_DOC"):
            i = self._ix(doc.reg, nome)
            data = data_aaaammdd(doc.valor(i)) if i is not None else ""
            if data:
                return data
        return ""

    def debitos_icms_por_situacao(self, periodo=None):
        """`(débitos do período, débitos extemporâneos)` — soma do VL_ICMS
        dos analíticos de débito (`_cfop_de_debito`), separando os documentos
        com COD_SIT 01/07. É o que o PVA confere em `MSG_VL_TOT_DEBITOS_E110`
        e `MSG_DEB_ESP_E110`.

        `periodo` (`(aaaammdd, aaaammdd)`, o do E100) limita os documentos
        regulares aos que entram na apuração dentro dele, como faz o PVA;
        o extemporâneo é de outro mês por definição e não passa pelo
        filtro."""
        no_periodo = extemp = 0.0
        indices = {}
        for reg in self.ANALITICOS_ICMS:
            i_icms, i_cfop = self._ix(reg, "VL_ICMS"), self._ix(reg, "CFOP")
            if i_icms is not None and i_cfop is not None:
                indices[reg] = (i_icms, i_cfop)
        for r in self.registros:            # uma passada, não uma por tipo
            par = indices.get(r.reg)
            if par is None or not self._cfop_de_debito(
                    (r.valor(par[1]) or "").strip()):
                continue
            v = _to_num(r.valor(par[0]))
            pai = r.pai
            i_sit = self._ix(pai.reg, "COD_SIT") if pai is not None else None
            sit = (pai.valor(i_sit) or "").strip() if i_sit is not None \
                else ""
            if sit in self.SITUACOES_EXTEMPORANEAS:
                extemp += v
                continue
            if periodo and pai is not None:
                data = self._data_do_documento(pai)
                if data and not periodo[0] <= data <= periodo[1]:
                    continue
            no_periodo += v
        return round(no_periodo, 2), round(extemp, 2)

    def periodo_e110(self, e110):
        """`(aaaammdd, aaaammdd)` do E100 pai do E110, ou None."""
        e100 = e110.pai
        if e100 is None or e100.reg != "E100":
            return None
        datas = tuple(data_aaaammdd(e100.valor(self._ix("E100", nome)))
                      for nome in ("DT_INI", "DT_FIN"))
        return datas if all(datas) else None

    def _ajustes_debito_especial(self, e110):
        """E111 de débito especial do E110: COD_AJ_APUR com 3º caractere 0
        (ICMS próprio) e 4º 5 (débito especial) — a outra parcela do
        DEB_ESP."""
        i_cod = self._ix("E111", "COD_AJ_APUR")
        i_vl = self._ix("E111", "VL_AJ_APUR")
        if i_cod is None or i_vl is None:
            return 0.0
        return sum(_to_num(f.valor(i_vl)) for f in e110.filhos
                   if f.reg == "E111"
                   and (f.valor(i_cod) or "")[2:4] == "05")

    def recalcular_e110(self):
        """Grava em cada E110 o `e110_esperado`: débitos pelos analíticos,
        `DEB_ESP` com o ICMS das saídas extemporâneas mais o que já era
        débito especial de outra origem (ajustes), os totais de ajuste pelos
        E111 e os saldos a partir deles. Créditos, ajustes de documento e
        deduções ficam como estão (não saem dos documentos).

        Cada E110 recebe os débitos dos documentos do período do seu E100,
        como no PVA. Com mais de um E100 no arquivo, o ICMS extemporâneo —
        que não tem período — vai para o primeiro, e a chave de cada campo
        devolvido leva o período ("01/09–15/09 VL_TOT_DEBITOS").

        Devolve `{campo: (antes, depois)}` do que mudou, ou None sem E110.
        """
        e110s = [r for r in self.registros if r.reg == "E110"]
        if not e110s:
            return None
        self._exigir_numeros(e110s + [r for r in self.registros
                                      if r.reg in self.ANALITICOS_ICMS
                                      or r.reg == "E111"])
        mudou = {}
        for k, e in enumerate(e110s):
            v = self.valores_e110(e)
            novo = self.e110_esperado(e, primeiro=k == 0)
            rotulo = ""
            if len(e110s) > 1:
                per = self.periodo_e110(e)
                rotulo = ("%s/%s–%s/%s " % (per[0][6:], per[0][4:6],
                                            per[1][6:], per[1][4:6])
                          if per else "E110 %d " % (k + 1))
            for campo, valor in novo.items():
                if round(valor, 2) != round(v.get(campo, 0.0), 2):
                    e.set_valor(self._ix("E110", campo), _fmt_val(valor))
                    mudou[rotulo + campo] = (v.get(campo, 0.0), valor)
        return mudou

    def consolidacao_cst_pis_cofins(self):
        """Consolida C170 (aquisições) e C175 (receitas) por CST de PIS,
        separando receitas/saídas (CST < 50), aquisições/custos (CST 50–98) e
        outras (99). Cada linha: (cst, vl_item, base_pis, base_cofins)."""
        from collections import defaultdict
        g = defaultdict(lambda: [0.0, 0.0, 0.0])
        idx = {
            "C170": (self._ix("C170", "CST_PIS"), self._ix("C170", "VL_ITEM"),
                     self._ix("C170", "VL_BC_PIS"),
                     self._ix("C170", "VL_BC_COFINS")),
            "C175": (self._ix("C175", "CST_PIS"), self._ix("C175", "VL_OPR"),
                     self._ix("C175", "VL_BC_PIS"),
                     self._ix("C175", "VL_BC_COFINS")),
        }
        for r in self.registros:
            cfg = idx.get(r.reg)
            if not cfg or cfg[0] is None:
                continue
            ic, iv, ip, icf = cfg
            cst = (r.valor(ic) or "").strip()
            v = g[cst]
            v[0] += _to_num(r.valor(iv))
            v[1] += _to_num(r.valor(ip)) if ip is not None else 0.0
            v[2] += _to_num(r.valor(icf)) if icf is not None else 0.0
        receitas, aquisicoes, outras = [], [], []
        tr = [0.0, 0.0, 0.0]
        ta = [0.0, 0.0, 0.0]
        for cst in sorted(g):
            v = g[cst]
            linha = (cst, v[0], v[1], v[2])
            if cst == "99":
                outras.append(linha)
            elif cst < "50":
                receitas.append(linha)
                for i in range(3):
                    tr[i] += v[i]
            else:
                aquisicoes.append(linha)
                for i in range(3):
                    ta[i] += v[i]
        return {"receitas": receitas, "tot_receitas": tr,
                "aquisicoes": aquisicoes, "tot_aquisicoes": ta,
                "outras": outras}

    # ----------------------------------------------- consolidação do C190
    def _ncampos(self, tipo):
        """Quantidade real de campos do registro `tipo` (incluindo o REG).

        Usa a moda dos registros do mesmo tipo já presentes no arquivo; se não
        houver nenhum, conta os campos **nomeados** do layout (o helper `campos`
        completa a lista com rótulos genéricos "Campo NN" só para exibição, e
        usá-los geraria linhas com pipes sobrando)."""
        tam = [len(r.campos) for r in self.registros if r.reg == tipo]
        if tam:
            from collections import Counter
            return Counter(tam).most_common(1)[0][0]
        import re as _re
        return sum(1 for c in campos(tipo, self.layout, 40)
                   if not _re.match(r"^Campo \d+$", c))

    # {(layout, tipo): {nome: índice}} — o leiaute é fixo durante a execução
    _INDICES = {}

    def _ix(self, tipo, nome):
        """Índice da coluna `nome` no layout atual para o registro `tipo`.

        Com cache: montar a lista de colunas a cada chamada custava mais que
        a regra que a chamava — as regras do guia consultam campo a campo, e
        num arquivo de 45 mil linhas o diagnóstico dobrava de tempo."""
        chave = (self.layout, tipo)
        mapa = self._INDICES.get(chave)
        if mapa is None:
            cols = campos(tipo, self.layout, 40)
            mapa = {}
            for i, c in enumerate(cols):
                mapa.setdefault(c, i)
            self._INDICES[chave] = mapa
        return mapa.get(nome)

    @staticmethod
    def _ancora_antes(pai, reg):
        """Último filho de `pai` cujo registro vem **antes** de `reg` no
        leiaute — é depois dele que um `reg` novo deve entrar.

        Dentro de um bloco o código do registro ordena como texto (`C170` <
        `C175` < `C190`, `0150` < `0190` < `0200`). Sem nenhum anterior, a
        âncora é o próprio pai. Era a mesma conta repetida no C190 e no C175
        — e faltava no 0190 da importação de inventário, que entrava logo
        depois do 0001, antes do 0005/0100/0150.
        """
        anteriores = [f for f in sorted(pai.filhos, key=lambda x: x.ordem)
                      if len(f.reg) == len(reg) and f.reg < reg]
        return anteriores[-1] if anteriores else pai

    @staticmethod
    def _preencher(registro, valores, largura=0):
        """Grava a linha montada **sem encolher** o registro.

        `novo_registro` já entrega a largura do arquivo; a lista montada à
        mão tem a do leiaute conhecido. Quando o arquivo é mais largo (versão
        de leiaute mais nova), os campos a mais ficam vazios em vez de sumir
        — um registro mais curto que os irmãos é recusa no PVA.

        `largura` é a medida tirada **antes** de remover os registros que
        estão sendo refeitos: sem eles no arquivo, `_ncampos` cairia no
        leiaute conhecido e perderia justamente a largura do arquivo.
        """
        largura = max(largura or 0, len(registro.campos))
        registro.campos = list(valores) + [""] * (largura - len(valores))
        return registro

    @staticmethod
    def rateio_acessorios(total, valores):
        """Quinhão de cada item nas despesas acessórias do documento.

        Usa **diferença de acumulados arredondados**: o quinhão é a variação
        do total rateado já arredondado, de modo que a soma feche EXATAMENTE
        com `total`. Arredondar item a item não fecha — com R$ 1,00 entre três
        itens iguais dá 0,33 × 3 = 0,99; assim dá 0,33 + 0,34 + 0,33.

        É o mesmo cálculo no C190 e no C175: os dois grupos precisam somar o
        mesmo VL_OPR, senão a conferência acusa diferença num registro que o
        próprio programa acabou de gerar.
        """
        if not total or not valores:
            return [0.0] * len(valores)
        soma = sum(valores)
        if not soma:
            # itens todos zerados e documento com despesa: sem base para
            # proporção, divide igual — deixar o valor de fora faria o VL_OPR
            # não fechar com o total do documento
            valores = [1.0] * len(valores)
            soma = float(len(valores))
        acum = 0.0
        ideal_ant = 0.0
        out = []
        for v in valores:
            acum += v
            ideal = round(total * acum / soma, 2)
            out.append(round(ideal - ideal_ant, 2))
            ideal_ant = ideal
        return out

    # -------------------------------------------------------------------
    # Números que os cálculos leem
    # -------------------------------------------------------------------
    def numeros_invalidos(self, registros):
        """`[(registro, campo, valor)]` dos campos numéricos (pelo nome, como
        na validação de leiaute) preenchidos com o que não é número do SPED.
        Vazio não entra: é zero legítimo."""
        saida, plano = [], {}
        for r in registros:
            chave = (r.reg, len(r.campos))
            ixs = plano.get(chave)
            if ixs is None:
                nomes = campos(r.reg, self.layout, len(r.campos))
                ixs = [(i, n) for i, n in enumerate(nomes)
                       if i and n.startswith(PREFIXOS_NUMERICOS)]
                plano[chave] = ixs
            for i, nome in ixs:
                if i < len(r.campos):
                    v = (r.campos[i] or "").strip()
                    if v and not RE_NUM_SPED.match(v):
                        saida.append((r, nome, v))
        return saida

    def _exigir_numeros(self, registros):
        """Levanta `CamposInvalidos` antes de qualquer alteração."""
        ruins = self.numeros_invalidos(registros)
        if ruins:
            raise CamposInvalidos(ruins)

    @staticmethod
    def _com_itens(documentos, tipo="C170"):
        """Os documentos e os filhos `tipo` de cada um, numa lista só."""
        saida = []
        for c in documentos:
            saida.append(c)
            saida.extend(f for f in c.filhos if f.reg == tipo)
        return saida

    # Compra para revenda com ICMS já retido por substituição tributária
    # (CFOP 1403/2403) e CST de ST com ICMS próprio do fornecedor (x10, x70):
    # o adquirente não se credita do ICMS próprio — o imposto da cadeia já
    # foi recolhido por ST. Base, alíquota e valor do ICMS do item ficam zero.
    CFOP_COMPRA_ST_SEM_CREDITO = ("1403", "2403")
    CST_ST_COM_ICMS_PROPRIO = ("10", "70")

    def itens_credito_icms_st(self):
        """C170 de **entrada** com CFOP 1403/2403, CST x10/x70 e algum valor
        de ICMS próprio (base, alíquota ou valor) — crédito que não cabe."""
        if self.layout != "ICMS":
            return []
        i = {c: self._ix("C170", c) for c in (
            "CFOP", "CST_ICMS", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS")}
        i_op = self._ix("C100", "IND_OPER")
        out = []
        for r in self.registros:
            if r.reg != "C170" or r.pai is None or r.pai.reg != "C100":
                continue
            if (r.pai.valor(i_op) or "").strip() != "0":
                continue
            if (r.valor(i["CFOP"]) or "").strip() not in \
                    self.CFOP_COMPRA_ST_SEM_CREDITO:
                continue
            if (r.valor(i["CST_ICMS"]) or "").strip()[-2:] not in \
                    self.CST_ST_COM_ICMS_PROPRIO:
                continue
            if any(_to_num(r.valor(i[c])) for c in (
                    "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS")):
                out.append(r)
        return out

    def previa_credito_icms_st(self):
        """O que `zerar_credito_icms_st` faria, sem mexer: `{"itens",
        "documentos", "vl_bc", "vl_icms"}`."""
        itens = self.itens_credito_icms_st()
        i_bc, i_v = self._ix("C170", "VL_BC_ICMS"), self._ix("C170", "VL_ICMS")
        return {"itens": len(itens),
                "documentos": len({id(r.pai) for r in itens}),
                "vl_bc": round(sum(_to_num(r.valor(i_bc)) for r in itens), 2),
                "vl_icms": round(sum(_to_num(r.valor(i_v)) for r in itens),
                                 2)}

    def zerar_credito_icms_st(self):
        """Zera base, alíquota e valor do ICMS próprio dos itens de
        `itens_credito_icms_st`, refaz o C190 dos documentos tocados (o
        `consolidar_c190` de sempre), põe no C100 a base e o ICMS somados
        do C190 e tira do `VL_TOT_CREDITOS` do E110 o crédito retirado,
        recalculando os saldos. Devolve a prévia do que foi feito."""
        itens = self.itens_credito_icms_st()
        docs = []
        for r in itens:
            if all(r.pai is not d for d in docs):
                docs.append(r.pai)
        self._exigir_numeros(itens + docs + [
            f for d in docs for f in d.filhos if f.reg == "C190"] + [
            r for r in self.registros if r.reg == "E110"])
        resumo = self.previa_credito_icms_st()
        if not itens:
            return resumo
        for r in itens:
            for campo in ("VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS"):
                i = self._ix("C170", campo)
                if i is not None and i < len(r.campos):
                    r.set_valor(i, "0")
        with self.lote():
            for d in docs:
                self.refazer_c190(d)
        e110 = next((r for r in self.registros if r.reg == "E110"), None)
        i_cred = self._ix("E110", "VL_TOT_CREDITOS")
        if e110 is not None and i_cred is not None and resumo["vl_icms"]:
            novo = max(_to_num(e110.valor(i_cred)) - resumo["vl_icms"], 0.0)
            e110.set_valor(i_cred, _fmt_val(round(novo, 2)))
            self.recalcular_e110()
        return resumo

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
        self._exigir_numeros([c100] + c170)

        # índices dos campos do C170
        i_item = self._ix("C170", "VL_ITEM")
        i_desc = self._ix("C170", "VL_DESC")
        i_bc = self._ix("C170", "VL_BC_ICMS")
        i_icms = self._ix("C170", "VL_ICMS")
        i_bcst = self._ix("C170", "VL_BC_ICMS_ST")
        i_icmsst = self._ix("C170", "VL_ICMS_ST")
        i_ipi = self._ix("C170", "VL_IPI")
        # base de PIS/COFINS: nos CST terminados em 70 o ICMS foi cobrado por
        # ST, então não há base própria de onde tirar a redução. Quando o item
        # tem base de PIS/COFINS, ela serve de substituta para achar a
        # diferença entre a operação e a parcela efetivamente tributada.
        i_bcpis = self._ix("C170", "VL_BC_PIS")
        i_bccof = self._ix("C170", "VL_BC_COFINS")

        # despesas acessórias do documento, rateadas entre os itens pelo valor.
        # O rateio usa DIFERENÇA DE ACUMULADOS ARREDONDADOS: o quinhão de cada
        # item é a variação do total rateado arredondado, de modo que a soma dos
        # quinhões feche EXATAMENTE com `acess` (sem sobrar/faltar centavos).
        acess = (_to_num(c100.valor(self._ix("C100", "VL_FRT")))
                 + _to_num(c100.valor(self._ix("C100", "VL_SEG")))
                 + _to_num(c100.valor(self._ix("C100", "VL_OUT_DA"))))
        rateios = self.rateio_acessorios(
            acess, [_to_num(it.valor(i_item)) for it in c170])

        grupos = {}
        for pos, it in enumerate(c170):
            chave = self.chave_c190(it)
            g = grupos.get(chave)
            if g is None:
                g = {"cst": chave[0], "cfop": chave[1], "aliq": chave[2],
                     "VL_OPR": 0.0, "VL_BC": 0.0, "VL_ICMS": 0.0,
                     "VL_BCST": 0.0, "VL_ICMSST": 0.0, "VL_IPI": 0.0,
                     "VL_BC_PC": 0.0}
                grupos[chave] = g
            vit = _to_num(it.valor(i_item))
            rateio = rateios[pos]
            g["VL_OPR"] += (vit - _to_num(it.valor(i_desc)) + rateio
                            + _to_num(it.valor(i_ipi))
                            + _to_num(it.valor(i_icmsst)))
            g["VL_BC"] += _to_num(it.valor(i_bc))
            g["VL_ICMS"] += _to_num(it.valor(i_icms))
            g["VL_BCST"] += _to_num(it.valor(i_bcst))
            g["VL_ICMSST"] += _to_num(it.valor(i_icmsst))
            g["VL_IPI"] += _to_num(it.valor(i_ipi))
            bc_pc = _to_num(it.valor(i_bcpis)) if i_bcpis is not None else 0.0
            if not bc_pc and i_bccof is not None:
                bc_pc = _to_num(it.valor(i_bccof))
            g["VL_BC_PC"] += bc_pc

        chaves = sorted(grupos)

        # remove os C190 antigos do documento
        largura = self._largura("C190")      # antes de remover os antigos
        antigos = [f for f in c100.filhos if f.reg == "C190"]
        n_rem = len(antigos)
        for a in antigos:
            self.remover_registro(a)

        ancora = self._ancora_antes(c100, "C190")

        n_cri = 0
        usou_pc = 0          # grupos em que a base de PIS/COFINS substituiu
        sem_base = 0         # grupos x20/x70 sem base de onde tirar a redução
        for chave in chaves:
            g = grupos[chave]
            # redução de base: nos CST terminados em 20 ou 70, o valor reduzido
            # é a parcela da operação que ficou fora da base de cálculo.
            cst2 = (g["cst"] or "").strip()[-2:]
            if cst2 in ("20", "70"):
                base = g["VL_BC"]
                if not base and cst2 == "70" and g["VL_BC_PC"]:
                    # ICMS cobrado por ST: sem base própria, a de PIS/COFINS
                    # é a melhor medida da parcela efetivamente tributada
                    base = g["VL_BC_PC"]
                    usou_pc += 1
                vl_red = round(g["VL_OPR"] - base, 2) if base else 0.0
                if vl_red < 0:
                    vl_red = 0.0
                if cst2 in ("20", "70") and not vl_red:
                    sem_base += 1
            else:
                vl_red = 0.0
            novo = self.novo_registro("C190", pai=c100, depois=ancora)
            self._preencher(novo, [
                "C190", g["cst"], g["cfop"], _fmt_val(g["aliq"]),
                _fmt_val(g["VL_OPR"]), _fmt_val(g["VL_BC"]),
                _fmt_val(g["VL_ICMS"]), _fmt_val(g["VL_BCST"]),
                _fmt_val(g["VL_ICMSST"]), _fmt_val(vl_red),
                _fmt_val(g["VL_IPI"]), ""], largura)
            ancora = novo
            n_cri += 1

        self.atualizar_bloco9_inplace()
        return {"grupos": len(chaves), "removidos": n_rem, "criados": n_cri,
                "base_pis_cofins": usou_pc, "sem_base": sem_base}

    # campo do C100 <- soma do mesmo campo nos C190 do documento. É o que o
    # PVA confere entre os dois (o VL_DOC não: ele é o valor do documento, e
    # o VL_OPR do C190 é que sai dele)
    TOTAIS_C100_PELO_C190 = ("VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
                             "VL_ICMS_ST", "VL_IPI")

    def totais_c100_pelo_c190(self, c100):
        """Põe no C100 a base e os impostos somados dos seus C190. Campo
        vazio com soma zero **continua vazio**: a NFC-e deixa ST e IPI em
        branco no C100, e zero ali dá `MSG_NFE_CONSUMIDOR`. Devolve `{campo:
        (antes, depois)}` do que mudou."""
        c190 = [f for f in c100.filhos if f.reg == "C190"]
        mudou = {}
        if not c190:
            return mudou
        for campo in self.TOTAIS_C100_PELO_C190:
            i100, i190 = self._ix("C100", campo), self._ix("C190", campo)
            if i100 is None or i190 is None:
                continue
            soma = round(sum(_to_num(f.valor(i190)) for f in c190), 2)
            antes = (c100.valor(i100) or "").strip()
            if not antes and not soma:
                continue
            if antes and round(_to_num(antes), 2) == soma:
                continue
            c100.set_valor(i100, _fmt_val(soma))
            mudou[campo] = (antes, _fmt_val(soma))
        return mudou

    def fundir_c190_duplicados(self, c100):
        """Funde os C190 de mesma chave (CST + CFOP + alíquota) do documento
        num só, somando os valores — o conserto para quem **não tem C170**
        de onde refazer o analítico (a NFC-e). Devolve quantos C190 saíram."""
        c190 = [f for f in c100.filhos if f.reg == "C190"]
        self._exigir_numeros(c190)
        valores = [self._ix("C190", c) for c in (
            "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST",
            "VL_RED_BC", "VL_IPI")]
        valores = [i for i in valores if i is not None]
        primeiro = {}
        sobra = []
        for f in c190:
            k = self.chave_c190(f)
            alvo = primeiro.get(k)
            if alvo is None:
                primeiro[k] = f
                continue
            for i in valores:
                soma = _to_num(alvo.valor(i)) + _to_num(f.valor(i))
                alvo.set_valor(i, _fmt_val(round(soma, 2)))
            sobra.append(f)
        for f in sobra:
            self.remover_registro(f)
        if sobra and self._lote is None:
            self.atualizar_bloco9_inplace()
        return len(sobra)

    def refazer_c190(self, c100):
        """O *Recalcular C190* de um documento: o analítico refeito pelos
        itens (`consolidar_c190`) — ou, sem C170, os C190 de mesma chave
        fundidos — e o C100 acertado pelo C190 (`totais_c100_pelo_c190`).
        Devolve o resumo do `consolidar_c190` com `fundidos` e `c100` (o que
        mudou no C100)."""
        res = self.consolidar_c190(c100)
        if res is None:
            return None
        if res.get("sem_c170"):
            res["fundidos"] = self.fundir_c190_duplicados(c100)
        res["c100"] = self.totais_c100_pelo_c190(c100)
        return res

    def chave_c190(self, r):
        """`(CST_ICMS, CFOP, alíquota)` de um C170 ou C190 — a chave do
        analítico. Sem espaços e com a alíquota como número: "18" e "18,00"
        são o mesmo grupo. Era refeita em seis lugares, e um deles comparava
        a alíquota como texto (via "0" e "0,00" como chaves diferentes)."""
        return ((r.valor(self._ix(r.reg, "CST_ICMS")) or "").strip(),
                (r.valor(self._ix(r.reg, "CFOP")) or "").strip(),
                round(_to_num(r.valor(self._ix(r.reg, "ALIQ_ICMS"))), 2))

    def documentos_c190_com_reducao_zerada(self):
        """C100 que têm algum C190 com CST x20/x70 e `VL_RED_BC` zerado —
        os candidatos ao recálculo. **Não altera nada.**

        Devolve `[(c100, [c190…])]`.
        """
        if self.layout != "ICMS":
            return []
        i_cst = self._ix("C190", "CST_ICMS")
        i_red = self._ix("C190", "VL_RED_BC")
        if i_cst is None or i_red is None:
            return []
        out = []
        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            ruins = [f for f in c100.filhos
                     if f.reg == "C190"
                     and (f.valor(i_cst) or "").strip()[-2:] in ("20", "70")
                     and _to_num(f.valor(i_red)) == 0]
            if ruins:
                out.append((c100, ruins))
        return out

    def documentos_c190_duplicados(self):
        """C100 com dois C190 de mesma chave (CST+CFOP+alíquota).

        O PVA recusa com `MSG_CHAVE_EXISTE_NO_REGISTRO_ITEM`. Refazer o
        analítico do documento resolve, porque a consolidação agrupa por essa
        mesma chave.
        """
        if self.layout != "ICMS":
            return []
        out = []
        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            vistos = set()
            for f in c100.filhos:
                if f.reg != "C190":
                    continue
                k = self.chave_c190(f)
                if k in vistos:
                    out.append(c100)
                    break
                vistos.add(k)
        return out

    def documentos_para_refazer_c190(self):
        """Os C100 cujo analítico o *Recalcular C190* refaz pelos itens, por
        motivo, cada documento num motivo só: `{"reducao", "duplicados",
        "nfce", "divergentes": [c100…]}` — redução de base zerada, chave
        repetida, NFC-e com C170 fictícios e C190 que não confere com os
        itens pelas regras do guia. O botão e o padrão de
        `consolidar_c190_em_massa` (que os roteiros usam) partem daqui."""
        if self.layout != "ICMS":
            return {}
        from sped_tables.dominio import regras_guia
        candidatos = (
            ("reducao", [c for c, _r in
                         self.documentos_c190_com_reducao_zerada()]),
            ("duplicados", self.documentos_c190_duplicados()),
            ("nfce", self.documentos_65_com_c170()),
            ("divergentes", regras_guia.documentos_c190_divergentes(self)))
        vistos = set()
        out = {}
        for motivo, docs in candidatos:
            out[motivo] = []
            for c in docs:
                if c.uid not in vistos:
                    vistos.add(c.uid)
                    out[motivo].append(c)
        return out

    def consolidar_c190_em_massa(self, documentos=None):
        """Roda `consolidar_c190` em vários documentos de uma vez.

        Sem `documentos`, refaz só os de `documentos_para_refazer_c190` — o
        recálculo substitui os C190 do documento, e refazer os que já estão
        certos seria mexer no que não pede conserto.

        Devolve o somatório, com quantos grupos usaram a base de PIS/COFINS no
        lugar da base de ICMS (CST x70) e quantos ficaram sem base alguma.
        """
        if self.layout != "ICMS":
            return {"erro": "O C190 é do EFD ICMS/IPI."}
        if documentos is None:
            documentos = [c for docs in
                          self.documentos_para_refazer_c190().values()
                          for c in docs]
        # confere todos antes do primeiro: parar no meio deixaria metade dos
        # documentos refeitos
        self._exigir_numeros(self._com_itens(documentos) + [
            f for c in documentos for f in c.filhos if f.reg == "C190"])
        tot = {"documentos": 0, "corrigidos": 0, "grupos": 0, "removidos": 0,
               "criados": 0, "base_pis_cofins": 0, "sem_base": 0,
               "sem_c170": 0, "fundidos": 0, "c100": 0}
        i_red = self._ix("C190", "VL_RED_BC")

        def red_do_doc(c100):
            return sum(_to_num(f.valor(i_red)) for f in c100.filhos
                       if f.reg == "C190")

        with self.lote():
            for c100 in documentos:
                antes = red_do_doc(c100)
                res = self.refazer_c190(c100)
                if not res:
                    continue
                if res["c100"]:
                    tot["c100"] += 1
                if res.get("sem_c170"):
                    # sem itens não há de onde refazer: os duplicados são
                    # fundidos (a NFC-e consolidada)
                    tot["sem_c170"] += 1
                    tot["fundidos"] += res["fundidos"]
                    continue
                tot["documentos"] += 1
                # documento em que a redução realmente mudou — sem isso, rodar
                # de novo diria "33 recalculados" sobre documentos que não têm
                # conserto possível, e o usuário não saberia o que aconteceu
                if round(red_do_doc(c100), 2) != round(antes, 2):
                    tot["corrigidos"] += 1
                for k in ("grupos", "removidos", "criados",
                          "base_pis_cofins", "sem_base"):
                    tot[k] += res.get(k, 0)
        return tot

    # somas diretas: campo do C100 <- soma do campo correspondente nos C170
    TOTAIS_C100 = {
        "VL_MERC": "VL_ITEM", "VL_DESC": "VL_DESC",
        "VL_BC_ICMS": "VL_BC_ICMS", "VL_ICMS": "VL_ICMS",
        "VL_BC_ICMS_ST": "VL_BC_ICMS_ST", "VL_ICMS_ST": "VL_ICMS_ST",
        "VL_IPI": "VL_IPI", "VL_PIS": "VL_PIS", "VL_COFINS": "VL_COFINS",
    }

    # ---------------------------------------------------- recálculo de ICMS
    # Situação tributária do ICMS pelos **dois últimos dígitos** do CST (o
    # primeiro é a origem da mercadoria, que não interfere no cálculo).
    CST_ICMS_REDUCAO = ("20", "70")          # base reduzida
    CST_ICMS_SEM_DEBITO = ("30", "40", "41", "50", "60")
    # 00 integral · 10 e 70 com ST · 90 outras · 51 diferimento (parcial)

    @staticmethod
    def situacao_icms(cst):
        """'tributado', 'reduzido' ou 'sem_debito' a partir do CST_ICMS."""
        d = re.sub(r"\D", "", cst or "")
        chave = d[-2:] if len(d) >= 2 else d
        if chave in SpedDocument.CST_ICMS_REDUCAO:
            return "reduzido"
        if chave in SpedDocument.CST_ICMS_SEM_DEBITO:
            return "sem_debito"
        return "tributado"

    def recalcular_icms_itens(self, uids=None, recalcular_base=False,
                              reducao_pct=None, zerar_sem_debito=True,
                              tol=0.005, refazer_c190=False):
        """Recalcula o ICMS dos itens C170.

        O fluxo pensado é: corrigir alíquota, base ou CST no **Modo Relatório**
        e depois pedir o recálculo — daí `uids` aceitar exatamente o conjunto
        que está na tela.

        * **VL_ICMS = VL_BC_ICMS × ALIQ_ICMS ÷ 100**, sempre. É o cálculo que
          amarra os três campos e o que mais sai errado quando a alíquota é
          corrigida na mão.
        * `recalcular_base` refaz a **base** a partir de `VL_ITEM − VL_DESC`.
          Nos CST de **redução** (x20 e x70) aplica `reducao_pct`; nos demais,
          a base é o valor líquido do item. Sem essa opção, a base informada é
          respeitada — inclusive uma base reduzida digitada à mão.
        * `zerar_sem_debito` zera base, alíquota e valor nos CST que não geram
          débito próprio (x30, x40, x41, x50, x60). Um CST desses com valor
          lançado é erro de escrituração, não redução.

        O ICMS-ST **não é tocado**: ele tem base e alíquota próprias, muitas
        vezes com MVA, e misturá-lo aqui produziria número errado em silêncio.

        Devolve um resumo com o que mudou.
        """
        i_item = self._ix("C170", "VL_ITEM")
        i_desc = self._ix("C170", "VL_DESC")
        i_cst = self._ix("C170", "CST_ICMS")
        i_bc = self._ix("C170", "VL_BC_ICMS")
        i_aliq = self._ix("C170", "ALIQ_ICMS")
        i_vl = self._ix("C170", "VL_ICMS")
        if None in (i_cst, i_bc, i_aliq, i_vl):
            return {"itens": 0, "alterados": 0, "sem_campos": True}

        alvo = set(uids) if uids is not None else None
        itens = [r for r in self.registros if r.reg == "C170"
                 and (alvo is None or r.uid in alvo)]
        lidos = list(itens)
        if refazer_c190:
            # o C190 e os totais refeitos leem o documento inteiro
            pais = {id(r.pai): r.pai for r in itens if r.pai is not None}
            lidos = self._com_itens(pais.values())
        self._exigir_numeros(lidos)
        resumo = {"itens": 0, "alterados": 0, "base_alterada": 0,
                  "valor_alterado": 0, "zerados": 0, "por_situacao": {},
                  "delta_icms": 0.0, "c190_refeitos": 0}
        # documentos com item alterado: só eles têm o C190 refeito
        tocados = {}

        for r in self.registros:
            if r.reg != "C170":
                continue
            if alvo is not None and r.uid not in alvo:
                continue
            resumo["itens"] += 1
            situacao = self.situacao_icms(r.valor(i_cst))
            resumo["por_situacao"][situacao] = \
                resumo["por_situacao"].get(situacao, 0) + 1

            bc_antes = _to_num(r.valor(i_bc))
            vl_antes = _to_num(r.valor(i_vl))
            mudou = False

            if situacao == "sem_debito" and zerar_sem_debito:
                if bc_antes or vl_antes or _to_num(r.valor(i_aliq)):
                    r.set_valor(i_bc, _fmt_val(0))
                    r.set_valor(i_aliq, "")
                    r.set_valor(i_vl, _fmt_val(0))
                    resumo["zerados"] += 1
                    resumo["delta_icms"] -= vl_antes
                    mudou = True
                if mudou:
                    resumo["alterados"] += 1
                    if r.pai is not None:
                        tocados[r.pai.uid] = r.pai
                continue

            base = bc_antes
            if recalcular_base and i_item is not None:
                liquido = _to_num(r.valor(i_item))
                if i_desc is not None:
                    liquido -= _to_num(r.valor(i_desc))
                if situacao == "reduzido" and reducao_pct:
                    liquido *= (1.0 - float(reducao_pct) / 100.0)
                base = round(liquido, 2)
                if abs(base - bc_antes) > tol:
                    r.set_valor(i_bc, _fmt_val(base))
                    resumo["base_alterada"] += 1
                    mudou = True

            aliq = _to_num(r.valor(i_aliq))
            valor = round(base * aliq / 100.0, 2)
            if abs(valor - vl_antes) > tol:
                r.set_valor(i_vl, _fmt_val(valor))
                resumo["valor_alterado"] += 1
                resumo["delta_icms"] += valor - vl_antes
                mudou = True

            if mudou:
                resumo["alterados"] += 1
                if r.pai is not None:
                    tocados[r.pai.uid] = r.pai

        resumo["delta_icms"] = round(resumo["delta_icms"], 2)
        # a cadeia que o botão fazia sozinho (e em todos os documentos, não
        # só nos alterados): C190 e totais do C100 de quem mudou
        if refazer_c190:
            for c100 in tocados.values():
                if c100.reg == "C100":
                    self.consolidar_c190(c100)
                    self.recalcular_totais_c100(c100)
                    resumo["c190_refeitos"] += 1
        return resumo

    def recalcular_totais_c100(self, c100):
        """Recalcula os totais de um C100 a partir dos seus itens C170.

        Soma, dos C170, os campos de mercadorias, desconto, base e valor de ICMS,
        ICMS-ST, IPI e (no EFD Contribuições) PIS/COFINS, gravando cada total no
        campo correspondente do C100 (apenas os que existem no layout). Por fim,
        recompõe o VL_DOC:
            VL_DOC = VL_MERC − VL_DESC − VL_ABAT_NT + VL_FRT + VL_SEG
                     + VL_OUT_DA + VL_IPI + VL_ICMS_ST
        mantendo frete, seguro e outras despesas (que são do documento, não dos
        itens). Devolve um dicionário {campo: total} com o que foi recalculado.
        """
        c170s = [f for f in c100.filhos if f.reg == "C170"]
        self._exigir_numeros([c100] + c170s)
        tot = {}
        for campo_c100, campo_c170 in self.TOTAIS_C100.items():
            i100 = self._ix("C100", campo_c100)
            i170 = self._ix("C170", campo_c170)
            if i100 is None or i170 is None:
                continue
            s = round(sum(_to_num(f.valor(i170)) for f in c170s), 2)
            tot[campo_c100] = s
            c100.set_valor(i100, _fmt_val(s))

        def c100v(nome):
            i = self._ix("C100", nome)
            return _to_num(c100.valor(i)) if i is not None else 0.0

        i_doc = self._ix("C100", "VL_DOC")
        if i_doc is not None:
            vl_doc = (tot.get("VL_MERC", c100v("VL_MERC"))
                      - tot.get("VL_DESC", c100v("VL_DESC"))
                      - c100v("VL_ABAT_NT")
                      + c100v("VL_FRT") + c100v("VL_SEG") + c100v("VL_OUT_DA")
                      + tot.get("VL_IPI", c100v("VL_IPI"))
                      + tot.get("VL_ICMS_ST", c100v("VL_ICMS_ST")))
            vl_doc = round(vl_doc, 2)
            tot["VL_DOC"] = vl_doc
            c100.set_valor(i_doc, _fmt_val(vl_doc))
        return tot

    def recalcular_totais_todos_c100(self):
        """Recalcula os totais de todos os C100 que possuem itens C170.
        Devolve a quantidade de documentos recalculados."""
        docs = [c for c in self.registros if c.reg == "C100"
                and any(f.reg == "C170" for f in c.filhos)]
        self._exigir_numeros(self._com_itens(docs))
        for c100 in docs:
            self.recalcular_totais_c100(c100)
        return len(docs)

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
        rateios = self.rateio_acessorios(
            acess, [(getattr(it, "vprod", 0.0) or 0.0) for it in itens])

        def fmt_aliq(a):
            return _fmt_val(_to_num((a or "").replace(".", ","))) if a else ""

        grupos, ordem = {}, []
        tot_pis = tot_cof = 0.0
        for pos, it in enumerate(itens):
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
            g["VL_OPR"] += vprod - vdesc + rateios[pos]
            g["VL_DESC"] += vdesc
            g["VL_BC_PIS"] += it.pis_vbc or 0.0
            g["VL_PIS"] += it.pis_vpis or 0.0
            g["VL_BC_COF"] += it.cofins_vbc or 0.0
            g["VL_COF"] += it.cofins_vcofins or 0.0
            tot_pis += it.pis_vpis or 0.0
            tot_cof += it.cofins_vcofins or 0.0

        largura = self._largura("C175")      # antes de remover os antigos
        antigos = [f for f in c100.filhos if f.reg == "C175"]
        n_rem = len(antigos)
        for a in antigos:
            self.remover_registro(a)

        ancora = self._ancora_antes(c100, "C175")

        n_cri = 0
        for chave in ordem:
            g = grupos[chave]
            novo = self.novo_registro("C175", pai=c100, depois=ancora)
            self._preencher(novo, [
                "C175", g["cfop"], _fmt_val(g["VL_OPR"]),
                _fmt_val(g["VL_DESC"]), g["cstp"],
                _fmt_val(g["VL_BC_PIS"]), fmt_aliq(g["aliq_pis"]),
                "", "", _fmt_val(g["VL_PIS"]), g["cstc"],
                _fmt_val(g["VL_BC_COF"]), fmt_aliq(g["aliq_cof"]),
                "", "", _fmt_val(g["VL_COF"]), "", ""], largura)
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

    # -------------------------------------------------------------------
    # NFC-e (modelo 65): C170 "fictício" para validar/corrigir o C175 por item
    # -------------------------------------------------------------------
    def gerar_c170_ficticios_65(self, nfes):
        """Para cada C100 modelo 65 casado com um XML (por série + número),
        cria registros **C170 fictícios** — um por item do XML — com COD_ITEM,
        valor, CFOP, ICMS e PIS/COFINS. O modelo 65 é escriturado consolidado
        (sem C170), e esses C170 são um andaime para corrigir por item:

        * no **EFD Contribuições**, o C175 é regenerado a partir deles
          (`regenerar_c175_de_c170_65`);
        * no **EFD ICMS/IPI**, o C190 é refeito por `consolidar_c190` — com a
          base de PIS/COFINS do XML, que é o que permite achar a redução de
          base no CST x70 —, e depois eles saem por
          `remover_c170_ficticios_65`.

        Nos dois, documento modelo 65 com C170 é estrutura **inválida**: o
        andaime não pode ser gravado.

        C170 fictícios anteriores (de execução prévia) são substituídos. Retorna
        um resumo com documentos e itens criados, os documentos sem XML e
        quantos itens vieram com CSOSN (emitente do Simples) no lugar do CST.
        """
        from sped_tables.dominio import xml_fiscal as xf
        idx_xml = xf.indexar(nfes, xf.chave_doc)
        i_mod = self._ix("C100", "COD_MOD")
        i_ser = self._ix("C100", "SER")
        i_num = self._ix("C100", "NUM_DOC")
        ncampos = self._ncampos("C170")
        col = {c: self._ix("C170", c) for c in (
            "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID",
            "VL_ITEM", "VL_DESC", "CST_ICMS", "CFOP", "VL_BC_ICMS",
            "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "ALIQ_ST", "VL_ICMS_ST",
            "CST_IPI", "VL_BC_IPI", "ALIQ_IPI", "VL_IPI",
            "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
            "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS")}

        def setv(reg, nome, valor):
            i = col.get(nome)
            if i is not None and i < len(reg.campos):
                reg.set_valor(i, valor)

        docs = itens = csosn = 0
        sem_xml = []
        alvos = []
        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            if (c100.valor(i_mod) or "").strip() != "65":
                continue
            chave = (xf.norm(c100.valor(i_mod)), xf.norm(c100.valor(i_ser)),
                     xf.norm(c100.valor(i_num)))
            achados = idx_xml.get(chave)
            if not achados:
                sem_xml.append(chave)
                continue
            alvos.append((c100, achados[0]))
        with self.lote():
            for c100, nfe in alvos:
                itens_doc, csosn_doc = self._ficticios_do_documento(
                    c100, nfe, ncampos, setv)
                itens += itens_doc
                csosn += csosn_doc
                docs += 1
        return {"docs": docs, "itens": itens, "sem_xml": sem_xml,
                "csosn": csosn}

    def _ficticios_do_documento(self, c100, nfe, ncampos, setv):
        """Os C170 fictícios de um C100 modelo 65, um por item do XML.
        Devolve `(itens, itens com CSOSN)`."""
        itens = csosn = 0
        for f in [x for x in c100.filhos if x.reg == "C170"]:
            self.remover_registro(f)
        # âncora: inserir os C170 logo após o C100 (antes dos C175)
        ancora = c100
        for k, it in enumerate(nfe.itens, 1):
            novo = self.novo_registro("C170", pai=c100, depois=ancora)
            novo.campos = ["C170"] + [""] * (ncampos - 1)
            setv(novo, "NUM_ITEM", str(k))
            setv(novo, "COD_ITEM", (it.cprod or "").strip())
            setv(novo, "DESCR_COMPL", (it.xprod or "").strip())
            if it.qtd:
                setv(novo, "QTD", _fmt_qtd(it.qtd))
            setv(novo, "UNID", (it.unid or "").strip())
            setv(novo, "VL_ITEM", _fmt_val(it.vprod or 0.0))
            setv(novo, "VL_DESC", _fmt_val(it.vdesc or 0.0))
            cst = (it.icms_cst or "").strip()
            if len(cst) == 4:
                # origem + CSOSN: não é CST, e o C190 sairia com ele
                csosn += 1
            setv(novo, "CST_ICMS", cst)
            setv(novo, "CFOP", (it.cfop or "").strip())
            setv(novo, "VL_BC_ICMS", _fmt_val(it.icms_vbc or 0.0))
            setv(novo, "ALIQ_ICMS", _fmt_aliq_pct(it.icms_aliq))
            setv(novo, "VL_ICMS", _fmt_val(it.icms_vicms or 0.0))
            setv(novo, "VL_BC_ICMS_ST", _fmt_val(it.icms_vbcst or 0.0))
            setv(novo, "ALIQ_ST", _fmt_aliq_pct(it.icms_aliqst))
            setv(novo, "VL_ICMS_ST", _fmt_val(it.icms_vicmsst or 0.0))
            setv(novo, "CST_IPI", (it.ipi_cst or "").strip())
            setv(novo, "VL_BC_IPI", _fmt_val(it.ipi_vbc or 0.0)
                 if it.ipi_vbc else "")
            setv(novo, "ALIQ_IPI", _fmt_aliq_pct(it.ipi_aliq))
            setv(novo, "VL_IPI", _fmt_val(it.vipi or 0.0)
                 if it.vipi else "")
            setv(novo, "CST_PIS", (it.pis_cst or "").strip())
            setv(novo, "VL_BC_PIS", _fmt_val(it.pis_vbc or 0.0))
            setv(novo, "ALIQ_PIS", _fmt_aliq_pct(it.pis_aliq))
            setv(novo, "VL_PIS", _fmt_val(it.pis_vpis or 0.0))
            setv(novo, "CST_COFINS", (it.cofins_cst or "").strip())
            setv(novo, "VL_BC_COFINS", _fmt_val(it.cofins_vbc or 0.0))
            setv(novo, "ALIQ_COFINS", _fmt_aliq_pct(it.cofins_aliq))
            setv(novo, "VL_COFINS", _fmt_val(it.cofins_vcofins or 0.0))
            ancora = novo
            itens += 1
        return itens, csosn

    def documentos_65_com_c170(self):
        """C100 modelo 65 com C170 — o andaime dos fictícios ainda no
        arquivo. Estrutura inválida nos dois leiautes: quem grava pergunta."""
        i_mod = self._ix("C100", "COD_MOD")
        return [c for c in self.registros
                if c.reg == "C100"
                and (c.valor(i_mod) or "").strip() == "65"
                and any(f.reg == "C170" for f in c.filhos)]

    def remover_c170_ficticios_65(self):
        """Tira os C170 dos documentos modelo 65, devolvendo a NFC-e à forma
        consolidada. No EFD ICMS/IPI é o passo final, depois de refazer o
        C190; no EFD Contribuições, o `regenerar_c175_de_c170_65` já faz isso
        (remover sem regenerar é desistir da correção)."""
        docs = self.documentos_65_com_c170()
        itens = 0
        with self.lote():
            for c100 in docs:
                for f in [x for x in c100.filhos if x.reg == "C170"]:
                    self.remover_registro(f)
                    itens += 1
        return {"docs": len(docs), "itens": itens}

    def discrepancias_c175_65(self):
        """Compara, em cada C100 modelo 65 que tenha C170 fictícios, a soma dos
        itens (por CFOP/CST/alíquota de PIS/COFINS) com o C175 já escriturado.
        Devolve a lista de divergências (dicts) — valores do C175 que não batem
        com a totalização dos itens do XML."""
        if self.layout != "CONTRIB":
            return []
        i_mod = self._ix("C100", "COD_MOD")
        i_num = self._ix("C100", "NUM_DOC")
        # C170
        a = {c: self._ix("C170", c) for c in (
            "CFOP", "VL_ITEM", "VL_DESC", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
            "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS")}
        # C175
        b = {c: self._ix("C175", c) for c in (
            "CFOP", "VL_OPR", "VL_DESC", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
            "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS")}
        div = []
        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            if (c100.valor(i_mod) or "").strip() != "65":
                continue
            c170s = [f for f in c100.filhos if f.reg == "C170"]
            c175s = [f for f in c100.filhos if f.reg == "C175"]
            if not c170s or not c175s:
                continue
            ndoc = (c100.valor(i_num) or "").strip()
            # o VL_OPR do C175 inclui o rateio das despesas acessórias do
            # documento — comparar sem ele acusava diferença em todo
            # documento com frete/seguro/outras
            rateios = self.rateio_acessorios(
                sum(_to_num(c100.valor(self._ix("C100", n)))
                    for n in ("VL_FRT", "VL_SEG", "VL_OUT_DA")),
                [_to_num(f.valor(a["VL_ITEM"])) for f in c170s])
            # consolida os C170 por (CFOP, CST_PIS, ALIQ_PIS, CST_COFINS, ALIQ_COFINS)
            grupos = {}
            for pos, f in enumerate(c170s):
                k = ((f.valor(a["CFOP"]) or "").strip(),
                     (f.valor(a["CST_PIS"]) or "").strip(),
                     "%.4f" % _to_num(f.valor(a["ALIQ_PIS"])),
                     (f.valor(a["CST_COFINS"]) or "").strip(),
                     "%.4f" % _to_num(f.valor(a["ALIQ_COFINS"])))
                g = grupos.setdefault(k, [0.0, 0.0, 0.0, 0.0, 0.0])
                g[0] += (_to_num(f.valor(a["VL_ITEM"]))
                         - _to_num(f.valor(a["VL_DESC"]))
                         + rateios[pos])                # VL_OPR
                g[1] += _to_num(f.valor(a["VL_BC_PIS"]))
                g[2] += _to_num(f.valor(a["VL_PIS"]))
                g[3] += _to_num(f.valor(a["VL_BC_COFINS"]))
                g[4] += _to_num(f.valor(a["VL_COFINS"]))
            # indexa o C175 existente pela mesma chave
            c175_por_k = {}
            for r in c175s:
                k = ((r.valor(b["CFOP"]) or "").strip(),
                     (r.valor(b["CST_PIS"]) or "").strip(),
                     "%.4f" % _to_num(r.valor(b["ALIQ_PIS"])),
                     (r.valor(b["CST_COFINS"]) or "").strip(),
                     "%.4f" % _to_num(r.valor(b["ALIQ_COFINS"])))
                c175_por_k[k] = r
            for k, g in grupos.items():
                r = c175_por_k.get(k)
                grp = "CFOP %s · PIS %s/%s · COFINS %s/%s" % (
                    k[0], k[1], k[2].rstrip("0").rstrip("."),
                    k[3], k[4].rstrip("0").rstrip("."))
                if r is None:
                    div.append({"nnf": ndoc, "grupo": grp, "campo": "C175",
                                "xml": _fmt_val(g[0]), "sped": "(ausente)",
                                "uid": None})
                    continue
                comps = [("VL_OPR", g[0], _to_num(r.valor(b["VL_OPR"]))),
                         ("VL_BC_PIS", g[1], _to_num(r.valor(b["VL_BC_PIS"]))),
                         ("VL_PIS", g[2], _to_num(r.valor(b["VL_PIS"]))),
                         ("VL_BC_COFINS", g[3],
                          _to_num(r.valor(b["VL_BC_COFINS"]))),
                         ("VL_COFINS", g[4], _to_num(r.valor(b["VL_COFINS"])))]
                for campo, vx, vs in comps:
                    if abs(round(vx, 2) - round(vs, 2)) > 0.01:
                        div.append({"nnf": ndoc, "grupo": grp, "campo": campo,
                                    "xml": _fmt_val(vx), "sped": _fmt_val(vs),
                                    "uid": r.uid})
        return div

    def previa_regeneracao_c175_65(self):
        """Quanto o *Regenerar C175* mudaria, **sem** aplicar nada.

        Existe por um motivo aprendido em arquivo real: o fluxo do modelo 65
        assume que o XML é a verdade e o C175 é que pode estar errado. Nem
        sempre é. Num caso concreto, o PDV emitiu parte das NFC-e com alíquota
        de não-cumulativo enquanto a empresa é cumulativa — a escrituração
        estava certa e o XML errado, e regenerar **aumentaria** o tributo
        declarado. Ver o valor antes de aplicar é o que separa uma correção de
        um estrago.

        Como a consolidação apenas agrupa (não altera somas), o total do C175
        regenerado é a soma dos itens; por isso a prévia não precisa repetir a
        lógica de agrupamento.

        Devolve `{"atual": {...}, "novo": {...}, "delta": {...}, "docs": n}`.
        """
        if self.layout != "CONTRIB":
            return None
        i_mod = self._ix("C100", "COD_MOD")
        a = {"pis": 0.0, "cofins": 0.0, "opr": 0.0}
        n = {"pis": 0.0, "cofins": 0.0, "opr": 0.0}
        c175_idx = {c: self._ix("C175", c)
                    for c in ("VL_PIS", "VL_COFINS", "VL_OPR")}
        c170_idx = {c: self._ix("C170", c)
                    for c in ("VL_PIS", "VL_COFINS", "VL_ITEM", "VL_DESC")}
        docs = 0
        for c100 in self.registros:
            if c100.reg != "C100":
                continue
            if (c100.valor(i_mod) or "").strip() != "65":
                continue
            itens = [f for f in (c100.filhos or []) if f.reg == "C170"]
            if not itens:
                continue          # sem fictícios, nada mudaria neste documento
            docs += 1
            # o VL_OPR que a regeneração vai gravar inclui o rateio
            rateios = self.rateio_acessorios(
                sum(_to_num(c100.valor(self._ix("C100", nome)))
                    for nome in ("VL_FRT", "VL_SEG", "VL_OUT_DA")),
                [_to_num(f.valor(c170_idx["VL_ITEM"])) for f in itens])
            for f in c100.filhos or []:
                if f.reg == "C175":
                    a["pis"] += _to_num(f.valor(c175_idx["VL_PIS"]))
                    a["cofins"] += _to_num(f.valor(c175_idx["VL_COFINS"]))
                    a["opr"] += _to_num(f.valor(c175_idx["VL_OPR"]))
            for pos, f in enumerate(itens):
                n["pis"] += _to_num(f.valor(c170_idx["VL_PIS"]))
                n["cofins"] += _to_num(f.valor(c170_idx["VL_COFINS"]))
                n["opr"] += (_to_num(f.valor(c170_idx["VL_ITEM"]))
                             - _to_num(f.valor(c170_idx["VL_DESC"]))
                             + rateios[pos])
        arred = lambda d: {k: round(v, 2) for k, v in d.items()}
        return {"atual": arred(a), "novo": arred(n), "docs": docs,
                "delta": {k: round(n[k] - a[k], 2) for k in a}}

    def regenerar_c175_de_c170_65(self):
        """Para cada C100 modelo 65 com C170 fictícios, regenera o C175 a partir
        dos itens (aplicando eventuais correções feitas neles) e **remove** os
        C170 fictícios, restaurando a estrutura consolidada do modelo 65.
        Retorna a quantidade de documentos e de C175 gerados."""
        if self.layout != "CONTRIB":
            return {"erro": "Disponível apenas no EFD Contribuições."}
        i_mod = self._ix("C100", "COD_MOD")
        self._exigir_numeros(self._com_itens(
            [c for c in self.registros if c.reg == "C100"
             and (c.valor(i_mod) or "").strip() == "65"]))
        docs = c175 = 0
        with self.lote():
            for c100 in self.documentos_65_com_c170():
                c170s = [f for f in c100.filhos if f.reg == "C170"]
                itens = [_ItemC170View(self, f) for f in c170s]
                res = self.consolidar_c175_de_itens(c100, itens)
                if res:
                    c175 += res.get("criados", 0)
                for f in c170s:
                    self.remover_registro(f)
                docs += 1
        return {"docs": docs, "c175": c175}

    # -------------------------------------------------------------------
    # Limpeza de campos preenchidos com "vazio" por extenso
    # -------------------------------------------------------------------
    # -------------------------------------------------------------------
    # Itens do 0200 — referências e limpeza do cadastro
    # -------------------------------------------------------------------
    def referencias_de_itens(self):
        """Onde os códigos do 0200 são citados no arquivo inteiro.

        Duas estratégias, de propósito:

        * registro com leiaute mapeado é lido pelo **nome** do campo
          (`COD_ITEM`) — preciso;
        * registro que o projeto ainda **não mapeia** é varrido por **valor**:
          qualquer campo cujo conteúdo seja um código do 0200 conta como
          referência. Desde a 0.39.0 o leiaute cobre os dois SPEDs inteiros
          (48 registros com `COD_ITEM` no ICMS/IPI, 21 no Contribuições), então
          essa via ficou para registros de versão mais nova que o leiaute.

        A varredura por valor erra **para mais** (pode contar coincidência
        como referência). Quando o passo seguinte é apagar cadastro, esse é o
        lado certo de errar.

        Devolve dict com `codigos`, `referenciados`, `por_registro` e
        `por_valor` (os tipos varridos pelo modo conservador).
        """
        i_cod = self._ix("0200", "COD_ITEM")
        codigos = set()
        if i_cod is not None:
            for r in self.registros:
                if r.reg == "0200":
                    v = (r.valor(i_cod) or "").strip()
                    if v:
                        codigos.add(v)

        # o próprio PVA diz quais campos apontam para o 0200
        # (`referenciaPesquisa="0200;COD_ITEM"` no descritor) — melhor que
        # supor que o campo se chama sempre COD_ITEM
        campos_ref = {}
        try:
            est, _i = referencias.atual().estrutura(self.layout)
            for (reg, campo), (alvo, campo_alvo) in \
                    referencias.do_descritor(est).items():
                if alvo == "0200" and campo_alvo == "COD_ITEM":
                    campos_ref.setdefault(reg, set()).add(campo)
        except Exception:                                   # noqa: BLE001
            campos_ref = {}

        referenciados = set()
        por_registro = {}
        por_valor = set()
        idx_cache = {}
        for r in self.registros:
            if r.reg == "0200" or not codigos:
                continue
            if r.reg not in idx_cache:
                mapeado = num_campos_esperado(r.reg, self.layout) is not None
                idx = [self._ix(r.reg, c) for c in campos_ref.get(r.reg, ())]
                idx = [x for x in idx if x is not None]
                if not idx:
                    um = self._ix(r.reg, "COD_ITEM")
                    idx = [um] if um is not None else []
                idx_cache[r.reg] = (idx, mapeado)
            indices, mapeado = idx_cache[r.reg]
            i = indices[0] if indices else None
            achou = False
            if indices:
                for k in indices:
                    v = (r.valor(k) or "").strip()
                    if v in codigos:
                        referenciados.add(v)
                        achou = True
            elif not mapeado:
                # sem leiaute: procura o código em qualquer campo
                for j, v in enumerate(r.campos):
                    if j == 0:
                        continue
                    v = (v or "").strip()
                    if v and v in codigos:
                        referenciados.add(v)
                        achou = True
                        por_valor.add(r.reg)
            if achou:
                por_registro[r.reg] = por_registro.get(r.reg, 0) + 1
        return {"codigos": codigos, "referenciados": referenciados,
                "por_registro": por_registro, "por_valor": por_valor}

    def itens_0200_nao_utilizados(self, refs=None):
        """Registros 0200 cujo código não aparece em nenhum outro registro.
        **Não altera nada.** Devolve `[(registro, cod_item, descricao)]`."""
        if refs is None:
            refs = self.referencias_de_itens()
        i_cod = self._ix("0200", "COD_ITEM")
        i_desc = self._ix("0200", "DESCR_ITEM")
        if i_cod is None:
            return []
        usados = refs["referenciados"]
        out = []
        for r in self.registros:
            if r.reg != "0200":
                continue
            cod = (r.valor(i_cod) or "").strip()
            if not cod or cod in usados:
                continue
            out.append((r, cod,
                        (r.valor(i_desc) or "").strip() if i_desc is not None
                        else ""))
        return out

    def remover_itens_0200(self, registros):
        """Remove os 0200 informados, com toda a subárvore (0205, 0206, 0220…).

        Recebe a lista já exibida ao usuário, para apagar exatamente o que ele
        viu. Devolve quantos registros saíram ao todo.
        """
        alvos = [r for r in registros if getattr(r, "reg", "") == "0200"]
        filhos = sum(len(r.filhos) for r in alvos)
        antes = len(self.registros)
        for r in alvos:
            self.remover_registro(r)
        self._cad_itens = None
        self.atualizar_bloco9_inplace()
        return {"itens": len(alvos), "filhos": filhos,
                "registros": antes - len(self.registros)}

    # -------------------------------------------------------------------
    # COD_CTA — conta contábil (obrigatória nos perfis A e B)
    # -------------------------------------------------------------------
    def data_final(self):
        """DT_FIN do 0000 (DDMMAAAA), ou `""`. É a data de referência das
        tabelas com vigência."""
        i_fim = self._ix("0000", "DT_FIN")
        for r in self.registros:
            if r.reg == "0000":
                return (r.valor(i_fim) or "").strip()
        return ""

    def perfil(self):
        """Perfil declarado no 0000 (`A`, `B` ou `C`). O COD_CTA só é exigido
        nos perfis A e B."""
        i = self._ix("0000", "IND_PERFIL")
        for r in self.registros:
            if r.reg == "0000" and i is not None:
                return (r.valor(i) or "").strip().upper()
        return ""

    def contas_0500(self):
        """Plano de contas do arquivo. Devolve
        `[(cod_cta, nome, nat_cc, ind_cta, nivel)]`."""
        idx = {c: self._ix("0500", c) for c in ("COD_CTA", "NOME_CTA",
                                                "COD_NAT_CC", "IND_CTA",
                                                "NIVEL")}
        out = []
        for r in self.registros:
            if r.reg != "0500":
                continue
            out.append(tuple((r.valor(idx[c]) or "").strip()
                             for c in ("COD_CTA", "NOME_CTA", "COD_NAT_CC",
                                       "IND_CTA", "NIVEL")))
        return out

    def registros_sem_cod_cta(self, tipo=None):
        """Registros com o campo COD_CTA vazio, agrupados por tipo quando
        `tipo` é None. Devolve `{tipo: [registros]}` ou a lista do tipo."""
        por_tipo = {}
        for r in self.registros:
            i = self._ix(r.reg, "COD_CTA")
            if i is None or i >= len(r.campos):
                continue
            if (r.valor(i) or "").strip():
                continue
            por_tipo.setdefault(r.reg, []).append(r)
        if tipo is not None:
            return por_tipo.get(tipo, [])
        return por_tipo

    def criar_conta_0500(self, cod_cta, nome_cta, nat_cc="01", ind_cta="A",
                         nivel="1", dt_alt=None):
        """Cria a conta no plano de contas (0500), se ainda não existir.

        O 0500 entra no bloco 0 **na posição do leiaute** — depois do último
        registro de código menor que 0500 —, senão o PVA recusa a ordem.
        """
        i_cod = self._ix("0500", "COD_CTA")
        for r in self.registros:
            if (r.reg == "0500"
                    and (r.valor(i_cod) or "").strip() == cod_cta):
                return None                     # já existe
        r0001 = next((r for r in self.registros if r.reg == "0001"), None)
        if r0001 is None:
            return None
        # o tamanho tem de ser medido ANTES de criar: `_ncampos` usa a moda
        # dos registros do tipo já presentes, e o recém-criado nasce com um
        # campo só — consultar depois devolveria 1 e geraria `|0500|`.
        n_campos = self._ncampos("0500")
        ancora = r0001
        for r in self.registros:
            if r.bloco == "0" and r.reg < "0500" and r.reg != "0000":
                ancora = r
        novo = self.novo_registro("0500", pai=r0001, depois=ancora)
        novo.campos = ["0500"] + [""] * (n_campos - 1)
        if dt_alt is None:
            i_ini = self._ix("0000", "DT_INI")
            dt_alt = next(((r.valor(i_ini) or "").strip()
                           for r in self.registros if r.reg == "0000"), "")
        for campo, valor in (("DT_ALT", dt_alt), ("COD_NAT_CC", nat_cc),
                             ("IND_CTA", ind_cta), ("NIVEL", str(nivel)),
                             ("COD_CTA", cod_cta), ("NOME_CTA", nome_cta)):
            i = self._ix("0500", campo)
            if i is not None and i < len(novo.campos):
                novo.set_valor(i, valor)
        return novo

    def preencher_cod_cta(self, tipo, cod_cta, registros=None,
                          criar_0500=True, nome_cta=None, nat_cc="01",
                          ind_cta="A", nivel="1"):
        """Preenche o COD_CTA dos registros de `tipo` que estão sem conta.

        Só toca no que está **vazio** — conta já informada é escolha do
        contribuinte. Com `criar_0500`, cadastra a conta no plano de contas
        quando ela ainda não existe ali.
        """
        cod_cta = (cod_cta or "").strip()
        if not cod_cta:
            return {"erro": "Informe o código da conta contábil."}
        i = self._ix(tipo, "COD_CTA")
        if i is None:
            return {"erro": "O registro %s não tem o campo COD_CTA." % tipo}
        if registros is None:
            registros = self.registros_sem_cod_cta(tipo)
        n = 0
        for r in registros:
            if r.reg != tipo or i >= len(r.campos):
                continue
            if (r.valor(i) or "").strip():
                continue
            r.set_valor(i, cod_cta)
            n += 1
        conta = None
        if criar_0500 and n:
            conta = self.criar_conta_0500(cod_cta, nome_cta or cod_cta,
                                          nat_cc, ind_cta, nivel)
        self.atualizar_bloco9_inplace()
        return {"registros": n, "tipo": tipo, "cod_cta": cod_cta,
                "conta_criada": conta is not None}

    # -------------------------------------------------------------------
    # COD_GEN do 0200 — capítulo do NCM (Tabela 4.2.1)
    # -------------------------------------------------------------------
    def divergencias_cod_gen(self):
        """Itens do 0200 cujo `COD_GEN` não é o capítulo do `COD_NCM`.
        **Não altera nada.** Devolve `[(registro, cod_item, ncm, atual, novo)]`.

        O gênero são os **dois primeiros dígitos do NCM**, então é derivável e
        não precisa vir de planilha — ainda bem: calcular `LEFT(ncm; 2)` numa
        célula numérica dá `40` para o NCM `04012010`, porque a planilha já
        comeu o zero. Aqui o NCM é normalizado antes de cortar.

        Item sem NCM de 8 dígitos (serviço, por exemplo) fica de fora: não há
        capítulo de onde tirar o gênero.
        """
        i_cod = self._ix("0200", "COD_ITEM")
        i_ncm = self._ix("0200", "COD_NCM")
        i_gen = self._ix("0200", "COD_GEN")
        if i_ncm is None or i_gen is None:
            return []
        out = []
        for r in self.registros:
            if r.reg != "0200":
                continue
            ncm = _zero_a_esquerda((r.valor(i_ncm) or "").strip(), 8)
            if len(ncm) != 8 or not ncm.isdigit():
                continue
            atual = (r.valor(i_gen) or "").strip()
            if atual != ncm[:2]:
                out.append((r, (r.valor(i_cod) or "").strip(), ncm, atual,
                            ncm[:2]))
        return out

    def preencher_cod_gen(self, ocorrencias=None):
        """Grava o `COD_GEN` derivado do NCM. Recebe a lista já exibida ao
        usuário, para corrigir exatamente o que ele viu."""
        if ocorrencias is None:
            ocorrencias = self.divergencias_cod_gen()
        i_gen = self._ix("0200", "COD_GEN")
        vazios = 0
        for r, _cod, _ncm, atual, novo in ocorrencias:
            r.set_valor(i_gen, novo)
            if not atual:
                vazios += 1
        return {"itens": len(ocorrencias), "vazios": vazios,
                "trocados": len(ocorrencias) - vazios}

    # -------------------------------------------------------------------
    # Bloco H — inventário a partir de planilha
    # -------------------------------------------------------------------
    # chaves canônicas aceitas em cada linha da planilha importada
    CAMPOS_INVENTARIO = (
        "cod_item", "unid", "qtd", "vl_unit", "vl_item", "ind_prop",
        "cod_part", "txt_compl", "cod_cta", "vl_item_ir",
        "descr_item", "cod_barra", "tipo_item", "cod_ncm", "ex_ipi",
        "cod_gen", "aliq_icms", "cest")

    def comparar_inventario_h010(self, linhas, tol=0.001):
        """Compara o inventário **já escriturado** (H010) com a planilha, por
        código e quantidade — sem alterar nada no arquivo.

        Devolve dict com:
          divergentes -> [(cod, qtd_sped, qtd_planilha, dif)] quantidades que
                         não batem (diferença acima de `tol`);
          so_sped     -> [(cod, qtd)] itens no H010 e ausentes da planilha;
          so_planilha -> [(cod, qtd)] itens da planilha sem H010;
          iguais      -> quantos coincidem;
          tot_sped / tot_planilha -> somas das quantidades;
          sem_h010    -> True se o arquivo não tem inventário escriturado.
        """
        h_cod = self._ix("H010", "COD_ITEM")
        h_qtd = self._ix("H010", "QTD")
        atual = {}
        for r in self.registros:
            if r.reg != "H010":
                continue
            cod = (r.valor(h_cod) or "").strip()
            if cod:
                atual[cod] = atual.get(cod, 0.0) + _to_num(r.valor(h_qtd))

        def num(v):
            if isinstance(v, (int, float)):
                return float(v)
            return _to_num(v)

        plan = {}
        for ln in linhas:
            cod = _texto_planilha(ln.get("cod_item"))
            if cod:
                plan[cod] = plan.get(cod, 0.0) + num(ln.get("qtd"))

        divergentes, so_sped, so_planilha = [], [], []
        iguais = 0
        for cod in sorted(set(atual) | set(plan)):
            if cod not in plan:
                so_sped.append((cod, atual[cod]))
            elif cod not in atual:
                so_planilha.append((cod, plan[cod]))
            else:
                dif = round(plan[cod] - atual[cod], 6)
                if abs(dif) > tol:
                    divergentes.append((cod, atual[cod], plan[cod], dif))
                else:
                    iguais += 1
        return {"divergentes": divergentes, "so_sped": so_sped,
                "so_planilha": so_planilha, "iguais": iguais,
                "tot_sped": round(sum(atual.values()), 4),
                "tot_planilha": round(sum(plan.values()), 4),
                "sem_h010": not atual}

    def conferir_itens_inventario(self, linhas):
        """Compara os itens da planilha com o cadastro 0200 já existente, sem
        alterar nada. Devolve dict com:
          novos       -> códigos que não existem no 0200 (serão criados);
          existentes  -> códigos já cadastrados;
          divergentes -> [(cod, campo, valor_0200, valor_planilha)] quando a
                         descrição/unidade/NCM da planilha diferem do 0200;
          duplicados  -> códigos repetidos dentro da própria planilha;
          ncm_truncado-> [(cod, ncm_0200, ncm_planilha)] itens cujo NCM no
                         **0200 do arquivo** perdeu o zero à esquerda (tem 7
                         dígitos) — é erro do arquivo, não da planilha;
          sem_qtd / sem_valor -> itens com quantidade ou valor zerado.
        """
        i_cod = self._ix("0200", "COD_ITEM")
        i_desc = self._ix("0200", "DESCR_ITEM")
        i_unid = self._ix("0200", "UNID_INV")
        i_ncm = self._ix("0200", "COD_NCM")
        cad = {}
        for r in self.registros:
            if r.reg == "0200":
                cad[(r.valor(i_cod) or "").strip()] = r
        novos, existentes, divergentes, duplicados = [], [], [], []
        ncm_truncado = []
        vistos = set()
        sem_qtd = sem_valor = 0
        for ln in linhas:
            cod = _texto_planilha(ln.get("cod_item"))
            if not cod:
                continue
            if cod in vistos:
                duplicados.append(cod)
                continue
            vistos.add(cod)
            if not _to_num_planilha(ln.get("qtd")):
                sem_qtd += 1
            if not _to_num_planilha(ln.get("vl_item")):
                sem_valor += 1
            r = cad.get(cod)
            if r is None:
                novos.append(cod)
                continue
            existentes.append(cod)
            for chave, idx, rot in (("descr_item", i_desc, "DESCR_ITEM"),
                                    ("unid", i_unid, "UNID_INV"),
                                    ("cod_ncm", i_ncm, "COD_NCM")):
                novo = _texto_planilha(ln.get(chave))
                if chave == "cod_ncm":          # a célula numérica perde o zero
                    novo = _zero_a_esquerda(novo, 8)
                if not novo or idx is None:
                    continue
                atual = (r.valor(idx) or "").strip()
                if not atual or atual.upper() == novo.upper():
                    continue
                if chave == "cod_ncm" and _zero_a_esquerda(atual, 8) == novo:
                    # mesmo NCM: quem está truncado é o 0200 do arquivo
                    ncm_truncado.append((cod, atual, novo))
                else:
                    divergentes.append((cod, rot, atual, novo))
        return {"novos": novos, "existentes": existentes,
                "divergentes": divergentes, "duplicados": duplicados,
                "ncm_truncado": ncm_truncado,
                "sem_qtd": sem_qtd, "sem_valor": sem_valor}

    @staticmethod
    def _mudancas_item_0200(reg, ln, z):
        """Diferenças entre um registro 0200 e a linha da planilha.

        Devolve `[(campo, indice, atual, novo)]`. Duas regras que evitam
        estrago: coluna **não mapeada** ou célula **vazia** não mexem no que
        já está lá (senão uma coluna em branco varreria o cadastro), e a
        alíquota é comparada como **número** — `18,00` e `18` são o mesmo
        valor e não deveriam contar como mudança.
        """
        out = []
        for chave, campo in CAMPOS_0200:
            if chave not in ln:
                continue
            novo = _valor_0200(chave, ln)
            i = z.get(campo)
            if not novo or i is None or i >= len(reg.campos):
                continue
            atual = (reg.valor(i) or "").strip()
            if atual == novo:
                continue
            if campo == "ALIQ_ICMS" and _to_num(atual) == _to_num(novo):
                continue
            out.append((campo, i, atual, novo))
        return out

    def previa_atualizacao_0200(self, linhas):
        """O que a planilha mudaria no cadastro 0200 já existente, **sem
        alterar nada**. Devolve `{campo: [(cod_item, atual, novo)]}`.

        Serve para escolher campo a campo antes de aplicar: num arquivo real,
        corrigir o NCM era acerto, mas a mesma planilha traria `TIPO_ITEM`
        inválido para 1.273 itens que estavam certos.
        """
        i_cod = self._ix("0200", "COD_ITEM")
        z = {c: self._ix("0200", c) for _k, c in CAMPOS_0200}
        cad = {}
        for r in self.registros:
            if r.reg == "0200":
                cad[(r.valor(i_cod) or "").strip()] = r
        prev = {}
        vistos = set()
        for ln in linhas:
            cod = _texto_planilha(ln.get("cod_item"))
            if not cod or cod in vistos:
                continue
            vistos.add(cod)
            reg = cad.get(cod)
            if reg is None:
                continue
            for campo, _i, atual, novo in self._mudancas_item_0200(reg, ln, z):
                prev.setdefault(campo, []).append((cod, atual, novo))
        return prev

    def atualizar_0200(self, linhas, campos):
        """Corrige o cadastro 0200 **já existente** com as `linhas` (da
        planilha ou do banco do ERP), só nos `campos` escolhidos (nomes do
        0200). É a aplicação da `previa_atualizacao_0200`: a mesma regra —
        valor vazio não apaga, alíquota comparada como número.

        Devolve `({campo: quantos itens}, {códigos alterados})`."""
        i_cod = self._ix("0200", "COD_ITEM")
        z = {c: self._ix("0200", c) for _k, c in CAMPOS_0200}
        cad = {}
        for r in self.registros:
            if r.reg == "0200":
                cad.setdefault((r.valor(i_cod) or "").strip(), r)
        contagem, itens, vistos = {}, set(), set()
        for ln in linhas:
            cod = _texto_planilha(ln.get("cod_item"))
            if not cod or cod in vistos:
                continue
            vistos.add(cod)
            reg = cad.get(cod)
            if reg is None:
                continue
            for campo, i, _atual, novo in self._mudancas_item_0200(reg, ln, z):
                if campo in campos:
                    reg.set_valor(i, novo)
                    contagem[campo] = contagem.get(campo, 0) + 1
                    itens.add(cod)
        if itens:
            self._cad_itens = None
        return contagem, itens

    def avisos_previa_0200(self, linhas, previa=None):
        """Riscos de cada campo de uma atualização de 0200, para o diálogo
        avisar **antes** de gravar. Devolve
        `{campo: (quantidade, texto, desmarcar)}`.

        `desmarcar=True` quer dizer "o valor novo é objetivamente inválido" —
        aí o campo nasce desmarcado. Alíquota indo a zero é decisão fiscal
        legítima, então avisa mas continua marcada.
        """
        if previa is None:
            previa = self.previa_atualizacao_0200(linhas)
        avisos = {}

        maus = [(c, novo) for c, _a, novo in previa.get("TIPO_ITEM", [])
                if novo not in TIPOS_ITEM_0200]
        if maus:
            avisos["TIPO_ITEM"] = (
                len(maus),
                "valor fora da tabela oficial do 0200 (%s; só 00 a 10 e 99): "
                "trocaria um código válido por um inválido e o PVA recusa"
                % ", ".join(sorted({v for _c, v in maus})), True)

        # o gênero é o capítulo do NCM; divergir denuncia LEFT(ncm;2) feito
        # sobre uma célula que já tinha perdido o zero à esquerda
        ncm_item = {}
        for ln in linhas:
            cod = _texto_planilha(ln.get("cod_item"))
            if cod and cod not in ncm_item:
                ncm_item[cod] = _zero_a_esquerda(
                    _texto_planilha(ln.get("cod_ncm")), 8)
        fora = [(c, novo, ncm_item[c][:2])
                for c, _a, novo in previa.get("COD_GEN", [])
                if len(ncm_item.get(c, "")) == 8
                and novo != ncm_item[c][:2]]
        if fora:
            c, novo, certo = fora[0]
            avisos["COD_GEN"] = (
                len(fora),
                "não é o capítulo do NCM (ex.: item %s receberia %s onde o "
                "NCM pede %s). É o sintoma de LEFT(NCM;2) sobre célula que "
                "perdeu o zero à esquerda — use \"Preencher COD_GEN pelo "
                "NCM\", que deriva do próprio arquivo" % (c, novo, certo),
                True)

        zerados = [c for c, a, b in previa.get("ALIQ_ICMS", [])
                   if _to_num(b) == 0 and _to_num(a) != 0]
        if zerados:
            avisos["ALIQ_ICMS"] = (
                len(zerados),
                "ficariam com a alíquota de ICMS zerada — é mudança de "
                "tributação, não de cadastro; confirme que é isso mesmo",
                False)
        return avisos

    def importar_inventario_h010(self, linhas, dt_inv, mot_inv="01",
                                 ind_prop_padrao="0", criar_0200=True,
                                 substituir=True, atualizar_0200=False):
        """(EFD ICMS/IPI) Gera o inventário do **bloco H** a partir das `linhas`
        de uma planilha — uma por item, com as chaves de `CAMPOS_INVENTARIO`.

        Cria/atualiza H001 (IND_MOV=0), um H005 com a data e o motivo do
        inventário, e um **H010** por item. Para manter a coerência com o
        cadastro, itens que ainda não existem no **0200** são criados (com
        descrição, unidade, tipo e NCM da planilha), sem duplicar os já
        cadastrados; as unidades novas também geram registros **0190**.

        `dt_inv` no formato DDMMAAAA. Com `substituir=True`, H005/H010 anteriores
        são removidos.

        Com `atualizar_0200=True`, o cadastro dos itens que **já existem** é
        corrigido com os dados da planilha — é para quando o 0200 do arquivo
        é que está errado (NCM truncado, descrição velha). Só mexe nas colunas
        que foram mapeadas, e célula vazia não apaga o que está lá.

        Devolve um resumo do que foi criado e corrigido.
        """
        if self.layout != "ICMS":
            return {"erro": "O bloco H (inventário) é do EFD ICMS/IPI."}

        # confere todas as células numéricas antes de mexer em qualquer
        # coisa: "abc" ou "NULL" na quantidade não pode virar zero calado
        ruins = []
        for k, ln in enumerate(linhas, 1):
            if not _texto_planilha(ln.get("cod_item")):
                continue
            for chave in ("qtd", "vl_unit", "vl_item", "vl_item_ir",
                          "aliq_icms"):
                try:
                    num_planilha_estrito(ln.get(chave))
                except ValueError:
                    ruins.append((ln.get("_linha", k), chave, ln.get(chave)))
        if ruins:
            raise CelulasInvalidas(ruins)

        h = {c: self._ix("H010", c) for c in (
            "COD_ITEM", "UNID", "QTD", "VL_UNIT", "VL_ITEM", "IND_PROP",
            "COD_PART", "TXT_COMPL", "COD_CTA", "VL_ITEM_IR")}
        z = {c: self._ix("0200", c) for c in (
            "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "UNID_INV", "TIPO_ITEM",
            "COD_NCM", "EX_IPI", "COD_GEN", "ALIQ_ICMS", "CEST")}
        n_h010 = self._ncampos("H010")
        n_h005 = self._ncampos("H005")
        n_0200 = self._ncampos("0200")
        n_0190 = self._ncampos("0190")

        def setv(reg, idx, valor):
            if idx is not None and idx < len(reg.campos):
                reg.set_valor(idx, valor)

        # ---- bloco H: abertura e limpeza -------------------------------
        h001 = next((r for r in self.registros if r.reg == "H001"), None)
        if h001 is None:
            ancora = next((r for r in reversed(self.registros)
                           if r.reg.startswith("G") or r.reg.startswith("E")
                           or r.reg.startswith("D") or r.reg.startswith("C")),
                          None)
            h001 = self.novo_registro("H001", depois=ancora)
            h001.campos = ["H001", "0"]
        else:
            setv(h001, 1, "0")            # IND_MOV = 0 (com dados)
        if substituir:
            for r in [x for x in self.registros if x.reg in ("H005", "H010",
                                                             "H020")]:
                self.remover_registro(r)

        h005 = self.novo_registro("H005", pai=h001, depois=h001)
        h005.campos = ["H005"] + [""] * (n_h005 - 1)
        setv(h005, self._ix("H005", "DT_INV"), dt_inv)
        setv(h005, self._ix("H005", "MOT_INV"), mot_inv)

        # ---- cadastro 0200 / 0190 já existentes ------------------------
        cad = {}
        for r in self.registros:
            if r.reg == "0200":
                cad[(r.valor(z["COD_ITEM"]) or "").strip()] = r
        i_u190 = self._ix("0190", "UNID")
        unids = {(r.valor(i_u190) or "").strip().upper()
                 for r in self.registros if r.reg == "0190"}
        ult_0200 = None
        ult_0190 = None
        for r in self.registros:
            if r.reg == "0200":
                ult_0200 = r
            elif r.reg == "0190":
                ult_0190 = r
        r0001 = next((r for r in self.registros if r.reg == "0001"), None)

        # ---- itens -----------------------------------------------------
        ancora_h = h005
        total = 0.0
        n_itens = n_novos_0200 = n_novos_0190 = 0
        vistos = set()
        ignorados = []

        # já conferido no início: aqui só converte
        num = num_planilha_estrito

        # a planilha é a fonte: corrige o cadastro que já existia, só nos
        # campos escolhidos (campo -> quantos itens; itens alterados)
        if atualizar_0200 is True:
            corrigir = {c for _k, c in CAMPOS_0200}
        else:
            corrigir = set(atualizar_0200 or ())
        campos_0200, itens_0200 = self.atualizar_0200(linhas, corrigir)

        for ln in linhas:
            cod = _texto_planilha(ln.get("cod_item"))
            if not cod or cod in vistos:
                if cod:
                    ignorados.append(cod)
                continue
            vistos.add(cod)
            unid = _texto_planilha(ln.get("unid"))
            qtd = num(ln.get("qtd"))
            vl_unit = num(ln.get("vl_unit"))
            vl_item = num(ln.get("vl_item"))
            if not vl_item and qtd and vl_unit:
                vl_item = qtd * vl_unit
            # arredonda **aqui**, num ponto só: é o mesmo número que vai para o
            # H010 e para o total do H005. Somar o valor bruto e arredondar no
            # fim deixava o VL_INV um centavo fora da soma dos itens.
            vl_item = round(vl_item, 2)
            if not vl_unit and qtd:
                vl_unit = round(vl_item / qtd, 6) if qtd else 0.0

            reg = self.novo_registro("H010", pai=h005, depois=ancora_h)
            reg.campos = ["H010"] + [""] * (n_h010 - 1)
            setv(reg, h["COD_ITEM"], cod)
            setv(reg, h["UNID"], unid)
            setv(reg, h["QTD"], _fmt_qtd(qtd))
            setv(reg, h["VL_UNIT"], _fmt_qtd(vl_unit))
            setv(reg, h["VL_ITEM"], _fmt_val(vl_item))
            setv(reg, h["IND_PROP"],
                 _texto_planilha(ln.get("ind_prop")) or ind_prop_padrao)
            for chave, campo in (("cod_part", "COD_PART"),
                                 ("txt_compl", "TXT_COMPL"),
                                 ("cod_cta", "COD_CTA")):
                v = _texto_planilha(ln.get(chave))
                if v:
                    setv(reg, h[campo], v)
            # VL_ITEM_IR é valor: sem isto ia para o arquivo o `str()` do float
            # da planilha ("11.24", "155.7"), com ponto e sem as duas casas.
            if _texto_planilha(ln.get("vl_item_ir")):
                setv(reg, h["VL_ITEM_IR"], _fmt_val(num(ln.get("vl_item_ir"))))
            ancora_h = reg
            total += vl_item
            n_itens += 1

            # cadastro 0200 do item, se ainda não existir
            if criar_0200 and cod not in cad and r0001 is not None:
                novo = self.novo_registro(
                    "0200", pai=r0001,
                    depois=(ult_0200 or self._ancora_antes(r0001, "0200")))
                novo.campos = ["0200"] + [""] * (n_0200 - 1)
                setv(novo, z["COD_ITEM"], cod)
                for chave, campo in CAMPOS_0200:
                    v = _valor_0200(chave, ln)
                    if v:
                        setv(novo, z[campo], v)
                cad[cod] = novo
                ult_0200 = novo
                n_novos_0200 += 1

            # unidade nova -> 0190
            if unid and unid.upper() not in unids and r0001 is not None:
                u = self.novo_registro(
                    "0190", pai=r0001,
                    depois=(ult_0190 or self._ancora_antes(r0001, "0190")))
                u.campos = ["0190"] + [""] * (n_0190 - 1)
                setv(u, self._ix("0190", "UNID"), unid)
                setv(u, self._ix("0190", "DESCR"), unid)
                unids.add(unid.upper())
                ult_0190 = u
                n_novos_0190 += 1

        setv(h005, self._ix("H005", "VL_INV"), _fmt_val(round(total, 2)))

        # ---- encerramento do bloco -------------------------------------
        # Arquivo sem bloco H nenhum não tem H990, e sem ele o PVA recusa o
        # arquivo inteiro. A contagem quem preenche é atualizar_bloco9_inplace.
        h990 = next((r for r in self.registros if r.reg == "H990"), None)
        if h990 is None:
            h990 = self.novo_registro("H990", depois=ancora_h)
            h990.campos = ["H990"] + [""] * (self._ncampos("H990") - 1)

        self._cad_itens = None
        self.atualizar_bloco9_inplace()
        return {"itens": n_itens, "vl_inv": round(total, 2),
                "novos_0200": n_novos_0200, "novos_0190": n_novos_0190,
                "ignorados": ignorados,
                "atualizados_0200": len(itens_0200),
                "campos_0200": campos_0200}

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
        # os totais dos C100 dos itens também são refeitos
        pais = {id(r.pai): r.pai for r in alvos
                if r.pai is not None and r.pai.reg == "C100"}
        self._exigir_numeros(list(alvos) + list(pais.values()))

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
            # documento consolidado (C175) soma só o C175: os C170 que
            # convivem com ele são os fictícios da validação por XML, e
            # somar os dois dobrava o VL_PIS/VL_COFINS do C100
            fonte = ("C175" if any(f.reg == "C175" for f in c100.filhos)
                     else "C170")
            for f in c100.filhos:
                if f.reg == fonte:
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

    # ------------------------------------------- receita do bloco M (CONTRIB)
    # Campos de PIS/COFINS nos registros de item: (cst, bc, valor da operação,
    # alíquota). O C175 consolida a NFC-e, que não tem C170.
    CAMPOS_RECEITA = {
        ("PIS", "C175"): (4, 5, 2, 6),
        ("PIS", "C170"): (24, 25, 6, 26),
        ("COFINS", "C175"): (10, 11, 2, 12),
        ("COFINS", "C170"): (30, 31, 6, 32),
    }
    # Registros que também carregam receita, fora dos documentos do bloco C.
    # A conferência do bloco M não os soma; quando existem, ela se declara
    # PARCIAL em vez de acusar diferença que o arquivo não tem.
    RECEITA_FORA_DO_BLOCO_C = ("A170", "D201", "D205", "D300", "D350", "D601",
                               "F100", "F200", "F500", "F510", "F525", "F550",
                               "F560")

    def saidas_c100(self):
        """Documentos do C100 de saída (IND_OPER = 1)."""
        i_op = self._ix("C100", "IND_OPER")
        if i_op is None:
            return []
        return [r for r in self.registros
                if r.reg == "C100" and (r.valor(i_op) or "").strip() == "1"]

    def receita_tributada_por_aliquota(self, tributo):
        """Agrupa a receita TRIBUTADA de saída por alíquota.

        `{"1.6500": {"aliq": "1,65", "rec": ..., "bc": ...}}`. Só entra item
        com base e alíquota positivas — é o que vira M210/M610.
        """
        grupos = {}
        for c100 in self.saidas_c100():
            for f in c100.filhos:
                idx = self.CAMPOS_RECEITA.get((tributo, f.reg))
                if idx is None:
                    continue
                _i_cst, i_bc, i_opr, i_al = idx
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

    def receita_por_cst(self, tributo):
        """Soma a receita de saída por CST, tributada ou não: `{cst: valor}`.

        É o lastro do M400/M800 (receitas isentas, não alcançadas, a alíquota
        zero ou com suspensão), que o PVA confere contra os documentos.
        """
        soma = {}
        for c100 in self.saidas_c100():
            for f in c100.filhos:
                idx = self.CAMPOS_RECEITA.get((tributo, f.reg))
                if idx is None:
                    continue
                i_cst, _i_bc, i_opr, _i_al = idx
                cst = (f.valor(i_cst) or "").strip()
                soma[cst] = soma.get(cst, 0.0) + _to_num(f.valor(i_opr))
        return soma

    def receita_parcial(self):
        """Registros de receita fora dos documentos do bloco C, se houver.

        Havendo, a conferência do bloco M não fecha por construção — e dizer
        "confere parcialmente" é melhor que acusar diferença inexistente.
        """
        tipos = {r.reg for r in self.registros}
        return sorted(t for t in self.RECEITA_FORA_DO_BLOCO_C if t in tipos)

    # Alíquota básica do regime não-cumulativo, por tributo. Só ela é
    # "alíquota básica" (tipo de crédito 01); qualquer outra é diferenciada.
    ALIQ_BASICA_NC = {"PIS": 1.65, "COFINS": 7.6}
    # Registros que também geram crédito fora dos documentos do bloco C. Tendo
    # algum, o crédito não sai só do C170 e o recálculo se abstém.
    CREDITO_FORA_DO_BLOCO_C = ("D101", "D105", "D501", "D505", "F100", "F120",
                               "F130", "F150", "F500", "F510", "F525", "F550",
                               "F560", "1100", "1500")
    # Ajustes de crédito: são filhos do M100/M500 e não há como reatribuí-los
    # a grupos refeitos, então a presença deles também trava o recálculo.
    AJUSTES_DE_CREDITO = ("M110", "M115", "M510", "M515")

    def creditos_por_aliquota(self, tributo, naturezas):
        """Base de crédito das ENTRADAS, agrupada como o PVA agrupa.

        Devolve `({chave_aliq: {"aliq", "base", "grupos"}}, ignorados)`, com
        `grupos` = `{(NAT_BC_CRED, CST): base}` — a mesma chave do M105 — e
        `ignorados` = itens com CST de crédito num CFOP fora da tabela 4.3.7,
        que não geram crédito e por isso ficam de fora (é o que a regra
        `MSG_COMPATIBILIDADE_CFOP_CRED` acusa).

        A natureza vem do CFOP pela tabela do próprio PVA: num arquivo real,
        esse agrupamento reproduziu o rateio que o contribuinte já tinha no
        M105, inclusive o único item de natureza 02.
        """
        i_op = self._ix("C100", "IND_OPER")
        i_cfop = self._ix("C170", "CFOP")
        i_cst = self._ix("C170", "CST_%s" % tributo)
        i_bc = self._ix("C170", "VL_BC_%s" % tributo)
        i_al = self._ix("C170", "ALIQ_%s" % tributo)
        if None in (i_op, i_cfop, i_cst, i_bc, i_al):
            return {}, 0
        grupos, ignorados = {}, 0
        for c100 in self.registros:
            if c100.reg != "C100" or (c100.valor(i_op) or "").strip() != "0":
                continue
            for f in c100.filhos:
                if f.reg != "C170":
                    continue
                cst = (f.valor(i_cst) or "").strip()
                if cst not in CST_CREDITO:
                    continue
                bc = _to_num(f.valor(i_bc))
                al = _to_num(f.valor(i_al))
                if bc <= 0 or al <= 0:
                    continue
                nat = naturezas.get((f.valor(i_cfop) or "").strip())
                if not nat:
                    ignorados += 1
                    continue
                k = "%.4f" % al
                g = grupos.setdefault(k, {"aliq": f.valor(i_al), "base": 0.0,
                                          "grupos": {}})
                g["base"] += bc
                g["grupos"][(nat, cst)] = g["grupos"].get((nat, cst), 0.0) + bc
        return grupos, ignorados

    def _motivo_para_nao_refazer_creditos(self, cod_inc):
        """Por que não dá para refazer o crédito, ou "" quando dá."""
        if cod_inc != "1":
            return ("o 0110 não declara incidência exclusivamente "
                    "não-cumulativa (COD_INC_TRIB %s): a divisão da base "
                    "entre os regimes não sai dos documentos" % cod_inc)
        tipos = {r.reg for r in self.registros}
        ajustes = [t for t in self.AJUSTES_DE_CREDITO if t in tipos]
        if ajustes:
            return ("o arquivo tem ajustes de crédito (%s), que são filhos "
                    "do M100/M500 e não há como reatribuir"
                    % ", ".join(ajustes))
        fora = [t for t in self.CREDITO_FORA_DO_BLOCO_C if t in tipos]
        if fora:
            return ("há crédito fora dos documentos do bloco C (%s)"
                    % ", ".join(fora))
        return ""

    def _refazer_creditos(self, tributo, debito, naturezas):
        """Refaz M100/M105 (PIS) ou M500/M505 (COFINS) a partir das entradas.

        Um M100 por alíquota, com um M105 por (natureza, CST) dentro dele — é
        exatamente como o PVA confere: ele soma os documentos por natureza,
        CST e alíquota e recusa registro que não corresponda a nada
        (`MSG_M105_NAO_DEVE_EXISTIR`) ou cujo total não bata
        (`MSG_VL_BC_PIS_TOT`).

        O crédito disponível é descontado até o limite do **débito do
        período**, na ordem das alíquotas; o que sobra vira saldo. Devolve
        `{"descontado", "disponivel", "grupos", "ignorados"}`.
        """
        reg_m, reg_det = (("M100", "M105") if tributo == "PIS"
                          else ("M500", "M505"))
        grupos, ignorados = self.creditos_por_aliquota(tributo, naturezas)
        antigos = [r for r in self.registros if r.reg in (reg_m, reg_det)]

        # COD_CRED tem 3 dígitos: o **primeiro** é o tipo do crédito (1 =
        # alíquota básica, 2 = diferenciadas, 3 = por unidade de medida) e os
        # **dois últimos** são a vinculação da receita (01 tributada no
        # mercado interno, 02 não tributada, 03 exportação). A vinculação é
        # decisão do contribuinte e não está nos documentos, então vem do que
        # já existe no arquivo; só o tipo é redecidido pela alíquota.
        vinc, ind_ori = "01", "0"
        i_cod = self._ix(reg_m, "COD_CRED")
        i_ori = self._ix(reg_m, "IND_CRED_ORI")
        base_por_cod = {}
        for r in antigos:
            if r.reg != reg_m:
                continue
            cod = (r.valor(i_cod) or "").strip()
            if len(cod) == 3:
                base_por_cod[cod] = base_por_cod.get(cod, 0.0) + _to_num(
                    r.valor(self._ix(reg_m, "VL_BC_%s" % tributo)))
            if (r.valor(i_ori) or "").strip():
                ind_ori = (r.valor(i_ori) or "").strip()
        if base_por_cod:
            vinc = max(base_por_cod.items(), key=lambda x: x[1])[0][1:]

        # âncora e largura ANTES de criar: `_ncampos` mede pela moda dos
        # registros existentes, e o recém-criado nasce com um campo só
        n_m, n_det = self._ncampos(reg_m), self._ncampos(reg_det)
        m001 = next((r for r in self.registros if r.reg == "M001"), None)
        cons = next((r for r in self.registros
                     if r.reg == ("M200" if tributo == "PIS" else "M600")),
                    None)
        if m001 is None or not grupos:
            return {"descontado": 0.0, "disponivel": 0.0, "grupos": 0,
                    "ignorados": ignorados, "sem_credito": not grupos}
        # A âncora é o registro que **precede** o primeiro M100/M500 — não o
        # M001: o M500 vem depois do M200/M400 no leiaute, e ancorar na
        # abertura do bloco jogaria o crédito da COFINS para antes deles.
        primeiro = min(antigos, key=lambda r: r.ordem) if antigos else cons
        if primeiro is None:
            return {"descontado": 0.0, "disponivel": 0.0, "grupos": 0,
                    "ignorados": ignorados, "sem_credito": True}
        anteriores = [r for r in self.registros if r.ordem < primeiro.ordem]
        ancora = max(anteriores, key=lambda r: r.ordem) if anteriores else m001
        for r in antigos:
            self.remover_registro(r)

        basica = self.ALIQ_BASICA_NC.get(tributo, 0.0)
        falta = round(debito, 2)
        disponivel = descontado = 0.0
        for k in sorted(grupos, key=float):
            g = grupos[k]
            al = float(k)
            base = round(g["base"], 2)
            cred = round(base * al / 100.0, 2)
            desc = min(cred, falta) if falta > 0 else 0.0
            desc = round(desc, 2)
            falta = round(falta - desc, 2)
            saldo = round(cred - desc, 2)
            disponivel += cred
            descontado += desc

            novo = self.novo_registro(reg_m, pai=m001, depois=ancora)
            ancora = novo
            cod = ("1" if abs(al - basica) < 0.0001 else "2") + vinc
            campos = [""] * n_m
            campos[0] = reg_m
            for nome, valor in (("COD_CRED", cod), ("IND_CRED_ORI", ind_ori),
                                ("VL_BC_%s" % tributo, _fmt_val(base)),
                                ("ALIQ_%s" % tributo, g["aliq"]),
                                ("QUANT_BC_%s" % tributo, "0"),
                                ("VL_CRED", _fmt_val(cred)),
                                ("VL_AJUS_ACRES", "0"),
                                ("VL_AJUS_REDUC", "0"),
                                ("VL_CRED_DISP", _fmt_val(cred)),
                                ("IND_DESC_CRED", "0" if saldo <= 0 else "1"),
                                ("VL_CRED_DESC", _fmt_val(desc)),
                                ("SLD_CRED", _fmt_val(saldo))):
                i = self._ix(reg_m, nome)
                if i is not None and i < n_m:
                    campos[i] = valor
            i_dif = self._ix(reg_m, "VL_CRED_DIF")
            if i_dif is None:
                i_dif = self._ix(reg_m, "VL_CRED_DIFER")
            if i_dif is not None and i_dif < n_m:
                campos[i_dif] = "0"
            novo.campos = campos

            for (nat, cst) in sorted(g["grupos"]):
                v = round(g["grupos"][(nat, cst)], 2)
                filho = self.novo_registro(reg_det, pai=novo, depois=ancora)
                ancora = filho
                c = [""] * n_det
                c[0] = reg_det
                for nome, valor in (
                        ("NAT_BC_CRED", nat), ("CST_%s" % tributo, cst),
                        ("VL_BC_%s_TOT" % tributo, _fmt_val(v)),
                        ("VL_BC_%s_NC" % tributo, _fmt_val(v)),
                        ("VL_BC_%s" % tributo, _fmt_val(v)),
                        ("QUANT_BC_%s" % tributo, "0")):
                    i = self._ix(reg_det, nome)
                    if i is not None and i < n_det:
                        c[i] = valor
                filho.campos = c

        # `depois=` empilha meios (x+0,5; x+1,0; x+1,5…) e, com grupos demais,
        # a ordem inventada alcançaria a do registro seguinte — o M500 cairia
        # depois do M600. `_reordenar` percorre a árvore e devolve inteiros.
        self._reordenar()
        return {"descontado": round(descontado, 2),
                "disponivel": round(disponivel, 2), "grupos": len(grupos),
                "ignorados": ignorados, "sem_credito": False}

    def conferir_creditos_m(self, tolerancia=0.02):
        """Confere o M105/M505 declarado contra a base de crédito dos documentos.

        É a conferência que o PVA faz em duas mensagens: o total do M105 tem
        de ser o somatório das bases dos documentos com aquela natureza, CST e
        alíquota, e não deve existir M105 para uma combinação que os
        documentos não têm.

        O agrupamento segue o do PVA: a alíquota vem do **M100 pai**, e a
        natureza de cada item sai do CFOP pela tabela 4.3.7. Devolve
        `[(registro, tributo, nat, cst, declarado, calculado)]` só do que não
        fecha, ou `[]` quando não dá para conferir (o motivo fica em
        `motivo_creditos`).
        """
        self.motivo_creditos = ""
        if self.layout != "CONTRIB":
            return []
        cod_inc = "1"
        r0110 = [r for r in self.registros if r.reg == "0110"]
        if r0110:
            i = self._ix("0110", "COD_INC_TRIB")
            cod_inc = (r0110[0].valor(i) or "1").strip()
        self.motivo_creditos = self._motivo_para_nao_refazer_creditos(cod_inc)
        if self.motivo_creditos:
            return []
        try:
            naturezas = referencias.atual().naturezas_cfop_credito(
                self.data_final())
        except Exception:                                       # noqa: BLE001
            naturezas = {}
        if not naturezas:
            self.motivo_creditos = ("a tabela de CFOP com direito a crédito "
                                    "do PVA não está disponível")
            return []

        fora = []
        for tributo, reg_m, reg_det in (("PIS", "M100", "M105"),
                                        ("COFINS", "M500", "M505")):
            grupos, _ig = self.creditos_por_aliquota(tributo, naturezas)
            i_al = self._ix(reg_m, "ALIQ_%s" % tributo)
            i_nat = self._ix(reg_det, "NAT_BC_CRED")
            i_cst = self._ix(reg_det, "CST_%s" % tributo)
            i_tot = self._ix(reg_det, "VL_BC_%s_TOT" % tributo)
            if None in (i_al, i_nat, i_cst, i_tot):
                continue
            for m in self.registros:
                if m.reg != reg_m:
                    continue
                k = "%.4f" % _to_num(m.valor(i_al))
                # grupo do M100 que os documentos não têm: TODO filho dele
                # sobra, mesmo o que declara zero — é o que o PVA recusa com
                # "não deverá existir um registro M105".
                sobrando = k not in grupos
                doc = grupos.get(k, {}).get("grupos", {})
                for f in m.filhos:
                    if f.reg != reg_det:
                        continue
                    nat = (f.valor(i_nat) or "").strip()
                    cst = (f.valor(i_cst) or "").strip()
                    dec = _to_num(f.valor(i_tot))
                    calc = round(doc.get((nat, cst), 0.0), 2)
                    if sobrando or abs(dec - calc) > tolerancia:
                        fora.append((f, tributo, nat, cst, dec, calc))
        return fora

    def conferir_apuracao_m(self, tolerancia=0.02):
        """Compara o M210/M610 declarado com a receita dos documentos.

        É a conferência que o PVA faz em `MSG_VL_REC_BRT` (campo VL_REC_BRT) e
        `MSG_VL_BC_CONT_IND_NAT_PJ` (campo VL_BC_CONT): o valor declarado na
        apuração tem de sair do somatório dos registros de receita.

        Devolve `{"PIS": {...}, "COFINS": {...}, "parcial": [registros]}`,
        cada tributo com `registros`, `declarado_rec`, `declarado_bc`,
        `calculado_rec`, `calculado_bc`, `difere_rec` e `difere_bc`.
        """
        if self.layout != "CONTRIB":
            return None
        out = {"parcial": self.receita_parcial()}
        for tributo, det in (("PIS", "M210"), ("COFINS", "M610")):
            grupos = self.receita_tributada_por_aliquota(tributo)
            calc_rec = round(sum(g["rec"] for g in grupos.values()), 2)
            calc_bc = round(sum(g["bc"] for g in grupos.values()), 2)
            regs = [r for r in self.registros if r.reg == det]
            i_rec = self._ix(det, "VL_REC_BRT")
            i_bc = self._ix(det, "VL_BC_CONT")
            dec_rec = (round(sum(_to_num(r.valor(i_rec)) for r in regs), 2)
                       if i_rec is not None else 0.0)
            dec_bc = (round(sum(_to_num(r.valor(i_bc)) for r in regs), 2)
                      if i_bc is not None else 0.0)
            out[tributo] = {
                "registro": det, "registros": regs,
                "declarado_rec": dec_rec, "declarado_bc": dec_bc,
                "calculado_rec": calc_rec, "calculado_bc": calc_bc,
                "difere_rec": bool(regs) and abs(dec_rec - calc_rec) > tolerancia,
                "difere_bc": bool(regs) and abs(dec_bc - calc_bc) > tolerancia}
        return out

    def conferir_receitas_isentas(self, tolerancia=0.02):
        """Confere o M400/M800 contra a receita por CST dos documentos.

        Devolve `[(registro, tributo, cst, declarado, calculado)]` apenas dos
        que **não fecham**. Calculado zero quer dizer que nenhum documento tem
        aquele CST — é o caso que o PVA acusa como registro que não deveria
        existir (`MSG_M400_NAO_DEVE_EXISTIR`).
        """
        if self.layout != "CONTRIB":
            return []
        fora = []
        for tributo, det, campo in (("PIS", "M400", "CST_PIS"),
                                    ("COFINS", "M800", "CST_COFINS")):
            regs = [r for r in self.registros if r.reg == det]
            if not regs:
                continue
            soma = self.receita_por_cst(tributo)
            i_cst = self._ix(det, campo)
            i_vl = self._ix(det, "VL_TOT_REC")
            if i_cst is None or i_vl is None:
                continue
            for r in regs:
                cst = (r.valor(i_cst) or "").strip()
                dec = _to_num(r.valor(i_vl))
                calc = round(soma.get(cst, 0.0), 2)
                if abs(dec - calc) > tolerancia:
                    fora.append((r, tributo, cst, dec, calc))
        return fora

    # --------------------------------------------- totais (in-place, p/ tela)
    def recalcular_bloco_m(self, refazer_creditos=True, naturezas=None):
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

        `naturezas` ({CFOP: NAT_BC_CRED}) é a tabela 4.3.7 do PVA. Sem ela,
        é pedida à porta `referencias`; os testes a passam pronta.

        Retorna um resumo, ou None se não se aplicar.
        """
        if self.layout != "CONTRIB":
            return None
        # a apuração soma receitas e créditos dos blocos A, C, D e F e
        # reescreve o M: todos precisam de números de verdade
        self._exigir_numeros([r for r in self.registros
                              if r.bloco in ("A", "C", "D", "F", "M")])
        r0110 = [r for r in self.registros if r.reg == "0110"]
        cod_inc = "1"
        if r0110:
            i = self._ix("0110", "COD_INC_TRIB")
            cod_inc = (r0110[0].valor(i) or "1").strip()
        cumulativo = (cod_inc == "2")
        cod_cont = "51" if cumulativo else "01"

        naturezas = dict(naturezas or {})
        motivo = self._motivo_para_nao_refazer_creditos(cod_inc)
        if cumulativo or not refazer_creditos or motivo:
            naturezas = {}
        if cumulativo:
            motivo = motivo or "regime cumulativo não gera crédito"
        elif refazer_creditos and not motivo and not naturezas:
            try:
                naturezas = referencias.atual().naturezas_cfop_credito(
                    self.data_final())
            except Exception:                                   # noqa: BLE001
                naturezas = {}
            if not naturezas:
                motivo = ("a tabela de CFOP com direito a crédito do PVA não "
                          "está disponível")

        resumo = {}
        for tributo, reg_cons, reg_det in (("PIS", "M200", "M210"),
                                           ("COFINS", "M600", "M610")):
            grupos = self.receita_tributada_por_aliquota(tributo)
            cons = next((r for r in self.registros if r.reg == reg_cons), None)
            if cons is None:
                resumo[tributo] = "sem %s" % reg_cons
                continue

            # remove os M210/M610 atuais e recria por alíquota, PRESERVANDO a
            # ordem do leiaute (M200 -> M205 -> M210 -> ...). A âncora correta é
            # o último M205/M605 (que precede os M210); se não houver, o registro
            # anterior ao 1º M210 atual; por fim, o próprio M200/M600. Isso
            # conserta inclusive arquivos onde o M210 ficou à frente do M205.
            largura = self._ncampos(reg_det)  # antes de remover os antigos
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
                self._preencher(novo, [
                    reg_det, cod_cont, _fmt_val(g["rec"]),
                    _fmt_val(g["bc"]), "0", "0",
                    _fmt_val(g["bc"]), g["aliq"], "0", "",
                    _fmt_val(apur), "0", "0",
                    "0", "0", _fmt_val(apur)], largura)
                ancora = novo

            # atualiza a consolidação M200/M600
            # o crédito é refeito antes da consolidação: o desconto do M200
            # é limitado pelo débito do período, que só agora se conhece
            cred = _to_num(cons.valor(2))           # VL_TOT_CRED_DESC (mantido)
            if naturezas:
                info = self._refazer_creditos(tributo, total_apur, naturezas)
                cred = info["descontado"]
                resumo.setdefault("creditos", {})[tributo] = info
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
            # o detalhamento por código de receita (M205/M605) acompanha o
            # valor a recolher do campo de origem (08 = NC, 12 = cumulativo).
            # Até aqui ele ficava com o débito antigo, e o PVA acusava
            # MSG_VALIDA_DET_RECEITA_DCTF no M200/M600 (num arquivo real,
            # 3.340,22 no M200 e 3.338,47 no M205). Com mais de um código no
            # mesmo campo a divisão é do contribuinte: fica como está.
            self._acompanhar_codigos_receita(
                "M205" if tributo == "PIS" else "M605",
                {"08": nc_rec, "12": cum_rec}, resumo, tributo)
            resumo[tributo] = {"grupos": len(grupos),
                               "apurado": round(total_apur, 2),
                               "a_recolher": round(nc_rec + cum_rec, 2)}

        if motivo:
            resumo["creditos_motivo"] = motivo
        self.atualizar_bloco9_inplace()
        resumo["regime"] = ("cumulativo" if cumulativo
                            else "não-cumulativo" if cod_inc == "1"
                            else "ambos")
        return resumo

    def _acompanhar_codigos_receita(self, reg, a_recolher, resumo, tributo):
        i_campo = self._ix(reg, "NUM_CAMPO")
        i_deb = self._ix(reg, "VL_DEBITO")
        if i_campo is None or i_deb is None:
            return
        por_campo = {}
        for r in self.registros:
            if r.reg == reg:
                por_campo.setdefault((r.valor(i_campo) or "").strip(),
                                     []).append(r)
        for campo, regs in por_campo.items():
            if campo not in a_recolher:
                continue
            if len(regs) != 1:
                resumo.setdefault("avisos", []).append(
                    "%s: %d códigos de receita no campo %s do %s — a divisão "
                    "do débito é do contribuinte; confira a soma"
                    % (tributo, len(regs), campo, reg))
                continue
            regs[0].set_valor(i_deb, _fmt_val(a_recolher[campo]))

    def atualizar_bloco9_inplace(self):
        """
        Atualiza, sem alterar a estrutura, os registros de contagem para que a
        interface reflita a realidade atual:
          * X990  -> nº de linhas do bloco (inclui o próprio X990);
          * 9900  -> nº de registros de cada tipo (ex.: 9900|C190|<qtd>);
          * 9990  -> nº de linhas do bloco 9;
          * 9999  -> total de linhas do arquivo.
        A gravação (gerar_texto) reconstrói o bloco 9 do zero e continua sendo
        a fonte definitiva; este método serve para exibição imediata. Dentro
        de um `lote()`, fica para a saída dele.
        """
        if self._lote is not None:
            return
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
        Cria um novo registro vazio do `tipo` informado, **com a largura do
        leiaute** — um registro de um campo só sai do arquivo como `|C170|` e
        o PVA recusa por quantidade de campos. Era o que acontecia com a
        linha criada pelo botão "+" da grade, que não redimensionava nada.

        `pai`    -> Registro pai (None = raiz)
        `depois` -> Registro após o qual inserir (controla a ordem do arquivo)
        """
        # a largura é medida ANTES de inserir: `_ncampos` usa a moda dos
        # registros já presentes, e um recém-criado puxaria a moda para baixo
        # (em lote, uma vez por tipo: medir é varrer o arquivo)
        n_campos = max(1, self._largura(tipo))
        partes = ["", tipo, ""]
        r = Registro(partes, self.layout, 0)
        r.campos = [tipo] + [""] * (n_campos - 1)
        r.pai = pai
        # ordem de inserção. Fora do lote a árvore é renumerada a cada
        # inserção e meio basta; em lote ela só é renumerada no fim, e uma
        # sequência de inserções encadeadas (cada uma depois da anterior)
        # andaria de meio em meio até alcançar o irmão seguinte — daí o passo
        # mínimo, que só precisa ordenar entre irmãos
        passo = self._PASSO_EM_LOTE if self._lote is not None else 0.5
        if depois is not None:
            r.ordem = depois.ordem + passo
        elif pai is not None:
            r.ordem = pai.ordem + passo
        else:
            r.ordem = (self.registros[-1].ordem + 1) if self.registros else 0

        if pai is not None:
            pai.filhos.append(r)
            pai.filhos.sort(key=lambda x: x.ordem)
        else:
            self.raizes.append(r)
            self.raizes.sort(key=lambda x: x.ordem)
        self.registros.append(r)
        if self._lote is None:
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
        if self._lote is not None:
            # a lista inteira é refeita uma vez, no fim do lote
            self._lote["remover"] |= remover
        else:
            self.registros = [x for x in self.registros
                              if x.uid not in remover]
        self._cad_itens = None

    _PASSO_EM_LOTE = 1e-7

    def _largura(self, tipo):
        """`_ncampos(tipo)`; dentro de um `lote()`, medido uma vez por tipo
        (medir é varrer o arquivo, e o lote insere milhares)."""
        if self._lote is None:
            return self._ncampos(tipo)
        larguras = self._lote["larguras"]
        if tipo not in larguras:
            larguras[tipo] = self._ncampos(tipo)
        return larguras[tipo]

    @contextlib.contextmanager
    def lote(self):
        """Muitas inserções e remoções de uma vez — os C170 fictícios de um
        mês de NFC-e, o analítico refeito de milhares de documentos.

        Fora do lote, cada `novo_registro` mede a largura (varre o arquivo) e
        renumera a árvore, e cada `remover_registro` refaz a lista inteira:
        custo quadrático, que num mês real (~32 mil itens de NFC-e) passava
        de minutos com a tela parada. Dentro do lote, a largura é medida uma
        vez por tipo, as remoções se acumulam, e a renumeração e o bloco 9 são
        refeitos uma vez, na saída. Durante o lote, `registros` ainda traz os
        removidos e a ordem não está renumerada: navegue pela árvore
        (`filhos`). Reentrante."""
        if self._lote is not None:
            yield
            return
        self._lote = {"larguras": {}, "remover": set()}
        try:
            yield
        finally:
            remover = self._lote["remover"]
            self._lote = None
            if remover:
                self.registros = [x for x in self.registros
                                  if x.uid not in remover]
            self._reordenar()
            self.atualizar_bloco9_inplace()

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

        # a ordem dos 9900 é a que o arquivo já tinha: cada ERP usa a sua
        # (alfabética, a dos blocos do leiaute…) e o PVA aceita qualquer
        # uma. Reordenar fazia "abrir e salvar sem mexer" devolver um arquivo
        # diferente. Tipo que não existia entra no fim, em ordem alfabética.
        ja = [r.valor(1) for r in self._linhas_em_ordem() if r.reg == "9900"]
        tipos_ordenados = [t for t in dict.fromkeys(ja) if t in cont_tipo]
        presentes = set(tipos_ordenados)
        tipos_ordenados += sorted(t for t in cont_tipo if t not in presentes)

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

    def salvar(self, caminho=None, descartar_invalidas=False):
        """Grava o arquivo **sem destruir o destino se algo der errado**.

        Linha que a leitura não reconheceu como registro (`linhas_invalidas`)
        não tem como ir para o arquivo gravado: salvar é recusado com
        `LinhasInvalidas`, a menos que quem chama tenha perguntado ao usuário
        e passe `descartar_invalidas=True`.

        O modo `"w"` trunca o arquivo no momento em que é aberto: qualquer
        falha depois disso — disco cheio, ou um caractere fora do latin-1
        colado numa descrição — deixava o usuário sem o arquivo e sem o
        conteúdo. Aqui o texto é codificado **antes** de tocar em disco,
        escrito num temporário ao lado e só então renomeado por cima
        (`os.replace`, que é atômico no mesmo volume).
        """
        caminho = caminho or self.caminho
        if self.linhas_invalidas and not descartar_invalidas:
            raise LinhasInvalidas(self.linhas_invalidas)
        texto = self.gerar_texto()
        try:
            dados = texto.encode(self.encoding)
        except UnicodeEncodeError as exc:
            linha = texto.count("\n", 0, exc.start) + 1
            try:
                trecho = texto.splitlines()[linha - 1][:90]
            except IndexError:
                trecho = ""
            raise ValueError(
                "O arquivo não foi gravado: a linha %d tem o caractere %r, "
                "que não existe na codificação %s do SPED. Normalmente é "
                "texto colado de outro programa (travessão, aspas curvas). "
                "Corrija o campo e salve de novo.\n\n%s"
                % (linha, texto[exc.start:exc.end], self.encoding,
                   trecho)) from None

        temporario = "%s.tmp" % caminho
        try:
            with open(temporario, "wb") as f:
                f.write(dados)
            os.replace(temporario, caminho)
        except Exception:
            try:
                os.remove(temporario)
            except OSError:
                pass
            raise
        self.caminho = caminho
        return caminho

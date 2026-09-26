# -*- coding: utf-8 -*-
"""Cadastro de empresas: regime tributário e parâmetros de conferência.

Cada empresa é identificada pelo **CNPJ** (só dígitos) e guarda o que o arquivo
SPED sozinho não diz — ou diz de forma incompleta: o regime federal, as
alíquotas que a empresa efetivamente pratica e o ramo de atividade. É esse
cadastro que permite às rotinas de `rotinas.py` decidir o que está certo e o
que está errado num arquivo.

Por que não basta o próprio arquivo: o registro **0110 (COD_INC_TRIB)** informa
o regime de PIS/COFINS, mas só existe no EFD Contribuições — o arquivo de ICMS
não tem nada equivalente — e, quando existe, pode estar **errado**, que é
justamente uma das coisas a conferir. O cadastro é a referência declarada pelo
contribuinte; o arquivo é o que está escriturado. Comparar os dois é útil.

Sem dependência de GUI: a interface lê e grava por estas funções.
"""


from dataclasses import asdict, dataclass, fields

from sped_tables.dominio.sped_model import _fmt_aliq, so_digitos


# --------------------------------------------------------------- vocabulário
REGIMES_FEDERAIS = [
    ("simples", "Simples Nacional"),
    ("presumido", "Lucro Presumido"),
    ("real", "Lucro Real"),
]
REGIMES_PIS_COFINS = [
    ("cumulativo", "Cumulativo"),
    ("nao_cumulativo", "Não-cumulativo"),
    ("ambos", "Ambos os regimes"),
]
ATIVIDADES = [
    ("comercio", "Comércio / revenda"),
    ("industria", "Indústria"),
    ("servico", "Prestação de serviços"),
]

# Alíquotas nominais de cada regime. O cumulativo não gera crédito, por isso
# só tem par de saída.
ALIQUOTAS = {
    "cumulativo": {"pis_saida": "0,65", "cofins_saida": "3",
                   "pis_credito": "", "cofins_credito": ""},
    "nao_cumulativo": {"pis_saida": "1,65", "cofins_saida": "7,6",
                       "pis_credito": "1,65", "cofins_credito": "7,6"},
}

# 0110/COD_INC_TRIB -> regime de PIS/COFINS
_COD_INC_TRIB = {"1": "nao_cumulativo", "2": "cumulativo", "3": "ambos"}

# O regime federal em regra determina o de PIS/COFINS. É só um palpite inicial
# para o cadastro novo: há exceções (receita sujeita ao cumulativo dentro do
# Lucro Real, por exemplo), e por isso os dois campos são independentes.
_REGIME_SUGERIDO = {"simples": "cumulativo", "presumido": "cumulativo",
                    "real": "nao_cumulativo"}


def formatar_cnpj(cnpj):
    d = so_digitos(cnpj)
    if len(d) != 14:
        return cnpj or ""
    return "%s.%s.%s/%s-%s" % (d[:2], d[2:5], d[5:8], d[8:12], d[12:])


def normalizar_aliquota(txt):
    """Alíquota digitada -> formato do SPED (`1,65`, `7,6`).

    O campo do cadastro é texto livre, e o que for digitado ali acaba
    **gravado no arquivo fiscal** pela rotina de correção. Digitar `1.65`
    punha ponto decimal no SPED, que o PVA recusa. Vazio continua vazio (é
    "não declarado", não zero), e texto que não é número fica como está para
    o usuário ver o que escreveu.
    """
    t = (txt or "").strip()
    if not t:
        return ""
    try:
        return _fmt_aliq(float(t.replace(".", ",").replace(",", ".", 1)
                               if t.count(",") + t.count(".") <= 1
                               else t.replace(".", "").replace(",", ".")))
    except ValueError:
        return t


@dataclass
class Empresa:
    """Parâmetros declarados de uma empresa.

    As alíquotas são strings no formato do SPED (vírgula decimal, sem zeros à
    direita: `1,65`, `7,6`) — guardar como texto evita converter de ida e volta
    e perder a forma exata que vai para o arquivo.
    """
    cnpj: str
    nome: str = ""
    uf: str = ""
    regime_federal: str = "presumido"
    regime_pis_cofins: str = "cumulativo"
    atividade: str = "comercio"
    aliq_pis_saida: str = "0,65"
    aliq_cofins_saida: str = "3"
    aliq_pis_credito: str = ""
    aliq_cofins_credito: str = ""
    # CST gravado quando uma rotina retira um crédito indevido. O 70 é
    # "operação de aquisição sem direito a crédito"; 98/98 e 73 aparecem em
    # outros cenários, por isso é configurável.
    cst_entrada_sem_credito: str = "70"
    observacoes: str = ""

    def __post_init__(self):
        """Normaliza as alíquotas na entrada — de qualquer origem: cadastro
        digitado à mão, `empresas.json` antigo ou padrão do regime."""
        for campo in ("aliq_pis_saida", "aliq_cofins_saida",
                      "aliq_pis_credito", "aliq_cofins_credito"):
            setattr(self, campo, normalizar_aliquota(getattr(self, campo)))

    # ------------------------------------------------------------- derivados
    @property
    def cumulativo(self):
        return self.regime_pis_cofins == "cumulativo"

    @property
    def nao_cumulativo(self):
        return self.regime_pis_cofins == "nao_cumulativo"

    @property
    def ambos_regimes(self):
        """No regime misto a alíquota não identifica sozinha um erro.

        A empresa tem receitas nos dois regimes, então tanto 0,65/3,00 quanto
        1,65/7,60 podem estar corretos na mesma escrituração — as rotinas que
        dependem de alíquota se abstêm.
        """
        return self.regime_pis_cofins == "ambos"

    def rotulo(self):
        return "%s — %s" % (formatar_cnpj(self.cnpj), self.nome or "(sem nome)")

    def aplicar_aliquotas_do_regime(self):
        """Preenche as alíquotas com as nominais do regime declarado."""
        padrao = ALIQUOTAS.get(self.regime_pis_cofins)
        if not padrao:
            return self
        # pelo mesmo funil do cadastro digitado
        self.aliq_pis_saida = normalizar_aliquota(padrao["pis_saida"])
        self.aliq_cofins_saida = normalizar_aliquota(padrao["cofins_saida"])
        self.aliq_pis_credito = normalizar_aliquota(padrao["pis_credito"])
        self.aliq_cofins_credito = normalizar_aliquota(
            padrao["cofins_credito"])
        return self


# ---------------------------------------------------------- serialização
# A gravação em disco é de `infra.cadastro`; aqui fica só a tradução entre a
# `Empresa` e o dicionário guardado — que é regra: campo desconhecido (de
# versão futura ou antiga) é ignorado, e CNPJ vale só pelos dígitos.
def de_registro(cnpj, registro):
    """A `Empresa` de um item do cadastro gravado, ou None se não servir."""
    if not isinstance(registro, dict):
        return None
    validos = {f.name for f in fields(Empresa)}
    d = {k: v for k, v in registro.items() if k in validos}
    d["cnpj"] = so_digitos(cnpj) or so_digitos(d.get("cnpj", ""))
    if not d["cnpj"]:
        return None
    return Empresa(**d)


def para_registro(empresa):
    """O dicionário gravado de uma `Empresa` (sem o CNPJ, que é a chave)."""
    d = asdict(empresa)
    d.pop("cnpj", None)
    return d


# ------------------------------------------------------- leitura do arquivo
def dados_do_arquivo(doc):
    """Extrai do 0000/0110 o que der para pré-preencher: (cnpj, nome, uf,
    regime_pis_cofins_do_arquivo). O regime vem vazio no leiaute de ICMS."""
    cnpj = nome = uf = ""
    i_cnpj = doc._ix("0000", "CNPJ")
    i_nome = doc._ix("0000", "NOME")
    i_uf = doc._ix("0000", "UF")
    for r in doc.registros:
        if r.reg == "0000":
            if i_cnpj is not None:
                cnpj = so_digitos(r.valor(i_cnpj))
            if i_nome is not None:
                nome = (r.valor(i_nome) or "").strip()
            if i_uf is not None:
                uf = (r.valor(i_uf) or "").strip()
            break

    regime = ""
    if doc.layout == "CONTRIB":
        i_inc = doc._ix("0110", "COD_INC_TRIB")
        for r in doc.registros:
            if r.reg == "0110" and i_inc is not None:
                regime = _COD_INC_TRIB.get((r.valor(i_inc) or "").strip(), "")
                break
    return cnpj, nome, uf, regime


def obter_ou_criar(mapa, doc):
    """Encontra a empresa do arquivo no cadastro; se não houver, monta uma
    sugestão (ainda **não** gravada) com o que o arquivo informa.

    Devolve (empresa, ja_cadastrada).
    """
    cnpj, nome, uf, regime = dados_do_arquivo(doc)
    if not cnpj:
        return None, False
    existente = mapa.get(cnpj)
    if existente is not None:
        return existente, True

    emp = Empresa(cnpj=cnpj, nome=nome, uf=uf)
    if regime and regime != "ambos":
        emp.regime_pis_cofins = regime
        emp.aplicar_aliquotas_do_regime()
    elif regime:
        emp.regime_pis_cofins = regime
    emp.regime_federal = "real" if regime == "nao_cumulativo" else "presumido"
    return emp, False


def conferir_regime(doc, empresa):
    """Compara o regime declarado no cadastro com o do arquivo (0110).

    Divergir aqui não é detalhe: é o cadastro e a escrituração discordando
    sobre qual regra vale. Devolve None quando não há como comparar.
    """
    if empresa is None or doc.layout != "CONTRIB":
        return None
    _, _, _, regime_arq = dados_do_arquivo(doc)
    if not regime_arq:
        return None
    if regime_arq == empresa.regime_pis_cofins:
        return None
    rot = dict(REGIMES_PIS_COFINS)
    return ("O registro 0110 declara **%s** e o cadastro da empresa diz **%s**."
            % (rot.get(regime_arq, regime_arq),
               rot.get(empresa.regime_pis_cofins, empresa.regime_pis_cofins)))


def sugerir_regime_pis_cofins(regime_federal):
    return _REGIME_SUGERIDO.get(regime_federal, "cumulativo")

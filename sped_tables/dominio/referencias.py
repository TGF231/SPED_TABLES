# -*- coding: utf-8 -*-
"""Porta: o que o domínio precisa das **tabelas oficiais**.

Parte das regras fiscais depende de dados que não são do arquivo nem do
programa — são do PVA instalado na máquina: o descritor de validação de
cada versão de leiaute, as tabelas de códigos válidos com vigência, a tabela
de CFOP com direito a crédito, o prazo de entrega de cada período.

O domínio não sabe **onde** isso está nem **como** se lê: pede a esta porta.
Quem liga a porta a uma implementação é a montagem da aplicação
(`sped_tables.aplicacao.montagem`), no início do programa; a implementação
de verdade, que lê a instalação do PVA, é `sped_tables.infra.referencias_pva`.

Sem nada ligado vale `Referencias` desta página, que não tem tabela
nenhuma: cada regra que depende dela se abstém, como já fazia quando o PVA
não estava instalado. É também o que permite testar uma regra com uma
tabela inventada, sem PVA nenhum na máquina.
"""


class Referencias:
    """Fonte de referências **vazia** — e a interface que as outras seguem."""

    nome = "nenhuma"

    def estrutura(self, layout):
        """Descritor do leiaute: `(estrutura, info)`; ver `descritor_pva`."""
        return {}, {"descritor": None,
                    "erro": "nenhuma fonte de tabelas oficiais configurada"}

    def dominios_por_datasource(self, estrutura, layout, uf=None,
                                data_ref=None):
        """Códigos válidos por (registro, campo): `(dominios, faltando)`."""
        return {}, []

    def rotulo(self, campo):
        """Nome legível do domínio de um campo, para as mensagens."""
        return campo

    def naturezas_cfop_credito(self, data_ref=None):
        """`{CFOP: NAT_BC_CRED}` da tabela 4.3.7 do EFD Contribuições."""
        return {}

    def cfops_com_credito(self, data_ref=None):
        """`(conjunto de CFOP que admitem crédito, versão da tabela)`."""
        return set(), ""

    def prazo_entrega(self, mes_ano):
        """Data limite (DDMMAAAA) da EFD Contribuições do período MMAAAA."""
        return ""


_atual = [Referencias()]


def atual():
    """A fonte ligada agora (a vazia, se ninguém ligou nenhuma)."""
    return _atual[0]


def definir(fonte):
    """Liga uma fonte; `None` volta à vazia. Devolve a anterior, para quem
    precisar restaurar (os testes)."""
    anterior = _atual[0]
    _atual[0] = fonte if fonte is not None else Referencias()
    return anterior


def do_descritor(estrutura):
    """`{(registro, campo): (registro_alvo, campo_alvo)}` — de onde o PVA
    cobra que o código exista. É o mapa que faz "COD_ITEM do C170 tem de
    estar no 0200" deixar de ser regra escrita à mão.

    Leitura pura da estrutura do descritor: vale para qualquer fonte.
    """
    out = {}
    for reg, d in estrutura.items():
        for nome, c in d["campos"].items():
            ref = c.get("referencia")
            if not ref or ";" not in ref:
                continue
            alvo, campo_alvo = ref.split(";", 1)
            out[(reg, nome)] = (alvo.strip(), campo_alvo.strip())
    return out

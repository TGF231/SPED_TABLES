# -*- coding: utf-8 -*-
"""Caso de uso: gerar o SPED de um período a partir dos XMLs.

Junta o que a tela precisa, sem tela: a memória da empresa (lida e gravada
pela infra), a leitura da pasta de XMLs, o aprendizado com um SPED
entregue, a geração dos dois leiautes (`dominio/geracao.py`) e as decisões
da pessoa, que voltam para a memória.

A memória só é gravada quando a pessoa **aprende** com um SPED entregue,
**decide** um ponto de revisão ou **grava** o SPED gerado — nunca por gerar
uma prévia.
"""

from sped_tables.aplicacao import leitura_xml
from sped_tables.dominio import geracao
from sped_tables.dominio import memoria_itens as mi
from sped_tables.dominio.sped_model import SpedDocument, so_digitos
from sped_tables.infra import cadastro, memoria as memoria_infra

LEIAUTES = ("ICMS", "CONTRIB")


def empresas_com_memoria():
    return memoria_infra.cnpjs()


class GeracaoXml:
    """A geração de uma empresa (pelo CNPJ)."""

    def __init__(self, cnpj):
        self.cnpj = so_digitos(cnpj)
        self.memoria = memoria_infra.carregar(self.cnpj)
        self.lote = None
        self.resultados = {}       # leiaute -> geracao.Resultado

    # ------------------------------------------------------------ memória
    def resumo(self):
        return mi.resumo(self.memoria)

    def leiautes_aprendidos(self):
        """Os leiautes que a memória sabe gerar: sem o cabeçalho de um SPED
        entregue daquele leiaute, não há de onde tirar o 0000."""
        modelos = self.memoria.get("modelos", {})
        return tuple(x for x in LEIAUTES if "0000" in modelos.get(x, {}))

    def aprender(self, pasta_xml, *speds, progresso=None, cancelar=None):
        """Aprende com os SPED entregues de um mês (um de cada leiaute, no
        máximo) e os XMLs do mesmo mês. Recusa SPED de outra empresa, dois
        do mesmo leiaute e leiautes de meses diferentes."""
        docs = {}
        for caminho in speds:
            doc = SpedDocument.carregar(caminho)
            cnpj = so_digitos(doc.registros[0].valor(doc._ix("0000", "CNPJ")))
            if cnpj != self.cnpj:
                raise ValueError("O SPED %s é de outra empresa (CNPJ do "
                                 "0000 diferente)." % caminho)
            if doc.layout in docs:
                raise ValueError("Dois SPED do mesmo leiaute: escolha um de "
                                 "cada.")
            docs[doc.layout] = doc
        if not docs:
            raise ValueError("Informe ao menos um SPED entregue.")
        if len({d.data_final() for d in docs.values()}) > 1:
            raise ValueError("Os SPED escolhidos são de meses diferentes.")
        lote = leitura_xml.ler_pasta_fiscal(pasta_xml, progresso, cancelar)
        res = mi.aprender(self.memoria, lote,
                          doc_icms=docs.get("ICMS"),
                          doc_contrib=docs.get("CONTRIB"))
        memoria_infra.salvar(self.memoria)
        return res

    def decidir(self, apontamento, **campos):
        """A decisão da pessoa sobre um ponto de revisão de produto (por
        exemplo, `CFOP="1556"`), gravada na memória."""
        d = apontamento.get("dados") or {}
        if not d.get("fornecedor"):
            raise ValueError("Este ponto de revisão não é de um produto.")
        cod = campos.pop("COD_ITEM", None)
        mi.ensinar(self.memoria, d["fornecedor"], d["cprod"], d["cfop"],
                   d["cst"], campos, cod_proprio=cod, usado=d.get("usado"))
        memoria_infra.salvar(self.memoria)

    # ------------------------------------------------------------- geração
    def ler(self, pasta_xml, progresso=None, cancelar=None):
        """Lê a pasta de XMLs (NF-e, NFC-e, CT-e e eventos), em paralelo."""
        self.lote = leitura_xml.ler_pasta_fiscal(pasta_xml, progresso,
                                                 cancelar)
        return self.lote

    def documentos(self, periodo):
        """O que entra no período: `(grupos, resultado)` com fora do
        período e ignorados já apontados — pela mesma regra de data que a
        geração usa."""
        if self.lote is None:
            raise ValueError("Leia a pasta de XMLs primeiro.")
        previa = geracao.Resultado()
        pad = self.memoria.get("padroes", {}).get("entrada", {})
        grupos = geracao.classificar(self.lote, self.cnpj, periodo, previa,
                                     pad.get("DT_E_S"))
        return grupos, previa

    def gerar(self, periodo, leiautes=LEIAUTES, excluir=(),
              saldo_credor_anterior=None, correlacoes=None, incluir=()):
        """`incluir`: chaves de fora do período que a pessoa marcou como
        extemporâneas."""
        if self.lote is None:
            raise ValueError("Leia a pasta de XMLs primeiro.")
        if correlacoes is None:
            correlacoes = cadastro.carregar_correlacoes()
        self.resultados = {}
        memoria = self.memoria
        if "ICMS" in leiautes:
            res = geracao.gerar_icms(
                memoria, self.lote, periodo,
                saldo_credor_anterior=saldo_credor_anterior,
                correlacoes=correlacoes, excluir=excluir, incluir=incluir)
            self.resultados["ICMS"] = res
            # o participante novo tem o mesmo código nos dois leiautes
            memoria = dict(memoria, participantes=dict(
                memoria["participantes"], **res.participantes_novos))
        if "CONTRIB" in leiautes:
            self.resultados["CONTRIB"] = geracao.gerar_contrib(
                memoria, self.lote, periodo, correlacoes=correlacoes,
                excluir=excluir, incluir=incluir)
        return self.resultados

    def bloqueios(self):
        return [b for r in self.resultados.values() for b in r.bloqueios]

    def salvar(self, layout, caminho):
        """Grava o SPED gerado e passa para a memória os participantes que
        ganharam código nesta geração — os dos dois leiautes, porque o
        Contribuições usa os códigos que o ICMS/IPI acabou de dar."""
        res = self.resultados[layout]
        if res.bloqueios:
            raise ValueError("Há %d ponto(s) de revisão que deixariam o "
                             "arquivo inválido." % len(res.bloqueios))
        res.doc.salvar(caminho)
        for r in self.resultados.values():
            self.memoria["participantes"].update(r.participantes_novos)
        memoria_infra.salvar(self.memoria)
        return caminho

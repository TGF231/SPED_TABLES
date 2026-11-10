# -*- coding: utf-8 -*-
"""Testes contra arquivos SPED reais — que **nunca** entram no repositório.

Rodam só quando a variável de ambiente aponta para a pasta com os arquivos:

    set SPED_TABLES_ARQUIVOS_REAIS=C:\\caminho\\para\\a\\pasta
    python -m unittest tests.test_reais

Sem ela, são pulados. A pasta pode ter subpastas; todo `.txt` que começa
por `|0000|` entra.

Duas camadas:

* **invariantes**, que valem para qualquer arquivo: carregar e gravar não
  perde registro, recalcular é idempotente, nenhuma verificação levanta
  exceção;
* **gabarito**, opcional: um `gabarito.json` na mesma pasta com os números
  exatos esperados por arquivo (quantos achados por regra de revisão e por
  tipo de diagnóstico). É o "validar contra arquivos reais com números
  exatos" do CLAUDE.md, sem pôr dado de cliente no git. Para gerar a partir
  do estado atual (depois de conferir os números à mão):

    python -m tests.test_reais gerar
"""

import json
import os
import sys
import unittest

from sped_tables.dominio import diagnostico
from sped_tables.dominio import revisao
from sped_tables.dominio import validacao
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria

VARIAVEL = "SPED_TABLES_ARQUIVOS_REAIS"
PASTA = os.environ.get(VARIAVEL, "")
GABARITO = "gabarito.json"


def arquivos_reais(pasta=PASTA):
    if not pasta or not os.path.isdir(pasta):
        return []
    achados = []
    for raiz, _d, nomes in os.walk(pasta):
        for nome in sorted(nomes):
            if not nome.lower().endswith(".txt"):
                continue
            caminho = os.path.join(raiz, nome)
            try:
                with open(caminho, "rb") as fh:
                    if fh.read(6) == b"|0000|":
                        achados.append(caminho)
            except OSError:
                pass
    return achados


def numeros(doc):
    """O que o gabarito guarda de cada arquivo."""
    rev = {rotulo: len(ps) for rotulo, ps in revisao.revisar_por_regra(doc)}
    achados, _info = diagnostico.verificar(doc)
    diag = {}
    for a in achados:
        diag[a.tipo] = diag.get(a.tipo, 0) + a.quantidade
    return {"layout": doc.layout, "registros": len(doc.registros),
            "revisao": rev, "diagnostico": diag}


def _chave(caminho, pasta=PASTA):
    return os.path.relpath(caminho, pasta).replace("\\", "/")


@unittest.skipUnless(arquivos_reais(), "defina %s para rodar" % VARIAVEL)
class TestArquivosReais(unittest.TestCase):

    def test_gravar_nao_perde_registro_e_estabiliza(self):
        for caminho in arquivos_reais():
            with self.subTest(arquivo=_chave(caminho)), \
                    PastaTemporaria() as p:
                doc = SpedDocument.carregar(caminho)
                fora_do_9 = sum(1 for r in doc.registros if r.bloco != "9")
                copia = os.path.join(p, "copia.txt")
                doc.salvar(copia)
                relido = SpedDocument.carregar(copia)
                self.assertEqual(
                    sum(1 for r in relido.registros if r.bloco != "9"),
                    fora_do_9)
                self.assertEqual(relido.gerar_texto(), doc.gerar_texto())

    def test_recalculo_do_bloco_m_e_idempotente(self):
        for caminho in arquivos_reais():
            doc = SpedDocument.carregar(caminho)
            if doc.layout != "CONTRIB":
                continue
            with self.subTest(arquivo=_chave(caminho)):
                doc.recalcular_bloco_m()
                uma = doc.gerar_texto()
                doc.recalcular_bloco_m()
                self.assertEqual(doc.gerar_texto(), uma)

    def test_verificacoes_nao_levantam_excecao(self):
        for caminho in arquivos_reais():
            with self.subTest(arquivo=_chave(caminho)):
                doc = SpedDocument.carregar(caminho)
                revisao.revisar_por_regra(doc)
                validacao.validar(doc)
                diagnostico.verificar(doc)

    def test_correcoes_automaticas(self):
        """As correções em lote sobre o arquivo real: acabam com o que
        corrigem, não criam erro de estrutura, são idempotentes e o arquivo
        gravado volta idêntico ao reabrir."""
        estruturais = ("num_campos", "bloco")
        for caminho in arquivos_reais():
            with self.subTest(arquivo=_chave(caminho)), \
                    PastaTemporaria() as p:
                doc = SpedDocument.carregar(caminho)
                antes, _i = diagnostico.verificar(doc)

                def corrigir():
                    doc.preencher_cod_gen()
                    validacao.normalizar(doc)
                    if doc.layout == "ICMS":
                        doc.consolidar_c190_em_massa()
                    else:
                        doc.recalcular_bloco_m()

                corrigir()
                uma = doc.gerar_texto()
                corrigir()
                self.assertEqual(doc.gerar_texto(), uma, "não idempotente")

                depois, _i = diagnostico.verificar(doc)
                conta = lambda achados, t: sum(          # noqa: E731
                    a.quantidade for a in achados if a.tipo == t)
                self.assertEqual(conta(depois, "nulo"), 0)
                self.assertEqual(doc.divergencias_cod_gen(), [])
                for tipo in estruturais:
                    self.assertLessEqual(conta(depois, tipo),
                                         conta(antes, tipo), tipo)

                copia = os.path.join(p, "corrigido.txt")
                doc.salvar(copia)
                self.assertEqual(SpedDocument.carregar(copia).gerar_texto(),
                                 uma)

    def test_icms_dos_itens(self):
        """Depois do recálculo, todo C170 tributado tem VL_ICMS = base ×
        alíquota; a segunda passada não mexe em nada."""
        from sped_tables.dominio.sped_model import _to_num
        for caminho in arquivos_reais():
            doc = SpedDocument.carregar(caminho)
            if doc.layout != "ICMS":
                continue
            with self.subTest(arquivo=_chave(caminho)):
                doc.recalcular_icms_itens()
                uma = doc.gerar_texto()
                ib, ia, iv, ic = (doc._ix("C170", c) for c in (
                    "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "CST_ICMS"))
                for r in doc.registros:
                    if r.reg != "C170" or doc.situacao_icms(
                            r.valor(ic)) == "sem_debito":
                        continue
                    esperado = round(_to_num(r.valor(ib))
                                     * _to_num(r.valor(ia)) / 100, 2)
                    self.assertAlmostEqual(_to_num(r.valor(iv)), esperado,
                                           places=2, msg=r.linha_sped())
                doc.recalcular_icms_itens()
                self.assertEqual(doc.gerar_texto(), uma)

    def test_troca_de_aliquotas_ida_e_volta(self):
        """Trocar a alíquota predominante por outra e voltar devolve os
        valores; todo registro trocado fica com valor = base × alíquota."""
        for caminho in arquivos_reais():
            doc = SpedDocument.carregar(caminho)
            if doc.layout != "CONTRIB":
                continue
            with self.subTest(arquivo=_chave(caminho)):
                pis = doc.aliquota_predominante("ALIQ_PIS")
                cof = doc.aliquota_predominante("ALIQ_COFINS")
                if not pis or not cof:
                    self.skipTest("sem saída tributada")
                original = doc.gerar_texto()
                r1 = doc.trocar_aliquotas_pis_cofins(
                    aliq_pis=pis + 1, aliq_cofins=cof + 1, de_pis=pis,
                    de_cofins=cof)
                self.assertGreater(r1["itens"], 0)
                r2 = doc.trocar_aliquotas_pis_cofins(
                    aliq_pis=pis, aliq_cofins=cof, de_pis=pis + 1,
                    de_cofins=cof + 1)
                self.assertEqual(r2["itens"], r1["itens"])
                volta = doc.gerar_texto()
                # os valores são recalculados (base × alíquota): onde o ERP
                # arredondou diferente, a volta corrige — por isso a
                # comparação é campo a campo, só nas alíquotas
                self.assertEqual(
                    [l.split("|")[:7] for l in volta.splitlines()],
                    [l.split("|")[:7] for l in original.splitlines()])

    def test_datas_ida_e_volta(self):
        import datetime
        for caminho in arquivos_reais():
            doc = SpedDocument.carregar(caminho)
            with self.subTest(arquivo=_chave(caminho)):
                original = doc.gerar_texto()
                args = dict(campo_filtro="DT_E_S",
                            data_ini=datetime.date(1900, 1, 1),
                            data_fim=datetime.date(2999, 12, 31),
                            campos_alterar=("DT_E_S", "DT_DOC"), modo="dias")
                doc.alterar_datas_c100(valor=3, **args)
                self.assertNotEqual(doc.gerar_texto(), original)
                doc.alterar_datas_c100(valor=-3, **args)
                self.assertEqual(doc.gerar_texto(), original)

    def test_gabarito(self):
        cam = os.path.join(PASTA, GABARITO)
        if not os.path.isfile(cam):
            self.skipTest("sem %s na pasta" % GABARITO)
        with open(cam, encoding="utf-8") as fh:
            esperado = json.load(fh)
        for caminho in arquivos_reais():
            chave = _chave(caminho)
            if chave not in esperado:
                continue
            with self.subTest(arquivo=chave):
                obtido = numeros(SpedDocument.carregar(caminho))
                self.assertEqual(obtido, esperado[chave])


def gerar_gabarito(pasta=PASTA):
    saida = {_chave(c, pasta): numeros(SpedDocument.carregar(c))
             for c in arquivos_reais(pasta)}
    cam = os.path.join(pasta, GABARITO)
    with open(cam, "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return cam, len(saida)


if __name__ == "__main__":
    if sys.argv[1:] == ["gerar"]:
        if not arquivos_reais():
            sys.exit("defina %s com a pasta dos arquivos" % VARIAVEL)
        print("gravado: %s (%d arquivos)" % gerar_gabarito())
    else:
        unittest.main()

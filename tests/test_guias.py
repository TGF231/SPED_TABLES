# -*- coding: utf-8 -*-
"""Os guias práticos como fonte: o extrator, os JSON de `recursos/`, o
descritor do PVA alinhado ao leiaute e a ajuda de campo."""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

from sped_tables import RAIZ_PROJETO
from sped_tables.dominio import ajuda
from sped_tables.dominio import referencias
from sped_tables.dominio import sped_layouts
from sped_tables.infra import descritor_pva
from sped_tables.infra import guias

sys.path.insert(0, os.path.join(RAIZ_PROJETO, "ferramentas"))
import extrair_guias  # noqa: E402

# trecho no formato do texto que o pdftotext -layout devolve do guia
TEXTO_GUIA = """Guia Prático EFD-ICMS/IPI – Versão 9.9.9
Atualização: 1 de janeiro de 2030

REGISTRO X100: REGISTRO DE TESTE
DO GUIA

          Este registro serve de teste.

          Validação do Registro: não podem ser informados dois ou mais
registros com a mesma combinação de valores dos campos: COD e DT.

Leiaute aplicável até 31/12/2018:
Nº Campo       Descrição                     Tipo Tam Dec Obrig
01 REG         Texto fixo contendo "X100"    C 004 -   O
02 COD         Código                        C 060 -   O
Observações:

Nº Campo       Descrição                     Tipo Tam Dec Obrig
01 REG         Texto fixo contendo "X100"    C 004 -   O
02 COD         Código                        C 060 -   O
03 DT_REF_INI  Data inicial                  N 008* -  O
                                                                Página 7 de 300
                                                         Guia Prático EFD-ICMS/IPI – Versão 9.9.9
Nº Campo       Descrição                     Tipo Tam Dec Obrig
04 MES_REF*    Mês de referência             N 006* -  O
05 OBS         Observações do lançamento,
                       01 - código que não é campo
               com mais texto                C -   -   OC
Observações:
Nível hierárquico - 3
Ocorrência – 1:N

Campo 01 (REG) - Valor Válido: [X100]

Campo 02 (COD) - Preenchimento: informar o código. Validação: o código
deve existir no registro 0200; o campo 03 dos 10 registros não é marca.

Campos 03 a 04 - Preenchimento: datas no formato ddmmaaaa.

Campo 05 (OBS) - Valores Válidos: [0, 1]
Campo 09 (NADA) - Preenchimento: parágrafo de outro assunto.

REGISTRO X990: ENCERRAMENTO
Nº Campo   Descrição   Tipo
01 REG     Texto fixo  C
02 QTD_LIN Quantidade  N
"""


class TestExtrator(unittest.TestCase):

    def setUp(self):
        self.g = extrair_guias.extrair(TEXTO_GUIA, "ICMS")
        self.r = self.g["registros"]["X100"]

    def test_identificacao(self):
        self.assertEqual(self.g["versao"], "9.9.9")
        self.assertEqual(self.g["atualizacao"], "1 de janeiro de 2030")
        self.assertEqual(self.r["titulo"], "REGISTRO DE TESTE DO GUIA")

    def test_vale_a_maior_tabela_e_atravessa_a_pagina(self):
        """Duas tabelas (leiaute até 2018 e o vigente): vale a maior; o
        cabeçalho repetido na quebra de página não a encerra; a nota de
        rodapé sai do nome; a lista recuada "01 - …" não é campo."""
        nomes = [c["nome"] for _n, c in sorted(
            self.r["campos"].items(), key=lambda x: int(x[0]))]
        self.assertEqual(nomes, ["REG", "COD", "DT_REF_INI", "MES_REF",
                                 "OBS"])

    def test_paragrafos(self):
        c = self.r["campos"]
        self.assertEqual(c["1"]["valores"], "[X100]")
        self.assertIn("informar o código", c["2"]["preenchimento"])
        self.assertIn("registro 0200", c["2"]["validacao"])
        # "Campos 03 a 04" vale para os dois
        self.assertIn("ddmmaaaa", c["3"]["preenchimento"])
        self.assertIn("ddmmaaaa", c["4"]["preenchimento"])
        self.assertEqual(c["5"]["valores"], "[0, 1]")
        # campo que a tabela não tem é de outro assunto
        self.assertNotIn("9", c)

    def test_registro(self):
        self.assertIn("COD e DT", self.r["validacao_registro"])
        self.assertEqual(self.r["nivel"], 3)
        self.assertEqual(self.r["ocorrencia"], "1:N")
        self.assertIn("X990", self.g["registros"])


class TestRecursos(unittest.TestCase):
    """Os JSON que viajam com o programa."""

    def test_cobrem_o_leiaute(self):
        for layout, tabela, minimo in (
                ("ICMS", sped_layouts.CAMPOS_ICMS, 265),
                ("CONTRIB", sped_layouts.CAMPOS_CONTRIB, 200)):
            g = guias.carregar(layout)
            self.assertTrue(g["versao"])
            self.assertGreaterEqual(len(g["registros"]), minimo, layout)
            self.assertFalse(set(g["registros"]) - set(tabela), layout)

    def test_textos_conhecidos(self):
        g = guias.carregar("ICMS")
        c190 = g["registros"]["C190"]
        self.assertIn("soma", c190["campos"]["6"]["validacao"])
        self.assertIn("CST_ICMS, CFOP e ALIQ_ICMS",
                      c190["validacao_registro"])
        self.assertIn("000", g["registros"]["E116"]["campos"]["2"]["valores"])
        gc = guias.carregar("CONTRIB")
        self.assertIn("VL_PIS", gc["registros"]["C175"]["campos"]["10"]
                      ["validacao"])

    def test_parametro_nomeado_e_o_mesmo_campo_do_leiaute(self):
        """Onde o parágrafo do guia nomeia o campo, o nome bate com o do
        leiaute na mesma posição — senão a ajuda sairia trocada (e
        `texto_do_campo` a recusa). As exceções são campo a campo, com o
        motivo; isentar o registro inteiro deixava de conferir os outros."""
        # o guia 3.2.4 nomeia diferente do PVA (que o leiaute segue) os
        # campos de estoque/FCP dos registros de ressarcimento de ST
        ressarcimento = {(reg, n) for reg in ("C330", "C380", "C430", "C480",
                                              "C815", "C880")
                         for n in ("8", "10")}
        divergentes = ressarcimento | {
            ("C330", "14"),   # o guia repete VL_UNIT_ICMS_ST_CONV_COMPL
            ("C176", "10"),   # CHAVE_ULT_NFE no guia, CHAVE_NFE_ULT_E no PVA
            ("C500", "39"),   # ENERG_INJET no guia, ENER_INJET no PVA
        }
        for layout, tabela in (("ICMS", sped_layouts.CAMPOS_ICMS),
                               ("CONTRIB", sped_layouts.CAMPOS_CONTRIB)):
            for reg, d in guias.carregar(layout)["registros"].items():
                for n, c in d["campos"].items():
                    nome = c.get("nome_no_paragrafo")
                    if (reg, n) in divergentes:
                        continue
                    if nome and int(n) <= len(tabela[reg]):
                        self.assertEqual(nome, tabela[reg][int(n) - 1],
                                         "%s %s campo %s" % (layout, reg, n))

    def test_texto_de_outro_campo_nao_vira_ajuda(self):
        g = {"registros": {"E111": {"campos": {"5": {
            "nome_no_paragrafo": "IND_BENEFICIO", "validacao": "x"}}}}}
        self.assertEqual(referencias.texto_do_campo(g, "E111", 5, "OUTRO"),
                         {})
        self.assertEqual(referencias.texto_do_campo(
            g, "E111", 5, "IND_BENEFICIO")["validacao"], "x")


DESCRITOR = """<descritor-escrituracao id="1">
<registro id="0000" nivel="0" ocorrencia="1" obrigatorio="1">
  <campo n="1" id="REG" tipo="C" tamanho="[4]" obrigatorio="1"/>
</registro>
<registro id="0150" nivel="2" chave="COD_PART" descricao="Participante &quot;X&quot;">
  <campo n="1" id="REG" tipo="C" tamanho="[4]" obrigatorio="1"/>
  <campo n="2" id="COD_PART" tipo="C" tamanho="60" obrigatorio="1"/>
  <!-- campo excluído do leiaute:
  <campo n="3" id="FANTASMA" tipo="C" obrigatorio="1"/> -->
  <campo n="3" id="NOME" tipo="C" tamanho="100" obrigatorio="1"/>
  <campo n="4'" id="ENDERECO" tipo="C" obrigatorio="1" rotulo="Endereço">
    <valores-validos valores="A=Rua;B=Avenida"/>
  </campo>
</registro>
<registro id="C100" nivel="2" chave="PARTICIPANTE,IND_OP">
  <campo n="1" id="REG" tipo="C" obrigatorio="1"/>
  <campo n="2" id="IND_OP" tipo="C"/>
  <campo n="3" id="IND_EMIT" tipo="C"/>
  <campo n="4" id="PARTICIPANTE" tipo="C" referenciaPesquisa="0150;COD_PART"/>
</registro>
</descritor-escrituracao>"""


class TestDescritor(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.jar = os.path.join(self.tmp, "teste.jar")
        with zipfile.ZipFile(self.jar, "w") as z:
            z.writestr("descritor/escrituracao/ato001/v1/descritor.xml",
                       DESCRITOR)
        self.est, _info = descritor_pva._ler(self.jar)

    def test_campo_comentado_nao_existe(self):
        self.assertEqual(list(self.est["0150"]["campos"]),
                         ["REG", "COD_PART", "NOME", "ENDERECO"])

    def test_n_com_erro_de_digitacao_e_entidades(self):
        c = self.est["0150"]["campos"]["ENDERECO"]
        self.assertEqual(c["n"], 4)
        self.assertEqual(c["significados"], {"A": "Rua", "B": "Avenida"})
        self.assertEqual(self.est["0150"]["descricao"], 'Participante "X"')

    def test_alinhar_ao_leiaute(self):
        """O ENDERECO do PVA é o END do guia: o campo passa a ter o nome do
        leiaute, e a chave e a referência acompanham."""
        al = referencias.alinhar_ao_leiaute(self.est, "ICMS")
        nomes = sped_layouts.CAMPOS_ICMS["0150"][:4]
        self.assertEqual(list(al["0150"]["campos"]), nomes)
        self.assertEqual(al["0150"]["campos"]["COD_PART"]["id_pva"],
                         "COD_PART")
        self.assertEqual(al["0150"]["campos"][nomes[3]]["id_pva"],
                         "ENDERECO")
        self.assertEqual(al["C100"]["campos"]["COD_PART"]["referencia"],
                         "0150;COD_PART")
        self.assertEqual(al["C100"]["chave"], "COD_PART,IND_OPER")


@unittest.skipUnless(descritor_pva.disponivel(), "PVA não instalado")
class TestLeiauteContraPVA(unittest.TestCase):
    """O leiaute do programa tem a **estrutura** do descritor do PVA
    instalado: mesma largura e nenhum campo em outra posição. Nomes podem
    diferir (o guia diz `END`, o PVA `ENDERECO`) — o alinhamento cuida —,
    mas campo deslocado é coluna errada na grade e validação no campo
    vizinho (era o caso do C870, do C181 e do E310)."""

    # largura que o programa mantém diferente de propósito
    LARGURA_PROPRIA = {("CONTRIB", "0200")}    # CEST, ver CLAUDE.md

    def test_estrutura(self):
        for layout, tabela in (("ICMS", sped_layouts.CAMPOS_ICMS),
                               ("CONTRIB", sped_layouts.CAMPOS_CONTRIB)):
            est, _info = descritor_pva.carregar(layout)
            for reg, d in est.items():
                if reg not in tabela:
                    continue
                pva = list(d["campos"])
                nosso = tabela[reg]
                if (layout, reg) not in self.LARGURA_PROPRIA:
                    self.assertEqual(len(nosso), len(pva),
                                     "%s %s" % (layout, reg))
                for i, nome in enumerate(nosso):
                    if nome in pva:
                        self.assertEqual(pva.index(nome), i,
                                         "%s %s.%s fora de posição"
                                         % (layout, reg, nome))


class FonteComGuia(referencias.Referencias):

    def estrutura(self, layout, versao=None):
        return {"C190": {"campos": {
            "REG": {"tipo": "C", "tamanho": "[4]", "obrigatorio": "1"},
            "CST_ICMS": {"tipo": "N", "tamanho": "[3]", "obrigatorio": "1",
                         "rotulo": "CST/ICMS",
                         "descricao": "Código da Situação Tributária"},
            "CFOP": {"tipo": "N", "valores": ["5102"],
                     "significados": {"5102": "Venda"}}}}}, {}

    def guia(self, layout):
        return {"guia": "EFD ICMS/IPI", "versao": "9.9", "registros": {
            "C190": {"titulo": "ANALÍTICO", "objetivo": "Totaliza.",
                     "campos": {"2": {"nome": "CST_ICMS",
                                      "nome_no_paragrafo": "CST_ICMS",
                                      "validacao": "deve existir na tabela"}}}}}


class TestAjuda(unittest.TestCase):

    def setUp(self):
        self._antes = referencias.definir(FonteComGuia())

    def tearDown(self):
        referencias.definir(self._antes)

    def test_campo_junta_descritor_e_guia(self):
        c = ajuda.do_campo("ICMS", "C190", 2, "CST_ICMS")
        self.assertEqual(c["rotulo"], "CST/ICMS")
        self.assertEqual(c["tamanho"], "3")
        self.assertTrue(c["fixo"])
        self.assertEqual(c["obrigatorio"], "sim")
        self.assertEqual(c["validacao"], "deve existir na tabela")
        self.assertEqual(ajuda.do_campo("ICMS", "C190", 3, "CFOP")["valores"],
                         [("5102", "Venda")])

    def test_registro(self):
        r = ajuda.do_registro("ICMS", "C190")
        self.assertEqual(r["titulo"], "ANALÍTICO")
        self.assertEqual(r["fonte"], "Guia Prático EFD ICMS/IPI 9.9")
        self.assertEqual([c["nome"] for c in r["campos"]],
                         sped_layouts.CAMPOS_ICMS["C190"])

    def test_html(self):
        from sped_tables.interface.dialogos import ajuda as dlg
        c = ajuda.do_campo("ICMS", "C190", 2, "CST_ICMS")
        self.assertIn("deve existir na tabela", dlg.dica_html(c))
        pagina = dlg.html_do_registro(ajuda.do_registro("ICMS", "C190"),
                                      "CST_ICMS")
        self.assertIn('name="campo_CST_ICMS"', pagina)
        self.assertIn("◀", pagina)


if __name__ == "__main__":
    unittest.main()

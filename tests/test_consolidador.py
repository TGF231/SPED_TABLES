# -*- coding: utf-8 -*-
"""O consolidador extrai `base/` de uma instalação do PVA — aqui, uma
instalação inventada, com descritores e tabelas mínimos."""

import contextlib
import datetime
import io
import json
import os
import unittest
import zipfile

from consolidador import descritor, extracao, instalacao as I
from consolidador.__main__ import main as principal
from sped_tables.infra import base_referencia
from sped_tables.infra.referencias_base import ReferenciasBase
from tests.fabrica import PastaTemporaria

XML = """<descritor-escrituracao>
<registro id="C100" nivel="2" ocorrencia="1:N" chave="IND_OPER">
  <campo n="1" id="REG" tipo="C" tamanho="[4]"/>
  <!-- <campo n="2" id="EXCLUIDO" tipo="C"/> -->
  <campo n="2" id="IND_OPER" tipo="C" tamanho="[1]">
    <valores-validos valores="0=Entrada;1=Saída"/>
  </campo>
  <validador id="REGRA_TESTE"/>
</registro>
</descritor-escrituracao>"""

VERSOES_ICMS = ("versão=21 COD_LEI, VERSAO, DT_INI, DT_FIM\n"
                "014|1.13|01012020|31122020\n"
                "015|1.14|01012021|31122021\n"
                "016|1.15|01012022|31122022\n"
                "021|1.20|01012027|\n")
VERSOES_CONTRIB = ("versão=6 COD_LEI, VERSAO, DT_INI, DT_FIM\n"
                   "005|101|01012019|31122019\n"
                   "006|101|01012020|\n")


def _pva_falso(raiz, sem_ato=()):
    """Instalação com descritores do ICMS nos atos 014 a 016 (o 015 em
    duas estruturas) e dois do Contribuições."""
    for layout in ("ICMS", "CONTRIB"):
        os.makedirs(I.pasta_tabelas(raiz, layout))
        jar = I.jar_descritor(raiz, layout)
        os.makedirs(os.path.dirname(jar))
        with zipfile.ZipFile(jar, "w") as z:
            if layout == "ICMS":
                for ato, est, v in (("014", 1, 1), ("015", 1, 2),
                                    ("015", 2, 1), ("016", 1, 1)):
                    if ato not in sem_ato:
                        z.writestr("descritor/escrituracao/ato%s/estrutura%03d"
                                   "/v%d/descritor.xml" % (ato, est, v), XML)
            else:
                for est in ("6001", "7007"):
                    z.writestr("descritor/escrituracao/estrutura%s/v1/"
                               "descritor.xml" % est, XML)
    tabelas = {
        ("ICMS", "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE$21$11"): VERSOES_ICMS,
        ("ICMS", "SPEDFISCAL_GLOBAL$CFOP$14$1"): "versão=14 CFOP\n1102|x||\n",
        ("CONTRIB", "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_VERSOES_LEIAUTE"
                    "$6$132"): VERSOES_CONTRIB,
        ("CONTRIB", "metadados"): "\x00",
    }
    for (layout, nome), texto in tabelas.items():
        with open(os.path.join(I.pasta_tabelas(raiz, layout), nome), "w",
                  encoding="latin-1") as fh:
            fh.write(texto)
    return raiz


DATA = datetime.date(2026, 10, 15)


class TestDescritor(unittest.TestCase):

    def test_campo_comentado_nao_existe_e_validador_registrado(self):
        with PastaTemporaria() as p:
            jar = I.jar_descritor(_pva_falso(p), "ICMS")
            est = descritor.ler(jar, descritor.mais_recente(jar))
        self.assertEqual(list(est["C100"]["campos"]), ["REG", "IND_OPER"])
        self.assertEqual(est["C100"]["validadores"], ["REGRA_TESTE"])

    def test_por_versao(self):
        with PastaTemporaria() as p:
            raiz = _pva_falso(p)
            icms = descritor.por_versao(
                I.jar_descritor(raiz, "ICMS"), "ICMS",
                I.tabela_de_versoes({}, "ICMS"))
            contrib = descritor.por_versao(
                I.jar_descritor(raiz, "CONTRIB"), "CONTRIB",
                {"005": ("01012019", "31122019"), "006": ("01012020", "")})
        self.assertEqual(sorted(icms), ["014", "015", "016"])
        self.assertIn("ato015/estrutura002/v1", icms["015"])
        self.assertEqual(list(contrib), ["006"])
        self.assertIn("estrutura7007", contrib["006"])


class TestInstalacao(unittest.TestCase):

    def test_retencao_de_cinco_anos(self):
        with PastaTemporaria() as p:
            pva = I.InstalacaoPVA(_pva_falso(p), data=DATA, fontes=p)
            self.assertEqual(sorted(pva.versoes("ICMS")), ["015", "016"])
            self.assertEqual(sorted(pva.versoes("CONTRIB")), ["006"])
            # 021 é futura e não tem descritor: fica de fora, com aviso
            self.assertTrue(any("021" in a for a in pva.avisos))
            self.assertNotIn("metadados", pva.tabelas())

    def test_versao_vigente_sem_descritor_recusa(self):
        with PastaTemporaria() as p:
            pva = I.InstalacaoPVA(_pva_falso(p, sem_ato=("016",)),
                                  data=DATA, fontes=p)
            with self.assertRaises(I.ConsolidadorErro):
                pva.versoes("ICMS")

    def test_sem_pva_recusa(self):
        with PastaTemporaria() as p:
            with self.assertRaises(I.ConsolidadorErro) as ctx:
                I.InstalacaoPVA(p, data=DATA, fontes=p)
            self.assertIn("faltam", str(ctx.exception))

    def test_vigencia_fora_de_ddmmaaaa_recusa(self):
        """`chave_data` devolve "" para data sem 8 dígitos (e uma data
        trocada para AAAA-MM-DD) e a versão viraria aberta dos dois lados,
        sem erro: a base valeria para qualquer período. O consolidador
        recusa em vez de gravar isso."""
        for ruim in ("2022-01-01", "0101202", "1/1/2022"):
            with PastaTemporaria() as p:
                raiz = _pva_falso(p)
                with open(os.path.join(
                        I.pasta_tabelas(raiz, "ICMS"),
                        "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE$21$11"), "w",
                        encoding="latin-1") as fh:
                    fh.write("versão=21 COD_LEI, VERSAO, DT_INI, DT_FIM\n"
                             "016|1.15|%s|31122022\n" % ruim)
                pva = I.InstalacaoPVA(raiz, data=DATA, fontes=p)
                with self.assertRaises(I.ConsolidadorErro) as ctx:
                    pva.versoes("ICMS")
                self.assertIn("DDMMAAAA", str(ctx.exception))


class TestExtracao(unittest.TestCase):

    def test_extrair_e_compilar(self):
        with PastaTemporaria() as p:
            destino = os.path.join(p, "base")
            pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva")),
                                  data=DATA, fontes=destino)
            m = extracao.extrair(pva, destino)
            self.assertEqual(m["versao"], "2026.10.1")
            self.assertEqual(m["leiautes"], {"ICMS": ["015", "016"],
                                             "CONTRIB": ["006"]})
            self.assertIn("SPEDFISCAL_GLOBAL$CFOP", m["tabelas"])
            with open(os.path.join(destino, "leiaute", "ICMS", "016.json"),
                      encoding="utf-8") as fh:
                d = json.load(fh)
            self.assertEqual(d["dt_ini"], "01012022")
            self.assertEqual(list(d["estrutura"]["C100"]["campos"]),
                             ["REG", "IND_OPER"])
            banco = os.path.join(p, "b.db")
            base_referencia.compilar(destino, banco)
            base = base_referencia.Base(banco)
            self.assertEqual(base.estrutura("ICMS", "016"),
                             pva.estrutura("ICMS", "016"))
            # segunda extração no mesmo mês: n + 1
            self.assertEqual(extracao.extrair(pva, destino)["versao"],
                             "2026.10.2")

    def test_vigencia_gravada_em_ddmmaaaa_e_a_base_acha_a_versao(self):
        """O que `ReferenciasBase.versao_vigente` entende: DDMMAAAA de 8
        dígitos (`dt_fim` vazio = em aberto). Em outro formato a versão
        viraria aberta dos dois lados e o teste de equivalência não veria."""
        with PastaTemporaria() as p:
            destino = os.path.join(p, "base")
            pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva")),
                                  data=DATA, fontes=destino)
            extracao.extrair(pva, destino)
            for layout in base_referencia.LEIAUTES:
                pasta = os.path.join(destino, "leiaute", layout)
                for nome in os.listdir(pasta):
                    with open(os.path.join(pasta, nome),
                              encoding="utf-8") as fh:
                        d = json.load(fh)
                    self.assertRegex(d["dt_ini"], r"^\d{8}$", nome)
                    self.assertRegex(d["dt_fim"], r"^(\d{8})?$", nome)
            banco = os.path.join(p, "b.db")
            base_referencia.compilar(destino, banco)
            ref = ReferenciasBase(base_referencia.Base(banco))
            self.assertEqual(ref.versao_vigente("ICMS", "15062021"), "015")
            self.assertEqual(ref.versao_vigente("ICMS", "15062022"), "016")
            # a 016 terminou em 31/12/2022 e a 021 ficou fora da base
            self.assertIsNone(ref.versao_vigente("ICMS", "15062023"))
            # sem dt_fim a versão continua vigente
            self.assertEqual(ref.versao_vigente("CONTRIB", "15062030"),
                             "006")
            self.assertIsNone(ref.versao_vigente("CONTRIB", "15062019"))

    def test_proxima_versao(self):
        self.assertEqual(extracao.proxima_versao(None, DATA), "2026.10.1")
        self.assertEqual(extracao.proxima_versao("2026.10.4", DATA),
                         "2026.10.5")
        self.assertEqual(extracao.proxima_versao("2026.09.4", DATA),
                         "2026.10.1")


class TestLinhaDeComando(unittest.TestCase):
    """`py -m consolidador`: só o que não regrava o `base/` do repositório
    (o `extrair` de verdade roda à mão, com revisão do `git diff base/`)."""

    def _rodar(self, *argv):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), \
                contextlib.redirect_stderr(erro):
            codigo = principal(list(argv))
        return codigo, saida.getvalue(), erro.getvalue()

    def test_extrair_sem_pva_recusa_e_nao_toca_em_base(self):
        with PastaTemporaria() as p:
            codigo, saida, erro = self._rodar("extrair", "--pva", p)
        self.assertEqual(codigo, 1)
        self.assertEqual(saida, "")
        self.assertIn("faltam", erro)

    def test_compilar_grava_o_banco_e_a_impressao_digital(self):
        with PastaTemporaria() as p:
            banco = os.path.join(p, "b.db")
            codigo, saida, _e = self._rodar("compilar", "--saida", banco)
            self.assertEqual(codigo, 0)
            self.assertIn("compilada", saida)
            with open(banco + ".sha256", encoding="ascii") as fh:
                self.assertEqual(fh.read().strip(),
                                 base_referencia.impressao_digital(banco))
            self.assertTrue(base_referencia.Base(banco).versoes("ICMS"))

    def test_publicar_gera_o_pacote_que_o_programa_importa(self):
        with PastaTemporaria() as p:
            codigo, saida, _e = self._rodar("publicar", "--saida", p)
            self.assertEqual(codigo, 0)
            pacotes = [n for n in os.listdir(p) if n.endswith(".zip")]
            self.assertEqual(len(pacotes), 1)
            self.assertRegex(pacotes[0], r"^base_referencia-\d{4}\.\d{2}\.\d+"
                                         r"\.zip$")
            pacote = base_referencia.inspecionar(os.path.join(p, pacotes[0]))
            self.assertTrue(pacote["confere"])
            self.assertIn(pacote["sha256"], saida)


if __name__ == "__main__":
    unittest.main()

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
from unittest import mock

from consolidador import descritor, extracao, guias, instalacao as I
from consolidador.__main__ import main as principal
from sped_tables.infra import base_referencia
from sped_tables.infra.referencias_base import ReferenciasBase
from tests.fabrica import PastaTemporaria
from tests.test_guias import TEXTO_GUIA

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


def _foto(pasta):
    """`{caminho relativo: bytes}` de tudo o que há em `pasta`: duas fotos
    iguais querem dizer que nada mudou, nem um byte."""
    out = {}
    for raiz, _d, nomes in os.walk(pasta):
        for nome in nomes:
            caminho = os.path.join(raiz, nome)
            with open(caminho, "rb") as fh:
                out[os.path.relpath(caminho, pasta)] = fh.read()
    return out


class _SemTabelas(I.InstalacaoPVA):
    """Versões certas, mas nenhuma tabela de códigos lida."""

    def tabelas(self):
        return {}

    def versoes(self, layout):
        return {"ICMS": {"016": ("01012022", "31122022",
                                 "descritor/escrituracao/ato016/estrutura001"
                                 "/v1/descritor.xml")},
                "CONTRIB": {"006": ("01012020", "",
                                    "descritor/escrituracao/estrutura7007"
                                    "/v1/descritor.xml")}}[layout]


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

    def _base_pronta(self, p):
        """Uma extração boa em `p/base`; devolve `(destino, foto)`."""
        destino = os.path.join(p, "base")
        pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva")),
                              data=DATA, fontes=destino)
        extracao.extrair(pva, destino)
        return destino, _foto(destino)

    def _recusa_e_deixa_intacta(self, p, destino, foto, pva, mensagem,
                                **kwargs):
        """`extrair(pva, destino)` recusa com `mensagem` e o `base/` que
        existia fica byte a byte como estava — e ainda compila."""
        with self.assertRaises(I.ConsolidadorErro) as ctx:
            extracao.extrair(pva, destino, **kwargs)
        self.assertIn(mensagem, str(ctx.exception))
        self.assertEqual(_foto(destino), foto)
        base_referencia.compilar(destino, os.path.join(p, "depois.db"))

    def test_recusa_no_meio_nao_deixa_base_quebrada(self):
        """Antes, o `leiaute/ICMS` era esvaziado e só depois a versão sem
        descritor era descoberta: sobrava o manifesto antigo apontando para
        JSON que não existiam, e o `compilar` caía em `FileNotFoundError`."""
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            ruim = I.InstalacaoPVA(
                _pva_falso(os.path.join(p, "pva2"), sem_ato=("016",)),
                data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(p, destino, foto, ruim,
                                         "não tem descritor")

    def test_tabela_de_versoes_ausente_recusa_e_deixa_base_intacta(self):
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            raiz = _pva_falso(os.path.join(p, "pva2"))
            os.remove(os.path.join(
                I.pasta_tabelas(raiz, "ICMS"),
                "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE$21$11"))
            ruim = I.InstalacaoPVA(raiz, data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(
                p, destino, foto, ruim,
                "Falta a tabela de versões do leiaute ICMS "
                "(SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE)")

    def test_tabela_de_versoes_sem_linhas_recusa(self):
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            raiz = _pva_falso(os.path.join(p, "pva2"))
            with open(os.path.join(
                    I.pasta_tabelas(raiz, "ICMS"),
                    "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE$21$11"), "w",
                    encoding="latin-1") as fh:
                fh.write("versão=21 COD_LEI, VERSAO, DT_INI, DT_FIM\n")
            ruim = I.InstalacaoPVA(raiz, data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(p, destino, foto, ruim,
                                         "nenhuma linha legível")

    def test_pastas_de_tabelas_vazias_recusam(self):
        """PVA recém-instalado, antes do *Atualizar Tabelas*: saía uma base
        sem versão nem tabela, com código 0."""
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            raiz = _pva_falso(os.path.join(p, "pva2"))
            for layout in base_referencia.LEIAUTES:
                pasta = I.pasta_tabelas(raiz, layout)
                for nome in os.listdir(pasta):
                    os.remove(os.path.join(pasta, nome))
            ruim = I.InstalacaoPVA(raiz, data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(p, destino, foto, ruim,
                                         "Falta a tabela de versões")
            # e sem base anterior não nasce uma base vazia
            novo = os.path.join(p, "novo")
            with self.assertRaises(I.ConsolidadorErro):
                extracao.extrair(ruim, novo)
            self.assertFalse(os.path.exists(novo))

    def test_leiaute_sem_nenhuma_versao_recusa(self):
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            raiz = _pva_falso(os.path.join(p, "pva2"))
            with open(os.path.join(
                    I.pasta_tabelas(raiz, "ICMS"),
                    "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE$21$11"), "w",
                    encoding="latin-1") as fh:
                # só versão fora da janela de retenção
                fh.write("versão=21 COD_LEI, VERSAO, DT_INI, DT_FIM\n"
                         "014|1.13|01012020|31122020\n")
            ruim = I.InstalacaoPVA(raiz, data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(p, destino, foto, ruim,
                                         "O leiaute ICMS ficou sem nenhuma "
                                         "versão")

    def test_base_sem_tabelas_recusa(self):
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            ruim = _SemTabelas(_pva_falso(os.path.join(p, "pva2")),
                               data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(p, destino, foto, ruim,
                                         "Nenhuma tabela de códigos")

    def test_planilha_de_ncm_ilegivel_recusa_antes_de_gravar(self):
        with PastaTemporaria() as p:
            destino, foto = self._base_pronta(p)
            pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva2")),
                                  data=DATA, fontes=destino)
            self._recusa_e_deixa_intacta(
                p, destino, foto, pva, "Não consegui ler a planilha de NCM",
                ncm_xlsx=os.path.join(p, "nao_existe.xlsx"))
            # planilha que abre mas não traz NCM
            import openpyxl
            vazia = os.path.join(p, "vazia.xlsx")
            wb = openpyxl.Workbook()
            wb.active.append(["Código", "Descrição"])
            wb.save(vazia)
            self._recusa_e_deixa_intacta(
                p, destino, foto, pva, "não traz nenhum NCM", ncm_xlsx=vazia)

    def test_ncm_da_planilha_entra_na_base(self):
        import openpyxl
        with PastaTemporaria() as p:
            planilha = os.path.join(p, "ncm.xlsx")
            wb = openpyxl.Workbook()
            for linha in (["Código", "Descrição"], ["0401.20.10", "x"],
                          ["04012020", "y"], ["0401", "capítulo"]):
                wb.active.append(linha)
            wb.save(planilha)
            destino = os.path.join(p, "base")
            pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva")),
                                  data=DATA, fontes=destino)
            m = extracao.extrair(pva, destino, ncm_xlsx=planilha)
            self.assertEqual(m["origem"]["ncm"], "ncm.xlsx")
            with open(os.path.join(destino, "ncm", "vigente.txt"),
                      encoding="utf-8") as fh:
                self.assertEqual(fh.read().split(), ["04012010", "04012020"])

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


class _Rodar:
    def _rodar(self, *argv):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), \
                contextlib.redirect_stderr(erro):
            codigo = principal(list(argv))
        return codigo, saida.getvalue(), erro.getvalue()


class TestGuiaNoManifesto(_Rodar, unittest.TestCase):
    """`guia` regrava os guias de `base/guias/` **e o manifesto junto**: sem
    isso o pacote saía com o mesmo `AAAA.MM.n` e conteúdo diferente, e duas
    bases distintas passavam a ter a mesma identidade."""

    def _base_com_guias_fora(self, p):
        destino = os.path.join(p, "base")
        pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva")),
                              data=DATA, fontes=destino)
        return destino, extracao.extrair(pva, destino)

    def _guia(self, destino, *argv, texto=TEXTO_GUIA):
        """Roda `guia` sobre o `destino` com o texto do PDF trocado."""
        with mock.patch.object(base_referencia, "pasta_fontes",
                               lambda: destino), \
                mock.patch.object(guias, "texto_do_pdf", lambda pdf: texto):
            return self._rodar("guia", *argv)

    def _manifesto(self, destino):
        with open(os.path.join(destino, "manifesto.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_guia_avanca_a_versao_e_registra_o_guia(self):
        with PastaTemporaria() as p:
            destino, antes = self._base_com_guias_fora(p)
            banco_antes = os.path.join(p, "antes.db")
            base_referencia.compilar(destino, banco_antes)
            codigo, saida, erro = self._guia(
                destino, "ICMS", "guia.pdf", "--data", "2026-10-20")
            self.assertEqual((codigo, erro), (0, ""))
            m = self._manifesto(destino)
            self.assertEqual(antes["versao"], "2026.10.1")
            self.assertEqual(m["versao"], "2026.10.2")
            self.assertEqual(m["data"], "2026-10-20")
            self.assertEqual(m["origem"]["guias"]["ICMS"],
                             "EFD ICMS/IPI 9.9.9")
            # o outro guia, o leiaute e as tabelas ficam como estavam
            self.assertEqual(m["origem"]["guias"]["CONTRIB"],
                             antes["origem"]["guias"]["CONTRIB"])
            self.assertEqual(m["leiautes"], antes["leiautes"])
            self.assertEqual(m["tabelas"], antes["tabelas"])
            self.assertIn("2026.10.2", saida)
            # e a base compilada agora é mais nova que a anterior
            banco = os.path.join(p, "depois.db")
            base_referencia.compilar(destino, banco)
            nova = base_referencia.Base(banco)
            velha = base_referencia.Base(banco_antes)
            self.assertGreater(
                base_referencia.chave_da_versao(nova.manifesto()["versao"]),
                base_referencia.chave_da_versao(velha.manifesto()["versao"]))
            self.assertEqual(nova.guia("ICMS")["versao"], "9.9.9")

    def test_guia_aceita_versao_e_data_como_o_extrair(self):
        with PastaTemporaria() as p:
            destino, _antes = self._base_com_guias_fora(p)
            codigo, _s, erro = self._guia(
                destino, "ICMS", "guia.pdf", "--data", "2026-11-03",
                "--versao", "2026.11.7")
            self.assertEqual((codigo, erro), (0, ""))
            m = self._manifesto(destino)
            self.assertEqual((m["versao"], m["data"]),
                             ("2026.11.7", "2026-11-03"))

    def test_guia_que_falha_nao_toca_no_manifesto(self):
        """O manifesto só é regravado depois de o guia ter sido gravado."""
        def falha(pdf):
            raise SystemExit("pdftotext não encontrado")
        with PastaTemporaria() as p:
            destino, _antes = self._base_com_guias_fora(p)
            foto = _foto(destino)
            with mock.patch.object(base_referencia, "pasta_fontes",
                                   lambda: destino), \
                    mock.patch.object(guias, "texto_do_pdf", falha):
                with self.assertRaises(SystemExit):
                    self._rodar("guia", "ICMS", "guia.pdf")
            self.assertEqual(_foto(destino), foto)

    def test_guia_sem_manifesto_grava_so_o_guia(self):
        """Pasta de fontes ainda sem manifesto (nada extraído): o guia entra
        e o próximo `extrair` o registra — não há versão para avançar."""
        with PastaTemporaria() as p:
            codigo, saida, erro = self._guia(p, "ICMS", "guia.pdf")
            self.assertEqual((codigo, erro), (0, ""))
            self.assertTrue(os.path.isfile(
                os.path.join(p, "guias", "ICMS.json")))
            self.assertFalse(os.path.exists(
                os.path.join(p, "manifesto.json")))
            self.assertIn("extrair", saida)


class TestLinhaDeComando(_Rodar, unittest.TestCase):
    """`python -m consolidador`: só o que não regrava o `base/` do repositório
    (o `extrair` de verdade roda à mão, com revisão do `git diff base/`)."""

    def test_extrair_sem_pva_recusa_e_nao_toca_em_base(self):
        base = base_referencia.pasta_fontes()
        antes = _foto(base)
        self.assertIn("manifesto.json", antes)
        with PastaTemporaria() as p:
            codigo, saida, erro = self._rodar("extrair", "--pva", p)
        self.assertEqual(codigo, 1)
        self.assertEqual(saida, "")
        self.assertIn("faltam", erro)
        self.assertEqual(_foto(base), antes)

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

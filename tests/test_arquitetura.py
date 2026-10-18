# -*- coding: utf-8 -*-
"""A regra de dependência entre as camadas — e o que ela permite.

    interface  ──►  aplicacao  ──►  dominio
        │               │             ▲
        └──────►  infra ──────────────┘

* `dominio` não importa ninguém de fora (nem Qt);
* `infra` pode usar o domínio, nunca a aplicação nem a interface;
* `aplicacao` usa domínio e infra, nunca a interface nem o Qt;
* `interface` usa todo mundo.

Ver ARQUITETURA.md. Import feito dentro de função conta igual: a regra é
sobre dependência, não sobre onde a linha está.
"""

import ast
import os
import unittest

from sped_tables.aplicacao import envio_pva, montagem
from sped_tables.aplicacao.sessao import Sessao
from sped_tables.dominio import referencias, revisao, rotinas
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import CNPJ_TESTE, PastaTemporaria, contrib_basico, ler
from tests.fabrica import icms_basico

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACOTE = os.path.join(RAIZ, "sped_tables")

PROIBIDO = {
    "dominio": ("sped_tables.infra", "sped_tables.aplicacao",
                "sped_tables.interface", "PyQt6"),
    "infra": ("sped_tables.aplicacao", "sped_tables.interface", "PyQt6"),
    "aplicacao": ("sped_tables.interface", "PyQt6"),
}
# a raiz de composição é o único ponto da aplicação que nomeia a
# implementação concreta de uma porta
EXCECOES = {("aplicacao", "montagem.py", "sped_tables.infra.referencias_pva")}


def _imports(caminho):
    with open(caminho, encoding="utf-8") as fh:
        arvore = ast.parse(fh.read())
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for a in no.names:
                yield no.lineno, a.name
        elif isinstance(no, ast.ImportFrom) and no.module:
            yield no.lineno, no.module


class TestRegraDeDependencia(unittest.TestCase):

    def test_camadas_so_dependem_para_dentro(self):
        violacoes = []
        for camada, proibidos in PROIBIDO.items():
            pasta = os.path.join(PACOTE, camada)
            for nome in sorted(os.listdir(pasta)):
                if not nome.endswith(".py"):
                    continue
                for linha, mod in _imports(os.path.join(pasta, nome)):
                    if (camada, nome, mod) in EXCECOES:
                        continue
                    if mod.startswith(proibidos):
                        violacoes.append("%s/%s:%d importa %s"
                                         % (camada, nome, linha, mod))
        self.assertEqual(violacoes, [])

    def test_sped_tables_nunca_importa_o_consolidador(self):
        """O consolidador roda na máquina de quem compila e pode usar o
        `sped_tables`; o contrário prenderia o programa a uma ferramenta
        que ele não leva (nem lê o PVA de quem o usa)."""
        violacoes = []
        for raiz, _d, nomes in os.walk(PACOTE):
            for nome in nomes:
                if not nome.endswith(".py"):
                    continue
                caminho = os.path.join(raiz, nome)
                for linha, mod in _imports(caminho):
                    if mod.split(".")[0] == "consolidador":
                        violacoes.append("%s:%d importa %s" % (
                            os.path.relpath(caminho, RAIZ), linha, mod))
        self.assertEqual(violacoes, [])

    def test_ninguem_importa_o_lancador(self):
        for raiz, _d, nomes in os.walk(PACOTE):
            for nome in nomes:
                if nome.endswith(".py"):
                    for _l, mod in _imports(os.path.join(raiz, nome)):
                        self.assertNotEqual(mod, "sped_editor", nome)


class FonteDeTeste(referencias.Referencias):
    """Tabelas oficiais inventadas: a regra roda sem PVA na máquina."""

    nome = "teste"

    def __init__(self, cfops=(), prazo=""):
        self._cfops = set(cfops)
        self._prazo = prazo

    def cfops_com_credito(self, data_ref=None):
        return set(self._cfops), "teste"

    def naturezas_cfop_credito(self, data_ref=None):
        return {c: "01" for c in self._cfops}

    def prazo_entrega(self, mes_ano):
        return self._prazo


class TestPorta(unittest.TestCase):
    """O domínio pergunta à porta; trocar a fonte troca a resposta."""

    def setUp(self):
        self._anterior = referencias.definir(None)

    def tearDown(self):
        referencias.definir(self._anterior)

    def _doc(self, m):
        with PastaTemporaria() as p:
            return SpedDocument.carregar(m.gravar(p))

    def test_sem_fonte_as_regras_se_abstem(self):
        doc = self._doc(contrib_basico())
        self.assertEqual(rotinas.verificar_cfop_sem_credito(doc), [])
        self.assertEqual(revisao.verificar_0900_ausente(doc, "20990101"), [])
        r = doc.recalcular_bloco_m()
        self.assertIn("não está disponível", r["creditos_motivo"])

    def test_cfop_sem_credito_com_tabela_de_teste(self):
        referencias.definir(FonteDeTeste(cfops={"1403"}))  # 1102 fora
        doc = self._doc(contrib_basico())
        oc = rotinas.verificar_cfop_sem_credito(doc)
        self.assertEqual({o.tributo for o in oc}, {"PIS", "COFINS"})

    def test_0900_com_prazo_de_teste(self):
        referencias.definir(FonteDeTeste(prazo="30092026"))
        doc = self._doc(contrib_basico())
        self.assertEqual(revisao.verificar_0900_ausente(doc, "20260930"), [])
        (p,) = revisao.verificar_0900_ausente(doc, "20261001")
        self.assertIn("30/09/2026", p.descricao)

    def test_bloco_m_pede_as_naturezas_a_porta(self):
        referencias.definir(FonteDeTeste(cfops={"1102"}))
        doc = self._doc(contrib_basico())
        r = doc.recalcular_bloco_m()
        self.assertEqual(r["creditos"]["PIS"]["descontado"], 1.65)

    def test_montagem_liga_e_devolve_a_anterior(self):
        fonte = FonteDeTeste()
        montagem.configurar(fonte)
        self.assertIs(referencias.atual(), fonte)


class TestSessao(unittest.TestCase):
    """O caso de uso do arquivo aberto, sem tela nenhuma."""

    def test_abrir_salvar_fechar(self):
        with PastaTemporaria() as p:
            caminho = icms_basico().gravar(p)
            s = Sessao()
            r = s.abrir(caminho)
            self.assertTrue(s.aberta)
            self.assertEqual(r.entrada["cnpj"], CNPJ_TESTE)
            self.assertEqual(s.identificacao()["periodo"], "08/2026")
            s.marcar_alterado()
            destino = os.path.join(p, "copia.txt")
            s.salvar(destino)
            self.assertFalse(s.alterado)
            self.assertEqual(s.caminho, destino)
            self.assertEqual(ler(destino), ler(caminho))
            s.fechar()
            self.assertFalse(s.aberta)

    def test_falha_ao_salvar_mantem_o_alterado(self):
        with PastaTemporaria() as p:
            s = Sessao()
            s.abrir(icms_basico().gravar(p))
            reg = next(r for r in s.doc.registros if r.reg == "0200")
            reg.set_valor(2, "TRAVESSÃO — FORA DO LATIN-1")
            s.marcar_alterado()
            with self.assertRaises(ValueError):
                s.salvar()
            self.assertTrue(s.alterado)

    def test_copia_de_emergencia_so_com_alteracao(self):
        with PastaTemporaria() as p:
            s = Sessao()
            s.abrir(icms_basico().gravar(p))
            self.assertIsNone(s.copia_de_emergencia())
            s.marcar_alterado()
            self.assertTrue(os.path.isfile(s.copia_de_emergencia()))


class TestEnvioPva(unittest.TestCase):

    def test_arquivo_nao_salvo(self):
        self.assertIn("Salve", envio_pva.problema_do_arquivo(""))
        self.assertEqual(envio_pva.problema_do_arquivo(__file__), "")

    def test_desfechos(self):
        d = envio_pva.desfecho
        self.assertEqual(d({"estado": "validando", "mensagem": "ok"}),
                         (envio_pva.STATUS, "ok"))
        self.assertEqual(d({"estado": "cancelado", "mensagem": "c"})[0],
                         envio_pva.STATUS)
        self.assertEqual(d({"estado": "pva_ocupado", "mensagem": "m"})[0],
                         envio_pva.INFORMAR)
        forma, msg = d({"estado": "erro"})
        self.assertEqual(forma, envio_pva.ALERTAR)
        self.assertTrue(msg)

    def test_pre_checagem_nunca_levanta(self):
        self.assertEqual(envio_pva.pre_checagem(object()), [])


class TestCanal(unittest.TestCase):
    """A versão declara o canal; release só mostra ação pronta."""

    def test_canais(self):
        from sped_tables import version
        casos = {"0.53.0": "dev", "1.0.0": "release", "1.0.0-rc.1": "rc",
                 "1.1.0-beta.2": "beta", "1.1.0-alpha.1": "alpha",
                 "1.2.0-nightly.5": "dev", "lixo": "dev"}
        for versao, canal in casos.items():
            with self.subTest(versao=versao):
                self.assertEqual(version.canal(versao), canal)

    def test_acao_nao_pronta_some_da_release(self):
        import dataclasses
        from unittest import mock
        from sped_tables.interface import acoes
        verde = dataclasses.replace(acoes.ACOES[0], atributo="act_x",
                                    pronta=False)
        with mock.patch.object(acoes, "ACOES", acoes.ACOES + (verde,)):
            self.assertIn(verde, acoes.visiveis("1.1.0-beta.1"))
            self.assertNotIn(verde, acoes.visiveis("1.1.0"))


if __name__ == "__main__":
    unittest.main()

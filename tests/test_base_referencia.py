# -*- coding: utf-8 -*-
"""A base de referência: compilação reproduzível, leitura, a escolha entre
a embutida e a importada, e a importação que recusa o que não serve."""

import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import unittest
import zipfile
from unittest import mock

from sped_tables.infra import base_referencia as B
from sped_tables.infra import dados
from tests import base_teste
from tests.fabrica import PastaTemporaria, ler


class TestVersao(unittest.TestCase):

    def test_chave_da_versao_compara_como_numero(self):
        self.assertEqual(B.chave_da_versao("2026.10.1"), (2026, 10, 1))
        self.assertGreater(B.chave_da_versao("2026.10.1"),
                           B.chave_da_versao("2026.9.3"))
        for invalida in ("", "x.y", None, "2026.a.1"):
            self.assertEqual(B.chave_da_versao(invalida), ())

    def test_arquivo_da_tabela_troca_o_cifrao(self):
        self.assertEqual(B.arquivo_da_tabela("SPEDFISCAL_GLOBAL$CFOP"),
                         "SPEDFISCAL_GLOBAL@CFOP.txt")


class TestCompilacao(unittest.TestCase):

    def test_conteudo(self):
        with PastaTemporaria() as p:
            base = B.Base(base_teste.compilada(p, ncm=["22030000"]))
            self.assertEqual(base.manifesto()["versao"], "2026.10.1")
            self.assertEqual(sorted(base.versoes("ICMS")), ["019", "020"])
            self.assertEqual(base.versoes("ICMS")["020"],
                             ("01012026", "", "teste/ICMS/020"))
            est = base.estrutura("ICMS", "019")
            self.assertEqual(list(est["C100"]["campos"]),
                             ["REG", "IND_OPER", "IND_EMIT"])
            self.assertIsNone(base.estrutura("ICMS", "014"))
            texto, versao = base.tabelas()["SPEDFISCAL_GLOBAL$CFOP"]
            self.assertEqual(versao, 14)
            self.assertEqual(texto.splitlines(),
                             base_teste.TABELA_CFOP.splitlines())
            self.assertEqual(base.guia("ICMS")["versao"], "9.9")
            self.assertEqual(base.guia("CONTRIB"), {})
            self.assertEqual(base.ncm_vigente(), {"22030000"})

    def test_sem_ncm_e_none(self):
        with PastaTemporaria() as p:
            self.assertIsNone(B.Base(base_teste.compilada(p)).ncm_vigente())

    def test_reproduzivel(self):
        with PastaTemporaria() as p:
            fontes = base_teste.escrever(os.path.join(p, "fontes"))
            um, dois = os.path.join(p, "um.db"), os.path.join(p, "dois.db")
            B.compilar(fontes, um)
            B.compilar(fontes, dois)
            self.assertEqual(B.impressao_digital(um),
                             B.impressao_digital(dois))
            with open(um + ".sha256", encoding="ascii") as fh:
                self.assertEqual(fh.read().strip(), B.impressao_digital(um))

    def test_fim_de_linha_nao_muda_o_banco(self):
        """O git troca LF por CRLF no checkout do Windows: a compilação
        normaliza, senão cada máquina daria um banco."""
        with PastaTemporaria() as p:
            fontes = base_teste.escrever(os.path.join(p, "fontes"))
            um = os.path.join(p, "um.db")
            B.compilar(fontes, um)
            tabela = os.path.join(fontes, "tabelas",
                                  B.arquivo_da_tabela("SPEDFISCAL_GLOBAL$CFOP"))
            with open(tabela, encoding="utf-8") as fh:
                texto = fh.read()
            with open(tabela, "w", encoding="utf-8", newline="\r\n") as fh:
                fh.write(texto)
            dois = os.path.join(p, "dois.db")
            B.compilar(fontes, dois)
            self.assertEqual(B.impressao_digital(um),
                             B.impressao_digital(dois))


class TestBaseIlegivel(unittest.TestCase):

    def _banco(self, pasta, n, manifesto):
        caminho = os.path.join(pasta, "%d.db" % n)
        with contextlib.closing(sqlite3.connect(caminho)) as con:
            con.execute("CREATE TABLE manifesto (conteudo TEXT NOT NULL)")
            con.execute("INSERT INTO manifesto VALUES (?)", (manifesto,))
            con.commit()
        return caminho

    def test_manifesto_que_nao_serve(self):
        """SQLite legível, mas sem manifesto de base: `BaseInvalida`, nunca
        `AttributeError`/`TypeError` escapando para quem abre o programa."""
        with PastaTemporaria() as p:
            for n, manifesto in enumerate(
                    ("[]", "{}", '{"versao": "x"}', "isto nao e json")):
                with self.assertRaises(B.BaseInvalida, msg=manifesto):
                    B.Base(self._banco(p, n, manifesto))

    def test_arquivo_inexistente(self):
        with PastaTemporaria() as p:
            with self.assertRaises(B.BaseInvalida):
                B.Base(os.path.join(p, "nao_existe.db"))


class TestEmUso(unittest.TestCase):
    """A mais nova entre a embutida e a importada; ilegível é avisada."""

    def setUp(self):
        pasta = PastaTemporaria()
        self.tmp = pasta.__enter__()
        self.addCleanup(pasta.__exit__, None, None, None)
        self.avisos = []
        dados.ao_avisar(self.avisos.append)
        self.addCleanup(dados.ao_avisar, None)
        self.embutida = os.path.join(self.tmp, "embutida.db")
        self.importada = os.path.join(self.tmp, "importada.db")
        for alvo, valor in (("caminho_embutido", self.embutida),
                            ("caminho_importado", self.importada)):
            p = mock.patch.object(B, alvo, lambda v=valor: v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(B, "compilar_se_preciso", lambda: False)
        p.start()
        self.addCleanup(p.stop)

    def _base(self, destino, versao, **k):
        shutil.copy(base_teste.compilada(self.tmp, versao=versao, **k),
                    destino)

    def test_vale_a_mais_nova(self):
        self._base(self.embutida, "2026.10.1")
        self._base(self.importada, "2026.11.1")
        base, origem = B.em_uso()
        self.assertEqual((base.manifesto()["versao"], origem),
                         ("2026.11.1", "importada"))
        self._base(self.importada, "2026.09.3")
        self.assertEqual(B.em_uso()[1], "embutida")

    def test_importada_ilegivel_vale_a_embutida(self):
        """Vazia, lixo ou truncada: aviso, vale a embutida, nada é apagado."""
        self._base(self.embutida, "2026.10.1")
        completa = ler(base_teste.compilada(self.tmp, versao="2026.11.1"))
        for lixo in (b"", b"isto nao e sqlite",
                     completa[:len(completa) // 2]):
            with open(self.importada, "wb") as fh:
                fh.write(lixo)
            self.avisos.clear()
            with self.assertLogs("sped_tables", "WARNING"):
                base, origem = B.em_uso()
            self.assertEqual(origem, "embutida")
            self.assertEqual(base.manifesto()["versao"], "2026.10.1")
            self.assertEqual(len(self.avisos), 1, lixo[:20])
            self.assertIn("importada", self.avisos[0])
            self.assertEqual(ler(self.importada), lixo)   # nunca mexida

    def test_importada_de_esquema_novo_vale_a_embutida(self):
        """Base importada por um programa mais novo, já na pasta de dados:
        o programa antigo não a lê, avisa, usa a embutida e abre."""
        self._base(self.embutida, "2026.10.1")
        self._base(self.importada, "2026.12.1", esquema=B.ESQUEMA + 1)
        with self.assertLogs("sped_tables", "WARNING"):
            base, origem = B.em_uso()
        self.assertEqual((base.manifesto()["versao"], origem),
                         ("2026.10.1", "embutida"))
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("importada", self.avisos[0])
        self.assertTrue(os.path.exists(self.importada))   # nunca apagada

    def test_esquema_novo_e_ilegivel(self):
        with PastaTemporaria() as p:
            caminho = base_teste.compilada(p, esquema=B.ESQUEMA + 1)
            with self.assertRaises(B.EsquemaNovo):
                B.Base(caminho)
            self.assertTrue(issubclass(B.EsquemaNovo, B.BaseInvalida))

    def test_nenhuma_base(self):
        base, motivo = B.em_uso()
        self.assertIsNone(base)
        self.assertIn("nenhuma", motivo)


class TestImportacao(unittest.TestCase):

    def setUp(self):
        pasta = PastaTemporaria()
        self.tmp = pasta.__enter__()
        self.addCleanup(pasta.__exit__, None, None, None)
        self.embutida = base_teste.compilada(self.tmp, versao="2026.10.1")
        self.importada = os.path.join(self.tmp, "dados", B.ARQUIVO)
        for alvo, valor in (("caminho_embutido", self.embutida),
                            ("caminho_importado", self.importada)):
            p = mock.patch.object(B, alvo, lambda v=valor: v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(B, "compilar_se_preciso", lambda: False)
        p.start()
        self.addCleanup(p.stop)

    def _pacote(self, versao, **k):
        banco = base_teste.compilada(self.tmp, versao=versao, **k)
        return B.empacotar(banco, os.path.join(self.tmp, versao + ".zip"))

    def _sobras(self):
        """Arquivos temporários que a importação deixou ao lado da base."""
        pasta = os.path.dirname(self.importada)
        if not os.path.isdir(pasta):
            return []
        return [n for n in os.listdir(pasta) if n != B.ARQUIVO]

    def test_mais_nova_entra(self):
        m = B.importar(self._pacote("2026.11.1"))
        self.assertEqual(m["versao"], "2026.11.1")
        base, origem = B.em_uso()
        self.assertEqual((base.manifesto()["versao"], origem),
                         ("2026.11.1", "importada"))
        self.assertEqual(self._sobras(), [])

    def test_igual_ou_mais_antiga_recusada(self):
        for versao in ("2026.10.1", "2026.09.9"):
            with self.assertRaises(B.BaseRecusada) as ctx:
                B.importar(self._pacote(versao))
            self.assertIn("não é mais nova", str(ctx.exception))
        self.assertFalse(os.path.exists(self.importada))
        self.assertEqual(self._sobras(), [])

    def _adulterar(self, zip_ok, destino, banco=None, manifesto=None,
                   sem=()):
        with zipfile.ZipFile(zip_ok) as z:
            membros = {n: z.read(n) for n in z.namelist()}
        if banco is not None:
            membros[B.ARQUIVO] = banco
        if manifesto is not None:
            membros["manifesto.json"] = json.dumps(manifesto).encode()
        with zipfile.ZipFile(destino, "w") as z:
            for nome, conteudo in membros.items():
                if nome not in sem:
                    z.writestr(nome, conteudo)
        return destino

    def test_pacote_malformado_recusado_sem_tocar_na_base(self):
        ok = self._pacote("2026.11.1")
        with zipfile.ZipFile(ok) as z:
            manifesto = json.loads(z.read("manifesto.json"))
            banco = z.read(B.ARQUIVO)
        casos = {
            "sem banco": self._adulterar(ok, os.path.join(self.tmp, "a.zip"),
                                         sem=(B.ARQUIVO,)),
            "sem manifesto": self._adulterar(
                ok, os.path.join(self.tmp, "b.zip"), sem=("manifesto.json",)),
            "digital": self._adulterar(ok, os.path.join(self.tmp, "c.zip"),
                                       banco=banco + b"x"),
            "manifesto de outra base": self._adulterar(
                ok, os.path.join(self.tmp, "d.zip"),
                manifesto=dict(manifesto, versao="2027.01.1")),
        }
        lixo = os.path.join(self.tmp, "e.zip")
        with open(lixo, "wb") as fh:
            fh.write(b"nao e zip")
        casos["não é zip"] = lixo
        for nome, caminho in casos.items():
            with self.assertRaises(B.BaseRecusada, msg=nome):
                B.importar(caminho)
        self.assertFalse(os.path.exists(self.importada))
        self.assertEqual(self._sobras(), [])
        self.assertEqual(B.em_uso()[1], "embutida")

    def test_membro_grande_demais(self):
        with mock.patch.object(B, "LIMITE_PACOTE", 10):
            with self.assertRaises(B.BaseRecusada) as ctx:
                B.inspecionar(self._pacote("2026.11.1"))
        self.assertIn("grande demais", str(ctx.exception))

    def test_esquema_novo_pede_programa_novo(self):
        """Pacote de esquema novo montado à mão — `empacotar` já recusa base
        que este programa não lê —, íntegro e coerente: só o esquema o
        reprova, e a mensagem manda atualizar o programa."""
        banco = ler(base_teste.compilada(self.tmp, versao="2026.11.1",
                                         esquema=B.ESQUEMA + 1))
        manifesto = {"esquema": B.ESQUEMA + 1, "versao": "2026.11.1",
                     "sha256": hashlib.sha256(banco).hexdigest()}
        pacote = os.path.join(self.tmp, "novo.zip")
        with zipfile.ZipFile(pacote, "w") as z:
            z.writestr(B.ARQUIVO, banco)
            z.writestr("manifesto.json", json.dumps(manifesto))
        self.assertTrue(B.inspecionar(pacote)["confere"])
        with self.assertRaises(B.BaseRecusada) as ctx:
            B.importar(pacote)
        self.assertIn("Atualize o programa", str(ctx.exception))
        self.assertFalse(os.path.exists(self.importada))
        self.assertEqual(self._sobras(), [])

    def test_empacotar_recusa_base_ilegivel(self):
        lixo = os.path.join(self.tmp, "lixo.db")
        with open(lixo, "wb") as fh:
            fh.write(b"isto nao e sqlite")
        with self.assertRaises(B.BaseInvalida):
            B.empacotar(lixo, os.path.join(self.tmp, "lixo.zip"))

    def test_inspecionar_mostra_a_digital(self):
        pacote = B.inspecionar(self._pacote("2026.11.1"))
        self.assertTrue(pacote["confere"])
        self.assertEqual(pacote["sha256"],
                         hashlib.sha256(pacote["banco"]).hexdigest())


if __name__ == "__main__":
    unittest.main()

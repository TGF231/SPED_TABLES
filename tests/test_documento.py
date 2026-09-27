# -*- coding: utf-8 -*-
"""Carregar, gravar e editar a estrutura do documento."""

import os
import unittest

from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico, ler


class TestIdaEVolta(unittest.TestCase):
    """Abrir e salvar sem mexer em nada devolve o mesmo arquivo."""

    def test_icms_e_contrib_voltam_identicos(self):
        for montador in (icms_basico(), contrib_basico()):
            with self.subTest(layout=montador.layout), PastaTemporaria() as p:
                caminho = montador.gravar(p)
                original = ler(caminho)
                doc = SpedDocument.carregar(caminho)
                self.assertEqual(doc.layout, montador.layout)
                doc.salvar(caminho)
                self.assertEqual(ler(caminho), original)

    def test_ordem_dos_9900_do_arquivo_e_mantida(self):
        """Cada ERP ordena os 9900 do seu jeito; nos arquivos reais do
        cliente A, abrir e salvar reordenava 31 e 39 linhas."""
        with PastaTemporaria() as p:
            caminho = icms_basico().gravar(p)
            linhas = ler(caminho).split(b"\r\n")
            ix = [i for i, l in enumerate(linhas) if l.startswith(b"|9900|")]
            linhas[ix[0]:ix[-1] + 1] = linhas[ix[0]:ix[-1] + 1][::-1]
            with open(caminho, "wb") as fh:
                fh.write(b"\r\n".join(linhas))
            original = ler(caminho)
            doc = SpedDocument.carregar(caminho)
            doc.salvar(caminho)
            self.assertEqual(ler(caminho), original)
            # tipo que some sai da lista; os demais não mudam de lugar
            for c190 in [r for r in doc.registros if r.reg == "C190"]:
                doc.remover_registro(c190)
            tipos = [l.split("|")[2] for l in doc.gerar_texto().splitlines()
                     if l.startswith("|9900|")]
            antes = [l.split(b"|")[2].decode() for l in original.split(b"\r\n")
                     if l.startswith(b"|9900|")]
            self.assertEqual(tipos, [t for t in antes if t != "C190"])

    def test_hierarquia_pai_filho(self):
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(icms_basico().gravar(p))
        c100 = next(r for r in doc.registros if r.reg == "C100")
        self.assertEqual([f.reg for f in c100.filhos],
                         ["C170", "C170", "C170", "C190"])
        self.assertIn("C100", doc.tipos_raiz_do_bloco("C"))
        self.assertNotIn("C170", doc.tipos_raiz_do_bloco("C"))


class TestEncoding(unittest.TestCase):
    TEXTO = "AÇÚCAR REFINADO UNIÃO"

    def _com_descricao(self, pasta, encoding):
        m = icms_basico()
        for campos in m.linhas:
            if campos[0] == "0200":
                campos[2] = self.TEXTO
                break
        return m.gravar(pasta, encoding=encoding)

    def test_utf8_e_lido_como_utf8_e_gravado_em_latin1(self):
        with PastaTemporaria() as p:
            caminho = self._com_descricao(p, "utf-8")
            doc = SpedDocument.carregar(caminho)
            self.assertTrue(doc.encoding_lido.startswith("utf-8"))
            descr = next(r.valor(2) for r in doc.registros if r.reg == "0200")
            self.assertEqual(descr, self.TEXTO)
            doc.salvar(caminho)
            self.assertIn(self.TEXTO,
                          ler(caminho).decode("latin-1"))

    def test_latin1_continua_latin1(self):
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(self._com_descricao(p, "latin-1"))
        self.assertEqual(doc.encoding_lido, "latin-1")
        self.assertEqual(doc.encoding, "latin-1")


class TestGravacaoSegura(unittest.TestCase):
    """Falha na gravação não pode destruir o arquivo de destino."""

    def test_caractere_fora_do_latin1_recusa_e_preserva_o_arquivo(self):
        with PastaTemporaria() as p:
            caminho = icms_basico().gravar(p)
            original = ler(caminho)
            doc = SpedDocument.carregar(caminho)
            reg = next(r for r in doc.registros if r.reg == "0200")
            reg.set_valor(2, "PRODUTO — COM TRAVESSÃO")
            with self.assertRaises(ValueError) as ctx:
                doc.salvar(caminho)
            self.assertIn("linha", str(ctx.exception))
            self.assertEqual(ler(caminho), original)
            self.assertFalse(os.path.exists(caminho + ".tmp"))

    def test_bloco_9_e_recontado(self):
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(icms_basico().gravar(p))
        c100 = next(r for r in doc.registros if r.reg == "C100")
        doc.remover_registro(c100.filhos[0])
        linhas = doc.gerar_texto().splitlines()
        self.assertIn("|9900|C170|2|", linhas)
        self.assertEqual(linhas[-1], "|9999|%d|" % len(linhas))
        c990 = next(l for l in linhas if l.startswith("|C990|"))
        n_c = sum(1 for l in linhas if l.startswith("|C"))
        self.assertEqual(c990, "|C990|%d|" % n_c)


class TestNovoRegistro(unittest.TestCase):
    """Registro criado nasce com a largura do leiaute (não `|C170|`)."""

    def test_largura_vem_do_arquivo(self):
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(icms_basico().gravar(p))
        c100 = next(r for r in doc.registros if r.reg == "C100")
        largura = len(c100.filhos[0].campos)
        novo = doc.novo_registro("C170", pai=c100, depois=c100.filhos[2])
        self.assertEqual(len(novo.campos), largura)
        self.assertEqual(novo.campos[0], "C170")

    def test_primeiro_do_tipo_usa_o_leiaute(self):
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(icms_basico().gravar(p))
        novo = doc.novo_registro("0500")
        self.assertGreater(len(novo.campos), 1)
        self.assertNotIn("Campo", "".join(novo.campos))


class TestLinhasMalformadas(unittest.TestCase):
    """Nada do arquivo some sem aviso (até a 0.55.0: a linha sem o | final
    perdia o último campo; a sem o | inicial sumia ao salvar)."""

    def _arquivo(self, pasta, mexer):
        caminho = icms_basico().gravar(pasta)
        linhas = ler(caminho).decode("latin-1").split("\r\n")
        mexer(linhas)
        with open(caminho, "wb") as fh:
            fh.write("\r\n".join(linhas).encode("latin-1"))
        return caminho

    def test_sem_pipe_final_le_o_ultimo_campo_e_acusa(self):
        from sped_tables.dominio import diagnostico

        def tirar_pipe(linhas):
            i = next(k for k, l in enumerate(linhas)
                     if l.startswith("|0200|"))
            linhas[i] = linhas[i].rstrip("|")
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(self._arquivo(p, tirar_pipe))
            r = next(r for r in doc.registros if r.reg == "0200")
            self.assertEqual(r.valor(doc._ix("0200", "COD_NCM")), "21069090")
            self.assertEqual([reg for _n, reg in doc.sem_pipe_final],
                             ["0200"])
            achados, _i = diagnostico.verificar(doc)
            self.assertIn(("sem_pipe_final", 1),
                          diagnostico.impedem_importacao(achados))
            # salvar grava a linha com o pipe, sem perder o campo
            doc.salvar(os.path.join(p, "saida.txt"))
            texto = ler(os.path.join(p, "saida.txt")).decode("latin-1")
            self.assertIn("|21069090|", texto)

    def test_linha_sem_pipe_inicial_exige_decisao_ao_salvar(self):
        from sped_tables.aplicacao.sessao import Sessao
        from sped_tables.dominio import diagnostico
        from sped_tables.dominio.sped_model import LinhasInvalidas
        with PastaTemporaria() as p:
            caminho = self._arquivo(
                p, lambda linhas: linhas.insert(3, "lixo sem pipe"))
            original = ler(caminho)
            s = Sessao()
            s.abrir(caminho)
            self.assertEqual(s.doc.linhas_invalidas, [(4, "lixo sem pipe")])
            achados, _i = diagnostico.verificar(s.doc)
            self.assertIn(("linha_invalida", 1),
                          diagnostico.impedem_importacao(achados))
            with self.assertRaises(LinhasInvalidas) as ctx:
                s.salvar()
            self.assertIn("linha 4: lixo sem pipe", str(ctx.exception))
            self.assertEqual(ler(caminho), original)     # nada gravado
            s.salvar(descartar_invalidas=True)
            self.assertNotIn(b"lixo", ler(caminho))
            self.assertEqual(s.doc.linhas_invalidas, [])


if __name__ == "__main__":
    unittest.main()

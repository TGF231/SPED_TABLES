# -*- coding: utf-8 -*-
"""Contrato do tema: nenhuma cor literal na interface, folha completa nos
dois temas e nas duas densidades."""

import glob
import os
import re
import unittest

from tests.test_interface import _app

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), "sped_tables", "interface")
COR = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")


class TesteTema(unittest.TestCase):

    def test_nenhuma_cor_literal_fora_do_tema(self):
        # cor literal some no tema escuro: tudo sai de tema.atual()
        achados = []
        for arq in glob.glob(os.path.join(RAIZ, "**", "*.py"), recursive=True):
            if os.path.basename(arq) == "tema.py":
                continue
            with open(arq, encoding="utf-8") as f:
                for n, linha in enumerate(f, 1):
                    if COR.search(linha):
                        achados.append("%s:%d" % (os.path.relpath(arq, RAIZ), n))
        self.assertEqual(achados, [])

    def test_folha_sem_marcador_sobrando(self):
        _app()
        from sped_tables.interface import tema
        antes = (tema.e_escuro(), tema.densidade())
        try:
            for escuro in (False, True):
                for dens in tema.DENSIDADES:
                    tema.definir_escuro(escuro)
                    tema.definir_densidade(dens)
                    qss = tema.folha_estilo()
                    self.assertNotIn("$", qss)
                    self.assertIn(tema.atual().focus, qss)
        finally:
            tema.definir_escuro(antes[0])
            tema.definir_densidade(antes[1])


if __name__ == "__main__":
    unittest.main()

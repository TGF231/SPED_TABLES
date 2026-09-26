# -*- coding: utf-8 -*-
"""Armadilhas de código que já custaram caro — conferidas em todo arquivo.

Ver CLAUDE.md: "Armadilha recorrente" (a linha `def` removida por uma
edição, deixando o corpo como código morto depois do `return` anterior) e
"Armadilha: scripts de teste que sombreiam o stdlib".
"""

import ast
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fontes():
    for pasta, subpastas, arquivos in os.walk(RAIZ):
        subpastas[:] = [d for d in subpastas
                        if not d.startswith((".", "_"))
                        and d not in ("build", "dist", "arquivos", "Versions",
                                      "Versions_BKP")]
        for nome in arquivos:
            if nome.endswith(".py"):
                yield os.path.join(pasta, nome)


def _arvore(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return ast.parse(fh.read(), caminho)


class TestArmadilhas(unittest.TestCase):

    def test_nenhum_codigo_depois_de_return(self):
        """Corpo de método órfão aparece como código depois de um `return`."""
        achados = []
        for caminho in _fontes():
            for no in ast.walk(_arvore(caminho)):
                if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for i, st in enumerate(no.body[:-1]):
                    if isinstance(st, ast.Return):
                        achados.append("%s:%d %s()" % (
                            os.path.relpath(caminho, RAIZ), st.lineno,
                            no.name))
        self.assertEqual(achados, [])

    def test_nenhum_modulo_sombreia_o_stdlib(self):
        nomes = getattr(sys, "stdlib_module_names", set())
        if not nomes:
            self.skipTest("Python sem sys.stdlib_module_names")
        conflito = [os.path.relpath(c, RAIZ) for c in _fontes()
                    if os.path.splitext(os.path.basename(c))[0] in nomes]
        self.assertEqual(conflito, [])

    def test_nenhum_import_sem_uso(self):
        """Import que sobrou de uma mudança esconde dependência que não
        existe mais — e, entre camadas, faz parecer que uma depende da outra.
        `# noqa: F401` marca reexportação intencional."""
        achados = []
        for caminho in _fontes():
            if os.path.basename(caminho) == "__init__.py":
                continue
            with open(caminho, encoding="utf-8") as fh:
                texto = fh.read()
            linhas = texto.split("\n")
            arvore = ast.parse(texto)
            importados = {}
            for no in arvore.body:
                if isinstance(no, (ast.Import, ast.ImportFrom)):
                    if "noqa: F401" in linhas[no.lineno - 1]:
                        continue
                    for a in no.names:
                        nome = (a.asname or a.name).split(".")[0]
                        importados[nome] = no.lineno
            usados = {n.id for n in ast.walk(arvore)
                      if isinstance(n, ast.Name)}
            for nome, linha in importados.items():
                if nome not in usados:
                    achados.append("%s:%d %s" % (
                        os.path.relpath(caminho, RAIZ), linha, nome))
        self.assertEqual(achados, [])

    def test_nenhum_metodo_definido_duas_vezes_na_mesma_classe(self):
        """A segunda definição apaga a primeira em silêncio."""
        achados = []
        for caminho in _fontes():
            for no in ast.walk(_arvore(caminho)):
                if not isinstance(no, ast.ClassDef):
                    continue
                vistos = set()
                for st in no.body:
                    if isinstance(st, ast.FunctionDef):
                        # `@x.setter` redefine de propósito
                        if any(isinstance(d, ast.Attribute)
                               and d.attr in ("setter", "deleter")
                               for d in st.decorator_list):
                            continue
                        if st.name in vistos:
                            achados.append("%s:%d %s.%s" % (
                                os.path.relpath(caminho, RAIZ), st.lineno,
                                no.name, st.name))
                        vistos.add(st.name)
        self.assertEqual(achados, [])


if __name__ == "__main__":
    unittest.main()

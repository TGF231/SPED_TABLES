# -*- coding: utf-8 -*-
"""Exportação em CSV para o Excel brasileiro: `;`, latin-1, CRLF.

Havia oito exportadores escritos à mão, um por tela, montando a linha com
`";".join(...)`. Dois defeitos em sete deles: um `;` dentro de uma descrição
de produto deslocava as colunas dali em diante, e um caractere fora do
latin-1 (travessão colado de outro programa) abortava a exportação inteira.
Aqui o `csv` põe aspas onde precisa e o caractere impossível vira `?` — num
relatório, perder um travessão é aceitável; no SPED não seria, e lá a
gravação recusa (ver `SpedDocument.salvar`).
"""

import csv


def gravar_csv(caminho, cabecalho, linhas):
    """Grava `cabecalho` e `linhas` (iteráveis de valores). Devolve o
    caminho e quantas linhas de dados foram escritas."""
    n = 0
    with open(caminho, "w", encoding="latin-1", errors="replace",
              newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\r\n")
        w.writerow(cabecalho)
        for linha in linhas:
            w.writerow(["" if v is None else v for v in linha])
            n += 1
    return caminho, n

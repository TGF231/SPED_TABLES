# -*- coding: utf-8 -*-
"""SPED Tables — editor de arquivos SPED (EFD ICMS/IPI e EFD Contribuições).

Ponto de entrada:

    python sped_editor.py [arquivo.txt]

O programa em si está no pacote `sped_tables` (ver ARQUITETURA.md).
"""

import multiprocessing

if __name__ == "__main__":
    # No executável, os processos da leitura em paralelo (infra/paralelo.py)
    # são o próprio executável: `freeze_support` os desvia para o trabalho
    # antes de qualquer janela. E o import fica aqui dentro porque o processo
    # filho também executa este arquivo — fora do `if`, cada um carregaria o
    # Qt à toa.
    multiprocessing.freeze_support()
    from sped_tables.interface.app import main
    main()

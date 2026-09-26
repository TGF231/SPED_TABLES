# -*- coding: utf-8 -*-
"""SPED Tables — editor de arquivos SPED (EFD ICMS/IPI e EFD Contribuições).

Ponto de entrada:

    python sped_editor.py [arquivo.txt]

O programa em si está no pacote `sped_tables` (ver ARQUITETURA.md).
"""

from sped_tables.interface.app import main

if __name__ == "__main__":
    main()

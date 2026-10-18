# -*- coding: utf-8 -*-
"""O **consolidador**: lê o que os PVAs (e, adiante, as notas técnicas)
publicam e regrava as fontes da base de referência em `base/`.

Roda na máquina de quem compila o programa, nunca na de quem o usa. Pode
importar o `sped_tables`; o `sped_tables` nunca o importa
(`tests/test_arquitetura.py`). Ver `CONTEXT.md` e
`docs/adr/0001-base-de-referencia-compilada.md`.
"""

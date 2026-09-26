# -*- coding: utf-8 -*-
"""Raiz de composição: liga as portas do domínio às implementações.

É o único lugar que conhece ao mesmo tempo o domínio e a infraestrutura
concreta. Roda uma vez, no início do programa (`interface.app.main`) e da
suíte de testes; trocar a fonte das tabelas oficiais — por um PVA noutra
pasta, por uma tabela de teste — é trocar o que se passa aqui.
"""

from sped_tables.dominio import referencias


def configurar(fonte_referencias=None):
    """Liga a porta das tabelas oficiais. Sem argumento, usa os PVAs
    instalados (onde o `config` disser que estão)."""
    if fonte_referencias is None:
        from sped_tables.infra.referencias_pva import ReferenciasPVA
        fonte_referencias = ReferenciasPVA()
    return referencias.definir(fonte_referencias)

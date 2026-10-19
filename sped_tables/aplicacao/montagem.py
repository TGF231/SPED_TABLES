# -*- coding: utf-8 -*-
"""Raiz de composição: liga as portas do domínio às implementações.

É o único lugar que conhece ao mesmo tempo o domínio e a infraestrutura
concreta. Roda no início do programa (`interface.app.main`), da suíte de
testes e depois de importar uma base de referência; trocar a fonte das
tabelas oficiais — por uma base nova, por uma tabela de teste — é trocar o
que se passa aqui.
"""

from sped_tables.dominio import referencias


def configurar(fonte_referencias=None):
    """Liga a porta das tabelas oficiais. Sem argumento, usa a base de
    referência em uso (a mais nova entre a embutida e a importada); sem
    nenhuma legível, a fonte vazia — as regras que dependem dela se
    abstêm — e um aviso."""
    if fonte_referencias is None:
        from sped_tables.infra import base_referencia, dados
        from sped_tables.infra.referencias_base import ReferenciasBase
        base, origem = base_referencia.em_uso()
        if base is None:
            dados.avisar(
                "Base de referência indisponível (%s): as verificações que "
                "dependem do leiaute e das tabelas oficiais ficam "
                "desligadas. Reinstale o programa ou importe uma base em "
                "Configurações → Base de referência." % origem)
        else:
            fonte_referencias = ReferenciasBase(
                base, nome="base de referência %s (%s)"
                % (base.manifesto()["versao"], origem))
    return referencias.definir(fonte_referencias)

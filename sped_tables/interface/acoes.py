# -*- coding: utf-8 -*-
"""Tabela única das ações da janela: menu Ferramentas, barra e habilitação.

Até a 0.52.0 cada ação existia em **quatro** lugares — criada em
`_criar_acoes` (sem o `.ui`), religada em `_conectar_ui` (com o `.ui`),
habilitada numa lista em `_carregado` e desabilitada noutra em
`fechar_arquivo`. Esquecer um deles derrubou a janela na criação duas vezes
(*Empresas*, *Limpar campos com NULL*), e a ação *Conferir entradas (NF-e
55)* ficou fora de todos os menus sem ninguém notar.

Agora uma ação é **uma linha** desta tabela. A janela cria, conecta, põe no
menu e habilita tudo a partir dela; `tests/test_interface.py` confere que
cada linha aponta para um método que existe e que toda ação está alcançável.
"""

from dataclasses import dataclass

# quando a ação fica habilitada
SEMPRE = "sempre"          # mesmo sem arquivo aberto
ARQUIVO = "arquivo"        # qualquer arquivo aberto
ICMS = "ICMS"              # arquivo do EFD ICMS/IPI
CONTRIB = "CONTRIB"        # arquivo do EFD Contribuições
COM_PVA = "pva"            # arquivo aberto e o PVA do leiaute instalado

# onde ela aparece. Os menus seguem as **etapas do trabalho** com o
# arquivo — conferir, corrigir, recalcular, gerar —, não o leiaute: a ação
# que não vale para o leiaute aberto some do menu (`_habilitar_acoes`), em
# vez de ficar cinza num submenu inteiro desabilitado.
BARRA = "barra"            # barra de ferramentas, fora do menu
MENU_RAIZ = "raiz"         # direto no menu Ferramentas, antes dos submenus
MENU_CONFERIR = "conferir"
MENU_CORRIGIR = "corrigir"
MENU_RECALCULAR = "recalcular"
MENU_GERAR = "gerar"
MENU_CONFIG = "config"
OCULTA = ""                # só atalho de teclado ou chamada interna


@dataclass(frozen=True)
class Acao:
    atributo: str               # nome do atributo na janela (self.act_...)
    rotulo: str
    metodo: str                 # método da janela chamado ao acionar
    quando: str = ARQUIVO
    onde: str = OCULTA
    atalho: str = ""            # nome de QKeySequence.StandardKey
    argumento: object = None    # passado ao método, se houver
    alternavel: bool = False    # botão liga/desliga (toggled)
    separador: bool = False     # separador ANTES dela no menu
    # cumpre o critério de aceite do ROADMAP? Ação com `pronta=False` existe
    # nos canais de desenvolvimento e **some** de uma versão de release
    pronta: bool = True


# Até a 1.1.0-dev.11 havia três menus por leiaute e funções repetidas:
# *Conferir itens* duas vezes (uma por tributo) e *Conferir entradas (NF-e
# 55)*, que era a mesma conferência sem o botão de corrigir; *Revisar erros*
# ao lado do *Diagnóstico*, que já cobria todas as verificações dela. Ficou
# uma de cada — a revisão por ocorrência abre de dentro do Diagnóstico.
ACOES = (
    # ---- barra: o caminho do arquivo, do abrir ao PVA
    Acao("act_abrir", "Abrir…", "abrir", SEMPRE, BARRA, atalho="Open"),
    Acao("act_salvar", "Salvar", "salvar", ARQUIVO, BARRA, atalho="Save"),
    Acao("act_salvar_como", "Salvar como…", "salvar_como", ARQUIVO, BARRA,
         atalho="SaveAs"),
    Acao("act_fechar", "Fechar arquivo", "fechar_arquivo", ARQUIVO, BARRA,
         separador=True),
    # Empresas fica na barra, não dentro do menu: é o cadastro que dá
    # sentido às rotinas e funciona sem nenhum arquivo aberto
    Acao("act_empresas", "Empresas", "mostrar_empresas", SEMPRE, BARRA,
         alternavel=True, separador=True),
    # o diagnóstico é o painel de onde se chega a cada correção
    Acao("act_diagnostico", "Diagnóstico", "diagnosticar", ARQUIVO, BARRA),

    # ---- Ferramentas: os XMLs do período valem para todas as funções
    Acao("act_xmls", "XMLs do período (escolher ou reler)…",
         "escolher_xmls", ARQUIVO, MENU_RAIZ),

    # ---- Conferir
    Acao("act_conferir_itens", "Itens com XMLs…", "conferir_itens_xml",
         ARQUIVO, MENU_CONFERIR),
    Acao("act_conferir_c190", "C190 (ICMS) com XMLs…", "conferir_c190_xml",
         ICMS, MENU_CONFERIR),
    # NFC-e 65: gravam o C175 a partir dos XMLs dos cupons, e nenhum
    # arquivo gerado por elas passou pelo PVA — faltam os XMLs de um mês
    # real (critério 3 do ROADMAP). Somem de uma release até lá.
    Acao("act_validar_c175_65", "C175 (modelo 65) com XMLs…",
         "validar_c175_65", CONTRIB, MENU_CONFERIR, pronta=False),
    Acao("act_verificar_cst", "CST por NCM (tabelas RFB)…",
         "verificar_cst_ncm", CONTRIB, MENU_CONFERIR),
    Acao("act_itens_sem_ref", "Itens do 0200 sem referência…",
         "itens_sem_referencia", ARQUIVO, MENU_CONFERIR, separador=True),

    # ---- Corrigir
    # as rotinas valem para os dois leiautes desde que o ICMS/IPI ganhou as
    # suas (CSOSN no CST, código de receita)
    Acao("act_empresa", "Empresa e rotinas…", "configurar_empresa", ARQUIVO,
         MENU_CORRIGIR),
    Acao("act_datas_xml", "Datas e extemporâneos pelos XMLs…",
         "datas_pelo_xml", ARQUIVO, MENU_CORRIGIR, separador=True),
    Acao("act_alterar_datas", "Alterar datas emissão/saída (C100)…",
         "alterar_datas", ARQUIVO, MENU_CORRIGIR),
    Acao("act_reducao_xml", "Redução de base do C190 pelos XMLs de compra…",
         "reducao_c190_pelo_xml", ICMS, MENU_CORRIGIR, separador=True),
    Acao("act_credito_st", "Zerar ICMS próprio das compras com ST "
         "(1403/2403, CST x10/x70)…", "zerar_credito_icms_st", ICMS,
         MENU_CORRIGIR),
    Acao("act_trocar_aliquotas", "Trocar alíquotas PIS/COFINS…",
         "trocar_aliquotas", CONTRIB, MENU_CORRIGIR, separador=True),
    Acao("act_cod_gen", "Preencher COD_GEN pelo NCM (0200)…",
         "preencher_cod_gen", ICMS, MENU_CORRIGIR, separador=True),
    Acao("act_cod_cta", "Preencher conta contábil (COD_CTA)…",
         "preencher_cod_cta", ARQUIVO, MENU_CORRIGIR),
    # ERP: só leitura do banco
    Acao("act_0200_erp", "Atualizar 0200 (produtos) pelo ERP…",
         "atualizar_0200_erp", ARQUIVO, MENU_CORRIGIR, separador=True,
         pronta=False),
    Acao("act_0150_erp", "Atualizar 0150 (participantes) pelo ERP…",
         "atualizar_0150_erp", ARQUIVO, MENU_CORRIGIR, pronta=False),
    Acao("act_importar_inventario",
         "Importar inventário (bloco H) de planilha ou ERP…",
         "importar_inventario", ICMS, MENU_CORRIGIR, separador=True),

    # ---- Recalcular
    Acao("act_recalc_icms", "ICMS dos itens…", "recalcular_icms", ICMS,
         MENU_RECALCULAR),
    Acao("act_recalc_c190_massa", "C190 (analítico) em massa…",
         "recalcular_c190_massa", ICMS, MENU_RECALCULAR),
    Acao("act_apuracao_icms", "Apuração do ICMS (E110)",
         "recalcular_apuracao_icms", ICMS, MENU_RECALCULAR),
    Acao("act_recalc_m", "Bloco M (apuração PIS/COFINS)…",
         "recalcular_bloco_m", CONTRIB, MENU_RECALCULAR),

    # ---- Gerar pelos XMLs
    # sem arquivo aberto: é daqui que o arquivo nasce
    Acao("act_gerar_xml", "SPED a partir dos XMLs…", "gerar_de_xml",
         SEMPRE, MENU_GERAR, pronta=False),
    Acao("act_regenerar_entradas", "Regenerar entradas pelos XMLs…",
         "regenerar_entradas", ARQUIVO, MENU_GERAR, pronta=False),
    # NFC-e 65 no ICMS/IPI: o mesmo andaime do Contribuições, para o C190
    # sair dos itens do XML. Família NFC-e: sem ensaio no PVA, pronta=False
    Acao("act_c170_ficticios_icms",
         "C170 fictícios da NFC-e (65) pelos XMLs…",
         "gerar_c170_ficticios_icms", ICMS, MENU_GERAR, separador=True,
         pronta=False),
    Acao("act_remover_ficticios_icms",
         "Remover C170 fictícios da NFC-e (65)",
         "remover_c170_ficticios_icms", ICMS, MENU_GERAR, pronta=False),
    Acao("act_importar_xml", "C175 consolidado pelos XMLs…",
         "importar_xml_c175", CONTRIB, MENU_GERAR, separador=True,
         pronta=False),
    Acao("act_regenerar_c175_65", "Regenerar C175 (modelo 65) dos itens…",
         "regenerar_c175_65", CONTRIB, MENU_GERAR, pronta=False),

    # ---- Configurações
    Acao("act_correlacoes_cfop", "Correlações de CFOP (entradas)…",
         "editar_correlacoes_cfop", SEMPRE, MENU_CONFIG),
    Acao("act_sistemas_erp", "Sistemas ERP (conexões e mapeamento)…",
         "sistemas_erp", SEMPRE, MENU_CONFIG, pronta=False),
    Acao("act_pasta_pva", "Pasta dos PVAs…", "escolher_pasta_pva", SEMPRE,
         MENU_CONFIG),

    # ---- barra, depois de Ferramentas: o fim do caminho
    Acao("act_abrir_pva", "Abrir no PVA", "abrir_no_pva", COM_PVA, BARRA),
)

# o rótulo do tema anuncia o destino ("Tema escuro" no tema claro), por isso
# é a janela que o escreve; a ação em si é uma linha como as outras
ACAO_TEMA = Acao("act_tema", "Tema", "alternar_tema", SEMPRE, BARRA,
                 separador=True)

# (chave, título) dos submenus de Ferramentas, na ordem
MENUS = ((MENU_CONFERIR, "Conferir"),
         (MENU_CORRIGIR, "Corrigir"),
         (MENU_RECALCULAR, "Recalcular"),
         (MENU_GERAR, "Gerar"),
         (MENU_CONFIG, "Configurações"))

# as ações da barra que vêm depois do botão Ferramentas
DEPOIS_DO_MENU = ("act_abrir_pva",)


def visiveis(versao=None):
    """As ações da versão em curso: numa release, só as prontas."""
    from sped_tables import version
    if version.e_release(versao):
        return tuple(a for a in ACOES if a.pronta)
    return ACOES


def habilitada(acao, layout, tem_pva=False):
    """A ação vale para o estado atual? `layout` é None sem arquivo aberto."""
    if acao.quando == SEMPRE:
        return True
    if layout is None:
        return False
    if acao.quando == ARQUIVO:
        return True
    if acao.quando == COM_PVA:
        return bool(tem_pva)
    return acao.quando == layout


def aparece(acao, layout):
    """A ação fica no menu? A de um leiaute some quando o arquivo aberto é
    do outro; sem arquivo, tudo aparece."""
    if acao.quando not in (ICMS, CONTRIB) or layout is None:
        return True
    return acao.quando == layout

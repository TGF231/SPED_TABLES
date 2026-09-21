# -*- coding: utf-8 -*-
"""
sped_layouts.py
---------------
Tabelas de layout do SPED:

  * NIVEIS_*   -> nível hierárquico de cada registro (define a relação pai/filho)
  * CAMPOS_*   -> nomes das colunas de cada registro (quando conhecidos)

Há dois layouts suportados:
  * "ICMS"     -> EFD ICMS/IPI
  * "CONTRIB"  -> EFD Contribuições (PIS/COFINS)

A relação pai/filho é resolvida pela leitura sequencial do arquivo:
o pai de um registro é o registro imediatamente anterior, no mesmo bloco,
que possua um nível estritamente menor.

Registros não mapeados recebem um nível pelo heurístico em `nivel()`:
  - abertura de bloco  (X001)            -> 1
  - encerramento       (X990 / X999)     -> 1
  - 9999 (encerramento do arquivo)       -> 0
  - demais                               -> 2
e colunas genéricas "Campo NN".
"""

# ---------------------------------------------------------------------------
# NÍVEIS HIERÁRQUICOS
# ---------------------------------------------------------------------------

NIVEIS_ICMS = {
    # ---- Bloco 0 ----
    "0000": 0, "0001": 1, "0002": 2, "0005": 2, "0015": 2, "0100": 2,
    "0150": 2, "0175": 3, "0190": 2, "0200": 2, "0205": 3, "0206": 3,
    "0210": 3, "0220": 3, "0221": 4, "0300": 2, "0305": 3, "0400": 2,
    "0450": 2, "0460": 2, "0500": 2, "0600": 2, "0990": 1,
    # ---- Bloco B ----
    "B001": 1, "B020": 2, "B025": 3, "B030": 2, "B035": 3, "B350": 2,
    "B420": 2, "B440": 2, "B460": 2, "B470": 2, "B500": 2, "B510": 3,
    "B990": 1,
    # ---- Bloco C ----
    "C001": 1, "C100": 2, "C101": 3, "C105": 3, "C110": 3, "C111": 4,
    "C112": 4, "C113": 4, "C114": 4, "C115": 4, "C116": 4, "C120": 3,
    "C130": 3, "C140": 3, "C141": 4, "C160": 3, "C165": 3, "C170": 3,
    "C171": 4, "C172": 4, "C173": 4, "C174": 4, "C175": 4, "C176": 4,
    "C177": 4, "C178": 4, "C179": 4, "C180": 3, "C181": 4, "C185": 4,
    "C186": 4, "C190": 3, "C191": 4, "C195": 3, "C197": 4,
    "C300": 2, "C310": 3, "C320": 2, "C321": 3, "C350": 2, "C370": 3,
    "C390": 3, "C400": 2, "C405": 3, "C410": 4, "C420": 4, "C425": 5,
    "C460": 4, "C465": 5, "C470": 5, "C490": 4, "C500": 2, "C510": 3,
    "C590": 3, "C600": 2, "C601": 3, "C610": 3, "C690": 3, "C700": 2,
    "C790": 3, "C791": 4, "C800": 2, "C810": 3, "C815": 3, "C850": 3,
    "C860": 2, "C870": 3, "C880": 3, "C890": 3, "C990": 1,
    # ---- Bloco D ----
    "D001": 1, "D100": 2, "D101": 3, "D110": 3, "D120": 3, "D130": 3,
    "D140": 3, "D150": 3, "D160": 3, "D161": 4, "D162": 4, "D170": 4,
    "D180": 3, "D190": 3, "D195": 3, "D197": 4, "D300": 2, "D301": 3,
    "D310": 3, "D350": 2, "D355": 3, "D360": 3, "D365": 3, "D370": 3,
    "D390": 3, "D400": 2, "D410": 3, "D411": 4, "D420": 3, "D500": 2,
    "D510": 3, "D530": 3, "D590": 3, "D600": 2, "D610": 3, "D690": 3,
    "D695": 2, "D696": 3, "D697": 4, "D990": 1,
    # ---- Bloco E ----
    "E001": 1, "E100": 2, "E110": 3, "E111": 4, "E112": 5, "E113": 5,
    "E115": 4, "E116": 4, "E200": 2, "E210": 3, "E220": 4, "E230": 5,
    "E240": 5, "E250": 4, "E300": 2, "E310": 3, "E311": 4, "E312": 5,
    "E313": 5, "E316": 4, "E500": 2, "E510": 3, "E520": 3, "E530": 4,
    "E531": 5, "E990": 1,
    # ---- Bloco G ----
    "G001": 1, "G110": 2, "G125": 3, "G126": 4, "G130": 4, "G140": 5,
    "G990": 1,
    # ---- Bloco H ----
    "H001": 1, "H005": 2, "H010": 3, "H020": 4, "H030": 4, "H990": 1,
    # ---- Bloco K ----
    "K001": 1, "K010": 2, "K100": 2, "K200": 3, "K210": 3, "K215": 4,
    "K220": 3, "K230": 3, "K235": 4, "K250": 3, "K255": 4, "K260": 3,
    "K265": 4, "K270": 3, "K275": 4, "K280": 3, "K290": 3, "K291": 4,
    "K292": 4, "K300": 3, "K301": 4, "K302": 4, "K990": 1,
    # ---- Bloco 1 ----
    "1001": 1, "1010": 2, "1100": 2, "1105": 3, "1110": 4, "1200": 2,
    "1210": 3, "1300": 2, "1310": 3, "1320": 4, "1350": 2, "1360": 3,
    "1370": 4, "1390": 2, "1391": 3, "1400": 2, "1500": 2, "1510": 3,
    "1600": 2, "1601": 2, "1700": 2, "1710": 3, "1800": 2, "1900": 2,
    "1910": 3, "1920": 3, "1921": 4, "1922": 4, "1923": 4, "1925": 3,
    "1926": 4, "1960": 3, "1970": 3, "1975": 4, "1980": 3, "1990": 1,
    # ---- Bloco 9 ----
    "9001": 1, "9900": 2, "9990": 1, "9999": 0,
}

NIVEIS_CONTRIB = {
    # ---- Bloco 0 ----
    "0000": 0, "0001": 1, "0035": 2, "0100": 2, "0110": 2, "0111": 3,
    "0120": 2, "0140": 2, "0145": 3, "0150": 3, "0175": 4, "0190": 3,
    "0200": 3, "0205": 4, "0206": 4, "0208": 4, "0400": 3, "0450": 3,
    "0460": 3, "0500": 2, "0600": 2, "0900": 2, "0990": 1,
    # ---- Bloco A ----
    # X010 (estabelecimento) é tratado como contexto de abertura (nível 1),
    # para que os documentos (A100/C100/D100...) sejam registros PRINCIPAIS
    # (nível 2) e seus filhos (C170, C175, C110...) fiquem em nível 3 —
    # espelhando o leiaute ICMS/IPI e a visão do Validador do SPED.
    "A001": 1, "A010": 1, "A100": 2, "A110": 3, "A111": 3, "A120": 3,
    "A170": 3, "A990": 1,
    # ---- Bloco C ----
    "C001": 1, "C010": 1, "C100": 2, "C110": 3, "C111": 4, "C120": 3,
    "C170": 3, "C175": 3, "C180": 2, "C181": 3, "C185": 3, "C188": 3,
    "C190": 2, "C191": 3, "C195": 3, "C198": 3, "C199": 3, "C380": 2,
    "C381": 3, "C385": 3, "C395": 2, "C396": 3, "C400": 2, "C405": 3,
    "C481": 4, "C485": 4, "C489": 4, "C490": 3, "C491": 4, "C495": 4,
    "C499": 4, "C500": 2, "C501": 3, "C505": 3, "C509": 3, "C600": 2,
    "C601": 3, "C605": 3, "C609": 3, "C800": 2, "C810": 3, "C820": 3,
    "C830": 3, "C860": 2, "C870": 3, "C880": 3, "C890": 3, "C990": 1,
    # ---- Bloco D ----
    "D001": 1, "D010": 1, "D100": 2, "D101": 3, "D105": 3, "D111": 3,
    "D200": 2, "D201": 3, "D205": 3, "D209": 3, "D300": 2, "D309": 3,
    "D350": 2, "D359": 3, "D500": 2, "D501": 3, "D505": 3, "D509": 3,
    "D600": 2, "D601": 3, "D605": 3, "D609": 3, "D990": 1,
    # ---- Bloco F ----
    "F001": 1, "F010": 2, "F100": 3, "F111": 4, "F120": 3, "F129": 4,
    "F130": 3, "F139": 4, "F150": 3, "F200": 3, "F205": 4, "F210": 4,
    "F211": 4, "F500": 3, "F509": 4, "F510": 3, "F519": 4, "F525": 3,
    "F550": 3, "F559": 4, "F560": 3, "F569": 4, "F600": 3, "F700": 3,
    "F800": 3, "F990": 1,
    # ---- Bloco I ----
    "I001": 1, "I010": 2, "I100": 3, "I199": 4, "I200": 3, "I299": 4,
    "I300": 3, "I399": 4, "I990": 1,
    # ---- Bloco M ----
    "M001": 1, "M100": 2, "M105": 3, "M110": 3, "M115": 4, "M200": 2,
    "M205": 3, "M210": 3, "M211": 4, "M215": 4, "M220": 3, "M225": 4,
    "M230": 3, "M300": 2, "M350": 2, "M400": 2, "M410": 3, "M500": 2,
    "M505": 3, "M510": 3, "M515": 4, "M600": 2, "M605": 3, "M610": 3,
    "M611": 4, "M615": 4, "M620": 3, "M625": 4, "M630": 3, "M700": 2,
    "M800": 2, "M810": 3, "M990": 1,
    # ---- Bloco P ----
    "P001": 1, "P010": 2, "P100": 3, "P110": 4, "P199": 4, "P200": 2,
    "P210": 3, "P990": 1,
    # ---- Bloco 1 ----
    "1001": 1, "1010": 2, "1011": 3, "1020": 2, "1050": 2, "1100": 2,
    "1101": 3, "1102": 4, "1200": 2, "1210": 3, "1220": 3, "1300": 2,
    "1500": 2, "1501": 3, "1502": 4, "1600": 2, "1610": 3, "1620": 3,
    "1700": 2, "1800": 2, "1809": 3, "1900": 2, "1990": 1,
    # ---- Bloco 9 ----
    "9001": 1, "9900": 2, "9990": 1, "9999": 0,
}


def nivel(reg: str, layout: str) -> int:
    """Retorna o nível hierárquico de um registro."""
    tabela = NIVEIS_CONTRIB if layout == "CONTRIB" else NIVEIS_ICMS
    if reg in tabela:
        return tabela[reg]
    # heurístico para registros não mapeados
    if reg == "9999":
        return 0
    if reg.endswith("001"):
        return 1
    if reg.endswith("990") or reg.endswith("999"):
        return 1
    return 2


# ---------------------------------------------------------------------------
# NOMES DE CAMPOS (colunas)
# O índice 0 é sempre "REG"; os nomes abaixo começam no campo 02.
# ---------------------------------------------------------------------------

CAMPOS_ICMS = {
    "0000": ["REG", "COD_VER", "COD_FIN", "DT_INI", "DT_FIN", "NOME", "CNPJ",
             "CPF", "UF", "IE", "COD_MUN", "IM", "SUFRAMA", "IND_PERFIL",
             "IND_ATIV"],
    "0001": ["REG", "IND_MOV"],
    "0002": ["REG", "CLAS_ESTAB_IND"],
    "0005": ["REG", "FANTASIA", "CEP", "END", "NUM", "COMPL", "BAIRRO",
             "FONE", "FAX", "EMAIL"],
    "0100": ["REG", "NOME", "CPF", "CRC", "CNPJ", "CEP", "END", "NUM",
             "COMPL", "BAIRRO", "FONE", "FAX", "EMAIL", "COD_MUN"],
    "0150": ["REG", "COD_PART", "NOME", "COD_PAIS", "CNPJ", "CPF", "IE",
             "COD_MUN", "SUFRAMA", "END", "NUM", "COMPL", "BAIRRO"],
    "0175": ["REG", "DT_ALT", "NR_CAMPO", "CONT_ANT"],
    "0190": ["REG", "UNID", "DESCR"],
    "0200": ["REG", "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM",
             "UNID_INV", "TIPO_ITEM", "COD_NCM", "EX_IPI", "COD_GEN",
             "COD_LST", "ALIQ_ICMS", "CEST"],
    "0205": ["REG", "DESCR_ANT_ITEM", "DT_INI", "DT_FIM", "COD_ANT_ITEM"],
    "0206": ["REG", "COD_COMB"],
    "0400": ["REG", "COD_NAT", "DESCR_NAT"],
    "0450": ["REG", "COD_INF", "TXT"],
    "0460": ["REG", "COD_OBS", "TXT"],
    # o 0500 do EFD ICMS/IPI tem 7 campos; o do EFD Contribuições tem 9
    # (ganha COD_CTA_REF e CNPJ_EST). Confundir os dois gera pipe sobrando.
    "0500": ["REG", "DT_ALT", "COD_NAT_CC", "IND_CTA", "NIVEL", "COD_CTA",
             "NOME_CTA"],
    "0990": ["REG", "QTD_LIN_0"],
    # ---- Bloco C ----
    "C001": ["REG", "IND_MOV"],
    "C100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
             "SER", "NUM_DOC", "CHV_NFE", "DT_DOC", "DT_E_S", "VL_DOC",
             "IND_PGTO", "VL_DESC", "VL_ABAT_NT", "VL_MERC", "IND_FRT",
             "VL_FRT", "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS", "VL_ICMS",
             "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI", "VL_PIS", "VL_COFINS",
             "VL_PIS_ST", "VL_COFINS_ST"],
    "C110": ["REG", "COD_INF", "TXT_COMPL"],
    "C113": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "SER",
             "SUB", "NUM_DOC", "DT_DOC", "CHV_DOCe"],
    "C170": ["REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID",
             "VL_ITEM", "VL_DESC", "IND_MOV", "CST_ICMS", "CFOP", "COD_NAT",
             "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
             "ALIQ_ST", "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ",
             "VL_BC_IPI", "ALIQ_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS",
             "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS",
             "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
             "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA", "VL_ABAT_NT"],
    "C190": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
             "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC",
             "VL_IPI", "COD_OBS"],
    "C195": ["REG", "COD_OBS", "TXT_COMPL"],
    "C197": ["REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
             "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "C500": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
             "SER", "SUB", "COD_CONS", "NUM_DOC", "DT_DOC", "DT_E_S",
             "VL_DOC", "VL_DESC", "VL_FORN", "VL_SERV_NT", "VL_TERC",
             "VL_DA", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST",
             "COD_INF", "VL_PIS", "VL_COFINS", "CHV_DOCe"],
    "C590": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
             "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC",
             "COD_OBS"],
    "C990": ["REG", "QTD_LIN_C"],
    # ---- Bloco D ----
    "D001": ["REG", "IND_MOV"],
    "D100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
             "SER", "SUB", "NUM_DOC", "CHV_CTE", "DT_DOC", "DT_A_P",
             "TP_CT-e", "CHV_CTE_REF", "VL_DOC", "VL_DESC", "IND_FRT",
             "VL_SERV", "VL_BC_ICMS", "VL_ICMS", "VL_NT", "COD_INF",
             "COD_CTA"],
    "D190": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
             "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "D990": ["REG", "QTD_LIN_D"],
    # ---- Bloco E ----
    "E001": ["REG", "IND_MOV"],
    "E100": ["REG", "DT_INI", "DT_FIN"],
    "E110": ["REG", "VL_TOT_DEBITOS", "VL_AJ_DEBITOS", "VL_TOT_AJ_DEBITOS",
             "VL_ESTORNOS_CRED", "VL_TOT_CREDITOS", "VL_AJ_CREDITOS",
             "VL_TOT_AJ_CREDITOS", "VL_ESTORNOS_DEB", "VL_SLD_CREDOR_ANT",
             "VL_SLD_APURADO", "VL_TOT_DED", "VL_ICMS_RECOLHER",
             "VL_SLD_CREDOR_TRANSPORTAR", "DEB_ESP"],
    "E111": ["REG", "COD_AJ_APUR", "DESCR_COMPL_AJ", "VL_AJ_APUR"],
    "E116": ["REG", "COD_OR", "VL_OR", "DT_VCTO", "COD_REC", "NUM_PROC",
             "IND_PROC", "PROC", "TXT_COMPL", "MES_REF"],
    "E200": ["REG", "UF", "DT_INI", "DT_FIN"],
    "E210": ["REG", "IND_MOV_ST", "VL_SLD_CRED_ANT_ST", "VL_DEVOL_ST",
             "VL_RESSARC_ST", "VL_OUT_CRED_ST", "VL_AJ_CREDITOS_ST",
             "VL_RETENCAO_ST", "VL_OUT_DEB_ST", "VL_AJ_DEBITOS_ST",
             "VL_SLD_DEV_ANT_ST", "VL_DEDUCOES_ST", "VL_ICMS_RECOL_ST",
             "VL_SLD_CRED_ST_TRANSPORTAR", "DEB_ESP_ST"],
    "E300": ["REG", "UF", "DT_INI", "DT_FIN"],
    "E310": ["REG", "IND_MOV_FCP_DIFAL", "VL_SLD_CRED_ANT_DIFAL",
             "VL_TOT_DEBITOS_DIFAL", "VL_OUT_DEB_DIFAL", "VL_AJ_DEBITOS_DIFAL",
             "VL_TOT_DEB_FCP", "VL_OUT_DEB_FCP", "VL_AJ_DEBITOS_FCP",
             "VL_TOT_CREDITOS_DIFAL", "VL_OUT_CRED_DIFAL",
             "VL_AJ_CREDITOS_DIFAL", "VL_TOT_CRED_FCP", "VL_OUT_CRED_FCP",
             "VL_AJ_CREDITOS_FCP", "VL_SLD_DEV_ANT_DIFAL", "VL_DEDUCOES_DIFAL",
             "VL_RECOL_DIFAL", "VL_SLD_CRED_TRANSPORTAR_DIFAL", "DEB_ESP_DIFAL",
             "VL_SLD_DEV_ANT_FCP", "VL_DEDUCOES_FCP", "VL_RECOL_FCP",
             "VL_SLD_CRED_TRANSPORTAR_FCP", "DEB_ESP_FCP"],
    "E500": ["REG", "IND_APUR", "DT_INI", "DT_FIN"],
    "E510": ["REG", "CFOP", "CST_IPI", "VL_CONT_IPI", "VL_BC_IPI", "VL_IPI"],
    "E520": ["REG", "VL_SD_ANT_IPI", "VL_DEB_IPI", "VL_CRED_IPI", "VL_OD_IPI",
             "VL_OC_IPI", "VL_SC_IPI", "VL_SD_IPI"],
    "E990": ["REG", "QTD_LIN_E"],
    # ---- Bloco H ----
    "H001": ["REG", "IND_MOV"],
    "H005": ["REG", "DT_INV", "VL_INV", "MOT_INV"],
    "H010": ["REG", "COD_ITEM", "UNID", "QTD", "VL_UNIT", "VL_ITEM",
             "IND_PROP", "COD_PART", "TXT_COMPL", "COD_CTA", "VL_ITEM_IR"],
    "H990": ["REG", "QTD_LIN_H"],
    # ---- Bloco 1 ----
    "1001": ["REG", "IND_MOV"],
    "1010": ["REG", "IND_EXP", "IND_CCRF", "IND_COMB", "IND_USINA",
             "IND_VA", "IND_EE", "IND_CART", "IND_FORM", "IND_AER"],
    "1990": ["REG", "QTD_LIN_1"],
    # ---- Bloco 9 ----
    "9001": ["REG", "IND_MOV"],
    "9900": ["REG", "REG_BLC", "QTD_REG_BLC"],
    "9990": ["REG", "QTD_LIN_9"],
    "9999": ["REG", "QTD_LIN"],
}

CAMPOS_CONTRIB = {
    "0000": ["REG", "COD_VER", "TIPO_ESCRIT", "IND_SIT_ESP", "NUM_REC_ANTERIOR",
             "DT_INI", "DT_FIN", "NOME", "CNPJ", "UF", "COD_MUN", "SUFRAMA",
             "IND_NAT_PJ", "IND_ATIV"],
    "0001": ["REG", "IND_MOV"],
    "0100": ["REG", "NOME", "CPF", "CRC", "CNPJ", "CEP", "END", "NUM",
             "COMPL", "BAIRRO", "FONE", "FAX", "EMAIL", "COD_MUN"],
    "0110": ["REG", "COD_INC_TRIB", "IND_APRO_CRED", "COD_TIPO_CONT",
             "IND_REG_CUM"],
    "0140": ["REG", "COD_EST", "NOME", "CNPJ", "UF", "IE", "COD_MUN", "IM",
             "SUFRAMA"],
    "0150": ["REG", "COD_PART", "NOME", "COD_PAIS", "CNPJ", "CPF", "IE",
             "COD_MUN", "SUFRAMA", "END", "NUM", "COMPL", "BAIRRO"],
    "0190": ["REG", "UNID", "DESCR"],
    "0200": ["REG", "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM",
             "UNID_INV", "TIPO_ITEM", "COD_NCM", "EX_IPI", "COD_GEN",
             "COD_LST", "ALIQ_ICMS", "CEST"],
    "0400": ["REG", "COD_NAT", "DESCR_NAT"],
    "0500": ["REG", "DT_ALT", "COD_NAT_CC", "IND_CTA", "NIVEL", "COD_CTA",
             "NOME_CTA", "COD_CTA_REF", "CNPJ_EST"],
    "0990": ["REG", "QTD_LIN_0"],
    # ---- Bloco A ----
    "A001": ["REG", "IND_MOV"],
    "A010": ["REG", "CNPJ"],
    "A100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_SIT", "SER",
             "SUB", "NUM_DOC", "CHV_NFSE", "DT_DOC", "DT_EXE_SERV", "VL_DOC",
             "IND_PGTO", "VL_DESC", "VL_BC_PIS", "VL_PIS", "VL_BC_COFINS",
             "VL_COFINS", "VL_PIS_RET", "VL_COFINS_RET", "VL_ISS"],
    "A170": ["REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "VL_ITEM",
             "VL_DESC", "NAT_BC_CRED", "IND_ORIG_CRED", "CST_PIS",
             "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS",
             "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "A990": ["REG", "QTD_LIN_A"],
    # ---- Bloco C ----
    "C001": ["REG", "IND_MOV"],
    "C010": ["REG", "CNPJ", "IND_ESCRI"],
    "C100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
             "SER", "NUM_DOC", "CHV_NFE", "DT_DOC", "DT_E_S", "VL_DOC",
             "IND_PGTO", "VL_DESC", "VL_ABAT_NT", "VL_MERC", "IND_FRT",
             "VL_FRT", "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS", "VL_ICMS",
             "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI", "VL_PIS", "VL_COFINS",
             "VL_PIS_ST", "VL_COFINS_ST"],
    "C110": ["REG", "COD_INF", "TXT_COMPL"],
    "C170": ["REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID",
             "VL_ITEM", "VL_DESC", "IND_MOV", "CST_ICMS", "CFOP", "COD_NAT",
             "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
             "ALIQ_ST", "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ",
             "VL_BC_IPI", "ALIQ_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS",
             "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS",
             "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
             "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "C175": ["REG", "CFOP", "VL_OPR", "VL_DESC", "CST_PIS", "VL_BC_PIS",
             "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS",
             "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
             "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA", "INFO_COMPL"],
    "C180": ["REG", "COD_MOD", "DT_DOC_INI", "DT_DOC_FIN", "COD_ITEM",
             "COD_NCM", "EX_IPI", "VL_TOT_ITEM"],
    "C181": ["REG", "CST_PIS", "CFOP", "VL_ITEM", "VL_DESC", "VL_BC_PIS",
             "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS",
             "COD_CTA"],
    "C185": ["REG", "CST_COFINS", "CFOP", "VL_ITEM", "VL_DESC", "VL_BC_COFINS",
             "ALIQ_COFINS", "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT",
             "VL_COFINS", "COD_CTA"],
    "C190": ["REG", "COD_MOD", "DT_REF_INI", "DT_REF_FIN", "COD_ITEM",
             "COD_NCM", "EX_IPI", "VL_TOT_ITEM"],
    "C990": ["REG", "QTD_LIN_C"],
    # ---- Bloco D ----
    "D001": ["REG", "IND_MOV"],
    "D010": ["REG", "CNPJ"],
    "D100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
             "SER", "SUB", "NUM_DOC", "CHV_CTE", "DT_DOC", "DT_A_P",
             "TP_CTe", "CHV_CTE_REF", "VL_DOC", "VL_DESC", "IND_FRT",
             "VL_SERV", "VL_BC_ICMS", "VL_ICMS", "VL_NT", "COD_INF",
             "COD_CTA"],
    "D990": ["REG", "QTD_LIN_D"],
    # ---- Bloco F ----
    "F001": ["REG", "IND_MOV"],
    "F010": ["REG", "CNPJ"],
    "F100": ["REG", "IND_OPER", "COD_PART", "COD_ITEM", "DT_OPER", "VL_OPER",
             "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS",
             "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "NAT_BC_CRED",
             "IND_ORIG_CRED", "COD_CTA", "COD_CCUS", "DESC_DOC_OPER"],
    "F990": ["REG", "QTD_LIN_F"],
    # ---- Bloco M ----
    "M001": ["REG", "IND_MOV"],
    "M100": ["REG", "COD_CRED", "IND_CRED_ORI", "VL_BC_PIS", "ALIQ_PIS",
             "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_CRED", "VL_AJUS_ACRES",
             "VL_AJUS_REDUC", "VL_CRED_DIF", "VL_CRED_DISP", "IND_DESC_CRED",
             "VL_CRED_DESC", "SLD_CRED"],
    "M105": ["REG", "NAT_BC_CRED", "CST_PIS", "VL_BC_PIS_TOT",
             "VL_BC_PIS_CUM", "VL_BC_PIS_NC", "VL_BC_PIS", "QUANT_BC_PIS_TOT",
             "QUANT_BC_PIS", "DESC_CRED"],
    "M200": ["REG", "VL_TOT_CONT_NC_PER", "VL_TOT_CRED_DESC",
             "VL_TOT_CRED_DESC_ANT", "VL_TOT_CONT_NC_DEV", "VL_RET_NC",
             "VL_OUT_DED_NC", "VL_CONT_NC_REC", "VL_TOT_CONT_CUM_PER",
             "VL_RET_CUM", "VL_OUT_DED_CUM", "VL_CONT_CUM_REC",
             "VL_TOT_CONT_REC"],
    "M205": ["REG", "NUM_CAMPO", "COD_REC", "VL_DEBITO"],
    "M210": ["REG", "COD_CONT", "VL_REC_BRT", "VL_BC_CONT", "VL_AJUS_ACRES_BC_PIS",
             "VL_AJUS_REDUC_BC_PIS", "VL_BC_CONT_AJUS", "ALIQ_PIS",
             "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_CONT_APUR", "VL_AJUS_ACRES",
             "VL_AJUS_REDUC", "VL_CONT_DIFER", "VL_CONT_DIFER_ANT",
             "VL_CONT_PER"],
    "M400": ["REG", "CST_PIS", "VL_TOT_REC", "COD_CTA", "DESC_COMPL"],
    "M410": ["REG", "NAT_REC", "VL_REC", "COD_CTA", "DESC_COMPL"],
    "M500": ["REG", "COD_CRED", "IND_CRED_ORI", "VL_BC_COFINS", "ALIQ_COFINS",
             "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_CRED",
             "VL_AJUS_ACRES", "VL_AJUS_REDUC", "VL_CRED_DIFER", "VL_CRED_DISP",
             "IND_DESC_CRED", "VL_CRED_DESC", "SLD_CRED"],
    "M505": ["REG", "NAT_BC_CRED", "CST_COFINS", "VL_BC_COFINS_TOT",
             "VL_BC_COFINS_CUM", "VL_BC_COFINS_NC", "VL_BC_COFINS",
             "QUANT_BC_COFINS_TOT", "QUANT_BC_COFINS", "DESC_CRED"],
    "M600": ["REG", "VL_TOT_CONT_NC_PER", "VL_TOT_CRED_DESC",
             "VL_TOT_CRED_DESC_ANT", "VL_TOT_CONT_NC_DEV", "VL_RET_NC",
             "VL_OUT_DED_NC", "VL_CONT_NC_REC", "VL_TOT_CONT_CUM_PER",
             "VL_RET_CUM", "VL_OUT_DED_CUM", "VL_CONT_CUM_REC",
             "VL_TOT_CONT_REC"],
    "M605": ["REG", "NUM_CAMPO", "COD_REC", "VL_DEBITO"],
    "M610": ["REG", "COD_CONT", "VL_REC_BRT", "VL_BC_CONT",
             "VL_AJUS_ACRES_BC_COFINS", "VL_AJUS_REDUC_BC_COFINS",
             "VL_BC_CONT_AJUS", "ALIQ_COFINS", "QUANT_BC_COFINS",
             "ALIQ_COFINS_QUANT", "VL_CONT_APUR", "VL_AJUS_ACRES",
             "VL_AJUS_REDUC", "VL_CONT_DIFER", "VL_CONT_DIFER_ANT",
             "VL_CONT_PER"],
    "M800": ["REG", "CST_COFINS", "VL_TOT_REC", "COD_CTA", "DESC_COMPL"],
    "M810": ["REG", "NAT_REC", "VL_REC", "COD_CTA", "DESC_COMPL"],
    "M990": ["REG", "QTD_LIN_M"],
    # ---- Bloco P ----
    "P001": ["REG", "IND_MOV"],
    "P990": ["REG", "QTD_LIN_P"],
    # ---- Bloco 1 ----
    "1001": ["REG", "IND_MOV"],
    "1990": ["REG", "QTD_LIN_1"],
    # ---- Bloco 9 ----
    "9001": ["REG", "IND_MOV"],
    "9900": ["REG", "REG_BLC", "QTD_REG_BLC"],
    "9990": ["REG", "QTD_LIN_9"],
    "9999": ["REG", "QTD_LIN"],
}


def campos(reg: str, layout: str, n: int):
    """
    Retorna a lista de nomes de coluna para `reg`, com tamanho `n`
    (n = número de campos da linha, incluindo REG).
    Preenche/aparа com "Campo NN" quando o layout não é conhecido
    ou a linha tem mais campos do que o esperado.
    """
    tabela = CAMPOS_CONTRIB if layout == "CONTRIB" else CAMPOS_ICMS
    base = tabela.get(reg)
    nomes = list(base) if base else ["REG"]
    # completa com nomes genéricos até atingir n
    while len(nomes) < n:
        nomes.append("Campo %02d" % (len(nomes) + 1))
    # se a linha tiver menos campos que o layout, apara
    return nomes[:n] if n > 0 else nomes


def num_campos_esperado(reg: str, layout: str):
    """Número de campos (incluindo REG) previsto no layout para `reg`,
    ou None se o tipo de registro não estiver mapeado."""
    tabela = CAMPOS_CONTRIB if layout == "CONTRIB" else CAMPOS_ICMS
    base = tabela.get(reg)
    return len(base) if base else None


def detectar_layout(linhas) -> str:
    """
    Detecta o tipo de SPED a partir do conteúdo.
    Retorna "CONTRIB" ou "ICMS".
    """
    marcadores_contrib = ("|M100|", "|M200|", "|M210|", "|M500|", "|M600|",
                          "|A010|", "|A100|", "|P001|", "|F100|", "|0110|")
    marcadores_icms = ("|E110|", "|E116|", "|E520|", "|C190|", "|B001|",
                       "|G001|", "|K001|", "|H010|")
    amostra = "\n".join(linhas[:5000])
    if any(m in amostra for m in marcadores_contrib):
        return "CONTRIB"
    if any(m in amostra for m in marcadores_icms):
        return "ICMS"
    # fallback: estrutura do 0000
    for ln in linhas[:3]:
        if ln.startswith("|0000|"):
            campos_0 = ln.split("|")
            # Contribuições tem TIPO_ESCRIT/IND_SIT_ESP logo após COD_VER
            # e não possui IND_PERFIL (letra A/B/C) no final.
            if len(campos_0) >= 9 and not any(
                    c in ("A", "B", "C") for c in campos_0[-4:]):
                return "CONTRIB"
            return "ICMS"
    return "ICMS"

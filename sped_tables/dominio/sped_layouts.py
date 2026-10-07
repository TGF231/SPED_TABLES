# -*- coding: utf-8 -*-
"""
sped_layouts.py
---------------
Tabelas de layout do SPED:

  * NIVEIS_*   -> nível hierárquico de cada registro (define a relação pai/filho)
  * CAMPOS_*   -> nomes das colunas de cada registro

As duas tabelas foram extraídas dos **guias práticos** da EFD-ICMS/IPI e da
EFD-Contribuições (vriconsulting.com.br), registro a registro: 270 e 203
registros, com todos os campos e o nível hierárquico de cada um.

Dois cuidados ficaram embutidos na extração e valem ao atualizar:

  * **nome repetido é desambiguado** — o guia chama de `ALIQ_PIS` tanto o
    percentual quanto o valor por unidade, e `_ix` devolveria sempre o
    primeiro; o segundo virou `ALIQ_PIS_QUANT`, como o código já usava;
  * **largura só cresce** — onde o guia trazia menos campos que o layout já
    validado contra arquivo real, o antigo prevaleceu (o guia estava numa
    versão anterior, caso do E116 e do E310).

Layout mais largo que o arquivo é inofensivo (sobram nomes não usados) e mais
estreito também (as colunas extras saem como "Campo NN"), porque `_ncampos`
mede o registro pelo próprio arquivo.

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
    "0000": 0, "0001": 1, "0002": 2, "0005": 2, "0015": 2, "0100": 2,
    "0150": 2, "0175": 3, "0190": 2, "0200": 2, "0205": 3, "0206": 3,
    "0210": 3, "0220": 3, "0221": 4, "0300": 2, "0305": 3, "0400": 2,
    "0450": 2, "0460": 2, "0500": 2, "0600": 2, "0990": 1, "1001": 1,
    "1010": 2, "1100": 2, "1105": 3, "1110": 4, "1200": 2, "1210": 3,
    "1250": 2, "1255": 3, "1300": 2, "1310": 3, "1320": 4, "1350": 2,
    "1360": 3, "1370": 4, "1390": 2, "1391": 3, "1400": 2, "1500": 2,
    "1510": 3, "1600": 2, "1601": 2, "1700": 2, "1710": 3, "1800": 2,
    "1900": 2, "1910": 3, "1920": 3, "1921": 4, "1922": 4, "1923": 4,
    "1925": 3, "1926": 4, "1960": 3, "1970": 3, "1975": 4, "1980": 3,
    "1990": 1, "9001": 1, "9900": 2, "9990": 1, "9999": 0, "B001": 1,
    "B020": 2, "B025": 3, "B030": 2, "B035": 3, "B350": 2, "B420": 2,
    "B440": 2, "B460": 2, "B470": 2, "B500": 2, "B510": 3, "B990": 1,
    "C001": 1, "C100": 2, "C101": 3, "C105": 3, "C110": 3, "C111": 4,
    "C112": 4, "C113": 4, "C114": 4, "C115": 4, "C116": 4, "C120": 3,
    "C130": 3, "C140": 3, "C141": 4, "C160": 3, "C165": 3, "C170": 3,
    "C171": 4, "C172": 4, "C173": 4, "C174": 4, "C175": 4, "C176": 4,
    "C177": 4, "C178": 4, "C179": 4, "C180": 3, "C181": 4, "C185": 4,
    "C186": 4, "C190": 3, "C191": 4, "C195": 3, "C197": 4, "C300": 2,
    "C310": 3, "C320": 2, "C321": 3, "C330": 5, "C350": 2, "C370": 3,
    "C380": 4, "C390": 3, "C400": 2, "C405": 3, "C410": 4, "C420": 4,
    "C425": 5, "C430": 6, "C460": 4, "C465": 5, "C470": 5, "C480": 6,
    "C490": 4, "C495": 2, "C500": 2, "C510": 3, "C590": 3, "C591": 4,
    "C595": 3, "C597": 3, "C600": 2, "C601": 3, "C610": 3, "C690": 3,
    "C700": 2, "C790": 3, "C791": 4, "C800": 2, "C810": 3, "C815": 3,
    "C850": 3, "C855": 3, "C857": 4, "C860": 2, "C870": 3, "C880": 3,
    "C890": 3, "C895": 3, "C897": 4, "C990": 1, "D001": 1, "D100": 2,
    "D101": 3, "D110": 3, "D120": 3, "D130": 3, "D140": 3, "D150": 3,
    "D160": 3, "D161": 4, "D162": 4, "D170": 4, "D180": 3, "D190": 3,
    "D195": 3, "D197": 4, "D300": 2, "D301": 3, "D310": 3, "D350": 2,
    "D355": 3, "D360": 3, "D365": 3, "D370": 3, "D390": 3, "D400": 2,
    "D410": 3, "D411": 4, "D420": 3, "D500": 2, "D510": 3, "D530": 3,
    "D590": 3, "D600": 2, "D610": 3, "D690": 3, "D695": 2, "D696": 3,
    "D697": 4, "D700": 2, "D730": 3, "D731": 4, "D735": 3, "D737": 4,
    "D750": 2, "D760": 3, "D761": 4, "D990": 1, "E001": 1, "E100": 2,
    "E110": 3, "E111": 4, "E112": 5, "E113": 5, "E115": 4, "E116": 4,
    "E200": 2, "E210": 3, "E220": 4, "E230": 5, "E240": 5, "E250": 4,
    "E300": 2, "E310": 3, "E311": 4, "E312": 5, "E313": 5, "E316": 4,
    "E500": 2, "E510": 3, "E520": 3, "E530": 4, "E531": 5, "E990": 1,
    "G001": 1, "G110": 2, "G125": 3, "G126": 4, "G130": 4, "G140": 5,
    "G990": 1, "H001": 1, "H005": 2, "H010": 3, "H020": 4, "H030": 4,
    "H990": 1, "K001": 1, "K010": 2, "K100": 2, "K200": 3, "K210": 3,
    "K215": 4, "K220": 3, "K230": 3, "K235": 4, "K250": 3, "K255": 4,
    "K260": 3, "K265": 4, "K270": 3, "K275": 4, "K280": 3, "K290": 3,
    "K291": 4, "K292": 4, "K300": 3, "K301": 4, "K302": 4, "K990": 1
}

NIVEIS_CONTRIB = {
    "0000": 0, "0001": 1, "0035": 2, "0100": 2, "0110": 2, "0111": 3,
    "0120": 2, "0140": 2, "0145": 3, "0150": 3, "0175": 4, "0190": 3,
    "0200": 3, "0205": 4, "0206": 4, "0208": 4, "0400": 3, "0450": 3,
    "0460": 3, "0500": 2, "0600": 2, "0900": 2, "0990": 1, "1001": 1,
    "1010": 2, "1011": 3, "1020": 2, "1050": 2, "1100": 2, "1101": 3,
    "1102": 4, "1200": 2, "1210": 3, "1220": 3, "1300": 2, "1500": 2,
    "1501": 3, "1502": 4, "1600": 2, "1610": 3, "1620": 3, "1700": 2,
    "1800": 2, "1809": 3, "1900": 2, "1990": 1, "9001": 1, "9900": 2,
    "9990": 1, "9999": 0, "A001": 1, "A010": 1, "A100": 2, "A110": 3,
    "A111": 3, "A120": 3, "A170": 3, "A990": 1, "C001": 1, "C010": 1,
    "C100": 2, "C110": 3, "C111": 4, "C120": 3, "C170": 3, "C175": 3,
    "C180": 2, "C181": 3, "C185": 3, "C188": 3, "C190": 2, "C191": 3,
    "C195": 3, "C198": 3, "C199": 3, "C380": 2, "C381": 3, "C385": 3,
    "C395": 2, "C396": 3, "C400": 2, "C405": 3, "C481": 4, "C485": 4,
    "C489": 4, "C490": 3, "C491": 4, "C495": 4, "C499": 4, "C500": 2,
    "C501": 3, "C505": 3, "C509": 3, "C600": 2, "C601": 3, "C605": 3,
    "C609": 3, "C800": 2, "C810": 3, "C820": 3, "C830": 3, "C860": 2,
    "C870": 3, "C880": 3, "C890": 3, "C990": 1, "D001": 1, "D010": 1,
    "D100": 2, "D101": 3, "D105": 3, "D111": 3, "D200": 2, "D201": 3,
    "D205": 3, "D209": 3, "D300": 2, "D309": 3, "D350": 2, "D359": 3,
    "D500": 2, "D501": 3, "D505": 3, "D509": 3, "D600": 2, "D601": 3,
    "D605": 3, "D609": 3, "D990": 1, "F001": 1, "F010": 2, "F100": 3,
    "F111": 4, "F120": 3, "F129": 4, "F130": 3, "F139": 4, "F150": 3,
    "F200": 3, "F205": 4, "F210": 4, "F211": 4, "F500": 3, "F509": 4,
    "F510": 3, "F519": 4, "F525": 3, "F550": 3, "F559": 4, "F560": 3,
    "F569": 4, "F600": 3, "F700": 3, "F800": 3, "F990": 1, "I001": 1,
    "I010": 2, "I100": 3, "I199": 4, "I200": 3, "I299": 4, "I300": 3,
    "I399": 4, "I990": 1, "M001": 1, "M100": 2, "M105": 3, "M110": 3,
    "M115": 4, "M200": 2, "M205": 3, "M210": 3, "M211": 4, "M215": 4,
    "M220": 3, "M225": 4, "M230": 3, "M300": 2, "M350": 2, "M400": 2,
    "M410": 3, "M500": 2, "M505": 3, "M510": 3, "M515": 4, "M600": 2,
    "M605": 3, "M610": 3, "M611": 4, "M615": 4, "M620": 3, "M625": 4,
    "M630": 3, "M700": 2, "M800": 2, "M810": 3, "M990": 1, "P001": 1,
    "P010": 2, "P100": 3, "P110": 4, "P199": 4, "P200": 2, "P210": 3,
    "P990": 1
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
    "0000": [
        "REG", "COD_VER", "COD_FIN", "DT_INI", "DT_FIN", "NOME", "CNPJ",
        "CPF", "UF", "IE", "COD_MUN", "IM", "SUFRAMA", "IND_PERFIL",
        "IND_ATIV"],
    "0001": ["REG", "IND_MOV"],
    "0002": ["REG", "CLAS_ESTAB_IND"],
    "0005": [
        "REG", "FANTASIA", "CEP", "END", "NUM", "COMPL", "BAIRRO", "FONE",
        "FAX", "EMAIL"],
    "0015": ["REG", "UF_ST", "IE_ST"],
    "0100": [
        "REG", "NOME", "CPF", "CRC", "CNPJ", "CEP", "END", "NUM", "COMPL",
        "BAIRRO", "FONE", "FAX", "EMAIL", "COD_MUN"],
    "0150": [
        "REG", "COD_PART", "NOME", "COD_PAIS", "CNPJ", "CPF", "IE",
        "COD_MUN", "SUFRAMA", "END", "NUM", "COMPL", "BAIRRO"],
    "0175": ["REG", "DT_ALT", "NR_CAMPO", "CONT_ANT"],
    "0190": ["REG", "UNID", "DESCR"],
    "0200": [
        "REG", "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM",
        "UNID_INV", "TIPO_ITEM", "COD_NCM", "EX_IPI", "COD_GEN", "COD_LST",
        "ALIQ_ICMS", "CEST"],
    "0205": ["REG", "DESCR_ANT_ITEM", "DT_INI", "DT_FIM", "COD_ANT_ITEM"],
    "0206": ["REG", "COD_COMB"],
    "0210": ["REG", "COD_ITEM_COMP", "QTD_COMP", "PERDA"],
    "0220": ["REG", "UNID_CONV", "FAT_CONV", "COD_BARRA"],
    "0221": ["REG", "COD_ITEM_ATOMICO", "QTD_CONTIDA"],
    "0300": [
        "REG", "COD_IND_BEM", "IDENT_MERC", "DESCR_ITEM", "COD_PRNC",
        "COD_CTA", "NR_PARC"],
    "0305": ["REG", "COD_CCUS", "FUNC", "VIDA_UTIL"],
    "0400": ["REG", "COD_NAT", "DESCR_NAT"],
    "0450": ["REG", "COD_INF", "TXT"],
    "0460": ["REG", "COD_OBS", "TXT"],
    "0500": [
        "REG", "DT_ALT", "COD_NAT_CC", "IND_CTA", "NIVEL", "COD_CTA",
        "NOME_CTA"],
    "0600": ["REG", "DT_ALT", "COD_CCUS", "CCUS"],
    "0990": ["REG", "QTD_LIN_0"],
    "1001": ["REG", "IND_MOV"],
    "1010": [
        "REG", "IND_EXP", "IND_CCRF", "IND_COMB", "IND_USINA", "IND_VA",
        "IND_EE", "IND_CART", "IND_FORM", "IND_AER", "IND_GIAF1", "IND_GIAF3",
        "IND_GIAF4", "IND_REST_RESSARC_COMPL_ICMS"],
    "1100": [
        "REG", "IND_DOC", "NRO_DE", "DT_DE", "NAT_EXP", "NRO_RE", "DT_RE",
        "CHC_EMB", "DT_CHC", "DT_AVB", "TP_CHC", "PAIS"],
    "1105": [
        "REG", "COD_MOD", "SERIE", "NUM_DOC", "CHV_NFE", "DT_DOC",
        "COD_ITEM"],
    "1110": [
        "REG", "COD_PART", "COD_MOD", "SER", "NUM_DOC", "DT_DOC", "CHV_NFE",
        "NR_MEMO", "QTD", "UNID"],
    "1200": [
        "REG", "COD_AJ_APUR", "SLD_CRED", "CRED_APR", "CRED_RECEB",
        "CRED_UTIL", "SLD_CRED_FIM"],
    "1210": ["REG", "TIPO_UTIL", "NR_DOC", "VL_CRED_UTIL", "CHV_DOCE"],
    "1250": [
        "REG", "VL_CREDITO_ICMS_OP", "VL_ICMS_ST_REST", "VL_FCP_ST_REST",
        "VL_ICMS_ST_COMPL", "VL_FCP_ST_COMPL"],
    "1255": [
        "REG", "COD_MOT_REST_COMPL", "VL_CREDITO_ICMS_OP_MOT",
        "VL_ICMS_ST_REST_MOT", "VL_FCP_ST_REST_MOT", "VL_ICMS_ST_COMPL_MOT",
        "VL_FCP_ST_COMPL_MOT"],
    "1300": [
        "REG", "COD_ITEM", "DT_FECH", "ESTQ_ABERT", "VOL_ENTR", "VOL_DISP",
        "VOL_SAIDAS", "ESTQ_ESCR", "VAL_AJ_PERDA", "VAL_AJ_GANHO",
        "FECH_FISICO"],
    "1310": [
        "REG", "NUM_TANQUE", "ESTQ_ABERT", "VOL_ENTR", "VOL_DISP",
        "VOL_SAIDAS", "ESTQ_ESCR", "VAL_AJ_PERDA", "VAL_AJ_GANHO",
        "FECH_FISICO", "CAP_TANQUE"],
    "1320": [
        "REG", "NUM_BICO", "NR_INTERV", "MOT_INTERV", "NOM_INTERV",
        "CNPJ_INTERV", "CPF_INTERV", "VAL_FECHA", "VAL_ABERT", "VOL_AFERI",
        "VOL_VENDAS"],
    "1350": ["REG", "SERIE", "FABRICANTE", "MODELO", "TIPO_MEDICAO"],
    "1360": ["REG", "NUM_LACRE", "DT_APLICACAO"],
    "1370": ["REG", "NUM_BICO", "COD_ITEM", "NUM_TANQUE"],
    "1390": ["REG", "COD_PROD"],
    "1391": [
        "REG", "DT_REGISTRO", "QTD_MOID", "ESTQ_INI", "QTD_PRODUZ",
        "ENT_ANID_HID", "OUTR_ENTR", "PERDA", "CONS", "SAI_ANI_HID",
        "SAIDAS", "ESTQ_FIN", "ESTQ_INI_MEL", "PROD_DIA_MEL", "UTIL_MEL",
        "PROD_ALC_MEL", "OBS", "COD_ITEM", "TP_RESIDUO", "QTD_RESIDUO",
        "QTD_RESIDUO_DDG", "QTD_RESIDUO_WDG", "QTD_RESIDUO_CANA"],
    "1400": ["REG", "COD_ITEM_IPM", "MUN", "VALOR"],
    "1500": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "SUB", "COD_CONS", "NUM_DOC", "DT_DOC", "DT_E_S", "VL_DOC",
        "VL_DESC", "VL_FORN", "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "COD_INF", "VL_PIS",
        "VL_COFINS", "TP_LIGACAO", "COD_GRUPO_TENSAO"],
    "1510": [
        "REG", "NUM_ITEM", "COD_ITEM", "COD_CLASS", "QTD", "UNID", "VL_ITEM",
        "VL_DESC", "CST_ICMS", "CFOP", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS",
        "VL_BC_ICMS_ST", "ALIQ_ST", "VL_ICMS_ST", "IND_REC", "COD_PART",
        "VL_PIS", "VL_COFINS", "COD_CTA"],
    "1600": ["REG", "COD_PART", "TOT_CREDITO", "TOT_DEBITO"],
    "1601": [
        "REG", "COD_PART_IP", "COD_PART_IT", "TOT_VS", "TOT_ISS",
        "TOT_OUTROS"],
    "1700": [
        "REG", "COD_DISP", "COD_MOD", "SER", "SUB", "NUM_DOC_INI",
        "NUM_DOC_FIN", "NUM_AUT"],
    "1710": ["REG", "NUM_DOC_INI", "NUM_DOC_FIN"],
    "1800": [
        "REG", "VL_CARGA", "VL_PASS", "VL_FAT", "IND_RAT", "VL_ICMS_ANT",
        "VL_BC_ICMS", "VL_ICMS_APUR", "VL_BC_ICMS_APUR", "VL_DIF"],
    "1900": ["REG", "IND_APUR_ICMS", "DESCR_COMPL_OUT_APUR"],
    "1910": ["REG", "DT_INI", "DT_FIN"],
    "1920": [
        "REG", "VL_TOT_TRANSF_DEBITOS_OA", "VL_TOT_AJ_DEBITOS_OA",
        "VL_ESTORNOS_CRED_OA", "VL_TOT_TRANSF_CREDITOS_OA",
        "VL_TOT_AJ_CREDITOS_OA", "VL_ESTORNOS_DEB_OA",
        "VL_SLD_CREDOR_ANT_OA", "VL_SLD_APURADO_OA", "VL_TOT_DED",
        "VL_ICMS_RECOLHER_OA", "VL_SLD_CREDOR_TRANSP_OA", "DEB_ESP_OA"],
    "1921": ["REG", "COD_AJ_APUR", "DESCR_COMPL_AJ", "VL_AJ_APUR"],
    "1922": ["REG", "NUM_DA", "NUM_PROC", "IND_PROC", "PROC", "TXT_COMPL"],
    "1923": [
        "REG", "COD_PART", "COD_MOD", "SER", "SUB", "NUM_DOC", "DT_DOC",
        "COD_ITEM", "VL_AJ_ITEM", "CHV_DOCE"],
    "1925": ["REG", "COD_INF_ADIC", "VL_INF_ADIC", "DESCR_COMPL_AJ"],
    "1926": [
        "REG", "COD_OR", "VL_OR", "DT_VCTO", "COD_REC", "NUM_PROC",
        "IND_PROC", "PROC", "TXT_COMPL", "MES_REF"],
    "1960": [
        "REG", "IND_AP", "G1_01", "G1_02", "G1_03", "G1_04", "G1_05",
        "G1_06", "G1_07", "G1_08", "G1_09", "G1_10", "G1_11"],
    "1970": [
        "REG", "IND_AP", "G3_01", "G3_02", "G3_03", "G3_04", "G3_05",
        "G3_06", "G3_07", "G3_T", "G3_08", "G3_09"],
    "1975": ["REG", "ALIQ_IMP_BASE", "G3_10", "G3_11", "G3_12"],
    "1980": [
        "REG", "IND_AP", "G4_01", "G4_02", "G4_03", "G4_04", "G4_05",
        "G4_06", "G4_07", "G4_08", "G4_09", "G4_10", "G4_11", "G4_12"],
    "1990": ["REG", "QTD_LIN_1"],
    "9001": ["REG", "IND_MOV"],
    "9900": ["REG", "REG_BLC", "QTD_REG_BLC"],
    "9990": ["REG", "QTD_LIN_9"],
    "9999": ["REG", "QTD_LIN"],
    "B001": ["REG", "IND_DAD"],
    "B020": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "NUM_DOC", "CHV_NFE", "DT_DOC", "COD_MUN_SERV", "VL_CONT",
        "VL_MAT_TERC", "VL_SUB", "VL_ISNT_ISS", "VL_DED_BC", "VL_BC_ISS",
        "VL_BC_ISS_RT", "VL_ISS_RT", "VL_ISS", "COD_INF_OBS"],
    "B025": [
        "REG", "VL_CONT_P", "VL_BC_ISS_P", "ALIQ_ISS", "VL_ISS_P",
        "VL_ISNT_ISS_P", "COD_SERV"],
    "B030": [
        "REG", "COD_MOD", "SER", "NUM_DOC_INI", "NUM_DOC_FIN", "DT_DOC",
        "QTD_CANC", "VL_CONT", "VL_ISNT_ISS", "VL_BC_ISS", "VL_ISS",
        "COD_INF_OBS"],
    "B035": [
        "REG", "VL_CONT_P", "VL_BC_ISS_P", "ALIQ_ISS", "VL_ISS_P",
        "VL_ISNT_ISS_P", "COD_SERV"],
    "B350": [
        "REG", "COD_CTD", "CTA_ISS", "CTA_COSIF", "QTD_OCOR", "COD_SERV",
        "VL_CONT", "VL_BC_ISS", "ALIQ_ISS", "VL_ISS", "COD_INF_OBS"],
    "B420": [
        "REG", "VL_CONT", "VL_BC_ISS", "ALIQ_ISS", "VL_ISNT_ISS", "VL_ISS",
        "COD_SERV"],
    "B440": [
        "REG", "IND_OPER", "COD_PART", "VL_CONT_RT", "VL_BC_ISS_RT",
        "VL_ISS_RT"],
    "B460": [
        "REG", "IND_DED", "VL_DED", "NUM_PROC", "IND_PROC", "PROC",
        "COD_INF_OBS", "IND_OBR"],
    "B470": [
        "REG", "VL_CONT", "VL_MAT_TERC", "VL_MAT_PROP", "VL_SUB", "VL_ISNT",
        "VL_DED_BC", "VL_BC_ISS", "VL_BC_ISS_RT", "VL_ISS", "VL_ISS_RT",
        "VL_DED", "VL_ISS_REC", "VL_ISS_ST", "VL_ISS_REC_UNI"],
    "B500": ["REG", "VL_REC", "QTD_PROF", "VL_OR"],
    "B510": ["REG", "IND_PROF", "IND_ESC", "IND_SOC", "CPF", "NOME"],
    "B990": ["REG", "QTD_LIN_B"],
    "C001": ["REG", "IND_MOV"],
    "C100": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "NUM_DOC", "CHV_NFE", "DT_DOC", "DT_E_S", "VL_DOC",
        "IND_PGTO", "VL_DESC", "VL_ABAT_NT", "VL_MERC", "IND_FRT", "VL_FRT",
        "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
        "VL_ICMS_ST", "VL_IPI", "VL_PIS", "VL_COFINS", "VL_PIS_ST",
        "VL_COFINS_ST"],
    "C101": ["REG", "VL_FCP_UF_DEST", "VL_ICMS_UF_DEST", "VL_ICMS_UF_REM"],
    "C105": ["REG", "OPER", "UF"],
    "C110": ["REG", "COD_INF", "TXT_COMPL"],
    "C111": ["REG", "NUM_PROC", "IND_PROC"],
    "C112": [
        "REG", "COD_DA", "UF", "NUM_DA", "COD_AUT", "VL_DA", "DT_VCTO",
        "DT_PGTO"],
    "C113": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "SER", "SUB",
        "NUM_DOC", "DT_DOC", "CHV_DOCE"],
    "C114": ["REG", "COD_MOD", "ECF_FAB", "ECF_CX", "NUM_DOC", "DT_DOC"],
    "C115": [
        "REG", "IND_CARGA", "CNPJ_COL", "IE_COL", "CPF_COL", "COD_MUN_COL",
        "CNPJ_ENTG", "IE_ENTG", "CPF_ENTG", "COD_MUN_ENTG"],
    "C116": ["REG", "COD_MOD", "NR_SAT", "CHV_CFE", "NUM_CFE", "DT_DOC"],
    "C120": [
        "REG", "COD_DOC_IMP", "NUM_DOC_IMP", "PIS_IMP", "COFINS_IMP",
        "NUM_ACDRAW"],
    "C130": [
        "REG", "VL_SERV_NT", "VL_BC_ISSQN", "VL_ISSQN", "VL_BC_IRRF",
        "VL_IRRF", "VL_BC_PREV", "VL_PREV"],
    "C140": [
        "REG", "IND_EMIT", "IND_TIT", "DESC_TIT", "NUM_TIT", "QTD_PARC",
        "VL_TIT"],
    "C141": ["REG", "NUM_PARC", "DT_VCTO", "VL_PARC"],
    "C160": [
        "REG", "COD_PART", "VEIC_ID", "QTD_VOL", "PESO_BRT", "PESO_LIQ",
        "UF_ID"],
    "C165": [
        "REG", "COD_PART", "VEIC_ID", "COD_AUT", "NR_PASSE", "HORA",
        "TEMPER", "QTD_VOL", "PESO_BRT", "PESO_LIQ", "NOM_MOT", "CPF",
        "UF_ID"],
    "C170": [
        "REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID",
        "VL_ITEM", "VL_DESC", "IND_MOV", "CST_ICMS", "CFOP", "COD_NAT",
        "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "ALIQ_ST",
        "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ", "VL_BC_IPI",
        "ALIQ_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
        "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA", "VL_ABAT_NT"],
    "C171": ["REG", "NUM_TANQUE", "QTDE"],
    "C172": ["REG", "VL_BC_ISSQN", "ALIQ_ISSQN", "VL_ISSQN"],
    "C173": [
        "REG", "LOTE_MED", "QTD_ITEM", "DT_FAB", "DT_VAL", "IND_MED",
        "TP_PROD", "VL_TAB_MAX"],
    "C174": ["REG", "IND_ARM", "NUM_ARM", "DESCR_COMPL"],
    "C175": ["REG", "IND_VEIC_OPER", "CNPJ", "UF", "CHASSI_VEIC"],
    "C176": [
        "REG", "COD_MOD_ULT_E", "NUM_DOC_ULT_E", "SER_ULT_E", "DT_ULT_E",
        "COD_PART_ULT_E", "QUANT_ULT_E", "VL_UNIT_ULT_E", "VL_UNIT_BC_ST",
        "CHAVE_NFE_ULT_E", "NUM_ITEM_ULT_E", "VL_UNIT_BC_ICMS_ULT_E",
        "ALIQ_ICMS_ULT_E", "VL_UNIT_LIMITE_BC_ICMS_ULT_E",
        "VL_UNIT_ICMS_ULT_E", "ALIQ_ST_ULT_E", "VL_UNIT_RES", "COD_RESP_RET",
        "COD_MOT_RES", "CHAVE_NFE_RET", "COD_PART_NFE_RET", "SER_NFE_RET",
        "NUM_NFE_RET", "ITEM_NFE_RET", "COD_DA", "NUM_DA",
        "VL_UNIT_RES_FCP_ST"],
    "C177": ["REG", "COD_INF_ITEM"],
    "C178": ["REG", "CL_ENQ", "VL_UNID", "QUANT_PAD"],
    "C179": [
        "REG", "BC_ST_ORIG_DEST", "ICMS_ST_REP", "ICMS_ST_COMPL", "BC_RET",
        "ICMS_RET"],
    "C180": [
        "REG", "COD_RESP_RET", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_OP_CONV", "VL_UNIT_BC_ICMS_ST_CONV",
        "VL_UNIT_ICMS_ST_CONV", "VL_UNIT_FCP_ST_CONV", "COD_DA", "NUM_DA"],
    "C181": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "COD_MOD_SAIDA",
        "SERIE_SAIDA", "ECF_FAB_SAIDA", "NUM_DOC_SAIDA", "CHV_DFE_SAIDA",
        "DT_DOC_SAIDA", "NUM_ITEM_SAIDA", "VL_UNIT_CONV_SAIDA",
        "VL_UNIT_ICMS_OP_ESTOQUE_CONV_SAIDA",
        "VL_UNIT_ICMS_ST_ESTOQUE_CONV_SAIDA",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV_SAIDA",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV_SAIDA", "VL_UNIT_ICMS_OP_CONV_SAIDA",
        "VL_UNIT_ICMS_ST_CONV_REST", "VL_UNIT_FCP_ST_CONV_REST",
        "VL_UNIT_ICMS_ST_CONV_COMPL", "VL_UNIT_FCP_ST_CONV_COMPL"],
    "C185": [
        "REG", "NUM_ITEM", "COD_ITEM", "CST_ICMS", "CFOP",
        "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_ICMS_OP_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL"],
    "C186": [
        "REG", "NUM_ITEM", "COD_ITEM", "CST_ICMS", "CFOP",
        "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "COD_MOD_ENTRADA",
        "SERIE_ENTRADA", "NUM_DOC_ENTRADA", "CHV_DFE_ENTRADA",
        "DT_DOC_ENTRADA", "NUM_ITEM_ENTRADA", "VL_UNIT_CONV_ENTRADA",
        "VL_UNIT_ICMS_OP_CONV_ENTRADA", "VL_UNIT_BC_ICMS_ST_CONV_ENTRADA",
        "VL_UNIT_ICMS_ST_CONV_ENTRADA", "VL_UNIT_FCP_ST_CONV_ENTRADA"],
    "C190": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC", "VL_IPI",
        "COD_OBS"],
    "C191": ["REG", "VL_FCP_OP", "VL_FCP_ST", "VL_FCP_RET"],
    "C195": ["REG", "COD_OBS", "TXT_COMPL"],
    "C197": [
        "REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
        "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "C300": [
        "REG", "COD_MOD", "SER", "SUB", "NUM_DOC_INI", "NUM_DOC_FIN",
        "DT_DOC", "VL_DOC", "VL_PIS", "VL_COFINS", "COD_CTA"],
    "C310": ["REG", "NUM_DOC_CANC"],
    "C320": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "C321": [
        "REG", "COD_ITEM", "QTD", "UNID", "VL_ITEM", "VL_DESC", "VL_BC_ICMS",
        "VL_ICMS", "VL_PIS", "VL_COFINS"],
    "C330": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_BC_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL"],
    "C350": [
        "REG", "SER", "SUB_SER", "NUM_DOC", "DT_DOC", "CNPJ_CPF", "VL_MERC",
        "VL_DOC", "VL_DESC", "VL_PIS", "VL_COFINS", "COD_CTA"],
    "C370": [
        "REG", "NUM_ITEM", "COD_ITEM", "QTD", "UNID", "VL_ITEM", "VL_DESC"],
    "C380": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_BC_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL", "CST_ICMS", "CFOP"],
    "C390": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "C400": ["REG", "COD_MOD", "ECF_MOD", "ECF_FAB", "ECF_CX"],
    "C405": ["REG", "DT_DOC", "CRO", "CRZ", "NUM_COO_FIN", "GT_FIN", "VL_BRT"],
    "C410": ["REG", "VL_PIS", "VL_COFINS"],
    "C420": ["REG", "COD_TOT_PAR", "VLR_ACUM_TOT", "NR_TOT", "DESCR_NR_TOT"],
    "C425": [
        "REG", "COD_ITEM", "QTD", "UNID", "VL_ITEM", "VL_PIS", "VL_COFINS"],
    "C430": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_BC_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL", "CST_ICMS", "CFOP"],
    "C460": [
        "REG", "COD_MOD", "COD_SIT", "NUM_DOC", "DT_DOC", "VL_DOC", "VL_PIS",
        "VL_COFINS", "CPF_CNPJ", "NOM_ADQ"],
    "C465": ["REG", "CHV_CFE", "NUM_CCF"],
    "C470": [
        "REG", "COD_ITEM", "QTD", "QTD_CANC", "UNID", "VL_ITEM", "CST_ICMS",
        "CFOP", "ALIQ_ICMS", "VL_PIS", "VL_COFINS"],
    "C480": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_BC_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL", "CST_ICMS", "CFOP"],
    "C490": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "COD_OBS"],
    "C495": [
        "REG", "ALIQ_ICMS", "COD_ITEM", "QTD", "QTD_CANC", "UNID", "VL_ITEM",
        "VL_DESC", "VL_CANC", "VL_ACMO", "VL_BC_ICMS", "VL_ICMS", "VL_ISEN",
        "VL_NT", "VL_ICMS_ST"],
    "C500": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "SUB", "COD_CONS", "NUM_DOC", "DT_DOC", "DT_E_S", "VL_DOC",
        "VL_DESC", "VL_FORN", "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "COD_INF", "VL_PIS",
        "VL_COFINS", "TP_LIGACAO", "COD_GRUPO_TENSAO", "CHV_DOCE",
        "FIN_DOCE", "CHV_DOCE_REF", "IND_DEST", "COD_MUN_DEST", "COD_CTA",
        "COD_MOD_DOC_REF", "HASH_DOC_REF", "SER_DOC_REF", "NUM_DOC_REF",
        "MES_DOC_REF", "ENER_INJET", "OUTRAS_DED"],
    "C510": [
        "REG", "NUM_ITEM", "COD_ITEM", "COD_CLASS", "QTD", "UNID", "VL_ITEM",
        "VL_DESC", "CST_ICMS", "CFOP", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS",
        "VL_BC_ICMS_ST", "ALIQ_ST", "VL_ICMS_ST", "IND_REC", "COD_PART",
        "VL_PIS", "VL_COFINS", "COD_CTA"],
    "C590": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC", "COD_OBS"],
    "C591": ["REG", "VL_FCP_OP", "VL_FCP_ST"],
    "C595": ["REG", "COD_OBS", "TXT_COMPL"],
    "C597": [
        "REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
        "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "C600": [
        "REG", "COD_MOD", "COD_MUN", "SER", "SUB", "COD_CONS", "QTD_CONS",
        "QTD_CANC", "DT_DOC", "VL_DOC", "VL_DESC", "CONS", "VL_FORN",
        "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS", "VL_ICMS",
        "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_PIS", "VL_COFINS"],
    "C601": ["REG", "NUM_DOC_CANC"],
    "C610": [
        "REG", "COD_CLASS", "COD_ITEM", "QTD", "UNID", "VL_ITEM", "VL_DESC",
        "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_BC_ICMS", "VL_ICMS",
        "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_PIS", "VL_COFINS", "COD_CTA"],
    "C690": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_RED_BC", "VL_BC_ICMS_ST", "VL_ICMS_ST", "COD_OBS"],
    "C700": [
        "REG", "COD_MOD", "SER", "NRO_ORD_INI", "NRO_ORD_FIN", "DT_DOC_INI",
        "DT_DOC_FIN", "NOM_MEST", "CHV_COD_DIG"],
    "C790": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_RED_BC", "COD_OBS"],
    "C791": ["REG", "UF", "VL_BC_ICMS_ST", "VL_ICMS_ST"],
    "C800": [
        "REG", "COD_MOD", "COD_SIT", "NUM_CFE", "DT_DOC", "VL_CFE", "VL_PIS",
        "VL_COFINS", "CNPJ_CPF", "NR_SAT", "CHV_CFE", "VL_DESC", "VL_MERC",
        "VL_OUT_DA", "VL_ICMS", "VL_PIS_ST", "VL_COFINS_ST"],
    "C810": [
        "REG", "NUM_ITEM", "COD_ITEM", "QTD", "UNID", "VL_ITEM", "CST_ICMS",
        "CFOP"],
    "C815": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_BC_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL"],
    "C850": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "COD_OBS"],
    "C855": ["REG", "COD_OBS", "TXT_COMPL"],
    "C857": [
        "REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
        "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "C860": ["REG", "COD_MOD", "NR_SAT", "DT_DOC", "DOC_INI", "DOC_FIM"],
    "C870": ["REG", "COD_ITEM", "QTD", "UNID", "CST_ICMS", "CFOP"],
    "C880": [
        "REG", "COD_MOT_REST_COMPL", "QUANT_CONV", "UNID", "VL_UNIT_CONV",
        "VL_UNIT_ICMS_NA_OPERACAO_CONV", "VL_UNIT_ICMS_OP_CONV",
        "VL_UNIT_BC_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_ESTOQUE_CONV",
        "VL_UNIT_FCP_ICMS_ST_ESTOQUE_CONV", "VL_UNIT_ICMS_ST_CONV_REST",
        "VL_UNIT_FCP_ST_CONV_REST", "VL_UNIT_ICMS_ST_CONV_COMPL",
        "VL_UNIT_FCP_ST_CONV_COMPL"],
    "C890": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "COD_OBS"],
    "C895": ["REG", "COD_OBS", "TXT_COMPL"],
    "C897": [
        "REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
        "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "C990": ["REG", "QTD_LIN_C"],
    "D001": ["REG", "IND_MOV"],
    "D100": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "SUB", "NUM_DOC", "CHV_CTE", "DT_DOC", "DT_A_P", "TP_CT-E",
        "CHV_CTE_REF", "VL_DOC", "VL_DESC", "IND_FRT", "VL_SERV",
        "VL_BC_ICMS", "VL_ICMS", "VL_NT", "COD_INF", "COD_CTA",
        "COD_MUN_ORIG", "COD_MUN_DEST"],
    "D101": ["REG", "VL_FCP_UF_DEST", "VL_ICMS_UF_DEST", "VL_ICMS_UF_REM"],
    "D110": ["REG", "NUM_ITEM", "COD_ITEM", "VL_SERV", "VL_OUT"],
    "D120": ["REG", "COD_MUN_ORIG", "COD_MUN_DEST", "VEIC_ID", "UF_ID"],
    "D130": [
        "REG", "COD_PART_CONSG", "COD_PART_RED", "IND_FRT_RED",
        "COD_MUN_ORIG", "COD_MUN_DEST", "VEIC_ID", "VL_LIQ_FRT",
        "VL_SEC_CAT", "VL_DESP", "VL_PEDG", "VL_OUT", "VL_FRT", "UF_ID"],
    "D140": [
        "REG", "COD_PART_CONSG", "COD_MUN_ORIG", "COD_MUN_DEST", "IND_VEIC",
        "VEIC_ID", "IND_NAV", "VIAGEM", "VL_FRT_LIQ", "VL_DESP_PORT",
        "VL_DESP_CAR_DESC", "VL_OUT", "VL_FRT_BRT", "VL_FRT_MM"],
    "D150": [
        "REG", "COD_MUN_ORIG", "COD_MUN_DEST", "VEIC_ID", "VIAGEM",
        "IND_TFA", "VL_PESO_TX", "VL_TX_TERR", "VL_TX_RED", "VL_OUT",
        "VL_TX_ADV"],
    "D160": [
        "REG", "DESPACHO", "CNPJ_CPF_REM", "IE_REM", "COD_MUN_ORI",
        "CNPJ_CPF_DEST", "IE_DEST", "COD_MUN_DEST"],
    "D161": [
        "REG", "IND_CARGA", "CNPJ_CPF_COL", "IE_COL", "COD_MUN_COL",
        "CNPJ_CPF_ENTG", "IE_ENTG", "COD_MUN_ENTG"],
    "D162": [
        "REG", "COD_MOD", "SER", "NUM_DOC", "DT_DOC", "VL_DOC", "VL_MERC",
        "QTD_VOL", "PESO_BRT", "PESO_LIQ"],
    "D170": [
        "REG", "COD_PART_CONSG", "COD_PART_RED", "COD_MUN_ORIG",
        "COD_MUN_DEST", "OTM", "IND_NAT_FRT", "VL_LIQ_FRT", "VL_GRIS",
        "VL_PDG", "VL_OUT", "VL_FRT", "VEIC_ID", "UF_ID"],
    "D180": [
        "REG", "NUM_SEQ", "IND_EMIT", "CNPJ_CPF_EMIT", "UF_EMIT", "IE_EMIT",
        "COD_MUN_ORIG", "CNPJ_CPF_TOM", "UF_TOM", "IE_TOM", "COD_MUN_DEST",
        "COD_MOD", "SER", "SUB", "NUM_DOC", "DT_DOC", "VL_DOC"],
    "D190": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "D195": ["REG", "COD_OBS", "TXT_COMPL"],
    "D197": [
        "REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
        "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "D300": [
        "REG", "COD_MOD", "SER", "SUB", "NUM_DOC_INI", "NUM_DOC_FIN",
        "CST_ICMS", "CFOP", "ALIQ_ICMS", "DT_DOC", "VL_OPR", "VL_DESC",
        "VL_SERV", "VL_SEG", "VL_OUT_DESP", "VL_BC_ICMS", "VL_ICMS",
        "VL_RED_BC", "COD_OBS", "COD_CTA"],
    "D301": ["REG", "NUM_DOC_CANC"],
    "D310": ["REG", "COD_MUN_ORIG", "VL_SERV", "VL_BC_ICMS", "VL_ICMS"],
    "D350": ["REG", "COD_MOD", "ECF_MOD", "ECF_FAB", "ECF_CX"],
    "D355": ["REG", "DT_DOC", "CRO", "CRZ", "NUM_COO_FIN", "GT_FIN", "VL_BRT"],
    "D360": ["REG", "VL_PIS", "VL_COFINS"],
    "D365": ["REG", "COD_TOT_PAR", "VLR_ACUM_TOT", "NR_TOT", "DESCR_NR_TOT"],
    "D370": [
        "REG", "COD_MUN_ORIG", "VL_SERV", "QTD_BILH", "VL_BC_ICMS",
        "VL_ICMS"],
    "D390": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ISSQN",
        "ALIQ_ISSQN", "VL_ISSQN", "VL_BC_ICMS", "VL_ICMS", "COD_OBS"],
    "D400": [
        "REG", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC",
        "DT_DOC", "VL_DOC", "VL_DESC", "VL_SERV", "VL_BC_ICMS", "VL_ICMS",
        "VL_PIS", "VL_COFINS", "COD_CTA"],
    "D410": [
        "REG", "COD_MOD", "SER", "SUB", "NUM_DOC_INI", "NUM_DOC_FIN",
        "DT_DOC", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_DESC",
        "VL_SERV", "VL_BC_ICMS", "VL_ICMS"],
    "D411": ["REG", "NUM_DOC_CANC"],
    "D420": ["REG", "COD_MUN_ORIG", "VL_SERV", "VL_BC_ICMS", "VL_ICMS"],
    "D500": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "SUB", "NUM_DOC", "DT_DOC", "DT_A_P", "VL_DOC", "VL_DESC",
        "VL_SERV", "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS", "VL_ICMS",
        "COD_INF", "VL_PIS", "VL_COFINS", "COD_CTA", "TP_ASSINANTE"],
    "D510": [
        "REG", "NUM_ITEM", "COD_ITEM", "COD_CLASS", "QTD", "UNID", "VL_ITEM",
        "VL_DESC", "CST_ICMS", "CFOP", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS",
        "VL_BC_ICMS_UF", "VL_ICMS_UF", "IND_REC", "COD_PART", "VL_PIS",
        "VL_COFINS", "COD_CTA"],
    "D530": [
        "REG", "IND_SERV", "DT_INI_SERV", "DT_FIN_SERV", "PER_FISCAL",
        "COD_AREA", "TERMINAL"],
    "D590": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_UF", "VL_ICMS_UF", "VL_RED_BC", "COD_OBS"],
    "D600": [
        "REG", "COD_MOD", "COD_MUN", "SER", "SUB", "COD_CONS", "QTD_CONS",
        "DT_DOC", "VL_DOC", "VL_DESC", "VL_SERV", "VL_SERV_NT", "VL_TERC",
        "VL_DA", "VL_BC_ICMS", "VL_ICMS", "VL_PIS", "VL_COFINS"],
    "D610": [
        "REG", "COD_CLASS", "COD_ITEM", "QTD", "UNID", "VL_ITEM", "VL_DESC",
        "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_BC_ICMS", "VL_ICMS",
        "VL_BC_ICMS_UF", "VL_ICMS_UF", "VL_RED_BC", "VL_PIS", "VL_COFINS",
        "COD_CTA"],
    "D690": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_UF", "VL_ICMS_UF", "VL_RED_BC", "COD_OBS"],
    "D695": [
        "REG", "COD_MOD", "SER", "NRO_ORD_INI", "NRO_ORD_FIN", "DT_DOC_INI",
        "DT_DOC_FIN", "NOM_MEST", "CHV_COD_DIG"],
    "D696": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_BC_ICMS_UF", "VL_ICMS_UF", "VL_RED_BC", "COD_OBS"],
    "D697": ["REG", "UF", "VL_BC_ICMS", "VL_ICMS"],
    "D700": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "NUM_DOC", "DT_DOC", "DT_E_S", "VL_DOC", "VL_DESC", "VL_SERV",
        "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS", "VL_ICMS", "COD_INF",
        "VL_PIS", "VL_COFINS", "CHV_DOCE", "FIN_DOCE", "TIP_FAT",
        "COD_MOD_DOC_REF", "CHV_DOCE_REF", "HASH_DOC_REF", "SER_DOC_REF",
        "NUM_DOC_REF", "MES_DOC_REF", "COD_MUN_DEST", "DED"],
    "D730": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "D731": ["REG", "VL_FCP_OP"],
    "D735": ["REG", "COD_OBS", "TXT_COMPL"],
    "D737": [
        "REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS",
        "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "D750": [
        "REG", "COD_MOD", "SER", "DT_DOC", "QTD_CONS", "IND_PREPAGO",
        "VL_DOC", "VL_SERV", "VL_SERV_NT", "VL_TERC", "VL_DESC", "VL_DA",
        "VL_BC_ICMS", "VL_ICMS", "VL_PIS", "VL_COFINS", "DED"],
    "D760": [
        "REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS",
        "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "D761": ["REG", "VL_FCP_OP"],
    "D990": ["REG", "QTD_LIN_D"],
    "E001": ["REG", "IND_MOV"],
    "E100": ["REG", "DT_INI", "DT_FIN"],
    "E110": [
        "REG", "VL_TOT_DEBITOS", "VL_AJ_DEBITOS", "VL_TOT_AJ_DEBITOS",
        "VL_ESTORNOS_CRED", "VL_TOT_CREDITOS", "VL_AJ_CREDITOS",
        "VL_TOT_AJ_CREDITOS", "VL_ESTORNOS_DEB", "VL_SLD_CREDOR_ANT",
        "VL_SLD_APURADO", "VL_TOT_DED", "VL_ICMS_RECOLHER",
        "VL_SLD_CREDOR_TRANSPORTAR", "DEB_ESP"],
    "E111": ["REG", "COD_AJ_APUR", "DESCR_COMPL_AJ", "VL_AJ_APUR"],
    "E112": ["REG", "NUM_DA", "NUM_PROC", "IND_PROC", "PROC", "TXT_COMPL"],
    "E113": [
        "REG", "COD_PART", "COD_MOD", "SER", "SUB", "NUM_DOC", "DT_DOC",
        "COD_ITEM", "VL_AJ_ITEM", "CHV_DOCE"],
    "E115": ["REG", "COD_INF_ADIC", "VL_INF_ADIC", "DESCR_COMPL_AJ"],
    "E116": [
        "REG", "COD_OR", "VL_OR", "DT_VCTO", "COD_REC", "NUM_PROC",
        "IND_PROC", "PROC", "TXT_COMPL", "MES_REF"],
    "E200": ["REG", "UF", "DT_INI", "DT_FIN"],
    "E210": [
        "REG", "IND_MOV_ST", "VL_SLD_CRED_ANT_ST", "VL_DEVOL_ST",
        "VL_RESSARC_ST", "VL_OUT_CRED_ST", "VL_AJ_CREDITOS_ST",
        "VL_RETENCAO_ST", "VL_OUT_DEB_ST", "VL_AJ_DEBITOS_ST",
        "VL_SLD_DEV_ANT_ST", "VL_DEDUCOES_ST", "VL_ICMS_RECOL_ST",
        "VL_SLD_CRED_ST_TRANSPORTAR", "DEB_ESP_ST"],
    "E220": ["REG", "COD_AJ_APUR", "DESCR_COMPL_AJ", "VL_AJ_APUR"],
    "E230": ["REG", "NUM_DA", "NUM_PROC", "IND_PROC", "PROC", "TXT_COMPL"],
    "E240": [
        "REG", "COD_PART", "COD_MOD", "SER", "SUB", "NUM_DOC", "DT_DOC",
        "COD_ITEM", "VL_AJ_ITEM", "CHV_DOCE"],
    "E250": [
        "REG", "COD_OR", "VL_OR", "DT_VCTO", "COD_REC", "NUM_PROC",
        "IND_PROC", "PROC", "TXT_COMPL", "MES_REF"],
    "E300": ["REG", "UF", "DT_INI", "DT_FIN"],
    "E310": [
        "REG", "IND_MOV_FCP_DIFAL", "VL_SLD_CRED_ANT_DIFAL",
        "VL_TOT_DEBITOS_DIFAL", "VL_OUT_DEB_DIFAL", "VL_TOT_CREDITOS_DIFAL",
        "VL_OUT_CRED_DIFAL", "VL_SLD_DEV_ANT_DIFAL", "VL_DEDUCOES_DIFAL",
        "VL_RECOL_DIFAL", "VL_SLD_CRED_TRANSPORTAR_DIFAL", "DEB_ESP_DIFAL",
        "VL_SLD_CRED_ANT_FCP", "VL_TOT_DEB_FCP", "VL_OUT_DEB_FCP",
        "VL_TOT_CRED_FCP", "VL_OUT_CRED_FCP", "VL_SLD_DEV_ANT_FCP",
        "VL_DEDUCOES_FCP", "VL_RECOL_FCP", "VL_SLD_CRED_TRANSPORTAR_FCP",
        "DEB_ESP_FCP"],
    "E311": ["REG", "COD_AJ_APUR", "DESCR_COMPL_AJ", "VL_AJ_APUR"],
    "E312": ["REG", "NUM_DA", "NUM_PROC", "IND_PROC", "PROC", "TXT_COMPL"],
    "E313": [
        "REG", "COD_PART", "COD_MOD", "SER", "SUB", "NUM_DOC", "CHV_DOCE",
        "DT_DOC", "COD_ITEM", "VL_AJ_ITEM"],
    "E316": [
        "REG", "COD_OR", "VL_OR", "DT_VCTO", "COD_REC", "NUM_PROC",
        "IND_PROC", "PROC", "TXT_COMPL", "MES_REF"],
    "E500": ["REG", "IND_APUR", "DT_INI", "DT_FIN"],
    "E510": ["REG", "CFOP", "CST_IPI", "VL_CONT_IPI", "VL_BC_IPI", "VL_IPI"],
    "E520": [
        "REG", "VL_SD_ANT_IPI", "VL_DEB_IPI", "VL_CRED_IPI", "VL_OD_IPI",
        "VL_OC_IPI", "VL_SC_IPI", "VL_SD_IPI"],
    "E530": [
        "REG", "IND_AJ", "VL_AJ", "COD_AJ", "IND_DOC", "NUM_DOC", "DESCR_AJ"],
    "E531": [
        "REG", "COD_PART", "COD_MOD", "SER", "SUB", "NUM_DOC", "DT_DOC",
        "COD_ITEM", "VL_AJ_ITEM", "CHV_NFE"],
    "E990": ["REG", "QTD_LIN_E"],
    "G001": ["REG", "IND_MOV"],
    "G110": [
        "REG", "DT_INI", "DT_FIN", "SALDO_IN_ICMS", "SOM_PARC",
        "VL_TRIB_EXP", "VL_TOTAL", "IND_PER_SAI", "ICMS_APROP",
        "SOM_ICMS_OC"],
    "G125": [
        "REG", "COD_IND_BEM", "DT_MOV", "TIPO_MOV", "VL_IMOB_ICMS_OP",
        "VL_IMOB_ICMS_ST", "VL_IMOB_ICMS_FRT", "VL_IMOB_ICMS_DIF",
        "NUM_PARC", "VL_PARC_PASS"],
    "G126": [
        "REG", "DT_INI", "DT_FIM", "NUM_PARC", "VL_PARC_PASS", "VL_TRIB_OC",
        "VL_TOTAL", "IND_PER_SAI", "VL_PARC_APROP"],
    "G130": [
        "REG", "IND_EMIT", "COD_PART", "COD_MOD", "SERIE", "NUM_DOC",
        "CHV_NFE_CTE", "DT_DOC", "NUM_DA"],
    "G140": [
        "REG", "NUM_ITEM", "COD_ITEM", "QTDE", "UNID", "VL_ICMS_OP_APLICADO",
        "VL_ICMS_ST_APLICADO", "VL_ICMS_FRT_APLICADO",
        "VL_ICMS_DIF_APLICADO"],
    "G990": ["REG", "QTD_LIN_G"],
    "H001": ["REG", "IND_MOV"],
    "H005": ["REG", "DT_INV", "VL_INV", "MOT_INV"],
    "H010": [
        "REG", "COD_ITEM", "UNID", "QTD", "VL_UNIT", "VL_ITEM", "IND_PROP",
        "COD_PART", "TXT_COMPL", "COD_CTA", "VL_ITEM_IR"],
    "H020": ["REG", "CST_ICMS", "BC_ICMS", "VL_ICMS"],
    "H030": ["REG", "VL_ICMS_OP", "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_FCP"],
    "H990": ["REG", "QTD_LIN_H"],
    "K001": ["REG", "IND_MOV"],
    "K010": ["REG", "IND_TP_LEIAUTE"],
    "K100": ["REG", "DT_INI", "DT_FIN"],
    "K200": ["REG", "DT_EST", "COD_ITEM", "QTD", "IND_EST", "COD_PART"],
    "K210": [
        "REG", "DT_INI_OS", "DT_FIN_OS", "COD_DOC_OS", "COD_ITEM_ORI",
        "QTD_ORI"],
    "K215": ["REG", "COD_ITEM_DES", "QTD_DES"],
    "K220": [
        "REG", "DT_MOV", "COD_ITEM_ORI", "COD_ITEM_DEST", "QTD_ORI",
        "QTD_DEST"],
    "K230": [
        "REG", "DT_INI_OP", "DT_FIN_OP", "COD_DOC_OP", "COD_ITEM", "QTD_ENC"],
    "K235": ["REG", "DT_SAIDA", "COD_ITEM", "QTD", "COD_INS_SUBST"],
    "K250": ["REG", "DT_PROD", "COD_ITEM", "QTD"],
    "K255": ["REG", "DT_CONS", "COD_ITEM", "QTD", "COD_INS_SUBST"],
    "K260": [
        "REG", "COD_OP_OS", "COD_ITEM", "DT_SAIDA", "QTD_SAIDA", "DT_RET",
        "QTD_RET"],
    "K265": ["REG", "COD_ITEM", "QTD_CONS", "QTD_RET"],
    "K270": [
        "REG", "DT_INI_AP", "DT_FIN_AP", "COD_OP_OS", "COD_ITEM",
        "QTD_COR_POS", "QTD_COR_NEG", "ORIGEM"],
    "K275": ["REG", "COD_ITEM", "QTD_COR_POS", "QTD_COR_NEG", "COD_INS_SUBST"],
    "K280": [
        "REG", "DT_EST", "COD_ITEM", "QTD_COR_POS", "QTD_COR_NEG", "IND_EST",
        "COD_PART"],
    "K290": ["REG", "DT_INI_OP", "DT_FIN_OP", "COD_DOC_OP"],
    "K291": ["REG", "COD_ITEM", "QTD"],
    "K292": ["REG", "COD_ITEM", "QTD"],
    "K300": ["REG", "DT_PROD"],
    "K301": ["REG", "COD_ITEM", "QTD"],
    "K302": ["REG", "COD_ITEM", "QTD"],
    "K990": ["REG", "QTD_LIN_K"],
}

CAMPOS_CONTRIB = {
    "0000": [
        "REG", "COD_VER", "TIPO_ESCRIT", "IND_SIT_ESP", "NUM_REC_ANTERIOR",
        "DT_INI", "DT_FIN", "NOME", "CNPJ", "UF", "COD_MUN", "SUFRAMA",
        "IND_NAT_PJ", "IND_ATIV"],
    "0001": ["REG", "IND_MOV"],
    "0035": ["REG", "COD_SCP", "DESC_SCP", "INF_COMP"],
    "0100": [
        "REG", "NOME", "CPF", "CRC", "CNPJ", "CEP", "END", "NUM", "COMPL",
        "BAIRRO", "FONE", "FAX", "EMAIL", "COD_MUN"],
    "0110": [
        "REG", "COD_INC_TRIB", "IND_APRO_CRED", "COD_TIPO_CONT",
        "IND_REG_CUM"],
    "0111": [
        "REG", "REC_BRU_NCUM_TRIB_MI", "REC_BRU_NCUM_NT_MI",
        "REC_BRU_NCUM_EXP", "REC_BRU_CUM", "REC_BRU_TOTAL"],
    "0120": ["REG", "MES_REFER", "INF_COMP"],
    "0140": [
        "REG", "COD_EST", "NOME", "CNPJ", "UF", "IE", "COD_MUN", "IM",
        "SUFRAMA"],
    "0145": [
        "REG", "COD_INC_TRIB", "VL_REC_TOT", "VL_REC_ATIV",
        "VL_REC_DEMAIS_ATIV", "INFO_COMPL"],
    "0150": [
        "REG", "COD_PART", "NOME", "COD_PAIS", "CNPJ", "CPF", "IE",
        "COD_MUN", "SUFRAMA", "END", "NUM", "COMPL", "BAIRRO"],
    "0190": ["REG", "UNID", "DESCR"],
    "0200": [
        "REG", "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM",
        "UNID_INV", "TIPO_ITEM", "COD_NCM", "EX_IPI", "COD_GEN", "COD_LST",
        "ALIQ_ICMS", "CEST"],
    "0205": ["REG", "DESCR_ANT_ITEM", "DT_INI", "DT_FIM", "COD_ANT_ITEM"],
    "0206": ["REG", "COD_COMB"],
    "0208": ["REG", "COD_TAB", "COD_GRU", "MARCA_COM"],
    "0400": ["REG", "COD_NAT", "DESCR_NAT"],
    "0450": ["REG", "COD_INF", "TXT"],
    "0500": [
        "REG", "DT_ALT", "COD_NAT_CC", "IND_CTA", "NIVEL", "COD_CTA",
        "NOME_CTA", "COD_CTA_REF", "CNPJ_EST"],
    "0600": ["REG", "DT_ALT", "COD_CCUS", "CCUS"],
    "0900": [
        "REG", "REC_TOTAL_BLOCO_A", "REC_NRB_BLOCO_A", "REC_TOTAL_BLOCO_C",
        "REC_NRB_BLOCO_C", "REC_TOTAL_BLOCO_D", "REC_NRB_BLOCO_D",
        "REC_TOTAL_BLOCO_F", "REC_NRB_BLOCO_F", "REC_TOTAL_BLOCO_I",
        "REC_NRB_BLOCO_I", "REC_TOTAL_BLOCO_1", "REC_NRB_BLOCO_1",
        "REC_TOTAL_PERIODO", "REC_TOTAL_NRB_PERIODO"],
    "0990": ["REG", "QTD_LIN_0"],
    "1001": ["REG", "IND_MOV"],
    "1010": [
        "REG", "NUM_PROC", "ID_SEC_JUD", "ID_VARA", "IND_NAT_ACAO",
        "DESC_DEC_JUD", "DT_SENT_JUD"],
    "1011": [
        "REG", "REG_REF", "CHAVE_DOC", "COD_PART", "COD_ITEM", "DT_OPER",
        "VL_OPER", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS",
        "CST_PIS_SUSP", "VL_BC_PIS_SUSP", "ALIQ_PIS_SUSP", "VL_PIS_SUSP",
        "CST_COFINS_SUSP", "VL_BC_COFINS_SUSP", "ALIQ_COFINS_SUSP",
        "VL_COFINS_SUSP", "COD_CTA", "COD_CCUS", "DESC_DOC_OPER"],
    "1020": ["REG", "NUM_PROC", "IND_NAT_ACAO", "DT_DEC_ADM"],
    "1050": [
        "REG", "DT_REF", "IND_AJ_BC", "CNPJ", "VL_AJ_TOT", "VL_AJ_CST01",
        "VL_AJ_CST02", "VL_AJ_CST03", "VL_AJ_CST04", "VL_AJ_CST05",
        "VL_AJ_CST06", "VL_AJ_CST07", "VL_AJ_CST08", "VL_AJ_CST09",
        "VL_AJ_CST49", "VL_AJ_CST99", "IND_APROP", "NUM_REC", "INFO_COMPL"],
    "1100": [
        "REG", "PER_APU_CRED", "ORIG_CRED", "CNPJ_SUC", "COD_CRED",
        "VL_CRED_APU", "VL_CRED_EXT_APU", "VL_TOT_CRED_APU",
        "VL_CRED_DESC_PA_ANT", "VL_CRED_PER_PA_ANT", "VL_CRED_DCOMP_PA_ANT",
        "SD_CRED_DISP_EFD", "VL_CRED_DESC_EFD", "VL_CRED_PER_EFD",
        "VL_CRED_DCOMP_EFD", "VL_CRED_TRANS", "VL_CRED_OUT", "SLD_CRED_FIM"],
    "1101": [
        "REG", "COD_PART", "COD_ITEM", "COD_MOD", "SER", "SUB_SER",
        "NUM_DOC", "DT_OPER", "CHV_NFE", "VL_OPER", "CFOP", "NAT_BC_CRED",
        "IND_ORIG_CRED", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "COD_CTA", "COD_CCUS", "DESC_COMPL", "PER_ESCRIT", "CNPJ"],
    "1102": [
        "REG", "VL_CRED_PIS_TRIB_MI", "VL_CRED_PIS_NT_MI", "VL_CRED_PIS_EXP"],
    "1200": [
        "REG", "PER_APUR_ANT", "NAT_CONT_REC", "VL_CONT_APUR",
        "VL_CRED_PIS_DESC", "VL_CONT_DEV", "VL_OUT_DED", "VL_CONT_EXT",
        "VL_MUL", "VL_JUR", "DT_RECOL"],
    "1210": [
        "REG", "CNPJ", "CST_PIS", "COD_PART", "DT_OPER", "VL_OPER",
        "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "COD_CTA", "DESC_COMPL"],
    "1220": ["REG", "PER_APU_CRED", "ORIG_CRED", "COD_CRED", "VL_CRED"],
    "1300": [
        "REG", "IND_NAT_RET", "PR_REC_RET", "VL_RET_APU", "VL_RET_DED",
        "VL_RET_PER", "VL_RET_DCOMP", "SLD_RET"],
    "1500": [
        "REG", "PER_APU_CRED", "ORIG_CRED", "CNPJ_SUC", "COD_CRED",
        "VL_CRED_APU", "VL_CRED_EXT_APU", "VL_TOT_CRED_APU",
        "VL_CRED_DESC_PA_ANT", "VL_CRED_PER_PA_ANT", "VL_CRED_DCOMP_PA_ANT",
        "SD_CRED_DISP_EFD", "VL_CRED_DESC_EFD", "VL_CRED_PER_EFD",
        "VL_CRED_DCOMP_EFD", "VL_CRED_TRANS", "VL_CRED_OUT", "SLD_CRED_FIM"],
    "1501": [
        "REG", "COD_PART", "COD_ITEM", "COD_MOD", "SER", "SUB_SER",
        "NUM_DOC", "DT_OPER", "CHV_NFE", "VL_OPER", "CFOP", "NAT_BC_CRED",
        "IND_ORIG_CRED", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS",
        "VL_COFINS", "COD_CTA", "COD_CCUS", "DESC_COMPL", "PER_ESCRIT",
        "CNPJ"],
    "1502": [
        "REG", "VL_CRED_COFINS_TRIB_MI", "VL_CRED_COFINS_NT_MI",
        "VL_CRED_COFINS_EXP"],
    "1600": [
        "REG", "PER_APUR_ANT", "NAT_CONT_REC", "VL_CONT_APUR",
        "VL_CRED_COFINS_DESC", "VL_CONT_DEV", "VL_OUT_DED", "VL_CONT_EXT",
        "VL_MUL", "VL_JUR", "DT_RECOL"],
    "1610": [
        "REG", "CNPJ", "CST_COFINS", "COD_PART", "DT_OPER", "VL_OPER",
        "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA", "DESC_COMPL"],
    "1620": ["REG", "PER_APU_CRED", "ORIG_CRED", "COD_CRED", "VL_CRED"],
    "1700": [
        "REG", "IND_NAT_RET", "PR_REC_RET", "VL_RET_APU", "VL_RET_DED",
        "VL_RET_PER", "VL_RET_DCOMP", "SLD_RET"],
    "1800": [
        "REG", "INC_IMOB", "REC_RECEB_RET", "REC_FIN_RET", "BC_RET",
        "ALIQ_RET", "VL_REC_UNI", "DT_REC_UNI", "COD_REC"],
    "1809": ["REG", "NUM_PROC", "IND_PROC"],
    "1900": [
        "REG", "CNPJ", "COD_MOD", "SER", "SUB_SER", "COD_SIT", "VL_TOT_REC",
        "QUANT_DOC", "CST_PIS", "CST_COFINS", "CFOP", "INF_COMPL", "COD_CTA"],
    "1990": ["REG", "QTD_LIN_1"],
    "9001": ["REG", "IND_MOV"],
    "9900": ["REG", "REG_BLC", "QTD_REG_BLC"],
    "9990": ["REG", "QTD_LIN_9"],
    "9999": ["REG", "QTD_LIN"],
    "A001": ["REG", "IND_MOV"],
    "A010": ["REG", "CNPJ"],
    "A100": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_SIT", "SER", "SUB",
        "NUM_DOC", "CHV_NFSE", "DT_DOC", "DT_EXE_SERV", "VL_DOC", "IND_PGTO",
        "VL_DESC", "VL_BC_PIS", "VL_PIS", "VL_BC_COFINS", "VL_COFINS",
        "VL_PIS_RET", "VL_COFINS_RET", "VL_ISS"],
    "A110": ["REG", "COD_INF", "TXT_COMPL"],
    "A111": ["REG", "NUM_PROC", "IND_PROC"],
    "A120": [
        "REG", "VL_TOT_SERV", "VL_BC_PIS", "VL_PIS_IMP", "DT_PAG_PIS",
        "VL_BC_COFINS", "VL_COFINS_IMP", "DT_PAG_COFINS", "LOC_EXE_SERV"],
    "A170": [
        "REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "VL_ITEM", "VL_DESC",
        "NAT_BC_CRED", "IND_ORIG_CRED", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
        "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS",
        "COD_CTA", "COD_CCUS"],
    "A990": ["REG", "QTD_LIN_A"],
    "C001": ["REG", "IND_MOV"],
    "C010": ["REG", "CNPJ", "IND_ESCRI"],
    "C100": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "NUM_DOC", "CHV_NFE", "DT_DOC", "DT_E_S", "VL_DOC",
        "IND_PGTO", "VL_DESC", "VL_ABAT_NT", "VL_MERC", "IND_FRT", "VL_FRT",
        "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
        "VL_ICMS_ST", "VL_IPI", "VL_PIS", "VL_COFINS", "VL_PIS_ST",
        "VL_COFINS_ST"],
    "C110": ["REG", "COD_INF", "TXT_COMPL"],
    "C111": ["REG", "NUM_PROC", "IND_PROC"],
    "C120": [
        "REG", "COD_DOC_IMP", "NUM_DOC_IMP", "VL_PIS_IMP", "VL_COFINS_IMP",
        "NUM_ACDRAW"],
    "C170": [
        "REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID",
        "VL_ITEM", "VL_DESC", "IND_MOV", "CST_ICMS", "CFOP", "COD_NAT",
        "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "ALIQ_ST",
        "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ", "VL_BC_IPI",
        "ALIQ_IPI", "VL_IPI", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
        "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "C175": [
        "REG", "CFOP", "VL_OPR", "VL_DESC", "CST_PIS", "VL_BC_PIS",
        "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA", "INFO_COMPL"],
    "C180": [
        "REG", "COD_MOD", "DT_DOC_INI", "DT_DOC_FIN", "COD_ITEM", "COD_NCM",
        "EX_IPI", "VL_TOT_ITEM"],
    "C181": [
        "REG", "CST_PIS", "CFOP", "VL_ITEM", "VL_DESC", "VL_BC_PIS",
        "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "COD_CTA"],
    "C185": [
        "REG", "CST_COFINS", "CFOP", "VL_ITEM", "VL_DESC", "VL_BC_COFINS",
        "ALIQ_COFINS", "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS",
        "COD_CTA"],
    "C188": ["REG", "NUM_PROC", "IND_PROC"],
    "C190": [
        "REG", "COD_MOD", "DT_REF_INI", "DT_REF_FIN", "COD_ITEM", "COD_NCM",
        "EX_IPI", "VL_TOT_ITEM"],
    "C191": [
        "REG", "CNPJ_CPF_PART", "CST_PIS", "CFOP", "VL_ITEM", "VL_DESC",
        "VL_BC_PIS", "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS",
        "COD_CTA"],
    "C195": [
        "REG", "CNPJ_CPF_PART", "CST_COFINS", "CFOP", "VL_ITEM", "VL_DESC",
        "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "C198": ["REG", "NUM_PROC", "IND_PROC"],
    "C199": [
        "REG", "COD_DOC_IMP", "NUM_DOC_IMP", "VL_PIS_IMP", "VL_COFINS_IMP",
        "NUM_ACDRAW"],
    "C380": [
        "REG", "COD_MOD", "DT_DOC_INI", "DT_DOC_FIN", "NUM_DOC_INI",
        "NUM_DOC_FIN", "VL_DOC", "VL_DOC_CANC"],
    "C381": [
        "REG", "CST_PIS", "COD_ITEM", "VL_ITEM", "VL_BC_PIS", "ALIQ_PIS",
        "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "COD_CTA"],
    "C385": [
        "REG", "CST_COFINS", "COD_ITEM", "VL_ITEM", "VL_BC_COFINS",
        "ALIQ_COFINS", "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS",
        "COD_CTA"],
    "C395": [
        "REG", "COD_MOD", "COD_PART", "SER", "SUB_SER", "NUM_DOC", "DT_DOC",
        "VL_DOC"],
    "C396": [
        "REG", "COD_ITEM", "VL_ITEM", "VL_DESC", "NAT_BC_CRED", "CST_PIS",
        "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "C400": ["REG", "COD_MOD", "ECF_MOD", "ECF_FAB", "ECF_CX"],
    "C405": ["REG", "DT_DOC", "CRO", "CRZ", "NUM_COO_FIN", "GT_FIN", "VL_BRT"],
    "C481": [
        "REG", "CST_PIS", "VL_ITEM", "VL_BC_PIS", "ALIQ_PIS", "QUANT_BC_PIS",
        "ALIQ_PIS_QUANT", "VL_PIS", "COD_ITEM", "COD_CTA"],
    "C485": [
        "REG", "CST_COFINS", "VL_ITEM", "VL_BC_COFINS", "ALIQ_COFINS",
        "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_ITEM",
        "COD_CTA"],
    "C489": ["REG", "NUM_PROC", "IND_PROC"],
    "C490": ["REG", "DT_DOC_INI", "DT_DOC_FIN", "COD_MOD"],
    "C491": [
        "REG", "COD_ITEM", "CST_PIS", "CFOP", "VL_ITEM", "VL_BC_PIS",
        "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "COD_CTA"],
    "C495": [
        "REG", "COD_ITEM", "CST_COFINS", "CFOP", "VL_ITEM", "VL_BC_COFINS",
        "ALIQ_COFINS", "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS",
        "COD_CTA"],
    "C499": ["REG", "NUM_PROC", "IND_PROC"],
    "C500": [
        "REG", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC",
        "DT_DOC", "DT_ENT", "VL_DOC", "VL_ICMS", "COD_INF", "VL_PIS",
        "VL_COFINS", "CHV_DOCE"],
    "C501": [
        "REG", "CST_PIS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_PIS", "ALIQ_PIS",
        "VL_PIS", "COD_CTA"],
    "C505": [
        "REG", "CST_COFINS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "C509": ["REG", "NUM_PROC", "IND_PROC"],
    "C600": [
        "REG", "COD_MOD", "COD_MUN", "SER", "SUB", "COD_CONS", "QTD_CONS",
        "QTD_CANC", "DT_DOC", "VL_DOC", "VL_DESC", "CONS", "VL_FORN",
        "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS", "VL_ICMS",
        "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_PIS", "VL_COFINS"],
    "C601": [
        "REG", "CST_PIS", "VL_ITEM", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "COD_CTA"],
    "C605": [
        "REG", "CST_COFINS", "VL_ITEM", "VL_BC_COFINS", "ALIQ_COFINS",
        "VL_COFINS", "COD_CTA"],
    "C609": ["REG", "NUM_PROC", "IND_PROC"],
    "C800": [
        "REG", "COD_MOD", "COD_SIT", "NUM_CFE", "DT_DOC", "VL_CFE", "VL_PIS",
        "VL_COFINS", "CNPJ_CPF", "NR_SAT", "CHV_CFE", "VL_DESC", "VL_MERC",
        "VL_OUT_DA", "VL_ICMS", "VL_PIS_ST", "VL_COFINS_ST"],
    "C810": [
        "REG", "CFOP", "VL_ITEM", "COD_ITEM", "CST_PIS", "VL_BC_PIS",
        "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS",
        "VL_COFINS", "COD_CTA"],
    "C820": [
        "REG", "CFOP", "VL_ITEM", "COD_ITEM", "CST_PIS", "QUANT_BC_PIS",
        "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "C830": ["REG", "NUM_PROC", "IND_PROC"],
    "C860": ["REG", "COD_MOD", "NR_SAT", "DT_DOC", "DOC_INI", "DOC_FIM"],
    "C870": [
        "REG", "COD_ITEM", "CFOP", "VL_ITEM", "VL_DESC", "CST_PIS",
        "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "C880": [
        "REG", "COD_ITEM", "CFOP", "VL_ITEM", "VL_DESC", "CST_PIS",
        "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS",
        "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "C890": ["REG", "NUM_PROC", "IND_PROC"],
    "C990": ["REG", "QTD_LIN_C"],
    "D001": ["REG", "IND_MOV"],
    "D010": ["REG", "CNPJ"],
    "D100": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT",
        "SER", "SUB", "NUM_DOC", "CHV_CTE", "DT_DOC", "DT_A_P", "TP_CTe",
        "CHV_CTE_REF", "VL_DOC", "VL_DESC", "IND_FRT", "VL_SERV",
        "VL_BC_ICMS", "VL_ICMS", "VL_NT", "COD_INF", "COD_CTA"],
    "D101": [
        "REG", "IND_NAT_FRT", "VL_ITEM", "CST_PIS", "NAT_BC_CRED",
        "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "COD_CTA"],
    "D105": [
        "REG", "IND_NAT_FRT", "VL_ITEM", "CST_COFINS", "NAT_BC_CRED",
        "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "D111": ["REG", "NUM_PROC", "IND_PROC"],
    "D200": [
        "REG", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC_INI",
        "NUM_DOC_FIN", "CFOP", "DT_REF", "VL_DOC", "VL_DESC"],
    "D201": [
        "REG", "CST_PIS", "VL_ITEM", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "COD_CTA"],
    "D205": [
        "REG", "CST_COFINS", "VL_ITEM", "VL_BC_COFINS", "ALIQ_COFINS",
        "VL_COFINS", "COD_CTA"],
    "D209": ["REG", "NUM_PROC", "IND_PROC"],
    "D300": [
        "REG", "COD_MOD", "SER", "SUB", "NUM_DOC_INI", "NUM_DOC_FIN", "CFOP",
        "DT_REF", "VL_DOC", "VL_DESC", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS",
        "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS",
        "COD_CTA"],
    "D309": ["REG", "NUM_PROC", "IND_PROC"],
    "D350": [
        "REG", "COD_MOD", "ECF_MOD", "ECF_FAB", "DT_DOC", "CRO", "CRZ",
        "NUM_COO_FIN", "GT_FIN", "VL_BRT", "CST_PIS", "VL_BC_PIS",
        "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "D359": ["REG", "NUM_PROC", "IND_PROC"],
    "D500": [
        "REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER",
        "SUB", "NUM_DOC", "DT_DOC", "DT_A_P", "VL_DOC", "VL_DESC", "VL_SERV",
        "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS", "VL_ICMS", "COD_INF",
        "VL_PIS", "VL_COFINS", "CHV_DOC_E"],
    "D501": [
        "REG", "CST_PIS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_PIS", "ALIQ_PIS",
        "VL_PIS", "COD_CTA"],
    "D505": [
        "REG", "CST_COFINS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "D509": ["REG", "NUM_PROC", "IND_PROC"],
    "D600": [
        "REG", "COD_MOD", "COD_MUN", "SER", "SUB", "IND_REC", "QTD_CONS",
        "DT_DOC_INI", "DT_DOC_FIN", "VL_DOC", "VL_DESC", "VL_SERV",
        "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS", "VL_ICMS", "VL_PIS",
        "VL_COFINS"],
    "D601": [
        "REG", "COD_CLASS", "VL_ITEM", "VL_DESC", "CST_PIS", "VL_BC_PIS",
        "ALIQ_PIS", "VL_PIS", "COD_CTA"],
    "D605": [
        "REG", "COD_CLASS", "VL_ITEM", "VL_DESC", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "D609": ["REG", "NUM_PROC", "IND_PROC"],
    "D990": ["REG", "QTD_LIN_D"],
    "F001": ["REG", "IND_MOV"],
    "F010": ["REG", "CNPJ"],
    "F100": [
        "REG", "IND_OPER", "COD_PART", "COD_ITEM", "DT_OPER", "VL_OPER",
        "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "NAT_BC_CRED",
        "IND_ORIG_CRED", "COD_CTA", "COD_CCUS", "DESC_DOC_OPER"],
    "F111": ["REG", "NUM_PROC", "IND_PROC"],
    "F120": [
        "REG", "NAT_BC_CRED", "IDENT_BEM_IMOB", "IND_ORIG_CRED",
        "IND_UTIL_BEM_IMOB", "VL_OPER_DEP", "PARC_OPER_NAO_BC_CRED",
        "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS",
        "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA", "COD_CCUS",
        "DESC_BEM_IMOB"],
    "F129": ["REG", "NUM_PROC", "IND_PROC"],
    "F130": [
        "REG", "NAT_BC_CRED", "IDENT_BEM_IMOB", "IND_ORIG_CRED",
        "IND_UTIL_BEM_IMOB", "MES_OPER_AQUIS", "VL_OPER_AQUIS",
        "PARC_OPER_NAO_BC_CRED", "VL_BC_CRED", "IND_NR_PARC", "CST_PIS",
        "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_CTA", "COD_CCUS", "DESC_BEM_IMOB"],
    "F139": ["REG", "NUM_PROC", "IND_PROC"],
    "F150": [
        "REG", "NAT_BC_CRED", "VL_TOT_EST", "EST_IMP", "VL_BC_EST",
        "VL_BC_MEN_EST", "CST_PIS", "ALIQ_PIS", "VL_CRED_PIS", "CST_COFINS",
        "ALIQ_COFINS", "VL_CRED_COFINS", "DESC_EST", "COD_CTA"],
    "F200": [
        "REG", "IND_OPER", "UNID_IMOB", "IDENT_EMP", "DESC_UNID_IMOB",
        "NUM_CONT", "CPF_CNPJ_ADQU", "DT_OPER", "VL_TOT_VEND", "VL_REC_ACUM",
        "VL_TOT_REC", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS",
        "PERC_REC_RECEB", "IND_NAT_EMP", "INF_COMP"],
    "F205": [
        "REG", "VL_CUS_INC_ACUM_ANT", "VL_CUS_INC_PER_ESC",
        "VL_CUS_INC_ACUM", "VL_EXC_BC_CUS_INC_ACUM", "VL_BC_CUS_INC",
        "CST_PIS", "ALIQ_PIS", "VL_CRED_PIS_ACUM", "VL_CRED_PIS_DESC_ANT",
        "VL_CRED_PIS_DESC", "VL_CRED_PIS_DESC_FUT", "CST_COFINS",
        "ALIQ_COFINS", "VL_CRED_COFINS_ACUM", "VL_CRED_COFINS_DESC_ANT",
        "VL_CRED_COFINS_DESC", "VL_CRED_COFINS_DESC_FUT"],
    "F210": [
        "REG", "VL_CUS_ORC", "VL_EXC", "VL_CUS_ORC_AJU", "VL_BC_CRED",
        "CST_PIS", "ALIQ_PIS", "VL_CRED_PIS_UTIL", "CST_COFINS",
        "ALIQ_COFINS", "VL_CRED_COFINS_UTIL"],
    "F211": ["REG", "NUM_PROC", "IND_PROC"],
    "F500": [
        "REG", "VL_REC_CAIXA", "CST_PIS", "VL_DESC_PIS", "VL_BC_PIS",
        "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_DESC_COFINS", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_MOD", "CFOP", "COD_CTA",
        "INFO_COMPL"],
    "F509": ["REG", "NUM_PROC", "IND_PROC"],
    "F510": [
        "REG", "VL_REC_CAIXA", "CST_PIS", "VL_DESC_PIS", "QUANT_BC_PIS",
        "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS", "VL_DESC_COFINS",
        "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_MOD",
        "CFOP", "COD_CTA", "INFO_COMPL"],
    "F519": ["REG", "NUM_PROC", "IND_PROC"],
    "F525": [
        "REG", "VL_REC", "IND_REC", "CNPJ_CPF", "NUM_DOC", "COD_ITEM",
        "VL_REC_DET", "CST_PIS", "CST_COFINS", "INFO_COMPL", "COD_CTA"],
    "F550": [
        "REG", "VL_REC_COMP", "CST_PIS", "VL_DESC_PIS", "VL_BC_PIS",
        "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_DESC_COFINS", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "COD_MOD", "CFOP", "COD_CTA",
        "INFO_COMPL"],
    "F559": ["REG", "NUM_PROC", "IND_PROC"],
    "F560": [
        "REG", "VL_REC_COMP", "CST_PIS", "VL_DESC_PIS", "QUANT_BC_PIS",
        "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS", "VL_DESC_COFINS",
        "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_MOD", "CFOP",
        "COD_CTA", "INFO_COMPL"],
    "F569": ["REG", "NUM_PROC", "IND_PROC"],
    "F600": [
        "REG", "IND_NAT_RET", "DT_RET", "VL_BC_RET", "VL_RET", "COD_REC",
        "IND_NAT_REC", "CNPJ", "VL_RET_PIS", "VL_RET_COFINS", "IND_DEC"],
    "F700": [
        "REG", "IND_ORI_DED", "IND_NAT_DED", "VL_DED_PIS", "VL_DED_COFINS",
        "VL_BC_OPER", "CNPJ", "INF_COMP"],
    "F800": [
        "REG", "IND_NAT_EVEN", "DT_EVEN", "CNPJ_SUCED", "PA_CONT_CRED",
        "COD_CRED", "VL_CRED_PIS", "VL_CRED_COFINS", "PER_CRED_CIS"],
    "F990": ["REG", "QTD_LIN_F"],
    "I001": ["REG", "IND_MOV"],
    "I010": ["REG", "CNPJ", "IND_ATIV", "INFO_COMPL"],
    "I100": [
        "REG", "VL_REC", "CST_PIS_COFINS", "VL_TOT_DED_GER",
        "VL_TOT_DED_ESP", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "VL_BC_COFINS",
        "ALIQ_COFINS", "VL_COFINS", "INFO_COMPL"],
    "I199": ["REG", "NUM_PROC", "IND_PROC"],
    "I200": [
        "REG", "NUM_CAMPO", "COD_DET", "DET_VALOR", "COD_CTA", "INFO_COMPL"],
    "I299": ["REG", "NUM_PROC", "IND_PROC"],
    "I300": ["REG", "COD_COMP", "DET_VALOR", "COD_CTA", "INFO_COMPL"],
    "I399": ["REG", "NUM_PROC", "IND_PROC"],
    "I990": ["REG", "QTD_LIN_I"],
    "M001": ["REG", "IND_MOV"],
    "M100": [
        "REG", "COD_CRED", "IND_CRED_ORI", "VL_BC_PIS", "ALIQ_PIS",
        "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_CRED", "VL_AJUS_ACRES",
        "VL_AJUS_REDUC", "VL_CRED_DIF", "VL_CRED_DISP", "IND_DESC_CRED",
        "VL_CRED_DESC", "SLD_CRED"],
    "M105": [
        "REG", "NAT_BC_CRED", "CST_PIS", "VL_BC_PIS_TOT", "VL_BC_PIS_CUM",
        "VL_BC_PIS_NC", "VL_BC_PIS", "QUANT_BC_PIS_TOT", "QUANT_BC_PIS",
        "DESC_CRED"],
    "M110": [
        "REG", "IND_AJ", "VL_AJ", "COD_AJ", "NUM_DOC", "DESCR_AJ", "DT_REF"],
    "M115": [
        "REG", "DET_VALOR_AJ", "CST_PIS", "DET_BC_CRED", "DET_ALIQ",
        "DT_OPER_AJ", "DESC_AJ", "COD_CTA", "INFO_COMPL"],
    "M200": [
        "REG", "VL_TOT_CONT_NC_PER", "VL_TOT_CRED_DESC",
        "VL_TOT_CRED_DESC_ANT", "VL_TOT_CONT_NC_DEV", "VL_RET_NC",
        "VL_OUT_DED_NC", "VL_CONT_NC_REC", "VL_TOT_CONT_CUM_PER",
        "VL_RET_CUM", "VL_OUT_DED_CUM", "VL_CONT_CUM_REC", "VL_TOT_CONT_REC"],
    "M205": ["REG", "NUM_CAMPO", "COD_REC", "VL_DEBITO"],
    "M210": [
        "REG", "COD_CONT", "VL_REC_BRT", "VL_BC_CONT",
        "VL_AJUS_ACRES_BC_PIS", "VL_AJUS_REDUC_BC_PIS", "VL_BC_CONT_AJUS",
        "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_CONT_APUR",
        "VL_AJUS_ACRES", "VL_AJUS_REDUC", "VL_CONT_DIFER",
        "VL_CONT_DIFER_ANT", "VL_CONT_PER"],
    "M211": [
        "REG", "IND_TIP_COOP", "VL_BC_CONT_ANT_EXC_COOP", "VL_EXC_COOP_GER",
        "VL_EXC_ESP_COOP", "VL_BC_CONT"],
    "M215": [
        "REG", "IND_AJ_BC", "VL_AJ_BC", "COD_AJ_BC", "NUM_DOC",
        "DESCR_AJ_BC", "DT_REF", "COD_CTA", "CNPJ", "INFO_COMPL"],
    "M220": [
        "REG", "IND_AJ", "VL_AJ", "COD_AJ", "NUM_DOC", "DESCR_AJ", "DT_REF"],
    "M225": [
        "REG", "DET_VALOR_AJ", "CST_PIS", "DET_BC_CRED", "DET_ALIQ",
        "DT_OPER_AJ", "DESC_AJ", "COD_CTA", "INFO_COMPL"],
    "M230": [
        "REG", "CNPJ", "VL_VEND", "VL_NAO_RECEB", "VL_CONT_DIF",
        "VL_CRED_DIF", "COD_CRED"],
    "M300": [
        "REG", "COD_CONT", "VL_CONT_APUR_DIFER", "NAT_CRED_DESC",
        "VL_CRED_DESC_DIFER", "VL_CONT_DIFER_ANT", "PER_APUR", "DT_RECEB"],
    "M350": [
        "REG", "VL_TOT_FOL", "VL_EXC_BC", "VL_TOT_BC", "ALIQ_PIS_FOL",
        "VL_TOT_CONT_FOL"],
    "M400": ["REG", "CST_PIS", "VL_TOT_REC", "COD_CTA", "DESC_COMPL"],
    "M410": ["REG", "NAT_REC", "VL_REC", "COD_CTA", "DESC_COMPL"],
    "M500": [
        "REG", "COD_CRED", "IND_CRED_ORI", "VL_BC_COFINS", "ALIQ_COFINS",
        "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_CRED", "VL_AJUS_ACRES",
        "VL_AJUS_REDUC", "VL_CRED_DIFER", "VL_CRED_DISP", "IND_DESC_CRED",
        "VL_CRED_DESC", "SLD_CRED"],
    "M505": [
        "REG", "NAT_BC_CRED", "CST_COFINS", "VL_BC_COFINS_TOT",
        "VL_BC_COFINS_CUM", "VL_BC_COFINS_NC", "VL_BC_COFINS",
        "QUANT_BC_COFINS_TOT", "QUANT_BC_COFINS", "DESC_CRED"],
    "M510": [
        "REG", "IND_AJ", "VL_AJ", "COD_AJ", "NUM_DOC", "DESCR_AJ", "DT_REF"],
    "M515": [
        "REG", "DET_VALOR_AJ", "CST_COFINS", "DET_BC_CRED", "DET_ALIQ",
        "DT_OPER_AJ", "DESC_AJ", "COD_CTA", "INFO_COMPL"],
    "M600": [
        "REG", "VL_TOT_CONT_NC_PER", "VL_TOT_CRED_DESC",
        "VL_TOT_CRED_DESC_ANT", "VL_TOT_CONT_NC_DEV", "VL_RET_NC",
        "VL_OUT_DED_NC", "VL_CONT_NC_REC", "VL_TOT_CONT_CUM_PER",
        "VL_RET_CUM", "VL_OUT_DED_CUM", "VL_CONT_CUM_REC", "VL_TOT_CONT_REC"],
    "M605": ["REG", "NUM_CAMPO", "COD_REC", "VL_DEBITO"],
    "M610": [
        "REG", "COD_CONT", "VL_REC_BRT", "VL_BC_CONT",
        "VL_AJUS_ACRES_BC_COFINS", "VL_AJUS_REDUC_BC_COFINS",
        "VL_BC_CONT_AJUS", "ALIQ_COFINS", "QUANT_BC_COFINS",
        "ALIQ_COFINS_QUANT", "VL_CONT_APUR", "VL_AJUS_ACRES",
        "VL_AJUS_REDUC", "VL_CONT_DIFER", "VL_CONT_DIFER_ANT", "VL_CONT_PER"],
    "M611": [
        "REG", "IND_TIP_COOP", "VL_BC_CONT_ANT_EXC_COOP", "VL_EXC_COOP_GER",
        "VL_EXC_ESP_COOP", "VL_BC_CONT"],
    "M615": [
        "REG", "IND_AJ_BC", "VL_AJ_BC", "COD_AJ_BC", "NUM_DOC",
        "DESCR_AJ_BC", "DT_REF", "COD_CTA", "CNPJ", "INFO_COMPL"],
    "M620": [
        "REG", "IND_AJ", "VL_AJ", "COD_AJ", "NUM_DOC", "DESCR_AJ", "DT_REF"],
    "M625": [
        "REG", "DET_VALOR_AJ", "CST_COFINS", "DET_BC_CRED", "DET_ALIQ",
        "DT_OPER_AJ", "DESC_AJ", "COD_CTA", "INFO_COMPL"],
    "M630": [
        "REG", "CNPJ", "VL_VEND", "VL_NAO_RECEB", "VL_CONT_DIF",
        "VL_CRED_DIF", "COD_CRED"],
    "M700": [
        "REG", "COD_CONT", "VL_CONT_APUR_DIFER", "NAT_CRED_DESC",
        "VL_CRED_DESC_DIFER", "VL_CONT_DIFER_ANT", "PER_APUR", "DT_RECEB"],
    "M800": ["REG", "CST_COFINS", "VL_TOT_REC", "COD_CTA", "DESC_COMPL"],
    "M810": ["REG", "NAT_REC", "VL_REC", "COD_CTA", "DESC_COMPL"],
    "M990": ["REG", "QTD_LIN_M"],
    "P001": ["REG", "IND_MOV"],
    "P010": ["REG", "CNPJ"],
    "P100": [
        "REG", "DT_INI", "DT_FIN", "VL_REC_TOT_EST", "COD_ATIV_ECON",
        "VL_REC_ATIV_ESTAB", "VL_EXC", "VL_BC_CONT", "02", "VL_CONT_APU",
        "COD_CTA", "INFO_COMPL"],
    "P110": ["REG", "NUM_CAMPO", "COD_DET", "DET_VALOR", "INF_COMPL"],
    "P199": ["REG", "NUM_PROC", "IND_PROC"],
    "P200": [
        "REG", "PER_REF", "VL_TOT_CONT_APU", "VL_TOT_AJ_REDUC",
        "VL_TOT_AJ_ACRES", "VL_TOT_CONT_DEV", "COD_REC"],
    "P210": [
        "REG", "IND_AJ", "VL_AJ", "COD_AJ", "NUM_DOC", "DESCR_AJ", "DT_REF"],
    "P990": ["REG", "QTD_LIN_P"],
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

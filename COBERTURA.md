# Cobertura das regras de validação

Gerado por `ferramentas/cobertura_guias.py` em 07/10/2026, a partir dos guias práticos (`recursos/`) e do descritor dos PVAs instalados.

* **Validações do guia**: parágrafos *Validação* dos campos mais a *Validação do Registro*, por registro.
* **Validadores do PVA**: regras compostas (`REGRA_…`) que o descritor declara para o registro; as declarativas (tipo, tamanho, obrigatoriedade, domínio, referência) o programa reproduz todas, pelo próprio descritor, e não entram na conta.
* **Reproduzidos**: validadores que o programa confere com as mesmas condições e tolerâncias do PVA (`dominio/regras_guia.py` e as verificações próprias do diagnóstico). O que falta continua sendo listado no diagnóstico como "só o PVA verifica".

## EFD ICMS/IPI

Guia prático 3.2.4 (30 de julho de 2026); descritor `descritor/escrituracao/ato020/estrutura001/v2/descritor.xml`.

| | Quantidade |
|---|---:|
| Validações escritas no guia | 939 |
| Validadores compostos do PVA | 739 |
| … reproduzidos pelo programa | 60 (8%) |

### Regras do guia implementadas

| Regra | Gravidade | Validadores do PVA |
|---|---|---|
| CFOP incompatível com a operação do documento | erro | `REGRA_CFOP_C100`, `REGRA_CFOP_NFCE`, `REGRA_CFOP_D190`, `REGRA_COERENCIA_CFOP_C170`, `REGRA_COERENCIA_CFOP` |
| Combinação CST/CFOP/alíquota sem par entre C170 e C190 | erro | `REGRA_CHAVE_EXISTE_NO_REGISTRO_ITEM_A8E1V1` |
| C190 diferente da soma dos itens (C170) | erro | `REGRA_VL_BC_ICMS_NO_REGISTRO_ITEM`, `REGRA_VL_ICMS_NO_REGISTRO_ITEM`, `REGRA_VL_BC_ICMS_ST_NO_REGISTRO_ITEM`, `REGRA_VL_ICMS_ST_NO_REGISTRO_ITEM` |
| Totais do documento diferentes dos analíticos (C190/D190) | erro | `REGRA_VL_BC_ICMS_ANALIT`, `REGRA_VL_ICMS_ANALIT`, `REGRA_VL_BC_ICMS_ST_ANALIT`, `REGRA_VL_ICMS_ST_ANALIT`, `REGRA_VL_IPI_C190` |
| VL_MERC abaixo da soma dos itens (C170) | erro | `REGRA_VL_MERC_C170` |
| Data depois do fim do período (C100, D100, H005) | erro | `REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_DOC_C100`, `REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_ES`, `REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_DOC`, `REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_A_P`, `REGRA_DATA_MENOR_IGUAL_DT_FIN_0000_DT_INV` |
| Período do 0000 fora do mesmo mês | erro | `REGRA_MES_ESCRITURACAO` |
| CNPJ/CPF inválido ou ausente (0000, 0100, 0150) | erro | `REGRA_DIGITO_CNPJ`, `REGRA_DIGITO_CPF`, `REGRA_VALIDA_CNPJ`, `REGRA_VALIDA_CPF`, `REGRA_CNPJ_EXCLUDENTE`, `REGRA_OBRIGATORIO_CPF_BRA_V2`, `REGRA_OBRIGATORIO_PARA_BRASIL_A10E3V4`, `REGRA_OBRIGATORIO_PARA_BRASIL_3002V1`, `REGRA_OBRIGATORIO_CPF_EXCLUDENTE_0000_CONTEUDO`, `REGRA_OBRIGATORIO_CPF_EXCLUDENTE_BRA_CNPJ`, `REGRA_OBRIGATORIO_CPF_EXCLUDENTE_BRA_CPF`, `REGRA_COD_MUN_EM_UF_V2`, `REGRA_COD_MUN_EM_UF` |
| Chave da NF-e/NFC-e ausente, inválida ou incoerente (C100) | erro | `REGRA_VALIDA_CHV_NFE_CTE`, `REGRA_VALIDA_CHV_NFE`, `REGRA_COMPARA_CNPJ_NFE_CTE_12001_V1`, `REGRA_COMPARA_NUM_DOC_NFE_CTE_C100_V4`, `REGRA_COMPARA_NUM_DOC_NFE`, `REGRA_COMPARA_UF_NFE_CTE_13001_V1`, `REGRA_COMPARA_CODIGO_MODELO`, `REGRA_VALIDA_SERIE_CHAVE`, `REGRA_OBRIGATORIO_CHV_NFE_CTE_A13E1V2`, `REGRA_OBRIGATORIO_CHVE_NFCE_A7E2V1`, `REGRA_OBRIGATORIO_CHV_NFE_1003_V2`, `REGRA_OBRIGATORIO_CHVE_NFCE`, `REGRA_COMPARA_MODELO_DOCUMENTO_NFE`, `REGRA_COMPARA_CNPJ_NFE_6001_V2`, `REGRA_COMPARA_CNPJ_NFE_PARTICIPANTE_12001_V1` |
| Contagem de linhas/registros (X990, 9900, 9999) | erro | `REGRA_QTD_REG_BLC_OBRIGATORIO`, `REGRA_QTD_LIN_ARQUIVO`, `REGRA_REGISTRO_DUPLICADO_9900` |
| Apuração do ICMS (E110) fora das expressões do guia | erro | `REGRA_VL_TOT_AJ_DEBITOS_E110`, `REGRA_VL_ESTORNOS_CRED_E110`, `REGRA_VL_TOT_AJ_CREDITOS_E110`, `REGRA_VL_ESTORNOS_DEB_E110`, `REGRA_SLD_DEVEDOR_E110`, `REGRA_SLD_CREDOR_E110`, `REGRA_ICMS_RECOLHER` |
| E116 diferente do ICMS a recolher mais o débito especial | erro | `REGRA_ICMS_REC_E116` |
| Inventário (H005/H010) incoerente | erro | `REGRA_VL_INV`, `REGRA_IND_PROP` |
| Item (C170) com quantidade zero | erro | `REGRA_MAIOR_ZERO_CONDICAO_COD_SIT` |

### Por registro

| Registro | Validações no guia | Validadores do PVA | Reproduzidos |
|---|---:|---:|---:|
| 0000 | 8 | 15 | 5 |
| 0005 | 0 | 2 | 0 |
| 0015 | 2 | 1 | 0 |
| 0100 | 3 | 4 | 2 |
| 0150 | 7 | 12 | 5 |
| 0175 | 2 | 6 | 0 |
| 0190 | 1 | 1 | 0 |
| 0200 | 6 | 10 | 1 |
| 0205 | 3 | 7 | 0 |
| 0206 | 1 | 0 | 0 |
| 0210 | 1 | 0 | 0 |
| 0220 | 3 | 4 | 1 |
| 0221 | 3 | 5 | 1 |
| 0300 | 2 | 6 | 0 |
| 0305 | 1 | 1 | 0 |
| 0400 | 2 | 1 | 0 |
| 0450 | 1 | 1 | 0 |
| 0460 | 1 | 1 | 0 |
| 0500 | 1 | 3 | 0 |
| 0600 | 2 | 4 | 0 |
| 0990 | 1 | 2 | 0 |
| 1001 | 1 | 0 | 0 |
| 1010 | 0 | 1 | 0 |
| 1100 | 5 | 11 | 0 |
| 1105 | 4 | 12 | 5 |
| 1110 | 6 | 12 | 6 |
| 1200 | 3 | 6 | 0 |
| 1210 | 3 | 4 | 1 |
| 1250 | 5 | 7 | 0 |
| 1255 | 5 | 5 | 0 |
| 1300 | 2 | 10 | 1 |
| 1310 | 1 | 4 | 0 |
| 1320 | 0 | 4 | 2 |
| 1360 | 1 | 3 | 0 |
| 1370 | 1 | 1 | 1 |
| 1390 | 1 | 2 | 0 |
| 1391 | 11 | 7 | 0 |
| 1400 | 3 | 6 | 0 |
| 1500 | 6 | 9 | 2 |
| 1510 | 6 | 8 | 3 |
| 1600 | 1 | 0 | 0 |
| 1601 | 2 | 3 | 0 |
| 1700 | 0 | 4 | 0 |
| 1710 | 0 | 3 | 0 |
| 1800 | 0 | 7 | 0 |
| 1900 | 1 | 2 | 0 |
| 1910 | 3 | 5 | 0 |
| 1920 | 11 | 13 | 0 |
| 1923 | 5 | 12 | 5 |
| 1926 | 3 | 6 | 0 |
| 1960 | 8 | 11 | 0 |
| 1970 | 5 | 8 | 0 |
| 1975 | 2 | 2 | 0 |
| 1980 | 6 | 10 | 0 |
| 1990 | 1 | 2 | 0 |
| 9900 | 1 | 1 | 1 |
| 9990 | 1 | 2 | 0 |
| 9999 | 1 | 2 | 2 |
| B001 | 1 | 1 | 0 |
| B020 | 14 | 23 | 7 |
| B025 | 4 | 2 | 0 |
| B030 | 9 | 10 | 0 |
| B035 | 3 | 2 | 0 |
| B350 | 7 | 4 | 0 |
| B420 | 7 | 5 | 0 |
| B440 | 5 | 4 | 1 |
| B460 | 1 | 1 | 0 |
| B470 | 11 | 18 | 0 |
| B500 | 2 | 2 | 0 |
| B510 | 3 | 4 | 1 |
| B990 | 0 | 2 | 0 |
| C001 | 1 | 0 | 0 |
| C100 | 15 | 42 | 21 |
| C101 | 0 | 1 | 0 |
| C105 | 1 | 0 | 0 |
| C110 | 2 | 1 | 0 |
| C111 | 1 | 0 | 0 |
| C112 | 3 | 4 | 0 |
| C113 | 7 | 18 | 6 |
| C114 | 4 | 3 | 0 |
| C115 | 8 | 4 | 2 |
| C116 | 2 | 10 | 1 |
| C120 | 1 | 0 | 0 |
| C140 | 1 | 1 | 0 |
| C141 | 2 | 3 | 0 |
| C160 | 1 | 1 | 1 |
| C165 | 3 | 2 | 2 |
| C170 | 11 | 19 | 5 |
| C171 | 2 | 1 | 0 |
| C172 | 0 | 1 | 0 |
| C173 | 2 | 3 | 0 |
| C174 | 1 | 0 | 0 |
| C175 | 3 | 2 | 1 |
| C176 | 16 | 19 | 4 |
| C180 | 3 | 4 | 1 |
| C181 | 7 | 14 | 2 |
| C185 | 8 | 10 | 2 |
| C186 | 4 | 9 | 2 |
| C190 | 9 | 14 | 8 |
| C191 | 0 | 5 | 0 |
| C195 | 1 | 1 | 0 |
| C197 | 2 | 4 | 1 |
| C300 | 5 | 9 | 1 |
| C310 | 1 | 1 | 0 |
| C320 | 2 | 7 | 0 |
| C321 | 2 | 3 | 2 |
| C330 | 5 | 7 | 1 |
| C350 | 1 | 5 | 1 |
| C370 | 4 | 6 | 2 |
| C380 | 6 | 8 | 1 |
| C390 | 2 | 4 | 0 |
| C400 | 1 | 0 | 0 |
| C405 | 6 | 8 | 1 |
| C420 | 5 | 6 | 0 |
| C425 | 4 | 6 | 2 |
| C430 | 6 | 8 | 1 |
| C460 | 5 | 6 | 0 |
| C465 | 2 | 2 | 0 |
| C470 | 6 | 7 | 2 |
| C480 | 6 | 8 | 1 |
| C490 | 5 | 9 | 1 |
| C495 | 5 | 0 | 0 |
| C500 | 21 | 40 | 10 |
| C510 | 7 | 8 | 3 |
| C590 | 9 | 11 | 1 |
| C591 | 2 | 3 | 0 |
| C595 | 1 | 1 | 0 |
| C597 | 3 | 3 | 1 |
| C600 | 9 | 13 | 5 |
| C601 | 1 | 1 | 0 |
| C610 | 7 | 8 | 2 |
| C690 | 9 | 8 | 5 |
| C700 | 5 | 7 | 0 |
| C790 | 5 | 5 | 0 |
| C791 | 1 | 0 | 0 |
| C800 | 5 | 15 | 2 |
| C810 | 1 | 6 | 2 |
| C815 | 5 | 8 | 1 |
| C850 | 7 | 4 | 0 |
| C855 | 1 | 1 | 0 |
| C857 | 1 | 3 | 1 |
| C860 | 5 | 5 | 1 |
| C870 | 4 | 6 | 2 |
| C880 | 5 | 7 | 1 |
| C890 | 4 | 4 | 0 |
| C895 | 1 | 1 | 0 |
| C897 | 1 | 3 | 1 |
| C990 | 2 | 2 | 0 |
| D001 | 1 | 0 | 0 |
| D100 | 12 | 39 | 11 |
| D101 | 0 | 1 | 0 |
| D110 | 2 | 1 | 1 |
| D120 | 2 | 0 | 0 |
| D130 | 6 | 5 | 1 |
| D140 | 3 | 3 | 1 |
| D150 | 2 | 2 | 0 |
| D160 | 4 | 4 | 0 |
| D161 | 6 | 3 | 0 |
| D162 | 3 | 5 | 1 |
| D170 | 4 | 3 | 1 |
| D180 | 10 | 9 | 0 |
| D190 | 5 | 6 | 1 |
| D195 | 1 | 1 | 0 |
| D197 | 2 | 4 | 1 |
| D300 | 11 | 15 | 1 |
| D301 | 1 | 1 | 0 |
| D310 | 2 | 0 | 0 |
| D350 | 1 | 0 | 0 |
| D355 | 6 | 6 | 1 |
| D365 | 5 | 6 | 0 |
| D370 | 1 | 0 | 0 |
| D390 | 3 | 5 | 0 |
| D400 | 5 | 6 | 2 |
| D410 | 6 | 9 | 0 |
| D411 | 1 | 2 | 0 |
| D420 | 1 | 0 | 0 |
| D500 | 6 | 13 | 3 |
| D510 | 10 | 8 | 3 |
| D530 | 3 | 4 | 0 |
| D590 | 6 | 11 | 5 |
| D600 | 5 | 5 | 1 |
| D610 | 5 | 6 | 2 |
| D690 | 9 | 11 | 5 |
| D695 | 3 | 5 | 0 |
| D696 | 5 | 6 | 0 |
| D697 | 1 | 0 | 0 |
| D700 | 0 | 21 | 4 |
| D730 | 5 | 4 | 0 |
| D735 | 1 | 1 | 0 |
| D737 | 2 | 2 | 1 |
| D750 | 4 | 9 | 0 |
| D760 | 5 | 4 | 0 |
| D990 | 1 | 2 | 0 |
| E001 | 1 | 1 | 0 |
| E100 | 3 | 5 | 0 |
| E110 | 13 | 16 | 10 |
| E111 | 0 | 3 | 0 |
| E113 | 5 | 12 | 5 |
| E116 | 3 | 7 | 0 |
| E200 | 3 | 6 | 0 |
| E210 | 12 | 14 | 0 |
| E220 | 1 | 2 | 0 |
| E240 | 5 | 11 | 5 |
| E250 | 5 | 7 | 0 |
| E300 | 3 | 7 | 0 |
| E310 | 19 | 21 | 0 |
| E311 | 1 | 2 | 0 |
| E313 | 5 | 12 | 5 |
| E316 | 4 | 6 | 0 |
| E500 | 2 | 5 | 0 |
| E510 | 2 | 0 | 0 |
| E520 | 6 | 8 | 0 |
| E530 | 1 | 3 | 0 |
| E531 | 7 | 13 | 6 |
| E990 | 1 | 2 | 0 |
| G001 | 1 | 0 | 0 |
| G110 | 5 | 12 | 0 |
| G125 | 8 | 23 | 0 |
| G126 | 1 | 8 | 0 |
| G130 | 2 | 10 | 5 |
| G140 | 3 | 4 | 2 |
| G990 | 0 | 2 | 0 |
| H001 | 1 | 0 | 0 |
| H005 | 3 | 9 | 2 |
| H010 | 4 | 9 | 4 |
| H020 | 0 | 1 | 0 |
| H030 | 0 | 2 | 0 |
| H990 | 1 | 2 | 0 |
| K001 | 1 | 0 | 0 |
| K010 | 1 | 0 | 0 |
| K100 | 2 | 5 | 0 |
| K200 | 4 | 7 | 2 |
| K210 | 5 | 8 | 1 |
| K215 | 2 | 4 | 1 |
| K220 | 6 | 7 | 1 |
| K230 | 6 | 11 | 1 |
| K235 | 3 | 7 | 1 |
| K250 | 2 | 5 | 1 |
| K255 | 3 | 6 | 1 |
| K260 | 6 | 8 | 1 |
| K265 | 2 | 4 | 1 |
| K270 | 6 | 8 | 1 |
| K275 | 5 | 6 | 1 |
| K280 | 7 | 9 | 2 |
| K290 | 4 | 8 | 0 |
| K291 | 3 | 3 | 1 |
| K292 | 2 | 4 | 1 |
| K300 | 1 | 2 | 0 |
| K301 | 2 | 3 | 1 |
| K302 | 2 | 4 | 1 |
| K990 | 1 | 2 | 0 |

## EFD Contribuições

Guia prático 1.35 (18/06/2021); descritor `descritor/escrituracao/estrutura7007/v1/descritor.xml`.

| | Quantidade |
|---|---:|
| Validações escritas no guia | 334 |
| Validadores compostos do PVA | 544 |
| … reproduzidos pelo programa | 32 (6%) |

### Regras do guia implementadas

| Regra | Gravidade | Validadores do PVA |
|---|---|---|
| CFOP incompatível com a operação do documento | erro | `REGRA_CFOP_C100`, `REGRA_CFOP_NFCE`, `REGRA_CFOP_D190`, `REGRA_COERENCIA_CFOP_C170`, `REGRA_COERENCIA_CFOP` |
| CFOP de NFC-e que não começa com 5 (C175) | erro | `REGRA_CFOP_NFCE_CFE` |
| Período do 0000 fora do mesmo mês | erro | `REGRA_MES_ESCRITURACAO` |
| CNPJ/CPF inválido ou ausente (0000, 0100, 0150) | erro | `REGRA_DIGITO_CNPJ`, `REGRA_DIGITO_CPF`, `REGRA_VALIDA_CNPJ`, `REGRA_VALIDA_CPF`, `REGRA_CNPJ_EXCLUDENTE`, `REGRA_OBRIGATORIO_CPF_BRA_V2`, `REGRA_OBRIGATORIO_PARA_BRASIL_A10E3V4`, `REGRA_OBRIGATORIO_PARA_BRASIL_3002V1`, `REGRA_OBRIGATORIO_CPF_EXCLUDENTE_0000_CONTEUDO`, `REGRA_OBRIGATORIO_CPF_EXCLUDENTE_BRA_CNPJ`, `REGRA_OBRIGATORIO_CPF_EXCLUDENTE_BRA_CPF`, `REGRA_COD_MUN_EM_UF_V2`, `REGRA_COD_MUN_EM_UF` |
| Chave da NF-e/NFC-e ausente, inválida ou incoerente (C100) | erro | `REGRA_VALIDA_CHV_NFE_CTE`, `REGRA_VALIDA_CHV_NFE`, `REGRA_COMPARA_CNPJ_NFE_CTE_12001_V1`, `REGRA_COMPARA_NUM_DOC_NFE_CTE_C100_V4`, `REGRA_COMPARA_NUM_DOC_NFE`, `REGRA_COMPARA_UF_NFE_CTE_13001_V1`, `REGRA_COMPARA_CODIGO_MODELO`, `REGRA_VALIDA_SERIE_CHAVE`, `REGRA_OBRIGATORIO_CHV_NFE_CTE_A13E1V2`, `REGRA_OBRIGATORIO_CHVE_NFCE_A7E2V1`, `REGRA_OBRIGATORIO_CHV_NFE_1003_V2`, `REGRA_OBRIGATORIO_CHVE_NFCE`, `REGRA_COMPARA_MODELO_DOCUMENTO_NFE`, `REGRA_COMPARA_CNPJ_NFE_6001_V2`, `REGRA_COMPARA_CNPJ_NFE_PARTICIPANTE_12001_V1` |
| Contagem de linhas/registros (X990, 9900, 9999) | erro | `REGRA_QTD_REG_BLC_OBRIGATORIO`, `REGRA_QTD_LIN_ARQUIVO`, `REGRA_REGISTRO_DUPLICADO_9900` |
| VL_PIS/VL_COFINS diferente de base × alíquota (mais de R$ 0,99) | aviso | `REGRA_VL_PIS`, `REGRA_VL_COFINS`, `REGRA_VL_QUANT_PIS`, `REGRA_VL_QUANT_COFINS` |
| Unidade (0190) com a descrição igual ao código | erro | — |

### Por registro

| Registro | Validações no guia | Validadores do PVA | Reproduzidos |
|---|---:|---:|---:|
| 0000 | 7 | 14 | 3 |
| 0035 | 1 | 4 | 1 |
| 0100 | 3 | 3 | 2 |
| 0110 | 1 | 3 | 0 |
| 0111 | 1 | 2 | 0 |
| 0120 | 0 | 8 | 0 |
| 0140 | 4 | 6 | 2 |
| 0150 | 7 | 11 | 5 |
| 0190 | 1 | 0 | 0 |
| 0200 | 2 | 6 | 1 |
| 0205 | 2 | 5 | 0 |
| 0206 | 1 | 0 | 0 |
| 0208 | 0 | 1 | 0 |
| 0500 | 1 | 2 | 1 |
| 0600 | 1 | 1 | 0 |
| 0900 | 6 | 16 | 0 |
| 0990 | 0 | 2 | 0 |
| 1001 | 1 | 0 | 0 |
| 1010 | 1 | 2 | 0 |
| 1011 | 4 | 19 | 1 |
| 1020 | 0 | 2 | 0 |
| 1050 | 0 | 6 | 1 |
| 1100 | 5 | 16 | 1 |
| 1101 | 4 | 0 | 0 |
| 1102 | 3 | 0 | 0 |
| 1200 | 2 | 0 | 0 |
| 1210 | 3 | 0 | 0 |
| 1220 | 1 | 0 | 0 |
| 1300 | 2 | 3 | 0 |
| 1500 | 5 | 16 | 1 |
| 1501 | 5 | 0 | 0 |
| 1502 | 3 | 0 | 0 |
| 1600 | 2 | 0 | 0 |
| 1700 | 2 | 3 | 0 |
| 1800 | 0 | 3 | 1 |
| 1809 | 0 | 1 | 0 |
| 1900 | 5 | 7 | 1 |
| 1990 | 1 | 2 | 0 |
| 9001 | 1 | 0 | 0 |
| 9900 | 1 | 0 | 0 |
| 9990 | 1 | 3 | 0 |
| 9999 | 1 | 3 | 2 |
| A001 | 1 | 0 | 0 |
| A010 | 1 | 3 | 0 |
| A100 | 6 | 14 | 2 |
| A110 | 1 | 0 | 0 |
| A111 | 0 | 1 | 0 |
| A120 | 0 | 8 | 0 |
| A170 | 3 | 37 | 4 |
| A990 | 1 | 2 | 0 |
| C001 | 1 | 0 | 0 |
| C010 | 1 | 4 | 0 |
| C100 | 8 | 35 | 11 |
| C110 | 1 | 0 | 0 |
| C111 | 0 | 1 | 0 |
| C120 | 0 | 1 | 0 |
| C170 | 10 | 62 | 9 |
| C175 | 6 | 30 | 6 |
| C180 | 1 | 13 | 1 |
| C181 | 3 | 15 | 3 |
| C185 | 3 | 15 | 3 |
| C188 | 0 | 1 | 0 |
| C190 | 1 | 10 | 1 |
| C191 | 3 | 24 | 3 |
| C195 | 3 | 24 | 3 |
| C198 | 0 | 1 | 0 |
| C199 | 0 | 1 | 0 |
| C380 | 2 | 6 | 0 |
| C381 | 3 | 17 | 4 |
| C385 | 3 | 16 | 3 |
| C395 | 2 | 5 | 1 |
| C396 | 3 | 21 | 4 |
| C405 | 5 | 6 | 0 |
| C481 | 4 | 16 | 4 |
| C485 | 4 | 15 | 3 |
| C489 | 0 | 1 | 0 |
| C490 | 2 | 7 | 0 |
| C491 | 5 | 16 | 3 |
| C495 | 5 | 16 | 3 |
| C499 | 0 | 1 | 0 |
| C500 | 7 | 14 | 1 |
| C501 | 1 | 12 | 2 |
| C505 | 1 | 12 | 2 |
| C509 | 0 | 1 | 0 |
| C600 | 6 | 6 | 0 |
| C601 | 0 | 9 | 2 |
| C605 | 0 | 9 | 2 |
| C609 | 0 | 1 | 0 |
| C800 | 4 | 0 | 0 |
| C810 | 6 | 0 | 0 |
| C820 | 6 | 0 | 0 |
| C860 | 4 | 6 | 0 |
| C870 | 6 | 15 | 4 |
| C880 | 6 | 10 | 4 |
| C890 | 0 | 1 | 0 |
| C990 | 1 | 2 | 0 |
| D001 | 1 | 0 | 0 |
| D010 | 1 | 3 | 0 |
| D100 | 8 | 22 | 1 |
| D101 | 1 | 12 | 2 |
| D105 | 1 | 12 | 2 |
| D111 | 0 | 1 | 0 |
| D200 | 2 | 5 | 0 |
| D201 | 0 | 10 | 2 |
| D205 | 0 | 10 | 2 |
| D209 | 0 | 1 | 0 |
| D300 | 2 | 24 | 3 |
| D309 | 0 | 1 | 0 |
| D350 | 5 | 31 | 5 |
| D359 | 0 | 1 | 0 |
| D500 | 5 | 16 | 1 |
| D501 | 1 | 11 | 2 |
| D505 | 1 | 11 | 2 |
| D509 | 0 | 1 | 0 |
| D600 | 2 | 8 | 0 |
| D601 | 1 | 10 | 2 |
| D605 | 1 | 10 | 2 |
| D609 | 0 | 1 | 0 |
| D990 | 1 | 2 | 0 |
| F001 | 1 | 0 | 0 |
| F010 | 1 | 4 | 0 |
| F100 | 3 | 47 | 1 |
| F111 | 0 | 1 | 0 |
| F120 | 4 | 19 | 3 |
| F129 | 0 | 1 | 0 |
| F130 | 5 | 22 | 1 |
| F139 | 0 | 1 | 0 |
| F150 | 1 | 8 | 1 |
| F200 | 0 | 20 | 2 |
| F205 | 3 | 11 | 0 |
| F210 | 2 | 8 | 0 |
| F211 | 0 | 1 | 0 |
| F500 | 5 | 12 | 3 |
| F509 | 0 | 1 | 0 |
| F510 | 5 | 8 | 3 |
| F519 | 0 | 1 | 0 |
| F525 | 0 | 10 | 1 |
| F550 | 5 | 14 | 3 |
| F559 | 0 | 1 | 0 |
| F560 | 5 | 8 | 3 |
| F569 | 0 | 1 | 0 |
| F600 | 1 | 6 | 1 |
| F700 | 0 | 2 | 1 |
| F800 | 0 | 6 | 1 |
| F990 | 1 | 2 | 0 |
| I001 | 1 | 0 | 0 |
| I010 | 1 | 3 | 0 |
| I100 | 3 | 20 | 0 |
| I199 | 0 | 1 | 0 |
| I200 | 0 | 5 | 1 |
| I299 | 0 | 1 | 0 |
| I300 | 0 | 4 | 1 |
| I399 | 0 | 1 | 0 |
| I990 | 0 | 2 | 0 |
| M001 | 1 | 0 | 0 |
| M100 | 1 | 20 | 0 |
| M105 | 1 | 21 | 0 |
| M110 | 0 | 2 | 0 |
| M115 | 0 | 3 | 1 |
| M200 | 2 | 23 | 0 |
| M205 | 0 | 1 | 0 |
| M210 | 3 | 20 | 2 |
| M211 | 1 | 2 | 0 |
| M215 | 0 | 8 | 1 |
| M220 | 0 | 2 | 0 |
| M225 | 0 | 3 | 1 |
| M230 | 0 | 1 | 1 |
| M300 | 1 | 5 | 0 |
| M350 | 0 | 2 | 0 |
| M400 | 0 | 6 | 1 |
| M410 | 0 | 3 | 1 |
| M500 | 1 | 18 | 0 |
| M505 | 1 | 20 | 0 |
| M510 | 0 | 2 | 0 |
| M515 | 0 | 3 | 1 |
| M600 | 2 | 23 | 0 |
| M605 | 0 | 1 | 0 |
| M610 | 3 | 19 | 2 |
| M611 | 1 | 2 | 0 |
| M615 | 0 | 8 | 1 |
| M620 | 0 | 2 | 0 |
| M625 | 0 | 3 | 1 |
| M630 | 0 | 1 | 1 |
| M700 | 0 | 5 | 0 |
| M800 | 0 | 6 | 1 |
| M810 | 0 | 2 | 1 |
| M990 | 1 | 2 | 0 |
| P001 | 1 | 0 | 0 |
| P010 | 1 | 0 | 0 |
| P100 | 1 | 0 | 0 |
| P990 | 1 | 2 | 0 |

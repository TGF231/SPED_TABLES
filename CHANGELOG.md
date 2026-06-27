# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.3.0] - 2026-06-26

### Adicionado
- **Correlação de CFOP nas entradas (NF-e 55)**: a conferência passou a checar
  se o CFOP de saída do fornecedor (5xxx/6xxx, no XML) corresponde a um CFOP de
  entrada válido no C170 (1xxx/2xxx). Ex.: um item com **5403** na compra
  escriturado como **1102** é apontado, com a sugestão de que deveria ser
  **1401** ou **1403**.
- **Tabela de correlações editável** (Ferramentas → Correlações de CFOP): lista
  de CFOP de saída → CFOPs de entrada válidos, editável na interface e
  persistida em `correlacoes_cfop.json`. Acompanha um conjunto padrão (96 CFOPs)
  que pode ser ajustado e restaurado.

## [0.2.0] - 2026-06-26

### Adicionado
- **Página inicial (Resumo)**: aba inicial com o cabeçalho do arquivo (registro
  0000: nome, CNPJ, IE, UF, período DT_INI–DT_FIN), data de modificação do
  arquivo em disco, layout detectado e contagem de registros (total e por bloco).
- **Revisão de erros**: ferramenta extensível que gera relatórios de
  inconsistências. Regras nesta versão: (1) registros com número de campos
  divergente do layout; (2) registros C190 com CST x20/x70 e VL_RED_BC zerado.
  Clicar numa linha do relatório navega até o registro exato.
- **Pesquisa em todos os blocos**: o campo de busca passou a aparecer em
  qualquer grade com registros (ex.: 0200, H010), pesquisando em todas as
  colunas. Em grades de documento continua focando o número do documento.
- **Versionamento**: arquivo `version.py` e este CHANGELOG; a versão aparece no
  título da janela e na página inicial.
- **Layout em `.ui`**: a janela principal pode ser editada no Qt Designer
  (`sped_editor.ui`); o aplicativo carrega o arquivo quando presente.

## [0.1.3] - anterior

### Adicionado
- Importação de XMLs (NFC-e 65) e consolidação de C175 por mod+série+nNF.
- Recálculo do bloco M (apuração PIS/COFINS) conforme o regime (0110).
- Conferência de entradas modelo 55 (item XML ↔ C170 por mod+série+nNF+nItem).
- Motor de vínculo genérico reaproveitável (`xml_fiscal.vincular`).
- Edição estilo planilha (setas, seleção múltipla, copiar/colar), filtros de
  operação/modelo, recálculo de C190 e recálculo de totais (C990/9900).

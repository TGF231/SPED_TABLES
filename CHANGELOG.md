# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.7.0] - 2026-07-02

### Corrigido
- **Recálculo do bloco M gerava erros de validação no PVA.** Os registros
  M210/M610 eram reinseridos logo após o M200/M600, ficando **à frente** do
  M205/M605 e violando a ordem do leiaute (M200 → M205 → M210). Isso causava os
  erros de "organização hierárquica" (esperado M211/M611 no lugar do M205/M605)
  e as divergências de contagem (QTD_LIN_M e QTD_LIN). Agora os detalhes são
  ancorados **após** o M205/M605, corrigindo inclusive arquivos que já tenham
  sido gravados fora de ordem. O formato dos campos zerados também passou a
  seguir o do arquivo original ("0" em vez de "0,00").

### Adicionado
- **Reordenação de abas por arrasto**, com a ordem preservada durante a sessão
  (não persiste após fechar). Vale para as abas de bloco e para as sub-abas de
  tipo de registro (inclusive as de registros-filho no detalhe). Cada aba é
  identificada por um id estável, então a ordem escolhida sobrevive às
  remontagens das grades.

## [0.6.0] - 2026-06-27

### Alterado
- Nome do aplicativo: **Editor SPED** → **SPED Tables** (melhor representa o
  foco em edição tabular de arquivos SPED).
- Ícone visual adicionado (icon.ico) exibido na barra de título da janela.

### Versão
Versão salto de 0.4.2 para 0.6.0 refletindo o amadurecimento da ferramenta
(suporte saídas/entradas, conferência CFOP, revisões, etc.).

## [0.4.2] - 2026-06-27

### Alterado
- **Trocar alíquotas de PIS/COFINS** agora atua também nos **documentos de
  entrada** (registros C170 de C100 com IND_OPER=0), recalculando o crédito com
  a alíquota do comprador. O diálogo ganhou o seletor de **escopo** (Saídas
  C175 / Entradas C170 / Ambos) e sugere a alíquota predominante de cada escopo
  (as entradas costumam ter alíquota de crédito diferente das saídas).

## [0.4.1] - 2026-06-27

### Adicionado
- **Revisão: 0200 não utilizados / duplicados** — nova regra em `revisao.py`
  que aponta registros 0200 cujo COD_ITEM não é referenciado por nenhum outro
  registro (C170, H010, etc.) e os 0200 com COD_ITEM duplicado. As referências
  são coletadas de qualquer registro que possua o campo COD_ITEM (não só
  C170/H010), evitando falsos positivos. Clicar no relatório navega até o 0200.

## [0.4.0] - 2026-06-27

### Adicionado
- **Trocar alíquotas de PIS/COFINS (C175)**: nova ferramenta que aplica novas
  alíquotas de PIS e/ou COFINS aos registros C175 e recalcula VL_PIS/VL_COFINS
  (base × alíquota), atualizando os totais dos C100. Sugere as alíquotas atuais
  predominantes e permite restringir aos registros tributados.

### Alterado
- As ferramentas passaram a ficar num botão **Ferramentas** na barra de
  ferramentas (ao lado de *Salvar como*).
- A **barra de menus** foi removida (redundante com a barra de ferramentas).
- A mensagem ao salvar agora informa apenas o caminho do arquivo salvo.

### Removido
- Ação manual **Recalcular totais (C990/9900)**: a recontagem (X990, 9900,
  9990, 9999) já é feita automaticamente ao salvar.

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

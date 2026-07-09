# Changelog

## [0.12.1] - 2026-07-03

### Alterado
- **Filtros do Modo Relatório agora aceitam múltiplos valores** em todos os
  campos, separados por ponto e vírgula (";"). Ex.: CFOP "1101;1102", CST
  "000;020;060", Alíq. PIS "1,65;0,65". Usa-se ";" (e não vírgula) para não
  conflitar com a vírgula decimal das alíquotas. O filtro de NCM continua por
  prefixo, agora aceitando vários (ex.: "02;2202").

## [0.12.0] - 2026-07-03

### Alterado
- **Aba Resumo reformulada.** A contagem de registros deixou de ser uma tabela e
  passou a ser uma **lista simples** agrupada por bloco. A aba agora traz também
  a **apuração do período**:
  - *EFD ICMS/IPI:* consolidação das **entradas** e das **saídas** por
    CST/CFOP/alíquota (só os totais, sem listar documentos), e a **apuração do
    ICMS de operações próprias (E110)** — débitos, créditos, saldo credor
    anterior, ICMS a recolher e saldo a transportar.
  - *EFD Contribuições:* **consolidação por CST** de PIS/COFINS, separando
    receitas/saídas, aquisições/custos e outras operações (valor do item, base
    de PIS e base de COFINS).
- A **conferência de entradas (NF-e 55 × C170)** passou a verificar também o
  **CST de ICMS** e os **valores de ICMS** (base e imposto) — antes só conferia
  VL_ITEM/VL_DESC e a correlação de CFOP. CST e valores de ICMS não podem
  divergir entre o XML e o SPED.

## [0.11.0] - 2026-07-03

### Adicionado
- **Conferir C190 (ICMS) com XMLs** (Ferramentas, EFD ICMS/IPI): compara os
  registros C190 com os XMLs, para entradas e saídas. Como o CFOP do XML é o de
  saída do fornecedor (diferente do CFOP de entrada escriturado), os itens do
  XML são agrupados pela **classificação do C170** (CST/CFOP/alíquota de ICMS),
  casada por **nItem** — assim os grupos do C190 (ex.: CFOP 1101 e 1102, quando o
  XML só traz 5102) são reconstruídos sem perder a correlação de cada item.
  Compara VL_OPR, VL_BC_ICMS e VL_ICMS por grupo (com o mesmo rateio de despesas
  acessórias do recálculo do C190) e exporta as divergências em CSV.
- O parser de XML passou a extrair os campos de **ICMS por item** (CST, base,
  alíquota, valor, ST e IPI), além de PIS/COFINS.

## [0.10.1] - 2026-07-03

### Corrigido
- **VL_RED_BC não era calculado no recálculo do C190.** Nos grupos com CST de
  ICMS terminado em **20** ou **70** (redução de base), o campo ficava zerado
  mesmo quando o C170 não trazia o percentual/valor de redução. Agora é obtido
  diretamente por **VL_OPR − VL_BC_ICMS** (nunca negativo).

## [0.10.0] - 2026-07-03

### Corrigido
- **Reposicionamento de abas não levava o conteúdo junto.** O gerenciador de
  ordem de abas desconectava o sinal `tabMoved` por completo, removendo também o
  slot interno do `QTabWidget` que sincroniza o conteúdo ao mover a aba —
  por isso o rótulo mudava de lugar mas a aba mostrava o conteúdo antigo. Agora o
  memorizador é ligado uma única vez, sem afetar a sincronização nativa.

### Adicionado
- **Soma da seleção (estilo Excel):** ao selecionar várias células numéricas
  numa grade, a barra de status mostra **Soma**, **Média** e **Contagem**.
- **Modo Relatório editável:** as células das colunas próprias do registro-fonte
  (C170/C175/C190) podem ser editadas diretamente na tabela do relatório — como
  uma *query* editável —, gravando a alteração no registro correspondente do
  SPED. Colunas derivadas (produto, dados do documento, valores calculados)
  ficam somente-leitura (fundo acinzentado). A edição respeita a ordenação por
  coluna.

## [0.9.1] - 2026-07-02

### Corrigido
- **Rateio de despesas acessórias no recálculo do C190.** Frete/seguro/outras
  despesas do C100 eram rateados arredondando o quinhão de cada item
  isoladamente, e a soma dos quinhões não fechava com o total (sobra/falta de
  centavos — ex.: 1,50 de VL_OUT_DA distribuído como 1,52). Agora o rateio usa a
  diferença de acumulados arredondados, de modo que a soma dos VL_OPR do C190
  bate exatamente com o total dos itens mais as despesas acessórias.

## [0.9.0] - 2026-07-02

### Adicionado
- **Verificar CST por NCM (tabelas RFB)** (Ferramentas): classifica cada item
  **C170** pelo NCM usando as tabelas oficiais do EFD-Contribuições — produtos de
  **alíquota zero** (CST 06) e **monofásicos** — e aponta CST de PIS/COFINS
  incoerentes, separando **entradas** e **saídas**. Ex.: entrada de produto
  monofásico (bebidas) escriturada com CST 50 (crédito indevido) em vez de 73/98.
  - As tabelas são localizadas automaticamente na pasta de recursos do PVA pela
    **maior versão** (nomes tipo `…$PROD_ALIQ_ZERO$48$166`), com opção de
    **informar o caminho de cada arquivo** diretamente caso o padrão mude.
  - Respeita a **vigência** (DT_INI/DT_FIM) na data de referência (por padrão, a
    DT_FIN do arquivo) e as exceções (NCM_EX). O **gênero** vem dos 2 primeiros
    dígitos do NCM. Opcionalmente valida contra a **Tabela NCM Vigente (XLSX)**
    do Siscomex. Resultado navegável e exportável em CSV. Config persistida em
    `config_tabelas_rfb.json`.
- Novo módulo `tabelas_rfb.py`; dependência opcional `openpyxl` (para o XLSX).

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.8.3] - 2026-07-02

### Alterado
- **Trocar alíquotas de PIS/COFINS** ampliada:
  - O escopo **Saídas** agora inclui, além do C175, os **C170 de documentos de
    saída** (débito detalhado por item) — antes só o C175 era corrigido.
  - Novo escopo **Todos os itens (C170 e C175)**, para corrigir alíquotas em
    qualquer registro, independentemente de entrada/saída.
  - Novo filtro opcional **“Trocar apenas onde a alíquota atual for”** (PIS e
    COFINS), para corrigir somente uma alíquota preenchida errada sem tocar nas
    demais.

## [0.8.2] - 2026-07-02

### Adicionado
- **Alterar datas de emissão/saída (C100)** (Ferramentas): filtra documentos por
  um intervalo de datas — avaliado sobre DT_E_S ou DT_DOC —, além de tipo de
  movimento e modelo, e altera a **data de emissão (DT_DOC)**, de **entrada/saída
  (DT_E_S)** ou ambas, seja para uma **data específica** ou **deslocando N dias**
  (aceita negativos).

### Corrigido
- O **filtro por modelo** de uma rotina externa de correção de datas estava
  invertido (marcar um modelo processava apenas ele, ao contrário do rótulo).
  Na versão integrada a semântica é explícita: *“Somente modelos”* aplica a
  alteração apenas aos modelos informados; em branco, a todos.

## [0.8.1] - 2026-07-02

### Adicionado
- **Modo Relatório com três fontes**, selecionáveis por um combo:
  **Itens (C170)**, **PIS/COFINS consolidado (C175)** e **ICMS consolidado
  (C190)**. Os relatórios de C175 e C190 cobrem documentos sem detalhamento de
  item — como a **NFC-e (modelo 65)** —, em que não há C170. Cada fonte mostra
  as colunas próprias do registro e habilita apenas os filtros aplicáveis
  (ex.: CST/alíquota de ICMS no C190; CST/alíquotas de PIS e COFINS no C175).
  Acrescentado o filtro de alíquota de ICMS.

## [0.8.0] - 2026-07-02

### Adicionado
- **Dois modos de visualização** no topo da janela: **Modo Tabela** (a edição
  mestre-detalhe por bloco, como antes) e **Modo Relatório**.
- **Modo Relatório**: visão achatada dos itens (uma linha por C170, com dados do
  C100 e do produto 0200), com filtros e colunas espelhando o relatório usado no
  banco do ERP — data, tipo (E/S), modelo, nº da nota, código do produto, item,
  NCM, CFOP, CST de ICMS/PIS/COFINS/IPI e alíquotas de PIS/COFINS. Permite
  **exportar em CSV** para comparar com o resultado do script SQL.

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

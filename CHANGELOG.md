# Changelog

## [0.44.0] - 2026-09-23

### Adicionado
- **Abrir no PVA** — em Ferramentas → Gerais e como botão na confirmação de
  salvamento. Abre o PVA do leiaute (ou traz para a frente o que já estiver
  aberto), dispara a importação e cola o caminho do arquivo salvo.
- `pva.py`: localização da instalação, janela principal por título, foco,
  área de transferência e envio de teclas — Win32 puro, sem dependência de
  GUI e inerte fora do Windows.

### Notas — por que assim
- **Não existe linha de comando para importar.** Os dois PVAs aceitam apenas
  `-buildVersion` e `-atualizarTabelas`. O caminho usado é o acelerador
  **Ctrl+I** que cada um declara no `ppgdmenubar.xml` do próprio `.jar`, com o
  caminho indo pela área de transferência até o campo "Nome do arquivo:" do
  seletor.
- **Nenhuma tecla é enviada sem conferir antes qual janela está em primeiro
  plano.** Falhando qualquer etapa, o caminho fica na área de transferência e
  a mensagem diz o que falta: Ctrl+I, Ctrl+V, Enter.
- A espera roda **fora da thread da interface** — PVA frio sobe um MySQL junto
  e pode passar de um minuto.
- Conferido ponta a ponta no PVA do EFD ICMS/IPI instalado: com o PVA aberto,
  do clique ao caminho dentro do campo levou **1 segundo**; partindo do zero,
  a janela apareceu em 6 s e o resto seguiu igual.

## [0.43.0] - 2026-09-22

As **sete mensagens restantes** do banco do PVA, implementadas. Com as duas da
0.42.0, o programa agora reproduz as 13 mensagens distintas que o validador
oficial gravou nas 11 validações feitas nesta máquina.

O método mudou de patamar: a tabela `master/escrituracao` liga cada banco ao
**arquivo que o gerou**, então dá para rodar a regra nova contra o mesmo
arquivo que o PVA validou e comparar o número exato. Duas regras fecharam
assim, sem reconstrução: **20/20** no CFOP e **25/25** no CST.

### Adicionado
- **CST 02 sem alíquota (C170, ICMS)** — `MSG_VALIDA_CST_ALIQ_ICMS_C170_CST_FINAL_2`.
  Desde 01/04/2023 o CST terminado em 02 é tributação monofásica de
  combustível e exige `ALIQ_ICMS > 0`. Na prática é o **CSOSN 102/202 do
  fornecedor do Simples** copiado na entrada — e o PVA acusa do mesmo jeito.
  25 itens num arquivo real, os mesmos 25 do validador.
- **Crédito em CFOP que não dá direito** — `MSG_COMPATIBILIDADE_CFOP_CRED`,
  como rotina de PIS/COFINS, usando a tabela 4.3.7 do PVA (89 CFOP de entrada
  com crédito). 20 ocorrências num arquivo real, todas em CFOP 1910
  (bonificação, doação, brinde) e 1949: mercadoria que entrou sem custo não
  gera crédito. Tem correção — troca o CST e zera base, alíquota e valor.
- **M210/M610 x documentos**, nos dois campos que o PVA confere:
  `VL_REC_BRT` (`MSG_VL_REC_BRT`) e `VL_BC_CONT`
  (`MSG_VL_BC_CONT_IND_NAT_PJ`). Num arquivo real a apuração trazia
  R$ 262.591,48 onde os documentos somavam R$ 431,64. Corrige com
  *Recalcular bloco M*, que usa exatamente o mesmo somatório.
- **M400/M800 sem lastro** — `MSG_M400_NAO_DEVE_EXISTIR`: receita isenta
  declarada num CST que nenhum documento usa.
- **IND_EMIT de terceiro em documento de saída** — `MSG_IND_EMIT`. Quando há
  chave de NF-e, o CNPJ dentro dela diz **qual dos dois campos** está errado:
  chave do próprio contribuinte, corrige-se o `IND_EMIT`; chave de outro, o
  documento é de entrada e o errado é o `IND_OPER`. Por isso a regra aponta e
  não corrige — os dois consertos levam o arquivo para lados opostos.
- **Registro 0900 ausente fora do prazo** — `MSG_PREENCHIMENTO_0900`, com a
  data limite saindo da tabela de prazos do próprio PVA.

### Corrigido
- **186 falsos positivos de CST do ICMS num único arquivo.** O domínio do
  campo vinha do produto cartesiano `SIT_TRIB_ICMS_A` × `SIT_TRIB_ICMS_B`,
  cuja tabela B é de 2009. O PVA publica também a tabela **composta**
  `SIT_TRIB_ICMS` (versão 4, 140 códigos com vigência), que traz os CSOSN do
  Simples (101, 102, 201, 202, 900) e os códigos de tributação monofásica de
  combustíveis de 2023 (final 02, 15, 53 e 61). Passou a valer ela, com o par
  A × B como reserva; o domínio embutido (usado quando o PVA não está
  instalado) foi alinhado. No arquivo real: 186 → 0, exatamente como o
  validador oficial.

### Notas
- Conferência do bloco M: o somatório é **o mesmo** de `recalcular_bloco_m` —
  verificação e correção que discordam produzem um erro que o botão de
  corrigir não conserta. Quando o arquivo tem receita fora do bloco C (A170,
  D201, F100...), a conferência se declara **parcial** e vira aviso, em vez de
  acusar diferença que o arquivo não tem.
- Validação: 3 regras conferidas contra a contagem exata do PVA, 1 contra um
  caso real de entrega fora do prazo e 3 por caso reconstruído a partir do
  valor encontrado/esperado que o banco registrou. Nos arquivos que o PVA
  aprovou, as sete regras devolvem zero.

## [0.42.0] - 2026-09-22

Duas regras tiradas do **banco do próprio PVA**: cada escrituração validada
deixa uma tabela `inconsistencia` com o erro, o campo, o valor encontrado e o
valor esperado. Nos bancos desta máquina havia 13 mensagens distintas em 11
validações — 2.876 ocorrências —, e duas delas o programa ainda não detectava.

### Adicionado
- **Chave duplicada no mesmo registro-pai** (`MSG_CHAVE_EXISTE_NO_REGISTRO_ITEM`
  — 130 ocorrências nos bancos). A regra é **genérica**: a chave vem do
  descritor do PVA, então vale para os 154 registros que a declaram no EFD
  ICMS/IPI e os 145 no Contribuições. No C190 a chave é CST + CFOP + alíquota.
- **Data de saída fora do período** (`MSG_PERIODO_INCOMPATIVEL_SAIDA` — 132
  ocorrências). Só as saídas são cobradas: numa entrada, documento anterior ao
  período é escrituração extemporânea legítima.
- **O recálculo do C190 passou a cobrir a duplicidade**, não só a redução de
  base zerada — consolidar agrupa pela mesma chave que o PVA cobra. A ação
  virou *Recalcular C190 (analítico) em massa*.
- No diagnóstico, os dois achados já vêm com o módulo que corrige: chave
  duplicada no C190 → *Recalcular C190*; data fora do período → *Alterar datas
  emissão/saída*.

### Notas
- Os arquivos de teste desta máquina não continham as ocorrências (vieram de
  outros períodos), então a validação foi por **caso reconstruído**: plantando
  um C190 repetido e três saídas com `DT_E_S 28052026`, as regras acusaram
  exatamente 1 e 3, e o recálculo do documento levou o C190 de 3 para 2
  registros, zerando a duplicidade.
- A tabela `inconsistencia` **não** guarda as regras, só o resultado delas. Mas
  valor encontrado + valor esperado revelam a condição sem decompilar, e os
  casos servem de gabarito para conferir qualquer reimplementação.

## [0.41.0] - 2026-09-22

### Adicionado
- **`diagnostico.py` e o painel *Diagnóstico do arquivo*, executado ao abrir
  o SPED.** Passa o arquivo pelas camadas de verificação do PVA e agrupa os
  problemas **pelo módulo que os corrige**, com o botão que abre a função
  certa em cada linha. Arquivo limpo não interrompe: só avisa na barra de
  status. Também disponível em Ferramentas → Gerais.
- Camadas novas, todas declaradas pelo descritor do PVA: **quantidade de
  campos** do registro, **obrigatoriedade de campo**, **referências entre
  registros** nos dois sentidos (código citado que não existe no cadastro, e
  cadastro que ninguém cita) e **bloco aberto sem encerramento**.
- O painel lista **quantas regras compostas** o PVA aplica aos registros do
  arquivo e que este programa não reproduz (208 no ICMS/IPI, 203 no
  Contribuições), com alguns nomes. Sem isso, "nenhum erro" pareceria
  aprovação.

### Notas — os limites, ditos de frente
- As ~1.400 regras compostas do PVA são implementadas **em Java sobre o banco
  embutido**; o bytecode não carrega as condições. Reimplementá-las por
  adivinhação produziria divergência silenciosa com o validador oficial, então
  elas são listadas, não simuladas.
- **Obrigatoriedade condicional não está no descritor**: o campo é declarado
  obrigatório e uma regra dispensa em certos casos. As exceções que dá para
  afirmar ficam em `DISPENSAS`, nominalmente. A primeira é `C100.COD_PART`,
  dispensado na NFC-e — sem ela, o arquivo de supermercado acusava **4.377**
  campos obrigatórios em branco que o PVA aceita, e os **5** casos reais
  (modelo 55) sumiam no meio.
- Medições: diagnóstico completo em 0,48 s num arquivo de 28.475 registros.
  No arquivo já tratado, 216 problemas; no original, 34.651.

## [0.40.0] - 2026-09-22

Três mudanças que vieram do uso: a validação cobrava o que o PVA não cobra, o
painel de revisão listava o que não dava para corrigir, e o leiaute completo
ainda não tinha chegado aos módulos que dependem dele.

### Adicionado
- **`descritor_pva.py`** — lê o **descritor de validação** que cada PVA embarca
  no `.jar` (`fiscalpva-dominio.jar` e `piscofinspva-infra.jar`): tipo,
  tamanho, casas decimais, obrigatoriedade, enumerações
  (`<valores-validos valores="0=Entrada;1=Saída"/>`), tabela externa
  (`datasource`) e referência entre registros
  (`referenciaPesquisa="0200;COD_ITEM"`), por versão de leiaute. É a fonte
  mais próxima de "como o PVA valida".
- **Validação por (registro, campo)**, como o PVA faz. No EFD Contribuições o
  `CST_PIS` tem tabela diferente no C175, no C181 e no C191 — a regra global
  achatava isso.
- **Tipo e tamanho passam a ser validados** em todos os campos declarados
  (1.612 no ICMS/IPI, 1.191 no Contribuições), substituindo a heurística por
  prefixo `VL_`/`ALIQ_`, que errava nos dois sentidos.
- **As referências ao 0200 vêm do descritor**: 28 registros no ICMS/IPI e 14
  no Contribuições apontam para o cadastro de itens. "COD_ITEM do C170 tem de
  existir no 0200" deixou de ser regra escrita à mão.

### Corrigido
- **Falso positivo de `CST_ICMS` no EFD Contribuições.** Aquele PVA não valida
  o campo, e a verificação global o cobrava. Passou a valer o princípio: campo
  que o descritor não declara não é validado. No Contribuições, nenhum
  `datasource` é tratado como tabela de validação — lá eles alimentam as
  listas da edição. No arquivo real da CASA DO ESPETO, as ocorrências caíram
  de 1 para **0**.

### Alterado
- **O painel de revisão virou um sumário.** Uma linha por verificação, com a
  contagem e o **atalho para a função que corrige** — Recalcular C190,
  Preencher COD_GEN, Itens sem referência, Validar campos. Antes eram 1.887
  linhas dizendo "COD_ITEM tal não é referenciado" numa tela sem nenhum botão
  de correção. A lista item a item ficou em `DialogoOcorrencias`, atrás de
  *Ver ocorrências*, para quando a correção é manual.
- `revisao.revisar_por_regra()` preserva o vínculo entre a regra e os seus
  achados, que é o que permite o atalho por linha.

### Notas
- Os `<validador id="REGRA_..."/>` do descritor são regras compostas
  implementadas em Java. O módulo registra que existem, mas **não as
  reimplementa**: adivinhar produziria divergência silenciosa com o validador
  oficial.
- Medições nos arquivos reais: REAL LIDER 24.313 ocorrências (era 24.755, a
  diferença é o excesso removido), CASA DO ESPETO ICMS 8, Contribuições **0**.

## [0.39.0] - 2026-09-22

O leiaute dos dois SPEDs passou a ser **completo**. Antes o projeto mapeava
cerca de 110 registros; o resto aparecia na interface como "Campo 02",
"Campo 03", e nenhuma verificação alcançava esses campos.

### Adicionado
- **270 registros do EFD ICMS/IPI e 203 do EFD Contribuições**, com todos os
  campos e o nível hierárquico de cada um, extraídos registro a registro dos
  guias práticos (vriconsulting.com.br).
- Nos três arquivos reais de teste não sobra **nenhuma** coluna "Campo NN"
  nem registro sem leiaute — antes eram 7 tipos sem mapa em cada arquivo
  ICMS (1601, B001, B990, G001, G990, K001, K990).
- Cobertura de `COD_ITEM`: de 4 para **48** registros no ICMS/IPI (o bloco K
  inteiro entrou: K200, K230, K235, K250…) e de 6 para **21** no
  Contribuições. A varredura de referências de itens passa a enxergar o bloco
  K pelo nome do campo, e não pelo modo conservador.

### Notas — o que a extração precisou tratar
- **Nome repetido no mesmo registro.** O guia chama de `ALIQ_PIS` tanto o
  percentual quanto o valor por unidade; como `_ix` devolve o primeiro, o
  segundo ficaria inalcançável. Preservada a desambiguação que o código já
  usava (`ALIQ_PIS_QUANT`, `ALIQ_COFINS_QUANT`).
- **Nomes "sujos" no guia:** `COD_ NAT_CC` com espaço, `NÍVEL` com acento,
  `MES_REF *` com nota de rodapé. Sem normalizar, o campo sumia e o registro
  saía curto — foi o que fez o 0500 do Contribuições aparecer com 7 campos em
  vez de 9.
- **Páginas com histórico têm mais de uma tabela de leiaute**; vale a última.
  Pegando a primeira, o M210 e o M610 saíam com 13 campos em vez de 16.
- **Largura nunca encolhe.** Onde o guia trouxe menos campos que o layout já
  validado contra arquivo real, prevaleceu o antigo: o guia é que está numa
  versão anterior (E116, E310).
- Conferência final contra os três arquivos SPED reais: todos os **índices de
  campo documentados no `CLAUDE.md`** continuam nas mesmas posições, e
  `_ncampos` devolve os mesmos valores de antes (C170 38/37, C175 18, C190 12,
  H010 11, 0200 13).

## [0.38.0] - 2026-09-22

A verificação de códigos deixou de morar no código e passou a vir das
**tabelas dos próprios PVAs**. Enquanto a lista era embutida, ela envelhecia e
divergia do validador oficial — foi assim que o `34011190` passou limpo aqui e
foi acusado lá.

### Adicionado
- **`tabelas_pva.py`** — módulo novo. Lê as tabelas instaladas com os dois
  PVAs (`Fiscal/recursos/TabelasExternas` e
  `EFD-Contribuicoes/recursos/tabelas`), resolve a maior versão de cada uma e
  monta os domínios de campo. `carregar_dominios(layout, uf, data_ref)` e
  `disponivel()`.
- **A validação usa esses domínios por padrão.** Eles substituem os embutidos
  nos campos que cobrem; os embutidos passam a valer só onde o PVA não tem
  tabela — ou quando ele não está instalado.
- **O diálogo diz de onde veio cada verificação**: quais campos foram
  validados por tabela oficial e quais tabelas faltaram. Silêncio ali seria
  pior que erro, porque "0 divergências" pareceria aprovação.
- Cobertura nas tabelas instaladas (268 arquivos): **16 domínios** no EFD
  ICMS/IPI e **12** no EFD Contribuições.

### Notas — quatro cuidados que o arquivo real exigiu
- **Vigência por código.** A tabela única de CST do ICMS foi revogada em
  31/12/2012; validar contra ela reprovaria o arquivo inteiro.
- **CST do ICMS é composto**: origem (`SIT_TRIB_ICMS_A`) × situação
  (`SIT_TRIB_ICMS_B`), produto cartesiano das duas tabelas vigentes.
- **Códigos de ajuste são estaduais** (E111, E116): a tabela é escolhida pela
  UF do 0000, e a data de referência é a DT_FIN do próprio arquivo.
- **Zero à esquerda sobrando não é erro.** `COD_PAIS 01058` é o `1058` da
  tabela com um zero a mais e o PVA aceita — tratar como erro gerava **141
  falsos positivos** num arquivo real. Falta de dígito continua virando
  sugestão, e código **só de zeros** (`COD_MUN 0000000`) é campo vazio
  disfarçado.
- O diagnóstico do CSOSN sem dígito de origem foi preservado sobre a nova
  base: é o erro mais comum do `CST_ICMS` e dizer "fora da tabela" não
  ajudaria ninguém.
- Desempenho: carga das tabelas em 0,03 s, varredura de 28.475 registros em
  0,15 s.

## [0.37.0] - 2026-09-22

O PVA acusava incidência monofásica no NCM `34011190` (sabonete) e o programa
não via nada. A causa: **o PVA tem duas tabelas de monofásico e o projeto lia
só uma.**

### Corrigido
- **`PROD_MONO_ALIQ_DIFER` (tabela 4.3.10) passou a ser carregada** junto com
  a `PROD_MONO_ALIQ_UNID` (4.3.11). A primeira traz perfumaria, higiene
  pessoal, medicamentos, veículos e autopeças — a Lei 10.147/2000, onde o
  `34011190` está citado nominalmente:

      202|Produtos de Perfumaria, de Toucador ou de Higiene Pessoal|01012009||
      3303;3304;3305;3306;3307;34011190;34012010;96032100|||2,20|10,30

  A segunda traz combustíveis e bebidas frias, com alíquota por unidade de
  medida. `carregar_tudo` funde as duas e a versão exibida vira `40+37`.
- **O leitor entendia só o formato de 10 colunas.** A 4.3.10 tem 9 (não tem
  `UNID`), e suas alíquotas eram descartadas.

### Adicionado
- Campo próprio para o caminho da tabela 4.3.10 no diálogo *Verificar CST por
  NCM*; apontar a **pasta** do PVA continua resolvendo as duas sozinho.
- **Aviso quando a 4.3.10 não é encontrada**, dizendo o que se perde. Silêncio
  ali é pior que erro: o programa devolvia "0 divergências" com ar de aprovação.

### Notas
- Verificado com as tabelas reais do PVA: `34011190` e `34012010` são
  monofásicos; `34011900` (sabão em barra), `34012090` e `34013000` não — a
  distinção é a da lista oficial, não o capítulo do NCM.
- **Controle:** plantando CST 50 num item de NCM `34011190`, a versão antiga
  devolvia **0 divergências** e a nova aponta **3**, corrigidas em 6
  lançamentos (PIS e COFINS), com reverificação em zero.

## [0.36.0] - 2026-09-22

### Adicionado
- **O cadastro por trás do código, na própria grade.** Ao selecionar uma
  linha, o topo passa a resolver também o **participante** (0150) nas grades
  com `COD_PART` — C100, D100 —, do mesmo jeito que já resolvia o **produto**
  (0200) nas grades com `COD_ITEM`. Mostra nome, CNPJ/CPF pontuado e IE.
- **Ficha completa na dica da célula `COD_PART`**: nome, documento, IE,
  endereço, bairro e município (IBGE).
- **Participante ausente do 0150 fica em cor de aviso** na célula. O PVA
  recusa `COD_PART` que não exista no cadastro, e ver isso na grade poupa uma
  ida ao validador.
- No modelo: `participante()`, `formatar_doc_participante()` e
  `invalidar_participantes()`, com o cache invalidado ao editar um 0150 — o
  mesmo tratamento que o 0200 já tinha.

### Notas
- Em grade com os dois campos o **produto tem preferência**: é o que muda de
  linha para linha.
- Os índices do 0150 são obtidos por nome, não por posição: o registro é igual
  nos dois leiautes hoje, mas o código não depende disso.

## [0.35.0] - 2026-09-21

A verificação de CST por NCM era a única rotina que **só apontava**. Nas
entradas, porém, a correção é objetiva: monofásico e alíquota zero não geram
crédito na revenda.

### Adicionado
- **`rotinas.corrigir_cst_ncm`** — retira o crédito das **entradas** cujo NCM
  não o admite: troca o CST pelo sugerido pela classificação e zera base,
  alíquota e valor.
- Botão **Corrigir entradas sem crédito** no diálogo *Verificar CST por NCM
  (tabelas RFB)*, chamando a mesma função da rotina — uma regra fiscal, uma
  implementação.
- A rotina `cst_ncm` do painel por regime passou a ter `corrigir`, com o
  rótulo *"Retirar o crédito das entradas (troca o CST e zera
  base/alíquota/valor)"*.

### Notas — os limites são de propósito
- **Só onde o crédito está sendo tomado** (CST 50-56 / 60-66). Item já num CST
  sem crédito não é tocado: 70, 73 e 98 se distinguem pelo **motivo** da
  vedação, e trocar um pelo outro sem saber o motivo seria palpite. Quem zera
  valores sobrando nesses casos continua sendo a rotina `cst_sem_direito`.
- **Saídas ficam de fora.** A sugestão existe (04, 06, 01), mas lá o CST
  depende de o produto ser revenda ou produção própria, e alíquota
  diferenciada (02/03) é legítima.
- Validado por **controle**: o arquivo real da CASA DO ESPETO já estava certo
  (entradas de bebida com CST 73), então o erro foi plantado — 12 entradas de
  NCM 2202/21069090 com CST 50 e alíquotas de não-cumulativo. Resultado: 24
  lançamentos corrigidos (PIS e COFINS), CST 73, base e valor zerados,
  alíquota em branco, R$ 111,00 de crédito indevido retirado, reverificação em
  zero, segunda passada sem efeito e saídas intactas.

## [0.34.0] - 2026-09-21

O recálculo do C190 já corrigia o `VL_RED_BC`, mas só documento a documento —
e no arquivo real eram 66 registros espalhados por 53 documentos.

### Adicionado
- **Ferramentas → EFD ICMS/IPI → Recalcular C190 com redução de base
  zerada…** Refaz o analítico apenas dos documentos com CST x20/x70 e
  `VL_RED_BC` em branco; refazer o que já está certo seria substituir registro
  sem motivo. No modelo: `documentos_c190_com_reducao_zerada()` (não altera
  nada) e `consolidar_c190_em_massa()`.
- **Base de PIS/COFINS como substituta no CST x70.** Ali o ICMS foi cobrado
  por ST e não existe base própria de onde tirar a diferença. Quando o item
  tem `VL_BC_PIS` (ou `VL_BC_COFINS`), ela entra no lugar **apenas para
  calcular a redução** — o `VL_BC_ICMS` do C190 continua zero, como deve ser.
  Sem nenhuma das duas bases, a redução fica zerada e o caso é apontado para
  conferência manual, nunca chutado.
- O relatório de **Revisar erros** passou a oferecer as correções em massa
  cabíveis ao que encontrou (recalcular C190, preencher COD_GEN, itens sem
  referência), com `DialogoRevisao(..., acoes=[...])`.

### Notas
- No arquivo real: 66 C190 com redução zerada em 53 documentos, **todos CST
  x70**. Depois do lote, **29 grupos** corrigidos pela base de PIS/COFINS e 37
  restantes (itens com `CST_PIS` 73, sem base nenhuma).
- `VL_OPR`, `VL_BC_ICMS` e `VL_ICMS` do arquivo ficaram **idênticos** antes e
  depois — 919.795,97 / 202.854,14 / 32.240,62 —, a contagem de C190 não mudou
  (6.678) e o E110 continua batendo com a soma das saídas (11.878,73). O
  recálculo repôs a redução sem mexer em valor nenhum.
- O resumo distingue `documentos` de `corrigidos`: rodar de novo devolve
  `corrigidos: 0`, em vez de dar a impressão de ter mudado algo.

## [0.33.0] - 2026-09-21

*"Não informar item, se não referenciado em pelo menos um dos demais blocos."*
O cadastro do arquivo real tinha **1.630 itens** que nenhum registro citava.

### Adicionado
- **Ferramentas → Gerais → Itens do 0200 sem referência…** Varre o arquivo
  inteiro atrás de cada código do cadastro, lista os órfãos com descrição e
  contagem de filhos, e remove sob confirmação — com duplo-clique que navega
  até o registro e exportação em CSV.
- No modelo: `referencias_de_itens()`, `itens_0200_nao_utilizados()` e
  `remover_itens_0200()` (que apaga a subárvore junto: 0205, 0206, 0220…).
- **Varredura em duas estratégias.** Registro com leiaute mapeado é lido pelo
  **nome** do campo `COD_ITEM`; registro que o projeto ainda não mapeia — o
  **bloco K** inteiro, que usa `COD_ITEM` em quase todos os registros — é
  varrido **por valor**. O modo conservador erra para mais: preserva item que
  talvez pudesse sair, mas nunca apaga item em uso. O painel mostra de onde
  vieram as referências e quais registros caíram nesse modo.

### Alterado
- A regra de revisão *0200 não utilizados* passou a usar a mesma varredura do
  modelo. Antes ela olhava só o nome do campo e, num arquivo com bloco K
  escriturado, apontaria como não utilizado item que está sendo usado lá.

### Notas
- Validado em arquivo real: 12.479 itens, 10.849 referenciados, 1.630 órfãos —
  os mesmos apontados pela regra de revisão, conferidos por `uid`. Depois de
  remover, nenhum referenciado se perdeu (verificação explícita por conjunto),
  larguras íntegras e inventário fechando em R$ 958.285,74.
- Num **controle**, um `K200` sem leiaute citando um órfão fez o item sair da
  lista — a proteção da varredura por valor funciona.
- Os 1.630 órfãos eram exatamente os 1.630 itens com `TIPO_ITEM` inválido
  herdado do ERP; removê-los zerou aquele achado também.

## [0.32.0] - 2026-09-21

O PVA recusou o H010 com *"O campo é obrigatório para EFD ICMS/IPI com Perfil
igual a 'A' ou 'B'"* no `COD_CTA`. O arquivo é perfil **B** e não tinha conta
contábil em nenhum dos 9.929 itens do inventário — nem em 2.486 C170.

### Adicionado
- **Ferramentas → Gerais → Preencher conta contábil (COD_CTA)…** Lista os
  tipos de registro que estão sem conta e preenche **um tipo por vez**, porque
  cada um leva uma conta diferente — estoque no H010, custo no C170. A
  natureza (`COD_NAT_CC`) vem sugerida conforme o registro. Registros que já
  têm conta não são tocados.
- **O registro 0500 (plano de contas) é criado junto**, na posição do leiaute
  (depois do último registro de código menor) e com `DT_ALT` igual ao início
  do período. Informar conta que não existe no plano seria o próximo erro.
  Quando o arquivo já tem 0500, as contas aparecem num seletor.
- No modelo: `perfil()`, `contas_0500()`, `registros_sem_cod_cta()`,
  `criar_conta_0500()` e `preencher_cod_cta()`.
- **Leiaute do 0500 do EFD ICMS/IPI** acrescentado ao `sped_layouts.py`: são
  **7 campos** (`REG`, `DT_ALT`, `COD_NAT_CC`, `IND_CTA`, `NIVEL`, `COD_CTA`,
  `NOME_CTA`). O do EFD Contribuições, já mapeado, tem **9** — ganha
  `COD_CTA_REF` e `CNPJ_EST`. Confundir os dois geraria pipe sobrando.

### Corrigido
- **`_ncampos` medido depois de criar devolvia 1.** O helper usa a moda dos
  registros do tipo já presentes, e `novo_registro` insere o registro com um
  campo só — o primeiro 0500 do arquivo saiu como `|0500|`. O tamanho passou a
  ser medido antes da criação. A armadilha ficou registrada no `CLAUDE.md`.

## [0.31.0] - 2026-09-21

Até aqui cada campo torto virava uma regra própria — `TIPO_ITEM` fora da
tabela, `COD_GEN` sem o capítulo, `NULL` gravado por extenso. Não escala. Esta
versão troca isso por uma tabela de **domínios por nome de campo**, aplicada a
qualquer registro que possua o campo.

### Adicionado
- **`validacao.py`** — módulo novo. `DOMINIOS` associa o nome do campo ao seu
  domínio (NCM 8 dígitos, CEST 7, CFOP 4 começando por 1/2/3/5/6/7, CST de
  PIS/COFINS na tabela oficial, `COD_SIT`, indicadores, datas reais, e campos
  numéricos pelo prefixo `VL_`/`ALIQ_`/`QTD`). Funciona por nome porque no SPED
  o nome carrega o domínio: `CFOP` é CFOP no C170, no C190 e no D190.
  `validar()` varre sem alterar; `normalizar()` grava só o que tem conserto
  mecânico; `resumo()` agrupa para o panorama.
- **Ferramentas → Gerais → Validar campos pelo leiaute…** O diálogo separa o
  que tem **conserto automático** (zero à esquerda perdido, texto de vazio) do
  que exige **decisão fiscal**, com filtros por natureza e por campo. O botão
  normaliza em lote; o **duplo-clique navega até o registro** para corrigir à
  mão o que não dá para adivinhar.
- Diagnóstico específico onde ele muda a ação do usuário: `CST_ICMS` com `101`
  ou `201` não é lixo, é o **CSOSN do fornecedor do Simples sem o dígito de
  origem** — e o texto diz isso, sem sugerir correção, porque origem de
  mercadoria é informação fiscal e não formatação.

### Notas
- Sugestão só nasce quando falta **exatamente um** dígito; repor dois zeros
  seria inventar. `sugestao=""` significa "esvaziar" e `None`, "não sei
  consertar".
- Só o que está **preenchido** é validado. Obrigatoriedade depende do registro
  e da operação, não do nome do campo.
- No SPED real de 08/2026: 28.475 registros varridos em 0,11 s, 24.751 campos
  fora do domínio, **14.253 corrigidos num clique** (COD_GEN 10.312, CEST
  3.499, COD_NCM 442). Nos arquivos da CASA DO ESPETO a regra achou 8
  ocorrências que nenhuma outra função via, entre elas um `CST_ICMS` truncado
  em `0`.

## [0.30.0] - 2026-09-21

O `COD_GEN` é derivável — são os **dois primeiros dígitos do NCM** (Tabela
4.2.1) — então não precisa vir de planilha. E é bom que não precise: calcular
`LEFT(NCM;2)` sobre uma célula numérica dá `40` para o NCM `04012010`, porque
a planilha já comeu o zero. Na planilha real seriam **593 itens** com o gênero
errado, todos com código válido — erro que passa silencioso.

### Adicionado
- **Ferramentas → EFD ICMS/IPI → Preencher COD_GEN pelo NCM (0200)…**
  Deriva o gênero do próprio arquivo, com o NCM normalizado antes do corte.
  Mostra quantos estão vazios e quantos têm outro valor, com exemplos, antes
  de gravar. No arquivo real: 12.478 itens preenchidos, 0 divergências depois.
  No modelo: `divergencias_cod_gen()` (não altera nada) e `preencher_cod_gen()`.
- **Regra de revisão "COD_GEN incoerente com o NCM (0200)"**, que aponta tanto
  o vazio quanto o gênero que não bate com o capítulo.
- Os avisos da atualização do 0200 saíram da GUI para o modelo
  (`avisos_previa_0200`), onde é o lugar da regra fiscal. Passou a cobrir
  também o **COD_GEN que não bate com o NCM** — campo assim nasce desmarcado,
  como o `TIPO_ITEM` fora da tabela.

### Corrigido
- **`TIPO_ITEM` e `COD_GEN` de um dígito ganham o zero à esquerda.** A célula
  com `00` vira o número 0 e chega como `"0"`, que o PVA não aceita; as duas
  tabelas só têm códigos de dois dígitos, então um dígito só pode ser o zero
  perdido. Na planilha real do cliente eram **9.929 itens** com `TIPO_ITEM`
  nessa situação.
- **Zero numérico não vira código.** Célula vazia de planilha chega como `0`, e
  `0` não é NCM, CEST, gênero nem código de barras — é o "sem valor" do ERP
  outra vez. A importação chegou a gravar `COD_NCM = 0` num item que não tinha
  NCM. A alíquota fica de fora da regra: ali o zero é alíquota zero.

## [0.29.0] - 2026-09-21

O PVA recusou itens que **já existiam no 0200**: o cadastro do arquivo estava
errado e a importação de inventário só criava os itens ausentes, nunca
corrigia os presentes.

### Adicionado
- **Atualizar o cadastro 0200 pela planilha**, opcional, no diálogo de
  importação de inventário. Corrige `DESCR_ITEM`, `UNID_INV`, `TIPO_ITEM`,
  `COD_BARRA`, `COD_NCM`, `EX_IPI`, `COD_GEN`, `ALIQ_ICMS` e `CEST` dos itens
  que já existem, com a mesma normalização usada ao criar.
- **A correção não é cega.** `previa_atualizacao_0200()` calcula antes, sem
  alterar nada, e o diálogo mostra campo a campo quantos valores mudariam, com
  exemplos, para marcar só o que deve ser aplicado. No arquivo real: `COD_NCM`
  447, `CEST` 471, `COD_BARRA` 36, `ALIQ_ICMS` 832 — e `TIPO_ITEM` 1.273.
- **Campo com valor fora da tabela oficial nasce desmarcado.** A mesma planilha
  que corrigia os NCM truncados traria `TIPO_ITEM` = `N` — que não existe na
  tabela (00 a 10 e 99) — para 1.273 itens que estavam **certos**, trocando um
  código válido por um inválido. Constante `TIPOS_ITEM_0200` no modelo.
- Aviso separado quando a planilha **zeraria a alíquota de ICMS**: é mudança de
  tributação, não de cadastro, e o diálogo diz quantos itens seriam afetados.
- **Regra de revisão "TIPO_ITEM fora da tabela (0200)"**. No arquivo real são
  **10.312 itens** com `N`, herdados da exportação do ERP — exatamente os
  mesmos que traziam `COD_GEN` = `NULL`. A correção em massa já existe: a
  grade do 0200 aplica um valor em toda a seleção.

### Corrigido
- **Alíquota comparada como número.** `18,00` e `18` são o mesmo valor; sem
  isso a prévia acusava 7.615 alterações onde havia **832** reais, e a
  importação reescrevia milhares de registros à toa.
- Coluna **não mapeada** e célula **vazia** nunca apagam o que já está no
  cadastro — uma coluna em branco varreria dados legítimos do 0200.

## [0.28.0] - 2026-09-21

### Corrigido
- **O H010 não aparecia depois de importar o inventário.** Os 11.585 registros
  estavam no arquivo e na árvore, mas a grade do `H005` — que tem **uma única
  linha** — nasce sem seleção, e o detalhe só é montado quando uma linha é
  selecionada. O bloco H exibia três grades de uma linha cada e nada mais.
  Grade com uma linha só passa a se selecionar sozinha quando o registro tem
  filhos; com várias linhas a escolha continua sendo do usuário, para não
  deixar uma linha marcada sem querer nas ações em lote.

### Alterado
- **Cada bloco abre na primeira sub-aba com conteúdo**, em vez do registro de
  abertura. Nível 1 é só abertura/encerramento (`C001`, `H001`, `H990`…), com
  um campo cada — cair ali fazia o inventário parecer inexistente. Agora o
  bloco C abre em `C100`, o H em `H005` (já com `H010` no detalhe), o E em
  `E100` (com `E110` à vista) e o 9 em `9900`. O bloco 0 continua abrindo em
  `0000`, que é nível 0 e de fato interessa.

## [0.27.1] - 2026-09-21

### Corrigido
- **A janela não abria.** A ação *Limpar campos com NULL* da 0.27.0 foi criada
  só em `_criar_acoes`, que **não roda** quando o `sped_editor.ui` existe — e é
  esse o caminho normal. `_montar_botao_ferramentas` roda nos dois e tentava
  montar o menu com uma ação inexistente, derrubando a janela no construtor com
  `AttributeError: 'JanelaPrincipal' object has no attribute
  'act_limpar_nulos'`. A ação passou a ser criada defensivamente também em
  `_conectar_ui`, como as demais. É o quarto ponto do padrão descrito no
  `CLAUDE.md` — o mesmo que já tinha derrubado a ação *Empresas*.

## [0.27.0] - 2026-09-21

O PVA recusou o arquivo da segunda empresa com *"Conteúdo de Campo inválido"*
no `COD_GEN`. A origem não era a importação de inventário: o **ERP do cliente
exporta o `NULL` do banco por extenso** para dentro do SPED — 13.341 campos,
em 82,6% dos itens do 0200.

### Adicionado
- **Limpar campos com NULL** (Ferramentas → Gerais). Encontra campos
  preenchidos com `NULL`, `None`, `#N/A`, `#REF!` e afins e os esvazia sob
  confirmação, mostrando antes a contagem por registro e campo. Detecção e
  correção separadas, como nas demais rotinas: `campos_nulos()` não altera
  nada; `limpar_campos_nulos()` corrige exatamente a lista exibida.
  No arquivo real: 13.341 campos em 10.312 registros — `COD_GEN` (10.312) e
  `CEST` (3.029) —, zero sobrando depois, larguras preservadas e os CEST
  legítimos intactos.
- `-` e `N/A` ficaram **fora** da lista `VALORES_NULOS` de propósito: podem ser
  descrição legítima de produto.

### Corrigido
- **A leitura de planilha passou a tratar esses textos como célula vazia**
  (`_texto_planilha`). Antes, uma planilha exportada do mesmo ERP levaria o
  `NULL` para dentro do 0200 pela importação de inventário — o caminho que o
  usuário suspeitou e que, embora não fosse a causa deste arquivo, tinha
  mesmo o defeito.

## [0.26.0] - 2026-09-17

Validação da **importação de inventário** contra a planilha real de uma segunda
empresa (11.585 itens, 22 colunas) e o SPED ICMS/IPI dela (28.475 registros,
sem bloco H). Quatro defeitos apareceram — e três deles fariam o PVA recusar o
arquivo gerado.

### Corrigido
- **O bloco H saía sem o `H990`.** Em arquivo que ainda não tem inventário
  nenhum, `importar_inventario_h010` criava H001/H005/H010 e parava aí: o
  arquivo ia de `H010` direto para `K001`. `atualizar_bloco9_inplace` só
  **atualiza** os X990 existentes, nunca cria o que falta, e `gerar_texto`
  reconstrói apenas o bloco 9. Bloco aberto e não encerrado é recusa certa no
  PVA. Agora o H990 é criado quando não existe, e a contagem sai correta
  (11.588 linhas no arquivo real).
- **`VL_INV` do H005 ficava um centavo fora da soma dos H010.** O total era
  acumulado com o valor **bruto** e arredondado no fim, enquanto cada H010
  gravava o valor arredondado — 958.285,73 contra 958.285,74. O arredondamento
  passou a acontecer num ponto só, antes de usar o valor nos dois lugares.
  É o mesmo erro do rateio de despesas acessórias, em outro lugar.
- **`VL_ITEM_IR` ia para o arquivo como `str()` do float da planilha** —
  `11.24`, `155.7`, `6` — com ponto decimal e sem as duas casas. Agora passa
  por `_fmt_val` como todo campo de valor.
- **Códigos de tamanho fixo perdiam o zero à esquerda.** A célula numérica da
  planilha devolve `4012010` no lugar de `04012010`: eram **593 NCM** e **530
  CEST** no arquivo real. Como nem NCM nem CEST começam com `00`, falta no
  máximo um dígito — `_zero_a_esquerda` repõe só nesse caso e não inventa nada
  fora dele. O código de barras, cujos comprimentos 8/12/13/14 são todos
  válidos, só é corrigido quando o **dígito verificador** confirma o palpite
  (`_gtin_corrigido`).

### Adicionado
- **A conferência separa o que é erro da planilha do que é erro do arquivo.**
  Quando o NCM só difere pelo zero à esquerda, quem está truncado é o **0200
  do SPED** — no arquivo real são **442 itens**, contra apenas **4** NCM
  realmente divergentes. Antes os 446 apareciam no mesmo balaio. O retorno de
  `conferir_itens_inventario` ganhou `ncm_truncado`, `sem_qtd` e `sem_valor`, e
  o diálogo mostra os três.
- A comparação de inventário limita a precisão do ajuste de colunas: com 11.585
  linhas, medir todas as células travava a abertura do diálogo.

## [0.25.0] - 2026-09-17

Primeira validação contra **arquivo real** (EFD ICMS/IPI e Contribuições de um
mesmo período, com 286 XMLs). Três correções nasceram do que os dados
mostraram, e nenhuma delas apareceria em arquivo sintético.

### Corrigido
- **Despesas acessórias: o critério virou auto-detectável por documento.** A
  0.15.3/0.15.4 assumia que `vOutro`/`vFrete`/`vSeg` do item sempre estão
  embutidos no VL_ITEM. O arquivo real mostrou o contrário: o ERP mantém
  `VL_ITEM = vProd` e lança a despesa em **VL_OUT_DA do C100**, como o leiaute
  prevê — o que produzia **227 falsos positivos**. Agora `conferir_itens_xml`
  compara `VL_OUT_DA + VL_FRT + VL_SEG` do C100 com a soma dos acessórios dos
  itens e decide, documento a documento, se soma ou não.
- **CSOSN deixou de gerar divergência falsa.** Fornecedor do Simples emite
  CSOSN (origem + 3 dígitos) e o comprador escritura CST normal (origem + 2):
  são tabelas diferentes. Os itens assim são contados em
  `cst_csosn_ignorados` em vez de comparados — era a limitação registrada na
  seção 4.1 do FUNCIONALIDADES.
- Com as duas correções, as divergências das entradas caíram de **404 para
  149** no arquivo real, sem perder nenhum achado verdadeiro.

### Adicionado
- **Guarda no *Regenerar C175* (modelo 65).** O fluxo assume que o XML é a
  verdade; no arquivo real, **28 das 205 NFC-e** foram emitidas pelo PDV com
  alíquota de não-cumulativo enquanto a empresa é cumulativa — a escrituração
  estava certa e o XML errado. Regenerar às cegas **aumentaria** o tributo
  declarado em R$ 1.117,31. Agora o diálogo mostra PIS, COFINS e valor da
  operação antes e depois, com a diferença, e o botão de confirmação deixa de
  ser o padrão quando há mudança. No modelo: `previa_regeneracao_c175_65()`.
- **Nova rotina: valor lançado em CST sem direito a crédito** (entradas com
  CST 70-75/98/99 trazendo base e valor). Encontrou **512 ocorrências** (256
  itens × 2 tributos) em 33 documentos do arquivo real. Vale para qualquer
  regime; a correção zera os valores **mantendo o CST**.

## [0.24.0] - 2026-09-17

### Corrigido
- **No executável, os dados do usuário seriam perdidos a cada fechamento.**
  `empresas.json`, `correlacoes_cfop.json`, `config_tabelas_rfb.json` e a pasta
  `arquivos/` eram gravados ao lado do módulo — que num executável *onefile* é
  a pasta temporária de extração, apagada na saída. O defeito só apareceria na
  **segunda** execução, sem erro nenhum: o programa simplesmente esqueceria
  tudo. Agora o novo módulo `dados.py` decide o caminho:
  - **empacotado** → `%APPDATA%\SPED Tables` (ou `~/.sped_tables` fora do
    Windows);
  - **do código-fonte** → a pasta do projeto, como sempre, para não espalhar
    arquivo de teste pelo perfil durante o desenvolvimento.

### Adicionado
- **Instalação na primeira execução** (só no executável): cria a pasta de
  dados, copia para lá os padrões que vieram no pacote **sem sobrescrever** o
  que já for do usuário, e oferece **criar o atalho na área de trabalho**. Uma
  marca na pasta de dados evita repetir a pergunta a cada atualização.
- `dados.criar_atalho_area_trabalho()`, via WScript.Shell pelo PowerShell —
  sem depender de pywin32 — tratando o redirecionamento da área de trabalho
  pelo OneDrive.

## [0.23.1] - 2026-09-17

### Corrigido
- **A margem da janela maximizada ignorava o DPI do monitor.**
  `GetSystemMetrics` devolve sempre a medida de 96 DPI; num monitor a 125% ou
  150% a margem sairia pequena demais e parte do conteúdo ficaria fora da tela
  — erro que, num arranjo de dois monitores com escalas diferentes, só aparece
  depois de arrastar a janela. Passa a usar `GetSystemMetricsForDpi` com o DPI
  da própria janela, caindo na medida clássica onde a função não existir
  (anterior ao Windows 10 1607).

### Alterado
- **A barra de título própria passa a ser considerada estável.** A
  documentação ainda a descrevia como experimental e opt-in, o que deixou de
  ser verdade na 0.19.1, quando virou padrão.

### Verificado
Suíte própria, em janela real do Windows: hit-test correto nas **oito** bordas
e cantos, HTCAPTION na faixa da barra e HTCLIENT sobre os botões, três ciclos
de maximizar/restaurar sem o conteúdo transbordar a área de trabalho (0 px em
todos), troca de tema com a barra preservada, escotilha
`SPED_TABLES_BARRA_NATIVA=1` e tolerância a ponteiro de mensagem inválido.

Fica registrado o que **não** foi observado: a máquina de desenvolvimento roda
a 96 DPI, então o caminho sensível a DPI é exercitado mas o valor escalado não
pôde ser comparado num monitor a 125%.

## [0.23.0] - 2026-09-17

### Adicionado
- **Recalcular ICMS dos itens** (Ferramentas → EFD ICMS/IPI). Fecha o fluxo de
  correção pelo **Modo Relatório**: corrija alíquota, base ou CST direto na
  grade e peça o recálculo para os campos derivados voltarem a bater.
  - **VL_ICMS = VL_BC_ICMS × ALIQ_ICMS ÷ 100**, sempre — é o cálculo que amarra
    os três campos e o que mais sai errado quando a alíquota é corrigida à mão.
  - Opcional: **refazer a base** a partir de `VL_ITEM − VL_DESC`, aplicando um
    percentual de **redução** nos CST **x20** e **x70**. Sem essa opção, a base
    informada é respeitada — inclusive uma base reduzida digitada à mão.
  - Opcional (ligado): **zerar** base, alíquota e valor nos CST **sem débito
    próprio** (x30, x40, x41, x50, x60). Um CST desses com valor lançado é erro
    de escrituração, não redução.
  - Ao final, refaz o **C190** e os **totais do C100** dos documentos afetados.
  - **Escopo padrão: os itens do Modo Relatório** — o conjunto que acabou de
    ser revisado. Sem relatório gerado, vale para todos os C170.
  - O **ICMS-ST não é tocado**: tem base e alíquota próprias, muitas vezes com
    MVA, e misturá-lo produziria número errado em silêncio.
- No modelo: `SpedDocument.recalcular_icms_itens()` e `situacao_icms()`, que
  classifica o CST em tributado / reduzido / sem débito pelos **dois últimos
  dígitos** (o primeiro é a origem da mercadoria e não interfere no cálculo).

## [0.22.2] - 2026-09-17

### Corrigido
- **O executável empacotado não levava recursos nenhum** (`datas` estava
  vazio no `.spec`). Passam a ser incluídos:
  - **`qtbase_pt_BR.qm`**, na pasta `traducoes/` do pacote — sem ele os
    diálogos do executável sairiam em inglês, mesmo com a correção da 0.22.1.
    O `instalar_traducao()` procura ali **antes** do caminho do sistema.
    O `qt_pt_BR.qm` fica de fora de propósito: é um meta-catálogo que só
    carrega com os `.qm` irmãos na mesma pasta; quem traz as strings de
    diálogo é o `qtbase`.
  - **`icon.ico`**, que além de ícone do executável é lido em tempo de execução
    pela barra de título e pelo `setWindowIcon`;
  - **`sped_editor.ui`**, o layout do Qt Designer (sem ele o programa cai no
    fallback programático);
  - **`correlacoes_cfop.json`**, para o programa nascer com a tabela padrão.
- O `.spec` agora **falha na geração** se a tradução não for encontrada —
  melhor que descobrir o inglês depois de distribuir.

## [0.22.1] - 2026-09-17

### Corrigido
- **Os diálogos do Qt apareciam em inglês** ("Save", "Discard", "Cancel",
  "Yes", "No"), destoando de uma interface toda em português. Duas camadas de
  correção:
  1. A **tradução pt-BR do próprio Qt** (`qtbase_pt_BR` e `qt_pt_BR`) passa a
     ser carregada na inicialização, junto com a locale pt-BR — isso cobre
     tudo que o Qt desenha, não só a pergunta de salvar.
  2. A pergunta de **salvar antes de fechar** escreve os próprios rótulos
     (*Salvar*, *Descartar*, *Cancelar*), sem depender dos arquivos `.qm`, que
     podem não ser empacotados no executável. É a pergunta em que sair em
     inglês seria pior: é ela que decide se o trabalho é gravado ou perdido.

### Alterado
- A pergunta foi separada da decisão (`_perguntar_salvar` devolve
  `"salvar"`/`"descartar"`/`"cancelar"`), o que também torna o fluxo testável
  sem depender de diálogo modal.

## [0.22.0] - 2026-09-17

### Adicionado
- **Fechar arquivo** na barra de ferramentas: encerra a escrituração aberta e
  volta para a tela inicial. Havendo alterações não salvas, pergunta antes,
  com as três saídas de sempre — **Salvar**, **Descartar** e **Cancelar**.
  - Um *Salvar* que acabe cancelado (o diálogo de *Salvar como* fechado no X)
    **não fecha o arquivo**: a intenção era guardar, e seguir em frente
    perderia o trabalho.
  - Ao fechar, as ferramentas que dependem de arquivo são desabilitadas e o
    título volta ao nome do programa.

### Alterado
- **Sair do programa passou a oferecer salvar.** Antes a pergunta era binária
  ("deseja sair mesmo assim?"), e a única saída com alterações pendentes era
  descartá-las. Agora usa a mesma pergunta do fechar arquivo.

## [0.21.0] - 2026-09-17

### Adicionado
- **Tela inicial**, no lugar das abas *Modo Tabela* e *Modo Relatório* vazias.
  Ela usa o que o programa já sabe sem abrir arquivo — o histórico arquivado e
  o cadastro — para responder três perguntas de quem chega:
  - **Em que eu estava?** Botão *Continuar* com o último período arquivado
    (empresa e mês no próprio rótulo) e área para **arrastar e soltar** o .txt.
  - **O que falta?** **Matriz empresa × período** dos últimos 8 meses:
    `●●` os dois leiautes arquivados, `●` só um (azul ICMS, âmbar
    Contribuições), `—` nenhum. Duplo clique numa célula abre aquele período.
    O rótulo é deliberado: **"arquivado neste sistema"**, nunca "entregue" — um
    arquivo pode ter sido transmitido sem jamais passar por aqui.
  - **O que dá para fazer agora?** Pendências (empresa com arquivo e sem
    cadastro, cadastro que nunca recebeu arquivo) e atalhos que não dependem de
    arquivo aberto.
- **Dimensionamento conforme a resolução** (`dimensionar_para_a_tela`): numa
  tela folgada a janela abre grande e centralizada (até 1600×960, limitada a
  88% da área útil); numa tela apertada **abre maximizada** e o tema entra em
  **densidade compacta** — fonte e espaçamentos menores, porque numa grade de
  SPED alguns pixels de padding por célula valem uma coluna a mais visível.
- `tema.definir_densidade("normal"|"compacta")`, que ajusta apenas corpo de
  fonte e espaçamento; cor e borda seguem idênticas nas duas.
- No modelo: `arquivos.cobertura()`, `arquivos.pendencias()` e
  `arquivos.resumo_acervo()` — a tela inicial é só a apresentação disso.

### Alterado
- O widget central tem agora três páginas: **tela inicial** (sem arquivo),
  **editor** (com arquivo) e **empresas**. Abrir um arquivo leva ao editor;
  sair de Empresas volta para onde fizer sentido.

## [0.20.1] - 2026-09-17

### Corrigido
- **O painel de empresas não lembrava a empresa selecionada.** A seleção era
  relida do próprio widget na hora de recarregar, o que falha nos fluxos em que
  a lista é remontada antes disso (cadastrar, remover, abrir do histórico).
  Agora a escolha é guardada explicitamente e **também sobrevive a reabrir o
  programa** (QSettings).

## [0.20.0] - 2026-09-17

### Alterado
- **Empresas deixou de ser janela separada e virou painel da janela
  principal.** Como diálogo ficava apertado: lista, cadastro e histórico lado a
  lado pedem a largura inteira. O painel ocupa uma **página própria do widget
  central** (QStackedWidget), fora das abas de bloco e dos modos
  Tabela/Relatório — não é um bloco do arquivo, é o cadastro.
- **O botão *Empresas* da barra virou interruptor.** Clicar abre o painel,
  clicar de novo volta ao editor. Enquanto está aberto, o botão fica com
  **moldura na cor do acento** e fundo suave, para deixar claro que é um
  estado, não um clique que passou. O botão *Voltar ao editor*, no rodapé do
  painel, também desmarca o botão da barra.
- Ao entrar no painel, o cadastro é **relido do disco** e a lista repintada:
  abrir ou salvar um arquivo arquiva uma cópia, e o histórico pode ter mudado
  desde a última visita.

## [0.19.2] - 2026-09-17

### Corrigido
- **Botões de minimizar e maximizar destoavam do de fechar.** Os três usavam
  caracteres de fontes diferentes (`–`, `□`, `✕`), com peso, altura e
  alinhamento óptico distintos. Passaram a usar os glifos de **Segoe MDL2
  Assets**, a mesma fonte que o Windows usa nos próprios botões de janela, com
  reserva em texto para sistemas sem ela. O botão central agora também troca
  entre os glifos de *maximizar* e *restaurar*.
- **Duas setas no botão Ferramentas.** O texto trazia um `▾` literal e o Qt
  desenhava o indicador de menu por cima. O caractere foi removido — o
  indicador nativo basta.

## [0.19.1] - 2026-09-17

### Corrigido
- **O programa não abria: o console piscava e fechava.** Duas falhas nativas,
  ambas sem traceback porque acontecem dentro do despacho de mensagens do
  Windows ou no envio de eventos do Qt.
  1. **`super().nativeEvent(...)` derruba o processo no PyQt6.** O override
     existia mesmo com a barra própria desligada, então o crash atingia
     **todos** os usuários, não só quem ligasse a barra. Para "não tratei",
     agora devolvemos `(False, 0)` — o Qt segue com o tratamento padrão.
  2. **Estruturas ctypes criadas a cada chamada.** Uma função que define
     `RECT` internamente devolve um *tipo novo* a cada invocação, e o ctypes
     compara tipos por identidade: `byref(RECT_A)` onde `argtypes` espera
     `POINTER(RECT_B)` falha. Como `WM_NCHITTEST` chega a cada movimento do
     mouse, o erro era imediato. As estruturas e os `argtypes` passaram a ser
     definidos **uma única vez, no import**.

### Alterado
- **A barra de título própria passou a ser o padrão**, agora que o caminho
  nativo foi validado por medição em janela real:
  - área de cliente cobrindo a janela inteira (WM_NCCALCSIZE);
  - `HTCAPTION` na faixa da barra, `HTRIGHT` na borda e `HTCLIENT` no conteúdo;
  - maximizada, o **conteúdo** ocupa exatamente a área de trabalho
    (0,0 → 1920,1050 num monitor 1080p), com a barra de tarefas visível — o
    retângulo da janela é maior de propósito, porque a moldura fica fora da
    tela, como em qualquer janela com WS_THICKFRAME.
  - Escotilha: **`SPED_TABLES_BARRA_NATIVA=1`** volta à barra do Windows.
- `tratar()` ficou inteiramente defensivo: qualquer exceção devolve "não
  tratei", e o Windows aplica o comportamento padrão.

## [0.19.0] - 2026-09-17

### Adicionado
- **Barra de título própria** (`janela_custom.py` + `BarraTitulo`), no lugar da
  barra do Windows — por enquanto **opcional**: ligue com a variável de
  ambiente `SPED_TABLES_BARRA_CUSTOM=1`.
  - Mostra ícone, nome do aplicativo, **empresa · período · leiaute · arquivo**
    e um **indicador de alterações não salvas** (antes, só um asterisco no fim
    do título, fácil de passar batido antes de fechar).
  - Botões de minimizar, maximizar/restaurar e fechar seguem a paleta; o de
    fechar acende em vermelho no hover.
  - **O comportamento nativo é preservado.** Em vez de `FramelessWindowHint` —
    que faria a janela deixar de ser uma janela para o Windows —, interceptamos
    três mensagens: `WM_NCCALCSIZE` (a área de cliente passa a ocupar a janela
    inteira), `WM_NCHITTEST` (nós definimos bordas, cantos e faixa de arrasto) e
    `WM_GETMINMAXINFO` (maximizar respeita a barra de tarefas do monitor certo).
    Assim continuam funcionando **Aero Snap**, redimensionar pelas bordas,
    duplo clique para maximizar, menu de sistema e sombra — o que importa num
    editor quase sempre usado lado a lado com o PVA.
  - Fora do Windows, sem a variável, ou se a preparação falhar, o programa usa
    a barra nativa: `showEvent` desmonta a barra própria e avisa na barra de
    status. Enfeite não pode impedir o aplicativo de abrir.

### Por que opcional
A interceptação de mensagens nativas **não pôde ser validada de forma
automatizada**: exibir uma janela real fora de uma sessão interativa não
funciona no ambiente de desenvolvimento usado, e uma falha nesse nível derruba
o processo sem traceback. O comportamento em Qt (montagem, contexto, indicador,
proteção dos botões, fallback e as duas paletas) está coberto por teste
offscreen. Confirmado o funcionamento em uso real, basta inverter o padrão em
`janela_custom.VARIAVEL`.

## [0.18.0] - 2026-09-17

### Adicionado
- **Memória persistente** (`arquivos.py`): ao **abrir** e ao **salvar**, o
  sistema guarda uma cópia do arquivo em `arquivos/<CNPJ>/<LEIAUTE>_<AAAAMM>.txt`
  — mesma ideia do banco interno do PVA, adaptada a um editor que trabalha o
  texto direto. **Uma cópia por empresa + leiaute + período**, sempre
  substituída pela mais recente; o índice fica em `arquivos/indice.json`.
  - A cópia é feita a partir do **arquivo em disco**, nunca de texto gerado em
    memória: é byte a byte o que o usuário tem, com o latin-1 e as quebras de
    linha originais.
  - Falha ao arquivar (pasta sem permissão, disco cheio) **não interrompe**
    abrir nem salvar — o aviso vai para a barra de status.
- **Histórico de arquivos por empresa**, dentro de *Empresas*: lista os
  períodos arquivados, com leiaute, data da última atualização, caminho de
  origem e tamanho. Duplo clique **abre a cópia interna** (não o arquivo de
  origem, que pode ter sido movido); dá para excluir um período do histórico
  sem afetar o arquivo original.
- **Aviso ao salvar**: além de informar que a cópia do período foi atualizada,
  lembra de validar no PVA e **reabrir aqui a versão validada**, para a cópia
  interna passar a refletir o arquivo definitivo.
- **Cadastro manual de empresas**, sem precisar abrir um SPED antes
  (*Empresas → Nova empresa…*, pelo CNPJ). A lista reúne o que está em
  `empresas.json` com as empresas que já têm arquivo no histórico.

### Alterado
- **Menu Ferramentas agrupado por tipo de SPED**: submenus **EFD ICMS/IPI**,
  **EFD Contribuições (PIS/COFINS)** e **Gerais**. O submenu inteiro fica
  desabilitado quando não corresponde ao leiaute aberto — antes, a lista única
  obrigava a saber de cor quais ferramentas valiam para o arquivo.
- **Empresas saiu do menu e foi para a barra principal**, ao lado de *Salvar
  como*: é o cadastro que dá sentido às rotinas, e funciona sem arquivo aberto.
- **Conferência com XMLs dividida por tributo**: são duas ações, uma em cada
  grupo, cada uma conferindo só os campos do seu leiaute —
  `conferir_itens_xml(doc, nfes, movimento=…, tributo=…)`.
  - **ICMS/IPI:** VL_ITEM, VL_DESC, base e valor de ICMS, base e valor de
    ICMS-ST, IPI e CST_ICMS.
  - **PIS/COFINS:** VL_ITEM, VL_DESC, base, alíquota e valor de PIS e de
    COFINS, mais CST_PIS e CST_COFINS.
- **Separação de entradas e saídas**: seletor de **Movimento**
  (Entradas / Saídas / Ambas) dentro do diálogo, que refaz a comparação sem
  reler a pasta de XMLs. A **correlação de CFOP só se aplica às entradas** —
  numa saída própria o CFOP do XML é o mesmo do SPED, e a comparação viraria
  identidade.
- `.gitignore`: `arquivos/` não entra no controle de versão (SPED de clientes).

### Compatibilidade
- `conferencia.conferir_entradas_55` continua existindo como atalho para
  `conferir_itens_xml(movimento="entrada", tributo="ICMS")`, e a ação antiga
  segue conectada para arquivos `.ui` que ainda a declarem — apenas não aparece
  no menu novo.

## [0.17.0] - 2026-09-17

### Adicionado
- **Configuração por empresa** (`empresas.py`) — *Ferramentas → Empresa e
  rotinas…*. Cada empresa é identificada pelo **CNPJ do registro 0000** e guarda
  o que o arquivo sozinho não diz: **regime federal** (Simples / Presumido /
  Real), **regime de PIS/COFINS** (cumulativo / não-cumulativo / ambos),
  atividade, alíquotas de saída e de crédito e o CST a usar quando um crédito
  indevido é retirado. Cadastro em `empresas.json`, por máquina.
  - Empresa nova é **pré-preenchida** com o que o arquivo informa (nome, UF e o
    regime do registro **0110**), para conferência antes de gravar.
  - **Divergência de regime**: quando o 0110 do arquivo contraria o cadastro, o
    diálogo avisa — é o escriturado discordando do declarado.
- **Rotinas de conferência e correção por regime** (`rotinas.py`), extensíveis
  como as regras de `revisao.py`:
  1. **Alíquota de saída fora do regime** — itens de saída com CST 01
     (alíquota básica) fora da alíquota do regime. Corrige a alíquota e
     recalcula o valor.
  2. **Crédito indevido na entrada (cumulativo)** — entradas com CST de
     creditamento (50-56, 60-66) e valor lançado numa empresa que não tem
     direito a crédito. Retira o crédito (zera base, alíquota e valor) e troca
     o CST pelo configurado (70 por padrão).
  3. **Alíquota de crédito fora do regime** — entradas do não-cumulativo cuja
     alíquota de crédito difere da esperada, tipicamente por terem ficado com
     a alíquota de saída.
  4. **CST incoerente com o NCM** — reaproveita as tabelas da RFB; sem correção
     automática, porque o CST correto depende do produto.
  - Toda rotina roda primeiro em **conferência**, com relatório navegável
    (duplo clique vai ao registro) e exportável em CSV. A correção só é
    aplicada depois de confirmar, com a **contagem do que será alterado**, e
    atua exatamente sobre as ocorrências exibidas.

### Regras fiscais codificadas
- Cumulativo: PIS 0,65 / COFINS 3,00, **sem** direito a crédito.
- Não-cumulativo: PIS 1,65 / COFINS 7,6, com crédito.
- **Ambos os regimes**: as rotinas de alíquota **se abstêm** — a mesma alíquota
  pode estar certa ou errada na mesma escrituração.
- A verificação de alíquota só olha **CST 01**: o CST 02 é "alíquota
  diferenciada" e o 03 é por quantidade; cobrar deles a alíquota nominal seria
  falso positivo.

### Alterado
- `.gitignore`: `empresas.json` não entra no controle de versão — é dado do
  usuário, com CNPJ de clientes.

## [0.16.0] - 2026-09-17

### Adicionado
- **Tema visual próprio, claro e escuro** (`tema.py` + `icones.py`), portado do
  projeto **Backup Maximus** — os dois aplicativos passam a compartilhar a mesma
  identidade, com o acento **cobre** e as cores semânticas (ok/aviso/erro)
  separadas do acento, para que "atenção" nunca se confunda com "clicável".
  - Botão **Tema escuro / Tema claro** na barra de ferramentas; a preferência é
    gravada entre sessões (QSettings) e vale para a máquina, não para a sessão.
  - A folha de estilo trata o que este aplicativo realmente é — **grades**:
    linha alternada, linha de grade discreta, cabeçalho de coluna destacado,
    célula somente-leitura e seleção em acento suave que preserva a leitura do
    número.
  - Abas, barra de ferramentas, menu Ferramentas, campos, botões, barra de
    status, diálogos, rolagem e dicas seguem a mesma paleta.
  - Os ícones de "✓" e da seta do combo são **desenhados em runtime** na cor da
    paleta ativa: o QSS não aceita data URI e o indicador nativo se perde ao
    trocar o fundo.

### Alterado
- As cores dos relatórios deixaram de ser literais espalhados pela GUI
  (`#b00`, `#0a0`, `#b60`, `#1565c0`, o cinza da célula derivada) e passaram a
  vir de **tokens da paleta** — sem isso, ficariam ilegíveis no tema escuro.
  Restou um único `setStyleSheet` no aplicativo: o global.
- Rótulos de estado usam a propriedade dinâmica `role` (`ok`, `erro`, `aviso`,
  `dica`, `info`, `produto`), não estilo embutido.
- O nome da aplicação registrado no Qt era "Editor SPED"; passou a usar o
  `APP_NAME` de `version.py`.

## [0.15.4] - 2026-09-17

### Alterado
- **Conferência de entradas (NF-e 55): o frete e o seguro do item também entram
  no VL_ITEM.** Mesmo caso do `vOutro` tratado na 0.15.3 — o C170 não tem campo
  de despesa acessória por item (o leiaute só prevê VL_FRT, VL_SEG e VL_OUT_DA
  no C100, por documento), então o que a NF-e traz em `det/prod/vFrete` e
  `det/prod/vSeg` é escriturado dentro do valor do item. O critério passa a ser
  `vProd + vOutro + vFrete + vSeg`, com os três acessórios reunidos na constante
  `conferencia.ACESSORIOS_ITEM`.
- O parser de XML passou a extrair **`vFrete` e `vSeg` por item**; antes só lia
  os totais da nota (`ICMSTot`).

  Se a sua escrituração lançar frete e seguro nos campos do **C100**
  (VL_FRT/VL_SEG) em vez de dentro do item, a conferência passará a apontar
  divergência — nesse caso, ajuste `ACESSORIOS_ITEM` para conter apenas
  `"voutro"`.

## [0.15.3] - 2026-09-17

### Corrigido
- **Conferência de entradas (NF-e 55): o "outros" do item era acusado como
  divergência.** O C170 não tem campo de despesas acessórias por item — o
  leiaute só prevê VL_OUT_DA no C100, por documento —, de modo que o valor que
  a NF-e traz em `det/prod/vOutro` é escriturado **dentro do VL_ITEM**. A
  comparação usava apenas o `vProd` e apontava um falso positivo do tamanho
  exato do "outros" em cada item que o tivesse. Agora o critério é
  `vProd + vOutro` (função `conferencia.valor_item_xml`).
- O parser de XML passou a extrair o **`vOutro` por item** (`det/prod/vOutro`);
  antes só lia o total da nota (`ICMSTot/vOutro`).

  A conferência do **C190** não muda: lá o "outros" continua entrando pelo
  rateio das despesas acessórias do documento, que distribui exatamente o mesmo
  montante — os dois caminhos permanecem coerentes.

## [0.15.2] - 2026-09-10

### Corrigido
- **Tabelas de resultado exibiam apenas a coluna "Situação"/primeira coluna, em
  todas as linhas menos a última.** Os diálogos preenchiam a grade com a
  **ordenação já ligada**: cada `setItem` reordenava a tabela na hora, de modo
  que as células seguintes da mesma linha caíam em outra linha. Agora a
  ordenação só é ativada **depois** do preenchimento (idioma já usado no Modo
  Relatório e na verificação de CST por NCM). Afetava:
  - *Comparar inventário com a planilha* (bloco H);
  - *Validar C175 (modelo 65) com XMLs* — relatório de discrepâncias;
  - *Conferir C190 (ICMS) com XMLs*.

### Alterado
- Os relatórios em tabela passam a **abrir na ordem em que foram montados**
  (na comparação de inventário: divergentes, depois só no SPED, depois só na
  planilha; nas conferências, documento a documento; na verificação de CST por
  NCM, entradas antes das saídas), em vez de ordenados alfabeticamente pela
  primeira coluna. O clique no cabeçalho continua ordenando normalmente. O
  indicador de ordenação é zerado **antes** de a ordenação ser ligada, porque o
  QTableWidget reordena o próprio modelo — depois de ordenado não há como voltar
  à ordem original.

## [0.15.1] - 2026-07-05

### Adicionado
- **Comparar o inventário atual com a planilha** (botão *Comparar com
  inventário atual*, no diálogo de importação do bloco H): confronta o **H010 já
  escriturado** com a planilha por **código e quantidade**, **sem alterar o
  arquivo**. Mostra os itens que conferem, os de **quantidade divergente** (com
  a diferença), os que estão **só no SPED**, os que estão **só na planilha** e as
  somas de quantidade dos dois lados; exportável em CSV.

## [0.15.0] - 2026-07-05

### Adicionado
- **Importar inventário (bloco H) de planilha** (Ferramentas, EFD ICMS/IPI):
  lê uma planilha **XLSX/CSV** e gera o inventário — H001 (IND_MOV=0), **H005**
  (data, motivo e valor total) e um **H010** por item.
  - As colunas são **reconhecidas automaticamente** pelo nome do cabeçalho
    (código, descrição, unidade, quantidade, valor unitário, NCM, conta
    contábil…), com **mapeamento manual** ajustável para qualquer layout.
  - **Coerência com o 0200:** itens que ainda não existem no cadastro são
    criados (descrição, unidade, tipo e NCM da planilha) e os já cadastrados
    **não são duplicados**; unidades novas geram registros **0190**.
  - Botão *Conferir com o 0200* mostra, antes de importar, quantos itens são
    novos, quantos já existem, códigos repetidos na planilha e divergências de
    descrição/unidade/NCM em relação ao cadastro.

### Corrigido
- Registros criados pelo programa passaram a usar o **número real de campos** do
  tipo (moda dos registros do arquivo ou campos nomeados do layout). Os C170
  fictícios do fluxo do modelo 65 vinham sendo gerados com 40 campos em vez de
  37, o que geraria erro de layout no PVA.

## [0.14.2] - 2026-07-04

### Corrigido
- **Erro ao abrir "Trocar alíquotas de PIS/COFINS"** (AttributeError:
  '_registros_aliq_escopo'). O método auxiliar de seleção de registros por
  escopo havia perdido sua assinatura numa edição anterior (o corpo ficara como
  código inacessível), quebrando a sugestão de alíquota predominante e a própria
  troca. Restaurado. Feita também uma varredura (AST) em todos os módulos para
  garantir que não há outros métodos na mesma situação.

## [0.14.1] - 2026-07-04

### Alterado
- Os **C170 fictícios** gerados na validação do C175 (modelo 65) agora recebem
  **todos os dados do item do XML** — descrição, quantidade, unidade, CST/base/
  alíquota/valor de ICMS, ICMS-ST e IPI, além de PIS/COFINS — e não apenas os
  campos consumidos pelo C175. O parser de XML passou a extrair quantidade
  (qCom), unidade (uCom), NCM, alíquota de ICMS-ST e o grupo de IPI (CST, base,
  alíquota).

## [0.14.0] - 2026-07-04

### Adicionado
- **Validação e correção do C175 (NFC-e modelo 65) por item, via XMLs.** Novo
  fluxo no EFD Contribuições, em três passos:
  1. *Ferramentas → Validar C175 (modelo 65) com XMLs:* importa os XMLs das
     NFC-e e cria, em cada C100 modelo 65, registros **C170 fictícios** (um por
     item do XML) com valor, CFOP e PIS/COFINS — já que o modelo 65 é
     escriturado consolidado, sem itens. Abre um **relatório de discrepâncias**
     entre a soma dos itens e o C175 escriturado (exportável em CSV).
  2. *Correção por item:* os C170 fictícios podem ser editados no **Modo
     Relatório** (fonte C170), inclusive com Ctrl+D/Ctrl+R.
  3. *Ferramentas → Regenerar C175 (modelo 65) dos itens:* reconsolida o C175 a
     partir dos itens corrigidos e **remove** os C170 fictícios, restaurando a
     estrutura consolidada.

### Corrigido
- A função interna de consolidação do C175 a partir de itens havia perdido sua
  assinatura numa edição anterior (ficara como código inacessível); restaurada.

## [0.13.1] - 2026-07-04

### Adicionado
- **Recalcular totais do C100** (botão à esquerda de adicionar/remover, na grade
  de C100): recompõe os totais do documento a partir dos itens C170 — valor das
  mercadorias, desconto, base e valor de ICMS, ICMS-ST, IPI e (no EFD
  Contribuições) PIS/COFINS —, e recalcula o VL_DOC mantendo frete, seguro e
  outras despesas do C100. Recalcula o documento selecionado ou, se nenhum
  estiver selecionado, oferece recalcular todos os C100 com itens.

## [0.13.0] - 2026-07-04

### Adicionado
- **Revisão: C170 sem C190 compatível.** Nova regra que aponta itens (C170) cuja
  combinação de CST_ICMS, CFOP e alíquota de ICMS não aparece em nenhum C190 do
  mesmo documento — ou seja, itens que não foram consolidados no analítico.
- **Conferência de entradas: ir ao registro.** Duplo clique numa linha de
  divergência leva ao C170 correspondente no editor.
- **Fixar / fechar / resetar sub-abas de detalhe** (menu de contexto ao clicar
  com o botão direito numa sub-aba do painel de detalhe):
  - *Fixar aba:* o tipo de registro fixado passa a ser **exibido primeiro** ao
    trocar de registro pai (resolve o detalhe voltar sempre para a primeira aba
    disponível do documento).
  - *Fechar aba:* oculta aquele tipo de sub-aba até resetar.
  - *Resetar abas:* limpa ordem, fixação e abas fechadas do contexto.
  Sem aba fixada, o painel passa a exibir sempre a primeira aba na ordem atual.

## [0.12.2] - 2026-07-03

### Adicionado
- **Atalhos estilo Excel no Modo Relatório:** **Ctrl+D** preenche as células
  selecionadas com o valor da primeira linha da seleção (ou, se houver só uma
  célula, com a de cima) e **Ctrl+R** preenche à direita a partir da primeira
  coluna. Só afeta as colunas editáveis (as derivadas continuam intactas) e cada
  preenchimento é gravado no registro correspondente do SPED.

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

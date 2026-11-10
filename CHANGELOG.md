# Changelog

## [1.1.0-dev.20] — 2026-11-10

### Adicionado
- **Replicar a data no *Alterar datas emissão/saída (C100)*.** Novo modo
  *Replicar a outra data do documento*: a DT_E_S recebe a DT_DOC, ou a
  DT_DOC recebe a DT_E_S, em cada documento do filtro. Documento sem a data
  de origem fica como está.

### Alterado
- **Base de referência `2026.11.1`.** Reextraída do PVA atualizado: só
  tabelas estaduais do ICMS/IPI mudaram — informações adicionais da
  apuração do ES (versão 8, com as isenções prorrogadas pelo Convênio ICMS
  178/21) e do RJ, ajustes e benefícios do RJ, itens do IPM do RJ e
  códigos de receita de PE. O teste de equivalência com o PVA volta a
  passar.

## [1.1.0-dev.19] — 2026-11-10

### Alterado
- **Ambiente isolado pelo pyenv.** O projeto fixa o Python no
  `.python-version` (3.15.2, instalado pelo pyenv-win) e roda do próprio
  ambiente, `.venv`, com as dependências de `requirements.txt` — nada mais
  se instala no Python global. O gerador do executável cria o `.venv-exe`
  a partir do Python do `.python-version` (antes procurava um Python do uv
  e caía no do sistema). Os comandos da documentação passam de `py …` a
  `python …`, com o ambiente ativo.

## [1.1.0-dev.18] — 2026-10-30

### Alterado
- **Python 3.15.** O executável passa a ser gerado com o Python 3.15.2
  (era 3.14.6), e o programa roda do código-fonte no 3.15. O `PyQt6-sip`
  sobe para a 13.13.0, a primeira com pacote para o 3.15. O gerador
  (`ferramentas/gerar_executavel.py`) só aceita Python de versão final —
  o uv ainda distribui o 3.15 em beta — e compila o `pyodbc`, que não tem
  pacote pronto para o 3.15, com as Ferramentas de Build do Visual Studio.
  Executável de 26,7 MB, autoteste aprovado.
- **Base de referência `2026.10.2`.** Reextraída do PVA atualizado: duas
  tabelas do EFD Contribuições mudaram — produtos com alíquota zero (versão
  53: novas vigências para gasolina e etanol a partir de 10/10/2026) e
  monofásicos por unidade de medida (versão 41: a alíquota cheia da
  gasolina volta em 10/11/2026, e o diesel e as correntes de diesel ganham
  a vigência de 01/06/2026). Os testes de equivalência com o PVA voltam a
  passar.

## [1.1.0-dev.17] — 2026-10-27

### Alterado
- **Tema MegUI.** A interface passa a seguir o tema MegUI: os valores saem de
  `interface/tema_tokens.py`, gerado pelo gerador do MegUI (que recusa paleta
  reprovada em contraste), e o `tema.py` só monta a paleta e a folha de
  estilo a partir deles. O que muda na tela:
  - `ink_3` (texto desabilitado e placeholder) fica mais escuro e passa
    4,5:1 sobre todo fundo;
  - no tema escuro o acento volta ao vinho `#7D0E0E` nos preenchimentos
    (botão principal, caixa marcada), e foco, aba ativa, seleção e caixa
    marcada ganham uma linha própria mais clara (`accent_linha`), que passa
    3:1 sobre o fundo;
  - corpo de texto de 13 px nas duas densidades (era 12 e 11), título da
    tela inicial de 22 px, só os pesos 400 e 700 (o 600 virou 700);
  - todo espaçamento sai da escala do MegUI (4, 8, 12, 16, 24…), com o
    multiplicador 0,75 na densidade compacta; botão e campo têm altura de
    28 px (24 na compacta); barra de título de 32 px e rodapé de 24 px;
  - fonte: Atkinson Hyperlegible Next e IBM Plex Mono quando instaladas;
    sem elas, Segoe UI e Cascadia Mono/Consolas.
- O limite de campo, o acento como texto, as cores sobre o erro e a do nome
  do produto continuam próprios do programa (`tema._EXTENSAO`), porque o
  MegUI ainda não os declara.

## [1.1.0-dev.16] — 2026-10-18

### Adicionado
- **Base de referência.** O leiaute de cada versão, as tabelas oficiais
  (CST, CFOP, códigos de ajuste e de receita por UF, naturezas da receita,
  monofásicos e alíquota zero…) e os guias práticos passam a vir de uma base
  compilada na geração do programa (`base/` → `recursos/base_referencia.db`,
  1,8 MB), e não mais da instalação do PVA na máquina de quem usa. Com PVA
  antigo ou sem PVA nenhum, a pré-validação é a mesma — o que antes dependia
  da versão que a pessoa tinha instalado, e desligava metade das
  verificações quando não havia nenhuma. O PVA da máquina só serve ao *Abrir
  no PVA*. Fontes em texto em `base/`, revisáveis por diff; a compilação é
  reproduzível (mesmas fontes, mesmo banco, byte a byte); a versão é
  `AAAA.MM.n` (esta, `2026.10.1`). **A base entregue não traz a Tabela NCM
  Vigente** (`origem.ncm` do manifesto é `null`): a conferência de NCM
  vigente da classificação fica desligada (`vigente_ncm` volta `None`) até
  alguém extrair com `py -m consolidador extrair --ncm planilha.xlsx`.
- **Leiaute pela versão do arquivo.** Cada arquivo é conferido com a
  estrutura do `COD_VER` que declara no 0000 (ICMS/IPI 015 a 020,
  Contribuições 006), e não com a mais recente: um campo que só existe na
  versão nova não é cobrado de arquivo da antiga. Guardam-se as versões com
  vigência nos últimos 5 anos mais a atual (e as futuras que já tenham
  descritor). Versão fora da base é **avisada** e nada é acusado por
  estrutura de outra; a geração do SPED pelos XMLs usa a versão do período
  que gera. A porta `dominio.referencias` ganhou `estrutura(layout,
  versao=None)`, `versao_vigente` e `descricao`, e o helper
  `referencias.versao_do_leiaute(doc)` tira o `COD_VER` do 0000.
- **Configurações → Base de referência…** mostra a base em uso (versão,
  data, origem, leiautes e impressão digital SHA-256) e importa um pacote
  mais novo (`base_referencia-AAAA.MM.n.zip`) sem trocar de programa. A
  impressão digital é mostrada antes de aceitar, para comparar com a
  publicada; o pacote adulterado, igual ou mais antigo que a base em uso ou
  feito para um programa mais novo é recusado, dizendo o motivo. Vale a
  mais nova entre a embutida no executável e a importada (guardada na pasta
  de dados); a ilegível é ignorada, nunca apagada.
- **Consolidador** (`py -m consolidador extrair|guia|compilar|publicar`),
  pacote novo na raiz que roda na máquina de **quem compila**: `extrair`
  lê os PVAs instalados (e, com `--ncm`, a planilha de NCM vigente) e
  regrava `base/` (a revisão é o `git diff base/`); `guia` extrai o guia
  prático de um PDF e avança a versão da base no manifesto; `compilar`
  gera o banco; `publicar` gera o pacote para importação. Recusa
  extrair sem PVA e nunca grava base parcial. O `sped_tables` não o
  importa — `tests/test_arquitetura.py` confere.
- **Teste de equivalência** (`tests/test_equivalencia_base.py`): na máquina
  com PVA, a base compilada responde igual à instalação — versões,
  estrutura, tabelas e cada método da porta. Falhou depois de o PVA ser
  atualizado: a base ficou para trás, rode `py -m consolidador extrair`.
- **Autoteste do executável** (`--autoteste`): o item *base de referência*
  confere que a base embutida carrega e mostra versão, origem, registros e
  guia de cada leiaute; substitui *tabelas do PVA* e *guias práticos*. O
  `ferramentas/gerar_executavel.py` compila a base de `base/` antes do
  PyInstaller (nunca a que estiver por acaso em `recursos/`).

### Alterado
- **Nada do programa lê a instalação do PVA para validar, diagnosticar ou
  corrigir.** Saíram `infra/referencias_pva.py`, `infra/descritor_pva.py` e
  `infra/guias.py`; `tabelas_pva` virou `tabelas_oficiais` e `tabelas_rfb`
  virou `tabelas_ncm` (a interpretação passou a receber o texto das
  tabelas, não uma pasta); o parser do descritor
  e o `banco_pva` moveram-se para o `consolidador`; o extrator de guias
  saiu de `ferramentas/` para `consolidador/guias.py`, e os guias, de
  `recursos/guia_*.json` para `base/guias/`. `config` perdeu as funções de
  tabelas e descritor e guarda só onde está o PVA para o *Abrir no PVA*;
  `SPED_TABLES_PVA`, quando definida, é a raiz mesmo sem PVA dentro.
- **A suíte roda com a pasta do PVA apontada para um diretório vazio**,
  como o programa na máquina de quem não tem PVA, e liga a base de
  referência: o `compilar_se_preciso` recompila `recursos/base_referencia.db`
  (fora do git) quando ele falta ou quando `base/` é mais nova. Os testes de
  `test_guias` e `test_regras_guia` leem a base e deixaram de pular sem PVA;
  só o de equivalência precisa da instalação (`tests.PVA_REAL`).
- **Diagnóstico sem a base não aprova.** O cabeçalho do diálogo e a barra de
  status do diagnóstico automático diziam "nenhum problema nas verificações"
  também quando a base faltava ou a versão do arquivo estava fora dela — ou
  seja, aprovavam o que não foi conferido. Agora dizem o que rodou e o que
  faltou ("nenhum problema nas regras embutidas; a versão XXX do leiaute
  não está na base de referência"), e o cabeçalho do diálogo sai como aviso,
  não em verde.
- **Arquivo de leiaute mais novo que a base diz o remédio.** A base
  `2026.10.1` vai do ICMS/IPI 015 ao 020: a partir de 2027, todo arquivo
  com `COD_VER` 021 perderia as verificações de leiaute com uma mensagem
  que sugeria arquivo velho ("a base guarda os últimos 5 anos") e não dizia
  o que fazer. O adaptador marca `info["mais_nova_que_a_base"]` quando a
  versão do arquivo passa da maior guardada (comparação numérica; `COD_VER`
  que não é número nunca levanta); o Diagnóstico, no diálogo e na barra do
  automático, diz que a versão X é mais nova que a base em uso, que valeram
  só as regras embutidas e que é preciso **importar uma base mais nova em
  Configurações → Base de referência…**. Versão antiga demais mantém o texto
  dos 5 anos.
- **Geração pelos XMLs aponta período que a base não cobre.** Sem versão de
  leiaute vigente no período (`versao_vigente` devolve `None`) a geração
  continua na versão mais recente, como antes, mas agora registra um
  apontamento de revisão — que não bloqueia a gravação — dizendo que o
  leiaute do período não está na base e que valeu a mais recente.
- **Abrir no PVA avisa quando a pré-checagem não rodou.** Sem a estrutura do
  leiaute (base ausente ou sem a versão do arquivo) os achados que o PVA
  recusa na importação nem existem, e a lista vazia passava em silêncio.
  `envio_pva.pre_checagem_com_aviso` devolve também o aviso, e a pergunta
  que já existe antes de abrir o PVA o mostra — sem impedir o envio, que o
  PVA valida de qualquer jeito.
- **Itens do 0200 sem referência** diz a origem verdadeira dos campos que
  apontam para o 0200: o leiaute da versão do arquivo na base de
  referência, e, sem ele, a varredura pelo valor do `COD_ITEM`.
- **Base ilegível dá um aviso só, com a causa** (arquivo truncado, esquema
  mais novo, manifesto ruim): sobrando uma base legível, a ilegível é
  avisada e ignorada; sobrando nenhuma, a montagem dá a única mensagem, em
  vez de dois modais seguidos. O título dos avisos de dados deixou de ser
  "Arquivo de dados ilegível" (servia só para JSON do usuário) e virou
  "Aviso".
- **Pasta dos PVAs (para o Abrir no PVA)…** diz no rótulo que só serve ao
  *Abrir no PVA*.

### Removido
- A configuração *Tabelas da RFB* (pasta e arquivos do CST por NCM): as
  tabelas de alíquota zero e de monofásicos vêm da base, e o diálogo *CST
  por NCM* deixou de pedir caminho. **A Tabela NCM Vigente do Siscomex**,
  que antes a pessoa podia ligar apontando a planilha, passa a ser entregue
  ao consolidador (`py -m consolidador extrair --ncm planilha.xlsx`), não ao
  programa — e como a base `2026.10.1` foi extraída sem ela, a conferência de
  NCM vigente está **desligada** até a próxima extração com `--ncm`.

### Corrigido
- **`consolidador guia` regrava o manifesto.** O comando refazia
  `base/guias/*.json` sem tocar em `base/manifesto.json`: a versão da base e
  o `origem.guias` ficavam os antigos, o pacote saía com o mesmo `AAAA.MM.n`
  e conteúdo diferente, quem tinha a base embutida recebia "não é mais
  nova" ao importar, e duas bases distintas passavam a ter a mesma
  identidade (a impressão digital publicada deixava de identificá-la). Agora,
  depois de gravar o guia, registra `origem.guias` do layout e avança a
  `versao` pela regra do `extrair`; aceita `--data` e `--versao` com o mesmo
  sentido.
- **Importar uma base não vira exceção quando a gravação falha.** Disco
  cheio, antivírus ou pasta de rede ao gravar o temporário ou trocá-lo pelo
  destino são recusados com "Não foi possível gravar a base na pasta de
  dados (…). A base em uso continua valendo."; a limpeza do arquivo
  temporário não mascara mais o motivo.
- **Pacote de base ruim é recusa, não queda.** Fluxo `deflate` estragado,
  membro cifrado, compressão desconhecida e banco truncado em menos de uma
  página (o SQLite abria sem reclamar e só falhava na primeira leitura) são
  detectados antes de a base entrar em uso. A base numa unidade de rede
  mapeada abre (a URI não passa mais por `Path.resolve()`, que a trocava
  pelo caminho de rede).

### Notas
- **O que foi medido:** a suíte passa com a pasta do PVA vazia. Nos 7
  arquivos reais disponíveis (todos em ICMS/IPI 020 e Contribuições 006), os
  números do `gabarito.json` — revisão por regra e diagnóstico — deram
  **idênticos** aos do código anterior, que lia o PVA instalado, agora com a
  pasta do PVA vazia. Arquivo de versão anterior do leiaute passa a ser
  conferido pela própria versão, o que pode mudar o resultado dele **de
  propósito** (critério 3 da spec). O teste de equivalência garante que a
  base dá ao programa as mesmas respostas que o PVA de onde saiu.
- Um teste confere a versão por arquivo **sobre a base entregue**
  (`tests/test_versao_leiaute.py`): a mesma linha de `C120.COD_DOC_IMP` (que
  aceita 0 e 1 na 019 e 0, 1 e 2 na 020) e do `1310` (10 campos na 019, 11
  na 020) é acusada no arquivo 019 e não no 020.
- O `COBERTURA.md` foi regenerado a partir da base (guias e descritor): os
  números não mudaram.
- `tests/fabrica.py` declara `COD_VER` `020` (ICMS/IPI) e `006`
  (Contribuições) **de propósito**: são versões que a base guarda, e é
  contra elas que os arquivos sintéticos são conferidos.

## [1.1.0-dev.15] — 2026-10-15

### Adicionado
- **Fundir registros de chave repetida** (*Ferramentas → Corrigir*). Até
  aqui só o C190 tinha conserto para a chave repetida no mesmo documento
  (`MSG_CHAVE_EXISTE_NO_REGISTRO_ITEM`); o C175 da NFC-e no EFD
  Contribuições, o C181/C185, o D190 e os demais registros de totais ficavam
  para a grade. A fusão vale para todo registro cuja chave o leiaute declara
  e que só tem valores fora dela: o primeiro fica com a soma dos valores e
  das quantidades, os outros saem, e os totais do documento e da apuração
  não mudam. A prévia mostra cada grupo; o que não pode ser fundido diz por
  quê — registro que não é de totais (dois C170 com o mesmo `NUM_ITEM` são
  itens mal numerados), registro com filhos (M210) ou texto complementar
  diferente entre os repetidos (`INFO_COMPL`). O *Diagnóstico* e a revisão
  apontam para ela.

### Alterado
- **A chave compara número como número** também fora do C190: `1,65` e
  `1,6500` na alíquota do C175 são a mesma chave, como o PVA trata.
  Detecção, fusão e o *Recalcular C190* passam pelo mesmo agrupamento
  (`SpedDocument.chaves_repetidas`); a fusão de C190 da rotina do CSOSN,
  que era uma cópia à parte, saiu.
- **Fusão que encontra valor que não é número recusa antes de mexer**, como
  os demais cálculos que gravam — inclusive a rotina do CSOSN, que trocava o
  CST e depois somava lixo como zero. Campo de valor vazio em todos os
  repetidos continua vazio (antes virava `0,00`).

## [1.1.0-dev.14] — 2026-10-14

### Alterado
- **Nova assinatura visual.** O acento passa do cobre ao **vinho**
  (`#7D0E0E`) da família de ferramentas, com as regras de contraste dela:
  borda de foco de 2 px em campos, botões, abas e grades (antes o foco do
  teclado mal aparecia); célula e item selecionados com linha de acento
  além do fundo suave; limite de campo num cinza que passa 3:1; dicas em
  texto secundário legível (antes no tom restrito a desabilitado); dica de
  ferramenta em fundo invertido. Fonte por densidade em px.
- O resumo do arquivo e a prévia do inventário tinham **cores fixas no
  HTML** (azul, cinzas, laranja) que sumiam no tema escuro; saem agora da
  paleta. `tests/test_tema.py` reprova cor literal fora de `tema.py`.
- **Botão dentro de tabela** (as correções do *Diagnóstico* e da revisão)
  usava o padding de um botão comum e transbordava a linha; agora é
  compacto, com folga em volta da célula.
- `comum.definir_papel` e `comum.marcar_erro` substituem o
  `setProperty` + unpolish/polish repetido nos diálogos.

## [1.1.0-dev.13] — 2026-10-14

### Corrigido
- **Recalcular C190 não tirava a chave duplicada da NFC-e.** O recálculo
  refaz o analítico pelos C170, e o documento sem C170 (a NFC-e
  consolidada) era pulado — num arquivo real ficavam os 10 documentos com
  C190 repetido que o PVA recusa. Agora, sem C170, os C190 de mesma chave
  (CST + CFOP + alíquota) são **fundidos**, somando os valores.
- **O C100 acompanha o C190 refeito.** Base e impostos do C100
  (`VL_BC_ICMS`, `VL_ICMS`, `VL_BC_ICMS_ST`, `VL_ICMS_ST`, `VL_IPI`)
  passam a ser a soma dos C190 do documento, no recálculo em massa e no
  botão do documento na grade; campo vazio com soma zero continua vazio
  (a NFC-e deixa ST e IPI em branco). *Zerar ICMS próprio das compras com
  ST* usa o mesmo cálculo.

## [1.1.0-dev.12] — 2026-10-14

### Alterado
- **Menu por etapa do trabalho, sem funções repetidas.** O botão
  *Ferramentas* deixou de ter um submenu por leiaute (*EFD ICMS/IPI*, *EFD
  Contribuições*, *Gerais*) e passou a ter **Conferir**, **Corrigir**,
  **Recalcular**, **Gerar** e **Configurações**; a função que não vale para
  o leiaute aberto some do menu, em vez de ficar cinza. Saíram as
  duplicatas: *Conferir itens com XMLs* existia uma vez por tributo (agora
  pega o do leiaute), *Conferir entradas (NF-e 55)* era a mesma conferência
  sem o botão de corrigir, e *Revisar erros* repetia o *Diagnóstico* —
  que agora fica na barra e abre a revisão pelo botão *Revisar
  ocorrências…*. *Abrir no PVA* também foi para a barra.
- **Todas as janelas são soltas.** Conferências, prévias (regenerar
  entradas, cadastro pelo ERP, inventário), diagnóstico, rotinas, trocar
  alíquotas, alterar datas, a geração pelos XMLs e a decisão de produto
  abrem sem bloquear o programa: a janela principal e as outras ferramentas
  continuam clicáveis, e cada uma tem minimizar e maximizar. Os avisos de
  resultado não esperam o OK. Só as perguntas que precisam de resposta na
  hora continuam esperando.
- **XMLs lidos uma vez por arquivo.** A primeira função que usa XMLs
  pergunta de onde vêm (pasta ou banco do ERP); as seguintes reaproveitam o
  mesmo lote, sem pedir a pasta de novo. *Ferramentas → XMLs do período*
  troca a origem ou relê. Todas as funções passaram a ler as subpastas e a
  contar uma vez o XML repetido.
- **O aviso de resultado traz a etapa seguinte**: *Recalcular bloco M*
  depois de trocar alíquotas; *Recalcular C190* e *Diagnóstico* depois de
  corrigir pelo XML; a apuração depois de regenerar as entradas; *Remover
  C170 fictícios* e *Recalcular E110* depois do C190 em massa.
- Gerar pelos XMLs: *Abrir no editor* abre o arquivo na hora, com a janela
  da geração ainda aberta ao lado (antes só abria depois de fechá-la).

## [1.1.0-dev.11] — 2026-10-13

### Corrigido
- **Gerar SPED pelos XMLs não cadastrava no 0200 os produtos vendidos.**
  Só os itens das entradas iam para o 0200; os das NF-e e NFC-e emitidas
  pela empresa ficavam de fora (a NFC-e não leva C170, e o gerador só
  cadastrava o que passava pelo C170 de entrada). Agora todo produto
  movimentado entra, nos dois leiautes, com a unidade no 0190: o cadastro
  que a empresa declarou no SPED entregue (memória) e, para produto que a
  memória não conhece, o do XML — descrição, código de barras, unidade,
  NCM e **CEST** (agora lido do XML) e tipo 00, apontados numa linha só na
  revisão com a lista dos códigos.

## [1.1.0-dev.10] — 2026-10-13

### Corrigido
- **Regenerar C175 (modelo 65) fechava o programa** com `NameError:
  pendentes` — regressão da revisão de qualidade da 1.0.0-rc.2, que tirou a
  contagem e deixou o uso na mensagem. O teste das ações não pegou porque,
  sem C170 fictícios no arquivo, a ação sai antes de chegar à linha.
- Dois testes novos: a ação com fictícios presentes, e
  `test_nenhum_nome_indefinido` em `tests/test_estrutura.py`, que lê a
  tabela de símbolos do Python em todo arquivo do projeto e reprova nome
  usado e nunca definido — o erro que só aparece rodando.

## [1.1.0-dev.9] — 2026-10-13

### Corrigido
- **Gerar SPED pelos XMLs (EFD Contribuições) não criava o M400/M410 nem o
  M800/M810** — obrigatórios quando há receita com CST 04 a 09 (monofásico,
  ST, alíquota zero, isenção, sem incidência, suspensão). Agora:
  - um M400/M800 por CST, com o total da receita do CST pelo mesmo
    somatório que a conferência e o PVA usam (`receita_por_cst`);
  - a **natureza da receita** (M410/M810) sai do NCM de cada item do XML
    pela tabela do CST no PVA (4.3.10 a 4.3.16, o prefixo mais longo,
    respeitando o EX da TIPI); sem casamento — a 918 das bebidas frias, por
    exemplo, não tem NCM na tabela —, vale a natureza que a empresa usou
    naquele CST no SPED entregue (aprendida na memória), e é apontada; sem
    nenhuma das duas, **bloqueia** a gravação;
  - o total do CST é repartido entre as naturezas pela proporção dos itens,
    com o rateio de sempre: o M410 fecha com o M400 ao centavo;
  - a conta contábil (COD_CTA) do M400/M410 é a que a empresa usou, se
    estiver no 0500 do arquivo gerado.
- A memória da empresa passa a guardar a natureza de cada CST e as contas
  do M400/M410 e M800/M810 do SPED entregue: **aprenda de novo** com um
  SPED do Contribuições para preencher.

## [1.1.0-dev.8] — 2026-10-13

### Adicionado
- **EFD ICMS/IPI → Zerar ICMS próprio das compras com ST (1403/2403, CST
  x10/x70).** Na compra para revenda com ICMS retido por substituição
  tributária, o imposto da cadeia já foi recolhido: não há crédito do ICMS
  próprio a apurar. A função acha os C170 de **entrada** com CFOP 1403 ou
  2403, CST terminado em 10 ou 70 e base, alíquota ou valor de ICMS
  preenchidos, mostra quantos itens, notas, base e crédito, e, confirmado:
  zera base, alíquota e valor do item; refaz o C190 das notas tocadas (o
  `consolidar_c190` de sempre); põe no C100 a base e o ICMS somados do
  C190; e tira do `VL_TOT_CREDITOS` do E110 o crédito retirado,
  recalculando os saldos (`SpedDocument.zerar_credito_icms_st`). CST 60 e
  saídas não são tocados.
- Num arquivo real (cliente A): 593 itens em 77 notas com a alíquota
  preenchida e base e valor zerados — corrigidos sem mudar crédito, com o
  C190 continuando a fechar com os itens.

## [1.1.0-dev.7] — 2026-10-13

### Corrigido
- **Gerar SPED pelos XMLs descartava sozinho o que tinha data de outro
  mês.** Cupom em contingência transmitido no mês seguinte é documento
  extemporâneo e precisa entrar — mas só a pessoa sabe quais são. Agora os
  documentos fora do período aparecem na aba *Documentos*, **desmarcados** e
  destacados ("fora do período: marque se extemporâneo"). Marcado, entra:
  - com **COD_SIT 01** (07 no complementar);
  - no ICMS/IPI, com a data real do XML, e o ICMS da saída vai para o
    **DEB_ESP** do E110 (não para os débitos do período) e para o E116 — o
    mesmo que o *Recalcular apuração do ICMS* calcula;
  - no EFD Contribuições, com o primeiro dia do período (o PVA de lá recusa
    data de outro mês mesmo com COD_SIT 01).
  Sem marcar, continua de fora e listado em *Fora do período e ignorados*.

## [1.1.0-dev.6] — 2026-10-09

### Corrigido (geração do executável)
- `ferramentas/gerar_executavel.py` reaproveitava um `.venv-exe` cujo
  Python de base (o do uv) não existia mais e o PyInstaller morria com
  "did not find executable at …". Agora o ambiente é conferido rodando o
  Python dele e, quebrado, é recriado; o Python do uv é procurado pelo
  `uv python find`, pela pasta versionada e, faltando, instalado.

### Adicionado
- **Corrigir pelo XML** na tela *Conferir itens com XMLs* (antes só havia
  *Exportar CSV*). Grava no C170 o valor do XML das linhas selecionadas —
  ou de todas, sem seleção —: VL_ITEM na composição que o documento usa,
  desconto, bases, alíquotas, impostos, e o CFOP quando a correlação aponta
  um único CFOP de entrada. O CST não é corrigido (o do XML é o do
  fornecedor). C190 e totais do C100 não são refeitos ali: num ERP que soma
  IPI e ST ao item, o total recalculado contaria o imposto duas vezes; a
  tela diz para rodar a revisão (`conferencia.corrigir_pelo_xml`). Depois
  de corrigir, a conferência é refeita na hora.
- **MySQL no executável** (PyMySQL 1.2.3). O adaptador agora fala com o
  MySQL 5.1 dos ERPs antigos: charset padrão `utf8` (o 5.1 não conhece o
  `utf8mb4`) e transação comum quando o servidor não tem `START
  TRANSACTION READ ONLY` (antes do 5.6.5). MySQL 8 com
  `caching_sha2_password` recebe a explicação de como criar o usuário de
  leitura.

### Corrigido
- **Valor do XML na conferência de itens ainda sem os impostos.** A
  1.1.0-dev.3 reconhecia IPI e ICMS-ST somados ao VL_ITEM só quando o valor
  batia ao centavo, e sem o **FCP retido por ST** (`vFCPST`, agora lido do
  XML), que o ERP soma ao custo junto do ST. Sem composição exata, a
  conferência voltava ao `vProd` puro e acusava todo item. Agora:
  - o FCP-ST entra junto do ICMS-ST, e o VL_ITEM **líquido do desconto**
    também é uma composição reconhecida;
  - vale a composição que explica mais itens e, no empate, a de menor
    diferença; **sem nenhuma exata, a que mais se aproxima** — o *Valor
    XML* mostrado já traz os impostos, e a diferença que sobra (centavos de
    custo, por exemplo) é a de verdade.

## [1.1.0-dev.5] — 2026-10-09

### Alterado
- **Executável enxuto, gerado de um ambiente mínimo do uv:** de 64 MB para
  **24,4 MB**, com o `--autoteste` inteiro passando.
  - `ferramentas/gerar_executavel.py` cria `.venv-exe` com o Python do uv,
    instala só `requirements-executavel.txt` (versões fixas; o `uv pip
    sync` tira o que não está na lista), roda o PyInstaller e o autoteste.
    Do Python do sistema, o PyInstaller arrastava tudo o que estivesse
    instalado lá (41 MB só pela troca de ambiente).
  - O `SPED Tables.spec` tira o que o programa não carrega: o
    `opengl32sw.dll` (20 MB — a interface é Widgets, desenha sem OpenGL),
    `Qt6Pdf`, `Qt6Network`, `Qt6Svg`, os plugins do Qt salvo `qwindows`,
    `qmodernwindowsstyle` e `qico`, as traduções do Qt em ~40 línguas (a
    pt-BR vai à parte), e do Python `ssl`/`libssl`, `_hashlib`/`libcrypto`
    (o SHA-1/SHA-256 do login do Firebird vem do próprio Python), `lzma`,
    `bz2` e `zstd`. Saíram 36,6 MB, listados em
    `build/manifesto_executavel.txt` a cada geração.
  - UPX desligado: corrompe plugin do Qt e dispara antivírus.

## [1.1.0-dev.4] — 2026-10-08

### Adicionado
- **Gerais → Regenerar entradas pelos XMLs** (`dominio/regeneracao.py`),
  nos dois leiautes. Refaz as notas de entrada (C100, C170 e C190) pelos
  XMLs da pasta ou do banco do ERP:
  - a **escrituração de cada produto** (código próprio, CFOP de entrada,
    CST, crédito, CST/alíquota de PIS e COFINS, conta) é aprendida do
    **próprio arquivo aberto**, sobre uma cópia da memória da empresa;
    quantidades, valores e impostos vêm do XML;
  - os documentos saem do gerador de sempre (`geracao.gerar_icms` /
    `gerar_contrib`): C190 e totais do C100 pelos mesmos cálculos dos
    botões;
  - nota com XML é trocada (casada pela chave), nota que o arquivo não tinha
    é incluída, nota sem XML na pasta **fica** como está, e o cadastro novo
    (0150, 0190, 0200, 0400, 0500) entra junto;
  - nota com item que sairia inválido (CFOP de entrada desconhecido, CST de
    PIS ausente) **não** é regenerada, e o original fica;
  - **prévia antes de gravar:** quantos valores mudam em cada campo (com
    `0`, `0,00` e vazio tratados como o mesmo valor), o que precisa de
    revisão e o que ficou de fora. A apuração (E110 / bloco M) não é
    refeita: a mensagem final diz qual botão rodar.
- CT-e (D100) e saídas ficam de fora por ora. Ação com `pronta=False` até
  passar por um mês real.

## [1.1.0-dev.3] — 2026-10-08

### Corrigido
- **Conferência de itens com os XMLs ignorava os impostos somados ao
  item.** Muitos ERPs gravam no VL_ITEM da entrada o custo da mercadoria,
  `vProd + vIPI + vICMSST`, e a conferência comparava só com o `vProd`
  (mais as despesas acessórias), acusando divergência em todo item com IPI
  ou ST. Agora a composição do VL_ITEM é reconhecida por documento —
  despesas acessórias, IPI e ICMS-ST, em qualquer combinação — pela que
  explica mais itens (`conferencia.criterio_valor_item`). Um item errado
  continua apontado sem contaminar os outros, e a divergência diz a
  composição usada ("VL_ITEM com IPI + ICMS-ST"). Vale para *Conferir
  entradas* e *Conferir itens com XMLs* (ICMS/IPI e PIS/COFINS).

## [1.1.0-dev.2] — 2026-10-07

**Integração com o banco do ERP.** Pedido do usuário: ler Firebird 2.5 e
5.0, SQL Server, DBF e MySQL, com um perfil por sistema guardado na
configuração, em que a pessoa aponta a tabela e a coluna de cada
informação de forma simples. Ações com `pronta=False` até passarem por um
ERP de verdade.

### Adicionado
- **Gerais → Sistemas ERP.** Duas abas:
  - *Sistemas (perfis de ERP)*: o tipo de banco e, para produtos,
    participantes, XMLs e estoque, a tabela e a coluna de cada
    informação, escolhidas das listas que o próprio banco devolve.
    *Sugerir pelo nome* preenche o óbvio (`CLASFISCAL` → NCM, `EAN` →
    código de barras), cada coluna mostra um exemplo do conteúdo e
    *Pré-visualizar* lê as primeiras linhas como o programa vai
    recebê-las. Para ERP que espalha a informação em várias tabelas, há a
    consulta própria, que aceita **um único `SELECT`**.
  - *Conexões*: o banco de cada cliente (servidor, arquivo `.fdb`, banco
    do SQL Server, pasta dos DBF), o código da empresa quando o banco
    guarda várias e o CNPJ vinculado. Abrir o SPED da empresa já sabe de
    onde buscar. *Testar conexão* mostra a versão do servidor.
- **Atualizar 0200 (produtos) e 0150 (participantes) pelo ERP**, com a
  mesma prévia campo a campo da correção pela planilha: valor vazio não
  apaga nada; CNPJ com dígito errado e município sem 7 dígitos nascem
  desmarcados. O 0150 casa pelo `COD_PART`; quando o ERP usa outro código,
  casa pelo CNPJ/CPF, se ele for único dos dois lados. IE "ISENTO" vira
  IE vazia (o PVA valida a inscrição pela UF), e CNPJ e CPF numa coluna só
  são separados pelo tamanho.
- **Inventário pelo ERP:** botão *Ler do ERP…* no *Importar inventário*. É
  o estoque na data do inventário (com coluna de data, a posição mais
  recente até ela; sem data, os depósitos somados), completado com o
  cadastro de produtos para criar o 0200 dos itens novos.
- **XMLs do banco:** quando a empresa tem conexão com XMLs, toda leitura de
  XMLs (conferências, C175, C170 fictícios, datas, redução de base)
  pergunta se vêm de uma pasta ou do banco, no período do arquivo. O
  conteúdo pode estar guardado como texto, bytes, gzip, zlib ou base64, e
  é lido em paralelo como a pasta.
- Adaptadores (`infra/bancos.py`): Firebird pelo `firebirdsql` (puro
  Python; tenta SRP com canal cifrado e cai para o `Legacy_Auth` do 2.5),
  SQL Server pelo `pyodbc` (o melhor driver ODBC instalado; sem usuário,
  entra com a conta do Windows), MySQL pelo `pymysql` (opcional), SQLite e
  **DBF por leitor próprio** (`infra/dbf.py`: dBase III/IV, Clipper,
  FoxPro e Visual FoxPro, memo `.dbt`/`.fpt`, registros apagados de fora,
  página de código do cabeçalho, cp850 por padrão).
- **Só leitura:** o programa monta apenas `SELECT`, abre a transação como
  somente leitura onde o driver deixa (Firebird, MySQL, SQLite) e nunca
  confirma nada.
- **A senha não fica legível no disco:** vai para `sistemas_erp.json`
  cifrada pela DPAPI do Windows (`infra/segredos.py`). JSON trazido de
  outra conta ou máquina chega sem a senha, e a tela pede de novo.
- Autoteste do executável: item *drivers dos bancos de ERP*.

### Alterado
- `SpedDocument.atualizar_0200(linhas, campos)`: a correção do cadastro
  saiu de dentro do `importar_inventario_h010`, e planilha e ERP usam a
  mesma função.
- `xml_fiscal.montar_lote` e `nfes_de`: a montagem do lote (repetidos,
  cancelamento por evento) é a mesma para a pasta e para o banco.

### Conferido
- SQL Server 2019 local, pela conta do Windows (banco `master`, só
  leitura): conectar, listar tabelas e ler amostra. Firebird e MySQL só
  pelo SQL que o adaptador monta, porque não havia credencial de teste. Os
  testes contra servidor rodam quando o ambiente aponta um (TESTES.md).

## [1.1.0-dev.1] — 2026-10-07

**Leitura de XMLs em paralelo.** Pedido do usuário: toda função que lê uma
pasta de XMLs estava ficando lenta. Medido com 5.000 NFC-e de 10 KB num
processador de 16 núcleos:

| modo | primeira leitura | com cache |
|---|---|---|
| um por vez (até a 1.0.0-rc.2) | 24,7 s | 2,5 s |
| threads | 4,3 s | 2,7 s |
| **processos (agora)** | **4,2 s** | **0,8 s** |

Na primeira leitura o tempo é espera de disco e do antivírus, que examina
cada arquivo ao abrir; com cache, é a análise do XML, que no Python só
processos dividem.

### Adicionado
- **`infra/paralelo.py`**: reparte uma lista de itens em pedaços de 64
  entre processos (um a menos que os núcleos, até 16; `trabalhadores` no
  `configuracao.json` muda isso) e devolve o resultado **na ordem
  original** — é a ordem que decide qual de dois XMLs repetidos vale. Abaixo
  de 256 itens usa threads (subir processos custaria mais do que rende); se
  o sistema não deixar subir processos, segue com threads e registra o
  aviso no log.
- **`aplicacao/leitura_xml.py`**: o caminho único de leitura de pasta. Usam
  esse caminho: *Gerar SPED pelos XMLs* (ler e aprender), *Importar XMLs (C175)*,
  *Validar C175*, *C170 fictícios*, *Conferir entradas*, *Conferir itens*,
  *Conferir C190*, *Datas pelo XML* e *Redução de base pelos XMLs de compra*.
- **Barra de andamento com Cancelar** (`comum.em_segundo_plano`) em todas
  essas leituras: "Lendo os XMLs… 1.234 de 5.000". A leitura roda fora da
  thread da interface, e a janela não congela mais.
- Autoteste do executável: item *leitura paralela de XMLs*. O processo
  filho é o próprio executável, e o item confere que os processos sobem
  (sem cair para threads) e que o resultado é igual ao da leitura um por um.

### Alterado
- `xml_fiscal.ler_pasta_fiscal` e `ler_pasta` recebem o leitor (`ler=`):
  listar (`listar_xmls`), ler (`ler_arquivos`, a unidade de trabalho que
  vai para os processos) e montar o lote ficaram separados. O resultado é
  o mesmo da 1.0.0-rc.2, conferido em teste com XML quebrado, repetido,
  em subpasta e cancelado por evento.
- O lançador (`sped_editor.py`) chama `multiprocessing.freeze_support()`
  antes de carregar a interface: no executável, sem isso cada processo da
  leitura abriria uma janela do programa.

## [1.0.0-rc.2] — 2026-10-07

**Os guias práticos como fonte.** Pedido do usuário antes da 1.0.0: seguir
os manuais dos dois SPEDs (Guia Prático EFD ICMS/IPI 3.2.4, de 30/07/2026,
e EFD Contribuições 1.35). Exceção ao congelamento do rc.1, registrada no
`ROADMAP.md`.

### Adicionado
- **Os dois guias, extraídos** por `ferramentas/extrair_guias.py` para
  `recursos/guia_icms.json` (268 registros) e `recursos/guia_contrib.json`
  (201): título, objetivo, *Validação do Registro*, nível, ocorrência e, de
  cada campo, *Valores válidos*, *Preenchimento* e *Validação*. Viajam no
  executável.
- **Ajuda de campo na grade.** A dica do cabeçalho de cada coluna mostra o
  que o guia e o descritor do PVA dizem do campo (tipo, tamanho,
  obrigatoriedade, valores válidos com o significado, preenchimento,
  validação). **F1** (ou o menu de contexto) abre a ajuda do registro
  inteiro, rolada até a coluna atual. Texto do guia que é de um leiaute
  mais novo que o do PVA instalado (o `IND_BENEFICIO` do E111) não vira
  ajuda do campo errado.
- **Regras do guia com as condições e as tolerâncias do PVA**
  (`dominio/regras_guia.py`), na revisão e no diagnóstico: CFOP × operação
  (C170/C190/C590/D190/D590, NFC-e só 5, itens com o mesmo primeiro
  dígito); combinação CST/CFOP/alíquota entre C170 e C190 nos dois
  sentidos; C190 = soma dos C170; totais do C100/D100 = soma dos
  analíticos; VL_MERC; datas até o fim do período; mês do 0000; CNPJ/CPF
  (dígito, exclusão mútua, participante do Brasil), município na UF; chave
  da NF-e/NFC-e (dígito, modelo, série, número, CNPJ e UF na emissão
  própria); contagens X990/9900/9999; apuração do E110 (ajustes do E111,
  saldos, E116); H005; quantidade do C170; VL_PIS/VL_COFINS = base ×
  alíquota; 0190.
  - As **condições** vêm das consultas SQL do próprio PVA
    (`descritor/comum/queries/queries.xml`, no `.jar` do descritor) e
    dizem o que o guia não diz: o VL_MERC só é cobrado **abaixo** da soma
    dos itens; NF-e de emissão própria e NFC-e ficam fora da conferência
    C190 × C170; CFOP só em documento 00/01.
  - As **tolerâncias** são as das classes do PVA: R$ 0,50 nas somas do
    ICMS/IPI (`EnumComparadoresSql.TOLERANCIA`) e R$ 0,99 no VL_PIS/
    VL_COFINS, que lá é só advertência.
  - Cada regra declara os validadores do descritor que reproduz, e o
    diagnóstico deixa de listá-los como "só o PVA verifica".
- `--autoteste` confere que os guias viajaram no executável.
- **`COBERTURA.md`** (`ferramentas/cobertura_guias.py`): validações do guia
  e validadores do PVA por registro, e quantos o programa reproduz — hoje
  60 de 739 no ICMS/IPI e 32 no Contribuições.

### Corrigido
- **Leiaute divergente do PVA instalado**, com coluna errada na grade e
  validação no campo vizinho: C870 com CST e CFOP trocados; C177 (o do
  selo do IPI, revogado), C181, C185, C186, C330, C380, C430, C480, C815,
  C880, E310 e E312 com campos a menos ou fora de ordem; nomes errados no
  1010 (`ND_GIAF1`), C113, D530 e D600. No Contribuições: C188 (`CFOP` no
  lugar de `IND_PROC`), C505/C605 (`ALIQ_PIS`/`VL_PIS` num registro de
  COFINS), F560, C199, 0111 e o `CHV_DOC_E` do D500. `tests/test_guias.py`
  confere a estrutura contra o descritor instalado.
- **Campos comentados no descritor eram lidos como reais.** O PVA guarda
  campos excluídos dentro de `<!-- -->` (o `IND_ST` do 1010, com o mesmo
  `n` do campo seguinte); e um `n="17'"` (D750) ficava sem posição.
- **Campo com nome interno do PVA não era validado.** O descritor chama de
  `ENDERECO` o `END` do guia, de `VL_OPER` o `VL_OPR` do C175, de
  `ALIQ_PIS_PERC` o `ALIQ_PIS` do C170; obrigatoriedade, domínio, chave e
  referência procuravam o campo por esse nome e pulavam em silêncio. O
  descritor agora é alinhado ao leiaute **por posição**
  (`referencias.alinhar_ao_leiaute`).
- **COD_OR do E116 contra a tabela errada.** Apontava para a tabela de
  códigos de receita da UF e só não acusava nada porque o descritor trazia,
  num comentário, uma enumeração que era lida como se valesse. Agora é a
  `OBR_ICMS_RECOL` do PVA.
- **Saldo credor do E110 perdia a dedução excedente.** Com saldo apurado
  100 e dedução 150, o recálculo transportava 0; pelo campo 14 do guia,
  são 50. Recálculo e conferência usam a mesma função
  (`SpedDocument.saldos_e110`).
- A chave de NF-e da fábrica de testes tinha dígito verificador inválido.

### Corrigido na revisão de código
- **Largura do registro pelo descritor** vinha do atributo `n`, que o PVA
  repete no 0220 e no C890: todo 0220 com código de barras virava "mais
  campos que o leiaute" — achado que **impede a importação** na
  pré-checagem — e o gerador pelos XMLs cortava o COD_BARRA. Agora é a
  posição do último `<campo>`.
- **Diagnóstico sem o PVA instalado** pulava as regras do guia, que não
  dependem dele.
- **Recalcular C190** (revisão e diagnóstico) só refazia documento com
  redução zerada ou NFC-e com fictícios: anunciado para C190 que não
  confere com os itens, não fazia nada. Passa a refazer também esses.
- **Chave da NF-e própria no Contribuições** conferida contra a UF e o
  CNPJ do estabelecimento (C010/0140), não do 0000 — nota de filial noutra
  UF era acusada. Regime especial (COD_SIT 08) fica fora, e a chave de
  **terceiros** passa a ser conferida com o CNPJ/CPF do participante.
- **Débitos do E110**: CFOP 5605 sai e 1605 entra (E110, campo 02 do guia);
  cada E110 recebe os documentos do período do seu E100, como na consulta
  do PVA — com dois E100, o recálculo jogava o mês inteiro no primeiro.
- Saída com DT_E_S depois do período conta uma vez só: o limite superior
  é da regra do guia, para todo C100 (inclusive o extemporâneo, que antes
  escapava das duas verificações), e o inferior da saída, da verificação
  própria.

### Simplificação e desempenho (revisão de qualidade)
- **Modo em lote no documento** (`SpedDocument.lote()`): inserções e
  remoções em massa medem a largura uma vez por tipo e renumeram a árvore e
  o bloco 9 uma vez, no fim. Refazer o C190 de 2.000 NFC-e caiu de 25 s para
  0,2 s; gerar os C170 fictícios de 300 NFC-e, de ~30 s para 0,06 s (o custo
  era quadrático: num mês real, minutos com a tela parada).
- **Uma fonte para cada cálculo que gera e confere:** `chave_c190` (CST,
  CFOP, alíquota — "18" e "18,00" são o mesmo grupo, inclusive na detecção
  de chave repetida), `data_aaaammdd` (havia seis cópias), `e110_esperado`
  (o recálculo do E110 agora também grava os totais de ajuste pelos E111,
  que a regra cobrava e o botão não corrigia) e `documentos_para_refazer_c190`
  (o botão e os roteiros refazem os mesmos documentos, inclusive os de chave
  repetida).
- O **E116** virou regra própria, de correção manual: o recálculo do E110
  não divide o valor entre as obrigações.
- **CST x02 sem alíquota** se divide no diagnóstico: o CSOSN de entrada vai
  para a rotina que o converte; combustível de verdade ou saída, para
  correção manual.
- O **COD_OR do E316** (datasource `COD_OR_E316`) voltou a ser validado.
- Diagnóstico e revisão montam os botões pelo mesmo mapa de módulos; o
  "Datas e extemporâneos pelos XMLs" ganhou botão no diagnóstico.
- Classificação por NCM uma vez por (NCM, Ex), não por C170; natureza da
  receita e guias com cache no adaptador; uma passada só pelos débitos do
  E110 e pelas regras do C190. Diagnóstico do maior arquivo real: 0,75 s.

### Desempenho
- `SpedDocument._ix` com cache: montar a lista de colunas a cada consulta
  custava mais que as regras. O diagnóstico do maior arquivo real caiu de
  3,1 s para 1,1 s, já com as regras novas.

### Gabarito dos arquivos reais
Muda só a revisão: entram os rótulos das regras do guia (zero em todos,
salvo o abaixo) e sai *C170 sem C190 compatível*, substituída pela regra
da combinação com as condições do PVA (zero em todos). No ICMS/IPI de
agosto do cliente A, **+6 CFOP incompatível**: os CT-e de entrada com CFOP
5353 no D190 — os mesmos 6 `MSG_CFOP_D190` que o PVA gravou no banco da
validação desse arquivo. Nos demais, nenhuma regra nova acusa o que o PVA
aceita.

## [1.0.0-rc.1] — 2026-10-02

Candidata à primeira release. **Congelada:** daqui até a 1.0.0, só
correção.

### Adicionado
- **Licença GNU GPL versão 3** (`LICENSE`), a mesma do PyQt6 que vai dentro
  do executável. README, seção 6.

### Adicionado (fora da 1.0.0, `pronta=False`)
- **C170 fictícios da NFC-e também no EFD ICMS/IPI**, para o *Recalcular
  C190 em massa* refazer o analítico das NFC-e pelos itens do XML.
  - *Gerar C170 fictícios da NFC-e (65) com XMLs…* e *Remover C170
    fictícios da NFC-e (65)*, no menu do ICMS/IPI.
  - O recálculo em massa passa a incluir as NFC-e com fictícios. Antes ele
    só olhava a redução zerada e, num arquivo sem esse defeito, não fazia
    nada mesmo com os itens no lugar.
  - Item com CSOSN no lugar do CST é contado e avisado.
- **Salvar com C170 em NFC-e pede confirmação**, nos dois leiautes; no
  ICMS/IPI oferece remover os fictícios antes de gravar.

Mês real (junho de 2026, numa cópia do ICMS/IPI entregue): 318 de 318
NFC-e casadas, 1.137 itens. Os 531 C190 refeitos têm **VL_OPR, base e
ICMS idênticos** ao entregue; só o `VL_RED_BC` muda (40.996,80 →
87.843,85, em 256 NFC-e), que é a diferença já conhecida entre a fórmula do
ERP e a do Guia (`VL_OPR − VL_BC_ICMS`). Nenhum achado impede a importação.
Falta o ensaio no PVA.

### Situações de contribuinte que não eram tratadas (cliente B, setembro)
Os dois SPEDs de setembro de um supermercado (cliente B), com os XMLs das
NFC-e e NF-e, validados no PVA de ensaio. O PVA acusou no ICMS/IPI: E116
sem código de receita (1), redução de base x70 zerada (47), município do
participante (2) e CST final 2 sem alíquota (31).

#### Adicionado
- **Cadastro da empresa** com o código de receita do E116 (seletor com a
  tabela da UF do PVA) e as regras das **entradas do Simples**: conversão
  ligada/desligada, origem, tabela CSOSN → situação e situação da compra
  com ST (CFOP 1403/2403).
- Rotina **CSOSN do Simples no CST do ICMS** (os dois leiautes): troca o
  CSOSN pelo CST do cadastro nos C170 e, no ICMS/IPI, nos C190 — somando os
  que passem a ter a mesma chave. No arquivo real: 78 registros no
  ICMS/IPI, 62 no Contribuições; os 31 "CST final 2" somem.
- Rotina **Código de receita em branco**: E116 pelo cadastro, M205/M605
  pelo campo do M200/M600.
- *Empresa e rotinas…* passa ao menu **Gerais**: as rotinas valem para os
  dois leiautes.
- **Datas e extemporâneos pelos XMLs**: 3.578 NFC-e
  emitidas de junho a agosto e autorizadas em setembro estavam com a data
  de setembro no ICMS/IPI (e com a data real só na saída, no
  Contribuições); mais 562 de setembro com o dia trocado. A correção grava
  a data do XML e COD_SIT 01 — e o PVA não acusa a data fora do período.
- **Recalcular apuração do ICMS (E110)** e a verificação
  *E110 com débitos diferentes dos analíticos*: o ICMS da saída
  extemporânea é débito especial. No arquivo real, R$ 4.889,67 saíram do
  total de débitos para o `DEB_ESP` — exatamente os 19.108,92 e 4.889,67
  que o PVA esperava. Nos cinco arquivos reais do gabarito a verificação
  dá zero: o cálculo reproduz o E110 entregue.
- **Redução de base do C190 pelos XMLs de compra**: para o CST 070 de
  entrada, sem base no arquivo. Aceita também o XML que o ERP exporta da
  entrada — sem chave, com o fornecedor no `dest` e só o `pRedBC` —,
  casado pelo CNPJ do fornecedor e o valor do documento (os 50 do cliente
  casaram um a um). No arquivo real: 41 → 6; os 6 que sobram são itens que
  o próprio ERP exportou com CST 70 e `pRedBC` zerado, e um sem XML.
- Três verificações que o PVA faz e o programa não fazia:
  - **data de entrada/saída antes da emissão** (`MSG_DATA_MAIOR_IGUAL_
    DT_DOC`): 4.142 no Contribuições original;
  - **natureza da receita fora da tabela do CST** do M400/M800
    (`MSG_EXISTE_NAT_REC`), pelas tabelas 4.3.10 a 4.3.16 do PVA: a cerveja
    (423/424, monofásico) sob o CST 06 — o PDV a vende com CST 06;
  - **crédito na entrada de produto monofásico ou de alíquota zero**
    (`MSG_COMPATIBILIDADE_NCM_*`), no diagnóstico e na revisão.
- No EFD ICMS/IPI a "data de saída fora do período" poupa o COD_SIT 01/07,
  que o PVA aceita; e não conta de novo o documento cuja saída é anterior à
  emissão (o PVA não acusa as duas).

#### Corrigido (segunda rodada)
- **O classificador de NCM ignorava o "Ex" da TIPI.** As três tabelas do
  PVA (alíquota zero e as duas de monofásico) trazem a coluna EX_IPI, e a
  linha com Ex só vale para o produto com o mesmo EX_IPI no 0200 — o
  21069010 Ex 02 é o concentrado para refrigerante, não toda preparação
  alimentícia. Num arquivo real: **86 entradas acusadas contra as 9 do
  PVA**; agora as 9, mais a cerveja revendida com crédito (que o PVA não
  acusa, mas é creditamento indevido).
- **Recalcular bloco M deixava o M205/M605 com o débito antigo**, e o PVA
  acusava `MSG_VALIDA_DET_RECEITA_DCTF` (3.340,22 no M200 e 3.338,47 no
  M205). O débito do código de receita acompanha o campo de origem; com
  mais de um código no mesmo campo, o recálculo avisa e não mexe.
- **No EFD Contribuições a NFC-e extemporânea fica no mês.** O PVA de lá
  recusa a saída com data de outro mês mesmo com COD_SIT 01
  (`MSG_PERIODO_INCOMPATIVEL_SAIDA`, 7.156 vezes): a correção pelos XMLs
  mantém a emissão do arquivo e iguala a saída a ela.

- Rotina **Natureza da receita fora da tabela do CST** (M410/M810). A
  bebida fria vendida pelo varejista é CST 06 com natureza **918** (Lei
  13.097/2015) — como o ERP já fazia em quase tudo. As cervejas que o PDV
  emitiu com CST 02/CFOP 5101 entraram certas no C175 (CST 06), mas o M410
  ficou com 423/424, códigos da tabela de monofásicos (venda do
  fabricante). A rotina troca para 918 e soma na linha que já existe; só
  propõe a troca para empresa de comércio, com o NCM do código errado
  confirmado como bebida fria pela tabela do PVA.

#### PVA de ensaio, setembro do cliente B
- **ICMS/IPI:** 81 erros (4 tipos) → **8** — 6 C190 sem dado de redução e 2
  participantes com município zerado (cadastro no ERP).
- **Contribuições:** 4.194 (10 tipos) → **4** — a natureza da receita da
  cerveja, que depende do CST com que o PDV vende.
- Retirar o crédito indevido (20 em CFOP de bonificação, 24 por NCM)
  aumenta o PIS a recolher em R$ 171,76 e a COFINS em R$ 791,13.

#### Corrigido
- O diagnóstico cobrava data, valor, participante e indicadores de NF-e
  **cancelada**, denegada e inutilizada, que pelo Guia só levam a
  identificação. Eram os "25 campos obrigatórios em branco que o PVA
  importou sem reclamar" da 0.57.0. Gabarito: obrigatórios 25 → 0, 16 → 1
  e 26 → 1 nos arquivos do cliente B.
- **COD_GEN em branco** deixou de ser erro (é aviso): o PVA não o cobra —
  1.355 no arquivo real, nenhuma mensagem.
- **Município zerado do participante** deixou de ser "campo vazio
  disfarçado": o *Normalizar* o esvaziava, trocando um erro por outro. Agora
  é achado próprio, que manda corrigir o cadastro do participante no ERP, e
  não impede a importação (o PVA importa e acusa na validação). Gabarito:
  os 2 do agosto do cliente B saem de "nulo" para "município".

### Fica fora da 1.0.0
Entram nesta candidata (canal rc), mas **somem da release** pelo
`pronta=False`, porque ainda não fecharam o critério do ROADMAP:
- NFC-e 65 por XML (*Importar XMLs → consolidar C175*, *Validar* e
  *Regenerar C175*; no ICMS/IPI, os C170 fictícios): falta o ensaio no
  PVA.
- *Gerar SPED a partir dos XMLs*: falta o ensaio no PVA do arquivo gravado
  pela tela e um mês real com CT-e.

### Falta para a 1.0.0
- Roteiro 2.3: monitor com escala acima de 100%.

## [0.58.0-dev.5]

Etapas 1 a 5 de **gerar o SPED a partir dos XMLs** (ROADMAP 4.4).

### Adicionado (etapa 5)
- **Ferramentas → Gerais → Gerar SPED a partir dos XMLs…** (canal de
  desenvolvimento, `pronta=False`). Empresa pelo CNPJ, pasta dos XMLs,
  período e leiautes; a tela mostra:
  - **Documentos** do período, cada um com a caixa *Incluir*. A nota que a
    empresa não escritura é desmarcada ali e continua na lista.
  - **Revisão**: o que o gerador não soube, com os bloqueios primeiro. Com
    algum bloqueio, o leiaute não é gravado.
  - **Fora do período e ignorados**, inclusive o arquivo ilegível e o XML
    repetido.
- **A decisão da pessoa volta para a memória.** Duplo clique num produto:
  CFOP, CST, crédito, código próprio, PIS/COFINS. Ela passa à frente do que
  foi aprendido e substitui uma decisão anterior. A próxima geração já sabe.
  - O digitado é conferido antes de gravar (`validar_decisao`), com todos
    os problemas de uma vez; alíquota sai no formato do SPED.
  - A decisão parte da escrituração **que a geração usou**. Sem isso, dizer
    só o CST de PIS de um produto escriturado pela correlação de CFOP
    guardava o CFOP vazio — e, como a memória passava a "saber", a geração
    seguinte não bloquearia. Escrituração sem CFOP ou CST do ICMS é recusada.
- **Aprender com SPED entregue…** na própria tela: um SPED de cada leiaute,
  do mesmo mês, da mesma empresa (recusa os outros casos).
- Os leiautes marcáveis são os que a memória sabe gerar.
- O participante novo recebe o mesmo código nos dois leiautes.
- Caso de uso `aplicacao/geracao_xml.py`: a memória só é gravada ao
  aprender, decidir ou salvar — nunca por gerar uma prévia.

### Corrigido
- **Abrir outro arquivo descartava as alterações sem perguntar.** Menu,
  histórico, painel de empresas e arrastar e soltar passavam direto por
  cima do arquivo alterado. Agora perguntam, como o *Fechar*.
- A comparação com o SPED entregue conferia PIS/COFINS também no EFD
  ICMS/IPI. Lá esses campos são informativos e o gerador os deixa vazios
  (o PVA aceita), então todo item saía "diferente". Voltam a ser comparados
  só no EFD Contribuições.

### Mês real pela tela (junho de 2026)
- Aprender com os dois SPED entregues e gerar: 20 bloqueios (o CFOP 5908 e
  o CST de PIS/COFINS de itens das 13 notas que a empresa não escriturou).
- Desmarcadas as 13 notas: **nenhum bloqueio** e os números da dev.3/dev.4
  (393 C100 e 562 C170 no ICMS/IPI; C175 e bloco M idênticos).
- Com as 13 notas e 9 decisões gravadas na memória: nenhum bloqueio, e a
  pré-checagem de importação limpa nos dois leiautes.

### Adicionado (etapa 4)
- **Gerador do EFD Contribuições.**
  - Entradas: C100 + C170, com PIS/COFINS e conta contábil pela memória.
    A base existe só nas entradas com crédito e é o valor do item menos o
    ICMS.
  - NFC-e: C100 + C175, pelo `consolidar_c175_de_itens`. A alíquota é
    trocada para a do regime pelo mesmo caminho do *Trocar alíquotas* —
    no mês real, o XML das NFC-e vinha com 1,65/7,60 num contribuinte
    cumulativo que escritura 0,65/3.
  - Bloco M pelo `recalcular_bloco_m`, e M205/M605 (código de receita)
    pelos modelos.
- A memória aprende também:
  - a conta contábil de cada item e o plano de contas (0500);
  - a alíquota de saída do regime;
  - a **largura de cada registro** na versão que a empresa entrega. O
    gerador limita essa largura pela do descritor do PVA: o 0200 do EFD
    Contribuições tem 12 campos lá e 13 no leiaute do programa, e com 13 o
    PVA recusava a importação.
- CSOSN do fornecedor do Simples não vai para o CST de ICMS do item no
  Contribuições (lá o ICMS é o do XML): vale o da escrituração.

### Mês real (junho de 2026, EFD Contribuições)
- **C175: 424 de 424 idênticos**; **bloco M inteiro idêntico** (M200, M205,
  M210, M600, M605, M610); 378 C100 idênticos.
- **PVA de ensaio: a mesma única inconsistência do entregue**
  (`MSG_PREENCHIMENTO_0900`, escrituração fora do prazo).
- Diferenças no C170 que ficam: o ERP escritura o mesmo item de forma
  diferente nos dois SPEDs do mesmo mês (CFOP 1101 num e 1403 no outro,
  quantidade arredondada). O gerador usa a mesma escrituração nos dois. A
  apuração não muda.

### Adicionado (etapa 3)
- **Gerador do EFD ICMS/IPI** (`dominio/geracao.py`): blocos 0, B, C, D, E,
  G, H, K, 1 e 9 a partir dos XMLs e da memória da empresa.
  - Os itens de todos os documentos são montados antes. O C190 sai do mesmo
    recálculo do botão; depois saem os C170 que o leiaute não pede (NFC-e e
    NF-e própria).
  - O C190 soma o VL_DOC: frete, ST e IPI que a empresa não separa entram
    no rateio.
  - A apuração do ICMS e do IPI é calculada. E116, E200/E300, 1010 e o
    cabeçalho saem dos **modelos** aprendidos do SPED entregue.
  - CT-e tomado vira D100/D190 de entrada.
- A memória aprende também:
  - o fator de conversão de unidade (um fardo no XML pode ser 12 unidades
    no SPED);
  - a data de entrada da empresa (emissão ou saída do XML) e se ela separa
    o frete;
  - as naturezas (0400), os indicadores do C100 e o saldo credor;
  - a **prática da empresa** por CFOP e CST de fornecedor, que é a segunda
    opção para produto nunca comprado.
- O que não se sabe vai para a lista de revisão. O que deixaria o arquivo
  inválido (um CFOP de entrada impossível de decidir) **bloqueia**.
- `comparacao_sped`: compara dois SPED do mesmo período documento a
  documento, com números comparados como números e participante pelo CNPJ.

### Mês real (junho de 2026, EFD ICMS/IPI)
- Com as mesmas notas do entregue e o saldo credor de maio: **393 C100
  idênticos**, **562 dos 572 C170**, **E110 idêntico**, os 21 participantes.
- **PVA de ensaio: 0 inconsistências**, como o entregue. A primeira versão
  tinha 954, porque a NFC-e exige vazios os campos de ST e IPI do C100,
  e o gerador gravava zero.
- Diferenças que ficam, todas explicadas:
  - 10 itens que a própria empresa escriturou de dois jeitos;
  - a fórmula do VL_RED_BC do ERP, que difere da do Guia;
  - centavos do rateio de outras despesas entre grupos;
  - os textos complementares (C110/C195), que o gerador ainda não monta.
- Com as 13 notas que a empresa não escriturou incluídas, o PVA acusa só o
  item cujo CFOP ninguém sabe — exatamente o que o gerador bloqueia.

### Adicionado (etapa 2)
- **Memória de itens por empresa** (`dominio/memoria_itens.py`, gravada em
  `memoria/<CNPJ>.json` na pasta de dados e lida só quando a geração
  precisa): produto do fornecedor → código próprio e **como a empresa o
  escritura** em cada situação (CFOP e CST de origem → CFOP, CST de ICMS,
  crédito, CST e alíquota de PIS/COFINS); o cadastro próprio (0200), os
  códigos de participante e as unidades.
- **Aprendizado a partir do SPED entregue**: casa cada C170 de entrada com o
  item do XML pela chave da nota e pelo número do item. Num mês real
  casaram os 577 itens, e a memória reproduz 567 exatamente como foram
  escriturados; os outros 10 são produtos que a própria empresa escriturou
  de dois jeitos, e ficam apontados como ambíguos. O que a memória não sabe
  é respondido com "não sei" — nunca com um palpite gravado.

### Adicionado (etapa 1)

### Adicionado
- **Leitura de CT-e (modelo 57)**: chave, série, número, CFOP, municípios de
  início e fim, participantes (emitente, remetente, expedidor, recebedor,
  destinatário), o **tomador** — pelo `toma3` ou, no `toma4`, com dados
  próprios —, valor da prestação, os grupos de ICMS (00, 20, 45, 60, 90,
  outra UF e Simples), protocolo e as NF-e transportadas.
- **NF-e com o que o 0150 e o C100 pedem**: emitente e destinatário com
  endereço e município, data de entrada/saída, finalidade, notas
  referenciadas, totais de impostos, situação do protocolo e o código de
  barras do item.
- **Eventos de cancelamento** de NF-e e CT-e, e `ler_pasta_fiscal`: lê a
  pasta e as subpastas, aplica os cancelamentos (o documento fica, com a
  situação "cancelada", para ir ao SPED com COD_SIT 02), conta repetido uma
  vez só e **lista o que não leu**, com o motivo — nada é descartado em
  silêncio.

## [0.57.0] - 2026-09-27

Preparação da 1.0.0-rc.1, sem entrar nela: toda função fechou os critérios
do roadmap ou saiu de uma release; README revisado de ponta a ponta.

### Corrigido
- **A planilha de inventário lia célula inválida como zero.** `abc`, `1.2.3`
  ou `NULL` na quantidade, nos valores ou na alíquota viravam 0, e o item
  entrava no inventário com quantidade zerada. Agora a importação confere
  todas as células numéricas **antes** de mexer no arquivo e recusa, dizendo
  a linha da planilha e a coluna de cada uma. A planilha real de 11.585 itens
  importa sem nenhuma recusa indevida.

### PVA (roteiro 2.1)
- **CST por NCM validado.** Nenhum arquivo real tinha o caso que a correção
  grava: ela só age em entrada que **toma** crédito, e as entradas
  encontradas já estavam sem crédito. O roteiro ganhou a série `_cstncm`, que
  põe o erro clássico sobre o arquivo real: 15 entradas de monofásico ou
  alíquota zero passam a CST 50 com crédito, e o bloco M é refeito. Nessa
  cópia o PVA acusa 34 inconsistências; corrigida, **0**.
- **Inventário validado abaixo do teto.** Isolado, ele só tinha passado num
  arquivo acima de 1.000 erros. Agora ele está na cadeia, que no arquivo 2
  fica em 63 inconsistências, todas já presentes no original. De passagem,
  o fluxo do roteiro reimportava o H010 **sem a conta contábil** e apagava o
  COD_CTA: era defeito do roteiro, não da importação, que traz a coluna.
- 56 validações ao todo, nenhuma correção criando erro que o original não
  tenha.

### Mudado
- **NFC-e 65** (importar XMLs e consolidar C175, validar e regenerar C175)
  com `pronta=False`: sem os XMLs de um mês real, nada do que elas gravam
  passou pelo PVA. As ações continuam nos canais de desenvolvimento e somem
  de uma release, como manda o roadmap.
- **README revisado de ponta a ponta:**
  - a seção antiga do bloco M, que dizia que o crédito não era refeito,
    contradizia a nova e saiu;
  - "cinco" regras de revisão eram 14;
  - a tabela de rotinas trazia 4 das 6;
  - os caminhos de menu e os locais da pasta de dados estavam desatualizados;
  - a gravação sempre em latin-1 e o executável como forma de uso agora
    estão descritos;
  - as funções de NFC-e estão marcadas como em desenvolvimento.

## [0.56.0] - 2026-09-26

Validar na entrada, nunca tolerar em silêncio. Uma revisão das funções que
existiam para contornar dado ruim achou quatro lugares em que o programa
**escondia** o erro em vez de acusá-lo, e duas ações que repetiam o que a
validação de leiaute já faz.

### Corrigido
- **A leitura descartava dado sem avisar.**
  - Linha **sem o `|` final** perdia o último campo. Num 0200 assim, o NCM ia
    embora, o diagnóstico não acusava nada e salvar gravava sem ele. Agora a
    linha é lida inteira e apontada.
  - Linha **sem o `|` inicial** era pulada e sumia ao salvar. Agora ela
    aparece no Diagnóstico, e salvar pergunta antes de gravar sem ela.

  As duas impedem o envio ao PVA, como qualquer erro de estrutura.
- **Cálculos que gravam liam lixo como zero.** `NULL` ou `12a` num campo de
  valor viravam 0,0, e o C190, os totais do C100, o ICMS dos itens, o bloco M,
  a troca de alíquotas ou o C175 da NFC-e gravavam um total errado com cara
  de certo. Agora esses cálculos **recusam antes de mexer em qualquer coisa**,
  dizendo o registro, o campo, o valor e a linha. A regra de "número do SPED"
  é a mesma da validação de leiaute: o que ela acusa é o que eles recusam.
- **Cadastro, correlações, acervo e configuração ilegíveis viravam vazio** e
  eram sobrescritos no próximo salvamento: bastava cadastrar uma empresa para
  o cadastro inteiro sumir. Agora o arquivo é guardado como
  `nome.corrompido-<data>`, e o usuário é avisado. Isso vale também para o
  `correlacoes_cfop.json` da 0.55.0, que caía na tabela padrão em silêncio.

### Roteiro de validação no PVA
- **Revalidado no PVA de ensaio: 54 arquivos, resultado idêntico ao da
  0.54.0.** Nenhuma correção cria erro que o original não tenha. A
  revalidação era necessária porque, desde a 0.55.0, os arquivos do cliente
  A saem com a ordem dos 9900 preservada e o 0500 criado pelo COD_CTA entra
  no fim da lista. O PVA aceitou os dois.
- **O roteiro apertava Enter em toda janela chamada "Erro"**, inclusive na
  tela de falha interna do PVA ("Erro durante a validacao no banco"), que
  tem um botão de enviar relatório à Receita. Nesta rodada o Enter caiu na
  caixa de texto e nada foi enviado. Agora o roteiro só responde a diálogo
  de um Ok (pelo tamanho da janela); diante da falha interna, **para** sem
  tocar em nada e diz o que fazer.
- **Arquivo importado mas não validado contava como "0 inconsistências"**:
  o banco existe, e a tabela fica vazia. Agora só conta se a validação rodou.
- Na recusa da importação, o PVA apaga o banco ao fechar o relatório: o
  roteiro lê o resultado antes de fechar as telas.

### Removido
- **Limpar campos com NULL.** A validação de leiaute já acusava o NULL e o
  *Normalizar* já o esvaziava: num arquivo real, o *Normalizar* sozinho
  corrigiu os mesmos 13.341 campos. O único caso que só a ação removida
  pegava, NULL num campo de texto livre como a descrição, agora é da
  validação.
- **Validar campos pelo leiaute**, do menu. Era um subconjunto do
  *Diagnóstico*, com a mesma validação e os mesmos domínios. A tela continua,
  como **Corrigir campos pelo leiaute**, aberta pela linha correspondente do
  Diagnóstico.

## [0.55.0] - 2026-09-26

O executável: gerado, conferido por dentro (`--autoteste`) e usado na tela
— roteiros 2.2 e 2.3 do TESTES.md.

### Roteiro na tela (executável, pasta de dados de ensaio)

| Item | Resultado |
|---|---|
| Primeira execução: cria a pasta de dados, pergunta do atalho em português (Sim/Não) | ✔ |
| Ícone na janela, na barra própria, nos diálogos e na barra de tarefas | ✔ |
| Arrastar pela barra; duplo clique maximiza e restaura | ✔ |
| Aero Snap na borda esquerda; depois dele, maximizar/restaurar volta ao tamanho de antes | ✔ |
| Redimensionar pelas 8 bordas (medido: 40 px em cada uma) | ✔ |
| Menu de sistema | ✔ depois da correção abaixo |
| Maximizada: ocupa a área útil a partir do pixel 0, sem cobrir a barra de tarefas | ✔ |
| Arrastar aba de bloco leva o conteúdo; fixar, fechar e resetar sub-aba | ✔ |
| Tema escuro na grade, nas abas, na barra e no cadastro de empresas | ✔ |
| Abrir pelo seletor nativo, diagnóstico, cópia no acervo | ✔ |
| Soltar um `.txt` na tela inicial | lógica na suíte; o gesto do Explorador não foi feito |
| Monitor com escala acima de 100% | não se aplica: os dois monitores daqui estão a 100% |

### Corrigido
- **O menu de sistema não abria na barra de título própria.** Clique
  direito na barra não fazia nada: o Windows abre esse menu ao tratar o
  `WM_CONTEXTMENU`, e o Qt intercepta a mensagem para os menus dele. O
  comentário do código dizia que o menu "saía de graça". Agora o clique
  direito na barra abre o menu nativo, em português, com Restaurar,
  Mover, Tamanho e Maximizar habilitados conforme a janela esteja ou não
  maximizada — conferido na tela, com Maximizar e Restaurar executados por
  ele.

### Adicionado
- **`SPED Tables.exe --autoteste relatorio.json [arquivo.txt]`**: o roteiro
  2.2 do TESTES.md que dá para automatizar, rodado de dentro do pacote —
  tradução do Qt, ícone e correlações empacotados, `openpyxl`, instalação
  da pasta de dados, tabelas do PVA, registro de falhas com aviso, janela
  principal e, com um arquivo, abrir → salvar → reabrir com cópia no
  acervo. Sempre numa pasta de dados temporária: não toca no cadastro nem
  no acervo de quem usa o programa. Passou no executável com os 4 arquivos
  reais e com um sintético; atualizar o executável sobre uma pasta com
  cadastro, correlações e acervo não alterou um byte.

### Corrigido
- **Abrir e salvar sem mexer mudava o arquivo.** O bloco 9 era refeito com
  os 9900 em ordem alfabética, e cada ERP usa a sua: nos dois arquivos
  reais do cliente A, 31 e 39 linhas mudavam de lugar. O PVA aceita as duas
  ordens, mas "salvar sem editar devolve o mesmo arquivo" é o que o roadmap
  promete. Agora a ordem do arquivo é mantida e tipo novo entra no fim —
  os 4 arquivos reais voltam idênticos byte a byte.
- **Um `correlacoes_cfop.json` no formato errado impedia o programa de
  abrir**: JSON válido mas que não fosse um objeto (uma lista, por exemplo)
  derrubava a criação da janela principal. Agora vale a tabela padrão, como
  com arquivo ilegível; valor que não é lista de CFOP é ignorado.
- Aviso de sintaxe (`\S` no docstring) ao gerar o executável.

## [0.54.0] - 2026-09-26

A coluna **PVA** do roadmap: cada correção que grava, validada no PVA de
verdade — 53 validações sobre 4 arquivos reais (dois EFD Contribuições, dois EFD
ICMS/IPI), 16 fluxos. **Nenhuma correção cria erro que o original não
tenha.**

### Resultado no PVA (inconsistências antes → depois)

| Arquivo | Régua | Fluxos isolados | Todas em cadeia |
|---|---|---|---|
| Contribuições, cliente B | 0 | 0 nos 8 | 0 |
| Contribuições, cliente A | 0 | 0 nos 8 | 0 |
| ICMS/IPI, cliente B | **recusado** na importação (1.000 erros de estrutura no 0200) | recusados como o original; sobre a régua importável, 1.025 → 1.025 (no teto) | **1.025 → 63** |
| ICMS/IPI, cliente A | **recusado** na importação (5 CST_ICMS `0`) | sobre a régua importável, 12 → 12 nos 5 | 12 → 12 |

- **O ICMS do cliente B nunca importou.** O ERP grava `N` no `TIPO_ITEM` de
  10.312 itens do 0200 — nenhuma correção automática decide isso (é a
  planilha, com prévia). A régua do roteiro põe `00` só para poder julgar as
  demais correções pela validação.
- **Os 63 que sobram na cadeia já estavam no original**: 35 C190 de CST x70
  sem base nenhuma (`MSG_CST_ICMS_RED_BC`: o ERP gravou 63, a cadeia
  consertou 28 pela base de PIS/COFINS e o resto fica para conferência
  manual, como manda a regra), 25 advertências de CST final 2, 1 no E116 e 2
  no 0150. O PVA não os listava na régua porque **para de listar erros em
  1.000**.
- Sem caso nos arquivos reais: **CST por NCM** (nada a corrigir nos dois
  Contribuições) e **NFC-e 65 / C175**, que depende dos XMLs dos cupons —
  continuam pendentes no roadmap.

### Adicionado
- Fluxos **cadeia** (todas as correções em sequência — a única comparação
  que o teto de 1.000 erros não mascara) e **totais do C100**.
- **Régua importável** para arquivo que o PVA recusa na importação: uma
  segunda série (`…_prep`) com NULL limpos, campos normalizados,
  `TIPO_ITEM` inválido como `00` e CST_ICMS curto completado com zeros.
  Decisões que o programa não toma sozinho; valem só no roteiro.
- O relatório distingue **recusa**, **teto** ("inconclusivo" quando régua e
  correção estão acima de 1.000; "a conferir no original" quando a correção
  desce abaixo do teto e aparece o que ele escondia) e piora de verdade.
- O roteiro fecha sozinho os diálogos que o PVA deixa depois de validar ou
  de recusar a importação — sem isso, o Ctrl+I seguinte era engolido e a
  rodada inteira parava no primeiro arquivo.

### Corrigido
- **Abrir no PVA anunciava "não consegui confirmar a importação" de
  arquivo importado.** Escrituração nova — CNPJ e período que o PVA ainda
  não tem — vai do seletor direto ao `Importando…`: o aviso "deseja
  importar?" só aparece quando há uma escrituração a **substituir**. A
  automação esperava o aviso assim mesmo, pegava o seguinte ("Deseja fazer
  a validação de conteúdo agora?"), respondia a ele e dava a importação por
  não confirmada. Recusa de escrituração nova saía com a mesma mensagem, em
  vez de "o PVA recusou". Sequências observadas no PVA e fixadas em teste.
- `gerar --fluxos` do roteiro sobrescrevia o manifesto só com os fluxos
  pedidos.

## [0.54.0-dev.1] — sem tag

Primeira parte da 0.54.0 do roadmap: validar no PVA o que cada correção
grava.

### Adicionado
- **`ferramentas/validar_no_pva.py`**, o roteiro 2.1 do TESTES.md automático:
  grava uma cópia de cada arquivo real por fluxo de correção (14 fluxos),
  importa e valida cada uma no PVA e compara as mensagens com as do arquivo
  original. Roda numa **cópia de ensaio** da instalação dos PVAs, com porta
  de banco própria, para não substituir as escriturações do PVA de uso. Tem
  modo manual (a pessoa importa e valida; a ferramenta lê o banco) e retoma
  de onde parou.
- **`infra/banco_pva.py`**: lê, sem subir o servidor, o que a validação do
  PVA gravou (`inconsistencia`, por mensagem e registro) e qual arquivo
  virou qual escrituração (`master`).
- Arquivos reais passam a exercitar também o recálculo de ICMS dos itens,
  a troca de alíquotas (ida e volta) e a alteração de datas (ida e volta).
  Nos arquivos de validação: o recálculo de ICMS altera 4 a 7 itens por
  arquivo, todos por 1 centavo de arredondamento do ERP.

### Mudado
- **A cadeia "ICMS dos itens → C190 → totais do C100" saiu da tela para o
  domínio** (`recalcular_icms_itens(refazer_c190=True)`) e passou a refazer
  **só os documentos que tiveram item alterado**. O botão refazia o C190 e
  os totais de todos os documentos com C170 quando não havia seleção do
  relatório.

### Corrigido
- **A automação do PVA podia dirigir a instalação errada**: a janela era
  reconhecida só pelo título, igual em duas instalações. Agora o executável
  do processo tem de estar dentro da pasta da instalação configurada.
- **Janela do PVA minimizada contava como focada**: para o Windows ela
  estava em primeiro plano, mas o Java descartava as teclas e o Ctrl+I
  sumia sem erro.

## [0.53.0] - 2026-09-26

Arquitetura em camadas, documentação reescrita e a regra de que uma release
não tem função pela metade.

### Mudado
- **O programa virou o pacote `sped_tables/`, em quatro camadas** —
  `dominio` (documento e regras fiscais), `aplicacao` (casos de uso),
  `infra` (PVA, disco, Win32) e `interface` (PyQt6) —, com as dependências
  apontando só para dentro. Um teste reprova quem desobedecer. A explicação
  completa, e onde entra cada coisa nova, está no `ARQUITETURA.md`.
- **O `sped_editor.py` de 7.200 linhas virou um lançador de 5.** A interface
  foi dividida em janela, controladores por área do menu, grade, telas e
  diálogos por assunto. `python sped_editor.py` continua funcionando.
- **Tabela única de ações** (`interface/acoes.py`). Cada ação era criada,
  religada ao `.ui`, habilitada e desabilitada em quatro lugares — esquecer
  um derrubou a janela duas vezes. Agora é uma linha. Com isso saíram o
  `sped_editor.ui` (a janela nascia por dois caminhos) e o
  `sped_editor_ui.py`, código morto de PySide6.
- **O domínio não lê mais a instalação do PVA.** Pergunta a uma porta
  (`dominio/referencias.py`), que a montagem liga ao PVA no início do
  programa. Sem PVA a porta fica vazia e as regras se abstêm, como antes; e
  os testes ligam uma tabela inventada, o que permite testar as regras de
  crédito por CFOP e do 0900 numa máquina sem PVA.
- A classificação de NCM e a conferência de CST saíram de `tabelas_rfb`
  (leitura de arquivo) para `dominio/ncm.py`. A gravação do cadastro de
  empresas e das correlações de CFOP saiu dos módulos de regra para
  `infra/cadastro.py`.
- Abrir, salvar, fechar e mandar ao PVA viraram casos de uso
  (`aplicacao/sessao.py`, `aplicacao/envio_pva.py`), testados sem tela.
- **`FUNCIONALIDADES.md` virou `ROADMAP.md`.** Marcar função como "em
  amadurecimento" ou "experimental" não cabe numa versão entregue: agora a
  **versão declara o canal** (`-dev`, `-alpha`, `-beta`, `-rc`, release) e a
  1.0.0 tem critério de aceite por função (suíte, arquivo real, PVA,
  executável, documentação), com o que falta para cada uma. Toda a série
  0.y.z é desenvolvimento.
- `TESTES.md` reescrito em torno da suíte automática; o roteiro manual ficou
  só com o que ela não alcança (PVA, executável, janela no Windows).
- README e CLAUDE.md atualizados para a estrutura nova. Nome e CNPJ de
  clientes saíram da documentação.

### Adicionado
- **`version.canal()` e `Acao.pronta`**: numa release, ação não pronta não é
  criada — nem menu, nem atalho.
- **Ferramentas → Gerais → Pasta dos PVAs…**, para instalação fora das pastas
  que a detecção automática conhece.
- Exportação de CSV única (`infra/exportacao.py`) e formulário de empresa
  único (`interface/formulario_empresa.py`), no lugar de oito e de duas
  cópias.
- Testes: correções que gravam (NULL, COD_GEN, COD_CTA, itens sem
  referência, ICMS dos itens, C190 em massa, datas), conferência com NF-e
  sintética, NCM × CST, totais do C100, NFC-e 65 (C170 fictícios e
  regeneração), camadas, canais — 148 no total. Nos arquivos reais, as
  correções em lote passaram a ser exercitadas com invariantes.
- A suíte liga o `faulthandler`: queda nativa sai com rastro, não com um
  *exit 127* mudo.

### Corrigido
- **A normalização em lote apagava o `CST_ICMS` = `0` de itens do C170 e do
  C190.** O domínio vindo das tabelas do PVA tratava o código "só de zeros"
  como campo vazio disfarçado e sugeria esvaziar — o que trocava um erro por
  outro, porque o CST é obrigatório ali, e contrariava a regra de que CST e
  CFOP são apontados, nunca sugeridos. Agora os dois campos nunca recebem
  sugestão. No arquivo real do cliente A, 5 ocorrências passaram de "nulo"
  para "domínio" no diagnóstico (o único número do gabarito que mudou).
- `validacao.normalizar()` sem lista usava os domínios embutidos, enquanto o
  diagnóstico usava os do PVA — o que o diagnóstico acusava pelas tabelas
  ficava sem conserto pelo caminho padrão.
- Os exportadores de CSV desalinhavam as colunas com `;` numa descrição e
  abortavam com um caractere fora do latin-1.
- O formulário do painel de empresas não editava o "CST sem crédito", e o
  do diálogo de rotinas não mostrava a UF.
- "Conferir entradas (NF-e 55) com XMLs" não estava em menu nenhum desde a
  reorganização do menu por leiaute; voltou a *Gerais*.
- Oito funções e duas tabelas sem uso foram removidas.

## [0.52.0] - 2026-09-26

Configuração num ponto só e os achados menores da revisão de código.

### Adicionado
- **`config.py`, ponto único de configuração dos caminhos.** O
  `C:\Arquivos de Programas RFB\Programas SPED` estava escrito em quatro
  módulos; PVA instalado noutro lugar desligava em silêncio metade das
  verificações. Agora a raiz vem, nesta ordem, de `SPED_TABLES_PVA`, do
  `configuracao.json` da pasta de dados, da primeira pasta conhecida que
  exista (inclusive Arquivos de Programas e outros discos) ou da padrão. A
  estrutura interna de cada PVA (tabelas, `.jar` do descritor) também mora
  lá, uma vez só.
- A configuração das tabelas da RFB passou para o `configuracao.json`. O
  `config_tabelas_rfb.json` antigo é lido uma vez, para não perder o que já
  estava escolhido, e saiu do repositório: era um arquivo versionado que o
  programa regravava rodando do código-fonte.
- `dados.gravar_atomico` / `dados.gravar_json`: gravação por arquivo
  temporário + troca, a mesma técnica do `salvar` do SPED.
- `SpedDocument.alterar_campo`: caminho único das edições da grade.

### Corrigido
- **Campo inexistente no leiaute levantava `TypeError`.** `Registro.valor`
  e `set_valor` com índice `None` (o que `_ix` devolve para campo que o
  leiaute não tem) estouravam na comparação — num slot do Qt, derrubando o
  programa. Agora leem vazio e não gravam nada.
- **C190, C175 e M210/M610 gerados podiam sair mais curtos que o arquivo.**
  A lista montada tinha a largura do leiaute conhecido, e a medida do
  arquivo era tirada depois de remover os registros antigos — quando a
  medida mais importava, não sobrava registro para medir. Agora a largura é
  medida antes e os campos a mais ficam vazios.
- **0190 e 0200 criados pela importação de inventário entravam fora de
  ordem** quando o arquivo não tinha nenhum: logo depois do 0001, antes do
  0005/0100/0150. A âncora agora segue o leiaute (`_ancora_antes`, a mesma
  conta que C190 e C175 faziam cada um à sua maneira).
- **Troca de alíquotas dobrava o VL_PIS/VL_COFINS do C100** que tinha C175
  e C170 ao mesmo tempo (os C170 fictícios da validação por XML). Documento
  consolidado soma só o C175.
- **Colar e Ctrl+D numa grade de 0150 não atualizavam o nome do
  participante**; cada caminho de edição invalidava os caches à sua
  maneira. Os cinco (digitar, colar, aplicar à seleção, Ctrl+D e o
  relatório) passam por `alterar_campo`.
- **Cadastro de empresas, índice do acervo e correlações de CFOP eram
  gravados truncando o arquivo antes de escrever**: uma falha no meio
  zerava o cadastro. Gravação atômica nos três.
- **Rotina de CST por NCM, aberta pelo cadastro de empresas, não acusava
  nada** sem configuração salva: o classificador era montado sem pasta, e
  esquecia a tabela 4.3.10 (perfumaria, medicamentos). Os dois diálogos
  usam agora `tabelas_rfb.classificador()`, com a pasta do PVA como padrão.
- O descritor do PVA era lido e interpretado três ou quatro vezes a cada
  abertura de arquivo (diagnóstico, validação, revisão) e o `.jar` ficava
  aberto; agora é lido uma vez por versão do `.jar`.
- O diagnóstico percorria o arquivo inteiro uma vez por tipo de registro do
  descritor (~12 milhões de comparações num arquivo de 45 mil linhas) ao
  procurar obrigatórios e referências; agora agrupa uma vez só.
- Exceção dentro de uma verificação do diagnóstico era engolida sem rastro;
  continua sem interromper as outras, mas vai para o registro.
- Os testes de interface alternavam o tema **no registro do Windows** do
  usuário; com a pasta de dados redirecionada, as preferências vão para um
  `.ini` lá dentro.

### Testes
- 99 testes. Novos: um por achado (`test_robustez`), a configuração, e a
  **inicialização completa** — `main()` em subprocesso, com a abertura pela
  linha de comando, até o laço de eventos e de volta. Foi ele que pegou,
  antes do commit, um `ajustes = ajustes()` que sombreava a função e
  impediria o programa de abrir.
- Gabarito dos arquivos reais idêntico ao da 0.51.0.

## [0.51.0] - 2026-09-26

Suíte de testes no repositório e rede de proteção para erro inesperado.

### Adicionado
- **Suíte de testes em `tests/`** (`py -m unittest discover -s tests -t .`),
  86 testes em ~7 s. Nenhum arquivo de cliente entra no git: os SPED de teste
  são montados na hora por `tests/fabrica.py`, pelo nome dos campos do
  leiaute, com blocos fechados e bloco 9 contado. Cobre gravação atômica,
  encoding, largura de registro novo, rateio de acessórios, C190 (x20/x70),
  bloco M (débito, crédito, idempotência, cumulativo), validação por
  domínio, regras de revisão, diagnóstico e pré-checagem do PVA, cadastro,
  rotinas, acervo de arquivos e o cancelamento da automação do PVA — esta
  sem abrir o PVA de verdade.
- **Teste de interface que dispara cada ação do menu** nos dois leiautes,
  com os diálogos modais neutralizados. É o teste que teria pegado o
  "Validar campos pelo leiaute" derrubando o programa: ele chama a ação, não
  o diálogo.
- **Armadilhas conferidas em todo arquivo** (`test_estrutura`): código
  depois de `return` (o `def` apagado por edição), módulo com nome da
  biblioteca padrão e método definido duas vezes na mesma classe.
- **Testes contra arquivos reais fora do repositório**: com
  `SPED_TABLES_ARQUIVOS_REAIS` apontando para a pasta, rodam invariantes
  (gravar não perde registro, recálculo idempotente, nenhuma verificação
  levanta exceção) e, havendo um `gabarito.json` na pasta, os **números
  exatos** por arquivo. `py -m tests.test_reais gerar` grava o gabarito.
- **Fallback para exceção não tratada** (`falhas.py`). O PyQt6 encerra o
  processo quando uma exceção escapa de um slot; agora ela é registrada em
  `logs/sped_tables.log` (pasta de dados, com rodízio), o documento com
  alteração pendente é gravado em `recuperacao/` e uma caixa diz o que houve
  — o programa continua aberto. Falhas nativas (Win32/ctypes) deixam rastro
  em `logs/falhas_nativas.log`; exceções de thread e avisos do Qt também vão
  para o registro. Um teste em subprocesso prova as duas coisas: com o
  gancho o processo sobrevive, sem ele morre.
- `SPED_TABLES_DADOS` no ambiente redireciona a pasta de dados (a suíte usa
  uma pasta temporária para nunca tocar no cadastro de verdade).
- `recalcular_bloco_m(naturezas=...)` aceita a tabela 4.3.7 pronta, sem
  depender do PVA instalado.

### Corrigido
- **`rotinas.executar` podia derrubar o programa.** Num `TypeError` ele
  repetia a verificação sem os parâmetros extras — mas o erro podia vir de
  dentro da verificação, e a segunda chamada, fora do `try`, levava a
  exceção até o slot do Qt. Agora passa só os parâmetros que a verificação
  declara e devolve qualquer erro como mensagem.
- **Alíquota padrão do regime saía `3,00`.** A normalização da 0.50.0 cobria
  o que era digitado, mas não o botão que aplica as alíquotas do regime; a
  tabela interna já está no formato do SPED.
- **Arquivo passado na linha de comando abria pela metade**: as abas eram
  montadas à mão, sem habilitar o menu, sem cópia no acervo e sem
  diagnóstico. Agora usa o mesmo caminho do histórico.
- Um arquivo de tabela do PVA ficava aberto após a leitura das naturezas de
  crédito.

## [0.50.0] - 2026-09-24

Os cinco achados **médios** da revisão completa do código.

### Corrigido
- **Arquivo em UTF-8 era lido como latin-1.** A lista de tentativas começava
  por `latin-1`, que **aceita qualquer byte e nunca falha** — as demais eram
  código morto. SPED exportado em UTF-8 entrava com a acentuação corrompida e
  era regravado assim; no CSV de inventário, o BOM ainda vinha grudado no nome
  da primeira coluna, quebrando o mapeamento do cabeçalho. Agora a ordem é
  `utf-8-sig, utf-8, latin-1` nos dois. A gravação continua sempre latin-1, e
  `doc.encoding_lido` guarda o que a origem usava.
- **Rateio de despesas acessórias no C175 era feito item a item.** É o defeito
  que já havia sido corrigido no C190 e voltou noutro lugar: R$ 1,00 entre três
  itens iguais somava 0,99. As duas consolidações passaram a chamar a mesma
  função, `rateio_acessorios`.
- **Três funções discordavam sobre o VL_OPR.** A geração do C175 somava o
  rateio, mas a conferência (`discrepancias_c175_65`) e a prévia
  (`previa_regeneracao_c175_65`) somavam sem — o comparador acusava divergência
  no C175 que o próprio programa acabara de gerar, em todo documento com
  frete/seguro/outras despesas.
- **Alíquota do cadastro ia crua para o arquivo.** O campo é texto livre:
  digitar `1.65` punha ponto decimal no SPED, que o PVA recusa. Normalizada em
  três pontos — ao digitar, ao montar a `Empresa` (inclusive de cadastro
  antigo) e na hora de gravar o campo.
- **A espera do PVA não tinha saída.** Quando ele abre um diálogo próprio e
  ninguém responde, a espera vai até 15 minutos — e a janela de progresso não
  tinha botão de cancelar. Agora tem, e `pva.abrir` aceita `cancelar`:
  cancelando, a automação para onde está e nenhuma tecla a mais é enviada.

### Notas
- `rateio_acessorios` passou a tratar o caso de itens todos zerados com
  despesa no documento dividindo igual, em vez de deixar o valor de fora.
- A alíquota gravada agora sai no formato do SPED (sem zeros à direita): o
  cadastro com `3,00` grava `3`, como já acontecia com `7,6`.
- Teste novo (`teste_medios`) cobre os cinco, incluindo o SPED e o CSV em
  UTF-8, a soma do rateio fechando com o total e o cancelamento em cada laço
  de espera.

## [0.49.1] - 2026-09-24

### Corrigido
- **"Validar campos pelo leiaute" derrubava o programa.** O resumo que diz de
  onde veio a validação ficou com a forma antiga do dicionário de domínios
  (`{campo: dominio}`); desde a 0.40.0 a chave é a tupla `(registro, campo)`,
  e `", ".join(sorted(dominios))` sobre tuplas levanta `TypeError`. Exceção
  dentro de um slot do Qt **encerra o processo** — daí o "crash" ao acionar a
  função. Acontecia em **todo arquivo** com o PVA instalado, inclusive quando
  não havia nenhum campo fora do domínio.
- O resumo passou a dizer o que interessa — quantos pares registro/campo, em
  quantos campos distintos, e a **origem** de cada domínio (enumeração do
  descritor, tabela externa ou tipo/tamanho). A lista dos nomes saiu: eram
  724 num arquivo real, em ordem alfabética, sem informar nada.

### Notas
- Teste novo (`teste_validar_campos`) chama a **ação do menu**, não o diálogo:
  o teste que existia montava o `DialogoValidacao` direto e por isso não via o
  defeito. Cobre os três desfechos — com achados, sem achados e sem PVA
  instalado.
- No arquivo do relato (cliente B, agosto): 2.205 pares registro/campo
  validados e 24.125 campos fora do domínio — 13.343 com `NULL`, 10.312 de
  `TIPO_ITEM` e 470 de tipo/tamanho.

## [0.49.0] - 2026-09-24

Os dois defeitos **graves** encontrados na revisão completa do código.

### Corrigido
- **Registro criado pela grade saía com um campo só.** O botão "+" chamava
  `novo_registro` e ninguém redimensionava nada: a linha ia para o arquivo
  como `|C170|`, recusada pelo PVA por quantidade de campos. Agora é o próprio
  `novo_registro` que mede `_ncampos(tipo)` **antes de inserir** e entrega o
  registro na largura do leiaute — os outros 13 pontos que criam registro
  continuam montando o conteúdo como antes.
- **Salvar podia destruir o arquivo do usuário.** `open(caminho, "w")` trunca
  o destino no instante em que é aberto; qualquer falha depois disso deixava
  o arquivo vazio. No ensaio, colar um travessão (`—`) numa descrição e salvar
  **zerava um SPED de 236 KB**. Agora o texto é codificado antes de tocar em
  disco, escrito num `.tmp` ao lado e renomeado por cima (`os.replace`).
- Caractere fora da codificação do SPED passou a **recusar a gravação com a
  linha e o caractere na mensagem**, em vez de estourar no meio da escrita.
  Trocar por `?` em silêncio mudaria a descrição do produto sem ninguém saber.

### Notas
- Teste novo (`teste_gravacao`) cobre os dois: largura do registro criado pelo
  modelo e pelo botão "+" da grade; e a gravação com caractere impossível,
  conferindo que o arquivo continua **byte a byte intacto**, sem `.tmp`
  sobrando, com a gravação normal idempotente.
- Os outros 14 achados da revisão (5 médios, 9 menores) seguem catalogados e
  não foram mexidos nesta versão.

## [0.48.0] - 2026-09-23

### Corrigido
- **O "Abrir no PVA" não funcionava no EFD ICMS/IPI.** Com uma escrituração
  aberta em edição — o estado de quem deixa o PVA aberto no arquivo do mês —,
  o menu *Nova → Importar* fica desabilitado e o Ctrl+I não faz nada. A
  segunda tentativa passou a mandar **Ctrl+F** (Fechar) antes do Ctrl+I; a
  escrituração continua no banco do PVA (reabrir é Ctrl+A). Com isso o
  caminho fechou em **5,1 s e 2 tentativas** num PVA que estava exatamente
  nesse estado.
- **Arquivo recusado era anunciado como importado.** A tela *Importando…*
  some tanto no sucesso quanto na falha; quem separa os dois é o **Erro** que
  o PVA abre em seguida. Agora ele é detectado e o resultado vira `erro_pva`.
- **Janela esquecida travava a espera.** *Resultado da Importação*, *Erro* e
  afins eram confundidos com o carregamento, e a automação queimava os dois
  minutos inteiros antes de dizer que o PVA estava ocupado. A janela de
  carregamento se chama **"Aguarde..."**; só ela (e as sem título) contam
  como carregamento.

### Adicionado
- **Pré-checagem antes de mandar ao PVA.** `diagnostico.impedem_importacao`
  separa os achados que fazem o PVA recusar a importação (`nulo`, `formato`,
  `num_campos`, `bloco`, `dominio`) e a GUI pergunta antes de abrir nada,
  oferecendo o diagnóstico. Num arquivo real de supermercado: 13.343 campos
  com `NULL`, 10.312 `TIPO_ITEM` inválidos e 470 `CEST` — exatamente o que o
  PVA recusou, com 1.000 erros no relatório (o teto dele).
- **As telas próprias do PVA passaram a ser esperadas, não respondidas**:
  *Atualizar Tabelas* (Ok/Cancelar, com o foco na árvore — Enter não aciona
  botão), *Transferindo Tabelas* e a *Mensagem* de conclusão. O andamento diz
  o que o PVA está pedindo, e a importação retoma sozinha quando o usuário
  responde.

### Notas
- Conferido ponta a ponta no EFD ICMS/IPI: arquivo corrigido importou,
  validou e o PVA devolveu o relatório de pendências.

## [0.47.0] - 2026-09-23

### Adicionado
- **A importação no PVA agora vai até a validação.** O programa responde aos
  dois avisos que o PVA abre — "deseja importar?" e, terminada a importação,
  "deseja validar?" —, porque importar sem validar não fecha o ciclo: o que
  interessa é o relatório de erros do validador.
- Cada confirmação é **conferida pelo efeito**: a tela de progresso
  correspondente (`Importando a escrituração…`, `Validando a escrituração…`)
  tem de aparecer. Não aparecendo, a automação para e diz o que falta — é o
  que impede responder no escuro a um aviso que fosse outra coisa.
- A janela de espera mostra o andamento ("Aguardando o PVA terminar de
  carregar…", "Importando no PVA…", "Confirmando a validação…"), e o botão da
  confirmação de salvamento virou *Importar e validar no PVA*.

### Notas
- `pva.abrir` ganhou `validar=True` e passou a devolver os estados
  `validando`, `importado` e `confirmar`.
- Medido no PVA do EFD Contribuições, do clique ao validador rodando:
  **19,2 s**, com uma única tentativa de atalho.
- Os textos vêm do próprio PVA: as chaves `desejaImportar` e `desejaValidar`
  em `ControleImportarEscrituracao`, e os títulos das telas de progresso nas
  classes de ação.

## [0.46.0] - 2026-09-23

### Corrigido
- **A importação no PVA não pegava numa partida a frio.** A janela principal
  aparece bem antes de o programa aceitar atalhos, e o Ctrl+I era enviado no
  meio do carregamento interno — onde é simplesmente ignorado.
  `_esperar_pronta` agora aguarda o fim desse carregamento, detectado por um
  sinal medido no próprio PVA: enquanto carrega, o processo mantém uma
  **segunda janela** (a barra de progresso); quando sobra só a principal, o
  atalho passa a valer. Numa partida a frio do PVA Fiscal: janela aos 4 s,
  atalho aceito aos 11,9 s, exatamente na queda de 2 para 1 janela.
- Por garantia, o **Ctrl+I é repetido** a cada 3 s até o seletor abrir. É
  seguro porque atalho ignorado pelo Swing não enfileira: no ensaio, dois
  Ctrl+I enviados durante o carregamento não abriram nenhuma janela extra.

### Alterado
- Depois do Enter no seletor, o resultado passa a ser **`confirmar`** quando o
  PVA abre o aviso pedindo para confirmar a importação — é o que acontece de
  fato, e a mensagem diz isso em vez de anunciar uma importação que ainda
  depende do usuário.

### Notas
- Medições: partida a frio do PVA do EFD Contribuições, do clique à janela de
  importação com o caminho colado, **14,4 s e uma única tentativa** de atalho.
  Com o PVA já aberto, 1 s.
- A automação para nas confirmações do PVA (importar? validar?), que seguem
  sendo do usuário.

## [0.45.0] - 2026-09-23

### Adicionado
- **O recálculo do bloco M passou a refazer também os créditos** — M100/M105
  (PIS) e M500/M505 (COFINS) — a partir das entradas: um M100 por alíquota,
  um M105 por (natureza da base, CST). A **natureza vem do CFOP**, pela
  coluna `NAT_BC_CRE` da tabela 4.3.7 do PVA; num arquivo real esse
  agrupamento reproduziu exatamente o rateio que o contribuinte já tinha,
  inclusive o único item de natureza 02.
- **Conferência do M105/M505 contra os documentos**, na revisão e no
  diagnóstico, com atalho para o recálculo. No arquivo real ela aponta os
  **mesmos 8 erros** que o PVA (4 no M105, 4 no M505) e zera depois do
  recálculo.
- `tabelas_pva.naturezas_cfop_credito()`.

### Corrigido
- Nada a corrigir no recálculo em si: rodá-lo sobre um arquivo correto
  devolve o arquivo **byte a byte idêntico**, nos dois caminhos (com e sem o
  refazimento do crédito). O que produzia os erros de M105/M505 era a
  correção de CST/alíquota das **entradas**, que muda a base de crédito
  enquanto o M100/M105 continuava como o ERP gravou — e o recálculo, até
  aqui, não consertava esse lado.

### Notas
- `COD_CRED` tem 3 dígitos: o **primeiro** é o tipo do crédito e os **dois
  últimos** a vinculação da receita. A vinculação é decisão do contribuinte e
  não está nos documentos, então vem do que já existe no arquivo; só o tipo é
  redecidido pela alíquota.
- **Quando não dá, não mexe** — e diz por quê: incidência que não seja
  exclusivamente não-cumulativa, ajustes de crédito (M110/M115/M510/M515),
  crédito fora do bloco C (D101, F100…) ou tabela do PVA ausente.
- Números do arquivo real: base de crédito 207.997,27 (207.875,98 na natureza
  01 e 121,29 na 02), crédito de PIS 3.431,95 com 2.203,98 descontados e
  1.227,97 de saldo; COFINS 15.807,79 com 10.151,65 descontados.

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
  listas da edição. No arquivo real da cliente A, as ocorrências caíram
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
- Medições nos arquivos reais: cliente B 24.313 ocorrências (era 24.755, a
  diferença é o excesso removido), cliente A ICMS 8, Contribuições **0**.

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
- Validado por **controle**: o arquivo real da cliente A já estava certo
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
  3.499, COD_NCM 442). Nos arquivos da cliente A a regra achou 8
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

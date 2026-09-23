# SPED Tables — contexto do projeto

Aplicativo desktop **PyQt6** para editar arquivos fiscais **SPED** (EFD ICMS/IPI e
EFD Contribuições) numa interface mestre-detalhe estilo planilha.

**Idioma: todo o código, comentários, documentação e conversa em português do
Brasil.**

## Executar

```bash
python sped_editor.py
```

Dependências em `requirements.txt` (PyQt6; `openpyxl` para planilhas XLSX).

## Arquitetura

| Arquivo | Papel |
|---|---|
| `sped_model.py` | Núcleo: `SpedDocument` (carregar/salvar), `Registro`, hierarquia pai/filho, todos os cálculos fiscais. **Sem dependência de GUI.** |
| `sped_layouts.py` | Layout **completo** dos dois SPEDs (270 registros no ICMS/IPI, 203 no Contribuições): nomes de campos e nível hierárquico, extraídos dos guias práticos. |
| `sped_editor.py` | Toda a GUI (PyQt6): janela principal, grades, diálogos. |
| `sped_editor.ui` | Layout Qt Designer (carregado por `uic.loadUi`, com fallback programático). |
| `tema.py` | Paleta (claro/escuro) e folha de estilo QSS. **Toda cor da GUI sai daqui** — nunca literais no `sped_editor.py`. |
| `icones.py` | Ícones do QSS (✓ e chevron) desenhados em runtime na cor da paleta. |
| `xml_fiscal.py` | Parser de NF-e/NFC-e (`NFe`, `ItemNFe`, `ler_pasta`, `chave_doc`, `indexar`). |
| `conferencia.py` | Conferência XML × SPED (entradas modelo 55, C190) e correlações de CFOP. |
| `revisao.py` | Regras de revisão extensíveis (lista `REGRAS`). |
| `validacao.py` | Domínio de cada campo **por nome** (`DOMINIOS`), varredura do arquivo e normalização em lote. Detecta; só `normalizar()` grava. |
| `tabelas_pva.py` | Tabelas externas dos PVAs (códigos válidos, com vigência). |
| `descritor_pva.py` | **Descritor de validação** que cada PVA embarca no `.jar`: tipo/tamanho de cada campo, enumerações, referências entre registros e os validadores nomeados. É a fonte mais próxima de "como o PVA valida". |
| `diagnostico.py` | Roda as camadas de verificação do PVA e diz **qual módulo corrige** cada grupo. Executado ao abrir o arquivo. |
| `empresas.py` | Cadastro por CNPJ: regime federal e de PIS/COFINS, alíquotas, atividade. Persistido em `empresas.json` (fora do git). |
| `rotinas.py` | Rotinas de conferência/correção por regime (lista `ROTINAS`). Verificação nunca altera o arquivo; a correção recebe as ocorrências já exibidas. |
| `arquivos.py` | Memória persistente: cópia do SPED em `arquivos/<CNPJ>/<LEIAUTE>_<AAAAMM>.txt` + `indice.json`. Uma cópia por período. Fora do git. |
| `dados.py` | **Todo caminho de dado do usuário sai daqui** (`pasta_dados`, `caminho`). Empacotado grava em `%APPDATA%`; do código-fonte, na pasta do projeto. Nunca use `__file__` para gravar. |
| `janela_custom.py` | Barra de título própria via mensagens nativas do Windows (WM_NCCALCSIZE/NCHITTEST/GETMINMAXINFO). Padrão; `SPED_TABLES_BARRA_NATIVA=1` volta à do Windows. |
| `tabelas_rfb.py` | Tabelas oficiais da RFB (alíquota zero, monofásicos, gênero, NCM) e verificação de CST. **São duas tabelas de monofásico** — ver abaixo. |
| `pva.py` | Abre o PVA oficial e leva o arquivo salvo até a tela de importação (Ctrl+I + área de transferência). Win32 puro, sem dependência de GUI. |
| `version.py` | `__version__` e `APP_NAME`. SemVer. |

Regra geral: **lógica fiscal no modelo, nunca na GUI.** A GUI só chama métodos de
`SpedDocument` e apresenta o resultado.

## Convenções obrigatórias

- **SemVer** em `version.py` + entrada no `CHANGELOG.md` (formato Keep a
  Changelog) a cada mudança relevante; atualizar `README.md` quando a
  funcionalidade for visível ao usuário.
- **Patches direcionados**, nunca reescrita completa de arquivos.
- **Validar contra arquivos SPED reais** com números exatos, não só compilar.
- Formato numérico SPED: valor `1.234,56` (2 casas), alíquota `1,65` / `7,6`
  (vírgula, sem zeros à direita). Helpers no modelo: `_to_num`, `_fmt_val`,
  `_fmt_aliq`, `_fmt_qtd`.
- Encoding dos arquivos SPED e dos CSVs exportados: **latin-1**.

### Ao criar registros novos

Usar **`self._ncampos(tipo)`** para o tamanho do registro. Nunca
`len(campos(tipo, layout, 40))` — esse helper completa a lista com rótulos
`"Campo NN"` apenas para exibição, e usá-lo gera linhas com pipes sobrando (erro
de layout no PVA).

**Meça o tamanho ANTES de criar o primeiro registro do tipo.** `_ncampos` usa
a **moda dos registros já presentes** e só cai no layout quando não há nenhum.
Como `novo_registro` já insere o registro com um campo só, chamar
`self._ncampos(tipo)` **depois** dele devolve `1` — e sai `|0500|` no arquivo.
Guarde o número numa variável antes da criação (foi o que aconteceu ao criar o
0500 do plano de contas).

**Abriu um bloco, feche o bloco.** Quem cria o primeiro registro de um bloco que
ainda não existe no arquivo precisa criar também o **X990**. `gerar_texto`
reconstrói só o bloco 9, e `atualizar_bloco9_inplace` apenas *atualiza* os X990
que já existem — nenhum dos dois cria o que falta. Bloco aberto e não encerrado
é recusa certa no PVA (aconteceu com o H990 na importação de inventário).

### Ao ler valores de planilha

A célula numérica do Excel **come o zero à esquerda**: o NCM `04012010` chega
como `4012010` e o CEST `0200420` como `200420` (593 e 530 casos num arquivo
real). Use `_zero_a_esquerda(valor, tamanho)`, que só repõe quando falta
exatamente um dígito — nem NCM nem CEST começam com `00`. Para código de barras
o comprimento não decide (8, 12, 13 e 14 são todos válidos): `_gtin_corrigido`
só completa quando o **dígito verificador** confirma.

Número de planilha nunca vai para o arquivo via `str()`: `11.24` e `155.7` são
inválidos no SPED. Passe por `_fmt_val` / `_fmt_qtd` / `_fmt_aliq`.

Texto de célula sai por **`_texto_planilha()`**, nunca por `str(v or "")`: ERPs
exportam o `NULL` do banco por extenso, e o PVA recusa cada campo desses com
"Conteúdo de Campo inválido". A lista está em `VALORES_NULOS` — e `-` e `N/A`
estão fora dela de propósito, porque podem ser descrição legítima de produto.
O mesmo lixo aparece **dentro do SPED** que o cliente entrega (13.341 campos num
arquivo real): quem limpa é a ação *Limpar campos com NULL*.

### Ao mexer em cores ou estilo

Cor **nunca** entra literal no `sped_editor.py`: use os tokens de
`tema.atual()` (`ok`, `warn`, `bad`, `info`, `produto`, `somente_leitura`…) ou
a propriedade dinâmica `role` (`QLabel[role="ok"]`, `"erro"`, `"aviso"`,
`"dica"`, `"info"`, `"produto"`). Literal quebra o tema escuro. Só existe um
`setStyleSheet` no projeto — o global, em `main()`.

Cores gravadas em `QTableWidgetItem` (coluna REG, célula somente-leitura,
divergências) não seguem a folha de estilo: são decididas em Python e por isso
`alternar_tema()` remonta as abas.

### Idioma da interface

A tradução pt-BR do Qt é carregada em `instalar_traducao()`, chamada no
`main()`. Os tradutores ficam guardados em `app._tradutores` — sem manter a
referência, o coletor de lixo os leva e a interface volta ao inglês no meio do
uso. Em diálogos críticos, escreva o rótulo do botão à mão: os `.qm` podem não
ser empacotados no executável.

### Ao mexer na barra ou no menu

A janela nasce de **dois caminhos**: `uic.loadUi(sped_editor.ui)` quando o
arquivo existe, e o fallback programático `_criar_barra`. Só
`_montar_botao_ferramentas` roda nos **dois** — é ali que vão os itens que
precisam aparecer sempre (foi o que aconteceu com a ação *Empresas*).

O menu Ferramentas é agrupado por leiaute (`menu_icms`, `menu_contrib`,
`menu_gerais`); `abrir()` habilita/desabilita o submenu inteiro conforme
`doc.layout`.

### O leiaute é completo — e como mantê-lo assim

`sped_layouts.py` cobre os dois SPEDs inteiros, extraído registro a registro
dos guias práticos. Nos três arquivos reais de teste não sobra **nenhuma**
coluna "Campo NN" nem registro sem leiaute.

Ao reextrair, três coisas quebram silenciosamente se esquecidas:

- **Nome repetido no mesmo registro.** O guia chama de `ALIQ_PIS` tanto o
  percentual quanto o valor por unidade; `_ix` devolve sempre o primeiro, e o
  segundo ficaria inalcançável. A desambiguação mantém `ALIQ_PIS_QUANT`, que
  o código já usava.
- **O guia escreve nomes "sujos":** `COD_ NAT_CC` com espaço, `NÍVEL` com
  acento, `MES_REF *` com nota de rodapé. Sem normalizar, o campo é descartado
  e o registro sai curto.
- **Páginas com histórico têm mais de uma tabela de leiaute.** Vale a última
  (o M210 saía com 13 campos em vez de 16).

Largura nunca deve encolher: onde o guia trouxer menos campos que o layout já
validado contra arquivo real, prevalece o antigo — o guia é que está numa
versão anterior (E116, E310). Layout mais largo ou mais estreito que o arquivo
é inofensivo, porque `_ncampos` mede o registro pelo próprio arquivo.

### Como o PVA valida — e por que a granularidade é por registro

Cada PVA embarca, num `.jar`, um **descritor XML** por versão de leiaute:
`fiscalpva-dominio.jar` (ICMS/IPI) e `piscofinspva-infra.jar` (Contribuições).
Ali está, campo a campo, `tipo` (C/N/D), `tamanho` (`[3]` fixo, `60` máximo),
`casasdecimais`, `obrigatorio`, a enumeração
(`<valores-validos valores="0=Entrada;1=Saída"/>`), a tabela externa
(`datasource`) e a referência a outro registro
(`referenciaPesquisa="0200;COD_ITEM"`).

Três consequências que o código incorpora:

- **Valida-se por (registro, campo), não por campo.** No EFD Contribuições o
  `CST_PIS` tem tabela diferente no C175, no C181 e no C191; a regra global
  achatava isso.
- **Campo que o descritor não declara não é validado.** Era daí que vinha o
  falso positivo do `CST_ICMS` no EFD Contribuições — o PVA de lá não cobra
  aquele domínio, e cobrar produzia erro que o validador oficial não acusa.
  No Contribuições, nenhum `datasource` é tratado como tabela de validação:
  lá eles alimentam as listas da edição.
- **`referenciaPesquisa` substitui regra escrita à mão.** "COD_ITEM do C170
  tem de existir no 0200" passou a vir do descritor — 28 registros apontam
  para o 0200 no ICMS/IPI e 14 no Contribuições.

Os `<validador id="REGRA_..."/>` são regras compostas implementadas em Java
(ex.: `REGRA_CST_ICMS_CAMPOS_ICMS_C170`). O módulo registra **que existem**,
mas não as reimplementa: adivinhar o conteúdo produziria divergência
silenciosa com o validador oficial.

### Domínios que vêm dos PVAs, não do código

`tabelas_pva.py` lê as tabelas instaladas com os dois PVAs e monta os domínios
de campo. É a fonte preferida: a lista de códigos válidos acompanha a
atualização do validador oficial sem ninguém mexer no código. Quando o PVA não
está instalado, valem os domínios embutidos de `validacao.py`.

Quatro coisas que a implementação **precisa** respeitar:

- **Vigência.** Cada código traz DT_INI/DT_FIM. A tabela única de CST do ICMS
  foi revogada em 2012 — validar contra ela reprovaria o arquivo inteiro.
- **Códigos compostos.** Hoje o CST do ICMS é origem (`SIT_TRIB_ICMS_A`) +
  situação (`SIT_TRIB_ICMS_B`), montados em produto cartesiano.
- **Tabelas por UF.** Códigos de ajuste (E111, E116) são estaduais; a UF sai
  do 0000, como a data.
- **Zero à esquerda sobrando não é erro.** `COD_PAIS 01058` é o `1058` da
  tabela com um zero a mais, e o PVA aceita: tratar como erro produzia 141
  falsos positivos num arquivo real. Falta de dígito é outra coisa — essa
  vira sugestão. Código **só de zeros** é campo vazio disfarçado.

### Validação por domínio de campo

`validacao.py` não tem uma regra por situação: tem uma tabela de **domínios por
nome de campo**, aplicada a todo registro que possua o campo. Funciona porque no
SPED o nome carrega o domínio — `CFOP` é CFOP no C170, no C190 e no D190.

Três decisões que evitam estrago:

- **Só o que está preenchido é validado.** Obrigatoriedade depende do registro e
  da operação, não do nome do campo; cobrá-la ali geraria enxurrada de falso
  positivo.
- **Sugestão só quando falta exatamente um dígito.** Repor dois zeros é
  inventar. `sugestao=""` quer dizer "esvaziar" e `None`, "não sei consertar" —
  por isso a comparação é sempre `is None`.
- **Origem da mercadoria não se adivinha.** `CST_ICMS` e `CFOP` são apontados,
  nunca sugeridos. O erro mais comum ali nem é lixo: é o **CSOSN do fornecedor
  do Simples copiado sem o dígito de origem** (`101`, `201`), e o diagnóstico
  diz isso com todas as letras.

### Navegação mestre-detalhe

Filho não vira aba de bloco: `tipos_raiz_do_bloco` só devolve os **principais**
(sem pai, ou com pai de nível ≤ 1). O `H010` aparece no detalhe do `H005`, como
o `C170` no do `C100` — e o detalhe só é montado quando uma linha do mestre é
selecionada. Por isso grade de **uma linha só** se seleciona sozinha quando o
registro tem filhos: sem isso o bloco H, cujo `H005` é único, parecia vazio
mesmo com 11.585 itens dentro. Com várias linhas a seleção fica com o usuário,
senão as ações em lote agem sobre uma linha que ninguém escolheu.

Cada bloco abre na primeira sub-aba de **nível ≠ 1** — nível 1 é abertura e
encerramento (`C001`, `H001`, `H990`), de um campo só.

### O banco do PVA guarda o resultado das validações

Cada escrituração validada vira um banco em `mysql/data/bd<AAAAMMDDhhmmss>`,
com uma tabela `inconsistencia`: `ID_MENSAGEM`, `ID_CAMPO`, `VALOR_CAMPO`,
`VALOR_ESPERADO_CAMPO`, `NOME_REGISTRO`, `CONTEUDO_LINHA`, `NUMERO_LINHA`. O
`.MYD` (MyISAM) é legível sem subir o servidor.

Ele **não** guarda as regras — essas continuam no código Java. Mas guarda o
que elas produziram, e isso serve para duas coisas:

- **descobrir a condição** sem decompilar: `MSG_ALIQ_BASICA` com valor
  `1,6500` e esperado `0,65` diz exatamente o que a regra cobra;
- **testar uma reimplementação**: os casos que o PVA acusou são o gabarito
  contra o qual conferir se a regra nova acusa os mesmos registros.

Foi assim que nasceram `verificar_chave_duplicada` e
`verificar_data_fora_periodo` — e, depois, as outras sete.

Duas coisas mais valem a pena saber sobre esses bancos:

* **`master/escrituracao` liga cada banco ao arquivo que o gerou** (CNPJ,
  nome, caminho). É o que permite rodar a regra nova contra o mesmo arquivo
  que o PVA validou e comparar o número exato — foi assim que a regra do CFOP
  fechou em 20/20 e a do CST em 25/25.
* **Cada banco guarda a escrituração inteira** em tabelas `reg_<registro>`.
  Os campos-texto saem com um `strings`; os numéricos são decimais binários do
  MyISAM e exigiriam o `.frm` para decodificar.

O nome da classe Java que emite a mensagem diz quase tudo: `RegraIndEmit` lê
`IND_EMIT` e `IND_OPER`; `RegraValidaCSTALIQICMSC170` compara a data do 0000
com 01/04/2023; `RegraVlBcContIndNatPj` soma `VL_BC_PIS`/`VL_BC_COFINS` dos
filhos. Vale mais que decompilar: o bytecode não traz as condições, mas o
`getErro`/`getAdvertencia` diz até a severidade.

### CST do ICMS: a tabela boa é a composta

O PVA Fiscal publica `SIT_TRIB_ICMS_A` (origem), `SIT_TRIB_ICMS_B` (situação,
versão de 2009) **e** `SIT_TRIB_ICMS` — uma tabela única, versão 4, com 140
códigos e vigência. Vale a última: só ela traz os CSOSN do Simples (101, 102,
201, 202, 900) e os códigos de tributação monofásica de combustíveis criados
em 01/04/2023 (final 02, 15, 53 e 61). O produto cartesiano A × B não gera
nenhum dos dois, e usá-lo acusava **186 CST inválidos** num arquivo real que
o validador oficial aceita sem uma palavra.

O que o PVA cobra nesses códigos não é o CST, é a **alíquota**: CST com final
02 é monofásico de combustível e exige `ALIQ_ICMS > 0`. Quem escreve 102 num
C170 de entrada quase sempre copiou o CSOSN do fornecedor do Simples — e o
PVA acusa assim mesmo (`verificar_cst_combustivel_sem_aliquota`).

### O crédito do bloco M sai das entradas — e precisa ser refeito junto

Corrigir CST ou alíquota das **entradas** muda a base de crédito, e o
M100/M105 (PIS) e M500/M505 (COFINS) continuam como o ERP gravou. O PVA
confere os dois lados e recusa: o total do M105 tem de ser o somatório das
bases dos documentos por natureza, CST e alíquota, e M105 de um grupo que os
documentos não têm "não deverá existir". Num arquivo real foram 8 erros — 4
no M105, 4 no M505 — todos criados pela correção das alíquotas de crédito,
que fundiu quatro grupos (1,65 / 0,65 / 1,86 / 0) num só.

**O recálculo do bloco M não causava isso — ele só não consertava.** Rodar o
recálculo sobre um arquivo correto devolve o arquivo byte a byte idêntico
(conferido nos dois caminhos). O que faltava era refazer o crédito, e agora
`recalcular_bloco_m` faz: um M100 por alíquota, um M105 por (natureza, CST).

Quatro decisões que a implementação carrega:

- **A natureza da base vem do CFOP**, pela coluna `NAT_BC_CRE` da tabela
  4.3.7 do PVA (`CFOP_CREDITO`). Num arquivo real esse agrupamento reproduziu
  exatamente o rateio que o contribuinte já tinha no M105, inclusive o único
  item de natureza 02 — é a prova de que a fonte é a certa.
- **`COD_CRED` tem 3 dígitos: o primeiro é o tipo** (1 = alíquota básica,
  2 = diferenciadas, 3 = por unidade de medida) e os **dois últimos são a
  vinculação da receita** (01 tributada no mercado interno, 02 não tributada,
  03 exportação). A vinculação é decisão do contribuinte e não está nos
  documentos: vem do que já existe no arquivo. Só o tipo é redecidido pela
  alíquota. (Montar como "tipo de 2 dígitos + vinculação de 1" gera `011` em
  vez de `101`.)
- **O desconto vai até o limite do débito do período**, na ordem das
  alíquotas; o resto vira `SLD_CRED`, e `IND_DESC_CRED` sai 0 quando o
  crédito foi todo usado e 1 quando sobrou.
- **Quando não dá, não mexe** — e diz por quê: incidência que não seja
  exclusivamente não-cumulativa (a divisão da base entre os regimes não sai
  dos documentos), ajustes de crédito (M110/M115/M510/M515, que são filhos do
  M100 e não há como reatribuir), crédito fora do bloco C (D101, F100…) ou
  tabela do PVA ausente.

Ao criar os registros, `depois=` empilha meios (x+0,5; x+1,0; x+1,5…) e, com
grupos demais, a ordem inventada alcança a do registro seguinte — o M500
cairia depois do M600. Por isso `_reordenar()` no fim, que percorre a árvore e
devolve ordem inteira.

### Conferir o bloco M contra os documentos

`conferir_apuracao_m` compara o `VL_REC_BRT` e o `VL_BC_CONT` do M210/M610
com o somatório dos registros de receita, que é o que o PVA faz em
`MSG_VL_REC_BRT` e `MSG_VL_BC_CONT_IND_NAT_PJ`. O somatório é **o mesmo** que
`recalcular_bloco_m` usa para gerar os registros — de propósito: verificação e
correção que discordam produzem o pior dos mundos, um erro que o botão de
corrigir não conserta.

O bloco C não é a única fonte de receita (há A170, D201, F100...). Quando o
arquivo traz algum desses, a conferência se declara **parcial** e rebaixa a
gravidade para aviso, em vez de acusar diferença que o arquivo não tem.
`conferir_receitas_isentas` faz o mesmo para o M400/M800, por CST.

### Diagnóstico ao abrir: o que é fiel ao PVA e o que não é

`diagnostico.verificar()` roda ao abrir o arquivo e agrupa os problemas pelo
**módulo que os corrige**. A distinção abaixo precisa ser mantida — apagá-la
transformaria "nenhum erro" numa falsa aprovação:

- **fiel**, porque a declaração vem do descritor do próprio PVA: quantidade de
  campos, obrigatoriedade de campo, tipo/tamanho/decimais, enumeração, tabela
  externa, referência entre registros e bloco sem encerramento;
- **não reproduzido**: as ~1.400 regras compostas (`REGRA_CST_ICMS_CAMPOS_...`),
  implementadas em Java sobre o banco embutido. O bytecode não carrega as
  condições, e adivinhá-las criaria divergência silenciosa. O painel **lista**
  quantas se aplicam ao arquivo.

**Obrigatoriedade condicional não está no descritor.** O campo é declarado
obrigatório e uma regra Java o dispensa em certos casos. As exceções que dá
para afirmar ficam em `DISPENSAS`, nominalmente — a primeira foi
`C100.COD_PART`, dispensado na NFC-e: sem ela, um arquivo de supermercado
acusava 4.377 campos obrigatórios em branco que o PVA aceita, e os 5 casos
reais (modelo 55) sumiam no meio.

### O painel de revisão é um sumário, não uma lista

`DialogoRevisao` mostra **uma linha por verificação** — quantos erros e qual
função corrige —, não uma linha por ocorrência. A versão anterior listava
1.887 itens dizendo "COD_ITEM tal não é referenciado" numa tela onde não havia
como corrigir nenhum. A lista detalhada existe em `DialogoOcorrencias`, atrás
do botão *Ver ocorrências*, e só faz sentido quando a correção é manual.

Regra ao criar uma verificação nova: se ela tem função que corrige, registre o
atalho em `acoes` (o mapa é por **rótulo da lista `REGRAS`**, não pelo texto
de `Problema.regra`, que é mais curto).

### Ao adicionar ações na GUI

Padrão em quatro pontos: criar a `QAction` em `_criar_acoes`, conectar
defensivamente em `_conectar_ui` (com `hasattr`, para `.ui` antigos), incluir em
`_montar_botao_ferramentas` e habilitar em `abrir()` conforme
`doc.layout` (`"ICMS"` ou `"CONTRIB"`). Diálogos não-modais (`show()`) precisam de
referência guardada (`self._dlg_x`) para não serem coletados.

**Pular o segundo ponto derruba a janela inteira.** `_criar_acoes` só roda no
fallback; com o `.ui` presente — o caso normal — quem roda é `_conectar_ui`, e
`_montar_botao_ferramentas` (que roda nos dois) estoura com `AttributeError` no
construtor. Já aconteceu com *Empresas* e de novo com *Limpar campos com NULL*.
Depois de mexer em ação ou menu, confira que a janela nasce:

```bash
QT_QPA_PLATFORM=offscreen py -c "import sped_editor as e;from PyQt6.QtWidgets import QApplication;a=QApplication([]);e.JanelaPrincipal();print('ok')"
```

O PyQt6 está no interpretador do `py` (`pythoncore-3.14-64`), não no `python`
do PATH — daí `py` no comando acima. E o `a=` não é enfeite: sem guardar a
referência, o `QApplication` é coletado antes do widget nascer e o processo
morre com **exit 127 e nenhum traceback** — o mesmo sintoma da barra de título
e dos tradutores.

## Abrir o PVA já com o arquivo

Não há linha de comando para isso: os dois PVAs aceitam só `-buildVersion` e
`-atualizarTabelas`. O que existe é o `ppgdmenubar.xml` que cada um carrega do
próprio `.jar`, e nele o acelerador **Ctrl+I** para *Escrituração → Nova →
Importar*. A janela que abre é um `JFileChooser`
(`FileChooserSelecionarArquivo`) cujo foco nasce no campo "Nome do arquivo:" —
então basta colar o caminho e dar Enter.

Cinco coisas que custaram tentativa:

- **A tela de abertura (splash) tem o mesmo nome da aplicação.** Casar a
  janela por "Sped Fiscal" pegava a splash, que não aceita foco, e a
  automação morria aos 6 segundos com o PVA ainda carregando. O casamento é
  pelo **título inteiro**, o do `aplicacao.properties`.
- **A janela principal aparece muito antes de aceitar atalhos.** Depois dela
  vem um carregamento interno, e enquanto ele roda o processo mantém uma
  **segunda janela** — a barra de progresso. Medido numa partida a frio do
  PVA Fiscal: janela aos 4 s, Ctrl+I só aceito aos **11,9 s**, exatamente
  quando a contagem de janelas do processo caiu de 2 para 1. É esse o sinal
  que `_esperar_pronta` usa. Os atalhos enviados no meio são **engolidos, não
  enfileirados** — foi o que permitiu, por garantia, repetir o Ctrl+I até o
  seletor abrir sem risco de abrir dois.
- **Só o processo dono do primeiro plano pode dar o primeiro plano a outro.**
  Clicando no nosso botão, o dono somos nós e o `SetForegroundWindow` passa;
  fora disso ele é ignorado **em silêncio**. O contorno é anexar a fila de
  entrada da nossa thread à da thread que está na frente
  (`AttachThreadInput`) durante a troca.
- **Detectar o seletor por "apareceu janela nova do processo", não por
  "está em primeiro plano".** Qualquer janela que roube o foco no meio
  derrubava a detecção de uma tela que tinha aberto direitinho.
- **Nenhuma tecla é enviada sem antes conferir o primeiro plano.** Num teste
  meu que pulou essa conferência, o Ctrl+A/Ctrl+C foi parar noutra janela e
  copiou texto de lá. Não dando certo, o caminho fica na área de
  transferência e a mensagem diz o que falta fazer à mão.
- **O PVA tem trava de instância única** (`TryLock.txt`): havendo janela, ela
  é trazida para a frente; a segunda execução só mostraria um erro.

A automação **para antes das confirmações**: depois do Enter no seletor, o
PVA abre um "Aviso" pedindo para confirmar a importação e, terminada ela,
outro perguntando se quer validar. Os dois são decisão do usuário, e é assim
que deve ficar — responder "sim" por conta própria importaria e validaria sem
ninguém ter pedido.

E a de sempre com ctypes: `GetClipboardData` **precisa** de `restype`
declarado. Sem ele o handle de 64 bits é truncado, o `GlobalLock` falha e a
leitura volta vazia — foi assim que um teste deu "campo vazio" com o campo
preenchido.

## Armadilha: scripts de teste que sombreiam o stdlib

Os testes põem a própria pasta no `sys.path`. Um arquivo chamado `bisect.py`,
`types.py`, `select.py` ou qualquer outro nome da biblioteca padrão passa a ser
importado no lugar do módulo real — e, como o import **executa** o arquivo, o
sintoma é surreal: o teste A imprime a saída do script B, o processo morre sem
traceback e o diagnóstico vai para o lado errado (já custou horas aqui).
Use nomes com prefixo (`teste_`, `montar_`) nos scripts auxiliares.

## Ao mexer na barra de título

**Nunca chamar `super().nativeEvent(...)`** — no PyQt6 isso derruba o processo
sem traceback. Devolva `(False, 0)` para "não tratei".

**Estruturas ctypes e `argtypes` definidos uma única vez, no import.** Criar
`RECT` dentro de uma função gera um tipo novo a cada chamada, e o ctypes
compara tipos por identidade — o erro estoura dentro do despacho de mensagens,
onde ninguém o vê. Foi o que fez o console "piscar e fechar" na 0.19.0.


A interceptação só pode começar **depois** de `janela_custom.aplicar()` ter
preparado a janela (primeiro `showEvent`): tratar WM_NCCALCSIZE durante a
criação do HWND é falha nativa, sem traceback. Toda chamada Win32 precisa de
`argtypes` declarados — sem isso o ctypes trunca o HWND de 64 bits para `int`.

## Armadilha recorrente (já ocorreu duas vezes)

Edições por substituição de texto já **removeram a linha `def` de um método**,
deixando o corpo como código inacessível após o `return` do método anterior. O
arquivo continua compilando e o `py_compile` não acusa — o erro só aparece em
runtime como `AttributeError`. Afetou `consolidar_c175_de_itens` e
`_registros_aliq_escopo`.

Verificação após qualquer edição estrutural:

```bash
python -c "
import ast
for f in ['sped_model.py','sped_editor.py','conferencia.py','revisao.py','xml_fiscal.py','tabelas_rfb.py']:
    t=ast.parse(open(f,encoding='utf-8').read())
    p=[(n.name,s.lineno) for n in ast.walk(t) if isinstance(n,ast.FunctionDef)
       for i,s in enumerate(n.body[:-1]) if isinstance(s,ast.Return)]
    print(f, p or 'ok')
"
```

## Índices de campos validados

Obter sempre por nome (`doc._ix(tipo, nome)`), nunca por número fixo. Referência:

- **C100 (ICMS):** IND_OPER 1, COD_MOD 4, SER 6, NUM_DOC 7, CHV_NFE 8, DT_DOC 9,
  DT_E_S 10, VL_DOC 11, VL_DESC 13, VL_MERC 15, VL_FRT 17, VL_SEG 18,
  VL_OUT_DA 19, VL_BC_ICMS 20, VL_ICMS 21, VL_BC_ICMS_ST 22, VL_ICMS_ST 23,
  VL_IPI 24
- **C170 (ICMS):** NUM_ITEM 1, COD_ITEM 2, QTD 4, UNID 5, VL_ITEM 6, VL_DESC 7,
  CST_ICMS 9, CFOP 10, VL_BC_ICMS 12, ALIQ_ICMS 13, VL_ICMS 14
- **C170 (CONTRIB):** CST_PIS 24, VL_BC_PIS 25, ALIQ_PIS 26, VL_PIS 29,
  CST_COFINS 30, VL_BC_COFINS 31, ALIQ_COFINS 32, VL_COFINS 35 — 37 campos
- **C175 (CONTRIB):** CFOP 1, VL_OPR 2, VL_DESC 3, CST_PIS 4, … VL_COFINS 15 —
  18 campos
- **C190 (ICMS):** CST_ICMS 1, CFOP 2, ALIQ_ICMS 3, VL_OPR 4, VL_BC_ICMS 5,
  VL_ICMS 6, VL_BC_ICMS_ST 7, VL_ICMS_ST 8, VL_RED_BC 9, VL_IPI 10 — 12 campos
- **H010:** COD_ITEM 1, UNID 2, QTD 3, VL_UNIT 4, VL_ITEM 5, IND_PROP 6 — 11 campos
- **0200:** COD_ITEM 1, DESCR_ITEM 2, UNID_INV 5, TIPO_ITEM 6, COD_NCM 7 — 13 campos
- **E110:** VL_TOT_DEBITOS 1, VL_TOT_CREDITOS 5, VL_SLD_CREDOR_ANT 9,
  VL_ICMS_RECOLHER 12, VL_SLD_CREDOR_TRANSPORTAR 13

## Regras fiscais já implementadas (não regredir)

- **Rateio de despesas acessórias (C190):** usar **diferença de acumulados
  arredondados**, não `round()` item a item — senão a soma não fecha com o total
  (caso real: 1,50 de VL_OUT_DA virava 1,52).
- **Total que soma itens arredonda uma vez só:** o `VL_INV` do H005 acumulava o
  valor bruto e arredondava no fim, enquanto cada H010 gravava o arredondado —
  um centavo de diferença em 11.585 itens. Arredonde no ponto em que o valor é
  calculado e use o mesmo número nos dois lugares.
- **VL_RED_BC (C190):** nos CST terminados em **20** ou **70**,
  `VL_OPR − VL_BC_ICMS` (nunca negativo). No **x70** o ICMS foi cobrado por
  ST e não há base própria: quando o item tem **base de PIS/COFINS**, ela
  entra no lugar da base de ICMS só para achar a diferença — o `VL_BC_ICMS`
  do C190 continua zero. Sem nenhuma das duas bases, a redução fica em zero e
  o caso é apontado para conferência manual, nunca chutado.
- **Situação do ICMS pelo CST** (`situacao_icms`): os **dois últimos dígitos**
  decidem — x20/x70 têm base reduzida; x30/x40/x41/x50/x60 não geram débito
  próprio; o resto é tributado. O primeiro dígito é a origem da mercadoria e
  não entra no cálculo.
- **Recalcular ICMS não toca no ICMS-ST:** base e alíquota da ST são outras,
  muitas vezes com MVA.
- **Bloco M:** ordem do leiaute é M200 → M205 → M210 (o M205 vem **antes** do
  M210); idem M600 → M605 → M610.
- **NFC-e modelo 65:** não tem C170 — é consolidada em C175 (PIS/COFINS) e C190
  (ICMS). O fluxo de validação por item cria C170 "fictícios" a partir do XML e
  depois os remove ao regenerar o C175.
- **Conferência de entradas:** o CFOP do XML é o de saída do fornecedor e difere
  do CFOP de entrada do SPED — casar por `nItem` e usar a classificação do
  **C170** para agrupar, não o CFOP do XML.
- **Monofásicos na revenda não geram crédito:** entrada de bebida (NCM 2202/2203/
  2208) com CST 50 é creditamento indevido (correto 73/98). A correção
  (`rotinas.corrigir_cst_ncm`) só age onde o crédito **está sendo tomado**
  (CST 50-56 / 60-66): troca o CST e zera base, alíquota e valor. Item já num
  CST sem crédito não é tocado — 70, 73 e 98 se distinguem pelo motivo da
  vedação, e trocar um pelo outro sem saber o motivo é palpite. **Saídas ficam
  de fora**: lá o CST depende de revenda ou produção própria, e alíquota
  diferenciada (02/03) é legítima.
- **Regime (empresas.py / rotinas.py):** cumulativo = PIS 0,65 / COFINS 3,00 e
  **sem crédito** na entrada; não-cumulativo = 1,65 / 7,6 com crédito. No regime
  **"ambos"** as rotinas de alíquota **se abstêm** — as duas alíquotas convivem
  legitimamente no mesmo arquivo.
- **TIPO_ITEM do 0200 só aceita 00 a 10 e 99** (`TIPOS_ITEM_0200`). ERP que
  exporta a coluna errada grava ali a origem da mercadoria ou um `N` de
  nacional. Vale a regra geral: **planilha do cliente não é verdade absoluta**
  — a mesma que corrigia 447 NCM truncados plantaria `TIPO_ITEM` inválido em
  1.273 itens certos. Correção em massa mostra a prévia e deixa escolher campo
  a campo (`previa_atualizacao_0200`).
- **Monofásico são DUAS tabelas do PVA, não uma.** `PROD_MONO_ALIQ_UNID`
  (4.3.11) traz combustíveis e bebidas frias, com alíquota por unidade de
  medida; `PROD_MONO_ALIQ_DIFER` (4.3.10) traz perfumaria, higiene pessoal,
  medicamentos, veículos e autopeças — a Lei 10.147/2000. Ler só a primeira
  fazia o sabonete (NCM 34011190) passar limpo enquanto o PVA o acusava.
  `carregar_tudo` funde as duas e a versão exibida vira `40+37`.
- **Só o CST 01 tem alíquota conferível:** 02 é "alíquota diferenciada" e 03 é
  por quantidade. Cobrar deles a alíquota nominal gera falso positivo.

## Empresa usada na validação

CASA DO ESPETO LTDA — CNPJ 22763092000102, MG, comércio/revenda. Os arquivos SPED
e XMLs reais usados nos testes ficam fora do repositório.

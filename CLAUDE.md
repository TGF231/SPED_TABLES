# SPED Tables — contexto do projeto

Aplicativo desktop **PyQt6** para editar arquivos fiscais **SPED** (EFD ICMS/IPI e
EFD Contribuições) numa interface mestre-detalhe estilo planilha.

**Idioma: todo o código, comentários, documentação e conversa em português do
Brasil.**

## Executar e testar

```bash
py sped_editor.py [arquivo.txt]
py -m unittest discover -s tests -t .
```

O PyQt6 está no interpretador do `py` (`pythoncore-3.14-64`), não no
`python` do PATH. Dependências em `requirements.txt` (PyQt6; `openpyxl` para
planilhas XLSX). A suíte (~190 testes, ~11 s) roda **antes de todo commit**;
ver `TESTES.md`.

## Arquitetura

Camadas com portas e adaptadores — a explicação completa, com o porquê, está
em `ARQUITETURA.md`. **As dependências só apontam para dentro**, e
`tests/test_arquitetura.py` reprova quem desobedecer:

```
interface ──► aplicacao ──► dominio ◄── infra
    └──────────────────────► infra
```

| Camada | Pode importar | Módulos |
|---|---|---|
| `sped_tables/dominio/` | só o domínio (nem Qt) | `sped_model` (`SpedDocument`, todos os cálculos), `sped_layouts` (leiaute completo: 270 registros no ICMS/IPI, 203 no Contribuições), `validacao`, `revisao` (lista `REGRAS`), `rotinas` (lista `ROTINAS`), `diagnostico`, `conferencia`, `ncm` (classificação do NCM e CST esperado), `empresas` (a entidade), `xml_fiscal`, **`referencias` (a porta)** |
| `sped_tables/infra/` | domínio | `config` (**ponto único de configuração**), `dados` (pasta de dados, gravação atômica, recursos), `descritor_pva`, `tabelas_pva`, `tabelas_rfb` (leitura), `referencias_pva` (**o adaptador**), `cadastro` (empresas e correlações em JSON), `arquivos` (acervo), `exportacao` (CSV), `pva` (automação Win32), `falhas` (registro e ganchos) |
| `sped_tables/aplicacao/` | domínio, infra | `sessao` (arquivo aberto: abrir/salvar/fechar + acervo), `envio_pva` (pré-checagem, envio, desfecho), `montagem` (**raiz de composição**) |
| `sped_tables/interface/` | todos | `app` (`main`), `janela`, **`acoes` (tabela única de ações)**, `controladores/` (mixins da janela por área do menu), `grade`, `telas/`, `dialogos/`, `formulario_empresa`, `comum`, `tema`, `icones`, `barra_titulo`, `janela_custom`, `autoteste` (`--autoteste`: o roteiro 2.2 de dentro do executável) |

`sped_editor.py` na raiz é só o lançador. `sped_tables/version.py` tem
`__version__`, `APP_NAME` e `canal()`.

Regras gerais:

- **Lógica fiscal no domínio, nunca na interface.** A interface chama o
  domínio (ou um caso de uso) e apresenta o resultado.
- **Nada do domínio lê a instalação do PVA.** O que precisa de tabela
  oficial pergunta a `referencias.atual()`; `montagem.configurar()` liga o
  adaptador do PVA no início do programa e da suíte. Sem fonte ligada, a
  fonte é vazia e as regras se abstêm. Teste liga fonte inventada com
  `referencias.definir(...)` e restaura.
- **Todo caminho sai de `config` (PVA) ou `dados` (pasta do usuário).**
  Nunca `__file__` para achar dado; recurso empacotado é `dados.recurso()`.
- **A janela não guarda o estado do arquivo:** `doc`, `caminho` e `alterado`
  são propriedades que leem `self.sessao`.

## Convenções obrigatórias

- **SemVer** em `sped_tables/version.py` + entrada no `CHANGELOG.md`
  (formato Keep a Changelog) a cada mudança relevante; atualizar `README.md`
  quando a funcionalidade for visível ao usuário.
- **A versão declara o canal** (`version.canal()`): toda a série 0.y.z é
  desenvolvimento; `-dev`, `-alpha`, `-beta`, `-rc` também. Numa release só
  aparece ação com `pronta=True` (`acoes.visiveis()`). Não existe função
  "parcial" numa release — ver `ROADMAP.md`.
- **Nenhum dado de cliente no repositório** — nem arquivo, nem nome, nem CNPJ,
  nem em documentação. Os testes usam `tests/fabrica.py`; os arquivos reais
  ficam fora, apontados por `SPED_TABLES_ARQUIVOS_REAIS`.
- **Patches direcionados**, nunca reescrita completa de arquivos.
- **Validar contra arquivos SPED reais** com números exatos, não só compilar:
  `tests/test_reais.py` com o `gabarito.json` da pasta dos arquivos reais.
  Mudança que altera o gabarito precisa ser explicada no CHANGELOG.
- Formato numérico SPED: valor `1.234,56` (2 casas), alíquota `1,65` / `7,6`
  (vírgula, sem zeros à direita). Helpers no modelo: `_to_num`, `_fmt_val`,
  `_fmt_aliq`, `_fmt_qtd`.
- Encoding dos arquivos SPED e dos CSVs exportados: **latin-1**.
  Na **leitura**, porém, tente UTF-8 primeiro: `latin-1` aceita qualquer byte
  e **nunca levanta `UnicodeDecodeError`**, então pô-lo à frente numa lista de
  tentativas transforma as demais em código morto — era o caso do SPED e do
  CSV de inventário, e arquivo exportado em UTF-8 entrava com a acentuação
  corrompida (no CSV, com o BOM grudado no nome da primeira coluna, o que
  sozinho já quebrava o mapeamento do cabeçalho). Texto latin-1 com acento não
  é UTF-8 válido, então a ordem `utf-8-sig, utf-8, latin-1` acerta os dois.
  A **gravação** continua sempre latin-1 (`doc.encoding`); o que o arquivo de
  origem usava fica em `doc.encoding_lido`, e abrir um SPED em UTF-8 e salvar
  aqui conserta o arquivo.

### Ao criar registros novos

**`novo_registro` já entrega o registro com a largura do leiaute** — mede
`_ncampos(tipo)` antes de inserir e preenche o resto com vazios. Quem monta o
conteúdo pode sobrescrever `campos` inteiro, como sempre; quem não monta
(o botão "+" da grade) recebe a linha certa de graça.

**O bloco 9 mantém a ordem dos 9900 que o arquivo tinha.** Cada ERP usa a
sua (alfabética, a dos blocos do leiaute); reordenar fazia "abrir e salvar
sem mexer" devolver outro arquivo. Tipo novo entra no fim.

Até a 0.49.0 não era assim: o registro nascia com **um campo só**, e a linha
criada pela grade saía `|C170|` no arquivo — recusa certa no PVA por
quantidade de campos. Era o único dos 14 pontos que criam registro que não
redimensionava nada.

Usar **`self._ncampos(tipo)`** para o tamanho. Nunca
`len(campos(tipo, layout, 40))` — esse helper completa a lista com rótulos
`"Campo NN"` apenas para exibição, e usá-lo gera linhas com pipes sobrando (erro
de layout no PVA).

**Meça o tamanho ANTES de criar o primeiro registro do tipo.** `_ncampos` usa
a **moda dos registros já presentes**, então um registro recém-inserido puxa a
moda para baixo. `novo_registro` faz essa medição no lugar certo; quem precisa
do número para outra coisa (o 0500 do plano de contas) guarda numa variável
antes da criação.

**Quem refaz registros mede antes de remover os antigos.** C190, C175 e
M210/M610 são apagados e recriados; sem os antigos no arquivo, `_ncampos`
cai no leiaute conhecido e perde a largura do arquivo (versão de leiaute mais
nova). O padrão: `largura = self._ncampos(tipo)` antes de remover e
`self._preencher(novo, valores, largura)` ao gravar a linha — os campos a
mais ficam vazios em vez de sumir. A posição sai de `_ancora_antes(pai,
reg)`, que devolve o último filho de código menor (é assim que o 0190 novo
cai depois do 0150, e não logo após o 0001).

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

E número de planilha que **grava** passa por **`num_planilha_estrito()`**, nunca
por `_to_num_planilha`: esta lê `abc`, `1.2.3` e `NULL` como zero, e o item
entrava no inventário com quantidade zerada. A importação confere **todas** as
células numéricas antes de mexer no arquivo e recusa com `CelulasInvalidas`,
dizendo a linha da planilha (`_linha`, que o diálogo preenche). Conferências
que só **contam** (a prévia do inventário) podem continuar lenientes.

Texto de célula sai por **`_texto_planilha()`**, nunca por `str(v or "")`: ERPs
exportam o `NULL` do banco por extenso, e o PVA recusa cada campo desses com
"Conteúdo de Campo inválido". A lista está em `VALORES_NULOS` — e `-` e `N/A`
estão fora dela de propósito, porque podem ser descrição legítima de produto.
O mesmo lixo apareceu **dentro de um SPED** antes de qualquer importação
(13.341 campos num arquivo real, de origem não identificada — não foi o ERP).
Ali quem acusa é a **validação de leiaute**, em qualquer campo, inclusive nos de
texto livre, e quem corrige é o *Normalizar*. Até a 0.55.0 havia uma ação à
parte, *Limpar campos com NULL*: era a mesma detecção em dois lugares.

### Validar na entrada, nunca tolerar em silêncio

Regra da 0.56.0: o que está errado é **acusado** onde entra, e a correção é
explícita, com prévia. Tolerância silenciosa esconde o erro e piora o arquivo.
Quatro lugares faziam isso e não fazem mais:

- **Leitura do SPED.** Linha sem o `|` inicial ia embora (e sumia ao salvar);
  linha sem o `|` final perdia o **último campo** — o `[1:-1]` do `Registro`
  supõe o pipe. Agora a primeira fica em `doc.linhas_invalidas` (salvar
  levanta `LinhasInvalidas`, e a GUI pergunta antes de gravar sem elas) e a
  segunda é lida inteira e anotada em `doc.sem_pipe_final`. As duas viram
  achado do diagnóstico e impedem o envio ao PVA.
- **Números nos cálculos que gravam.** `_to_num` lê lixo como zero, e é
  certo que leia — mas cálculo que **grava** chama antes
  `_exigir_numeros(registros)`, que levanta `CamposInvalidos` sem ter mexido
  em nada. A regra de "número do SPED" (`RE_NUM_SPED`, `PREFIXOS_NUMERICOS`)
  mora no `sped_model` e a validação de leiaute importa dali: o que ela acusa
  é exatamente o que os cálculos recusam. **Cálculo novo que grava chama
  `_exigir_numeros` sobre tudo o que lê, antes do primeiro `set_valor`**; na
  GUI, passa por `comum.calcular(...)`.
- **JSON do usuário.** Cadastro, correlações, acervo e configuração ilegíveis
  viravam vazio e eram sobrescritos no próximo salvamento. Agora
  `dados.ler_json_do_usuario(caminho, tipo)` guarda o arquivo como
  `.corrompido-<data>` e avisa (`dados.ao_avisar`, ligado no `main()`).
- **NULL** — acima.

### Ao mexer em cores ou estilo

Cor **nunca** entra literal na interface: use os tokens de
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

Uma ação é **uma linha** de `interface/acoes.py`: atributo, rótulo, método da
janela, quando fica habilitada (`SEMPRE`, `ARQUIVO`, `ICMS`, `CONTRIB`,
`COM_PVA`), onde aparece (`BARRA`, `MENU_ICMS`, `MENU_CONTRIB`,
`MENU_GERAIS`) e se está `pronta`. A janela cria, conecta, põe no menu e
habilita tudo a partir dela (`_montar_acoes`, `_montar_barra_ferramentas`,
`_habilitar_acoes`). O método vai no controlador da área
(`interface/controladores/`).

Até a 0.52.0 cada ação existia em quatro lugares e a janela nascia por dois
caminhos (o `.ui` do Qt Designer e um fallback); esquecer um ponto derrubou
a janela duas vezes e deixou *Conferir entradas (NF-e 55)* fora de todos os
menus. O `.ui` saiu. `tests/test_interface.py` confere que todo método da
tabela existe, que toda ação visível está num menu ou na barra e **dispara
cada ação** nos dois leiautes.

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
  achatava isso. A chave de `dominios_do_documento` é a **tupla**
  `(registro, campo)` — quem a tratar como nome de campo quebra em silêncio
  até o dia em que roda: foi o que aconteceu com o resumo da tela de
  validação, onde um `", ".join(sorted(dominios))` sobre tuplas levantava
  `TypeError`. **Exceção dentro de um slot do Qt derruba o processo**, então
  a ação inteira virou "o programa fecha sozinho" durante três versões, sem
  que nenhum teste visse: o teste da GUI montava o diálogo direto, pulando o
  método do menu. Teste de ação de menu chama a ação, não o diálogo.
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
  diz isso com todas as letras. Isso vale também para o domínio que vem das
  **tabelas do PVA** (`CAMPOS_DE_DECISAO`, `dominio_de_tabela`): até a 0.53.0
  o `CST_ICMS` = `0` recebia a sugestão "esvaziar" por ser "só zeros", e a
  normalização em lote apagava o CST de itens do C170/C190.
- **`normalizar()` sem lista usa os mesmos domínios do diagnóstico**
  (`dominios_do_documento`). Com os embutidos, o que o diagnóstico acusava
  pelas tabelas do PVA ficava sem conserto.

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
atalho no mapa `acoes` de `ControladorGerais.revisar_erros` (o mapa é por
**rótulo da lista `REGRAS`**, não pelo texto de `Problema.regra`, que é mais
curto). Para o diagnóstico, o mapa equivalente fica em
`ControladorGerais.diagnosticar`.

### Ao adicionar ações na GUI

Uma linha em `acoes.ACOES` + o método num controlador. Função que ainda não
cumpre o critério de aceite do `ROADMAP.md` entra com `pronta=False`.
Diálogos não-modais (`show()`) precisam de referência guardada
(`self._dlg_x`) para não serem coletados.

**Exceção num slot do Qt encerra o processo** quando o `sys.excepthook` é o
padrão. O `main()` instala `infra/falhas.py`, que troca isso por registro em
`logs/`, cópia de emergência em `recuperacao/` e um aviso; mas os testes que
montam a janela sem `main()` continuam sem essa rede — por isso o teste de
interface instala um gancho que **reprova** qualquer exceção.

O `QApplication` precisa de referência guardada: sem ela, é coletado antes do
widget nascer e o processo morre com **exit 127 e nenhum traceback** — o
mesmo sintoma da barra de título e dos tradutores. Na suíte, use `_app()` de
`tests/test_interface.py`.

## Abrir o PVA já com o arquivo

A automação é `infra/pva.py`; a decisão em volta dela (pré-checagem, como
apresentar cada desfecho) é `aplicacao/envio_pva.py`; a espera com barra de
progresso e cancelar, `ControladorArquivo.abrir_no_pva`.

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

**Escrituração aberta desabilita o Importar.** Com uma escrituração em
edição — o estado em que fica quem deixa o PVA aberto no arquivo do mês —, o
menu *Nova → Importar* fica cinza e o Ctrl+I não faz nada. Era isso que
travava o EFD ICMS/IPI. A segunda tentativa manda **Ctrl+F** (Fechar) antes
do Ctrl+I: a escrituração continua no banco do PVA e reabrir é Ctrl+A. Se o
Ctrl+F abrir diálogo, a automação para e devolve a decisão ao usuário.

**O PVA atravessa o caminho com telas próprias.** Na abertura ele pode pedir
*Atualizar Tabelas* (lista as tabelas obrigatórias à validação, com Ok e
Cancelar — e o foco nasce na árvore, então Enter não aciona botão nenhum),
depois mostra *Transferindo Tabelas* e uma *Mensagem* de conclusão. Nenhuma
delas é respondida por conta própria: são classificadas em `_classificar` e
**esperadas**, com o motivo dito no andamento. Só assim a automação retoma
sozinha em vez de anunciar que não conseguiu.

**A tela de progresso sumir não quer dizer sucesso.** Quando o arquivo tem
erro de estrutura, o PVA fecha o *Importando…* e abre um **Erro** —
"Importação não realizada. Ocorreram erros na estrutura do arquivo" — e um
*Resultado da Importação* com o relatório. Sem checar esse Erro, arquivo
recusado era anunciado como importado. Num arquivo real foram 1.000 erros
(o teto do PVA): 634 "Conteúdo de Campo inválido" e 366 "Tamanho do campo
inválido", em `TIPO_ITEM`, `COD_GEN` e `CEST`.

Daí a **pré-checagem**: `diagnostico.impedem_importacao` separa os achados
que o PVA recusa já na importação (`nulo`, `formato`, `num_campos`, `bloco`,
`dominio`) e a GUI pergunta antes de abrir o PVA. `obrigatorio` fica de fora
de propósito: num arquivo real do Contribuições havia 25 campos obrigatórios
em branco pelo descritor e o PVA importou sem reclamar.

**As duas confirmações são respondidas — e conferidas pelo efeito.** Depois
do Enter no seletor o PVA abre um "Aviso" ("deseja importar?", só quando
há escrituração a substituir — ver abaixo) e, terminada a
importação, outro ("deseja validar?"). Os dois vêm do mesmo
`ExibirMensagem.solicitarConfirmacao`, um `JOptionPane` cujo botão padrão
responde ao Enter. Como "apertei Enter" não prova nada, o sucesso é medido
pela tela de progresso que **tem de** aparecer em seguida — `Importando a
escrituração…` e `Validando a escrituração…`. Não aparecendo, a automação
para e diz o que falta: é isso que impede responder no escuro a um aviso que
fosse outra coisa.

**O primeiro aviso só existe quando há o que substituir.** Escrituração
nova (CNPJ e período que o PVA ainda não tem) vai do seletor direto ao
`Importando…`, sem pergunta. Até a 0.54.0 a automação esperava o aviso
assim mesmo, pegava o **seguinte** ("Deseja fazer a validação de conteúdo
agora?"), dava Enter nele achando que era o da importação e anunciava "não
consegui confirmar" de um arquivo importado e validado. Agora a tela de
progresso vista antes de qualquer aviso encerra a espera
(`_confirmar_aviso`, com as duas sequências em `tests/test_pva.py`).

**"Erro" depois da validação não é recusa.** Validação que acha erros
termina num diálogo "Erro" ("O arquivo contém erros e avisos"). A recusa da
importação é o "Erro" **mais** o "Resultado da Importação" — é a checagem
logo depois do `Importando…` que as separa, e o roteiro de validação marca
recusa só pelo relatório.

Importar sem validar não fecha o ciclo: o que interessa é o relatório de erros
do PVA. Por isso `validar=True` é o padrão.

**Importar o mesmo CNPJ e período apaga a escrituração anterior** — o PVA
remove o banco `bd…` antigo e cria outro. Por isso o roteiro de validação
(`ferramentas/validar_no_pva.py`) roda numa **cópia da instalação**, com
porta de banco própria, e a automação só dirige janela cujo executável está
dentro da pasta indicada (`pva.janela` confere o caminho do processo).

**Depois de validar, o PVA deixa dois diálogos modais** — "Mensagem" (o
arquivo foi validado com sucesso) e "Aviso" (pronta para entrega) — e, com
eles abertos, o próximo Ctrl+I é engolido. Importação recusada deixa um
"Erro" e o "Resultado da Importação". O roteiro fecha os dois tipos antes e
depois de cada arquivo (`_dispensar_conclusao`); o botão da GUI não, porque
ali quem lê o resultado é o usuário.

**Acesso remoto com modo privacidade bloqueia toda entrada sintética.** No
AnyDesk em modo privacidade, `SendInput`/`keybd_event` são descartados em
silêncio: o foco troca, as teclas não chegam. Antes de suspeitar do PVA,
teste numa janela Tk própria — nunca numa janela do usuário (um teste que
casou o título "Notepad" fechou o Notepad++ dele).

**Toda espera é cancelável.** O usuário pode levar 15 minutos para responder a
um diálogo do PVA, e nesse tempo a janela de espera prendia o programa inteiro
sem saída. `pva.abrir` recebe `cancelar` (uma função consultada nas esperas) e
levanta `Cancelado` — exceção, e não código de retorno, porque a espera
acontece em meia dúzia de laços aninhados e esquecer um significaria continuar
mandando tecla depois do cancelamento. Quem dorme é `_dormir`, que fatia a
espera e olha o pedido; `_focar` também, senão o cancelamento só valia depois
dos 15 segundos dele.

E a de sempre com ctypes: `GetClipboardData` **precisa** de `restype`
declarado. Sem ele o handle de 64 bits é truncado, o `GlobalLock` falha e a
leitura volta vazia — foi assim que um teste deu "campo vazio" com o campo
preenchido.

## Gravar nunca pode destruir o arquivo de destino

`salvar` **codifica o texto inteiro antes de tocar em disco**, escreve num
`.tmp` ao lado e só então renomeia por cima (`os.replace`, atômico no mesmo
volume). O modo `"w"` trunca o arquivo no instante em que é aberto: até a
0.49.0, qualquer falha depois disso — disco cheio, ou um caractere fora do
latin-1 numa descrição — deixava o usuário **sem o arquivo e sem o
conteúdo**. No ensaio, colar um travessão (`—`) numa descrição e salvar
zerava um SPED de 236 KB.

Caractere impossível de codificar não vira `?` em silêncio: a gravação é
recusada com a **linha** e o caractere na mensagem ("a linha 43 tem o
caractere '—'"), porque trocar por `?` mudaria a descrição do produto sem
ninguém saber. O caso típico é texto colado de outro programa — travessão,
aspas curvas.

O mesmo vale para todo JSON do usuário (cadastro, acervo, configuração,
correlações): `dados.gravar_json`, que escreve em `.tmp` e troca. Já o CSV
exportado (`infra/exportacao.py`) troca o caractere impossível por `?`: num
relatório isso é aceitável, e o `csv` põe aspas no `;` de uma descrição.

## Armadilha: scripts de teste que sombreiam o stdlib

Os testes põem a própria pasta no `sys.path`. Um arquivo chamado `bisect.py`,
`types.py`, `select.py` ou qualquer outro nome da biblioteca padrão passa a ser
importado no lugar do módulo real — e, como o import **executa** o arquivo, o
sintoma é surreal: o teste A imprime a saída do script B, o processo morre sem
traceback e o diagnóstico vai para o lado errado (já custou horas aqui).
Use nomes com prefixo (`teste_`, `montar_`, `test_`) nos scripts auxiliares.
`tests/test_estrutura.py` reprova módulo do projeto com nome da biblioteca
padrão.

## Ao mexer na barra de título

**O menu de sistema não sai de graça do `HTCAPTION`.** O Windows o abre ao
tratar o `WM_CONTEXTMENU`, e o Qt intercepta essa mensagem. Por isso
`janela_custom.tratar` responde ao `WM_NCRBUTTONUP` na faixa da barra e
abre o menu à mão (`TrackPopupMenu` + `WM_SYSCOMMAND`). Até a 0.55.0 o
clique direito na barra não fazia nada.

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

`tests/test_estrutura.py` confere isso em **todo** arquivo do projeto, junto
com import sem uso e método definido duas vezes na mesma classe. Outra
variante da mesma armadilha, vista na reestruturação: um patch que engole o
`\` de continuação deixa duas linhas coladas — compila, mas fica ilegível.

Duas mais, que a suíte pegou antes do commit na 0.52/0.53: variável local com
o nome de um módulo importado (`ajustes = ajustes()`, `cadastro =
cadastro.carregar_empresas()`) vira `UnboundLocalError` na função inteira.

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

- **Rateio de despesas acessórias:** há **uma** função,
  `SpedDocument.rateio_acessorios(total, valores)`, e ela usa **diferença de
  acumulados arredondados** — nunca `round()` item a item, que não fecha com o
  total (R$ 1,00 entre três itens iguais dá 0,33 × 3 = 0,99; assim dá
  0,33 + 0,34 + 0,33). O C190 fazia certo e o C175 fazia item a item; hoje os
  dois chamam a mesma função, e **quem confere o C175 também**: a conferência
  e a prévia da regeneração somavam VL_OPR **sem** o rateio enquanto a geração
  gravava **com**, e acusavam diferença em todo documento com frete/seguro.
  Cálculo que gera e cálculo que confere precisam ser o mesmo código.
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
- **Alíquota do cadastro é texto livre — normalize na entrada.** O que o
  usuário digita em *Empresas* acaba **gravado no arquivo fiscal** pela rotina
  de correção: `1.65` com ponto ia assim para o SPED. `empresas.
  normalizar_aliquota` passa pelo `_fmt_aliq` em três pontos — ao digitar, ao
  montar a `Empresa` (inclusive de um `empresas.json` antigo) e na hora de
  gravar o campo. Consequência visível: o cadastro mostra `3`, não `3,00`, que
  é o formato do SPED.
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

## Arquivos reais usados na validação

Ficam **fora do repositório**, numa pasta apontada por
`SPED_TABLES_ARQUIVOS_REAIS` (ver `TESTES.md`), com o `gabarito.json` dos
números esperados. Nunca cite nome, CNPJ ou caminho de cliente em código,
teste, commit ou documentação; nos textos, "cliente A" / "cliente B".

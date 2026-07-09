# Editor SPED (EFD ICMS/IPI e EFD Contribuições)

Editor visual para arquivos **SPED Fiscal**, em estilo planilha, com a mesma
navegação **mestre-detalhe** do *Validador do SPED*: cada **bloco** é uma aba,
cada **registro** é uma sub-aba, e os registros-filho (ex.: itens C170,
analítico C190, complemento C110) aparecem em sub-abas **dentro** do registro
pai (C100).

Suporta os dois leiautes e detecta automaticamente qual é o arquivo:
- **EFD ICMS/IPI**
- **EFD Contribuições (PIS/COFINS)**

---

## 1. Instalação

Requer **Python 3.10+**. Instale a dependência (apenas PyQt6):

```bash
pip install PyQt6
# ou:  pip install -r requirements.txt
```

> Observação: este projeto foi montado e testado em um ambiente **sem PyQt6 e
> sem internet**, então a *lógica* (leitura, hierarquia, edição e gravação) foi
> validada de forma isolada e está 100% funcional. A **interface gráfica** deve
> ser executada na sua máquina, onde o PyQt6 estará instalado.

## 2. Como executar

```bash
python sped_editor.py
```

Ou abrindo um arquivo direto pela linha de comando:

```bash
python sped_editor.py  caminho/para/SPED_ICMS_IPI_xxxx.txt
```

Depois, use **Arquivo → Abrir** (Ctrl+O) para escolher o `.txt` do SPED.

## 3. Como usar

O topo da janela tem dois modos: **📋 Modo Tabela** (edição mestre-detalhe por
bloco) e **📊 Modo Relatório** (visão achatada dos itens para comparação com o
banco). O Modo Tabela funciona assim:

- **Abas superiores** = blocos (0, A, C, D, E, …, 9).
- Dentro de cada bloco, **sub-abas** = registros principais (ex.: C001, C100, C990).
- **Reordenar abas**: arraste as abas (de bloco ou de tipo) para a ordem que
  preferir. A ordem escolhida vale **durante a sessão** — ao fechar e reabrir o
  programa, tudo volta ao padrão.
- **Soma da seleção**: ao selecionar várias células numéricas numa grade, a
  barra de status mostra **Soma, Média e Contagem** (como no Excel).
- Clique numa linha da grade. Se o registro tiver filhos, aparecem **sub-abas
  de detalhe** logo abaixo (ex.: `C110 (1)`, `C170 (4)`, `C190 (1)`,
  `C195 (4)`), cada uma com sua própria grade editável — e isso é **recursivo**.
- **Editar**: dê duplo-clique numa célula e digite. A coluna **REG** (azul) é
  fixa, pois define a hierarquia.
- **➕ Adicionar linha / ➖ Remover linha**: inserem/excluem registros no nível
  da grade atual. Remover um registro remove também toda a subárvore dele.
- **Salvar / Salvar como** (Ctrl+S): grava o arquivo no formato SPED, com a
  mesma codificação do original (latin-1), recalculando automaticamente os
  registros de totalização: **X990** (total por bloco), **9900** (um por tipo
  de registro), **9990** e **9999**.

### Pesquisa e filtro por modelo (aba C100)

Nas grades de documento (que têm `NUM_DOC`/`COD_MOD`, como **C100**):

- **🔎 Nº do documento**: caixa de pesquisa que filtra as linhas pelo número do
  documento conforme você digita.
- **Modelo:**: seletor que filtra por **COD_MOD** (ex.: `55` = NF-e, `65` =
  NFC-e), preenchido com os modelos presentes no arquivo.

Os filtros se combinam entre si e com o seletor **Operação** (entradas/saídas);
o rótulo mostra "X de Y" quando há filtro ativo.

### Edição estilo planilha (Excel-like)

- **Digite para editar**: basta começar a digitar na célula selecionada — não
  precisa de duplo-clique nem F2.
- **Setas ↑/↓ e Enter durante a edição** confirmam o valor e já abrem a edição
  na célula vizinha, para você preencher uma coluna inteira sem tocar no mouse.
- **Seleção múltipla** com **Ctrl** e **Shift** (clique ou setas), como no Excel.
- **Preencher várias células com um valor**: selecione as células e use o botão
  direito → *Preencher seleção com um valor…*, ou **cole** (Ctrl+V) um valor
  único — ele é aplicado a toda a seleção.
- **Ctrl+C / Ctrl+V**: copia/cola blocos de células (formato tabulado,
  compatível com Excel). **Ctrl+D**: preenche para baixo o valor da célula do
  topo da seleção.

A coluna **REG** é sempre protegida e nunca é sobrescrita por colar/preencher.

### Filtro de operação (Entradas × Saídas)

Em qualquer grade de documento que tenha o campo **IND_OPER** (ex.: **C100**,
**D100**), aparece no canto superior direito um seletor **Operação:** com as
opções **Todas / Entradas (0) / Saídas (1)**. Ele filtra as linhas exibidas
pelo `IND_OPER` (`0` = entrada, `1` = saída) e o rótulo mostra "X de Y". Com um
filtro ativo, ao **Adicionar linha** o novo registro já nasce com o `IND_OPER`
correspondente.

### Importar XMLs → consolidar C175 (EFD Contribuições)

**Ferramentas → Importar XMLs → consolidar C175…** lê uma pasta de XMLs de
NFC-e (modelo 65) e gera os registros **C175** dos documentos correspondentes:

- **Vínculo** XML ↔ C100 pelas tags **mod + série + nNF** (lidas de dentro de
  cada XML; o nome do arquivo é ignorado, pois é inconsistente).
- Para cada documento, os itens do XML são agrupados por **CFOP + CST_PIS +
  ALIQ_PIS + CST_COFINS + ALIQ_COFINS** e somados (VL_OPR, VL_BC, VL_PIS,
  VL_COFINS), substituindo os C175 anteriores.
- **VL_PIS** e **VL_COFINS** do C100 e os totais (C990/9900) são atualizados.
- NF-e modelo 55 são ignoradas (usam C170, não C175); a ferramenta informa
  quantos XMLs casaram, quantos ficaram sem C100 e eventuais erros de leitura.

O motor de vínculo (`xml_fiscal.vincular`) é genérico e reaproveitável: a mesma
função casa **item XML ↔ C170** pela chave **mod + série + nNF + nItem** (útil
para conferir entradas modelo 55, em que o código do produto muda entre a saída
do fornecedor e a entrada do comprador, mas a ordem do item se mantém).

### Recalcular bloco M — apuração PIS/COFINS (EFD Contribuições)

**Ferramentas → Recalcular bloco M (apuração)…** recompõe a apuração de PIS
(**M200/M210**) e COFINS (**M600/M610**) a partir das receitas tributadas de
saída (C175 e C170), agrupadas por alíquota. Fórmula validada contra arquivos
reais:

- `VL_REC_BRT` = Σ VL_OPR do grupo;
- `VL_BC_CONT` = Σ VL_BC do grupo;
- `VL_CONT_APUR` = VL_BC_CONT × alíquota (ex.: PIS 1,65 %, COFINS 7,6 %).

O **regime** é lido do registro **0110 (COD_INC_TRIB)** e respeitado:

- **Cumulativo (2):** a contribuição é lançada nos campos *CUM* do M200/M600
  (COD_CONT 51) e os registros de crédito **M100/M105/M500/M505 não são usados
  nem criados** — como você indicou, no regime cumulativo não há créditos.
- **Não-cumulativo (1) / ambos (3):** a contribuição vai nos campos *NC*
  (COD_CONT 01); os créditos já existentes (M100/M500) são **preservados** e
  apenas descontados na consolidação (`VL_TOT_CONT_NC_DEV = apurado − créditos`).

Este recálculo cobre o **débito** (apuração da contribuição). Ele não recompõe
os **créditos** (M100/M105/M500/M505), que dependem da classificação das
entradas — por isso são mantidos como estão. Recomenda-se conferência por
profissional antes da transmissão.

### Trocar alíquotas de PIS/COFINS

**Ferramentas → Trocar alíquotas PIS/COFINS…** (EFD Contribuições) substitui as
alíquotas de PIS e/ou COFINS e recalcula **VL_PIS** e **VL_COFINS** (base ×
alíquota ÷ 100), atualizando os totais dos **C100**. Um seletor de **escopo**
define onde aplicar:

- **Saídas — débito (C175 + C170 de saída):** recalcula as vendas consolidadas
  (C175) e também os itens de documentos de saída detalhados (C170);
- **Entradas — crédito (C170):** os itens dos documentos de entrada (C100 com
  IND_OPER=0), cujo crédito é apurado pela **alíquota do comprador**;
- **Todos os itens (C170 e C175):** qualquer registro, independentemente de
  entrada/saída — útil para corrigir alíquotas preenchidas erradas.

Há ainda o filtro opcional **“Trocar apenas onde a alíquota atual for”**: com ele
marcado, só os registros cuja alíquota atual seja exatamente o valor informado
são corrigidos, deixando os demais intactos.

### Alterar datas de emissão/saída (C100)

**Ferramentas → Alterar datas emissão/saída (C100)…** seleciona documentos por
um **intervalo de datas** (avaliado sobre a data de entrada/saída *DT_E_S* ou a
de emissão *DT_DOC*), podendo restringir por **tipo de movimento** (entrada/saída)
e por **modelo** (campo *Somente modelos*, ex.: `55, 65`; em branco, todos). Nos
documentos filtrados, altera a **DT_DOC**, a **DT_E_S** ou **ambas**, para uma
**data específica** (DDMMAAAA) ou **deslocando N dias** (aceita negativos, ex.:
`-3`). As datas seguem o formato do arquivo (DDMMAAAA).

### Conferir entradas (NF-e modelo 55) com os XMLs

**Ferramentas → Conferir entradas (NF-e 55) com XMLs…** compara cada item dos
XMLs de compra com o **C170** correspondente do SPED, usando o mesmo motor de
vínculo (`xml_fiscal.vincular`) — aqui no nível de item, pela chave
**mod + série + nNF + nItem**.

A ordem do item (nItem) é a chave porque, da saída do fornecedor para a entrada
do comprador, **o código do produto muda** (cProd ≠ COD_ITEM) e **o CFOP muda**
(5xxx → 1xxx/2xxx). Por isso esses campos não entram como chave nem são
conferidos por igualdade; o que se confere por padrão é o **valor do item**
(VL_ITEM × vProd) e o **desconto** (VL_DESC × vDesc), além do **total do
documento** (VL_DOC × vNF). As comparações são parametrizáveis em
`conferencia.COMPARACOES_PADRAO`.

O resultado abre numa janela com o resumo (documentos casados, itens conferidos,
divergências, itens sem C170, notas sem XML) e a lista de divergências, que pode
ser **exportada em CSV**. Além de VL_ITEM e VL_DESC, a conferência verifica o
**CST de ICMS** e os **valores de ICMS** (base e imposto) de cada item — que não
podem divergir entre o XML e o SPED. Itens presentes no XML mas ausentes no
SPED — e vice-versa — são identificados individualmente.

#### Correlação de CFOP (saída do fornecedor → entrada do comprador)

Numa compra, o XML do fornecedor traz o CFOP de **saída** (5xxx mesma UF, 6xxx
outra UF) e o C170 do comprador traz o CFOP de **entrada** (1xxx/2xxx). A
conferência verifica se esse par é coerente: o CFOP de saída deve corresponder a
um CFOP de entrada **válido**, preservando a natureza da operação (comercializar,
industrializar, ST, ativo, uso/consumo). Por exemplo, um item com **5403** na
compra lançado como **1102** é apontado, indicando que o correto seria **1401**
ou **1403**.

A lista de correlações válidas é **editável na interface** em **Ferramentas →
Correlações de CFOP (entradas)…**: uma tabela *CFOP de saída → CFOPs de entrada
válidos* (separados por vírgula), com botões para adicionar, remover, restaurar o
padrão e salvar. As correlações ficam em **`correlacoes_cfop.json`** (ao lado do
programa); o aplicativo já vem com um conjunto inicial que cobre os casos mais
comuns e pode ser ajustado à realidade da empresa.

### Recalcular C190 (analítico) a partir dos itens C170

Na grade **C190** de um documento C100 (EFD ICMS/IPI), ao lado de *Adicionar/
Remover linha* há o botão **🔄 Recalcular C190**. Ele reconstrói os registros
C190 a partir dos itens **C170**, agrupando por **CST_ICMS + CFOP + ALIQ_ICMS**
e somando os valores — substituindo os C190 anteriores e mantendo a sequência
correta dentro do C100 (entre os itens e os C195).

- **VL_BC_ICMS, VL_ICMS, VL_BC_ICMS_ST, VL_ICMS_ST, VL_IPI**: soma exata dos
  itens do grupo (conferido contra arquivos reais: ~100%).
- **VL_OPR**: `Σ(VL_ITEM − VL_DESC) + VL_IPI + VL_ICMS_ST`, mais o **rateio** de
  frete, seguro e outras despesas do C100 (proporcional ao VL_ITEM). Reproduz o
  valor original em ~98–99% dos casos; quando há rateio de despesas, pode haver
  diferença de centavos que você pode ajustar manualmente.

Assim, depois de alterar qualquer C170, basta um clique para deixar o C190
coerente, sem somar grupo por grupo na mão.

### Contagens / totais (C990, 9900, 9990, 9999)

As contagens são **sempre reconstruídas ao salvar**: **X990** (ex.: `C990` = nº
de linhas do bloco), **9900** (um por tipo de registro, ex.: `9900|C190|<qtd>`),
**9990** (linhas do bloco 9) e **9999** (total do arquivo). Não é preciso
recalcular manualmente — basta salvar.

### Nome do produto no topo (grades C170)

Nas grades que têm **COD_ITEM** (ex.: **C170**), ao **selecionar uma linha** o
nome do produto aparece **centralizado no topo do widget** (ao lado do contador
`C170 — N registro(s)`), em destaque verde, no formato `📦 1021 — PESC PANGA
FILE...`. A descrição é buscada no cadastro **0200** (`COD_ITEM → DESCR_ITEM`).
Se o código não estiver cadastrado, o rótulo avisa; se você editar o `COD_ITEM`
da linha, o nome é atualizado na hora. A busca é indexada e se refaz sozinha
quando um registro 0200 é editado, criado ou removido.

### Página inicial (Resumo)

A aba **📋 Resumo** reúne, no topo, os dados do registro 0000 (razão social,
CNPJ, IE, UF, período e layout) e os metadados do arquivo. Em seguida vem a
**apuração do período** e uma **lista dos registros** (agrupada por bloco, com a
quantidade de cada tipo).

A apuração depende do layout:

- **EFD ICMS/IPI:** consolidação das **entradas** e das **saídas** por
  CST/CFOP/alíquota (apenas os totais, sem listar documentos individuais) e a
  **apuração do ICMS de operações próprias (E110)** — débitos, créditos, saldo
  credor anterior, ICMS a recolher e saldo credor a transportar.
- **EFD Contribuições:** **consolidação por CST** de PIS/COFINS, separando
  receitas/saídas, aquisições/custos/despesas e outras operações, com valor do
  item e bases de PIS e COFINS.

Ao abrir um arquivo, a primeira aba **📋 Resumo** mostra o cabeçalho do registro
**0000** (nome do contribuinte, CNPJ, IE, UF e o período DT_INI–DT_FIN), o
**layout** detectado, a **data de modificação** do arquivo em disco, o nome do
arquivo, o **total de registros** e uma tabela com a **contagem por tipo de
registro**. Funciona nos dois leiautes (os campos do 0000 são localizados pelo
nome, já que a posição muda entre ICMS/IPI e Contribuições).

### Pesquisa em qualquer bloco

O campo de busca aparece em **qualquer grade com registros** — não só nas de
documento. Em grades com **NUM_DOC** (ex.: C100) a busca foca o número do
documento; nas demais (ex.: **0200**, **H010**) pesquisa em **todas as colunas**,
útil para localizar um item, um produto ou um saldo entre milhares de linhas.

### Revisão de erros
**Ferramentas → Revisar erros…** gera um relatório de inconsistências simples.
Nesta versão há duas regras:

1. **Número de campos divergente** — registros cujo número de campos destoa dos
   demais do **mesmo tipo** no próprio arquivo (detecta uma linha editada com um
   `|` a mais ou a menos). A referência é a maioria dos registros daquele tipo,
   não um leiaute fixo, o que evita falsos positivos por diferença de versão.
2. **C190 com CST x20/x70 e VL_RED_BC zerado** — registros C190 cujo CST indica
   redução de base de cálculo, mas com o valor da redução em branco/zero.

Dê **duplo-clique** numa linha do relatório (ou use **Ir para o registro**) e o
editor abre o bloco, a sub-aba e a linha exata do registro com problema —
inclusive descendo até registros-filho como o C190 (dentro do C100). O
relatório fica aberto enquanto você navega. As regras estão centralizadas em
`revisao.py` (lista `REGRAS`) e novas verificações podem ser acrescentadas com
poucas linhas.

### Modo Relatório (comparação com o banco)
A aba **📊 Modo Relatório** mostra os itens do arquivo numa **tabela achatada**.
Um seletor de **Fonte** escolhe o registro de origem, porque nem todo documento
tem detalhamento por item:

- **Itens (C170)** — uma linha por item, com dados do documento (C100) e do
  produto (0200): tipo, data, nota, item, código/descrição/NCM do produto,
  quantidades e valores, CFOP, ICMS, ICMS-ST, PIS, COFINS e IPI.
- **PIS/COFINS consolidado (C175)** — para documentos sem C170, como a **NFC-e
  (modelo 65)**: CFOP, valor da operação/desconto e os campos de PIS e COFINS.
- **ICMS consolidado (C190)** — também típico de **NFC-e (modelo 65)** e outros
  consolidados: CST, CFOP, alíquota, base e valor de ICMS, ICMS-ST, redução de
  base, IPI e código de observação.

Ao trocar a fonte, apenas os filtros aplicáveis ficam ativos. Todos os campos de
filtro aceitam **vários valores separados por ponto e vírgula** (`;`) — por
exemplo, CFOP `1101;1102`, CST `000;020;060` ou Alíq. PIS `1,65;0,65`. Usa-se
`;` (e não vírgula) para não conflitar com a vírgula decimal das alíquotas; o
filtro de NCM aceita vários prefixos (ex.: `02;2202`).

A tabela do relatório é **editável**: as colunas próprias do registro-fonte
(C170/C175/C190) podem ser alteradas diretamente — como uma *query* editável —,
gravando no registro correspondente do SPED (é preciso salvar o arquivo para
persistir). As colunas derivadas (produto, dados da nota, valores calculados)
aparecem em cinza e são somente-leitura.

O painel de **Filtros** reproduz os do script SQL (data inicial/final, tipo de
movimento, modelo, nº da nota, código do produto, nº do item, NCM por prefixo,
CFOP, CST de ICMS/PIS/COFINS/IPI — aceitando listas separadas por vírgula — e
alíquotas de PIS/COFINS). Clique em **Gerar relatório** para aplicar os filtros
e **Exportar CSV** para salvar o resultado (separador `;`, latin-1), que pode ser
confrontado com a saída do mesmo relatório no banco.

### Verificar CST por NCM (tabelas da RFB)

**Ferramentas → Verificar CST por NCM (tabelas RFB)…** (EFD Contribuições)
classifica cada item **C170** pelo NCM e aponta CST de PIS/COFINS incoerentes,
separando entradas e saídas. A classificação usa as tabelas oficiais do
EFD-Contribuições: **produtos de alíquota zero** (CST 06) e **monofásicos**.

As tabelas ficam na pasta de recursos do PVA
(`C:\Arquivos de Programas RFB\Programas SPED\EFD-Contribuicoes\recursos\tabelas`);
o programa localiza automaticamente a **maior versão** de cada uma (nomes como
`…$SPEDPISCOFINS_PROD_ALIQ_ZERO$48$166`). Se o padrão de nome mudar, é possível
**apontar o caminho de cada arquivo** manualmente no diálogo. A verificação
respeita a **vigência** (DT_INI/DT_FIM) na data de referência — por padrão a
DT_FIN do arquivo — e as exceções (NCM_EX); o **gênero** do item vem dos dois
primeiros dígitos do NCM. Opcionalmente, a **Tabela NCM Vigente** (XLSX do portal
Siscomex) pode ser informada para validar os NCMs.

Exemplos de achados típicos: entrada de produto **monofásico** (bebidas) com CST
50 — crédito indevido, quando o correto seria 73/98 — ou produto de **alíquota
zero** escriturado como tributado. O resultado é navegável (duplo clique leva ao
registro) e exportável em CSV. Como o **C175** (NFC-e consolidada) não traz o
item/NCM, a verificação por NCM cobre os **C170** (entradas e saídas detalhadas).

### Editar o layout no Qt Designer
A janela principal é descrita em **`sped_editor.ui`** (formato padrão do Qt). O
aplicativo carrega esse arquivo automaticamente quando ele está presente, de modo
que você pode abrir o **Qt Designer**, reorganizar a barra de ferramentas e as
ações, e ver as mudanças sem mexer no código. Se o arquivo não existir (ou não
puder ser lido), a interface é montada programaticamente como alternativa. As
ações mantêm nomes fixos (`act_abrir`, `act_salvar`, `act_revisar`, …) e o
`QTabWidget` central chama-se `tabs_bloco` — preserve esses nomes ao editar. O
botão **Ferramentas** da barra é montado em código (reúne as ações de
ferramentas num menu suspenso ao lado de *Salvar como*).

## 4. Estrutura do projeto

| Arquivo            | Função                                                         |
|--------------------|----------------------------------------------------------------|
| `sped_editor.py`   | Interface gráfica PyQt6 (mestre-detalhe recursivo).            |
| `sped_editor.ui`   | Layout da janela principal (editável no Qt Designer).         |
| `sped_model.py`    | Modelo de dados: parser, árvore pai/filho, CRUD e gravação.    |
| `sped_layouts.py`  | Níveis hierárquicos e nomes oficiais de campos por registro.   |
| `xml_fiscal.py`    | Leitura de XML NF-e/NFC-e e motor de vínculo genérico.        |
| `conferencia.py`   | Conferência de entradas modelo 55 (item XML ↔ C170).          |
| `tabelas_rfb.py`   | Tabelas RFB (alíq. zero, monofásicos, gênero, NCM) + CST.     |
| `correlacoes_cfop.json` | Correlações CFOP saída→entrada (gerado/editável).        |
| `revisao.py`       | Regras de revisão de erros (extensível).                      |
| `version.py`       | Versão do aplicativo (SemVer).                                |
| `CHANGELOG.md`     | Histórico de versões.                                          |
| `requirements.txt` | Dependências (PyQt6).                                          |

## 5. Notas e limitações

- A hierarquia espelha a visão do Validador nos dois leiautes: o **C100** é
  registro **principal** do bloco C (vira aba de topo) e seus filhos **C170**
  (itens), **C190**, **C195**, **C110** ficam em **nível 3**, logo abaixo. No
  **Contribuições**, o **C010** (estabelecimento) é tratado como registro de
  abertura/contexto (nível 1), o mesmo valendo para **A010** e **D010**.
- As **sub-abas de filhos** mostram apenas os tipos de registro que **já
  existem** sob aquele pai. Para acrescentar um tipo de filho ainda inexistente
  (ex.: criar o primeiro C170 de um C100 que só tem C190), seria necessário um
  catálogo completo de filhos permitidos por registro — fora do escopo atual.
  Adicionar **mais** registros de um tipo já presente funciona normalmente.
- Os nomes de coluna são os oficiais para os registros mais comuns das amostras;
  registros sem mapeamento específico recebem colunas genéricas
  (`Campo 02`, `Campo 03`, …), sem prejuízo da edição nem da gravação.
- Arquivos grandes (dezenas de milhares de registros) abrem em frações de
  segundo; as abas de bloco são construídas sob demanda para manter a abertura
  rápida.

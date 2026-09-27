# SPED Tables (EFD ICMS/IPI e EFD Contribuições)

> A versão corrente está em [`sped_tables/version.py`](sped_tables/version.py);
> o histórico, em [CHANGELOG.md](CHANGELOG.md); os próximos passos, em
> [ROADMAP.md](ROADMAP.md).

Editor visual para arquivos **SPED Fiscal**, em estilo planilha, com a mesma
navegação **mestre-detalhe** do *Validador do SPED*: cada **bloco** é uma aba,
cada **registro** é uma sub-aba, e os registros-filho (ex.: itens C170,
analítico C190, complemento C110) aparecem em sub-abas **dentro** do registro
pai (C100).

Suporta os dois leiautes e detecta automaticamente qual é o arquivo:
- **EFD ICMS/IPI** — 270 registros mapeados
- **EFD Contribuições (PIS/COFINS)** — 203 registros mapeados

O leiaute é **completo**: todos os registros dos dois SPEDs, com os nomes de
todos os campos e o nível hierárquico de cada um, extraídos dos guias
práticos. Nenhuma coluna aparece como "Campo NN".

---

## 1. Instalação

Para usar, basta o **`SPED Tables.exe`**: um arquivo só, sem instalação. Na
primeira execução ele cria a pasta de dados (ver 3A) e oferece o atalho na
área de trabalho.

Para rodar do código-fonte, requer **Python 3.10+**:

```bash
pip install -r requirements.txt
```

- **PyQt6** — interface gráfica (obrigatório);
- **openpyxl** — leitura de planilhas **XLSX** (importação do inventário do
  bloco H e Tabela NCM Vigente do Siscomex). Sem ele o programa abre
  normalmente; apenas as funções de XLSX ficam indisponíveis (CSV continua
  funcionando).

> **Antes de usar em produção:** trabalhe sempre sobre uma **cópia** do arquivo
> SPED e valide o resultado no **PVA** antes de transmitir. Enquanto a versão
> for 0.y.z, o programa está em desenvolvimento — o que falta para a 1.0.0
> está no [ROADMAP.md](ROADMAP.md).

## 2. Como executar

```bash
python sped_editor.py
```

Ou abrindo um arquivo direto pela linha de comando:

```bash
python sped_editor.py  caminho/para/SPED_ICMS_IPI_xxxx.txt
```

Depois, use o botão **Abrir** da barra de ferramentas (ou **Ctrl+O**) para
escolher o `.txt` do SPED. O programa não tem barra de menus: as ações ficam na
barra de ferramentas e as rotinas de correção/conferência no botão
**Ferramentas**.

## 3. Como usar

O topo da janela tem dois modos: **📋 Modo Tabela** (edição mestre-detalhe por
bloco) e **📊 Modo Relatório** (visão achatada dos itens para comparação com o
banco). O Modo Tabela funciona assim:

- **Abas superiores** = blocos (0, A, C, D, E, …, 9).
- Dentro de cada bloco, **sub-abas** = registros principais (ex.: C001, C100, C990).
- **Reordenar abas**: arraste as abas (de bloco ou de tipo) para a ordem que
  preferir. A ordem escolhida vale **durante a sessão** — ao fechar e reabrir o
  programa, tudo volta ao padrão.
- **Fixar / fechar sub-abas**: no painel de detalhe (registros-filho), clique com
  o **botão direito** numa sub-aba para *fixá-la* (passa a ser exibida primeiro
  ao trocar de registro pai), *fechá-la* (fica oculta até resetar) ou *resetar as
  abas*. Sem aba fixada, o detalhe sempre abre na primeira aba da ordem atual.
- **Soma da seleção**: ao selecionar várias células numéricas numa grade, a
  barra de status mostra **Soma, Média e Contagem** (como no Excel).
- **Quem é o código da linha**: ao selecionar uma linha, o topo da grade mostra
  o cadastro por trás do código — o **produto** (0200) nas grades com
  `COD_ITEM`, como o C170, e o **participante** (0150) nas grades com
  `COD_PART`, como o C100 e o D100. Parar o mouse sobre a célula `COD_PART`
  abre a ficha completa: nome, CNPJ/CPF pontuado, IE, endereço, bairro e
  município. Participante que não existe no 0150 aparece em cor de aviso — o
  PVA recusa esse caso, e ver na grade poupa uma ida ao validador.
- Clique numa linha da grade. Se o registro tiver filhos, aparecem **sub-abas
  de detalhe** logo abaixo (ex.: `C110 (1)`, `C170 (4)`, `C190 (1)`,
  `C195 (4)`), cada uma com sua própria grade editável — e isso é **recursivo**.
- **Editar**: dê duplo-clique numa célula e digite. A coluna **REG** (azul) é
  fixa, pois define a hierarquia.
- **➕ Adicionar linha / ➖ Remover linha**: inserem/excluem registros no nível
  da grade atual. Remover um registro remove também toda a subárvore dele.
- **Salvar / Salvar como** (Ctrl+S): grava o arquivo no formato SPED, sempre
  em latin-1 (arquivo aberto em UTF-8 é convertido), recalculando automaticamente os
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

> **Em desenvolvimento.** Nenhum arquivo gerado por esta função passou ainda
> pelo PVA (faltam os XMLs de um mês real), então ela não entra numa versão de
> release até isso acontecer — ver ROADMAP.

**Ferramentas → EFD Contribuições → Importar XMLs → consolidar C175…** lê uma pasta de XMLs de
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

### Trocar alíquotas de PIS/COFINS

**Ferramentas → EFD Contribuições → Trocar alíquotas PIS/COFINS…** substitui as
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

**Ferramentas → Gerais → Alterar datas emissão/saída (C100)…** seleciona documentos por
um **intervalo de datas** (avaliado sobre a data de entrada/saída *DT_E_S* ou a
de emissão *DT_DOC*), podendo restringir por **tipo de movimento** (entrada/saída)
e por **modelo** (campo *Somente modelos*, ex.: `55, 65`; em branco, todos). Nos
documentos filtrados, altera a **DT_DOC**, a **DT_E_S** ou **ambas**, para uma
**data específica** (DDMMAAAA) ou **deslocando N dias** (aceita negativos, ex.:
`-3`). As datas seguem o formato do arquivo (DDMMAAAA).

### Conferir entradas (NF-e modelo 55) com os XMLs

**Ferramentas → Gerais → Conferir entradas (NF-e 55) com XMLs…** compara cada item dos
XMLs de compra com o **C170** correspondente do SPED, usando o mesmo motor de
vínculo (`xml_fiscal.vincular`) — aqui no nível de item, pela chave
**mod + série + nNF + nItem**.

A ordem do item (nItem) é a chave porque, da saída do fornecedor para a entrada
do comprador, **o código do produto muda** (cProd ≠ COD_ITEM) e **o CFOP muda**
(5xxx → 1xxx/2xxx). Por isso esses campos não entram como chave nem são
conferidos por igualdade; o que se confere por padrão é o **valor do item**
(VL_ITEM × vProd + vOutro + vFrete + vSeg) e o **desconto** (VL_DESC × vDesc),
além do **total do documento** (VL_DOC × vNF). As comparações são
parametrizáveis em `conferencia.COMPARACOES_PADRAO`.

> **Por que somar as despesas acessórias:** o C170 não tem campo para elas por
> item — o leiaute só prevê VL_OUT_DA, VL_FRT e VL_SEG no C100, por documento.
> O que a NF-e traz em `det/prod/vOutro`, `det/prod/vFrete` e `det/prod/vSeg` é,
> portanto, escriturado dentro do próprio VL_ITEM, e comparar só com o `vProd`
> acusaria uma divergência do tamanho exato dessas despesas. Os três campos
> somados estão na constante `conferencia.ACESSORIOS_ITEM`: se a sua
> escrituração lançar frete e seguro no C100 em vez de dentro do item, deixe
> apenas `"voutro"` na lista.

O resultado é uma lista de divergências, navegável e **exportável em CSV**.
Além de VL_ITEM e VL_DESC, a conferência verifica o **CST de ICMS** e os **valores de ICMS** (base e imposto) de cada
item — que não podem divergir entre o XML e o SPED. Um **duplo clique** numa
divergência leva ao registro C170 correspondente no editor. Itens presentes no
XML mas ausentes no SPED — e vice-versa — são identificados individualmente.

#### Correlação de CFOP (saída do fornecedor → entrada do comprador)

Numa compra, o XML do fornecedor traz o CFOP de **saída** (5xxx mesma UF, 6xxx
outra UF) e o C170 do comprador traz o CFOP de **entrada** (1xxx/2xxx). A
conferência verifica se esse par é coerente: o CFOP de saída deve corresponder a
um CFOP de entrada **válido**, preservando a natureza da operação (comercializar,
industrializar, ST, ativo, uso/consumo). Por exemplo, um item com **5403** na
compra lançado como **1102** é apontado, indicando que o correto seria **1401**
ou **1403**.

A lista de correlações válidas é **editável na interface** em **Ferramentas →
Gerais → Correlações de CFOP (entradas)…**: uma tabela *CFOP de saída → CFOPs de entrada
válidos* (separados por vírgula), com botões para adicionar, remover, restaurar o
padrão e salvar. As correlações ficam em **`correlacoes_cfop.json`**, na pasta
de dados (ver 3A); o aplicativo já vem com um conjunto inicial que cobre os casos mais
comuns e pode ser ajustado à realidade da empresa.

### Conferir C190 (ICMS) com os XMLs

**Ferramentas → EFD ICMS/IPI → Conferir C190 (ICMS) com XMLs…** compara o
analítico **C190** com os XMLs, tanto nas entradas quanto nas saídas.

O ponto delicado é o agrupamento: numa compra, o CFOP do XML é o de **saída do
fornecedor** e não corresponde ao CFOP de entrada escriturado. Por isso os itens
do XML são agrupados pela **classificação do C170** (CST + CFOP + alíquota de
ICMS), casada item a item por **nItem** — assim, quando o XML traz um único CFOP
5102 e o SPED separa os itens em 1101 e 1102, os grupos do C190 são
reconstruídos corretamente. A comparação cobre **VL_OPR, VL_BC_ICMS e VL_ICMS**
por grupo, com o mesmo rateio de despesas acessórias do recálculo do C190, e é
exportável em CSV.

Recomenda-se **recalcular o C190 antes**, para comparar contra um analítico
consistente. Documentos sem C170 (NFC-e modelo 65) não entram na comparação:
aparecem no resumo como "itens sem C170".

### Recalcular totais do C100 a partir dos itens C170

Na grade **C100**, ao lado de *Adicionar/Remover linha*, o botão **🔄 Recalcular
totais** recompõe os totais do documento selecionado somando os itens **C170**:
valor das mercadorias (VL_MERC), desconto, base e valor de ICMS, ICMS-ST, IPI e —
no EFD Contribuições — PIS/COFINS. Em seguida recalcula o **VL_DOC**
(`VL_MERC − VL_DESC − VL_ABAT_NT + VL_FRT + VL_SEG + VL_OUT_DA + VL_IPI +
VL_ICMS_ST`), mantendo frete, seguro e outras despesas do próprio C100. Útil
depois de editar itens C170, quando as bases de cálculo do documento mudam. Se
nenhum C100 estiver selecionado, o programa oferece recalcular **todos** os
documentos com itens.

### Recalcular ICMS dos itens (C170)

**Ferramentas → EFD ICMS/IPI → Recalcular ICMS dos itens…** fecha o fluxo de
correção pelo **Modo Relatório**: você corrige alíquota, base ou CST direto na
grade — que já grava no registro — e pede o recálculo para os campos derivados
voltarem a bater.

- **VL_ICMS = base × alíquota** é sempre refeito;
- opcionalmente a **base** é refeita a partir de `VL_ITEM − VL_DESC`, com o
  percentual de **redução** aplicado nos CST **x20** e **x70**. Sem essa opção,
  a base informada é respeitada — inclusive uma base reduzida digitada à mão;
- nos CST **sem débito próprio** (x30, x40, x41, x50, x60), base, alíquota e
  valor são zerados: um CST desses com valor lançado é erro de escrituração;
- ao final, o **C190** e os **totais do C100** dos documentos afetados são
  refeitos.

O escopo padrão são **os itens do Modo Relatório**, isto é, o conjunto que você
acabou de revisar; sem relatório gerado, vale para todos os C170.

> O **ICMS-ST não é tocado**: tem base e alíquota próprias, frequentemente com
> MVA, e recalculá-lo junto produziria número errado em silêncio.

### Recalcular C190 (analítico) a partir dos itens C170

Na grade **C190** de um documento C100 (EFD ICMS/IPI), ao lado de *Adicionar/
Remover linha* há o botão **🔄 Recalcular C190**. Ele reconstrói os registros
C190 a partir dos itens **C170**, agrupando por **CST_ICMS + CFOP + ALIQ_ICMS**
e somando os valores — substituindo os C190 anteriores e mantendo a sequência
correta dentro do C100 (entre os itens e os C195).

- **VL_BC_ICMS, VL_ICMS, VL_BC_ICMS_ST, VL_ICMS_ST, VL_IPI**: soma exata dos
  itens do grupo (conferido contra arquivos reais: ~100%).
- **VL_OPR**: `Σ(VL_ITEM − VL_DESC) + VL_IPI + VL_ICMS_ST`, mais o **rateio** de
  frete, seguro e outras despesas do C100 (proporcional ao VL_ITEM). O rateio usa
  **diferença de acumulados arredondados**, de modo que a soma dos quinhões fecha
  **exatamente** com o total das despesas — arredondar item a item deixava sobra
  de centavos (ex.: 1,50 de VL_OUT_DA distribuído como 1,52).
- **VL_RED_BC**: nos grupos com CST de ICMS terminado em **20** ou **70**
  (redução de base), é calculado como `VL_OPR − VL_BC_ICMS` (nunca negativo);
  nos demais CST fica zerado.

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

Funciona nos dois leiautes: os campos do 0000 são localizados **pelo nome**, já
que a posição muda entre o EFD ICMS/IPI e o EFD Contribuições.

### Pesquisa em qualquer bloco

O campo de busca aparece em **qualquer grade com registros** — não só nas de
documento. Em grades com **NUM_DOC** (ex.: C100) a busca foca o número do
documento; nas demais (ex.: **0200**, **H010**) pesquisa em **todas as colunas**,
útil para localizar um item, um produto ou um saldo entre milhares de linhas.

### Revisão de erros
**Ferramentas → Gerais → Revisar erros…** abre um **painel de resumo**: uma linha por
verificação, com quantos erros ela achou e o **atalho para a função que
corrige**. Verificação sem correção automática traz *Ver ocorrências*, que
abre a lista item a item para corrigir na grade.

As regras implementadas hoje:

1. **Número de campos divergente** — registros cujo número de campos destoa dos
   demais do **mesmo tipo** no próprio arquivo (detecta uma linha editada com um
   `|` a mais ou a menos). A referência é a maioria dos registros daquele tipo,
   não um leiaute fixo, o que evita falsos positivos por diferença de versão.
2. **C190 com CST x20/x70 e VL_RED_BC zerado** — registros C190 cujo CST indica
   redução de base de cálculo, mas com o valor da redução em branco/zero.
3. **C170 sem C190 compatível** — itens cuja combinação de CST_ICMS, CFOP e
   alíquota de ICMS não aparece em nenhum C190 do mesmo documento, ou seja, que
   ficaram de fora do analítico.
4. **0200 não utilizados / duplicados** — produtos cadastrados que nenhum outro
   registro referencia (as referências são coletadas de qualquer registro com
   COD_ITEM, não só C170/H010) e códigos de item repetidos no cadastro.
5. **TIPO_ITEM fora da tabela (0200)** — o campo só aceita 00 a 10 e 99. Num
   arquivo real vinha ali um "N" de nacional em 10.312 itens, e o PVA recusou
   a importação inteira.
6. **COD_GEN incoerente com o NCM (0200)** — o gênero são os dois primeiros
   dígitos do NCM; a regra aponta tanto o campo vazio quanto o que não bate
   com o capítulo.
7. **Chave duplicada no mesmo registro-pai** — dois registros irmãos com a
   mesma chave declarada no leiaute (no C190, CST + CFOP + alíquota). O PVA
   recusa; refazer o analítico do documento resolve.
8. **Data de saída fora do período** — C100 de saída cuja `DT_E_S` não está
   entre `DT_INI` e `DT_FIN` do arquivo. Só as saídas são cobradas: na
   entrada, documento anterior ao período é escrituração extemporânea
   legítima.
9. **CST 02 sem alíquota (C170, ICMS)** — desde 01/04/2023 o CST terminado
   em 02 é tributação monofásica de combustível e exige alíquota. Na prática
   quase sempre é o **CSOSN 102/202 do fornecedor do Simples** copiado na
   entrada; o PVA acusa do mesmo jeito.
10. **IND_EMIT de terceiro em documento de saída** — saída é documento
    próprio. Quando há chave de NF-e, o CNPJ dentro dela diz qual campo está
    errado: se a chave é do próprio contribuinte, o `IND_EMIT`; se é de
    outro, o documento é de entrada e o errado é o `IND_OPER`.
11. **M210/M610 com receita bruta divergente** — o `VL_REC_BRT` declarado na
    apuração tem de sair do somatório dos documentos. Corrige com *Recalcular
    bloco M*.
12. **M210/M610 com base de cálculo divergente** — idem para o `VL_BC_CONT`.
13. **M400/M800 sem lastro nos documentos** — receita isenta declarada num
    CST que nenhum documento usa. Para o PVA, o registro não deveria existir.
14. **Registro 0900 ausente fora do prazo** — escrituração sem o 0900 cujo
    prazo de entrega, na tabela do PVA, já venceu.

A revisão **não substitui o PVA** — é uma triagem rápida antes dele.

Dê **duplo-clique** numa linha do relatório (ou use **Ir para o registro**) e o
editor abre o bloco, a sub-aba e a linha exata do registro com problema —
inclusive descendo até registros-filho como o C190 (dentro do C100). O
relatório fica aberto enquanto você navega. As regras estão centralizadas em
`sped_tables/dominio/revisao.py` (lista `REGRAS`) e novas verificações podem ser acrescentadas com
poucas linhas.

### Verificar CST por NCM — as duas tabelas de monofásico

O PVA distribui **duas** listas de produtos monofásicos, e o programa carrega
as duas:

| Arquivo na pasta do PVA | Tabela | O que traz |
|---|---|---|
| `PROD_MONO_ALIQ_UNID` | 4.3.11 | combustíveis, bebidas frias (alíquota por unidade) |
| `PROD_MONO_ALIQ_DIFER` | 4.3.10 | perfumaria, higiene pessoal, medicamentos, veículos, autopeças (Lei 10.147/2000) |

Apontar a **pasta** das tabelas resolve as duas automaticamente; os campos de
caminho direto existem para quando os arquivos estão fora dela. Se a 4.3.10
não for encontrada, o programa avisa — sem ela, produtos como o sabonete
(NCM `34011190`) passam despercebidos enquanto o PVA os acusa.

### Corrigir CST de entrada pelo NCM (EFD Contribuições)

No diálogo **Ferramentas → EFD Contribuições → Verificar CST por NCM (tabelas
RFB)…**, o botão **Corrigir entradas sem crédito** retira o crédito dos itens
de **entrada** cujo NCM não o admite — monofásicos e alíquota zero não geram
crédito na revenda.

A correção troca o CST pelo sugerido pela classificação do NCM e **zera base,
alíquota e valor**. Ela só age onde o crédito está de fato sendo tomado (CST
50-56 / 60-66): item que já está num CST sem crédito não é tocado, porque 70,
73 e 98 se distinguem pelo motivo da vedação e trocar um pelo outro sem saber
o motivo seria palpite.

**Saídas não são alteradas.** Lá o CST depende de o produto ser revenda ou
produção própria, e alíquota diferenciada (02/03) é legítima — corrigir em
massa erraria.

A mesma correção está disponível na rotina *CST incoerente com o NCM* do painel
de rotinas por regime, com a mesma implementação.

### Recalcular C190 com redução de base zerada (em massa)

**Ferramentas → EFD ICMS/IPI → Recalcular C190 (analítico) em massa…**
refaz o analítico dos documentos em que algum C190 tem CST terminado em **20**
ou **70** e o `VL_RED_BC` em branco — erro que o PVA acusa. Só esses documentos
são tocados: refazer o analítico que já está certo seria substituir registro
sem motivo.

Nos CST terminados em **70** o ICMS foi cobrado por substituição tributária e
**não existe base de ICMS própria** de onde tirar a diferença. Quando o item
tem **base de PIS/COFINS**, ela é usada no lugar para achar a parcela reduzida
— o `VL_BC_ICMS` do C190 continua zero, como deve ser. Quando não há nenhuma
das duas bases, a redução fica em zero e o caso é apontado para conferência
manual, em vez de chutado.

O mesmo conserto é oferecido como botão dentro de **Revisar erros**, junto da
lista que o apontou.

### Itens do 0200 sem referência

**Ferramentas → Gerais → Itens do 0200 sem referência…** aplica a regra do Guia
Prático: *"Não informar item, se não referenciado em pelo menos um dos demais
blocos."* Varre o arquivo inteiro atrás de cada código do cadastro, lista os que
ninguém cita e remove sob confirmação.

A varredura usa **duas estratégias**, conforme o registro:

- registro com leiaute mapeado é lido pelo **nome** do campo (`COD_ITEM`);
- registro que o programa ainda não mapeia — o **bloco K** inteiro, por
  exemplo — é varrido **por valor**: qualquer campo cujo conteúdo seja um
  código do 0200 conta como referência.

A segunda erra para mais, nunca para menos: preserva item que talvez não
precisasse ficar, mas jamais apaga item que está sendo usado. O painel mostra
de onde vieram as referências e quais registros caíram no modo conservador.

A lista traz código, descrição e quantos registros-filho o item tem;
**duplo-clique leva até o registro** e há exportação em CSV. A remoção apaga o
0200 e toda a sua subárvore (0205, 0206, 0220…), e **não há desfazer** — se
errar, feche o arquivo sem salvar.

### Preencher conta contábil (COD_CTA)

**Ferramentas → Gerais → Preencher conta contábil (COD_CTA)…** resolve o erro
*"O campo é obrigatório para EFD ICMS/IPI com Perfil igual a 'A' ou 'B'"* no
**H010** — e em qualquer outro registro que tenha o campo.

O diálogo lista os tipos de registro que estão sem conta (ex.: `H010 — 9929 sem
conta`, `C170 — 2486 sem conta`) e preenche **um tipo por vez**, porque cada um
leva uma conta diferente: estoque no H010, custo no C170. A natureza da conta
(`COD_NAT_CC`) já vem sugerida conforme o registro — ativo para o inventário,
resultado para o item de nota.

Registros que **já têm** conta não são tocados.

Marcando *Cadastrar a conta no plano de contas*, o registro **0500** é criado
junto, na posição correta do bloco 0, com data de alteração igual ao início do
período. Isso importa: informar uma conta que não existe no plano de contas é
o próximo erro a aparecer. Se o arquivo já tiver 0500, as contas existentes
aparecem num seletor.

### Recalcular o bloco M (EFD Contribuições)

**Ferramentas → EFD Contribuições → Recalcular bloco M (apuração)…** refaz a
apuração a partir dos documentos: as contribuições (M200/M210 e
M600/M610) pelas receitas tributadas de saída, e os **créditos** (M100/M105 e
M500/M505) pelas entradas — um grupo por alíquota, com a natureza da base
vinda do CFOP pela tabela 4.3.7 do PVA. O desconto vai até o limite do débito
do período; o que sobra fica como saldo.

Refazer o crédito importa porque corrigir CST ou alíquota das entradas muda a
base: o PVA confere os dois lados e recusa o M105 que não corresponda aos
documentos. Num arquivo real eram 8 erros, todos resolvidos pelo recálculo.

Quando a divisão do crédito não sai dos documentos, ele **não mexe** e diz o
motivo: incidência não exclusivamente não-cumulativa, ajustes de crédito
(M110/M115/M510/M515), crédito fora do bloco C (D101, F100…) ou tabela do PVA
ausente.

O **regime** vem do **0110 (COD_INC_TRIB)**: no **cumulativo** a contribuição
vai para os campos *CUM* (COD_CONT 51) e não há crédito — M100/M105/M500/M505
não são usados nem criados; no **não-cumulativo** vai para os campos *NC*
(COD_CONT 01), com o crédito descontado até o limite do débito.

### Abrir no PVA depois de salvar

Ao salvar, a janela de confirmação oferece **Abrir no PVA e importar**: o
programa abre o PVA do leiaute (ou traz para a frente o que já estiver
aberto), manda o Ctrl+I que abre a importação e cola ali o caminho do arquivo
recém-salvo. Também está em **Ferramentas → Gerais → Abrir no PVA**.

O PVA não recebe arquivo por linha de comando — o caminho usado é o acelerador
que ele mesmo declara no menu. Se alguma coisa sair do lugar (o PVA demorando
a abrir, outra janela roubando o foco, um diálogo aberto esperando resposta),
**nada é teclado às cegas**: o caminho fica na área de transferência e a
mensagem diz o que falta, que é Ctrl+I, Ctrl+V, Enter.

O programa espera o PVA **terminar de carregar** antes de mandar o atalho: a
janela principal aparece bem antes de aceitar teclas, e nesse intervalo o
atalho é simplesmente ignorado. Numa partida a frio medida aqui, a janela
apareceu em 4 s e o atalho só passou a valer aos 12 s — com a espera, a
importação abre na primeira tentativa, 14 s depois do clique.

Antes de abrir o PVA, o programa confere se o arquivo tem erro de estrutura
— o PVA recusa a importação inteira nesse caso, e o diagnóstico daqui já
conhece esses campos. Se tiver, ele avisa e oferece o diagnóstico em vez de
mandar um arquivo que voltaria com "Importação não realizada".

Se o PVA estiver com uma escrituração aberta, o *Importar* fica desabilitado:
o programa fecha a escrituração (Ctrl+F) e repete o atalho. Telas do próprio
PVA no meio do caminho — atualizar tabelas, transferência, mensagens — são
**esperadas**, não respondidas: o andamento diz o que ele está pedindo.

O ciclo vai até o fim: o programa confirma a importação — o PVA só pergunta
quando já tem a escrituração daquele CNPJ e período, que será
**substituída**; sendo nova, ele importa direto — e, terminada ela, a
**validação** — é o relatório de erros do PVA que interessa. Cada confirmação
é conferida pelo efeito (a tela de progresso correspondente tem de aparecer);
não aparecendo, a automação para e avisa o que falta fazer.

Medido aqui, do clique ao validador rodando: **19 segundos**.

### Nada é descartado nem lido como zero em silêncio

- **Linha fora do formato.** Linha sem o `|` inicial não é registro. Ela
  aparece no Diagnóstico, e salvar pergunta antes de gravar sem ela: até a
  0.55.0 ela sumia ao salvar. Linha sem o `|` final é lida inteira (antes,
  perdia o último campo; num 0200, o NCM) e também é apontada.
- **Número inválido nos cálculos.** Recalcular C190, totais do C100, ICMS dos
  itens, bloco M, alíquotas de PIS/COFINS e C175 da NFC-e **recusam** quando
  algum campo de valor que eles leem não é número do SPED (`NULL`, `12a`,
  `1.234,5.6`). A mensagem diz o registro, o campo, o valor e a linha. Nada é
  alterado: antes, o lixo era lido como zero e o total saía gravado errado,
  com cara de certo.
- **Cadastro, acervo ou configuração ilegíveis.** O arquivo é guardado como
  `nome.corrompido-<data>` e você é avisado. Antes ele virava "vazio", e
  cadastrar uma empresa gravava por cima do cadastro inteiro.

### Segurança ao salvar

O arquivo só é substituído quando a gravação inteira deu certo: o conteúdo é
codificado na memória, escrito num temporário ao lado e renomeado por cima.
Falta de espaço em disco ou um caractere que não existe no padrão do SPED não
deixam mais o arquivo pela metade.

Caractere impossível de gravar (travessão, aspas curvas — normalmente texto
colado de outro programa) **não é trocado por outro em silêncio**: a gravação
é recusada dizendo a linha e o caractere, para você corrigir o campo.

### Diagnóstico do arquivo (automático ao abrir)

Ao abrir um SPED, o programa passa o arquivo pelas camadas de verificação do
PVA e mostra um painel com os problemas **agrupados pelo módulo que os
corrige** — cada linha tem o botão que abre a função certa:

```
Corrigir campos pelo leiaute          24313   [Abrir]
Preencher COD_GEN pelo NCM            12478   [Abrir]
Itens do 0200 sem referência          10312   [Abrir]
Recalcular C190 (analítico)              66   [Abrir]
Correção manual na grade                 26   campo obrigatório em branco
```

Abaixo, o detalhe por registro e campo; duplo-clique leva ao registro. Se o
arquivo estiver limpo, o painel não aparece — só uma mensagem na barra de
status. Também dá para chamá-lo a qualquer momento em **Ferramentas → Gerais
→ Diagnóstico do arquivo**.

**O que ele verifica com fidelidade:** tudo o que o PVA declara no descritor —
quantidade de campos do registro, obrigatoriedade de campo, tipo, tamanho,
casas decimais, enumerações, tabelas externas, referências entre registros
(`COD_ITEM` → 0200, `COD_PART` → 0150, `UNID` → 0190, `COD_CTA` → 0500) e
bloco aberto sem encerramento.

**O que ele não reproduz:** as cerca de 1.400 regras compostas do PVA,
implementadas em Java. O painel diz **quantas** se aplicam ao arquivo e cita
alguns nomes, para deixar claro que validar no PVA continua necessário — o
diagnóstico adianta trabalho, não substitui o validador oficial.

### Crédito em CFOP que não dá direito (EFD Contribuições)

Entre as rotinas de conferência de PIS/COFINS há uma que usa a tabela 4.3.7
do PVA (`CFOP_CREDITO`, 89 CFOP de entrada que geram crédito): CST de
creditamento num CFOP fora dela é crédito indevido. Num arquivo real de
supermercado eram 20 ocorrências, todas em CFOP 1910 (bonificação, doação ou
brinde) e 1949 (outra entrada não especificada) — mercadoria que entrou sem
custo não gera crédito. A correção troca o CST e zera base, alíquota e valor.

### Como a validação acompanha o PVA

Cada PVA embarca um **descritor de validação** — um XML, dentro do próprio
`.jar`, com tipo, tamanho, casas decimais, obrigatoriedade, enumerações e
referências entre registros, por versão de leiaute. O programa lê esse
descritor e valida **na mesma granularidade**: por registro e campo, não por
nome de campo.

Isso corrige um excesso e uma falta:

- **excesso** — o `CST_ICMS` do EFD Contribuições deixou de ser cobrado, porque
  aquele PVA não o valida (era falso positivo);
- **falta** — tipo e tamanho passaram a ser conferidos em todos os campos
  declarados (1.612 no ICMS/IPI, 1.191 no Contribuições), no lugar da
  heurística por prefixo `VL_`/`ALIQ_`.

As regras compostas do PVA (`REGRA_CST_ICMS_CAMPOS_ICMS_C170` e afins) são
implementadas em Java; o programa reconhece que existem, mas não as
reimplementa — adivinhar o conteúdo produziria divergência silenciosa com o
validador oficial.

### Validação contra as tabelas dos PVAs

O **Diagnóstico** (e a tela *Corrigir campos pelo leiaute*, aberta por ele) usa, quando os PVAs
estão instalados, **as mesmas tabelas que o fisco aplica** — as dos programas
validadores do EFD ICMS/IPI e do EFD Contribuições. Assim a lista de códigos
válidos acompanha a atualização do PVA sem depender de o programa ser
atualizado.

Campos cobertos hoje: `CFOP`, `CST_ICMS`, `CST_IPI`, `CST_PIS`, `CST_COFINS`,
`COD_MOD`, `COD_SIT`, `IND_EMIT`, `COD_MUN`, `COD_PAIS`, `CEST`, `COD_GEN`,
`TP_CT-e`, `COD_AJ_APUR`, `COD_REC`, `COD_INF_ADIC` (ICMS/IPI) e `NAT_BC_CRED`,
`COD_CRED`, `COD_AJ`, `IND_NAT_PROC` (Contribuições) — 16 e 12 domínios,
respectivamente, lidos de 268 tabelas.

O diálogo diz **de onde veio** cada verificação: quais campos foram validados
por tabela oficial e quais tabelas não foram encontradas. Sem os PVAs
instalados, valem as regras embutidas e o programa avisa.

Três cuidados embutidos: a **vigência** de cada código é respeitada (a tabela
única de CST do ICMS foi revogada em 2012 — hoje é origem + situação); os
códigos de **ajuste são estaduais**, e a UF sai do próprio 0000; e **zero à
esquerda sobrando não é erro** (`COD_PAIS 01058` é o `1058` da tabela), embora
código só de zeros seja tratado como campo vazio.

### Corrigir campos pelo leiaute

Aberta pelo **Diagnóstico**, na linha *Corrigir campos pelo leiaute*, confere **todo o
arquivo** contra o domínio de cada campo — NCM com 8 dígitos, CEST com 7, CFOP
com 4 começando por 1/2/3/5/6/7, CST de PIS e COFINS na tabela oficial, datas
que existem de verdade, campos de valor no formato numérico do SPED, e assim por
diante. A regra vale por **nome de campo**, então alcança qualquer registro que
o possua.

O resultado vem separado em duas naturezas:

- **Com conserto automático** — o valor está certo mas perdeu o zero à esquerda
  (CEST com 6 dígitos, NCM com 7, `TIPO_ITEM` com 1) ou é texto de vazio
  (`NULL`, `None`, `#N/A`, `#REF!`) em **qualquer** campo, inclusive nos de
  texto livre, como a descrição. O botão **Normalizar** corrige todos de uma vez, e a
  sugestão só existe quando falta **exatamente um** dígito — repor dois zeros
  seria inventar.
- **Exigem correção manual** — CST do ICMS incompleto, CFOP inexistente, data
  impossível. Esses ficam na lista, e o **duplo-clique leva até o registro**
  para você corrigir na grade.

Os dois filtros do topo (natureza e campo) servem para triagem em arquivo
grande. Num SPED real de 28.475 registros a varredura levou 0,11 s e encontrou
24.751 campos fora do domínio, 14.253 deles corrigidos num clique.

O diagnóstico procura ser específico. O erro mais comum no `CST_ICMS`, por
exemplo, não é lixo: é o **CSOSN do fornecedor do Simples** (`101`, `201`)
copiado sem o dígito de origem. O programa diz isso em vez de apenas "valor
inválido" — mas não sugere a correção, porque a origem da mercadoria é
informação fiscal, não formatação.

### Preencher COD_GEN pelo NCM (0200)

**Ferramentas → EFD ICMS/IPI → Preencher COD_GEN pelo NCM (0200)…** preenche o
gênero do item a partir do próprio NCM — são os **dois primeiros dígitos**
(Tabela 4.2.1). Como é derivável, não depende de a planilha trazer a coluna, e
não erra o zero à esquerda: o NCM é normalizado antes do corte.

Isso importa mais do que parece. Calcular `LEFT(NCM;2)` numa planilha cuja
célula de NCM é **numérica** devolve `40` para o NCM `04012010` — borracha no
lugar de laticínios. Num arquivo real seriam 593 itens com gênero errado, todos
com código existente, portanto sem erro visível. (Se preferir manter a coluna na
planilha, use `=LEFT(TEXT(NCM;"00000000");2)`.)

O diálogo mostra quantos itens estão sem COD_GEN e quantos têm outro valor,
com exemplos, antes de gravar. Itens sem NCM de 8 dígitos ficam de fora: não há
capítulo de onde tirar o gênero.

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
aparecem em cinza e são somente-leitura. Há atalhos no estilo do Excel:
**Ctrl+D** preenche as células selecionadas para baixo (com o valor da primeira
linha da seleção) e **Ctrl+R** preenche para a direita.

O painel de **Filtros** reproduz os do script SQL (data inicial/final, tipo de
movimento, modelo, nº da nota, código do produto, nº do item, NCM por prefixo,
CFOP, CST de ICMS/PIS/COFINS/IPI e alíquotas de PIS/COFINS — todos aceitando
listas separadas por **ponto e vírgula**). Clique em **Gerar relatório** para aplicar os filtros
e **Exportar CSV** para salvar o resultado (separador `;`, latin-1), que pode ser
confrontado com a saída do mesmo relatório no banco.

### Validar e corrigir o C175 (NFC-e modelo 65) por item

> **Em desenvolvimento.** Nenhum arquivo gerado por esta função passou ainda
> pelo PVA (faltam os XMLs de um mês real), então ela não entra numa versão de
> release até isso acontecer — ver ROADMAP.

Como as NFC-e (modelo 65) são escrituradas de forma **consolidada** em C175 (sem
itens), validar valor a valor exige um artifício. O fluxo, em **Ferramentas**
(EFD Contribuições), tem três passos:

1. **Validar C175 (modelo 65) com XMLs** — importa os XMLs das NFC-e e cria, em
   cada C100 modelo 65, registros **C170 fictícios** (um por item do XML), com
   **todos os dados do item**: descrição, quantidade, unidade, ICMS (CST, base,
   alíquota, valor), ICMS-ST, IPI e PIS/COFINS. Abre um relatório com as
   **discrepâncias** entre a soma dos itens e o C175 já escriturado (exportável
   em CSV).
2. **Corrigir por item** — os C170 fictícios ficam disponíveis no **Modo
   Relatório** (fonte C170) e podem ser editados célula a célula (com Ctrl+D/R).
3. **Regenerar C175 (modelo 65) dos itens** — reconsolida o C175 a partir dos
   itens corrigidos e **remove** os C170 fictícios, restaurando a estrutura
   consolidada do modelo 65.

### Importar inventário (bloco H) de planilha

**Ferramentas → EFD ICMS/IPI → Importar inventário (bloco H) de planilha…** lê
uma planilha **XLSX** ou **CSV** com o inventário e gera os registros do bloco H:
**H001** (com movimento), **H005** (data, motivo e valor total), um **H010** por
item — com unidade, quantidade, valor unitário, valor total, indicador de
propriedade e, quando informados, participante, complemento, conta contábil e
valor para IR — e o **H990** de encerramento.

**Atualizar o cadastro dos itens que já existem.** Marcando a opção, a planilha
também corrige o **0200** dos itens já cadastrados, e não só cria os ausentes —
é o caminho para quando o cadastro do arquivo é que está errado (NCM sem o zero
à esquerda, CEST faltando, descrição velha).

A correção **não é cega**: antes de gravar qualquer coisa, o programa mostra
campo a campo quantos valores mudariam, com exemplos, e você marca só o que deve
ser aplicado. Campo cujo valor novo está **fora da tabela oficial** nasce
desmarcado — vale a pena: num arquivo real, a mesma planilha que corrigia 447
NCM truncados traria `TIPO_ITEM` = `N`, que não existe na tabela, para 1.273
itens que estavam certos. Quando a planilha **zeraria a alíquota de ICMS**, o
aviso é separado, porque isso é mudança de tributação e não de cadastro.

Coluna não mapeada e célula vazia **nunca apagam** o que já está no cadastro.

**Número que não é número recusa a importação.** Quantidade, valores e
alíquota com `abc`, `1.2.3` ou `NULL` não viram zero: a importação inteira é
recusada antes de mexer no arquivo, e a mensagem diz a **linha da planilha** e
a coluna de cada célula. Até a 0.56.0 o item entrava no inventário com
quantidade zerada.

A primeira linha da planilha deve ser o **cabeçalho**. As colunas são
reconhecidas automaticamente pelo nome (por exemplo *Código do Produto*,
*Descrição*, *Unidade*, *Quantidade*, *Valor Unitário*, *NCM*, *Conta Contábil*)
e o **mapeamento pode ser ajustado manualmente**, de modo que qualquer layout de
planilha funciona. Só *código*, *unidade* e *quantidade* são obrigatórios; o
valor total é calculado (quantidade × valor unitário) quando não vier na
planilha.

**Comparar sem alterar:** o botão *Comparar com inventário atual* confronta o
**H010 já escriturado** com a planilha por **código e quantidade**, sem modificar
o arquivo — útil para conferir a contagem física contra o que foi escriturado.
O resultado separa os itens que conferem, os de quantidade divergente (com a
diferença), os que só existem no SPED e os que só existem na planilha, além das
somas dos dois lados, e pode ser exportado em CSV.

**Coerência com o cadastro 0200:** antes de gravar, o botão *Conferir com o 0200*
informa quantos itens já estão cadastrados, quantos serão criados, códigos
repetidos na planilha e divergências de descrição/unidade/NCM frente ao cadastro
atual. Na importação, os itens ausentes do **0200** são cadastrados (com
descrição, unidade, tipo e NCM da planilha) e os existentes **não são
duplicados**; unidades ainda não declaradas geram registros **0190**.

### Verificar CST por NCM (tabelas da RFB)
**Ferramentas → EFD Contribuições → Verificar CST por NCM (tabelas RFB)…**
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

### Fechar a escrituração

O botão **Fechar arquivo**, na barra, encerra a escrituração aberta e volta à
tela inicial. Se houver alterações não salvas, ele pergunta antes: **Salvar**,
**Descartar** ou **Cancelar**. Cancelar — ou fechar o diálogo de *Salvar como*
que aparece depois de escolher salvar — mantém o arquivo aberto, sem perder
nada. A mesma pergunta é feita ao sair do programa.

### Tela inicial

Sem nenhum arquivo aberto, a janela mostra uma **tela inicial** em vez das abas
de modo vazias:

- **Continuar** — abre o último período arquivado, com empresa e mês no rótulo;
- **Arrastar e soltar** — largue um `.txt` de SPED na janela para abrir;
- **Matriz empresa × período** (últimos 8 meses) — `●●` os dois leiautes
  arquivados, `●` só um, `—` nenhum; duplo clique abre o período;
- **Pendências** — empresa com arquivo mas sem cadastro (as rotinas por regime
  não rodam para ela) e cadastro que nunca recebeu arquivo;
- **Atalhos** — Empresas, Correlações de CFOP e tema.

> A matriz diz o que está **arquivado neste sistema**, não o que foi entregue
> ao Fisco: um período pode ter sido transmitido sem nunca ter sido aberto aqui.

A janela abre grande e centralizada; se a resolução for pequena, abre
**maximizada** e a interface passa à **densidade compacta**, com fonte e
espaçamentos menores para caber mais colunas na grade.

### Empresas, histórico e memória persistente

O botão **Empresas**, na barra principal, funciona como um **interruptor**:
clique e o editor dá lugar ao painel de empresas; clique de novo e você volta
de onde parou. Enquanto o painel está aberto, o botão fica com **moldura na cor
do acento**. O painel ocupa a janela inteira — lista de empresas à esquerda,
cadastro e histórico à direita — e funciona **sem nenhum arquivo aberto**, para
você cadastrar a empresa antes de importar o primeiro SPED (*Nova empresa…*,
pelo CNPJ). A lista reúne as empresas de `empresas.json` com as que já têm
arquivo no histórico.

**Memória persistente:** ao **abrir** e ao **salvar**, o programa guarda uma
cópia do arquivo em

```
arquivos/<CNPJ>/<LEIAUTE>_<AAAAMM>.txt
```

É a mesma ideia do banco interno do PVA, adaptada a um editor que trabalha o
texto direto: **uma cópia por empresa, leiaute e período**, sempre substituída
pela mais recente. O painel *Histórico de arquivos* lista os períodos daquela
empresa — duplo clique **abre a cópia interna**, não o arquivo de origem, que
pode ter sido movido ou apagado.

> **Fluxo com o PVA:** ao salvar, o aviso lembra de validar o arquivo no PVA e
> **reabrir aqui a versão validada**. Se o PVA regravar alguma coisa, a cópia
> interna só passa a refletir o arquivo definitivo depois que você reabri-lo no
> sistema.

A pasta `arquivos/` fica fora do controle de versão — são arquivos fiscais de
clientes.

### Configuração por empresa e rotinas de correção

**Ferramentas → EFD Contribuições → Empresa e rotinas…** abre o cadastro da empresa do arquivo
(identificada pelo **CNPJ do registro 0000**) e as rotinas que dependem dele.

O cadastro guarda o que o arquivo não diz: **regime federal** (Simples
Nacional, Lucro Presumido, Lucro Real), **regime de PIS/COFINS** (cumulativo,
não-cumulativo ou ambos), atividade, as alíquotas de saída e de crédito e o CST
a gravar quando um crédito indevido é retirado. Uma empresa ainda não cadastrada
vem pré-preenchida com o nome, a UF e o regime do registro **0110** — confira
antes de gravar. Os dados ficam em `empresas.json`, na pasta de dados (ver 3A).

Quando o **0110 do arquivo contraria o cadastro**, o diálogo avisa: é a
escrituração discordando do que a empresa declara ser, e vale conferir qual dos
dois está errado antes de rodar qualquer rotina.

As rotinas desta versão:

| Rotina | O que aponta | Corrige? |
|---|---|---|
| Alíquota de saída fora do regime | Itens de saída com CST 01 fora da alíquota do regime | Sim — aplica a alíquota e recalcula o valor |
| Crédito indevido na entrada | Entradas com CST de crédito (50-56, 60-66) e valor lançado, em empresa **cumulativa** | Sim — zera base/alíquota/valor e troca o CST |
| Alíquota de crédito fora do regime | Entradas do não-cumulativo com alíquota de crédito errada | Sim — aplica a alíquota de crédito |
| Valor lançado em CST sem direito a crédito | Entradas em CST sem crédito com base ou valor lançados | Sim — zera base/alíquota/valor |
| CST incoerente com o NCM | Monofásico / alíquota zero, pelas tabelas da RFB | Nas **entradas** que tomam crédito, sim; nas saídas, não — lá o CST depende de o produto ser revenda |
| Crédito em CFOP que não dá direito | CST de crédito em CFOP fora da tabela 4.3.7 do PVA | Sim — troca o CST e zera o crédito |

**Toda rotina roda primeiro em conferência.** O relatório é navegável (duplo
clique vai ao registro) e exportável em CSV; a correção só é aplicada depois de
confirmar, informando **quantos registros serão alterados**, e atua exatamente
sobre as ocorrências que você viu — nunca sobre um segundo diagnóstico. O
arquivo continua não salvo até você usar *Salvar como*.

> **Atenção ao regime "ambos":** quando a empresa tem receita nos dois regimes,
> as rotinas de alíquota se abstêm — 0,65/3,00 e 1,65/7,60 podem estar ambas
> corretas no mesmo arquivo, e apontar qualquer uma delas seria falso positivo.
> Pelo mesmo motivo, só o **CST 01** tem alíquota conferida: o 02 é justamente
> "alíquota diferenciada" e o 03 é por quantidade.

### Barra de título própria

A janela principal usa uma barra de título própria, no estilo do tema,
mostrando **empresa · período · leiaute · arquivo** e um indicador visível de
**alterações não salvas**.

A janela **continua nativa**: em vez de `FramelessWindowHint` — que faria o
Windows deixar de tratá-la como janela —, o programa intercepta três mensagens
(`WM_NCCALCSIZE`, `WM_NCHITTEST`, `WM_GETMINMAXINFO`). Com isso **Aero Snap**,
redimensionar pelas bordas, duplo clique para maximizar, menu de sistema e
sombra continuam funcionando, o que importa num editor quase sempre aberto ao
lado do PVA. A margem usada ao maximizar acompanha o **DPI do monitor**, para
o conteúdo não transbordar em telas com escala acima de 100%.

Os **diálogos mantêm a barra do Windows** — a substituição vale só para a
janela principal. Fora do Windows, ou se a preparação falhar, a barra nativa é
usada e o programa avisa na barra de status. Para forçá-la:

```bash
set SPED_TABLES_BARRA_NATIVA=1
python sped_editor.py
```

### Tema claro e escuro

A interface tem paleta própria, com **tema claro e escuro**. O botão à direita
da barra de ferramentas alterna entre os dois — o rótulo anuncia o destino
(*Tema escuro* quando você está no claro) — e a escolha é **gravada entre
sessões**, por máquina.

O acento é o **cobre**, o mesmo do Backup Maximus: os dois aplicativos são da
mesma família de ferramentas. As cores de significado são separadas do acento —
verde para "confere", âmbar para "atenção", vermelho para "divergência", azul
para a coluna **REG** (a chave estrutural) —, de modo que a cor de ação nunca se
confunde com a cor de estado. No tema escuro elas não são invertidas
automaticamente: sobem de saturação para continuar legíveis sobre fundo escuro.

A paleta e a folha de estilo ficam em **`sped_tables/interface/tema.py`**; os ícones do "✓" e da seta
dos combos são desenhados em tempo de execução na cor da paleta ativa
(**`interface/icones.py`**), porque o Qt Style Sheets não aceita imagem embutida.

### Pasta dos PVAs

As verificações que dependem das tabelas oficiais (validação de campos,
crédito por CFOP, prazo do 0900, descritor do PVA) e o **Abrir no PVA**
precisam saber onde os PVAs estão instalados. O programa procura sozinho na
pasta padrão da Receita (`C:\Arquivos de Programas RFB\Programas SPED`) e
nas de *Arquivos de Programas*. Se a instalação estiver noutro lugar, aponte
em **Ferramentas → Gerais → Pasta dos PVAs…** — a pasta certa é a que contém
`Fiscal` e/ou `EFD-Contribuicoes`. A escolha fica gravada; para voltar à
detecção automática, escolha a pasta padrão de novo.

### Quando algo dá errado

Um erro que o programa não esperava **não fecha a janela**. Ele é gravado
num registro, e uma caixa diz o que aconteceu e onde ficou o registro. Se
havia alteração não salva, uma **cópia de emergência** do arquivo é gravada
antes, na pasta `recuperacao` (ver 3A) — nunca por cima do seu arquivo.

Ao pedir ajuda, mande o arquivo `logs\sped_tables.log`: ele tem o rastro
completo do erro.

## 3A. Onde ficam os dados

Rodando **do código-fonte**, cadastro, configurações e cópias dos SPED ficam
na pasta do projeto. No **executável**, vão para `%APPDATA%\SPED Tables`: o
pacote *onefile* é extraído numa pasta temporária que o Windows apaga ao sair,
e gravar ao lado do programa perderia tudo a cada fechamento.

| Na pasta de dados | O que é |
|---|---|
| `empresas.json` | Cadastro das empresas (regime, alíquotas). |
| `correlacoes_cfop.json` | Correlações de CFOP saída → entrada. |
| `configuracao.json` | Pasta dos PVAs e caminhos das tabelas da RFB escolhidos. |
| `arquivos\` | O acervo: uma cópia de cada SPED por empresa e período. |
| `logs\` | Registro de erros (`sped_tables.log`) e de quedas nativas. |
| `recuperacao\` | Cópias de emergência gravadas quando um erro acontece. |

Nada disso vai para o repositório (`.gitignore`): são dados de clientes.

Na **primeira execução** do executável, o programa cria essa pasta, copia
para lá os padrões que vieram no pacote (sem sobrescrever nada que já seja
seu) e oferece criar um **atalho na área de trabalho**.

Para conferir se o executável está inteiro — tradução, ícone, pasta de
dados, tabelas do PVA, registro de erros —, rode
`"SPED Tables.exe" --autoteste relatorio.json` (com um SPED no fim, testa
também abrir e salvar). Ele trabalha numa pasta temporária, sem tocar no
seu cadastro, e grava o resultado no `relatorio.json`.

Duas variáveis de ambiente mudam os caminhos:

| Variável | Efeito |
|---|---|
| `SPED_TABLES_DADOS` | Usa outra pasta de dados (um disco de rede, por exemplo). |
| `SPED_TABLES_PVA` | Força a raiz das instalações dos PVAs. |
| `SPED_TABLES_BARRA_NATIVA=1` | Usa a barra de título do Windows. |

## 4. Estrutura do projeto

O programa é o pacote `sped_tables/`, organizado em camadas — a explicação
completa está em [ARQUITETURA.md](ARQUITETURA.md).

| Caminho | Conteúdo |
|---|---|
| `sped_editor.py` | Lançador: `python sped_editor.py [arquivo.txt]`. |
| `sped_tables/dominio/` | O documento SPED e as regras fiscais (sem tela, sem disco, sem PVA). |
| `sped_tables/aplicacao/` | Casos de uso: o arquivo aberto (abrir/salvar/fechar), mandar ao PVA, a montagem. |
| `sped_tables/infra/` | Configuração, pasta de dados, tabelas e automação do PVA, acervo, registro de falhas. |
| `sped_tables/interface/` | A aplicação PyQt6: janela, tabela de ações, controladores, grades, diálogos, tema. |
| `tests/` | Suíte automática (ver [TESTES.md](TESTES.md)). |
| `SPED Tables.spec` | Empacotamento (PyInstaller, arquivo único). |
| `icon.ico`, `correlacoes_cfop.json` | Recursos que vão junto no executável. |
| `ARQUITETURA.md` | Como o código se organiza e onde entra o que é novo. |
| `ROADMAP.md` | Canais de versão, critério de aceite e o caminho até a 1.0.0. |
| `TESTES.md` | A suíte automática e o roteiro manual (PVA, executável). |
| `CHANGELOG.md` | Histórico de versões (Keep a Changelog). |
| `CLAUDE.md` | Convenções do projeto para desenvolvimento assistido. |

### Testes

```bash
py -m unittest discover -s tests -t .
```

A suíte monta arquivos SPED sintéticos na hora — nenhum dado de cliente entra
no repositório — e roda também contra cópias de arquivos reais quando
`SPED_TABLES_ARQUIVOS_REAIS` aponta para elas. Detalhes em
[TESTES.md](TESTES.md).

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
- O leiaute cobre os dois SPEDs inteiros; uma coluna genérica (`Campo NN`)
  só aparece se o arquivo trouxer mais campos que o leiaute conhecido — e
  mesmo assim a edição e a gravação preservam tudo.
- Arquivos grandes (dezenas de milhares de registros) abrem em frações de
  segundo; as abas de bloco são construídas sob demanda para manter a abertura
  rápida.
- A **ordem, a fixação e o fechamento de abas** valem apenas **durante a
  sessão** — ao reabrir o programa, tudo volta ao padrão.
- **Não há desfazer (undo)** para edições em lote: prefira executar as rotinas
  com o arquivo já salvo, para poder voltar à cópia anterior.
- No fluxo da NFC-e (modelo 65), entre *Validar C175* e *Regenerar C175* o
  arquivo fica com registros C170 em documentos modelo 65 — estrutura
  **inválida** para o EFD Contribuições. **Não salve nem transmita nesse
  estado:** rode sempre o *Regenerar C175* antes de gerar o arquivo final.
- Os CST esperados na verificação por NCM (`CST_ACEITOS`/`CST_SUGERIDO`, em
  `sped_tables/dominio/ncm.py`) foram montados para **comércio/revenda**.
- As regras compostas do PVA (implementadas em Java dentro dele) não são
  reproduzidas; o diagnóstico diz quantas se aplicam ao arquivo. O validador
  oficial continua sendo o juiz.

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

- **Abas superiores** = blocos (0, A, C, D, E, …, 9).
- Dentro de cada bloco, **sub-abas** = registros principais (ex.: C001, C100, C990).
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

Sempre que você adiciona, remove ou recalcula registros, as contagens são
atualizadas: **X990** (ex.: `C990` = nº de linhas do bloco), **9900** (um por
tipo de registro, ex.: `9900|C190|<qtd>`), **9990** (linhas do bloco 9) e
**9999** (total do arquivo). Esses valores são **sempre reconstruídos ao
salvar** e podem ser atualizados na tela a qualquer momento por
**Ferramentas → Recalcular totais (C990/9900)**.

### Nome do produto no topo (grades C170)

Nas grades que têm **COD_ITEM** (ex.: **C170**), ao **selecionar uma linha** o
nome do produto aparece **centralizado no topo do widget** (ao lado do contador
`C170 — N registro(s)`), em destaque verde, no formato `📦 1021 — PESC PANGA
FILE...`. A descrição é buscada no cadastro **0200** (`COD_ITEM → DESCR_ITEM`).
Se o código não estiver cadastrado, o rótulo avisa; se você editar o `COD_ITEM`
da linha, o nome é atualizado na hora. A busca é indexada e se refaz sozinha
quando um registro 0200 é editado, criado ou removido.

## 4. Estrutura do projeto

| Arquivo            | Função                                                         |
|--------------------|----------------------------------------------------------------|
| `sped_editor.py`   | Interface gráfica PyQt6 (mestre-detalhe recursivo).            |
| `sped_model.py`    | Modelo de dados: parser, árvore pai/filho, CRUD e gravação.    |
| `sped_layouts.py`  | Níveis hierárquicos e nomes oficiais de campos por registro.   |
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

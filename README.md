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

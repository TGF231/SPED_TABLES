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
| `sped_layouts.py` | Layout dos registros por tipo e por leiaute (ICMS/CONTRIB): nomes de campos, nível hierárquico. |
| `sped_editor.py` | Toda a GUI (PyQt6): janela principal, grades, diálogos. |
| `sped_editor.ui` | Layout Qt Designer (carregado por `uic.loadUi`, com fallback programático). |
| `tema.py` | Paleta (claro/escuro) e folha de estilo QSS. **Toda cor da GUI sai daqui** — nunca literais no `sped_editor.py`. |
| `icones.py` | Ícones do QSS (✓ e chevron) desenhados em runtime na cor da paleta. |
| `xml_fiscal.py` | Parser de NF-e/NFC-e (`NFe`, `ItemNFe`, `ler_pasta`, `chave_doc`, `indexar`). |
| `conferencia.py` | Conferência XML × SPED (entradas modelo 55, C190) e correlações de CFOP. |
| `revisao.py` | Regras de revisão extensíveis (lista `REGRAS`). |
| `empresas.py` | Cadastro por CNPJ: regime federal e de PIS/COFINS, alíquotas, atividade. Persistido em `empresas.json` (fora do git). |
| `rotinas.py` | Rotinas de conferência/correção por regime (lista `ROTINAS`). Verificação nunca altera o arquivo; a correção recebe as ocorrências já exibidas. |
| `arquivos.py` | Memória persistente: cópia do SPED em `arquivos/<CNPJ>/<LEIAUTE>_<AAAAMM>.txt` + `indice.json`. Uma cópia por período. Fora do git. |
| `janela_custom.py` | Barra de título própria via mensagens nativas do Windows (WM_NCCALCSIZE/NCHITTEST/GETMINMAXINFO). Opcional: `SPED_TABLES_BARRA_CUSTOM=1`. |
| `tabelas_rfb.py` | Tabelas oficiais da RFB (alíquota zero, monofásicos, gênero, NCM) e verificação de CST. |
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

### Ao adicionar ações na GUI

Padrão em quatro pontos: criar a `QAction` em `_criar_acoes`, conectar
defensivamente em `_conectar_ui` (com `hasattr`, para `.ui` antigos), incluir em
`_montar_botao_ferramentas` e habilitar em `abrir()` conforme
`doc.layout` (`"ICMS"` ou `"CONTRIB"`). Diálogos não-modais (`show()`) precisam de
referência guardada (`self._dlg_x`) para não serem coletados.

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
- **VL_RED_BC (C190):** nos CST terminados em **20** ou **70**,
  `VL_OPR − VL_BC_ICMS` (nunca negativo).
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
  2208) com CST 50 é creditamento indevido (correto 73/98).
- **Regime (empresas.py / rotinas.py):** cumulativo = PIS 0,65 / COFINS 3,00 e
  **sem crédito** na entrada; não-cumulativo = 1,65 / 7,6 com crédito. No regime
  **"ambos"** as rotinas de alíquota **se abstêm** — as duas alíquotas convivem
  legitimamente no mesmo arquivo.
- **Só o CST 01 tem alíquota conferível:** 02 é "alíquota diferenciada" e 03 é
  por quantidade. Cobrar deles a alíquota nominal gera falso positivo.

## Empresa usada na validação

CASA DO ESPETO LTDA — CNPJ 22763092000102, MG, comércio/revenda. Os arquivos SPED
e XMLs reais usados nos testes ficam fora do repositório.

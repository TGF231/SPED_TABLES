# Testes — SPED Tables

Duas partes: a **suíte automática** (`tests/`), que roda a cada mudança, e o
**roteiro manual**, só para o que a automação não alcança — o PVA de verdade,
o executável e o comportamento da janela no Windows.

---

## 1. Suíte automática

### Rodar

Da raiz do projeto, com o interpretador que tem o PyQt6 (`py`):

```bash
py -m unittest discover -s tests -t .
```

Os testes são `unittest` puro; com o pytest instalado, `py -m pytest tests`
também roda. A suíte leva cerca de 8 segundos.

A interface roda **sem tela** (`QT_QPA_PLATFORM=offscreen`, definido em
`tests/__init__.py`). Cadastro de empresas, acervo, registros e preferências
que os testes gravam vão para uma pasta temporária (`SPED_TABLES_DADOS`). O
cadastro de verdade e o registro do Windows não são tocados.

### O que cada arquivo cobre

| Arquivo | Cobre |
|---|---|
| `test_documento` | Ida e volta byte a byte, hierarquia, encoding (UTF-8 lido, latin-1 gravado), gravação que não destrói o destino, bloco 9, largura de registro novo. |
| `test_calculos` | Formatos numéricos, zero à esquerda de planilha, GTIN, `NULL` do ERP, rateio de acessórios, C190 (agrupamento, frete, x20, x70 pela base de PIS/COFINS). |
| `test_bloco_m` | Débito, crédito refeito das entradas, ordem do leiaute, idempotência, cumulativo, conferência igual à geração. |
| `test_correcoes` | Cada correção que **grava**: NULL pela validação e normalizar, planilha de inventário com célula inválida, cálculos que recusam número inválido, COD_GEN, COD_CTA + 0500, itens sem referência, ICMS dos itens, C190 em massa, datas. Confere o conserto, a idempotência e o arquivo bem formado depois de salvar. |
| `test_conferencia` | Leitura de NF-e (XML sintético); conferência de entradas (casamento, divergência por item, CSOSN ignorado, nota sem C100); classificação de NCM (prefixo, exceção, vigência) e CST esperado; totais do C100; NFC-e 65 — C170 fictícios, regeneração do C175 e rateio igual na conferência e na geração. |
| `test_validacao` | Domínios de campo, sugestões (só com um dígito faltando), CST_ICMS e CFOP nunca sugeridos, normalização. |
| `test_revisao` | Todas as regras nos dois leiautes sem exceção, e as que reproduzem mensagens do PVA. |
| `test_diagnostico` | Diagnóstico nos dois leiautes e a pré-checagem do que o PVA recusa na importação. |
| `test_empresas_rotinas` | Alíquota normalizada, cadastro corrompido, rotinas por regime, `executar` sem propagar exceção. |
| `test_arquivos` | Acervo: cópia por período, índice, abrir do histórico sem truncar, remover. |
| `test_robustez` | Um teste por achado da revisão de código; configuração (`config`); JSON atômico; CSV com `;` e travessão. |
| `test_arquitetura` | **Regra de dependência entre as camadas**; a porta das tabelas oficiais com fonte inventada (regras testadas sem PVA); sessão e envio ao PVA sem tela; canal da versão. |
| `test_estrutura` | Armadilhas: código depois de `return`, import sem uso, nome da biblioteca padrão, método duplicado. |
| `test_interface` | A janela nasce; **toda ação do menu roda** nos dois leiautes; a tabela de ações é coerente; o formulário de empresa; `main()` inteiro pelo `sped_editor.py`. |
| `test_falhas` | Fallback de exceções: registro, cópia de emergência, aviso sem empilhar, e — em subprocesso — o processo sobrevive à exceção num slot (e morre sem o gancho). |
| `test_pva` | Cancelamento de cada espera da automação e classificação das telas do PVA, **sem abrir o PVA**. |
| `test_reais` | Arquivos reais, fora do repositório (ver 1.2). |

### 1.1 Arquivos de teste: sintéticos, nunca de cliente

`tests/fabrica.py` monta SPED completos na hora, **pelo nome dos campos**:

```python
m = icms_basico(itens=[{"COD_ITEM": "P1", "CST_ICMS": "020",
                        "VL_BC_ICMS": "6,00"}], frete="1,00")
doc = SpedDocument.carregar(m.gravar(pasta))
```

Os blocos são abertos e fechados, o X990 e o bloco 9 são contados e o fim de
linha é CRLF, como num arquivo de verdade. O CNPJ é inventado
(`CNPJ_TESTE`). **Nenhum arquivo, XML, planilha ou nome de cliente entra no
repositório.**

### 1.2 Arquivos reais: invariantes e gabarito

`test_reais` só roda quando uma variável aponta para uma pasta com cópias
dos arquivos reais (fora do git):

```bash
set SPED_TABLES_ARQUIVOS_REAIS=C:\caminho\das\copias
py -m unittest tests.test_reais
```

Em todo `.txt` que começa com `|0000|`, confere:

- gravar e reabrir não perde registro e estabiliza;
- recálculo do bloco M idempotente;
- nenhuma verificação levanta exceção;
- **as correções em lote** (normalizar — que esvazia o NULL —, COD_GEN, C190 em
  massa, bloco M): acabam com o que corrigem, não criam erro de estrutura,
  são idempotentes e o arquivo gravado volta idêntico;
- **gabarito**: se houver um `gabarito.json` na pasta, os números exatos de
  cada arquivo — quantos achados por regra de revisão e por tipo de
  diagnóstico. Gerar (depois de conferir os números à mão):

  ```bash
  py -m tests.test_reais gerar
  ```

É o "validar contra arquivos reais com números exatos" do projeto, sem pôr
dado de cliente no git. Mudança que altera o gabarito tem de ser explicada no
CHANGELOG.

**Regra nova do guia (`dominio/regras_guia.py`) passa antes nos arquivos
reais que o PVA validou**: ela não pode acusar nada que o PVA aceite. O
banco de cada validação do PVA de ensaio (`banco_pva.inconsistencias`)
diz o que o PVA acusou; o que a regra acusa a mais é falso positivo — quase
sempre condição ou tolerância que o guia não escreve e o PVA aplica (ver
CLAUDE.md, "Os guias práticos e as regras do guia").

### 1.2.1 Leiaute contra o PVA instalado

`tests/test_guias.py` confere, com o PVA instalado, que o leiaute do
programa tem a **estrutura** do descritor (largura e posição de cada campo,
registro a registro) e que, onde o guia nomeia o campo, o nome bate com o do
leiaute na mesma posição. Atualizou o PVA ou saiu guia novo: rode a suíte
antes de qualquer outra coisa — a divergência aparece aqui, não na grade do
usuário. Para refazer os JSON dos guias:

```bash
py ferramentas/extrair_guias.py ICMS "Guia Prático EFD - Versão X.pdf"
py ferramentas/extrair_guias.py CONTRIB "Guia_Pratico_EFD_Contribuicoes_X.pdf"
py ferramentas/cobertura_guias.py
```

### 1.3 Ao escrever um teste

- **Teste de ação de menu chama a ação**, não o diálogo. Foi pulando o
  método do menu que o "Validar campos pelo leiaute" derrubou o programa por
  três versões sem teste nenhum ver.
- **Guarde a referência do `QApplication`** (`_app()` em `test_interface`).
  Sem ela o processo morre com *exit 127* e nenhum traceback.
- **Nunca abra o PVA nem mande tecla**: troque `pva.janela`, `pva._janelas`
  e afins por falsos (`unittest.mock`).
- **Nome de arquivo com prefixo** (`test_`): um `select.py` na pasta sombreia
  a biblioteca padrão (há um teste que confere).
- Regra que precisa de tabela do PVA: ligue uma fonte inventada com
  `referencias.definir(...)` e restaure no `tearDown` (ver
  `test_arquitetura.FonteDeTeste`).

---

## 2. Roteiro manual

Só o que a suíte não cobre. Trabalhe sempre com **cópias**.

Marque: ✅ passou · ❌ falhou · ⏭️ não se aplica.

### 2.1 No PVA (antes de cada release)

O único juiz do arquivo é o validador oficial. `ferramentas/validar_no_pva.py`
faz este roteiro inteiro: grava uma cópia de cada arquivo real por fluxo de
correção, importa e valida cada uma no PVA e compara o que a validação
acusou com o arquivo original passado pelo mesmo caminho. Uma correção passa
quando não aparece mensagem nova nem aumenta a contagem de nenhuma.

```bash
py ferramentas/validar_no_pva.py preparar  --ensaio D:\pva_ensaio
py ferramentas/validar_no_pva.py gerar     --reais D:\reais --saida D:\saida
py ferramentas/validar_no_pva.py validar   --ensaio D:\pva_ensaio --saida D:\saida
py ferramentas/validar_no_pva.py relatorio --saida D:\saida
```

- **Roda numa cópia da instalação** (`preparar`), com porta de banco própria:
  importar no PVA de uso uma cópia do mesmo CNPJ e período **substituiria**
  a escrituração que está lá. A automação só dirige janela cujo executável
  está dentro da pasta de ensaio.
- `validar --manual`: sem automação — a ferramenta põe o caminho na área de
  transferência, você importa e valida, e ela só lê o resultado do banco do
  PVA (`infra/banco_pva.py`).
- A saída fica **fora do repositório** (a ferramenta recusa o contrário).
- Retoma de onde parou: o que já foi validado não é refeito. `gerar
  --fluxos x` refaz só esses e mantém o resto do manifesto.
- **Arquivo que o PVA recusa na importação** ganha uma segunda série,
  `arqNN_…_prep`, sobre uma **régua importável**: campos
  normalizados (o que esvazia o NULL), `TIPO_ITEM` inválido do 0200 como `00` e CST_ICMS curto
  completado com zeros. São decisões que o programa, de propósito, não toma
  sozinho — valem só para o roteiro poder julgar as correções pela
  validação, e não pela recusa.
- **CST por NCM** não tinha caso que grava nos arquivos reais (a correção só
  age em entrada que **toma** crédito). A série `arqNN_…_cstncm` põe o erro
  clássico sobre o arquivo real — entrada de monofásico ou alíquota zero com
  CST 50 e crédito, bloco M refeito — e julga só a correção contra ela.
- **O teto do PVA:** o relatório para de listar erros em 1.000 (as
  advertências vêm à parte). Acima disso, uma correção isolada só troca
  erros por outros que estavam escondidos, e o relatório diz
  "inconclusivo". O fluxo **cadeia** — todas as correções em sequência —
  é o que desce abaixo do teto e testa a interação entre elas.
- **Recusa** é o "Resultado da Importação". Um "Erro" sozinho é o fim de
  uma validação que achou erros.

Os fluxos cobertos:

- [ ] Recalcular C190 (um documento e em massa) → importar e validar no PVA
- [ ] Recalcular ICMS dos itens → PVA
- [ ] Trocar alíquotas de PIS/COFINS + recalcular bloco M → PVA
- [ ] Rotinas por regime (aplicar a correção) + bloco M → PVA
- [ ] Validar e regenerar C175 (NFC-e 65) → PVA
- [ ] Importar inventário (bloco H) → PVA
- [ ] Normalizar campos (inclui NULL), preencher COD_GEN e COD_CTA → PVA
- [ ] Alterar datas (C100) → PVA
- [ ] **Abrir no PVA** pelo botão, com o PVA fechado e com ele aberto numa
      escrituração: chega até "Validando a escrituração…"
- [ ] Anote os números (erros antes × depois) na entrada do CHANGELOG

### 2.2 No executável

```bash
pyinstaller "SPED Tables.spec"
"dist\SPED Tables.exe" --autoteste relatorio.json arquivo_real.txt
```

O **`--autoteste`** roda de dentro do executável o que só o empacotamento
quebra, e grava o resultado no JSON (código de saída 0 = passou). Ele usa
sempre uma pasta de dados temporária: nunca mexe no cadastro nem no acervo
de quem usa o programa. Cobre:

- tradução pt-BR do Qt (os botões "Sim", "Cancelar", "Salvar");
- ícone e correlações de CFOP empacotados; `openpyxl`;
- instalação da pasta de dados, e a segunda instalação não copia nada por
  cima;
- tabelas do PVA encontradas;
- leitura paralela de XMLs: 300 XMLs lidos por processos — o processo
  filho é o próprio executável, e sem o `freeze_support()` do lançador cada
  um abriria uma janela —, sem cair para threads e com o mesmo resultado da
  leitura um por um;
- registro de falhas: um erro provocado vai para `logs\sped_tables.log`
  e chega ao aviso;
- janela principal criada com ícone;
- com um arquivo: abrir, salvar e reabrir, com a cópia no acervo.

**Atualizar não apaga cadastro nem acervo:** rode o `--autoteste`, sem
arquivo, com `SPED_TABLES_DADOS` apontando para uma pasta com cadastro,
correlações e acervo, e confira que nada mudou.

Na tela, que o autoteste não vê:

- [ ] Primeira execução: cria `%APPDATA%\SPED Tables`, oferece o atalho
      (a pergunta em português, "Sim"/"Não")
- [ ] Ícone na janela, na barra própria e na barra de tarefas

### 2.3 Na janela, no Windows

- [ ] Barra de título própria: arrastar, Aero Snap, redimensionar pelas
      oito bordas, duplo clique maximiza, menu de sistema
- [ ] Monitor com escala acima de 100%
- [ ] Arrastar uma aba leva o conteúdo junto; fixar/fechar/resetar sub-aba
- [ ] Tema escuro: grade, diálogos e células coloridas legíveis
- [ ] Arrastar um `.txt` para a tela inicial abre o arquivo

### 2.4 Conferência com XMLs reais

A lógica é coberta pela suíte; a leitura dos XMLs de cada emissor, não.

- [ ] Conferir entradas (NF-e 55): documentos casam por modelo+série+número
- [ ] Conferir C190 com XMLs: grupos reconstruídos pela classificação do C170
- [ ] Validar C175 (NFC-e 65): C170 fictícios criados e removidos, contagem
      final igual à inicial

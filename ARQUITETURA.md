# Arquitetura — SPED Tables

Como o programa está organizado, por que assim, e onde cada coisa nova deve
entrar. Vale a partir da 0.53.0.

---

## 1. O modelo escolhido: camadas com portas e adaptadores

O ponto de partida era um único `sped_editor.py` de 7.200 linhas, com 28
classes, e módulos de regra que liam direto a pasta do PVA e gravavam JSON
em disco. O MVC foi descartado porque ele organiza **a tela** (modelo,
visão, controlador), e o problema aqui não era só a tela: era a regra
fiscal depender de onde o PVA está instalado, a gravação de cadastro
morar dentro do módulo de regra e a mesma ação existir em quatro lugares.

O modelo adotado é a **arquitetura em camadas com portas e adaptadores**
(a família "hexagonal" / "Clean Architecture"), no tamanho que um programa
de desktop precisa. Ela se resume em uma regra:

> **As dependências só apontam para dentro.** O centro — as regras
> fiscais — não sabe que existe tela, Windows, disco nem PVA. Quem está
> na borda conhece o centro; o centro nunca conhece a borda.

```
                 ┌────────────────────────────────────────────┐
                 │  interface   (PyQt6: janela, grades, menus)│
                 └───────┬───────────────────────┬────────────┘
                         │                       │
                         ▼                       ▼
                 ┌───────────────┐       ┌───────────────────┐
                 │  aplicacao    │──────►│  infra            │
                 │ (casos de uso)│       │ (base de          │
                 └───────┬───────┘       │  referência, disco│
                         │               │  Win32, PVA)      │
                         │               └─────────┬─────────┘
                         ▼                         │
                 ┌──────────────────────────────┐  │
                 │  dominio  (documento SPED e  │◄─┘
                 │  regras fiscais)             │
                 └──────────────────────────────┘
```

Tudo mora no pacote `sped_tables/`; o `sped_editor.py` da raiz é só o
lançador (`python sped_editor.py [arquivo.txt]`).

**Fora do `sped_tables/`**, na raiz do repositório, mora o `consolidador/`: a
ferramenta de quem **compila** o programa, que lê as instalações dos PVAs e os
guias e regrava as fontes da base de referência (`base/`). Ele pode importar o
`sped_tables` (reaproveita o leitor das tabelas e o compilador da base); o
`sped_tables` **nunca** importa o `consolidador`:

```
 consolidador/ ──(lê PVAs, guias, planilha de NCM)──► base/ (fontes em texto)
      │                                                  │
      │ pode importar                                    │ compilar
      ▼                                                  ▼
 sped_tables/  ◄── infra/referencias_base.py ◄── recursos/base_referencia.db
 (nunca importa o consolidador)                  (no executável, ou importada)
```

`tests/test_arquitetura.py` confere as duas direções.

---

## 2. As quatro camadas

### 2.1 `dominio` — o documento e as regras fiscais

O que o programa **sabe** de SPED, sem saber de mais nada.

| Módulo | Conteúdo |
|---|---|
| `sped_model.py` | `SpedDocument`, `Registro`, carga/gravação, hierarquia, todos os cálculos (C190, C175, bloco M, rateio…). |
| `sped_layouts.py` | O leiaute completo dos dois SPEDs. |
| `validacao.py` | Domínio de cada campo; varredura e normalização. |
| `revisao.py` | As regras de revisão (lista `REGRAS`). |
| `rotinas.py` | Rotinas de conferência/correção por regime. |
| `diagnostico.py` | As camadas de verificação do PVA agrupadas pelo módulo que corrige. |
| `conferencia.py` | Conferência XML × SPED e correlações de CFOP. |
| `ncm.py` | Classificação do NCM (alíquota zero, monofásico) e o CST esperado. |
| `empresas.py` | A entidade `Empresa`: regime, alíquotas, normalização. |
| `xml_fiscal.py` | O modelo da NF-e/NFC-e e o parser. |
| `referencias.py` | **A porta** das tabelas oficiais (ver §3). |

**Proibido aqui:** importar `infra`, `aplicacao`, `interface` ou `PyQt6`.
Um teste confere (`tests/test_arquitetura.py`). A exceção prática é ler o
próprio arquivo SPED ou XML que o usuário abriu — é o objeto do domínio,
não uma dependência de infraestrutura.

### 2.2 `infra` — o mundo de fora

Tudo que depende da máquina: onde as coisas estão e como se leem.

| Módulo | Conteúdo |
|---|---|
| `config.py` | **Ponto único de configuração**: onde estão os PVAs (só o *Abrir no PVA* os usa). |
| `dados.py` | Pasta de dados do usuário (projeto × `%APPDATA%`), gravação atômica, recursos empacotados. |
| `base_referencia.py` | A **base de referência**: compila `base/` num SQLite reproduzível, lê, escolhe a que vale (embutida × importada) e importa um pacote mais novo. |
| `referencias_base.py` | **O adaptador**: implementa a porta `dominio.referencias` sobre a base de referência. |
| `tabelas_oficiais.py` | Interpretação das tabelas oficiais a partir de texto (vigência, domínios por `datasource`, CFOP com crédito, naturezas…). |
| `tabelas_ncm.py` | Tabelas de alíquota zero e monofásicos → um `ClassificadorNCM` do domínio. |
| `cadastro.py` | Empresas e correlações de CFOP em JSON. |
| `arquivos.py` | O acervo (uma cópia por empresa/período) e o índice. |
| `exportacao.py` | CSV para o Excel brasileiro. |
| `pva.py` | Automação da janela do PVA (Win32). |
| `falhas.py` | Registro em arquivo, cópia de emergência, ganchos de exceção. |

**Proibido aqui:** `aplicacao`, `interface`, `PyQt6`. A infraestrutura pode
usar o domínio (ex.: `cadastro` monta objetos `Empresa`).

### 2.3 `aplicacao` — os casos de uso

O que o usuário **faz**, de ponta a ponta, sem tela. Cada caso de uso junta
domínio e infraestrutura e decide o que acontece quando uma parte falha.

| Módulo | Conteúdo |
|---|---|
| `sessao.py` | O arquivo aberto: `abrir`, `salvar`, `fechar`, cópia de emergência. Arquivar no acervo nunca impede abrir nem salvar. |
| `envio_pva.py` | Mandar ao PVA: pré-checagem (o que o PVA recusaria na importação), envio e como apresentar cada desfecho. |
| `montagem.py` | **Raiz de composição**: liga a porta ao adaptador (ver §3). |

**Proibido aqui:** `interface` e `PyQt6`. É isso que permite testar "abrir e
salvar" (`tests/test_arquitetura.py::TestSessao`) sem janela.

### 2.4 `interface` — a aplicação PyQt6

Apresenta e pergunta; não decide regra fiscal.

```
interface/
├── app.py                 main(): tradução, tema, fallback, montagem
├── janela.py              JanelaPrincipal: monta a tela e delega
├── acoes.py               a TABELA de ações (menu, barra, habilitação)
├── controladores/         o que cada ação faz, por área do menu
│   ├── arquivo.py           abrir, salvar, fechar, PVA
│   ├── icms.py              ferramentas do EFD ICMS/IPI
│   ├── contribuicoes.py     ferramentas do EFD Contribuições
│   └── gerais.py            as que valem para os dois
├── grade.py               a grade mestre-detalhe (recursiva)
├── telas/                 páginas: resumo, relatório, inicial, empresas
├── dialogos/              janelas de conferência, correção, cadastro…
├── formulario_empresa.py  o formulário de empresa (um só, para 2 telas)
├── comum.py               preferências, exportar CSV, formatação
├── barra_titulo.py, janela_custom.py, tema.py, icones.py
```

Três peças merecem explicação:

**Controladores são *mixins* da janela.** `JanelaPrincipal` herda de
`ControladorArquivo`, `ControladorIcms`, `ControladorContribuicoes` e
`ControladorGerais`. Cada um é um arquivo com os métodos de uma área do
menu; juntos formam a janela. Um método de controlador usa `self.doc`,
`self.statusBar()` e os demais membros da janela como se estivesse nela —
porque está. O ganho é ter 1.900 linhas de ações divididas por assunto,
sem inventar uma camada de mensagens entre a janela e elas.

**A tabela de ações (`acoes.py`).** Cada ação é **uma linha**: atributo,
rótulo, método, quando fica habilitada (sempre / com arquivo / só ICMS /
só Contribuições / com PVA instalado), onde aparece e se está pronta para
release. A janela cria, conecta, põe no menu e habilita tudo a partir dela.
Antes, cada ação existia em quatro lugares — e esquecer um derrubou a
janela duas vezes e deixou uma ação fora de todos os menus.

**`doc`, `caminho` e `alterado` são da sessão.** A janela os expõe como
propriedades que leem `self.sessao` (o caso de uso). Widgets e diálogos
continuam usando `janela.doc`; quem muda o estado é a `Sessao`.

---

## 3. A porta das tabelas oficiais

Parte das regras depende de dados que não são do arquivo nem do programa:
o descritor de validação de cada versão de leiaute, as tabelas de códigos
com vigência, a tabela de CFOP com crédito (4.3.7), o prazo de entrega, os
guias práticos. Eles nascem nos PVAs e nos guias da Receita — mas o programa
**não os lê de lá**: quem os extrai é o consolidador, na máquina de quem
compila, e eles viajam na **base de referência**. Com PVA antigo na máquina de
quem usa, a pré-validação seria outra; com a base, é a mesma.

A solução é uma **porta**: `dominio/referencias.py` define *o que* o
domínio pergunta (`estrutura(layout, versao)`, `naturezas_cfop_credito(data)`,
`prazo_entrega(mes_ano)`…); `infra/referencias_base.py` responde lendo a base
de referência; `aplicacao/montagem.py` liga um ao outro no início do programa
(e de novo depois de importar uma base mais nova).

```
revisao.verificar_0900_ausente(doc)
        │  pergunta:  referencias.atual().prazo_entrega("082026")
        ▼
dominio.referencias ──(ligada por montagem.configurar())──► infra.referencias_base
                                                              └─ base_referencia → recursos/base_referencia.db
```

A base é compilada de `base/` (fontes em texto, versionadas) e vale a mais
nova entre a embutida no executável e a importada em *Configurações → Base de
referência…*.

**A porta pede a versão do leiaute do arquivo.** `estrutura(layout, versao)`
devolve a estrutura do `COD_VER` que o arquivo declara
(`referencias.versao_do_leiaute(doc)` o tira do 0000); `versao=None` é "a mais
recente", que só a geração de um período novo usa. Versão que a base não guarda
volta como `fora_da_base`: o programa avisa e se abstém, em vez de cobrar a
estrutura de outra versão.

Sem nada ligado vale a fonte **vazia**: cada regra que precisa de tabela se
abstém, que é o que acontece quando nenhuma base é legível (e a pessoa é
avisada). E um teste pode ligar uma fonte inventada:

```python
class FonteDeTeste(referencias.Referencias):
    def prazo_entrega(self, mes_ano):
        return "30092026"

referencias.definir(FonteDeTeste())
revisao.verificar_0900_ausente(doc, hoje="20261001")   # acusa
```

É assim que `tests/test_arquitetura.py` testa as regras de crédito por
CFOP e do 0900 sem depender da base. O adaptador, por sua vez, lê qualquer
origem com a interface da `Base` (`manifesto`, `versoes`, `estrutura`,
`tabelas`, `guia`, `ncm_vigente`): a instalação do PVA, no consolidador,
tem essa interface — e é assim que `tests/test_equivalencia_base.py` põe o
mesmo adaptador para ler a base e o PVA e conferir que respondem igual.

---

## 4. Três fluxos, de ponta a ponta

**Abrir um arquivo.** Menu *Abrir…* → `acoes.py` liga a
`ControladorArquivo.abrir` → pergunta o arquivo → `sessao.abrir(caminho)`
(domínio: `SpedDocument.carregar`; infra: `arquivos.arquivar`, que pode
falhar sem impedir) → o controlador monta as abas, habilita as ações pela
tabela e agenda o diagnóstico.

**Recalcular o bloco M.** `ControladorContribuicoes.recalcular_bloco_m`
mostra a prévia e confirma → `doc.recalcular_bloco_m()` (domínio) pede as
naturezas de crédito à porta → a interface mostra o resumo e marca o
arquivo como alterado.

**Mandar ao PVA.** `ControladorArquivo.abrir_no_pva` →
`envio_pva.pre_checagem(doc)` (o que o PVA recusaria) → confirmação →
`envio_pva.enviar(...)` numa thread, com barra de progresso e cancelar →
`envio_pva.desfecho(resultado)` diz se basta a barra de status, uma
informação ou um alerta.

---

## 5. Onde colocar o que é novo

| Vou criar… | Vai em… |
|---|---|
| Uma regra de revisão | `dominio/revisao.py`, na lista `REGRAS`. Se tem correção, o atalho no mapa `acoes` de `ControladorGerais.revisar_erros` (a chave é o rótulo da lista `REGRAS`). |
| Um achado de diagnóstico | `dominio/diagnostico.py` + o módulo que corrige em `MODULOS`; o atalho no mapa `acoes` de `ControladorGerais.diagnosticar`. |
| Um cálculo que grava no arquivo | Método de `SpedDocument` (ou módulo do domínio), com teste em `tests/test_correcoes.py`. |
| Algo que precisa de tabela oficial | Método novo na porta (`dominio/referencias.py`, com resposta vazia) e no adaptador (`infra/referencias_base.py`). |
| Uma tabela, versão de leiaute ou guia novo | **Não vai no código nem em `base/` à mão:** `py -m consolidador extrair` (ou `guia`) regrava `base/`, e a revisão é o `git diff base/`. |
| Um caminho, pasta ou opção da máquina | `infra/config.py`. Nunca `__file__`, nunca caminho escrito no módulo. |
| Ler ou gravar um arquivo do usuário | `infra/` (JSON: `dados.gravar_json`, que é atômico). |
| Um fluxo que junta várias peças | `aplicacao/`. |
| Uma ação de menu | **Uma linha** em `interface/acoes.py` + o método num controlador. |
| Uma janela de diálogo | `interface/dialogos/`, no arquivo do assunto. |

Uma função nova que ainda não cumpre o critério de aceite do
[ROADMAP.md](ROADMAP.md) entra com `pronta=False` na tabela de ações: aparece
nas versões de desenvolvimento e some de uma release.

---

## 6. O que os testes garantem

- `test_arquitetura` — a regra de dependência entre as camadas (o
  `sped_tables` não importa o `consolidador`; só o *Abrir no PVA* cita a pasta
  do PVA); a porta com fonte inventada, e a fonte vazia quando não há base; a
  sessão e o envio ao PVA sem tela; o canal da versão.
- `test_base_referencia`, `test_referencias_base`, `test_consolidador`,
  `test_versao_leiaute` — a compilação reproduzível, a importação que recusa
  o que não serve, o adaptador, a extração e a versão do leiaute pelo
  arquivo. `test_equivalencia_base` (só com PVA instalado) confere que a base
  responde igual ao PVA de onde saiu.
- `test_estrutura` — código depois de `return` (o `def` apagado por
  edição), import sem uso, módulo com nome da biblioteca padrão, método
  definido duas vezes.
- `test_interface` — a janela nasce, **toda ação do menu roda** nos dois
  leiautes, a tabela de ações é coerente, `main()` sobe e desce.

Ver [TESTES.md](TESTES.md).

---

## 7. O que ficou de fora de propósito

- **Diálogos como MVP completo** (apresentador separado de cada tela). Os
  diálogos já chamam o domínio para tudo que é regra; separar ainda a
  lógica de apresentação de cada um dobraria o número de arquivos sem
  ganho proporcional.
- **Injeção de dependência generalizada.** Só existe uma porta —
  referências oficiais —, porque é a única dependência externa que varia
  (de uma versão da base para outra) *e* que o domínio precisa. Disco e
  acervo são usados pela aplicação, não pelo domínio, e dispensam porta.
- **Undo/redo.** Pediria que cada edição fosse um comando do domínio;
  está no roadmap pós-1.0.

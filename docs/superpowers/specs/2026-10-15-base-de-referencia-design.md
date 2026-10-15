# Base de referência — desenho (projeto 1 de 4)

Data: 15/10/2026. Vocabulário em `CONTEXT.md`; decisões de fundo em
`docs/adr/0001-base-de-referencia-compilada.md` e
`docs/adr/0002-regras-em-sql-sobre-o-arquivo.md`.

## Contexto

O objetivo maior é o SPED Tables ser um **pré-validador consistente com o
PVA** e absorver rápido as atualizações das regras e das tabelas. Ele foi
dividido em quatro projetos, nesta ordem:

1. **Base de referência** (este documento);
2. Motor de regras (SQL sobre o arquivo montado como banco, ocorrência
   1:1 com o PVA, causa);
3. Consolidador completo (diferença entre versões do PVA, confirmação no
   PVA de ensaio, notas técnicas);
4. Migração das regras atuais e ampliação da cobertura.

Hoje o programa lê, **na máquina de quem o usa**, o descritor, as tabelas e
o leiaute direto da instalação do PVA (`infra/referencias_pva.py`,
`descritor_pva.py`, `tabelas_pva.py`, `tabelas_rfb.py`). Com PVA antigo
na máquina, a pré-validação discorda do PVA vigente; sem PVA, as regras se
abstêm. Este projeto troca essa fonte por uma **base de referência**
montada na compilação.

## Objetivo e critérios de aceite

Ao fim deste projeto:

1. **O programa não lê nada da instalação do PVA** para validar, diagnosticar
   ou corrigir. A instalação local só é usada pelo *Abrir no PVA* (e pelo
   consolidador, na máquina de quem compila).
2. **O resultado não muda.** O diagnóstico, a revisão e as correções sobre os
   arquivos reais dão exatamente o mesmo resultado de hoje
   (`tests/test_reais.py` com o `gabarito.json` atual), **com a pasta do
   PVA apontada para um lugar vazio**.
3. **A estrutura do leiaute vale pela versão do arquivo** (`COD_VER` do 0000,
   com o período): um arquivo de 2025 é conferido com o descritor da versão
   de 2025, não com o mais recente.
4. **A base atualiza sem programa novo:** *Configurações → Atualizar base de
   referência…* importa uma base mais nova, com conferência de integridade.
5. **A base sai do executável e é reproduzível:** compilar as mesmas fontes
   duas vezes dá o mesmo arquivo, byte a byte.

Fora deste projeto: regras compostas novas, o motor SQL, a causa, o
relatório de diferença entre versões do PVA, notas técnicas, download
automático, assinatura digital.

## O que a base contém

Só fatos, nunca código do PVA (ADR 0001):

| Conteúdo | Origem na compilação | Hoje |
|---|---|---|
| Estrutura do leiaute **por versão**: registros, campos, tipo, tamanho, decimais, obrigatoriedade, enumeração, tabela externa, referência entre registros, chave, e a lista de `REGRA_…` declaradas em cada registro (com momento e campos) | descritores do PVA de quem compila | descritor mais recente, lido na máquina do usuário |
| Correspondência versão do leiaute → período de vigência | tabela `VERSOES_LEIAUTE` (ICMS/IPI); no Contribuições, levantada na primeira tarefa do plano e conferida importando um arquivo de cada versão no PVA de ensaio | só a versão mais recente |
| Tabelas externas com vigência: CST, CFOP, códigos de ajuste e de receita por UF, naturezas da receita, CFOP com crédito, prazos, monofásicos e alíquota zero, gênero do item | pastas de tabelas dos dois PVAs, depois do *Atualizar Tabelas* | lidas da máquina do usuário |
| NCM vigente (Siscomex) | planilha que quem compila entrega ao consolidador | caminho escolhido pelo usuário |
| Guias práticos já extraídos | `recursos/guia_*.json` (hoje) | já viajam com o programa |
| Manifesto: versão da base (`AAAA.MM.n`), data, origem (versões dos PVAs e dos guias usados), versão do esquema | gerado | — |

Retenção (Q20): as versões do leiaute com vigência nos últimos **5 anos**
mais a atual. Arquivo de versão mais antiga é avisado como **fora da base**
e as validações que dependem do leiaute se abstêm, como hoje quando não há
PVA.

A configuração *Tabelas da RFB* (caminhos escolhidos pelo usuário) sai da
interface: as tabelas passam a vir da base.

## Arquitetura

```
consolidador/  ──► (lê PVA, guias, planilhas)  ──► base/ (fontes em texto)
     │                                              │
     └──────── compilar ───────────────────────────►│──► base_referencia.db
                                                         (vai no executável;
sped_tables/infra/referencias_base.py ◄── lê ────────────  importável)
          │
          └──► dominio.referencias (a porta, que já existe)
```

- **`consolidador/`**: pacote novo na raiz do repositório, com linha de
  comando (`py -m consolidador …`). Para ele se mudam, intactos, os
  leitores de hoje (`descritor_pva`, `tabelas_pva`, a parte de PVA do
  `tabelas_rfb`) e o `ferramentas/extrair_guias.py`. O `sped_tables` **nunca
  importa** o `consolidador`; o contrário é permitido.
  `tests/test_arquitetura.py` passa a conferir as duas coisas.
- **`base/`**: as fontes em texto, versionadas no git e revisáveis por diff.
  JSON ordenado e indentado para estrutura e manifesto; uma tabela por
  arquivo em texto separado por tabulação, UTF-8, ordenado. Ficam no
  repositório porque são fatos públicos (tabelas da Receita, leiaute do
  guia) e não código do PVA.
- **Compilação** (`sped_tables/infra/base_referencia.py`, chamada por
  `py -m consolidador compilar`): lê `base/`, grava um SQLite com ordem
  determinística e o `.sha256` ao lado. Fica no `sped_tables`, e não no
  consolidador, porque não lê nada do PVA — só texto do repositório — e
  porque o programa rodando do código-fonte compila a base sozinho quando
  ela falta ou é mais velha que `base/`. O
  `ferramentas/gerar_executavel.py` compila antes do PyInstaller e embute o
  banco como recurso (`dados.recurso`).
- **O consolidador, neste projeto, só extrai**: `py -m consolidador
  extrair` lê os PVAs, os guias e a planilha de NCM e regrava `base/`. A
  revisão do que mudou é o diff do git.
- **`sped_tables/infra/referencias_base.py`**: o novo adaptador da porta
  `dominio.referencias`, lendo o SQLite. `aplicacao/montagem.configurar()`
  passa a ligá-lo no lugar do `ReferenciasPVA`, que deixa de existir no
  programa.
- **Qual base vale:** a mais nova entre a que veio no executável e a
  importada (guardada na pasta de dados do usuário). Importada corrompida
  ou ilegível → aviso e vale a embutida.

### A porta muda num ponto: a versão

Hoje `referencias.atual().estrutura(layout)` devolve sempre o descritor
mais recente. Passa a ser `estrutura(layout, versao=None)`: `versao` é a
versão do leiaute do arquivo (`COD_VER`); `None` mantém o comportamento
atual (a mais recente), que é o que a geração de um período novo usa. Um
helper do domínio, `versao_do_leiaute(doc)`, tira a versão do 0000. Quem
tem o documento em mãos (diagnóstico, revisão, regras do guia, cálculos do
modelo, ajuda) passa a versão; a geração pelos XMLs passa a versão do
período que gera.

Os demais métodos da porta (domínios, CFOP com crédito, naturezas, prazo,
classificador de NCM, códigos de receita, guia) não mudam de assinatura:
já recebem a data de referência quando a vigência importa.

## Atualizar a base (importação)

*Configurações → Atualizar base de referência…* abre o arquivo distribuído
(`base_referencia-AAAA.MM.n.zip`: o banco e o manifesto). Antes de aceitar,
mostra versão, data, origem e a impressão digital (SHA-256), para comparar
com a publicada. Recusa, dizendo o motivo:

- impressão digital que não confere com o banco;
- versão igual ou mais antiga que a em uso;
- esquema mais novo do que o programa entende ("atualize o programa").

A tela *Sobre* mostra a versão do programa e a da base.

## Tratamento de erros

- **Base embutida ausente ou ilegível** (executável danificado): o programa
  abre e avisa; as validações que dependem dela se abstêm — o mesmo
  comportamento de hoje sem PVA.
- **Arquivo fora da base** (versão do leiaute não guardada): aviso no
  diagnóstico; nada é acusado por estrutura de outra versão.
- **Consolidador sem PVA na máquina:** recusa compilar e diz o que falta;
  nunca gera base parcial em silêncio.

## Testes

- **Equivalência, o teste central da migração:** na máquina com PVA, cada
  método da porta respondido pelo leitor antigo (agora no consolidador) e
  pelo adaptador da base dá o mesmo resultado, para os dois leiautes e para
  datas de referência dentro da vigência. Se pula sem PVA.
- **Arquivos reais sem PVA:** `test_reais` com a pasta do PVA apontada para
  um diretório vazio; gabarito inalterado.
- **Versão por arquivo:** um arquivo sintético com `COD_VER` antigo é
  conferido com a estrutura daquela versão (um campo que só existe na nova
  não é cobrado).
- A suíte compila a base de `base/` uma vez por execução, numa pasta
  temporária; nenhum teste depende de PVA instalado, salvo o de
  equivalência.
- **Compilação:** a partir de fontes pequenas de teste, o banco tem o
  conteúdo esperado e duas compilações dão o mesmo SHA-256.
- **Importação:** mais nova aceita; igual, mais antiga, corrompida ou de
  esquema novo recusada com a mensagem certa.
- **Arquitetura:** `sped_tables` não importa `consolidador`, e nenhum módulo
  do `sped_tables` lê a pasta do PVA além de `infra/pva.py` e
  `aplicacao/envio_pva.py` (o *Abrir no PVA*).
- Os testes que hoje leem o descritor instalado (`test_guias`,
  `test_regras_guia`) passam a ler a base e **deixam de pular** quando não
  há PVA.
- **Executável:** o autoteste confere que a base embutida carrega e mostra
  a versão.

## Documentação

CLAUDE.md (seções sobre domínios do PVA, descritor e a regra "nada do
domínio lê a instalação do PVA"), README (atualizar a base, fim da
configuração das tabelas da RFB), TESTES.md e CHANGELOG. O
`ROADMAP_REGRAS_PVA.md` é reescrito com os quatro projetos.

## Riscos

- **Correspondência versão → descritor no Contribuições** sem declaração
  legível: resolvida pela conferência no PVA de ensaio, um arquivo por
  versão; se alguma versão não puder ser confirmada, fica fora da base e o
  arquivo dela é tratado como "fora da base".
- **Tamanho:** as tabelas somam 6,4 MB em texto e as estruturas de ~6
  versões por leiaute alguns MB; a base compilada deve ficar abaixo de
  10 MB. O plano mede depois da primeira compilação.
- **Base desatualizada no executável distribuído:** é para isso a
  importação; a data na tela *Sobre* torna o atraso visível.

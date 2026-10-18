# Roadmap — SPED Tables

Para onde o programa vai e o que falta para cada marco. Substitui o antigo
`FUNCIONALIDADES.md`, que marcava funções como "estável", "em
amadurecimento" ou "experimental" — marcas que não cabem numa versão
entregue. O que cada função faz, e como usá-la, está no
[README](README.md); como o código se organiza, em
[ARQUITETURA.md](ARQUITETURA.md).

---

## 1. A regra: release não tem função pela metade

Numa **versão de release**, toda função que aparece na tela está **pronta**
— cumpre o critério de aceite da seção 3. Não existe "parcial", "beta" ou
"experimental" dentro de uma release: o que não está pronto não aparece.

Maturidade intermediária existe só nos **canais de desenvolvimento**, e
quem a declara é o **número da versão** (identificador de pré-release do
SemVer), não uma etiqueta ao lado da função:

| Canal | Versão | Para quem | Pode conter |
|---|---|---|---|
| **dev** | `1.1.0-dev.3` (e toda a série `0.y.z`) | desenvolvimento | qualquer coisa |
| **alpha** | `1.1.0-alpha.1` | teste interno | função nova completa, ainda sem arquivo real |
| **beta** | `1.1.0-beta.2` | usuários convidados | validada em arquivo real; falta PVA ou executável |
| **rc** | `1.1.0-rc.1` | candidata | congelada: só correção |
| **release** | `1.1.0` | todos | só o que cumpre a seção 3 |

Sufixos fora da lista (`-nightly`, `-preview`, `-canary`) contam como
**dev** — na dúvida, nunca release.

**Isso está no código.** `version.canal()` lê a versão; cada ação da tabela
de ações (`interface/acoes.py`) tem `pronta=True/False`, e numa release as
não prontas simplesmente não são criadas — nem menu, nem atalho
(`acoes.visiveis()`, com teste em `tests/test_arquitetura.py`). Uma função
nova nasce com `pronta=False` e só vira `True` quando passa pelo critério.

**Onde estamos:** `1.0.0-rc.2`, canal **rc**. O rc.1 estava congelado (só
correção); o rc.2 é exceção pedida pelo usuário — "profissionalizar a
ferramenta seguindo os manuais dos dois SPEDs" antes da 1.0.0: os guias
práticos como fonte (ajuda de campo, regras com as condições do PVA) e o
leiaute alinhado ao descritor instalado. A 1.0.0 sai quando fecharem as
verificações manuais que faltam (4.2), a partir do commit do rc.2.

Depois do rc.2 o desenvolvimento seguiu na **1.1.0** (`1.1.0-dev.N`), a
pedido do usuário: leitura de XMLs em paralelo (dev.1) e integração com
os bancos dos ERPs por perfil (Firebird 2.5/5.0, SQL Server, MySQL, DBF).
Toda a série 0.y.z foi sandbox: nenhuma versão antes da 1.0.0 é entregue
como release.

---

## 2. Versionamento

- **SemVer** em `sped_tables/version.py`; toda mudança relevante ganha
  entrada no [CHANGELOG](CHANGELOG.md) (formato Keep a Changelog).
- A partir da 1.0.0: **MAJOR** muda o formato de algo gravado pelo usuário
  (cadastro, acervo, configuração) de forma incompatível; **MINOR**
  acrescenta função; **PATCH** só corrige.
- O que sai do pacote numa release: o executável e a documentação. A suíte
  de testes e o roteiro manual (ver [TESTES.md](TESTES.md)) são o portão.

---

## 3. Critério de aceite ("pronta")

Uma função está pronta quando cumpre **todos** os itens que se aplicam a
ela:

1. **Suíte:** coberta por teste automático em `tests/`, inclusive o
   disparo pela ação do menu.
2. **Arquivo real:** conferida em cópia de arquivo real, com os números no
   gabarito (`tests/test_reais.py`) — sem nenhum dado de cliente no git.
3. **PVA:** se **grava** no arquivo, o arquivo resultante é importado e
   validado no PVA sem erro novo (roteiro 2.1 do TESTES.md).
4. **Executável:** funciona no pacote gerado pelo PyInstaller.
5. **Documentada:** o README diz o que faz, a regra de uso e o limite.

---

## 4. Marco 1.0.0

### 4.1 Escopo e situação

"—" é critério que não se aplica (a função não grava no arquivo, por
exemplo). O item 4 (executável) é comum a todas e está na seção 4.2.

| Área | Funções | Suíte | Arquivo real | PVA |
|---|---|---|---|---|
| Edição | Abrir, grade mestre-detalhe, editar, adicionar/remover, salvar com segurança, soma da seleção, abas, tela inicial, tema, barra própria | ✔ | ✔ ida e volta idêntica | — |
| Relatório | Modo Relatório: três fontes, filtros, edição, CSV | ✔ ações | ✔ | — |
| ICMS/IPI | Recalcular C190 (documento e em massa) | ✔ | ✔ | ✔ |
| | Recalcular ICMS dos itens (e C190/totais dos alterados) | ✔ | ✔ | ✔ |
| | Totais do C100 | ✔ | ✔ | ✔ |
| | Inventário do bloco H (importar, comparar, atualizar 0200) | ✔ | ✔ 11.585 itens | ✔ na cadeia, abaixo do teto |
| | Preencher COD_GEN | ✔ | ✔ | ✔ |
| Contribuições | Recalcular bloco M (apuração e crédito) | ✔ | ✔ | ✔ |
| | Trocar alíquotas de PIS/COFINS | ✔ | ✔ | ✔ |
| | NFC-e 65: importar XMLs, validar e regenerar C175; no ICMS/IPI, C170 fictícios para refazer o C190 | ✔ | ✔ 205 documentos; ICMS/IPI: 318 NFC-e, C190 idêntico salvo o VL_RED_BC | **pendente** — `pronta=False` |
| | CST por NCM (verificar e corrigir) | ✔ | ✔ 79 casos | ✔ com o erro injetado no arquivo real: 34 → 0 |
| | Empresas e rotinas por regime | ✔ | ✔ verificação; correção por controle | ✔ |
| Gerais | Diagnóstico, revisão, validação de campos | ✔ | ✔ gabarito | ✔ contra o banco do PVA |
| | Normalizar campos (inclui NULL), COD_CTA, itens sem referência | ✔ | ✔ | ✔ |
| | Alterar datas (C100) | ✔ | ✔ | ✔ |
| | Conferência com XMLs (entradas, C190, itens) | ✔ | ✔ | — |
| | Abrir no PVA (importar e validar) | ✔ sem PVA | ✔ nos dois PVAs | — |
| | Acervo e histórico por empresa | ✔ | ✔ | — |
| Sistema | Fallback de exceções, registro, cópia de emergência | ✔ | — | — |

**PVA:** 56 validações sobre 4 arquivos reais, nenhuma correção criando
erro que o original não tenha — os números estão no CHANGELOG (0.54.0,
0.56.0 e 0.57.0). A única função sem a coluna fechada é a **NFC-e 65**, que
precisa dos XMLs dos cupons de um mês real: ela está com `pronta=False` e
**some de uma release** até lá.

### 4.2 Etapas

| Versão | Entrega | Situação |
|---|---|---|
| 0.51.0 | Suíte de testes no repositório; fallback de exceções | ✔ |
| 0.52.0 | Configuração num ponto só; achados menores da revisão | ✔ |
| 0.53.0 | Arquitetura em camadas; tabela de ações; correções cobertas pela suíte; canais de versão | ✔ |
| 0.54.0 | Coluna **PVA** da tabela 4.1 inteira (roteiro 2.1) e as três funções sem arquivo real | ✔ — menos NFC-e 65 e CST por NCM, sem caso |
| 0.55.0 | Executável: gerar, rodar o roteiro 2.2 e 2.3 sobre ele | ✔ — falta só arrastar um `.txt` do Explorador (a lógica está na suíte) e a escala acima de 100%, sem monitor para isso aqui: entram no rc.1 |
| 0.56.0 | Validar na entrada: leitura sem descarte, cálculos que recusam número inválido, JSON ilegível preservado; *Limpar NULL* e *Validar campos* absorvidos pelo Diagnóstico | ✔ |
| 0.57.0 | Preparação do rc.1: CST por NCM e inventário fechados no PVA; NFC-e 65 com `pronta=False`; planilha de inventário conferida célula a célula; README revisado de ponta a ponta | ✔ |
| 1.0.0-rc.1 | Congelamento: só correção; licença GPL-3.0; executável e `--autoteste`; do roteiro 2.3, arrastar um `.txt` do Explorador e um monitor acima de 100% | em curso — faltam arrastar um `.txt` do Explorador para o executável e o monitor acima de 100% |
| 1.0.0-rc.2 | Os guias práticos como fonte: ajuda de campo (F1), regras do guia com as condições e tolerâncias do PVA, leiaute conferido contra o descritor, `COBERTURA.md` | ✔ — suíte, arquivos reais, executável gerado e `--autoteste` (com os guias no pacote) |
| **1.0.0** | Release — ver 4.3 | — |
| 1.1.0-dev.1 | Leitura de XMLs em paralelo (processos), com andamento e Cancelar em todas as leituras de pasta | ✔ — suíte, executável e `--autoteste` (item *leitura paralela*) |
| 1.1.0-dev.4 | Regenerar entradas pelos XMLs (C100/C170/C190 com a escrituração aprendida do próprio arquivo), com prévia | ✔ na suíte; **falta** um mês real para `pronta=True` |
| 1.1.0-dev.2 | Integração com ERP: conexões e perfis salvos, mapeamento de tabela e coluna sem SQL; produtos, participantes, XMLs no banco, estoque | ✔ na suíte (SQLite e DBF de verdade, SQL Server local); **falta** um ERP real em Firebird 2.5/5 e em MySQL para virar `pronta=True` |

Função que não fechar a coluna PVA até o rc.1 sai da 1.0.0 com
`pronta=False` e volta numa 1.x. Saem assim: a NFC-e 65 por XML (4.1) e
*Gerar SPED a partir dos XMLs* (4.4).

### 4.3 Publicação da 1.0.0

Toda a história até aqui é sandbox. O que vai para o GitHub na 1.0.0 é um
**começo limpo**: um repositório (ou um histórico) novo, com um único commit
contendo o código da 1.0.0, e um CHANGELOG que começa na 1.0.0. O histórico
0.x — que contém nome e CNPJ de clientes em documentos antigos — não é
publicado. As tags 0.x não são recriadas.

Decidido no rc.1: licença **GPL-3.0** (a do PyQt6, que vai dentro do
executável); o começo limpo é preparado **localmente**, num repositório à
parte, e nada é publicado nem tornado público até você decidir.

---

### 4.4 Em desenvolvimento: gerar o SPED a partir dos XMLs

Gerar o **EFD ICMS/IPI e o EFD Contribuições** de um período só com os XMLs
de entradas e saídas (NF-e 55, NFC-e 65 e **CT-e 57**) e o cadastro da
empresa. Entra com `pronta=False` e só fica pronta pelo critério da seção 3,
contra um mês real com os XMLs **e o SPED entregue** desse mês (o gabarito,
fora do repositório).

Decisões tomadas:

- **Os dois leiautes**, da mesma pasta de XMLs.
- **CT-e nos dois papéis**, documento a documento pelo CNPJ: emitente =
  saída; tomador = entrada.
- **Código do item nas entradas** por uma **memória persistente por
  empresa** (um arquivo por CNPJ na pasta de dados, carregado só quando a
  geração precisa): código do fornecedor → código próprio, e também como a
  empresa escritura aquele produto (CFOP, CST de ICMS e de PIS/COFINS).
  Ela é **aprendida** casando o SPED entregue com os XMLs do mesmo mês
  (chave da nota + número do item); o que ela não souber vai para uma lista
  de revisão, nunca para um palpite gravado.

| Etapa | Entrega | Situação |
|---|---|---|
| 1 | Leitura: NF-e com participantes, protocolo e cancelamento; **CT-e**; eventos; pasta inteira sem descartar nada | ✔ 0.58.0-dev.1 |
| 2 | Memória de itens por empresa e o aprendizado a partir do SPED entregue | ✔ 0.58.0-dev.2 — reproduz 567 de 577 itens do mês real |
| 3 | Gerador do EFD ICMS/IPI (0, C, D, E, H, 9) e comparação com o gabarito | ✔ 0.58.0-dev.3 — mês real: 0 inconsistências no PVA |
| 4 | Gerador do EFD Contribuições (0, A, C, D, F, M, 9) | ✔ 0.58.0-dev.4 — mês real: C175 e bloco M idênticos; PVA igual ao entregue |
| 5 | Tela: pasta, período, prévia, lista de revisão, abrir o resultado | ✔ 0.58.0-dev.5 — decisões gravadas na memória; mês real sem bloqueio |
| 6 | PVA de ensaio com o mês real | pendente |

## 5. Depois da 1.0

Sem data; entram pelo canal dev e seguem a seção 1.

- **Desfazer (undo)** para edições em lote — pede que cada edição seja um
  comando do domínio.
- Persistir entre sessões a ordem e a fixação das abas.
- Refazer a densidade da interface ao mover a janela entre monitores.
- `CST_ACEITOS`/`CST_SUGERIDO` editáveis pela interface (hoje montados para
  comércio/revenda).
- Copiar/colar em bloco no Modo Relatório, compatível com o Excel.
- Aviso ao salvar com C170 fictícios de NFC-e ainda no arquivo.
- Conferência do ICMS das NFC-e usando os C170 fictícios.
- Redução de base por produto no recálculo de ICMS.
- Catálogo de filhos permitidos por registro (criar o primeiro C170 de um
  C100 que só tem C190).
- **Mais regras do PVA**: plano próprio em `ROADMAP_REGRAS_PVA.md` —
  ferramental (inventário, comparador contra o banco do PVA, gabarito
  sintético), depois as regras com SQL legível, as famílias
  parametrizáveis e as classes específicas por impacto.
- ~~**Descritor da versão do arquivo** (`COD_VER`), não só o mais
  recente.~~ **Feito na 1.1.0-dev.16**, com a base de referência: cada
  arquivo é conferido com a estrutura do `COD_VER` que declara (ver
  `ROADMAP_REGRAS_PVA.md`, projeto 1).
- **Obrigatoriedade por perfil** (seção 2 do guia do ICMS/IPI: registro
  obrigatório, facultativo ou vedado para o perfil A, B e C).
- **Inscrição estadual por UF** (dígito verificador de cada estado), que o
  PVA confere no 0000 e no 0150.
- Leiaute 2027 do ICMS/IPI (guia 3.2.4: `IND_BENEFICIO` no E111, C197,
  D197…, `COD_PROD` no C180) quando o PVA trouxer o descritor — e o
  consolidador o extrair para a base de referência.

---

## 6. Limites que a 1.0 assume

Não são funções pela metade: são comportamentos definidos, documentados no
README, que uma versão futura pode ampliar.

- A ordem, a fixação e o fechamento de abas valem durante a sessão.
- Não há desfazer: as rotinas em lote devem rodar com o arquivo salvo.
- Das ~1.300 regras compostas do PVA, o programa reproduz as que o guia
  escreve e o PVA deixa legível (92 validadores na 1.0.0-rc.2, ver
  `COBERTURA.md`); o diagnóstico diz quantas das outras se aplicam ao
  arquivo. O validador oficial continua sendo o juiz.
- Os CST esperados por NCM valem para comércio/revenda.
- Entre *Validar C175* e *Regenerar C175* (NFC-e 65) o arquivo tem C170 em
  documento modelo 65, estrutura inválida: não salve nesse estado.

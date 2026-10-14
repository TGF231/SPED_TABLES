# Roadmap — regras compostas do PVA

Hoje o programa reproduz **todas as validações declarativas** do descritor
(tipo, tamanho, obrigatoriedade, domínio, referência entre registros) e
**92 das ~1.300 regras compostas** (`REGRA_…`), as que o guia escreve por
extenso e o PVA deixa legíveis (`dominio/regras_guia.py`, `COBERTURA.md`).
O resto o diagnóstico só **conta** ("o PVA aplica ainda N regras que este
programa não reproduz").

Este documento é o plano para reproduzir as compostas que importam, sem
quebrar a regra que tornou as 92 confiáveis: **acusação onde o PVA aceita é
regressão, não rigor.**

## 1. Onde estamos (levantamento de 14/10/2026)

Contagem sobre o descritor instalado e os arquivos reais de validação
(4 de ICMS/IPI, 3 de Contribuições). "Aplicáveis" são as regras de
registros que aparecem nesses arquivos.

| | ICMS/IPI | Contribuições |
|---|---:|---:|
| Regras compostas no descritor | 739 | 544 |
| … já reproduzidas | 60 | 32 |
| … aplicáveis aos arquivos reais | 254 | 259 |
| **Aplicáveis que faltam** | **194** | **227** |
| … com consulta SQL legível (`queries.xml`) | 53 | 45 |
| … implementadas em classe Java | 141 | 182 |

Onde as que faltam se concentram:

- **ICMS/IPI:** D100 (28), C100 (21), E310 (21), E210 (14), C170 (14),
  C113 (12), 0000 (10), 0200 (9), E520 (8), E116/E300/H005 (7 cada).
- **Contribuições:** C170 (53), C175 (24), C100 (24), M200/M600 (23 cada),
  M105 (21), M100/M505 (20 cada), M500/M210 (18 cada), M610 (17).

No Contribuições quase metade do que falta é o **bloco M**, que o programa
já **recalcula** (`recalcular_bloco_m`): ali a regra do PVA é a conferência
do mesmo cálculo, e verificação e correção têm de ser o mesmo código.

Cada classe Java é de uma regra só (141 e 182 classes distintas): não há
"uma classe genérica cobre 50 regras". Há, sim, **famílias de nome**
(`RegraQtdLinBloco*`, `RegraObrigatorio*`, `RegraDuplicidade*`,
`RegraDataMinima`, `RegraMaiorIgualZero`…) que em Python podem partilhar
uma implementação parametrizada.

## 2. Princípios (valem para toda fase)

1. **A condição vem do PVA, nunca de palpite.** Fontes, nesta ordem: o SQL
   de `queries.xml`; o guia prático; o pool de constantes da classe
   (mensagem, tolerância, `getErro`/`getAdvertencia`); o nome da classe e
   dos campos que ela lê. Não se copia o SQL nem o código do PVA para o
   repositório: reimplementa-se a condição e cita-se a origem.
2. **O PVA é o oráculo.** Toda regra nova é conferida contra o que o PVA
   acusou no mesmo arquivo (tabela `inconsistencia` do banco `bd…`):
   mesmo registro, mesma linha, mesma mensagem, mesma severidade.
3. **Zero falso positivo nos arquivos reais** antes de ligar. Uma regra que
   acusa onde o PVA aceita não entra.
4. **Regra sem caso não entra.** Se nenhum arquivo real dispara a regra no
   PVA, ela precisa de um **caso sintético** (`tests/fabrica.py`) que o
   PVA confirmou acusar — senão não há como saber se a reimplementação
   está certa.
5. **Gravidade e tolerância iguais às do PVA** (`0,5` nas somas do
   ICMS/IPI, `0,99` e aviso no VL_PIS…).
6. **Verificação e correção são o mesmo cálculo.** Onde já existe função
   que conserta (C190, E110, bloco M, C175), a regra chama o mesmo código
   que a correção usa.

## 3. Fases

### Fase 0 — Ferramental (pré-requisito de tudo)

Sem isto, cada regra custa uma investigação manual.

- **Inventário das regras** (`ferramentas/inventario_regras.py`): para
  cada `REGRA_…` do descritor, os registros em que se aplica, o tipo
  (SQL / classe), a classe Java, a mensagem e a severidade (pool de
  constantes), se já é reproduzida e quantas vezes o PVA a disparou nos
  bancos `bd…` disponíveis. Gera a fila de trabalho, ordenada por
  impacto, e passa a alimentar o `COBERTURA.md`.
- **Mapa validador → `ID_MENSAGEM`.** É o que liga a regra do descritor à
  linha da tabela `inconsistencia`. Sai do atributo de mensagem do SQL e
  do pool de constantes da classe.
- **Comparador diferencial** (`ferramentas/comparar_com_pva.py`): roda o
  diagnóstico num arquivo cujo banco do PVA existe e compara, regra a
  regra, o conjunto `(registro, linha, mensagem)`. Saída: acertos,
  faltas (o PVA acusou e nós não) e excessos (acusamos e o PVA não).
- **Gabarito sintético.** Para cada regra, um arquivo da fábrica que a
  viola, validado **uma vez** na cópia de ensaio do PVA
  (`ferramentas/validar_no_pva.py`); o resultado (`regra`, `registro`,
  `linha`, `mensagem`) fica em `tests/gabarito_regras/*.json` — é dado
  sintético, pode ir para o repositório, e o teste roda sem PVA.

**Aceite:** o inventário reproduz os números da seção 1; o comparador roda
sobre os arquivos reais e mostra, para as 92 já implementadas, zero
excesso.

### Fase 1 — Regras com SQL legível (98 aplicáveis)

A condição está escrita; o trabalho é traduzir e conferir.

1. **ICMS/IPI, documentos:** combinação CST × campos do C170/C190,
   duplicidade do C100/D100, C113 e D100.
2. **ICMS/IPI, apuração:** E210 (ST), E310/E316 (DIFAL/FCP), E116,
   ajustes do C197 refletidos no E110, E520 (IPI).
3. **Contribuições, documentos:** C170, C175 e C100 (CST × campos de PIS e
   COFINS, natureza da receita).
4. **Contribuições, bloco M:** M100/M105, M200/M205/M210, M500/M505,
   M600/M605/M610, M400/M800 — usando o somatório de
   `recalcular_bloco_m` / `conferir_apuracao_m`.

**Aceite por grupo:** comparador sem excesso nos arquivos reais, gabarito
sintético batendo, `COBERTURA.md` regenerado. Meta: ~45% das aplicáveis
reproduzidas no ICMS/IPI e ~30% no Contribuições.

### Fase 2 — Famílias Java parametrizáveis

Regras de mesmo padrão com uma implementação parametrizada em Python:
contagem de linhas por bloco, obrigatoriedade condicional (que alimenta
também `DISPENSAS`), duplicidade de registro, data mínima/máxima, valor
maior ou igual a zero, existência condicionada a modelo/situação.

A condição sai do nome, do pool de constantes e, sobretudo, do gabarito
sintético: varia-se o caso até a acusação do PVA delimitar a regra.

**Aceite:** como na fase 1, mais um caso sintético **que o PVA aceita**
para cada borda (o limite da condição, não só a violação óbvia).

### Fase 3 — Classes específicas, por impacto

O resto, uma a uma, na ordem do inventário (disparos reais primeiro). Regra
cuja condição não se consegue delimitar pelo gabarito fica **declarada como
não reproduzida** — e continua contada no diagnóstico.

### Fase 4 — O que muda a base das regras

Itens já no `ROADMAP.md` que mudam *quais* regras valem para o arquivo:

- descritor da **versão do arquivo** (`COD_VER`), não só o mais recente;
- **obrigatoriedade por perfil** (A, B, C) no ICMS/IPI;
- **inscrição estadual por UF** (dígito verificador de cada estado).

## 4. Como cada regra entra no programa

Uma `Regra` em `dominio/regras_guia.py` (ou verificação própria do
diagnóstico) com:

- `pva=` listando os validadores que reproduz — é o que tira a regra da
  contagem de "não reproduzidas";
- gravidade e módulo que corrige; atalho no mapa `acoes` do diagnóstico
  quando há correção;
- teste com o gabarito sintético e passagem nos arquivos reais
  (`tests/test_reais.py`), sem aumentar acusações onde o PVA aceita;
- comentário com a origem da condição (SQL, guia, classe).

Mudança que altera o `gabarito.json` dos arquivos reais é explicada no
CHANGELOG.

## 5. Riscos

- **Mudança de versão do PVA.** As regras mudam com o validador: o
  inventário registra a versão do `.jar` e acusa regra nova, removida ou
  com SQL alterado ao rodar contra outra instalação.
- **Tempo de PVA.** O gabarito sintético exige a cópia de ensaio e a
  automação; por isso é gerado uma vez e guardado, não a cada teste.
- **Condição só parcialmente observável.** Melhor deixar a regra fora
  (contada) do que acusar errado: o diagnóstico já diz que o validador
  oficial continua sendo o juiz.

## 6. Marcos

| Marco | Entrega | Critério |
|---|---|---|
| R0 | Fase 0 | inventário + comparador + primeiro gabarito sintético; zero excesso nas 92 atuais |
| R1 | Fase 1, ICMS/IPI | SQL legível do ICMS/IPI aplicável reproduzido |
| R2 | Fase 1, Contribuições | idem, com o bloco M conferido pelo mesmo cálculo da correção |
| R3 | Fase 2 | famílias parametrizadas, com bordas aceitas pelo PVA |
| R4 | Fases 3 e 4 | por impacto; sem meta de 100% |

Cada marco sai pelo canal dev, como o resto (`ROADMAP.md`, seção 1).

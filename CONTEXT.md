# SPED Tables — validação

Como o SPED Tables pré-valida um arquivo SPED do mesmo jeito que o PVA da
Receita, e como as regras do PVA chegam ao programa.

## Language

### Regras

**Regra**:
Uma verificação do PVA, identificada pelo nome que o descritor declara
(`REGRA_…`), no registro em que vale.
_Avoid_: validador, verificação, checagem

**Momento**:
O nível em que a regra olha o arquivo: estrutura (na importação), campo,
registro (um de cada vez) ou escrituração (cruzando registros).
_Avoid_: tipo, fase

**Mensagem**:
O texto oficial que o PVA associa a uma violação, identificado por
`MSG_…`.

**Regra confirmada**:
Regra cujo resultado foi conferido contra o PVA de ensaio, numa versão
do PVA.

**Regra antecipada**:
Regra tirada de nota técnica antes de existir PVA que a aplique; acusa
como aviso até ser confirmada.

**Base de referência**:
Tudo o que o programa sabe do SPED fora do próprio código — leiaute de cada
versão, tabelas, regras e mensagens —, montado na compilação e atualizável
sem nova versão do programa; nunca lido do PVA instalado na máquina.
_Avoid_: pacote de regras, tabelas do PVA

**Versão do leiaute**:
A versão que o próprio arquivo declara (`COD_VER` e período); é ela que
decide quais regras valem para ele.

### Resultado

**Ocorrência**:
Uma regra violada num registro de uma linha do arquivo, com a sua
mensagem.
_Avoid_: problema, inconsistência, erro (como substantivo)

**Achado**:
O agrupamento de ocorrências que o diagnóstico mostra, por tipo e pela
função que corrige.

**Causa**:
O porquê de uma ocorrência, dito com os valores do arquivo: o que estava
lá, o que se esperava e de onde vem a diferença.
_Avoid_: motivo, explicação

### Ferramentas

**PVA de ensaio**:
Cópia isolada da instalação do PVA usada como juiz para confirmar regras.
_Avoid_: oráculo, sandbox

**Consolidador**:
O aplicativo que lê o que os PVAs e as notas técnicas publicam, detecta o
que mudou e propõe as mudanças na base de referência.

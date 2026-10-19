# Regras em SQL nosso sobre o arquivo montado como banco

Cada regra da base é uma consulta SQL escrita por nós que devolve os
registros infratores, executada sobre o arquivo montado como banco SQLite
em memória (uma tabela por registro, vínculo com o pai) — o mesmo modelo do
PVA. O programa fornece uma biblioteca fixa de funções (número e data do
SPED, dígitos verificadores, inscrição estadual por UF); regra que dependa
de função mais nova que o programa se abstém e avisa. A causa da ocorrência
também é dado: texto com os valores devolvidos pela consulta.

O SQL vem de um arquivo importável, então roda isolado: banco só de leitura,
`ATTACH`, gravação e `PRAGMA` recusados, sem extensões, com tempo-limite.

## Considered Options

- Só modelos fixos com parâmetros: seguro, mas cada modelo novo exigiria
  versão nova do programa, contra o objetivo de atualizar sem código.
- Trechos de Python na base: descartado, é executar código vindo de arquivo.

# Base de referência compilada, nunca lida do PVA da máquina

Leiaute, tabelas, vigências, regras e mensagens vêm de uma **base de
referência** montada na compilação pelo consolidador e atualizável por
importação, sem nova versão do programa. O PVA instalado na máquina de quem
usa o programa só serve para o *Abrir no PVA*. Motivo: a pessoa pode ter um
PVA antigo, e a pré-validação passaria a discordar do PVA vigente. As regras
valem pela versão do leiaute do próprio arquivo (`COD_VER` e período), como
o PVA faz com um descritor por ato, e não pela versão do PVA instalado.

Nada do PVA é copiado para o repositório nem distribuído: a base guarda
fatos (campos, tipos, tamanhos, códigos de tabela pública), regras escritas
por nós e textos de mensagem nossos. A consulta SQL e o texto das mensagens
do PVA servem ao consolidador só como indício, na máquina de quem compila.

## Considered Options

- Ler o descritor, as tabelas e as consultas do PVA instalado na hora de
  abrir o arquivo (como até a 1.1.0-dev.14): atualização automática, mas
  dependente da versão que a pessoa instalou.
- Traduzir automaticamente o SQL do PVA e embuti-lo: rápido, mas distribui
  derivado direto do código do Serpro.

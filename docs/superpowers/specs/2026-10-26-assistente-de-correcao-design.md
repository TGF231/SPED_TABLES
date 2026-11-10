# Assistente de correção — desenho (fila do assistente, item 2)

Data: 26/10/2026. Vocabulário em `CONTEXT.md`. Depende das **versões do
arquivo** (item 1 da fila, ainda sem desenho): a geração mostra o original ×
final comparando com a primeira importação guardada.

## Contexto

Hoje o programa é uma grade com menus de ferramentas. Para corrigir um arquivo
a pessoa precisa saber a ordem certa — conferir, corrigir, recalcular, gerar,
validar — e escolher, entre opções parecidas, a que executar. Quem não é
especialista se perde.

O assistente vira a porta de entrada: um fluxo linear que o programa percorre
sozinho, a partir do Diagnóstico, como um instalador. As ferramentas continuam
existindo, mas como modo avançado.

## Objetivo

1. Ao abrir um arquivo, o programa leva a pessoa pelas seis etapas em ordem:
   configuração → conferência → correção → recálculo → geração → validação.
2. Cada etapa mostra o achado, a sugestão e a ação; a pessoa aplica, pula ou
   volta.
3. XMLs e respostas ficam guardados por **empresa e período**: outro arquivo do
   mesmo período não importa de novo nem repergunta.
4. A conclusão só existe com a validação no PVA confirmada.

Fora deste desenho: regras novas do PVA (`ROADMAP_REGRAS_PVA.md`), comparação
entre versões do PVA, retorno do PVA e feedback (item 3 da fila), versões do
arquivo (item 1) e desfazer.

## Princípios herdados

- **Lógica fiscal no domínio.** O assistente não calcula nada novo: chama as
  mesmas funções que as ações de menu já chamam (conferência, correção,
  recálculo, geração). A tabela de ações (`interface/acoes.py`) continua sendo
  o único lugar onde uma ação é declarada.
- **Nenhuma tela lê o PVA da máquina**, salvo o *Abrir no PVA*.
- **Janelas soltas** pelo `comum.abrir_janela`. A pergunta que precisa de
  resposta na hora é modal, como manda o `CLAUDE.md`.

## As seis etapas

| # | Etapa | O que a pessoa decide | Reaproveita |
|---|---|---|---|
| 1 | Configuração | Regime declarado da empresa (cumulativo, não-cumulativo ou ambos); se lembra para a empresa | cadastro de empresas |
| 2 | Conferência | Importar os XMLs do período (sim ou não); conferir o arquivo pelo Diagnóstico e pelos XMLs | ler pasta/ERP de XMLs, Diagnóstico, conferência com XMLs |
| 3 | Correção | Quais correções aplicar, com caixa de marcação por registro; alíquotas, se divergirem do regime | sugestões do Diagnóstico, prévias de correção |
| 4 | Recálculo | Nada a escolher: recalcula o que a correção alterou (C190, E110, bloco M) | recalcular C190, E110, bloco M |
| 5 | Geração | Gravar o arquivo corrigido, com o comparativo original × final e o registro do aplicado | gravação atômica; comparativo (depende do item 1) |
| 6 | Validação | Validar no PVA, trazer o resultado de volta e marcar como validado | *Abrir no PVA* |

## Estados de passo

- **Concluído** — círculo verde com check.
- **Parcial** — círculo laranja: a etapa foi executada, mas ficou algo sem
  tratar (achado não corrigido, pergunta sem resposta).
- **Não feito** — círculo cinza.
- **Pulado** — círculo roxo. Exige um motivo registrado, que aparece no
  fechamento.

Não existe "decidir depois". Um passo ou se conclui, ou se pula com motivo, ou
fica parcial ou não feito.

## Navegação

- A linha de passos fica no topo da janela do assistente. Os passos já feitos
  abrem; os seguintes só se o anterior estiver concluído ou pulado.
- **Retomada.** Ao abrir um arquivo cuja chave (abaixo) já tem estado, o
  assistente posiciona a pessoa no primeiro passo sem conclusão depois do
  último concluído. Um botão **Verificar novamente** leva a qualquer passo
  anterior.
- **Retroagir.** Voltar a um passo marca como não feitos **todos os
  posteriores**, porque o resultado deles depende do anterior. Antes de
  desmarcar, o assistente mostra quantos passos serão afetados e pede
  confirmação. Nada é apagado: XMLs e respostas continuam guardados e voltam a
  ser usados quando a etapa é refeita.

## Persistência

- **Chave:** CNPJ da empresa + período (`DT_INI` e `DT_FIN` do 0000). Não
  depende do nome do arquivo nem da data de importação. Trocar o período abre
  outra chave.
- **O que fica guardado:** a origem dos XMLs (pasta ou perfil do ERP), o estado
  de cada passo, as respostas com o arquivo de origem e a data, e o hash e a
  data da última validação.
- **Onde:** pasta de dados, `assistente/<chave>.json`, gravado por
  `dados.gravar_json`. Arquivo ilegível vai para `.corrompido-<data>` com aviso,
  como os demais JSON do usuário (`dados.ler_json_do_usuario`).
- **XMLs.** Guarda-se a origem, não o conteúdo: a leitura passa pelo cache de
  `aplicacao/leitura_xml.py`. Se a pasta sumiu, o passo 2 volta a não feito e
  pergunta a origem de novo, sem perder as respostas.
- **Outro arquivo da mesma chave** reaproveita XMLs e respostas. A pergunta
  sobre alíquotas só volta se o arquivo novo diverge de forma diferente da que
  já foi respondida.

## Perguntas

Regras comuns:

- Pergunta só quando a resposta muda o resultado. Regime único e óbvio não
  pergunta.
- **Sem botão padrão.** Enter não confirma nada. As opções têm o mesmo peso
  visual.
- O texto diz o efeito de cada resposta.
- Cada resposta registra de qual arquivo veio.

**Importar os XMLs do período?** Sim ou Não, sem padrão.
- *Sim:* lê a pasta ou o ERP e segue para a conferência com XMLs.
- *Não:* o passo 2 fica pulado com o motivo "sem XMLs", e a conferência por XML
  não é feita. O fechamento mostra isso.

**Divergência de alíquotas.** Só aparece quando as alíquotas do arquivo não
batem com o regime declarado. O regime define o grupo esperado: cumulativo
0,65 / 3,00; não-cumulativo 1,65 / 7,60. A pergunta mostra os dois valores
lado a lado e o efeito em valores, pela prévia da correção (sem gravar):
- *Manter o arquivo como está:* o passo 3 fica pulado com o motivo "alíquota
  divergente mantida pela pessoa", que aparece no fechamento.
- *Aplicar o regime declarado:* a correção entra no passo 3, com prévia.

Sem divergência, a pergunta não existe. Com regime **ambos**, o passo de
alíquotas fica pulado com o motivo "regime ambos: as duas alíquotas são
válidas", como já fazem as rotinas de alíquota.

**Regime (configuração).** Escolha entre três opções, sem padrão: a pessoa tem
de escolher. A caixa "lembrar para esta empresa" começa desmarcada.

## Validação

- A validação guarda o **hash SHA-256 do arquivo salvo** naquele momento.
- Se o arquivo mudar depois disso (salvamento com conteúdo diferente), a
  marcação de validado é removida sozinha e o assistente avisa.
- O resultado do PVA pode ser anexado ao passo. **Nesta versão a leitura é
  manual:** o programa não lê o banco do PVA; isso fica para o item 3.
- Desfazer a confirmação de validado volta o passo 6 para **parcial**.

## Conclusão

A linha final só diz "conferência concluída" com o passo 6 validado. Antes
disso, lista o que falta: passos não feitos e parciais. Os pulados aparecem
sempre, com o motivo, mesmo com a conclusão dada.

Pular um passo não bloqueia a conclusão; a decisão só fica visível.

## Onde o código fica

- `dominio/assistente.py`: funções puras, sem Qt. Estado dos passos, chave da
  sessão, regime esperado (lendo as constantes que `rotinas` e `empresas` já
  usam, sem copiar valores), divergência de alíquotas, o que um retroagir
  desmarca.
- `infra/assistente_estado.py`: leitura e gravação do JSON por chave.
- `aplicacao/assistente.py`: casos de uso — abrir a sessão, registrar resposta,
  avançar, retroagir, marcar e desmarcar validado.
- `interface/dialogos/assistente.py`: a janela (não modal) com a linha de passos;
  as perguntas são diálogos modais sem botão padrão.
- `interface/acoes.py`: uma ação nova, *Assistente de correção*, com
  `pronta=False` até passar pelo critério. Os menus atuais viram modo avançado.

## Testes (sem PVA, sem dado de cliente)

- **Domínio:** regime e divergência; chave da sessão; retroagir zera os
  posteriores e só eles; regime ambos se abstém; passo pulado exige motivo.
- **Infraestrutura:** ida e volta do JSON; arquivo corrompido vai para
  `.corrompido` com aviso.
- **Aplicação:** retomada no primeiro passo sem conclusão; outro arquivo da
  mesma chave reaproveita XMLs e respostas; arquivo com divergência diferente
  repergunta; alteração do arquivo derruba a validação; desfazer validação
  deixa o passo 6 parcial.
- **Interface:** nenhuma pergunta tem botão padrão, e Enter não aceita; a ação
  do menu dispara a janela (`tests/test_interface.py`).
- **Arquivos reais:** o assistente só orquestra; `tests/test_reais.py` não
  pode mudar de gabarito.

## Aceite (critério da seção 3 do `ROADMAP.md`)

Suíte; fluxo completo num arquivo real **em cópia**; arquivo gerado importado
e validado no PVA sem erro novo (roteiro 2.1 do `TESTES.md`); executável com o
item de autoteste; README com o que a etapa faz e o limite.

## Riscos

- **Fadiga de popup.** Uma pergunta por vez, e as parecidas se agrupam.
- **Resposta reaproveitada no arquivo errado.** A chave é a empresa e o período,
  e a pergunta volta quando a divergência muda.
- **Assistente esconder erro.** A conclusão só existe com validação; pulados
  ficam visíveis.
- **Comparativo original × final depende do item 1.** Sem as versões do arquivo,
  a geração não fica pronta.

## Decisões marcadas como do autor (a conferir)

1. **Persistência entre reinícios.** pedido diz "por sessão"; interpretei como
   chave empresa + período guardada em disco, válida ao reabrir o programa.
2. **"Não" nos XMLs = passo pulado**, não "não feito".
3. **"Manter o arquivo como está" = passo pulado** com motivo.
4. **Regime "ambos" = alíquotas puladas**, com motivo.
5. **Validação por hash**; o resultado do PVA é anexado à mão.
6. **Cores.** A imagem de referência mostra o passo concluído em roxo; este
   desenho segue o texto (verde = concluído, roxo = pulado). Confirmar.

## Em aberto

- A verificação do desenho por um leitor independente (o `builder-check` da
  skill de brainstorming) não foi feita. Pode ser feita antes da aprovação.
- Este texto precisa de aprovação antes de qualquer código (o gate de
  brainstorming).

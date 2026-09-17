# Funcionalidades — SPED Tables

Inventário do que existe hoje (v0.23.1), com **grau de maturidade** e as
**regras de uso** de cada função. O objetivo deste documento é registrar o que
já é confiável, o que ainda precisa de polimento e quais restrições evitam
resultado errado.

> **Antes da primeira release:** o que estiver marcado 🔴 precisa ser validado
> contra arquivo real ou isolado do pacote. Veja o roteiro no fim do
> documento, em *10. Caminho até a primeira release*.

## Legenda de maturidade

| Marca | Significado |
|---|---|
| ✅ **Estável** | Validado contra arquivos reais com números conferidos; pode ser usado em produção com revisão normal. |
| 🟡 **Em amadurecimento** | Funciona e foi testado, mas ainda faltam casos de borda, ajuste de regras ou validação em mais arquivos. Conferir o resultado antes de transmitir. |
| 🔴 **Experimental** | Implementado e testado apenas em cenário construído/limitado. Usar só em cópia do arquivo. |

Em todos os casos vale a regra geral: **trabalhe sempre sobre uma cópia** e
valide o arquivo final no **PVA** antes de transmitir.

---

## 1. Edição e navegação

### 1.1 Abertura e estrutura em abas — ✅ Estável
Cada **bloco** vira uma aba; cada **tipo de registro** vira uma sub-aba, com
relação pai/filho recursiva (mestre-detalhe). Detecta automaticamente o leiaute
(EFD ICMS/IPI ou EFD Contribuições).

### 1.2 Grade estilo planilha — ✅ Estável
Edição célula a célula, com setas/Enter avançando como no Excel. Busca genérica
por bloco. Adicionar/remover linha.

*Regra de uso:* alterar um campo não recalcula nada automaticamente — os
recálculos são explícitos (ver seção 3).

### 1.3 Soma da seleção — ✅ Estável
Selecionando várias células numéricas, a barra de status mostra **Soma, Média e
Contagem**. Ignora texto, códigos com pontos (ex.: `3.1.1`) e inteiros longos
(chaves de acesso).

### 1.4 Reordenar / fixar / fechar abas — 🟡 Em amadurecimento
Arraste para reordenar. Botão direito numa sub-aba: **fixar** (passa a ser
exibida primeiro ao trocar de registro pai), **fechar** (oculta até resetar) e
**resetar abas**.

*Limitação conhecida:* as preferências valem **só durante a sessão** — ao fechar
o programa tudo volta ao padrão. A aba fixada é selecionada, mas não é movida
fisicamente para a primeira posição.

### 1.4A Barra de título própria — ✅ Estável
Substitui a barra do Windows (ligada por padrão), mostrando empresa, período,
leiaute, arquivo e o indicador de alterações não salvas.

A janela **continua nativa**: a interceptação de WM_NCCALCSIZE, WM_NCHITTEST e
WM_GETMINMAXINFO preserva Aero Snap, redimensionamento pelas bordas, duplo
clique para maximizar, menu de sistema e sombra. Coberta por suíte em janela
real: oito bordas, ciclos de maximizar sem transbordar a área de trabalho,
troca de tema e margem sensível ao DPI do monitor.

*Regras de uso:* os **diálogos mantêm a barra do Windows** — a substituição
vale só para a janela principal. Se a preparação falhar (fora do Windows,
ctypes bloqueado), o programa volta sozinho para a barra nativa e avisa na
barra de status. Para forçar a barra do Windows:
`SPED_TABLES_BARRA_NATIVA=1`.

*Limitação conhecida:* o comportamento em monitores com escala acima de 100%
não foi observado diretamente — o código usa as métricas por DPI, mas a
máquina de validação roda a 96 DPI.

### 1.4B Tela inicial — 🟡 Em amadurecimento
Sem arquivo aberto, a janela mostra: **Continuar** (último período arquivado),
área para **arrastar e soltar** o .txt, **matriz empresa × período** dos
últimos 8 meses, **pendências** de cadastro e atalhos.

*Regras de uso:* a matriz mostra o que está **arquivado neste sistema** — um
período pode ter sido transmitido sem nunca ter sido aberto aqui, e a ausência
não é indício de falta de entrega. A matriz só se povoa conforme os arquivos
são abertos.

### 1.4C Fechar arquivo — ✅ Estável
Botão na barra que encerra a escrituração e volta à tela inicial, perguntando
antes o que fazer com as alterações: **Salvar**, **Descartar** ou **Cancelar**.
A mesma pergunta é usada ao sair do programa.

*Regra de uso:* escolher *Salvar* num arquivo que nunca foi gravado abre o
*Salvar como*; fechar esse diálogo cancela também o fechamento, preservando o
trabalho.

### 1.4D Dimensionamento e densidade — 🟡 Em amadurecimento
A janela abre grande e centralizada (até 1600×960, limitada a 88% da área
útil). Em tela menor que isso, abre **maximizada** e a interface passa à
**densidade compacta**, com fonte e espaçamentos menores.

*Limitação conhecida:* a decisão é tomada uma única vez, na abertura. Mudar a
resolução ou mover a janela para um monitor menor durante o uso não refaz a
densidade.

### 1.5 Tema claro e escuro — ✅ Estável
Paleta própria (acento cobre, compartilhada com o Backup Maximus) com botão de
alternância na barra de ferramentas e preferência gravada entre sessões.

*Regra de uso:* ao trocar de tema com um arquivo aberto, as abas são
**remontadas** — as cores gravadas em célula (coluna REG, célula derivada,
divergências) não seguem a folha de estilo. A aba de bloco é preservada; a
seleção de linha, não.

### 1.6 Aba Resumo — 🟡 Em amadurecimento
Dados do 0000, metadados do arquivo, lista de registros por bloco e a **apuração
do período**: no ICMS, consolidação de entradas e saídas por CST/CFOP/alíquota
mais o E110; no Contribuições, consolidação por CST.

*Validação feita:* o ICMS dos C190 de saída bateu com os débitos do E110 e o das
entradas com os créditos, no arquivo real de abril/2026.

---

### 1.7 Menu agrupado por tipo de SPED — ✅ Estável
O botão **Ferramentas** organiza as ações em **EFD ICMS/IPI**, **EFD
Contribuições** e **Gerais**; o submenu inteiro fica desabilitado quando não
corresponde ao leiaute aberto. **Empresas** fica fora do menu, na barra
principal, e funciona sem arquivo aberto.

---

## 2. Modo Relatório

### 2.1 Visão achatada com três fontes — ✅ Estável
Combo de **Fonte**: itens (C170), PIS/COFINS consolidado (C175) e ICMS
consolidado (C190). As duas últimas cobrem documentos sem itens, como a **NFC-e
modelo 65**.

### 2.2 Filtros multi-valor — ✅ Estável
Todos os campos aceitam vários valores separados por `;` (ex.: CFOP `1101;1102`,
CST `000;020;060`, alíquota `1,65;0,65`).

*Regra de uso:* o separador é **ponto e vírgula**, nunca vírgula — a vírgula é o
separador decimal das alíquotas. O filtro de NCM é por **prefixo**.

### 2.3 Edição no relatório — 🟡 Em amadurecimento
As colunas do registro-fonte são editáveis; as derivadas (produto, dados da nota,
valores calculados) ficam em cinza, somente-leitura. Atalhos **Ctrl+D** (preencher
para baixo) e **Ctrl+R** (para a direita).

*Limitação conhecida:* a grade do Modo Tabela já aberta pode continuar exibindo o
valor antigo até ser reaberta — o valor gravado é o do relatório. Não há desfazer:
faça a edição em lote com o arquivo salvo.

---

## 3. Recálculos

### 3.1 Recalcular C190 a partir do C170 — ✅ Estável
Reconstrói o analítico agrupando por **CST + CFOP + alíquota**. Rateia frete,
seguro e outras despesas do C100 por **diferença de acumulados arredondados**
(a soma fecha exatamente com o total). Calcula **VL_RED_BC** nos CST terminados em
20 ou 70 (`VL_OPR − VL_BC_ICMS`).

### 3.1A Recalcular ICMS dos itens — 🟡 Em amadurecimento
Refaz VL_ICMS = base × alíquota nos C170; opcionalmente refaz a base
(VL_ITEM − VL_DESC, com redução nos CST x20/x70) e zera os CST sem débito.
Depois refaz C190 e totais do C100.

*Regras de uso:* o escopo padrão são os itens do Modo Relatório — confira o
contador no diálogo antes de aplicar. O **ICMS-ST não é recalculado**. A
redução de base é um percentual único para todos os itens do escopo: se a
empresa tiver reduções diferentes por produto, rode em lotes filtrados no
relatório.

### 3.2 Recalcular totais do C100 — ✅ Estável
Soma os itens C170 para VL_MERC, desconto, base e valor de ICMS, ICMS-ST, IPI e
PIS/COFINS, e recompõe o **VL_DOC** mantendo frete/seguro/outras despesas.

*Regra de uso:* depois de editar itens, o fluxo completo é **recalcular o C190 e
depois os totais do C100**.

### 3.3 Recalcular bloco M — 🟡 Em amadurecimento
Recalcula a apuração de PIS (M200/M210) e COFINS (M600/M610), respeitando a ordem
do leiaute (M205 **antes** do M210).

*Regra de uso:* rode **por último**, depois de qualquer alteração em alíquotas,
CST ou valores. Confira o resultado no PVA — a apuração tem casos (créditos de
períodos anteriores, ajustes) que o recálculo não cobre.

### 3.4 Trocar alíquotas de PIS/COFINS — 🟡 Em amadurecimento
Escopos: saídas (C175 + C170 de saída), entradas (C170) ou todos os itens.
Filtro opcional "trocar apenas onde a alíquota atual for X".

*Regra de uso:* entradas e saídas têm alíquotas diferentes (crédito × débito) —
use o escopo certo. Prefira o filtro por alíquota atual para corrigir só o que
está errado. Marque "somente tributados" para não afetar CST sem tributação.
Depois, recalcule o bloco M.

### 3.5 Alterar datas de emissão/saída (C100) — 🟡 Em amadurecimento
Filtra por intervalo (sobre DT_E_S ou DT_DOC), tipo de movimento e modelo, e
altera DT_DOC, DT_E_S ou ambas — para data fixa ou deslocando N dias.

*Regra de uso:* o campo "Somente modelos" **aplica apenas aos modelos listados**;
em branco vale para todos. Alterar datas pode mudar o período de apuração —
confira o 0000 (DT_INI/DT_FIN) depois.

---

## 4. Conferência com XMLs

### 4.0 Conferir itens com XMLs, por tributo e movimento — 🟡 Em amadurecimento
Duas ações, uma por tipo de SPED, cada uma conferindo só os campos do seu
leiaute; o **movimento** (entradas / saídas / ambas) é um seletor dentro do
diálogo, que refaz a comparação sem reler a pasta.

*Regra de uso:* a **correlação de CFOP só vale nas entradas** — numa saída
própria o CFOP do XML é o mesmo do escriturado. Nas saídas, portanto, esse
grupo de divergências não aparece, e isso é esperado.

### 4.1 Conferir entradas (NF-e modelo 55) — 🟡 Em amadurecimento
Casa item do XML com o C170 por **modelo + série + número + nItem** e compara
VL_ITEM, VL_DESC, base e valor de **ICMS**, além do **CST de ICMS** e da
correlação de CFOP. Duplo clique vai ao registro.

*Regra de uso:* o VL_ITEM é comparado com **vProd + vOutro + vFrete + vSeg**
do item, porque o C170 não tem campo de despesas acessórias por item (só o C100
tem VL_OUT_DA, VL_FRT e VL_SEG) e elas acabam escrituradas dentro do valor do
produto. Os campos somados ficam em `conferencia.ACESSORIOS_ITEM` — ajuste a
lista se a sua escrituração lançar frete/seguro no C100.

*Limitação conhecida:* o CST é comparado por igualdade — fornecedor do **Simples
Nacional** emite CSOSN e pode gerar divergência legítima. Ainda não tratado.

### 4.2 Conferir C190 com XMLs — 🟡 Em amadurecimento
Agrupa os itens do XML pela **classificação do C170** (casada por nItem), não pelo
CFOP do XML — que é o de saída do fornecedor. Compara VL_OPR, VL_BC_ICMS e
VL_ICMS por grupo.

*Regra de uso:* rode o **recálculo do C190 antes**, para comparar com um analítico
consistente. Documentos sem C170 (NFC-e) não entram: aparecem como "itens sem
C170" no resumo.

### 4.3 Correlações de CFOP — 🟡 Em amadurecimento
Tabela editável de CFOP de saída do fornecedor → CFOPs de entrada válidos,
persistida em `correlacoes_cfop.json`.

*Regra de uso:* a tabela padrão (96 CFOPs, 5→1 / 6→2) é um ponto de partida —
ajuste conforme a operação da empresa.

---

## 5. PIS/COFINS — tabelas da RFB

### 5.1 Verificar CST por NCM — 🟡 Em amadurecimento
Classifica cada item C170 pelo NCM usando as tabelas oficiais (alíquota zero e
monofásicos), respeitando **vigência** (DT_INI/DT_FIM) e exceções (NCM_EX), e
aponta CST incoerentes separando entradas e saídas. Localiza a maior versão das
tabelas na pasta do PVA ou aceita os caminhos manualmente.

*Achado real:* 108 entradas de bebidas monofásicas com CST 50 (crédito indevido;
correto 73/98).

*Regra de uso — importante:* os conjuntos de CST esperados
(`CST_ACEITOS` / `CST_SUGERIDO`, no topo de `tabelas_rfb.py`) foram montados para
**comércio/revenda** e **precisam ser revisados** conforme a atividade. O C175 não
é verificável por NCM (não tem COD_ITEM). A Tabela NCM Vigente (XLSX Siscomex) é
opcional.

---

## 6. NFC-e modelo 65 — validação do C175 por item

### 6.1 Validar C175 com XMLs (C170 fictícios) — 🔴 Experimental
Cria C170 "fictícios" (um por item do XML, com todos os dados: descrição,
quantidade, unidade, ICMS, ICMS-ST, IPI, PIS/COFINS) e mostra as discrepâncias
com o C175 escriturado.

### 6.2 Regenerar C175 dos itens — 🔴 Experimental
Reconsolida o C175 a partir dos itens corrigidos e **remove** os C170 fictícios.

*Regra de uso — crítica:* entre 6.1 e 6.2 o arquivo fica com C170 em documentos
modelo 65, o que **não é estrutura válida** para o EFD Contribuições. **Não salve
nem transmita nesse estado** — sempre execute 6.2 antes de gerar o arquivo final.
Testado até agora com XML sintético casado; falta validar em lote com os XMLs
reais do período.

---

## 7. Inventário — bloco H

### 7.1 Importar inventário de planilha — 🔴 Experimental
Lê XLSX/CSV e gera H001 (com movimento), H005 (data, motivo, valor total) e um
H010 por item. Colunas reconhecidas automaticamente pelo cabeçalho, com
mapeamento manual ajustável. Itens ausentes do **0200** são cadastrados (sem
duplicar os existentes) e unidades novas geram **0190**.

### 7.2 Comparar inventário atual com a planilha — 🔴 Experimental
Confronta o H010 escriturado com a planilha por **código e quantidade**, sem
alterar o arquivo: itens que conferem, quantidade divergente (com a diferença),
só no SPED e só na planilha. Exporta CSV.

*Regras de uso:* use **Conferir com o 0200** e **Comparar com inventário atual**
antes de importar. A importação **substitui** H005/H010 anteriores. Só código,
unidade e quantidade são obrigatórios; o valor total é calculado quando ausente.
Ainda não validado com uma planilha real de inventário — a auto-detecção de
colunas pode precisar de ajuste.

---

## 7A. Configuração por empresa e rotinas por regime

### 7A.0 Painel de empresas — ✅ Estável
Página própria da janela principal (não é diálogo nem aba de bloco), alternada
pelo botão *Empresas* da barra, que funciona como interruptor e ganha moldura
de acento enquanto o painel está aberto. Ao entrar, o cadastro é relido do
disco.

### 7A.1 Cadastro da empresa — 🟡 Em amadurecimento
Por CNPJ (registro 0000): regime federal, regime de PIS/COFINS, atividade,
alíquotas de saída e de crédito, CST de entrada sem crédito. Persistido em
`empresas.json`. Empresa nova vem pré-preenchida pelo arquivo (nome, UF, 0110).

*Regra de uso:* confira o pré-preenchimento antes de gravar — o 0110 pode estar
errado no arquivo, e é justamente uma das coisas a conferir. Quando cadastro e
0110 divergem, o diálogo avisa.

### 7A.2 Rotinas de conferência e correção — 🔴 Experimental
Quatro rotinas: alíquota de saída fora do regime, crédito indevido na entrada
(cumulativo), alíquota de crédito fora do regime (não-cumulativo) e CST
incoerente com o NCM. As três primeiras corrigem sob confirmação; a última só
aponta.

*Regras de uso — importantes:*
- No regime **"ambos"** as rotinas de alíquota se abstêm: as duas alíquotas
  convivem legitimamente no mesmo arquivo.
- Só o **CST 01** tem a alíquota conferida (02 é alíquota diferenciada, 03 é
  por quantidade).
- A correção do crédito indevido grava o CST configurado (**70** por padrão);
  conforme o motivo da vedação, o correto pode ser 73 ou 98 — ajuste no
  cadastro antes de aplicar.
- Validado até agora com arquivo sintético cobrindo os dois regimes; falta
  rodar contra o arquivo real do período.

## 7B. Memória persistente e histórico

### 7B.1 Cópia interna por período — 🟡 Em amadurecimento
Abrir e salvar guardam uma cópia em `arquivos/<CNPJ>/<LEIAUTE>_<AAAAMM>.txt`.
Uma cópia por empresa + leiaute + período, sempre substituída.

*Regras de uso:* o arquivo precisa ter **CNPJ no 0000** para ser arquivado (sem
ele, o aviso vai para a barra de status e nada é guardado). A cópia **não é
versionada**: a anterior se perde a cada atualização — para guardar um estado
antes de uma rotina de correção, salve uma cópia própria fora do sistema.
Depois de validar no PVA, **reabra a versão validada** para a cópia refletir o
arquivo definitivo.

### 7B.2 Histórico por empresa — 🟡 Em amadurecimento
Em *Empresas*, lista os períodos arquivados com leiaute, data, origem e
tamanho. Duplo clique abre a cópia interna; excluir do histórico apaga só a
cópia, nunca o arquivo de origem. Períodos cuja cópia sumiu da pasta aparecem
em vermelho.

## 8. Revisão de erros

### 8.1 Regras implementadas — 🟡 Em amadurecimento
- Número de campos divergente do layout (usa a **moda** do arquivo);
- C190 com CST \*20/\*70 e VL_RED_BC zerado;
- **C170 sem C190 compatível** (item não consolidado no analítico);
- 0200 não utilizados / duplicados.

*Regra de uso:* a revisão **não substitui o PVA** — é uma triagem rápida antes
dele. Novas regras entram na lista `REGRAS` de `revisao.py`.

---

## 9. Pendências e ideias

### 9.1 Bloqueadores da primeira release
- ~~Dados do usuário no executável~~ — resolvido na 0.24.0 (`dados.py`).
- ~~Instalador: pasta em `%APPDATA%` e atalho~~ — resolvido na 0.24.0, na
  primeira execução do executável.
- **Validar os 🔴 contra arquivo real** (ver seção 10) ou deixá-los desligados
  na primeira versão distribuída. **Único bloqueador restante.**

### 9.2 Melhorias desejáveis
- Persistir entre sessões a ordem/fixação de abas e as preferências.
- Tratar **CSOSN** (fornecedor do Simples) na conferência de CST — hoje gera
  divergência legítima.
- Tornar `CST_ACEITOS`/`CST_SUGERIDO` editáveis pela interface, em vez de
  constantes montadas para comércio/revenda.
- Copiar/colar em bloco (Ctrl+C/Ctrl+V) no Modo Relatório, compatível com Excel.
- Aviso ao salvar se ainda houver C170 fictícios (modelo 65) pendentes.
- Conferência do **ICMS** das NFC-e usando os C170 fictícios.
- Desfazer (undo) para edições em lote — hoje a única rede é salvar antes.
- Redução de base por produto no recálculo de ICMS (hoje é um percentual único
  por lote).
- Refazer a densidade ao mover a janela entre monitores.

### 9.3 Atendidas desde a última revisão
- Recalcular ICMS dos itens, encadeando C190 e totais do C100 (0.23.0).
- Fechar arquivo com pergunta de salvamento (0.22.0).
- Diálogos em português (0.22.1).
- Tela inicial no lugar das abas vazias (0.21.0).

---

## 10. Caminho até a primeira release

O critério: **nada 🔴 sai na versão distribuída**. Ou a função é validada
contra arquivo real e sobe para 🟡, ou fica desligada no pacote.

| Etapa | O que fazer | Encerra |
|---|---|---|
| 1 | Corrigir o caminho dos dados (`%APPDATA%` quando empacotado) | 9.1 |
| 2 | Validar 7A.2 (rotinas por regime) no SPED real de um período | 🔴 → 🟡 |
| 3 | Validar 6.1/6.2 (NFC-e 65) com os XMLs reais do período | 🔴 → 🟡 |
| 4 | Validar 7.1/7.2 (inventário) com uma planilha real | 🔴 → 🟡 |
| 5 | Rodar o `TESTES.md` inteiro num arquivo real de cada leiaute | — |
| 6 | Validar no **PVA** os arquivos gerados em cada fluxo | — |
| 7 | Gerar o executável e repetir o smoke test sobre ele | — |
| 8 | Instalador (pasta em `%APPDATA%` + atalho) | 9.1 |
| 9 | Marcar a versão `1.0.0` e publicar a release | — |

Etapas 2 a 4 são as que dependem de dados que não estão no repositório; as
demais podem ser feitas a qualquer momento.

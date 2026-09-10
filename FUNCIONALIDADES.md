# Funcionalidades — SPED Tables

Inventário do que existe hoje (v0.15.1), com **grau de maturidade** e as
**regras de uso** de cada função. A maioria está em amadurecimento: o objetivo
deste documento é registrar o que já é confiável, o que ainda precisa de
polimento e quais restrições evitam resultado errado.

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

### 1.5 Aba Resumo — 🟡 Em amadurecimento
Dados do 0000, metadados do arquivo, lista de registros por bloco e a **apuração
do período**: no ICMS, consolidação de entradas e saídas por CST/CFOP/alíquota
mais o E110; no Contribuições, consolidação por CST.

*Validação feita:* o ICMS dos C190 de saída bateu com os débitos do E110 e o das
entradas com os créditos, no arquivo real de abril/2026.

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

### 4.1 Conferir entradas (NF-e modelo 55) — 🟡 Em amadurecimento
Casa item do XML com o C170 por **modelo + série + número + nItem** e compara
VL_ITEM, VL_DESC, base e valor de **ICMS**, além do **CST de ICMS** e da
correlação de CFOP. Duplo clique vai ao registro.

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

- Persistir entre sessões a ordem/fixação de abas e as preferências.
- Tratar **CSOSN** (fornecedor do Simples) na conferência de CST.
- Tornar `CST_ACEITOS`/`CST_SUGERIDO` editáveis pela interface.
- Copiar/colar em bloco (Ctrl+C/Ctrl+V) no Modo Relatório, compatível com Excel.
- Aviso ao salvar se ainda houver C170 fictícios (modelo 65) pendentes.
- Conferência do **ICMS** das NFC-e usando os C170 fictícios.
- Desfazer (undo) para edições em lote.
- Encadear "recalcular tudo do documento" (C190 + totais do C100).

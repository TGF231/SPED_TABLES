# Funcionalidades — SPED Tables

Inventário do que existe hoje (v0.39.0), com **grau de maturidade** e as
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

### 1.2A Cadastro por trás do código — 🟡 Em amadurecimento
A grade mostra `COD_ITEM 25121` ou `COD_PART 10` e ninguém sabe do que se
trata. Ao selecionar a linha, o topo resolve o código no cadastro do bloco 0:
**produto** pelo 0200 (grades com `COD_ITEM`, ex.: C170) e **participante**
pelo 0150 (grades com `COD_PART`, ex.: C100 e D100). A dica da célula
`COD_PART` traz a ficha inteira — nome, CNPJ/CPF pontuado, IE, endereço,
bairro e município.

Participante ausente do 0150 fica em cor de aviso na própria célula: é recusa
no PVA e aparecer ali evita a viagem ao validador.

*Regra de uso:* em grade que tenha os dois campos, o **produto tem
preferência** — é o que muda de linha para linha. No modelo:
`participante()`, `formatar_doc_participante()` e o cache invalidado ao editar
um 0150, como já acontecia com o 0200.

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

### 4.0 Conferir itens com XMLs, por tributo e movimento — ✅ Estável
Duas ações, uma por tipo de SPED, cada uma conferindo só os campos do seu
leiaute; o **movimento** (entradas / saídas / ambas) é um seletor dentro do
diálogo, que refaz a comparação sem reler a pasta.

*Regra de uso:* a **correlação de CFOP só vale nas entradas** — numa saída
própria o CFOP do XML é o mesmo do escriturado. Nas saídas, portanto, esse
grupo de divergências não aparece, e isso é esperado.

### 4.1 Conferir entradas (NF-e modelo 55) — ✅ Estável
Casa item do XML com o C170 por **modelo + série + número + nItem** e compara
VL_ITEM, VL_DESC, base e valor de **ICMS**, além do **CST de ICMS** e da
correlação de CFOP. Duplo clique vai ao registro.

*Regra de uso:* o VL_ITEM é comparado com **vProd + vOutro + vFrete + vSeg**
do item, porque o C170 não tem campo de despesas acessórias por item (só o C100
tem VL_OUT_DA, VL_FRT e VL_SEG) e elas acabam escrituradas dentro do valor do
produto. Os campos somados ficam em `conferencia.ACESSORIOS_ITEM` — ajuste a
lista se a sua escrituração lançar frete/seguro no C100.

*Validado em arquivo real (08/2026):* 81 NF-e de entrada, 577 itens
conferidos, 79 documentos casados. Depois das correções da 0.25.0, as
divergências caíram de 404 para 149 — nenhuma delas falso positivo conhecido.
A conferência **não altera o arquivo**, o que mantém o risco baixo.

*Tratado desde a 0.25.0:* fornecedor do **Simples Nacional** emite CSOSN
(origem + 3 dígitos) e o comprador escritura CST normal (origem + 2). Esses
itens não são comparados e aparecem no resumo como `cst_csosn_ignorados`.

*Despesas acessórias:* o critério do VL_ITEM é **auto-detectado por
documento** — se o C100 traz VL_OUT_DA/VL_FRT/VL_SEG batendo com a soma dos
itens do XML, elas não são somadas ao item; senão, são.

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

### 6.1 Validar C175 com XMLs (C170 fictícios) — 🟡 Em amadurecimento
Cria C170 "fictícios" (um por item do XML, com todos os dados: descrição,
quantidade, unidade, ICMS, ICMS-ST, IPI, PIS/COFINS) e mostra as discrepâncias
com o C175 escriturado.

### 6.2 Regenerar C175 dos itens — 🟡 Em amadurecimento
Reconsolida o C175 a partir dos itens corrigidos e **remove** os C170 fictícios.

*Regra de uso — crítica:* entre 6.1 e 6.2 o arquivo fica com C170 em documentos
modelo 65, o que **não é estrutura válida** para o EFD Contribuições. **Não salve
nem transmita nesse estado** — sempre execute 6.2 antes de gerar o arquivo final.

*Regra de uso — igualmente crítica:* **o XML nem sempre é a verdade.** No
arquivo real de 08/2026, 28 das 205 NFC-e foram emitidas pelo PDV com alíquota
de não-cumulativo enquanto a empresa é cumulativa: a escrituração estava certa
e o XML errado. Regenerar sem revisar aumentaria o tributo declarado em
R$ 1.117,31. Desde a 0.25.0 o diálogo mostra PIS, COFINS e valor da operação
antes e depois — **leia a diferença antes de confirmar**.

*Validado em arquivo real (08/2026):* 205 documentos modelo 65, 520 C170
fictícios criados e removidos, contagem de registros idêntica no fim
(1615 → 1615), nenhum C170 sobrando em documento modelo 65, e o relatório de
discrepâncias apontou exatamente as 56 notas com problema.

---

## 7. Inventário — bloco H

### 7.1 Importar inventário de planilha — 🟡 Em amadurecimento
Lê XLSX/CSV e gera H001 (com movimento), H005 (data, motivo, valor total),
um H010 por item e o H990 de encerramento. Colunas reconhecidas
automaticamente pelo cabeçalho, com mapeamento manual ajustável. Itens
ausentes do **0200** são cadastrados (sem duplicar os existentes) e unidades
novas geram **0190**.

**Atualizar o cadastro existente.** Marcando a opção, a planilha também
corrige o 0200 dos itens que já existem — para quando é o arquivo que está
errado. A correção **não é cega**: `previa_atualizacao_0200()` mostra antes,
campo a campo, quantos valores mudariam e exemplos, e a escolha é por campo.

Isso não é excesso de zelo. No arquivo real, a mesma planilha que corrigia
**447 NCM truncados, 471 CEST e 36 códigos de barras** plantaria `TIPO_ITEM`
**inválido** (`N`, fora da tabela 00–10/99) em 1.273 itens que estavam
certos — e o PVA recusaria. Campo cujo valor novo está fora da tabela oficial
nasce **desmarcado**, com o aviso à vista; alíquota que iria a zero segue
marcada, mas o diálogo diz quantos itens seriam zerados.

Duas regras impedem estrago silencioso: coluna **não mapeada** e célula
**vazia** nunca apagam o que já está no cadastro, e a alíquota é comparada
como número — `18,00` e `18` não contam como mudança (sem isso, 7.615
"alterações" apareciam onde havia 832 reais).

### 7.2 Comparar inventário atual com a planilha — 🟡 Em amadurecimento
Confronta o H010 escriturado com a planilha por **código e quantidade**, sem
alterar o arquivo: itens que conferem, quantidade divergente (com a diferença),
só no SPED e só na planilha. Exporta CSV.

*Regras de uso:* use **Conferir com o 0200** e **Comparar com inventário atual**
antes de importar. A importação **substitui** H005/H010 anteriores. Só código,
unidade e quantidade são obrigatórios; o valor total é calculado quando ausente.

*Validado em planilha real (08/2026, segunda empresa):* 11.585 itens em 22
colunas, todas reconhecidas sem ajuste manual, sobre um SPED de 28.475
registros **sem bloco H nenhum**. Gerou H001/H005/H010/H990 com 11.588 linhas
de bloco, R$ 958.285,74 de inventário, largura correta em todos os registros,
bloco contíguo entre `G990` e `K001` e ida-e-volta (salvar → recarregar) sem
perda. A comparação seguinte acusou **11.585 de 11.585 conferindo**.

Quatro defeitos saíram dessa validação e foram corrigidos na 0.26.0 — bloco sem
`H990`, `VL_INV` um centavo fora da soma, `VL_ITEM_IR` com ponto decimal e
NCM/CEST sem o zero à esquerda. Os três primeiros fariam o PVA recusar o
arquivo.

*O que a planilha revelou do arquivo do cliente:* **442 itens do 0200 com NCM
de 7 dígitos** (zero à esquerda perdido na origem) e apenas **4** com NCM
realmente divergente — a conferência separa os dois casos. Há ainda 85 itens
com quantidade zero e 1.656 sem valor, escriturados como vieram e apenas
sinalizados.

*Ainda não exercitado em arquivo real:* o cadastro automático de itens no 0200
não rodou, porque os 11.585 itens já existiam. Foi validado por controle —
descadastrando 598 itens de propósito, todos voltaram com NCM de 8 dígitos,
CEST de 7 e as 8 unidades do 0190 recriadas. Código de barras que não fecha o
dígito verificador é mantido como veio: o PVA vai apontá-lo, e a origem é o
cadastro do cliente.

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

### 7A.2 Rotinas de conferência e correção — 🟡 Em amadurecimento
Cinco rotinas: alíquota de saída fora do regime, crédito indevido na entrada
(cumulativo), alíquota de crédito fora do regime (não-cumulativo), **valor
lançado em CST sem direito a crédito** e CST incoerente com o NCM. **Todas as
cinco corrigem sob confirmação** desde a 0.35.0 — a de CST por NCM era a única
que só apontava.

*Correção do CST por NCM (0.35.0):* age apenas nas **entradas** que estão
tomando crédito (CST 50-56 / 60-66) num NCM monofásico ou de alíquota zero —
troca o CST pelo sugerido e zera base, alíquota e valor. Item já num CST sem
crédito não é tocado: 70, 73 e 98 se distinguem pelo **motivo** da vedação, e
trocar um pelo outro sem saber o motivo é palpite. **Saídas ficam de fora**,
porque lá o CST depende de revenda ou produção própria e alíquota diferenciada
(02/03) é legítima. O mesmo botão existe no diálogo *Verificar CST por NCM*,
chamando a mesma função — uma regra fiscal, uma implementação.

*Validado por controle (CASA DO ESPETO, 08/2026):* o arquivo real já estava
correto (entradas de bebida com CST 73), então o erro foi **plantado** — 12
entradas de NCM 2202/21069090 com CST 50, base 100,00 e alíquotas de
não-cumulativo. A correção devolveu 24 lançamentos ajustados (PIS e COFINS),
CST 73, base e valor zerados, alíquota em branco, R$ 111,00 de crédito
indevido retirado; a reverificação voltou zero, a segunda passada não mexeu em
nada e as saídas ficaram intactas.

*Regras de uso — importantes:*
- No regime **"ambos"** as rotinas de alíquota se abstêm: as duas alíquotas
  convivem legitimamente no mesmo arquivo.
- Só o **CST 01** tem a alíquota conferida (02 é alíquota diferenciada, 03 é
  por quantidade).
- A correção do crédito indevido grava o CST configurado (**70** por padrão);
  conforme o motivo da vedação, o correto pode ser 73 ou 98 — ajuste no
  cadastro antes de aplicar.
*Validado em arquivo real (08/2026):* as três rotinas de regime devolveram
zero no arquivo — e um **controle negativo** (declarar a empresa como
não-cumulativa) fez a de alíquota de saída apontar 412 ocorrências nos 232
C175, provando que o zero era acerto e não cegueira. A rotina nova encontrou
512 ocorrências reais (256 itens × 2 tributos) em 33 documentos.

- Falta exercitar as **correções** em arquivo real: até agora só as
  verificações rodaram sobre os dados do cliente.

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
- 0200 não utilizados / duplicados (usa a mesma varredura da 8.3);
- **TIPO_ITEM fora da tabela do 0200** (só 00 a 10 e 99) — no arquivo real,
  10.312 itens com `N`, herdados da exportação do ERP;
- **COD_GEN incoerente com o NCM** — o gênero são os dois primeiros dígitos do
  NCM, então dá para conferir e preencher sozinho (8.6).

*Regra de uso:* a revisão **não substitui o PVA** — é uma triagem rápida antes
dele. Novas regras entram na lista `REGRAS` de `revisao.py`.

O relatório oferece as **correções em massa** cabíveis ao que encontrou
(recalcular C190, preencher COD_GEN, itens sem referência): ver o erro e ter o
conserto no mesmo lugar.

### 8.2 Recalcular C190 com redução zerada (em massa) — 🟡 Em amadurecimento
`documentos_c190_com_reducao_zerada()` acha os C100 cujo analítico tem CST
x20/x70 com `VL_RED_BC` em branco; `consolidar_c190_em_massa()` refaz só
esses. O recálculo por documento já existia (7.x); o que faltava era o lote.

*Regra do CST x70:* o ICMS foi cobrado por ST e não há base própria. Quando o
item tem base de **PIS/COFINS**, ela substitui a base de ICMS apenas para
achar a diferença — o `VL_BC_ICMS` do C190 continua zero. Sem nenhuma das
duas, a redução fica zerada e o caso vai para conferência manual.

*Validado em arquivo real (08/2026):* 66 C190 com redução zerada em 53
documentos, todos CST x70. Depois do lote: **29 grupos** corrigidos pela base
de PIS/COFINS, sobrando 37 (itens com CST_PIS 73, sem base nenhuma).
`VL_OPR`, `VL_BC_ICMS` e `VL_ICMS` do arquivo **idênticos** antes e depois
(919.795,97 / 202.854,14 / 32.240,62) — o recálculo repôs a redução sem mexer
em valor —, contagem de C190 igual (6.678) e E110 batendo com a soma das
saídas (11.878,73).

*Idempotente:* a segunda passada devolve `corrigidos: 0`.

### 8.3 Itens do 0200 sem referência — 🟡 Em amadurecimento
Aplica a regra do Guia Prático: *"Não informar item, se não referenciado em
pelo menos um dos demais blocos"*. `referencias_de_itens()` varre o arquivo
inteiro, `itens_0200_nao_utilizados()` lista sem alterar e
`remover_itens_0200()` apaga o que foi exibido, com a subárvore.

*Duas estratégias de varredura:* registro com leiaute mapeado é lido pelo nome
do campo `COD_ITEM`; registro **sem leiaute** (o bloco K inteiro, que usa
COD_ITEM em quase todos os registros e não está em `sped_layouts.py`) é
varrido **por valor**. O modo conservador erra para mais — preserva item a
mais, nunca apaga item em uso —, e o painel diz quais registros caíram nele.

*Validado em arquivo real (08/2026):* 12.479 itens, 10.849 referenciados,
**1.630 órfãos** — os mesmos apontados pela regra 8.1, conferidos por uid.
Depois de remover: 0200 com 10.849, nenhum referenciado perdido (verificação
explícita por conjunto), larguras íntegras e o inventário fechando em
R$ 958.285,74. Num **controle**, um `K200` sem leiaute citando um órfão fez o
item sair da lista — a proteção funciona.

*Efeito colateral bem-vindo:* os 1.630 órfãos eram exatamente os 1.630 com
`TIPO_ITEM` inválido herdado do ERP. Removê-los zerou aquele achado também.

### 8.4 Preencher conta contábil (COD_CTA) — 🟡 Em amadurecimento
O `COD_CTA` é obrigatório nos perfis **A** e **B**, e o erro clássico é o
**H010**: o cadastro do produto não tem conta de estoque vinculada no ERP.
Preenche um tipo de registro por vez — cada um leva a sua conta —, sem tocar
no que já está preenchido, e cria o **0500** (plano de contas) junto, na
posição do leiaute.

*Validado em arquivo real (08/2026):* perfil B, 9.929 H010 e 2.486 C170 sem
conta. Preenchendo o H010 com `1.1.03.01`: 9.929 registros, 0500 criado com
os 7 campos do EFD ICMS/IPI, entre o último `0460` e o `0990`, contagem do
bloco 0 batendo (13.543) e idempotente na segunda passada.

*Leiaute conferido na fonte:* o 0500 tem **7 campos** na EFD ICMS/IPI e **9**
na EFD Contribuições (ganha `COD_CTA_REF` e `CNPJ_EST`) — o do ICMS faltava
em `sped_layouts.py` e foi acrescentado.

### 8.5 Validar campos pelo leiaute — 🟡 Em amadurecimento
**Desde a 0.38.0 a fonte preferida são as tabelas dos próprios PVAs**
(`tabelas_pva.py`), e não a lista embutida: os códigos válidos acompanham a
atualização do validador oficial sem mexer no código. Sem PVA instalado, os
domínios embutidos continuam valendo e o diálogo avisa de onde veio cada
verificação.

*Cobertura medida nas tabelas instaladas (268 arquivos):* **16 domínios** no
EFD ICMS/IPI (CFOP, CST de ICMS/IPI/PIS/COFINS, COD_MOD, COD_SIT, IND_EMIT,
COD_MUN, COD_PAIS, CEST, COD_GEN, TP_CT-e, COD_AJ_APUR, COD_REC,
COD_INF_ADIC) e **12** no EFD Contribuições (inclui NAT_BC_CRED, COD_CRED,
COD_AJ, IND_NAT_PROC). Carga em 0,03 s; varredura de 28.475 registros em
0,15 s.

*Quatro cuidados, todos aprendidos em arquivo real:*
- **vigência** por código — a tabela única de CST do ICMS foi revogada em
  2012, e validar contra ela reprovaria o arquivo inteiro;
- **CST do ICMS é composto**: origem (`SIT_TRIB_ICMS_A`) × situação
  (`SIT_TRIB_ICMS_B`);
- **tabelas por UF** para os códigos de ajuste (E111, E116), com a UF vinda
  do 0000;
- **zero à esquerda sobrando não é erro**: `COD_PAIS 01058` é o `1058` da
  tabela, e tratá-lo como erro gerava **141 falsos positivos**. Código só de
  zeros, ao contrário, é campo vazio disfarçado (`COD_MUN 0000000`) e vira
  sugestão de esvaziar.

Tabela de **domínios por nome de campo** (`validacao.py`), aplicada a qualquer
registro que possua o campo: NCM, CEST, COD_GEN, TIPO_ITEM, CST de ICMS/PIS/
COFINS, CFOP, COD_SIT, indicadores, datas e campos numéricos (por prefixo
`VL_`, `ALIQ_`, `QTD`).

A saída separa **conserto mecânico** (zero à esquerda perdido, texto de vazio —
normalizados em lote) de **decisão fiscal** (lista com duplo-clique que navega
até o registro). Sugestão só existe quando falta **exatamente um** dígito.

*Validado em arquivo real (08/2026):* 28.475 registros varridos em 0,11 s,
24.751 campos fora do domínio — 14.253 corrigidos de uma vez (COD_GEN 10.312,
CEST 3.499, COD_NCM 442) e 10.498 restantes com diagnóstico nominal. Depois da
normalização: NCM todos com 8 dígitos, CEST com 7, nenhum `NULL` e larguras
preservadas.

*Falso positivo que a validação evita:* `CST_ICMS` com `101`/`201` não é lixo —
é o **CSOSN do fornecedor do Simples sem o dígito de origem**, e o diagnóstico
diz isso. Nos dois arquivos da CASA DO ESPETO a regra achou 8 ocorrências que
nenhuma outra função via, entre elas um `CST_ICMS` truncado em `0`.

*Limite conhecido:* obrigatoriedade de campo não é verificada — depende do
registro e da operação, e cobrá-la pelo nome geraria falso positivo em massa.

### 8.6 Preencher COD_GEN pelo NCM — 🟡 Em amadurecimento
O gênero do item são os **dois primeiros dígitos do NCM** (Tabela 4.2.1), logo
é derivável do próprio arquivo. `divergencias_cod_gen()` lista sem alterar;
`preencher_cod_gen()` grava o que foi exibido. Item sem NCM de 8 dígitos fica
de fora — não há capítulo de onde tirar o gênero.

*Por que não confiar na planilha:* `LEFT(NCM;2)` sobre célula numérica devolve
`40` para o NCM `04012010`. Na planilha real seriam **593 itens** com gênero
errado — e todos com código existente, então o erro não apareceria como
inválido, só como errado. Derivar do arquivo, com o NCM normalizado antes do
corte, é imune.

*Validado em arquivo real (08/2026):* 12.478 itens preenchidos, nenhuma
divergência restante, larguras preservadas.

### 8.7 Limpar campos com NULL — 🟡 Em amadurecimento
Encontra e esvazia os campos em que o sistema de origem gravou o "vazio" por
extenso — `NULL`, `None`, `#N/A`, `#REF!` e afins. É erro de exportação: o ERP
despeja o `NULL` do banco no arquivo e o PVA recusa cada ocorrência com
*"Conteúdo de Campo inválido"*.

Detecção e correção são separadas, como nas demais rotinas: `campos_nulos()`
devolve a lista sem tocar no arquivo, o diálogo mostra a contagem por
registro/campo, e só depois da confirmação `limpar_campos_nulos()` esvazia
exatamente o que foi exibido.

*Validado em arquivo real (08/2026):* **13.341 campos** em 10.312 registros —
`COD_GEN` (10.312) e `CEST` (3.029) do 0200, ou **82,6% dos itens**
cadastrados. Depois da limpeza, nenhuma ocorrência restante, largura dos
registros preservada e o CEST legítimo intacto.

*Por que `-` e `N/A` ficam de fora:* ambos podem ser descrição legítima de
produto. A lista `VALORES_NULOS` só tem textos que nenhum campo de SPED
aceitaria como conteúdo.

A mesma proteção vale na leitura de planilha: `_texto_planilha()` trata esses
textos como célula vazia, para que o `NULL` da origem não entre no arquivo pela
importação de inventário.

---

## 9. Pendências e ideias

### 9.1 Bloqueadores da primeira release
- ~~Dados do usuário no executável~~ — resolvido na 0.24.0 (`dados.py`).
- ~~Instalador: pasta em `%APPDATA%` e atalho~~ — resolvido na 0.24.0, na
  primeira execução do executável.
- ~~Validar o inventário (7.1/7.2) contra planilha real~~ — resolvido na
  0.26.0, com a planilha de 11.585 itens da segunda empresa.
- **Nenhum 🔴 restante.** O que falta para a release não é mais funcionalidade
  e sim prova: exercitar as **correções** em arquivo real (etapa 5), validar no
  **PVA** os arquivos gerados (etapa 7) e repetir o smoke test sobre o
  executável (etapa 8).

### 9.2 Melhorias desejáveis
- Oferecer a limpeza de campos com `NULL` (8.2) automaticamente ao abrir um
  arquivo que os contenha, em vez de depender do usuário lembrar do menu.
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

| Etapa | O que fazer | Situação |
|---|---|---|
| 1 | Caminho dos dados (`%APPDATA%` quando empacotado) | ✔ 0.24.0 |
| 2 | Validar 7A.2 (rotinas por regime) no SPED real | ✔ 0.25.0 |
| 3 | Validar 6.1/6.2 (NFC-e 65) com os XMLs reais | ✔ 0.25.0 |
| 4 | Validar 7.1/7.2 (inventário) com planilha real | ✔ 0.26.0 |
| 5 | Exercitar as **correções** (não só as verificações) em arquivo real | **pendente** |
| 6 | Atualizar o `TESTES.md`, hoje parado na v0.15.1 | **pendente** |
| 7 | Validar no **PVA** os arquivos gerados em cada fluxo | **pendente** |
| 8 | Gerar o executável e repetir o smoke test sobre ele | **pendente** |
| 9 | Marcar a versão `1.0.0` e publicar a release | — |

A etapa 5 merece destaque: até aqui o arquivo real passou pelas **verificações**,
que não alteram nada. As correções (trocar alíquota, zerar crédito, regenerar
C175, recalcular ICMS) só foram exercitadas em arquivo sintético — e são elas
que gravam.

Etapas 2 a 4 são as que dependem de dados que não estão no repositório; as
demais podem ser feitas a qualquer momento.

# Roteiro de testes — SPED Tables

Checklist de validação manual e automatizada. A ideia é rodar o **smoke test**
antes de qualquer entrega e a seção completa da área que foi mexida.

Marque o resultado: ✅ passou · ❌ falhou · ⏭️ não se aplica.

## Preparação

- Trabalhe sempre com **cópias** dos arquivos SPED reais.
- Tenha à mão, num diretório fora do repositório:
  - um **EFD ICMS/IPI** com C170, C190 e E110;
  - um **EFD Contribuições** com C170 (entradas) e C175 (NFC-e mod. 65);
  - uma pasta de **XMLs** do mesmo período (modelos 55 e 65);
  - as **tabelas da RFB** (pasta de recursos do PVA);
  - uma **planilha de inventário** (XLSX).
- Referência de valores conferidos (arquivo de abril/2026): C190 saída
  **11.921,50** = débitos do E110; C190 entrada **4.202,70** = créditos.

---

## 0. Verificações automáticas (rodar sempre)

```bash
# 0.1 tudo compila
python -m py_compile *.py

# 0.2 o .ui continua válido
python -c "import xml.dom.minidom as m; m.parse('sped_editor.ui')"

# 0.3 nenhum método perdeu a assinatura (armadilha recorrente — ver CLAUDE.md)
python -c "
import ast
for f in ['sped_model.py','sped_editor.py','conferencia.py','revisao.py','xml_fiscal.py','tabelas_rfb.py']:
    t=ast.parse(open(f,encoding='utf-8').read())
    p=[(n.name,s.lineno) for n in ast.walk(t) if isinstance(n,ast.FunctionDef)
       for i,s in enumerate(n.body[:-1]) if isinstance(s,ast.Return)]
    print(f, p or 'ok')
"

# 0.4 todos os módulos importam
python -c "import sped_model, sped_layouts, xml_fiscal, conferencia, revisao, tabelas_rfb; print('ok')"

# 0.5 métodos-chave existem (pega AttributeError antes do usuário)
python -c "
from sped_model import SpedDocument as D
faltam=[m for m in ['consolidar_c190','recalcular_totais_c100','consolidar_c175_de_itens',
 '_registros_aliq_escopo','trocar_aliquotas_pis_cofins','alterar_datas_c100','recalcular_bloco_m',
 'importar_inventario_h010','comparar_inventario_h010','gerar_c170_ficticios_65',
 'regenerar_c175_de_c170_65','itens_relatorio','itens_relatorio_c175','itens_relatorio_c190',
 'resumo_c190','apuracao_e110','consolidacao_cst_pis_cofins'] if not hasattr(D,m)]
print('faltando:', faltam or 'nenhum')
"
```

- [ ] 0.1 a 0.5 sem erros

---

## 1. Smoke test (5 minutos, antes de qualquer entrega)

- [ ] 1.1 Abrir um **EFD ICMS/IPI**: abas de bloco aparecem, Resumo mostra razão
      social, CNPJ e período corretos
- [ ] 1.2 Abrir um **EFD Contribuições**: idem, e as ferramentas de PIS/COFINS
      ficam habilitadas (as de ICMS, desabilitadas)
- [ ] 1.3 Navegar C100 → sub-abas de detalhe (C170/C190) carregam
- [ ] 1.4 Editar uma célula, salvar como novo arquivo, reabrir: valor persistiu
- [ ] 1.5 **Salvar sem alterar nada** e comparar com o original: o arquivo deve
      sair equivalente (só os totalizadores recalculados)
- [ ] 1.6 Modo Relatório: gera linhas nas três fontes
- [ ] 1.7 Abrir o menu Ferramentas: nenhuma ação dispara erro ao ser clicada

---

## 2. Edição e navegação

- [ ] 2.1 Setas/Enter avançam a edição como no Excel
- [ ] 2.2 Adicionar linha: registro entra na posição certa e o bloco 9 é recontado
- [ ] 2.3 Remover linha: registro e filhos somem; contagens batem
- [ ] 2.4 Busca no bloco localiza e navega
- [ ] 2.5 Soma da seleção: selecionar valores mostra Soma/Média/Contagem
- [ ] 2.6 Soma **ignora** chave de acesso (44 dígitos) e códigos como `3.1.1`
- [ ] 2.7 Arrastar aba: **o conteúdo acompanha** o rótulo (regressão da v0.10.0)
- [ ] 2.8 Botão direito na sub-aba: fixar / fechar / resetar funcionam
- [ ] 2.9 Com aba fixada, trocar de C100 abre nela sempre que existir
- [ ] 2.10 Sem aba fixada, o detalhe abre sempre na **primeira** aba da ordem atual

---

## 3. Modo Relatório

- [ ] 3.1 Trocar a fonte habilita só os filtros aplicáveis
- [ ] 3.2 Filtro simples (ex.: CFOP `1101`) reduz corretamente
- [ ] 3.3 Multi-valor: `1101;1102` retorna a **união** dos dois filtros isolados
- [ ] 3.4 Alíquota multi-valor `1,65;0,65` funciona (vírgula decimal preservada)
- [ ] 3.5 NCM por prefixo (`02;2202`) traz os dois grupos
- [ ] 3.6 Editar célula editável grava no registro (conferir no Modo Tabela após
      reabrir)
- [ ] 3.7 Colunas cinza **não** são editáveis
- [ ] 3.8 Ordenar por uma coluna e depois editar grava no **registro certo**
- [ ] 3.9 Ctrl+D preenche para baixo; Ctrl+R para a direita
- [ ] 3.10 Ctrl+D sobre bloco que inclui coluna cinza pula as read-only
- [ ] 3.11 Exportar CSV abre corretamente no Excel (latin-1, separador `;`)

---

## 4. Recálculos (ICMS)

- [ ] 4.1 Recalcular C190 de um documento: grupos por CST+CFOP+alíquota corretos
- [ ] 4.2 **Soma dos VL_OPR = soma dos itens + despesas acessórias** (caso de
      referência: itens 3.293,00 + VL_OUT_DA 1,50 = **3.294,50**)
- [ ] 4.3 CST \*20/\*70: VL_RED_BC = VL_OPR − VL_BC_ICMS; demais CST = 0
- [ ] 4.4 Recalcular totais do C100: VL_MERC = soma dos itens; VL_DOC recomposto
- [ ] 4.5 Frete/seguro/outras despesas do C100 **preservados** no VL_DOC
- [ ] 4.6 Sem C100 selecionado, oferece recalcular todos
- [ ] 4.7 Após recalcular, salvar e validar no **PVA**: sem erro de layout

---

## 5. PIS/COFINS (Contribuições)

- [ ] 5.1 Abrir "Trocar alíquotas": diálogo abre e sugere a alíquota
      predominante (regressão da v0.14.2 — `_registros_aliq_escopo`)
- [ ] 5.2 Escopo **saídas** sugere ~1,65/7,6; **entradas**, as de crédito
      (ex.: 1,86/8,54)
- [ ] 5.3 Escopo saídas altera C175 **e** C170 de saída
- [ ] 5.4 Filtro "apenas onde a alíquota atual for X" não toca nas demais
- [ ] 5.5 "Somente tributados" preserva CST sem tributação
- [ ] 5.6 VL_PIS/VL_COFINS recalculados = base × alíquota ÷ 100
- [ ] 5.7 Totais do C100 pai atualizados
- [ ] 5.8 Recalcular bloco M: ordem **M200 → M205 → M210** (idem M600/M605/M610)
- [ ] 5.9 Arquivo resultante validado no PVA sem erro de hierarquia

---

## 6. Conferência com XMLs

- [ ] 6.1 Conferir entradas 55: documentos casam por modelo+série+número
- [ ] 6.2 Divergência de VL_ITEM é apontada item a item
- [ ] 6.3 Divergência de **CST_ICMS** e de valores de ICMS é apontada
- [ ] 6.4 Duplo clique numa divergência navega até o C170
- [ ] 6.5 Itens só no XML e só no SPED aparecem separados
- [ ] 6.6 Exportar CSV
- [ ] 6.7 Conferir C190: com XML de CFOP único (ex.: 5102) e C170 com CFOPs
      distintos (1101/1102), os grupos são reconstruídos **pelo C170**
- [ ] 6.8 Sem divergências reais, o resultado vem zerado (sem falso positivo)
- [ ] 6.9 Correlações de CFOP: editar, salvar e reabrir o app mantém o JSON

---

## 7. Tabelas RFB / CST por NCM

- [ ] 7.1 Localiza automaticamente a **maior versão** das tabelas na pasta do PVA
- [ ] 7.2 Caminho manual de cada arquivo funciona
- [ ] 7.3 Classificação por prefixo de NCM: carnes (02xx) = alíquota zero;
      bebidas (2202/2203/2208) = monofásico
- [ ] 7.4 Vigência respeitada (registros com DT_FIM não classificam)
- [ ] 7.5 Aponta entradas de monofásico com CST 50
- [ ] 7.6 Resultado navegável e exportável
- [ ] 7.7 Config persistida em `config_tabelas_rfb.json`

---

## 8. NFC-e modelo 65 (C175 por item) — experimental

- [ ] 8.1 Validar C175 com XMLs cria os C170 fictícios nos documentos casados
- [ ] 8.2 O C170 fictício traz **todos** os dados do item (descrição, quantidade,
      unidade, ICMS, ICMS-ST, IPI, PIS/COFINS)
- [ ] 8.3 C170 fictício com o **número correto de campos** (37 no Contribuições)
- [ ] 8.4 Relatório mostra as discrepâncias com o C175 escriturado
- [ ] 8.5 Documentos sem XML são reportados no resumo
- [ ] 8.6 Corrigir um item no Modo Relatório e regenerar: C175 reflete a correção
- [ ] 8.7 Após regenerar, **nenhum C170 sobra** nos documentos modelo 65
- [ ] 8.8 Arquivo final validado no PVA

---

## 9. Inventário — bloco H — experimental

- [ ] 9.1 Ler XLSX e CSV; linhas vazias ignoradas
- [ ] 9.2 Auto-detecção de colunas acerta cabeçalhos comuns ("Código do
      Produto", "Quantidade", "Valor Unitário"…)
- [ ] 9.3 Mapeamento manual funciona para cabeçalhos fora do padrão
- [ ] 9.4 Faltando coluna obrigatória, avisa em vez de importar errado
- [ ] 9.5 **Conferir com o 0200**: separa novos, existentes, duplicados e
      divergências de descrição/unidade/NCM
- [ ] 9.6 **Comparar com inventário atual**: quantidade divergente com sinal,
      só no SPED, só na planilha, somas dos dois lados
- [ ] 9.7 A comparação **não altera** o arquivo (contar H010 antes e depois)
- [ ] 9.8 Importar: H001 com IND_MOV=0, H005 com data/motivo, VL_INV = soma
- [ ] 9.9 Itens já cadastrados **não duplicam** no 0200; novos são criados
- [ ] 9.10 Unidade nova gera 0190
- [ ] 9.11 Registros com o número correto de campos (H005=4, H010=11, 0200=13,
      0190=3) — sem pipes sobrando
- [ ] 9.12 Reimportar substitui o inventário anterior (com confirmação)
- [ ] 9.13 Arquivo final validado no PVA

---

## 10. Revisão

- [ ] 10.1 Número de campos: sem falso positivo em arquivo íntegro
- [ ] 10.2 C190 com CST \*20/\*70 e VL_RED_BC zerado é apontado
- [ ] 10.3 **C170 sem C190 compatível**: zero em arquivo correto; aponta ao
      alterar o CFOP de um item
- [ ] 10.4 0200 não utilizados/duplicados
- [ ] 10.5 Navegação até o registro a partir do resultado

---

## 11. Integridade do arquivo (fazer ao final de qualquer alteração)

- [ ] 11.1 Salvar e reabrir: hierarquia preservada (filhos no pai certo)
- [ ] 11.2 Totalizadores **X990** de cada bloco corretos
- [ ] 11.3 **9900** com a contagem por tipo de registro
- [ ] 11.4 **9990** e **9999** corretos
- [ ] 11.5 Encoding **latin-1** preservado (acentos das descrições intactos)
- [ ] 11.6 Nenhum registro com número de campos fora do layout
- [ ] 11.7 **Validação no PVA sem erros**

---

## 12. Regressões conhecidas (verificar sempre)

Casos que já quebraram e precisam de conferência a cada entrega:

- [ ] 12.1 Método com assinatura perdida → `AttributeError` em runtime
      (`consolidar_c175_de_itens`, `_registros_aliq_escopo`) — cobre-se com 0.3/0.5
- [ ] 12.2 Aba movida sem levar o conteúdo (`tabMoved.disconnect()`)
- [ ] 12.3 Rateio de despesas com soma estourando centavos
- [ ] 12.4 Bloco M com M210 antes do M205
- [ ] 12.5 Registro criado com 40 campos em vez do tamanho real do layout
- [ ] 12.6 Filtro de modelo invertido (aplicar × ignorar) na alteração de datas

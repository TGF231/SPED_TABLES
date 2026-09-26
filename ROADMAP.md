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

**Onde estamos:** `0.55.0`, canal **dev**. Toda a série 0.y.z é sandbox:
nenhuma versão antes da 1.0.0 é entregue como release.

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
| | Inventário do bloco H (importar, comparar, atualizar 0200) | ✔ parcial | ✔ 11.585 itens | ✔ importar — só num arquivo acima do teto de 1.000 erros |
| | Preencher COD_GEN | ✔ | ✔ | ✔ |
| Contribuições | Recalcular bloco M (apuração e crédito) | ✔ | ✔ | ✔ |
| | Trocar alíquotas de PIS/COFINS | ✔ | ✔ | ✔ |
| | NFC-e 65: validar e regenerar C175 | ✔ | ✔ 205 documentos | **pendente** — precisa dos XMLs |
| | CST por NCM (verificar e corrigir) | ✔ | ✔ | **pendente** — sem caso nos arquivos reais |
| | Empresas e rotinas por regime | ✔ | ✔ verificação; correção por controle | ✔ |
| Gerais | Diagnóstico, revisão, validação de campos | ✔ | ✔ gabarito | ✔ contra o banco do PVA |
| | Limpar NULL, normalizar campos, COD_CTA, itens sem referência | ✔ | ✔ | ✔ |
| | Alterar datas (C100) | ✔ | ✔ | ✔ |
| | Conferência com XMLs (entradas, C190, itens) | ✔ | ✔ | — |
| | Abrir no PVA (importar e validar) | ✔ sem PVA | ✔ nos dois PVAs | — |
| | Acervo e histórico por empresa | ✔ | ✔ | — |
| Sistema | Fallback de exceções, registro, cópia de emergência | ✔ | — | — |

**PVA:** 53 validações sobre 4 arquivos reais, nenhuma correção criando
erro que o original não tenha — os números estão no CHANGELOG da 0.54.0.
Faltam duas funções, por falta de caso, não de defeito: **NFC-e 65** precisa
dos XMLs dos cupons e **CST por NCM** não tem o que corrigir nos arquivos
reais. Se não ganharem caso até o rc.1, saem da 1.0.0 com `pronta=False`.

### 4.2 Etapas

| Versão | Entrega | Situação |
|---|---|---|
| 0.51.0 | Suíte de testes no repositório; fallback de exceções | ✔ |
| 0.52.0 | Configuração num ponto só; achados menores da revisão | ✔ |
| 0.53.0 | Arquitetura em camadas; tabela de ações; correções cobertas pela suíte; canais de versão | ✔ |
| 0.54.0 | Coluna **PVA** da tabela 4.1 inteira (roteiro 2.1) e as três funções sem arquivo real | ✔ — menos NFC-e 65 e CST por NCM, sem caso |
| 0.55.0 | Executável: gerar, rodar o roteiro 2.2 e 2.3 sobre ele | ✔ — falta só arrastar um `.txt` do Explorador (a lógica está na suíte) e a escala acima de 100%, sem monitor para isso aqui: entram no rc.1 |
| 1.0.0-rc.1 | Congelamento: só correção; README revisado de ponta a ponta; do roteiro 2.3, arrastar um `.txt` do Explorador e um monitor acima de 100% | pendente |
| **1.0.0** | Release — ver 4.3 | — |

Função que não fechar a coluna PVA até o rc.1 sai da 1.0.0 com
`pronta=False` e volta numa 1.x.

### 4.3 Publicação da 1.0.0

Toda a história até aqui é sandbox. O que vai para o GitHub na 1.0.0 é um
**começo limpo**: um repositório (ou um histórico) novo, com um único commit
contendo o código da 1.0.0, e um CHANGELOG que começa na 1.0.0. O histórico
0.x — que contém nome e CNPJ de clientes em documentos antigos — não é
publicado. As tags 0.x não são recriadas.

---

## 5. Depois da 1.0

Sem data; entram pelo canal dev e seguem a seção 1.

- **Desfazer (undo)** para edições em lote — pede que cada edição seja um
  comando do domínio.
- Persistir entre sessões a ordem e a fixação das abas.
- Refazer a densidade da interface ao mover a janela entre monitores.
- `CST_ACEITOS`/`CST_SUGERIDO` editáveis pela interface (hoje montados para
  comércio/revenda).
- Oferecer a limpeza de campos `NULL` ao abrir um arquivo que os tenha.
- Copiar/colar em bloco no Modo Relatório, compatível com o Excel.
- Aviso ao salvar com C170 fictícios de NFC-e ainda no arquivo.
- Conferência do ICMS das NFC-e usando os C170 fictícios.
- Redução de base por produto no recálculo de ICMS.
- Catálogo de filhos permitidos por registro (criar o primeiro C170 de um
  C100 que só tem C190).

---

## 6. Limites que a 1.0 assume

Não são funções pela metade: são comportamentos definidos, documentados no
README, que uma versão futura pode ampliar.

- A ordem, a fixação e o fechamento de abas valem durante a sessão.
- Não há desfazer: as rotinas em lote devem rodar com o arquivo salvo.
- As ~1.400 regras compostas do PVA (em Java) não são reproduzidas; o
  diagnóstico diz quantas se aplicam ao arquivo. O validador oficial
  continua sendo o juiz.
- Os CST esperados por NCM valem para comércio/revenda.
- Entre *Validar C175* e *Regenerar C175* (NFC-e 65) o arquivo tem C170 em
  documento modelo 65, estrutura inválida: não salve nesse estado.

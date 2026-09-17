# Changelog

## [0.24.0] - 2026-09-17

### Corrigido
- **No executável, os dados do usuário seriam perdidos a cada fechamento.**
  `empresas.json`, `correlacoes_cfop.json`, `config_tabelas_rfb.json` e a pasta
  `arquivos/` eram gravados ao lado do módulo — que num executável *onefile* é
  a pasta temporária de extração, apagada na saída. O defeito só apareceria na
  **segunda** execução, sem erro nenhum: o programa simplesmente esqueceria
  tudo. Agora o novo módulo `dados.py` decide o caminho:
  - **empacotado** → `%APPDATA%\SPED Tables` (ou `~/.sped_tables` fora do
    Windows);
  - **do código-fonte** → a pasta do projeto, como sempre, para não espalhar
    arquivo de teste pelo perfil durante o desenvolvimento.

### Adicionado
- **Instalação na primeira execução** (só no executável): cria a pasta de
  dados, copia para lá os padrões que vieram no pacote **sem sobrescrever** o
  que já for do usuário, e oferece **criar o atalho na área de trabalho**. Uma
  marca na pasta de dados evita repetir a pergunta a cada atualização.
- `dados.criar_atalho_area_trabalho()`, via WScript.Shell pelo PowerShell —
  sem depender de pywin32 — tratando o redirecionamento da área de trabalho
  pelo OneDrive.

## [0.23.1] - 2026-09-17

### Corrigido
- **A margem da janela maximizada ignorava o DPI do monitor.**
  `GetSystemMetrics` devolve sempre a medida de 96 DPI; num monitor a 125% ou
  150% a margem sairia pequena demais e parte do conteúdo ficaria fora da tela
  — erro que, num arranjo de dois monitores com escalas diferentes, só aparece
  depois de arrastar a janela. Passa a usar `GetSystemMetricsForDpi` com o DPI
  da própria janela, caindo na medida clássica onde a função não existir
  (anterior ao Windows 10 1607).

### Alterado
- **A barra de título própria passa a ser considerada estável.** A
  documentação ainda a descrevia como experimental e opt-in, o que deixou de
  ser verdade na 0.19.1, quando virou padrão.

### Verificado
Suíte própria, em janela real do Windows: hit-test correto nas **oito** bordas
e cantos, HTCAPTION na faixa da barra e HTCLIENT sobre os botões, três ciclos
de maximizar/restaurar sem o conteúdo transbordar a área de trabalho (0 px em
todos), troca de tema com a barra preservada, escotilha
`SPED_TABLES_BARRA_NATIVA=1` e tolerância a ponteiro de mensagem inválido.

Fica registrado o que **não** foi observado: a máquina de desenvolvimento roda
a 96 DPI, então o caminho sensível a DPI é exercitado mas o valor escalado não
pôde ser comparado num monitor a 125%.

## [0.23.0] - 2026-09-17

### Adicionado
- **Recalcular ICMS dos itens** (Ferramentas → EFD ICMS/IPI). Fecha o fluxo de
  correção pelo **Modo Relatório**: corrija alíquota, base ou CST direto na
  grade e peça o recálculo para os campos derivados voltarem a bater.
  - **VL_ICMS = VL_BC_ICMS × ALIQ_ICMS ÷ 100**, sempre — é o cálculo que amarra
    os três campos e o que mais sai errado quando a alíquota é corrigida à mão.
  - Opcional: **refazer a base** a partir de `VL_ITEM − VL_DESC`, aplicando um
    percentual de **redução** nos CST **x20** e **x70**. Sem essa opção, a base
    informada é respeitada — inclusive uma base reduzida digitada à mão.
  - Opcional (ligado): **zerar** base, alíquota e valor nos CST **sem débito
    próprio** (x30, x40, x41, x50, x60). Um CST desses com valor lançado é erro
    de escrituração, não redução.
  - Ao final, refaz o **C190** e os **totais do C100** dos documentos afetados.
  - **Escopo padrão: os itens do Modo Relatório** — o conjunto que acabou de
    ser revisado. Sem relatório gerado, vale para todos os C170.
  - O **ICMS-ST não é tocado**: tem base e alíquota próprias, muitas vezes com
    MVA, e misturá-lo produziria número errado em silêncio.
- No modelo: `SpedDocument.recalcular_icms_itens()` e `situacao_icms()`, que
  classifica o CST em tributado / reduzido / sem débito pelos **dois últimos
  dígitos** (o primeiro é a origem da mercadoria e não interfere no cálculo).

## [0.22.2] - 2026-09-17

### Corrigido
- **O executável empacotado não levava recursos nenhum** (`datas` estava
  vazio no `.spec`). Passam a ser incluídos:
  - **`qtbase_pt_BR.qm`**, na pasta `traducoes/` do pacote — sem ele os
    diálogos do executável sairiam em inglês, mesmo com a correção da 0.22.1.
    O `instalar_traducao()` procura ali **antes** do caminho do sistema.
    O `qt_pt_BR.qm` fica de fora de propósito: é um meta-catálogo que só
    carrega com os `.qm` irmãos na mesma pasta; quem traz as strings de
    diálogo é o `qtbase`.
  - **`icon.ico`**, que além de ícone do executável é lido em tempo de execução
    pela barra de título e pelo `setWindowIcon`;
  - **`sped_editor.ui`**, o layout do Qt Designer (sem ele o programa cai no
    fallback programático);
  - **`correlacoes_cfop.json`**, para o programa nascer com a tabela padrão.
- O `.spec` agora **falha na geração** se a tradução não for encontrada —
  melhor que descobrir o inglês depois de distribuir.

## [0.22.1] - 2026-09-17

### Corrigido
- **Os diálogos do Qt apareciam em inglês** ("Save", "Discard", "Cancel",
  "Yes", "No"), destoando de uma interface toda em português. Duas camadas de
  correção:
  1. A **tradução pt-BR do próprio Qt** (`qtbase_pt_BR` e `qt_pt_BR`) passa a
     ser carregada na inicialização, junto com a locale pt-BR — isso cobre
     tudo que o Qt desenha, não só a pergunta de salvar.
  2. A pergunta de **salvar antes de fechar** escreve os próprios rótulos
     (*Salvar*, *Descartar*, *Cancelar*), sem depender dos arquivos `.qm`, que
     podem não ser empacotados no executável. É a pergunta em que sair em
     inglês seria pior: é ela que decide se o trabalho é gravado ou perdido.

### Alterado
- A pergunta foi separada da decisão (`_perguntar_salvar` devolve
  `"salvar"`/`"descartar"`/`"cancelar"`), o que também torna o fluxo testável
  sem depender de diálogo modal.

## [0.22.0] - 2026-09-17

### Adicionado
- **Fechar arquivo** na barra de ferramentas: encerra a escrituração aberta e
  volta para a tela inicial. Havendo alterações não salvas, pergunta antes,
  com as três saídas de sempre — **Salvar**, **Descartar** e **Cancelar**.
  - Um *Salvar* que acabe cancelado (o diálogo de *Salvar como* fechado no X)
    **não fecha o arquivo**: a intenção era guardar, e seguir em frente
    perderia o trabalho.
  - Ao fechar, as ferramentas que dependem de arquivo são desabilitadas e o
    título volta ao nome do programa.

### Alterado
- **Sair do programa passou a oferecer salvar.** Antes a pergunta era binária
  ("deseja sair mesmo assim?"), e a única saída com alterações pendentes era
  descartá-las. Agora usa a mesma pergunta do fechar arquivo.

## [0.21.0] - 2026-09-17

### Adicionado
- **Tela inicial**, no lugar das abas *Modo Tabela* e *Modo Relatório* vazias.
  Ela usa o que o programa já sabe sem abrir arquivo — o histórico arquivado e
  o cadastro — para responder três perguntas de quem chega:
  - **Em que eu estava?** Botão *Continuar* com o último período arquivado
    (empresa e mês no próprio rótulo) e área para **arrastar e soltar** o .txt.
  - **O que falta?** **Matriz empresa × período** dos últimos 8 meses:
    `●●` os dois leiautes arquivados, `●` só um (azul ICMS, âmbar
    Contribuições), `—` nenhum. Duplo clique numa célula abre aquele período.
    O rótulo é deliberado: **"arquivado neste sistema"**, nunca "entregue" — um
    arquivo pode ter sido transmitido sem jamais passar por aqui.
  - **O que dá para fazer agora?** Pendências (empresa com arquivo e sem
    cadastro, cadastro que nunca recebeu arquivo) e atalhos que não dependem de
    arquivo aberto.
- **Dimensionamento conforme a resolução** (`dimensionar_para_a_tela`): numa
  tela folgada a janela abre grande e centralizada (até 1600×960, limitada a
  88% da área útil); numa tela apertada **abre maximizada** e o tema entra em
  **densidade compacta** — fonte e espaçamentos menores, porque numa grade de
  SPED alguns pixels de padding por célula valem uma coluna a mais visível.
- `tema.definir_densidade("normal"|"compacta")`, que ajusta apenas corpo de
  fonte e espaçamento; cor e borda seguem idênticas nas duas.
- No modelo: `arquivos.cobertura()`, `arquivos.pendencias()` e
  `arquivos.resumo_acervo()` — a tela inicial é só a apresentação disso.

### Alterado
- O widget central tem agora três páginas: **tela inicial** (sem arquivo),
  **editor** (com arquivo) e **empresas**. Abrir um arquivo leva ao editor;
  sair de Empresas volta para onde fizer sentido.

## [0.20.1] - 2026-09-17

### Corrigido
- **O painel de empresas não lembrava a empresa selecionada.** A seleção era
  relida do próprio widget na hora de recarregar, o que falha nos fluxos em que
  a lista é remontada antes disso (cadastrar, remover, abrir do histórico).
  Agora a escolha é guardada explicitamente e **também sobrevive a reabrir o
  programa** (QSettings).

## [0.20.0] - 2026-09-17

### Alterado
- **Empresas deixou de ser janela separada e virou painel da janela
  principal.** Como diálogo ficava apertado: lista, cadastro e histórico lado a
  lado pedem a largura inteira. O painel ocupa uma **página própria do widget
  central** (QStackedWidget), fora das abas de bloco e dos modos
  Tabela/Relatório — não é um bloco do arquivo, é o cadastro.
- **O botão *Empresas* da barra virou interruptor.** Clicar abre o painel,
  clicar de novo volta ao editor. Enquanto está aberto, o botão fica com
  **moldura na cor do acento** e fundo suave, para deixar claro que é um
  estado, não um clique que passou. O botão *Voltar ao editor*, no rodapé do
  painel, também desmarca o botão da barra.
- Ao entrar no painel, o cadastro é **relido do disco** e a lista repintada:
  abrir ou salvar um arquivo arquiva uma cópia, e o histórico pode ter mudado
  desde a última visita.

## [0.19.2] - 2026-09-17

### Corrigido
- **Botões de minimizar e maximizar destoavam do de fechar.** Os três usavam
  caracteres de fontes diferentes (`–`, `□`, `✕`), com peso, altura e
  alinhamento óptico distintos. Passaram a usar os glifos de **Segoe MDL2
  Assets**, a mesma fonte que o Windows usa nos próprios botões de janela, com
  reserva em texto para sistemas sem ela. O botão central agora também troca
  entre os glifos de *maximizar* e *restaurar*.
- **Duas setas no botão Ferramentas.** O texto trazia um `▾` literal e o Qt
  desenhava o indicador de menu por cima. O caractere foi removido — o
  indicador nativo basta.

## [0.19.1] - 2026-09-17

### Corrigido
- **O programa não abria: o console piscava e fechava.** Duas falhas nativas,
  ambas sem traceback porque acontecem dentro do despacho de mensagens do
  Windows ou no envio de eventos do Qt.
  1. **`super().nativeEvent(...)` derruba o processo no PyQt6.** O override
     existia mesmo com a barra própria desligada, então o crash atingia
     **todos** os usuários, não só quem ligasse a barra. Para "não tratei",
     agora devolvemos `(False, 0)` — o Qt segue com o tratamento padrão.
  2. **Estruturas ctypes criadas a cada chamada.** Uma função que define
     `RECT` internamente devolve um *tipo novo* a cada invocação, e o ctypes
     compara tipos por identidade: `byref(RECT_A)` onde `argtypes` espera
     `POINTER(RECT_B)` falha. Como `WM_NCHITTEST` chega a cada movimento do
     mouse, o erro era imediato. As estruturas e os `argtypes` passaram a ser
     definidos **uma única vez, no import**.

### Alterado
- **A barra de título própria passou a ser o padrão**, agora que o caminho
  nativo foi validado por medição em janela real:
  - área de cliente cobrindo a janela inteira (WM_NCCALCSIZE);
  - `HTCAPTION` na faixa da barra, `HTRIGHT` na borda e `HTCLIENT` no conteúdo;
  - maximizada, o **conteúdo** ocupa exatamente a área de trabalho
    (0,0 → 1920,1050 num monitor 1080p), com a barra de tarefas visível — o
    retângulo da janela é maior de propósito, porque a moldura fica fora da
    tela, como em qualquer janela com WS_THICKFRAME.
  - Escotilha: **`SPED_TABLES_BARRA_NATIVA=1`** volta à barra do Windows.
- `tratar()` ficou inteiramente defensivo: qualquer exceção devolve "não
  tratei", e o Windows aplica o comportamento padrão.

## [0.19.0] - 2026-09-17

### Adicionado
- **Barra de título própria** (`janela_custom.py` + `BarraTitulo`), no lugar da
  barra do Windows — por enquanto **opcional**: ligue com a variável de
  ambiente `SPED_TABLES_BARRA_CUSTOM=1`.
  - Mostra ícone, nome do aplicativo, **empresa · período · leiaute · arquivo**
    e um **indicador de alterações não salvas** (antes, só um asterisco no fim
    do título, fácil de passar batido antes de fechar).
  - Botões de minimizar, maximizar/restaurar e fechar seguem a paleta; o de
    fechar acende em vermelho no hover.
  - **O comportamento nativo é preservado.** Em vez de `FramelessWindowHint` —
    que faria a janela deixar de ser uma janela para o Windows —, interceptamos
    três mensagens: `WM_NCCALCSIZE` (a área de cliente passa a ocupar a janela
    inteira), `WM_NCHITTEST` (nós definimos bordas, cantos e faixa de arrasto) e
    `WM_GETMINMAXINFO` (maximizar respeita a barra de tarefas do monitor certo).
    Assim continuam funcionando **Aero Snap**, redimensionar pelas bordas,
    duplo clique para maximizar, menu de sistema e sombra — o que importa num
    editor quase sempre usado lado a lado com o PVA.
  - Fora do Windows, sem a variável, ou se a preparação falhar, o programa usa
    a barra nativa: `showEvent` desmonta a barra própria e avisa na barra de
    status. Enfeite não pode impedir o aplicativo de abrir.

### Por que opcional
A interceptação de mensagens nativas **não pôde ser validada de forma
automatizada**: exibir uma janela real fora de uma sessão interativa não
funciona no ambiente de desenvolvimento usado, e uma falha nesse nível derruba
o processo sem traceback. O comportamento em Qt (montagem, contexto, indicador,
proteção dos botões, fallback e as duas paletas) está coberto por teste
offscreen. Confirmado o funcionamento em uso real, basta inverter o padrão em
`janela_custom.VARIAVEL`.

## [0.18.0] - 2026-09-17

### Adicionado
- **Memória persistente** (`arquivos.py`): ao **abrir** e ao **salvar**, o
  sistema guarda uma cópia do arquivo em `arquivos/<CNPJ>/<LEIAUTE>_<AAAAMM>.txt`
  — mesma ideia do banco interno do PVA, adaptada a um editor que trabalha o
  texto direto. **Uma cópia por empresa + leiaute + período**, sempre
  substituída pela mais recente; o índice fica em `arquivos/indice.json`.
  - A cópia é feita a partir do **arquivo em disco**, nunca de texto gerado em
    memória: é byte a byte o que o usuário tem, com o latin-1 e as quebras de
    linha originais.
  - Falha ao arquivar (pasta sem permissão, disco cheio) **não interrompe**
    abrir nem salvar — o aviso vai para a barra de status.
- **Histórico de arquivos por empresa**, dentro de *Empresas*: lista os
  períodos arquivados, com leiaute, data da última atualização, caminho de
  origem e tamanho. Duplo clique **abre a cópia interna** (não o arquivo de
  origem, que pode ter sido movido); dá para excluir um período do histórico
  sem afetar o arquivo original.
- **Aviso ao salvar**: além de informar que a cópia do período foi atualizada,
  lembra de validar no PVA e **reabrir aqui a versão validada**, para a cópia
  interna passar a refletir o arquivo definitivo.
- **Cadastro manual de empresas**, sem precisar abrir um SPED antes
  (*Empresas → Nova empresa…*, pelo CNPJ). A lista reúne o que está em
  `empresas.json` com as empresas que já têm arquivo no histórico.

### Alterado
- **Menu Ferramentas agrupado por tipo de SPED**: submenus **EFD ICMS/IPI**,
  **EFD Contribuições (PIS/COFINS)** e **Gerais**. O submenu inteiro fica
  desabilitado quando não corresponde ao leiaute aberto — antes, a lista única
  obrigava a saber de cor quais ferramentas valiam para o arquivo.
- **Empresas saiu do menu e foi para a barra principal**, ao lado de *Salvar
  como*: é o cadastro que dá sentido às rotinas, e funciona sem arquivo aberto.
- **Conferência com XMLs dividida por tributo**: são duas ações, uma em cada
  grupo, cada uma conferindo só os campos do seu leiaute —
  `conferir_itens_xml(doc, nfes, movimento=…, tributo=…)`.
  - **ICMS/IPI:** VL_ITEM, VL_DESC, base e valor de ICMS, base e valor de
    ICMS-ST, IPI e CST_ICMS.
  - **PIS/COFINS:** VL_ITEM, VL_DESC, base, alíquota e valor de PIS e de
    COFINS, mais CST_PIS e CST_COFINS.
- **Separação de entradas e saídas**: seletor de **Movimento**
  (Entradas / Saídas / Ambas) dentro do diálogo, que refaz a comparação sem
  reler a pasta de XMLs. A **correlação de CFOP só se aplica às entradas** —
  numa saída própria o CFOP do XML é o mesmo do SPED, e a comparação viraria
  identidade.
- `.gitignore`: `arquivos/` não entra no controle de versão (SPED de clientes).

### Compatibilidade
- `conferencia.conferir_entradas_55` continua existindo como atalho para
  `conferir_itens_xml(movimento="entrada", tributo="ICMS")`, e a ação antiga
  segue conectada para arquivos `.ui` que ainda a declarem — apenas não aparece
  no menu novo.

## [0.17.0] - 2026-09-17

### Adicionado
- **Configuração por empresa** (`empresas.py`) — *Ferramentas → Empresa e
  rotinas…*. Cada empresa é identificada pelo **CNPJ do registro 0000** e guarda
  o que o arquivo sozinho não diz: **regime federal** (Simples / Presumido /
  Real), **regime de PIS/COFINS** (cumulativo / não-cumulativo / ambos),
  atividade, alíquotas de saída e de crédito e o CST a usar quando um crédito
  indevido é retirado. Cadastro em `empresas.json`, por máquina.
  - Empresa nova é **pré-preenchida** com o que o arquivo informa (nome, UF e o
    regime do registro **0110**), para conferência antes de gravar.
  - **Divergência de regime**: quando o 0110 do arquivo contraria o cadastro, o
    diálogo avisa — é o escriturado discordando do declarado.
- **Rotinas de conferência e correção por regime** (`rotinas.py`), extensíveis
  como as regras de `revisao.py`:
  1. **Alíquota de saída fora do regime** — itens de saída com CST 01
     (alíquota básica) fora da alíquota do regime. Corrige a alíquota e
     recalcula o valor.
  2. **Crédito indevido na entrada (cumulativo)** — entradas com CST de
     creditamento (50-56, 60-66) e valor lançado numa empresa que não tem
     direito a crédito. Retira o crédito (zera base, alíquota e valor) e troca
     o CST pelo configurado (70 por padrão).
  3. **Alíquota de crédito fora do regime** — entradas do não-cumulativo cuja
     alíquota de crédito difere da esperada, tipicamente por terem ficado com
     a alíquota de saída.
  4. **CST incoerente com o NCM** — reaproveita as tabelas da RFB; sem correção
     automática, porque o CST correto depende do produto.
  - Toda rotina roda primeiro em **conferência**, com relatório navegável
    (duplo clique vai ao registro) e exportável em CSV. A correção só é
    aplicada depois de confirmar, com a **contagem do que será alterado**, e
    atua exatamente sobre as ocorrências exibidas.

### Regras fiscais codificadas
- Cumulativo: PIS 0,65 / COFINS 3,00, **sem** direito a crédito.
- Não-cumulativo: PIS 1,65 / COFINS 7,6, com crédito.
- **Ambos os regimes**: as rotinas de alíquota **se abstêm** — a mesma alíquota
  pode estar certa ou errada na mesma escrituração.
- A verificação de alíquota só olha **CST 01**: o CST 02 é "alíquota
  diferenciada" e o 03 é por quantidade; cobrar deles a alíquota nominal seria
  falso positivo.

### Alterado
- `.gitignore`: `empresas.json` não entra no controle de versão — é dado do
  usuário, com CNPJ de clientes.

## [0.16.0] - 2026-09-17

### Adicionado
- **Tema visual próprio, claro e escuro** (`tema.py` + `icones.py`), portado do
  projeto **Backup Maximus** — os dois aplicativos passam a compartilhar a mesma
  identidade, com o acento **cobre** e as cores semânticas (ok/aviso/erro)
  separadas do acento, para que "atenção" nunca se confunda com "clicável".
  - Botão **Tema escuro / Tema claro** na barra de ferramentas; a preferência é
    gravada entre sessões (QSettings) e vale para a máquina, não para a sessão.
  - A folha de estilo trata o que este aplicativo realmente é — **grades**:
    linha alternada, linha de grade discreta, cabeçalho de coluna destacado,
    célula somente-leitura e seleção em acento suave que preserva a leitura do
    número.
  - Abas, barra de ferramentas, menu Ferramentas, campos, botões, barra de
    status, diálogos, rolagem e dicas seguem a mesma paleta.
  - Os ícones de "✓" e da seta do combo são **desenhados em runtime** na cor da
    paleta ativa: o QSS não aceita data URI e o indicador nativo se perde ao
    trocar o fundo.

### Alterado
- As cores dos relatórios deixaram de ser literais espalhados pela GUI
  (`#b00`, `#0a0`, `#b60`, `#1565c0`, o cinza da célula derivada) e passaram a
  vir de **tokens da paleta** — sem isso, ficariam ilegíveis no tema escuro.
  Restou um único `setStyleSheet` no aplicativo: o global.
- Rótulos de estado usam a propriedade dinâmica `role` (`ok`, `erro`, `aviso`,
  `dica`, `info`, `produto`), não estilo embutido.
- O nome da aplicação registrado no Qt era "Editor SPED"; passou a usar o
  `APP_NAME` de `version.py`.

## [0.15.4] - 2026-09-17

### Alterado
- **Conferência de entradas (NF-e 55): o frete e o seguro do item também entram
  no VL_ITEM.** Mesmo caso do `vOutro` tratado na 0.15.3 — o C170 não tem campo
  de despesa acessória por item (o leiaute só prevê VL_FRT, VL_SEG e VL_OUT_DA
  no C100, por documento), então o que a NF-e traz em `det/prod/vFrete` e
  `det/prod/vSeg` é escriturado dentro do valor do item. O critério passa a ser
  `vProd + vOutro + vFrete + vSeg`, com os três acessórios reunidos na constante
  `conferencia.ACESSORIOS_ITEM`.
- O parser de XML passou a extrair **`vFrete` e `vSeg` por item**; antes só lia
  os totais da nota (`ICMSTot`).

  Se a sua escrituração lançar frete e seguro nos campos do **C100**
  (VL_FRT/VL_SEG) em vez de dentro do item, a conferência passará a apontar
  divergência — nesse caso, ajuste `ACESSORIOS_ITEM` para conter apenas
  `"voutro"`.

## [0.15.3] - 2026-09-17

### Corrigido
- **Conferência de entradas (NF-e 55): o "outros" do item era acusado como
  divergência.** O C170 não tem campo de despesas acessórias por item — o
  leiaute só prevê VL_OUT_DA no C100, por documento —, de modo que o valor que
  a NF-e traz em `det/prod/vOutro` é escriturado **dentro do VL_ITEM**. A
  comparação usava apenas o `vProd` e apontava um falso positivo do tamanho
  exato do "outros" em cada item que o tivesse. Agora o critério é
  `vProd + vOutro` (função `conferencia.valor_item_xml`).
- O parser de XML passou a extrair o **`vOutro` por item** (`det/prod/vOutro`);
  antes só lia o total da nota (`ICMSTot/vOutro`).

  A conferência do **C190** não muda: lá o "outros" continua entrando pelo
  rateio das despesas acessórias do documento, que distribui exatamente o mesmo
  montante — os dois caminhos permanecem coerentes.

## [0.15.2] - 2026-09-10

### Corrigido
- **Tabelas de resultado exibiam apenas a coluna "Situação"/primeira coluna, em
  todas as linhas menos a última.** Os diálogos preenchiam a grade com a
  **ordenação já ligada**: cada `setItem` reordenava a tabela na hora, de modo
  que as células seguintes da mesma linha caíam em outra linha. Agora a
  ordenação só é ativada **depois** do preenchimento (idioma já usado no Modo
  Relatório e na verificação de CST por NCM). Afetava:
  - *Comparar inventário com a planilha* (bloco H);
  - *Validar C175 (modelo 65) com XMLs* — relatório de discrepâncias;
  - *Conferir C190 (ICMS) com XMLs*.

### Alterado
- Os relatórios em tabela passam a **abrir na ordem em que foram montados**
  (na comparação de inventário: divergentes, depois só no SPED, depois só na
  planilha; nas conferências, documento a documento; na verificação de CST por
  NCM, entradas antes das saídas), em vez de ordenados alfabeticamente pela
  primeira coluna. O clique no cabeçalho continua ordenando normalmente. O
  indicador de ordenação é zerado **antes** de a ordenação ser ligada, porque o
  QTableWidget reordena o próprio modelo — depois de ordenado não há como voltar
  à ordem original.

## [0.15.1] - 2026-07-05

### Adicionado
- **Comparar o inventário atual com a planilha** (botão *Comparar com
  inventário atual*, no diálogo de importação do bloco H): confronta o **H010 já
  escriturado** com a planilha por **código e quantidade**, **sem alterar o
  arquivo**. Mostra os itens que conferem, os de **quantidade divergente** (com
  a diferença), os que estão **só no SPED**, os que estão **só na planilha** e as
  somas de quantidade dos dois lados; exportável em CSV.

## [0.15.0] - 2026-07-05

### Adicionado
- **Importar inventário (bloco H) de planilha** (Ferramentas, EFD ICMS/IPI):
  lê uma planilha **XLSX/CSV** e gera o inventário — H001 (IND_MOV=0), **H005**
  (data, motivo e valor total) e um **H010** por item.
  - As colunas são **reconhecidas automaticamente** pelo nome do cabeçalho
    (código, descrição, unidade, quantidade, valor unitário, NCM, conta
    contábil…), com **mapeamento manual** ajustável para qualquer layout.
  - **Coerência com o 0200:** itens que ainda não existem no cadastro são
    criados (descrição, unidade, tipo e NCM da planilha) e os já cadastrados
    **não são duplicados**; unidades novas geram registros **0190**.
  - Botão *Conferir com o 0200* mostra, antes de importar, quantos itens são
    novos, quantos já existem, códigos repetidos na planilha e divergências de
    descrição/unidade/NCM em relação ao cadastro.

### Corrigido
- Registros criados pelo programa passaram a usar o **número real de campos** do
  tipo (moda dos registros do arquivo ou campos nomeados do layout). Os C170
  fictícios do fluxo do modelo 65 vinham sendo gerados com 40 campos em vez de
  37, o que geraria erro de layout no PVA.

## [0.14.2] - 2026-07-04

### Corrigido
- **Erro ao abrir "Trocar alíquotas de PIS/COFINS"** (AttributeError:
  '_registros_aliq_escopo'). O método auxiliar de seleção de registros por
  escopo havia perdido sua assinatura numa edição anterior (o corpo ficara como
  código inacessível), quebrando a sugestão de alíquota predominante e a própria
  troca. Restaurado. Feita também uma varredura (AST) em todos os módulos para
  garantir que não há outros métodos na mesma situação.

## [0.14.1] - 2026-07-04

### Alterado
- Os **C170 fictícios** gerados na validação do C175 (modelo 65) agora recebem
  **todos os dados do item do XML** — descrição, quantidade, unidade, CST/base/
  alíquota/valor de ICMS, ICMS-ST e IPI, além de PIS/COFINS — e não apenas os
  campos consumidos pelo C175. O parser de XML passou a extrair quantidade
  (qCom), unidade (uCom), NCM, alíquota de ICMS-ST e o grupo de IPI (CST, base,
  alíquota).

## [0.14.0] - 2026-07-04

### Adicionado
- **Validação e correção do C175 (NFC-e modelo 65) por item, via XMLs.** Novo
  fluxo no EFD Contribuições, em três passos:
  1. *Ferramentas → Validar C175 (modelo 65) com XMLs:* importa os XMLs das
     NFC-e e cria, em cada C100 modelo 65, registros **C170 fictícios** (um por
     item do XML) com valor, CFOP e PIS/COFINS — já que o modelo 65 é
     escriturado consolidado, sem itens. Abre um **relatório de discrepâncias**
     entre a soma dos itens e o C175 escriturado (exportável em CSV).
  2. *Correção por item:* os C170 fictícios podem ser editados no **Modo
     Relatório** (fonte C170), inclusive com Ctrl+D/Ctrl+R.
  3. *Ferramentas → Regenerar C175 (modelo 65) dos itens:* reconsolida o C175 a
     partir dos itens corrigidos e **remove** os C170 fictícios, restaurando a
     estrutura consolidada.

### Corrigido
- A função interna de consolidação do C175 a partir de itens havia perdido sua
  assinatura numa edição anterior (ficara como código inacessível); restaurada.

## [0.13.1] - 2026-07-04

### Adicionado
- **Recalcular totais do C100** (botão à esquerda de adicionar/remover, na grade
  de C100): recompõe os totais do documento a partir dos itens C170 — valor das
  mercadorias, desconto, base e valor de ICMS, ICMS-ST, IPI e (no EFD
  Contribuições) PIS/COFINS —, e recalcula o VL_DOC mantendo frete, seguro e
  outras despesas do C100. Recalcula o documento selecionado ou, se nenhum
  estiver selecionado, oferece recalcular todos os C100 com itens.

## [0.13.0] - 2026-07-04

### Adicionado
- **Revisão: C170 sem C190 compatível.** Nova regra que aponta itens (C170) cuja
  combinação de CST_ICMS, CFOP e alíquota de ICMS não aparece em nenhum C190 do
  mesmo documento — ou seja, itens que não foram consolidados no analítico.
- **Conferência de entradas: ir ao registro.** Duplo clique numa linha de
  divergência leva ao C170 correspondente no editor.
- **Fixar / fechar / resetar sub-abas de detalhe** (menu de contexto ao clicar
  com o botão direito numa sub-aba do painel de detalhe):
  - *Fixar aba:* o tipo de registro fixado passa a ser **exibido primeiro** ao
    trocar de registro pai (resolve o detalhe voltar sempre para a primeira aba
    disponível do documento).
  - *Fechar aba:* oculta aquele tipo de sub-aba até resetar.
  - *Resetar abas:* limpa ordem, fixação e abas fechadas do contexto.
  Sem aba fixada, o painel passa a exibir sempre a primeira aba na ordem atual.

## [0.12.2] - 2026-07-03

### Adicionado
- **Atalhos estilo Excel no Modo Relatório:** **Ctrl+D** preenche as células
  selecionadas com o valor da primeira linha da seleção (ou, se houver só uma
  célula, com a de cima) e **Ctrl+R** preenche à direita a partir da primeira
  coluna. Só afeta as colunas editáveis (as derivadas continuam intactas) e cada
  preenchimento é gravado no registro correspondente do SPED.

## [0.12.1] - 2026-07-03

### Alterado
- **Filtros do Modo Relatório agora aceitam múltiplos valores** em todos os
  campos, separados por ponto e vírgula (";"). Ex.: CFOP "1101;1102", CST
  "000;020;060", Alíq. PIS "1,65;0,65". Usa-se ";" (e não vírgula) para não
  conflitar com a vírgula decimal das alíquotas. O filtro de NCM continua por
  prefixo, agora aceitando vários (ex.: "02;2202").

## [0.12.0] - 2026-07-03

### Alterado
- **Aba Resumo reformulada.** A contagem de registros deixou de ser uma tabela e
  passou a ser uma **lista simples** agrupada por bloco. A aba agora traz também
  a **apuração do período**:
  - *EFD ICMS/IPI:* consolidação das **entradas** e das **saídas** por
    CST/CFOP/alíquota (só os totais, sem listar documentos), e a **apuração do
    ICMS de operações próprias (E110)** — débitos, créditos, saldo credor
    anterior, ICMS a recolher e saldo a transportar.
  - *EFD Contribuições:* **consolidação por CST** de PIS/COFINS, separando
    receitas/saídas, aquisições/custos e outras operações (valor do item, base
    de PIS e base de COFINS).
- A **conferência de entradas (NF-e 55 × C170)** passou a verificar também o
  **CST de ICMS** e os **valores de ICMS** (base e imposto) — antes só conferia
  VL_ITEM/VL_DESC e a correlação de CFOP. CST e valores de ICMS não podem
  divergir entre o XML e o SPED.

## [0.11.0] - 2026-07-03

### Adicionado
- **Conferir C190 (ICMS) com XMLs** (Ferramentas, EFD ICMS/IPI): compara os
  registros C190 com os XMLs, para entradas e saídas. Como o CFOP do XML é o de
  saída do fornecedor (diferente do CFOP de entrada escriturado), os itens do
  XML são agrupados pela **classificação do C170** (CST/CFOP/alíquota de ICMS),
  casada por **nItem** — assim os grupos do C190 (ex.: CFOP 1101 e 1102, quando o
  XML só traz 5102) são reconstruídos sem perder a correlação de cada item.
  Compara VL_OPR, VL_BC_ICMS e VL_ICMS por grupo (com o mesmo rateio de despesas
  acessórias do recálculo do C190) e exporta as divergências em CSV.
- O parser de XML passou a extrair os campos de **ICMS por item** (CST, base,
  alíquota, valor, ST e IPI), além de PIS/COFINS.

## [0.10.1] - 2026-07-03

### Corrigido
- **VL_RED_BC não era calculado no recálculo do C190.** Nos grupos com CST de
  ICMS terminado em **20** ou **70** (redução de base), o campo ficava zerado
  mesmo quando o C170 não trazia o percentual/valor de redução. Agora é obtido
  diretamente por **VL_OPR − VL_BC_ICMS** (nunca negativo).

## [0.10.0] - 2026-07-03

### Corrigido
- **Reposicionamento de abas não levava o conteúdo junto.** O gerenciador de
  ordem de abas desconectava o sinal `tabMoved` por completo, removendo também o
  slot interno do `QTabWidget` que sincroniza o conteúdo ao mover a aba —
  por isso o rótulo mudava de lugar mas a aba mostrava o conteúdo antigo. Agora o
  memorizador é ligado uma única vez, sem afetar a sincronização nativa.

### Adicionado
- **Soma da seleção (estilo Excel):** ao selecionar várias células numéricas
  numa grade, a barra de status mostra **Soma**, **Média** e **Contagem**.
- **Modo Relatório editável:** as células das colunas próprias do registro-fonte
  (C170/C175/C190) podem ser editadas diretamente na tabela do relatório — como
  uma *query* editável —, gravando a alteração no registro correspondente do
  SPED. Colunas derivadas (produto, dados do documento, valores calculados)
  ficam somente-leitura (fundo acinzentado). A edição respeita a ordenação por
  coluna.

## [0.9.1] - 2026-07-02

### Corrigido
- **Rateio de despesas acessórias no recálculo do C190.** Frete/seguro/outras
  despesas do C100 eram rateados arredondando o quinhão de cada item
  isoladamente, e a soma dos quinhões não fechava com o total (sobra/falta de
  centavos — ex.: 1,50 de VL_OUT_DA distribuído como 1,52). Agora o rateio usa a
  diferença de acumulados arredondados, de modo que a soma dos VL_OPR do C190
  bate exatamente com o total dos itens mais as despesas acessórias.

## [0.9.0] - 2026-07-02

### Adicionado
- **Verificar CST por NCM (tabelas RFB)** (Ferramentas): classifica cada item
  **C170** pelo NCM usando as tabelas oficiais do EFD-Contribuições — produtos de
  **alíquota zero** (CST 06) e **monofásicos** — e aponta CST de PIS/COFINS
  incoerentes, separando **entradas** e **saídas**. Ex.: entrada de produto
  monofásico (bebidas) escriturada com CST 50 (crédito indevido) em vez de 73/98.
  - As tabelas são localizadas automaticamente na pasta de recursos do PVA pela
    **maior versão** (nomes tipo `…$PROD_ALIQ_ZERO$48$166`), com opção de
    **informar o caminho de cada arquivo** diretamente caso o padrão mude.
  - Respeita a **vigência** (DT_INI/DT_FIM) na data de referência (por padrão, a
    DT_FIN do arquivo) e as exceções (NCM_EX). O **gênero** vem dos 2 primeiros
    dígitos do NCM. Opcionalmente valida contra a **Tabela NCM Vigente (XLSX)**
    do Siscomex. Resultado navegável e exportável em CSV. Config persistida em
    `config_tabelas_rfb.json`.
- Novo módulo `tabelas_rfb.py`; dependência opcional `openpyxl` (para o XLSX).

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.8.3] - 2026-07-02

### Alterado
- **Trocar alíquotas de PIS/COFINS** ampliada:
  - O escopo **Saídas** agora inclui, além do C175, os **C170 de documentos de
    saída** (débito detalhado por item) — antes só o C175 era corrigido.
  - Novo escopo **Todos os itens (C170 e C175)**, para corrigir alíquotas em
    qualquer registro, independentemente de entrada/saída.
  - Novo filtro opcional **“Trocar apenas onde a alíquota atual for”** (PIS e
    COFINS), para corrigir somente uma alíquota preenchida errada sem tocar nas
    demais.

## [0.8.2] - 2026-07-02

### Adicionado
- **Alterar datas de emissão/saída (C100)** (Ferramentas): filtra documentos por
  um intervalo de datas — avaliado sobre DT_E_S ou DT_DOC —, além de tipo de
  movimento e modelo, e altera a **data de emissão (DT_DOC)**, de **entrada/saída
  (DT_E_S)** ou ambas, seja para uma **data específica** ou **deslocando N dias**
  (aceita negativos).

### Corrigido
- O **filtro por modelo** de uma rotina externa de correção de datas estava
  invertido (marcar um modelo processava apenas ele, ao contrário do rótulo).
  Na versão integrada a semântica é explícita: *“Somente modelos”* aplica a
  alteração apenas aos modelos informados; em branco, a todos.

## [0.8.1] - 2026-07-02

### Adicionado
- **Modo Relatório com três fontes**, selecionáveis por um combo:
  **Itens (C170)**, **PIS/COFINS consolidado (C175)** e **ICMS consolidado
  (C190)**. Os relatórios de C175 e C190 cobrem documentos sem detalhamento de
  item — como a **NFC-e (modelo 65)** —, em que não há C170. Cada fonte mostra
  as colunas próprias do registro e habilita apenas os filtros aplicáveis
  (ex.: CST/alíquota de ICMS no C190; CST/alíquotas de PIS e COFINS no C175).
  Acrescentado o filtro de alíquota de ICMS.

## [0.8.0] - 2026-07-02

### Adicionado
- **Dois modos de visualização** no topo da janela: **Modo Tabela** (a edição
  mestre-detalhe por bloco, como antes) e **Modo Relatório**.
- **Modo Relatório**: visão achatada dos itens (uma linha por C170, com dados do
  C100 e do produto 0200), com filtros e colunas espelhando o relatório usado no
  banco do ERP — data, tipo (E/S), modelo, nº da nota, código do produto, item,
  NCM, CFOP, CST de ICMS/PIS/COFINS/IPI e alíquotas de PIS/COFINS. Permite
  **exportar em CSV** para comparar com o resultado do script SQL.

## [0.7.0] - 2026-07-02

### Corrigido
- **Recálculo do bloco M gerava erros de validação no PVA.** Os registros
  M210/M610 eram reinseridos logo após o M200/M600, ficando **à frente** do
  M205/M605 e violando a ordem do leiaute (M200 → M205 → M210). Isso causava os
  erros de "organização hierárquica" (esperado M211/M611 no lugar do M205/M605)
  e as divergências de contagem (QTD_LIN_M e QTD_LIN). Agora os detalhes são
  ancorados **após** o M205/M605, corrigindo inclusive arquivos que já tenham
  sido gravados fora de ordem. O formato dos campos zerados também passou a
  seguir o do arquivo original ("0" em vez de "0,00").

### Adicionado
- **Reordenação de abas por arrasto**, com a ordem preservada durante a sessão
  (não persiste após fechar). Vale para as abas de bloco e para as sub-abas de
  tipo de registro (inclusive as de registros-filho no detalhe). Cada aba é
  identificada por um id estável, então a ordem escolhida sobrevive às
  remontagens das grades.

## [0.6.0] - 2026-06-27

### Alterado
- Nome do aplicativo: **Editor SPED** → **SPED Tables** (melhor representa o
  foco em edição tabular de arquivos SPED).
- Ícone visual adicionado (icon.ico) exibido na barra de título da janela.

### Versão
Versão salto de 0.4.2 para 0.6.0 refletindo o amadurecimento da ferramenta
(suporte saídas/entradas, conferência CFOP, revisões, etc.).

## [0.4.2] - 2026-06-27

### Alterado
- **Trocar alíquotas de PIS/COFINS** agora atua também nos **documentos de
  entrada** (registros C170 de C100 com IND_OPER=0), recalculando o crédito com
  a alíquota do comprador. O diálogo ganhou o seletor de **escopo** (Saídas
  C175 / Entradas C170 / Ambos) e sugere a alíquota predominante de cada escopo
  (as entradas costumam ter alíquota de crédito diferente das saídas).

## [0.4.1] - 2026-06-27

### Adicionado
- **Revisão: 0200 não utilizados / duplicados** — nova regra em `revisao.py`
  que aponta registros 0200 cujo COD_ITEM não é referenciado por nenhum outro
  registro (C170, H010, etc.) e os 0200 com COD_ITEM duplicado. As referências
  são coletadas de qualquer registro que possua o campo COD_ITEM (não só
  C170/H010), evitando falsos positivos. Clicar no relatório navega até o 0200.

## [0.4.0] - 2026-06-27

### Adicionado
- **Trocar alíquotas de PIS/COFINS (C175)**: nova ferramenta que aplica novas
  alíquotas de PIS e/ou COFINS aos registros C175 e recalcula VL_PIS/VL_COFINS
  (base × alíquota), atualizando os totais dos C100. Sugere as alíquotas atuais
  predominantes e permite restringir aos registros tributados.

### Alterado
- As ferramentas passaram a ficar num botão **Ferramentas** na barra de
  ferramentas (ao lado de *Salvar como*).
- A **barra de menus** foi removida (redundante com a barra de ferramentas).
- A mensagem ao salvar agora informa apenas o caminho do arquivo salvo.

### Removido
- Ação manual **Recalcular totais (C990/9900)**: a recontagem (X990, 9900,
  9990, 9999) já é feita automaticamente ao salvar.

## [0.3.0] - 2026-06-26

### Adicionado
- **Correlação de CFOP nas entradas (NF-e 55)**: a conferência passou a checar
  se o CFOP de saída do fornecedor (5xxx/6xxx, no XML) corresponde a um CFOP de
  entrada válido no C170 (1xxx/2xxx). Ex.: um item com **5403** na compra
  escriturado como **1102** é apontado, com a sugestão de que deveria ser
  **1401** ou **1403**.
- **Tabela de correlações editável** (Ferramentas → Correlações de CFOP): lista
  de CFOP de saída → CFOPs de entrada válidos, editável na interface e
  persistida em `correlacoes_cfop.json`. Acompanha um conjunto padrão (96 CFOPs)
  que pode ser ajustado e restaurado.

## [0.2.0] - 2026-06-26

### Adicionado
- **Página inicial (Resumo)**: aba inicial com o cabeçalho do arquivo (registro
  0000: nome, CNPJ, IE, UF, período DT_INI–DT_FIN), data de modificação do
  arquivo em disco, layout detectado e contagem de registros (total e por bloco).
- **Revisão de erros**: ferramenta extensível que gera relatórios de
  inconsistências. Regras nesta versão: (1) registros com número de campos
  divergente do layout; (2) registros C190 com CST x20/x70 e VL_RED_BC zerado.
  Clicar numa linha do relatório navega até o registro exato.
- **Pesquisa em todos os blocos**: o campo de busca passou a aparecer em
  qualquer grade com registros (ex.: 0200, H010), pesquisando em todas as
  colunas. Em grades de documento continua focando o número do documento.
- **Versionamento**: arquivo `version.py` e este CHANGELOG; a versão aparece no
  título da janela e na página inicial.
- **Layout em `.ui`**: a janela principal pode ser editada no Qt Designer
  (`sped_editor.ui`); o aplicativo carrega o arquivo quando presente.

## [0.1.3] - anterior

### Adicionado
- Importação de XMLs (NFC-e 65) e consolidação de C175 por mod+série+nNF.
- Recálculo do bloco M (apuração PIS/COFINS) conforme o regime (0110).
- Conferência de entradas modelo 55 (item XML ↔ C170 por mod+série+nNF+nItem).
- Motor de vínculo genérico reaproveitável (`xml_fiscal.vincular`).
- Edição estilo planilha (setas, seleção múltipla, copiar/colar), filtros de
  operação/modelo, recálculo de C190 e recálculo de totais (C990/9900).

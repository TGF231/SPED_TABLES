# -*- coding: utf-8 -*-
"""
pva.py
------
Abre o PVA oficial e leva o arquivo salvo até a tela de importação.

**Não existe linha de comando para isso.** Os dois PVAs aceitam apenas
`-buildVersion` e `-atualizarTabelas`; nenhum importa um arquivo por
argumento. O que existe é melhor do que parece: os dois declaram, no
`ppgdmenubar.xml` que carregam do próprio `.jar`, o acelerador **Ctrl+I** para
*Escrituração → Nova → Importar*, e a janela que abre é um `JFileChooser`
(`FileChooserSelecionarArquivo`) cujo foco nasce no campo "Nome do arquivo:".

Daí o caminho usado aqui:

1. achar a janela do PVA — se já houver uma, **não** abrir outra (o PVA tem
   trava de instância única, `TryLock.txt`, e a segunda só mostra um erro);
2. não havendo, executar o `.exe` e esperar a janela aparecer (o PVA sobe um
   MySQL próprio e demora);
3. **esperar o carregamento interno terminar** — a janela principal aparece
   antes de aceitar atalhos, e enquanto carrega o processo mantém uma segunda
   janela, a barra de progresso. Medido numa partida a frio: janela aos 4 s,
   Ctrl+I só aceito aos 11,9 s, exatamente quando a contagem de janelas caiu
   de 2 para 1. Os atalhos enviados no meio são **engolidos**, não
   enfileirados — por isso o Ctrl+I também é repetido até o seletor abrir;
4. copiar o caminho do arquivo para a área de transferência;
5. mandar Ctrl+I, esperar o seletor de arquivo e mandar Ctrl+V e Enter;
6. responder aos dois "Aviso" que o PVA abre — "deseja importar?" e, ao fim da
   importação, "deseja validar?" —, cada um **conferido pelo efeito**: a tela
   `Importando a escrituração…` / `Validando a escrituração…` tem de aparecer.
   Não aparecendo, a automação para e diz o que falta. Importar sem validar
   não fecha o ciclo: o que interessa é o relatório de erros do PVA.

**A tecla só é enviada depois de conferir que a janela em primeiro plano é do
processo do PVA.** Não sendo, a função para e devolve o que falta fazer — com
o caminho já na área de transferência, terminar à mão é Ctrl+I, Ctrl+V, Enter.
Digitar às cegas numa janela que não é a esperada seria digitar dentro de
qualquer coisa que tenha roubado o foco.

Sem dependência de GUI e só no Windows; em outro sistema todas as funções
devolvem "não disponível" em vez de estourar.
"""

import os
import subprocess
import sys
import time

from sped_tables.infra import config

# ------------------------------------------------------------ instalações
# a raiz das instalações e a pasta de cada PVA vêm de `config`; aqui fica só
# o que é da automação (executável e títulos de janela)

# O `titulo` é o da janela principal, exatamente como o PVA o monta a partir
# do `titulo` do seu `aplicacao.properties`. Tem de ser o texto **inteiro**: a
# tela de abertura (splash) leva o nome curto da aplicação, aparece antes e
# não aceita foco — casar por "Sped Fiscal" pegava ela e a automação morria
# aos 6 segundos, com o PVA ainda carregando.
INSTALACOES = {
    "ICMS": {"exe": "SpedEFD.exe",
             "titulo": "Sped Fiscal - EFD ICMS/IPI - Sistema Público de "
                       "Escrituração Digital",
             "nome": "PVA do EFD ICMS/IPI"},
    "CONTRIB": {"exe": "SpedContribuicoes.exe",
                "titulo": "Sistema Público de Escrituração Digital - EFD "
                          "Contribuições",
                "nome": "PVA do EFD Contribuições"},
}

# tempo de espera, em segundos
ESPERA_JANELA = 120      # PVA subindo do zero (sobe um MySQL junto)
ESPERA_PRONTA = 120      # carregamento interno, DEPOIS de a janela aparecer
ESPERA_SELETOR = 45      # o seletor de arquivo, com o Ctrl+I sendo repetido
INTERVALO_ATALHO = 3.0   # de quanto em quanto tempo repetir o Ctrl+I
ESPERA_AVISO = 20        # o "Aviso" de confirmação aparecer
ESPERA_PROGRESSO = 30    # a tela de progresso aparecer depois do "sim"
ESPERA_IMPORTACAO = 1800 # a importação terminar (arquivo grande demora)

# Títulos que o PVA usa. O "Aviso" é o diálogo de confirmação
# (`solicitarConfirmacao`, sempre com esse título); os outros são as telas de
# progresso, e é a **aparição delas** que confirma que o "sim" foi aceito.
TITULO_AVISO = "aviso"
TITULO_ERRO = "erro"

# Telas que atravessam o caminho sem serem o que se espera. As de **progresso**
# só pedem paciência; as de **decisão** são do usuário e não são respondidas —
# a automação espera ele resolver e segue. A de atualizar tabelas é a mais
# comum: aparece na abertura, lista as tabelas obrigatórias à validação e não
# tem botão alcançável por Enter (o foco nasce na árvore).
TITULOS_PROGRESSO = ("aguarde", "transferindo")
TITULOS_DECISAO = ("atualizar tabelas", "mensagem")
ESPERA_DECISAO = 900     # quanto se espera o usuário responder
TITULO_IMPORTANDO = "importando a escrituração"
TITULO_VALIDANDO = "validando a escrituração"


def disponivel():
    """Só faz sentido no Windows — é onde o PVA roda."""
    return sys.platform == "win32"


def instalacao(layout, raiz=None):
    """`{"exe", "pasta", "titulo", "nome"}` do PVA do leiaute, ou None."""
    cfg = INSTALACOES.get(layout)
    if not cfg:
        return None
    pasta = config.pasta_pva(layout, raiz)
    exe = os.path.join(pasta, cfg["exe"])
    if not os.path.isfile(exe):
        return None
    return {"exe": exe, "pasta": pasta, "titulo": cfg["titulo"],
            "nome": cfg["nome"]}


# --------------------------------------------------------------- win32
# Estruturas e `argtypes` são definidos UMA vez, no import: criar o tipo dentro
# da função gera um tipo novo a cada chamada e o ctypes compara por identidade.
if disponivel():
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                   wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_ENUMPROC, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR,
                                       ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                 ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.IsIconic.restype = wintypes.BOOL
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.BringWindowToTop.argtypes = [wintypes.HWND]
    _user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD,
                                          wintypes.BOOL]
    _user32.AttachThreadInput.restype = wintypes.BOOL
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    _user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE,
                                    wintypes.DWORD, ctypes.c_void_p]
    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.EmptyClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _user32.SetClipboardData.restype = wintypes.HANDLE
    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    SW_RESTORE = 9
    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL, VK_I, VK_V, VK_RETURN, VK_ESCAPE = 0x11, 0x49, 0x56, 0x0D, 0x1B
    VK_F = 0x46                  # Escrituração Fiscal → Fechar


def _janelas(exigir_titulo=True):
    """`[(hwnd, titulo, pid)]` das janelas de topo visíveis.

    `exigir_titulo=False` inclui as sem título — um diálogo do Swing pode
    aparecer sem texto na barra, e é justamente ele que se quer detectar.
    """
    achadas = []

    def cb(hwnd, _lp):
        if not _user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        n = _user32.GetWindowTextW(hwnd, buf, 512)
        if exigir_titulo and n <= 0:
            return True
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        achadas.append((hwnd, buf.value, pid.value))
        return True

    _user32.EnumWindows(_ENUMPROC(cb), 0)
    return achadas


def _hwnds_do_processo(pid):
    """Janelas visíveis de um processo, com ou sem título."""
    return {h for h, _t, p in _janelas(exigir_titulo=False) if p == pid}


def janela(layout, raiz=None):
    """`(hwnd, pid)` da janela principal do PVA do leiaute, ou `(None, None)`.

    O casamento é pelo **título**, que o PVA monta com `nomeAplicacao` do seu
    `aplicacao.properties` ("Sped Fiscal - EFD ICMS/IPI" e "EFD
    Contribuições"). Janela de outro PVA não confunde: os títulos não se
    contêm.
    """
    inst = instalacao(layout, raiz)
    if not disponivel() or not inst:
        return None, None
    for hwnd, titulo, pid in _janelas():
        if inst["titulo"].lower() in titulo.lower():
            return hwnd, pid
    return None, None


def _copiar(texto):
    """Põe o texto na área de transferência (CF_UNICODETEXT)."""
    dados = ctypes.create_unicode_buffer(texto)
    tam = ctypes.sizeof(dados)
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, tam)
    if not h:
        return False
    p = _kernel32.GlobalLock(h)
    ctypes.memmove(p, dados, tam)
    _kernel32.GlobalUnlock(h)
    if not _user32.OpenClipboard(None):
        return False
    try:
        _user32.EmptyClipboard()
        return bool(_user32.SetClipboardData(CF_UNICODETEXT, h))
    finally:
        _user32.CloseClipboard()


def _focar(hwnd, pid, limite=15.0, cancelar=None):
    """Traz a janela do PVA para a frente. Devolve o hwnd que ficou lá, ou None.

    Duas armadilhas do Windows aqui:

    * **Só o processo dono do primeiro plano pode dar o primeiro plano a
      outro.** Quando quem chama é a nossa janela, recém-clicada pelo usuário,
      passa direto; fora disso o `SetForegroundWindow` é ignorado em silêncio.
      O contorno padrão é anexar a fila de entrada da nossa thread à da thread
      que está na frente (`AttachThreadInput`) durante a troca.
    * **Janela recém-criada recusa foco** enquanto a interface está sendo
      montada — daí insistir por alguns segundos.

    O sucesso é medido pelo **processo**, não pelo hwnd: se o PVA estiver com
    um diálogo aberto, quem vem para a frente é o diálogo, e é isso que o
    chamador precisa saber.
    """
    fim = time.time() + limite
    meu = _kernel32.GetCurrentThreadId()
    while time.time() < fim:
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, SW_RESTORE)
        frente = _user32.GetForegroundWindow()
        tid = _user32.GetWindowThreadProcessId(frente, None) if frente else 0
        anexou = bool(tid) and bool(_user32.AttachThreadInput(meu, tid, True))
        try:
            _user32.SetForegroundWindow(hwnd)
            _user32.BringWindowToTop(hwnd)
        finally:
            if anexou:
                _user32.AttachThreadInput(meu, tid, False)
        fg, fg_pid = _pid_do_primeiro_plano()
        if fg_pid == pid:
            return fg
        _dormir(0.3, cancelar)
    return None


def _pid_do_primeiro_plano():
    hwnd = _user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, pid.value


def _tecla(vk, ctrl=False):
    if ctrl:
        _user32.keybd_event(VK_CONTROL, 0, 0, None)
    _user32.keybd_event(vk, 0, 0, None)
    _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, None)
    if ctrl:
        _user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, None)
    time.sleep(0.15)


class Cancelado(Exception):
    """O usuário desistiu de esperar o PVA.

    É exceção e não retorno porque a espera acontece em meia dúzia de laços
    aninhados — devolver um código em cada um deles é convite a esquecer um,
    e esquecer um significa continuar mandando tecla para o PVA depois de o
    usuário ter cancelado.
    """


def _dormir(segundos, cancelar=None):
    """Espera cortada em fatias, olhando o pedido de cancelamento.

    Sem isto a interface ficava presa até o limite — e o limite da decisão do
    usuário é de 15 minutos, tempo em que o programa parecia travado.
    """
    fim = time.time() + segundos
    while True:
        if cancelar is not None and cancelar():
            raise Cancelado()
        resta = fim - time.time()
        if resta <= 0:
            return
        time.sleep(min(0.2, resta))


def _janela_com_titulo(pid, contem, limite, ausente=False, cancelar=None):
    """Espera uma janela do processo cujo título contenha `contem`.

    Com `ausente=True`, espera o contrário: que ela **suma**. Devolve o hwnd
    (ou True/False no modo ausente) — None/False quando estoura o tempo.
    """
    fim = time.time() + limite
    while time.time() < fim:
        achou = None
        for hwnd, titulo, p in _janelas(exigir_titulo=False):
            if p == pid and contem in (titulo or "").lower():
                achou = hwnd
                break
        if ausente and achou is None:
            return True
        if not ausente and achou is not None:
            return achou
        _dormir(0.4, cancelar)
    return False if ausente else None


def _confirmar_aviso(pid, titulo_efeito, limite_aviso=ESPERA_AVISO,
                     limite_efeito=ESPERA_PROGRESSO, progresso=None,
                     cancelar=None):
    """Responde "sim" a um "Aviso" do PVA — e confere pelo efeito.

    O diálogo é um `JOptionPane` (`ExibirMensagem.solicitarConfirmacao`), cujo
    botão padrão responde ao Enter. Como "apertei Enter" não prova nada, o
    sucesso é medido pela tela de progresso que **tem de** aparecer em
    seguida: `Importando a escrituração…` ou `Validando a escrituração…`. Não
    aparecendo, a automação para e diz o que falta — é o que impede responder
    no escuro a um aviso que fosse outra coisa.

    Devolve o hwnd da tela de progresso, ou None.
    """
    # a atualização de tabelas costuma entrar aqui, entre o Enter no seletor
    # e o pedido de confirmação
    _esperar_livre(pid, progresso=progresso, cancelar=cancelar)
    aviso = _janela_com_titulo(pid, TITULO_AVISO, limite_aviso,
                               cancelar=cancelar)
    if aviso is None:
        return None
    if _focar(aviso, pid, limite=5.0, cancelar=cancelar) != aviso:
        return None
    _tecla(VK_RETURN)
    return _janela_com_titulo(pid, titulo_efeito, limite_efeito,
                              cancelar=cancelar)


def _esperar_pronta(hwnd, pid, limite=ESPERA_PRONTA, sossego=1.0,
                    progresso=None, cancelar=None):
    """Espera o PVA terminar o **carregamento interno**.

    A janela principal aparece bem antes de aceitar atalhos: enquanto carrega,
    o processo mantém uma segunda janela — a barra de progresso. Medido numa
    partida a frio: janela principal aos 4 s, atalho só aceito aos 11,9 s,
    exatamente quando a contagem de janelas caiu de 2 para 1. Os dois Ctrl+I
    enviados no meio foram **engolidos**, não enfileirados, o que é o que
    torna seguro repetir o atalho depois.

    Devolve True quando sobra só a janela principal e ela se mantém assim.
    """
    fim = time.time() + limite
    desde = None
    while time.time() < fim:
        extras = [(h, t) for h, t, p in _janelas(exigir_titulo=False)
                  if p == pid and h != hwnd]
        espera = _classificar(extras)
        if espera:
            desde = None
            if progresso:
                progresso(espera)
        elif extras:
            # janela esquecida ("Resultado da Importação", "Aviso", "Erro")
            # não é carregamento: esperar por ela queimava os 2 minutos
            # inteiros antes de dizer que o PVA estava ocupado
            return True
        elif desde is None:
            desde = time.time()
        elif time.time() - desde >= sossego:
            return True
        _dormir(0.3, cancelar)
    return False


def _classificar(extras):
    """Mensagem de espera para as janelas atravessadas, ou "" se não há.

    Devolver texto quer dizer "continue esperando"; devolver "" quer dizer
    que nada conhecido está no caminho.
    """
    for _h, titulo in extras:
        t = (titulo or "").lower()
        if not t or any(x in t for x in TITULOS_PROGRESSO):
            return ("Aguardando o PVA terminar de carregar…" if "transfer"
                    not in t else "O PVA está transferindo tabelas…")
        if any(x in t for x in TITULOS_DECISAO):
            return ("O PVA está pedindo uma resposta (%s) — responda na tela "
                    "dele que a importação segue." % (titulo or "").strip())
    return ""


def _esperar_livre(pid, limite=ESPERA_DECISAO, progresso=None,
                   cancelar=None):
    """Espera sair do caminho o que for progresso ou decisão do usuário.

    A atualização de tabelas entra bem no meio da importação: o PVA pergunta,
    baixa e ainda avisa que deu certo. Nada disso é respondido aqui — são
    decisões do usuário —, mas esperar por elas é o que faz a automação
    retomar sozinha em vez de dizer que não conseguiu.
    """
    fim = time.time() + limite
    while time.time() < fim:
        extras = [(h, t) for h, t, p in _janelas(exigir_titulo=False)
                  if p == pid]
        espera = _classificar(extras)
        if not espera:
            return True
        if progresso:
            progresso(espera)
        _dormir(0.5, cancelar)
    return False


def _esperar_janela(layout, raiz, limite, progresso=None, cancelar=None):
    fim = time.time() + limite
    while time.time() < fim:
        hwnd, pid = janela(layout, raiz)
        if hwnd:
            return hwnd, pid
        if progresso:
            progresso("Abrindo o PVA…")
        _dormir(1.0, cancelar)
    return None, None


def abrir(caminho, layout, importar=True, confirmar=True, validar=True,
          raiz=None, progresso=None, espera_janela=ESPERA_JANELA,
          cancelar=None):
    """Abre o PVA do leiaute, importa `caminho` e manda validar.

    `importar=False` só abre (ou traz para a frente) o PVA. `confirmar=False`
    cola o caminho no seletor e para ali. `validar=False` importa e não pede a
    validação — importar sem validar, porém, não fecha o ciclo: o que
    interessa é o relatório de erros do PVA.

    As duas confirmações que o PVA pede ("deseja importar?" e "deseja
    validar?") são respondidas e **conferidas pelo efeito**: a tela de
    progresso correspondente tem de aparecer. Não aparecendo, a função para e
    diz o que falta fazer.

    `cancelar` é uma função sem argumentos consultada durante as esperas;
    devolvendo verdadeiro, a automação para onde está e nenhuma tecla a mais é
    enviada. É o que permite à interface oferecer um botão de cancelar em vez
    de ficar presa até o limite.

    Devolve `{"estado", "mensagem", "aberto_agora", "tentativas"}`, com
    `estado` em: `validando`, `importado`, `importando` (ainda rodando),
    `confirmar` (o caminho chegou, a confirmação não), `caminho_colado`,
    `pva_aberto`, `pva_ocupado`, `cancelado`, `sem_pva`, `sem_arquivo` ou
    `indisponivel`.
    """
    if not disponivel():
        return {"estado": "indisponivel", "aberto_agora": False,
                "mensagem": "Abrir o PVA automaticamente só funciona no "
                            "Windows."}
    if not os.path.isfile(caminho):
        return {"estado": "sem_arquivo", "aberto_agora": False,
                "mensagem": "Salve o arquivo antes de mandá-lo para o PVA."}
    inst = instalacao(layout, raiz)
    if not inst:
        return {"estado": "sem_pva", "aberto_agora": False,
                "mensagem": "Não encontrei o %s em %s."
                            % (INSTALACOES.get(layout, {}).get("nome", "PVA"),
                               raiz or config.raiz_pva())}

    try:
        return _abrir(caminho, layout, importar, confirmar, validar, raiz,
                      progresso, espera_janela, cancelar, inst)
    except Cancelado:
        return {"estado": "cancelado", "aberto_agora": False,
                "mensagem": "Espera cancelada. O caminho do arquivo está na "
                            "área de transferência — no %s, Ctrl+I, Ctrl+V, "
                            "Enter." % inst["nome"]}


def _abrir(caminho, layout, importar, confirmar, validar, raiz, progresso,
           espera_janela, cancelar, inst):
    """O corpo de `abrir`, separado só para o cancelamento ter um lugar só
    onde ser capturado."""
    hwnd, pid = janela(layout, raiz)
    aberto_agora = False
    if not hwnd:
        # trava de instância única: só executa quando não há janela
        subprocess.Popen([inst["exe"]], cwd=inst["pasta"],
                         close_fds=True)
        aberto_agora = True
        hwnd, pid = _esperar_janela(layout, raiz, espera_janela, progresso,
                                    cancelar)
        if not hwnd:
            return {"estado": "pva_aberto", "aberto_agora": True,
                    "mensagem": "O %s foi iniciado, mas a janela não apareceu "
                                "a tempo. Quando abrir, use Ctrl+I e cole o "
                                "caminho (já está na área de transferência)."
                                % inst["nome"]}

    def saida_simples(estado, msg):
        return {"estado": estado, "aberto_agora": aberto_agora,
                "mensagem": msg}

    _copiar(caminho)
    # o carregamento interno vem DEPOIS de a janela aparecer, e enquanto ele
    # roda o atalho é ignorado — esperar aqui é o que faz a importação pegar
    if aberto_agora or len(_hwnds_do_processo(pid)) > 1:
        _esperar_pronta(hwnd, pid, progresso=progresso, cancelar=cancelar)
    frente = _focar(hwnd, pid, cancelar=cancelar)
    if frente is None:
        return {"estado": "pva_aberto", "aberto_agora": aberto_agora,
                "mensagem": "Não consegui trazer o %s para a frente. Vá até "
                            "ele e faça Ctrl+I, Ctrl+V, Enter — o caminho já "
                            "está na área de transferência." % inst["nome"]}
    if not importar:
        return {"estado": "pva_aberto", "aberto_agora": aberto_agora,
                "mensagem": "%s em primeiro plano. O caminho do arquivo está "
                            "na área de transferência." % inst["nome"]}
    if frente != hwnd:
        # o PVA está com um diálogo aberto; o Ctrl+I não chega ao menu
        return {"estado": "pva_ocupado", "aberto_agora": aberto_agora,
                "mensagem": "O %s está com uma janela aberta esperando "
                            "resposta. Feche-a e tente de novo — ou faça "
                            "Ctrl+I, Ctrl+V, Enter, que o caminho já está na "
                            "área de transferência." % inst["nome"]}

    # O seletor de arquivo é uma janela NOVA do mesmo processo. Detectar por
    # "apareceu janela nova" e não por "está em primeiro plano": no segundo
    # critério, qualquer janela que roube o foco no meio derruba a detecção de
    # uma tela que abriu direitinho.
    #
    # O Ctrl+I é **repetido** até o seletor aparecer: a espera pelo
    # carregamento cobre o caso conhecido, mas atalho engolido não deixa
    # rastro, e insistir custa pouco — teclado ignorado não enfileira.
    alvo = None
    tentativas = 0
    fim = time.time() + ESPERA_SELETOR
    while time.time() < fim and alvo is None:
        if _focar(hwnd, pid, limite=3.0, cancelar=cancelar) != hwnd:
            break
        antes = _hwnds_do_processo(pid)
        if tentativas:
            # O atalho não pegou na primeira. A causa conhecida é o PVA estar
            # com uma **escrituração aberta (em edição)**: nesse estado ele
            # desabilita *Nova → Importar*, e o Ctrl+I não faz nada — era o
            # que travava o EFD ICMS/IPI de quem deixa o PVA aberto no
            # arquivo do mês. Ctrl+F fecha a escrituração (ela continua no
            # banco do PVA; reabrir é Ctrl+A) e o Importar volta a valer.
            _tecla(VK_F, ctrl=True)
            time.sleep(0.8)
            if _hwnds_do_processo(pid) - antes:
                return saida_simples(
                    "pva_ocupado",
                    "O %s está com uma escrituração aberta e pediu "
                    "confirmação para fechá-la. Responda por lá e repita — o "
                    "caminho já está na área de transferência." % inst["nome"])
            antes = _hwnds_do_processo(pid)
        _tecla(VK_I, ctrl=True)      # Escrituração → Nova → Importar
        tentativas += 1
        espera = time.time() + INTERVALO_ATALHO
        while time.time() < espera:
            novas = _hwnds_do_processo(pid) - antes
            if novas:
                alvo = max(novas)
                break
            _dormir(0.25, cancelar)
    if alvo is None:
        return saida_simples(
            "pva_aberto",
            "O %s está aberto, mas a janela de importação não apareceu — o "
            "atalho Ctrl+I não foi aceito. Veja se há escrituração aberta ou "
            "diálogo esperando resposta por lá; o caminho já está na área de "
            "transferência (Ctrl+I, Ctrl+V, Enter)." % inst["nome"])

    # nada é teclado antes de a janela nova estar mesmo na frente
    if _focar(alvo, pid, cancelar=cancelar) != alvo:
        return {"estado": "pva_aberto", "aberto_agora": aberto_agora,
                "mensagem": "A janela de importação do %s abriu, mas não ficou "
                            "em primeiro plano. Cole o caminho lá (Ctrl+V) — "
                            "ele já está na área de transferência."
                            % inst["nome"]}
    time.sleep(0.4)                  # o foco cai no campo "Nome do arquivo:"
    _tecla(VK_V, ctrl=True)
    if not confirmar:
        return {"estado": "caminho_colado", "aberto_agora": aberto_agora,
                "tentativas": tentativas,
                "mensagem": "Caminho colado na janela de importação do %s — "
                            "confirme por lá." % inst["nome"]}
    _tecla(VK_RETURN)

    def saida(estado, msg):
        return {"estado": estado, "aberto_agora": aberto_agora,
                "tentativas": tentativas, "mensagem": msg}

    # ---- "Deseja importar?" ------------------------------------------
    if progresso:
        progresso("Confirmando a importação…")
    importando = _confirmar_aviso(pid, TITULO_IMPORTANDO,
                                  progresso=progresso, cancelar=cancelar)
    if importando is None:
        return saida("confirmar",
                     "O caminho foi entregue ao %s, mas não consegui "
                     "confirmar a importação. Responda ao aviso na tela do "
                     "PVA." % inst["nome"])
    if progresso:
        progresso("Importando no %s…" % inst["nome"])
    if not _janela_com_titulo(pid, TITULO_IMPORTANDO, ESPERA_IMPORTACAO,
                              ausente=True, cancelar=cancelar):
        return saida("importando",
                     "A importação no %s passou de %d minutos e continua "
                     "rodando; acompanhe por lá." % (inst["nome"],
                                                     ESPERA_IMPORTACAO // 60))
    # A tela de progresso some tanto no sucesso quanto na recusa. Quem separa
    # os dois é o "Erro" que o PVA abre quando o arquivo tem problema de
    # estrutura: sem esta checagem, arquivo recusado era anunciado como
    # importado — foi o que aconteceu com um SPED ICMS cheio de `NULL`.
    if _janela_com_titulo(pid, TITULO_ERRO, 3.0) is not None:
        return saida("erro_pva",
                     "O %s **recusou** a importação: a mensagem está na tela "
                     "dele. Erro de estrutura no arquivo (tipo ou tamanho de "
                     "campo) é o motivo mais comum — o Diagnóstico daqui "
                     "aponta esses campos." % inst["nome"])
    if not validar:
        return saida("importado",
                     "Arquivo importado no %s." % inst["nome"])

    # ---- "Deseja validar?" -------------------------------------------
    if progresso:
        progresso("Confirmando a validação…")
    validando = _confirmar_aviso(pid, TITULO_VALIDANDO,
                                 progresso=progresso, cancelar=cancelar)
    if validando is None:
        return saida("importado",
                     "Arquivo importado no %s. O aviso da validação não foi "
                     "confirmado — mande verificar as pendências por lá "
                     "(Ctrl+V)." % inst["nome"])
    return saida("validando",
                 "Arquivo importado e validação em andamento no %s — o "
                 "relatório de erros aparece por lá." % inst["nome"])

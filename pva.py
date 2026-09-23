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
3. copiar o caminho do arquivo para a área de transferência;
4. mandar Ctrl+I, esperar o seletor de arquivo e mandar Ctrl+V e Enter.

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

# ------------------------------------------------------------ instalações
RAIZ_PVA = r"C:\Arquivos de Programas RFB\Programas SPED"

# O `titulo` é o da janela principal, exatamente como o PVA o monta a partir
# do `titulo` do seu `aplicacao.properties`. Tem de ser o texto **inteiro**: a
# tela de abertura (splash) leva o nome curto da aplicação, aparece antes e
# não aceita foco — casar por "Sped Fiscal" pegava ela e a automação morria
# aos 6 segundos, com o PVA ainda carregando.
INSTALACOES = {
    "ICMS": {"pasta": "Fiscal", "exe": "SpedEFD.exe",
             "titulo": "Sped Fiscal - EFD ICMS/IPI - Sistema Público de "
                       "Escrituração Digital",
             "nome": "PVA do EFD ICMS/IPI"},
    "CONTRIB": {"pasta": "EFD-Contribuicoes", "exe": "SpedContribuicoes.exe",
                "titulo": "Sistema Público de Escrituração Digital - EFD "
                          "Contribuições",
                "nome": "PVA do EFD Contribuições"},
}

# tempo de espera, em segundos
ESPERA_JANELA = 120      # PVA subindo do zero (sobe um MySQL junto)
ESPERA_SELETOR = 20      # o seletor de arquivo depois do Ctrl+I


def disponivel():
    """Só faz sentido no Windows — é onde o PVA roda."""
    return sys.platform == "win32"


def instalacao(layout, raiz=None):
    """`{"exe", "pasta", "titulo", "nome"}` do PVA do leiaute, ou None."""
    cfg = INSTALACOES.get(layout)
    if not cfg:
        return None
    pasta = os.path.join(raiz or RAIZ_PVA, cfg["pasta"])
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


def _focar(hwnd, pid, limite=15.0):
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
        time.sleep(0.3)
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


def _esperar_janela(layout, raiz, limite, progresso=None):
    fim = time.time() + limite
    while time.time() < fim:
        hwnd, pid = janela(layout, raiz)
        if hwnd:
            return hwnd, pid
        if progresso:
            progresso(int(fim - time.time()))
        time.sleep(1.0)
    return None, None


def abrir(caminho, layout, importar=True, confirmar=True, raiz=None,
          progresso=None, espera_janela=ESPERA_JANELA):
    """Abre o PVA do leiaute e leva `caminho` até a importação.

    `importar=False` só abre (ou traz para a frente) o PVA. `confirmar=False`
    cola o caminho no seletor mas **não** dá Enter, deixando a confirmação com
    o usuário.

    Devolve `{"estado", "mensagem", "aberto_agora"}`, com `estado` em:
    `importando`, `caminho_colado`, `pva_aberto` (não deu para automatizar o
    resto), `sem_pva`, `sem_arquivo` ou `indisponivel`.
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
                               raiz or RAIZ_PVA)}

    hwnd, pid = janela(layout, raiz)
    aberto_agora = False
    if not hwnd:
        # trava de instância única: só executa quando não há janela
        subprocess.Popen([inst["exe"]], cwd=inst["pasta"],
                         close_fds=True)
        aberto_agora = True
        hwnd, pid = _esperar_janela(layout, raiz, espera_janela, progresso)
        if not hwnd:
            return {"estado": "pva_aberto", "aberto_agora": True,
                    "mensagem": "O %s foi iniciado, mas a janela não apareceu "
                                "a tempo. Quando abrir, use Ctrl+I e cole o "
                                "caminho (já está na área de transferência)."
                                % inst["nome"]}

    _copiar(caminho)
    frente = _focar(hwnd, pid)
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

    antes = _hwnds_do_processo(pid)
    _tecla(VK_I, ctrl=True)          # Escrituração → Nova → Importar

    # O seletor de arquivo é uma janela NOVA do mesmo processo. Detectar por
    # "apareceu janela nova" e não por "está em primeiro plano": no segundo
    # critério, qualquer janela que roube o foco no meio derruba a detecção de
    # uma tela que abriu direitinho.
    alvo = None
    fim = time.time() + ESPERA_SELETOR
    while time.time() < fim:
        novas = _hwnds_do_processo(pid) - antes
        if novas:
            alvo = max(novas)
            break
        time.sleep(0.3)
    if alvo is None:
        return {"estado": "pva_aberto", "aberto_agora": aberto_agora,
                "mensagem": "O %s está aberto, mas a janela de importação não "
                            "apareceu. Faça Ctrl+I e cole o caminho (Ctrl+V), "
                            "que já está na área de transferência."
                            % inst["nome"]}

    # nada é teclado antes de a janela nova estar mesmo na frente
    if _focar(alvo, pid) != alvo:
        return {"estado": "pva_aberto", "aberto_agora": aberto_agora,
                "mensagem": "A janela de importação do %s abriu, mas não ficou "
                            "em primeiro plano. Cole o caminho lá (Ctrl+V) — "
                            "ele já está na área de transferência."
                            % inst["nome"]}
    time.sleep(0.4)                  # o foco cai no campo "Nome do arquivo:"
    _tecla(VK_V, ctrl=True)
    if not confirmar:
        return {"estado": "caminho_colado", "aberto_agora": aberto_agora,
                "mensagem": "Caminho colado na janela de importação do %s — "
                            "confirme por lá." % inst["nome"]}
    _tecla(VK_RETURN)
    return {"estado": "importando", "aberto_agora": aberto_agora,
            "mensagem": "Importação iniciada no %s." % inst["nome"]}

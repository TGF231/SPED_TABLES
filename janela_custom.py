# -*- coding: utf-8 -*-
"""Barra de título própria **sem** abrir mão do comportamento nativo.

O caminho fácil seria `Qt.FramelessWindowHint`: a moldura some e pronto. O
problema é que, para o Windows, a janela deixa de ser uma janela — vão junto o
**Aero Snap** (arrastar para a borda e encaixar), o redimensionamento pelas
bordas, o duplo clique para maximizar, a sombra e o Snap Layouts do Win11.
Num editor de SPED isso pesa: o arquivo é quase sempre conferido lado a lado
com o PVA ou com o Excel.

A abordagem aqui é a mesma do VS Code, do Chrome e do Discord: **manter** os
estilos nativos da janela (WS_THICKFRAME, WS_CAPTION) e apenas interceptar três
mensagens:

* **WM_NCCALCSIZE** — devolve a área de cliente ocupando a janela inteira, de
  modo que o Qt desenhe por cima de onde ficava a legenda. O Windows continua
  achando que existe moldura, e é por isso que o Snap sobrevive.
* **WM_NCHITTEST** — como a área não-cliente sumiu, somos nós que dizemos o que
  é borda, canto e faixa de arrasto. Devolver HTCAPTION na faixa da barra dá de
  graça o arrastar, o duplo clique para maximizar e o menu de sistema.
* **WM_GETMINMAXINFO** — maximizar uma janela sem moldura cobriria a barra de
  tarefas; aqui o tamanho é limitado à área de trabalho do monitor **daquela**
  janela (importante com dois monitores de resoluções diferentes).

Fora do Windows — ou se qualquer passo falhar — `aplicar()` devolve False e o
programa segue com a barra nativa. Uma barra de título é enfeite: nunca pode
impedir o aplicativo de abrir.

Estado: **opcional**. Ligue com **SPED_TABLES_BARRA_CUSTOM=1**; sem isso o
programa usa a barra do Windows. A interceptação de mensagens nativas não pôde
ser validada em ambiente automatizado (mostrar uma janela real fora de uma
sessão interativa não funciona), e uma falha nativa derruba o processo sem
traceback — por isso o padrão conservador.
"""

import ctypes.wintypes
import os
import sys

# ------------------------------------------------------- mensagens e códigos
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_GETMINMAXINFO = 0x0024

HTCLIENT = 1
HTCAPTION = 2
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

MONITOR_DEFAULTTONEAREST = 2

# espessura da faixa sensível ao redimensionamento, em pixels lógicos
BORDA = 6


# Enquanto a interceptação não for validada em uso real, a barra própria é
# **opcional**: ligue com SPED_TABLES_BARRA_CUSTOM=1. O motivo é conservador —
# um erro no tratamento de mensagens nativas derruba o processo sem traceback,
# e este é um programa que edita arquivos que vão para a Receita. Depois de
# confirmada em uso, basta inverter o padrão aqui.
VARIAVEL = "SPED_TABLES_BARRA_CUSTOM"


def disponivel():
    """Windows, ctypes utilizável e barra própria habilitada."""
    if sys.platform != "win32":
        return False
    if os.environ.get(VARIAVEL) != "1":
        return False
    try:
        import ctypes  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _structs():
    import ctypes
    from ctypes import wintypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MINMAXINFO(ctypes.Structure):
        _fields_ = [("ptReserved", POINT), ("ptMaxSize", POINT),
                    ("ptMaxPosition", POINT), ("ptMinTrackSize", POINT),
                    ("ptMaxTrackSize", POINT)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

    class NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", RECT * 3), ("lppos", ctypes.c_void_p)]

    class MARGINS(ctypes.Structure):
        _fields_ = [("cxLeftWidth", ctypes.c_int),
                    ("cxRightWidth", ctypes.c_int),
                    ("cyTopHeight", ctypes.c_int),
                    ("cyBottomHeight", ctypes.c_int)]

    return POINT, RECT, MINMAXINFO, MONITORINFO, NCCALCSIZE_PARAMS, MARGINS


def _api():
    """Funções do Win32 com assinatura declarada.

    Sem `argtypes`, o ctypes converte inteiros para C int (32 bits) e o HWND
    de um Windows 64-bit é truncado — a chamada passa a operar sobre um handle
    inválido, com resultado imprevisível.
    """
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    d = ctypes.windll.dwmapi
    _P, _R, _MMI, _MI, _NC, MARGINS = _structs()

    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_R)]
    u.GetWindowRect.restype = wintypes.BOOL
    u.IsZoomed.argtypes = [wintypes.HWND]
    u.IsZoomed.restype = wintypes.BOOL
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, ctypes.c_int,
                               ctypes.c_uint]
    u.SetWindowPos.restype = wintypes.BOOL
    u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    u.MonitorFromWindow.restype = wintypes.HANDLE
    u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MI)]
    u.GetMonitorInfoW.restype = wintypes.BOOL
    d.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND,
                                               ctypes.POINTER(MARGINS)]
    d.DwmExtendFrameIntoClientArea.restype = ctypes.c_long
    return u, d, MARGINS


def aplicar(janela):
    """Prepara a janela para a barra própria. Devolve True se conseguiu.

    Deve ser chamada **depois** de a janela existir de fato (primeiro
    showEvent): forçar `winId()` no meio da construção do QMainWindow cria a
    janela nativa cedo demais, e o SetWindowPos com FRAMECHANGED reentra na
    montagem do Qt.

    Não altera window flags: os estilos nativos precisam continuar lá, senão o
    Snap e o redimensionamento vão embora junto.
    """
    if not disponivel():
        return False
    try:
        import ctypes
        u, d, MARGINS = _api()
        hwnd = ctypes.wintypes.HWND(int(janela.winId()))
        # sombra: sem isso a janela fica "chapada" contra o fundo
        margens = MARGINS(1, 1, 1, 1)
        d.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margens))
        # SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
        u.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0020)
        return True
    except Exception:  # noqa: BLE001
        return False


def _margem_moldura(hwnd):
    """Espessura da moldura que o Windows usa quando a janela é maximizada."""
    import ctypes
    u = ctypes.windll.user32
    try:
        u.GetDpiForWindow.argtypes = [ctypes.wintypes.HWND]
        u.GetDpiForWindow.restype = ctypes.c_uint
        dpi = u.GetDpiForWindow(hwnd)
        if dpi:
            larg = u.GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi) + \
                u.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
            alt = u.GetSystemMetricsForDpi(SM_CYSIZEFRAME, dpi) + \
                u.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
            return larg, alt
    except Exception:  # noqa: BLE001
        pass
    larg = u.GetSystemMetrics(SM_CXSIZEFRAME) + \
        u.GetSystemMetrics(SM_CXPADDEDBORDER)
    alt = u.GetSystemMetrics(SM_CYSIZEFRAME) + \
        u.GetSystemMetrics(SM_CXPADDEDBORDER)
    return larg, alt


def tratar(janela, mensagem_ptr, altura_barra, ponto_arrastavel=None):
    """Trata as mensagens nativas. Devolve (tratado, resultado).

    `ponto_arrastavel(x, y)` recebe coordenadas **locais** da janela e informa
    se ali a barra pode ser arrastada — falso sobre os botões, senão ninguém
    conseguiria clicar em fechar.
    """
    if not disponivel():
        return False, 0
    import ctypes
    from ctypes import wintypes

    POINT, RECT, MINMAXINFO, MONITORINFO, NCCALC, _M = _structs()

    class MSG(ctypes.Structure):
        _fields_ = [("hWnd", wintypes.HWND), ("message", wintypes.UINT),
                    ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p),
                    ("time", wintypes.DWORD), ("pt", POINT)]

    msg = ctypes.cast(int(mensagem_ptr), ctypes.POINTER(MSG)).contents
    hwnd = msg.hWnd

    # ------------------------------------------------------ WM_NCCALCSIZE
    if msg.message == WM_NCCALCSIZE and msg.wParam:
        u, _d, _M = _api()
        maximizada = bool(u.IsZoomed(hwnd))
        if maximizada:
            # maximizada, a janela nativa extrapola a área útil; sem encolher,
            # as bordas (e parte do conteúdo) ficariam fora da tela
            p = ctypes.cast(msg.lParam, ctypes.POINTER(NCCALC)).contents
            larg, alt = _margem_moldura(hwnd)
            p.rgrc[0].left += larg
            p.rgrc[0].right -= larg
            p.rgrc[0].top += alt
            p.rgrc[0].bottom -= alt
        # 0 = a área de cliente ocupa o retângulo proposto (sem legenda)
        return True, 0

    # -------------------------------------------------------- WM_NCHITTEST
    if msg.message == WM_NCHITTEST:
        lp = int(msg.lParam or 0)
        # coordenadas de tela vêm empacotadas em 16 bits com sinal
        x = ctypes.c_short(lp & 0xFFFF).value
        y = ctypes.c_short((lp >> 16) & 0xFFFF).value
        u, _d, _M = _api()
        r = RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        escala = janela.devicePixelRatioF() or 1.0
        borda = int(BORDA * escala)

        if not bool(u.IsZoomed(hwnd)):
            esq = x < r.left + borda
            dir_ = x >= r.right - borda
            topo = y < r.top + borda
            base = y >= r.bottom - borda
            if topo and esq:
                return True, HTTOPLEFT
            if topo and dir_:
                return True, HTTOPRIGHT
            if base and esq:
                return True, HTBOTTOMLEFT
            if base and dir_:
                return True, HTBOTTOMRIGHT
            if esq:
                return True, HTLEFT
            if dir_:
                return True, HTRIGHT
            if topo:
                return True, HTTOP
            if base:
                return True, HTBOTTOM

        # faixa da barra de título: arrastar, duplo clique e menu de sistema
        # saem de graça do HTCAPTION
        local_x = int((x - r.left) / escala)
        local_y = int((y - r.top) / escala)
        if 0 <= local_y < altura_barra:
            if ponto_arrastavel is None or ponto_arrastavel(local_x, local_y):
                return True, HTCAPTION
        return True, HTCLIENT

    # ---------------------------------------------------- WM_GETMINMAXINFO
    if msg.message == WM_GETMINMAXINFO:
        try:
            u, _d, _M = _api()
            monitor = u.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            u.GetMonitorInfoW(monitor, ctypes.byref(info))
            trabalho, tela = info.rcWork, info.rcMonitor
            mmi = ctypes.cast(msg.lParam, ctypes.POINTER(MINMAXINFO)).contents
            # tamanho e posição de "maximizada" limitados à área de trabalho,
            # para a barra de tarefas continuar visível
            mmi.ptMaxSize.x = trabalho.right - trabalho.left
            mmi.ptMaxSize.y = trabalho.bottom - trabalho.top
            mmi.ptMaxPosition.x = trabalho.left - tela.left
            mmi.ptMaxPosition.y = trabalho.top - tela.top
            mmi.ptMaxTrackSize.x = mmi.ptMaxSize.x
            mmi.ptMaxTrackSize.y = mmi.ptMaxSize.y
            return True, 0
        except Exception:  # noqa: BLE001
            return False, 0

    return False, 0

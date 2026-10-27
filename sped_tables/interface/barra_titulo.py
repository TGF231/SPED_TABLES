# -*- coding: utf-8 -*-
"""Barra de título própria (os ganchos nativos estão em `janela_custom`)."""

import os

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from sped_tables.infra import dados
from sped_tables.interface import tema_tokens as megui
from sped_tables.version import APP_NAME


class BarraTitulo(QWidget):
    """Barra de título do aplicativo, no lugar da barra do Windows.

    A janela continua nativa (ver `janela_custom`): esta barra só desenha. O
    arrasto, o duplo clique para maximizar e o menu de sistema são resolvidos
    pelo Windows, porque o WM_NCHITTEST devolve HTCAPTION na faixa dela — é
    por isso que não há aqui nenhum mousePressEvent para arrastar a janela.

    Além do título, mostra o que o usuário de SPED precisa saber sem procurar:
    **empresa e período** do arquivo aberto e se **há alterações não salvas** —
    hoje apenas um asterisco no fim do título, fácil de passar batido.
    """

    ALTURA = megui.LAYOUT["barraTitulo"]

    # O Windows 10/11 traz "Segoe MDL2 Assets", a fonte que o próprio sistema
    # usa nos botões de janela: com ela os três glifos têm o mesmo peso,
    # tamanho e alinhamento óptico. Misturar caracteres de fontes diferentes
    # (– □ ✕) dava um minimizar fino, um maximizar alto e um fechar grosso.
    FONTE_ICONES = "Segoe MDL2 Assets"
    GLIFOS = {
        "mdl2": {"min": "\uE921", "max": "\uE922", "restaurar": "\uE923",
                 "fechar": "\uE8BB"},
        # reserva para sistemas sem a fonte (ou fora do Windows)
        "texto": {"min": "\u2013", "max": "\u25a1", "restaurar": "\u2750",
                  "fechar": "\u2715"},
    }

    @staticmethod
    def _detectar_fonte():
        try:
            from PyQt6.QtGui import QFontDatabase
            if BarraTitulo.FONTE_ICONES in QFontDatabase.families():
                return "mdl2"
        except Exception:  # noqa: BLE001
            pass
        return "texto"

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self._fonte_icones = self._detectar_fonte()
        self.setObjectName("barraTitulo")
        self.setFixedHeight(self.ALTURA)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(8)

        self.lbl_icone = QLabel()
        cam = dados.recurso("icon.ico")
        if os.path.exists(cam):
            self.lbl_icone.setPixmap(QIcon(cam).pixmap(18, 18))
        lay.addWidget(self.lbl_icone)

        self.lbl_app = QLabel(APP_NAME)
        self.lbl_app.setProperty("role", "tituloApp")
        lay.addWidget(self.lbl_app)

        self.lbl_ctx = QLabel("")
        self.lbl_ctx.setProperty("role", "tituloCtx")
        lay.addWidget(self.lbl_ctx)

        self.lbl_alterado = QLabel("")
        self.lbl_alterado.setProperty("role", "aviso")
        lay.addWidget(self.lbl_alterado)

        lay.addStretch(1)

        self.botoes = []
        for nome, slot in (("min", self.janela.showMinimized),
                           ("max", self._alternar_maximizada),
                           ("fechar", self.janela.close)):
            b = QToolButton(self)
            b.setObjectName("btn_%s" % nome)
            b.setText(self.GLIFOS[self._fonte_icones][nome])
            # a propriedade escolhe a regra de fonte na folha de estilo
            b.setProperty("iconfont", self._fonte_icones)
            b.setFixedSize(46, self.ALTURA)
            b.clicked.connect(slot)
            lay.addWidget(b)
            self.botoes.append(b)
        self.btn_max = self.botoes[1]

    def _alternar_maximizada(self):
        if self.janela.isMaximized():
            self.janela.showNormal()
        else:
            self.janela.showMaximized()
        self.sincronizar()

    def sincronizar(self, contexto=None, alterado=None):
        """Atualiza contexto (empresa · período · leiaute) e o indicador."""
        if contexto is not None:
            self.lbl_ctx.setText(contexto)
        if alterado is not None:
            self.lbl_alterado.setText("\u25cf alterações não salvas"
                                      if alterado else "")
        glifos = self.GLIFOS[self._fonte_icones]
        self.btn_max.setText(glifos["restaurar"] if self.janela.isMaximized()
                             else glifos["max"])

    def area_arrastavel(self, x, y):
        """Falso sobre os botões — senão o Windows engoliria o clique.

        O WM_NCHITTEST pergunta isto antes de devolver HTCAPTION: tudo que for
        HTCAPTION é tratado como legenda e nunca chega ao widget.
        """
        for b in self.botoes:
            g = b.geometry()
            if g.left() <= x <= g.right() and g.top() <= y <= g.bottom():
                return False
        return True

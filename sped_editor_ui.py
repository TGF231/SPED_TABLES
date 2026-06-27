# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sped_editor.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QMenuBar,
    QSizePolicy, QStatusBar, QTabWidget, QToolBar,
    QVBoxLayout, QWidget)

class Ui_JanelaPrincipal(object):
    def setupUi(self, JanelaPrincipal):
        if not JanelaPrincipal.objectName():
            JanelaPrincipal.setObjectName(u"JanelaPrincipal")
        JanelaPrincipal.resize(1200, 760)
        self.act_abrir = QAction(JanelaPrincipal)
        self.act_abrir.setObjectName(u"act_abrir")
        self.act_salvar = QAction(JanelaPrincipal)
        self.act_salvar.setObjectName(u"act_salvar")
        self.act_salvar_como = QAction(JanelaPrincipal)
        self.act_salvar_como.setObjectName(u"act_salvar_como")
        self.act_sair = QAction(JanelaPrincipal)
        self.act_sair.setObjectName(u"act_sair")
        self.act_importar_xml = QAction(JanelaPrincipal)
        self.act_importar_xml.setObjectName(u"act_importar_xml")
        self.act_recalc_m = QAction(JanelaPrincipal)
        self.act_recalc_m.setObjectName(u"act_recalc_m")
        self.act_conferir_55 = QAction(JanelaPrincipal)
        self.act_conferir_55.setObjectName(u"act_conferir_55")
        self.act_revisar = QAction(JanelaPrincipal)
        self.act_revisar.setObjectName(u"act_revisar")
        self.act_correlacoes_cfop = QAction(JanelaPrincipal)
        self.act_correlacoes_cfop.setObjectName(u"act_correlacoes_cfop")
        self.centralwidget = QWidget(JanelaPrincipal)
        self.centralwidget.setObjectName(u"centralwidget")
        self.layout_central = QVBoxLayout(self.centralwidget)
        self.layout_central.setObjectName(u"layout_central")
        self.layout_central.setContentsMargins(0, 0, 0, 0)
        self.tabs_bloco = QTabWidget(self.centralwidget)
        self.tabs_bloco.setObjectName(u"tabs_bloco")
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)

        self.layout_central.addWidget(self.tabs_bloco)

        JanelaPrincipal.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(JanelaPrincipal)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1200, 22))
        self.menu_arquivo = QMenu(self.menubar)
        self.menu_arquivo.setObjectName(u"menu_arquivo")
        self.menu_ferramentas = QMenu(self.menubar)
        self.menu_ferramentas.setObjectName(u"menu_ferramentas")
        JanelaPrincipal.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(JanelaPrincipal)
        self.statusbar.setObjectName(u"statusbar")
        JanelaPrincipal.setStatusBar(self.statusbar)
        self.toolbar = QToolBar(JanelaPrincipal)
        self.toolbar.setObjectName(u"toolbar")
        self.toolbar.setMovable(False)
        JanelaPrincipal.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.menubar.addAction(self.menu_arquivo.menuAction())
        self.menubar.addAction(self.menu_ferramentas.menuAction())
        self.menu_arquivo.addAction(self.act_abrir)
        self.menu_arquivo.addAction(self.act_salvar)
        self.menu_arquivo.addAction(self.act_salvar_como)
        self.menu_arquivo.addSeparator()
        self.menu_arquivo.addAction(self.act_sair)
        self.menu_ferramentas.addAction(self.act_importar_xml)
        self.menu_ferramentas.addAction(self.act_recalc_m)
        self.menu_ferramentas.addSeparator()
        self.menu_ferramentas.addAction(self.act_conferir_55)
        self.menu_ferramentas.addAction(self.act_correlacoes_cfop)
        self.menu_ferramentas.addAction(self.act_revisar)
        self.toolbar.addAction(self.act_abrir)
        self.toolbar.addAction(self.act_salvar)
        self.toolbar.addAction(self.act_salvar_como)

        self.retranslateUi(JanelaPrincipal)

        QMetaObject.connectSlotsByName(JanelaPrincipal)
    # setupUi

    def retranslateUi(self, JanelaPrincipal):
        JanelaPrincipal.setWindowTitle(QCoreApplication.translate("JanelaPrincipal", u"Editor SPED", None))
        self.act_abrir.setText(QCoreApplication.translate("JanelaPrincipal", u"Abrir\u2026", None))
        self.act_salvar.setText(QCoreApplication.translate("JanelaPrincipal", u"Salvar", None))
        self.act_salvar_como.setText(QCoreApplication.translate("JanelaPrincipal", u"Salvar como", None))
        self.act_sair.setText(QCoreApplication.translate("JanelaPrincipal", u"Sair", None))
        self.act_importar_xml.setText(QCoreApplication.translate("JanelaPrincipal", u"Importar XMLs de NFC-e \u2192 consolidar C175", None))
        self.act_recalc_m.setText(QCoreApplication.translate("JanelaPrincipal", u"Recalcular bloco M (apura\u00e7\u00e3o)", None))
        self.act_conferir_55.setText(QCoreApplication.translate("JanelaPrincipal", u"Conferir entradas com XMLs", None))
        self.act_revisar.setText(QCoreApplication.translate("JanelaPrincipal", u"Revisar erros comuns", None))
        self.act_correlacoes_cfop.setText(QCoreApplication.translate("JanelaPrincipal", u"Correla\u00e7\u00f5es de CFOP (entradas)", None))
        self.menu_arquivo.setTitle(QCoreApplication.translate("JanelaPrincipal", u"&Arquivo", None))
        self.menu_ferramentas.setTitle(QCoreApplication.translate("JanelaPrincipal", u"&Ferramentas", None))
        self.toolbar.setWindowTitle(QCoreApplication.translate("JanelaPrincipal", u"Principal", None))
    # retranslateUi


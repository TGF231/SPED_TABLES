# -*- coding: utf-8 -*-
"""Janela principal: montagem da tela, barra de título, tema e abas."""

import os

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QStackedWidget, QStatusBar, QTabWidget,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from sped_tables.aplicacao.sessao import Sessao
from sped_tables.infra import cadastro
from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import config
from sped_tables.infra import dados
from sped_tables.infra import pva
from sped_tables.interface import acoes
from sped_tables.interface import janela_custom
from sped_tables.interface import tema
from sped_tables.version import APP_NAME
from sped_tables.version import __version__
from sped_tables.interface.barra_titulo import BarraTitulo
from sped_tables.interface.comum import ajustes
from sped_tables.interface.controladores.arquivo import ControladorArquivo
from sped_tables.interface.controladores.contribuicoes import (
    ControladorContribuicoes,
)
from sped_tables.interface.controladores.gerais import ControladorGerais
from sped_tables.interface.controladores.icms import ControladorIcms
from sped_tables.interface.grade import BlocoWidget, GerenciadorOrdemAbas
from sped_tables.interface.telas.empresas import PainelEmpresas
from sped_tables.interface.telas.inicial import TelaInicial
from sped_tables.interface.telas.relatorio import RelatorioWidget
from sped_tables.interface.telas.resumo import ResumoWidget


class JanelaPrincipal(ControladorArquivo, ControladorIcms,
                      ControladorContribuicoes, ControladorGerais,
                      QMainWindow):
    """Janela principal: monta a tela e delega as ações aos
    controladores (um por área do menu)."""

    def __init__(self):
        super().__init__()
        # Carrega o ícone da janela
        icon_path = dados.recurso("icon.ico")
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        # o arquivo aberto (documento, caminho, alteração) é da sessão; a
        # janela só expõe `doc`, `caminho` e `alterado` para os widgets
        self.sessao = Sessao()
        self._offset_blocos = 0
        self._blocos = []
        # ordem de abas escolhida por arrasto (só durante a sessão)
        self._ger_abas = GerenciadorOrdemAbas()
        self.resize(1200, 760)

        # correlações de CFOP (saída -> entradas válidas), persistidas em JSON
        self._caminho_correl = cadastro.caminho_correlacoes()
        self.correlacoes_cfop = cadastro.carregar_correlacoes()

        # configuração das tabelas da RFB (verificação de CST por NCM)
        self.cfg_tabelas = config.tabelas_rfb()

        # Um caminho só para montar a janela. Até a 0.52.0 eram dois — o
        # `sped_editor.ui` do Qt Designer e um fallback em código —, e só o
        # que rodava nos dois via as ações novas; o resto quebrava num deles.
        self._montar_acoes()
        self._montar_barra_ferramentas()
        self.tabs_bloco = QTabWidget()
        self.tabs_bloco.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs_bloco.currentChanged.connect(self._bloco_aberto)
        self.setStatusBar(QStatusBar())
        self._habilitar_acoes()

        self._montar_modo_topo()
        self.setWindowTitle("%s v%s" % (APP_NAME, __version__))
        self.statusBar().showMessage("Pronto. Abra um arquivo SPED (Ctrl+O).")
        # por último: a barra própria precisa das ações e da toolbar já montadas
        self._montar_barra_titulo()

    # ------------------------------------------------ estado (da sessão)
    @property
    def doc(self):
        return self.sessao.doc

    @property
    def caminho(self):
        return self.sessao.caminho

    @property
    def alterado(self):
        return self.sessao.alterado

    @alterado.setter
    def alterado(self, valor):
        self.sessao.alterado = bool(valor)

    def _montar_modo_topo(self):
        """Envolve as grades num QTabWidget de nível superior com dois modos:
        'Modo Tabela' (as abas de bloco atuais) e 'Modo Relatório' (visão
        achatada dos itens para comparação com o banco)."""
        self.tabs_topo = QTabWidget()
        self.tabs_topo.setTabPosition(QTabWidget.TabPosition.North)
        # Modo Tabela: reparenta o tabs_bloco para dentro de um container
        cont_tabela = QWidget()
        lt = QVBoxLayout(cont_tabela)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.addWidget(self.tabs_bloco)
        self.tabs_topo.addTab(cont_tabela, "📋 Modo Tabela")
        # Modo Relatório
        self.relatorio = RelatorioWidget()
        self.tabs_topo.addTab(self.relatorio, "📊 Modo Relatório")

        # O widget central passa a ser uma pilha de duas páginas: o editor
        # (abas de bloco e modos) e o painel de empresas. Empilhar, em vez de
        # acrescentar mais uma aba, mantém o painel fora da navegação por
        # blocos — ele não é um bloco do arquivo, é o cadastro.
        self.pilha = QStackedWidget()
        self.tela_inicial = TelaInicial(self)
        self.pilha.addWidget(self.tela_inicial)      # 0
        self.pilha.addWidget(self.tabs_topo)         # 1
        self.painel_empresas = PainelEmpresas(self)
        self.pilha.addWidget(self.painel_empresas)   # 2
        self.setCentralWidget(self.pilha)

    def mostrar_editor(self):
        """Editor se há arquivo aberto; senão, tela inicial (recarregada)."""
        if not hasattr(self, "pilha"):
            return
        if self.doc is None:
            self.tela_inicial.recarregar()
            self.pilha.setCurrentIndex(0)
        else:
            self.pilha.setCurrentIndex(1)
        if self.act_empresas.isChecked():
            self.act_empresas.setChecked(False)

    def dimensionar_para_a_tela(self):
        """Tamanho inicial conforme a resolução disponível.

        Numa tela folgada a janela abre grande e centralizada; numa tela
        apertada ela **abre maximizada** e o tema entra em densidade compacta —
        numa grade de SPED, alguns pixels de padding a menos por célula valem
        uma coluna inteira a mais visível.
        """
        tela = QApplication.primaryScreen()
        if tela is None:
            return
        disp = tela.availableGeometry()
        alvo_l, alvo_a = 1600, 960
        if disp.width() < alvo_l or disp.height() < alvo_a:
            tema.definir_densidade("compacta")
            QApplication.instance().setStyleSheet(tema.folha_estilo())
            self.showMaximized()
            return
        largura = min(alvo_l, int(disp.width() * 0.88))
        altura = min(alvo_a, int(disp.height() * 0.88))
        self.resize(largura, altura)
        self.move(disp.left() + (disp.width() - largura) // 2,
                  disp.top() + (disp.height() - altura) // 2)

    def mostrar_empresas(self, ligado):
        """Alterna entre o editor e o painel de empresas.

        Ao entrar, a lista é recarregada: o histórico pode ter ganhado
        períodos desde a última visita (abrir ou salvar um arquivo arquiva uma
        cópia) e uma empresa nova pode ter aparecido por aí.
        """
        if not hasattr(self, "pilha"):
            return
        if ligado:
            self.painel_empresas.recarregar()
            self.pilha.setCurrentIndex(2)
        else:
            self.mostrar_editor()
        if self.act_empresas.isChecked() != bool(ligado):
            self.act_empresas.setChecked(bool(ligado))
        self.statusBar().showMessage(
            "Cadastro de empresas e histórico de arquivos." if ligado
            else "", 4000)

    # ----------------------------------------------------------- tema
    # --------------------------------------------------------------- ações
    def _montar_acoes(self):
        """Cria e conecta todas as ações a partir de `acoes.ACOES`."""
        for a in acoes.visiveis() + (acoes.ACAO_TEMA,):
            acao = QAction(a.rotulo, self)
            if a.atalho:
                acao.setShortcut(getattr(QKeySequence.StandardKey, a.atalho))
            metodo = getattr(self, a.metodo)
            if a.alternavel:
                acao.setCheckable(True)
                acao.toggled.connect(metodo)
            elif a.argumento is not None:
                acao.triggered.connect(
                    lambda _marcado=False, m=metodo, arg=a.argumento: m(arg))
            else:
                acao.triggered.connect(lambda _marcado=False, m=metodo: m())
            setattr(self, a.atributo, acao)
        self._sincronizar_rotulo_tema()

    def _montar_barra_ferramentas(self):
        """Barra: as ações de arquivo, Empresas, o botão Ferramentas (menus
        por leiaute) e o tema — tudo na ordem da tabela."""
        barra = QToolBar("Principal")
        barra.setMovable(False)
        self.addToolBar(barra)
        self.toolbar = barra

        menu = QMenu(self)
        self._menus = {}
        for chave, titulo, _layout in acoes.MENUS:
            if chave == acoes.MENU_GERAIS:
                menu.addSeparator()
            self._menus[chave] = menu.addMenu(titulo)
        # nomes antigos, usados pelos testes e por quem desabilita o submenu
        self.menu_icms = self._menus[acoes.MENU_ICMS]
        self.menu_contrib = self._menus[acoes.MENU_CONTRIB]
        self.menu_gerais = self._menus[acoes.MENU_GERAIS]

        for a in acoes.visiveis():
            acao = getattr(self, a.atributo)
            if a.onde == acoes.BARRA:
                if a.separador:
                    barra.addSeparator()
                barra.addAction(acao)
            elif a.onde in self._menus:
                sub = self._menus[a.onde]
                if a.separador and not sub.isEmpty():
                    sub.addSeparator()
                sub.addAction(acao)

        botao = QToolButton(self)
        # sem "▾" no texto: o Qt já desenha o indicador do menu, e o
        # caractere literal produzia duas setas
        botao.setText("Ferramentas")
        botao.setMenu(menu)
        botao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        botao.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        barra.addSeparator()
        barra.addWidget(botao)
        self._botao_ferramentas = botao
        barra.addSeparator()
        barra.addAction(self.act_tema)

    def _habilitar_acoes(self):
        """Liga e desliga cada ação conforme o arquivo aberto (ou nenhum)."""
        layout = self.doc.layout if self.doc is not None else None
        tem_pva = (layout is not None
                   and pva.instalacao(layout) is not None)
        for a in acoes.visiveis():
            getattr(self, a.atributo).setEnabled(
                acoes.habilitada(a, layout, tem_pva))
        for chave, _titulo, so_layout in acoes.MENUS:
            if so_layout is not None:
                self._menus[chave].setEnabled(layout == so_layout)

    def _sincronizar_rotulo_tema(self):
        if hasattr(self, "act_tema"):
            self.act_tema.setText(
                "Tema claro" if tema.e_escuro() else "Tema escuro")

    def alternar_tema(self):
        """Troca a paleta, repinta tudo e grava a preferência.

        A folha de estilo cobre os widgets, mas não as cores gravadas em
        QTableWidgetItem (coluna REG, célula somente-leitura, divergências):
        essas são pixels já decididos em Python. Por isso as abas são
        remontadas — é o único caminho que garante a grade inteira na paleta
        nova, e o custo é o mesmo de abrir o arquivo.
        """
        tema.definir_escuro(not tema.e_escuro())
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(tema.folha_estilo())
        self._sincronizar_rotulo_tema()
        ajustes().setValue("tema_escuro", tema.e_escuro())
        if self.doc is not None:
            bloco = self.tabs_bloco.currentIndex()
            self._montar_abas()
            if 0 <= bloco < self.tabs_bloco.count():
                self.tabs_bloco.setCurrentIndex(bloco)
        self.statusBar().showMessage(
            "Tema %s aplicado." % tema.atual().nome, 4000)

    # ------------------------------------------------- barra de título
    def _montar_barra_titulo(self):
        """Põe a barra própria no lugar da do Windows, quando der.

        `setMenuWidget` ocupa exatamente a faixa acima das barras de
        ferramentas — o mesmo lugar onde ficava a barra de menus que o
        programa já escondia desde a 0.4.0.

        Se `janela_custom.aplicar` falhar (não é Windows, ctypes bloqueado, a
        escotilha SPED_TABLES_BARRA_NATIVA=1), nada é montado e o aplicativo
        segue com a barra nativa: enfeite não pode impedir de abrir.
        """
        self.barra_titulo = None
        self._barra_aplicada = False
        if not janela_custom.disponivel():
            return
        # o widget pode ser montado agora (e so Qt); os ganchos nativos ficam
        # para o primeiro showEvent, quando a janela ja existe de verdade
        self.barra_titulo = BarraTitulo(self)
        self.setMenuWidget(self.barra_titulo)
        self.sincronizar_barra()

    def showEvent(self, evento):
        """Aplica os ganchos nativos uma unica vez, ja com a janela criada.

        Fazer isso no __init__ forcava `winId()` no meio da construcao do
        QMainWindow e o SetWindowPos(FRAMECHANGED) reentrava na montagem —
        o processo morria sem traceback, por ser uma falha nativa.
        """
        super().showEvent(evento)
        if self.barra_titulo is None or self._barra_aplicada:
            return
        self._barra_aplicada = True
        if not janela_custom.aplicar(self):
            # sem os ganchos, a barra propria conviveria com a nativa
            self.setMenuWidget(None)
            self.barra_titulo = None
            self.statusBar().showMessage(
                "Barra de titulo propria indisponivel; usando a do Windows.",
                6000)

    def sincronizar_barra(self):
        """Empresa, período, leiaute e indicador de alterações."""
        if not getattr(self, "barra_titulo", None):
            return
        ident = self.sessao.identificacao()
        ctx = "  ·  ".join(ident[k] for k in ("nome", "periodo", "leiaute",
                                              "arquivo") if ident.get(k))
        self.barra_titulo.sincronizar(contexto=ctx,
                                      alterado=bool(self.alterado))

    def nativeEvent(self, tipo, mensagem):
        """Delega as mensagens de moldura para o módulo nativo.

        Sem a barra montada não interceptamos nada — o Windows continua
        desenhando a moldura dele.

        **Nunca chamar `super().nativeEvent(...)` aqui.** No PyQt6 isso derruba
        o processo sem traceback (o console só pisca e fecha). Para "não
        tratei", devolva `(False, 0)`: o Qt segue com o tratamento padrão.
        """
        # so interceptamos depois de aplicar() ter preparado a janela: tratar
        # WM_NCCALCSIZE durante a criacao do HWND derruba o processo
        if (getattr(self, "barra_titulo", None) is not None
                and getattr(self, "_barra_aplicada", False)):
            tratado, resultado = janela_custom.tratar(
                self, int(mensagem), BarraTitulo.ALTURA,
                self.barra_titulo.area_arrastavel)
            if tratado:
                return True, resultado
        return False, 0

    def changeEvent(self, evento):
        # trocar entre maximizada e restaurada muda o ícone do botão
        super().changeEvent(evento)
        if evento.type() == QEvent.Type.WindowStateChange:
            if getattr(self, "barra_titulo", None):
                self.barra_titulo.sincronizar()

    def ir_para_registro(self, uid):
        """Navega até o registro de `uid`: abre a aba do bloco, a sub-aba do
        tipo raiz de exibição e desce pela cadeia até o registro alvo.

        A "raiz de exibição" não é o topo absoluto da cadeia .pai, mas o
        ancestral principal mais próximo do alvo (aquele que vira sub-aba de
        topo do bloco). Ex.: para um C190, a raiz é o C100 (não o C001 de
        abertura); o C190 aparece no detalhe do C100.
        """
        if not self.doc:
            return False
        reg = next((r for r in self.doc.registros if r.uid == uid), None)
        if reg is None:
            return False

        # sobe do alvo até o topo, coletando os ancestrais
        sobe = []
        cur = reg
        while cur is not None:
            sobe.append(cur)
            cur = cur.pai
        # raiz de exibição = primeiro ancestral principal (subindo do alvo)
        raiz_idx = next((i for i, r in enumerate(sobe)
                         if SpedDocument._eh_principal(r)), len(sobe) - 1)
        cadeia = list(reversed(sobe[:raiz_idx + 1]))   # [raiz_exib, ..., alvo]
        raiz = cadeia[0]

        blocos = self.doc.blocos()
        if raiz.bloco not in blocos:
            return False
        # localiza a aba pelo widget do bloco (robusto à reordenação)
        alvo = next((w for w in self._blocos if w.bloco == raiz.bloco), None)
        if alvo is None:
            return False
        # garante que o Modo Tabela esteja visível antes de navegar
        if hasattr(self, "tabs_topo"):
            self.tabs_topo.setCurrentIndex(0)
        idx_aba = self.tabs_bloco.indexOf(alvo)
        if idx_aba < 0:
            return False
        self.tabs_bloco.setCurrentIndex(idx_aba)
        self._bloco_aberto(idx_aba)
        md = alvo.widget_do_tipo(raiz.reg)
        if md is None:
            return False
        md.selecionar_uid(raiz.uid)
        for prox in cadeia[1:]:
            sub = md.subwidget_de_tipo(prox.reg)
            if sub is None:
                break
            sub.selecionar_uid(prox.uid)
            md = sub
        self.raise_()
        self.activateWindow()
        return True

    def _montar_abas(self):
        # reutiliza o QTabWidget central (criado no __init__ ou vindo do .ui)
        self.tabs_bloco.blockSignals(True)
        self.tabs_bloco.clear()
        self.tabs_bloco.blockSignals(False)

        nomes_bloco = {
            "0": "0 · Abertura/Identificação", "A": "A · Serviços",
            "B": "B · ISS", "C": "C · Mercadorias (ICMS/IPI)",
            "D": "D · Serviços (ICMS/Transporte)", "E": "E · Apuração ICMS/IPI",
            "F": "F · Demais Documentos/Operações", "G": "G · CIAP",
            "H": "H · Inventário", "I": "I · Outras informações",
            "K": "K · Produção/Estoque", "M": "M · Apuração PIS/COFINS",
            "P": "P · Apuração Previdenciária", "1": "1 · Outras",
            "9": "9 · Controle/Totais",
        }
        self._blocos = []
        # aba inicial de resumo (cabeçalho + contagem)
        self.tabs_bloco.addTab(
            ResumoWidget(self.doc, self.caminho), "📋 Resumo")
        self._offset_blocos = 1
        ids = ["resumo"]
        for b in self.doc.blocos():
            w = BlocoWidget(self.doc, b, on_change=self._marcar_alterado,
                            gerenciador=self._ger_abas)
            self._blocos.append(w)
            self.tabs_bloco.addTab(w, nomes_bloco.get(b, "Bloco %s" % b))
            ids.append(b)
        # permite reordenar as abas de bloco (persistente na sessão)
        self._ger_abas.registrar(self.tabs_bloco, "blocos", ids)
        self.tabs_bloco.setCurrentIndex(0)
        # atualiza o Modo Relatório com o documento aberto
        if hasattr(self, "relatorio"):
            self.relatorio.set_doc(self.doc)

    def _bloco_aberto(self, idx):
        # robusto à reordenação: usa o widget da aba, não o índice na lista
        w = self.tabs_bloco.widget(idx)
        if isinstance(w, BlocoWidget):
            w.construir()

    # ------------------------------------------------------------ salvar
    def _marcar_alterado(self):
        self.sessao.marcar_alterado()
        self.sincronizar_barra()
        t = self.windowTitle()
        if not t.endswith(" *"):
            self.setWindowTitle(t + " *")

    # ------------------------------------------------------------ fechar
    def closeEvent(self, event):
        # mesma pergunta do fechar arquivo: oferecer salvar é melhor que a
        # escolha binária "sair mesmo assim?", que só permitia descartar
        if not self._resolver_alteracoes(
                "Sair",
                "Há alterações não salvas.<br><br>"
                "Deseja salvar antes de sair?"):
            event.ignore()
            return
        event.accept()

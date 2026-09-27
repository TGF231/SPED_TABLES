# -*- coding: utf-8 -*-
"""Ponto de entrada da interface: `main()`, tradução, instalação e o aviso do fallback de exceções."""

import os
import sys

from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from sped_tables.aplicacao import montagem
from sped_tables.infra import dados
from sped_tables.infra import falhas
from sped_tables.interface import tema
from sped_tables.version import APP_NAME
from sped_tables.interface.comum import ajustes
from sped_tables.interface.janela import JanelaPrincipal


def avisar_erro(tipo, valor, detalhe, copia):
    """Caixa que substitui o encerramento do processo (ver `falhas`)."""
    caixa = QMessageBox(QApplication.activeWindow())
    caixa.setIcon(QMessageBox.Icon.Critical)
    caixa.setWindowTitle("Erro inesperado")
    texto = ("Aconteceu um erro que o programa não esperava:<br><b>%s</b>"
             "<br><br>O programa continua aberto, mas a última operação "
             "pode não ter terminado." % _escapar(
                 "%s: %s" % (tipo.__name__, valor)))
    if copia:
        texto += ("<br><br>Havia alterações não salvas; uma cópia foi "
                  "gravada em:<br><b>%s</b>" % _escapar(copia))
    texto += ("<br><br>O registro completo está em:<br>%s"
              % _escapar(falhas.caminho_log()))
    caixa.setText(texto)
    caixa.setDetailedText(detalhe)
    b_pasta = caixa.addButton("Abrir pasta do registro",
                              QMessageBox.ButtonRole.ActionRole)
    caixa.addButton("Continuar", QMessageBox.ButtonRole.AcceptRole)
    caixa.exec()
    if caixa.clickedButton() is b_pasta:
        try:
            os.startfile(falhas.pasta_logs())       # noqa: S606 (só Windows)
        except (AttributeError, OSError):
            pass


def _escapar(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _mensagens_do_qt(tipo, _contexto, mensagem):
    """Avisos do próprio Qt vão para o registro em vez do console, que no
    executável nem existe."""
    from PyQt6.QtCore import QtMsgType
    nivel = {QtMsgType.QtWarningMsg: 30, QtMsgType.QtCriticalMsg: 40,
             QtMsgType.QtFatalMsg: 50}.get(tipo, 10)
    falhas.log.log(nivel, "Qt: %s", mensagem)


def instalar_traducao(app):
    """Carrega a tradução pt-BR do próprio Qt.

    Sem isso, os botões padrão dos diálogos saem em inglês — "Save",
    "Discard", "Cancel" —, o que destoa de um programa cuja interface é toda
    em português. A tradução cobre tudo que o Qt desenha: caixas de mensagem,
    diálogos de arquivo não-nativos, menus de contexto de campos de texto.

    Os tradutores precisam ficar vivos enquanto o aplicativo existir; guardá-los
    no próprio `app` evita que o coletor de lixo os leve embora e a interface
    volte ao inglês no meio do uso.
    """
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese,
                               QLocale.Country.Brazil))
    # No executável empacotado os .qm vêm na pasta "traducoes" (ver o .spec);
    # rodando do código-fonte, ficam no diretório de traduções do próprio Qt.
    pastas = [dados.recurso("traducoes"),
              QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)]
    carregados = []
    app._tradutores = []
    for nome in ("qtbase_pt_BR", "qt_pt_BR"):
        for pasta in pastas:
            if not pasta or not os.path.isdir(pasta):
                continue
            t = QTranslator(app)
            if t.load(nome, pasta) and app.installTranslator(t):
                app._tradutores.append(t)
                carregados.append(nome)
                break
    return carregados


def primeira_instalacao(janela):
    """Prepara a pasta de dados e oferece o atalho, na primeira execução.

    Só faz sentido no executável: rodando do código-fonte, os dados já ficam na
    pasta do projeto e o atalho seria do interpretador. A marca de instalação
    vive na própria pasta de dados — apagá-la refaz a pergunta, e atualizar o
    executável não a repete.
    """
    if not dados.empacotado() or not dados.primeira_execucao():
        return
    copiados = dados.instalar()
    resp = QMessageBox.question(
        janela, "Instalação",
        "As configurações e o histórico serão guardados em:<br><b>%s</b>"
        "<br><br>Criar um atalho na área de trabalho?"
        % dados.pasta_dados(),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes)
    if resp == QMessageBox.StandardButton.Yes:
        ok, detalhe = dados.criar_atalho_area_trabalho()
        if not ok:
            QMessageBox.warning(
                janela, "Atalho",
                "Não foi possível criar o atalho:<br>%s" % detalhe)
    dados.marcar_instalado()
    janela.statusBar().showMessage(
        "Instalação concluída. Dados em %s%s"
        % (dados.pasta_dados(),
           " (%d item[ns] copiado[s])" % len(copiados) if copiados else ""),
        10000)


def main():
    app = QApplication(sys.argv)
    if sys.argv[1:2] == ["--autoteste"]:
        # conferência do pacote (TESTES.md 2.2), sem janela e sem tocar nos
        # dados de quem usa o programa
        from sped_tables.interface import autoteste
        sys.exit(autoteste.executar(app, sys.argv[2:]))
    # antes de qualquer janela: exceção num slot, sem isto, encerra o processo
    falhas.instalar(avisar=avisar_erro)
    # liga as regras fiscais às tabelas oficiais do PVA instalado
    montagem.configurar()
    from PyQt6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(_mensagens_do_qt)
    instalar_traducao(app)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    # fonte um pouco menor deixa as grades mais densas (estilo planilha)
    f = QFont()
    f.setPointSize(max(8, f.pointSize() - 1))
    app.setFont(f)
    # tema: a preferência é da máquina, não da sessão
    preferencias = ajustes()
    tema.definir_escuro(preferencias.value("tema_escuro", False, type=bool))
    app.setStyleSheet(tema.folha_estilo())
    janela = JanelaPrincipal()
    falhas.definir_salvar_emergencia(janela.copia_de_emergencia)
    # dimensiona antes de mostrar: numa tela apertada isso já abre maximizada
    # e troca o tema para a densidade compacta
    janela.dimensionar_para_a_tela()
    janela.show()
    # arquivo de dados ilegível (cadastro, acervo, configuração) é guardado à
    # parte pela infra; aqui a pessoa fica sabendo — inclusive dos achados
    # antes de a janela existir
    dados.ao_avisar(lambda texto: QMessageBox.warning(
        janela, "Arquivo de dados ilegível", texto))
    primeira_instalacao(janela)
    # abre direto se um caminho for passado na linha de comando. Pelo mesmo
    # caminho do histórico: montar as abas à mão deixava o menu desabilitado,
    # sem cópia no acervo e sem diagnóstico
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        janela.abrir_caminho(sys.argv[1])
    codigo = app.exec()
    falhas.log.info("sessão encerrada (%s)", codigo)
    sys.exit(codigo)

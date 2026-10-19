# -*- coding: utf-8 -*-
"""Ações do menu: abrir, salvar, fechar e mandar ao PVA.

A regra de cada operação está nos casos de uso (`aplicacao.sessao`,
`aplicacao.envio_pva`); aqui ficam só as perguntas, as caixas e a espera.
"""

import os
import threading

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QMessageBox, QProgressDialog,
)

from sped_tables.aplicacao import envio_pva
from sped_tables.dominio.sped_model import LinhasInvalidas
from sped_tables.version import APP_NAME
from sped_tables.version import __version__
from sped_tables.interface.comum import informar


class ControladorArquivo:
    """Abrir, salvar, fechar e mandar ao PVA.

    Mixin da `JanelaPrincipal`: usa `self.sessao`, `self.statusBar()` e os
    demais membros da janela.
    """

    # ------------------------------------------------- fechar arquivo
    def _resolver_alteracoes(self, titulo, texto):
        """Pergunta o que fazer com as alterações pendentes.

        Devolve True quando é seguro prosseguir (salvou ou descartou) e False
        quando o usuário desistiu. Um "Salvar" que acabe cancelado — o diálogo
        de *Salvar como* fechado no X, por exemplo — também devolve False: a
        intenção era guardar, e seguir em frente perderia o trabalho.
        """
        if not self.alterado or self.doc is None:
            return True
        escolha = self._perguntar_salvar(titulo, texto)
        if escolha == "cancelar":
            return False
        if escolha == "salvar":
            self.salvar()
            return not self.alterado
        return True

    def _perguntar_salvar(self, titulo, texto):
        """Mostra a pergunta e devolve 'salvar', 'descartar' ou 'cancelar'.

        Os rótulos são escritos à mão em vez de usar os botões padrão do Qt:
        a tradução pt-BR vem de arquivos .qm que podem não ser empacotados no
        executável, e esta é a pergunta em que sair em inglês seria pior — é a
        que decide se o trabalho do usuário é gravado ou perdido.

        Separar a pergunta da decisão também deixa o fluxo testável sem
        depender de diálogo modal.
        """
        caixa = QMessageBox(self)
        caixa.setWindowTitle(titulo)
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setText(texto)
        caixa.setIcon(QMessageBox.Icon.Question)
        b_salvar = caixa.addButton("Salvar",
                                   QMessageBox.ButtonRole.AcceptRole)
        b_descartar = caixa.addButton("Descartar",
                                      QMessageBox.ButtonRole.DestructiveRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_salvar)
        caixa.exec()
        clicado = caixa.clickedButton()
        if clicado is b_salvar:
            return "salvar"
        if clicado is b_descartar:
            return "descartar"
        return "cancelar"

    def fechar_arquivo(self):
        """Fecha a escrituração aberta e volta para a tela inicial."""
        if self.doc is None:
            return False
        nome = os.path.basename(self.caminho or "") or "o arquivo aberto"
        if not self._resolver_alteracoes(
                "Fechar arquivo",
                "As alterações em <b>%s</b> ainda não foram salvas.<br><br>"
                "Deseja salvar antes de fechar?" % nome):
            return False

        self.sessao.fechar()
        self.tabs_bloco.blockSignals(True)
        self.tabs_bloco.clear()
        self.tabs_bloco.blockSignals(False)
        self._habilitar_acoes()
        self.setWindowTitle("%s v%s" % (APP_NAME, __version__))
        self.mostrar_editor()          # sem doc, cai na tela inicial
        self.sincronizar_barra()
        self.statusBar().showMessage("Arquivo fechado.", 4000)
        return True

    # ------------------------------------------------------------ abrir
    def abrir(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir arquivo SPED", "",
            "Arquivos SPED (*.txt);;Todos os arquivos (*)")
        if caminho:
            self.abrir_caminho(caminho)

    def abrir_caminho(self, caminho):
        """Abre um arquivo pelo caminho (menu, histórico, linha de comando,
        arrastar e soltar).

        Com o arquivo aberto alterado, pergunta antes: abrir outro por cima
        descartava as alterações sem aviso."""
        nome = os.path.basename(self.caminho or "") or "o arquivo aberto"
        if not self._resolver_alteracoes(
                "Abrir arquivo",
                "As alterações em <b>%s</b> ainda não foram salvas.<br><br>"
                "Deseja salvar antes de abrir outro arquivo?" % nome):
            return False
        try:
            resultado = self.sessao.abrir(caminho)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao abrir",
                                 "Não foi possível ler o arquivo:\n%s" % e)
            return False
        self._carregado(resultado)
        return True

    def _carregado(self, resultado):
        """Depois de abrir: abas, ações, título e o diagnóstico automático."""
        doc = self.doc
        self._montar_abas()
        self.mostrar_editor()
        self._habilitar_acoes()
        nome = os.path.basename(resultado.caminho)
        tipo = "EFD Contribuições" if doc.layout == "CONTRIB" \
            else "EFD ICMS/IPI"
        self.setWindowTitle("%s v%s — %s  [%s]"
                            % (APP_NAME, __version__, nome, tipo))
        self.statusBar().showMessage(
            resultado.aviso or "%s carregado: %d registros, layout %s."
            % (nome, len(doc.registros), tipo), 8000 if resultado.aviso else 0)
        self.sincronizar_barra()
        # diagnóstico automático: saber o que falta antes de começar a
        # trabalhar vale mais do que descobrir depois de transmitir. Roda
        # depois da janela assentar, para o arquivo aparecer primeiro.
        QTimer.singleShot(150, lambda: self.diagnosticar(automatico=True))

    # ------------------------------------------------------------ salvar
    def salvar(self):
        if not self.doc:
            return
        if not self.doc.caminho:
            return self.salvar_como()
        self._gravar(self.doc.caminho)

    def salvar_como(self):
        if not self.doc:
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar arquivo SPED",
            self.doc.caminho or "", "Arquivos SPED (*.txt)")
        if not caminho:
            return
        self._gravar(caminho)

    def _ficticios_antes_de_gravar(self):
        """NFC-e com C170 — o andaime dos fictícios — é estrutura inválida
        nos dois leiautes. Pergunta antes de gravar; no ICMS/IPI oferece
        removê-los (o C190 já foi refeito), no Contribuições lembra do
        *Regenerar C175*, que é quem aproveita a correção."""
        docs = self.doc.documentos_65_com_c170()
        if not docs:
            return True
        icms = self.doc.layout == "ICMS"
        cx = QMessageBox(
            QMessageBox.Icon.Warning, "C170 em NFC-e",
            "%d NFC-e (modelo 65) ainda têm C170 fictícios. NFC-e com C170 é "
            "estrutura inválida: o PVA recusa o arquivo." % len(docs),
            parent=self)
        cx.setInformativeText(
            "Remova os fictícios antes de gravar." if icms else
            "Rode \"Regenerar C175 (modelo 65) dos itens\" antes de gravar.")
        b_rem = None
        if icms:
            b_rem = cx.addButton("Remover e gravar",
                                 QMessageBox.ButtonRole.AcceptRole)
        b_assim = cx.addButton("Gravar assim",
                               QMessageBox.ButtonRole.DestructiveRole)
        b_canc = cx.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        cx.setDefaultButton(b_rem or b_canc)
        cx.exec()
        if b_rem is not None and cx.clickedButton() is b_rem:
            self.doc.remover_c170_ficticios_65()
            self._montar_abas()
            return True
        return cx.clickedButton() is b_assim

    def _gravar(self, caminho):
        if not self._ficticios_antes_de_gravar():
            return
        try:
            try:
                resultado = self.sessao.salvar(caminho)
            except LinhasInvalidas as inv:
                # nada some sem a pessoa decidir: são linhas que a leitura
                # não reconheceu como registro e que não têm como ir adiante
                cx = QMessageBox(QMessageBox.Icon.Warning,
                                 "Linhas fora do formato", str(inv),
                                 parent=self)
                cx.setInformativeText(
                    "Gravar sem essas linhas? O arquivo original continua "
                    "como está até você escolher gravar por cima dele.")
                b_sim = cx.addButton("Gravar sem elas",
                                     QMessageBox.ButtonRole.AcceptRole)
                cx.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
                cx.setDefaultButton(b_sim)
                cx.exec()
                if cx.clickedButton() is not b_sim:
                    return
                resultado = self.sessao.salvar(caminho,
                                               descartar_invalidas=True)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao salvar",
                                 "Não foi possível gravar:\n%s" % e)
            return
        nome = os.path.basename(caminho)
        self.setWindowTitle(self.windowTitle().removesuffix(" *"))
        self.statusBar().showMessage(resultado.aviso or "Salvo em %s." % nome)
        self.sincronizar_barra()
        msg = "Arquivo salvo com sucesso em\n%s" % caminho
        if resultado.entrada:
            msg += ("\n\nA cópia interna do período %s foi atualizada."
                    % self.sessao.identificacao().get("periodo", ""))
        msg += ("\n\nValide este arquivo no PVA. Se o PVA corrigir ou "
                "regravar alguma coisa, **reabra aqui a versão validada** "
                "para que a cópia interna passe a refletir o arquivo "
                "definitivo do período.")
        cx = QMessageBox(QMessageBox.Icon.Information, "Salvo", msg,
                         parent=self)
        b_ok = cx.addButton("Fechar", QMessageBox.ButtonRole.RejectRole)
        b_pva = None
        if envio_pva.instalacao(self.doc.layout) is not None:
            b_pva = cx.addButton("Importar e validar no PVA",
                                 QMessageBox.ButtonRole.AcceptRole)
            cx.setDefaultButton(b_pva)
        else:
            cx.setDefaultButton(b_ok)
        cx.exec()
        if b_pva is not None and cx.clickedButton() is b_pva:
            self.abrir_no_pva(caminho)

    # --------------------------------------------------------- PVA
    def abrir_no_pva(self, caminho=None):
        """Abre o PVA do leiaute e leva o arquivo salvo até a importação.

        O PVA não recebe arquivo por linha de comando; o que `pva.abrir` faz é
        usar o acelerador **Ctrl+I** que ele declara no próprio menu e colar o
        caminho no seletor. Cada tecla só é enviada depois de conferir que a
        janela em primeiro plano é do processo do PVA — não dando certo, o
        caminho fica na área de transferência e a mensagem diz o que falta.

        Vai até o fim: confirma a importação e, terminada ela, a **validação**
        — importar sem validar não fecha o ciclo, porque o que interessa é o
        relatório de erros do PVA.

        A espera roda **fora da thread da interface**: PVA frio sobe um MySQL
        junto e pode levar mais de um minuto, tempo em que a janela apareceria
        travada.
        """
        if not self.doc:
            return
        alvo = caminho or self.caminho or self.doc.caminho
        problema = envio_pva.problema_do_arquivo(alvo)
        if problema:
            QMessageBox.warning(self, "Abrir no PVA", problema)
            return
        if self.alterado:
            r = QMessageBox.question(
                self, "Abrir no PVA",
                "Há alterações não salvas — o PVA vai importar a versão "
                "gravada em disco.\n\nContinuar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                return

        inst = envio_pva.instalacao(self.doc.layout)
        if inst is None:
            QMessageBox.warning(self, "Abrir no PVA",
                                "Não encontrei o PVA do leiaute %s em:\n%s"
                                % (self.doc.layout, envio_pva.onde_procurei()))
            return

        impedem, aviso = envio_pva.pre_checagem_com_aviso(self.doc)
        if ((impedem or aviso)
                and not self._mandar_mesmo_assim(impedem, aviso)):
            return

        # com botão de cancelar: a espera pode chegar a 15 minutos quando o
        # PVA abre um diálogo próprio e ninguém responde, e sem saída a janela
        # inteira ficava presa
        espera = QProgressDialog("Abrindo o %s…" % inst["nome"], "Cancelar",
                                 0, 0, self)
        espera.setWindowTitle("Abrir no PVA")
        espera.setWindowModality(Qt.WindowModality.ApplicationModal)
        espera.show()
        QApplication.processEvents()

        resultado = {}
        andamento = {"texto": ""}
        layout = self.doc.layout

        def trabalho():
            resultado.update(envio_pva.enviar(
                alvo, layout,
                progresso=lambda t: andamento.__setitem__("texto", t),
                cancelar=espera.wasCanceled))

        th = threading.Thread(target=trabalho, daemon=True)
        th.start()
        ultimo = ""
        while th.is_alive():
            if andamento["texto"] != ultimo:
                ultimo = andamento["texto"]
                espera.setLabelText(ultimo)
            QApplication.processEvents()
            th.join(0.05)
        espera.close()

        # deu certo (ou o usuário cancelou): a barra de status basta, e uma
        # caixa modal só atrapalharia quem já está olhando o PVA
        forma, msg = envio_pva.desfecho(resultado)
        self.statusBar().showMessage(msg, 15000)
        if forma == envio_pva.INFORMAR:
            informar(self, "Abrir no PVA", msg)
        elif forma == envio_pva.ALERTAR:
            QMessageBox.warning(self, "Abrir no PVA", msg)

    def _mandar_mesmo_assim(self, impedem, aviso=""):
        """O arquivo tem o que o PVA recusa na importação — ou a conferência
        prévia não rodou (`aviso`: sem o leiaute do arquivo na base): pergunta
        antes. O aviso sozinho não impede nada, o PVA valida de qualquer
        jeito; a pergunta só deixa de ser aprovação em silêncio."""
        partes = []
        if impedem:
            total = sum(q for _t, q in impedem)
            detalhe = "\n".join("• %s: %d" % (t, q) for t, q in impedem)
            partes.append("Este arquivo tem %d campo(s) que o PVA recusa "
                          "já na importação:\n\n%s\n\nEle vai responder "
                          "\"Importação não realizada — erros na estrutura "
                          "do arquivo\". Corrija antes pelo Diagnóstico."
                          % (total, detalhe))
        if aviso:
            partes.append(aviso + ("" if impedem else
                                   " O PVA valida o arquivo de qualquer "
                                   "jeito."))
        cx = QMessageBox(QMessageBox.Icon.Warning, "Abrir no PVA",
                         "\n\n".join(partes), parent=self)
        b_diag = cx.addButton("Ver diagnóstico",
                              QMessageBox.ButtonRole.AcceptRole)
        b_ass = cx.addButton(
            "Mandar assim mesmo" if impedem else "Abrir o PVA",
            QMessageBox.ButtonRole.DestructiveRole)
        cx.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        cx.setDefaultButton(b_diag)
        cx.exec()
        if cx.clickedButton() is b_diag:
            self.diagnosticar()
            return False
        return cx.clickedButton() is b_ass

    def copia_de_emergencia(self):
        """Chamada pelo fallback de exceções (`infra.falhas`)."""
        return self.sessao.copia_de_emergencia()

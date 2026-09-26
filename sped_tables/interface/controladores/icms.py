# -*- coding: utf-8 -*-
"""Ações do menu: ferramentas do efd icms/ipi"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from sped_tables.dominio import conferencia as cf
from sped_tables.dominio import revisao as rev
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.interface.dialogos.conferencia import DialogoConfC190
from sped_tables.interface.dialogos.correcao import DialogoRecalcularICMS
from sped_tables.interface.dialogos.inventario import DialogoImportarInventario


class ControladorIcms:
    """Ferramentas do EFD ICMS/IPI.

    Mixin da `JanelaPrincipal`: usa `self.doc`, `self.statusBar()` e os
    demais membros da janela.
    """

    def recalcular_icms(self):
        """Recalcula o ICMS dos itens, no escopo do Modo Relatório.

        Os uids vêm do relatório já gerado: é o conjunto que o usuário acabou
        de revisar. Sem relatório, o diálogo avisa que vale para o arquivo
        inteiro.
        """
        if not self.doc or self.doc.layout != "ICMS":
            QMessageBox.information(
                self, "Recalcular ICMS",
                "O recálculo de ICMS aplica-se ao EFD ICMS/IPI.")
            return
        uids = []
        rel = getattr(self, "relatorio", None)
        if rel is not None and getattr(rel, "_uids", None):
            # só itens C170: as outras fontes do relatório (C175/C190) não
            # entram, porque o recálculo é por item
            por_uid = {r.uid: r for r in self.doc.registros}
            uids = [u for u in rel._uids
                    if getattr(por_uid.get(u), "reg", "") == "C170"]
        DialogoRecalcularICMS(self.doc, uids, self).exec()

    def conferir_c190_xml(self):
        """Compara os C190 (ICMS analítico) com os XMLs, agrupando os itens do
        XML pela classificação do C170 (CFOP/CST/alíquota de entrada), casada
        por nItem — resolvendo a diferença de CFOP entre XML e SPED."""
        if not self.doc:
            return
        pasta = QFileDialog.getExistingDirectory(
            self, "Selecione a pasta com os XMLs (entradas/saídas)")
        if not pasta:
            return
        try:
            nfes, _erros = xf.ler_pasta(pasta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Conferir C190",
                                 "Erro ao ler a pasta:\n%s" % e)
            return
        if not nfes:
            QMessageBox.warning(self, "Conferir C190",
                                "Nenhum XML encontrado na pasta.")
            return
        resultado = cf.conferir_c190_com_xml(self.doc, nfes)
        r = resultado["resumo"]
        self.statusBar().showMessage(
            "C190 × XML: %d documentos, %d grupos, %d divergência(s)."
            % (r["docs_casados"], r["grupos_conferidos"], r["divergencias"]))
        DialogoConfC190(resultado, self).exec()

    def importar_inventario(self):
        """Importa planilha e gera o inventário do bloco H (H005/H010),
        cadastrando no 0200 apenas os itens ainda inexistentes."""
        if not self.doc or self.doc.layout != "ICMS":
            QMessageBox.information(
                self, "Importar inventário",
                "O bloco H (inventário) pertence ao EFD ICMS/IPI.")
            return
        self._dlg_inv = DialogoImportarInventario(
            self.doc, self._data_fin_doc(), self)
        self._dlg_inv.exec()

    def _corrigir_c190_da_revisao(self):
        """Corrige e reabre o relatório, para o usuário ver o que restou."""
        self.recalcular_c190_massa()
        if getattr(self, "_dlg_revisao", None) is not None:
            self._dlg_revisao.close()
        self.revisar_erros()

    def recalcular_c190_massa(self):
        """Refaz os C190 dos documentos em que a redução de base está zerada
        num CST x20/x70. Só mexe nesses documentos: recalcular o que já está
        certo seria substituir analítico sem motivo."""
        if not self.doc:
            return
        docs = self.doc.documentos_c190_com_reducao_zerada()
        if not docs:
            QMessageBox.information(
                self, "Recalcular C190",
                "Nenhum C190 com CST x20/x70 está com a redução de base "
                "zerada.")
            return
        n_c190 = sum(len(v) for _c, v in docs)
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Recalcular C190")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Question)
        caixa.setText(
            "<b>%d</b> documento(s) têm <b>%d</b> registro(s) C190 com CST "
            "x20/x70 e redução de base zerada.<br><br>"
            "O analítico desses documentos será <b>refeito a partir dos "
            "itens (C170)</b>, o que recompõe o VL_RED_BC.<br><br>"
            "Nos CST terminados em <b>70</b> o ICMS foi cobrado por "
            "substituição e não há base própria; quando o item tiver base de "
            "PIS/COFINS, ela é usada para achar a diferença.<br><br>"
            "Continuar?" % (len(docs), n_c190))
        b_ok = caixa.addButton("Recalcular",
                               QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_ok)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return

        res = self.doc.consolidar_c190_em_massa([c for c, _v in docs])
        self._marcar_alterado()
        self._montar_abas()
        restantes = len(rev.verificar_c190_reducao(self.doc))
        msg = ("%d documento(s) recalculados, %d grupo(s) C190 refeitos.\n\n"
               "• %d documento(s) tiveram a redução de base corrigida\n"
               "• %d grupo(s) usaram a base de PIS/COFINS (CST x70)\n"
               "• %d grupo(s) continuam sem base de onde tirar a redução"
               % (res["documentos"], res["criados"], res["corrigidos"],
                  res["base_pis_cofins"], res["sem_base"]))
        if restantes:
            msg += ("\n\nAinda há %d C190 com redução zerada: são itens sem "
                    "base de ICMS e sem base de PIS/COFINS, que precisam de "
                    "conferência manual." % restantes)
        QMessageBox.information(self, "Recalcular C190", msg)

    def preencher_cod_gen(self):
        """Deriva o COD_GEN do 0200 a partir do NCM (Tabela 4.2.1: o gênero
        são os dois primeiros dígitos). Como é derivável, não depende de a
        planilha trazer a coluna certa — e não erra o zero à esquerda."""
        if not self.doc:
            return
        div = self.doc.divergencias_cod_gen()
        if not div:
            QMessageBox.information(
                self, "COD_GEN pelo NCM",
                "Todos os itens com NCM já têm o COD_GEN do capítulo "
                "correspondente.")
            return
        vazios = sum(1 for _r, _c, _n, atual, _novo in div if not atual)
        trocas = len(div) - vazios
        amostra = "<br>".join(
            "&nbsp;&nbsp;• item <b>%s</b> · NCM %s → COD_GEN %s %s"
            % (cod, ncm, novo, ("(era %s)" % atual) if atual else "(vazio)")
            for _r, cod, ncm, atual, novo in div[:6])

        caixa = QMessageBox(self)
        caixa.setWindowTitle("COD_GEN pelo NCM")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Question)
        caixa.setText(
            "<b>%d</b> item(ns) do 0200 ficariam com o COD_GEN do capítulo do "
            "NCM — <b>%d</b> estão vazios e <b>%d</b> têm outro valor:"
            "<br><br>%s%s<br><br>Preencher?"
            % (len(div), vazios, trocas, amostra,
               "<br>&nbsp;&nbsp;…" if len(div) > 6 else ""))
        b_ok = caixa.addButton("Preencher",
                               QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_ok)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return

        res = self.doc.preencher_cod_gen(div)
        self._marcar_alterado()
        self._montar_abas()
        self.statusBar().showMessage(
            "COD_GEN: %d item(ns) preenchidos (%d vazios, %d corrigidos)."
            % (res["itens"], res["vazios"], res["trocados"]), 6000)

# -*- coding: utf-8 -*-
"""Ações do menu: ferramentas do efd icms/ipi"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from sped_tables.dominio import conferencia as cf
from sped_tables.dominio import revisao as rev
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.interface.comum import (calcular, ler_pasta_xml,
                                         lista_de_mudancas)
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
        num CST x20/x70, os das NFC-e com C170 fictícios (gerados dos XMLs
        para isso) e os que o guia acusa de não conferir com os itens
        (combinação sem par, soma fora da tolerância). Só mexe nesses
        documentos: recalcular o que já está certo seria substituir
        analítico sem motivo."""
        if not self.doc:
            return
        alvos = self.doc.documentos_para_refazer_c190()
        docs = [c for lista in alvos.values() for c in lista]
        if not docs:
            QMessageBox.information(
                self, "Recalcular C190",
                "Nenhum C190 com CST x20/x70 está com a redução de base "
                "zerada ou com chave repetida, nenhuma NFC-e tem C170 "
                "fictícios e todo C190 confere com os itens do documento.")
            return
        motivos = (
            ("reducao", "têm C190 com CST x20/x70 e redução de base zerada"),
            ("duplicados", "têm dois C190 com a mesma chave"),
            ("nfce", "são NFC-e com C170 fictícios gerados dos XMLs"),
            ("divergentes", "têm C190 que não confere com os itens "
                            "(combinação sem par ou soma diferente)"))
        texto = "".join("<b>%d</b> documento(s) %s.<br><br>"
                        % (len(alvos[m]), frase)
                        for m, frase in motivos if alvos.get(m))
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Recalcular C190")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Question)
        caixa.setText(
            texto
            + "O analítico desses documentos será <b>refeito a partir dos "
            "itens (C170)</b>, o que recompõe o VL_RED_BC.<br><br>"
            "Nos CST terminados em <b>70</b> o ICMS foi cobrado por "
            "substituição e não há base própria; quando o item tiver base de "
            "PIS/COFINS, ela é usada para achar a diferença.<br><br>"
            "Continuar?")
        b_ok = caixa.addButton("Recalcular",
                               QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_ok)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return

        ok, res = calcular(self, "Recalcular C190",
                           self.doc.consolidar_c190_em_massa, docs)
        if not ok:
            return
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
        if self.doc.documentos_65_com_c170():
            msg += ("\n\nFalta remover os C170 fictícios das NFC-e (*Remover "
                    "C170 fictícios da NFC-e*): com eles o arquivo é recusado "
                    "pelo PVA.")
        QMessageBox.information(self, "Recalcular C190", msg)

    def reducao_c190_pelo_xml(self):
        """Redução de base dos C190 de entrada com CST x20/x70 zerada, pela
        base reduzida que o XML de compra traz por item. É o caso do CST 070
        na entrada: o ICMS veio por ST e o arquivo não tem base própria."""
        if not self.doc or self.doc.layout != "ICMS":
            return
        titulo = "Redução de base pelos XMLs de compra"
        lote = ler_pasta_xml(self, titulo, "Pasta dos XMLs de compra (as "
                                           "subpastas entram)")
        if lote is None:
            return
        achados = cf.reducao_c190_pelo_xml(self.doc,
                                           lote.nfes + lote.sem_chave)
        faltam = len(rev.verificar_c190_reducao(self.doc))
        if not achados:
            QMessageBox.information(
                self, titulo,
                "Nenhum C190 com redução zerada tem XML de compra com base "
                "reduzida nesta pasta (%d C190 continuam com a redução "
                "zerada)." % faltam)
            return
        if QMessageBox.question(
                self, titulo,
                "%d de %d C190 com redução zerada têm a base no XML de "
                "compra.\n\nGravar o VL_RED_BC deles?"
                % (len(achados), faltam)) != QMessageBox.StandardButton.Yes:
            return
        n = cf.corrigir_reducao_c190(self.doc, achados)
        self._marcar_alterado()
        self._montar_abas()
        QMessageBox.information(
            self, titulo, "%d C190 com a redução gravada; %d continuam "
            "zerados." % (n, len(rev.verificar_c190_reducao(self.doc))))

    def recalcular_apuracao_icms(self):
        """Refaz os débitos do E110 pelos analíticos de saída — com o ICMS
        dos documentos extemporâneos (COD_SIT 01/07) no débito especial — e
        o saldo a partir deles."""
        if not self.doc or self.doc.layout != "ICMS":
            return
        titulo = "Apuração do ICMS (E110)"
        ok, mudou = calcular(self, titulo, self.doc.recalcular_e110)
        if not ok:
            return
        if mudou is None:
            QMessageBox.information(self, titulo, "O arquivo não tem E110.")
            return
        if not mudou:
            QMessageBox.information(
                self, titulo, "O E110 já confere com os analíticos.")
            return
        self._marcar_alterado()
        self._montar_abas()
        QMessageBox.information(
            self, titulo, "E110 recalculado:\n" + lista_de_mudancas(mudou)
            + "\n\nConfira o E116: a soma dele tem de ser o ICMS a recolher "
              "mais o débito especial.")

    def gerar_c170_ficticios_icms(self):
        """Cria, em cada NFC-e (65), um C170 fictício por item do XML. A
        NFC-e não tem C170, e sem itens o *Recalcular C190 em massa* não tem
        de onde refazer o analítico; com eles, refaz — inclusive a redução
        de base do CST x70, pela base de PIS/COFINS do XML. Depois, *Remover
        C170 fictícios*: o andaime não pode ir para o arquivo."""
        if not self.doc or self.doc.layout != "ICMS":
            return
        titulo = "C170 fictícios (NFC-e)"
        pasta = QFileDialog.getExistingDirectory(
            self, "Selecione a pasta com os XMLs das NFC-e (modelo 65)")
        if not pasta:
            return
        try:
            nfes, _erros = xf.ler_pasta(pasta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, titulo, "Erro ao ler:\n%s" % e)
            return
        nfe65 = [n for n in nfes if xf.norm(n.mod) == "65"]
        if not nfe65:
            QMessageBox.warning(
                self, titulo,
                "Nenhum XML de NFC-e (modelo 65) encontrado na pasta.")
            return
        res = self.doc.gerar_c170_ficticios_65(nfe65)
        if res["docs"]:
            self._marcar_alterado()
            self._montar_abas()
        msg = ("C170 fictícios criados: %d item(ns) em %d NFC-e.\n"
               "NFC-e do arquivo sem XML na pasta: %d."
               % (res["itens"], res["docs"], len(res["sem_xml"])))
        if res["csosn"]:
            msg += ("\n\n%d item(ns) vieram com CSOSN (emitente do "
                    "Simples) no lugar do CST: confira antes de refazer o "
                    "C190." % res["csosn"])
        msg += ("\n\nPróximos passos:\n"
                "1. Recalcular C190 (analítico) em massa\n"
                "2. Remover C170 fictícios da NFC-e (65)\n\n"
                "NFC-e com C170 é estrutura inválida: o arquivo não deve ser "
                "gravado com os fictícios.")
        QMessageBox.information(self, titulo, msg)

    def remover_c170_ficticios_icms(self):
        """Devolve as NFC-e à forma consolidada (sem C170)."""
        if not self.doc or self.doc.layout != "ICMS":
            return
        titulo = "Remover C170 fictícios"
        if not self.doc.documentos_65_com_c170():
            QMessageBox.information(
                self, titulo, "Nenhuma NFC-e (65) tem C170 no arquivo.")
            return
        res = self.doc.remover_c170_ficticios_65()
        self._marcar_alterado()
        self._montar_abas()
        QMessageBox.information(
            self, titulo, "%d C170 removido(s) de %d NFC-e."
            % (res["itens"], res["docs"]))

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

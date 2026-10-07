# -*- coding: utf-8 -*-
"""Ações do ERP: os sistemas e conexões, e corrigir o cadastro do arquivo
(0200, 0150) pelo banco do ERP — com a mesma prévia campo a campo da
correção pela planilha."""

from PyQt6.QtWidgets import QDialog, QMessageBox

from sped_tables.aplicacao import erp as caso
from sped_tables.dominio import participantes
from sped_tables.interface.dialogos.erp import (DialogoSistemasERP,
                                                escolher_conexao, no_banco)
from sped_tables.interface.dialogos.inventario import DialogoAtualizar0200


class ControladorERP:

    def sistemas_erp(self):
        DialogoSistemasERP(self, doc=self.doc).exec()

    def atualizar_0200_erp(self):
        self._cadastro_pelo_erp("produtos", "0200")

    def atualizar_0150_erp(self):
        self._cadastro_pelo_erp("participantes", "0150")

    def _cadastro_pelo_erp(self, entidade, registro):
        if not self.doc:
            return
        titulo = "Atualizar o %s pelo ERP" % registro
        par = escolher_conexao(self, self.doc, entidade, titulo)
        if par is None:
            return
        cfg, conexao = par
        linhas = no_banco(self, titulo, "Lendo o cadastro do ERP…",
                          lambda: caso.ler(cfg, conexao, entidade))
        if linhas is None:
            return
        if entidade == "produtos":
            previa = self.doc.previa_atualizacao_0200(linhas)
            avisos = self.doc.avisos_previa_0200(linhas, previa)
        else:
            previa = participantes.previa(self.doc, linhas)
            avisos = participantes.avisos(previa)
        if not previa:
            QMessageBox.information(
                self, titulo, "O %s do arquivo já está igual ao cadastro do "
                "ERP (%d registro(s) lido(s) de \"%s\")."
                % (registro, len(linhas), conexao.nome))
            return
        dlg = DialogoAtualizar0200(
            previa, avisos, self, registro=registro, sujeito="O ERP",
            titulo=titulo, botao="Aplicar")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        campos = dlg.escolhidos()
        if not campos:
            return
        if entidade == "produtos":
            contagem, _itens = self.doc.atualizar_0200(linhas, campos)
        else:
            contagem = participantes.atualizar(self.doc, linhas, campos)
        if contagem:
            self._marcar_alterado()
            self._montar_abas()
        self.statusBar().showMessage(
            "%s pelo ERP: %s." % (registro, ", ".join(
                "%s (%d)" % (c, n) for c, n in sorted(contagem.items()))
                or "nada mudou"), 15000)

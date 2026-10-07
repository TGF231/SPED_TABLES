# -*- coding: utf-8 -*-
"""Ações do menu: ferramentas que valem para os dois leiautes"""

import os
from collections import Counter

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox

from sped_tables.dominio import conferencia as cf
from sped_tables.dominio import diagnostico
from sped_tables.dominio import regras_guia
from sped_tables.dominio import revisao as rev
from sped_tables.dominio import validacao
from sped_tables.dominio import xml_fiscal as xf
from sped_tables.infra import cadastro, config
from sped_tables.interface.comum import (calcular, ler_nfes_da_pasta,
                                         lista_de_mudancas,
                                         ler_pasta_xml)
from sped_tables.interface.dialogos.cadastro import (
    DialogoCodCta, DialogoItensNaoUsados,
)
from sped_tables.interface.dialogos.conferencia import (
    DialogoConferencia, DialogoCorrelacoesCFOP,
)
from sped_tables.interface.dialogos.correcao import DialogoAlterarDatas
from sped_tables.interface.dialogos.geracao import DialogoGerarDeXml
from sped_tables.interface.dialogos.verificacao import (
    DialogoDiagnostico, DialogoRevisao, DialogoValidacao,
)


class ControladorGerais:
    """Ferramentas que valem para os dois leiautes.

    Mixin da `JanelaPrincipal`: usa `self.doc`, `self.statusBar()` e os
    demais membros da janela.
    """

    def gerar_de_xml(self):
        """Gera o SPED de um período só com os XMLs e a memória da empresa
        (`aplicacao/geracao_xml.py`). Gravado o arquivo, a pessoa pode
        abri-lo aqui para conferir e mandar ao PVA."""
        dlg = DialogoGerarDeXml(self, empresas=cadastro.carregar_empresas(),
                                correlacoes=self.correlacoes_cfop)
        dlg.exec()
        if dlg.abrir_depois:
            self.abrir_caminho(dlg.abrir_depois)

    def conferir_entradas_55(self):
        """Confere os itens das NF-e modelo 55 (entradas) de uma pasta de XMLs
        contra os C170 do SPED, vinculando por mod + série + nNF + nItem."""
        if not self.doc:
            return
        lidos = ler_nfes_da_pasta(
            self, "Conferir entradas",
            "Selecione a pasta com os XMLs das NF-e (modelo 55)")
        if lidos is None:
            return
        nfes, _erros = lidos
        if not any(xf.norm(n.mod) == "55" for n in nfes):
            QMessageBox.warning(
                self, "Conferir entradas",
                "Nenhum XML de NF-e modelo 55 foi encontrado na pasta.")
            return
        resultado = cf.conferir_entradas_55(
            self.doc, nfes, correlacoes_cfop=self.correlacoes_cfop)
        self.statusBar().showMessage(
            "Conferência: %d itens, %d divergência(s)."
            % (resultado["resumo"]["itens_conferidos"],
               resultado["resumo"]["divergencias"]))
        DialogoConferencia(resultado, self).exec()

    def conferir_itens_xml(self, tributo):
        """Confere os itens dos XMLs contra os C170, por tributo.

        O movimento (entradas/saídas) é escolhido dentro do diálogo, que
        refaz a comparação sem pedir a pasta de novo — reler dezenas de XMLs a
        cada troca seria desperdício.
        """
        if not self.doc:
            return
        lidos = ler_nfes_da_pasta(
            self, "Conferir itens",
            "Selecione a pasta com os XMLs das NF-e (modelo 55)")
        if lidos is None:
            return
        nfes, _erros = lidos
        if not any(xf.norm(n.mod) == "55" for n in nfes):
            QMessageBox.warning(
                self, "Conferir itens",
                "Nenhum XML de NF-e modelo 55 foi encontrado na pasta.")
            return
        self._dlg_conferencia = DialogoConferencia(
            None, self, doc=self.doc, nfes=nfes, tributo=tributo,
            correlacoes=self.correlacoes_cfop)
        self._dlg_conferencia.show()

    def escolher_pasta_pva(self):
        """Aponta onde os PVAs estão instalados (`config.definir_raiz_pva`).

        A detecção automática cobre a pasta padrão da RFB e as de Arquivos de
        Programas; instalação noutro lugar desligava as verificações que
        dependem das tabelas do PVA sem dizer nada. Pasta vazia volta à
        detecção.
        """
        atual = config.raiz_pva()
        pasta = QFileDialog.getExistingDirectory(
            self, "Pasta que contém Fiscal e EFD-Contribuicoes", atual)
        if not pasta:
            return
        pasta = os.path.normpath(pasta)
        achados = [nome for nome, cfg in config.PVAS.items()
                   if os.path.isdir(os.path.join(pasta, cfg["pasta"]))]
        if not achados:
            QMessageBox.warning(
                self, "Pasta dos PVAs",
                "Não encontrei nenhum PVA em:\n%s\n\nA pasta certa é a que "
                "contém as pastas \"Fiscal\" e/ou \"EFD-Contribuicoes\"."
                % pasta)
            return
        config.definir_raiz_pva(pasta)
        self._habilitar_acoes()
        self.statusBar().showMessage(
            "PVAs em %s (%s)." % (pasta, ", ".join(sorted(achados))), 10000)

    def editar_correlacoes_cfop(self):
        """Abre o editor da tabela de correlações de CFOP (saída -> entrada)."""
        def aplicar(novo_mapa):
            self.correlacoes_cfop = novo_mapa
            self.statusBar().showMessage(
                "Correlações de CFOP atualizadas (%d CFOP de saída)."
                % len(novo_mapa))
        DialogoCorrelacoesCFOP(
            self.correlacoes_cfop, self._caminho_correl, aplicar, self).exec()

    def datas_pelo_xml(self):
        """Acerta as datas do C100 pelo XML e passa à situação extemporânea
        (01/07) o documento emitido antes do período — o caso da NFC-e em
        contingência autorizada no mês seguinte. No ICMS/IPI a apuração
        acompanha: o ICMS dessas saídas é débito especial (E110)."""
        if not self.doc:
            return
        titulo = "Datas pelo XML"
        lote = ler_pasta_xml(self, titulo,
                             "Pasta dos XMLs do período (as subpastas entram)")
        if lote is None:
            return
        achados = cf.datas_pelo_xml(self.doc, lote.nfes)
        if not achados:
            QMessageBox.information(
                self, titulo, "As datas de todos os %d documento(s) com XML "
                "conferem." % len(lote.nfes))
            return
        por_campo = Counter(a["campo"] for a in achados)
        docs = len({id(a["c100"]) for a in achados})
        texto = ("<b>%d</b> documento(s) com data diferente do XML:<br><br>"
                 % docs)
        rotulos = {"DT_DOC": "data de emissão (DT_DOC)",
                   "DT_E_S": "data de saída (DT_E_S)",
                   "COD_SIT": "<b>situação 01/07 — extemporâneo</b> "
                              "(emitido antes do período)"}
        for campo in ("DT_DOC", "DT_E_S", "COD_SIT"):
            if campo in por_campo:
                texto += "• %s: %d<br>" % (rotulos[campo], por_campo[campo])
        if "COD_SIT" in por_campo and self.doc.layout == "ICMS":
            texto += ("<br>O ICMS das saídas extemporâneas passa a ser "
                      "<b>débito especial</b> no E110 (extra-apuração), e a "
                      "apuração é recalculada.")
        caixa = QMessageBox(self)
        caixa.setWindowTitle(titulo)
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Question)
        caixa.setText(texto + "<br><br>Aplicar?")
        b_ok = caixa.addButton("Aplicar", QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_ok)
        caixa.exec()
        if caixa.clickedButton() is not b_ok:
            return
        n, ndocs = cf.corrigir_datas_pelo_xml(self.doc, achados)
        msg = "%d campo(s) alterado(s) em %d documento(s)." % (n, ndocs)
        if self.doc.layout == "ICMS" and "COD_SIT" in por_campo:
            ok, mudou = calcular(self, titulo, self.doc.recalcular_e110)
            if ok and mudou:
                msg += "\n\nApuração (E110):\n" + lista_de_mudancas(mudou)
        self._marcar_alterado()
        self._montar_abas()
        QMessageBox.information(self, titulo, msg)

    def alterar_datas(self):
        """Altera datas de emissão/saída dos C100 conforme filtro de data."""
        if not self.doc:
            return
        dlg = DialogoAlterarDatas(self.doc, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.valores()
        if p is None:
            return
        res = self.doc.alterar_datas_c100(**p)
        self._marcar_alterado()
        self._montar_abas()
        campos = " e ".join(p["campos_alterar"])
        self.statusBar().showMessage(
            "Datas alteradas em %d documento(s) C100 (%s)."
            % (res["c100"], campos))
        QMessageBox.information(
            self, "Alterar datas",
            "%d documento(s) no filtro; %d alterado(s) (%s).%s"
            % (res["no_filtro"], res["c100"], campos,
               ("\n%d sem data válida no campo de filtro." % res["sem_data"])
               if res["sem_data"] else ""))

    def _acoes_dos_modulos(self):
        """Módulo de correção (o rótulo de `diagnostico.MODULOS` e de
        `Regra.modulo`) → método da janela. O diagnóstico e a revisão montam
        os botões daqui: um mapa por tela deixava módulo sem botão numa
        delas (o "Datas e extemporâneos pelos XMLs" no diagnóstico)."""
        return {
            "Corrigir campos pelo leiaute": self.validar_campos,
            "Itens do 0200 sem referência": self.itens_sem_referencia,
            "Preencher conta contábil (COD_CTA)": self.preencher_cod_cta,
            "Preencher COD_GEN pelo NCM": self.preencher_cod_gen,
            regras_guia.RECALCULAR_C190[0]: self.recalcular_c190_massa,
            regras_guia.ALTERAR_DATAS[0]: self.alterar_datas,
            "Datas e extemporâneos pelos XMLs": self.datas_pelo_xml,
            "Recalcular bloco M (apuração PIS/COFINS)":
                self.recalcular_bloco_m,
            "Empresa e rotinas": self.configurar_empresa,
            regras_guia.RECALCULAR_E110[0]: self.recalcular_apuracao_icms,
        }

    def revisar_erros(self):
        """Executa as regras de revisão e abre o relatório (não-modal, para
        permitir navegar até os registros enquanto a lista fica aberta)."""
        if not self.doc:
            return
        por_regra = rev.revisar_por_regra(self.doc)
        # cada verificação aponta para a função que a corrige; sem isso o
        # painel vira uma lista de reclamações sem saída
        acoes = {
            "C190 CST x20/x70 com VL_RED_BC zerado":
                ("Recalcular C190…", self._corrigir_c190_da_revisao),
            "Chave duplicada no mesmo registro-pai":
                ("Recalcular C190…", self._corrigir_c190_da_revisao),
            "Data de saída fora do período":
                ("Alterar datas…", self.alterar_datas),
            "COD_GEN incoerente com o NCM (0200)":
                ("Preencher COD_GEN…", self.preencher_cod_gen),
            "0200 não utilizados / duplicados":
                ("Itens sem referência…", self.itens_sem_referencia),
            "TIPO_ITEM fora da tabela (0200)":
                ("Corrigir campos…", self.validar_campos),
            "M210/M610 com receita bruta divergente":
                ("Recalcular bloco M…", self.recalcular_bloco_m),
            "M210/M610 com base de cálculo divergente":
                ("Recalcular bloco M…", self.recalcular_bloco_m),
            "M105/M505 fora da base de crédito dos documentos":
                ("Recalcular bloco M…", self.recalcular_bloco_m),
            "E110 com débitos diferentes dos analíticos":
                ("Recalcular E110…", self.recalcular_apuracao_icms),
            "CST 02 (monofásico) sem alíquota (C170)":
                ("Empresa e rotinas…", self.configurar_empresa),
            "Natureza da receita fora da tabela do CST (M410/M810)":
                ("Empresa e rotinas…", self.configurar_empresa),
            "Crédito em NCM monofásico ou de alíquota zero":
                ("Empresa e rotinas…", self.configurar_empresa),
            "Data de entrada/saída antes da emissão (C100)":
                ("Datas pelos XMLs…", self.datas_pelo_xml),
        }
        # as regras do guia: o botão sai do módulo da regra, pelo mesmo mapa
        # do diagnóstico (o C190 daqui reabre a revisão depois de corrigir)
        modulos = self._acoes_dos_modulos()
        modulos[regras_guia.RECALCULAR_C190[0]] = \
            self._corrigir_c190_da_revisao
        for regra in regras_guia.REGRAS:
            fn = modulos.get(regra.modulo)
            if fn is not None:
                acoes.setdefault(regra.rotulo, (regra.modulo + "…", fn))
        self._dlg_revisao = DialogoRevisao(
            por_regra, self.ir_para_registro, self, acoes=acoes)
        self._dlg_revisao.show()
        total = sum(len(ps) for _r, ps in por_regra)
        self.statusBar().showMessage("Revisão: %d ocorrência(s)." % total)

    def itens_sem_referencia(self):
        """Itens do 0200 que nenhum outro registro cita. O Guia Prático manda
        não informar item sem referência; a remoção fica com o usuário, depois
        de ver a lista e de onde vieram as referências."""
        if not self.doc:
            return
        refs = self.doc.referencias_de_itens()
        nao_usados = self.doc.itens_0200_nao_utilizados(refs)
        if not nao_usados:
            QMessageBox.information(
                self, "Itens do 0200 sem referência",
                "Todos os %d item(ns) do cadastro são referenciados em algum "
                "registro do arquivo." % len(refs["codigos"]))
            return
        self._dlg_itens = DialogoItensNaoUsados(
            self.doc, refs, nao_usados, self.ir_para_registro, self)
        self._dlg_itens.show()
        self.statusBar().showMessage(
            "%d de %d item(ns) do 0200 sem referência no arquivo."
            % (len(nao_usados), len(refs["codigos"])), 8000)

    def preencher_cod_cta(self):
        """Conta contábil dos registros que estão sem ela. Obrigatória nos
        perfis A e B — é o erro clássico do H010, cujo item não tem conta de
        estoque vinculada no ERP."""
        if not self.doc:
            return
        faltantes = self.doc.registros_sem_cod_cta()
        if not faltantes:
            QMessageBox.information(
                self, "Conta contábil",
                "Todos os registros que têm o campo COD_CTA já estão "
                "preenchidos.")
            return
        self._dlg_cod_cta = DialogoCodCta(self.doc, self)
        self._dlg_cod_cta.show()
        resumo = ", ".join("%s (%d)" % (t, len(v))
                           for t, v in sorted(faltantes.items(),
                                              key=lambda x: -len(x[1])))
        self.statusBar().showMessage("Sem conta contábil: %s." % resumo, 8000)

    def diagnosticar(self, automatico=False):
        """Passa o arquivo pelas camadas de verificação do PVA e mostra, por
        grupo, qual módulo corrige. Roda sozinho ao abrir — daí o
        `automatico`, que evita interromper quem abriu um arquivo limpo."""
        if not self.doc:
            return
        try:
            achados, info = diagnostico.verificar(self.doc)
        except Exception as exc:                            # noqa: BLE001
            if not automatico:
                QMessageBox.critical(self, "Diagnóstico",
                                     "Falha ao diagnosticar:\n%s" % exc)
            return
        total = sum(a.quantidade for a in achados)
        if automatico and not total:
            self.statusBar().showMessage(
                "Diagnóstico: nenhum problema nas verificações automáticas.",
                8000)
            return
        self._dlg_diag = DialogoDiagnostico(
            achados, info, self._acoes_dos_modulos(), self.ir_para_registro,
            self)
        self._dlg_diag.show()
        self.statusBar().showMessage(
            "Diagnóstico: %d problema(s) em %d verificação(ões)."
            % (total, len(achados)), 10000)

    def validar_campos(self):
        """Confere todo o arquivo contra o domínio de cada campo do leiaute.
        Não altera nada: quem grava é o botão de normalizar, dentro do
        diálogo, e só sobre o que tem conserto mecânico."""
        if not self.doc:
            return
        # as tabelas dos PVAs mandam: a lista de códigos válidos acompanha
        # a atualização do validador oficial sem mexer no código daqui
        dominios, info = validacao.dominios_do_documento(self.doc)
        achados = validacao.validar(self.doc, dominios_pva=dominios)
        if not achados:
            QMessageBox.information(
                self, "Validar campos pelo leiaute",
                "Nenhum campo preenchido está fora do domínio do leiaute.\n\n"
                "%s" % self._resumo_tabelas_pva(dominios, info))
            return
        self._dlg_validacao = DialogoValidacao(
            self.doc, achados, self.ir_para_registro, self,
            info_tabelas=self._resumo_tabelas_pva(dominios, info))
        self._dlg_validacao.show()
        auto = sum(1 for o in achados if o.sugestao is not None)
        self.statusBar().showMessage(
            "Validação: %d campo(s) fora do domínio, %d com conserto "
            "automático." % (len(achados), auto), 8000)

    @staticmethod
    def _resumo_tabelas_pva(dominios, info):
        """Diz de onde veio a validação. Sem isso o usuário não sabe se o
        resultado saiu das tabelas oficiais ou das regras embutidas.

        A chave de `dominios` é **(registro, campo)** desde que a validação
        passou a ter a granularidade do descritor do PVA. Tratá-la como nome
        de campo fazia `", ".join` estourar com `TypeError` — e exceção dentro
        de um slot do Qt derruba o processo, então a ação inteira ficou
        inutilizável. Aqui as duas formas são aceitas.
        """
        if not dominios:
            return ("Tabelas dos PVAs não encontradas — a verificação usou "
                    "apenas as regras embutidas. Instale os PVAs para validar "
                    "contra as mesmas tabelas do fisco.")
        # a lista dos nomes não informa nada (são 724 num arquivo real, em
        # ordem alfabética); o que responde "de onde veio isto" é a origem
        nomes = {k[1] if isinstance(k, tuple) else k for k in dominios}
        txt = ("Validação feita pelo descritor do PVA: %d par(es) "
               "registro/campo, em %d campo(s) distintos."
               % (len(dominios), len(nomes)))
        fontes = [(info.get("por_enum"), "enumeração do descritor"),
                  (info.get("por_tabela"), "tabela externa"),
                  (info.get("por_formato"), "tipo/tamanho do descritor")]
        detalhe = ", ".join("%d por %s" % (n, rot)
                            for n, rot in fontes if n)
        if detalhe:
            txt += "\nOrigem: %s." % detalhe
        if info.get("faltando"):
            txt += ("\nTabelas não encontradas: %s."
                    % ", ".join(info["faltando"]))
        return txt

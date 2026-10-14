# -*- coding: utf-8 -*-
"""Ações do menu: ferramentas do efd contribuições"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from sped_tables.dominio import xml_fiscal as xf
from sped_tables.infra import config
from sped_tables.interface.comum import (_br, abrir_janela, calcular,
                                         informar, ler_nfes_da_pasta)
from sped_tables.interface.dialogos.cadastro import DialogoEmpresa
from sped_tables.interface.dialogos.conferencia import DialogoDiscrepanciasC175
from sped_tables.interface.dialogos.correcao import (
    DialogoTrocarAliquotas, DialogoVerificarCST,
)


class ControladorContribuicoes:
    """Ferramentas do EFD Contribuições.

    Mixin da `JanelaPrincipal`: usa `self.doc`, `self.statusBar()` e os
    demais membros da janela.
    """

    def importar_xml_c175(self):
        """Importa XMLs de NFC-e (modelo 65) de uma pasta e consolida os C175
        dos C100 correspondentes (vínculo por mod + série + nNF)."""
        if not self.doc or self.doc.layout != "CONTRIB":
            informar(
                self, "Importar XMLs",
                "A consolidação de C175 a partir de XMLs aplica-se ao "
                "EFD Contribuições.")
            return
        lidos = ler_nfes_da_pasta(self, "Importar XMLs",
                                  "Selecione a pasta com os XMLs das NFC-e")
        if lidos is None:
            return
        nfes, erros = lidos
        if not nfes:
            QMessageBox.warning(
                self, "Importar XMLs",
                "Nenhum XML de NF-e/NFC-e válido foi encontrado na pasta.")
            return

        from sped_tables.dominio.sped_layouts import campos
        cols = campos("C100", self.doc.layout, 30)
        i_mod = cols.index("COD_MOD")
        i_ser = cols.index("SER")
        i_num = cols.index("NUM_DOC")
        c100s = [r for r in self.doc.registros if r.reg == "C100"]

        def ch_c100(r):
            return (xf.norm(r.valor(i_mod)), xf.norm(r.valor(i_ser)),
                    xf.norm(r.valor(i_num)))

        # apenas NFC-e (modelo 65) geram C175
        nfes65 = [n for n in nfes if xf.norm(n.mod) == "65"]
        n55 = sum(1 for n in nfes if xf.norm(n.mod) == "55")
        pares, so_xml, _ = xf.vincular(nfes65, xf.chave_doc, c100s, ch_c100)

        n_doc = n_c175 = 0
        for nfe, casados in pares:
            res = self.doc.consolidar_c175_de_itens(casados[0], nfe.itens)
            if res and not res.get("sem_itens"):
                n_doc += 1
                n_c175 += res["criados"]

        if n_doc:
            self._marcar_alterado()
            self._montar_abas()

        msg = ("Importação concluída:\n\n"
               "• %d XML(s) lido(s)  —  NFC-e (65): %d, NF-e (55): %d\n"
               "• %d documento(s) C100 consolidados\n"
               "• %d registro(s) C175 gerados\n"
               % (len(nfes), len(nfes65), n55, n_doc, n_c175))
        if so_xml:
            msg += "• %d NFC-e sem C100 correspondente no SPED\n" % len(so_xml)
        if n55:
            msg += ("• %d NF-e modelo 55 ignoradas (usam C170, não C175)\n"
                    % n55)
        if erros:
            msg += "• %d arquivo(s) com erro de leitura\n" % len(erros)
        msg += ("\nVL_PIS/VL_COFINS dos C100 e os totais (C990/9900) foram "
                "atualizados.")
        self.statusBar().showMessage(
            "Importação de XMLs: %d C100 consolidados, %d C175 gerados."
            % (n_doc, n_c175))
        informar(self, "Importar XMLs", msg)

    def recalcular_bloco_m(self):
        """Recalcula a apuração do bloco M (M200/M210 e M600/M610) conforme o
        regime declarado no registro 0110."""
        if not self.doc or self.doc.layout != "CONTRIB":
            informar(
                self, "Bloco M",
                "A apuração do bloco M aplica-se ao EFD Contribuições.")
            return
        ok, res = calcular(self, "Bloco M", self.doc.recalcular_bloco_m)
        if not ok:
            return
        if not res:
            QMessageBox.warning(self, "Bloco M",
                                "Não foi possível recalcular o bloco M.")
            return
        self._marcar_alterado()
        self._montar_abas()

        def linha(t, d):
            if isinstance(d, dict):
                return ("• %s: apurado R$ %s  |  a recolher R$ %s"
                        % (t, _br(d["apurado"]), _br(d["a_recolher"])))
            return "• %s: %s" % (t, d)

        cred = res.get("creditos") or {}
        if cred:
            det = "\n".join(
                "• crédito de %s: base refeita em %d grupo(s), "
                "R$ %s disponível, R$ %s descontado"
                % (t, d["grupos"], _br(d["disponivel"]), _br(d["descontado"]))
                for t, d in sorted(cred.items()))
            obs = ("Os créditos (M100/M105 e M500/M505) foram **refeitos** "
                   "a partir das entradas: um grupo por alíquota, com a "
                   "natureza da base vinda do CFOP pela tabela do PVA. O "
                   "desconto vai até o limite do débito do período; o resto "
                   "fica como saldo.\n\n" + det)
        else:
            obs = ("Observação: os créditos (M100/M105/M500/M505) foram "
                   "preservados — %s."
                   % (res.get("creditos_motivo")
                      or "não havia o que refazer"))
        msg = ("Apuração recalculada — regime %s.\n\n%s\n%s\n\n"
               "As bases e contribuições foram somadas das receitas "
               "tributadas de saída (C175/C170) por alíquota.\n\n%s"
               % (res.get("regime", "?"),
                  linha("PIS", res.get("PIS", "—")),
                  linha("COFINS", res.get("COFINS", "—")), obs))
        self.statusBar().showMessage("Bloco M recalculado (regime %s)."
                                     % res.get("regime", "?"))
        informar(self, "Bloco M", msg)

    def validar_c175_65(self):
        """Importa XMLs de NFC-e (modelo 65), gera C170 fictícios por item e
        mostra as discrepâncias com o C175 escriturado."""
        if not self.doc or self.doc.layout != "CONTRIB":
            informar(
                self, "Validar C175 (modelo 65)",
                "Disponível apenas no EFD Contribuições.")
            return
        lidos = ler_nfes_da_pasta(
            self, "Validar C175",
            "Selecione a pasta com os XMLs das NFC-e (modelo 65)")
        if lidos is None:
            return
        nfe65 = [n for n in lidos[0] if xf.norm(n.mod) == "65"]
        if not nfe65:
            QMessageBox.warning(
                self, "Validar C175",
                "Nenhum XML de NFC-e (modelo 65) encontrado na pasta.")
            return
        res = self.doc.gerar_c170_ficticios_65(nfe65)
        div = self.doc.discrepancias_c175_65()
        self._marcar_alterado()
        self._montar_abas()
        abrir_janela(self, DialogoDiscrepanciasC175(res, div, self))

    def regenerar_c175_65(self):
        """Regenera o C175 a partir dos C170 fictícios (já corrigidos) e remove
        os fictícios, restaurando a estrutura consolidada do modelo 65."""
        if not self.doc or self.doc.layout != "CONTRIB":
            return
        pendentes = len(self.doc.documentos_65_com_c170())
        if not pendentes:
            informar(
                self, "Regenerar C175",
                "Não há C170 fictícios (modelo 65) para consolidar. Rode antes "
                "\"Validar C175 (modelo 65) com XMLs\".")
            return
        # o impacto em valores antes de aplicar: num arquivo real, o PDV havia
        # emitido parte das NFC-e com alíquota de não-cumulativo enquanto a
        # empresa é cumulativa — regenerar às cegas aumentaria o tributo
        # declarado, desfazendo uma escrituração que estava correta
        p = self.doc.previa_regeneracao_c175_65() or {}
        d = p.get("delta") or {}
        muda = any(abs(d.get(k, 0.0)) > 0.005 for k in ("pis", "cofins", "opr"))
        detalhe = ""
        if muda:
            detalhe = (
                "<br><br><b>Atenção: os valores vão mudar.</b>"
                "<table cellpadding=3>"
                "<tr><td></td><td align=right><b>escriturado</b></td>"
                "<td align=right><b>após regenerar</b></td>"
                "<td align=right><b>diferença</b></td></tr>"
                "<tr><td>PIS</td><td align=right>%s</td><td align=right>%s</td>"
                "<td align=right><b>%+.2f</b></td></tr>"
                "<tr><td>COFINS</td><td align=right>%s</td>"
                "<td align=right>%s</td><td align=right><b>%+.2f</b></td></tr>"
                "<tr><td>Valor da operação</td><td align=right>%s</td>"
                "<td align=right>%s</td><td align=right><b>%+.2f</b></td></tr>"
                "</table>"
                "<br>Confira se a diferença é a correção que você quer: os "
                "valores vêm dos <b>XMLs</b>, e é possível que a escrituração "
                "esteja certa e o XML errado."
                % (_br(p["atual"]["pis"]), _br(p["novo"]["pis"]),
                   d.get("pis", 0.0),
                   _br(p["atual"]["cofins"]), _br(p["novo"]["cofins"]),
                   d.get("cofins", 0.0),
                   _br(p["atual"]["opr"]), _br(p["novo"]["opr"]),
                   d.get("opr", 0.0)))
        else:
            detalhe = ("<br><br>Os totais de PIS, COFINS e valor da operação "
                       "<b>não mudam</b>.")

        caixa = QMessageBox(self)
        caixa.setWindowTitle("Regenerar C175")
        caixa.setTextFormat(Qt.TextFormat.RichText)
        caixa.setIcon(QMessageBox.Icon.Warning if muda
                      else QMessageBox.Icon.Question)
        caixa.setText(
            "Regenerar o C175 de <b>%d</b> documento(s) modelo 65 a partir dos "
            "itens C170 e remover os fictícios.%s" % (pendentes, detalhe))
        b_sim = caixa.addButton("Regenerar", QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.setDefaultButton(b_sim if not muda else caixa.buttons()[-1])
        caixa.exec()
        if caixa.clickedButton() is not b_sim:
            return
        ok, r = calcular(self, "Regenerar C175",
                         self.doc.regenerar_c175_de_c170_65)
        if not ok:
            return
        self._marcar_alterado()
        self._montar_abas()
        informar(
            self, "Regenerar C175",
            "C175 regenerado em %d documento(s); %d registro(s) C175 gerado(s). "
            "Os C170 fictícios foram removidos." % (r["docs"], r["c175"]))

    def _salvar_cfg_tabelas(self, cfg):
        self.cfg_tabelas = cfg
        try:
            config.gravar_tabelas_rfb(cfg)
        except OSError as exc:
            self.statusBar().showMessage(
                "Não foi possível guardar a configuração das tabelas: %s"
                % exc, 10000)

    def _data_fin_doc(self):
        """DT_FIN do registro 0000 (DDMMAAAA), para referência de vigência."""
        if not self.doc:
            return ""
        i = self.doc._ix("0000", "DT_FIN")
        for r in self.doc.registros:
            if r.reg == "0000":
                return (r.valor(i) or "").strip() if i is not None else ""
        return ""

    def verificar_cst_ncm(self):
        """Verifica o CST de PIS/COFINS dos itens C170 por NCM, usando as
        tabelas oficiais da RFB (alíquota zero e monofásicos)."""
        if not self.doc or self.doc.layout != "CONTRIB":
            informar(
                self, "Verificar CST",
                "Esta verificação aplica-se ao EFD Contribuições (CST de "
                "PIS/COFINS por NCM).")
            return
        self._dlg_cst = abrir_janela(self, DialogoVerificarCST(
            self.doc, self.cfg_tabelas, self._data_fin_doc(),
            self._salvar_cfg_tabelas, self))

    def trocar_aliquotas(self):
        """Troca alíquotas de PIS/COFINS (saídas C175 / entradas C170) e
        recalcula os valores."""
        if not self.doc or self.doc.layout != "CONTRIB":
            informar(
                self, "Trocar alíquotas",
                "Esta ferramenta aplica-se ao EFD Contribuições (registros "
                "C175 de saída e C170 de entrada).")
            return
        dlg = DialogoTrocarAliquotas(self.doc, self)
        doc = self.doc

        def aplicar():
            if self.doc is not doc:
                return
            aliq_pis, aliq_cofins, apenas_trib, escopo, de_pis, de_cof = \
                dlg.valores()
            if aliq_pis is None and aliq_cofins is None:
                return
            ok, res = calcular(
                self, "Trocar alíquotas", doc.trocar_aliquotas_pis_cofins,
                aliq_pis=aliq_pis, aliq_cofins=aliq_cofins,
                apenas_tributados=apenas_trib, escopo=escopo,
                de_pis=de_pis, de_cofins=de_cof)
            if not ok:
                return
            if res.get("sem_alvo"):
                alvo = "C175/C170 de saída" if escopo == "saidas" else \
                    ("C170 de entrada" if escopo == "entradas" else "C170/C175")
                informar(
                    self, "Trocar alíquotas",
                    "Nenhum registro %s foi encontrado neste arquivo." % alvo)
                return
            self._marcar_alterado()
            self._montar_abas()
            rot_escopo = {"saidas": "saídas (C175 + C170)",
                          "entradas": "entradas (C170)",
                          "todos": "todos os itens (C170 e C175)"}[escopo]
            partes = []
            if aliq_pis is not None:
                partes.append("PIS → %s%%" % ("%.4f" % aliq_pis).rstrip("0")
                              .rstrip("."))
            if aliq_cofins is not None:
                partes.append("COFINS → %s%%" % ("%.4f" % aliq_cofins)
                              .rstrip("0").rstrip("."))
            self.statusBar().showMessage(
                "Alíquotas atualizadas em %s (%s): %d registros, %d C100."
                % (rot_escopo, ", ".join(partes), res["itens"], res["c100"]))
            informar(
                self, "Trocar alíquotas",
                "Escopo: %s\n%s\n\n%d registro(s) recalculado(s) em %d "
                "documento(s) C100.\nNovos totais no escopo: VL_PIS = %s, "
                "VL_COFINS = %s\n\nA apuração (bloco M) ainda é a de antes."
                % (rot_escopo, ", ".join(partes), res["itens"], res["c100"],
                   _br(res["vl_pis"]), _br(res["vl_cofins"])),
                proximos=(("Recalcular bloco M…", self.recalcular_bloco_m),))
        abrir_janela(self, dlg, ao_aceitar=aplicar)

    def configurar_empresa(self):
        """Cadastro da empresa e rotinas de conferência/correção.

        Não-modal (`show()`), para o usuário navegar até um registro apontado
        sem fechar o diálogo — por isso a referência fica guardada, senão o
        coletor de lixo leva a janela embora.
        """
        if self.doc is None:
            return
        self._dlg_empresa = abrir_janela(self, DialogoEmpresa(
            self.doc, self, cfg_rfb=getattr(self, "cfg_tabelas", None)))

# -*- coding: utf-8 -*-
"""Inventário (bloco H) a partir de planilha, comparação e atualização do 0200."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from sped_tables.interface.comum import exportar_csv
from sped_tables.interface import tema
from sped_tables.interface.comum import _br


# ---------------------------------------------------------------------------
# Diálogo de resultado da conferência de entradas (NF-e 55)
# ---------------------------------------------------------------------------
class DialogoComparaInventario(QDialog):
    """Resultado da comparação entre o inventário escriturado (H010) e a
    planilha — por código e quantidade, sem alterar o arquivo."""

    COLS = ["Situação", "Código do item", "Qtde. SPED", "Qtde. planilha",
            "Diferença"]

    def __init__(self, res, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comparar inventário com a planilha")
        self.resize(760, 560)
        lay = QVBoxLayout(self)

        resumo = QLabel(
            "Conferem: <b>%d</b> &nbsp;·&nbsp; Quantidade divergente: "
            "<b>%d</b> &nbsp;·&nbsp; Só no SPED: <b>%d</b> &nbsp;·&nbsp; "
            "Só na planilha: <b>%d</b><br>Soma das quantidades — SPED: "
            "<b>%s</b> &nbsp;|&nbsp; planilha: <b>%s</b>"
            % (res["iguais"], len(res["divergentes"]), len(res["so_sped"]),
               len(res["so_planilha"]), _br(res["tot_sped"]),
               _br(res["tot_planilha"])))
        resumo.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(resumo)

        pal = tema.atual()
        linhas = []
        for cod, qs, qp, dif in res["divergentes"]:
            linhas.append(("Quantidade difere", cod, _br(qs), _br(qp),
                           _br(dif), pal.bad))
        for cod, q in res["so_sped"]:
            linhas.append(("Só no SPED", cod, _br(q), "—", "", pal.warn))
        for cod, q in res["so_planilha"]:
            linhas.append(("Só na planilha", cod, "—", _br(q), "", pal.info))

        self.tab = QTableWidget(len(linhas), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True)
        # a ordenação só é ligada depois de preencher: com ela ativa, cada
        # setItem reordena a tabela e as células seguintes caem em outra linha
        self.tab.setSortingEnabled(False)
        self.tab.horizontalHeader().setStretchLastSection(True)
        for i, ln in enumerate(linhas):
            for c, v in enumerate(ln[:5]):
                it = QTableWidgetItem(str(v))
                if c == 0:
                    it.setForeground(QColor(ln[5]))
                self.tab.setItem(i, c, it)
        # o indicador -1 precisa vir ANTES de ligar a ordenação: o
        # QTableWidget ordena o próprio modelo e, depois de ordenado,
        # não há como voltar à ordem de montagem (divergentes -> só no SPED -> só na planilha).
        # O clique no cabeçalho continua ordenando normalmente.
        self.tab.horizontalHeader().setSortIndicator(
            -1, Qt.SortOrder.AscendingOrder)
        self.tab.setSortingEnabled(True)
        # sem limitar a precisão, o ajuste de largura mede as 5 células de
        # cada linha — num inventário inteiro (11 mil itens) isso trava a
        # abertura do diálogo por segundos. As 200 primeiras bastam.
        self.tab.horizontalHeader().setResizeContentsPrecision(200)
        self.tab.resizeColumnsToContents()
        lay.addWidget(self.tab, 1)

        self._linhas = linhas
        rod = QHBoxLayout()
        if not linhas:
            ok = QLabel("Inventário e planilha conferem integralmente.")
            ok.setProperty("role", "ok")
            rod.addWidget(ok)
        rod.addStretch(1)
        b_csv = QPushButton("Exportar CSV")
        b_csv.clicked.connect(self._exportar)
        b_csv.setEnabled(bool(linhas))
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.accept)
        rod.addWidget(b_csv)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    def _exportar(self):
        exportar_csv(self, "Exportar comparação", "comparacao_inventario.csv",
                     self.COLS, (ln[:5] for ln in self._linhas))


class DialogoAtualizar0200(QDialog):
    """Escolha, campo a campo, do que a planilha vai corrigir no cadastro
    0200 já existente.

    Existe porque "sobrescrever tudo" não é seguro: no arquivo real que
    motivou a função, a planilha corrigia 447 NCM truncados — e ao mesmo
    tempo plantaria `TIPO_ITEM` inválido em 1.273 itens que estavam certos.
    Quem decide é quem conhece a empresa, mas só depois de ver os números.
    """

    COLS = ["", "Campo", "Itens", "Exemplo"]

    def __init__(self, previa, avisos=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atualizar o cadastro 0200 pela planilha")
        self.resize(760, 460)
        self.previa = previa
        avisos = avisos or {}
        lay = QVBoxLayout(self)

        total = sum(len(v) for v in previa.values())
        lay.addWidget(QLabel(
            "A planilha mudaria <b>%d</b> valor(es) no cadastro de itens. "
            "Marque o que deve ser corrigido:" % total))

        pal = tema.atual()
        self.tab = QTableWidget(len(previa), len(self.COLS))
        self.tab.setHorizontalHeaderLabels(self.COLS)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self._campos = []
        ordem = sorted(previa.items(), key=lambda x: -len(x[1]))
        for i, (campo, lst) in enumerate(ordem):
            self._campos.append(campo)
            _qtd, _txt, desmarcar = avisos.get(campo, (0, "", False))
            it = QTableWidgetItem("")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # campo cujo valor novo é inválido nasce desmarcado
            it.setCheckState(Qt.CheckState.Unchecked if desmarcar
                             else Qt.CheckState.Checked)
            self.tab.setItem(i, 0, it)
            rot = QTableWidgetItem(campo)
            if campo in avisos:
                rot.setForeground(QColor(pal.bad if desmarcar else pal.warn))
            self.tab.setItem(i, 1, rot)
            self.tab.setItem(i, 2, QTableWidgetItem(str(len(lst))))
            exemplo = "; ".join("%s: %s → %s" % (c, a or "(vazio)", b)
                                for c, a, b in lst[:2])
            self.tab.setItem(i, 3, QTableWidgetItem(exemplo))
        self.tab.resizeColumnsToContents()
        lay.addWidget(self.tab, 1)

        for campo, (qtd, texto, desmarcar) in sorted(avisos.items()):
            av = QLabel("⚠ <b>%s</b> — %d item(ns): %s.%s"
                        % (campo, qtd, texto,
                           " Deixei desmarcado." if desmarcar else ""))
            av.setWordWrap(True)
            av.setProperty("role", "erro" if desmarcar else "aviso")
            lay.addWidget(av)

        nota = QLabel(
            "Coluna não mapeada e célula vazia nunca apagam o que já está no "
            "cadastro.")
        nota.setWordWrap(True)
        nota.setProperty("role", "dica")
        lay.addWidget(nota)

        rod = QHBoxLayout()
        rod.addStretch(1)
        b_ok = QPushButton("Aplicar e importar")
        b_ok.clicked.connect(self.accept)
        b_ca = QPushButton("Cancelar")
        b_ca.clicked.connect(self.reject)
        rod.addWidget(b_ok)
        rod.addWidget(b_ca)
        lay.addLayout(rod)

    def escolhidos(self):
        """Campos marcados, no formato aceito por `importar_inventario_h010`."""
        return {self._campos[i] for i in range(self.tab.rowCount())
                if self.tab.item(i, 0).checkState() == Qt.CheckState.Checked}


class DialogoImportarInventario(QDialog):
    """Importa uma planilha (XLSX/CSV) e gera o inventário do bloco H (H005 e
    H010), criando no 0200 apenas os itens que ainda não estão cadastrados."""

    # (chave canônica, rótulo, obrigatório, palavras-chave p/ auto-detecção)
    CAMPOS = [
        ("cod_item", "Código do item (COD_ITEM)", True,
         ("cod_item", "codigo do item", "cod. item", "cod item", "codigo",
          "código", "cod prod", "produto", "item")),
        ("descr_item", "Descrição (0200)", False,
         ("descr", "descricao", "descrição", "nome do produto", "nome")),
        ("unid", "Unidade (UNID)", True,
         ("unid", "unidade", "un.")),
        ("qtd", "Quantidade (QTD)", True,
         ("qtd", "quantidade", "quant", "estoque", "saldo")),
        ("vl_unit", "Valor unitário (VL_UNIT)", False,
         ("vl_unit", "valor unitario", "valor unitário", "vl unit",
          "unitario", "unitário", "custo", "preco", "preço")),
        ("vl_item", "Valor total (VL_ITEM)", False,
         ("vl_item", "valor total", "vl total", "total")),
        ("ind_prop", "Indicador de propriedade (IND_PROP)", False,
         ("ind_prop", "propriedade", "posse")),
        ("cod_part", "Participante (COD_PART)", False,
         ("cod_part", "participante", "fornecedor")),
        ("txt_compl", "Complemento (TXT_COMPL)", False,
         ("txt_compl", "complement", "observ", "obs")),
        ("cod_cta", "Conta contábil (COD_CTA)", False,
         ("cod_cta", "conta contabil", "conta contábil", "conta")),
        ("vl_item_ir", "Valor item IR (VL_ITEM_IR)", False,
         ("vl_item_ir", "valor ir", "ir")),
        ("tipo_item", "Tipo do item (0200)", False, ("tipo",)),
        ("cod_ncm", "NCM (0200)", False, ("ncm",)),
        ("cod_barra", "Código de barras (0200)", False,
         ("barra", "ean", "gtin")),
        ("ex_ipi", "EX IPI (0200)", False, ("ex_ipi", "ex ipi")),
        ("cod_gen", "Gênero (0200)", False, ("cod_gen", "genero", "gênero")),
        ("aliq_icms", "Alíquota ICMS (0200)", False,
         ("aliq_icms", "aliquota", "alíquota", "aliq")),
        ("cest", "CEST (0200)", False, ("cest",)),
    ]
    MOTIVOS = [("01", "01 - Final do período"),
               ("02", "02 - Mudança de tributação da mercadoria"),
               ("03", "03 - Solicitação da baixa cadastral/paralisação"),
               ("04", "04 - Alteração de regime de pagamento"),
               ("05", "05 - Determinação dos fiscos"),
               ("06", "06 - Controle das mercadorias sujeitas a ST")]

    def __init__(self, doc, dt_padrao, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.cabecalho = []
        self.linhas_brutas = []
        self.setWindowTitle("Importar inventário (bloco H) de planilha")
        self.resize(720, 640)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Selecione a planilha com o inventário (a primeira linha deve ser o "
            "cabeçalho). As colunas são reconhecidas automaticamente pelo nome; "
            "ajuste o mapeamento se necessário. Os itens que ainda não existirem "
            "no <b>0200</b> serão cadastrados — os já existentes não são "
            "duplicados.")
        info.setWordWrap(True)
        lay.addWidget(info)

        lin = QHBoxLayout()
        self.ed_arq = QLineEdit()
        self.ed_arq.setPlaceholderText("Planilha .xlsx / .csv")
        b_sel = QPushButton("Selecionar…")
        b_sel.clicked.connect(self._escolher)
        lin.addWidget(self.ed_arq, 1)
        lin.addWidget(b_sel)
        lay.addLayout(lin)

        cab = QHBoxLayout()
        cab.addWidget(QLabel("Data do inventário:"))
        self.ed_dt = QLineEdit(dt_padrao or "")
        self.ed_dt.setPlaceholderText("DDMMAAAA")
        self.ed_dt.setMaximumWidth(110)
        cab.addWidget(self.ed_dt)
        cab.addSpacing(12)
        cab.addWidget(QLabel("Motivo:"))
        self.cb_motivo = QComboBox()
        for _c, rot in self.MOTIVOS:
            self.cb_motivo.addItem(rot)
        cab.addWidget(self.cb_motivo, 1)
        cab.addSpacing(12)
        cab.addWidget(QLabel("IND_PROP padrão:"))
        self.ed_prop = QLineEdit("0")
        self.ed_prop.setMaximumWidth(40)
        cab.addWidget(self.ed_prop)
        lay.addLayout(cab)

        self.chk_atualizar = QCheckBox(
            "Atualizar o cadastro (0200) dos itens que já existem com os "
            "dados da planilha")
        self.chk_atualizar.setToolTip(
            "Use quando o 0200 do arquivo é que está errado — NCM truncado, "
            "descrição velha, CEST ausente.\n"
            "Só mexe nas colunas mapeadas acima, e célula vazia não apaga o "
            "que já está no cadastro.")
        lay.addWidget(self.chk_atualizar)

        grupo = QGroupBox("Mapeamento das colunas")
        scr = QScrollArea()
        scr.setWidgetResizable(True)
        interno = QWidget()
        form = QFormLayout(interno)
        self.combos = {}
        for chave, rotulo, obrig, _kw in self.CAMPOS:
            cb = QComboBox()
            cb.addItem("(não usar)")
            self.combos[chave] = cb
            form.addRow(rotulo + (" *" if obrig else ""), cb)
        scr.setWidget(interno)
        gl = QVBoxLayout(grupo)
        gl.addWidget(scr)
        lay.addWidget(grupo, 1)

        self.lbl = QLabel("Selecione uma planilha para começar.")
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)

        rod = QHBoxLayout()
        b_conf = QPushButton("Conferir com o 0200")
        b_conf.clicked.connect(self._conferir)
        b_comp = QPushButton("Comparar com inventário atual")
        b_comp.setToolTip("Compara o H010 já escriturado com a planilha "
                          "(código e quantidade), sem alterar o arquivo")
        b_comp.clicked.connect(self._comparar)
        self.b_imp = QPushButton("Importar inventário")
        self.b_imp.clicked.connect(self._importar)
        self.b_imp.setEnabled(False)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.reject)
        rod.addWidget(b_conf)
        rod.addWidget(b_comp)
        rod.addStretch(1)
        rod.addWidget(self.b_imp)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)

    # ------------------------------------------------------------ leitura
    def _escolher(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Planilha do inventário", "",
            "Planilhas (*.xlsx *.xlsm *.csv);;Todos (*.*)")
        if not caminho:
            return
        self.ed_arq.setText(caminho)
        try:
            self.cabecalho, self.linhas_brutas = self._ler(caminho)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Planilha",
                                 "Não foi possível ler:\n%s" % exc)
            return
        for cb in self.combos.values():
            cb.clear()
            cb.addItem("(não usar)")
            for h in self.cabecalho:
                cb.addItem(str(h))
        self._auto_mapear()
        self.lbl.setText("Planilha lida: %d linha(s), %d coluna(s)."
                         % (len(self.linhas_brutas), len(self.cabecalho)))
        self.b_imp.setEnabled(True)

    @staticmethod
    def _ler(caminho):
        """Devolve (cabecalho, linhas) da primeira aba/arquivo."""
        if caminho.lower().endswith(".csv"):
            import csv
            linhas = []
            # UTF-8 primeiro, e com `-sig` para comer o BOM: latin-1 aceita
            # qualquer byte e nunca falha, então tentá-lo antes tornava o
            # resto código morto — CSV salvo do Excel em UTF-8 entrava com a
            # acentuação corrompida e com o BOM colado no **nome da primeira
            # coluna**, o que sozinho já quebrava o mapeamento do cabeçalho.
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    with open(caminho, encoding=enc, newline="") as fh:
                        amostra = fh.read(4096)
                        fh.seek(0)
                        try:
                            dialeto = csv.Sniffer().sniff(amostra, ";,\t")
                        except csv.Error:
                            dialeto = csv.excel
                            dialeto.delimiter = ";"
                        linhas = list(csv.reader(fh, dialeto))
                    break
                except UnicodeDecodeError:
                    continue
            if not linhas:
                return [], []
            return linhas[0], linhas[1:]
        import openpyxl
        wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        ws = wb.active
        linhas = []
        cabecalho = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                cabecalho = [("" if v is None else v) for v in row]
                continue
            if all(v is None or str(v).strip() == "" for v in row):
                continue
            linhas.append(list(row))
        return cabecalho, linhas

    def _auto_mapear(self):
        """Pré-seleciona cada coluna pelo nome do cabeçalho."""
        norm = [str(h).strip().lower() for h in self.cabecalho]
        usados = set()
        for chave, _rot, _ob, palavras in self.CAMPOS:
            achou = None
            for p in palavras:                      # 1º: igualdade
                for j, h in enumerate(norm):
                    if j not in usados and h == p:
                        achou = j
                        break
                if achou is not None:
                    break
            if achou is None:                       # 2º: contém
                for p in palavras:
                    for j, h in enumerate(norm):
                        if j not in usados and p in h:
                            achou = j
                            break
                    if achou is not None:
                        break
            if achou is not None:
                usados.add(achou)
                self.combos[chave].setCurrentIndex(achou + 1)

    def _linhas_mapeadas(self):
        """Converte as linhas da planilha em dicts com as chaves canônicas."""
        mapa = {}
        for chave, _r, _o, _k in self.CAMPOS:
            i = self.combos[chave].currentIndex() - 1
            if i >= 0:
                mapa[chave] = i
        faltando = [rot for ch, rot, ob, _k in self.CAMPOS
                    if ob and ch not in mapa]
        if faltando:
            QMessageBox.warning(
                self, "Mapeamento",
                "Informe a coluna para: %s" % ", ".join(faltando))
            return None
        out = []
        for row in self.linhas_brutas:
            d = {}
            for chave, i in mapa.items():
                d[chave] = row[i] if i < len(row) else None
            if str(d.get("cod_item") or "").strip():
                out.append(d)
        return out

    # ------------------------------------------------------------- ações
    def _conferir(self):
        linhas = self._linhas_mapeadas()
        if linhas is None:
            return
        c = self.doc.conferir_itens_inventario(linhas)
        div = c["divergentes"]
        texto = ("<b>%d</b> item(ns) na planilha · <b>%d</b> já cadastrados no "
                 "0200 · <b>%d</b> serão criados."
                 % (len(linhas), len(c["existentes"]), len(c["novos"])))
        if c["duplicados"]:
            texto += ("<br><span style='color:#b60'>%d código(s) repetido(s) na "
                      "planilha — só a primeira ocorrência será usada.</span>"
                      % len(c["duplicados"]))
        if c.get("sem_qtd") or c.get("sem_valor"):
            texto += ("<br><span style='color:#b60'>%d item(ns) com quantidade "
                      "zero e %d sem valor — serão escriturados como estão."
                      "</span>" % (c.get("sem_qtd", 0), c.get("sem_valor", 0)))
        if c.get("ncm_truncado"):
            texto += ("<br><span style='color:#b60'>%d item(ns) com NCM de 7 "
                      "dígitos no <b>0200 deste arquivo</b> (zero à esquerda "
                      "perdido) — o NCM da planilha confere; corrija o cadastro."
                      "</span>" % len(c["ncm_truncado"]))
        if div:
            amostra = "; ".join("%s: %s (0200) ≠ %s (planilha)"
                                % (d[0], d[2][:24], d[3][:24]) for d in div[:3])
            texto += ("<br><span style='color:#b00'>%d divergência(s) com o "
                      "cadastro 0200 — o cadastro atual é mantido. %s%s</span>"
                      % (len(div), amostra, " …" if len(div) > 3 else ""))
        self.lbl.setText(texto)

    def _comparar(self):
        """Compara o inventário já escriturado com a planilha, sem alterar."""
        linhas = self._linhas_mapeadas()
        if linhas is None:
            return
        res = self.doc.comparar_inventario_h010(linhas)
        if res["sem_h010"]:
            QMessageBox.information(
                self, "Comparar inventário",
                "O arquivo ainda não tem inventário escriturado (nenhum H010) "
                "para comparar. Use \"Importar inventário\" para gerá-lo.")
            return
        n = (len(res["divergentes"]) + len(res["so_sped"])
             + len(res["so_planilha"]))
        self.lbl.setText(
            "Comparação com o inventário atual: <b>%d</b> item(ns) conferem, "
            "<b>%d</b> com quantidade diferente, <b>%d</b> só no SPED, "
            "<b>%d</b> só na planilha."
            % (res["iguais"], len(res["divergentes"]), len(res["so_sped"]),
               len(res["so_planilha"])))
        DialogoComparaInventario(res, self).exec()
        if n == 0:
            self.lbl.setText(self.lbl.text() + "  ✔ Tudo confere.")

    def _importar(self):
        linhas = self._linhas_mapeadas()
        if linhas is None:
            return
        dt = self.ed_dt.text().strip()
        if len(dt) != 8 or not dt.isdigit():
            QMessageBox.critical(self, "Data",
                                 "Informe a data do inventário (DDMMAAAA).")
            return
        n_h = sum(1 for r in self.doc.registros if r.reg in ("H005", "H010"))
        if n_h:
            resp = QMessageBox.question(
                self, "Inventário existente",
                "Já existem %d registro(s) H005/H010 no arquivo. Eles serão "
                "substituídos pelo inventário da planilha. Continuar?" % n_h,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return
        # correção do cadastro existente: mostra a prévia e deixa escolher
        # campo a campo antes de gravar qualquer coisa
        atualizar = set()
        if self.chk_atualizar.isChecked():
            previa = self.doc.previa_atualizacao_0200(linhas)
            if not previa:
                QMessageBox.information(
                    self, "Atualizar o cadastro 0200",
                    "O cadastro dos itens já existentes está igual à "
                    "planilha — nada a corrigir.")
            else:
                avisos = self.doc.avisos_previa_0200(linhas, previa)
                dlg = DialogoAtualizar0200(previa, avisos, self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                atualizar = dlg.escolhidos()

        res = self.doc.importar_inventario_h010(
            linhas, dt_inv=dt,
            mot_inv=self.MOTIVOS[self.cb_motivo.currentIndex()][0],
            ind_prop_padrao=self.ed_prop.text().strip() or "0",
            atualizar_0200=atualizar)
        if res.get("erro"):
            QMessageBox.critical(self, "Importar inventário", res["erro"])
            return
        jan = self.parent()
        if jan is not None:
            if hasattr(jan, "_marcar_alterado"):
                jan._marcar_alterado()
            if hasattr(jan, "_montar_abas"):
                jan._montar_abas()
        extra = ""
        if res.get("atualizados_0200"):
            por_campo = ", ".join(
                "%s (%d)" % (c, n)
                for c, n in sorted(res["campos_0200"].items(),
                                   key=lambda x: -x[1]))
            extra += ("\n• %d cadastro(s) do 0200 corrigido(s) pela planilha"
                      "\n   %s" % (res["atualizados_0200"], por_campo))
        if res["ignorados"]:
            extra += ("\n• %d código(s) repetido(s) ignorado(s)"
                      % len(res["ignorados"]))
        QMessageBox.information(
            self, "Importar inventário",
            "Inventário gerado:\n\n"
            "• %d registro(s) H010\n"
            "• Valor total do inventário: %s\n"
            "• %d item(ns) novo(s) cadastrado(s) no 0200\n"
            "• %d unidade(s) nova(s) no 0190%s"
            % (res["itens"], _br(res["vl_inv"]), res["novos_0200"],
               res["novos_0190"], extra))
        self.accept()

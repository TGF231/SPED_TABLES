# -*- coding: utf-8 -*-
"""Sistemas ERP e conexões.

**Sistema** é o perfil de um ERP: o tipo de banco e, para cada informação
que o SPED Tables entende (produtos, participantes, XMLs, estoque), a
tabela e a coluna onde ela está — apontadas aqui, escolhendo da lista que o
próprio banco devolve, sem escrever SQL. **Conexão** é o banco de um
cliente que usa aquele sistema, vinculada ao CNPJ da empresa: abrir o SPED
da empresa já sabe de onde buscar.

Falar com o banco pode demorar (servidor na rede, 10 s de espera para
conectar): tudo passa por `comum.em_segundo_plano`, com Cancelar.
"""

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from sped_tables.aplicacao import erp as caso
from sped_tables.dominio import erp
from sped_tables.dominio.empresas import dados_do_arquivo
from sped_tables.infra.paralelo import Cancelado
from sped_tables.interface.comum import em_segundo_plano
from sped_tables.interface.comum import abrir_janela, informar

NAO_USAR = "(não usar)"
CODIFICACOES = ["", "WIN1252", "ISO8859_1", "UTF8", "NONE", "cp850",
                "cp1252", "latin-1", "utf8mb4"]
TITULO = "Sistemas ERP"


def no_banco(pai, titulo, texto, trabalho):
    """Roda `trabalho()` fora da thread da interface. Devolve o resultado,
    ou None se a pessoa cancelou ou o banco recusou — o erro já foi
    mostrado."""
    try:
        return em_segundo_plano(pai, titulo, texto,
                                lambda _p, _c: trabalho())
    except Cancelado:
        return None
    except (caso.ErroDeBanco, ValueError) as exc:
        QMessageBox.warning(pai, titulo, str(exc))
        return None


def escolher_conexao(pai, doc, entidade, titulo):
    """A conexão do ERP vinculada à empresa do arquivo que oferece a
    entidade: `(cfg, conexao)`, ou None — e aí a pessoa já sabe por quê."""
    cnpj = dados_do_arquivo(doc)[0] if doc is not None else ""
    cfg = caso.carregar()
    candidatas = caso.conexoes_da_empresa(cfg, cnpj, entidade)
    if not candidatas:
        informar(
            pai, titulo,
            "Nenhuma conexão de ERP vinculada a esta empresa (CNPJ %s) traz "
            "%s.\n\nCadastre em Ferramentas → Configurações → Sistemas ERP: a conexão do banco, "
            "o CNPJ vinculado e, no sistema, a tabela e as colunas de \"%s\"."
            % (cnpj or "?", erp.ENTIDADES[entidade].rotulo.lower(),
               erp.ENTIDADES[entidade].rotulo))
        return None
    if len(candidatas) == 1:
        return cfg, candidatas[0]
    nomes = [c.nome for c in candidatas]
    nome, ok = QInputDialog.getItem(pai, titulo, "Conexão:", nomes, 0, False)
    if not ok or nome not in nomes:
        return None
    return cfg, candidatas[nomes.index(nome)]


# ============================================================ prévia
class DialogoPrevia(QDialog):
    """As linhas como o programa vai recebê-las."""

    def __init__(self, entidade, linhas, parent=None):
        super().__init__(parent)
        ent = erp.ENTIDADES[entidade]
        self.setWindowTitle("Pré-visualizar — %s" % ent.rotulo)
        self.resize(900, 420)
        lay = QVBoxLayout(self)
        infos = [i for i in ent.informacoes
                 if any(i.chave in ln for ln in linhas)]
        lay.addWidget(QLabel("%d linha(s) lida(s) do banco, já nas "
                             "informações do SPED Tables:" % len(linhas)))
        tab = QTableWidget(len(linhas), len(infos))
        tab.setHorizontalHeaderLabels([i.rotulo for i in infos])
        tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, ln in enumerate(linhas):
            for c, info in enumerate(infos):
                v = ln.get(info.chave)
                if isinstance(v, bytes):
                    v = "(%d bytes)" % len(v)
                elif isinstance(v, str) and len(v) > 120:
                    v = v[:120] + "…"
                tab.setItem(r, c, QTableWidgetItem("" if v is None else
                                                   str(v)))
        tab.resizeColumnsToContents()
        lay.addWidget(tab, 1)
        b = QPushButton("Fechar")
        b.clicked.connect(self.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)


# ======================================================== uma entidade
class EditorEntidade(QWidget):
    """De onde sai uma entidade: a tabela (ou consulta própria) e a coluna
    de cada informação."""

    def __init__(self, entidade, dono):
        super().__init__()
        self.entidade = entidade
        self.ent = erp.ENTIDADES[entidade]
        self.dono = dono
        self._colunas = []
        lay = QVBoxLayout(self)
        desc = QLabel(self.ent.descricao)
        desc.setWordWrap(True)
        desc.setProperty("role", "dica")
        lay.addWidget(desc)

        origem = QHBoxLayout()
        self.rb_tabela = QRadioButton("Tabela:")
        self.rb_tabela.setChecked(True)
        self.cb_tabela = QComboBox()
        self.cb_tabela.setEditable(True)
        self.cb_tabela.setMinimumWidth(260)
        self.rb_sql = QRadioButton("Consulta própria (para juntar tabelas)")
        origem.addWidget(self.rb_tabela)
        origem.addWidget(self.cb_tabela, 1)
        origem.addWidget(self.rb_sql)
        lay.addLayout(origem)
        self.ed_sql = QPlainTextEdit()
        self.ed_sql.setPlaceholderText(
            "SELECT P.CODIGO, P.DESCRICAO, N.NCM FROM PRODUTOS P "
            "JOIN NCM N ON N.ID = P.ID_NCM")
        self.ed_sql.setMaximumHeight(80)
        self.ed_sql.setVisible(False)
        lay.addWidget(self.ed_sql)
        self.rb_sql.toggled.connect(self._origem_mudou)

        botoes = QHBoxLayout()
        b_cols = QPushButton("Ler colunas")
        b_cols.setToolTip("Lê as colunas e uma linha de exemplo da tabela")
        b_cols.clicked.connect(self.ler_colunas)
        b_sug = QPushButton("Sugerir pelo nome")
        b_sug.clicked.connect(self.sugerir)
        b_prev = QPushButton("Pré-visualizar")
        b_prev.setToolTip("Lê as primeiras linhas como o programa vai "
                          "recebê-las")
        b_prev.clicked.connect(self.previsualizar)
        for b in (b_cols, b_sug, b_prev):
            botoes.addWidget(b)
        botoes.addStretch(1)
        lay.addLayout(botoes)

        scr = QScrollArea()
        scr.setWidgetResizable(True)
        interno = QWidget()
        self.form = QFormLayout(interno)
        self.cb_empresa = QComboBox()
        self.cb_empresa.setToolTip(
            "Só para bancos que guardam várias empresas: a coluna com o "
            "código da empresa (o valor fica em cada conexão)")
        linha_emp = QHBoxLayout()
        linha_emp.addWidget(self.cb_empresa, 1)
        linha_emp.addWidget(QLabel(""), 1)
        self.form.addRow("Coluna da empresa (opcional)", linha_emp)
        self.combos, self.exemplos = {}, {}
        for info in self.ent.informacoes:
            cb = QComboBox()
            ex = QLabel("")
            ex.setProperty("role", "dica")
            linha = QHBoxLayout()
            linha.addWidget(cb, 1)
            linha.addWidget(ex, 1)
            rot = info.rotulo + (" *" if info.obrigatoria else "")
            self.form.addRow(rot, linha)
            self.combos[info.chave] = cb
            self.exemplos[info.chave] = ex
        scr.setWidget(interno)
        lay.addWidget(scr, 1)
        self._preencher_combos([])

    # ------------------------------------------------------------ estado
    def _origem_mudou(self, sql):
        self.ed_sql.setVisible(sql)
        self.cb_tabela.setEnabled(not sql)

    def _preencher_combos(self, colunas, exemplo=None):
        self._colunas = list(colunas)
        atuais = {k: self._coluna(cb) for k, cb in self.combos.items()}
        atual_emp = self._coluna(self.cb_empresa)
        for chave, cb in list(self.combos.items()) + [("", self.cb_empresa)]:
            cb.blockSignals(True)
            cb.clear()
            cb.addItem(NAO_USAR)
            cb.addItems(self._colunas)
            cb.blockSignals(False)
        for chave, col in atuais.items():
            self._escolher(self.combos[chave], col)
        self._escolher(self.cb_empresa, atual_emp)
        exemplo = exemplo or {}
        for chave, cb in self.combos.items():
            v = exemplo.get(self._coluna(cb))
            if isinstance(v, bytes):
                v = "(%d bytes)" % len(v)
            txt = "" if v is None else str(v)
            self.exemplos[chave].setText(
                ("ex.: " + txt[:40]) if txt else "")
        self._exemplo = exemplo

    @staticmethod
    def _coluna(cb):
        t = cb.currentText()
        return "" if t == NAO_USAR else t

    @staticmethod
    def _escolher(cb, coluna):
        if not coluna:
            cb.setCurrentIndex(0)
            return
        i = cb.findText(coluna)
        if i < 0:                   # coluna do perfil que a lista não tem
            cb.addItem(coluna)
            i = cb.count() - 1
        cb.setCurrentIndex(i)

    def definir_tabelas(self, tabelas):
        atual = self.cb_tabela.currentText()
        self.cb_tabela.clear()
        self.cb_tabela.addItems(tabelas)
        self.cb_tabela.setCurrentText(atual)

    def carregar(self, mapeamento):
        self.rb_sql.setChecked(bool(mapeamento.sql))
        self.rb_tabela.setChecked(not mapeamento.sql)
        self.ed_sql.setPlainText(mapeamento.sql)
        self.cb_tabela.setCurrentText(mapeamento.tabela)
        self._preencher_combos(self._colunas)
        for chave, cb in self.combos.items():
            self._escolher(cb, mapeamento.colunas.get(chave, ""))
        self._escolher(self.cb_empresa, mapeamento.coluna_empresa)

    def mapeamento(self):
        sql = self.ed_sql.toPlainText().strip() if self.rb_sql.isChecked() \
            else ""
        return erp.Mapeamento(
            "" if sql else self.cb_tabela.currentText().strip(), sql,
            {k: self._coluna(cb) for k, cb in self.combos.items()},
            self._coluna(self.cb_empresa))

    # ------------------------------------------------------------ ações
    def _origem(self):
        return self.mapeamento().origem

    def ler_colunas(self):
        par = self.dono.para_ler_estrutura()
        if par is None:
            return
        sistema, conexao = par
        res = no_banco(self, TITULO, "Lendo as colunas…",
                       lambda: caso.amostra(sistema, conexao,
                                            self._origem(), 1))
        if res is None:
            return
        cols, linhas = res
        exemplo = dict(zip(cols, linhas[0])) if linhas else {}
        self._preencher_combos(cols, exemplo)
        if not any(self._coluna(cb) for cb in self.combos.values()):
            self.sugerir()

    def sugerir(self):
        if not self._colunas:
            informar(self, TITULO,
                     "Leia as colunas da tabela primeiro.")
            return
        for chave, col in erp.sugerir(self.entidade, self._colunas).items():
            if not self._coluna(self.combos[chave]):
                self._escolher(self.combos[chave], col)
        self._preencher_combos(self._colunas, self._exemplo)

    def previsualizar(self):
        par = self.dono.para_ler_estrutura()
        if par is None:
            return
        sistema, conexao = par
        sistema = erp.Sistema(sistema.nome, sistema.banco,
                              {self.entidade: self.mapeamento()})
        faltam = erp.problemas(sistema, self.entidade)
        if faltam:
            QMessageBox.warning(self, TITULO, "\n".join(faltam))
            return
        linhas = no_banco(self, TITULO, "Lendo do banco…",
                          lambda: caso.previa(sistema, conexao,
                                              self.entidade))
        if linhas is not None:
            abrir_janela(self, DialogoPrevia(self.entidade, linhas, self))


# ======================================================== o diálogo
class DialogoSistemasERP(QDialog):

    def __init__(self, parent=None, doc=None):
        super().__init__(parent)
        self.setWindowTitle(TITULO)
        self.resize(1080, 700)
        self.doc = doc
        self.cfg = caso.carregar()
        self._inicial = self._serial()
        self._con_atual = self._sis_atual = None
        lay = QVBoxLayout(self)
        aviso = QLabel(
            "O programa só <b>lê</b> o banco do ERP. Mesmo assim, use um "
            "usuário do banco com permissão só de leitura.")
        aviso.setProperty("role", "dica")
        lay.addWidget(aviso)
        if self.cfg.senhas_perdidas:
            perdida = QLabel(
                "A senha destas conexões não pôde ser lida (configuração "
                "trazida de outra conta ou computador) — informe de novo: %s"
                % ", ".join(self.cfg.senhas_perdidas))
            perdida.setProperty("role", "aviso")
            perdida.setWordWrap(True)
            lay.addWidget(perdida)
        self.abas = QTabWidget()
        self.abas.addTab(self._montar_conexoes(), "Conexões")
        self.abas.addTab(self._montar_sistemas(), "Sistemas (perfis de ERP)")
        lay.addWidget(self.abas, 1)
        rod = QHBoxLayout()
        self.lbl = QLabel("")
        rod.addWidget(self.lbl, 1)
        b_salvar = QPushButton("Salvar")
        b_salvar.clicked.connect(self.salvar)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.close)
        rod.addWidget(b_salvar)
        rod.addWidget(b_fechar)
        lay.addLayout(rod)
        self._listar()
        if not self.cfg.sistemas:
            self.abas.setCurrentIndex(1)

    # ------------------------------------------------------- conexões
    def _montar_conexoes(self):
        w = QSplitter()
        esq = QWidget()
        le = QVBoxLayout(esq)
        self.lst_con = QListWidget()
        self.lst_con.currentRowChanged.connect(self._mostrar_conexao)
        le.addWidget(self.lst_con, 1)
        bl = QHBoxLayout()
        b_nova = QPushButton("Nova")
        b_nova.clicked.connect(self.nova_conexao)
        b_exc = QPushButton("Excluir")
        b_exc.clicked.connect(self.excluir_conexao)
        bl.addWidget(b_nova)
        bl.addWidget(b_exc)
        le.addLayout(bl)
        w.addWidget(esq)

        dir_ = QWidget()
        f = QFormLayout(dir_)
        self.c_nome = QLineEdit()
        self.c_sistema = QComboBox()
        self.c_host = QLineEdit()
        self.c_host.setPlaceholderText("servidor ou IP (vazio = este "
                                       "computador)")
        self.c_porta = QLineEdit()
        self.c_porta.setPlaceholderText("padrão do banco")
        self.c_base = QLineEdit()
        b_base = QPushButton("Procurar…")
        b_base.clicked.connect(self._escolher_base)
        linha_base = QHBoxLayout()
        linha_base.addWidget(self.c_base, 1)
        linha_base.addWidget(b_base)
        self.c_usuario = QLineEdit()
        self.c_senha = QLineEdit()
        self.c_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.c_cod = QComboBox()
        self.c_cod.setEditable(True)
        self.c_cod.addItems(CODIFICACOES)
        self.c_cod.lineEdit().setPlaceholderText("padrão do banco")
        self.c_empresa = QLineEdit()
        self.c_empresa.setPlaceholderText("código da empresa no ERP, se "
                                          "o banco tiver várias")
        self.c_cnpjs = QLineEdit()
        self.c_cnpjs.setPlaceholderText("CNPJs separados por vírgula")
        b_vinc = QPushButton("Vincular ao arquivo aberto")
        b_vinc.setEnabled(self.doc is not None)
        b_vinc.clicked.connect(self._vincular)
        linha_cnpj = QHBoxLayout()
        linha_cnpj.addWidget(self.c_cnpjs, 1)
        linha_cnpj.addWidget(b_vinc)
        f.addRow("Nome", self.c_nome)
        f.addRow("Sistema", self.c_sistema)
        f.addRow("Servidor", self.c_host)
        f.addRow("Porta", self.c_porta)
        f.addRow("Banco / arquivo / pasta", linha_base)
        f.addRow("Usuário", self.c_usuario)
        f.addRow("Senha", self.c_senha)
        f.addRow("Codificação", self.c_cod)
        f.addRow("Empresa no ERP", self.c_empresa)
        f.addRow("Empresas (CNPJ)", linha_cnpj)
        b_testar = QPushButton("Testar conexão")
        b_testar.clicked.connect(self.testar)
        linha_testar = QHBoxLayout()
        linha_testar.addWidget(b_testar)
        linha_testar.addStretch(1)
        f.addRow("", linha_testar)
        dica = QLabel(
            "Firebird: caminho do .fdb no servidor (ou o apelido). SQL "
            "Server: servidor\\instância e o nome do banco; sem usuário, "
            "entra com a conta do Windows. DBF: a pasta dos arquivos. A "
            "senha é guardada cifrada pelo Windows.")
        dica.setWordWrap(True)
        dica.setProperty("role", "dica")
        f.addRow("", dica)
        self.form_con = dir_
        w.addWidget(dir_)
        w.setStretchFactor(1, 3)
        return w

    def _escolher_base(self):
        sistema = self.cfg.sistemas.get(self.c_sistema.currentData())
        banco = sistema.banco if sistema else ""
        if banco == "dbf":
            p = QFileDialog.getExistingDirectory(self, "Pasta dos DBF")
        else:
            p, _f = QFileDialog.getOpenFileName(
                self, "Arquivo do banco", "",
                "Bancos (*.fdb *.gdb *.db *.sqlite *.sqlite3);;Todos (*.*)")
        if p:
            self.c_base.setText(p)

    def _vincular(self):
        cnpj = dados_do_arquivo(self.doc)[0]
        atuais = [c.strip() for c in self.c_cnpjs.text().split(",")
                  if c.strip()]
        if cnpj and cnpj not in atuais:
            atuais.append(cnpj)
        self.c_cnpjs.setText(", ".join(atuais))

    def _mostrar_conexao(self, linha):
        self._guardar_conexao()
        self._con_atual = None
        if not 0 <= linha < len(self.cfg.conexoes):
            self.form_con.setEnabled(False)
            return
        self.form_con.setEnabled(True)
        c = self.cfg.conexoes[linha]
        self.c_nome.setText(c.nome)
        self._encher_sistemas(c.sistema)
        self.c_host.setText(c.host)
        self.c_porta.setText(c.porta)
        self.c_base.setText(c.base)
        self.c_usuario.setText(c.usuario)
        self.c_senha.setText(c.senha)
        self.c_cod.setCurrentText(c.codificacao)
        self.c_empresa.setText(c.empresa)
        self.c_cnpjs.setText(", ".join(c.cnpjs))
        self._con_atual = c

    def _encher_sistemas(self, atual):
        self.c_sistema.clear()
        for ident in sorted(self.cfg.sistemas,
                            key=lambda k: self.cfg.sistemas[k].nome.lower()):
            s = self.cfg.sistemas[ident]
            self.c_sistema.addItem("%s (%s)" % (s.nome, erp.BANCOS.get(
                s.banco, s.banco)), ident)
        i = self.c_sistema.findData(atual)
        self.c_sistema.setCurrentIndex(max(i, 0))

    def _guardar_conexao(self):
        c = self._con_atual
        if c is None:
            return
        novo = erp.Conexao(
            nome=self.c_nome.text().strip() or c.nome,
            sistema=self.c_sistema.currentData() or "",
            host=self.c_host.text(), porta=self.c_porta.text(),
            base=self.c_base.text(), usuario=self.c_usuario.text(),
            senha=self.c_senha.text(), codificacao=self.c_cod.currentText(),
            empresa=self.c_empresa.text(),
            cnpjs=self.c_cnpjs.text().split(","), ident=c.ident)
        i = self.cfg.conexoes.index(c)
        self.cfg.conexoes[i] = novo
        self._con_atual = novo
        item = self.lst_con.item(i)
        if item is not None:
            item.setText(novo.nome)

    def nova_conexao(self):
        if not self.cfg.sistemas:
            informar(
                self, TITULO, "Cadastre primeiro o sistema (o perfil do "
                "ERP), na aba ao lado.")
            self.abas.setCurrentIndex(1)
            return
        self._guardar_conexao()
        nome = self.cfg.nome_livre("Nova conexão",
                                   [c.nome for c in self.cfg.conexoes])
        cnpjs = [dados_do_arquivo(self.doc)[0]] if self.doc else []
        sistema = self._sis_atual.ident if self._sis_atual else \
            next(iter(self.cfg.sistemas))
        self.cfg.conexoes.append(erp.Conexao(
            nome, sistema, cnpjs=cnpjs,
            ident=self._ident_livre(nome, [c.ident for c in
                                           self.cfg.conexoes])))
        self._listar(con=len(self.cfg.conexoes) - 1)

    def excluir_conexao(self):
        i = self.lst_con.currentRow()
        if not 0 <= i < len(self.cfg.conexoes):
            return
        self._con_atual = None
        del self.cfg.conexoes[i]
        self._listar(con=min(i, len(self.cfg.conexoes) - 1))

    def _conexao_do_formulario(self):
        self._guardar_conexao()
        c = self._con_atual
        if c is None:
            return None
        sistema = self.cfg.sistema_da(c)
        if sistema is None:
            QMessageBox.warning(self, TITULO, "Escolha o sistema da "
                                "conexão.")
            return None
        return sistema, c

    def testar(self):
        par = self._conexao_do_formulario()
        if par is None:
            return
        versao = no_banco(self, TITULO, "Conectando…",
                          lambda: caso.testar(*par))
        if versao is not None:
            informar(self, TITULO,
                     "Conectou: %s" % versao)

    # ------------------------------------------------------- sistemas
    def _montar_sistemas(self):
        w = QSplitter()
        esq = QWidget()
        le = QVBoxLayout(esq)
        self.lst_sis = QListWidget()
        self.lst_sis.currentRowChanged.connect(self._mostrar_sistema)
        le.addWidget(self.lst_sis, 1)
        bl = QHBoxLayout()
        for rot, fn in (("Novo", self.novo_sistema),
                        ("Duplicar", self.duplicar_sistema),
                        ("Excluir", self.excluir_sistema)):
            b = QPushButton(rot)
            b.clicked.connect(fn)
            bl.addWidget(b)
        le.addLayout(bl)
        w.addWidget(esq)

        dir_ = QWidget()
        ld = QVBoxLayout(dir_)
        f = QFormLayout()
        self.s_nome = QLineEdit()
        self.s_banco = QComboBox()
        for k, rot in erp.BANCOS.items():
            self.s_banco.addItem(rot, k)
        self.s_con = QComboBox()
        b_tab = QPushButton("Carregar tabelas")
        b_tab.clicked.connect(self.carregar_tabelas)
        linha = QHBoxLayout()
        linha.addWidget(self.s_con, 1)
        linha.addWidget(b_tab)
        f.addRow("Nome do sistema", self.s_nome)
        f.addRow("Banco de dados", self.s_banco)
        f.addRow("Ler a estrutura pela conexão", linha)
        ld.addLayout(f)
        self.abas_ent = QTabWidget()
        self.editores = {}
        for chave, ent in erp.ENTIDADES.items():
            ed = EditorEntidade(chave, self)
            self.editores[chave] = ed
            self.abas_ent.addTab(ed, ent.rotulo)
        ld.addWidget(self.abas_ent, 1)
        self.form_sis = dir_
        w.addWidget(dir_)
        w.setStretchFactor(1, 3)
        return w

    def _sistemas_ordenados(self):
        return sorted(self.cfg.sistemas.values(), key=lambda s: s.nome.lower())

    def _mostrar_sistema(self, linha):
        self._guardar_sistema()
        self._sis_atual = None
        lista = self._sistemas_ordenados()
        if not 0 <= linha < len(lista):
            self.form_sis.setEnabled(False)
            return
        self.form_sis.setEnabled(True)
        s = lista[linha]
        self.s_nome.setText(s.nome)
        self.s_banco.setCurrentIndex(max(self.s_banco.findData(s.banco), 0))
        self.s_con.clear()
        for c in self.cfg.conexoes:
            if c.sistema == s.ident:
                self.s_con.addItem(c.nome, c.ident)
        for chave, ed in self.editores.items():
            ed.carregar(s.mapeamento(chave))
        self._sis_atual = s
        self._marcar_abas()

    def _guardar_sistema(self):
        s = self._sis_atual
        if s is None:
            return
        s.nome = self.s_nome.text().strip() or s.nome
        s.banco = self.s_banco.currentData()
        s.entidades = {k: ed.mapeamento() for k, ed in self.editores.items()
                       if not ed.mapeamento().vazio}
        self._marcar_abas()

    def _marcar_abas(self):
        s = self._sis_atual
        for i, chave in enumerate(self.editores):
            rot = erp.ENTIDADES[chave].rotulo
            if s is not None and s.oferece(chave):
                rot = "✔ " + rot
            self.abas_ent.setTabText(i, rot)

    @staticmethod
    def _ident_livre(nome, existentes):
        base = erp.Sistema(nome, "").ident
        ident, n = base, 2
        while ident in existentes:
            ident, n = "%s_%d" % (base, n), n + 1
        return ident

    def novo_sistema(self, _=False, modelo=None):
        self._guardar_sistema()
        nome = self.cfg.nome_livre(
            modelo.nome + " (cópia)" if modelo else "Novo sistema",
            [s.nome for s in self.cfg.sistemas.values()])
        ident = self._ident_livre(nome, self.cfg.sistemas)
        dados = modelo.para_dict() if modelo else {"banco": "firebird"}
        s = erp.Sistema(nome, dados.get("banco", "firebird"),
                        dados.get("entidades"), ident)
        self.cfg.sistemas[ident] = s
        self._listar(sis=self._sistemas_ordenados().index(s))

    def duplicar_sistema(self):
        if self._sis_atual is not None:
            self.novo_sistema(modelo=self._sis_atual)

    def excluir_sistema(self):
        s = self._sis_atual
        if s is None:
            return
        usando = [c.nome for c in self.cfg.conexoes if c.sistema == s.ident]
        if usando:
            QMessageBox.warning(self, TITULO,
                                "O sistema é usado pelas conexões: %s."
                                % ", ".join(usando))
            return
        self._sis_atual = None
        del self.cfg.sistemas[s.ident]
        self._listar(sis=0)

    def para_ler_estrutura(self):
        """`(sistema, conexão)` para descobrir tabelas e colunas: o sistema
        como está na tela e a conexão escolhida para ler a estrutura."""
        self._guardar_sistema()
        self._guardar_conexao()
        s = self._sis_atual
        ident = self.s_con.currentData()
        c = next((x for x in self.cfg.conexoes if x.ident == ident), None)
        if s is None or c is None:
            informar(
                self, TITULO, "Cadastre uma conexão deste sistema (aba "
                "Conexões) para ler a estrutura do banco.")
            return None
        return s, c

    def carregar_tabelas(self):
        par = self.para_ler_estrutura()
        if par is None:
            return
        tabelas = no_banco(self, TITULO, "Lendo as tabelas…",
                           lambda: caso.tabelas(*par))
        if tabelas is None:
            return
        for ed in self.editores.values():
            ed.definir_tabelas(tabelas)
        self.lbl.setText("%d tabela(s) no banco." % len(tabelas))

    # ---------------------------------------------------------- geral
    def _listar(self, con=0, sis=0):
        self._guardar_conexao()
        self._guardar_sistema()
        self._con_atual = self._sis_atual = None
        self.lst_con.blockSignals(True)
        self.lst_con.clear()
        self.lst_con.addItems([c.nome for c in self.cfg.conexoes])
        self.lst_con.blockSignals(False)
        self.lst_sis.blockSignals(True)
        self.lst_sis.clear()
        self.lst_sis.addItems([s.nome for s in self._sistemas_ordenados()])
        self.lst_sis.blockSignals(False)
        self.lst_con.setCurrentRow(con if self.cfg.conexoes else -1)
        self._mostrar_conexao(self.lst_con.currentRow())
        self.lst_sis.setCurrentRow(sis if self.cfg.sistemas else -1)
        self._mostrar_sistema(self.lst_sis.currentRow())

    def _serial(self):
        return json.dumps({
            "s": {k: v.para_dict() for k, v in self.cfg.sistemas.items()},
            "c": [vars(c) for c in self.cfg.conexoes]}, sort_keys=True,
            default=str)

    def salvar(self):
        self._guardar_conexao()
        self._guardar_sistema()
        try:
            caso.salvar(self.cfg)
        except Exception as exc:                            # noqa: BLE001
            QMessageBox.critical(self, TITULO, "Não foi possível salvar:\n%s"
                                 % exc)
            return False
        self._inicial = self._serial()
        self.lbl.setText("Salvo.")
        return True

    def closeEvent(self, ev):
        self._guardar_conexao()
        self._guardar_sistema()
        if self._serial() != self._inicial:
            r = QMessageBox.question(
                self, TITULO, "Salvar as alterações?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                ev.ignore()
                return
            if r == QMessageBox.StandardButton.Yes and not self.salvar():
                ev.ignore()
                return
        super().closeEvent(ev)

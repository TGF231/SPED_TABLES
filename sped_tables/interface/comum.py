# -*- coding: utf-8 -*-
"""Utilidades compartilhadas pelas telas: preferências, formatação de número e data para exibição."""

import os
import re
import threading

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (QApplication, QFileDialog, QMessageBox,
                             QProgressDialog)

from sped_tables.aplicacao import erp as caso_erp
from sped_tables.aplicacao import leitura_xml
from sped_tables.dominio.sped_model import EntradaInvalida
from sped_tables.infra import dados
from sped_tables.infra.paralelo import Cancelado
from sped_tables.infra import exportacao
from sped_tables.version import APP_NAME


def definir_papel(widget, papel):
    """Troca o papel visual (`role`, ver tema.py) e repinta o widget.

    Mudar uma propriedade usada em seletor de QSS **não** repinta sozinho: o
    Qt já resolveu o estilo daquele widget. Sem o unpolish/polish o rótulo
    continua com a cor antiga e parece que a folha de estilo está errada."""
    widget.setProperty("role", papel)
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
    widget.update()
    return widget


def marcar_erro(campo, mensagem=None, rotulo_msg=None):
    """Marca (ou, com `mensagem=None`, desmarca) um campo com erro: borda e
    fundo de erro **e** a mensagem com "⚠" no `rotulo_msg` — cor nunca é o
    único sinal. A mensagem vira também a descrição acessível do campo,
    para o leitor de tela anunciar o erro."""
    erro = bool(mensagem)
    campo.setProperty("erro", "true" if erro else "false")
    estilo = campo.style()
    estilo.unpolish(campo)
    estilo.polish(campo)
    campo.setAccessibleDescription(mensagem or "")
    if rotulo_msg is not None:
        rotulo_msg.setText("⚠ %s" % mensagem if erro else "")
        rotulo_msg.setVisible(erro)
        definir_papel(rotulo_msg, "erro")
    return erro


def calcular(parent, titulo, funcao, *args, **kwargs):
    """Roda um cálculo que grava no arquivo. Devolve `(True, resultado)`,
    ou `(False, None)` quando ele recusou por campo numérico inválido — e
    aí a pessoa já viu quais campos e onde corrigir.

    O cálculo recusa **antes** de alterar qualquer coisa
    (`SpedDocument._exigir_numeros`): lixo num campo de valor seria lido
    como zero e gravado num total com cara de certo.
    """
    try:
        return True, funcao(*args, **kwargs)
    except EntradaInvalida as exc:
        QMessageBox.warning(parent, titulo, str(exc))
        return False, None


def em_segundo_plano(pai, titulo, texto, trabalho):
    """Roda `trabalho(progresso, cancelar)` fora da thread da interface, com
    barra de andamento e botão Cancelar, e devolve o que ele devolver.

    `progresso(feitos, total)` atualiza a barra; `cancelar()` diz se a
    pessoa pediu para parar (o trabalho levanta `Cancelado`). O que o
    trabalho levantar sobe aqui, na thread da interface — e nenhum widget é
    tocado fora dela: a barra lê o andamento de um dicionário."""
    barra = QProgressDialog(texto, "Cancelar", 0, 0, pai)
    barra.setWindowTitle(titulo)
    barra.setWindowModality(Qt.WindowModality.ApplicationModal)
    barra.setMinimumDuration(0)
    barra.setAutoReset(False)
    barra.show()
    QApplication.processEvents()
    andamento = {"feitos": 0, "total": 0}
    saida = {}
    parar = threading.Event()

    def progresso(feitos, total):
        andamento["feitos"], andamento["total"] = feitos, total

    def rodar():
        try:
            saida["valor"] = trabalho(progresso, parar.is_set)
        except BaseException as exc:                        # noqa: BLE001
            saida["erro"] = exc

    th = threading.Thread(target=rodar, daemon=True)
    th.start()
    mostrado = None
    while th.is_alive():
        if barra.wasCanceled():
            parar.set()
        feitos, total = andamento["feitos"], andamento["total"]
        if total and (feitos, total) != mostrado:
            mostrado = (feitos, total)
            barra.setMaximum(total)
            barra.setValue(feitos)
            barra.setLabelText("%s %s de %s" % (texto, _milhar(feitos),
                                                _milhar(total)))
        QApplication.processEvents()
        th.join(0.05)
    barra.close()
    if "erro" in saida:
        raise saida["erro"]
    return saida.get("valor")


def _milhar(n):
    return "{:,}".format(n).replace(",", ".")


def escolher_origem_xml(pai, titulo, conexoes):
    """"pasta", a conexão do ERP escolhida, ou None (desistiu). Só pergunta
    quando a empresa do arquivo tem conexão de ERP com XMLs."""
    caixa = QMessageBox(QMessageBox.Icon.Question, titulo,
                        "De onde vêm os XMLs?", parent=pai)
    botoes = {caixa.addButton("Banco do ERP: %s" % c.nome,
                              QMessageBox.ButtonRole.AcceptRole): c
              for c in conexoes}
    b_pasta = caixa.addButton("Uma pasta…",
                              QMessageBox.ButtonRole.AcceptRole)
    caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caixa.exec()
    if caixa.clickedButton() is b_pasta:
        return "pasta"
    return botoes.get(caixa.clickedButton())


def ler_pasta_xml(pai, titulo, pergunta, reler=False):
    """O lote (`xml_fiscal.Lote`) dos XMLs do período, ou None se a pessoa
    desistiu ou a leitura falhou — o erro já foi mostrado.

    **Lido uma vez por arquivo aberto.** A primeira função que precisa dos
    XMLs pergunta de onde vêm — uma pasta (as subpastas entram) ou, quando a
    empresa do arquivo tem conexão de ERP com XMLs, o banco, no período do
    arquivo — e o lote fica na sessão; as seguintes o reaproveitam sem
    perguntar nada. `reler=True` (a ação *XMLs do período…*) troca a origem.
    """
    sessao = getattr(pai, "sessao", None)
    if sessao is not None and sessao.xmls is not None and not reler:
        _status(pai, "XMLs do período: %s (já lidos)." % sessao.origem_xmls)
        return sessao.xmls
    doc = getattr(pai, "doc", None)
    cfg = caso_erp.carregar() if doc is not None else None
    conexoes = (caso_erp.conexoes_da_empresa(cfg, caso_erp.cnpj(doc), "xmls")
                if cfg is not None else [])
    origem = (escolher_origem_xml(pai, titulo, conexoes) if conexoes
              else "pasta")
    if origem is None:
        return None
    if origem == "pasta":
        pasta = QFileDialog.getExistingDirectory(pai, pergunta)
        if not pasta:
            return None
        descricao = "pasta %s" % pasta

        def trabalho(prog, canc):
            return leitura_xml.ler_pasta_fiscal(pasta, prog, canc)
    else:
        dt_ini, dt_fin = caso_erp.periodo(doc)
        descricao = "banco do ERP (%s)" % origem.nome

        def trabalho(prog, canc):
            return caso_erp.xmls(cfg, origem, dt_ini, dt_fin, prog, canc)
    try:
        lote = em_segundo_plano(pai, titulo, "Lendo os XMLs…", trabalho)
    except Cancelado:
        return None
    except Exception as e:                                  # noqa: BLE001
        QMessageBox.critical(pai, titulo, "Erro ao ler os XMLs:\n%s" % e)
        return None
    n = len(lote.nfes) + len(lote.sem_chave) + len(lote.ctes)
    descricao += " — %s documento(s)" % _milhar(n)
    # lote vazio não fica guardado: foi a pasta errada, e a próxima função
    # tem de poder perguntar de novo
    if sessao is not None and n:
        sessao.guardar_xmls(lote, descricao)
    _status(pai, "XMLs do período: %s." % descricao)
    return lote


def _status(pai, texto):
    barra = getattr(pai, "statusBar", None)
    if callable(barra):
        barra().showMessage(texto, 10000)


def nfes_do_lote(lote):
    """As NF-e/NFC-e numeradas do lote, inclusive as sem chave (a entrada
    que o ERP exporta), na ordem."""
    return [n for n in lote.nfes + lote.sem_chave if n.nnf]


def ler_nfes_da_pasta(pai, titulo, pergunta):
    """`(nfes, erros)` dos XMLs do período (`ler_pasta_xml`), ou None."""
    lote = ler_pasta_xml(pai, titulo, pergunta)
    if lote is None:
        return None
    return nfes_do_lote(lote), lote.erros


# janelas soltas que nasceram sem pai (os testes chamam assim): sem esta
# referência o coletor de lixo as fecharia no mesmo instante
_SEM_PAI = []


def abrir_janela(pai, dlg, ao_aceitar=None, chave=None):
    """Mostra `dlg` como janela própria, **sem bloquear as outras**: a
    principal e as demais ferramentas continuam clicáveis enquanto ela está
    aberta, e cada uma tem minimizar e maximizar.

    `ao_aceitar()` roda quando a pessoa confirma (o `accepted` do diálogo) —
    é o lugar do que vinha depois de `if dlg.exec() == Accepted`. Há uma
    janela por `chave` (o nome da classe, por padrão): abrir de novo fecha a
    anterior, que mostraria um resultado velho. A referência fica guardada na
    janela principal; sem ela o diálogo seria coletado (CLAUDE.md, "Ao
    adicionar ações")."""
    dlg.setModal(False)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.setWindowFlags(Qt.WindowType.Window
                       | Qt.WindowType.WindowTitleHint
                       | Qt.WindowType.WindowSystemMenuHint
                       | Qt.WindowType.WindowMinMaxButtonsHint
                       | Qt.WindowType.WindowCloseButtonHint)
    chave = chave or type(dlg).__name__
    if pai is not None:
        abertas = getattr(pai, "_janelas", None)
        if abertas is None:
            abertas = {}
            setattr(pai, "_janelas", abertas)
        anterior = abertas.get(chave)
        if anterior is not None and anterior is not dlg:
            anterior.close()
        abertas[chave] = dlg

        def esquecer(_codigo=0):
            if abertas.get(chave) is dlg:
                del abertas[chave]
        dlg.finished.connect(esquecer)
    else:
        _SEM_PAI.append(dlg)
        dlg.finished.connect(lambda _c=0: _SEM_PAI.remove(dlg)
                             if dlg in _SEM_PAI else None)
    if ao_aceitar is not None:
        dlg.accepted.connect(ao_aceitar)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg


def informar(pai, titulo, texto, proximos=()):
    """Aviso de resultado que **não espera o OK**: a caixa fica aberta ao
    lado do trabalho, e a pessoa segue usando o programa. Pergunta que
    precisa de resposta continua modal — esta é só para o "feito".

    `proximos` são `(rótulo, função)` da etapa seguinte — "Recalcular bloco
    M" depois de trocar alíquotas, por exemplo: um botão no próprio aviso,
    em vez de mandar a pessoa procurar a função no menu."""
    caixa = QMessageBox(QMessageBox.Icon.Information, titulo, texto,
                        QMessageBox.StandardButton.Ok, pai)
    caixa.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    for rotulo, funcao in proximos:
        b = caixa.addButton(rotulo, QMessageBox.ButtonRole.ActionRole)
        b.clicked.connect(lambda _=False, f=funcao: f())
    return abrir_janela(pai, caixa, chave="informar:" + titulo)


def lista_de_mudancas(mudou):
    """`{campo: (antes, depois)}` como linhas "• campo: antes → depois"."""
    return "\n".join("• %s: %s → %s" % (c, _br(a), _br(b))
                     for c, (a, b) in mudou.items())


def ajustes():
    """Preferências da interface (tema, última empresa escolhida).

    Normalmente no registro do Windows. Com a pasta de dados redirecionada
    (`SPED_TABLES_DADOS`, como faz a suíte de testes), vão para um `.ini`
    dentro dela: o teste que alterna o tema não pode trocar a preferência de
    quem usa o programa.
    """
    if os.environ.get("SPED_TABLES_DADOS"):
        return QSettings(os.path.join(dados.pasta_dados(), "preferencias.ini"),
                         QSettings.Format.IniFormat)
    return QSettings(APP_NAME, APP_NAME)


def _br(v):
    """Formata número no padrão brasileiro: 1234.5 -> '1.234,50'."""
    try:
        return ("%0.2f" % float(v)).replace(".", "@").replace(",", ".").replace("@", ",")
    except (TypeError, ValueError):
        return str(v)


# número no padrão BR: inteiro, com pontos de milhar e/ou vírgula decimal.
# (evita tratar códigos como "3.1.1" ou datas como número)
_RE_NUM_BR = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$|^-?\d+(,\d+)?$")


def _num_celula(texto):
    """Converte o texto de uma célula em float se for um número BR; senão None.
    Ignora inteiros muito longos (ex.: chave de acesso de 44 dígitos), que não
    são valores somáveis e perderiam precisão."""
    s = (texto or "").strip()
    if not s or not _RE_NUM_BR.match(s):
        return None
    if len(s.replace("-", "").replace(".", "").replace(",", "")) > 15:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Página inicial: cabeçalho do arquivo e contagem de registros
# ---------------------------------------------------------------------------
def _data_br(s):
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return "%s/%s/%s" % (s[0:2], s[2:4], s[4:8])
    return s or "—"


def exportar_csv(pai, titulo, nome_sugerido, cabecalho, linhas):
    """Pergunta onde, grava (`infra.exportacao`) e avisa. Devolve o caminho
    gravado, ou None se o usuário desistiu ou a gravação falhou.

    `linhas` pode ser um gerador: só é percorrido depois da escolha do
    arquivo.
    """
    caminho, _ = QFileDialog.getSaveFileName(pai, titulo, nome_sugerido,
                                             "CSV (*.csv)")
    if not caminho:
        return None
    try:
        caminho, n = exportacao.gravar_csv(caminho, cabecalho, linhas)
    except OSError as exc:
        QMessageBox.critical(pai, titulo, "Não foi possível gravar:\n%s"
                             % exc)
        return None
    informar(pai, titulo, "%d linha(s) exportada(s) para:\n%s"
             % (n, caminho))
    return caminho


def linhas_da_tabela(tabela):
    """O texto de cada célula de um QTableWidget, linha a linha."""
    for r in range(tabela.rowCount()):
        yield [(tabela.item(r, c).text() if tabela.item(r, c) else "")
               for c in range(tabela.columnCount())]

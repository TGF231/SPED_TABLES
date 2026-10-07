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


def _ler_xmls(pai, titulo, pergunta, ler, do_lote):
    """Lê os XMLs com a barra de andamento: de uma pasta (`ler(pasta,
    progresso, cancelar)`) ou, quando a empresa do arquivo tem conexão de
    ERP com XMLs, do banco — no período do arquivo, convertido por
    `do_lote(lote)`. None se a pessoa desistiu ou a leitura falhou — o erro
    já foi mostrado."""
    doc = getattr(pai, "doc", None)
    cfg = caso_erp.carregar() if doc is not None else None
    conexoes = (caso_erp.conexoes_da_empresa(cfg, caso_erp.cnpj(doc), "xmls")
                if cfg is not None else [])
    origem = escolher_origem_xml(pai, titulo, conexoes) if conexoes \
        else "pasta"
    if origem is None:
        return None
    if origem == "pasta":
        pasta = QFileDialog.getExistingDirectory(pai, pergunta)
        if not pasta:
            return None

        def trabalho(prog, canc):
            return ler(pasta, prog, canc)
    else:
        dt_ini, dt_fin = caso_erp.periodo(doc)

        def trabalho(prog, canc):
            return do_lote(caso_erp.xmls(cfg, origem, dt_ini, dt_fin, prog,
                                         canc))
    try:
        return em_segundo_plano(pai, titulo, "Lendo os XMLs…", trabalho)
    except Cancelado:
        return None
    except Exception as e:                                  # noqa: BLE001
        QMessageBox.critical(pai, titulo, "Erro ao ler os XMLs:\n%s" % e)
        return None


def ler_pasta_xml(pai, titulo, pergunta):
    """Lê os XMLs de uma pasta (as subpastas entram) ou do banco do ERP, em
    paralelo e com andamento. Devolve o lote (`xml_fiscal.Lote`), ou None."""
    return _ler_xmls(pai, titulo, pergunta, leitura_xml.ler_pasta_fiscal,
                     lambda lote: lote)


def ler_nfes_da_pasta(pai, titulo, pergunta):
    """Lê as NF-e/NFC-e de uma pasta (sem subpastas) ou do banco do ERP, em
    paralelo e com andamento. Devolve `(nfes, erros)`, ou None."""
    return _ler_xmls(pai, titulo, pergunta, leitura_xml.ler_pasta,
                     lambda lote: ([n for n in lote.nfes + lote.sem_chave
                                    if n.nnf], lote.erros))


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
    QMessageBox.information(pai, titulo, "%d linha(s) exportada(s) para:\n%s"
                            % (n, caminho))
    return caminho


def linhas_da_tabela(tabela):
    """O texto de cada célula de um QTableWidget, linha a linha."""
    for r in range(tabela.rowCount()):
        yield [(tabela.item(r, c).text() if tabela.item(r, c) else "")
               for c in range(tabela.columnCount())]

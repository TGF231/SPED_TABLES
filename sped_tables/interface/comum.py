# -*- coding: utf-8 -*-
"""Utilidades compartilhadas pelas telas: preferências, formatação de número e data para exibição."""

import os
import re

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from sped_tables.dominio.sped_model import EntradaInvalida
from sped_tables.infra import dados
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

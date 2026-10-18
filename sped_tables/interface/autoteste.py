# -*- coding: utf-8 -*-
"""Autoteste do pacote: o roteiro 2.2 do TESTES.md que dá para automatizar.

    "SPED Tables.exe" --autoteste relatorio.json [arquivo.txt]

Confere, **de dentro do executável**, o que só o empacotamento quebra e a
suíte (que roda do código-fonte) não vê: a tradução do Qt que o PyInstaller
não inclui sozinho, o ícone e as correlações que viajam como recurso, o
`openpyxl` opcional, a instalação da pasta de dados, o registro de falhas e,
com um arquivo, abrir → salvar → reabrir com a cópia no acervo.

**Nunca toca nos dados de quem usa o programa:** sem `SPED_TABLES_DADOS` no
ambiente, a pasta de dados vira uma temporária antes de qualquer outra coisa
— senão o arquivo aberto aqui iria parar no acervo de verdade. Pela mesma
razão o relatório não leva nome, CNPJ nem caminho do arquivo: só contagens.

Devolve 0 quando tudo passou e 1 quando algo falhou; o detalhe vai no JSON
(o executável não tem console).
"""

import json
import os
import shutil
import sys
import tempfile
import traceback

from sped_tables.version import __version__

# texto que a tradução pt-BR do Qt dá ao botão "Yes" das caixas de mensagem
_BOTOES = {"&Yes": "&Sim", "Cancel": "Cancelar", "Save": "Salvar"}
# NFC-e mínima para a leitura paralela: chave e número
_XML_MINIMO = ('<nfeProc><NFe><infNFe Id="NFe3126089999999900019965001'
               '%09d1%08d0"><ide><mod>65</mod><serie>1</serie><nNF>1</nNF>'
               '</ide></infNFe></NFe></nfeProc>')


class _Relatorio:
    def __init__(self):
        self.itens = []

    def conferir(self, nome, funcao):
        """Roda `funcao()`, que devolve `(ok, detalhe)`; exceção é falha."""
        try:
            ok, detalhe = funcao()
        except Exception as exc:                            # noqa: BLE001
            ok, detalhe = False, "%s: %s\n%s" % (
                type(exc).__name__, exc, traceback.format_exc(limit=4))
        self.itens.append({"nome": nome, "ok": bool(ok),
                           "detalhe": detalhe})
        return ok

    @property
    def passou(self):
        return all(i["ok"] for i in self.itens)


def _isolar_dados():
    """Pasta de dados temporária, a menos que o ambiente já tenha uma."""
    if os.environ.get("SPED_TABLES_DADOS"):
        return None
    pasta = tempfile.mkdtemp(prefix="sped_tables_autoteste_")
    os.environ["SPED_TABLES_DADOS"] = pasta
    return pasta


def executar(app, argumentos):
    """`argumentos` = `[relatorio.json, arquivo.txt?]`. Devolve o código de
    saída."""
    if not argumentos:
        return 2
    destino = os.path.abspath(argumentos[0])
    arquivo = argumentos[1] if len(argumentos) > 1 else None
    temporaria = _isolar_dados()
    # só agora: tudo que lê a pasta de dados precisa já ver a isolada
    from sped_tables.infra import dados, falhas
    rel = _Relatorio()
    try:
        _conferir(app, rel, arquivo, dados, falhas)
    finally:
        saida = {"versao": __version__, "empacotado": dados.empacotado(),
                 "passou": rel.passou, "itens": rel.itens}
        with open(destino, "w", encoding="utf-8") as fh:
            json.dump(saida, fh, ensure_ascii=False, indent=2)
        if temporaria:
            shutil.rmtree(temporaria, ignore_errors=True)
    return 0 if rel.passou else 1


def _conferir(app, rel, arquivo, dados, falhas):
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtGui import QIcon

    from sped_tables.aplicacao import montagem
    from sped_tables.interface.app import instalar_traducao

    avisos = []
    falhas.instalar(avisar=lambda tipo, valor, detalhe, copia:
                    avisos.append((tipo.__name__, copia)))

    def traducao():
        carregados = instalar_traducao(app)
        errados = {en: QCoreApplication.translate("QPlatformTheme", en)
                   for en in _BOTOES}
        errados = {en: pt for en, pt in errados.items() if pt != _BOTOES[en]}
        return (not errados, "carregados: %s; botões fora do português: %s"
                % (carregados, errados or "nenhum"))
    rel.conferir("tradução pt-BR do Qt", traducao)

    def icone():
        cam = dados.recurso("icon.ico")
        return (os.path.isfile(cam) and not QIcon(cam).isNull(), cam)
    rel.conferir("ícone", icone)

    def correlacoes():
        cam = dados.recurso("correlacoes_cfop.json")
        with open(cam, encoding="utf-8") as fh:
            n = len(json.load(fh))
        return n > 0, "%d correlações" % n
    rel.conferir("correlações CFOP padrão", correlacoes)

    def planilhas():
        import openpyxl
        return True, "openpyxl %s" % openpyxl.__version__
    rel.conferir("leitura de planilhas (openpyxl)", planilhas)

    def instalacao():
        copiados = dados.instalar()
        pasta = dados.pasta_dados()
        # empacotado, a instalação copia as correlações; do código-fonte a
        # pasta de dados é a do projeto e não há o que copiar
        esperado = ["correlacoes_cfop.json"] if dados.empacotado() else []
        faltam = [n for n in esperado
                  if not os.path.isfile(os.path.join(pasta, n))]
        # atualizar não pode sobrescrever: a segunda vez não copia nada
        return (not faltam and dados.instalar() == [],
                "copiados na primeira: %s" % copiados)
    rel.conferir("instalação da pasta de dados", instalacao)

    def tabelas_pva():
        from sped_tables.dominio import referencias
        montagem.configurar()
        info = {}
        for layout in ("ICMS", "CONTRIB"):
            estrutura, meta = referencias.atual().estrutura(layout)
            info[layout] = ("%d registros no descritor" % len(estrutura)
                            if estrutura else "PVA não encontrado")
        # sem PVA a função fica sem as tabelas oficiais, mas não é defeito
        # do pacote: registra e segue
        return True, info
    rel.conferir("tabelas do PVA", tabelas_pva)

    def guias_praticos():
        # viajam em base/guias/ (SPED Tables.spec); sem eles a ajuda F1 some
        from sped_tables.dominio import referencias
        info = {}
        for layout in ("ICMS", "CONTRIB"):
            g = referencias.atual().guia(layout)
            info[layout] = ("%s %s, %d registros" % (
                g.get("guia"), g.get("versao"), len(g.get("registros", {})))
                if g else "ausente")
        return all(v != "ausente" for v in info.values()), info
    rel.conferir("guias práticos", guias_praticos)

    def leitura_paralela():
        # o processo filho é o próprio executável: sem o `freeze_support` do
        # lançador cada um abriria uma janela, e sem processos a leitura cai
        # para threads (avisa no log) — as duas coisas aparecem aqui
        import logging
        from sped_tables.aplicacao import leitura_xml
        from sped_tables.dominio import xml_fiscal
        from sped_tables.infra import paralelo
        qtd = paralelo.MINIMO_PROCESSOS + 44
        pasta = tempfile.mkdtemp(prefix="sped_tables_xml_")
        avisos_log = []

        class _Captura(logging.Handler):
            def emit(self, registro):
                avisos_log.append(registro.getMessage())
        captura = _Captura(logging.WARNING)
        paralelo.log.addHandler(captura)
        try:
            for i in range(qtd):
                with open(os.path.join(pasta, "%04d.xml" % i), "w",
                          encoding="utf-8") as fh:
                    fh.write(_XML_MINIMO % (i + 1, i + 1))
            lote = leitura_xml.ler_pasta_fiscal(pasta)
            serial = xml_fiscal.ler_pasta_fiscal(pasta)
        finally:
            paralelo.log.removeHandler(captura)
            shutil.rmtree(pasta, ignore_errors=True)
        iguais = ([n.chave for n in lote.nfes]
                  == [n.chave for n in serial.nfes])
        ok = len(lote.nfes) == qtd and iguais and not avisos_log
        return ok, "%d XMLs, %d trabalhadores%s" % (
            len(lote.nfes), paralelo.trabalhadores(),
            "; " + avisos_log[0] if avisos_log else "")
    rel.conferir("leitura paralela de XMLs", leitura_paralela)

    def drivers_erp():
        # importados só dentro dos adaptadores: o PyInstaller os acha pela
        # análise, e é aqui que se confere que vieram no pacote
        info, faltam = {}, []
        for nome in ("firebirdsql", "pyodbc", "pymysql"):
            try:
                mod = __import__(nome)
                info[nome] = getattr(mod, "__version__", "ok")
            except ImportError:
                info[nome] = "ausente"
                faltam.append(nome)
        return not faltam, info
    rel.conferir("drivers dos bancos de ERP", drivers_erp)

    def registro_de_falhas():
        try:
            raise RuntimeError("falha provocada pelo autoteste")
        except RuntimeError:
            falhas.tratar(*sys.exc_info())
        with open(falhas.caminho_log(), encoding="utf-8") as fh:
            texto = fh.read()
        ok = "falha provocada pelo autoteste" in texto and \
            avisos[-1:] == [("RuntimeError", None)]
        return ok, "registro e aviso"
    rel.conferir("registro de falhas e aviso", registro_de_falhas)

    def janela():
        from sped_tables.interface.janela import JanelaPrincipal
        j = JanelaPrincipal()
        ok = not j.windowIcon().isNull()
        j.close()
        j.deleteLater()
        return ok, "ícone da janela %s" % ("ok" if ok else "vazio")
    rel.conferir("janela principal", janela)

    if arquivo:
        rel.conferir("abrir, salvar e reabrir",
                     lambda: _ida_e_volta(arquivo, dados))


def _ida_e_volta(arquivo, dados):
    from sped_tables.aplicacao.sessao import Sessao
    from sped_tables.dominio.sped_model import SpedDocument
    from sped_tables.infra import arquivos

    pasta = os.path.join(dados.pasta_dados(), "autoteste")
    os.makedirs(pasta, exist_ok=True)
    copia = os.path.join(pasta, "entrada.txt")
    shutil.copyfile(arquivo, copia)            # o original nunca é aberto
    s = Sessao()
    r = s.abrir(copia)
    n = len(s.doc.registros)
    salvo = os.path.join(pasta, "salvo.txt")
    s.salvar(salvo)
    de_novo = SpedDocument.carregar(salvo)
    with open(copia, "rb") as a, open(salvo, "rb") as b:
        identico = a.read() == b.read()
    acervo = len(arquivos.historico())
    ok = len(de_novo.registros) == n and acervo >= 1 and r.entrada
    return ok, ("%d registros, gravado %s, %d cópia(s) no acervo"
                % (n, "idêntico" if identico else "diferente do original",
                   acervo))

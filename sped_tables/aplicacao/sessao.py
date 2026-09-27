# -*- coding: utf-8 -*-
"""Caso de uso: o arquivo aberto — abrir, salvar, fechar.

Cada operação junta três coisas que a janela fazia sozinha: o documento
(`SpedDocument`), o caminho no disco e a cópia no acervo (`infra.arquivos`).
A regra que atravessa as três fica aqui, testável sem tela:

* **arquivar nunca impede abrir nem salvar.** Pasta sem permissão, disco
  cheio: a falha do acervo vira um aviso, não um erro;
* **salvar só limpa o "alterado" se gravou.** Falha na gravação propaga
  (a mensagem do `salvar` diz a linha e o caractere) e o estado não muda;
* **fechar esquece tudo** — documento, caminho e alteração.
"""

import os

from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import arquivos
from sped_tables.infra import falhas


class Resultado:
    """O que a interface precisa mostrar depois de abrir ou salvar."""

    def __init__(self, caminho, entrada=None, aviso=""):
        self.caminho = caminho
        self.entrada = entrada        # item do índice do acervo, ou None
        self.aviso = aviso            # texto para a barra de status

    @property
    def periodo(self):
        return (self.entrada or {}).get("periodo", "")


class Sessao:
    """Estado do arquivo aberto na janela."""

    def __init__(self):
        self.doc = None
        self.caminho = ""
        self.alterado = False

    @property
    def aberta(self):
        return self.doc is not None

    # ------------------------------------------------------------ operações
    def abrir(self, caminho):
        """Lê o SPED e guarda a cópia do período. Erro de leitura propaga
        (o arquivo não abriu); erro do acervo vira aviso."""
        doc = SpedDocument.carregar(caminho)
        self.doc, self.caminho, self.alterado = doc, caminho, False
        entrada, aviso = self._arquivar("abertura", caminho)
        if entrada is None and not aviso:
            aviso = "Arquivo sem CNPJ no 0000: não foi arquivado no histórico."
        return Resultado(caminho, entrada, aviso)

    def salvar(self, caminho=None, descartar_invalidas=False):
        """Grava (atomicamente — ver `SpedDocument.salvar`) e atualiza a
        cópia do período. Sem caminho, grava onde o arquivo está.

        Arquivo com linhas fora do formato levanta `LinhasInvalidas`: quem
        chama pergunta ao usuário e, com o sim, repete com
        `descartar_invalidas=True`.
        """
        if self.doc is None:
            raise ValueError("Nenhum arquivo aberto.")
        destino = caminho or self.doc.caminho or self.caminho
        if not destino:
            raise ValueError("O arquivo ainda não tem onde ser gravado.")
        self.doc.salvar(destino, descartar_invalidas=descartar_invalidas)
        if descartar_invalidas:
            falhas.log.warning("gravado sem %d linha(s) fora do formato: %s",
                               len(self.doc.linhas_invalidas), destino)
            self.doc.linhas_invalidas = []
        self.caminho = destino
        self.alterado = False
        entrada, aviso = self._arquivar("salvamento", destino)
        return Resultado(destino, entrada, aviso)

    def fechar(self):
        self.doc = None
        self.caminho = ""
        self.alterado = False

    def marcar_alterado(self):
        self.alterado = True

    # ----------------------------------------------------------- consultas
    def identificacao(self):
        """`{nome, periodo, leiaute, arquivo}` para títulos e barras."""
        if self.doc is None:
            return {}
        try:
            _cnpj, nome, layout, periodo = arquivos.identificar(self.doc)
        except Exception:                                   # noqa: BLE001
            nome = periodo = ""
            layout = self.doc.layout
        return {
            "nome": nome,
            "periodo": arquivos.formatar_periodo(periodo) if periodo else "",
            "leiaute": ("EFD Contribuições" if layout == "CONTRIB"
                        else "EFD ICMS/IPI"),
            "arquivo": os.path.basename(self.caminho or ""),
        }

    def copia_de_emergencia(self):
        """Cópia em `recuperacao/` quando há alteração pendente (chamada pelo
        fallback de exceções). Devolve o caminho, ou None."""
        if self.doc is None or not self.alterado:
            return None
        return falhas.gravar_emergencia(self.doc, self.caminho)

    # --------------------------------------------------------------- acervo
    def _arquivar(self, motivo, caminho):
        """`(entrada, aviso)` — arquivar é conveniência e nunca levanta."""
        try:
            return arquivos.arquivar(self.doc, caminho, motivo=motivo), ""
        except Exception as exc:                            # noqa: BLE001
            falhas.log.warning("acervo: %s", exc)
            return None, "Não foi possível arquivar a cópia interna: %s" % exc

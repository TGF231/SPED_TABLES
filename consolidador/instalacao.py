# -*- coding: utf-8 -*-
"""A instalação dos PVAs na máquina de quem compila: onde ficam o
descritor e as tabelas, lidos na forma que a base guarda.

`InstalacaoPVA` tem a interface de `base_referencia.Base` (`manifesto`,
`versoes`, `estrutura`, `tabelas`, `guia`, `ncm_vigente`): é dela que o
consolidador extrai a base, e é com ela que o teste de equivalência confere
que a base compilada responde igual ao PVA de onde saiu.
"""

import datetime
import json
import os

from consolidador import descritor
from sped_tables.infra import base_referencia, config, tabelas_oficiais

# onde fica cada coisa dentro da pasta de cada PVA
SUBPASTAS = {
    "ICMS": {
        "tabelas": os.path.join("recursos", "TabelasExternas"),
        "descritor": os.path.join("lib", "br.gov.serpro.sped.fiscalpva",
                                  "fiscalpva-dominio.jar"),
        "versoes": "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE",
    },
    "CONTRIB": {
        "tabelas": os.path.join("recursos", "tabelas"),
        "descritor": os.path.join("lib", "br.gov.serpro.sped.piscofinspva",
                                  "piscofinspva-infra.jar"),
        "versoes": "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_VERSOES_LEIAUTE",
    },
}


class ConsolidadorErro(Exception):
    """Falta o que o consolidador precisa; a mensagem diz o quê."""


def jar_descritor(raiz, layout):
    return os.path.join(config.pasta_pva(layout, raiz),
                        SUBPASTAS[layout]["descritor"])


def pasta_tabelas(raiz, layout):
    return os.path.join(config.pasta_pva(layout, raiz),
                        SUBPASTAS[layout]["tabelas"])


def tabela_de_versoes(tabs, layout):
    """`{COD_VER: (dt_ini, dt_fim)}` da tabela de versões do leiaute."""
    alvo = tabs.get(SUBPASTAS[layout]["versoes"])
    out = {}
    for linha in (alvo[0] if alvo else "").splitlines()[1:]:
        p = linha.split("|")
        if len(p) >= 4 and p[0].strip():
            out[p[0].strip()] = (p[2].strip(), p[3].strip())
    return out


def _data_do_pva(texto):
    """A data de vigência no formato do PVA (DDMMAAAA, 8 dígitos)."""
    return len(texto) == 8 and texto.isdigit()


class InstalacaoPVA:
    """Os dois PVAs de uma raiz. `data` fixa a janela de retenção (os
    últimos `anos` anos, mais as versões futuras que já têm descritor);
    `fontes` é a pasta `base/`, de onde vêm guias e NCM, que não são do
    PVA."""

    def __init__(self, raiz=None, data=None, anos=5, fontes=None):
        self.raiz = raiz or config.raiz_pva()
        self.data = data or datetime.date.today()
        self.anos = anos
        self.fontes = fontes or base_referencia.pasta_fontes()
        self.avisos = []
        self._tabs = None
        self._versoes = {}
        self._estruturas = {}
        faltam = [c for layout in base_referencia.LEIAUTES
                  for c in (jar_descritor(self.raiz, layout),
                            pasta_tabelas(self.raiz, layout))
                  if not os.path.exists(c)]
        if faltam:
            raise ConsolidadorErro(
                "PVA incompleto em %s; faltam:\n  %s"
                % (self.raiz, "\n  ".join(faltam)))

    def manifesto(self):
        return {"versao": "instalação", "data": self.data.isoformat()}

    def tabelas(self):
        if self._tabs is None:
            tabs = {}
            for layout in base_referencia.LEIAUTES:
                tabs.update(tabelas_oficiais.tabelas_da_pasta(
                    pasta_tabelas(self.raiz, layout)))
            self._tabs = tabs
        return self._tabs

    def versoes(self, layout):
        """`{COD_VER: (dt_ini, dt_fim, descritor)}` das versões que entram
        na base."""
        if layout not in self._versoes:
            self._versoes[layout] = self._selecionar(layout)
        return self._versoes[layout]

    def _selecionar(self, layout):
        limite = "%04d0101" % (self.data.year - self.anos)
        hoje = self.data.strftime("%Y%m%d")
        tabela = tabela_de_versoes(self.tabelas(), layout)
        caminhos = descritor.por_versao(jar_descritor(self.raiz, layout),
                                        layout, tabela)
        out = {}
        for cod, (ini, fim) in sorted(tabela.items()):
            # `chave_data` devolve "" para data que não tem 8 dígitos (e uma
            # data trocada para AAAA-MM-DD), e a versão viraria aberta dos
            # dois lados sem erro nenhum: valeria para qualquer período.
            # Melhor recusar.
            if not (_data_do_pva(ini) and (not fim or _data_do_pva(fim))):
                raise ConsolidadorErro(
                    "A vigência da versão %s do leiaute %s não está em "
                    "DDMMAAAA (%r a %r): o PVA mudou o formato da tabela de "
                    "versões." % (cod, layout, ini, fim))
            if fim and tabelas_oficiais.chave_data(fim) < limite:
                continue
            if cod in caminhos:
                out[cod] = (ini, fim, caminhos[cod])
            elif tabelas_oficiais.chave_data(ini) > hoje:
                self.avisos.append(
                    "%s %s (a partir de %s) ainda não tem descritor nesta "
                    "instalação: fica fora da base" % (layout, cod, ini))
            else:
                raise ConsolidadorErro(
                    "A versão %s do leiaute %s está na janela de retenção e "
                    "não tem descritor correspondente nesta instalação do "
                    "PVA." % (cod, layout))
        return out

    def estrutura(self, layout, versao):
        chave = (layout, versao)
        if chave not in self._estruturas:
            caminho = self.versoes(layout)[versao][2]
            self._estruturas[chave] = descritor.ler(
                jar_descritor(self.raiz, layout), caminho)
        return self._estruturas[chave]

    def guia(self, layout):
        caminho = os.path.join(self.fontes, "guias", layout + ".json")
        if not os.path.exists(caminho):
            return {}
        with open(caminho, encoding="utf-8") as fh:
            return json.load(fh)

    def ncm_vigente(self):
        caminho = os.path.join(self.fontes, "ncm", "vigente.txt")
        if not os.path.exists(caminho):
            return None
        with open(caminho, encoding="utf-8") as fh:
            return {l.strip() for l in fh if l.strip()} or None

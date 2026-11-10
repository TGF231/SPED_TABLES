# -*- coding: utf-8 -*-
"""Gera `COBERTURA.md`: quanto das validações dos guias práticos e dos
validadores do PVA o programa reproduz, registro a registro.

    python ferramentas/cobertura_guias.py

Usa a base de referência em uso (os validadores vêm do descritor da versão
mais recente do leiaute que ela guarda); não precisa dos PVAs instalados.
O arquivo gerado não tem dado de cliente — só leiaute, guia e regras — e
vai para o repositório: é a resposta honesta a "o programa valida tudo?".
"""

import datetime
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from sped_tables.aplicacao import montagem  # noqa: E402
from sped_tables.dominio import diagnostico, referencias, regras_guia  # noqa

NOMES = {"ICMS": "EFD ICMS/IPI", "CONTRIB": "EFD Contribuições"}


def _linhas_do_leiaute(layout):
    guia = referencias.atual().guia(layout)
    est, info = referencias.atual().estrutura(layout)
    reproduzidos = diagnostico.validadores_reproduzidos()
    linhas = []
    tot = {"val_guia": 0, "pva": set(), "repro": set()}
    for reg in sorted(set(guia.get("registros", {})) | set(est)):
        g = guia.get("registros", {}).get(reg, {})
        n_guia = sum(1 for c in g.get("campos", {}).values()
                     if c.get("validacao"))
        if g.get("validacao_registro"):
            n_guia += 1
        pva = set((est.get(reg) or {}).get("validadores", ()))
        repro = pva & reproduzidos
        tot["val_guia"] += n_guia
        tot["pva"] |= pva
        tot["repro"] |= repro
        if n_guia or pva:
            linhas.append((reg, n_guia, len(pva), len(repro)))
    return guia, info, linhas, tot


def main():
    montagem.configurar()
    out = ["# Cobertura das regras de validação",
           "",
           "Gerado por `ferramentas/cobertura_guias.py` em %s, a partir dos "
           "guias práticos e do descritor da base de referência."
           % datetime.date.today().strftime("%d/%m/%Y"),
           "",
           "* **Validações do guia**: parágrafos *Validação* dos campos mais a "
           "*Validação do Registro*, por registro.",
           "* **Validadores do PVA**: regras compostas (`REGRA_…`) que o "
           "descritor declara para o registro; as declarativas (tipo, "
           "tamanho, obrigatoriedade, domínio, referência) o programa "
           "reproduz todas, pelo próprio descritor, e não entram na conta.",
           "* **Reproduzidos**: validadores que o programa confere com as "
           "mesmas condições e tolerâncias do PVA (`dominio/regras_guia.py` "
           "e as verificações próprias do diagnóstico). O que falta continua "
           "sendo listado no diagnóstico como \"só o PVA verifica\".",
           ""]
    for layout in ("ICMS", "CONTRIB"):
        guia, info, linhas, tot = _linhas_do_leiaute(layout)
        pct = (100.0 * len(tot["repro"]) / len(tot["pva"])) if tot["pva"] \
            else 0
        out += ["## %s" % NOMES[layout], "",
                "Guia prático %s (%s); descritor `%s`." % (
                    guia.get("versao", "?"), guia.get("atualizacao", "?"),
                    info.get("descritor")),
                "",
                "| | Quantidade |", "|---|---:|",
                "| Validações escritas no guia | %d |" % tot["val_guia"],
                "| Validadores compostos do PVA | %d |" % len(tot["pva"]),
                "| … reproduzidos pelo programa | %d (%.0f%%) |" % (
                    len(tot["repro"]), pct),
                "",
                "### Regras do guia implementadas", "",
                "| Regra | Gravidade | Validadores do PVA |",
                "|---|---|---|"]
        for r in regras_guia.regras(layout):
            out.append("| %s | %s | %s |" % (
                r.rotulo, r.gravidade,
                ", ".join("`%s`" % v for v in r.pva) or "—"))
        out += ["", "### Por registro", "",
                "| Registro | Validações no guia | Validadores do PVA | "
                "Reproduzidos |", "|---|---:|---:|---:|"]
        for reg, n_guia, n_pva, n_repro in linhas:
            out.append("| %s | %d | %d | %d |" % (reg, n_guia, n_pva,
                                                  n_repro))
        out.append("")
    destino = os.path.join(RAIZ, "COBERTURA.md")
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))
    print("gravado:", destino)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Roteiro 2.1 do TESTES.md, automático: cada correção que grava, validada
no PVA de verdade.

Para cada arquivo real e cada fluxo de correção aplicável, grava uma cópia
corrigida, importa e valida no PVA e compara o que a validação acusou com o
arquivo **original** passado pelo mesmo caminho. Uma correção passa quando
não aparece mensagem nova nem aumenta a contagem de nenhuma.

Roda numa **cópia de ensaio** da instalação dos PVAs, com portas de banco
próprias: importar uma cópia do mesmo CNPJ e período no PVA de uso
substituiria a escrituração que o usuário tem lá. A automação só dirige
janela cujo executável esteja dentro da pasta de ensaio
(`pva._da_instalacao`).

    py ferramentas/validar_no_pva.py preparar --ensaio D:\\pva_ensaio
    py ferramentas/validar_no_pva.py gerar    --reais D:\\reais --saida D:\\saida
    py ferramentas/validar_no_pva.py validar  --ensaio D:\\pva_ensaio --saida D:\\saida
    py ferramentas/validar_no_pva.py relatorio --saida D:\\saida

Nada disso vai para o repositório: a saída tem de ficar fora dele (o script
recusa), porque são arquivos de cliente.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from sped_tables.aplicacao import montagem  # noqa: E402
from sped_tables.dominio import empresas as emp_mod  # noqa: E402
from sped_tables.dominio import rotinas, validacao  # noqa: E402
from sped_tables.dominio.sped_model import SpedDocument, _to_num  # noqa: E402
from sped_tables.infra import banco_pva, config, pva  # noqa: E402
from sped_tables.infra import tabelas_rfb  # noqa: E402

PORTAS = {"Fiscal": ("spedfiscal.properties", 3347),
          "EFD-Contribuicoes": ("spedpiscofins.properties", 3348)}
RESULTADOS = "resultados.json"


def _fora_do_repositorio(pasta):
    alvo = os.path.normcase(os.path.abspath(pasta))
    if alvo.startswith(os.path.normcase(RAIZ) + os.sep) or \
            alvo == os.path.normcase(RAIZ):
        sys.exit("A saída não pode ficar dentro do repositório: são arquivos "
                 "de cliente. Use uma pasta fora dele.")
    return pasta


# ------------------------------------------------------------ preparar
def preparar(ensaio):
    """Copia as instalações dos PVAs para `ensaio` e troca a porta do banco
    embutido, para as duas poderem rodar ao mesmo tempo sem se tocar."""
    origem = config.raiz_pva()
    destino = os.path.join(ensaio, "Programas SPED")
    for pasta, (props, porta) in PORTAS.items():
        de, para = os.path.join(origem, pasta), os.path.join(destino, pasta)
        if not os.path.isdir(de):
            continue
        if not os.path.isdir(para):
            print("copiando %s…" % pasta)
            subprocess.run(["robocopy", de, para, "/E", "/NFL", "/NDL",
                            "/NJH", "/NJS", "/NP", "/R:1", "/W:1"],
                           check=False)
        cam = os.path.join(para, "configuracoes", props)
        with open(cam, encoding="latin-1") as fh:
            linhas = fh.read().splitlines()
        linhas = ["portaBanco=%d" % porta if l.startswith("portaBanco=")
                  else l for l in linhas]
        with open(cam, "w", encoding="latin-1", newline="\r\n") as fh:
            fh.write("\n".join(linhas) + "\n")
        print("%s: porta %d" % (pasta, porta))
    return destino


# ------------------------------------------------------------ fluxos
def _empresa_do_arquivo(doc):
    mapa = {}
    emp, _ja = emp_mod.obter_ou_criar(mapa, doc)
    return emp


def _rotinas(doc):
    emp = _empresa_do_arquivo(doc)
    n = 0
    for rot in rotinas.aplicaveis(doc, emp):
        if rot.corrigir is None or rot.requer:
            continue
        ocs, _erro = rotinas.executar(doc, emp, rot)
        if ocs:
            n += rot.corrigir(doc, emp, ocs)
    doc.recalcular_bloco_m()
    return n


def _cst_ncm(doc):
    emp = _empresa_do_arquivo(doc)
    clf, _c = tabelas_rfb.classificador()
    ocs = rotinas.verificar_cst_ncm(doc, emp, classificador=clf,
                                    data_ref=doc.data_final())
    n = rotinas.corrigir_cst_ncm(doc, emp, ocs) if ocs else 0
    doc.recalcular_bloco_m()
    return n


def _aliquotas(doc):
    """Reaplica a alíquota predominante nas saídas (recalcula os valores)
    e refaz o bloco M — o caminho de gravação da troca de alíquotas."""
    pis = doc.aliquota_predominante("ALIQ_PIS")
    cof = doc.aliquota_predominante("ALIQ_COFINS")
    if not pis or not cof:
        return 0
    r = doc.trocar_aliquotas_pis_cofins(aliq_pis=pis, aliq_cofins=cof,
                                        de_pis=pis, de_cofins=cof)
    doc.recalcular_bloco_m()
    return r.get("itens", 0)


def _datas(doc):
    """Emissão um dia antes em todo documento que continue no período."""
    ini = doc.data_final()                      # DDMMAAAA
    i_ini = doc._ix("0000", "DT_INI")
    for r in doc.registros:
        if r.reg == "0000":
            ini = (r.valor(i_ini) or "").strip()
    d0 = datetime.datetime.strptime(ini, "%d%m%Y").date()
    d1 = datetime.datetime.strptime(doc.data_final(), "%d%m%Y").date()
    r = doc.alterar_datas_c100(campo_filtro="DT_DOC",
                               data_ini=d0 + datetime.timedelta(days=1),
                               data_fim=d1, campos_alterar=("DT_DOC",),
                               modo="dias", valor=-1)
    return r.get("c100", 0) if isinstance(r, dict) else r


def _inventario(doc):
    """Reimporta o próprio H010 como se viesse de planilha."""
    h = {c: doc._ix("H010", c) for c in ("COD_ITEM", "UNID", "QTD",
                                          "VL_UNIT", "VL_ITEM", "IND_PROP")}
    linhas = [{"cod_item": r.valor(h["COD_ITEM"]), "unid": r.valor(h["UNID"]),
               "qtd": _to_num(r.valor(h["QTD"])),
               "vl_unit": _to_num(r.valor(h["VL_UNIT"])),
               "vl_item": _to_num(r.valor(h["VL_ITEM"])),
               "ind_prop": r.valor(h["IND_PROP"])}
              for r in doc.registros if r.reg == "H010"]
    if not linhas:
        return 0
    h005 = next(r for r in doc.registros if r.reg == "H005")
    dt = h005.valor(doc._ix("H005", "DT_INV"))
    mot = h005.valor(doc._ix("H005", "MOT_INV")) or "01"
    r = doc.importar_inventario_h010(linhas, dt, mot_inv=mot)
    return r.get("itens", len(linhas))


def _cod_cta(doc):
    n = 0
    for tipo in doc.registros_sem_cod_cta():
        r = doc.preencher_cod_cta(tipo, "1.1.03.01",
                                  nome_cta="ESTOQUE DE MERCADORIAS")
        n += r.get("registros", 0)
    return n


def _itens_sem_ref(doc):
    orfaos = doc.itens_0200_nao_utilizados()
    return doc.remover_itens_0200([o[0] for o in orfaos]) if orfaos else 0


AMBOS = ("ICMS", "CONTRIB")
FLUXOS = [
    ("original", lambda d: 0, AMBOS),
    ("nulos", lambda d: d.limpar_campos_nulos()["campos"], AMBOS),
    ("normalizar", lambda d: validacao.normalizar(d)["campos"], AMBOS),
    ("cod_gen", lambda d: d.preencher_cod_gen()["itens"], AMBOS),
    ("itens_sem_ref", _itens_sem_ref, AMBOS),
    ("datas", _datas, AMBOS),
    ("cod_cta", _cod_cta, ("ICMS",)),
    ("c190_massa", lambda d: d.consolidar_c190_em_massa().get("documentos",
                                                             0), ("ICMS",)),
    ("icms_itens", lambda d: d.recalcular_icms_itens(
        refazer_c190=True)["alterados"], ("ICMS",)),
    ("inventario", _inventario, ("ICMS",)),
    ("bloco_m", lambda d: bool(d.recalcular_bloco_m()), ("CONTRIB",)),
    ("aliquotas", _aliquotas, ("CONTRIB",)),
    ("rotinas", _rotinas, ("CONTRIB",)),
    ("cst_ncm", _cst_ncm, ("CONTRIB",)),
]


def _reais(pasta):
    for raiz, _d, nomes in os.walk(pasta):
        for n in sorted(nomes):
            cam = os.path.join(raiz, n)
            if n.lower().endswith(".txt"):
                with open(cam, "rb") as fh:
                    if fh.read(6) == b"|0000|":
                        yield cam


def gerar(reais, saida, somente=None):
    os.makedirs(saida, exist_ok=True)
    feitos = []
    for k, cam in enumerate(_reais(reais), 1):
        base = SpedDocument.carregar(cam)
        rotulo = "arq%02d_%s" % (k, base.layout)
        for nome, fn, layouts in FLUXOS:
            if base.layout not in layouts or (somente and nome not in somente):
                continue
            doc = SpedDocument.carregar(cam)
            try:
                n = fn(doc)
            except Exception as exc:                    # noqa: BLE001
                print("  %s %s: ERRO %s" % (rotulo, nome, exc))
                continue
            if nome != "original" and not n:
                print("  %-16s %-14s nada a corrigir" % (rotulo, nome))
                continue
            destino = os.path.join(saida, "%s_%s.txt" % (rotulo, nome))
            doc.salvar(destino)
            feitos.append({"arquivo": destino, "origem": cam,
                           "layout": base.layout, "fluxo": nome,
                           "rotulo": rotulo, "alteracoes": n})
            print("  %-16s %-14s %s" % (rotulo, nome, n))
    with open(os.path.join(saida, "gerados.json"), "w",
              encoding="utf-8") as fh:
        json.dump(feitos, fh, ensure_ascii=False, indent=2)
    return feitos


# ------------------------------------------------------------ validar
def _validar_um(item, raiz, limite=1800, manual=False):
    layout = item["layout"]
    antes = set(banco_pva.bancos(layout, raiz))
    t0 = time.time()
    if manual:
        # sem automação: a pessoa importa e valida; aqui só se lê o banco
        pva._copiar(item["arquivo"])
        input("\n  No PVA (%s): Importar, colar o caminho (já está na área "
              "de transferência) e validar.\n  %s\n  Terminada a "
              "validação, Enter aqui… " % (layout, item["arquivo"]))
        item["estado"] = "manual"
        item["mensagem"] = ""
    else:
        r = pva.abrir(item["arquivo"], layout, raiz=raiz,
                      progresso=lambda t: None)
        item["estado"] = r.get("estado")
        item["mensagem"] = r.get("mensagem", "")
        if r.get("estado") == "validando":
            hwnd, pid = pva.janela(layout, raiz)
            pva._janela_com_titulo(pid, pva.TITULO_VALIDANDO, limite,
                                   ausente=True)
    time.sleep(3)                           # o PVA grava e fecha a tabela
    novos = sorted(set(banco_pva.bancos(layout, raiz)) - antes)
    item["bd"] = novos[-1] if novos else None
    cont = (banco_pva.inconsistencias(layout, item["bd"], raiz)
            if item["bd"] else None)
    item["inconsistencias"] = (
        None if cont is None
        else {"%s|%s" % k: v for k, v in sorted(cont.items())})
    item["segundos"] = round(time.time() - t0)
    return item


def validar(ensaio, saida, somente=None, rotulos=None, manual=False):
    raiz = os.path.join(ensaio, "Programas SPED")
    with open(os.path.join(saida, "gerados.json"), encoding="utf-8") as fh:
        itens = json.load(fh)
    cam_res = os.path.join(saida, RESULTADOS)
    feitos = {}
    if os.path.exists(cam_res):
        with open(cam_res, encoding="utf-8") as fh:
            feitos = {i["arquivo"]: i for i in json.load(fh)}
    # o original de cada arquivo primeiro: é a régua dos demais
    itens.sort(key=lambda i: (i["rotulo"], i["fluxo"] != "original"))
    for item in itens:
        if somente and item["fluxo"] not in somente:
            continue
        if rotulos and item["rotulo"] not in rotulos:
            continue
        if item["arquivo"] in feitos and \
                feitos[item["arquivo"]].get("inconsistencias") is not None:
            continue
        print("%s %s…" % (item["rotulo"], item["fluxo"]), flush=True)
        feitos[item["arquivo"]] = _validar_um(dict(item), raiz,
                                              manual=manual)
        r = feitos[item["arquivo"]]
        total = sum((r["inconsistencias"] or {}).values()) \
            if r["inconsistencias"] is not None else "?"
        print("   %s em %ss — %s inconsistência(s)"
              % (r["estado"], r["segundos"], total), flush=True)
        with open(cam_res, "w", encoding="utf-8") as fh:
            json.dump(list(feitos.values()), fh, ensure_ascii=False,
                      indent=2)


# ------------------------------------------------------------ relatório
def comparar(original, corrigido):
    """`(novas, piores, melhores)` por mensagem|registro."""
    novas, piores, melhores = [], [], []
    for chave in sorted(set(original) | set(corrigido)):
        a, b = original.get(chave, 0), corrigido.get(chave, 0)
        if a == 0 and b > 0:
            novas.append((chave, b))
        elif b > a:
            piores.append((chave, a, b))
        elif b < a:
            melhores.append((chave, a, b))
    return novas, piores, melhores


def relatorio(saida):
    with open(os.path.join(saida, RESULTADOS), encoding="utf-8") as fh:
        itens = json.load(fh)
    base = {i["rotulo"]: i for i in itens if i["fluxo"] == "original"}
    linhas = ["| Arquivo | Fluxo | Alterações | PVA antes | PVA depois | "
              "Resultado |", "|---|---|---|---|---|---|"]
    falhas = 0
    for i in sorted(itens, key=lambda x: (x["rotulo"], x["fluxo"])):
        orig = base.get(i["rotulo"], {}).get("inconsistencias")
        dep = i.get("inconsistencias")
        if dep is None or orig is None:
            res, antes, depois = "não validado (%s)" % i.get("estado"), \
                "?", "?"
        else:
            antes, depois = sum(orig.values()), sum(dep.values())
            novas, piores, melhores = comparar(orig, dep)
            if i["fluxo"] == "original":
                res = "régua"
            elif novas or piores:
                falhas += 1
                res = "**PIORA**: " + "; ".join(
                    ["%s (novo, %d)" % (k, n) for k, n in novas]
                    + ["%s %d→%d" % (k, a, b) for k, a, b in piores])
            else:
                res = "ok" + (" (corrige: %s)" % "; ".join(
                    "%s %d→%d" % (k, a, b) for k, a, b in melhores)
                    if melhores else "")
        linhas.append("| %s | %s | %s | %s | %s | %s |" % (
            i["rotulo"], i["fluxo"], i.get("alteracoes", ""), antes, depois,
            res))
    texto = "\n".join(linhas)
    with open(os.path.join(saida, "relatorio.md"), "w",
              encoding="utf-8") as fh:
        fh.write(texto + "\n")
    print(texto)
    return falhas


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("acao", choices=("preparar", "gerar", "validar",
                                     "relatorio"))
    ap.add_argument("--ensaio")
    ap.add_argument("--reais")
    ap.add_argument("--saida")
    ap.add_argument("--fluxos", help="só estes (separados por vírgula)")
    ap.add_argument("--rotulos", help="só estes arquivos (arq01_ICMS,…)")
    ap.add_argument("--manual", action="store_true",
                    help="a pessoa importa e valida; o roteiro só lê o banco")
    a = ap.parse_args()
    somente = set(a.fluxos.split(",")) if a.fluxos else None
    rotulos = set(a.rotulos.split(",")) if a.rotulos else None
    montagem.configurar()
    if a.acao == "preparar":
        preparar(a.ensaio)
    elif a.acao == "gerar":
        gerar(a.reais, _fora_do_repositorio(a.saida), somente)
    elif a.acao == "validar":
        validar(a.ensaio, _fora_do_repositorio(a.saida), somente, rotulos,
                a.manual)
    else:
        sys.exit(1 if relatorio(a.saida) else 0)


if __name__ == "__main__":
    main()

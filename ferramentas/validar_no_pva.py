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
import ctypes
import ctypes.wintypes
import datetime
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from consolidador import banco_pva  # noqa: E402
from sped_tables.aplicacao import montagem  # noqa: E402
from sped_tables.dominio import empresas as emp_mod  # noqa: E402
from sped_tables.dominio import diagnostico, rotinas, validacao  # noqa: E402
from sped_tables.dominio import referencias  # noqa: E402
from sped_tables.dominio.sped_model import (  # noqa: E402
    TIPOS_ITEM_0200, SpedDocument, _fmt_aliq, _fmt_val, _to_num)
from sped_tables.infra import config, pva  # noqa: E402

if sys.platform == "win32":
    # declarado uma vez, no import (armadilha do ctypes: ver CLAUDE.md)
    _GetWindowRect = ctypes.WinDLL("user32").GetWindowRect
    _GetWindowRect.argtypes = [ctypes.wintypes.HWND,
                               ctypes.POINTER(ctypes.wintypes.RECT)]
    _GetWindowRect.restype = ctypes.wintypes.BOOL

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
    clf = referencias.atual().classificador_ncm()
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
    # todas as colunas que a planilha de verdade traz — sem a conta
    # contábil, a reimportação apagava o COD_CTA que a cadeia preencheu e o
    # PVA acusava 997 H010 sem conta
    h = {c: doc._ix("H010", c) for c in (
        "COD_ITEM", "UNID", "QTD", "VL_UNIT", "VL_ITEM", "IND_PROP",
        "COD_PART", "TXT_COMPL", "COD_CTA", "VL_ITEM_IR")}
    linhas = [{"cod_item": r.valor(h["COD_ITEM"]), "unid": r.valor(h["UNID"]),
               "qtd": _to_num(r.valor(h["QTD"])),
               "vl_unit": _to_num(r.valor(h["VL_UNIT"])),
               "vl_item": _to_num(r.valor(h["VL_ITEM"])),
               "ind_prop": r.valor(h["IND_PROP"]),
               "cod_part": r.valor(h["COD_PART"]),
               "txt_compl": r.valor(h["TXT_COMPL"]),
               "cod_cta": r.valor(h["COD_CTA"]),
               "vl_item_ir": r.valor(h["VL_ITEM_IR"])}
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


def _cadeia(doc):
    """Todas as correções, na ordem em que alguém as aplicaria. Testa a
    interação entre elas e, num arquivo com mais de 1.000 erros, é a única
    comparação que o teto do PVA não mascara: o relatório para de listar
    erros em 1.000, e uma correção isolada só troca uns erros por outros que
    estavam escondidos atrás deles."""
    passos = [lambda d: validacao.normalizar(d)["campos"],
              lambda d: d.preencher_cod_gen()["itens"],
              _itens_sem_ref]
    if doc.layout == "ICMS":
        passos += [_cod_cta,
                   lambda d: d.consolidar_c190_em_massa().get("documentos",
                                                             0),
                   lambda d: d.recalcular_icms_itens(
                       refazer_c190=True)["alterados"],
                   # isolado, o inventário só foi validado num arquivo
                   # acima do teto de erros: na cadeia, fica abaixo dele
                   _inventario]
    else:
        passos += [_rotinas, _cst_ncm]
    n = 0
    for passo in passos:
        r = passo(doc)
        n += r.get("registros", 0) if isinstance(r, dict) else int(r or 0)
    return n


AMBOS = ("ICMS", "CONTRIB")
FLUXOS = [
    ("original", lambda d: 0, AMBOS),
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
    ("totais_c100", lambda d: d.recalcular_totais_todos_c100(), AMBOS),
    ("cadeia", _cadeia, AMBOS),
]


def _preparar_importacao(doc):
    """Régua do roteiro, **não** correção do programa: deixa importável um
    arquivo que o PVA recusa já na importação, para que as correções possam
    ser julgadas pela validação e não pelo teto de 1.000 erros de estrutura.

    Normaliza (o que esvazia o NULL) e decide o que o programa, de propósito, não
    decide sozinho:

    - `00` (mercadoria para revenda) no TIPO_ITEM do 0200 fora da tabela —
      num arquivo real o ERP gravou `N` em 10.312 itens;
    - CST_ICMS curto completado com zeros à esquerda (`0` → `000`) no C170
      e no C190 — noutro, 5 registros assim bastaram para a recusa.

    No programa as duas decisões são do usuário (planilha com prévia; CST
    nunca é sugerido); aqui são só o que falta para o PVA aceitar o arquivo.
    """
    n = validacao.normalizar(doc)["campos"]
    if doc.layout != "ICMS":
        return n
    i = doc._ix("0200", "TIPO_ITEM")
    cst = {t: doc._ix(t, "CST_ICMS") for t in ("C170", "C190")}
    for r in doc.registros:
        if r.reg == "0200" and i is not None and \
                r.valor(i) not in TIPOS_ITEM_0200:
            r.set_valor(i, "00")
            n += 1
        elif cst.get(r.reg) is not None:
            v = (r.valor(cst[r.reg]) or "").strip()
            if v.isdigit() and len(v) < 3:
                r.set_valor(cst[r.reg], v.zfill(3))
                n += 1
    return n


def _injetar_credito_indevido(doc):
    """Régua do roteiro, **não** correção: o erro que *CST por NCM* existe
    para consertar, posto sobre o arquivo real.

    A correção só age em entrada que **toma** crédito de produto que não o
    admite (monofásico, alíquota zero), e nos arquivos reais nenhuma entrada
    fazia isso — estavam todas em CST 99. Aqui essas entradas passam a tomar
    crédito (CST 50, base = valor líquido do item, 1,65 / 7,6) e o bloco M
    é refeito com ele. Julgar a correção é comparar esta régua com ela
    corrigida. Devolve quantos itens ganharam o crédito indevido.
    """
    emp = _empresa_do_arquivo(doc)
    clf = referencias.atual().classificador_ncm()
    ocs = [o for o in rotinas.verificar_cst_ncm(
        doc, emp, classificador=clf, data_ref=doc.data_final())
        if o.escopo == "entrada"]
    por_uid = {r.uid: r for r in doc.registros}
    ix = {c: doc._ix("C170", c) for c in (
        "VL_ITEM", "VL_DESC", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS",
        "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS")}
    n = 0
    for oc in ocs:
        r = por_uid.get(oc.uid)
        if r is None or r.reg != "C170":
            continue
        base = round(_to_num(r.valor(ix["VL_ITEM"]))
                     - _to_num(r.valor(ix["VL_DESC"])), 2)
        for trib, aliq in (("PIS", 1.65), ("COFINS", 7.6)):
            r.set_valor(ix["CST_" + trib], "50")
            r.set_valor(ix["VL_BC_" + trib], _fmt_val(base))
            r.set_valor(ix["ALIQ_" + trib], _fmt_aliq(aliq))
            r.set_valor(ix["VL_" + trib], _fmt_val(round(base * aliq / 100,
                                                         2)))
        n += 1
    if n:
        doc.recalcular_bloco_m()
    return n


def _impede_importacao(doc):
    achados, _info = diagnostico.verificar(doc)
    return diagnostico.impedem_importacao(achados)


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
        series = [(rotulo, None, None)]
        # arquivo que o PVA recusa na importação ganha uma segunda série,
        # sobre a régua importável: na primeira, toda correção esbarra no
        # mesmo teto de erros de estrutura e nada se conclui
        if _impede_importacao(base):
            series.append((rotulo + "_prep", _preparar_importacao, None))
        # a correção de CST por NCM não tinha caso nos arquivos reais: esta
        # série põe o erro que ela conserta e julga só ela
        if (base.layout == "CONTRIB"
                and _injetar_credito_indevido(SpedDocument.carregar(cam))):
            series.append((rotulo + "_cstncm", _injetar_credito_indevido,
                           ("original", "cst_ncm")))
        for rot, prep, so_estes in series:
            for nome, fn, layouts in FLUXOS:
                if base.layout not in layouts or (somente and
                                                  nome not in somente):
                    continue
                if so_estes and nome not in so_estes:
                    continue
                doc = SpedDocument.carregar(cam)
                try:
                    if prep:
                        prep(doc)
                    n = fn(doc)
                except Exception as exc:                # noqa: BLE001
                    print("  %s %s: ERRO %s" % (rot, nome, exc))
                    continue
                if nome != "original" and not n:
                    print("  %-16s %-14s nada a corrigir" % (rot, nome))
                    continue
                destino = os.path.join(saida, "%s_%s.txt" % (rot, nome))
                doc.salvar(destino)
                feitos.append({"arquivo": destino, "origem": cam,
                               "layout": base.layout, "fluxo": nome,
                               "rotulo": rot, "alteracoes": n})
                print("  %-16s %-14s %s" % (rot, nome, n))
    # `--fluxos` gera só uma parte: o resto do manifesto fica como estava
    cam = os.path.join(saida, "gerados.json")
    novos = {i["arquivo"] for i in feitos}
    if os.path.exists(cam):
        with open(cam, encoding="utf-8") as fh:
            feitos = [i for i in json.load(fh)
                      if i["arquivo"] not in novos] + feitos
    with open(cam, "w", encoding="utf-8") as fh:
        json.dump(feitos, fh, ensure_ascii=False, indent=2)
    return feitos


# ------------------------------------------------------------ validar
# avisos que o PVA abre depois de validar ou de recusar, todos só com Ok:
# "O arquivo foi validado com sucesso" (Mensagem), "A escrituração está
# pronta para ser gerada" (Aviso), "O arquivo contém erros e avisos" (Erro)
TITULOS_CONCLUSAO = ("mensagem", "aviso", "erro")
# a janela com o relatório da importação recusada não tem botão de Ok ao
# alcance do Enter: é fechada por mensagem de janela
TITULOS_FECHAR = ("resultado da importação",)
# O PVA também tem uma tela de **falha interna** chamada "Erro" ("Erro
# durante a validacao no banco"), com caixa de texto e os botões "Não
# Enviar" e "Enviar Relatório de Erros" — para a Receita. Enter ali pode
# mandar o relatório. Ela é bem maior que um JOptionPane de Ok (670×474
# contra ~430×120), e é pelo tamanho que o roteiro a reconhece: diálogo
# maior que isto nunca recebe tecla, e a rodada para.
ALTURA_MAXIMA_OK = 250


class FalhaDoPva(RuntimeError):
    """O PVA abriu uma tela que não é de Ok. A resposta é de quem usa."""


def _altura(hwnd):
    r = ctypes.wintypes.RECT()
    if not _GetWindowRect(hwnd, ctypes.byref(r)):
        return 0
    return r.bottom - r.top


def _dispensar_conclusao(layout, raiz, limite=30, sossego=3.0):
    """Fecha os avisos de conclusão da validação — ou da recusa.

    No programa eles ficam para a pessoa ver; no roteiro, travam o próximo
    Ctrl+I. Só age em janela com um desses títulos, do processo da
    instalação de ensaio, e **só aperta Enter em diálogo pequeno** (um Ok).
    Janela "Erro" maior é a falha interna do PVA: levanta `FalhaDoPva` sem
    tocar nela. Dá por encerrado quando nenhum aparece por `sossego`
    segundos (eles vêm um depois do outro).

    Devolve `(sossegou, vistos)`: `vistos` são os títulos que apareceram.
    """
    vistos = set()
    hwnd, pid = pva.janela(layout, raiz)
    if not pid:
        return False, vistos
    fim = time.time() + limite
    livre_desde = time.time()
    while time.time() < fim:
        janelas = [(h, t.strip().lower()) for h, t, p in pva._janelas()
                   if p == pid]
        vistos.update(t for _h, t in janelas
                      if t in TITULOS_FECHAR + TITULOS_CONCLUSAO)
        for h, t in janelas:
            if t in TITULOS_CONCLUSAO and _altura(h) > ALTURA_MAXIMA_OK:
                raise FalhaDoPva(
                    "O %s abriu uma tela de falha interna (\"%s\", %d px de "
                    "altura), com a opção de enviar relatório à Receita. O "
                    "roteiro parou sem tocar nela: responda no PVA (\"Não "
                    "Enviar\") e rode de novo — ele retoma de onde parou."
                    % (pva.INSTALACOES[layout]["nome"], t, _altura(h)))
        for h, t in janelas:
            if t in TITULOS_FECHAR:
                pva._user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
        msgs = [h for h, t in janelas if t in TITULOS_CONCLUSAO]
        if not msgs and any(t in TITULOS_FECHAR for _h, t in janelas):
            livre_desde = time.time()
            time.sleep(1)
            continue
        if not msgs:
            if time.time() - livre_desde >= sossego:
                return True, vistos
            time.sleep(0.5)
            continue
        livre_desde = time.time()
        if (pva._focar(msgs[0], pid, limite=5)
                and pva._pid_do_primeiro_plano()[0] == msgs[0]):
            pva._tecla(pva.VK_RETURN)
        time.sleep(1)
    return False, vistos


# "Erro" sozinho não é recusa: é também o que o PVA mostra depois de uma
# validação que achou erros ("O arquivo contém erros e avisos"). A recusa
# da importação é a única que abre o relatório.
RECUSA = {"resultado da importação"}
# Só estes desfechos dizem que o banco tem o resultado de uma validação (ou
# da recusa). "importado" é importação **sem** validação: o banco existe e a
# tabela de inconsistências está vazia — ler isso como "0 erros" foi um
# falso positivo da primeira rodada da 0.56.0.
VALIDADO = ("validando", "manual", "erro_pva")


def _validar_um(item, raiz, limite=1800, manual=False):
    layout = item["layout"]
    if not manual:
        _dispensar_conclusao(layout, raiz, sossego=1.0)   # sobra de antes
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
    item["segundos"] = round(time.time() - t0)
    # lê **antes** de fechar as telas: na recusa, o PVA apaga o banco quando
    # o relatório da importação é fechado
    cont = (banco_pva.inconsistencias(layout, item["bd"], raiz)
            if item["bd"] else None)
    if not manual:
        _ok, vistos = _dispensar_conclusao(layout, raiz)
        item["recusado"] = (bool(vistos & RECUSA)
                            or item["estado"] == "erro_pva")
    if item["estado"] not in VALIDADO and not item.get("recusado"):
        cont = None                 # importado sem validar: não é "0 erros"
    item["inconsistencias"] = (
        None if cont is None
        else {"%s|%s" % k: v for k, v in sorted(cont.items())})
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
        try:
            feitos[item["arquivo"]] = _validar_um(dict(item), raiz,
                                                  manual=manual)
        except FalhaDoPva as exc:
            # o que já foi validado está gravado; a rodada retoma daqui
            sys.exit("\n%s" % exc)
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


ERROS_DE_ESTRUTURA = ("MSG_ERRO_TIPO_CAMPO", "MSG_ERRO_TAMANHO_CAMPO")
# o PVA para de listar erros em 1.000 (as advertências vêm à parte): acima
# disso, uma correção só troca erros por outros que estavam escondidos
TETO_PVA = 1000


def _recusado(item):
    """Importação recusada: o PVA mostrou "Erro"/"Resultado da Importação"
    (marca gravada pelo `validar`) ou — em resultado de antes da marca — só
    há erro de estrutura, que é o que a importação acusa."""
    if item.get("recusado") or item.get("estado") == "erro_pva":
        return True
    inc = item.get("inconsistencias") or {}
    return (item.get("recusado") is None and item.get("estado") == "confirmar"
            and bool(inc) and all(k.startswith(ERROS_DE_ESTRUTURA)
                                  for k in inc))


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
        rec_orig = _recusado(base.get(i["rotulo"], {}))
        if dep is None or orig is None:
            res, antes, depois = "não validado (%s)" % i.get("estado"), \
                "?", "?"
        elif _recusado(i):
            antes, depois = sum(orig.values()), sum(dep.values())
            if i["fluxo"] == "original":
                res = "régua recusada na importação"
            elif rec_orig:
                res = "recusado na importação, como o original"
            else:
                falhas += 1
                res = "**PIORA**: recusado na importação"
        elif rec_orig:
            antes, depois = sum(orig.values()), sum(dep.values())
            res = "importável (o original é recusado)"
        else:
            antes, depois = sum(orig.values()), sum(dep.values())
            novas, piores, melhores = comparar(orig, dep)
            no_teto = antes >= TETO_PVA and depois >= TETO_PVA
            if i["fluxo"] == "original":
                res = "régua" + (" (no teto de erros)" if antes >= TETO_PVA
                                 else "")
            elif (novas or piores) and no_teto:
                res = "inconclusivo: os dois no teto de erros (%s)" % \
                    "; ".join(["%s novo" % k for k, _n in novas]
                              + ["%s %d→%d" % (k, a, b)
                                 for k, a, b in piores])
            elif (novas or piores) and antes >= TETO_PVA:
                # a régua no teto não listou tudo: o que "aparece" pode
                # estar lá desde o original — conferir no arquivo
                res = ("abaixo do teto (%d→%d); a conferir no original, "
                       "que o teto escondia: %s" % (antes, depois, "; ".join(
                           ["%s (%d)" % (k, n) for k, n in novas]
                           + ["%s %d→%d" % (k, a, b)
                              for k, a, b in piores])))
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

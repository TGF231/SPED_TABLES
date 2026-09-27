# -*- coding: utf-8 -*-
"""Arquivos SPED sintéticos para os testes.

Nenhum dado de cliente entra no repositório: os arquivos daqui são montados
na hora, com CNPJ e nomes inventados, e só têm o que cada teste precisa.

O `Montador` escreve cada registro **pelo nome dos campos** do leiaute —
`m.reg("C170", CFOP="1102", VL_ITEM="10,00")` — e completa a linha com a
largura do leiaute. Assim um teste não depende da posição de coluna, e o
arquivo gerado tem a forma de um arquivo de verdade: blocos abertos e
fechados, X990 e bloco 9 com as contagens certas, CRLF no fim de linha.
"""

import os
import tempfile

from sped_tables.dominio.sped_layouts import CAMPOS_CONTRIB, CAMPOS_ICMS

# CNPJ válido de exemplo (dígitos verificadores corretos), não é de ninguém
CNPJ_TESTE = "11222333000181"


class Montador:
    """Acumula registros e devolve o texto de um SPED completo."""

    def __init__(self, layout="ICMS"):
        self.layout = layout
        self.tabela = CAMPOS_CONTRIB if layout == "CONTRIB" else CAMPOS_ICMS
        self.linhas = []

    def reg(self, tipo, **valores):
        nomes = self.tabela[tipo]
        desconhecidos = set(valores) - set(nomes)
        if desconhecidos:
            raise KeyError("%s não tem %s" % (tipo, sorted(desconhecidos)))
        campos = [valores.get(n, "") for n in nomes]
        campos[0] = tipo
        self.linhas.append(campos)
        return self

    def texto(self):
        """O arquivo inteiro: abre/fecha os blocos que faltarem e monta o 9."""
        corpo = []
        blocos = []
        for campos in self.linhas:
            b = campos[0][0]
            if b not in blocos:
                blocos.append(b)
        for b in blocos:
            do_bloco = [c for c in self.linhas if c[0][0] == b]
            tipos = [c[0] for c in do_bloco]
            if b != "0" and "%s001" % b not in tipos:
                do_bloco.insert(0, ["%s001" % b, "0"])
            if b == "0" and "0001" not in tipos:
                do_bloco.insert(1, ["0001", "0"])
            if "%s990" % b not in tipos:
                do_bloco.append(["%s990" % b, str(len(do_bloco) + 1)])
            corpo.extend(do_bloco)

        contagem = {}
        for c in corpo:
            contagem[c[0]] = contagem.get(c[0], 0) + 1
        for t in ("9001", "9990", "9999"):
            contagem[t] = 1
        contagem["9900"] = len(contagem) + 1
        bloco9 = [["9001", "0"]]
        bloco9 += [["9900", t, str(contagem[t])] for t in sorted(contagem)]
        bloco9.append(["9990", str(len(bloco9) + 2)])
        total = len(corpo) + len(bloco9) + 1
        bloco9.append(["9999", str(total)])

        return "".join("|%s|\r\n" % "|".join(c) for c in corpo + bloco9)

    def gravar(self, pasta, nome="sped.txt", encoding="latin-1"):
        caminho = os.path.join(pasta, nome)
        with open(caminho, "wb") as fh:
            fh.write(self.texto().encode(encoding))
        return caminho


# ---------------------------------------------------------------- cenários
def icms_basico(itens=None, frete="0", uf="MG"):
    """EFD ICMS/IPI com uma NF-e de entrada, itens e C190.

    `itens` é uma lista de dicts com os campos do C170 que variam; o padrão
    são três itens de R$ 10,00 com CST 000, CFOP 1102 e 18%.
    """
    m = Montador("ICMS")
    m.reg("0000", COD_VER="019", COD_FIN="0", DT_INI="01082026",
          DT_FIN="31082026", NOME="EMPRESA TESTE LTDA", CNPJ=CNPJ_TESTE,
          UF=uf, IE="0012345670012", COD_MUN="3106200", IND_PERFIL="A",
          IND_ATIV="1")
    m.reg("0150", COD_PART="F1", NOME="FORNECEDOR TESTE", COD_PAIS="1058",
          CNPJ="11444777000161", COD_MUN="3106200")
    m.reg("0190", UNID="UN", DESCR="UNIDADE")
    itens = itens or [{"COD_ITEM": "P%d" % i} for i in (1, 2, 3)]
    for it in itens:
        m.reg("0200", COD_ITEM=it["COD_ITEM"],
              DESCR_ITEM="PRODUTO %s" % it["COD_ITEM"], UNID_INV="UN",
              TIPO_ITEM="00", COD_NCM="21069090")
    m.reg("C100", IND_OPER="0", IND_EMIT="1", COD_PART="F1", COD_MOD="55",
          COD_SIT="00", SER="1", NUM_DOC="123",
          CHV_NFE="31260811444777000161550010000001231000001230",
          DT_DOC="05082026", DT_E_S="06082026", VL_DOC="30,00",
          IND_PGTO="0", VL_MERC="30,00", IND_FRT="9", VL_FRT=frete,
          VL_SEG="0", VL_OUT_DA="0", VL_BC_ICMS="30,00", VL_ICMS="5,40")
    for n, it in enumerate(itens, 1):
        base = {"NUM_ITEM": str(n), "QTD": "1", "UNID": "UN",
                "VL_ITEM": "10,00", "VL_DESC": "0", "IND_MOV": "0",
                "CST_ICMS": "000", "CFOP": "1102", "VL_BC_ICMS": "10,00",
                "ALIQ_ICMS": "18", "VL_ICMS": "1,80"}
        base.update(it)
        m.reg("C170", **base)
    m.reg("C190", CST_ICMS="000", CFOP="1102", ALIQ_ICMS="18",
          VL_OPR="30,00", VL_BC_ICMS="30,00", VL_ICMS="5,40",
          VL_BC_ICMS_ST="0", VL_ICMS_ST="0", VL_RED_BC="0", VL_IPI="0")
    m.reg("E100", DT_INI="01082026", DT_FIN="31082026")
    return m


def contrib_basico(cod_inc_trib="1", bloco_m=True):
    """EFD Contribuições não-cumulativa: uma entrada com crédito e uma saída.

    Entrada: R$ 100,00 CST 50, CFOP 1102 (natureza 01), PIS 1,65 / COFINS 7,6.
    Saída:   R$ 300,00 CST 01, CFOP 5102, mesmas alíquotas.

    Com `bloco_m`, traz M100/M105/M200/M210 (e os de COFINS) com valores
    velhos — o que o recálculo tem de consertar.
    """
    m = Montador("CONTRIB")
    m.reg("0000", COD_VER="006", TIPO_ESCRIT="0", IND_SIT_ESP="",
          DT_INI="01082026", DT_FIN="31082026", NOME="EMPRESA TESTE LTDA",
          CNPJ=CNPJ_TESTE, UF="MG", COD_MUN="3106200", IND_NAT_PJ="00",
          IND_ATIV="2")
    m.reg("0110", COD_INC_TRIB=cod_inc_trib, IND_APRO_CRED="1",
          COD_TIPO_CONT="1")
    m.reg("0140", COD_EST="1", NOME="EMPRESA TESTE LTDA", CNPJ=CNPJ_TESTE,
          UF="MG", COD_MUN="3106200")
    m.reg("0200", COD_ITEM="P1", DESCR_ITEM="PRODUTO P1", UNID_INV="UN",
          TIPO_ITEM="00", COD_NCM="21069090")
    m.reg("C010", CNPJ=CNPJ_TESTE, IND_ESCRI="2")
    for oper, cfop, cst, valor, num in (("0", "1102", "50", "100,00", "1"),
                                        ("1", "5102", "01", "300,00", "2")):
        m.reg("C100", IND_OPER=oper, IND_EMIT="1" if oper == "0" else "0",
              COD_MOD="55", COD_SIT="00", SER="1", NUM_DOC=num,
              DT_DOC="05082026", DT_E_S="05082026", VL_DOC=valor,
              IND_PGTO="0", VL_MERC=valor, IND_FRT="9")
        pis = "%.2f" % (float(valor.replace(",", ".")) * 0.0165)
        cof = "%.2f" % (float(valor.replace(",", ".")) * 0.076)
        m.reg("C170", NUM_ITEM="1", COD_ITEM="P1", QTD="1", UNID="UN",
              VL_ITEM=valor, IND_MOV="0", CST_ICMS="000", CFOP=cfop,
              CST_PIS=cst, VL_BC_PIS=valor, ALIQ_PIS="1,65",
              VL_PIS=pis.replace(".", ","), CST_COFINS=cst,
              VL_BC_COFINS=valor, ALIQ_COFINS="7,6",
              VL_COFINS=cof.replace(".", ","))
    if bloco_m:
        # apuração "como o ERP gravou": valores propositalmente velhos, para
        # o recálculo ter o que corrigir
        for trib, cons, det, cred, cred_det, ali in (
                ("PIS", "M200", "M210", "M100", "M105", "1,65"),
                ("COFINS", "M600", "M610", "M500", "M505", "7,6")):
            m.reg(cred, **{"COD_CRED": "101", "IND_CRED_ORI": "0",
                           "VL_BC_" + trib: "90,00", "ALIQ_" + trib: ali,
                           "VL_CRED": "1,00", "VL_CRED_DISP": "1,00",
                           "IND_DESC_CRED": "0", "VL_CRED_DESC": "1,00",
                           "SLD_CRED": "0"})
            m.reg(cred_det, **{"NAT_BC_CRED": "01", "CST_" + trib: "50",
                               "VL_BC_%s_TOT" % trib: "90,00",
                               "VL_BC_%s_NC" % trib: "90,00",
                               "VL_BC_" + trib: "90,00"})
            m.reg(cons, VL_TOT_CONT_NC_PER="1,00", VL_TOT_CRED_DESC="1,00",
                  VL_TOT_CRED_DESC_ANT="0", VL_TOT_CONT_NC_DEV="0",
                  VL_RET_NC="0", VL_OUT_DED_NC="0", VL_CONT_NC_REC="0",
                  VL_TOT_CONT_CUM_PER="0", VL_RET_CUM="0",
                  VL_OUT_DED_CUM="0", VL_CONT_CUM_REC="0",
                  VL_TOT_CONT_REC="0")
            m.reg(det, **{"COD_CONT": "01", "VL_REC_BRT": "250,00",
                          "VL_BC_CONT": "250,00", "ALIQ_" + trib: ali,
                          "VL_CONT_APUR": "1,00", "VL_CONT_PER": "1,00"})
    return m


class PastaTemporaria:
    """`with PastaTemporaria() as p:` — some sozinha no fim do teste."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="sped_teste_")
        return self._tmp.name

    def __exit__(self, *exc):
        self._tmp.cleanup()
        return False


def ler(caminho):
    """Bytes do arquivo, fechando o descritor (o `open().read()` solto gera
    ResourceWarning e, no Windows, pode segurar o arquivo aberto)."""
    with open(caminho, "rb") as fh:
        return fh.read()


def _parte_xml(tag, cnpj, nome, uf="MG", cmun="3106200", ie="0010000000"):
    ender = {"emit": "enderEmit", "rem": "enderReme", "exped": "enderExped",
             "receb": "enderReceb", "dest": "enderDest",
             "toma4": "enderToma"}.get(tag, "ender")
    return ("<%s><CNPJ>%s</CNPJ><IE>%s</IE><xNome>%s</xNome><%s>"
            "<xLgr>RUA TESTE</xLgr><nro>10</nro><xBairro>CENTRO</xBairro>"
            "<cMun>%s</cMun><xMun>CIDADE</xMun><CEP>30000000</CEP><UF>%s</UF>"
            "</%s></%s>" % (tag, cnpj, ie, nome, ender, cmun, uf, ender, tag))


def cte_xml(chave="31260899888777000166570010000004561000004560",
            nct="456", toma="3", emit=("99888777000166", "TRANSPORTADORA"),
            rem=("11444777000161", "FORNECEDOR TESTE"),
            dest=(CNPJ_TESTE, "EMPRESA TESTE LTDA"), toma4=None,
            icms="<ICMS00><CST>00</CST><vBC>100.00</vBC><pICMS>12.00</pICMS>"
                 "<vICMS>12.00</vICMS></ICMS00>",
            vtprest="100.00", tpcte="0", cstat="100", cfop="6352",
            chaves_nfe=("31260811444777000161550010000001231000001230",)):
    """XML de CT-e 4.00 (modelo 57) com protocolo. `toma` é o código do
    <toma3> (0 remetente, 1 expedidor, 2 recebedor, 3 destinatário); com
    `toma4=(cnpj, nome)` o tomador é um terceiro com dados próprios."""
    if toma4:
        tomador = ("<toma4><toma>4</toma>%s</toma4>"
                   % _parte_xml("toma4", *toma4)[len("<toma4>"):-len(
                       "</toma4>")])
    else:
        tomador = "<toma3><toma>%s</toma></toma3>" % toma
    docs = "".join("<infNFe><chave>%s</chave></infNFe>" % c
                   for c in chaves_nfe)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<cteProc xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">'
        '<CTe><infCte Id="CTe%s" versao="4.00"><ide><CFOP>%s</CFOP>'
        "<natOp>PRESTACAO DE SERVICO</natOp><mod>57</mod><serie>1</serie>"
        "<nCT>%s</nCT><dhEmi>2026-08-10T09:00:00-03:00</dhEmi>"
        "<tpCTe>%s</tpCTe><cMunIni>3550308</cMunIni><UFIni>SP</UFIni>"
        "<cMunFim>3106200</cMunFim><UFFim>MG</UFFim>%s</ide>%s%s%s"
        "<vPrest><vTPrest>%s</vTPrest><vRec>%s</vRec></vPrest>"
        "<imp><ICMS>%s</ICMS></imp><infCTeNorm><infDoc>%s</infDoc>"
        "</infCTeNorm></infCte></CTe><protCTe><infProt><chCTe>%s</chCTe>"
        "<nProt>131260000000001</nProt><cStat>%s</cStat></infProt>"
        "</protCTe></cteProc>"
        % (chave, cfop, nct, tpcte, tomador, _parte_xml("emit", *emit),
           _parte_xml("rem", *rem), _parte_xml("dest", *dest), vtprest,
           vtprest, icms, docs, chave, cstat))


def evento_cancelamento_xml(chave, modelo="nfe", cstat="135"):
    """procEventoNFe/procEventoCTe de cancelamento (110111)."""
    ch = "chNFe" if modelo == "nfe" else "chCTe"
    raiz = "procEventoNFe" if modelo == "nfe" else "procEventoCTe"
    return ('<?xml version="1.0" encoding="UTF-8"?><%s><evento><infEvento>'
            "<%s>%s</%s><tpEvento>110111</tpEvento></infEvento></evento>"
            "<retEvento><infEvento><cStat>%s</cStat></infEvento></retEvento>"
            "</%s>" % (raiz, ch, chave, ch, cstat, raiz))


def nfe_xml(itens=None, nnf="123", serie="1", mod="55", cfop="5102",
            vicms="1.80"):
    """XML mínimo de uma NF-e, casando com a nota de `icms_basico`.

    Só os grupos que o parser (`xml_fiscal.ler_nfe`) lê. `itens` é uma lista
    de dicts que sobrepõem os campos do item padrão (vProd 10.00, ICMS00 a
    18%); `CSOSN` no dict troca o grupo ICMS00 por um ICMSSN.
    """
    itens = itens or [{}, {}, {}]
    dets = []
    for n, extra in enumerate(itens, 1):
        c = {"cProd": "P%d" % n, "CFOP": cfop, "vProd": "10.00",
             "NCM": "21069090", "orig": "0", "CST": "00", "vBC": "10.00",
             "pICMS": "18.00", "vICMS": vicms}
        c.update(extra)
        if "CSOSN" in c:
            icms = ("<ICMSSN102><orig>%s</orig><CSOSN>%s</CSOSN></ICMSSN102>"
                    % (c["orig"], c["CSOSN"]))
        else:
            icms = ("<ICMS00><orig>%s</orig><CST>%s</CST><vBC>%s</vBC>"
                    "<pICMS>%s</pICMS><vICMS>%s</vICMS></ICMS00>"
                    % (c["orig"], c["CST"], c["vBC"], c["pICMS"], c["vICMS"]))
        dets.append(
            '<det nItem="%d"><prod><cProd>%s</cProd><xProd>PRODUTO</xProd>'
            "<NCM>%s</NCM><CFOP>%s</CFOP><uCom>UN</uCom><qCom>1</qCom>"
            "<vProd>%s</vProd></prod><imposto><ICMS>%s</ICMS></imposto></det>"
            % (n, c["cProd"], c["NCM"], c["CFOP"], c["vProd"], icms))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe>'
        '<infNFe Id="NFe31260811444777000161550010000001231000001230">'
        "<ide><mod>%s</mod><serie>%s</serie><nNF>%s</nNF>"
        "<dhEmi>2026-08-05T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide>%s%s"
        "<total><ICMSTot><vProd>30.00</vProd><vNF>30.00</vNF></ICMSTot>"
        "</total></infNFe></NFe></nfeProc>"
        % (mod, serie, nnf, _parte_xml("emit", "11444777000161",
                                        "FORNECEDOR TESTE"), "".join(dets)))

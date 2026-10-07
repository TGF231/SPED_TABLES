# -*- coding: utf-8 -*-
"""Os sistemas ERP e as conexões, guardados em `sistemas_erp.json` na pasta
de dados.

    {"sistemas": [{"id", "nome", "banco", "entidades": {...}}],
     "conexoes": [{"id", "nome", "sistema", "host", "porta", "base",
                   "usuario", "senha": "dpapi:…", "codificacao", "empresa",
                   "cnpjs": [...]}]}

O **sistema** é o perfil do ERP (tabela e coluna de cada informação) e vale
para todo cliente que usa aquele ERP; a **conexão** é o banco de um cliente.
A senha nunca vai legível para o disco (`segredos`, DPAPI do Windows).
Arquivo ilegível é preservado e avisado, como todo JSON do usuário.
"""

from sped_tables.dominio import erp
from sped_tables.infra import dados, segredos

ARQUIVO = "sistemas_erp.json"


class Configuracao:
    """Sistemas (`{id: Sistema}`) e conexões (`[Conexao]`) lidos do disco.
    `senhas_perdidas` lista as conexões cuja senha não pôde ser decifrada
    (JSON trazido de outra conta ou máquina): ficam sem senha."""

    def __init__(self, sistemas=None, conexoes=None):
        self.sistemas = dict(sistemas or {})
        self.conexoes = list(conexoes or [])
        self.senhas_perdidas = []

    def sistema_da(self, conexao):
        return self.sistemas.get(conexao.sistema)

    def da_empresa(self, cnpj):
        """As conexões vinculadas ao CNPJ."""
        return [c for c in self.conexoes if c.atende(cnpj)]

    def nome_livre(self, base, existentes):
        nomes = {x.lower() for x in existentes}
        if base.lower() not in nomes:
            return base
        n = 2
        while ("%s (%d)" % (base, n)).lower() in nomes:
            n += 1
        return "%s (%d)" % (base, n)


def caminho(arquivo=None):
    return arquivo or dados.caminho(ARQUIVO)


def carregar(arquivo=None):
    bruto = dados.ler_json_do_usuario(caminho(arquivo), dict) or {}
    cfg = Configuracao()
    for d in bruto.get("sistemas") or []:
        s = erp.Sistema.de_dict(d)
        if s.nome:
            cfg.sistemas[s.ident] = s
    for d in bruto.get("conexoes") or []:
        senha = ""
        try:
            senha = segredos.decifrar(d.get("senha", ""))
        except segredos.SegredoIndisponivel:
            cfg.senhas_perdidas.append(d.get("nome", ""))
        cfg.conexoes.append(erp.Conexao(
            nome=d.get("nome", ""), sistema=d.get("sistema", ""),
            host=d.get("host", ""), porta=d.get("porta", ""),
            base=d.get("base", ""), usuario=d.get("usuario", ""),
            senha=senha, codificacao=d.get("codificacao", ""),
            empresa=d.get("empresa", ""), cnpjs=d.get("cnpjs") or (),
            ident=d.get("id", "")))
    return cfg


def salvar(cfg, arquivo=None):
    conteudo = {
        "sistemas": [cfg.sistemas[k].para_dict() for k in sorted(cfg.sistemas)],
        "conexoes": [{
            "id": c.ident, "nome": c.nome, "sistema": c.sistema,
            "host": c.host, "porta": c.porta, "base": c.base,
            "usuario": c.usuario, "senha": segredos.cifrar(c.senha),
            "codificacao": c.codificacao, "empresa": c.empresa,
            "cnpjs": list(c.cnpjs)} for c in cfg.conexoes],
    }
    cam = caminho(arquivo)
    dados.gravar_json(cam, conteudo)
    return cam

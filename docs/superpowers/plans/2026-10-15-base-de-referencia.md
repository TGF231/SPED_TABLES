# Base de referência — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O programa deixa de ler a instalação do PVA para validar,
diagnosticar e corrigir: leiaute **por versão**, tabelas oficiais, guias e
NCM vigente passam a vir de uma **base de referência** compilada de `base/`,
embutida no executável e atualizável por importação.

**Architecture:** `consolidador/` (pacote novo na raiz, fora do
`sped_tables`) lê os PVAs da máquina de quem compila e regrava `base/` em
texto. `sped_tables/infra/base_referencia.py` compila `base/` num SQLite,
escolhe a base em uso (a mais nova entre a embutida e a importada) e importa
pacotes. `sped_tables/infra/referencias_base.py` é o novo adaptador da porta
`dominio.referencias`, que ganha a versão do leiaute
(`estrutura(layout, versao=None)`). O formato das tabelas continua sendo
lido no `sped_tables` (`tabelas_oficiais`, `tabelas_ncm`), agora sobre
**texto** e não sobre caminhos.

**Tech Stack:** Python 3.14 pelo `py` (é onde está o PyQt6), PyQt6,
`sqlite3`/`zlib`/`zipfile`/`hashlib` da biblioteca padrão, `openpyxl` (só no
consolidador, para a planilha de NCM), `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-15-base-de-referencia-design.md`
(vocabulário em `CONTEXT.md`; decisões em
`docs/adr/0001-base-de-referencia-compilada.md` e
`docs/adr/0002-regras-em-sql-sobre-o-arquivo.md`). Leia o spec e o
`CLAUDE.md` antes da primeira tarefa.

## Global Constraints

- Todo código, comentário, mensagem, teste e documentação em **português do
  Brasil**.
- **Nenhum dado de cliente** no repositório: nem arquivo, nem nome, nem CNPJ,
  nem caminho. Nos textos, "cliente A" / "cliente B". Nunca imprima o
  conteúdo de `arquivos/indice.json` nem nomes de arquivos reais.
- **O `sped_tables` nunca importa o `consolidador`**; o contrário é
  permitido.
- **Nada do `sped_tables` lê a pasta do PVA** para validar, diagnosticar ou
  corrigir. Só o *Abrir no PVA* usa a instalação local (`infra/pva.py`,
  `aplicacao/envio_pva.py` e o *Pasta dos PVAs…* da interface, que só
  escolhe a raiz para ele).
- **Nada do PVA é copiado** para o repositório além de fatos (ADR 0001):
  estrutura declarada do descritor, tabelas de códigos, nomes das regras.
  Nada de SQL, código Java nem textos de mensagem do PVA.
- Versão da base `AAAA.MM.n`; **esquema 1**; base compilada **abaixo de
  10 MB**.
- Retenção: versões do leiaute com vigência nos **últimos 5 anos** mais a
  atual (e as futuras que já tiverem descritor).
- **Compilação reproduzível:** mesmas fontes, mesmo banco, byte a byte.
- Fontes de `base/` em **UTF-8**; arquivos SPED continuam **latin-1**.
- **O resultado não muda:** `tests/test_reais.py` com o `gabarito.json`
  atual passa sem alteração, com a pasta do PVA apontada para um diretório
  vazio.
- A suíte inteira roda **antes de todo commit**:
  `py -m unittest discover -s tests -t .`
- **Patches direcionados**, nunca reescrita completa de arquivo (mover com
  `git mv` e editar é permitido).
- SemVer em `sped_tables/version.py` + `CHANGELOG.md` (Keep a Changelog).
- Mensagem de commit termina com
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commits só
  locais (sem push).

## Desvios em relação ao spec (decididos ao planejar)

1. **A leitura do formato das tabelas fica no `sped_tables`**, sobre texto
   (`{chave: (texto, versao)}`); para o consolidador vai só o acesso à
   pasta e ao `.jar` do PVA. O spec dizia que os leitores se mudavam
   "intactos" — mas o programa precisa interpretar as tabelas que vêm da
   base, e duas cópias do mesmo leitor divergiriam.
2. **As tabelas em `base/` mantêm o formato do PVA** (`cod|desc|DT_INI|
   DT_FIM`, cabeçalho `versão=N …`), em UTF-8 e **na ordem original das
   linhas** — a ordem decide a descrição quando um código se repete
   (`carregar_codigos` fica com a primeira vigente). Nome do arquivo:
   `GRUPO@TABELA.txt` (o `$` atrapalha no terminal).
3. **O JSON do leiaute não é ordenado por chave:** a ordem dos campos é a
   posição no registro (`alinhar_ao_leiaute` usa `enumerate`). Ordenar
   trocaria colunas em silêncio.
4. **Não existe tela *Sobre*.** A versão da base aparece no novo diálogo
   *Configurações → Base de referência…* (que também importa) e no
   autoteste do executável.
5. **A suíte compila `base/` no mesmo lugar que o programa**
   (`recursos/base_referencia.db`, ignorado pelo git); testes que precisam
   de outra base compilam fontes inventadas numa pasta temporária.
6. **Contribuições:** a tabela `SPEDPISCOFINS_VERSOES_LEIAUTE` do próprio PVA
   diz que só a versão `006` (desde 01/01/2020, em aberto) cabe na janela de
   5 anos; ela corresponde ao descritor mais recente. Nenhuma outra versão
   do Contribuições entra, e não há o que confirmar no PVA de ensaio neste
   projeto.
7. **`tests/fabrica.py` passa a declarar `COD_VER="020"`** no ICMS/IPI (hoje
   `019` com período de 2026). Até aqui o arquivo de teste era conferido com
   o descritor mais recente qualquer que fosse a versão declarada; com a
   versão por arquivo, deixar `019` mudaria a régua de todos os testes.

## Review Focus

1. **`COD_VER` ausente ou fora do formato** (`""`, `"19"`, `"abc"`, sem
   0000): vale a versão mais recente da base, como antes, sem exceção —
   teste na Tarefa 3.
2. **`COD_VER` que não bate com o período** (`019` com `DT_FIN` de 2026): a
   estrutura usada é a da versão **declarada** (é por ela que o PVA
   importa), sem acusação nova — teste na Tarefa 5.
3. **Base importada ilegível ou truncada** na pasta de dados (0 bytes, lixo,
   esquema novo): aviso, vale a embutida, o programa abre — teste na
   Tarefa 4.
4. **Pacote malformado** (sem banco, sem manifesto, impressão digital
   divergente, manifesto que não corresponde ao banco, membro grande
   demais, versão igual/mais antiga): recusa com o motivo e a base em uso
   continua intacta — testes na Tarefa 4.
5. **Nenhuma base legível** (executável danificado, `base/` ausente): a
   fonte fica vazia, um aviso, as validações se abstêm e o diagnóstico diz
   "base de referência indisponível" — testes nas Tarefas 4 e 7.

## Mapa de arquivos

| Arquivo | Papel |
|---|---|
| `sped_tables/infra/tabelas_oficiais.py` (era `tabelas_pva.py`) | lê o formato das tabelas a partir de texto; domínios por datasource; CFOP com crédito; naturezas; prazos |
| `sped_tables/infra/tabelas_ncm.py` (era `tabelas_rfb.py`) | tabelas de produtos (alíquota zero, monofásicos, gênero) → `ClassificadorNCM` |
| `sped_tables/infra/base_referencia.py` (novo) | compila `base/`, lê o banco (`Base`), escolhe a base em uso, empacota e importa |
| `sped_tables/infra/referencias_base.py` (novo) | adaptador da porta sobre qualquer origem com a interface de `Base` |
| `sped_tables/dominio/referencias.py` | porta: `estrutura(layout, versao=None)`, `versao_vigente`, `descricao`; helper `versao_do_leiaute(doc)` |
| `consolidador/` (novo) | `descritor.py` (era `infra/descritor_pva.py`), `instalacao.py`, `extracao.py`, `guias.py` (era `ferramentas/extrair_guias.py`), `banco_pva.py` (era `infra/banco_pva.py`), `__main__.py` |
| `base/` (novo) | fontes em texto: `manifesto.json`, `leiaute/<LEIAUTE>/<COD_VER>.json`, `tabelas/*.txt`, `guias/<LEIAUTE>.json` (eram `recursos/guia_*.json`), `ncm/vigente.txt` |
| `sped_tables/interface/dialogos/base_referencia.py` (novo) | mostra a base em uso e importa uma mais nova |
| apagados | `infra/referencias_pva.py`, `infra/guias.py`, configuração *Tabelas da RFB* |

---

### Task 1: Fim da configuração "Tabelas da RFB"

O classificador de NCM passa a vir sempre da porta (`referencias.atual().
classificador_ncm()`). Os diálogos param de pedir pasta e arquivos, e a
configuração gravada sai do `config`.

**Files:**
- Modify: `sped_tables/interface/dialogos/correcao.py` (`DialogoVerificarCST`)
- Modify: `sped_tables/interface/dialogos/cadastro.py:357-360,493-545`
- Modify: `sped_tables/interface/controladores/contribuicoes.py:239-270,339`
- Modify: `sped_tables/interface/janela.py:67`
- Modify: `sped_tables/infra/config.py:156-187` e o `import json`
- Modify: `sped_tables/infra/tabelas_rfb.py:188-202` (apaga `classificador`)
- Modify: `sped_tables/infra/referencias_pva.py:71-80`
- Modify: `ferramentas/validar_no_pva.py:44,115,288`
- Modify: `tests/test_robustez.py:171-178` (apaga o teste da migração)
- Test: `tests/test_interface.py`

**Interfaces:**
- Consumes: `referencias.atual().classificador_ncm()` (já existe; devolve
  `ClassificadorNCM` ou `None`).
- Produces: `DialogoVerificarCST(doc, data_ref, parent=None)`;
  `DialogoEmpresa(doc, parent=None)` (sem `cfg_rfb`); `config` sem
  `tabelas_rfb`/`gravar_tabelas_rfb`/`CHAVES_TABELAS_RFB`/
  `ARQUIVO_ANTIGO_RFB`; `tabelas_rfb` sem `classificador`.

- [ ] **Step 1: Write the failing test** — em `tests/test_interface.py`,
  dentro de `TestJanela`:

```python
    def test_cst_por_ncm_usa_a_fonte_de_referencias(self):
        """O diálogo não pede mais pasta nem arquivos: o classificador vem
        da porta, a mesma fonte das outras regras."""
        from sped_tables.dominio import referencias
        from sped_tables.dominio.ncm import ClassificadorNCM

        class Fonte(referencias.Referencias):
            def classificador_ncm(self):
                return ClassificadorNCM()

        antes = referencias.definir(Fonte())
        try:
            with PastaTemporaria() as p:
                j = self.ed.JanelaPrincipal()
                self.assertTrue(j.abrir_caminho(contrib_basico().gravar(p)))
                _esperar()
                j.verificar_cst_ncm()
                dlg = j._janelas["DialogoVerificarCST"]
                self.assertFalse(hasattr(dlg, "ed_pasta"))
                dlg._verificar()
                self.assertEqual(dlg.tab.rowCount(), 0)
                j.close()
        finally:
            referencias.definir(antes)
        self.assertEqual(self.erros, [], self._falhas())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_interface.TestJanela.test_cst_por_ncm_usa_a_fonte_de_referencias -v`
Expected: FAIL (`ed_pasta` existe).

- [ ] **Step 3: Implement**

`correcao.py` — o construtor perde `cfg` e `on_cfg`; a caixa de
configuração fica só com a data. Troque o trecho de `def __init__(self,
doc, cfg, data_ref, on_cfg, parent=None):` até `lay.addWidget(cfgbox)` por:

```python
    def __init__(self, doc, data_ref, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("Verificar CST de PIS/COFINS por NCM")
        self.resize(880, 620)
        lay = QVBoxLayout(self)

        info = QLabel(
            "Classifica cada item (C170) pelo NCM usando as tabelas oficiais da "
            "RFB (alíquota zero e monofásicos, da base de referência) e aponta "
            "CST de PIS/COFINS incoerentes (ex.: entrada de produto monofásico "
            "com crédito, ou produto de alíquota zero tributado). O C175 "
            "(NFC-e consolidada) não é verificável por NCM.")
        info.setWordWrap(True)
        lay.addWidget(info)

        cfgbox = QGroupBox("Vigência")
        gl = QGridLayout(cfgbox)
        gl.addWidget(QLabel("Data de referência:"), 0, 0)
        self.ed_data = QLineEdit(data_ref or "")
        self.ed_data.setPlaceholderText("DDMMAAAA")
        self.ed_data.setMaximumWidth(120)
        gl.addWidget(self.ed_data, 0, 1)
        lay.addWidget(cfgbox)
```

Apague `_pasta`, `_arquivo` e `_coletar_cfg`. Em `_verificar`, troque o
começo (do `cfg = self._coletar_cfg()` até `self.on_cfg(cfg)`) por:

```python
    def _verificar(self):
        clf = referencias.atual().classificador_ncm()
        if clf is None:
            QMessageBox.warning(
                self, "Tabelas",
                "A base de referência não tem as tabelas de alíquota zero e "
                "de monofásicos: a verificação não tem com o que comparar.")
            return
```

Troque `from sped_tables.infra import tabelas_rfb as trfb` por
`from sped_tables.dominio import referencias` e retire do import do Qt o que
ficar sem uso (`QFileDialog`, se nada mais o usar — o
`tests/test_estrutura.py` acusa import sem uso).

`cadastro.py` — `def __init__(self, doc, parent=None):` (sem `cfg_rfb`) e
apague `self.cfg_rfb = cfg_rfb or {}`. Em `_rotina_mudou`, apague o bloco
`if r.requer == "tabelas_rfb": texto += (...)`. Troque `_classificador` por:

```python
    def _classificador(self):
        """O classificador de NCM da base de referência (a mesma fonte das
        outras regras), ou None com o aviso."""
        clf = referencias.atual().classificador_ncm()
        if clf is None:
            QMessageBox.warning(
                self, "Tabelas de NCM",
                "A base de referência não tem as tabelas de alíquota zero e "
                "de monofásicos: esta rotina não pode rodar.")
        return clf
```

e troque `from sped_tables.infra import tabelas_rfb as trfb` por
`from sped_tables.dominio import referencias` (se ainda não importado).

`contribuicoes.py` — apague `_salvar_cfg_tabelas`; em `verificar_cst_ncm`:

```python
        self._dlg_cst = abrir_janela(self, DialogoVerificarCST(
            self.doc, self._data_fin_doc(), self))
```

e em `configurar_empresa` (linha ~339):

```python
        self._dlg_empresa = abrir_janela(self, DialogoEmpresa(self.doc, self))
```

`janela.py:67` — apague `self.cfg_tabelas = config.tabelas_rfb()` (e o
`import` de `config`, se ficar sem uso).

`config.py` — apague a seção `# ----- tabelas da RFB` inteira
(`CHAVES_TABELAS_RFB`, `ARQUIVO_ANTIGO_RFB`, `tabelas_rfb`,
`gravar_tabelas_rfb`) e o `import json`. Na docstring do topo, troque
"`tabelas_rfb`" por "e as tabelas de NCM".

`tabelas_rfb.py` — apague a função `classificador(cfg=None)`.

`referencias_pva.py` — em `classificador_ncm`:

```python
                from sped_tables.infra import tabelas_rfb
                self._clf = tabelas_rfb.carregar_tudo()[0]
```

`ferramentas/validar_no_pva.py` — apague `from sped_tables.infra import
tabelas_rfb`; nas linhas 115 e 288 troque
`clf, _c = tabelas_rfb.classificador()` por
`clf = referencias.atual().classificador_ncm()` e importe
`from sped_tables.dominio import referencias  # noqa: E402` junto dos
outros imports do domínio.

`tests/test_robustez.py` — apague `test_tabelas_rfb_migram_do_arquivo_antigo`.

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_interface tests.test_robustez tests.test_estrutura -v`
Expected: PASS. Depois a suíte inteira: `py -m unittest discover -s tests -t .` → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A sped_tables ferramentas tests
git commit -m "Tabelas de NCM pela porta de referências (fim da configuração Tabelas da RFB)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Tabelas oficiais lidas de texto

Toda a interpretação das tabelas passa a receber um **conjunto**
`{chave: (texto, versao)}` — chave `GRUPO$TABELA`, sempre na maior versão —
em vez de procurar arquivos numa pasta. É o que permite, depois, a base
entregar o mesmo conjunto. **Nenhum comportamento muda.**

**Files:**
- Move: `sped_tables/infra/tabelas_pva.py` → `sped_tables/infra/tabelas_oficiais.py`
- Move: `sped_tables/infra/tabelas_rfb.py` → `sped_tables/infra/tabelas_ncm.py`
- Modify: `sped_tables/infra/referencias_pva.py`
- Modify: `sped_tables/dominio/ncm.py:7,16` (docstring cita `tabelas_rfb`)
- Modify: `tests/test_revisao.py:68-70`
- Test: `tests/test_tabelas_oficiais.py` (novo)

**Interfaces:**
- Produces (`tabelas_oficiais`):
  - `tabelas_da_pasta(pasta, encoding="latin-1") -> {chave: (texto, versao:int)}`
  - `chave_data(ddmmaaaa) -> "AAAAMMDD" | ""` (era `_chave_data`)
  - `carregar_codigos(texto, data_ref=None) -> {"versao", "codigos"}`
  - `dominio_cst_icms(tabs, data_ref=None)`
  - `cfops_com_credito(tabs, data_ref=None)`
  - `naturezas_receita(tabs, cst, data_ref=None)`
  - `tabela_natureza_receita(tabs, cst)`
  - `ncms_da_natureza(tabs, codigo)`
  - `naturezas_cfop_credito(tabs, data_ref=None)`
  - `prazo_entrega(tabs, mes_ano)`
  - `codigos_receita_icms(tabs, uf, data_ref=None)`
  - `codigos_de(chave, tabs, uf=None, data_ref=None)` (inalterada)
  - `dominios_por_datasource(tabs, estrutura, layout, uf=None, data_ref=None)`
  - `ROTULOS` (inalterado)
- Produces (`tabelas_ncm`):
  - `CHAVE_ALIQ_ZERO`, `CHAVE_MONO`, `CHAVE_MONO_DIFER`, `CHAVE_GENERO`
    (chaves completas `GRUPO$TABELA`)
  - `carregar_tabela_produtos(texto)`, `carregar_genero(texto)`
  - `classificador(tabs, ncm_vigente=None) -> ClassificadorNCM | None`
    (`None` quando não há nem a tabela de alíquota zero nem as de
    monofásico)

- [ ] **Step 1: Write the failing test** — `tests/test_tabelas_oficiais.py`:

```python
# -*- coding: utf-8 -*-
"""As tabelas oficiais lidas de texto: o formato do PVA, com vigência,
independente de onde o texto veio (pasta do PVA, base de referência)."""

import os
import unittest

from sped_tables.infra import tabelas_ncm, tabelas_oficiais as T
from tests.fabrica import PastaTemporaria

CFOP = ("versão=14 CFOP, DESC_CFOP, DT_INI, DT_FIM\n"
        "1102|Compra para comercialização|01012009|\n"
        "1999|Revogado|01012009|31122010\n")
CREDITO = ("versão=9 CFOP, DESC, DT_INI, DT_FIM, NAT_BC_CRE\n"
           "1102|Compra|01012009||01\n")
PRAZO = ("versão=51 MES_ANO, DATA\n"
         "082026|14102026|01012009|\n")
ZERO = ("versão=52 COD, DESC, DT_INI, DT_FIM, NCM, EXC, EX_IPI\n"
        "101|Hortícolas|01012009||0702;0703||\n")
MONO = ("versão=40 COD, DESC, DT_INI, DT_FIM, NCM, EXC, EX_IPI, UNID, "
        "ALIQ_PIS, ALIQ_COFINS\n"
        "201|Cerveja|01012009||2203||UN|1,00|2,00\n")


class TestLeitura(unittest.TestCase):

    def test_codigos_respeitam_a_vigencia(self):
        t = T.carregar_codigos(CFOP, "31082026")
        self.assertEqual(t["versao"], "14")
        self.assertEqual(set(t["codigos"]), {"1102"})
        self.assertEqual(set(T.carregar_codigos(CFOP)["codigos"]),
                         {"1102", "1999"})

    def test_pasta_fica_com_a_maior_versao_e_ignora_metadados(self):
        with PastaTemporaria() as p:
            for nome, texto in (("SPEDFISCAL_GLOBAL$CFOP$13$1", "antigo"),
                                ("SPEDFISCAL_GLOBAL$CFOP$14$1", CFOP),
                                ("metadados", "\x00\x01")):
                with open(os.path.join(p, nome), "w",
                          encoding="latin-1") as fh:
                    fh.write(texto)
            tabs = T.tabelas_da_pasta(p)
        self.assertEqual(list(tabs), ["SPEDFISCAL_GLOBAL$CFOP"])
        self.assertEqual(tabs["SPEDFISCAL_GLOBAL$CFOP"], (CFOP, 14))

    def test_funcoes_sobre_o_conjunto(self):
        tabs = {
            "SPEDPISCOFINS_OPER_CREDITO$SPEDPISCOFINS_CFOP_CREDITO":
                (CREDITO, 9),
            "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_DATA_LIMITE_ENTREGA":
                (PRAZO, 51),
        }
        self.assertEqual(T.naturezas_cfop_credito(tabs, "31082026"),
                         {"1102": "01"})
        self.assertEqual(T.cfops_com_credito(tabs)[0], {"1102"})
        self.assertEqual(T.prazo_entrega(tabs, "082026"), "14102026")
        self.assertEqual(T.prazo_entrega({}, "082026"), "")

    def test_dominio_pelo_datasource_do_descritor(self):
        estrutura = {"C170": {"campos": {"CFOP": {"datasource": "CFOP"}}}}
        tabs = {"SPEDFISCAL_GLOBAL$CFOP": (CFOP, 14)}
        dom, faltando = T.dominios_por_datasource(
            tabs, estrutura, "ICMS", uf="MG", data_ref="31082026")
        self.assertEqual(dom[("C170", "CFOP")]["codigos"], {"1102"})
        self.assertEqual(faltando, [])

    def test_classificador_das_tabelas_de_ncm(self):
        tabs = {tabelas_ncm.CHAVE_ALIQ_ZERO: (ZERO, 52),
                tabelas_ncm.CHAVE_MONO: (MONO, 40)}
        clf = tabelas_ncm.classificador(tabs)
        self.assertTrue(clf.eh_aliquota_zero("07031019"))
        self.assertTrue(clf.eh_monofasico("22030000"))
        self.assertIsNone(tabelas_ncm.classificador({}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_tabelas_oficiais -v`
Expected: FAIL com `ImportError` (`tabelas_oficiais` não existe).

- [ ] **Step 3: Implement**

```bash
git mv sped_tables/infra/tabelas_pva.py sped_tables/infra/tabelas_oficiais.py
git mv sped_tables/infra/tabelas_rfb.py sped_tables/infra/tabelas_ncm.py
```

Em `tabelas_oficiais.py`:

- docstring do topo: troque o título por `tabelas_oficiais.py` e o parágrafo
  de abertura por "Domínios de campo e consultas sobre as **tabelas
  oficiais** (as que os PVAs publicam), lidas de **texto**: quem entrega o
  conjunto `{chave: (texto, versao)}` é a base de referência (ou, no
  consolidador, a pasta do PVA). Aqui só se interpreta o formato." Mantenha
  o resto (formato, vigência, compostos, UF).
- imports: apague `io`, `glob` e `from sped_tables.infra import config`;
  acrescente `from sped_tables.infra import tabelas_ncm`.
- apague `_pasta_fiscal`, `_pasta_contrib`, `_chave_sem_versao` e
  `listar_tabelas`; no lugar deles:

```python
# nome de arquivo de tabela do PVA: GRUPO$TABELA$versao$id
RE_ARQUIVO = re.compile(r"^(.*?)\$(\d+)\$\d+$")


def tabelas_da_pasta(pasta, encoding="latin-1"):
    """`{chave: (texto, versao)}` das tabelas de uma pasta do PVA, cada uma
    na **maior versão**. Arquivo fora do padrão `GRUPO$TABELA$versao$id`
    (o `metadados`, binário) fica de fora."""
    out = {}
    if not pasta or not os.path.isdir(pasta):
        return out
    for nome in sorted(os.listdir(pasta)):
        m = RE_ARQUIVO.match(nome)
        caminho = os.path.join(pasta, nome)
        if not m or not os.path.isfile(caminho):
            continue
        chave, versao = m.group(1), int(m.group(2))
        if chave in out and out[chave][1] >= versao:
            continue
        with open(caminho, encoding=encoding) as fh:
            out[chave] = (fh.read(), versao)
    return out
```

- renomeie `_chave_data` para `chave_data` (e todos os usos no módulo).
- `carregar_codigos` passa a receber o texto:

```python
def carregar_codigos(texto, data_ref=None):
    """Lê uma tabela de códigos no formato do PVA. Devolve `{"versao",
    "codigos"}`, com `codigos` = `{codigo: descricao}` **vigentes** em
    `data_ref`.

    Sem `data_ref`, entra tudo — útil para inspeção, não para validar.
    """
    codigos = {}
    versao = None
    linhas = (texto or "").splitlines()
    if linhas:
        m = re.search(r"vers[ãa]o=(\S+)", linhas[0])
        versao = m.group(1) if m else None
    alvo = chave_data(data_ref)
    for l in linhas[1:]:
        # (o corpo do laço continua igual ao de hoje)
```

- cada função que fazia `tabs = listar_tabelas(_pasta_contrib(pasta_contrib))`
  ou `listar_tabelas(_pasta_fiscal(pasta_fiscal))` passa a receber `tabs`
  como **primeiro parâmetro** e apaga essa linha. Assinaturas novas, na
  ordem do arquivo:

```python
def cfops_com_credito(tabs, data_ref=None):
def naturezas_receita(tabs, cst, data_ref=None):
def tabela_natureza_receita(tabs, cst):
def ncms_da_natureza(tabs, codigo):
def naturezas_cfop_credito(tabs, data_ref=None):
def prazo_entrega(tabs, mes_ano):
def codigos_receita_icms(tabs, uf, data_ref=None):
def dominios_por_datasource(tabs, estrutura, layout, uf=None, data_ref=None):
```

- em `tabela_natureza_receita` e `ncms_da_natureza`, apague o
  `from sped_tables.infra import tabelas_rfb` local, troque
  `tabelas_rfb.carregar_tabela_produtos(alvo[0])` por
  `tabelas_ncm.carregar_tabela_produtos(alvo[0])` e apague o
  `try/except OSError` em volta (não há mais arquivo).
- em `naturezas_cfop_credito`, troque o bloco `try: with io.open(...)` por
  `linhas = alvo[0].splitlines()`.
- em `dominios_por_datasource`, apague as duas linhas de `listar_tabelas`.

Em `tabelas_ncm.py`:

- docstring: "Tabelas de produtos da EFD Contribuições usadas na conferência
  de CST por NCM (4.3.13 alíquota zero; 4.3.10 e 4.3.11 monofásicos; gênero
  do item), lidas de texto." Mantenha a lista das tabelas.
- apague `import os`, `import glob`, `from sped_tables.infra import config`,
  `pasta_padrao`, `_versao_do_nome`, `localizar_tabela`,
  `carregar_ncm_vigente` (volta no consolidador, Tarefa 6) e
  `carregar_tudo`.
- as chaves passam a ser completas:

```python
CHAVE_ALIQ_ZERO = "SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_PROD_ALIQ_ZERO"
# São DUAS tabelas de monofásico, e ler só uma esconde metade dos produtos:
# o NCM 34011190 (sabonete) só existe na de alíquotas diferenciadas, e sem ela
# o programa não via nada que o PVA via.
CHAVE_MONO = "SPEDPISCOFINS_OPER_CONTRIB$SPEDPISCOFINS_PROD_MONO_ALIQ_UNID"
CHAVE_MONO_DIFER = ("SPEDPISCOFINS_OPER_CONTRIB$"
                    "SPEDPISCOFINS_PROD_MONO_ALIQ_DIFER")
CHAVE_GENERO = "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_GENERO_ITEM"
```

- `carregar_tabela_produtos(texto)` e `carregar_genero(texto)`: troque o
  `with open(caminho, ...) as fh: linhas = fh.read().splitlines()` por
  `linhas = (texto or "").splitlines()` (o resto do corpo fica).
- no lugar de `carregar_tudo`:

```python
def classificador(tabs, ncm_vigente=None):
    """`ClassificadorNCM` das tabelas de alíquota zero, das duas de
    monofásico e do gênero do item, mais o conjunto de NCM vigente (ou
    None). Sem nenhuma das tabelas de produto, devolve None: a regra se
    abstém em vez de aprovar no escuro."""
    def produtos(chave):
        alvo = tabs.get(chave)
        return carregar_tabela_produtos(alvo[0]) if alvo else None

    tab_zero = produtos(CHAVE_ALIQ_ZERO)
    tab_mono = _unir_tabelas(produtos(CHAVE_MONO), produtos(CHAVE_MONO_DIFER))
    if tab_zero is None and tab_mono is None:
        return None
    gen = tabs.get(CHAVE_GENERO)
    return ClassificadorNCM(tab_zero, tab_mono,
                            carregar_genero(gen[0]) if gen else None,
                            ncm_vigente or None)
```

Em `referencias_pva.py` (vive até a Tarefa 7): troque o import de
`tabelas_pva` por `from sped_tables.infra import config, tabelas_ncm,
tabelas_oficiais`, acrescente `self._tabs = None` no `__init__` e:

```python
    def _tabelas(self):
        # as duas pastas, como `dominios_por_datasource` sempre leu
        if self._tabs is None:
            tabs = tabelas_oficiais.tabelas_da_pasta(
                config.pasta_tabelas("ICMS"))
            tabs.update(tabelas_oficiais.tabelas_da_pasta(
                config.pasta_tabelas("CONTRIB")))
            self._tabs = tabs
        return self._tabs
```

e cada método passa `self._tabelas()` como primeiro argumento à função de
mesmo nome em `tabelas_oficiais` (`dominios_por_datasource(self._tabelas(),
estrutura, layout, uf=uf, data_ref=data_ref)`, `naturezas_receita(
self._tabelas(), cst, data_ref=data_ref)`, …). `rotulo` usa
`tabelas_oficiais.ROTULOS`. `classificador_ncm`:

```python
    def classificador_ncm(self):
        if not self._clf_lido:
            self._clf_lido = True
            self._clf = tabelas_ncm.classificador(self._tabelas())
        return self._clf
```

`dominio/ncm.py`: nas linhas 7 e 16 da docstring, `infra.tabelas_rfb` →
`infra.tabelas_ncm`.

`tests/test_revisao.py:68-70`:

```python
        from sped_tables.dominio import referencias
        if not referencias.atual().prazo_entrega("082026"):
            self.skipTest("tabela de prazos indisponível")
```

Procure resto de nome antigo:
`grep -rn "tabelas_pva\|tabelas_rfb" --include=*.py .` — só podem sobrar
textos em comentário que você vai acertar agora.

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_tabelas_oficiais -v` → PASS.
Run: `py -m unittest discover -s tests -t .` → PASS.
Run (na máquina com os arquivos reais): `py -m unittest tests.test_reais -v`
com `SPED_TABLES_ARQUIVOS_REAIS` apontando a pasta → PASS, gabarito
inalterado.

- [ ] **Step 5: Commit**

```bash
git add -A sped_tables tests
git commit -m "Tabelas oficiais lidas de texto (tabelas_oficiais, tabelas_ncm)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: A porta pede a versão do leiaute

A porta ganha a versão (`estrutura(layout, versao=None)`), quem tem o
documento passa o `COD_VER` dele, e a geração passa a versão do período que
gera. Até a Tarefa 7, o `ReferenciasPVA` aceita a versão e a ignora (só tem
a mais recente) — o comportamento não muda.

**Files:**
- Modify: `sped_tables/dominio/referencias.py`
- Modify: `sped_tables/dominio/diagnostico.py:221-225`
- Modify: `sped_tables/dominio/validacao.py:422`
- Modify: `sped_tables/dominio/revisao.py:193`
- Modify: `sped_tables/dominio/regras_guia.py:140`
- Modify: `sped_tables/dominio/sped_model.py:2420`
- Modify: `sped_tables/dominio/ajuda.py:23-31,57-60`
- Modify: `sped_tables/dominio/geracao.py:549,587-597,718,909`
- Modify: `sped_tables/interface/grade.py:442-453`, `sped_tables/interface/dialogos/ajuda.py:116-122`
- Modify: `sped_tables/interface/dialogos/verificacao.py:247-255`
- Modify: `sped_tables/infra/referencias_pva.py:30`
- Modify: `tests/fabrica.py:97`, `tests/test_situacoes_contribuinte.py:302`, `tests/test_guias.py:260`
- Test: `tests/test_versao_leiaute.py` (novo)

**Interfaces:**
- Produces (porta, em `Referencias`):
  - `estrutura(self, layout, versao=None) -> (estrutura, info)`; versão que
    a fonte não guarda → `({}, {"descritor": None, "versao": versao,
    "fora_da_base": True, "erro": "..."})`
  - `versao_vigente(self, layout, data) -> str | None` (data `DDMMAAAA`)
  - `descricao(self) -> str`
- Produces (helper do domínio): `referencias.versao_do_leiaute(doc) -> str | None`
- Produces: `ajuda.do_campo(layout, reg, n, nome, est=None, guia=None, versao=None)`,
  `ajuda.do_registro(layout, reg, versao=None)`,
  `DialogoAjuda(layout, reg, campo=None, parent=None, versao=None)`
- Produces: `diagnostico.verificar` devolve `info` com `"sem_base"`
  (estrutura vazia), `"fora_da_base"` (a versão, ou None) e `"versao"`; a
  chave `"sem_pva"` deixa de existir.

- [ ] **Step 1: Write the failing test** — `tests/test_versao_leiaute.py`:

```python
# -*- coding: utf-8 -*-
"""A versão do leiaute é a do arquivo: quem tem o documento pede à porta a
estrutura do COD_VER dele, nunca "a mais recente"."""

import unittest

from sped_tables.dominio import diagnostico, geracao, referencias, validacao
from sped_tables.dominio.sped_model import SpedDocument
from tests.fabrica import PastaTemporaria, contrib_basico, icms_basico


class FonteQueAnota(referencias.Referencias):
    """Anota cada versão pedida e responde "fora da base"."""

    def __init__(self):
        self.pedidas = []

    def estrutura(self, layout, versao=None):
        self.pedidas.append((layout, versao))
        return {}, {"descritor": None, "versao": versao,
                    "fora_da_base": True, "erro": "fora da base"}

    def versao_vigente(self, layout, data):
        return "020" if data.endswith("2026") else None


def _doc(m):
    with PastaTemporaria() as p:
        return SpedDocument.carregar(m.gravar(p))


class TestVersaoDoArquivo(unittest.TestCase):

    def setUp(self):
        self.fonte = FonteQueAnota()
        self._antes = referencias.definir(self.fonte)

    def tearDown(self):
        referencias.definir(self._antes)

    def test_versao_do_leiaute(self):
        self.assertEqual(referencias.versao_do_leiaute(_doc(icms_basico())),
                         "020")
        self.assertEqual(
            referencias.versao_do_leiaute(_doc(contrib_basico())), "006")
        for ruim in ("", "19", "abc"):
            m = icms_basico()
            m.alterar("0000", COD_VER=ruim)
            self.assertIsNone(referencias.versao_do_leiaute(_doc(m)), ruim)

    def test_diagnostico_pede_a_versao_do_arquivo(self):
        _achados, info = diagnostico.verificar(_doc(icms_basico()))
        self.assertTrue(self.fonte.pedidas)
        self.assertEqual({v for _l, v in self.fonte.pedidas}, {"020"})
        self.assertEqual(info["fora_da_base"], "020")
        self.assertTrue(info["sem_base"])

    def test_validacao_pede_a_versao_do_arquivo(self):
        validacao.dominios_do_documento(_doc(contrib_basico()))
        self.assertEqual(self.fonte.pedidas, [("CONTRIB", "006")])

    def test_cod_ver_ruim_pede_a_mais_recente(self):
        m = icms_basico()
        m.alterar("0000", COD_VER="19")
        validacao.dominios_do_documento(_doc(m))
        self.assertEqual(self.fonte.pedidas, [("ICMS", None)])

    def test_geracao_pede_a_versao_do_periodo(self):
        geracao._larguras({}, "ICMS", "31082026")
        self.assertEqual(self.fonte.pedidas, [("ICMS", "020")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_versao_leiaute -v`
Expected: FAIL (`versao_do_leiaute` não existe; `fabrica` declara `019`).

- [ ] **Step 3: Implement**

`referencias.py` — atualize a docstring do topo (a implementação de verdade
é "a base de referência, `sped_tables.infra.referencias_base`"; a porta não
lê o PVA) e troque o método `estrutura` por:

```python
    def estrutura(self, layout, versao=None):
        """Estrutura do leiaute: `(estrutura, info)`.

        `versao` é a versão que o arquivo declara (`versao_do_leiaute`);
        `None` pede a mais recente da fonte — é o que vale para arquivo sem
        COD_VER legível. Versão que a fonte não guarda devolve estrutura
        vazia e `info["fora_da_base"]`: nada se cobra por estrutura de
        outra versão."""
        return {}, {"descritor": None,
                    "erro": "nenhuma base de referência ligada"}

    def versao_vigente(self, layout, data):
        """COD_VER vigente na data (DDMMAAAA), entre as versões que a fonte
        guarda; None quando nenhuma cobre a data."""
        return None

    def descricao(self):
        """De onde vêm as referências, numa linha, para as telas."""
        return "nenhuma base de referência"
```

e acrescente, depois de `texto_do_campo`:

```python
def versao_do_leiaute(doc):
    """A versão do leiaute que o arquivo declara (COD_VER do 0000, ex.:
    "020"), ou None quando falta ou não tem três dígitos — aí vale a mais
    recente da fonte, como antes de a versão contar."""
    i = doc._ix("0000", "COD_VER")
    if i is None:
        return None
    for r in doc.registros:
        if r.reg == "0000":
            v = (r.valor(i) or "").strip()
            return v if len(v) == 3 and v.isdigit() else None
    return None
```

Chamadas que passam a versão do arquivo (troque exatamente a linha citada):

```python
# diagnostico.py:221 — e o dicionário `info` logo abaixo
    estrutura, info_desc = referencias.atual().estrutura(
        doc.layout, referencias.versao_do_leiaute(doc))
    achados = []
    info = {"descritor": info_desc.get("descritor"),
            "registros_descritor": info_desc.get("registros", 0),
            "versao": info_desc.get("versao"),
            "fora_da_base": (info_desc.get("versao")
                             if info_desc.get("fora_da_base") else None),
            "sem_base": not estrutura}

# validacao.py:422
    estrutura, info_desc = fonte.estrutura(
        doc.layout, referencias.versao_do_leiaute(doc))

# revisao.py:193
        estrutura, _i = referencias.atual().estrutura(
            doc.layout, referencias.versao_do_leiaute(doc))

# regras_guia.py:140
    est, _info = referencias.atual().estrutura(
        doc.layout, referencias.versao_do_leiaute(doc))

# sped_model.py:2420
            est, _i = referencias.atual().estrutura(
                self.layout, referencias.versao_do_leiaute(self))
```

`ajuda.py`:

```python
def do_campo(layout, reg, n, nome, est=None, guia=None, versao=None):
    ...
    if est is None:
        est, _info = referencias.atual().estrutura(layout, versao)
```

```python
def do_registro(layout, reg, versao=None):
    """Ajuda do registro inteiro: título, objetivo, validação do registro e a
    ajuda de cada campo do leiaute, na versão do arquivo."""
    est, _info = referencias.atual().estrutura(layout, versao)
```

e, dentro de `do_registro`, as chamadas a `do_campo` passam `est=est` (já
passam a estrutura; confira).

`geracao.py` — `_larguras` recebe o fim do período:

```python
def _larguras(memoria, layout, fim):
    """Largura de cada registro: a do SPED que a empresa entregou, limitada
    pela do descritor da versão vigente no fim do período (`fim`,
    DDMMAAAA) — vale a menor, que é o que o PVA aceita (o 0200 do EFD
    Contribuições tem 12 campos lá e 13 no leiaute do programa)."""
    larguras = dict(memoria.get("larguras", {}).get(layout) or {})
    fonte = referencias.atual()
    estrutura, _info = fonte.estrutura(layout,
                                       fonte.versao_vigente(layout, fim))
```

e as três chamadas (linhas 549, 718, 909) passam `fim`:
`_larguras(memoria, "ICMS", fim)` / `_larguras(memoria, "CONTRIB", fim)`
(nas três funções `fim` já está no escopo — confira).

`interface/grade.py` — `from sped_tables.dominio import referencias` no
topo, e:

```python
                dica = self._dicas[(j, nome)] = dica_html(ajuda.do_campo(
                    self.doc.layout, self.tipo, j + 1, nome,
                    versao=referencias.versao_do_leiaute(self.doc)))
```

```python
        self._dlg_ajuda = abrir_janela(self, DialogoAjuda(
            self.doc.layout, self.tipo, campo, self,
            versao=referencias.versao_do_leiaute(self.doc)))
```

`interface/dialogos/ajuda.py` — `def __init__(self, layout, reg,
campo=None, parent=None, versao=None):` e
`r = ajuda.do_registro(layout, reg, versao)`.

`interface/dialogos/verificacao.py:247-255` — o texto de origem:

```python
        if info.get("fora_da_base"):
            texto_origem = (
                "A versão %s do leiaute deste arquivo não está na base de "
                "referência (ela guarda os últimos 5 anos): valeram apenas "
                "as regras embutidas, que cobrem menos que o validador "
                "oficial." % info["fora_da_base"])
        elif info.get("sem_base"):
            texto_origem = (
                "Base de referência indisponível: valeram apenas as regras "
                "embutidas no programa, que cobrem menos que o validador "
                "oficial.")
        else:
            texto_origem = (
                "Verificado com o leiaute da versão %s (%s registros) — o "
                "que o validador declara: tipo, tamanho, obrigatoriedade, "
                "enumerações, tabelas e referências entre registros."
                % (info.get("versao") or "?",
                   info.get("registros_descritor", "?")))
        origem = QLabel(texto_origem)
```

(`grep -rn "sem_pva" sped_tables tests` não pode devolver nada fora de
`infra/pva.py` e `aplicacao/envio_pva.py`, onde é outro estado.)

`referencias_pva.py`:

```python
    def estrutura(self, layout, versao=None):
        # só o descritor mais recente: a versão do arquivo passa a contar
        # com a base de referência (este adaptador sai na mesma série)
```

`tests/fabrica.py:97` e `tests/test_situacoes_contribuinte.py:302`:
`COD_VER="019"` → `COD_VER="020"` (período de 2026 — ver Desvio 7).

`tests/test_guias.py:260`: `def estrutura(self, layout, versao=None):`.

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_versao_leiaute -v` → PASS.
Run: `py -m unittest discover -s tests -t .` → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A sped_tables tests
git commit -m "Porta de referências pede a versão do leiaute do arquivo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: A base de referência — compilar, ler, escolher, importar

**Files:**
- Create: `sped_tables/infra/base_referencia.py`
- Modify: `sped_tables/infra/dados.py:143-166` (`_avisar` → `avisar`)
- Modify: `.gitignore`
- Create: `tests/base_teste.py` (fontes inventadas)
- Test: `tests/test_base_referencia.py`

**Interfaces:**
- Produces (`base_referencia`):
  - constantes `ESQUEMA = 1`, `ARQUIVO = "base_referencia.db"`,
    `LEIAUTES = ("ICMS", "CONTRIB")`, `LIMITE_PACOTE`
  - exceções `BaseInvalida`, `EsquemaNovo(BaseInvalida)`, `BaseRecusada`
  - `chave_da_versao(versao) -> tuple`
  - `arquivo_da_tabela(chave) -> str`
  - `compilar(fontes, destino) -> manifesto`
  - `class Base(caminho)` com `manifesto()`, `versoes(layout) ->
    {cod: (dt_ini, dt_fim, descritor)}`, `estrutura(layout, versao) -> dict
    | None` (nomes do descritor, não alinhada), `tabelas() -> {chave:
    (texto, versao)}`, `guia(layout) -> dict`, `ncm_vigente() -> set |
    None`
  - `impressao_digital(caminho) -> str` (SHA-256 hex)
  - `pasta_fontes()`, `caminho_embutido()`, `caminho_importado()`
  - `compilar_se_preciso() -> bool`
  - `em_uso() -> (Base, "embutida" | "importada") | (None, motivo)`
  - `empacotar(caminho_banco, destino_zip) -> destino_zip`
  - `inspecionar(caminho_zip) -> {"manifesto", "sha256", "confere", "banco"}`
  - `importar(caminho_zip) -> manifesto`
- Produces (`tests/base_teste.py`): `campo(...)`, `registro(campos)`,
  `estrutura_c100(ind_emit)`, `TABELA_CFOP`, `escrever(pasta, **k)`,
  `compilada(pasta, **k) -> caminho_do_banco`
- Produces (`dados`): `avisar(texto)` (era `_avisar`).

- [ ] **Step 1: Write the fixtures and the failing test**

`tests/base_teste.py`:

```python
# -*- coding: utf-8 -*-
"""Fontes de base de referência inventadas (no formato de `base/`), para
testar compilação, importação e o adaptador sem PVA nem a base real."""

import json
import os

from sped_tables.infra import base_referencia

TABELA_CFOP = ("versão=14 CFOP, DESC_CFOP, DT_INI, DT_FIM\n"
               "1102|Compra para comercialização|01012009|\n"
               "5102|Venda de mercadoria|01012009|\n"
               "1999|Revogado|01012009|31122010\n")


def campo(tipo="C", tamanho="", valores=None, obrigatorio="0",
          datasource=None, referencia=None, n=None):
    return {"n": n, "tipo": tipo, "tamanho": tamanho, "decimais": "",
            "obrigatorio": obrigatorio, "valores": valores,
            "datasource": datasource, "referencia": referencia,
            "rotulo": "", "descricao": "", "significados": {}}


def registro(campos, nivel=2):
    return {"nivel": nivel, "ocorrencia": "1:N", "obrigatorio": "0",
            "chave": "", "rotulo": "", "descricao": "", "validadores": [],
            "campos": campos}


def estrutura_c100(ind_emit):
    """Um C100 de três campos, com o IND_EMIT aceitando `ind_emit`."""
    return {"C100": registro({
        "REG": campo(tamanho="[4]", n=1),
        "IND_OPER": campo(tamanho="[1]", valores=["0", "1"], n=2),
        "IND_EMIT": campo(tamanho="[1]", valores=list(ind_emit), n=3)})}


def _json(caminho, objeto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(objeto, fh, ensure_ascii=False, indent=1)


def _texto(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)


def escrever(pasta, versao="2026.10.1", leiautes=None, tabelas=None,
             guias=None, ncm=None, esquema=base_referencia.ESQUEMA):
    """Escreve fontes em `pasta`, no formato de `base/`, e devolve a pasta.

    `leiautes`: `{layout: {cod: (dt_ini, dt_fim, estrutura)}}`;
    `tabelas`: `{chave: (texto, versao)}`. O padrão tem o ICMS/IPI em 019
    (IND_EMIT 0 ou 1) e 020 (só 0) e o Contribuições em 006."""
    if leiautes is None:
        leiautes = {
            "ICMS": {"019": ("01012025", "31122025", estrutura_c100("01")),
                     "020": ("01012026", "", estrutura_c100("0"))},
            "CONTRIB": {"006": ("01012020", "", estrutura_c100("01"))}}
    if tabelas is None:
        tabelas = {"SPEDFISCAL_GLOBAL$CFOP": (TABELA_CFOP, 14)}
    if guias is None:
        guias = {"ICMS": {"guia": "EFD ICMS/IPI", "versao": "9.9",
                          "registros": {}}}
    for layout, versoes in leiautes.items():
        for cod, (ini, fim, est) in versoes.items():
            _json(os.path.join(pasta, "leiaute", layout, cod + ".json"),
                  {"versao": cod, "descritor": "teste/%s/%s" % (layout, cod),
                   "dt_ini": ini, "dt_fim": fim, "estrutura": est})
    for chave, (texto, _v) in tabelas.items():
        _texto(os.path.join(pasta, "tabelas",
                            base_referencia.arquivo_da_tabela(chave)), texto)
    for layout, g in guias.items():
        _json(os.path.join(pasta, "guias", layout + ".json"), g)
    if ncm is not None:
        _texto(os.path.join(pasta, "ncm", "vigente.txt"),
               "\n".join(ncm) + "\n")
    _json(os.path.join(pasta, "manifesto.json"), {
        "esquema": esquema, "versao": versao, "data": "2026-10-15",
        "origem": {"teste": True},
        "leiautes": {l: sorted(v) for l, v in leiautes.items()},
        "tabelas": {c: v for c, (_t, v) in tabelas.items()}})
    return pasta


def compilada(pasta, **k):
    """Fontes em `pasta/fontes-<versao>`, compiladas em
    `pasta/base-<versao>.db`; devolve o caminho do banco."""
    versao = k.get("versao", "2026.10.1")
    fontes = escrever(os.path.join(pasta, "fontes-" + versao), **k)
    destino = os.path.join(pasta, "base-%s.db" % versao)
    base_referencia.compilar(fontes, destino)
    return destino
```

`tests/test_base_referencia.py`:

```python
# -*- coding: utf-8 -*-
"""A base de referência: compilação reproduzível, leitura, a escolha entre
a embutida e a importada, e a importação que recusa o que não serve."""

import hashlib
import json
import os
import shutil
import unittest
import zipfile
from unittest import mock

from sped_tables.infra import base_referencia as B
from sped_tables.infra import dados
from tests import base_teste
from tests.fabrica import PastaTemporaria


class TestCompilacao(unittest.TestCase):

    def test_conteudo(self):
        with PastaTemporaria() as p:
            base = B.Base(base_teste.compilada(p, ncm=["22030000"]))
            self.assertEqual(base.manifesto()["versao"], "2026.10.1")
            self.assertEqual(sorted(base.versoes("ICMS")), ["019", "020"])
            self.assertEqual(base.versoes("ICMS")["020"],
                             ("01012026", "", "teste/ICMS/020"))
            est = base.estrutura("ICMS", "019")
            self.assertEqual(list(est["C100"]["campos"]),
                             ["REG", "IND_OPER", "IND_EMIT"])
            self.assertIsNone(base.estrutura("ICMS", "014"))
            texto, versao = base.tabelas()["SPEDFISCAL_GLOBAL$CFOP"]
            self.assertEqual(versao, 14)
            self.assertEqual(texto.splitlines(),
                             base_teste.TABELA_CFOP.splitlines())
            self.assertEqual(base.guia("ICMS")["versao"], "9.9")
            self.assertEqual(base.guia("CONTRIB"), {})
            self.assertEqual(base.ncm_vigente(), {"22030000"})

    def test_sem_ncm_e_none(self):
        with PastaTemporaria() as p:
            self.assertIsNone(B.Base(base_teste.compilada(p)).ncm_vigente())

    def test_reproduzivel(self):
        with PastaTemporaria() as p:
            fontes = base_teste.escrever(os.path.join(p, "fontes"))
            um, dois = os.path.join(p, "um.db"), os.path.join(p, "dois.db")
            B.compilar(fontes, um)
            B.compilar(fontes, dois)
            self.assertEqual(B.impressao_digital(um),
                             B.impressao_digital(dois))
            with open(um + ".sha256", encoding="ascii") as fh:
                self.assertEqual(fh.read().strip(), B.impressao_digital(um))

    def test_fim_de_linha_nao_muda_o_banco(self):
        """O git troca LF por CRLF no checkout do Windows: a compilação
        normaliza, senão cada máquina daria um banco."""
        with PastaTemporaria() as p:
            fontes = base_teste.escrever(os.path.join(p, "fontes"))
            um = os.path.join(p, "um.db")
            B.compilar(fontes, um)
            tabela = os.path.join(fontes, "tabelas",
                                  B.arquivo_da_tabela("SPEDFISCAL_GLOBAL$CFOP"))
            with open(tabela, encoding="utf-8") as fh:
                texto = fh.read()
            with open(tabela, "w", encoding="utf-8", newline="\r\n") as fh:
                fh.write(texto)
            dois = os.path.join(p, "dois.db")
            B.compilar(fontes, dois)
            self.assertEqual(B.impressao_digital(um),
                             B.impressao_digital(dois))


class TestEmUso(unittest.TestCase):
    """A mais nova entre a embutida e a importada; ilegível é avisada."""

    def setUp(self):
        self.tmp = PastaTemporaria().__enter__()
        self.addCleanup(self.tmp.__exit__, None, None, None)
        self.avisos = []
        dados.ao_avisar(self.avisos.append)
        self.addCleanup(dados.ao_avisar, None)
        self.embutida = os.path.join(self.tmp, "embutida.db")
        self.importada = os.path.join(self.tmp, "importada.db")
        for alvo, valor in (("caminho_embutido", self.embutida),
                            ("caminho_importado", self.importada)):
            p = mock.patch.object(B, alvo, lambda v=valor: v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(B, "compilar_se_preciso", lambda: False)
        p.start()
        self.addCleanup(p.stop)

    def _base(self, destino, versao):
        shutil.copy(base_teste.compilada(self.tmp, versao=versao), destino)

    def test_vale_a_mais_nova(self):
        self._base(self.embutida, "2026.10.1")
        self._base(self.importada, "2026.11.1")
        base, origem = B.em_uso()
        self.assertEqual((base.manifesto()["versao"], origem),
                         ("2026.11.1", "importada"))
        self._base(self.importada, "2026.09.3")
        self.assertEqual(B.em_uso()[1], "embutida")

    def test_importada_ilegivel_vale_a_embutida(self):
        self._base(self.embutida, "2026.10.1")
        for lixo in (b"", b"isto nao e sqlite"):
            with open(self.importada, "wb") as fh:
                fh.write(lixo)
            base, origem = B.em_uso()
            self.assertEqual(origem, "embutida")
        self.assertTrue(self.avisos)
        self.assertTrue(os.path.exists(self.importada))   # nunca apagada

    def test_esquema_novo_e_ilegivel(self):
        with PastaTemporaria() as p:
            caminho = base_teste.compilada(p, esquema=B.ESQUEMA + 1)
            with self.assertRaises(B.EsquemaNovo):
                B.Base(caminho)

    def test_nenhuma_base(self):
        base, motivo = B.em_uso()
        self.assertIsNone(base)
        self.assertIn("nenhuma", motivo)


class TestImportacao(unittest.TestCase):

    def setUp(self):
        self.tmp = PastaTemporaria().__enter__()
        self.addCleanup(self.tmp.__exit__, None, None, None)
        self.embutida = base_teste.compilada(self.tmp, versao="2026.10.1")
        self.importada = os.path.join(self.tmp, "dados", B.ARQUIVO)
        for alvo, valor in (("caminho_embutido", self.embutida),
                            ("caminho_importado", self.importada)):
            p = mock.patch.object(B, alvo, lambda v=valor: v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(B, "compilar_se_preciso", lambda: False)
        p.start()
        self.addCleanup(p.stop)

    def _pacote(self, versao, **k):
        banco = base_teste.compilada(self.tmp, versao=versao, **k)
        return B.empacotar(banco, os.path.join(self.tmp, versao + ".zip"))

    def test_mais_nova_entra(self):
        m = B.importar(self._pacote("2026.11.1"))
        self.assertEqual(m["versao"], "2026.11.1")
        base, origem = B.em_uso()
        self.assertEqual((base.manifesto()["versao"], origem),
                         ("2026.11.1", "importada"))

    def test_igual_ou_mais_antiga_recusada(self):
        for versao in ("2026.10.1", "2026.09.9"):
            with self.assertRaises(B.BaseRecusada) as ctx:
                B.importar(self._pacote(versao))
            self.assertIn("não é mais nova", str(ctx.exception))
        self.assertFalse(os.path.exists(self.importada))

    def _adulterar(self, zip_ok, destino, banco=None, manifesto=None,
                   sem=()):
        with zipfile.ZipFile(zip_ok) as z:
            membros = {n: z.read(n) for n in z.namelist()}
        if banco is not None:
            membros[B.ARQUIVO] = banco
        if manifesto is not None:
            membros["manifesto.json"] = json.dumps(manifesto).encode()
        with zipfile.ZipFile(destino, "w") as z:
            for nome, conteudo in membros.items():
                if nome not in sem:
                    z.writestr(nome, conteudo)
        return destino

    def test_pacote_malformado_recusado_sem_tocar_na_base(self):
        ok = self._pacote("2026.11.1")
        with zipfile.ZipFile(ok) as z:
            manifesto = json.loads(z.read("manifesto.json"))
            banco = z.read(B.ARQUIVO)
        casos = {
            "sem banco": self._adulterar(ok, os.path.join(self.tmp, "a.zip"),
                                         sem=(B.ARQUIVO,)),
            "sem manifesto": self._adulterar(
                ok, os.path.join(self.tmp, "b.zip"), sem=("manifesto.json",)),
            "digital": self._adulterar(ok, os.path.join(self.tmp, "c.zip"),
                                       banco=banco + b"x"),
            "manifesto de outra base": self._adulterar(
                ok, os.path.join(self.tmp, "d.zip"),
                manifesto=dict(manifesto, versao="2027.01.1")),
        }
        lixo = os.path.join(self.tmp, "e.zip")
        with open(lixo, "wb") as fh:
            fh.write(b"nao e zip")
        casos["não é zip"] = lixo
        for nome, caminho in casos.items():
            with self.assertRaises(B.BaseRecusada, msg=nome):
                B.importar(caminho)
        self.assertFalse(os.path.exists(self.importada))
        self.assertEqual(B.em_uso()[1], "embutida")

    def test_membro_grande_demais(self):
        with mock.patch.object(B, "LIMITE_PACOTE", 10):
            with self.assertRaises(B.BaseRecusada) as ctx:
                B.inspecionar(self._pacote("2026.11.1"))
        self.assertIn("grande demais", str(ctx.exception))

    def test_esquema_novo_pede_programa_novo(self):
        with self.assertRaises(B.BaseRecusada) as ctx:
            B.importar(self._pacote("2026.11.1", esquema=B.ESQUEMA + 1))
        self.assertIn("Atualize o programa", str(ctx.exception))

    def test_inspecionar_mostra_a_digital(self):
        pacote = B.inspecionar(self._pacote("2026.11.1"))
        self.assertTrue(pacote["confere"])
        self.assertEqual(pacote["sha256"],
                         hashlib.sha256(pacote["banco"]).hexdigest())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_base_referencia -v`
Expected: FAIL com `ImportError` (`base_referencia` não existe).

- [ ] **Step 3: Implement**

`dados.py`: renomeie `_avisar` para `avisar` (definição e o uso em
`preservar_corrompido`); confira com `grep -rn "_avisar" sped_tables`.

`sped_tables/infra/base_referencia.py`:

```python
# -*- coding: utf-8 -*-
"""A **base de referência**: tudo o que o programa sabe do SPED fora do
próprio código — leiaute de cada versão, tabelas oficiais, guias práticos
e NCM vigente —, montado na compilação e nunca lido do PVA da máquina de
quem usa (ver `docs/adr/0001-base-de-referencia-compilada.md`).

As fontes ficam em `base/`, em texto, versionadas no git e regravadas pelo
consolidador (`py -m consolidador extrair`); `compilar` as transforma num
SQLite que viaja com o executável. Uma base mais nova pode ser importada
sem trocar de programa (`importar`); vale a mais nova entre a embutida e a
importada (`em_uso`).

Fontes (`base/`):

    manifesto.json                    versão, data, origem, leiautes, tabelas
    leiaute/<LEIAUTE>/<COD_VER>.json  {"versao", "descritor", "dt_ini",
                                       "dt_fim", "estrutura"}
    tabelas/<GRUPO@TABELA>.txt        a tabela no formato do PVA, em UTF-8
    guias/<LEIAUTE>.json              o guia prático extraído
    ncm/vigente.txt                   um NCM por linha (opcional)

A `estrutura` guarda os nomes do descritor e **a ordem dos campos é a
posição** no registro: não ordene o JSON do leiaute.
"""

import contextlib
import hashlib
import json
import os
import pathlib
import sqlite3
import zipfile
import zlib

from sped_tables.infra import dados

ESQUEMA = 1
ARQUIVO = "base_referencia.db"
LEIAUTES = ("ICMS", "CONTRIB")
# membro do pacote maior que isto não é base de referência: é engano ou
# bomba de zip
LIMITE_PACOTE = 64 * 1024 * 1024


class BaseInvalida(Exception):
    """O arquivo não é uma base de referência legível."""


class EsquemaNovo(BaseInvalida):
    """A base foi feita para um programa mais novo."""


class BaseRecusada(Exception):
    """O pacote não pode substituir a base em uso; a mensagem diz por quê."""


def chave_da_versao(versao):
    """`"2026.10.1"` -> `(2026, 10, 1)`, para comparar; inválida -> `()`."""
    try:
        return tuple(int(p) for p in str(versao).split("."))
    except ValueError:
        return ()


def arquivo_da_tabela(chave):
    """`GRUPO$TABELA` -> nome do arquivo em `base/tabelas` (o `$` atrapalha
    no terminal)."""
    return chave.replace("$", "@") + ".txt"


def impressao_digital(caminho):
    """SHA-256 do arquivo, em hexadecimal."""
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# --------------------------------------------------------------- compilar
def _texto(caminho):
    # o git pode trocar o fim de linha no checkout: normaliza, para a
    # compilação dar o mesmo banco em qualquer máquina
    with open(caminho, encoding="utf-8") as fh:
        return "\n".join(fh.read().splitlines())


def _json(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


def _comprimir(texto):
    return zlib.compress(texto.encode("utf-8"), 9)


def compilar(fontes, destino):
    """Compila `fontes` (a pasta `base/`) num SQLite em `destino`, com o
    SHA-256 em `destino.sha256`, e devolve o manifesto.

    Mesmas fontes, mesmo banco, byte a byte: nada de data de compilação, e
    tudo é inserido em ordem fixa."""
    manifesto = _json(os.path.join(fontes, "manifesto.json"))
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    temporario = destino + ".compilando"
    if os.path.exists(temporario):
        os.remove(temporario)
    con = sqlite3.connect(temporario)
    try:
        con.executescript("""
            PRAGMA page_size = 4096;
            CREATE TABLE manifesto (conteudo TEXT NOT NULL);
            CREATE TABLE leiaute (layout TEXT, versao TEXT, dt_ini TEXT,
                                  dt_fim TEXT, descritor TEXT,
                                  estrutura BLOB,
                                  PRIMARY KEY (layout, versao));
            CREATE TABLE tabela (chave TEXT PRIMARY KEY, versao INTEGER,
                                 texto BLOB);
            CREATE TABLE guia (layout TEXT PRIMARY KEY, conteudo BLOB);
            CREATE TABLE ncm_vigente (ncm TEXT PRIMARY KEY);
        """)
        con.execute("PRAGMA user_version = %d" % int(manifesto["esquema"]))
        con.execute("INSERT INTO manifesto VALUES (?)", (json.dumps(
            manifesto, ensure_ascii=False, sort_keys=True),))
        for layout in LEIAUTES:
            for versao in sorted(manifesto.get("leiautes", {})
                                 .get(layout, [])):
                d = _json(os.path.join(fontes, "leiaute", layout,
                                       versao + ".json"))
                con.execute(
                    "INSERT INTO leiaute VALUES (?, ?, ?, ?, ?, ?)",
                    (layout, versao, d.get("dt_ini", ""),
                     d.get("dt_fim", ""), d.get("descritor", ""),
                     _comprimir(json.dumps(d["estrutura"],
                                           ensure_ascii=False))))
        for chave in sorted(manifesto.get("tabelas", {})):
            texto = _texto(os.path.join(fontes, "tabelas",
                                        arquivo_da_tabela(chave)))
            con.execute("INSERT INTO tabela VALUES (?, ?, ?)",
                        (chave, int(manifesto["tabelas"][chave]),
                         _comprimir(texto)))
        for layout in LEIAUTES:
            caminho = os.path.join(fontes, "guias", layout + ".json")
            if os.path.exists(caminho):
                con.execute("INSERT INTO guia VALUES (?, ?)",
                            (layout, _comprimir(_texto(caminho))))
        caminho = os.path.join(fontes, "ncm", "vigente.txt")
        if os.path.exists(caminho):
            ncms = sorted({l.strip() for l in _texto(caminho).splitlines()
                           if l.strip()})
            con.executemany("INSERT INTO ncm_vigente VALUES (?)",
                            [(n,) for n in ncms])
        con.commit()
        con.execute("VACUUM")
    finally:
        con.close()
    os.replace(temporario, destino)
    with open(destino + ".sha256", "w", encoding="ascii",
              newline="\n") as fh:
        fh.write(impressao_digital(destino) + "\n")
    return manifesto


# ------------------------------------------------------------------- ler
class Base:
    """Um banco compilado. Cada consulta abre e fecha a conexão (o `sqlite3`
    não divide conexão entre threads) e o que é lido fica em memória: a base
    não muda enquanto o programa roda."""

    def __init__(self, caminho):
        self.caminho = caminho
        self._cache = {}
        if not os.path.isfile(caminho):
            raise BaseInvalida("%s não existe" % caminho)
        try:
            with self._conectar() as con:
                esquema = con.execute("PRAGMA user_version").fetchone()[0]
                (texto,) = con.execute(
                    "SELECT conteudo FROM manifesto").fetchone()
            manifesto = json.loads(texto)
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise BaseInvalida(str(exc))
        if esquema > ESQUEMA:
            raise EsquemaNovo("esquema %d; este programa entende até o %d"
                              % (esquema, ESQUEMA))
        if not chave_da_versao(manifesto.get("versao")):
            raise BaseInvalida("manifesto sem versão")
        self._manifesto = manifesto

    def _conectar(self):
        uri = pathlib.Path(self.caminho).resolve().as_uri() + "?mode=ro"
        return contextlib.closing(sqlite3.connect(uri, uri=True))

    def _uma_vez(self, chave, ler):
        if chave not in self._cache:
            with self._conectar() as con:
                self._cache[chave] = ler(con)
        return self._cache[chave]

    def manifesto(self):
        return self._manifesto

    def versoes(self, layout):
        """`{COD_VER: (dt_ini, dt_fim, descritor)}` das versões guardadas."""
        return self._uma_vez(("versoes", layout), lambda con: {
            v: (i, f, d) for v, i, f, d in con.execute(
                "SELECT versao, dt_ini, dt_fim, descritor FROM leiaute "
                "WHERE layout = ? ORDER BY versao", (layout,))})

    def estrutura(self, layout, versao):
        """Estrutura da versão com os nomes do descritor, ou None."""
        def ler(con):
            linha = con.execute(
                "SELECT estrutura FROM leiaute WHERE layout = ? AND "
                "versao = ?", (layout, versao)).fetchone()
            return (json.loads(zlib.decompress(linha[0]).decode("utf-8"))
                    if linha else None)
        return self._uma_vez(("estrutura", layout, versao), ler)

    def tabelas(self):
        """`{chave: (texto, versao)}` — o mesmo formato de
        `tabelas_oficiais.tabelas_da_pasta`."""
        return self._uma_vez("tabelas", lambda con: {
            c: (zlib.decompress(t).decode("utf-8"), v)
            for c, v, t in con.execute(
                "SELECT chave, versao, texto FROM tabela")})

    def guia(self, layout):
        def ler(con):
            linha = con.execute("SELECT conteudo FROM guia WHERE layout = ?",
                                (layout,)).fetchone()
            return (json.loads(zlib.decompress(linha[0]).decode("utf-8"))
                    if linha else {})
        return self._uma_vez(("guia", layout), ler)

    def ncm_vigente(self):
        """Conjunto de NCM vigentes, ou None quando a base não traz."""
        return self._uma_vez("ncm", lambda con: {
            n for (n,) in con.execute("SELECT ncm FROM ncm_vigente")}
            or None)


# ------------------------------------------------------------ qual vale
def pasta_fontes():
    """`base/` do repositório — só existe rodando do código-fonte."""
    return dados.recurso("base")


def caminho_embutido():
    return dados.recurso(os.path.join("recursos", ARQUIVO))


def caminho_importado():
    return dados.caminho(ARQUIVO)


def _mais_recente(pasta):
    m = 0.0
    for raiz, _d, nomes in os.walk(pasta):
        for n in nomes:
            m = max(m, os.path.getmtime(os.path.join(raiz, n)))
    return m


def compilar_se_preciso():
    """Rodando do código-fonte, recompila a base embutida quando ela falta
    ou quando `base/` mudou depois dela. Empacotado, não há fontes."""
    fontes, destino = pasta_fontes(), caminho_embutido()
    if dados.empacotado() or not os.path.isfile(
            os.path.join(fontes, "manifesto.json")):
        return False
    if (os.path.exists(destino)
            and os.path.getmtime(destino) >= _mais_recente(fontes)):
        return False
    compilar(fontes, destino)
    return True


def em_uso():
    """`(Base, "embutida" | "importada")` da base que vale — a mais nova
    entre as duas —, ou `(None, motivo)` quando nenhuma é legível.

    Importada ilegível é avisada e ignorada; nunca apagada."""
    try:
        compilar_se_preciso()
    except Exception as exc:                               # noqa: BLE001
        dados.avisar("Não foi possível compilar a base de referência de "
                     "base/ (%s); segue a última compilada." % exc)
    candidatas = []
    for origem, caminho in (("embutida", caminho_embutido()),
                            ("importada", caminho_importado())):
        if not os.path.exists(caminho):
            continue
        try:
            candidatas.append((Base(caminho), origem))
        except BaseInvalida as exc:
            dados.avisar("A base de referência %s está ilegível (%s) e foi "
                         "ignorada." % (origem, exc))
    if not candidatas:
        return None, "nenhuma base de referência legível"
    return max(candidatas,
               key=lambda c: chave_da_versao(c[0].manifesto()["versao"]))


# ------------------------------------------------------------- importar
def empacotar(caminho_banco, destino_zip):
    """O pacote que se distribui: o banco e o manifesto com a impressão
    digital do banco."""
    base = Base(caminho_banco)
    with open(caminho_banco, "rb") as fh:
        banco = fh.read()
    manifesto = dict(base.manifesto(),
                     sha256=hashlib.sha256(banco).hexdigest())
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(ARQUIVO, banco)
        z.writestr("manifesto.json", json.dumps(
            manifesto, ensure_ascii=False, indent=1, sort_keys=True))
    return destino_zip


def inspecionar(caminho_zip):
    """Lê o pacote sem instalar nada: `{"manifesto", "sha256", "confere",
    "banco"}`. Pacote que não serve levanta `BaseRecusada`."""
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            nomes = set(z.namelist())
            if ARQUIVO not in nomes or "manifesto.json" not in nomes:
                raise BaseRecusada("O pacote não tem o banco e o manifesto "
                                   "da base de referência.")
            if (z.getinfo(ARQUIVO).file_size > LIMITE_PACOTE
                    or z.getinfo("manifesto.json").file_size > 1 << 20):
                raise BaseRecusada("O pacote é grande demais para ser uma "
                                   "base de referência.")
            banco = z.read(ARQUIVO)
            manifesto = json.loads(z.read("manifesto.json").decode("utf-8"))
    except (zipfile.BadZipFile, OSError, ValueError, KeyError) as exc:
        raise BaseRecusada("O arquivo não é um pacote de base de referência "
                           "legível (%s)." % exc)
    if not isinstance(manifesto, dict):
        raise BaseRecusada("O manifesto do pacote está ilegível.")
    digital = hashlib.sha256(banco).hexdigest()
    return {"manifesto": manifesto, "sha256": digital,
            "confere": digital == manifesto.get("sha256"), "banco": banco}


def importar(caminho_zip):
    """Instala a base do pacote na pasta de dados, se ela for íntegra,
    legível por este programa e mais nova que a em uso. Devolve o
    manifesto; o que não serve levanta `BaseRecusada` sem tocar na base em
    uso."""
    pacote = inspecionar(caminho_zip)
    if not pacote["confere"]:
        raise BaseRecusada(
            "A impressão digital do banco (%s…) não confere com a do "
            "manifesto: o arquivo foi alterado ou está corrompido."
            % pacote["sha256"][:16])
    destino = caminho_importado()
    temporario = destino + ".importando"
    dados.gravar_atomico(temporario, pacote["banco"])
    try:
        try:
            nova = Base(temporario)
        except EsquemaNovo as exc:
            raise BaseRecusada("Esta base foi feita para um programa mais "
                               "novo (%s). Atualize o programa." % exc)
        except BaseInvalida as exc:
            raise BaseRecusada("O banco do pacote está ilegível (%s)." % exc)
        versao = nova.manifesto()["versao"]
        if versao != pacote["manifesto"].get("versao"):
            raise BaseRecusada("O manifesto do pacote não corresponde ao "
                               "banco.")
        atual, _origem = em_uso()
        if atual is not None and (chave_da_versao(versao)
                                  <= chave_da_versao(
                                      atual.manifesto()["versao"])):
            raise BaseRecusada("A base %s não é mais nova que a em uso (%s)."
                               % (versao, atual.manifesto()["versao"]))
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
    return nova.manifesto()
```

`.gitignore` — acrescente no fim:

```
# Base de referência compilada de base/ (o programa recompila sozinho)
recursos/base_referencia.db
recursos/base_referencia.db.sha256
*.compilando
*.importando
```

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_base_referencia -v` → PASS.
Run: `py -m unittest discover -s tests -t .` → PASS.

- [ ] **Step 5: Commit**

```bash
git add .gitignore sped_tables/infra/base_referencia.py sped_tables/infra/dados.py tests/base_teste.py tests/test_base_referencia.py
git commit -m "Base de referência: compilação reproduzível, leitura e importação" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: O adaptador da porta sobre a base

**Files:**
- Create: `sped_tables/infra/referencias_base.py`
- Test: `tests/test_referencias_base.py`

**Interfaces:**
- Consumes: `base_referencia.Base` (ou qualquer origem com `manifesto`,
  `versoes`, `estrutura`, `tabelas`, `guia`, `ncm_vigente`);
  `tabelas_oficiais`, `tabelas_ncm` (Tarefa 2); a porta da Tarefa 3.
- Produces: `ReferenciasBase(origem, nome="base de referência")` —
  implementa todos os métodos de `Referencias`, mais `manifesto()`.
  `estrutura(layout, None)` usa a maior versão guardada; `info` traz
  `descritor`, `registros`, `versao`, `base`.

- [ ] **Step 1: Write the failing test** — `tests/test_referencias_base.py`:

```python
# -*- coding: utf-8 -*-
"""O adaptador da porta lendo a base de referência: versão do arquivo,
fora da base, vigência e tabelas."""

import unittest

from sped_tables.dominio import referencias, validacao
from sped_tables.dominio.sped_model import SpedDocument
from sped_tables.infra import base_referencia
from sped_tables.infra.referencias_base import ReferenciasBase
from tests import base_teste
from tests.fabrica import PastaTemporaria, icms_basico


class TestReferenciasBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = PastaTemporaria()
        pasta = cls._tmp.__enter__()
        cls.fonte = ReferenciasBase(base_referencia.Base(
            base_teste.compilada(pasta)))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.__exit__(None, None, None)

    def setUp(self):
        self._antes = referencias.definir(self.fonte)

    def tearDown(self):
        referencias.definir(self._antes)

    def test_estrutura_por_versao(self):
        est, info = self.fonte.estrutura("ICMS", "019")
        self.assertEqual(est["C100"]["campos"]["IND_EMIT"]["valores"],
                         ["0", "1"])
        self.assertEqual(info["versao"], "019")
        self.assertEqual(info["descritor"], "teste/ICMS/019")
        self.assertEqual(info["base"], "2026.10.1")

    def test_sem_versao_vale_a_mais_recente(self):
        _est, info = self.fonte.estrutura("ICMS")
        self.assertEqual(info["versao"], "020")

    def test_fora_da_base(self):
        est, info = self.fonte.estrutura("ICMS", "014")
        self.assertEqual(est, {})
        self.assertTrue(info["fora_da_base"])
        self.assertIn("014", info["erro"])

    def test_versao_vigente(self):
        self.assertEqual(self.fonte.versao_vigente("ICMS", "31082026"), "020")
        self.assertEqual(self.fonte.versao_vigente("ICMS", "31082025"), "019")
        self.assertIsNone(self.fonte.versao_vigente("ICMS", "31082020"))

    def test_tabelas_pela_base(self):
        est = {"C170": {"campos": {"CFOP": {"datasource": "CFOP"}}}}
        dom, _f = self.fonte.dominios_por_datasource(est, "ICMS", "MG",
                                                     "31082026")
        self.assertEqual(dom[("C170", "CFOP")]["codigos"], {"1102", "5102"})
        self.assertIsNone(self.fonte.classificador_ncm())
        self.assertEqual(self.fonte.guia("ICMS")["versao"], "9.9")

    def _ind_emit(self, cod_ver):
        """Ocorrências de domínio no IND_EMIT de um C100 com IND_EMIT=1."""
        m = icms_basico()
        m.alterar("0000", COD_VER=cod_ver)
        m.alterar("C100", IND_EMIT="1")
        with PastaTemporaria() as p:
            doc = SpedDocument.carregar(m.gravar(p))
        dominios, _info = validacao.dominios_do_documento(doc)
        return [o for o in validacao.validar(doc, dominios_pva=dominios)
                if o.reg == "C100" and o.campo == "IND_EMIT"]

    def test_arquivo_conferido_pela_propria_versao(self):
        """Na 020 inventada o IND_EMIT só aceita 0; na 019, 0 ou 1. O
        arquivo que declara 019 — mesmo com o período de 2026 — é conferido
        pela 019 e não é acusado."""
        self.assertEqual(self._ind_emit("019"), [])
        self.assertTrue(self._ind_emit("020"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_referencias_base -v`
Expected: FAIL com `ImportError` (`referencias_base` não existe).

- [ ] **Step 3: Implement** — `sped_tables/infra/referencias_base.py`:

```python
# -*- coding: utf-8 -*-
"""Adaptador: a porta `dominio.referencias` lida da **base de referência**.

Nada aqui lê a instalação do PVA. A origem é qualquer objeto com a
interface de `base_referencia.Base` (`manifesto`, `versoes`, `estrutura`,
`tabelas`, `guia`, `ncm_vigente`): o banco compilado, no programa; a
instalação do PVA, no consolidador — que é como se confere que a base
responde igual ao PVA de onde saiu.
"""

from sped_tables.dominio import referencias
from sped_tables.dominio.referencias import Referencias
from sped_tables.infra import tabelas_ncm, tabelas_oficiais


class ReferenciasBase(Referencias):

    def __init__(self, origem, nome="base de referência"):
        self.origem = origem
        self.nome = nome
        # a base não muda durante a sessão: o que custa montar fica aqui
        self._alinhadas = {}       # (leiaute, versão) -> estrutura alinhada
        self._ncms_natureza = {}   # natureza da receita -> NCM
        self._tab_natureza = {}    # CST -> tabela da natureza da receita
        self._clf = None
        self._clf_lido = False

    def manifesto(self):
        return self.origem.manifesto()

    def descricao(self):
        m = self.manifesto()
        return "base de referência %s, de %s" % (m.get("versao", "?"),
                                                  m.get("data", "?"))

    def estrutura(self, layout, versao=None):
        versoes = self.origem.versoes(layout)
        if not versoes:
            return {}, {"descritor": None, "erro": "a base de referência "
                        "não tem o leiaute %s" % layout}
        if versao is None:
            versao = max(versoes, key=int)
        if versao not in versoes:
            return {}, {"descritor": None, "versao": versao,
                        "fora_da_base": True,
                        "erro": "a versão %s do leiaute não está na base de "
                                "referência %s"
                                % (versao, self.manifesto().get("versao"))}
        chave = (layout, versao)
        if chave not in self._alinhadas:
            self._alinhadas[chave] = referencias.alinhar_ao_leiaute(
                self.origem.estrutura(layout, versao), layout)
        est = self._alinhadas[chave]
        return est, {"descritor": versoes[versao][2], "registros": len(est),
                     "versao": versao,
                     "base": self.manifesto().get("versao")}

    def versao_vigente(self, layout, data):
        alvo = tabelas_oficiais.chave_data(data)
        if not alvo:
            return None
        for versao, (ini, fim, _d) in sorted(
                self.origem.versoes(layout).items()):
            if ((tabelas_oficiais.chave_data(ini) or "00000000") <= alvo
                    <= (tabelas_oficiais.chave_data(fim) or "99999999")):
                return versao
        return None

    def dominios_por_datasource(self, estrutura, layout, uf=None,
                                data_ref=None):
        return tabelas_oficiais.dominios_por_datasource(
            self.origem.tabelas(), estrutura, layout, uf=uf,
            data_ref=data_ref)

    def rotulo(self, campo):
        return tabelas_oficiais.ROTULOS.get(campo, campo)

    def naturezas_cfop_credito(self, data_ref=None):
        return tabelas_oficiais.naturezas_cfop_credito(
            self.origem.tabelas(), data_ref=data_ref)

    def cfops_com_credito(self, data_ref=None):
        return tabelas_oficiais.cfops_com_credito(self.origem.tabelas(),
                                                  data_ref=data_ref)

    def prazo_entrega(self, mes_ano):
        return tabelas_oficiais.prazo_entrega(self.origem.tabelas(), mes_ano)

    def naturezas_receita(self, cst, data_ref=None):
        return tabelas_oficiais.naturezas_receita(
            self.origem.tabelas(), cst, data_ref=data_ref)

    def ncms_da_natureza(self, codigo):
        # cada consulta lê até 7 tabelas, e a rotina pergunta por ocorrência
        if codigo not in self._ncms_natureza:
            self._ncms_natureza[codigo] = tabelas_oficiais.ncms_da_natureza(
                self.origem.tabelas(), codigo)
        return self._ncms_natureza[codigo]

    def tabela_natureza_receita(self, cst):
        if cst not in self._tab_natureza:
            self._tab_natureza[cst] = (
                tabelas_oficiais.tabela_natureza_receita(
                    self.origem.tabelas(), cst))
        return self._tab_natureza[cst]

    def classificador_ncm(self):
        if not self._clf_lido:
            self._clf_lido = True
            self._clf = tabelas_ncm.classificador(
                self.origem.tabelas(), self.origem.ncm_vigente())
        return self._clf

    def codigos_receita_icms(self, uf, data_ref=None):
        return tabelas_oficiais.codigos_receita_icms(
            self.origem.tabelas(), uf, data_ref=data_ref)

    def guia(self, layout):
        return self.origem.guia(layout)
```

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_referencias_base -v` → PASS.
Run: `py -m unittest discover -s tests -t .` → PASS.

- [ ] **Step 5: Commit**

```bash
git add sped_tables/infra/referencias_base.py tests/test_referencias_base.py
git commit -m "Adaptador da porta de referências sobre a base" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: O consolidador extrai `base/` dos PVAs

**Files:**
- Create: `consolidador/__init__.py`, `consolidador/__main__.py`,
  `consolidador/descritor.py`, `consolidador/instalacao.py`,
  `consolidador/extracao.py`
- Move: `ferramentas/extrair_guias.py` → `consolidador/guias.py`
- Move: `recursos/guia_icms.json` → `base/guias/ICMS.json`;
  `recursos/guia_contrib.json` → `base/guias/CONTRIB.json`
- Modify: `sped_tables/infra/guias.py:19-23` (aponta para `base/guias`
  até sair na Tarefa 7), `tests/test_guias.py:19-20`, `SPED Tables.spec:68-69`
- Create (gerado): `base/manifesto.json`, `base/leiaute/**`, `base/tabelas/**`
- Test: `tests/test_consolidador.py`, `tests/test_equivalencia_base.py`

**Interfaces:**
- Consumes: `tabelas_oficiais.tabelas_da_pasta`, `chave_data` (Tarefa 2);
  `base_referencia` (Tarefa 4); `ReferenciasBase` (Tarefa 5). O parser do
  descritor é **copiado** de `sped_tables/infra/descritor_pva.py` para
  `consolidador/descritor.py`; o original é apagado na Tarefa 7.
- Produces (`consolidador.descritor`): `ler(jar, caminho) -> estrutura`,
  `mais_recente(jar) -> caminho`, `por_versao(jar, layout, tabela_versoes)
  -> {COD_VER: caminho}`.
- Produces (`consolidador.instalacao`): `SUBPASTAS`, `ConsolidadorErro`,
  `jar_descritor(raiz, layout)`, `pasta_tabelas(raiz, layout)`,
  `tabela_de_versoes(tabs, layout) -> {cod: (dt_ini, dt_fim)}`,
  `InstalacaoPVA(raiz=None, data=None, anos=5, fontes=None)` com a
  interface de `Base` e `avisos: list[str]`.
- Produces (`consolidador.extracao`): `extrair(instalacao, destino,
  versao=None, ncm_xlsx=None) -> manifesto`, `proxima_versao(anterior,
  data) -> str`, `ler_ncm_vigente(xlsx) -> set`.
- Produces (`consolidador.guias`): `extrair(texto, layout)` (inalterada),
  `texto_do_pdf(pdf)`, `gravar(layout, pdf, fontes) -> caminho`.
- CLI: `py -m consolidador extrair|guia|compilar|publicar`.

- [ ] **Step 1: Write the failing test** — `tests/test_consolidador.py`:

```python
# -*- coding: utf-8 -*-
"""O consolidador extrai `base/` de uma instalação do PVA — aqui, uma
instalação inventada, com descritores e tabelas mínimos."""

import datetime
import json
import os
import unittest
import zipfile

from consolidador import descritor, extracao, instalacao as I
from sped_tables.infra import base_referencia
from tests.fabrica import PastaTemporaria

XML = """<descritor-escrituracao>
<registro id="C100" nivel="2" ocorrencia="1:N" chave="IND_OPER">
  <campo n="1" id="REG" tipo="C" tamanho="[4]"/>
  <!-- <campo n="2" id="EXCLUIDO" tipo="C"/> -->
  <campo n="2" id="IND_OPER" tipo="C" tamanho="[1]">
    <valores-validos valores="0=Entrada;1=Saída"/>
  </campo>
  <validador id="REGRA_TESTE"/>
</registro>
</descritor-escrituracao>"""

VERSOES_ICMS = ("versão=21 COD_LEI, VERSAO, DT_INI, DT_FIM\n"
                "014|1.13|01012020|31122020\n"
                "015|1.14|01012021|31122021\n"
                "016|1.15|01012022|31122022\n"
                "021|1.20|01012027|\n")
VERSOES_CONTRIB = ("versão=6 COD_LEI, VERSAO, DT_INI, DT_FIM\n"
                   "005|101|01012019|31122019\n"
                   "006|101|01012020|\n")


def _pva_falso(raiz, sem_ato=()):
    """Instalação com descritores do ICMS nos atos 014 a 016 (o 015 em
    duas estruturas) e dois do Contribuições."""
    for layout in ("ICMS", "CONTRIB"):
        os.makedirs(I.pasta_tabelas(raiz, layout))
        jar = I.jar_descritor(raiz, layout)
        os.makedirs(os.path.dirname(jar))
        with zipfile.ZipFile(jar, "w") as z:
            if layout == "ICMS":
                for ato, est, v in (("014", 1, 1), ("015", 1, 2),
                                    ("015", 2, 1), ("016", 1, 1)):
                    if ato not in sem_ato:
                        z.writestr("descritor/escrituracao/ato%s/estrutura%03d"
                                   "/v%d/descritor.xml" % (ato, est, v), XML)
            else:
                for est in ("6001", "7007"):
                    z.writestr("descritor/escrituracao/estrutura%s/v1/"
                               "descritor.xml" % est, XML)
    tabelas = {
        ("ICMS", "SPEDFISCAL_GLOBAL$VERSOES_LEIAUTE$21$11"): VERSOES_ICMS,
        ("ICMS", "SPEDFISCAL_GLOBAL$CFOP$14$1"): "versão=14 CFOP\n1102|x||\n",
        ("CONTRIB", "SPEDPISCOFINS_GLOBAL$SPEDPISCOFINS_VERSOES_LEIAUTE"
                    "$6$132"): VERSOES_CONTRIB,
        ("CONTRIB", "metadados"): "\x00",
    }
    for (layout, nome), texto in tabelas.items():
        with open(os.path.join(I.pasta_tabelas(raiz, layout), nome), "w",
                  encoding="latin-1") as fh:
            fh.write(texto)
    return raiz


DATA = datetime.date(2026, 10, 15)


class TestDescritor(unittest.TestCase):

    def test_campo_comentado_nao_existe_e_validador_registrado(self):
        with PastaTemporaria() as p:
            jar = I.jar_descritor(_pva_falso(p), "ICMS")
            est = descritor.ler(jar, descritor.mais_recente(jar))
        self.assertEqual(list(est["C100"]["campos"]), ["REG", "IND_OPER"])
        self.assertEqual(est["C100"]["validadores"], ["REGRA_TESTE"])

    def test_por_versao(self):
        with PastaTemporaria() as p:
            raiz = _pva_falso(p)
            icms = descritor.por_versao(
                I.jar_descritor(raiz, "ICMS"), "ICMS",
                I.tabela_de_versoes({}, "ICMS"))
            contrib = descritor.por_versao(
                I.jar_descritor(raiz, "CONTRIB"), "CONTRIB",
                {"005": ("01012019", "31122019"), "006": ("01012020", "")})
        self.assertEqual(sorted(icms), ["014", "015", "016"])
        self.assertIn("ato015/estrutura002/v1", icms["015"])
        self.assertEqual(list(contrib), ["006"])
        self.assertIn("estrutura7007", contrib["006"])


class TestInstalacao(unittest.TestCase):

    def test_retencao_de_cinco_anos(self):
        with PastaTemporaria() as p:
            pva = I.InstalacaoPVA(_pva_falso(p), data=DATA, fontes=p)
            self.assertEqual(sorted(pva.versoes("ICMS")), ["015", "016"])
            self.assertEqual(sorted(pva.versoes("CONTRIB")), ["006"])
            # 021 é futura e não tem descritor: fica de fora, com aviso
            self.assertTrue(any("021" in a for a in pva.avisos))
            self.assertNotIn("metadados", pva.tabelas())

    def test_versao_vigente_sem_descritor_recusa(self):
        with PastaTemporaria() as p:
            pva = I.InstalacaoPVA(_pva_falso(p, sem_ato=("016",)),
                                  data=DATA, fontes=p)
            with self.assertRaises(I.ConsolidadorErro):
                pva.versoes("ICMS")

    def test_sem_pva_recusa(self):
        with PastaTemporaria() as p:
            with self.assertRaises(I.ConsolidadorErro) as ctx:
                I.InstalacaoPVA(p, data=DATA, fontes=p)
            self.assertIn("faltam", str(ctx.exception))


class TestExtracao(unittest.TestCase):

    def test_extrair_e_compilar(self):
        with PastaTemporaria() as p:
            destino = os.path.join(p, "base")
            pva = I.InstalacaoPVA(_pva_falso(os.path.join(p, "pva")),
                                  data=DATA, fontes=destino)
            m = extracao.extrair(pva, destino)
            self.assertEqual(m["versao"], "2026.10.1")
            self.assertEqual(m["leiautes"], {"ICMS": ["015", "016"],
                                             "CONTRIB": ["006"]})
            self.assertIn("SPEDFISCAL_GLOBAL$CFOP", m["tabelas"])
            with open(os.path.join(destino, "leiaute", "ICMS", "016.json"),
                      encoding="utf-8") as fh:
                d = json.load(fh)
            self.assertEqual(d["dt_ini"], "01012022")
            self.assertEqual(list(d["estrutura"]["C100"]["campos"]),
                             ["REG", "IND_OPER"])
            banco = os.path.join(p, "b.db")
            base_referencia.compilar(destino, banco)
            base = base_referencia.Base(banco)
            self.assertEqual(base.estrutura("ICMS", "016"),
                             pva.estrutura("ICMS", "016"))
            # segunda extração no mesmo mês: n + 1
            self.assertEqual(extracao.extrair(pva, destino)["versao"],
                             "2026.10.2")

    def test_proxima_versao(self):
        self.assertEqual(extracao.proxima_versao(None, DATA), "2026.10.1")
        self.assertEqual(extracao.proxima_versao("2026.10.4", DATA),
                         "2026.10.5")
        self.assertEqual(extracao.proxima_versao("2026.09.4", DATA),
                         "2026.10.1")


if __name__ == "__main__":
    unittest.main()
```

`tests/test_equivalencia_base.py` (roda só onde há PVA):

```python
# -*- coding: utf-8 -*-
"""O teste central da migração: a base compilada de `base/` responde igual
ao PVA instalado nesta máquina — dado a dado e pela porta.

Falhou depois de o PVA ser atualizado? A base ficou para trás: rode
`py -m consolidador extrair`, revise o `git diff base/` e faça o commit."""

import datetime
import json
import os
import unittest

from consolidador.instalacao import InstalacaoPVA
from sped_tables.infra import base_referencia
from sped_tables.infra.referencias_base import ReferenciasBase
from sped_tables.infra import config

# até a troca (Tarefa 7) a suíte ainda enxerga o PVA pelo config
PVA = config.raiz_pva() if any(
    os.path.isdir(config.pasta_pva(l)) for l in config.PVAS) else None


@unittest.skipUnless(PVA, "PVA não instalado nesta máquina")
class TestBaseReproduzOPva(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fontes = base_referencia.pasta_fontes()
        with open(os.path.join(fontes, "manifesto.json"),
                  encoding="utf-8") as fh:
            data = datetime.date.fromisoformat(json.load(fh)["data"])
        cls.pva = InstalacaoPVA(PVA, data=data, fontes=fontes)
        cls.base, _origem = base_referencia.em_uso()

    def test_mesmas_versoes(self):
        for layout in base_referencia.LEIAUTES:
            self.assertEqual(self.pva.versoes(layout),
                             self.base.versoes(layout), layout)

    def test_mesma_estrutura(self):
        for layout in base_referencia.LEIAUTES:
            for versao in self.pva.versoes(layout):
                self.assertEqual(self.pva.estrutura(layout, versao),
                                 self.base.estrutura(layout, versao),
                                 "%s %s" % (layout, versao))

    def test_mesmas_tabelas(self):
        a, b = self.pva.tabelas(), self.base.tabelas()
        self.assertEqual(sorted(a), sorted(b))
        for chave in a:
            self.assertEqual(a[chave][1], b[chave][1], chave)
            self.assertEqual(a[chave][0].splitlines(),
                             b[chave][0].splitlines(), chave)

    def test_mesmas_respostas_da_porta(self):
        antigo = _referencia_pva()
        nova = ReferenciasBase(self.base)
        for layout in base_referencia.LEIAUTES:
            ea, _i = antigo.estrutura(layout)
            eb, _i = nova.estrutura(layout)
            self.assertEqual(ea, eb, layout)
            for uf in ("MG", "SP"):
                self.assertEqual(
                    antigo.dominios_por_datasource(ea, layout, uf,
                                                   "31082026"),
                    nova.dominios_por_datasource(eb, layout, uf, "31082026"),
                    "%s %s" % (layout, uf))
        self.assertEqual(antigo.naturezas_cfop_credito("31082026"),
                         nova.naturezas_cfop_credito("31082026"))
        self.assertEqual(antigo.cfops_com_credito("31082026"),
                         nova.cfops_com_credito("31082026"))
        self.assertEqual(antigo.prazo_entrega("082026"),
                         nova.prazo_entrega("082026"))
        for cst in ("04", "05", "06", "07", "08", "09"):
            self.assertEqual(antigo.naturezas_receita(cst, "31082026"),
                             nova.naturezas_receita(cst, "31082026"), cst)
            self.assertEqual(antigo.tabela_natureza_receita(cst),
                             nova.tabela_natureza_receita(cst), cst)
        self.assertEqual(antigo.codigos_receita_icms("MG", "31082026"),
                         nova.codigos_receita_icms("MG", "31082026"))
        for layout in base_referencia.LEIAUTES:
            self.assertEqual(antigo.guia(layout), nova.guia(layout))


def _referencia_pva():
    """O lado "PVA" da comparação pela porta: o leitor antigo enquanto ele
    existe (troca na Tarefa 7)."""
    from sped_tables.infra.referencias_pva import ReferenciasPVA
    return ReferenciasPVA()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_consolidador -v`
Expected: FAIL com `ModuleNotFoundError: consolidador`.

- [ ] **Step 3: Implement**

```bash
mkdir -p consolidador base/guias
git mv ferramentas/extrair_guias.py consolidador/guias.py
git mv recursos/guia_icms.json base/guias/ICMS.json
git mv recursos/guia_contrib.json base/guias/CONTRIB.json
```

`consolidador/__init__.py`:

```python
# -*- coding: utf-8 -*-
"""O **consolidador**: lê o que os PVAs (e, adiante, as notas técnicas)
publicam e regrava as fontes da base de referência em `base/`.

Roda na máquina de quem compila o programa, nunca na de quem o usa. Pode
importar o `sped_tables`; o `sped_tables` nunca o importa
(`tests/test_arquitetura.py`). Ver `CONTEXT.md` e
`docs/adr/0001-base-de-referencia-compilada.md`.
"""
```

`consolidador/descritor.py` — o parser do `sped_tables/infra/descritor_pva.py`
(que ainda fica onde está até a Tarefa 7): copie a docstring do topo,
`RE_REGISTRO`, `RE_CAMPO`, `RE_ATTR`, `RE_VALORES`, `RE_COMENTARIO` e
`_attrs`, e escreva:

```python
import html
import re
import zipfile

# (RE_* e _attrs como em sped_tables/infra/descritor_pva.py)


def _caminhos(z):
    return [n for n in z.namelist()
            if n.endswith("descritor.xml") and "escrituracao" in n]


def _numeros(caminho):
    return [int(x) for x in re.findall(r"(\d+)", caminho)]


def mais_recente(jar):
    """Caminho interno do descritor de maior versão: maior (ato/estrutura,
    versão) lido do próprio caminho; no empate, o arquivo maior."""
    with zipfile.ZipFile(jar) as z:
        alvos = _caminhos(z)
        if not alvos:
            return None
        return max(alvos, key=lambda n: (_numeros(n), z.getinfo(n).file_size))


def por_versao(jar, layout, tabela_versoes):
    """`{COD_VER: caminho interno}`.

    No ICMS/IPI a pasta diz a versão: `ato020` é o COD_VER 020; dentro do
    ato vale a maior (estrutura, versão). No Contribuições as pastas
    (`estrutura7007`…) não dizem a versão: só a versão **em aberto** da
    tabela (DT_FIM vazio) é ligada, ao descritor mais recente."""
    with zipfile.ZipFile(jar) as z:
        alvos = _caminhos(z)
        tam = {n: z.getinfo(n).file_size for n in alvos}
    if not alvos:
        return {}
    if layout == "CONTRIB":
        abertas = [c for c, (_i, fim) in tabela_versoes.items() if not fim]
        if len(abertas) != 1:
            return {}
        return {abertas[0]: max(alvos, key=lambda n: (_numeros(n), tam[n]))}
    out = {}
    for n in alvos:
        m = re.search(r"/ato(\d+)/", n)
        if not m:
            continue
        cod = "%03d" % int(m.group(1))
        if cod not in out or ((_numeros(n), tam[n])
                              > (_numeros(out[cod]), tam[out[cod]])):
            out[cod] = n
    return out


def ler(jar, caminho):
    """Estrutura do descritor `caminho` do `.jar`:
    `{registro: {"nivel", "ocorrencia", "obrigatorio", "chave", "rotulo",
    "descricao", "validadores", "campos": {nome: {...}}}}`, na ordem do
    XML (a ordem dos campos é a posição)."""
    with zipfile.ZipFile(jar) as z:
        xml = z.read(caminho).decode("utf-8", "replace")
    # daqui para baixo: as linhas 106–162 de `_ler` em
    # sped_tables/infra/descritor_pva.py, sem mudança (começam em
    # `xml = RE_COMENTARIO.sub("", xml)` e montam `out`); o `info` que a
    # linha 163 devolve junto não existe aqui
    return out
```

`consolidador/instalacao.py`:

```python
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
```

`consolidador/extracao.py`:

```python
# -*- coding: utf-8 -*-
"""Regrava `base/` a partir de uma `InstalacaoPVA`. A revisão do que mudou
é o `git diff base/`."""

import hashlib
import json
import os

from sped_tables.dominio.sped_model import so_digitos
from sped_tables.infra import base_referencia


def _gravar_texto(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(texto.splitlines()) + "\n")


def _gravar_json(caminho, objeto, ordenar=False):
    # o leiaute NÃO é ordenado: a ordem dos campos é a posição
    _gravar_texto(caminho, json.dumps(objeto, ensure_ascii=False, indent=1,
                                      sort_keys=ordenar))


def _limpar(pasta, extensao):
    if os.path.isdir(pasta):
        for nome in os.listdir(pasta):
            if nome.endswith(extensao):
                os.remove(os.path.join(pasta, nome))


def proxima_versao(anterior, data):
    """`AAAA.MM.n`: n + 1 no mesmo mês da anterior, 1 num mês novo."""
    a = base_referencia.chave_da_versao(anterior or "")
    if len(a) == 3 and a[:2] == (data.year, data.month):
        return "%04d.%02d.%d" % (data.year, data.month, a[2] + 1)
    return "%04d.%02d.1" % (data.year, data.month)


def ler_ncm_vigente(caminho_xlsx):
    """NCM de 8 dígitos da planilha de NCM vigente do Portal Siscomex."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho_xlsx, read_only=True,
                                data_only=True)
    ncms = set()
    for row in wb.active.iter_rows(values_only=True):
        cod = row[0] if row else None
        d = so_digitos(cod if isinstance(cod, str) else str(cod or ""))
        if len(d) == 8:
            ncms.add(d)
    return ncms


def _sha_curto(caminho):
    with open(caminho, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def extrair(instalacao, destino, versao=None, ncm_xlsx=None):
    """Regrava `destino` (a pasta `base/`) com o que a instalação publica e
    devolve o manifesto. Guias ficam como estão (`py -m consolidador
    guia`); o NCM só muda com `ncm_xlsx`."""
    from consolidador.instalacao import jar_descritor
    anterior = {}
    caminho_manifesto = os.path.join(destino, "manifesto.json")
    if os.path.exists(caminho_manifesto):
        with open(caminho_manifesto, encoding="utf-8") as fh:
            anterior = json.load(fh)
    origem = {}
    for layout in base_referencia.LEIAUTES:
        pasta = os.path.join(destino, "leiaute", layout)
        _limpar(pasta, ".json")
        for cod, (ini, fim, caminho) in instalacao.versoes(layout).items():
            _gravar_json(os.path.join(pasta, cod + ".json"), {
                "versao": cod, "descritor": caminho, "dt_ini": ini,
                "dt_fim": fim,
                "estrutura": instalacao.estrutura(layout, cod)})
        jar = jar_descritor(instalacao.raiz, layout)
        origem[layout] = {"descritor": os.path.basename(jar),
                          "sha256_descritor": _sha_curto(jar)}
    tabs = instalacao.tabelas()
    pasta = os.path.join(destino, "tabelas")
    _limpar(pasta, ".txt")
    for chave, (texto, _v) in sorted(tabs.items()):
        _gravar_texto(os.path.join(
            pasta, base_referencia.arquivo_da_tabela(chave)), texto)
    if ncm_xlsx:
        _gravar_texto(os.path.join(destino, "ncm", "vigente.txt"),
                      "\n".join(sorted(ler_ncm_vigente(ncm_xlsx))))
        origem["ncm"] = os.path.basename(ncm_xlsx)
    else:
        origem["ncm"] = anterior.get("origem", {}).get("ncm")
    origem["guias"] = {l: "%s %s" % (instalacao.guia(l).get("guia", ""),
                                     instalacao.guia(l).get("versao", ""))
                       for l in base_referencia.LEIAUTES}
    origem["tabelas"] = len(tabs)
    manifesto = {
        "esquema": base_referencia.ESQUEMA,
        "versao": versao or proxima_versao(anterior.get("versao"),
                                           instalacao.data),
        "data": instalacao.data.isoformat(),
        "origem": origem,
        "leiautes": {l: sorted(instalacao.versoes(l))
                     for l in base_referencia.LEIAUTES},
        "tabelas": {c: v for c, (_t, v) in sorted(tabs.items())},
    }
    _gravar_json(caminho_manifesto, manifesto, ordenar=True)
    return manifesto
```

`consolidador/guias.py` — edições sobre o arquivo movido:

- docstring: "para os JSON de `recursos/`" → "para `base/guias/`"; as
  linhas de uso viram
  `py -m consolidador guia ICMS "Guia Prático EFD - Versão 3.2.4.pdf"`.
- apague `RAIZ = …`, `sys.path.insert(…)` e
  `from sped_tables.infra.guias import ARQUIVOS as SAIDA`; apague `import
  sys` se ficar sem uso.
- troque `main()` por:

```python
def gravar(layout, pdf, fontes):
    """Extrai o guia do PDF para `fontes/guias/<layout>.json` e devolve o
    caminho."""
    if layout not in ("ICMS", "CONTRIB"):
        raise ValueError("leiaute: ICMS ou CONTRIB")
    guia = extrair(texto_do_pdf(pdf), layout)
    destino = os.path.join(fontes, "guias", layout + ".json")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(guia, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return destino
```

  e apague o bloco `if __name__ == "__main__":`.

`consolidador/__main__.py`:

```python
# -*- coding: utf-8 -*-
"""Linha de comando do consolidador.

    py -m consolidador extrair [--pva PASTA] [--data AAAA-MM-DD]
                               [--versao AAAA.MM.n] [--ncm planilha.xlsx]
        lê os PVAs desta máquina e regrava base/ (revise com git diff)
    py -m consolidador guia ICMS|CONTRIB arquivo.pdf
        extrai o guia prático para base/guias/
    py -m consolidador compilar [--saida arquivo.db]
        compila base/ (rodando do código-fonte, o programa faz isso sozinho)
    py -m consolidador publicar [--saida PASTA]
        compila e gera o pacote base_referencia-AAAA.MM.n.zip
"""

import argparse
import datetime
import os
import sys
import tempfile

from consolidador import extracao, guias
from consolidador.instalacao import ConsolidadorErro, InstalacaoPVA
from sped_tables.infra import base_referencia


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -m consolidador")
    sub = p.add_subparsers(dest="comando", required=True)
    e = sub.add_parser("extrair")
    e.add_argument("--pva")
    e.add_argument("--data", type=datetime.date.fromisoformat)
    e.add_argument("--versao")
    e.add_argument("--ncm")
    g = sub.add_parser("guia")
    g.add_argument("layout", choices=("ICMS", "CONTRIB"))
    g.add_argument("pdf")
    c = sub.add_parser("compilar")
    c.add_argument("--saida", default=base_referencia.caminho_embutido())
    u = sub.add_parser("publicar")
    u.add_argument("--saida", default="dist")
    a = p.parse_args(argv)
    fontes = base_referencia.pasta_fontes()
    try:
        if a.comando == "extrair":
            pva = InstalacaoPVA(a.pva, data=a.data, fontes=fontes)
            m = extracao.extrair(pva, fontes, versao=a.versao,
                                 ncm_xlsx=a.ncm)
            for aviso in pva.avisos:
                print("aviso:", aviso)
            print("base %s: %s; %d tabelas. Revise com: git diff base/"
                  % (m["versao"], m["leiautes"], len(m["tabelas"])))
        elif a.comando == "guia":
            print("guia gravado em", guias.gravar(a.layout, a.pdf, fontes))
        elif a.comando == "compilar":
            m = base_referencia.compilar(fontes, a.saida)
            print("base %s compilada em %s (%.1f MB)" % (
                m["versao"], a.saida, os.path.getsize(a.saida) / 1e6))
        else:
            os.makedirs(a.saida, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp:
                banco = os.path.join(tmp, base_referencia.ARQUIVO)
                m = base_referencia.compilar(fontes, banco)
                destino = os.path.join(
                    a.saida, "base_referencia-%s.zip" % m["versao"])
                base_referencia.empacotar(banco, destino)
            print("pacote:", destino)
            print("SHA-256 do banco:",
                  base_referencia.inspecionar(destino)["sha256"])
    except ConsolidadorErro as exc:
        print("erro:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`sped_tables/infra/guias.py` (sai na Tarefa 7; até lá aponta para o lugar
novo):

```python
ARQUIVOS = {"ICMS": "ICMS.json", "CONTRIB": "CONTRIB.json"}


def caminho(layout):
    return dados.recurso(os.path.join("base", "guias", ARQUIVOS[layout]))
```

`SPED Tables.spec:68-69` — os dois `recursos/guia_*.json` viram
`("base/guias/ICMS.json", "base/guias")` e
`("base/guias/CONTRIB.json", "base/guias")` (saem de vez na Tarefa 9).

`tests/test_guias.py:19-20` — troque o `sys.path.insert(...)` e
`import extrair_guias` por `from consolidador import guias as extrair_guias`
(apague `import sys` se ficar sem uso).

- [ ] **Step 4: Run the unit tests**

Run: `py -m unittest tests.test_consolidador tests.test_guias -v` → PASS.

- [ ] **Step 5: Extrair a base real e conferir a equivalência**

Run: `py -m consolidador extrair --data 2026-10-15 --versao 2026.10.1`
Expected: `base 2026.10.1: {'CONTRIB': ['006'], 'ICMS': ['015', '016',
'017', '018', '019', '020']}; ~290 tabelas` e um aviso do `021`.

Run: `py -m consolidador compilar` e anote o tamanho impresso — tem de ser
**menor que 10 MB** (se não for, pare e leve o número a quem pediu).
Run: `py -m consolidador compilar --saida %TEMP%\b2.db` e confira que os
dois `.sha256` são iguais.
Run: `py -m unittest tests.test_equivalencia_base -v` → PASS (4 testes).
Run: `git status --short base | head` — confira que nada em `base/` tem
nome ou dado de cliente (são só leiaute, tabelas da Receita e guias).
Run: `py -m unittest discover -s tests -t .` → PASS.

- [ ] **Step 6: Commit**

```bash
git add -A consolidador base ferramentas recursos sped_tables/infra/guias.py "SPED Tables.spec" tests
git commit -m "Consolidador extrai base/ dos PVAs (leiaute por versão, tabelas, guias)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: A troca — o programa passa a usar só a base

**Files:**
- Modify: `sped_tables/aplicacao/montagem.py`
- Delete: `sped_tables/infra/referencias_pva.py`, `sped_tables/infra/guias.py`
- Delete: `sped_tables/infra/descritor_pva.py` (o código já está em
  `consolidador/descritor.py`)
- Move: `sped_tables/infra/banco_pva.py` → `consolidador/banco_pva.py`;
  `tests/test_banco_pva.py` acompanha (imports)
- Modify: `sped_tables/infra/config.py` (apaga `pasta_tabelas`,
  `jar_descritor`, `pasta_tabelas_rfb` e as chaves `tabelas`/`descritor` de
  `PVAS`)
- Modify: `sped_tables/dominio/sped_model.py:3657,3803` (texto "do PVA")
- Modify: `sped_tables/interface/controladores/gerais.py:425-440`
  (`_resumo_tabelas_pva`)
- Modify: `sped_tables/interface/app.py:134` (comentário)
- Modify: `sped_tables/interface/autoteste.py:153-163` (`guias_praticos`
  usava o `infra/guias.py` que sai)
- Modify: `ferramentas/cobertura_guias.py`, `ferramentas/validar_no_pva.py`
- Modify: `tests/__init__.py`, `tests/test_arquitetura.py`,
  `tests/test_guias.py`, `tests/test_regras_guia.py`,
  `tests/test_robustez.py`, `tests/test_equivalencia_base.py`
- Test: `tests/test_arquitetura.py` (duas regras novas)

**Interfaces:**
- Consumes: `base_referencia.em_uso()`, `ReferenciasBase`,
  `InstalacaoPVA`.
- Produces: `montagem.configurar(fonte_referencias=None)` liga
  `ReferenciasBase(base, nome=...)`, ou a fonte vazia com aviso;
  `tests.PVA_REAL` (raiz do PVA de verdade, ou None).

- [ ] **Step 1: Write the failing tests** — em `tests/test_arquitetura.py`:

```python
class TestSemPvaNoPrograma(unittest.TestCase):
    """O programa não lê a instalação do PVA para validar; só o Abrir no
    PVA a usa. E o consolidador fica fora do programa."""

    # quem pode citar a raiz/pasta do PVA: o Abrir no PVA e quem a escolhe
    PODEM = {os.path.join("infra", "pva.py"),
             os.path.join("infra", "config.py"),
             os.path.join("aplicacao", "envio_pva.py"),
             os.path.join("interface", "controladores", "gerais.py")}
    NOMES = ("raiz_pva", "pasta_pva", "pasta_tabelas", "jar_descritor",
             "PVAS")

    def test_sped_tables_nao_importa_o_consolidador(self):
        for raiz, _d, nomes in os.walk(PACOTE):
            for nome in nomes:
                if nome.endswith(".py"):
                    for linha, mod in _imports(os.path.join(raiz, nome)):
                        self.assertFalse(mod.startswith("consolidador"),
                                         "%s:%d" % (nome, linha))

    def test_so_o_abrir_no_pva_le_a_instalacao(self):
        violacoes = []
        for raiz, _d, nomes in os.walk(PACOTE):
            for nome in nomes:
                if not nome.endswith(".py"):
                    continue
                caminho = os.path.join(raiz, nome)
                rel = os.path.relpath(caminho, PACOTE)
                if rel in self.PODEM:
                    continue
                with open(caminho, encoding="utf-8") as fh:
                    arvore = ast.parse(fh.read())
                for no in ast.walk(arvore):
                    if (isinstance(no, ast.Attribute)
                            and no.attr in self.NOMES
                            and isinstance(no.value, ast.Name)
                            and no.value.id == "config"):
                        violacoes.append("%s:%d config.%s"
                                         % (rel, no.lineno, no.attr))
        self.assertEqual(violacoes, [])

    def test_sem_base_a_montagem_liga_a_fonte_vazia(self):
        from unittest import mock
        from sped_tables.infra import base_referencia, dados
        avisos = []
        dados.ao_avisar(avisos.append)
        anterior = referencias.atual()
        try:
            with mock.patch.object(base_referencia, "em_uso",
                                   lambda: (None, "nenhuma legível")):
                montagem.configurar()
            self.assertEqual(type(referencias.atual()),
                             referencias.Referencias)
            self.assertTrue(avisos)
        finally:
            dados.ao_avisar(None)
            referencias.definir(anterior)
```

e acrescente em `TestPorta`:

```python
    def test_montagem_liga_a_base_de_referencia(self):
        from sped_tables.infra.referencias_base import ReferenciasBase
        montagem.configurar()
        self.assertIsInstance(referencias.atual(), ReferenciasBase)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m unittest tests.test_arquitetura -v`
Expected: FAIL — `infra/descritor_pva.py`, `infra/tabelas_*`/`referencias_pva`
citam `config.pasta_tabelas`/`jar_descritor`, e a montagem liga o
`ReferenciasPVA`.

- [ ] **Step 3: Implement**

`montagem.py`:

```python
"""Raiz de composição: liga as portas do domínio às implementações.

É o único lugar que conhece ao mesmo tempo o domínio e a infraestrutura
concreta. Roda no início do programa (`interface.app.main`), da suíte de
testes e depois de importar uma base de referência; trocar a fonte das
tabelas oficiais — por uma base nova, por uma tabela de teste — é trocar o
que se passa aqui.
"""

from sped_tables.dominio import referencias


def configurar(fonte_referencias=None):
    """Liga a porta das tabelas oficiais. Sem argumento, usa a base de
    referência em uso (a mais nova entre a embutida e a importada); sem
    nenhuma legível, a fonte vazia — as regras que dependem dela se
    abstêm — e um aviso."""
    if fonte_referencias is None:
        from sped_tables.infra import base_referencia, dados
        from sped_tables.infra.referencias_base import ReferenciasBase
        base, origem = base_referencia.em_uso()
        if base is None:
            dados.avisar(
                "Base de referência indisponível (%s): as verificações que "
                "dependem do leiaute e das tabelas oficiais ficam "
                "desligadas. Reinstale o programa ou importe uma base em "
                "Configurações → Base de referência." % origem)
        else:
            fonte_referencias = ReferenciasBase(
                base, nome="base de referência %s (%s)"
                % (base.manifesto()["versao"], origem))
    return referencias.definir(fonte_referencias)
```

Apague os módulos que saem e mova o `banco_pva`:

```bash
git rm sped_tables/infra/referencias_pva.py sped_tables/infra/guias.py sped_tables/infra/descritor_pva.py
git mv sped_tables/infra/banco_pva.py consolidador/banco_pva.py
```

No `consolidador/banco_pva.py`, o import de `config` continua
`from sped_tables.infra import config` (permitido). Em
`tests/test_banco_pva.py` e `ferramentas/validar_no_pva.py`, troque
`from sped_tables.infra import banco_pva` por
`from consolidador import banco_pva`.

`config.py` — apague `pasta_tabelas`, `jar_descritor` e
`pasta_tabelas_rfb`; em `PVAS` fica só a `"pasta"` de cada leiaute (as
subpastas moram em `consolidador.instalacao.SUBPASTAS`). Atualize a
docstring do topo: "Ponto único de configuração: onde estão os PVAs — que o
programa só usa para o *Abrir no PVA* (as tabelas e o leiaute vêm da base
de referência)."

`tests/test_robustez.py` — em `test_variavel_de_ambiente_manda`, troque a
asserção de `config.pasta_tabelas("ICMS")` por
`self.assertEqual(config.pasta_pva("ICMS"), os.path.join(p, "Fiscal"))`;
`_pva_falso` cria só `os.path.join(raiz, cfg["pasta"])`; apague
`test_descritor_e_lido_uma_vez` e o import de `descritor_pva`.

`sped_model.py:3657` e `:3803` — "do PVA não está disponível" /
"…crédito do PVA não…" → "da base de referência não está disponível" /
"…crédito da base de referência não…" (o teste
`test_sem_fonte_as_regras_se_abstem` procura só "não está disponível").

`gerais.py` — `_resumo_tabelas_pva` vira `_resumo_tabelas` (e as duas
chamadas em `validar_campos`); o texto sem domínios:

```python
        if not dominios:
            return ("Base de referência sem o leiaute deste arquivo — a "
                    "verificação usou apenas as regras embutidas, que "
                    "cobrem menos que o validador oficial.")
```

e "Validação feita pelo descritor do PVA" → "Validação feita pelo leiaute
da versão %s (%s)" com `info.get("versao")` e
`referencias.atual().descricao()` (importe `referencias` se preciso;
`validacao.dominios_do_documento` passa a devolver `"versao":
info_desc.get("versao")` no `info` — acrescente a chave no `return` do fim
da função).

`app.py:134` — comentário: "liga as regras fiscais à base de referência".

`autoteste.py`, em `guias_praticos` (o item inteiro sai na Tarefa 9; aqui
só não pode quebrar): troque `from sped_tables.infra import guias` e
`g = guias.carregar(layout)` por `from sped_tables.dominio import
referencias` e `g = referencias.atual().guia(layout)`. O
`test_autoteste_pelo_lancador` roda esse item.

`ferramentas/cobertura_guias.py` — troque `from sped_tables.infra import
descritor_pva` e `est, info = descritor_pva.carregar(layout)` por
`est, info = referencias.atual().estrutura(layout)` (a montagem já é
chamada no `main` do script; confira).

`tests/__init__.py` — depois do bloco que define `SPED_TABLES_DADOS` e
antes de `montagem.configurar()`:

```python
# a suíte roda como o programa na máquina de quem não tem PVA: a pasta do
# PVA aponta para um diretório vazio e tudo vem da base de referência. A
# instalação de verdade fica guardada em PVA_REAL para o teste de
# equivalência, que confere que a base reproduz o PVA desta máquina.
from sped_tables.infra import config  # noqa: E402

_raiz = config.raiz_pva()
PVA_REAL = _raiz if any(os.path.isdir(config.pasta_pva(l, _raiz))
                        for l in config.PVAS) else None
os.environ[config.VARIAVEL] = tempfile.mkdtemp(prefix="sped_sem_pva_")
config.esquecer()
```

e atualize o comentário de `montagem.configurar()`: "a suíte liga a mesma
fonte que o programa: a base de referência compilada de `base/`".

`tests/test_equivalencia_base.py` — `PVA = tests.PVA_REAL` (com `import
tests`; apague o cálculo pelo `config`) e troque `_referencia_pva`:

```python
def _referencia_pva():
    """O lado "PVA" da comparação pela porta: o mesmo adaptador, lendo a
    instalação em vez da base."""
    return ReferenciasBase(TestBaseReproduzOPva.pva)
```

`tests/test_guias.py`:
- `TestDescritor.setUp`: `self.est = descritor.ler(self.jar,
  "descritor/escrituracao/ato001/v1/descritor.xml")` com
  `from consolidador import descritor`.
- `TestRecursos`: `g = referencias.atual().guia(layout)` no lugar de
  `guias.carregar(layout)` (três lugares); apague `from sped_tables.infra
  import guias`.
- `TestLeiauteContraPVA`: apague o `@unittest.skipUnless(...)`; a estrutura
  bruta vem da base:

```python
    def test_estrutura(self):
        from sped_tables.infra import base_referencia
        base, _origem = base_referencia.em_uso()
        for layout, tabela in (("ICMS", sped_layouts.CAMPOS_ICMS),
                               ("CONTRIB", sped_layouts.CAMPOS_CONTRIB)):
            versao = max(base.versoes(layout), key=int)
            est = base.estrutura(layout, versao)
            for reg, d in est.items():
                # (o corpo do laço continua igual)
```

`tests/test_regras_guia.py:393-404` — sem o `skipUnless`, sobre todas as
versões da base:

```python
class TestValidadoresDoPva(unittest.TestCase):

    def test_ids_existem_no_descritor(self):
        """Todo id em `pva` existe no leiaute de alguma versão guardada —
        erro de digitação ali faria o diagnóstico continuar listando a
        regra como "só o PVA verifica"."""
        from sped_tables.infra import base_referencia
        base, _origem = base_referencia.em_uso()
        todos = set()
        for layout in base_referencia.LEIAUTES:
            for versao in base.versoes(layout):
                for d in base.estrutura(layout, versao).values():
                    todos |= set(d.get("validadores", ()))
        self.assertEqual(G.validadores_reproduzidos() - todos, set())
```

(apague o `from sped_tables.infra import descritor_pva`).

`test_arquitetura.py` — `EXCECOES` passa a nomear
`"sped_tables.infra.referencias_base"`.

Depois: `grep -rn "descritor_pva\|referencias_pva\|infra.guias\|infra import guias\|banco_pva" --include=*.py sped_tables tests ferramentas`
não pode devolver nada além de `consolidador`/`from consolidador import
banco_pva`.

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_arquitetura -v` → PASS.
Run: `py -m unittest discover -s tests -t .` → PASS. Os testes que antes
pulavam com "PVA não instalado" (`test_guias`, `test_regras_guia`) agora
rodam; o de equivalência roda onde há PVA.
Run (na máquina com os arquivos reais, `SPED_TABLES_ARQUIVOS_REAIS`
apontada): `py -m unittest tests.test_reais -v` → PASS com o gabarito
**inalterado** — e a suíte já roda com a pasta do PVA vazia. Qualquer
diferença: pare e investigue (critério 2 do spec), não ajuste o gabarito.
Run: `py sped_editor.py` — abra um arquivo, rode o diagnóstico e confira o
texto "Verificado com o leiaute da versão …".

- [ ] **Step 5: Commit**

```bash
git add -A sped_tables consolidador ferramentas tests
git commit -m "O programa usa só a base de referência; o PVA fica para o Abrir no PVA" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Atualizar a base pela interface

**Files:**
- Create: `sped_tables/interface/dialogos/base_referencia.py`
- Modify: `sped_tables/interface/acoes.py:155-162`
- Modify: `sped_tables/interface/controladores/gerais.py` (método novo,
  perto de `escolher_pasta_pva`)
- Test: `tests/test_interface.py`

**Interfaces:**
- Consumes: `base_referencia.em_uso`, `inspecionar`, `importar`,
  `impressao_digital`, `BaseRecusada`; `montagem.configurar()`;
  `comum.abrir_janela`, `comum.informar`, `comum.definir_papel`.
- Produces: `DialogoBaseReferencia(parent=None, ao_importar=None)`; ação
  `act_base_referencia` → `JanelaPrincipal.mostrar_base_referencia()`.

- [ ] **Step 1: Write the failing test** — em `TestJanela`:

```python
    def test_base_de_referencia_mostra_a_versao_e_importa(self):
        from sped_tables.dominio import referencias
        from sped_tables.infra import base_referencia
        from tests import base_teste
        j = self.ed.JanelaPrincipal()
        j.act_base_referencia.trigger()
        dlg = j._janelas["DialogoBaseReferencia"]
        base, _origem = base_referencia.em_uso()
        self.assertIn(base.manifesto()["versao"], dlg.lbl.text())
        with PastaTemporaria() as p:
            pacote = base_referencia.empacotar(
                base_teste.compilada(p, versao="2999.01.1"),
                os.path.join(p, "pacote.zip"))
            with mock.patch.object(
                    QFileDialog, "getOpenFileName",
                    staticmethod(lambda *a, **k: (pacote, ""))), \
                    mock.patch.object(dlg, "_confirmar", lambda m, d: True):
                dlg._importar()
            try:
                self.assertIn("2999.01.1", dlg.lbl.text())
                self.assertIn("2999.01.1", referencias.atual().nome)
            finally:
                os.remove(base_referencia.caminho_importado())
                from sped_tables.aplicacao import montagem
                montagem.configurar()
        j.close()
        self.assertEqual(self.erros, [], self._falhas())
```

(Confira os imports no topo de `tests/test_interface.py`: `os`, `mock`,
`QFileDialog` — acrescente o que faltar.)

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_interface.TestJanela.test_base_de_referencia_mostra_a_versao_e_importa -v`
Expected: FAIL (`act_base_referencia` não existe).

- [ ] **Step 3: Implement**

`acoes.py`, na seção `# ---- Configurações`:

```python
    Acao("act_base_referencia", "Base de referência…",
         "mostrar_base_referencia", SEMPRE, MENU_CONFIG),
    Acao("act_pasta_pva", "Pasta dos PVAs (para o Abrir no PVA)…",
         "escolher_pasta_pva", SEMPRE, MENU_CONFIG),
```

(substitui a linha atual do `act_pasta_pva`).

`gerais.py`:

```python
    def mostrar_base_referencia(self):
        """A base de referência em uso (versão, data, origem, impressão
        digital) e a importação de uma mais nova."""
        self._dlg_base = abrir_janela(self, DialogoBaseReferencia(
            self, ao_importar=montagem.configurar))
```

com `from sped_tables.aplicacao import montagem` e
`from sped_tables.interface.dialogos.base_referencia import
DialogoBaseReferencia` no topo.

`sped_tables/interface/dialogos/base_referencia.py`:

```python
# -*- coding: utf-8 -*-
"""A base de referência em uso e a importação de uma mais nova.

A base traz o leiaute de cada versão, as tabelas oficiais e os guias; ela
atualiza sem programa novo. Antes de aceitar um pacote, a tela mostra a
impressão digital para conferir com a publicada."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QVBoxLayout)

from sped_tables.infra import base_referencia
from sped_tables.interface.comum import definir_papel, informar

NOMES = {"ICMS": "EFD ICMS/IPI", "CONTRIB": "EFD Contribuições"}


def _texto(manifesto, origem, digital):
    leiautes = "; ".join(
        "%s %s" % (NOMES[l], ", ".join(v))
        for l, v in sorted(manifesto.get("leiautes", {}).items()) if v)
    return ("Versão %s, de %s (%s).\nLeiautes: %s.\n"
            "Impressão digital (SHA-256):\n%s"
            % (manifesto.get("versao", "?"), manifesto.get("data", "?"),
               origem, leiautes or "nenhum", digital))


class DialogoBaseReferencia(QDialog):

    def __init__(self, parent=None, ao_importar=None):
        super().__init__(parent)
        self.ao_importar = ao_importar
        self.setWindowTitle("Base de referência")
        self.resize(560, 260)
        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl, 1)
        botoes = QHBoxLayout()
        b_importar = QPushButton("Importar base mais nova…")
        b_importar.clicked.connect(self._importar)
        b_fechar = QPushButton("Fechar")
        b_fechar.clicked.connect(self.reject)
        botoes.addWidget(b_importar)
        botoes.addStretch(1)
        botoes.addWidget(b_fechar)
        lay.addLayout(botoes)
        self._mostrar()

    def _mostrar(self):
        base, origem = base_referencia.em_uso()
        if base is None:
            self.lbl.setText(
                "Nenhuma base de referência legível: as verificações que "
                "dependem do leiaute e das tabelas oficiais estão "
                "desligadas. Importe uma base.")
            definir_papel(self.lbl, "erro")
            return
        definir_papel(self.lbl, "info")
        self.lbl.setText(_texto(base.manifesto(), origem,
                                base_referencia.impressao_digital(
                                    base.caminho)))

    def _confirmar(self, manifesto, digital):
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Importar base de referência")
        caixa.setText(
            "Importar a base %s, de %s?\n\nImpressão digital (SHA-256):\n%s"
            "\n\nCompare com a publicada antes de confirmar."
            % (manifesto.get("versao", "?"), manifesto.get("data", "?"),
               digital))
        sim = caixa.addButton("Importar", QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caixa.exec()
        return caixa.clickedButton() is sim

    def _importar(self):
        caminho, _f = QFileDialog.getOpenFileName(
            self, "Pacote da base de referência", "",
            "Base de referência (base_referencia-*.zip);;Todos (*)")
        if not caminho:
            return
        try:
            pacote = base_referencia.inspecionar(caminho)
            if not pacote["confere"]:
                raise base_referencia.BaseRecusada(
                    "A impressão digital do banco não confere com a do "
                    "manifesto: o arquivo foi alterado ou está corrompido.")
            if not self._confirmar(pacote["manifesto"], pacote["sha256"]):
                return
            manifesto = base_referencia.importar(caminho)
        except base_referencia.BaseRecusada as exc:
            QMessageBox.warning(self, "Base de referência", str(exc))
            return
        if self.ao_importar is not None:
            self.ao_importar()
        self._mostrar()
        informar(self, "Base de referência",
                 "Base %s importada: ela já vale para o próximo "
                 "diagnóstico." % manifesto["versao"])
```

- [ ] **Step 4: Run the tests**

Run: `py -m unittest tests.test_interface -v` → PASS (inclusive o que
dispara toda ação nos dois leiautes).
Run: `py -m unittest discover -s tests -t .` → PASS.

- [ ] **Step 5: Commit**

```bash
git add sped_tables/interface tests/test_interface.py
git commit -m "Configurações → Base de referência: versão em uso e importação" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: A base dentro do executável

**Files:**
- Modify: `ferramentas/gerar_executavel.py`
- Modify: `SPED Tables.spec:16-17,65-69`
- Modify: `sped_tables/interface/autoteste.py:140-165`
- Test: `tests/test_interface.py:655` (`test_autoteste_pelo_lancador`)

**Interfaces:**
- Consumes: `base_referencia.compilar`, `pasta_fontes`,
  `caminho_embutido`, `em_uso`.
- Produces: item de autoteste `"base de referência"` (substitui `"tabelas
  do PVA"` e `"guias práticos"`).

- [ ] **Step 1: Write the failing test** — no fim de
  `test_autoteste_pelo_lancador` (`tests/test_interface.py:655`), que roda
  o autoteste pelo lançador e lê o JSON (`itens`: `nome`, `ok`,
  `detalhe`):

```python
        self.assertNotIn("tabelas do PVA", nomes)
        self.assertNotIn("guias práticos", nomes)
        item = next(i for i in saida["itens"]
                    if i["nome"] == "base de referência")
        with open(os.path.join(raiz, "base", "manifesto.json"),
                  encoding="utf-8") as fh:
            versao = json.load(fh)["versao"]
        self.assertEqual(item["detalhe"]["versao"], versao)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m unittest tests.test_interface.TestAutoteste -v` → FAIL
(`StopIteration`: o item não existe).

- [ ] **Step 3: Implement**

`autoteste.py` — troque os itens `tabelas_pva` e `guias_praticos` por:

```python
    def base_de_referencia():
        # vai dentro do executável (SPED Tables.spec); sem ela as
        # validações pelo leiaute e as tabelas oficiais se desligam
        from sped_tables.dominio import referencias
        from sped_tables.infra import base_referencia
        montagem.configurar()
        base, origem = base_referencia.em_uso()
        if base is None:
            return False, origem
        info = {"versao": base.manifesto()["versao"], "origem": origem}
        for layout in base_referencia.LEIAUTES:
            est, meta = referencias.atual().estrutura(layout)
            guia = referencias.atual().guia(layout)
            info[layout] = "versão %s, %d registros, guia %s" % (
                meta.get("versao"), len(est), guia.get("versao"))
            if not est or not guia:
                return False, info
        return True, info
    rel.conferir("base de referência", base_de_referencia)
```

`SPED Tables.spec` — no docstring, o item dos guias vira:

```
* **`recursos/base_referencia.db`**, a base de referência compilada de
  `base/` por `ferramentas/gerar_executavel.py`: leiaute de cada versão,
  tabelas oficiais e guias práticos. Sem ela as validações pelo leiaute se
  desligam.
```

e em `_recursos` as duas linhas dos guias viram
`("recursos/base_referencia.db", "recursos"),`.

`gerar_executavel.py` — antes de `empacotar()` no fluxo principal:

```python
def compilar_base():
    """A base de referência vai dentro do executável, compilada de base/
    agora — nunca a que estiver por acaso em recursos/."""
    sys.path.insert(0, RAIZ)
    from sped_tables.infra import base_referencia
    m = base_referencia.compilar(base_referencia.pasta_fontes(),
                                 base_referencia.caminho_embutido())
    tamanho = os.path.getsize(base_referencia.caminho_embutido()) / 1e6
    print("base de referência %s compilada (%.1f MB)"
          % (m["versao"], tamanho))
```

e chame `compilar_base()` logo antes de `empacotar()`.

- [ ] **Step 4: Run the tests and the executable**

Run: `py -m unittest discover -s tests -t .` → PASS.
Run: `py ferramentas/gerar_executavel.py` → "base de referência … compilada
(< 10 MB)" e "autoteste: passou". Confira no
`build/manifesto_executavel.txt` que `recursos/base_referencia.db` está lá e
que nenhum `guia_*.json` ficou.

- [ ] **Step 5: Commit**

```bash
git add ferramentas/gerar_executavel.py "SPED Tables.spec" sped_tables/interface/autoteste.py tests
git commit -m "Executável leva a base de referência compilada; autoteste confere" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Documentação e versão

**Files:**
- Modify: `sped_tables/version.py` (`1.1.0-dev.14` → `1.1.0-dev.15`)
- Modify: `CHANGELOG.md`, `README.md`, `TESTES.md`, `CLAUDE.md`,
  `ARQUITETURA.md`, `ROADMAP_REGRAS_PVA.md`

- [ ] **Step 1: CHANGELOG** — entrada `## [1.1.0-dev.15] - 2026-10-15`:

```markdown
### Adicionado
- **Base de referência.** O leiaute de cada versão, as tabelas oficiais,
  os guias práticos e o NCM vigente vêm de uma base compilada na geração do
  programa (`base/` → `recursos/base_referencia.db`), não mais do PVA
  instalado na máquina. Com PVA antigo ou sem PVA, a pré-validação é a
  mesma.
- **Leiaute pela versão do arquivo.** Cada arquivo é conferido com a
  estrutura do `COD_VER` que declara (ICMS/IPI 015 a 020, Contribuições
  006); versão fora da base é avisada e não é cobrada por estrutura de
  outra.
- **Configurações → Base de referência…** mostra a base em uso e importa um
  pacote mais novo (`base_referencia-AAAA.MM.n.zip`), conferindo a
  impressão digital; recusa pacote adulterado, igual ou mais antigo, ou
  feito para programa mais novo.
- **Consolidador** (`py -m consolidador extrair|guia|compilar|publicar`):
  regrava `base/` a partir dos PVAs de quem compila.

### Removido
- A configuração *Tabelas da RFB* (pasta e arquivos do CST por NCM): as
  tabelas vêm da base.

### Alterado
- O gabarito dos arquivos reais **não mudou**; a suíte passou a rodar com a
  pasta do PVA vazia.
```

- [ ] **Step 2: README** — seção nova "Base de referência" (o que é, como
  ver a versão, como importar, que o PVA só é usado pelo *Abrir no PVA*);
  apague o que fala da configuração das tabelas da RFB no *CST por NCM*;
  na tabela de pastas, `consolidador/` e `base/` e o `ferramentas/` sem o
  `extrair_guias.py`.

- [ ] **Step 3: TESTES.md** — a suíte roda sem PVA (pasta vazia); a base é
  compilada de `base/` sozinha; `tests.PVA_REAL` e o teste de equivalência
  (o que fazer quando falha: `py -m consolidador extrair`, revisar o diff);
  os comandos de guia passam a `py -m consolidador guia …`.

- [ ] **Step 4: CLAUDE.md** — tabela de módulos (sai `descritor_pva`,
  `tabelas_pva`, `tabelas_rfb`, `referencias_pva`, `guias`, `banco_pva`;
  entram `base_referencia`, `referencias_base`, `tabelas_oficiais`,
  `tabelas_ncm` e o pacote `consolidador`); a regra "Nada do domínio lê a
  instalação do PVA" vira "**Nada do programa lê a instalação do PVA**, salvo
  o *Abrir no PVA*: leiaute, tabelas e guias vêm de
  `referencias.atual()`, ligada à base de referência"; a seção "Domínios que
  vêm dos PVAs, não do código" passa a dizer que vêm da base, extraída do
  PVA na compilação; "Os guias práticos" aponta `base/guias/` e
  `py -m consolidador guia`; "O descritor" cita `consolidador/descritor.py`
  e acrescenta: **a ordem dos campos no JSON do leiaute é a posição — não
  ordene**; nova seção curta "A base de referência" com o desenho (fontes
  em texto, compilação reproduzível, versão `AAAA.MM.n`, retenção de 5 anos,
  `COD_VER` por arquivo, Contribuições só 006) e o aviso de que
  `tests/fabrica.py` declara `020` de propósito.

- [ ] **Step 5: ARQUITETURA.md** — o diagrama de camadas ganha, fora do
  `sped_tables`, o `consolidador` (que pode importar o programa, nunca o
  contrário) e a base de referência como o adaptador da porta.

- [ ] **Step 6: ROADMAP_REGRAS_PVA.md** — reescreva em torno dos quatro
  projetos do spec (1 Base de referência — feito nesta versão; 2 Motor de
  regras; 3 Consolidador completo; 4 Migração e cobertura), mantendo as
  seções que continuam valendo (números do levantamento, princípios,
  riscos) e trocando a "Fase 4" (descritor da versão do arquivo) por "feito
  no projeto 1".

- [ ] **Step 7: Verify and commit**

Run: `py -m unittest discover -s tests -t .` → PASS.
Run: `grep -rn "tabelas_pva\|tabelas_rfb\|descritor_pva\|referencias_pva\|extrair_guias\|recursos/guia_" --include=*.md . | grep -v "docs/superpowers\|CHANGELOG.md"`
→ nada (o CHANGELOG guarda o histórico).

```bash
git add -A sped_tables/version.py CHANGELOG.md README.md TESTES.md CLAUDE.md ARQUITETURA.md ROADMAP_REGRAS_PVA.md
git commit -m "Versão 1.1.0-dev.15 — base de referência" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

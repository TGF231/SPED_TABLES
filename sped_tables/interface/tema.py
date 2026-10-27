# -*- coding: utf-8 -*-
"""Paleta e folha de estilo (QSS) do SPED Tables.

Os valores vêm do tema **MegUI** (`tema_tokens.py`, GERADO pelo gerador do
MegUI a partir do `megui.tokens.json` — não editar à mão): as cores dos dois
temas, a tipografia, a escala de espaço, as densidades, o raio, as medidas
de layout e o movimento. O gerador recusa paleta que reprove em contraste:
cada tinta (`ink`, `ink_2`, `ink_3`) passa 4,5:1 sobre todo fundo,
`accent_linha` passa 3:1 sobre `surface` e `on_accent`, 4,5:1 sobre
`accent`. Valor que falte vai para o JSON do MegUI, não para cá.

O que o MegUI ainda não declara e o programa precisa fica em `_EXTENSAO`,
nominalmente, até entrar no JSON: o limite de campo, o acento como texto, o
texto sobre o erro e o fundo de campo com erro, e o `produto` (nome do
produto no topo das grades C170).

O uso de cada token é um contrato:

* limite de campo é `field_border` (>= 3:1), nunca `border_2`, que é
  decorativo;
* foco, aba ativa, seleção e caixa marcada são marcados com `accent_linha`:
  no tema escuro o `accent` é um preenchimento (botão, caixa marcada) e quase
  some como linha contra o fundo;
* seleção tem **dois** sinais: o fundo `accent_soft` e a linha de acento —
  o fundo sozinho tem contraste ~1,2:1 e não basta;
* acento e erro são dois vermelhos: erro vai sempre com ícone e texto;
* só os pesos 400 e 700; nenhuma animação decorativa.

O que este aplicativo tem de próprio é ser lido em **grades**: a linha
divisória precisa ser discreta para não competir com o número, e visível o
bastante para o olho não pular de coluna.

As cores dos relatórios (divergência, conferido, aviso) vêm daqui — nunca
literais no código da GUI —, senão o tema escuro as deixaria ilegíveis.

O template é um `string.Template` (`$bg`, `$accent`…) em vez de f-string,
para que as chaves do QSS não precisem ser dobradas.
"""

from dataclasses import dataclass
from string import Template

from sped_tables.interface import tema_tokens as megui

# ------------------------------------------------------------------ fontes
# As famílias do MegUI; sem elas instaladas, as do Windows.
FONT_UI = megui.FONT_UI.replace(", sans-serif", ', "Segoe UI", sans-serif')
FONT_MONO = megui.FONT_MONO.replace(
    ", monospace", ', "Cascadia Mono", "Consolas", monospace')


@dataclass(frozen=True)
class Paleta:
    nome: str
    bg: str               # fundo da janela
    surface: str          # painéis, campos e fundo das grades
    surface_2: str        # faixas, cabeçalhos, barra de título e rodapé
    sunken: str           # fundo de listas e campos rebaixados
    linha_alt: str        # linha alternada da grade (decorativo)
    somente_leitura: str  # célula derivada, não editável
    ink: str              # texto principal
    ink_2: str            # texto secundário
    ink_3: str            # desabilitado, placeholder (passa 4,5:1 no MegUI)
    border: str           # linha de grade e divisórias
    border_2: str         # contorno decorativo; NÃO é limite de campo
    field_border: str     # limite de campo/controle (>= 3:1)
    accent: str           # preenchimento: ação primária, caixa marcada
    accent_hover: str     # hover do acento (texto branco por cima)
    accent_linha: str     # marca de acento: foco, aba ativa, seleção (>= 3:1)
    accent_soft: str      # fundo de seleção (sempre com a linha de acento)
    on_accent: str        # texto sobre o acento
    accent_text: str      # acento como texto ou link (>= 4,5:1)
    focus: str            # borda de foco: é a accent_linha
    ok: str               # confere / sem divergência
    warn: str             # atenção / sem regra cadastrada
    bad: str              # divergência / erro
    on_bad: str           # texto sobre bad
    bad_soft: str         # fundo de campo com erro
    info: str             # chave estrutural (coluna REG), links neutros
    inverse_surface: str  # fundo de tooltip
    on_inverse_surface: str
    produto: str          # nome do produto no topo das grades C170


# O que o MegUI ainda não declara (ver o topo): candidatos ao JSON.
_EXTENSAO = {
    "claro": dict(field_border="#748AA0", accent_text="#7D0E0E",
                  on_bad="#FFFFFF", bad_soft="#FCE8E6", produto="#2E7D32"),
    "escuro": dict(field_border="#5F768E", accent_text="#E0716D",
                   on_bad="#1A0505", bad_soft="#3A1414", produto="#86EFAC"),
}


def _de_megui(m):
    return Paleta(
        nome=m.nome, bg=m.bg, surface=m.surface, surface_2=m.surface2,
        sunken=m.sunken, linha_alt=m.linha_alt,
        somente_leitura=m.somente_leitura, ink=m.ink, ink_2=m.ink2,
        ink_3=m.ink3, border=m.border, border_2=m.border2,
        accent=m.accent, accent_hover=m.accent_hover,
        accent_linha=m.accent_linha, accent_soft=m.accent_soft,
        on_accent=m.on_accent, focus=m.accent_linha, ok=m.ok, warn=m.warn,
        bad=m.bad, info=m.info, inverse_surface=m.ink,
        on_inverse_surface=m.surface, **_EXTENSAO[m.nome])


CLARO = _de_megui(megui.CLARO)
ESCURO = _de_megui(megui.ESCURO)

# ------------------------------------------------------------- densidade
# Numa tela apertada, alguns pixels de padding a menos por célula valem uma
# coluna inteira a mais visível numa grade de SPED. A densidade do MegUI mexe
# no espaçamento (multiplicador) e na altura dos controles; corpo de fonte,
# cor e borda seguem iguais nas duas. Pares (y, x) em chaves da escala de
# espaço.
DENSIDADES = megui.DENSIDADES
_PADDINGS = {"celula": ("meio", "1"), "cabecalho": ("1", "2"),
             "aba": ("1", "3"), "botao": ("1", "3"), "campo": ("1", "2")}
_densidade = "normal"
_ativa = CLARO


def definir_densidade(nome):
    """'normal' ou 'compacta'. Devolve a densidade ativa."""
    global _densidade
    if nome in DENSIDADES:
        _densidade = nome
    return _densidade


def densidade():
    return _densidade


def atual():
    return _ativa


def definir_escuro(escuro):
    """Troca a paleta ativa e devolve a nova."""
    global _ativa
    _ativa = ESCURO if escuro else CLARO
    return _ativa


def e_escuro():
    return _ativa is ESCURO


def _esp(chave, densidade_nome):
    """Valor da escala de espaço do MegUI, pelo multiplicador da densidade."""
    k = DENSIDADES[densidade_nome]["multiplicador"]
    return max(1, round(megui.ESPACO[chave] * k))


def _pad(yx, menos=0):
    y, x = yx
    return "%dpx %dpx" % (max(y - menos, 0), max(x - menos, 0))


_QSS = Template("""
QWidget {
    background: $bg;
    color: $ink;
    font-family: $font_ui;
    font-size: ${fonte}px;
}
QMainWindow, QDialog { background: $bg; }

/* ------------------------------------------------- barra de título
   A janela continua nativa (ver janela_custom): a faixa só desenha. Os
   botões têm fundo próprio no hover para dar retorno de clique, já que o
   resto da barra é área de arrasto do Windows. */
QWidget#barraTitulo {
    background: $surface_2;
    border-bottom: 1px solid $border;
}
QWidget#barraTitulo QLabel { background: transparent; }
QLabel[role="tituloApp"] { color: $ink; font-weight: 700; }
QLabel[role="tituloCtx"] { color: $ink_2; }
QWidget#barraTitulo QToolButton {
    background: transparent; color: $ink_2;
    border: none; border-radius: 0; padding: 0; font-size: ${corpo}px;
}
/* glifos da fonte de ícones do Windows: mesmo peso e tamanho nos três */
QWidget#barraTitulo QToolButton[iconfont="mdl2"] {
    font-family: "Segoe MDL2 Assets"; font-size: ${dica}px;
}
QWidget#barraTitulo QToolButton:hover { background: $border; color: $ink; }
QWidget#barraTitulo QToolButton#btn_fechar:hover { background: $bad; color: $on_bad; }

/* ------------------------------------------------------ barra de ações */
QToolBar {
    background: $surface_2;
    border: none;
    border-bottom: 1px solid $border;
    padding: ${esp_meio}px ${esp_1}px;
    spacing: ${esp_meio}px;
}
QToolBar::separator { background: $border_2; width: 1px; margin: ${esp_1}px ${esp_2}px; }
QToolButton {
    background: transparent;
    color: $ink_2;
    border: 1px solid transparent;
    border-radius: ${raio}px;
    padding: $pad_botao;
    min-height: ${min_controle}px;
}
QToolButton:hover { background: $surface; color: $ink; border-color: $border_2; }
QToolButton:pressed { background: $border; }
QToolButton:focus { border: 2px solid $focus; padding: $pad_botao_foco; }
QToolButton:disabled { color: $ink_3; }
/* interruptor (painel Empresas aberto): estado, não clique que passou */
QToolBar QToolButton:checked {
    background: $accent_soft; color: $ink;
    border: 1px solid $accent_linha; font-weight: 700;
}

QMenu { background: $surface; color: $ink; border: 1px solid $border_2; padding: ${esp_1}px; }
QMenu::item { padding: ${esp_2}px ${esp_6}px ${esp_2}px ${esp_3}px; border-radius: ${raio}px; }
QMenu::item:selected { background: $accent_soft; color: $ink; }
QMenu::item:disabled { color: $ink_3; }
QMenu::separator { height: 1px; background: $border; margin: ${esp_1}px ${esp_2}px; }

QStatusBar {
    background: $surface_2; color: $ink_2; border-top: 1px solid $border;
    min-height: ${rodape}px; max-height: ${rodape}px;
}
QStatusBar::item { border: none; }

/* ---------------------------------------------------------------- abas */
QTabWidget::pane {
    background: $surface; border: 1px solid $border;
    border-radius: ${raio}px; top: -1px;
}
QTabBar::tab {
    background: $sunken;
    color: $ink_2;
    border: 1px solid $border;
    border-bottom: none;
    border-top-left-radius: ${raio}px;
    border-top-right-radius: ${raio}px;
    padding: $pad_aba;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: $surface; color: $ink; font-weight: 700;
    border-top: 2px solid $accent_linha;
}
QTabBar::tab:hover:!selected { color: $ink; background: $surface_2; }
QTabBar:focus { outline: none; }
QTabBar::tab:selected:focus { border: 2px solid $focus; border-bottom: none; }

/* -------------------------------------------------------------- grades
   Seleção = fundo suave + linha de acento em cima e embaixo da célula; numa
   linha inteira selecionada, as linhas se juntam num contorno. O texto é
   preservado em vez de fundo sólido: o valor não pode sumir. */
QTableWidget, QTableView {
    background: $surface;
    alternate-background-color: $linha_alt;
    color: $ink;
    gridline-color: $border;
    border: 1px solid $border_2;
    border-radius: ${raio}px;
    selection-background-color: $accent_soft;
    selection-color: $ink;
    outline: none;
}
QTableWidget:focus, QTableView:focus { border: 1px solid $focus; }
QTableWidget::item, QTableView::item { padding: $pad_celula; }
QTableWidget::item:selected, QTableView::item:selected {
    background: $accent_soft;
    color: $ink;
    border-top: 1px solid $accent_linha;
    border-bottom: 1px solid $accent_linha;
}
QTableWidget::item:focus, QTableView::item:focus { border: 1px solid $focus; }
QTableWidget QLineEdit, QTableView QLineEdit {
    border: 2px solid $focus; border-radius: 0; padding: 0 2px;
}

QHeaderView::section {
    background: $surface_2;
    color: $ink_2;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 1px solid $border_2;
    padding: $pad_cabecalho;
    font-weight: 700;
}
QHeaderView::section:hover { background: $border; color: $ink; }
QHeaderView::section:vertical { border-right: 1px solid $border_2; font-weight: 400; }
QTableCornerButton::section {
    background: $surface_2; border: none; border-bottom: 1px solid $border_2;
}

QTreeWidget, QTreeView, QListWidget, QListView {
    background: $sunken;
    color: $ink;
    border: 1px solid $border_2;
    border-radius: ${raio}px;
    outline: none;
}
QTreeWidget:focus, QTreeView:focus, QListWidget:focus, QListView:focus {
    border: 1px solid $focus;
}
QTreeWidget::item:selected, QTreeView::item:selected,
QListWidget::item:selected, QListView::item:selected {
    background: $accent_soft; color: $ink;
    border-left: 3px solid $accent_linha;
}

/* ------------------------------------------------------------- rótulos
   Papel visual = propriedade dinâmica `role`. Trocá-la depois que o widget
   apareceu exige unpolish/polish: use comum.definir_papel. */
QLabel { background: transparent; color: $ink; }
QLabel[role="secao"] { font-weight: 700; letter-spacing: 1px; }
QLabel[role="info"] { color: $ink_2; }
QLabel[role="dica"] { color: $ink_2; }
QLabel[role="desabilitado"] { color: $ink_3; }
QLabel[role="mono"] { font-family: $font_mono; color: $ink_2; }
QLabel[role="link"] { color: $accent_text; text-decoration: underline; }
QLabel[role="ok"] { color: $ok; font-weight: bold; }
QLabel[role="aviso"] { color: $warn; font-weight: bold; }
QLabel[role="erro"] { color: $bad; font-weight: bold; }
QLabel[role="tituloInicial"] { color: $ink; font-size: ${destaque}px; font-weight: 700; }
QLabel[role="solte"] {
    color: $ink_2; border: 2px dashed $field_border; border-radius: ${raio}px; padding: ${esp_3}px;
}
QLabel[role="produto"] { color: $produto; font-weight: bold; padding: 0 ${esp_2}px; }

/* ------------------------------------------------------------- botões
   Botão se identifica pelo texto; a borda é decorativa (border_2). */
QPushButton {
    background: $surface;
    color: $ink;
    border: 1px solid $border_2;
    border-radius: ${raio}px;
    padding: $pad_botao;
    min-height: ${min_controle}px;
}
QPushButton:hover { background: $surface_2; }
QPushButton:pressed { background: $border; }
QPushButton:focus { border: 2px solid $focus; padding: $pad_botao_foco; }
QPushButton:disabled { background: $bg; color: $ink_3; border-color: $border; }
QPushButton[role="accent"] {
    background: $accent; color: $on_accent;
    border: 1px solid $accent; font-weight: 700;
}
QPushButton[role="accent"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[role="accent"]:focus { border: 2px solid $focus; }
QPushButton[role="accent"]:disabled {
    background: $border_2; border-color: $border_2; color: $ink_2;
}
QPushButton[role="perigo"] { background: transparent; color: $bad; border: 1px solid $bad; }
QPushButton[role="perigo"]:hover { background: $bad; color: $on_bad; }
/* botão dentro de célula (setCellWidget): cabe na altura da linha, com
   folga em volta, em vez de ocupar a célula inteira com o padding normal */
QAbstractItemView QPushButton {
    padding: 0 ${esp_2}px; margin: ${esp_meio}px ${esp_1}px; min-height: 0;
    border-radius: ${raio}px; font-size: ${fonte_celula}px;
}
QAbstractItemView QPushButton:focus { padding: 0 ${esp_2_foco}px; }

/* ------------------------------------------------------------- campos
   Limite de campo = field_border (>= 3:1). Campo com erro: propriedade
   erro="true" + mensagem com ícone ao lado (comum.marcar_erro), nunca só a
   cor. */
QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit,
QPlainTextEdit, QTextEdit {
    background: $sunken;
    color: $ink;
    border: 1px solid $field_border;
    border-radius: ${raio}px;
    padding: $pad_campo;
    min-height: ${min_controle}px;
    selection-background-color: $accent_soft;
    selection-color: $ink;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
QDateTimeEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 2px solid $focus; padding: $pad_campo_foco;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled {
    background: $bg; color: $ink_3; border-color: $border;
}
QLineEdit[mono="true"] { font-family: $font_mono; }
QLineEdit[erro="true"], QSpinBox[erro="true"], QDoubleSpinBox[erro="true"],
QDateEdit[erro="true"], QComboBox[erro="true"], QPlainTextEdit[erro="true"] {
    border: 2px solid $bad; background: $bad_soft; padding: $pad_campo_foco;
}

QComboBox {
    background: $surface;
    color: $ink;
    border: 1px solid $field_border;
    border-radius: ${raio}px;
    padding: $pad_campo;
    min-height: ${min_controle}px;
}
QComboBox:focus { border: 2px solid $focus; padding: $pad_campo_foco; }
QComboBox:disabled { background: $bg; color: $ink_3; border-color: $border; }
QComboBox::drop-down { border: none; width: ${esp_6}px; }
QComboBox::down-arrow { image: url("$chevron"); width: ${esp_3}px; height: ${esp_3}px; }
QComboBox::down-arrow:disabled { image: url("$chevron_off"); }
QComboBox QAbstractItemView {
    background: $surface; color: $ink; border: 1px solid $border_2;
    selection-background-color: $accent_soft; selection-color: $ink;
    outline: none; padding: ${esp_meio}px;
}

QCheckBox, QRadioButton { background: transparent; color: $ink; spacing: ${esp_2}px; }
QCheckBox:disabled, QRadioButton:disabled { color: $ink_3; }
QCheckBox::indicator {
    width: ${caixa}px; height: ${caixa}px;
    border: 1px solid $field_border;
    border-radius: ${raio}px;
    background: $surface;
}
QCheckBox::indicator:hover { border-color: $accent_linha; }
QCheckBox::indicator:focus { border: 2px solid $focus; width: ${caixa_foco}px; height: ${caixa_foco}px; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent_linha; image: url("$check"); }
QCheckBox::indicator:checked:focus { border: 2px solid $focus; }
QCheckBox::indicator:disabled { background: $bg; border-color: $border; }

QGroupBox {
    background: transparent; border: 1px solid $border;
    border-radius: ${raio}px; margin-top: ${esp_3}px; padding-top: ${esp_2}px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: ${esp_2}px; padding: 0 ${esp_1}px;
    color: $ink_2; font-weight: 700;
}

/* -------------------------------------------------------------- barras */
QProgressBar {
    background: $surface_2; border: 1px solid $border;
    border-radius: ${raio}px; min-height: ${esp_4}px; text-align: center; color: $ink;
}
QProgressBar::chunk { background: $accent; border-radius: ${raio}px; }

QScrollBar:vertical { background: $bg; width: ${esp_3}px; margin: 0; }
QScrollBar::handle:vertical { background: $border_2; border-radius: ${raio}px; min-height: ${esp_6}px; }
QScrollBar::handle:vertical:hover { background: $ink_3; }
QScrollBar:horizontal { background: $bg; height: ${esp_3}px; margin: 0; }
QScrollBar::handle:horizontal { background: $border_2; border-radius: ${raio}px; min-width: ${esp_6}px; }
QScrollBar::handle:horizontal:hover { background: $ink_3; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: $border; }
QSplitter::handle:hover { background: $accent_linha; }

QDockWidget { color: $ink; }
QDockWidget::title {
    background: $surface_2; padding: ${esp_1}px ${esp_2}px; border-bottom: 1px solid $border;
}

/* ------------------------------------------------------------ diversos */
QFrame[role="divisor"] { background: $border; max-height: 1px; border: none; }
QToolTip {
    background: $inverse_surface; color: $on_inverse_surface;
    border: none; padding: ${esp_1}px ${esp_2}px;
}
QMessageBox { background: $bg; }
QMessageBox QLabel { color: $ink; }
""")


def valores(paleta=None, densidade_nome=None):
    """Dicionário de substituição do template (útil para testes)."""
    from sped_tables.interface import icones
    p = paleta or _ativa
    nome = densidade_nome or _densidade
    tipo = megui.ESCALA_TIPO
    v = {k: getattr(p, k) for k in p.__dataclass_fields__ if k != "nome"}
    v.update(icones.caminhos(p))
    pads = {k: (_esp(y, nome), _esp(x, nome))
            for k, (y, x) in _PADDINGS.items()}
    # altura do controle (botão, campo) = conteúdo + padding + 1 px de borda
    # em cima e embaixo; o foco troca 1 px de padding por 1 px de borda
    controle = DENSIDADES[nome]["alturaControle"]
    v.update({"esp_" + k: _esp(k, nome) for k in megui.ESPACO})
    v.update(
        font_ui=FONT_UI, font_mono=FONT_MONO, fonte=tipo["corpo"]["px"],
        corpo=tipo["corpo"]["px"], dica=tipo["dica"]["px"],
        destaque=tipo["destaque"]["px"], raio=megui.RAIO,
        fonte_celula=tipo["dica"]["px"],
        min_controle=controle - 2 * pads["botao"][0] - 2,
        rodape=megui.LAYOUT["rodape"],
        caixa=_esp("4", "normal"), caixa_foco=_esp("4", "normal") - 2,
        esp_2_foco=_esp("2", nome) - 1,
        pad_celula=_pad(pads["celula"]), pad_aba=_pad(pads["aba"]),
        pad_cabecalho=_pad(pads["cabecalho"]),
        pad_botao=_pad(pads["botao"]), pad_botao_foco=_pad(pads["botao"], 1),
        pad_campo=_pad(pads["campo"]), pad_campo_foco=_pad(pads["campo"], 1),
    )
    return v


def folha_estilo():
    """Folha de estilo completa, com os ícones desenhados em runtime."""
    return _QSS.substitute(valores())

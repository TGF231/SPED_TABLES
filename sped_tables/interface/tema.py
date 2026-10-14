# -*- coding: utf-8 -*-
"""Paleta e folha de estilo (QSS) do SPED Tables.

É a **assinatura visual** compartilhada pelas ferramentas da família (kit
`minha-ui`, `desktop-pyside6`): acento vinho `#7D0E0E`, neutros com viés
azulado e as cores semânticas (ok/aviso/erro) separadas do acento, para que
"atenção" nunca se confunda com "isto é clicável". Os valores das paletas são
os dos tokens do kit; o único token próprio daqui é `produto` (o nome do
produto no topo das grades C170).

O uso de cada token é um contrato de contraste:

* `ink_3` é **restrito** — texto desabilitado, placeholder sem informação ou
  texto grande. Passa 3:1, não 4,5:1: dica que a pessoa precisa ler é
  `ink_2`;
* limite de campo é `field_border`, nunca `border_2` (que é decorativo);
* foco é `focus`, com borda de 2 px;
* seleção tem **dois** sinais: o fundo `accent_soft` e uma linha de acento —
  o fundo sozinho tem contraste ~1,2:1 e não basta;
* acento e erro são dois vermelhos: erro vai sempre com ícone e texto.

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

# ------------------------------------------------------------------ fontes
FONT_UI = '"Segoe UI", system-ui, "Roboto", "Noto Sans", sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", ui-monospace, monospace'


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
    ink_2: str            # texto secundário (dicas que se leem)
    ink_3: str            # RESTRITO: desabilitado, placeholder, texto grande
    border: str           # linha de grade e divisórias
    border_2: str         # contorno decorativo; NÃO é limite de campo
    field_border: str     # limite de campo/controle (>= 3:1)
    accent: str           # ação primária, checkbox marcado, aba ativa
    accent_hover: str     # hover do acento (texto branco por cima)
    accent_soft: str      # fundo de seleção (sempre com linha de acento)
    on_accent: str        # texto sobre o acento
    accent_text: str      # acento como texto ou link (>= 4,5:1)
    focus: str            # borda de foco (>= 3:1 contra todos os fundos)
    ok: str               # confere / sem divergência
    warn: str             # atenção / sem regra cadastrada
    bad: str              # divergência / erro
    on_bad: str           # texto sobre bad
    bad_soft: str         # fundo de campo com erro
    info: str             # chave estrutural (coluna REG), links neutros
    inverse_surface: str  # fundo de tooltip
    on_inverse_surface: str
    produto: str          # nome do produto no topo das grades C170


CLARO = Paleta(
    nome="claro",
    bg="#F4F6F8",
    surface="#FFFFFF",
    surface_2="#E9EDF1",
    sunken="#FBFCFD",
    linha_alt="#F7F9FB",
    somente_leitura="#EFF2F5",
    ink="#16202A",
    ink_2="#4A5A6A",
    ink_3="#74848F",
    border="#D2DAE2",
    border_2="#BAC5D0",
    field_border="#748AA0",
    accent="#7D0E0E",
    accent_hover="#5C0A0A",
    accent_soft="#F6E7E6",
    on_accent="#FFFFFF",
    accent_text="#7D0E0E",
    focus="#7D0E0E",
    ok="#14793A",
    warn="#975C07",
    bad="#C92A1E",
    on_bad="#FFFFFF",
    bad_soft="#FCE8E6",
    info="#1565C0",
    inverse_surface="#16202A",
    on_inverse_surface="#FFFFFF",
    produto="#2E7D32",
)

ESCURO = Paleta(
    nome="escuro",
    bg="#0F1620",
    surface="#18212C",
    surface_2="#212C39",
    sunken="#131C25",
    linha_alt="#1C2632",
    somente_leitura="#222C38",
    ink="#E3E9EF",
    ink_2="#94A4B5",
    ink_3="#6E7F91",
    border="#2B3745",
    border_2="#3A4857",
    field_border="#5F768E",
    accent="#D43A34",
    accent_hover="#B82C26",
    accent_soft="#2E1616",
    on_accent="#FFFFFF",
    accent_text="#E0716D",
    focus="#E0716D",
    ok="#4ADE80",
    warn="#FBBF24",
    bad="#FF8A8A",
    on_bad="#1A0505",
    bad_soft="#3A1414",
    info="#60A5FA",
    inverse_surface="#E3E9EF",
    on_inverse_surface="#18212C",
    produto="#86EFAC",
)

# ------------------------------------------------------------- densidade
# Numa tela apertada, alguns pixels de padding a menos por célula valem uma
# coluna inteira a mais visível numa grade de SPED. A densidade só mexe em
# espaçamento e corpo de fonte (px) — cor e borda seguem iguais nas duas.
# Valores (y, x) para padding.
DENSIDADES = {
    "normal": {"fonte": 12, "celula": (2, 4), "aba": (6, 14),
               "botao": (5, 13), "campo": (4, 7), "cabecalho": (5, 6)},
    "compacta": {"fonte": 11, "celula": (1, 3), "aba": (4, 10),
                 "botao": (4, 10), "campo": (3, 5), "cabecalho": (3, 5)},
}
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
    border: none; border-radius: 0; padding: 0; font-size: 11pt;
}
/* glifos da fonte de ícones do Windows: mesmo peso e tamanho nos três */
QWidget#barraTitulo QToolButton[iconfont="mdl2"] {
    font-family: "Segoe MDL2 Assets"; font-size: 10px;
}
QWidget#barraTitulo QToolButton:hover { background: $border; color: $ink; }
QWidget#barraTitulo QToolButton#btn_fechar:hover { background: $bad; color: $on_bad; }

/* ------------------------------------------------------ barra de ações */
QToolBar {
    background: $surface_2;
    border: none;
    border-bottom: 1px solid $border;
    padding: 3px 4px;
    spacing: 2px;
}
QToolBar::separator { background: $border_2; width: 1px; margin: 4px 6px; }
QToolButton {
    background: transparent;
    color: $ink_2;
    border: 1px solid transparent;
    border-radius: ${raio}px;
    padding: 5px 11px;
    min-height: 14px;
}
QToolButton:hover { background: $surface; color: $ink; border-color: $border_2; }
QToolButton:pressed { background: $border; }
QToolButton:focus { border: 2px solid $focus; padding: 4px 10px; }
QToolButton:disabled { color: $ink_3; }
/* interruptor (painel Empresas aberto): estado, não clique que passou */
QToolBar QToolButton:checked {
    background: $accent_soft; color: $ink;
    border: 1px solid $accent; font-weight: 600;
}

QMenu { background: $surface; color: $ink; border: 1px solid $border_2; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 3px; }
QMenu::item:selected { background: $accent_soft; color: $ink; }
QMenu::item:disabled { color: $ink_3; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

QStatusBar { background: $surface_2; color: $ink_2; border-top: 1px solid $border; }
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
    background: $surface; color: $ink; font-weight: 600;
    border-top: 2px solid $accent;
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
    border-top: 1px solid $accent;
    border-bottom: 1px solid $accent;
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
    font-weight: 600;
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
    border-left: 3px solid $accent;
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
QLabel[role="tituloInicial"] { color: $ink; font-size: 15pt; font-weight: 700; }
QLabel[role="solte"] {
    color: $ink_2; border: 2px dashed $field_border; border-radius: 6px; padding: 10px;
}
QLabel[role="produto"] { color: $produto; font-weight: bold; padding: 0 8px; }

/* ------------------------------------------------------------- botões
   Botão se identifica pelo texto; a borda é decorativa (border_2). */
QPushButton {
    background: $surface;
    color: $ink;
    border: 1px solid $border_2;
    border-radius: ${raio}px;
    padding: $pad_botao;
    min-height: 16px;
}
QPushButton:hover { background: $surface_2; }
QPushButton:pressed { background: $border; }
QPushButton:focus { border: 2px solid $focus; padding: $pad_botao_foco; }
QPushButton:disabled { background: $bg; color: $ink_3; border-color: $border; }
QPushButton[role="accent"] {
    background: $accent; color: $on_accent;
    border: 1px solid $accent; font-weight: 600;
}
QPushButton[role="accent"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[role="accent"]:focus { border: 2px solid $focus; }
QPushButton[role="accent"]:disabled {
    background: $border_2; border-color: $border_2; color: $ink_2;
}
QPushButton[role="perigo"] { background: transparent; color: $bad; border: 1px solid $bad; }
QPushButton[role="perigo"]:hover { background: $bad; color: $on_bad; }

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
}
QComboBox:focus { border: 2px solid $focus; padding: $pad_campo_foco; }
QComboBox:disabled { background: $bg; color: $ink_3; border-color: $border; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { image: url("$chevron"); width: 12px; height: 12px; }
QComboBox::down-arrow:disabled { image: url("$chevron_off"); }
QComboBox QAbstractItemView {
    background: $surface; color: $ink; border: 1px solid $border_2;
    selection-background-color: $accent_soft; selection-color: $ink;
    outline: none; padding: 2px;
}

QCheckBox, QRadioButton { background: transparent; color: $ink; spacing: 7px; }
QCheckBox:disabled, QRadioButton:disabled { color: $ink_3; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid $field_border;
    border-radius: 3px;
    background: $surface;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:focus { border: 2px solid $focus; width: 12px; height: 12px; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$check"); }
QCheckBox::indicator:checked:focus { border: 2px solid $focus; }
QCheckBox::indicator:disabled { background: $bg; border-color: $border; }

QGroupBox {
    background: transparent; border: 1px solid $border;
    border-radius: ${raio}px; margin-top: 10px; padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 9px; padding: 0 5px;
    color: $ink_2; font-weight: 600;
}

/* -------------------------------------------------------------- barras */
QProgressBar {
    background: $surface_2; border: 1px solid $border;
    border-radius: 7px; min-height: 14px; text-align: center; color: $ink;
}
QProgressBar::chunk { background: $accent; border-radius: 6px; }

QScrollBar:vertical { background: $bg; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: $border_2; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $ink_3; }
QScrollBar:horizontal { background: $bg; height: 11px; margin: 0; }
QScrollBar::handle:horizontal { background: $border_2; border-radius: 5px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: $ink_3; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: $border; }
QSplitter::handle:hover { background: $accent; }

QDockWidget { color: $ink; }
QDockWidget::title {
    background: $surface_2; padding: 4px 8px; border-bottom: 1px solid $border;
}

/* ------------------------------------------------------------ diversos */
QFrame[role="divisor"] { background: $border; max-height: 1px; border: none; }
QToolTip {
    background: $inverse_surface; color: $on_inverse_surface;
    border: none; padding: 5px 7px;
}
QMessageBox { background: $bg; }
QMessageBox QLabel { color: $ink; }
""")


def valores(paleta=None, densidade_nome=None):
    """Dicionário de substituição do template (útil para testes)."""
    from sped_tables.interface import icones
    p = paleta or _ativa
    d = DENSIDADES[densidade_nome or _densidade]
    v = {k: getattr(p, k) for k in p.__dataclass_fields__ if k != "nome"}
    v.update(icones.caminhos(p))
    v.update(
        font_ui=FONT_UI, font_mono=FONT_MONO, fonte=d["fonte"], raio=4,
        pad_celula=_pad(d["celula"]), pad_aba=_pad(d["aba"]),
        pad_cabecalho=_pad(d["cabecalho"]),
        pad_botao=_pad(d["botao"]), pad_botao_foco=_pad(d["botao"], 1),
        pad_campo=_pad(d["campo"]), pad_campo_foco=_pad(d["campo"], 1),
    )
    return v


def folha_estilo():
    """Folha de estilo completa, com os ícones desenhados em runtime."""
    return _QSS.substitute(valores())

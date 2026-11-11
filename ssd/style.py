"""Couleurs et feuille de style de l'IHM (thème sombre de salle de contrôle)."""

FOND = "#12161c"
PANNEAU = "#1a2029"
BORD = "#2b3442"
TEXTE = "#e4e8ee"
TEXTE_DISCRET = "#8b96a7"
BLEU = "#5aa2ff"
VERT = "#35c58a"
ORANGE = "#f0a53a"
ROUGE = "#ff5d5d"

FEUILLE = f"""
QWidget {{ background: {FOND}; color: {TEXTE}; font-size: 10pt; }}
QGroupBox {{
    background: {PANNEAU}; border: 1px solid {BORD}; border-radius: 6px;
    margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
    color: {TEXTE_DISCRET}; background: {FOND};
}}
QGroupBox QWidget {{ background: transparent; }}
QLabel[role="discret"] {{ color: {TEXTE_DISCRET}; font-size: 9pt; font-weight: 400; }}
QLabel[role="titre"] {{ color: {TEXTE_DISCRET}; font-size: 9pt; font-weight: 600; }}
QPushButton {{
    background: #263142; border: 1px solid #3a475a; border-radius: 5px;
    padding: 7px 10px; font-weight: 600;
}}
QPushButton:hover {{ background: #31405a; }}
QPushButton:pressed {{ background: #1f2836; }}
QPushButton:focus {{ border: 1px solid {BLEU}; }}
QPushButton#arret {{
    background: #b3262d; border: 1px solid #e0535a; color: white;
    font-size: 13pt; padding: 12px;
}}
QPushButton#arret:hover {{ background: #cf3038; }}
QPushButton#arret:pressed {{ background: #8f1d23; }}
QLineEdit, QComboBox {{
    background: #0e1217; border: 1px solid {BORD}; border-radius: 4px;
    padding: 5px 6px; selection-background-color: {BLEU};
}}
QGroupBox QLineEdit, QGroupBox QComboBox {{ background: #0e1217; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {BLEU}; }}
QComboBox QAbstractItemView {{ background: {PANNEAU}; selection-background-color: #31405a; }}
QPlainTextEdit, QTableWidget, QListWidget {{
    background: #0e1217; border: 1px solid {BORD}; border-radius: 4px;
}}
QGroupBox QPlainTextEdit, QGroupBox QTableWidget, QGroupBox QListWidget {{ background: #0e1217; }}
QTableWidget {{ gridline-color: #1f2630; }}
QTableWidget::item {{ padding: 2px 6px; }}
QHeaderView::section {{
    background: {PANNEAU}; color: {TEXTE_DISCRET}; border: none;
    border-bottom: 1px solid {BORD}; padding: 4px 6px; font-weight: 600;
}}
QTabWidget::pane {{ border: 1px solid {BORD}; border-radius: 4px; top: -1px; }}
QTabBar::tab {{
    background: {FOND}; color: {TEXTE_DISCRET}; padding: 7px 16px;
    border: 1px solid transparent; border-bottom: none;
}}
QTabBar::tab:selected {{
    background: {PANNEAU}; color: {TEXTE}; border-color: {BORD};
    border-top-left-radius: 4px; border-top-right-radius: 4px;
}}
QStatusBar {{ background: {PANNEAU}; color: {TEXTE_DISCRET}; border-top: 1px solid {BORD}; }}
QStatusBar QLabel {{ background: transparent; color: {TEXTE_DISCRET}; padding: 0 8px; }}
QSplitter::handle {{ background: {FOND}; }}
QScrollBar:vertical {{ background: {FOND}; width: 10px; }}
QScrollBar::handle:vertical {{ background: #364152; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {FOND}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: #364152; border-radius: 4px; min-width: 24px; }}
"""

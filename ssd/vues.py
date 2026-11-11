"""Vues secondaires de l'IHM : journal, données instrument, courbes des HK."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from html import escape

import pyqtgraph as pg
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from . import style
from .icd import CHAMPS_HK, Acteur
from .messages import HK, DonneeInstrument, formater_date


def police_fixe():
    police = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    police.setPointSize(9)
    return police


def creer_graphique(unite: str = "") -> pg.PlotWidget:
    """Graphique temporel (axe des abscisses en heure UTC)."""
    axe = pg.DateAxisItem(orientation="bottom", utcOffset=0)
    graphique = pg.PlotWidget(axisItems={"bottom": axe}, background="#0e1217")
    graphique.showGrid(x=True, y=True, alpha=0.18)
    graphique.setMenuEnabled(False)
    for nom in ("left", "bottom"):
        graphique.getAxis(nom).setPen(style.BORD)
        graphique.getAxis(nom).setTextPen(style.TEXTE_DISCRET)
    if unite:
        graphique.setLabel("left", unite, color=style.TEXTE_DISCRET)
    return graphique


class VueJournal(QPlainTextEdit):
    """Affichage du journal des commandes et des événements [EX-IHM-150]."""

    _COULEURS = {"COMMANDE": style.BLEU, "ALERTE": style.ROUGE,
                 "ERREUR": style.ORANGE, "EVENEMENT": style.TEXTE_DISCRET}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        self.setFont(police_fixe())

    def ajouter(self, date: datetime, categorie: str, evenement: str) -> None:
        couleur = self._COULEURS.get(categorie, style.TEXTE)
        marge = "&nbsp;" * max(1, 11 - len(categorie))
        self.appendHtml(
            f'<span style="color:{style.TEXTE_DISCRET}">{formater_date(date)}</span>'
            f'&nbsp;&nbsp;<span style="color:{couleur}">{categorie}</span>{marge}'
            f'{escape(evenement)}')


class ConsoleInstrument(QWidget):
    """Données reçues de l'instrument, au fil de l'eau [EX-IHM-070]."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nbMessages = 0
        self.nbOctets = 0
        self._chemin = ""
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(8, 8, 8, 8)
        self._resume = QLabel("Aucune donnée reçue")
        self._resume.setProperty("role", "discret")
        disposition.addWidget(self._resume)
        self._texte = QPlainTextEdit()
        self._texte.setReadOnly(True)
        self._texte.setMaximumBlockCount(2000)
        self._texte.setFont(police_fixe())
        self._texte.setLineWrapMode(QPlainTextEdit.NoWrap)
        disposition.addWidget(self._texte, 1)

    def definirFichier(self, chemin: str) -> None:
        self._chemin = chemin
        self._actualiser()

    def ajouter(self, d: DonneeInstrument) -> None:
        self.nbMessages += 1
        self.nbOctets += len(d.mesures)
        lignes = [f"{formater_date(d.date, True)} UTC   {len(d.mesures)} octets"]
        for debut in range(0, len(d.mesures), 16):
            bloc = d.mesures[debut:debut + 16]
            texte = "".join(chr(o) if 32 <= o < 127 else "." for o in bloc)
            lignes.append(f"  {debut:04X}  {bloc.hex(' ').upper():<47}  |{texte}|")
        self._texte.appendPlainText("\n".join(lignes))
        self._texte.horizontalScrollBar().setValue(0)
        self._actualiser()

    def _actualiser(self) -> None:
        if self.nbMessages:
            ko = f"{self.nbOctets / 1000:.1f}".replace(".", ",")
            texte = (f"{self.nbMessages} messages · {ko} Ko reçus depuis le démarrage"
                     "  ·  date GNSS de la PFP, puis octets en hexadécimal et en ASCII")
        else:
            texte = "Aucune donnée reçue"
        if self._chemin:
            texte += f"\nEnregistré dans : {self._chemin}"
        self._resume.setText(texte)


class CourbesHK(QWidget):
    """Courbe d'un paramètre de HK au choix, sur l'historique de la session."""

    HISTORIQUE = 5000          # points conservés par paramètre

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._historique: dict[str, deque] = {}
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(8, 8, 8, 8)
        ligne = QHBoxLayout()
        etiquette = QLabel("Paramètre :")
        etiquette.setProperty("role", "titre")
        ligne.addWidget(etiquette)
        self.choix = QComboBox()
        for source, champs in CHAMPS_HK.items():
            for champ in champs:
                if champ.numerique:
                    cle = f"{source.name}:{champ.nom}"
                    self._historique[cle] = deque(maxlen=self.HISTORIQUE)
                    unite = f" ({champ.unite})" if champ.unite else ""
                    self.choix.addItem(f"{source.name} · {champ.libelle}{unite}", cle)
        self.choix.currentIndexChanged.connect(self._tracer)
        ligne.addWidget(self.choix, 1)
        disposition.addLayout(ligne)
        self._graphique = creer_graphique()
        self._courbe = self._graphique.plot(
            pen=pg.mkPen(style.BLEU, width=2), symbol="o", symbolSize=4,
            symbolBrush=style.BLEU, symbolPen=None)
        disposition.addWidget(self._graphique, 1)

    def selectionner(self, source: Acteur, nom: str) -> None:
        index = self.choix.findData(f"{source.name}:{nom}")
        if index >= 0:
            self.choix.setCurrentIndex(index)

    def ajouter(self, hk: HK) -> None:
        instant = hk.date.timestamp()
        prefixe = f"{hk.source.name}:"
        for nom, valeur in hk.mesures.items():
            points = self._historique.get(prefixe + nom)
            if points is not None:
                points.append((instant, valeur))
        if str(self.choix.currentData()).startswith(prefixe):
            self._tracer()

    def _tracer(self) -> None:
        points = self._historique.get(self.choix.currentData(), ())
        self._courbe.setData([p[0] for p in points], [p[1] for p in points])

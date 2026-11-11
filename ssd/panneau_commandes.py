"""PanneauCommandes : commandes de l'opérateur (diagramme de classes).

Couvre CU1 (piloter la PFP), CU2 (consigne de distance) et CU3 (instrument).
Le panneau ne connaît pas le réseau : il émet ``commandeDemandee`` et l'IHM
se charge de l'envoi et du journal.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from . import style
from .icd import DISTANCE_MAX_M, TypeCommande
from .messages import Commande

_FINS_DE_LIGNE = {"Aucune": b"", "CR": b"\r", "LF": b"\n", "CR + LF": b"\r\n"}


class PanneauCommandes(QWidget):
    """Boutons et saisies de commande."""

    DISTANCE_MAX = DISTANCE_MAX_M          # m [EX-IHM-110]

    #: une commande valide est prête à être envoyée (objet Commande)
    commandeDemandee = Signal(object)
    #: une saisie a été refusée (texte pour le journal)
    saisieRefusee = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.consigneDistance = 0.0        # dernière consigne acceptée (m)
        self._construire()

    # ------------------------------------------------------------------
    # Interface du diagramme de classes
    # ------------------------------------------------------------------

    def descendre(self) -> None:                                   # EX-IHM-030
        self.commandeDemandee.emit(Commande(TypeCommande.DESCENTE))

    def monter(self) -> None:                                      # EX-IHM-030
        self.commandeDemandee.emit(Commande(TypeCommande.MONTEE))

    def arreterMouvement(self) -> None:                            # EX-IHM-120
        self.commandeDemandee.emit(Commande(TypeCommande.ARRET))

    def verifierConsigne(self, d: float) -> bool:                  # EX-IHM-110
        """Vrai si la consigne est un nombre compris entre 0 et DISTANCE_MAX."""
        try:
            d = float(d)
        except (TypeError, ValueError):
            return False
        return math.isfinite(d) and 0.0 <= d <= self.DISTANCE_MAX

    def envoyerConsigne(self, d: float) -> bool:                   # EX-IHM-040
        """Envoie la consigne si elle est valide. Retourne False si refusée."""
        if not self.verifierConsigne(d):
            self._refuser(self._messageConsigne,
                          f"Consigne refusée : {d} (attendu : 0 à "
                          f"{self.DISTANCE_MAX:.0f} m)")
            return False
        self.consigneDistance = float(d)
        self._informer(self._messageConsigne,
                       f"Consigne acceptée : {self.consigneDistance:.1f} m".replace(".", ","))
        self.commandeDemandee.emit(
            Commande(TypeCommande.CONSIGNE_DISTANCE, self.consigneDistance))
        return True

    def mettreInstrumentSousTension(self) -> None:                 # EX-IHM-050
        self.commandeDemandee.emit(Commande(TypeCommande.INSTRUMENT_ON))

    def mettreInstrumentHorsTension(self) -> None:                 # EX-IHM-050
        self.commandeDemandee.emit(Commande(TypeCommande.INSTRUMENT_OFF))

    def envoyerCommandeInstrument(self, c: str, hexadecimal: bool = False,
                                  finDeLigne: bytes = b"") -> bool:  # EX-IHM-060
        """Envoie une commande à l'instrument.

        ``c`` est un texte ASCII, ou une suite d'octets en hexadécimal
        (« 01 A0 FF ») si ``hexadecimal`` est vrai. Retourne False si refusée.
        """
        try:
            charge = bytes.fromhex(c) if hexadecimal else c.encode("ascii") + finDeLigne
        except ValueError:
            attendu = "octets en hexadécimal, ex. 01 A0 FF" if hexadecimal else "texte ASCII"
            self._refuser(self._messageInstrument,
                          f"Commande instrument refusée : « {c} » ({attendu})")
            return False
        if not charge:
            self._refuser(self._messageInstrument, "Commande instrument refusée : vide")
            return False
        if len(charge) > Commande.TAILLE_MAX_CHARGE:
            self._refuser(self._messageInstrument,
                          f"Commande instrument refusée : {len(charge)} octets "
                          f"(maximum {Commande.TAILLE_MAX_CHARGE})")
            return False
        self._informer(self._messageInstrument, f"Commande acceptée : {len(charge)} octets")
        self.commandeDemandee.emit(
            Commande(TypeCommande.COMMANDE_INSTRUMENT, charge=charge))
        return True

    # ------------------------------------------------------------------
    # États connus par les HK (affichés à côté des boutons)
    # ------------------------------------------------------------------

    def afficherEtatTreuil(self, texte: str) -> None:
        self._etatTreuil.setText(f"État connu (HK) : {texte}")

    def afficherEtatInstrument(self, texte: str) -> None:
        self._etatInstrument.setText(f"État connu (HK) : {texte}")

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _construire(self) -> None:
        racine = QVBoxLayout(self)
        racine.setContentsMargins(0, 0, 0, 0)
        racine.setSpacing(10)

        # --- Treuil -----------------------------------------------------
        treuil = QGroupBox("Déplacement de la PFP")
        grille = QGridLayout(treuil)
        grille.setSpacing(8)

        self.boutonDescendre = QPushButton("▼  Descendre")
        self.boutonMonter = QPushButton("▲  Monter")
        self.boutonArret = QPushButton("ARRÊT")
        self.boutonArret.setObjectName("arret")
        self.boutonArret.setToolTip("Interrompt la descente ou la montée en cours")
        self.boutonDescendre.clicked.connect(self.descendre)
        self.boutonMonter.clicked.connect(self.monter)
        self.boutonArret.clicked.connect(self.arreterMouvement)
        grille.addWidget(self.boutonDescendre, 0, 0)
        grille.addWidget(self.boutonMonter, 0, 1)
        grille.addWidget(self.boutonArret, 1, 0, 1, 2)

        titre = QLabel(f"Consigne de distance (0 à {self.DISTANCE_MAX:.0f} m)")
        titre.setProperty("role", "titre")
        grille.addWidget(titre, 2, 0, 1, 2)
        self.saisieConsigne = QLineEdit()
        self.saisieConsigne.setPlaceholderText("Écart d'altitude en m")
        self.saisieConsigne.setAlignment(Qt.AlignRight)
        self.boutonConsigne = QPushButton("Envoyer")
        self.boutonConsigne.clicked.connect(self._valider_consigne)
        self.saisieConsigne.returnPressed.connect(self._valider_consigne)
        ligne = QHBoxLayout()
        ligne.addWidget(self.saisieConsigne, 1)
        ligne.addWidget(QLabel("m"))
        ligne.addWidget(self.boutonConsigne)
        grille.addLayout(ligne, 3, 0, 1, 2)
        self._messageConsigne = self._ligne_message()
        grille.addWidget(self._messageConsigne, 4, 0, 1, 2)
        self._etatTreuil = QLabel("État connu (HK) : aucun HK reçu")
        self._etatTreuil.setProperty("role", "discret")
        grille.addWidget(self._etatTreuil, 5, 0, 1, 2)
        racine.addWidget(treuil)

        # --- Instrument -------------------------------------------------
        instrument = QGroupBox("Instrument scientifique")
        grille = QGridLayout(instrument)
        grille.setSpacing(8)
        self.boutonInstrumentOn = QPushButton("Sous tension")
        self.boutonInstrumentOff = QPushButton("Hors tension")
        self.boutonInstrumentOn.clicked.connect(self.mettreInstrumentSousTension)
        self.boutonInstrumentOff.clicked.connect(self.mettreInstrumentHorsTension)
        grille.addWidget(self.boutonInstrumentOn, 0, 0)
        grille.addWidget(self.boutonInstrumentOff, 0, 1)
        self._etatInstrument = QLabel("État connu (HK) : aucun HK reçu")
        self._etatInstrument.setProperty("role", "discret")
        grille.addWidget(self._etatInstrument, 1, 0, 1, 2)

        titre = QLabel("Commande vers l'instrument")
        titre.setProperty("role", "titre")
        grille.addWidget(titre, 2, 0, 1, 2)
        self.saisieInstrument = QLineEdit()
        self.saisieInstrument.setPlaceholderText("Texte ou octets hexadécimaux")
        self.saisieInstrument.returnPressed.connect(self._valider_commande_instrument)
        grille.addWidget(self.saisieInstrument, 3, 0, 1, 2)
        self.choixFormat = QComboBox()
        self.choixFormat.addItems(["Texte ASCII", "Hexadécimal"])
        self.choixFinDeLigne = QComboBox()
        self.choixFinDeLigne.addItems(list(_FINS_DE_LIGNE))
        self.choixFinDeLigne.setToolTip("Fin de ligne ajoutée au texte ASCII")
        self.choixFormat.currentIndexChanged.connect(
            lambda i: self.choixFinDeLigne.setEnabled(i == 0))
        grille.addWidget(self.choixFormat, 4, 0)
        grille.addWidget(self.choixFinDeLigne, 4, 1)
        self.boutonInstrument = QPushButton("Envoyer à l'instrument")
        self.boutonInstrument.clicked.connect(self._valider_commande_instrument)
        grille.addWidget(self.boutonInstrument, 5, 0, 1, 2)
        self._messageInstrument = self._ligne_message()
        grille.addWidget(self._messageInstrument, 6, 0, 1, 2)
        racine.addWidget(instrument)
        racine.addStretch(1)

    @staticmethod
    def _ligne_message() -> QLabel:
        etiquette = QLabel(" ")
        etiquette.setWordWrap(True)
        etiquette.setProperty("role", "discret")
        return etiquette

    # ------------------------------------------------------------------
    # Saisies
    # ------------------------------------------------------------------

    def _valider_consigne(self) -> None:
        texte = self.saisieConsigne.text().strip().replace(",", ".")
        try:
            valeur: float | str = float(texte)
        except ValueError:
            valeur = texte or "vide"
        self.envoyerConsigne(valeur)

    def _valider_commande_instrument(self) -> None:
        hexadecimal = self.choixFormat.currentIndex() == 1
        fin = _FINS_DE_LIGNE[self.choixFinDeLigne.currentText()]
        if self.envoyerCommandeInstrument(self.saisieInstrument.text(), hexadecimal, fin):
            self.saisieInstrument.clear()

    def _refuser(self, etiquette: QLabel, texte: str) -> None:
        etiquette.setStyleSheet(f"color: {style.ROUGE};")
        etiquette.setText(texte)
        self.saisieRefusee.emit(texte)

    @staticmethod
    def _informer(etiquette: QLabel, texte: str) -> None:
        etiquette.setStyleSheet(f"color: {style.TEXTE_DISCRET};")
        etiquette.setText(texte)

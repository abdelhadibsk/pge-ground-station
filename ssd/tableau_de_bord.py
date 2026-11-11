"""TableauDeBord : surveillance de l'état par l'opérateur (diagramme de classes).

Couvre CU4 : HK datés du DPF et de la PFP, écart d'altitude, état des
liaisons et alertes.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from . import style
from .alertes import Alerte
from .icd import CHAMPS_HK, TOLERANCE_DISTANCE_M, Acteur
from .messages import HK, formater_date, formater_valeur, maintenant_utc
from .surveillance import EtatSousSysteme
from .vues import creer_graphique, police_fixe

_COULEUR_ETAT = {
    EtatSousSysteme.EN_ATTENTE: style.ORANGE,
    EtatSousSysteme.PRESENT: style.VERT,
    EtatSousSysteme.PERDU: style.ROUGE,
}


def _metres(valeur: float, signe: bool = False) -> str:
    texte = f"{valeur:+.1f}" if signe else f"{valeur:.1f}"
    return texte.replace(".", ",") + " m"


def _duree(secondes: float) -> str:
    secondes = int(secondes)
    if secondes < 60:
        return f"{secondes} s"
    minutes, s = divmod(secondes, 60)
    if minutes < 60:
        return f"{minutes} min {s:02d} s"
    heures, minutes = divmod(minutes, 60)
    return f"{heures} h {minutes:02d} min"


class Voyant(QFrame):
    """Indicateur d'état : titre, état en couleur, détail."""

    def __init__(self, titre: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("voyant")
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(12, 8, 12, 8)
        disposition.setSpacing(1)
        self._titre = QLabel(titre)
        self._etat = QLabel("—")
        self._detail = QLabel(" ")
        for etiquette in (self._titre, self._etat, self._detail):
            etiquette.setStyleSheet("background: transparent;")
            disposition.addWidget(etiquette)
        self._titre.setStyleSheet(
            f"background: transparent; color: {style.TEXTE_DISCRET}; font-size: 9pt;")
        self._detail.setStyleSheet(
            f"background: transparent; color: {style.TEXTE_DISCRET}; font-size: 9pt;")
        self.afficher("—", style.TEXTE_DISCRET)

    def afficher(self, etat: str, couleur: str, detail: str = " ") -> None:
        self._etat.setText(f"●  {etat}")
        self._etat.setStyleSheet(
            f"background: transparent; color: {couleur}; font-size: 13pt; font-weight: 700;")
        self._detail.setText(detail)
        self.setStyleSheet(
            f"QFrame#voyant {{ background: {style.PANNEAU}; border: 1px solid {style.BORD};"
            f" border-left: 4px solid {couleur}; border-radius: 6px; }}")

    def texteEtat(self) -> str:
        return self._etat.text().lstrip("● ").strip()


class TableauDeBord(QWidget):
    """Affichage de l'état du système."""

    HISTORIQUE_ECART = 7200        # points conservés (2 h à 1 point par seconde)
    #: pendant un déplacement, l'écart est attendu chaque seconde : au-delà de
    #: cet âge (s), il est signalé comme ancien
    PEREMPTION_EN_MOUVEMENT_S = 5.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dernierHK: HK | None = None             # dernier HK reçu (toutes sources)
        self.ecartAltitude: float | None = None      # m
        self.derniersHK: dict[Acteur, HK] = {}
        #: au-delà de cet âge (s), l'écart d'altitude est signalé comme ancien
        self.delaiPeremption = 180.0
        self._receptionHK: dict[Acteur, float] = {}
        self._receptionEcart: float | None = None
        self._dateEcart: datetime | None = None
        self._etats = {Acteur.DPF: EtatSousSysteme.EN_ATTENTE,
                       Acteur.PFP: EtatSousSysteme.EN_ATTENTE}
        self._liaisonOuverte = True
        self._detailLiaison = ""
        self._pointsEcart: deque = deque(maxlen=self.HISTORIQUE_ECART)
        self._construire()
        self.rafraichir()

    # ------------------------------------------------------------------
    # Interface du diagramme de classes
    # ------------------------------------------------------------------

    def afficherHK(self, hk: HK) -> None:                          # EX-IHM-020
        """Affiche un HK daté dans le tableau de sa source."""
        self.dernierHK = hk
        self.derniersHK[hk.source] = hk
        self._receptionHK[hk.source] = time.monotonic()
        table = self._tables[hk.source]
        for ligne, champ in enumerate(CHAMPS_HK[hk.source]):
            valeur = hk.mesures[champ.nom]
            hors_seuil = ((champ.mini is not None and valeur < champ.mini)
                          or (champ.maxi is not None and valeur > champ.maxi))
            cellule = table.item(ligne, 1)
            cellule.setText(formater_valeur(champ, valeur))
            cellule.setForeground(QColor(style.ROUGE if hors_seuil else style.TEXTE))
        self._datesHK[hk.source].setText(f"Daté du {formater_date(hk.date)} UTC (GNSS)")
        self.rafraichir()

    def afficherEcartAltitude(self, e: float, date: datetime | None = None) -> None:
        """Affiche l'écart d'altitude DPF - PFP, en mètres.     EX-IHM-090/100"""
        date = date or maintenant_utc()
        if date == self._dateEcart:
            return          # mesure déjà affichée : elle ne rajeunit pas la valeur
        self.ecartAltitude = float(e)
        self._dateEcart = date
        self._receptionEcart = time.monotonic()
        self._pointsEcart.append((date.timestamp(), self.ecartAltitude))
        self._courbeEcart.setData([p[0] for p in self._pointsEcart],
                                  [p[1] for p in self._pointsEcart])
        self.rafraichir()

    def afficherPresenceDPF(self, e: EtatSousSysteme) -> None:     # EX-IHM-130
        self._etats[Acteur.DPF] = e
        self.rafraichir()

    def afficherPresencePFP(self, e: EtatSousSysteme) -> None:     # EX-IHM-140
        self._etats[Acteur.PFP] = e
        self.rafraichir()

    def afficherAlerte(self, a: Alerte) -> None:                   # EX-IHM-160
        element = QListWidgetItem(
            f"{formater_date(a.date)}   {a.source.name}   {a.description}")
        element.setData(Qt.UserRole, f"{a.source.name}|{a.code or a.description}")
        element.setForeground(QColor(style.ROUGE))
        self._listeAlertes.addItem(element)
        self._actualiser_alertes()

    def retirerAlerte(self, a: Alerte) -> None:
        cle = f"{a.source.name}|{a.code or a.description}"
        for ligne in range(self._listeAlertes.count() - 1, -1, -1):
            if self._listeAlertes.item(ligne).data(Qt.UserRole) == cle:
                self._listeAlertes.takeItem(ligne)
        self._actualiser_alertes()

    # ------------------------------------------------------------------
    # Compléments
    # ------------------------------------------------------------------

    def afficherEtatLiaison(self, ouverte: bool, detail: str = "") -> None:
        """État du port UDP local (fermé = aucune réception possible)."""
        self._liaisonOuverte = ouverte
        self._detailLiaison = detail
        self.rafraichir()

    def installerOnglets(self, onglets: QWidget) -> None:
        """Place les onglets de l'IHM (journal, données...) sous les alertes."""
        self._colonneCentrale.addWidget(onglets, 1)

    def nombreAlertes(self) -> int:
        return self._listeAlertes.count()

    def rafraichir(self) -> None:
        """Met à jour l'heure, les âges et les voyants (appelé chaque seconde)."""
        maintenant = time.monotonic()
        self._voyantHeure.afficher(maintenant_utc().strftime("%H:%M:%S"), style.BLEU,
                                   maintenant_utc().strftime("%Y-%m-%d"))
        for acteur, voyant in ((Acteur.DPF, self._voyantDPF), (Acteur.PFP, self._voyantPFP)):
            etat = self._etats[acteur]
            if acteur in self._receptionHK:
                detail = f"Dernier HK reçu il y a {_duree(maintenant - self._receptionHK[acteur])}"
            else:
                detail = "Aucun HK reçu depuis le démarrage"
            if acteur is Acteur.DPF and not self._liaisonOuverte:
                voyant.afficher("PORT FERMÉ", style.ROUGE, self._detailLiaison or detail)
            else:
                voyant.afficher(etat.value, _COULEUR_ETAT[etat], detail)
            self._agesHK[acteur].setText(detail)

        if self._receptionEcart is None:
            self._valeurEcart.setText("—")
            self._detailEcart.setText("Aucune mesure reçue")
            self._actualiser_consigne(ancien=False)
            return
        age = maintenant - self._receptionEcart
        hk = self.derniersHK.get(Acteur.DPF)
        en_mouvement = hk is not None and int(hk.mesures.get("etat_treuil", 0)) != 0
        limite = self.PEREMPTION_EN_MOUVEMENT_S if en_mouvement else self.delaiPeremption
        # Sans le DPF ou sans la PFP, l'écart ne peut plus être à jour.
        ancien = age > limite or EtatSousSysteme.PERDU in self._etats.values()
        self._valeurEcart.setText(_metres(self.ecartAltitude))
        self._valeurEcart.setStyleSheet(
            "background: transparent; font-size: 34pt; font-weight: 700; color: "
            f"{style.TEXTE_DISCRET if ancien else style.TEXTE};")
        detail = (f"Mesure GNSS du {formater_date(self._dateEcart)} UTC\n"
                  f"Reçue il y a {_duree(age)}")
        self._detailEcart.setText(detail)
        self._actualiser_consigne(ancien)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _actualiser_consigne(self, ancien: bool) -> None:
        """Compare l'écart mesuré à la consigne en cours remontée par le DPF."""
        hk = self.derniersHK.get(Acteur.DPF)
        if hk is None or "consigne_distance" not in hk.mesures:
            if ancien:
                self._etiqueter("VALEUR ANCIENNE", style.ORANGE)
            return
        consigne = hk.mesures["consigne_distance"]
        self._ligneConsigne.setPos(consigne)
        self._ligneConsigne.setVisible(True)
        texte = f"Consigne en cours (HK DPF) : {_metres(consigne)}"
        if self.ecartAltitude is None:
            self._consigne.setText(texte)
            return
        difference = self.ecartAltitude - consigne
        texte += f"\nÉcart − consigne : {_metres(difference, signe=True)}"
        self._consigne.setText(texte)
        en_mouvement = int(hk.mesures.get("etat_treuil", 0)) != 0
        if ancien:
            self._etiqueter("VALEUR ANCIENNE", style.ORANGE)
        elif en_mouvement:
            self._etiqueter("DÉPLACEMENT EN COURS", style.BLEU)
        elif abs(difference) <= TOLERANCE_DISTANCE_M:
            self._etiqueter(f"DANS LA TOLÉRANCE ±{TOLERANCE_DISTANCE_M:.0f} m", style.VERT)
        else:
            self._etiqueter(f"HORS TOLÉRANCE ±{TOLERANCE_DISTANCE_M:.0f} m", style.ORANGE)

    def _etiqueter(self, texte: str, couleur: str) -> None:
        self._tolerance.setText(texte)
        self._tolerance.setStyleSheet(
            f"background: transparent; color: {couleur}; font-weight: 700; font-size: 9pt;")

    def _actualiser_alertes(self) -> None:
        nombre = self._listeAlertes.count()
        self._groupeAlertes.setTitle(
            f"Alertes actives ({nombre})" if nombre else "Alertes actives")
        self._aucuneAlerte.setVisible(nombre == 0)
        self._listeAlertes.setVisible(nombre > 0)
        bord = style.ROUGE if nombre else style.BORD
        self._groupeAlertes.setStyleSheet(
            f"QGroupBox#alertes {{ border: 1px solid {bord}; }}")

    def _construire(self) -> None:
        racine = QHBoxLayout(self)
        racine.setContentsMargins(0, 0, 0, 0)
        racine.setSpacing(10)
        self._colonneCentrale = QVBoxLayout()
        self._colonneCentrale.setSpacing(10)
        racine.addLayout(self._colonneCentrale, 1)

        # --- Voyants ----------------------------------------------------
        voyants = QHBoxLayout()
        voyants.setSpacing(10)
        self._voyantDPF = Voyant("Liaison Ethernet avec le DPF")
        self._voyantPFP = Voyant("Présence de la PFP")
        self._voyantHeure = Voyant("Heure UTC du PC")
        voyants.addWidget(self._voyantDPF, 3)
        voyants.addWidget(self._voyantPFP, 3)
        voyants.addWidget(self._voyantHeure, 2)
        self._colonneCentrale.addLayout(voyants)

        # --- Écart d'altitude --------------------------------------------
        groupe = QGroupBox("Écart d'altitude DPF – PFP")
        ligne = QHBoxLayout(groupe)
        ligne.setSpacing(14)
        carte = QVBoxLayout()
        carte.setSpacing(4)
        self._valeurEcart = QLabel("—")
        self._valeurEcart.setStyleSheet(
            "background: transparent; font-size: 34pt; font-weight: 700;")
        self._detailEcart = QLabel("Aucune mesure reçue")
        self._detailEcart.setProperty("role", "discret")
        self._consigne = QLabel("Consigne en cours : inconnue (aucun HK du DPF)")
        self._consigne.setStyleSheet("background: transparent; font-weight: 400;")
        self._tolerance = QLabel(" ")
        carte.addWidget(self._valeurEcart)
        carte.addWidget(self._detailEcart)
        carte.addSpacing(8)
        carte.addWidget(self._consigne)
        carte.addWidget(self._tolerance)
        carte.addStretch(1)
        conteneur = QWidget()
        conteneur.setLayout(carte)
        conteneur.setMinimumWidth(290)
        ligne.addWidget(conteneur)
        self._graphiqueEcart = creer_graphique("m")
        self._graphiqueEcart.setMinimumHeight(150)
        groupe.setMaximumHeight(290)
        self._courbeEcart = self._graphiqueEcart.plot(pen=pg.mkPen(style.BLEU, width=2))
        self._ligneConsigne = pg.InfiniteLine(
            angle=0, pen=pg.mkPen(style.VERT, width=1, style=Qt.DashLine),
            label="consigne", labelOpts={"color": style.VERT, "position": 0.12})
        self._ligneConsigne.setVisible(False)
        self._graphiqueEcart.addItem(self._ligneConsigne)
        ligne.addWidget(self._graphiqueEcart, 1)
        self._colonneCentrale.addWidget(groupe)

        # --- Alertes ------------------------------------------------------
        self._groupeAlertes = QGroupBox("Alertes actives")
        self._groupeAlertes.setObjectName("alertes")
        disposition = QVBoxLayout(self._groupeAlertes)
        self._aucuneAlerte = QLabel("Aucune alerte")
        self._aucuneAlerte.setProperty("role", "discret")
        self._listeAlertes = QListWidget()
        self._listeAlertes.setSelectionMode(QAbstractItemView.NoSelection)
        self._listeAlertes.setFocusPolicy(Qt.NoFocus)
        self._listeAlertes.setMaximumHeight(96)
        self._listeAlertes.setWordWrap(True)
        disposition.addWidget(self._aucuneAlerte)
        disposition.addWidget(self._listeAlertes)
        self._colonneCentrale.addWidget(self._groupeAlertes)
        self._actualiser_alertes()

        # --- Housekeeping -------------------------------------------------
        colonneHK = QVBoxLayout()
        colonneHK.setSpacing(10)
        self._tables: dict[Acteur, QTableWidget] = {}
        self._datesHK: dict[Acteur, QLabel] = {}
        self._agesHK: dict[Acteur, QLabel] = {}
        for acteur in (Acteur.DPF, Acteur.PFP):
            groupe = QGroupBox(f"Housekeeping {acteur.name}")
            disposition = QVBoxLayout(groupe)
            disposition.setSpacing(3)
            date = QLabel("Aucun HK reçu")
            date.setStyleSheet("background: transparent; font-weight: 600;")
            age = QLabel(" ")
            age.setProperty("role", "discret")
            disposition.addWidget(date)
            disposition.addWidget(age)
            table = self._creer_table(acteur)
            disposition.addWidget(table)
            self._tables[acteur], self._datesHK[acteur], self._agesHK[acteur] = table, date, age
            colonneHK.addWidget(groupe, len(CHAMPS_HK[acteur]) + 3)
        conteneur = QWidget()
        conteneur.setLayout(colonneHK)
        conteneur.setFixedWidth(360)
        racine.addWidget(conteneur)

    @staticmethod
    def _creer_table(acteur: Acteur) -> QTableWidget:
        champs = CHAMPS_HK[acteur]
        table = QTableWidget(len(champs), 2)
        table.setHorizontalHeaderLabels(["Paramètre", "Valeur"])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.setShowGrid(False)
        police = police_fixe()
        for ligne, champ in enumerate(champs):
            table.setItem(ligne, 0, QTableWidgetItem(champ.libelle))
            valeur = QTableWidgetItem("—")
            valeur.setFont(police)
            valeur.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(ligne, 1, valeur)
        return table

    # -- lecture pour les tests ---------------------------------------------

    def texteValeurHK(self, source: Acteur, nom: str) -> str:
        for ligne, champ in enumerate(CHAMPS_HK[source]):
            if champ.nom == nom:
                return self._tables[source].item(ligne, 1).text()
        raise KeyError(nom)

    def texteEcart(self) -> str:
        return self._valeurEcart.text()

    def textePresence(self, acteur: Acteur) -> str:
        voyant = self._voyantDPF if acteur is Acteur.DPF else self._voyantPFP
        return voyant.texteEtat()

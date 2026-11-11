"""Surveillance de la présence du DPF et de la PFP (diagramme de classes).

Règle [EX-COM-130] : le DPF (respectivement la PFP) est déclaré perdu si
aucun de ses HK n'est reçu pendant ``seuilPerte`` périodes de HK.

Ce module ne dépend pas de Qt : l'IHM appelle verifierPeriode() une fois par
seconde.
"""

from __future__ import annotations

import enum
import time
from typing import Callable

from .icd import Acteur


class EtatSousSysteme(enum.Enum):
    """État de présence d'un sous-système.

    EN_ATTENTE (ajout par rapport au diagramme) : depuis le démarrage, aucun
    HK n'a encore été reçu et le délai de perte n'est pas écoulé.
    """

    EN_ATTENTE = "EN ATTENTE"
    PRESENT = "PRÉSENT"
    PERDU = "PERDU"


class SurveillancePresence:
    """Suit la réception des HK et déclare la perte du DPF et de la PFP."""

    def __init__(self, periodeHK: float = 60.0, seuilPerte: int = 3,
                 horloge: Callable[[], float] = time.monotonic) -> None:
        self.periodeHK = float(periodeHK)      # s  [EX-COM-120]
        self.seuilPerte = int(seuilPerte)      # périodes [EX-COM-130]
        self.compteurDPF = 0                   # périodes écoulées sans HK
        self.compteurPFP = 0
        self.etatDPF = EtatSousSysteme.EN_ATTENTE
        self.etatPFP = EtatSousSysteme.EN_ATTENTE
        #: appelé à chaque changement d'état : (acteur, nouvel état)
        self.surChangement: Callable[[Acteur, EtatSousSysteme], None] | None = None
        self._horloge = horloge
        depart = horloge()
        self._reference = {Acteur.DPF: depart, Acteur.PFP: depart}
        self._jamais_recu = {Acteur.DPF, Acteur.PFP}

    # -- interface du diagramme --------------------------------------------

    def signalerReceptionHK(self, source: Acteur) -> None:
        """À appeler à chaque HK reçu du DPF ou de la PFP."""
        if source not in self._reference:
            return
        self._reference[source] = self._horloge()
        self._ecrire_compteur(source, 0)
        self._changer_etat(source, EtatSousSysteme.PRESENT)

    def verifierPeriode(self) -> None:
        """Met à jour les compteurs et déclare les pertes éventuelles."""
        maintenant = self._horloge()
        for acteur, reference in self._reference.items():
            periodes = int((maintenant - reference) // self.periodeHK)
            self._ecrire_compteur(acteur, periodes)
            if periodes >= self.seuilPerte:
                self.declarerPerdu(acteur)

    def declarerPerdu(self, s: Acteur) -> None:
        self._changer_etat(s, EtatSousSysteme.PERDU)

    # -- consultation ------------------------------------------------------

    def etat(self, acteur: Acteur) -> EtatSousSysteme:
        return self.etatDPF if acteur is Acteur.DPF else self.etatPFP

    def delaiPerte(self) -> float:
        """Durée sans HK au bout de laquelle la perte est déclarée (s)."""
        return self.periodeHK * self.seuilPerte

    def ageDernierHK(self, acteur: Acteur) -> float | None:
        """Secondes écoulées depuis le dernier HK, None si jamais reçu."""
        if acteur in self._jamais_recu:
            return None
        return self._horloge() - self._reference[acteur]

    # -- interne -----------------------------------------------------------

    def _ecrire_compteur(self, acteur: Acteur, valeur: int) -> None:
        if acteur is Acteur.DPF:
            self.compteurDPF = valeur
        else:
            self.compteurPFP = valeur

    def _changer_etat(self, acteur: Acteur, etat: EtatSousSysteme) -> None:
        if etat is EtatSousSysteme.PRESENT:
            self._jamais_recu.discard(acteur)
        if self.etat(acteur) is etat:
            return
        if acteur is Acteur.DPF:
            self.etatDPF = etat
        else:
            self.etatPFP = etat
        if self.surChangement is not None:
            self.surChangement(acteur, etat)

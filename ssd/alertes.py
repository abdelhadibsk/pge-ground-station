"""Alertes relatives à l'état du DPF et de la PFP (diagramme de classes).

GestionAlertes tient la liste des alertes actives [EX-IHM-160]. Une alerte
est identifiée par sa source et son code : la déclencher deux fois ne crée
pas de doublon, et elle s'efface dès que sa cause disparaît.

Ce module ne dépend pas de Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .icd import CHAMPS_HK, Acteur
from .messages import HK, formater_valeur


@dataclass(frozen=True)
class Alerte:
    """Alerte : source, description, date (+ code interne d'identification)."""

    source: Acteur
    description: str
    date: datetime
    code: str = ""

    @property
    def cle(self) -> tuple[Acteur, str]:
        return (self.source, self.code or self.description)


class GestionAlertes:
    """Liste des alertes actives."""

    def __init__(self) -> None:
        self.alertesActives: list[Alerte] = []
        self.surDeclenchement: Callable[[Alerte], None] | None = None
        self.surEffacement: Callable[[Alerte], None] | None = None

    def declencher(self, a: Alerte) -> bool:
        """Ajoute l'alerte si elle n'est pas déjà active. Retourne True si ajoutée."""
        if any(active.cle == a.cle for active in self.alertesActives):
            return False
        self.alertesActives.append(a)
        if self.surDeclenchement is not None:
            self.surDeclenchement(a)
        return True

    def effacer(self, a: Alerte) -> bool:
        """Retire l'alerte de même source et de même code. Retourne True si retirée."""
        for active in self.alertesActives:
            if active.cle == a.cle:
                self.alertesActives.remove(active)
                if self.surEffacement is not None:
                    self.surEffacement(active)
                return True
        return False

    def effacerCode(self, source: Acteur, code: str) -> bool:
        return self.effacer(Alerte(source, "", datetime.min, code))

    def analyserHK(self, hk: HK) -> None:
        """Met à jour les alertes déduites d'un HK :

        - alertes remontées par le bord (octet « alertes » du HK) ;
        - valeurs hors des seuils du cahier des charges (icd.CHAMPS_HK).
        Les alertes de cette source qui ne sont plus vraies sont effacées.
        """
        voulues: dict[str, str] = {}
        for bit, texte in hk.alertesBord().items():
            voulues[f"BORD:{bit}"] = texte
        for champ in CHAMPS_HK[hk.source]:
            valeur = hk.mesures[champ.nom]
            if champ.mini is not None and valeur < champ.mini:
                voulues[f"SEUIL:{champ.nom}"] = (
                    f"{champ.libelle} sous le minimum : {formater_valeur(champ, valeur)} "
                    f"(minimum {formater_valeur(champ, champ.mini)}, {champ.origine_seuil})")
            elif champ.maxi is not None and valeur > champ.maxi:
                voulues[f"SEUIL:{champ.nom}"] = (
                    f"{champ.libelle} au-dessus du maximum : {formater_valeur(champ, valeur)} "
                    f"(maximum {formater_valeur(champ, champ.maxi)}, {champ.origine_seuil})")

        for active in list(self.alertesActives):
            deduite_hk = active.code.startswith(("BORD:", "SEUIL:"))
            if active.source is hk.source and deduite_hk and active.code not in voulues:
                self.effacer(active)
        for code, texte in voulues.items():
            self.declencher(Alerte(hk.source, texte, hk.date, code))

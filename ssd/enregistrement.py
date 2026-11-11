"""Fichiers produits par la station sol.

Un dossier par session (date UTC de démarrage) contenant :
  journal.csv             commandes envoyées et événements, datés [EX-IHM-150]
  donnees_instrument.csv  données de l'instrument, fichier dédié [EX-IHM-070/080]
  hk_dpf.csv, hk_pfp.csv  archive des HK reçus

Chaque ligne est écrite sur le disque dès sa réception : rien n'est perdu si
l'application est fermée brutalement.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .icd import CHAMPS_HK, Acteur
from .messages import HK, DonneeInstrument, formater_date


class FichierCSV:
    """Fichier CSV (séparateur « ; », UTF-8) écrit ligne par ligne."""

    def __init__(self, chemin: Path, entetes: list[str]) -> None:
        self.chemin = Path(chemin)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        nouveau = not self.chemin.exists() or self.chemin.stat().st_size == 0
        self._fichier = open(self.chemin, "a", newline="", encoding="utf-8-sig")
        self._csv = csv.writer(self._fichier, delimiter=";")
        self.nbLignes = 0
        if nouveau:
            self._csv.writerow(entetes)
            self._fichier.flush()

    def ecrire(self, ligne: list) -> None:
        self._csv.writerow(ligne)
        self._fichier.flush()
        self.nbLignes += 1

    def fermer(self) -> None:
        if not self._fichier.closed:
            self._fichier.close()


def creer_dossier_session(racine: str | Path, debut: datetime) -> Path:
    """Crée et retourne le dossier de la session : racine/AAAAMMJJ_HHMMSS."""
    base = Path(racine) / debut.strftime("%Y%m%d_%H%M%S")
    dossier, n = base, 1
    while dossier.exists():                 # deux démarrages dans la même seconde
        n += 1
        dossier = base.with_name(f"{base.name}_{n}")
    dossier.mkdir(parents=True)
    return dossier


def ouvrir_journal(dossier: Path) -> FichierCSV:
    return FichierCSV(dossier / "journal.csv", ["date_utc", "categorie", "evenement"])


def ouvrir_donnees_instrument(dossier: Path) -> FichierCSV:
    return FichierCSV(dossier / "donnees_instrument.csv",
                      ["date_gnss_utc", "date_reception_utc", "nb_octets", "donnees_hex"])


def ligne_donnee_instrument(d: DonneeInstrument, reception: datetime) -> list:
    return [formater_date(d.date, True), formater_date(reception, True),
            len(d.mesures), d.mesures.hex().upper()]


def ouvrir_archive_hk(dossier: Path, source: Acteur) -> FichierCSV:
    entetes = ["date_gnss_utc", "date_reception_utc"]
    for champ in CHAMPS_HK[source]:
        entetes.append(f"{champ.nom} [{champ.unite}]" if champ.unite else champ.nom)
    entetes.append("alertes_bord")
    return FichierCSV(dossier / f"hk_{source.name.lower()}.csv", entetes)


def ligne_hk(hk: HK, reception: datetime) -> list:
    ligne = [formater_date(hk.date, True), formater_date(reception, True)]
    for champ in CHAMPS_HK[hk.source]:
        valeur = hk.mesures[champ.nom]
        if champ.valeurs is not None:
            ligne.append(champ.valeurs.get(int(valeur), int(valeur)))
        else:
            ligne.append(f"{valeur:.{max(champ.decimales, 1)}f}")
    ligne.append(f"0x{hk.alertes:02X}")
    return ligne

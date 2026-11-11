"""Lecture de la configuration de la station sol (fichier .ini)."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from .icd import PORT_TC_DEFAUT, PORT_TM_DEFAUT


@dataclass
class Configuration:
    # [reseau]
    adresse_dpf: str = "172.20.4.10"      # réseau bord 172.20.4.x (réponse CNES)
    port_dpf: int = PORT_TC_DEFAUT        # port d'écoute du DPF (commandes)
    port_ecoute: int = PORT_TM_DEFAUT     # port d'écoute de la SSD (HK, données)
    adresse_locale: str = "0.0.0.0"       # interface du PC ; 0.0.0.0 = toutes
    # [surveillance]
    periode_hk_s: float = 60.0            # EX-COM-120
    seuil_perte: int = 3                  # EX-COM-130
    # [enregistrement]
    dossier: str = "enregistrements"

    @classmethod
    def charger(cls, chemin: str | Path | None) -> "Configuration":
        """Charge un fichier .ini ; les clés absentes gardent leur valeur par défaut."""
        config = cls()
        if chemin is None:
            return config
        chemin = Path(chemin)
        if not chemin.is_file():
            raise FileNotFoundError(f"fichier de configuration introuvable : {chemin}")
        ini = configparser.ConfigParser()
        ini.read(chemin, encoding="utf-8")
        reseau = ini["reseau"] if ini.has_section("reseau") else {}
        surveillance = ini["surveillance"] if ini.has_section("surveillance") else {}
        enregistrement = ini["enregistrement"] if ini.has_section("enregistrement") else {}
        config.adresse_dpf = reseau.get("adresse_dpf", config.adresse_dpf)
        config.port_dpf = int(reseau.get("port_dpf", config.port_dpf))
        config.port_ecoute = int(reseau.get("port_ecoute", config.port_ecoute))
        config.adresse_locale = reseau.get("adresse_locale", config.adresse_locale)
        config.periode_hk_s = float(surveillance.get("periode_hk_s", config.periode_hk_s))
        config.seuil_perte = int(surveillance.get("seuil_perte", config.seuil_perte))
        config.dossier = enregistrement.get("dossier", config.dossier)
        if config.periode_hk_s <= 0 or config.seuil_perte < 1:
            raise ValueError("periode_hk_s doit être > 0 et seuil_perte >= 1")
        return config

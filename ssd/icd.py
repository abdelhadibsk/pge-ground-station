"""Définition d'interface des messages (ICD) - PROPOSITION v0, à valider en équipe.

Tout ce qui dépend du format des messages est regroupé ici et dans
``messages.py`` : quand le document d'interface sera figé avec les groupes DPF
et PFP, ce sont les deux seuls fichiers à modifier (l'IHM affiche les HK à
partir des tables ci-dessous, sans rien coder en dur).

Origine des valeurs :
  [CDC]         cahier des charges CNES STB-0-15453-CN v1.0
  [EXIGENCE]    exigences du groupe Sol & Com, v2 du 20/10/2026
  [PROPOSITION] choix proposé ici, à valider
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


# --------------------------------------------------------------------------
# Énumérations de l'en-tête                                     [EX-COM-050]
# --------------------------------------------------------------------------

class Acteur(enum.IntEnum):
    """Source ou destinataire d'un message. Codes [PROPOSITION]."""

    SSD = 1
    DPF = 2
    PFP = 3


class TypeMessage(enum.IntEnum):
    """Types de messages [EX-COM-060].

    ECART_ALTITUDE vient du diagramme de classes (classe EcartAltitude) ;
    il n'est pas encore dans EX-COM-060 (voir les propositions d'évolution).
    """

    COMMANDE = 1
    HK = 2
    DONNEE_INSTRUMENT = 3
    ECART_ALTITUDE = 4


class TypeCommande(enum.IntEnum):
    """Types de commandes [EX-COM-070] + diagramme de classes."""

    DESCENTE = 1
    MONTEE = 2
    CONSIGNE_DISTANCE = 3
    ARRET = 4
    INSTRUMENT_ON = 5
    INSTRUMENT_OFF = 6
    COMMANDE_INSTRUMENT = 7


#: Destinataire de chaque commande : le treuil est sur le DPF, l'instrument
#: sur la PFP (le DPF relaie, EX-COM-100).
DESTINATAIRE_COMMANDE = {
    TypeCommande.DESCENTE: Acteur.DPF,
    TypeCommande.MONTEE: Acteur.DPF,
    TypeCommande.CONSIGNE_DISTANCE: Acteur.DPF,
    TypeCommande.ARRET: Acteur.DPF,
    TypeCommande.INSTRUMENT_ON: Acteur.PFP,
    TypeCommande.INSTRUMENT_OFF: Acteur.PFP,
    TypeCommande.COMMANDE_INSTRUMENT: Acteur.PFP,
}

LIBELLE_COMMANDE = {
    TypeCommande.DESCENTE: "Descente",
    TypeCommande.MONTEE: "Montée",
    TypeCommande.CONSIGNE_DISTANCE: "Consigne de distance",
    TypeCommande.ARRET: "Arrêt",
    TypeCommande.INSTRUMENT_ON: "Instrument sous tension",
    TypeCommande.INSTRUMENT_OFF: "Instrument hors tension",
    TypeCommande.COMMANDE_INSTRUMENT: "Commande instrument",
}


# --------------------------------------------------------------------------
# Constantes du format de trame                                [PROPOSITION]
# --------------------------------------------------------------------------

VERSION_PROTOCOLE = 1
TAILLE_ENTETE = 6        # version, source, destinataire, type, longueur (2)
TAILLE_CRC = 2           # CRC-16/CCITT-FALSE sur en-tête + données
#: Un message doit tenir dans un seul paquet LoRa (255 octets au maximum)
#: pour être relayé à l'identique par le DPF (EX-COM-110).
TAILLE_MAX_DONNEES = 240

# Valeurs du cahier des charges utilisées par l'IHM
DISTANCE_MAX_M = 2000.0      # [CDC DPF-0040] [EX-IHM-110]
TOLERANCE_DISTANCE_M = 5.0   # [CDC SSD-0030]
VITESSE_TREUIL_M_S = 1.5     # [CDC DPF-0040]

# Ports et adresses par défaut (modifiables dans config.ini)
PORT_TM_DEFAUT = 5000        # bord -> sol : port d'écoute de la SSD [PROPOSITION]
PORT_TC_DEFAUT = 5001        # sol -> bord : port d'écoute du DPF   [PROPOSITION]


# --------------------------------------------------------------------------
# Contenu des housekeeping                                     [PROPOSITION]
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ChampHK:
    """Un champ d'un message HK, après la date.

    ``fmt`` est un code du module ``struct`` (gros-boutiste) ; la valeur
    physique vaut ``brut * echelle``. ``mini`` / ``maxi`` sont les seuils
    surveillés par la station sol : une alerte est levée en dehors.
    """

    nom: str
    libelle: str
    fmt: str
    unite: str = ""
    echelle: float = 1.0
    decimales: int = 0
    mini: float | None = None
    maxi: float | None = None
    valeurs: dict[int, str] | None = None   # champ énuméré : code -> texte
    origine_seuil: str = ""

    @property
    def numerique(self) -> bool:
        """Vrai si le champ peut être tracé en courbe."""
        return self.valeurs is None


_GNSS = (
    ChampHK("latitude", "Latitude GNSS", "i", "°", 1e-7, 5),
    ChampHK("longitude", "Longitude GNSS", "i", "°", 1e-7, 5),
    ChampHK("altitude", "Altitude GNSS", "f", "m", 1.0, 1),
    ChampHK("gnss_valide", "Position GNSS", "B",
            valeurs={0: "NON VALIDE", 1: "VALIDE"}),
)

#: HK du DPF, dans l'ordre de la trame.
HK_DPF: tuple[ChampHK, ...] = _GNSS + (
    ChampHK("tension_alim", "Tension d'alimentation", "H", "V", 1e-3, 2,
            mini=10.0, maxi=35.0, origine_seuil="CDC SYS-0080"),
    ChampHK("courant_alim", "Courant d'alimentation", "H", "A", 1e-3, 2,
            maxi=5.0, origine_seuil="CDC SYS-0080"),
    ChampHK("temperature_carte", "Température carte", "h", "°C", 0.1, 1,
            mini=-40.0, maxi=60.0, origine_seuil="CDC DPF-0010"),
    ChampHK("etat_treuil", "État du treuil", "B",
            valeurs={0: "ARRÊT", 1: "DESCENTE", 2: "MONTÉE"}),
    ChampHK("consigne_distance", "Consigne en cours", "H", "m", 0.1, 1),
)

#: HK de la PFP, dans l'ordre de la trame.
HK_PFP: tuple[ChampHK, ...] = _GNSS + (
    ChampHK("tension_batterie", "Tension batterie", "H", "V", 1e-3, 2,
            mini=8.0, maxi=25.0, origine_seuil="CDC PFP-0145"),
    ChampHK("courant_batterie", "Courant batterie (+ = charge)", "h", "A", 1e-3, 3),
    ChampHK("etat_charge", "État de charge", "B", "%", 1.0, 0),
    ChampHK("tension_panneau", "Tension panneau solaire", "H", "V", 1e-3, 2),
    ChampHK("courant_panneau", "Courant panneau solaire", "H", "A", 1e-3, 3),
    ChampHK("temperature_interne", "Température interne", "h", "°C", 0.1, 1,
            mini=-30.0, origine_seuil="CDC PFP-0100"),
    ChampHK("etat_instrument", "Instrument", "B",
            valeurs={0: "HORS TENSION", 1: "SOUS TENSION"}),
    ChampHK("courant_instrument", "Courant instrument", "H", "A", 1e-3, 3),
    ChampHK("rechauffage", "Réchauffage", "B",
            valeurs={0: "ARRÊT", 1: "MARCHE"}),
    ChampHK("rssi_radio", "Niveau radio reçu (RSSI)", "h", "dBm", 1.0, 0),
)

#: Table des HK par source. Le dernier octet de chaque HK est le champ
#: de bits « alertes » décrit par ALERTES_BORD.
CHAMPS_HK: dict[Acteur, tuple[ChampHK, ...]] = {
    Acteur.DPF: HK_DPF,
    Acteur.PFP: HK_PFP,
}

#: Alertes remontées par le bord dans l'octet « alertes » des HK
#: (bit -> description) [EX-IHM-160].
ALERTES_BORD: dict[Acteur, dict[int, str]] = {
    Acteur.DPF: {
        0: "Défaut treuil",
        1: "Liaison radio avec la PFP perdue (vue du DPF)",
    },
    Acteur.PFP: {
        0: "Instrument disjoncté (court-circuit)",   # CDC PFP-0110
        1: "Batterie faible",
        2: "Tampon des données instrument plein",
    },
}


def champ_hk(source: Acteur, nom: str) -> ChampHK:
    """Retourne la définition d'un champ HK par son nom."""
    for champ in CHAMPS_HK[source]:
        if champ.nom == nom:
            return champ
    raise KeyError(f"champ HK inconnu pour {source.name} : {nom}")

"""Simulateur du bord : DPF (treuil, passerelle) et PFP (instrument).

Il reprend les classes « bord » du diagramme de classes : PasserelleDPF et
LiaisonDPF_PFP (ici une liaison radio simulée en mémoire). Il sert à essayer
et à valider l'IHM ; ce n'est pas le logiciel embarqué.

Comportement simulé (voir docs/ICD_messages_v0.md) :
  - le DPF lit le destinataire de chaque message : il le traite, ou le
    transmet à la PFP, ou à la SSD [EX-COM-100] ;
  - la PFP envoie ses HK au DPF ; le DPF envoie ses HK et ceux de la PFP à la
    SSD à chaque période [EX-COM-120] ;
  - pendant un déplacement, la PFP envoie sa position chaque seconde
    [EX-LDP-050] et le DPF envoie l'écart d'altitude chaque seconde ;
  - un HK est émis juste après chaque commande exécutée.

Ce module ne dépend pas de Qt.
"""

from __future__ import annotations

import math
import random
import struct
import time
from collections import deque
from typing import Callable

from ssd.icd import DISTANCE_MAX_M, VITESSE_TREUIL_M_S, Acteur, TypeCommande
from ssd.liaison import Liaison, LiaisonEthernet
from ssd.messages import (
    HK, Commande, DonneeInstrument, EcartAltitude, Message, maintenant_utc,
)

TREUIL_ARRET, TREUIL_DESCENTE, TREUIL_MONTEE = 0, 1, 2


# --------------------------------------------------------------------------
# Liaison radio simulée
# --------------------------------------------------------------------------

class CanalRadio:
    """Support de la liaison DPF-PFP simulée ; ``coupe`` = liaison perdue."""

    def __init__(self) -> None:
        self.coupe = False
        self.files: dict[Acteur, deque[bytes]] = {Acteur.DPF: deque(), Acteur.PFP: deque()}


class LiaisonDPF_PFP:
    """Liaison DPF <-> PFP (une instance côté DPF, une côté PFP).

    Les messages y circulent sous leur forme codée, comme sur la radio.
    """

    portee = int(DISTANCE_MAX_M)       # m [EX-LDP-060]

    def __init__(self, canal: CanalRadio, cote: Acteur) -> None:
        self._canal = canal
        self._cote = cote
        self._autre = Acteur.PFP if cote is Acteur.DPF else Acteur.DPF

    def envoyer(self, m: Message) -> None:
        if not self._canal.coupe:
            self._canal.files[self._autre].append(m.coder())

    def recevoir(self) -> Message | None:
        file = self._canal.files[self._cote]
        if self._canal.coupe:
            file.clear()
        return Message.decoder(file.popleft()) if file else None


# --------------------------------------------------------------------------
# Passerelle du DPF
# --------------------------------------------------------------------------

class PasserelleDPF:
    """Passe d'Ethernet à la liaison DPF-PFP et inversement [EX-COM-090/100]."""

    def __init__(self, liaisonEthernet: Liaison, liaisonDPF_PFP: Liaison,
                 traiter: Callable[[Message], None]) -> None:
        self.liaisonEthernet = liaisonEthernet
        self.liaisonDPF_PFP = liaisonDPF_PFP
        self._traiter = traiter            # traitement des messages pour le DPF

    def lireDestinataire(self, m: Message) -> Acteur:
        return m.destinataire

    def convertirEthernetVersDPF_PFP(self, m: Message) -> None:
        self.liaisonDPF_PFP.envoyer(m)

    def convertirDPF_PFPVersEthernet(self, m: Message) -> None:
        self.liaisonEthernet.envoyer(m)

    def acheminer(self, m: Message) -> None:
        destinataire = self.lireDestinataire(m)
        if destinataire is Acteur.DPF:
            self._traiter(m)
        elif destinataire is Acteur.PFP:
            self.convertirEthernetVersDPF_PFP(m)
        else:
            self.convertirDPF_PFPVersEthernet(m)


# --------------------------------------------------------------------------
# PFP simulée
# --------------------------------------------------------------------------

class SimulateurPFP:
    """Plate-forme profiler : HK, position GNSS, instrument."""

    PERIODE_DONNEES_S = 4.0            # ~46 octets toutes les 4 s = 1000 Ko / 24 h

    def __init__(self, liaison: Liaison, periodeHK: float, alea: random.Random) -> None:
        self.liaison = liaison
        self.periodeHK = periodeHK
        self.alea = alea
        self.instrumentSousTension = False
        self.courtCircuit = False          # panne injectée
        self.froid = False                 # panne injectée
        self.altitudeVraie = 0.0
        self.distance = 0.0                # longueur de fil déroulée (m)
        self.enMouvement = False
        self.etatCharge = 78.0
        self._t0 = time.monotonic()
        self._prochainHK = 0.0
        self._prochaineDonnee = 0.0
        self._compteurMesures = 0

    def pas(self, maintenant: float) -> None:
        while (m := self.liaison.recevoir()) is not None:
            if isinstance(m, Commande):
                self._executer(m)
                self._prochainHK = 0.0     # compte rendu immédiat par HK
        periode = min(1.0, self.periodeHK) if self.enMouvement else self.periodeHK
        if maintenant >= self._prochainHK or self._prochainHK - maintenant > periode:
            self._prochainHK = maintenant + periode
            self.liaison.envoyer(self.construireHK())
        if self.instrumentSousTension and maintenant >= self._prochaineDonnee:
            self._prochaineDonnee = maintenant + self.PERIODE_DONNEES_S * self.alea.uniform(0.5, 1.5)
            self.liaison.envoyer(DonneeInstrument(maintenant_utc(), self._mesure()))

    def _executer(self, c: Commande) -> None:
        if c.typeCommande is TypeCommande.INSTRUMENT_ON:
            self.instrumentSousTension = not self.courtCircuit
            self._prochaineDonnee = 0.0
        elif c.typeCommande is TypeCommande.INSTRUMENT_OFF:
            self.instrumentSousTension = False
        elif c.typeCommande is TypeCommande.COMMANDE_INSTRUMENT and self.instrumentSousTension:
            # L'instrument simulé répond en renvoyant ce qu'il a reçu.
            reponse = b"RECU:" + c.charge
            self.liaison.envoyer(DonneeInstrument(
                maintenant_utc(), reponse[:DonneeInstrument.TAILLE_MAX_MESURES]))

    def _mesure(self) -> bytes:
        """Trame binaire fictive de l'instrument (46 octets)."""
        self._compteurMesures += 1
        valeurs = [self.alea.gauss(0.0, 1.0) for _ in range(10)]
        return struct.pack(">HI10f", 0xAA55, self._compteurMesures, *valeurs)

    def construireHK(self) -> HK:
        t = time.monotonic() - self._t0
        temperature = -34.0 if self.froid else -12.0 + 6.0 * math.sin(t / 900.0)
        rechauffage = 1 if temperature < -20.0 else 0
        courant_panneau = 0.42 + 0.03 * math.sin(t / 300.0)
        courant_instrument = 0.135 if self.instrumentSousTension else 0.0
        courant_batterie = courant_panneau - courant_instrument - 0.05 - 0.4 * rechauffage
        self.etatCharge = min(100.0, max(5.0, self.etatCharge + courant_batterie * 0.002))
        alertes = (1 if self.courtCircuit else 0) | (2 if self.etatCharge < 15.0 else 0)
        return HK(Acteur.PFP, maintenant_utc(), {
            "latitude": 0.1002 + self.alea.gauss(0, 2e-6),
            "longitude": -50.0003 + self.alea.gauss(0, 2e-6),
            "altitude": self.altitudeVraie + self.alea.gauss(0, 1.0),
            "gnss_valide": 1,
            "tension_batterie": 13.2 + 3.6 * self.etatCharge / 100.0,
            "courant_batterie": courant_batterie,
            "etat_charge": round(self.etatCharge),
            "tension_panneau": 18.3 + self.alea.gauss(0, 0.05),
            "courant_panneau": courant_panneau,
            "temperature_interne": temperature,
            "etat_instrument": int(self.instrumentSousTension),
            "courant_instrument": courant_instrument,
            "rechauffage": rechauffage,
            "rssi_radio": round(-45.0 - 20.0 * math.log10(max(self.distance, 5.0) / 5.0)),
        }, alertes, destinataire=Acteur.DPF)


# --------------------------------------------------------------------------
# DPF simulé
# --------------------------------------------------------------------------

class SimulateurDPF:
    """Descendeur : treuil, GNSS, HK, passerelle vers la PFP."""

    ALTITUDE_VOL_M = 20000.0

    def __init__(self, ethernet: Liaison, radio: Liaison, periodeHK: float,
                 vitesse: float, alea: random.Random) -> None:
        self.ethernet = ethernet
        self.radio = radio
        self.periodeHK = periodeHK
        self.vitesse = vitesse
        self.alea = alea
        self.passerelle = PasserelleDPF(ethernet, radio, self._traiter)
        self.longueur = 0.0                # fil déroulé (m)
        self.cible = 0.0                   # distance visée (m)
        self.etatTreuil = TREUIL_ARRET
        self.defautTreuil = False          # panne injectée
        self.dernierHKPFP: HK | None = None
        self._receptionHKPFP = -math.inf
        self._dernierRelaisPFP = -math.inf
        self._ecart: float | None = None   # écart d'altitude calculé (m)
        self._dateEcart = maintenant_utc()
        self._prochainHK = 0.0
        self._prochainEcart = 0.0
        self._t0 = time.monotonic()
        self._precedent = time.monotonic()

    # -- grandeurs physiques -------------------------------------------------

    def altitudeVraie(self) -> float:
        t = time.monotonic() - self._t0
        return self.ALTITUDE_VOL_M + 30.0 * math.sin(2 * math.pi * t / 600.0)

    def enMouvement(self) -> bool:
        return self.etatTreuil != TREUIL_ARRET

    # -- pas de simulation ---------------------------------------------------

    def pas(self, maintenant: float) -> None:
        dt, self._precedent = maintenant - self._precedent, maintenant

        while (m := self.ethernet.recevoir()) is not None:      # messages de la SSD
            self.passerelle.acheminer(m)
        while (m := self.radio.recevoir()) is not None:         # messages de la PFP
            if isinstance(m, HK) and m.source is Acteur.PFP:
                self._recevoir_hk_pfp(m, maintenant)
            else:
                self.passerelle.acheminer(m)

        etat_avant = self.etatTreuil
        self._deplacer(dt)
        if self.etatTreuil != etat_avant:
            self._prochainHK = 0.0                               # changement d'état
        if maintenant >= self._prochainHK:
            self._prochainHK = maintenant + self.periodeHK
            self._prochainEcart = 0.0
            self.ethernet.envoyer(self.construireHK(maintenant))
        periode_ecart = min(1.0, self.periodeHK) if self.enMouvement() else self.periodeHK
        if maintenant >= self._prochainEcart and self._ecart is not None:
            # Chaque écart calculé n'est envoyé qu'une fois : sans nouvelle
            # position de la PFP, la SSD voit que la valeur vieillit.
            self._prochainEcart = maintenant + periode_ecart
            self.ethernet.envoyer(EcartAltitude(self._dateEcart, self._ecart))
            self._ecart = None

    def radioPerdue(self, maintenant: float) -> bool:
        return maintenant - self._receptionHKPFP > 3.0 * self.periodeHK

    def _recevoir_hk_pfp(self, hk: HK, maintenant: float) -> None:
        """La PFP envoie ses HK au DPF, qui les envoie à la SSD (CU7).

        Un HK de la PFP n'est jamais envoyé deux fois : si la PFP se tait, la
        SSD ne reçoit plus ses HK et peut constater sa perte.
        """
        self.dernierHKPFP = hk
        self._receptionHKPFP = maintenant
        # Écart d'altitude = altitude GNSS du DPF - altitude GNSS de la PFP,
        # mesurées au même instant [EX-IHM-100].
        self._ecart = (self.altitudeVraie() + self.alea.gauss(0, 1.0)
                       - hk.mesures["altitude"])
        self._dateEcart = hk.date
        if not self.enMouvement() or maintenant - self._dernierRelaisPFP >= self.periodeHK:
            self._dernierRelaisPFP = maintenant
            self.passerelle.convertirDPF_PFPVersEthernet(
                HK(Acteur.PFP, hk.date, hk.mesures, hk.alertes, destinataire=Acteur.SSD))

    def _traiter(self, m: Message) -> None:
        """Message dont le destinataire est le DPF."""
        if not isinstance(m, Commande):
            return
        if m.typeCommande is TypeCommande.DESCENTE:
            self.cible = DISTANCE_MAX_M
        elif m.typeCommande is TypeCommande.MONTEE:
            self.cible = 0.0
        elif m.typeCommande is TypeCommande.CONSIGNE_DISTANCE:
            if 0.0 <= m.parametre <= DISTANCE_MAX_M:
                self.cible = m.parametre
        elif m.typeCommande is TypeCommande.ARRET:
            self.cible = self.longueur
        self._prochainHK = 0.0                                   # compte rendu par HK

    def _deplacer(self, dt: float) -> None:
        if self.defautTreuil:
            self.cible = self.longueur
        reste = self.cible - self.longueur
        pas = self.vitesse * dt
        if abs(reste) <= pas:
            self.longueur = self.cible
            self.etatTreuil = TREUIL_ARRET
        else:
            self.longueur += math.copysign(pas, reste)
            self.etatTreuil = TREUIL_DESCENTE if reste > 0 else TREUIL_MONTEE

    def construireHK(self, maintenant: float) -> HK:
        courant = 0.35 + (2.1 if self.enMouvement() else 0.0) + self.alea.gauss(0, 0.01)
        alertes = (1 if self.defautTreuil else 0) | (2 if self.radioPerdue(maintenant) else 0)
        return HK(Acteur.DPF, maintenant_utc(), {
            "latitude": 0.1002 + self.alea.gauss(0, 2e-6),
            "longitude": -50.0003 + self.alea.gauss(0, 2e-6),
            "altitude": self.altitudeVraie() + self.alea.gauss(0, 1.0),
            "gnss_valide": 1,
            "tension_alim": 28.0 + self.alea.gauss(0, 0.05),
            "courant_alim": courant,
            "temperature_carte": -38.5 + self.alea.gauss(0, 0.2),
            "etat_treuil": self.etatTreuil,
            "consigne_distance": self.cible,
        }, alertes)


# --------------------------------------------------------------------------
# Ensemble
# --------------------------------------------------------------------------

class Simulateur:
    """DPF + PFP + liaison radio simulée. Appeler pas() régulièrement."""

    def __init__(self, adresseSSD: str = "127.0.0.1", portSSD: int = 5000,
                 portEcoute: int = 5001, periodeHK: float = 5.0,
                 vitesse: float = VITESSE_TREUIL_M_S, graine: int | None = None) -> None:
        alea = random.Random(graine)
        self.ethernet = LiaisonEthernet(adresseSSD, portSSD, portEcoute)
        self.canal = CanalRadio()
        self.dpf = SimulateurDPF(self.ethernet, LiaisonDPF_PFP(self.canal, Acteur.DPF),
                                 periodeHK, vitesse, alea)
        self.pfp = SimulateurPFP(LiaisonDPF_PFP(self.canal, Acteur.PFP), periodeHK, alea)
        self.ethernetCoupe = False         # panne injectée : le DPF se tait

    def ouvrir(self) -> None:
        self.ethernet.ouvrir()

    def fermer(self) -> None:
        self.ethernet.fermer()

    def pas(self) -> None:
        maintenant = time.monotonic()
        if self.ethernetCoupe:
            # DPF injoignable : rien n'entre ni ne sort (les commandes sont perdues).
            while self.ethernet.recevoir() is not None:
                pass
            self.dpf._precedent = maintenant
            return
        self.pfp.altitudeVraie = self.dpf.altitudeVraie() - self.dpf.longueur
        self.pfp.distance = self.dpf.longueur
        self.pfp.enMouvement = self.dpf.enMouvement()
        self.pfp.pas(maintenant)
        try:
            self.dpf.pas(maintenant)
        except OSError:
            pass                           # station sol absente : on continue

    # -- pannes injectables ---------------------------------------------------

    def commander(self, ligne: str) -> str:
        """Exécute une commande de la console du simulateur ; retourne la réponse."""
        mots = ligne.strip().lower().split()
        if not mots:
            return ""
        actif = len(mots) > 1 and mots[1] in ("on", "oui", "1")
        match mots[0]:
            case "radio":
                self.canal.coupe = not actif
                return f"Liaison radio DPF-PFP : {'établie' if actif else 'COUPÉE'}"
            case "eth":
                self.ethernetCoupe = not actif
                return f"Liaison Ethernet du DPF : {'établie' if actif else 'COUPÉE'}"
            case "froid":
                self.pfp.froid = actif
                return f"Température interne PFP : {'-34 °C (trop froid)' if actif else 'normale'}"
            case "cc":
                self.pfp.courtCircuit = actif
                if actif:
                    self.pfp.instrumentSousTension = False
                return f"Court-circuit instrument : {'OUI (disjoncté)' if actif else 'non'}"
            case "treuil":
                self.dpf.defautTreuil = not actif
                return f"Treuil : {'normal' if actif else 'EN DÉFAUT'}"
            case "etat":
                return (f"fil déroulé {self.dpf.longueur:.1f} m, cible {self.dpf.cible:.1f} m, "
                        f"treuil {('arrêt', 'descente', 'montée')[self.dpf.etatTreuil]}, "
                        f"instrument {'ON' if self.pfp.instrumentSousTension else 'OFF'}, "
                        f"radio {'coupée' if self.canal.coupe else 'ok'}, "
                        f"ethernet {'coupé' if self.ethernetCoupe else 'ok'}")
            case "aide" | "?":
                return AIDE
        return f"Commande inconnue : {ligne.strip()} (taper « aide »)"


AIDE = """Pannes injectables (taper la commande puis Entrée) :
  radio off | on    coupe / rétablit la liaison radio DPF-PFP  -> perte de la PFP
  eth off | on      coupe / rétablit l'Ethernet du DPF         -> perte du DPF (et de la PFP)
  froid on | off    température interne PFP à -34 °C           -> alerte de seuil
  cc on | off       court-circuit de l'instrument              -> alerte du bord
  treuil off | on   défaut du treuil                           -> alerte du bord
  etat              affiche l'état simulé
  quitter           arrête le simulateur"""

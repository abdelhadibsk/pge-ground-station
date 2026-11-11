"""Messages échangés entre la SSD, le DPF et la PFP (diagramme de classes).

Classes : Message et ses spécialisations Commande, HK, DonneeInstrument,
EcartAltitude. Tous les messages suivent le même format [EX-COM-050] :

    octet 0      version du protocole
    octet 1      source          (Acteur)
    octet 2      destinataire    (Acteur)
    octet 3      type            (TypeMessage)
    octets 4-5   longueur N des données (entier non signé, gros-boutiste)
    octets 6...  données (N octets)
    2 derniers   CRC-16/CCITT-FALSE calculé sur tout ce qui précède

Ce module ne dépend pas de Qt : il sert aussi au simulateur et aux tests.
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone

from .icd import (
    ALERTES_BORD,
    CHAMPS_HK,
    DESTINATAIRE_COMMANDE,
    LIBELLE_COMMANDE,
    TAILLE_CRC,
    TAILLE_ENTETE,
    TAILLE_MAX_DONNEES,
    VERSION_PROTOCOLE,
    Acteur,
    ChampHK,
    TypeCommande,
    TypeMessage,
)

__all__ = [
    "Acteur", "TypeMessage", "TypeCommande", "ErreurMessage", "Message",
    "Commande", "HK", "DonneeInstrument", "EcartAltitude", "crc16",
    "maintenant_utc", "formater_date", "formater_valeur",
]

_FMT_ENTETE = ">BBBBH"
_FMT_DATE = ">IH"          # secondes depuis le 01/01/1970 UTC + millisecondes
_TAILLE_DATE = struct.calcsize(_FMT_DATE)


class ErreurMessage(ValueError):
    """Trame reçue invalide (taille, version, CRC, champ inconnu...)."""


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------

def crc16(octets: bytes) -> int:
    """CRC-16/CCITT-FALSE (polynôme 0x1021, valeur initiale 0xFFFF)."""
    crc = 0xFFFF
    for octet in octets:
        crc ^= octet << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def maintenant_utc() -> datetime:
    """Date courante du PC, en UTC."""
    return datetime.now(timezone.utc)


def formater_date(date: datetime, millisecondes: bool = False) -> str:
    """Date UTC lisible : 2026-11-10 14:03:21 (ou .123 en plus)."""
    date = date.astimezone(timezone.utc)
    texte = date.strftime("%Y-%m-%d %H:%M:%S")
    if millisecondes:
        texte += f".{date.microsecond // 1000:03d}"
    return texte


def _coder_date(date: datetime) -> bytes:
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    millis_total = round(date.timestamp() * 1000)
    secondes, millis = divmod(millis_total, 1000)
    return struct.pack(_FMT_DATE, secondes, millis)


def _decoder_date(octets: bytes) -> datetime:
    secondes, millis = struct.unpack(_FMT_DATE, octets[:_TAILLE_DATE])
    if millis > 999:
        raise ErreurMessage(f"date invalide ({millis} ms)")
    return datetime.fromtimestamp(secondes + millis / 1000.0, tz=timezone.utc)


def formater_valeur(champ: ChampHK, valeur: float | int) -> str:
    """Texte affiché pour une valeur de HK (avec son unité)."""
    if champ.valeurs is not None:
        return champ.valeurs.get(int(valeur), f"code {int(valeur)} inconnu")
    texte = f"{valeur:.{champ.decimales}f}".replace(".", ",")
    return f"{texte} {champ.unite}".strip()


# --------------------------------------------------------------------------
# Message
# --------------------------------------------------------------------------

class Message:
    """Message générique : source, destinataire, type, données."""

    def __init__(self, source: Acteur, destinataire: Acteur,
                 type: TypeMessage, donnees: bytes = b"") -> None:
        self.source = Acteur(source)
        self.destinataire = Acteur(destinataire)
        self.type = TypeMessage(type)
        self._donnees = bytes(donnees)

    @property
    def donnees(self) -> bytes:
        """Données utiles du message (octets après l'en-tête)."""
        return self._donnees

    def coder(self) -> bytes:
        """Construit la trame complète (en-tête + données + CRC)."""
        donnees = self.donnees
        if len(donnees) > TAILLE_MAX_DONNEES:
            raise ErreurMessage(
                f"données trop longues : {len(donnees)} octets "
                f"(maximum {TAILLE_MAX_DONNEES})")
        corps = struct.pack(_FMT_ENTETE, VERSION_PROTOCOLE, self.source,
                            self.destinataire, self.type, len(donnees)) + donnees
        return corps + struct.pack(">H", crc16(corps))

    @staticmethod
    def decoder(trame: bytes) -> "Message":
        """Analyse une trame et retourne le message du bon type.

        Lève ErreurMessage si la trame est invalide.
        """
        if len(trame) < TAILLE_ENTETE + TAILLE_CRC:
            raise ErreurMessage(f"trame trop courte ({len(trame)} octets)")
        version, source, destinataire, type_, longueur = struct.unpack(
            _FMT_ENTETE, trame[:TAILLE_ENTETE])
        if version != VERSION_PROTOCOLE:
            raise ErreurMessage(f"version de protocole inconnue ({version})")
        attendu = TAILLE_ENTETE + longueur + TAILLE_CRC
        if len(trame) != attendu:
            raise ErreurMessage(
                f"longueur incohérente : {len(trame)} octets reçus, {attendu} attendus")
        corps, (crc_recu,) = trame[:-TAILLE_CRC], struct.unpack(">H", trame[-TAILLE_CRC:])
        if crc16(corps) != crc_recu:
            raise ErreurMessage("CRC incorrect")
        try:
            source, destinataire = Acteur(source), Acteur(destinataire)
            type_ = TypeMessage(type_)
        except ValueError as erreur:
            raise ErreurMessage(f"en-tête invalide : {erreur}") from None

        donnees = corps[TAILLE_ENTETE:]
        classe = _CLASSES[type_]
        try:
            return classe._depuis_donnees(source, destinataire, donnees)
        except struct.error as erreur:
            raise ErreurMessage(f"données {type_.name} invalides : {erreur}") from None

    def __eq__(self, autre: object) -> bool:
        return isinstance(autre, Message) and self.coder() == autre.coder()

    def __repr__(self) -> str:
        return (f"<{type(self).__name__} {self.source.name}->{self.destinataire.name} "
                f"{len(self.donnees)} octets>")


# --------------------------------------------------------------------------
# Commande
# --------------------------------------------------------------------------

class Commande(Message):
    """Commande de la SSD vers le DPF ou la PFP [EX-COM-070].

    Données : typeCommande (1 octet), parametre (flottant 32 bits), puis,
    pour COMMANDE_INSTRUMENT seulement, les octets destinés à l'instrument
    (transmis tels quels sur sa liaison RS232).
    """

    _FMT = ">Bf"
    TAILLE_MAX_CHARGE = TAILLE_MAX_DONNEES - struct.calcsize(_FMT)

    def __init__(self, typeCommande: TypeCommande, parametre: float = 0.0,
                 charge: bytes = b"", source: Acteur = Acteur.SSD,
                 destinataire: Acteur | None = None) -> None:
        typeCommande = TypeCommande(typeCommande)
        if destinataire is None:
            destinataire = DESTINATAIRE_COMMANDE[typeCommande]
        super().__init__(source, destinataire, TypeMessage.COMMANDE)
        self.typeCommande = typeCommande
        self.parametre = float(parametre)
        self.charge = bytes(charge)

    @property
    def donnees(self) -> bytes:
        return struct.pack(self._FMT, self.typeCommande, self.parametre) + self.charge

    @classmethod
    def _depuis_donnees(cls, source, destinataire, donnees) -> "Commande":
        taille = struct.calcsize(cls._FMT)
        code, parametre = struct.unpack(cls._FMT, donnees[:taille])
        try:
            typeCommande = TypeCommande(code)
        except ValueError:
            raise ErreurMessage(f"type de commande inconnu ({code})") from None
        return cls(typeCommande, parametre, donnees[taille:], source, destinataire)

    def description(self) -> str:
        """Texte de la commande pour le journal."""
        texte = LIBELLE_COMMANDE[self.typeCommande]
        if self.typeCommande is TypeCommande.CONSIGNE_DISTANCE:
            texte += f" : {self.parametre:.1f} m".replace(".", ",")
        elif self.typeCommande is TypeCommande.COMMANDE_INSTRUMENT:
            texte += f" : {len(self.charge)} octets [{self.charge.hex(' ').upper()}]"
        return f"{texte} (vers {self.destinataire.name})"


# --------------------------------------------------------------------------
# HK
# --------------------------------------------------------------------------

class HK(Message):
    """Housekeeping daté du DPF ou de la PFP [EX-COM-080].

    ``mesures`` associe le nom de chaque champ (voir icd.CHAMPS_HK) à sa
    valeur physique ; ``alertes`` est le champ de bits des alertes du bord.
    """

    def __init__(self, source: Acteur, date: datetime, mesures: dict[str, float],
                 alertes: int = 0, destinataire: Acteur = Acteur.SSD) -> None:
        super().__init__(source, destinataire, TypeMessage.HK)
        if self.source not in CHAMPS_HK:
            raise ErreurMessage(f"pas de HK défini pour la source {self.source.name}")
        self.date = date
        self.mesures = dict(mesures)
        self.alertes = int(alertes)

    @staticmethod
    def _format(source: Acteur) -> str:
        return ">" + "".join(champ.fmt for champ in CHAMPS_HK[source]) + "B"

    @property
    def donnees(self) -> bytes:
        bruts = []
        for champ in CHAMPS_HK[self.source]:
            brut = self.mesures[champ.nom] / champ.echelle
            bruts.append(brut if champ.fmt in "fd" else round(brut))
        try:
            corps = struct.pack(self._format(self.source), *bruts, self.alertes & 0xFF)
        except struct.error as erreur:
            raise ErreurMessage(f"HK {self.source.name} hors plage : {erreur}") from None
        return _coder_date(self.date) + corps

    @classmethod
    def _depuis_donnees(cls, source, destinataire, donnees) -> "HK":
        if source not in CHAMPS_HK:
            raise ErreurMessage(f"HK reçu d'une source inattendue ({source.name})")
        fmt = cls._format(source)
        attendu = _TAILLE_DATE + struct.calcsize(fmt)
        if len(donnees) != attendu:
            raise ErreurMessage(
                f"HK {source.name} : {len(donnees)} octets reçus, {attendu} attendus")
        date = _decoder_date(donnees)
        *bruts, alertes = struct.unpack(fmt, donnees[_TAILLE_DATE:])
        mesures = {champ.nom: brut if champ.valeurs is not None else brut * champ.echelle
                   for champ, brut in zip(CHAMPS_HK[source], bruts)}
        return cls(source, date, mesures, alertes, destinataire)

    def alertesBord(self) -> dict[int, str]:
        """Alertes actives remontées par le bord : bit -> description."""
        return {bit: texte for bit, texte in ALERTES_BORD[self.source].items()
                if self.alertes & (1 << bit)}


# --------------------------------------------------------------------------
# DonneeInstrument
# --------------------------------------------------------------------------

class DonneeInstrument(Message):
    """Données brutes de l'instrument, datées par la PFP [EX-COM-080]."""

    TAILLE_MAX_MESURES = TAILLE_MAX_DONNEES - _TAILLE_DATE

    def __init__(self, date: datetime, mesures: bytes, source: Acteur = Acteur.PFP,
                 destinataire: Acteur = Acteur.SSD) -> None:
        super().__init__(source, destinataire, TypeMessage.DONNEE_INSTRUMENT)
        self.date = date
        self.mesures = bytes(mesures)

    @property
    def donnees(self) -> bytes:
        return _coder_date(self.date) + self.mesures

    @classmethod
    def _depuis_donnees(cls, source, destinataire, donnees) -> "DonneeInstrument":
        if len(donnees) < _TAILLE_DATE:
            raise ErreurMessage("donnée instrument sans date")
        return cls(_decoder_date(donnees), donnees[_TAILLE_DATE:], source, destinataire)


# --------------------------------------------------------------------------
# EcartAltitude
# --------------------------------------------------------------------------

class EcartAltitude(Message):
    """Écart d'altitude DPF - PFP, calculé à bord à partir des deux GNSS
    [EX-IHM-090, EX-IHM-100]. ``valeur`` en mètres."""

    _FMT = ">f"

    def __init__(self, date: datetime, valeur: float, source: Acteur = Acteur.DPF,
                 destinataire: Acteur = Acteur.SSD) -> None:
        super().__init__(source, destinataire, TypeMessage.ECART_ALTITUDE)
        self.date = date
        self.valeur = float(valeur)

    @property
    def donnees(self) -> bytes:
        return _coder_date(self.date) + struct.pack(self._FMT, self.valeur)

    @classmethod
    def _depuis_donnees(cls, source, destinataire, donnees) -> "EcartAltitude":
        if len(donnees) != _TAILLE_DATE + struct.calcsize(cls._FMT):
            raise ErreurMessage(f"écart d'altitude : taille invalide ({len(donnees)})")
        (valeur,) = struct.unpack(cls._FMT, donnees[_TAILLE_DATE:])
        return cls(_decoder_date(donnees), valeur, source, destinataire)


_CLASSES = {
    TypeMessage.COMMANDE: Commande,
    TypeMessage.HK: HK,
    TypeMessage.DONNEE_INSTRUMENT: DonneeInstrument,
    TypeMessage.ECART_ALTITUDE: EcartAltitude,
}

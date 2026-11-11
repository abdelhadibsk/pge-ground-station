"""Format des messages : EX-COM-050, 060, 070, 080, 110."""

from datetime import datetime, timezone

import pytest

from ssd.icd import CHAMPS_HK, DESTINATAIRE_COMMANDE, TAILLE_MAX_DONNEES
from ssd.messages import (
    HK, Acteur, Commande, DonneeInstrument, EcartAltitude, ErreurMessage,
    Message, TypeCommande, TypeMessage, crc16,
)

DATE = datetime(2026, 11, 10, 14, 3, 21, 250000, tzinfo=timezone.utc)


def _hk(source):
    mesures = {champ.nom: (1 if champ.valeurs else 12.0) for champ in CHAMPS_HK[source]}
    return HK(source, DATE, mesures, alertes=0b10)


def test_crc16_valeur_de_reference():
    assert crc16(b"123456789") == 0x29B1


def test_entete_source_destinataire_type_donnees():
    """EX-COM-050 : même format pour tous, avec source, destinataire, type, données."""
    trame = Commande(TypeCommande.ARRET).coder()
    assert trame[1] == Acteur.SSD and trame[2] == Acteur.DPF
    assert trame[3] == TypeMessage.COMMANDE
    assert int.from_bytes(trame[4:6], "big") == len(trame) - 8


@pytest.mark.parametrize("type_commande", list(TypeCommande))
def test_commandes_aller_retour(type_commande):
    """EX-COM-070 et EX-COM-110 : la commande est relue à l'identique."""
    envoyee = Commande(type_commande, parametre=1234.5, charge=b"\x01\xA0\xFF")
    recue = Message.decoder(envoyee.coder())
    assert isinstance(recue, Commande)
    assert recue.typeCommande is type_commande
    assert recue.parametre == 1234.5
    assert recue.charge == b"\x01\xA0\xFF"
    assert recue.destinataire is DESTINATAIRE_COMMANDE[type_commande]
    assert recue.coder() == envoyee.coder()


@pytest.mark.parametrize("source", [Acteur.DPF, Acteur.PFP])
def test_hk_aller_retour_et_date(source):
    """EX-COM-080 : les HK portent leur date."""
    recu = Message.decoder(_hk(source).coder())
    assert isinstance(recu, HK) and recu.source is source
    assert recu.date == DATE
    assert recu.alertes == 0b10
    for champ in CHAMPS_HK[source]:
        attendu = 1 if champ.valeurs else 12.0
        assert recu.mesures[champ.nom] == pytest.approx(attendu, abs=champ.echelle)


def test_donnee_instrument_aller_retour():
    mesures = bytes(range(200))
    recue = Message.decoder(DonneeInstrument(DATE, mesures).coder())
    assert isinstance(recue, DonneeInstrument)
    assert recue.mesures == mesures and recue.date == DATE
    assert recue.source is Acteur.PFP and recue.destinataire is Acteur.SSD


def test_ecart_altitude_aller_retour():
    recu = Message.decoder(EcartAltitude(DATE, 1499.5).coder())
    assert isinstance(recu, EcartAltitude)
    assert recu.valeur == 1499.5 and recu.date == DATE


def test_trame_alteree_rejetee():
    trame = bytearray(Commande(TypeCommande.DESCENTE).coder())
    trame[7] ^= 0x01
    with pytest.raises(ErreurMessage, match="CRC"):
        Message.decoder(bytes(trame))


@pytest.mark.parametrize("trame", [
    b"", b"\x01\x02", Commande(TypeCommande.MONTEE).coder()[:-1],
    Commande(TypeCommande.MONTEE).coder() + b"\x00",
])
def test_trame_de_mauvaise_taille_rejetee(trame):
    with pytest.raises(ErreurMessage):
        Message.decoder(trame)


def test_version_inconnue_rejetee():
    trame = bytearray(Commande(TypeCommande.MONTEE).coder())
    trame[0] = 9
    with pytest.raises(ErreurMessage, match="version"):
        Message.decoder(bytes(trame))


def test_acteur_inconnu_rejete():
    corps = bytes([1, 7, 1, 2, 0, 0])
    trame = corps + crc16(corps).to_bytes(2, "big")
    with pytest.raises(ErreurMessage):
        Message.decoder(trame)


def test_donnees_trop_longues_refusees():
    with pytest.raises(ErreurMessage):
        DonneeInstrument(DATE, bytes(TAILLE_MAX_DONNEES)).coder()


def test_un_message_tient_dans_un_paquet_radio():
    """Un message doit tenir dans un paquet LoRa (255 octets) pour être relayé tel quel."""
    plus_long = DonneeInstrument(DATE, bytes(DonneeInstrument.TAILLE_MAX_MESURES))
    assert len(plus_long.coder()) <= 255

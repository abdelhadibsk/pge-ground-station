"""Alertes : EX-IHM-160."""

from datetime import datetime, timezone

from ssd.alertes import Alerte, GestionAlertes
from ssd.icd import CHAMPS_HK, Acteur
from ssd.messages import HK

DATE = datetime(2026, 11, 10, tzinfo=timezone.utc)

NOMINAL_PFP = {
    "latitude": 0.1, "longitude": -50.0, "altitude": 19000.0, "gnss_valide": 1,
    "tension_batterie": 15.0, "courant_batterie": 0.2, "etat_charge": 80,
    "tension_panneau": 18.0, "courant_panneau": 0.4, "temperature_interne": -10.0,
    "etat_instrument": 1, "courant_instrument": 0.13, "rechauffage": 0, "rssi_radio": -80,
}


def test_la_table_de_test_couvre_tous_les_champs():
    assert set(NOMINAL_PFP) == {champ.nom for champ in CHAMPS_HK[Acteur.PFP]}


def test_pas_de_doublon_et_effacement():
    g = GestionAlertes()
    a = Alerte(Acteur.DPF, "DPF perdu", DATE, "PERTE")
    assert g.declencher(a) is True
    assert g.declencher(Alerte(Acteur.DPF, "DPF perdu (bis)", DATE, "PERTE")) is False
    assert g.declencher(Alerte(Acteur.PFP, "PFP perdue", DATE, "PERTE")) is True
    assert len(g.alertesActives) == 2
    assert g.effacer(a) is True and g.effacer(a) is False
    assert [x.source for x in g.alertesActives] == [Acteur.PFP]


def test_hk_nominal_sans_alerte():
    g = GestionAlertes()
    g.analyserHK(HK(Acteur.PFP, DATE, NOMINAL_PFP))
    assert g.alertesActives == []


def test_seuil_du_cahier_des_charges_puis_retour_a_la_normale():
    """Température interne PFP sous -30 °C (CDC PFP-0100)."""
    g = GestionAlertes()
    g.analyserHK(HK(Acteur.PFP, DATE, {**NOMINAL_PFP, "temperature_interne": -32.0}))
    assert len(g.alertesActives) == 1
    assert "Température interne" in g.alertesActives[0].description
    assert "PFP-0100" in g.alertesActives[0].description
    g.analyserHK(HK(Acteur.PFP, DATE, {**NOMINAL_PFP, "temperature_interne": -32.5}))
    assert len(g.alertesActives) == 1                     # toujours la même alerte
    g.analyserHK(HK(Acteur.PFP, DATE, NOMINAL_PFP))
    assert g.alertesActives == []


def test_alerte_remontee_par_le_bord():
    g = GestionAlertes()
    g.analyserHK(HK(Acteur.PFP, DATE, NOMINAL_PFP, alertes=0b001))
    assert [a.description for a in g.alertesActives] == ["Instrument disjoncté (court-circuit)"]
    g.analyserHK(HK(Acteur.PFP, DATE, NOMINAL_PFP, alertes=0))
    assert g.alertesActives == []


def test_un_hk_n_efface_pas_les_alertes_des_autres():
    g = GestionAlertes()
    g.declencher(Alerte(Acteur.PFP, "PFP perdue", DATE, "PERTE"))
    g.declencher(Alerte(Acteur.DPF, "Défaut treuil", DATE, "BORD:0"))
    g.analyserHK(HK(Acteur.PFP, DATE, NOMINAL_PFP))
    assert len(g.alertesActives) == 2

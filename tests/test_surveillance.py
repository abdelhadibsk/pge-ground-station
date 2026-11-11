"""Surveillance de présence : EX-COM-130, EX-IHM-130, EX-IHM-140."""

from ssd.icd import Acteur
from ssd.surveillance import EtatSousSysteme, SurveillancePresence


class Horloge:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _surveillance():
    horloge = Horloge()
    s = SurveillancePresence(periodeHK=60, seuilPerte=3, horloge=horloge)
    changements = []
    s.surChangement = lambda acteur, etat: changements.append((acteur, etat))
    return s, horloge, changements


def test_en_attente_au_demarrage():
    s, _, _ = _surveillance()
    assert s.etatDPF is EtatSousSysteme.EN_ATTENTE
    assert s.etatPFP is EtatSousSysteme.EN_ATTENTE


def test_present_a_la_reception_d_un_hk():
    s, _, changements = _surveillance()
    s.signalerReceptionHK(Acteur.DPF)
    assert s.etatDPF is EtatSousSysteme.PRESENT
    assert s.etatPFP is EtatSousSysteme.EN_ATTENTE
    assert changements == [(Acteur.DPF, EtatSousSysteme.PRESENT)]


def test_perte_apres_exactement_trois_periodes():
    s, horloge, changements = _surveillance()
    s.signalerReceptionHK(Acteur.PFP)
    horloge.t += 179.0
    s.verifierPeriode()
    assert s.etatPFP is EtatSousSysteme.PRESENT and s.compteurPFP == 2
    horloge.t += 1.0
    s.verifierPeriode()
    assert s.etatPFP is EtatSousSysteme.PERDU and s.compteurPFP == 3
    s.verifierPeriode()                       # pas de second signalement
    assert changements.count((Acteur.PFP, EtatSousSysteme.PERDU)) == 1


def test_un_hk_remet_le_compteur_a_zero():
    s, horloge, _ = _surveillance()
    s.signalerReceptionHK(Acteur.DPF)
    for _ in range(10):                       # un HK toutes les 60 s : jamais perdu
        horloge.t += 60.0
        s.verifierPeriode()
        s.signalerReceptionHK(Acteur.DPF)
    assert s.etatDPF is EtatSousSysteme.PRESENT and s.compteurDPF == 0


def test_dpf_et_pfp_suivis_separement():
    s, horloge, _ = _surveillance()
    s.signalerReceptionHK(Acteur.DPF)
    s.signalerReceptionHK(Acteur.PFP)
    horloge.t += 100.0
    s.signalerReceptionHK(Acteur.DPF)         # seul le DPF continue d'émettre
    horloge.t += 100.0
    s.verifierPeriode()
    assert s.etatDPF is EtatSousSysteme.PRESENT
    assert s.etatPFP is EtatSousSysteme.PERDU


def test_retour_apres_perte():
    s, horloge, _ = _surveillance()
    s.signalerReceptionHK(Acteur.DPF)
    horloge.t += 200.0
    s.verifierPeriode()
    assert s.etatDPF is EtatSousSysteme.PERDU
    s.signalerReceptionHK(Acteur.DPF)
    assert s.etatDPF is EtatSousSysteme.PRESENT


def test_perdu_si_rien_recu_depuis_le_demarrage():
    s, horloge, _ = _surveillance()
    horloge.t += 180.0
    s.verifierPeriode()
    assert s.etatDPF is EtatSousSysteme.PERDU and s.etatPFP is EtatSousSysteme.PERDU
    assert s.ageDernierHK(Acteur.DPF) is None

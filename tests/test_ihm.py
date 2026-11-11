"""Essais de l'IHM complète (sans écran) face au simulateur DPF/PFP.

Chaque essai cite les exigences EX-IHM / EX-COM qu'il vérifie.
"""

import csv
import socket
import time

import pytest

from simulateur.simulateur import Simulateur
from ssd.config import Configuration
from ssd.icd import Acteur, TypeCommande
from ssd.ihm import IHM
from ssd.messages import Commande, maintenant_utc
from ssd.surveillance import EtatSousSysteme

PERIODE = 0.3          # période des HK pendant les essais (s)


class Banc:
    """IHM + simulateur reliés en UDP sur la machine locale."""

    def __init__(self, application, dossier):
        self.application = application
        self.simulateur = Simulateur(portEcoute=0, periodeHK=PERIODE, vitesse=60.0, graine=1)
        self.simulateur.ouvrir()
        config = Configuration(adresse_dpf="127.0.0.1",
                               port_dpf=self.simulateur.ethernet.portEcoute,
                               port_ecoute=0, adresse_locale="127.0.0.1",
                               periode_hk_s=PERIODE, seuil_perte=3, dossier=str(dossier))
        self.ihm = IHM(config)
        self.ihm.demarrer()
        self.simulateur.ethernet.portUDP = self.ihm.liaisonEthernet.portEcoute
        self.commandes = []
        self.ihm.panneauCommandes.commandeDemandee.connect(self.commandes.append)

    def tourner(self, duree=None, jusqua=None, delai=8.0):
        """Fait vivre le simulateur et l'IHM pendant ``duree`` ou jusqu'à ``jusqua()``."""
        fin = time.monotonic() + (duree if duree is not None else delai)
        while time.monotonic() < fin:
            self.simulateur.pas()
            self.application.processEvents()
            self.ihm.surveillancePresence.verifierPeriode()
            if jusqua is not None and jusqua():
                return True
            time.sleep(0.005)
        return jusqua is None

    def lire(self, nom):
        with open(self.ihm.dossierSession / nom, encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f, delimiter=";"))

    def journal(self):
        return [ligne[2] for ligne in self.lire("journal.csv")[1:]]

    def fermer(self):
        self.ihm.close()
        self.simulateur.fermer()


@pytest.fixture
def banc(application, tmp_path):
    banc = Banc(application, tmp_path)
    yield banc
    banc.fermer()


def _present(banc):
    s = banc.ihm.surveillancePresence
    return (s.etatDPF is EtatSousSysteme.PRESENT and s.etatPFP is EtatSousSysteme.PRESENT
            and banc.ihm.tableauDeBord.ecartAltitude is not None)


def test_affichage_des_hk_dates_et_presence(banc):
    """EX-IHM-020, 130, 140 : HK datés affichés, DPF et PFP vus présents."""
    tableau = banc.ihm.tableauDeBord
    assert tableau.textePresence(Acteur.DPF) == "EN ATTENTE"
    assert banc.tourner(jusqua=lambda: _present(banc))
    assert tableau.textePresence(Acteur.DPF) == "PRÉSENT"
    assert tableau.textePresence(Acteur.PFP) == "PRÉSENT"
    assert tableau.texteValeurHK(Acteur.DPF, "etat_treuil") == "ARRÊT"
    assert tableau.texteValeurHK(Acteur.DPF, "tension_alim").endswith(" V")
    assert tableau.texteValeurHK(Acteur.PFP, "etat_instrument") == "HORS TENSION"
    assert "UTC" in tableau._datesHK[Acteur.PFP].text()
    hk_dpf, hk_pfp = banc.lire("hk_dpf.csv"), banc.lire("hk_pfp.csv")
    assert len(hk_dpf) >= 2 and len(hk_pfp) >= 2
    assert hk_dpf[1][0].startswith(str(maintenant_utc().year))          # date GNSS


def test_consigne_de_distance_et_ecart_d_altitude(banc):
    """EX-IHM-040, 090, 100 : consigne envoyée, écart affiché, atteint à ±5 m."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    banc.ihm.panneauCommandes.saisieConsigne.setText("120,5")
    banc.ihm.panneauCommandes.boutonConsigne.click()
    assert banc.commandes[-1].typeCommande is TypeCommande.CONSIGNE_DISTANCE
    assert banc.commandes[-1].parametre == 120.5
    tableau = banc.ihm.tableauDeBord

    def arrive():
        hk = tableau.derniersHK.get(Acteur.DPF)
        return (hk is not None and hk.mesures["consigne_distance"] == pytest.approx(120.5)
                and hk.mesures["etat_treuil"] == 0 and banc.simulateur.dpf.longueur == 120.5
                and abs(tableau.ecartAltitude - 120.5) <= 5.0)

    assert banc.tourner(jusqua=arrive)
    assert "DANS LA TOLÉRANCE" in tableau._tolerance.text()
    assert tableau.texteEcart().endswith(" m")
    journal = banc.journal()
    assert any("Consigne de distance : 120,5 m" in ligne for ligne in journal)
    assert any("État du treuil" in ligne and "DESCENTE" in ligne for ligne in journal)


@pytest.mark.parametrize("texte", ["-1", "2000,1", "abc", "", "nan", "1e9"])
def test_consigne_hors_plage_refusee(banc, texte):
    """EX-IHM-110 : seules les consignes de 0 à 2000 m sont acceptées."""
    panneau = banc.ihm.panneauCommandes
    panneau.saisieConsigne.setText(texte)
    panneau.boutonConsigne.click()
    assert banc.commandes == []
    assert banc.ihm.liaisonEthernet.nbEmis == 0
    assert any("Consigne refusée" in ligne for ligne in banc.journal())


@pytest.mark.parametrize("valeur", [0, 0.0, 1999.9, 2000])
def test_consigne_aux_limites_acceptee(banc, valeur):
    """EX-IHM-110 : 0 et 2000 m sont acceptés."""
    assert banc.ihm.panneauCommandes.envoyerConsigne(valeur) is True
    assert banc.commandes[-1].parametre == pytest.approx(valeur)


def test_descente_montee_et_interruption(banc):
    """EX-IHM-030, 120 : descendre, monter, interrompre le mouvement en cours."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    panneau, dpf = banc.ihm.panneauCommandes, banc.simulateur.dpf
    panneau.boutonDescendre.click()
    assert banc.tourner(jusqua=lambda: dpf.etatTreuil == 1 and dpf.longueur > 20)
    panneau.boutonArret.click()
    assert banc.tourner(jusqua=lambda: dpf.etatTreuil == 0)
    arret = dpf.longueur
    assert 20 < arret < 2000
    banc.tourner(duree=0.3)
    assert dpf.longueur == arret                      # le treuil reste arrêté
    panneau.boutonMonter.click()
    assert banc.tourner(jusqua=lambda: dpf.etatTreuil == 2)
    assert banc.tourner(jusqua=lambda: dpf.longueur == 0 and dpf.etatTreuil == 0)
    types = [c.typeCommande for c in banc.commandes]
    assert types == [TypeCommande.DESCENTE, TypeCommande.ARRET, TypeCommande.MONTEE]
    assert all(c.destinataire is Acteur.DPF for c in banc.commandes)


def test_instrument_et_enregistrement_des_donnees(banc):
    """EX-IHM-050, 060, 070, 080 : ON/OFF, commandes, données datées dans un fichier dédié."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    panneau, pfp = banc.ihm.panneauCommandes, banc.simulateur.pfp
    pfp.PERIODE_DONNEES_S = 0.05
    panneau.boutonInstrumentOn.click()
    assert banc.commandes[-1].destinataire is Acteur.PFP
    assert banc.tourner(jusqua=lambda: pfp.instrumentSousTension
                        and banc.ihm.console.nbMessages >= 3)

    panneau.saisieInstrument.setText("MESURE?")
    panneau.boutonInstrument.click()
    panneau.choixFormat.setCurrentIndex(1)
    panneau.saisieInstrument.setText("01 A0 ff")
    panneau.boutonInstrument.click()
    assert banc.commandes[-2].charge == b"MESURE?"
    assert banc.commandes[-1].charge == b"\x01\xA0\xFF"
    banc.tourner(duree=0.3)

    panneau.boutonInstrumentOff.click()
    assert banc.tourner(jusqua=lambda: not pfp.instrumentSousTension)
    banc.tourner(duree=0.3)
    recus = banc.ihm.console.nbMessages
    banc.tourner(duree=0.3)
    assert banc.ihm.console.nbMessages == recus       # plus de données une fois hors tension

    lignes = banc.lire("donnees_instrument.csv")
    assert lignes[0] == ["date_gnss_utc", "date_reception_utc", "nb_octets", "donnees_hex"]
    donnees = [bytes.fromhex(ligne[3]) for ligne in lignes[1:]]
    assert len(donnees) == recus                      # tout ce qui est reçu est enregistré
    assert all(int(ligne[2]) == len(d) for ligne, d in zip(lignes[1:], donnees))
    assert b"RECU:MESURE?" in donnees and b"RECU:\x01\xA0\xFF" in donnees
    assert sum(len(d) for d in donnees) == banc.ihm.console.nbOctets
    # fichier dédié : aucune donnée instrument ailleurs
    assert not any("AA55" in " ".join(ligne) for ligne in banc.lire("journal.csv"))
    journal = banc.journal()
    assert any("Instrument sous tension" in ligne for ligne in journal)
    assert any("Instrument : HORS TENSION → SOUS TENSION" in ligne for ligne in journal)


def test_commande_instrument_invalide_refusee(banc):
    panneau = banc.ihm.panneauCommandes
    assert panneau.envoyerCommandeInstrument("", False) is False
    assert panneau.envoyerCommandeInstrument("ZZ", True) is False
    assert panneau.envoyerCommandeInstrument("é", False) is False
    assert panneau.envoyerCommandeInstrument("A" * 300, False) is False
    assert banc.commandes == []


def test_perte_de_la_pfp_puis_retour(banc):
    """EX-COM-130, EX-IHM-140, 160 : PFP perdue après 3 périodes sans HK, alerte, retour."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    s, tableau = banc.ihm.surveillancePresence, banc.ihm.tableauDeBord
    debut = time.monotonic()
    banc.simulateur.commander("radio off")
    assert banc.tourner(jusqua=lambda: s.etatPFP is EtatSousSysteme.PERDU)
    assert 2 * PERIODE <= time.monotonic() - debut <= 4.5 * PERIODE
    assert s.etatDPF is EtatSousSysteme.PRESENT       # le DPF, lui, reste présent
    assert tableau.textePresence(Acteur.PFP) == "PERDU"
    assert any(a.source is Acteur.PFP and a.code == "PERTE"
               for a in banc.ihm.gestionAlertes.alertesActives)
    assert banc.tourner(jusqua=lambda: any(
        a.source is Acteur.DPF and "radio" in a.description
        for a in banc.ihm.gestionAlertes.alertesActives))
    assert tableau.nombreAlertes() == len(banc.ihm.gestionAlertes.alertesActives) == 2

    banc.simulateur.commander("radio on")
    assert banc.tourner(jusqua=lambda: s.etatPFP is EtatSousSysteme.PRESENT
                        and not banc.ihm.gestionAlertes.alertesActives)
    assert tableau.nombreAlertes() == 0
    journal = banc.journal()
    assert any("La PFP ne répond plus" in ligne for ligne in journal)
    assert any("Fin d'alerte PFP" in ligne for ligne in journal)


def test_perte_du_dpf(banc):
    """EX-COM-130, EX-IHM-130 : DPF perdu, donc PFP perdue aussi (variante de CU7)."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    s = banc.ihm.surveillancePresence
    banc.simulateur.commander("eth off")
    assert banc.tourner(jusqua=lambda: s.etatDPF is EtatSousSysteme.PERDU
                        and s.etatPFP is EtatSousSysteme.PERDU)
    assert banc.ihm.tableauDeBord.textePresence(Acteur.DPF) == "PERDU"
    descriptions = [a.description for a in banc.ihm.gestionAlertes.alertesActives]
    assert any("Le DPF ne répond plus" in d and "HK de la PFP" in d for d in descriptions)
    assert any("La PFP ne répond plus" in d for d in descriptions)
    # une commande reste possible et journalisée, avec un avertissement
    banc.ihm.panneauCommandes.boutonArret.click()
    assert "n'est pas vu présent" in banc.ihm.statusBar().currentMessage()


def test_alertes_de_seuil_et_du_bord(banc):
    """EX-IHM-160 : alertes sur l'état du DPF ou de la PFP, effacées à la fin."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    alertes = banc.ihm.gestionAlertes
    banc.simulateur.commander("froid on")
    banc.simulateur.commander("treuil off")
    assert banc.tourner(jusqua=lambda: len(alertes.alertesActives) == 2)
    textes = sorted(a.description for a in alertes.alertesActives)
    assert textes[0] == "Défaut treuil"
    assert "Température interne sous le minimum : -34,0 °C" in textes[1]
    banc.simulateur.commander("froid off")
    banc.simulateur.commander("treuil on")
    assert banc.tourner(jusqua=lambda: not alertes.alertesActives)


def test_trames_invalides_ignorees(banc):
    """Une trame invalide ou mal adressée est rejetée et journalisée, sans arrêt de l'IHM."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    port = banc.ihm.liaisonEthernet.portEcoute
    emetteur = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    emetteur.sendto(b"n'importe quoi", ("127.0.0.1", port))
    trame = bytearray(Commande(TypeCommande.ARRET).coder())
    trame[-1] ^= 0xFF
    emetteur.sendto(bytes(trame), ("127.0.0.1", port))
    emetteur.sendto(Commande(TypeCommande.ARRET).coder(), ("127.0.0.1", port))   # pour le DPF
    emetteur.close()
    assert banc.tourner(jusqua=lambda: banc.ihm.liaisonEthernet.nbRejetes == 2)
    banc.tourner(duree=0.2)
    journal = banc.journal()
    assert sum("trame rejetée" in ligne for ligne in journal) == 2
    assert any("Message ignoré : destinataire DPF" in ligne for ligne in journal)
    assert _present(banc)


def test_journal_date_des_commandes_et_evenements(banc):
    """EX-IHM-150 : commandes et événements journalisés avec leur date."""
    banc.ihm.panneauCommandes.boutonDescendre.click()
    banc.ihm.panneauCommandes.boutonArret.click()
    lignes = banc.lire("journal.csv")
    assert lignes[0] == ["date_utc", "categorie", "evenement"]
    commandes = [ligne for ligne in lignes[1:] if ligne[1] == "COMMANDE"]
    assert [ligne[2] for ligne in commandes] == ["Descente (vers DPF)", "Arrêt (vers DPF)"]
    for ligne in lignes[1:]:
        assert ligne[0][:4] == str(maintenant_utc().year) and len(ligne[0]) == 23
    assert any("Démarrage de la station sol" in ligne[2] for ligne in lignes)


def test_port_d_ecoute_deja_pris(application, tmp_path):
    """Si le port UDP est occupé, l'IHM démarre quand même et l'affiche en alerte."""
    occupe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    occupe.bind(("127.0.0.1", 0))
    config = Configuration(adresse_dpf="127.0.0.1", port_ecoute=occupe.getsockname()[1],
                           adresse_locale="127.0.0.1", dossier=str(tmp_path))
    ihm = IHM(config)
    ihm.demarrer()
    try:
        assert ihm.tableauDeBord.textePresence(Acteur.DPF) == "PORT FERMÉ"
        assert [a.code for a in ihm.gestionAlertes.alertesActives] == ["PORT"]
    finally:
        ihm.close()
        occupe.close()


def test_ecart_signale_ancien_si_la_pfp_est_perdue(banc):
    """EX-IHM-090 : un écart qui n'est plus mis à jour n'est pas présenté comme actuel."""
    assert banc.tourner(jusqua=lambda: _present(banc))
    tableau = banc.ihm.tableauDeBord
    banc.tourner(duree=0.2)
    assert "ANCIENNE" not in tableau._tolerance.text()
    banc.simulateur.commander("radio off")
    s = banc.ihm.surveillancePresence
    assert banc.tourner(jusqua=lambda: s.etatPFP is EtatSousSysteme.PERDU)
    date_figee = tableau._dateEcart
    banc.tourner(duree=2 * PERIODE)
    assert tableau._dateEcart == date_figee           # aucune fausse mise à jour
    assert tableau._tolerance.text() == "VALEUR ANCIENNE"

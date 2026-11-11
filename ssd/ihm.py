"""IHM : fenêtre principale de la station sol (diagramme de classes).

L'IHM compose PanneauCommandes, TableauDeBord, SurveillancePresence,
GestionAlertes et LiaisonEthernet. Elle envoie les commandes, traite les
messages reçus, tient le journal et enregistre les données de l'instrument.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QScrollArea, QTabWidget, QWidget,
)

from . import __version__, enregistrement
from .alertes import Alerte, GestionAlertes
from .config import Configuration
from .icd import CHAMPS_HK, Acteur
from .liaison import LiaisonEthernet
from .messages import (
    HK, Commande, DonneeInstrument, EcartAltitude, Message, formater_date,
    formater_valeur, maintenant_utc,
)
from .panneau_commandes import PanneauCommandes
from .surveillance import EtatSousSysteme, SurveillancePresence
from .tableau_de_bord import TableauDeBord
from .vues import ConsoleInstrument, CourbesHK, VueJournal


class IHM(QMainWindow):
    """Interface de contrôle-commande du Système Profiler Ballon."""

    PERIODE_RECEPTION_MS = 20      # scrutation du port UDP
    MESSAGES_PAR_SCRUTATION = 200  # borne pour garder l'interface réactive

    def __init__(self, config: Configuration | None = None) -> None:
        super().__init__()
        self.config = config or Configuration()
        self.enService = False
        self.fichierJournal: enregistrement.FichierCSV | None = None
        self.fichierDonnees: enregistrement.FichierCSV | None = None
        self.fichiersHK: dict[Acteur, enregistrement.FichierCSV] = {}
        self.dossierSession: Path | None = None

        # Composition (diagramme de classes)
        self.panneauCommandes = PanneauCommandes()
        self.tableauDeBord = TableauDeBord()
        self.surveillancePresence = SurveillancePresence(
            self.config.periode_hk_s, self.config.seuil_perte)
        self.gestionAlertes = GestionAlertes()
        self.liaisonEthernet = LiaisonEthernet(
            self.config.adresse_dpf, self.config.port_dpf,
            self.config.port_ecoute, self.config.adresse_locale)

        self._minuterieReception = QTimer(self)
        self._minuterieReception.setInterval(self.PERIODE_RECEPTION_MS)
        self._minuterieReception.timeout.connect(self._lire_liaison)
        self._minuterieSeconde = QTimer(self)
        self._minuterieSeconde.setInterval(1000)
        self._minuterieSeconde.timeout.connect(self._chaque_seconde)

        self._construire()
        self._relier()

    # ------------------------------------------------------------------
    # Interface du diagramme de classes
    # ------------------------------------------------------------------

    def demarrer(self) -> None:
        """Ouvre les fichiers et la liaison Ethernet, lance la surveillance."""
        if self.enService:
            return
        debut = maintenant_utc()
        self.dossierSession = enregistrement.creer_dossier_session(self.config.dossier, debut)
        self.fichierJournal = enregistrement.ouvrir_journal(self.dossierSession)
        self.fichierDonnees = enregistrement.ouvrir_donnees_instrument(self.dossierSession)
        self.fichiersHK = {acteur: enregistrement.ouvrir_archive_hk(self.dossierSession, acteur)
                           for acteur in CHAMPS_HK}
        self.console.definirFichier(str(self.fichierDonnees.chemin.resolve()))
        self._etatDossier.setText(f"Session : {self.dossierSession.resolve()}")
        self.enService = True

        self.journaliser(debut, f"Démarrage de la station sol (version {__version__})")
        self.journaliser(
            debut, f"Surveillance : HK attendus toutes les {self.config.periode_hk_s:g} s, "
            f"perte déclarée après {self.surveillancePresence.delaiPerte():g} s sans HK")
        try:
            self.liaisonEthernet.ouvrir()
        except OSError as erreur:
            detail = f"Port UDP {self.config.port_ecoute} indisponible"
            self.tableauDeBord.afficherEtatLiaison(False, detail)
            self.gestionAlertes.declencher(Alerte(
                Acteur.SSD, f"{detail} : aucune réception possible ({erreur})",
                maintenant_utc(), "PORT"))
        else:
            self.tableauDeBord.afficherEtatLiaison(True)
            self.journaliser(
                maintenant_utc(),
                f"Liaison Ethernet ouverte : écoute sur le port UDP "
                f"{self.liaisonEthernet.portEcoute}, commandes vers "
                f"{self.config.adresse_dpf}:{self.config.port_dpf}")
        self._minuterieReception.start()
        self._minuterieSeconde.start()

    def arreter(self) -> None:
        """Arrête la réception et ferme proprement les fichiers."""
        if not self.enService:
            return
        self._minuterieReception.stop()
        self._minuterieSeconde.stop()
        self.journaliser(maintenant_utc(), "Arrêt de la station sol")
        self.enService = False
        self.liaisonEthernet.fermer()
        for fichier in (self.fichierJournal, self.fichierDonnees, *self.fichiersHK.values()):
            if fichier is not None:
                fichier.fermer()

    def envoyerCommande(self, c: Commande) -> None:
        """Envoie une commande au DPF et la journalise [EX-IHM-150]."""
        try:
            self.liaisonEthernet.envoyer(c)
        except (OSError, ValueError) as erreur:
            self.journaliser(maintenant_utc(),
                             f"ÉCHEC d'envoi : {c.description()} ({erreur})", "ERREUR")
            self.statusBar().showMessage(f"Commande non envoyée : {erreur}", 8000)
            return
        self.journaliser(maintenant_utc(), c.description(), "COMMANDE")
        avertissement = ""
        if self.surveillancePresence.etatDPF is not EtatSousSysteme.PRESENT:
            avertissement = "  (attention : le DPF n'est pas vu présent)"
        self.statusBar().showMessage(f"Commande envoyée : {c.description()}{avertissement}", 8000)
        self._actualiser_compteurs()

    def traiterMessage(self, m: Message) -> None:
        """Aiguille un message reçu selon son type."""
        if m.destinataire is not Acteur.SSD:
            self.journaliser(maintenant_utc(),
                             f"Message ignoré : destinataire {m.destinataire.name} "
                             f"(reçu de {m.source.name})", "ERREUR")
            return
        if isinstance(m, HK):
            self._traiter_hk(m)
        elif isinstance(m, DonneeInstrument):
            self.enregistrerDonnee(m)
        elif isinstance(m, EcartAltitude):
            self.tableauDeBord.afficherEcartAltitude(m.valeur, m.date)
        else:
            self.journaliser(maintenant_utc(),
                             f"Message inattendu de {m.source.name} : {m.type.name}", "ERREUR")

    def journaliser(self, date: datetime, evenement: str,
                    categorie: str = "EVENEMENT") -> None:
        """Ajoute une ligne datée au journal (fichier + affichage) [EX-IHM-150]."""
        if self.fichierJournal is not None and self.enService:
            self.fichierJournal.ecrire([formater_date(date, True), categorie, evenement])
        self.vueJournal.ajouter(date, categorie, evenement)

    def enregistrerDonnee(self, d: DonneeInstrument) -> None:
        """Enregistre une donnée instrument dans le fichier dédié [EX-IHM-070/080]."""
        if self.fichierDonnees is not None:
            self.fichierDonnees.ecrire(
                enregistrement.ligne_donnee_instrument(d, maintenant_utc()))
        self.console.ajouter(d)

    # ------------------------------------------------------------------
    # Traitements internes
    # ------------------------------------------------------------------

    def _traiter_hk(self, hk: HK) -> None:
        precedent = self.tableauDeBord.derniersHK.get(hk.source)
        self.surveillancePresence.signalerReceptionHK(hk.source)
        self.tableauDeBord.afficherHK(hk)
        self.courbes.ajouter(hk)
        if hk.source in self.fichiersHK:
            self.fichiersHK[hk.source].ecrire(enregistrement.ligne_hk(hk, maintenant_utc()))
        self.gestionAlertes.analyserHK(hk)

        # Les changements d'état vus dans les HK tiennent lieu de compte rendu
        # des commandes (il n'y a pas d'acquittement sur UDP).
        for champ in CHAMPS_HK[hk.source]:
            if champ.valeurs is None:
                continue
            valeur = hk.mesures[champ.nom]
            if precedent is not None and precedent.mesures[champ.nom] != valeur:
                self.journaliser(
                    maintenant_utc(),
                    f"{hk.source.name} : {champ.libelle} : "
                    f"{formater_valeur(champ, precedent.mesures[champ.nom])} → "
                    f"{formater_valeur(champ, valeur)}")
            if champ.nom == "etat_treuil":
                self.panneauCommandes.afficherEtatTreuil(formater_valeur(champ, valeur))
            elif champ.nom == "etat_instrument":
                self.panneauCommandes.afficherEtatInstrument(formater_valeur(champ, valeur))

    def _lire_liaison(self) -> None:
        for _ in range(self.MESSAGES_PAR_SCRUTATION):
            message = self.liaisonEthernet.recevoir()
            if message is None:
                break
            self.traiterMessage(message)
        self._actualiser_compteurs()

    def _chaque_seconde(self) -> None:
        self.surveillancePresence.verifierPeriode()
        self.tableauDeBord.rafraichir()

    def _changement_presence(self, acteur: Acteur, etat: EtatSousSysteme) -> None:
        """Appelé par SurveillancePresence : affichage, journal et alerte."""
        if acteur is Acteur.DPF:
            self.tableauDeBord.afficherPresenceDPF(etat)
        else:
            self.tableauDeBord.afficherPresencePFP(etat)
        nom = "Le DPF" if acteur is Acteur.DPF else "La PFP"
        if etat is EtatSousSysteme.PERDU:
            delai = self.surveillancePresence.delaiPerte()
            texte = (f"{nom} ne répond plus : aucun HK reçu depuis {delai:g} s "
                     f"({self.surveillancePresence.seuilPerte} périodes)")
            if acteur is Acteur.DPF:
                # Variante de CU7 : sans le DPF, plus rien n'arrive de la PFP.
                texte += " ; les HK de la PFP ne peuvent plus arriver non plus"
            self.gestionAlertes.declencher(Alerte(acteur, texte, maintenant_utc(), "PERTE"))
        elif etat is EtatSousSysteme.PRESENT:
            if not self.gestionAlertes.effacerCode(acteur, "PERTE"):
                vu = "est vu présent" if acteur is Acteur.DPF else "est vue présente"
                self.journaliser(maintenant_utc(), f"{nom} {vu} (premier HK reçu)")

    def _alerte_declenchee(self, a: Alerte) -> None:
        self.tableauDeBord.afficherAlerte(a)
        self.journaliser(maintenant_utc(), f"{a.source.name} : {a.description}", "ALERTE")

    def _alerte_effacee(self, a: Alerte) -> None:
        self.tableauDeBord.retirerAlerte(a)
        self.journaliser(maintenant_utc(),
                         f"Fin d'alerte {a.source.name} : {a.description}")

    def _erreur_liaison(self, texte: str) -> None:
        self.journaliser(maintenant_utc(), f"Liaison Ethernet : {texte}", "ERREUR")

    def _actualiser_compteurs(self) -> None:
        liaison = self.liaisonEthernet
        texte = (f"Messages émis : {liaison.nbEmis}   reçus : {liaison.nbRecus}   "
                 f"rejetés : {liaison.nbRejetes}")
        if texte != self._etatCompteurs.text():
            self._etatCompteurs.setText(texte)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _construire(self) -> None:
        self.setWindowTitle("Station sol – Système Profiler Ballon (PGE)")
        self.resize(1500, 900)
        self.setMinimumSize(1180, 700)

        self.vueJournal = VueJournal()
        self.console = ConsoleInstrument()
        self.courbes = CourbesHK()
        self.courbes.selectionner(Acteur.PFP, "temperature_interne")
        self.onglets = QTabWidget()
        self.onglets.addTab(self.vueJournal, "Journal")
        self.onglets.addTab(self.console, "Données instrument")
        self.onglets.addTab(self.courbes, "Courbes des HK")
        self.tableauDeBord.installerOnglets(self.onglets)
        self.tableauDeBord.delaiPeremption = self.surveillancePresence.delaiPerte()

        defilement = QScrollArea()
        defilement.setWidget(self.panneauCommandes)
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QScrollArea.NoFrame)
        defilement.setFixedWidth(320)

        centre = QWidget()
        disposition = QHBoxLayout(centre)
        disposition.setContentsMargins(10, 10, 10, 6)
        disposition.setSpacing(10)
        disposition.addWidget(defilement)
        disposition.addWidget(self.tableauDeBord, 1)
        self.setCentralWidget(centre)

        self._etatCompteurs = QLabel()
        self._etatDossier = QLabel("Session : non démarrée")
        self.statusBar().addPermanentWidget(self._etatCompteurs)
        self.statusBar().addPermanentWidget(self._etatDossier)
        self._actualiser_compteurs()

    def _relier(self) -> None:
        self.panneauCommandes.commandeDemandee.connect(self.envoyerCommande)
        self.panneauCommandes.saisieRefusee.connect(
            lambda texte: self.journaliser(maintenant_utc(), texte, "ERREUR"))
        self.surveillancePresence.surChangement = self._changement_presence
        self.gestionAlertes.surDeclenchement = self._alerte_declenchee
        self.gestionAlertes.surEffacement = self._alerte_effacee
        self.liaisonEthernet.surErreur = self._erreur_liaison

    def closeEvent(self, evenement) -> None:      # noqa: N802 (nom imposé par Qt)
        self.arreter()
        super().closeEvent(evenement)

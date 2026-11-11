# Station sol (SSD) — Système Profiler Ballon

IHM de la station sol du PGE, groupe Station sol & Communications, avec un simulateur du DPF et de la PFP pour l'essayer sans matériel.

Le code suit les exigences du groupe v2 (20/10/2026), les cas d'utilisation CU1 à CU9 et le diagramme de classes « IHM et communication ». Aucun document d'interface n'existant, le format des messages est une **proposition** décrite dans `docs/ICD_messages_v0.md`.

## Installation

Python 3.10 ou plus récent.

```
python -m venv .venv
.venv\Scripts\activate          (Windows)     source .venv/bin/activate   (Linux, macOS)
pip install -r requirements.txt
```

## Essai sur un seul PC, avec le simulateur

Depuis ce dossier, dans deux terminaux :

```
python -m simulateur
python -m ssd --config config_demo.ini
```

Le simulateur émet des HK toutes les 5 s. Dans son terminal, on peut provoquer des pannes : `radio off` (perte de la PFP), `eth off` (perte du DPF), `froid on`, `cc on`, `treuil off` ; `aide` donne la liste. Une descente de 2000 m dure 22 min à 1,5 m/s : `python -m simulateur --vitesse 20` l'accélère.

Si Windows demande d'autoriser Python sur le réseau, accepter pour les réseaux privés.

## Utilisation avec le vrai DPF

```
python -m ssd --config config.ini
```

`config.ini` contient l'adresse du DPF, les ports UDP et la période des HK. Les valeurs par défaut (DPF en `172.20.4.10`, ports 5000 et 5001) sont à confirmer avec le groupe DPF.

## Fichiers produits

Un dossier par session dans `enregistrements/`, nommé d'après la date UTC de démarrage :

| Fichier | Contenu | Exigence |
|---|---|---|
| `journal.csv` | Commandes envoyées, événements, alertes, avec leur date | EX-IHM-150 |
| `donnees_instrument.csv` | Données de l'instrument : date GNSS, date de réception, taille, octets en hexadécimal | EX-IHM-070, 080 |
| `hk_dpf.csv`, `hk_pfp.csv` | Tous les HK reçus | — |

Séparateur « ; », dates en UTC, décimales avec un point (lecture directe avec pandas : `pd.read_csv(f, sep=";")`). Chaque ligne est écrite sur le disque dès sa réception.

## Organisation du code

| Fichier | Classes du diagramme | Rôle |
|---|---|---|
| `ssd/icd.py` | `Acteur`, `TypeMessage`, `TypeCommande` | Codes, tailles, **liste des HK et des alertes** : le fichier à modifier quand l'interface sera figée |
| `ssd/messages.py` | `Message`, `Commande`, `HK`, `DonneeInstrument`, `EcartAltitude` | Codage et décodage des trames |
| `ssd/liaison.py` | `Liaison`, `LiaisonEthernet` | UDP/IP |
| `ssd/surveillance.py` | `SurveillancePresence`, `EtatSousSysteme` | Perte du DPF et de la PFP |
| `ssd/alertes.py` | `GestionAlertes`, `Alerte` | Alertes actives |
| `ssd/panneau_commandes.py` | `PanneauCommandes` | Boutons et saisies de l'opérateur |
| `ssd/tableau_de_bord.py` | `TableauDeBord` | HK, écart d'altitude, présence, alertes |
| `ssd/ihm.py` | `IHM` | Fenêtre principale, journal, enregistrement |
| `ssd/vues.py`, `enregistrement.py`, `config.py`, `style.py` | — | Onglets, fichiers CSV, configuration, apparence |
| `simulateur/simulateur.py` | `PasserelleDPF`, `LiaisonDPF_PFP` | DPF et PFP simulés |

Les noms de classes, d'attributs et de méthodes sont ceux du diagramme. Les écarts sont listés dans `docs/Propositions_exigences_v3.md`, partie D.

## Tests

```
python -m pytest
```

57 tests : format des messages, surveillance, alertes, et l'IHM complète face au simulateur (sans écran).

## Couverture des exigences IHM

| Exigence | Réalisation | Test |
|---|---|---|
| EX-IHM-010 PC standard, Ethernet | Python + PySide6, socket UDP du PC | inspection |
| EX-IHM-020 HK datés affichés | `TableauDeBord.afficherHK` | `test_affichage_des_hk_dates_et_presence` |
| EX-IHM-030 descente, montée | `PanneauCommandes.descendre`, `monter` | `test_descente_montee_et_interruption` |
| EX-IHM-040 consigne de distance | `PanneauCommandes.envoyerConsigne` | `test_consigne_de_distance_et_ecart_d_altitude` |
| EX-IHM-050 instrument ON/OFF | `mettreInstrumentSousTension`, `…HorsTension` | `test_instrument_et_enregistrement_des_donnees` |
| EX-IHM-060 commandes à l'instrument | `envoyerCommandeInstrument` (ASCII ou hexadécimal) | idem |
| EX-IHM-070 données enregistrées, datées, au fil de l'eau | `IHM.enregistrerDonnee` | idem |
| EX-IHM-080 fichier dédié | `donnees_instrument.csv` | idem |
| EX-IHM-090 écart affiché en continu | `TableauDeBord.afficherEcartAltitude` | `test_consigne_…`, `test_ecart_signale_ancien_…` |
| EX-IHM-100 écart issu des deux GNSS | calculé à bord, message `EcartAltitude` | simulateur |
| EX-IHM-110 consigne de 0 à 2000 m | `PanneauCommandes.verifierConsigne` | `test_consigne_hors_plage_refusee`, `…_aux_limites_acceptee` |
| EX-IHM-120 interruption | bouton ARRÊT, `arreterMouvement` | `test_descente_montee_et_interruption` |
| EX-IHM-130 état de la liaison avec le DPF | `afficherPresenceDPF` | `test_perte_du_dpf` |
| EX-IHM-140 présence de la PFP | `afficherPresencePFP` | `test_perte_de_la_pfp_puis_retour` |
| EX-IHM-150 journal daté | `IHM.journaliser`, `journal.csv` | `test_journal_date_des_commandes_et_evenements` |
| EX-IHM-160 alertes | `GestionAlertes`, `afficherAlerte` | `test_alertes_de_seuil_et_du_bord` |
| EX-COM-130 perte après 3 périodes | `SurveillancePresence` | `tests/test_surveillance.py` |

## Limites connues

- Le format des messages et le contenu des HK sont des propositions : ils changeront avec le document d'interface.
- Aucune retransmission ni acquittement (hypothèse « UDP parfait » des exigences). L'effet d'une commande se lit dans le HK suivant.
- Testé sous Linux sans écran ; pas encore essayé sous Windows ni avec une vraie carte DPF.
- Le simulateur sert à valider l'IHM : ce n'est pas le logiciel embarqué.

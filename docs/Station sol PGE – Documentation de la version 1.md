# Station sol PGE – Documentation de la version 1

Nov 10, 2026 · @Hadi

## En bref

La version 1 est une station sol complète, testée contre un simulateur, mais jamais contre du vrai matériel.

| Livré dans `pge_station_sol.zip` | Où |
| --- | --- |
| L'IHM (fenêtre Python + PySide6 + pyqtgraph) | dossier `ssd/` |
| Un simulateur du DPF et de la PFP | dossier `simulateur/` |
| 57 tests automatiques | dossier `tests/` |
| Une proposition de format des messages | `docs/ICD_messages_v0.md` |
| Des propositions pour la v3 des exigences | `docs/Propositions_exigences_v3.md` |

Trois limites à garder en tête en lisant la suite :

1. **Le format des messages et la liste des HK sont de moi.** Il n'existait pas de document d'interface, j'ai donc proposé les deux. Rien n'est validé par l'équipe ni par les groupes DPF et PFP.
2. **Je n'ai testé que sous Linux, sans écran, IHM et simulateur sur la même machine.** Pas sous Windows, pas à travers un câble Ethernet, pas à travers un routeur.
3. **Le logiciel embarqué du DPF n'existe pas.** Le simulateur le remplace pour les essais ; il ne tournera jamais sur la carte.

Pour installer et essayer, lis « Installation pas à pas » puis « Premier essai pas à pas ». Pour savoir quoi vérifier et quoi décider, va à « Ce qui manque » et « Points pas clairs pour moi ».

## Installation pas à pas

Il te faut Python 3.10 ou plus récent et trois paquets ; rien d'autre à télécharger.

### Ce dont tu as besoin

| Élément | Version | À quoi il sert |
| --- | --- | --- |
| Python | 3.10 minimum ; j'ai testé avec 3.13 | Le langage |
| PySide6 | 6.6 minimum ; testé avec 6.12 | Les fenêtres et boutons (Qt) |
| pyqtgraph | 0.13 minimum ; testé avec 0.14 | Les courbes ; installe numpy tout seul |
| pytest | 8 minimum ; testé avec 9.1 | Lancer les tests, pas nécessaire pour utiliser l'IHM |
| `socket`, `struct`, `csv`, `configparser` | Livrés avec Python | Réseau UDP, trames, fichiers, configuration |

Les trois paquets sont listés dans `requirements.txt`. Internet ne sert que pour cette installation.

### Étapes sous Windows

1. **Installer Python** depuis python.org. Dans l'installateur, coche « Add python.exe to PATH ». Vérifie dans un terminal : `python --version`.
2. **Dézipper** `pge_station_sol.zip`, par exemple dans `C:\PGE\pge_station_sol`.
3. **Ouvrir un terminal dans ce dossier** : celui qui contient `ssd`, `simulateur` et `requirements.txt`. Dans VS Code : Fichier > Ouvrir le dossier, puis Terminal > Nouveau terminal.
4. **Créer l'environnement virtuel** : `python -m venv .venv`
5. **L'activer** : `.venv\Scripts\activate`. Le texte `(.venv)` apparaît au début de la ligne.
6. **Installer les paquets** : `pip install -r requirements.txt`. PySide6 est gros, compte quelques minutes.
7. **Vérifier** : `python -m pytest`. Tu dois lire `57 passed`.

Sous Linux ou macOS, seules les étapes 4 et 5 changent : `python3 -m venv .venv` puis `source .venv/bin/activate`.

À chaque nouveau terminal, il faut refaire l'étape 5 (activer l'environnement) avant de lancer quoi que ce soit.

### Pannes courantes

| Ce que tu vois | Cause probable | Quoi faire |
| --- | --- | --- |
| `python` n'est pas reconnu | Python absent du PATH | Réinstaller en cochant la case, ou essayer `py` à la place de `python` |
| PowerShell refuse `activate` (« l'exécution de scripts est désactivée ») | Politique d'exécution de PowerShell | Taper `Set-ExecutionPolicy -Scope Process RemoteSigned` puis réessayer, ou utiliser l'invite de commandes (cmd) |
| `No module named ssd` | Terminal ouvert dans le mauvais dossier | Se placer dans le dossier qui contient `ssd` |
| `No module named PySide6` | Environnement non activé | Refaire l'étape 5 |
| Voyant « PORT FERMÉ » dans l'IHM | Le port 5000 est déjà pris, souvent par une autre IHM ouverte | Fermer l'autre fenêtre, ou changer `port_ecoute` dans le fichier `.ini` |
| Le simulateur dit « Impossible d'ouvrir le port UDP 5001 » | Un autre simulateur tourne déjà | Le fermer |
| Les voyants restent « EN ATTENTE » | Simulateur non lancé, ou pare-feu | Lancer le simulateur ; autoriser Python dans le pare-feu Windows |

Je n'ai pas pu exécuter ces étapes sous Windows moi-même : si l'une d'elles échoue, copie-moi le message d'erreur exact.

## Premier essai pas à pas

L'essai complet prend une dizaine de minutes, avec deux terminaux sur le même PC.

### Lancer

1. **Terminal 1, le simulateur** : `python -m simulateur --vitesse 20`. Il affiche la liste des pannes qu'on peut provoquer. L'option `--vitesse 20` fait tourner le treuil à 20 m/s au lieu de 1,5 m/s, pour ne pas attendre.
2. **Terminal 2, l'IHM** : `python -m ssd --config config_demo.ini`. La fenêtre s'ouvre.
3. En moins de 5 s, les deux voyants du haut passent de « EN ATTENTE » à « PRÉSENT ».

Les pannes se tapent dans le terminal 1, suivies de Entrée. `aide` redonne la liste, `etat` affiche l'état simulé, `quitter` arrête.

### Scénario de test

Fais les étapes dans l'ordre et note le numéro de celles qui ne donnent pas le résultat attendu.

| N° | Action | Résultat attendu | Exigence |
| --- | --- | --- | --- |
| 1 | Attendre 5 s après le lancement | Voyants DPF et PFP « PRÉSENT » ; tableaux HK remplis et datés ; écart proche de 0 m | EX-IHM-020, 130, 140 |
| 2 | Saisir `350` dans la consigne, cliquer Envoyer | Journal : « Consigne de distance : 350,0 m » ; treuil DESCENTE puis ARRÊT ; écart proche de 350 m ; « DANS LA TOLÉRANCE ±5 m » | EX-IHM-040, 090 |
| 3 | Saisir `2500`, Envoyer | Message rouge « Consigne refusée » ; rien n'est envoyé | EX-IHM-110 |
| 4 | Cliquer Descendre, puis ARRÊT après quelques secondes | Treuil DESCENTE puis ARRÊT ; l'écart ne bouge plus | EX-IHM-030, 120 |
| 5 | Cliquer Monter | L'écart revient vers 0 m, puis treuil ARRÊT | EX-IHM-030 |
| 6 | Instrument : « Sous tension » | État connu « SOUS TENSION » ; l'onglet Données instrument se remplit toutes les 4 s environ | EX-IHM-050, 070 |
| 7 | Taper `STATUS?`, cliquer Envoyer à l'instrument | Un bloc contenant `RECU:STATUS?` dans Données instrument | EX-IHM-060 |
| 8 | Instrument : « Hors tension » | Plus aucune nouvelle donnée | EX-IHM-050 |
| 9 | Simulateur : `radio off` | Après 15 à 20 s : PFP « PERDU », deux alertes, écart marqué « VALEUR ANCIENNE ». Puis `radio on` : tout revient | EX-IHM-140, 160 ; EX-COM-130 |
| 10 | Simulateur : `eth off` | Après 15 à 20 s : DPF et PFP « PERDU ». Puis `eth on` | EX-IHM-130 |
| 11 | Simulateur : `froid on` | Alerte « Température interne sous le minimum : -34,0 °C », valeur en rouge. Puis `froid off` | EX-IHM-160 |
| 12 | Simulateur : `cc on` puis `treuil off` | Alertes « Instrument disjoncté » et « Défaut treuil ». Puis `cc off` et `treuil on` | EX-IHM-160 |
| 13 | Fermer la fenêtre, ouvrir `enregistrements`, puis le dossier daté | Quatre fichiers CSV, voir ci-dessous | EX-IHM-070, 080, 150 |

Les alertes et les changements d'état arrivent avec le HK suivant, donc avec jusqu'à 5 s de retard en démo.

### Fichiers à contrôler

| Fichier | Ce que tu dois y trouver |
| --- | --- |
| `journal.csv` | Une ligne datée par commande envoyée, par alerte et par changement d'état |
| `donnees_instrument.csv` | Une ligne par bloc reçu : date GNSS, date de réception, taille, octets en hexadécimal |
| `hk_dpf.csv`, `hk_pfp.csv` | Une ligne par HK reçu |

Le séparateur est « ; » et les décimales sont avec un point. Excel en français peut lire ces nombres comme du texte ; pandas les lit directement avec `pd.read_csv(fichier, sep=";")`.

### Tests automatiques

`python -m pytest` lance les 57 tests en 10 s environ, sans ouvrir de fenêtre. `python -m pytest -v` affiche le nom de chaque test ; ceux de `tests/test_ihm.py` citent l'exigence qu'ils vérifient.

### Essai sur deux PC, par câble Ethernet

Je ne l'ai pas fait : c'est le premier essai qui sortira du cadre que j'ai vérifié.

1. Relier les deux PC par un câble ou un switch et leur donner une adresse fixe, par exemple `172.20.3.10` (IHM) et `172.20.3.20` (simulateur).
2. Sur le second PC : `python -m simulateur --adresse-ssd 172.20.3.10`
3. Sur le premier, mettre `adresse_dpf = 172.20.3.20` et `periode_hk_s = 5` dans `config.ini`, puis `python -m ssd --config config.ini`
4. Autoriser Python dans le pare-feu du PC de l'IHM, en UDP entrant sur le port 5000.

## Visite de l'écran

L'écran a trois colonnes : les commandes à gauche, la surveillance au centre, les HK à droite.

&#91;image: L'IHM pendant un essai avec le simulateur : consigne de 350 m atteinte, instrument sous tension\]

Capture prise pendant un essai avec le simulateur, après une consigne de 350 m.

| Zone | Ce qu'elle montre | Cas d'utilisation |
| --- | --- | --- |
| Gauche, « Déplacement de la PFP » | Boutons Descendre, Monter, ARRÊT ; saisie de la consigne (0 à 2000 m) ; état du treuil lu dans le dernier HK | CU1, CU2 |
| Gauche, « Instrument scientifique » | Sous tension, Hors tension ; commande en texte ASCII ou en hexadécimal, avec fin de ligne au choix ; état de l'instrument lu dans le dernier HK | CU3 |
| Haut, trois voyants | Liaison Ethernet avec le DPF, présence de la PFP, heure UTC du PC. Sous chaque voyant : l'âge du dernier HK | CU4 |
| Centre, « Écart d'altitude DPF – PFP » | La valeur en grand, la date GNSS de la mesure, son âge, la consigne en cours, la différence avec la consigne, et la courbe avec la consigne en pointillés | CU4 |
| Centre, « Alertes actives » | Une ligne rouge par alerte en cours ; elle disparaît seule quand la cause disparaît | CU4 |
| Bas, onglet Journal | Commandes envoyées, événements, alertes, erreurs, avec leur date | CU9 |
| Bas, onglet Données instrument | Chaque bloc reçu, en hexadécimal et en ASCII, et le chemin du fichier d'enregistrement | CU5 |
| Bas, onglet Courbes des HK | La courbe d'un paramètre de HK au choix | CU4 |
| Droite, « Housekeeping DPF » et « PFP » | La date GNSS du dernier HK, son âge, puis chaque valeur ; en rouge si elle sort d'un seuil du cahier des charges | CU4 |
| Barre du bas | Dernière commande envoyée, compteurs de messages émis, reçus, rejetés, dossier de la session |  |

Les voyants de présence prennent quatre valeurs :

| Valeur | Sens |
| --- | --- |
| EN ATTENTE (orange) | Aucun HK reçu depuis le démarrage, délai de perte pas encore écoulé |
| PRÉSENT (vert) | Un HK reçu depuis moins de 3 périodes |
| PERDU (rouge) | Aucun HK depuis 3 périodes ; une alerte est levée |
| PORT FERMÉ (rouge) | Le port UDP du PC n'a pas pu s'ouvrir : l'IHM ne peut rien recevoir |

Sous l'écart d'altitude, une étiquette résume la situation : « DÉPLACEMENT EN COURS », « DANS LA TOLÉRANCE ±5 m », « HORS TOLÉRANCE ±5 m » ou « VALEUR ANCIENNE ». Cette dernière apparaît quand le DPF ou la PFP est perdu, ou quand aucune nouvelle mesure n'arrive (5 s en déplacement, 3 périodes de HK au repos).

Le bouton ARRÊT n'est jamais désactivé et aucune commande ne demande de confirmation.

## Comment le code fonctionne

L'IHM tourne sur deux minuteries : toutes les 20 ms elle lit le port UDP, toutes les secondes elle vérifie les pertes et rafraîchit les âges affichés. Il n'y a aucun thread.

&#91;embedded content: Architecture de l'IHM · 8 blocs\]

La classe `IHM` est au centre : aucun autre bloc ne parle directement au réseau ni aux fichiers. Le DPF, ou le simulateur à sa place, est la seule chose extérieure au PC.

### Les fichiers

| Fichier | Classes du diagramme | Rôle |
| --- | --- | --- |
| `ssd/icd.py` | `Acteur`, `TypeMessage`, `TypeCommande` | Tous les codes, tailles, la liste des HK et des alertes |
| `ssd/messages.py` | `Message`, `Commande`, `HK`, `DonneeInstrument`, `EcartAltitude` | Transformer un message en octets et l'inverse |
| `ssd/liaison.py` | `Liaison`, `LiaisonEthernet` | Envoyer et recevoir en UDP avec le module `socket` |
| `ssd/surveillance.py` | `SurveillancePresence`, `EtatSousSysteme` | Décider si le DPF et la PFP sont présents ou perdus |
| `ssd/alertes.py` | `GestionAlertes`, `Alerte` | Tenir la liste des alertes actives |
| `ssd/panneau_commandes.py` | `PanneauCommandes` | Les boutons et saisies de gauche |
| `ssd/tableau_de_bord.py` | `TableauDeBord` | Voyants, écart, alertes, tableaux de HK |
| `ssd/ihm.py` | `IHM` | La fenêtre : elle relie tout le reste |
| `ssd/vues.py` |  | Les trois onglets du bas |
| `ssd/enregistrement.py` |  | Les fichiers CSV |
| `ssd/config.py`, `ssd/style.py` |  | Lecture du `.ini`, couleurs |
| `simulateur/simulateur.py` | `PasserelleDPF`, `LiaisonDPF_PFP` | Le DPF et la PFP simulés |

Les cinq premiers fichiers ne dépendent pas de Qt : ils servent aussi au simulateur et aux tests.

### Trajet d'un message reçu

1. Toutes les 20 ms, `IHM._lire_liaison` appelle `LiaisonEthernet.recevoir()`, qui lit un datagramme UDP s'il y en a un.
2. `Message.decoder` vérifie la taille, la version et le CRC, puis fabrique un objet `HK`, `DonneeInstrument` ou `EcartAltitude`. Une trame invalide est comptée, écrite au journal et ignorée.
3. `IHM.traiterMessage` aiguille selon le type :
   - **HK** : la surveillance note la réception, le tableau de bord l'affiche, il est écrit dans `hk_dpf.csv` ou `hk_pfp.csv`, puis `GestionAlertes.analyserHK` cherche les alertes.
   - **Donnée instrument** : `IHM.enregistrerDonnee` l'écrit dans `donnees_instrument.csv` et l'affiche dans l'onglet.
   - **Écart d'altitude** : `TableauDeBord.afficherEcartAltitude` met à jour la valeur et la courbe.

### Trajet d'une commande

1. Un bouton appelle une méthode de `PanneauCommandes` (`descendre`, `envoyerConsigne`…), qui fabrique une `Commande`. Une consigne hors de 0 à 2000 m s'arrête ici.
2. `IHM.envoyerCommande` la passe à `LiaisonEthernet.envoyer`, qui l'envoie au DPF, puis l'écrit au journal.
3. Il n'y a pas d'acquittement. L'effet se lit dans le HK suivant : le journal note alors le changement, par exemple « État du treuil : ARRÊT → DESCENTE ».

### Surveillance de présence

Chaque seconde, `SurveillancePresence.verifierPeriode` compte les périodes de HK écoulées depuis le dernier HK de chaque source. À 3 périodes, la source est déclarée perdue (EX-COM-130). La période et le seuil se règlent dans le fichier `.ini`.

### Alertes

Une alerte vient de quatre origines, et s'efface seule quand sa cause disparaît :

| Origine | Exemple |
| --- | --- |
| Perte d'un sous-système | « La PFP ne répond plus » |
| Alerte remontée par le bord, dans un octet du HK | « Défaut treuil » |
| Valeur de HK hors d'un seuil du cahier des charges | Température interne PFP sous −30 °C |
| Port UDP du PC impossible à ouvrir | « Port UDP 5000 indisponible » |

### Enregistrement

Chaque ligne est écrite sur le disque dès sa réception. Si l'IHM est fermée brutalement, ce qui a été reçu est déjà dans les fichiers.

## Format des messages

Tous les messages ont le même format : un en-tête de 6 octets, les données, puis un CRC de 2 octets. C'est une proposition de ma part, détaillée octet par octet dans `PGE_ICD_messages_v0.md` (dans le Projet et dans `docs/` du zip).

| Octet | Champ | Contenu | Demandé par |
| --- | --- | --- | --- |
| 0 | version | `0x01` | Ma proposition |
| 1 | source | 1 = SSD, 2 = DPF, 3 = PFP | EX-COM-050 |
| 2 | destinataire | 1 = SSD, 2 = DPF, 3 = PFP | EX-COM-050 |
| 3 | type | 1 = commande, 2 = HK, 3 = donnée instrument, 4 = écart d'altitude | EX-COM-050, 060 |
| 4 à 5 | longueur | Nombre d'octets de données, 0 à 240 | Ma proposition |
| 6 et suivants | données | Selon le type | EX-COM-050 |
| 2 derniers | CRC | CRC-16/CCITT-FALSE sur tout ce qui précède | Ma proposition |

Exemple, la commande « consigne de distance 500 m » fait 13 octets : `01 01 02 01 00 05 03 43 FA 00 00 9E B7`.

Trois choix à connaître :

- **Un message = un datagramme UDP**, et il tient dans un seul paquet LoRa (248 octets au plus). Le DPF peut donc le relayer sans le découper.
- **Les nombres sont en gros-boutiste** (octet de poids fort en premier). Le code C du DPF devra faire pareil.
- **Les dates** sont codées sur 6 octets : secondes depuis le 01/01/1970 en UTC, puis millisecondes.

Le type 4 (écart d'altitude) et la commande 7 (commande à l'instrument) viennent de votre diagramme de classes, pas des exigences v2 : voir les points A1 et A2 de `PGE_propositions_exigences_v3.md`.

## Le simulateur

Le simulateur joue le DPF et la PFP sur ton PC pour que l'IHM ait quelqu'un à qui parler ; ce n'est pas le logiciel embarqué.

| Ce qu'il imite | Comment |
| --- | --- |
| Le treuil | Se déplace à 1,5 m/s (ou `--vitesse`) vers la distance visée, entre 0 et 2000 m |
| Les GNSS | Nacelle vers 20 000 m, PFP plus bas de la longueur de fil déroulée, avec un bruit de 1 m |
| Les HK | DPF et PFP toutes les 5 s (ou `--periode`), plus un HK juste après chaque commande |
| L'écart d'altitude | Calculé par le DPF simulé ; envoyé chaque seconde pendant un déplacement, sinon à chaque HK |
| La passerelle du DPF | Lit le destinataire de chaque message et le traite, ou le passe à la PFP, ou à la SSD (EX-COM-100) |
| L'instrument | Sous tension, il émet 46 octets toutes les 4 s environ, soit près de 1000 Ko par 24 h ; il répond à une commande par `RECU:` suivi de ce qu'il a reçu |
| Les pannes | `radio off`, `eth off`, `froid on`, `cc on`, `treuil off` |

Ce qu'il ne fait pas :

- **La liaison radio est idéale.** Les messages DPF ↔ PFP passent en mémoire, sans perte, sans délai et sans limite de débit. Il ne dit rien sur LoRa.
- **Les valeurs d'énergie et de température sont fictives.** Elles servent à remplir les HK, pas à dimensionner quoi que ce soit.
- **Le treuil s'arrête exactement sur la consigne.** Le vrai DPF devra réguler sur l'écart GNSS pour tenir les ±5 m ; le simulateur ne teste pas cette régulation.
- **Les messages de l'instrument sont inventés.** Je n'ai pas le document d'interface de l'instrument (DCI Rachuts, cité par le cahier des charges).

## Ce qui manque et ce qui reste à développer

Cinq points empêchent aujourd'hui de s'appuyer sur cette version avec du vrai matériel ; les autres sont des développements à planifier.

### À régler avant de s'appuyer dessus

| N° | Sujet | État actuel | À faire |
| --- | --- | --- | --- |
| 1 | Format des messages | Proposition de ma part, validée par personne | La faire valider par l'équipe, puis par les groupes DPF et PFP |
| 2 | Contenu des HK | Listes inventées : 9 valeurs pour le DPF, 14 pour la PFP | Les remplacer par ce que les cartes mesurent vraiment |
| 3 | Essai sous Windows | Jamais fait | Suivre « Installation » et « Premier essai » sur ton PC |
| 4 | Essai sur un vrai réseau | Jamais fait : ni câble Ethernet, ni routeur entre deux réseaux | Essai sur deux PC, puis avec un routeur (réseaux `172.20.3.x` et `172.20.4.x`) |
| 5 | Logiciel embarqué du DPF | N'existe pas ; le simulateur le remplace | Écrire en C le codage et le décodage des trames, le CRC et la passerelle. Les tests Python donnent des trames de référence à comparer |

### À développer

| N° | Sujet | État actuel | À faire |
| --- | --- | --- | --- |
| 6 | Perte de liaison pendant un déplacement | L'écart est marqué « VALEUR ANCIENNE » après 5 s, sans alerte ; la perte n'est déclarée qu'après 3 périodes de HK | Décider d'une règle plus rapide en déplacement, puis la coder |
| 7 | Messages perdus | Indétectables : pas de compteur de messages (hypothèse « UDP parfait » des exigences) | Ajouter un compteur par source si vous voulez vérifier l'hypothèse en essai |
| 8 | Suivi des commandes | L'IHM envoie et journalise ; elle ne sait pas si la commande est arrivée et ne la renvoie jamais | Afficher « en attente de confirmation » jusqu'au HK qui montre l'effet, et alerter s'il ne vient pas |
| 9 | Expéditeur des messages | L'IHM accepte un message valide de n'importe quelle machine du réseau | Rejeter ce qui ne vient pas de l'adresse du DPF |
| 10 | Essai de volume | EX-IHM-070 demande 1000 Ko par 24 h ; mes essais durent quelques secondes | Laisser tourner 24 h avec le simulateur et contrôler la taille du fichier |
| 11 | Commandes de l'instrument | Saisie libre en texte ou en hexadécimal ; aucune commande prédéfinie | Ajouter les vraies commandes quand le format de l'instrument sera connu |
| 12 | Dossier de validation | Les tests automatiques existent, pas les procédures de test rédigées ni la matrice de couverture au modèle CNES | Les rédiger (livrables PRJ-0030 et PRJ-0040 du cahier des charges) |

### Confort, plus tard

| N° | Sujet | État actuel |
| --- | --- | --- |
| 13 | Relire une session | Impossible de recharger des fichiers enregistrés dans l'IHM |
| 14 | Historique à l'écran | Courbe de l'écart limitée à 7200 points, courbes de HK à 5000 points, journal à 5000 lignes. Les fichiers, eux, gardent tout |
| 15 | Heure du journal | C'est l'horloge du PC, pas l'heure GNSS |
| 16 | Fichier instrument | CSV avec les octets en hexadécimal ; pas de fichier binaire brut |
| 17 | Sécurité des commandes | Aucune confirmation avant d'envoyer ; les boutons restent actifs même si le DPF est perdu (un avertissement s'affiche) |
| 18 | Distribution | Il faut Python installé ; pas d'exécutable `.exe` |

## Points pas clairs pour moi

J'ai dû trancher quatorze questions sans avoir la réponse ; chacune peut changer le code si mon hypothèse est fausse.

| N° | Question | Ce que j'ai supposé | Qui peut trancher |
| --- | --- | --- | --- |
| 1 | Où se calcule l'écart d'altitude : à bord ou au sol ? | À bord, par le DPF, qui l'envoie à la SSD | L'équipe, le groupe DPF |
| 2 | Que mesurent vraiment les cartes DPF et PFP ? | Les listes de HK que j'ai inventées | Groupes DPF et PFP |
| 3 | Que disent exactement les réponses du CNES (Q18 à Q26) ? Je n'ai que les renvois dans vos documents, pas le texte | Ce que vos documents en citent | Toi : envoie-moi le questionnaire et les réponses |
| 4 | Que fait « Descente » ou « Montée » sans consigne ? | Jusqu'à 2000 m ou 0 m, ou jusqu'à un arrêt | L'équipe, le groupe DPF |
| 5 | La consigne est-elle un écart d'altitude GNSS que le DPF régule, ou une longueur de fil ? | Un écart GNSS, régulé par le DPF | Groupe DPF, client |
| 6 | Quelle sera la période réelle des HK ? | 60 s en configuration réelle, 5 s en démo | L'équipe |
| 7 | Le DPF envoie-t-il les HK de la PFP tels quels, ou regroupés avec les siens ? | Tels quels, un message par HK, source = PFP | L'équipe, le groupe DPF |
| 8 | Quelles alertes le bord sait-il remonter ? | Deux pour le DPF, trois pour la PFP, inventées | Groupes DPF et PFP |
| 9 | Les commandes de l'instrument sont-elles du texte ou du binaire, avec quelle fin de ligne ? | Les deux sont possibles dans l'IHM | Client (document d'interface de l'instrument) |
| 10 | Les dates des cartes seront-elles en UTC ou en temps GPS ? Les deux diffèrent de 18 s à ma connaissance | En UTC | Groupes DPF et PFP |
| 11 | Quelles adresses IP et quels ports ? Comment le DPF connaît-il l'adresse de la SSD ? | DPF en `172.20.4.10`, ports 5000 et 5001, adresse de la SSD configurée à bord | Groupe DPF, client |
| 12 | Quand le DPF est perdu, la PFP est-elle « perdue » ou « inconnue » ? | Perdue, avec la précision dans l'alerte du DPF | L'équipe |
| 13 | Le client veut-il les données de l'instrument en binaire brut plutôt qu'en CSV ? | CSV avec les octets en hexadécimal | Client |
| 14 | L'IHM doit-elle juger elle-même si les ±5 m sont tenus ? | Non : elle affiche l'écart et la différence avec la consigne, le DPF tient la tolérance | L'équipe |

Les questions 1, 2, 5 et 7 sont celles qui changeraient le plus de code.

## Où modifier quoi

Presque tout ce qui dépend de l'interface se change dans `ssd/icd.py` ou dans le fichier `.ini`, sans toucher à la fenêtre.

| Pour… | Fichier | Quoi changer |
| --- | --- | --- |
| Changer l'adresse du DPF ou un port | `config.ini` | `adresse_dpf`, `port_dpf`, `port_ecoute` |
| Changer la période des HK ou le seuil de perte | `config.ini` | `periode_hk_s`, `seuil_perte` |
| Ajouter, retirer ou renommer une valeur de HK | `ssd/icd.py` | Une ligne `ChampHK` dans `HK_DPF` ou `HK_PFP`. Le tableau, les courbes et le CSV suivent tout seuls |
| Changer un seuil d'alerte | `ssd/icd.py` | `mini` et `maxi` de la ligne `ChampHK` |
| Ajouter une alerte remontée par le bord | `ssd/icd.py` | Une entrée dans `ALERTES_BORD` (numéro du bit, texte) |
| Ajouter une commande | `ssd/icd.py`, puis `ssd/panneau_commandes.py` | Le code dans `TypeCommande`, son destinataire et son libellé ; puis un bouton et sa méthode |
| Changer l'en-tête des trames | `ssd/messages.py` | `Message.coder` et `Message.decoder` |
| Changer les colonnes d'un fichier CSV | `ssd/enregistrement.py` | La fonction `ouvrir_…` et la fonction `ligne_…` correspondantes |
| Changer les couleurs | `ssd/style.py` | Les constantes du début du fichier |

Deux précautions :

- **Après un changement de HK, mets aussi à jour le simulateur** (`construireHK` dans `simulateur/simulateur.py`), sinon il ne pourra plus fabriquer ses HK.
- **Trois noms de HK sont utilisés par la fenêtre** : `etat_treuil`, `consigne_distance` et `etat_instrument`. Si tu les renommes, l'état affiché près des boutons et l'étiquette de tolérance ne se mettront plus à jour.

Après chaque modification, relance `python -m pytest` : un test qui échoue te dit ce que le changement a cassé.

## Préparer la version 2

Pour lancer la version 2, renvoie-moi tes résultats d'essai et les décisions de l'équipe ; plus c'est précis, moins je devine.

- [ ] Installation sous Windows : version de Python, et le message d'erreur exact s'il y en a un
- [ ] Scénario de test : le numéro des étapes qui échouent, ce que tu as vu à la place, une capture d'écran
- [ ] Le dossier `enregistrements` de la session où le problème est apparu
- [ ] Résultat de `python -m pytest` sur ton PC
- [ ] Essai sur deux PC par câble Ethernet, si tu as pu le faire
- [ ] Les réponses aux questions de « Points pas clairs pour moi », au moins les 1, 2, 5 et 7
- [ ] La liste réelle des HK du DPF et de la PFP, avec unités et plages
- [ ] Le questionnaire envoyé au CNES et ses réponses du 15/10/2026
- [ ] Ce que tu veux changer dans l'écran : zone, texte, couleur, ordre
- [ ] Les numéros de « Ce qui manque » que tu veux voir traités dans la version 2

Un retour utile ressemble à : « étape 9 : la PFP reste PRÉSENT après 40 s, capture jointe ».

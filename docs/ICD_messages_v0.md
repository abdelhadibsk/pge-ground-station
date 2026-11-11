# PGE — Document d'interface des messages SSD ↔ DPF ↔ PFP (proposition v0)

> Groupe Sol & Com (resp. Hadi). Statut : **proposition v0 du 10/11/2026, à valider en équipe puis avec les groupes DPF et PFP**.
> Ce document décrit exactement ce que le code de la station sol (`ssd/icd.py`, `ssd/messages.py`) et le simulateur implémentent. Modifier ces deux fichiers suffit à faire évoluer le format.
> Repères : **[CDC]** cahier des charges CNES · **[CNES]** réponses du 15/10/2026 · **[EX-…]** exigences du groupe v2 (20/10/2026) · **[Proposition]** choix fait ici, ouvert.

## 1. Transport

| Élément | Valeur | Origine |
|---|---|---|
| Protocole | UDP/IP sur Ethernet, un message par datagramme | [CDC SYS-0050/0060], [EX-COM-010] |
| Réseau sol (SSD) | `172.20.3.x` | [CNES] |
| Réseau bord (DPF) | `172.20.4.x` | [CNES] |
| Adresse du DPF | `172.20.4.10` | [Proposition] |
| Port d'écoute du DPF (commandes sol → bord) | 5001 | [Proposition] |
| Port d'écoute de la SSD (HK, données, écart bord → sol) | 5000 | [Proposition] |
| Acquittement, retransmission | aucun : transport supposé parfait | [CNES Q23], hypothèse des exigences §2.1 |

Le DPF envoie vers l'adresse de la SSD configurée à bord. Sur la liaison DPF–PFP, les mêmes messages circulent sans modification [EX-COM-110].

## 2. Format commun des messages [EX-COM-050]

Tous les champs de plusieurs octets sont en gros-boutiste (octet de poids fort en premier).

| Octet | Taille | Champ | Contenu |
|---|---|---|---|
| 0 | 1 | version | `0x01` [Proposition] |
| 1 | 1 | source | 1 = SSD, 2 = DPF, 3 = PFP |
| 2 | 1 | destinataire | 1 = SSD, 2 = DPF, 3 = PFP |
| 3 | 1 | type | 1 = commande, 2 = HK, 3 = donnée instrument, 4 = écart d'altitude |
| 4 | 2 | longueur N | nombre d'octets de données, 0 à 240 |
| 6 | N | données | selon le type, voir §3 |
| 6 + N | 2 | CRC | CRC-16/CCITT-FALSE (polynôme `0x1021`, valeur initiale `0xFFFF`) sur les octets 0 à 5 + N |

- **Source, destinataire, type, données** : exigés par EX-COM-050. **Version, longueur et CRC** : [Proposition]. Le CRC de bout en bout permet de vérifier EX-COM-110 (message compris à l'identique après la passerelle).
- **Taille maximale** : 240 octets de données, soit 248 octets par message, pour tenir dans un seul paquet LoRa (255 octets) [Proposition].
- Une trame de version inconnue, de longueur incohérente ou de CRC faux est rejetée ; la SSD la compte et la journalise.
- Valeur de contrôle du CRC : `"123456789"` → `0x29B1`.

Le type 4 (écart d'altitude) vient du diagramme de classes (classe `EcartAltitude`) ; il ne figure pas encore dans EX-COM-060.

## 3. Données par type de message

### 3.1 Commande (type 1) [EX-COM-070]

| Octet | Taille | Champ | Contenu |
|---|---|---|---|
| 0 | 1 | typeCommande | voir le tableau ci-dessous |
| 1 | 4 | parametre | flottant 32 bits ; 0 si la commande n'a pas de paramètre |
| 5 | 0 à 235 | charge | seulement pour la commande 7 : octets à remettre tels quels à l'instrument (RS232) |

| Code | Commande | Destinataire | Paramètre | Effet attendu |
|---|---|---|---|---|
| 1 | DESCENTE | DPF | — | Descendre jusqu'à 2000 m ou jusqu'à un ARRÊT |
| 2 | MONTEE | DPF | — | Remonter jusqu'à 0 m ou jusqu'à un ARRÊT |
| 3 | CONSIGNE_DISTANCE | DPF | écart d'altitude visé, en m (0 à 2000) | Rejoindre la consigne à ±5 m [CDC SSD-0030] |
| 4 | ARRET | DPF | — | Interrompre le déplacement en cours [EX-IHM-120] |
| 5 | INSTRUMENT_ON | PFP | — | Mettre l'instrument sous tension |
| 6 | INSTRUMENT_OFF | PFP | — | Mettre l'instrument hors tension |
| 7 | COMMANDE_INSTRUMENT | PFP | — | Transmettre `charge` à l'instrument |

Les codes 1 à 6 reprennent EX-COM-070 ; le code 7 vient du diagramme de classes (`COMMANDE_INSTRUMENT`) et d'EX-IHM-060. Le comportement de DESCENTE et MONTEE sans consigne est une [Proposition].

Exemples de trames complètes :
- Consigne de distance 500 m : `01 01 02 01 00 05 03 43 FA 00 00 9E B7`
- Arrêt : `01 01 02 01 00 05 04 00 00 00 00 28 B0`

### 3.2 HK (type 2) [EX-COM-080, EX-COM-120]

Le contenu des HK n'est défini ni par le cahier des charges ni par les exigences v2 : les deux listes ci-dessous sont une **[Proposition]** à ajuster avec les groupes DPF et PFP. Les seuils viennent du cahier des charges ; la station sol lève une alerte en dehors.

#### HK DPF (source = DPF)

| Octet | Taille | Champ | Codage | Unité du bit de poids faible | Seuil surveillé au sol |
|---|---|---|---|---|---|
| 0 | 6 | date GNSS | secondes (32 bits) + millisecondes (16 bits) | UTC depuis le 01/01/1970 | |
| 6 | 4 | `latitude` | entier signé 32 bits | 10⁻⁷ ° | |
| 10 | 4 | `longitude` | entier signé 32 bits | 10⁻⁷ ° | |
| 14 | 4 | `altitude` | flottant 32 bits | m | |
| 18 | 1 | `gnss_valide` | entier 8 bits | 0 = non valide, 1 = valide | |
| 19 | 2 | `tension_alim` | entier non signé 16 bits | 1 mV | 10 à 35 V [CDC SYS-0080] |
| 21 | 2 | `courant_alim` | entier non signé 16 bits | 1 mA | ≤ 5 A [CDC SYS-0080] |
| 23 | 2 | `temperature_carte` | entier signé 16 bits | 0,1 °C | −40 à +60 °C [CDC DPF-0010] |
| 25 | 1 | `etat_treuil` | entier 8 bits | 0 = arrêt, 1 = descente, 2 = montée | |
| 26 | 2 | `consigne_distance` | entier non signé 16 bits | 0,1 m | |
| 28 | 1 | `alertes` | champ de bits | bit 0 = défaut treuil ; bit 1 = liaison radio avec la PFP perdue (vue du DPF) | toute alerte est affichée |

Données : 29 octets (message complet : 37 octets). `consigne_distance` est la distance visée par le treuil : la consigne reçue, 2000 m pendant une descente libre, 0 m pendant une montée libre, la distance atteinte après un arrêt.

#### HK PFP (source = PFP)

| Octet | Taille | Champ | Codage | Unité du bit de poids faible | Seuil surveillé au sol |
|---|---|---|---|---|---|
| 0 | 6 | date GNSS | secondes (32 bits) + millisecondes (16 bits) | UTC depuis le 01/01/1970 | |
| 6 | 4 | `latitude` | entier signé 32 bits | 10⁻⁷ ° | |
| 10 | 4 | `longitude` | entier signé 32 bits | 10⁻⁷ ° | |
| 14 | 4 | `altitude` | flottant 32 bits | m | |
| 18 | 1 | `gnss_valide` | entier 8 bits | 0 = non valide, 1 = valide | |
| 19 | 2 | `tension_batterie` | entier non signé 16 bits | 1 mV | 8 à 25 V [CDC PFP-0145] |
| 21 | 2 | `courant_batterie` | entier signé 16 bits | 1 mA, positif en charge | |
| 23 | 1 | `etat_charge` | entier 8 bits | 1 % | |
| 24 | 2 | `tension_panneau` | entier non signé 16 bits | 1 mV | |
| 26 | 2 | `courant_panneau` | entier non signé 16 bits | 1 mA | |
| 28 | 2 | `temperature_interne` | entier signé 16 bits | 0,1 °C | ≥ −30 °C [CDC PFP-0100] |
| 30 | 1 | `etat_instrument` | entier 8 bits | 0 = hors tension, 1 = sous tension | |
| 31 | 2 | `courant_instrument` | entier non signé 16 bits | 1 mA | |
| 33 | 1 | `rechauffage` | entier 8 bits | 0 = arrêt, 1 = marche | |
| 34 | 2 | `rssi_radio` | entier signé 16 bits | 1 dBm | |
| 36 | 1 | `alertes` | champ de bits | bit 0 = instrument disjoncté [CDC PFP-0110] ; bit 1 = batterie faible ; bit 2 = tampon des données instrument plein | toute alerte est affichée |

Données : 37 octets (message complet : 45 octets).

### 3.3 Donnée instrument (type 3) [EX-COM-080, CDC PFP-0135]

| Octet | Taille | Champ | Contenu |
|---|---|---|---|
| 0 | 6 | date GNSS | date à laquelle la PFP a reçu ces octets de l'instrument |
| 6 | 1 à 234 | mesures | octets de l'instrument, tels quels (binaire) [CNES] |

Source = PFP, destinataire = SSD. Les réponses de l'instrument à une commande arrivent par ce même type.

### 3.4 Écart d'altitude (type 4) [EX-IHM-090, EX-IHM-100]

| Octet | Taille | Champ | Contenu |
|---|---|---|---|
| 0 | 6 | date GNSS | date des mesures utilisées |
| 6 | 4 | valeur | flottant 32 bits : altitude GNSS du DPF − altitude GNSS de la PFP, en m |

Source = DPF, destinataire = SSD. Calcul à bord [Proposition] : la tolérance de ±5 m porte sur l'écart d'altitude GNSS [CNES Q20] et le DPF reçoit déjà la position de la PFP chaque seconde pendant un déplacement [EX-LDP-050].

## 4. Règles d'échange

| # | Règle | Origine |
|---|---|---|
| R1 | Le DPF lit le destinataire de chaque message : il le traite, le transmet à la PFP, ou le transmet à la SSD | [EX-COM-100] |
| R2 | La PFP envoie ses HK au DPF (destinataire = DPF) avec une période ≤ 60 s, et ≤ 1 s pendant un déplacement du treuil | [EX-LDP-030, EX-LDP-050] |
| R3 | Le DPF envoie à la SSD ses HK et ceux de la PFP (source = PFP, destinataire = SSD) avec une période ≤ 60 s | [EX-COM-120] |
| R4 | Le DPF n'envoie jamais deux fois le même HK de la PFP : si la PFP se tait, la SSD ne reçoit plus ses HK et constate sa perte | [Proposition], nécessaire à EX-IHM-140 |
| R5 | Le DPF envoie l'écart d'altitude à chaque période de HK, et toutes les secondes pendant un déplacement ; un écart déjà envoyé n'est pas répété | [Proposition], pour EX-IHM-090 |
| R6 | Le DPF et la PFP émettent un HK juste après avoir exécuté une commande : c'est le compte rendu vu par l'opérateur, en l'absence d'acquittement | [Proposition] |
| R7 | La SSD déclare le DPF (resp. la PFP) perdu après 3 périodes sans HK de cette source | [EX-COM-130] |

## 5. Points à valider

- **Avec le groupe DPF** : adresse et ports, liste des HK du DPF, sens de `consigne_distance`, comportement de DESCENTE / MONTEE sans consigne, règles R4 à R6, alertes du DPF.
- **Avec le groupe PFP** : liste des HK de la PFP (ce qu'ils mesurent réellement), alertes de la PFP, taille des blocs de données instrument (≤ 234 octets par message).
- **En équipe** : garder ou non la version et le CRC ; ajouter ou non un compteur de messages par source si l'hypothèse « UDP parfait » doit être vérifiée en essai.

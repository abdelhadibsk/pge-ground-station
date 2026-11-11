# PGE — Propositions pour la v3 des exigences Sol & Com

> Relevé fait le 10/11/2026 en codant l'IHM à partir des exigences v2 (20/10/2026), des cas d'utilisation et du diagramme de classes.
> Ce sont des **propositions** : rien n'est modifié dans vos documents. La colonne « Dans le code » dit ce que l'IHM livrée fait aujourd'hui.

## A. Incohérences entre les documents

| # | Constat | Proposition | Dans le code |
|---|---|---|---|
| A1 | EX-COM-060 liste 3 types de messages ; le diagramme de classes en a un 4ᵉ, `EcartAltitude`. | Ajouter « écart d'altitude » à EX-COM-060. | 4 types. |
| A2 | EX-COM-070 liste 5 types de commandes ; l'énumération `TypeCommande` du diagramme en a 7, et EX-IHM-060 exige les commandes à l'instrument. | Ajouter « commande destinée à l'instrument » à EX-COM-070. | 7 types. |
| A3 | La classe `Commande` ne porte qu'un `parametre : float` : elle ne peut pas contenir une commande à l'instrument, qui est une suite d'octets (instrument binaire, réponse CNES). | Ajouter un attribut `charge : byte[]` à `Commande`. | Fait ; la saisie accepte du texte ASCII ou de l'hexadécimal. |
| A4 | EX-IHM-100 (écart calculé à partir des deux GNSS) est rangée dans l'IHM, alors que le diagramme fait de l'écart un message reçu : le calcul est donc à bord. | Déplacer l'exigence vers la chaîne de communication : « Le DPF devra calculer l'écart d'altitude à partir des mesures GNSS du DPF et de la PFP et le transmettre à la SSD. » | L'IHM affiche l'écart reçu du DPF. |
| A5 | Le diagramme fixe `periodeHK = 60 s`, EX-COM-120 dit « inférieure ou égale à 60 s ». | En faire un paramètre de configuration. | `periode_hk_s` dans `config.ini`. |
| A6 | CU7 : « le DPF envoie ses HK et ceux de la PFP ». Si le DPF répète le dernier HK de la PFP quand elle se tait, la SSD ne verra jamais sa perte (EX-IHM-140). | Ajouter : « Le DPF ne devra transmettre chaque HK de la PFP qu'une seule fois. » | Le simulateur l'applique. |

## B. Exigences à préciser pour être vérifiables

| # | Exigence | Constat | Proposition de rédaction |
|---|---|---|---|
| B1 | EX-IHM-090 | « en continu » n'a pas de cadence, et rien n'oblige le DPF à envoyer l'écart à la SSD plus souvent que les HK (EX-LDP-050 s'arrête au DPF). | « Le DPF devra transmettre l'écart d'altitude à la SSD avec une période ≤ 1 s pendant un déplacement et ≤ 60 s sinon. L'IHM devra afficher l'écart avec sa date et signaler une valeur ancienne. » |
| B2 | EX-IHM-020 | Le contenu des HK n'est défini nulle part : le test ne peut pas dire quoi afficher. | Renvoyer à la liste des HK du document d'interface (une liste est proposée dans `ICD_messages_v0.md`). |
| B3 | EX-IHM-160 | « toute alerte » n'est pas vérifiable sans liste. | Lister : perte du DPF, perte de la PFP, alertes remontées par le bord, valeurs hors des plages du cahier des charges (10–35 V, 8–25 V, −30 °C, −40/+60 °C). |
| B4 | EX-IHM-070 | « datées » : par quelle date ? | « …datées par la date GNSS de la PFP et par la date de réception au sol. » |
| B5 | EX-IHM-030 | Jusqu'où va une descente ou une montée sans consigne ? | « Une descente (resp. montée) se poursuit jusqu'à 2000 m (resp. 0 m) ou jusqu'à un arrêt. » |
| B6 | EX-COM-130 | Avec 60 s de période, une perte est vue après 180 s ; à 1,5 m/s le treuil a parcouru 270 m entre-temps. | Garder la règle au repos et ajouter une règle pour les déplacements : « Pendant un déplacement, la SSD devra signaler l'absence d'écart d'altitude pendant plus de 5 s. » Côté bord, à proposer au groupe DPF : arrêt du treuil si la position de la PFP n'est plus reçue. Dans le code : pendant un déplacement, l'écart est marqué « valeur ancienne » après 5 s, sans alerte. |
| B7 | EX-IHM-130/140 | L'énumération `EtatSousSysteme` n'a que PRESENT et PERDU : au démarrage, avant le premier HK, aucun des deux n'est vrai. | Ajouter un état EN_ATTENTE. |
| B8 | Variante de CU7 | Quand le DPF est perdu, la PFP est affichée « perdue » alors que son état est en réalité inconnu. | Le dire dans l'alerte du DPF (fait), ou ajouter un état INCONNU. |

## C. Exigences à ajouter

| # | Sujet | Proposition de rédaction | Pourquoi |
|---|---|---|---|
| C1 | Compte rendu des commandes | « Le DPF (resp. la PFP) devra émettre un HK dans la seconde qui suit l'exécution d'une commande. Les HK devront contenir l'état du treuil, la consigne en cours et l'état de l'instrument. » | Sans acquittement (réponse CNES Q23), l'opérateur ne voit sinon l'effet d'une commande qu'au HK suivant, jusqu'à 60 s plus tard. |
| C2 | Intégrité des messages | « Chaque message devra contenir un numéro de version et un code de contrôle (CRC). » | Rend EX-COM-110 (« à l'identique ») vérifiable par test. |
| C3 | Taille des messages | « Un message devra tenir dans un seul paquet de la liaison DPF–PFP. » | Sinon le DPF doit découper et réassembler, ce que EX-COM-090 ne prévoit pas. |
| C4 | Messages invalides | « L'IHM devra rejeter et journaliser tout message invalide sans interrompre son fonctionnement. » | Robustesse ; déjà fait dans le code. |
| C5 | Archivage des HK | « L'IHM devra enregistrer les HK reçus, datés, dans un fichier par sous-système. » | EX-IHM-080 parle de fichiers de HK sans qu'une exigence les demande. |
| C6 | Référence de temps | « Toutes les dates affichées et enregistrées devront être en UTC. » | Évite la confusion entre heure GNSS et heure locale du PC. |

## D. Écarts volontaires entre le code et le diagramme de classes

| Classe | Écart | Raison |
|---|---|---|
| `EtatSousSysteme` | Valeur EN_ATTENTE ajoutée | B7 |
| `SurveillancePresence` | Les compteurs sont déduits du temps écoulé depuis le dernier HK, et non incrémentés par un minuteur | Une perte n'est jamais déclarée avant 3 périodes complètes |
| `Commande` | Attribut `charge` ajouté | A3 |
| `Alerte` | Attribut `code` ajouté | Reconnaître une alerte pour l'effacer quand sa cause disparaît |
| `GestionAlertes` | Méthode `analyserHK` ajoutée | Déduire les alertes des HK (B3) |
| `TableauDeBord` | `retirerAlerte` ajoutée ; `afficherEcartAltitude` reçoit aussi la date | Fin d'alerte ; affichage de l'âge de la mesure |
| `IHM` | `arreter()` ajoutée ; fichiers d'archive des HK | Fermeture propre ; C5 |
| `LiaisonEthernet` | `portEcoute` ajouté ; `recevoir()` retourne « rien » au lieu de bloquer | Réception sans bloquer l'interface |
| `PasserelleDPF`, `LiaisonDPF_PFP` | Présentes seulement dans le simulateur | Ce sont des classes du bord |

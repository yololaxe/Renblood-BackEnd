# Étape 3 — Marchés, commerces, auberges et récompenses

Livraison de développement du 4 novembre 2026. Les cinq parties sont raccordées au règlement économique commun. La recette Minecraft et la mise en service restent distinctes : aucun monde n’a été créé pour cette livraison, aucun profil de jeu n’a reçu automatiquement les JAR, aucune migration générale n’a été exécutée.

## Fonctionnement livré

| Partie | Fonctionnement |
|---|---|
| Back | Réservations transactionnelles de fonds, de capacité et de stock ; prix accepté figé ; caisse finie ; fiscalité versionnée ; remboursement lié au règlement original ; historique commercial projeté une fois depuis le reçu confirmé. |
| MedievalCoins | Achats/reventes en espèces ; rendu de monnaie contrôlé ; dépôt/reprise de stock joueur avec NBT ; caisse centralisée transférée en banque ; journal durable et reprise sans nouvelle distribution automatique après une remise incertaine. |
| NpcShopkeeper | Contrats RP conservés, règlement bancaire financé par une enveloppe finie ; contrat payable une seule fois ; prix et totaux en entiers 64 bits ; conservation des objets laissés dans la fenêtre d’échange. |
| MedievalStructures | Location et avances payées en banque ; encaissement dans la caisse de l’auberge ; recettes des voyageurs prélevées sur un budget fini ; remboursement d’exploration limité au payeur et au service original. |
| Front | Caisses confirmées dans Mes finances, reçus commerciaux et remise des récompenses ; achats/reventes distingués ; montants exacts et valeurs inconnues explicites ; pages commerciales avec l’en-tête commun du guide. |

Le client transmet le prix unitaire affiché pour les achats/reventes au comptoir. Un changement avant la validation provoque une nouvelle consultation de l’offre. Une fois le règlement réservé, une modification ultérieure du barème ne change pas le reçu accepté.

## Autorités et reprise

La banque et les caisses sont dans `economy_accounts`. Les offres et quantités disponibles sont dans `economy_offers`. Les cases d’un nouveau comptoir joueur affichent ce stock ; elles ne constituent plus un deuxième inventaire transférable. Le dépôt/retrait passe par les boutons dédiés, avec conservation des propriétés de l’objet.

Les données de bloc sont des caches pour ces stocks. Détruire un comptoir ne distribue pas ses objets une seconde fois et ne supprime pas sa caisse distante. Le propriétaire peut récupérer une caisse ou un stock conservé avec les commandes ci-dessous. Les anciens blocs sans marqueur v1 ne sont pas convertis automatiquement ; leur migration relève de l’étape 5.

Un règlement physique suit `REQUESTED → APPLYING → APPLIED → DONE` dans `data/renblood-bank/<UUID>/`. L’application a lieu sur le thread Minecraft, les requêtes réseau sur l’exécuteur borné. La sauvegarde standard du joueur est vérifiée avant la preuve finale. `APPLIED` peut confirmer de nouveau le même reçu ; `APPLYING` ambigu retient les réservations et demande un rapprochement. Aucun délai n’annule automatiquement une remise potentiellement effectuée.

Les prestations passives d’auberge déplacent uniquement des fonds entre caisses. Elles portent une clé stable par auberge/jour/chambre et peuvent confirmer le même transfert après une réponse perdue. Une enveloppe épuisée ne crée pas d’argent de remplacement.

## Récompenses de quête

La nouvelle validation fige la récompense avec l’accomplissement dans `economy_quest_completions`. Le versement bancaire est unique par personnage et quête, avec une trace `QUEST_REWARD`. Supprimer ensuite la définition de quête ou sa ligne de progression n’efface pas ce droit accepté.

La remise des objets et de l’XP possède un état séparé. Un inventaire plein conserve les objets à remettre ; ils ne sont pas jetés au sol. Les récompenses en attente sont retrouvées à la connexion et après une opération économique normale. Une coupure entre la remise et sa preuve entraîne un contrôle, pas une deuxième distribution. Les anciennes quêtes terminées sans reçu d’accomplissement v1 ne sont jamais repayées automatiquement.

## Administration

Les commandes portent sur des identifiants d’établissement stables : `market:<counterId>`, `inn:<economyId>`, `npc-contracts`, `inn-customers`, `explorations`.

- `/economie caisse <établissement>` : transférer le disponible confirmé de sa caisse vers sa banque.
- `/economie stock <établissement> <offre> <quantité>` : reprendre son stock, notamment après disparition d’un bloc. La vérification du propriétaire se fait aussi au back ; le NBT est conservé.
- `/economie budget <établissement> <fer>` : administrateur Minecraft et compte web Admin ; transfert de sa banque vers l’enveloppe. Cette commande n’émet pas de monnaie.

Les enveloppes commencent à zéro et sont enregistrées au premier usage. Les recettes de ventes alimentent la caisse du comptoir. Le rachat dépense le disponible de cette même caisse. Les contrats PNJ utilisent `npc-contracts` ; les clients et nuitées PNJ des auberges utilisent `inn-customers`.

API administrative, préfixe `/api/economy/v1/` :

| Route POST | Usage |
|---|---|
| `admin/businesses/<id>/stock` | Réapprovisionnement/correction tracé : `offer_id`, `expected_stock`, `stock`, `reason`, `idempotency_key`. Refuse une vue de stock devenue ancienne. |
| `admin/businesses/<id>/policy` | Nouveau barème : `expected_rule_version`, `rule_version`, `tax_bps`, `treasury_account_id`. La trésorerie doit exister et être distincte. |
| `admin/operations/<reçu>/resolve` | Reçu à rapprocher : décision `delivery` ou `cancel`, révision et preuve de vérification. |
| `admin/operations/<reçu>/materials` | Récompense : `DELIVERED` ou `RETRY`, avec motif. `RETRY` exige d’avoir vérifié les objets **et** l’XP pour éviter une nouvelle remise injustifiée. |

La nouvelle fiscalité démarre à **0**. Les recettes nettes et la part fiscale sont réservées séparément ; le remboursement restitue aussi la taxe depuis sa trésorerie d’origine. Aucune nouvelle marge ni variation dynamique n’est activée par cette livraison. L’interface complète de gestion des budgets et corrections reste le travail d’interface prévu à l’étape 4.

## Diagnostic et équilibrage

Depuis le back, avec son environnement Python :

```powershell
python -m economy.audit --env-file .env.local --database renblood_mongo_staging --report rapport-economie.json
python -m economy.simulate --env-file .env.local --database renblood_mongo_staging --report simulation.json --resources-data <dossier-data> --minecraft-jar <client-1.20.1.jar> --npc-sell-bps 7000
```

Les outils vérifient le nom de base demandé, refusent d’écraser un rapport et ne corrigent aucune donnée. Le rapprochement compare les réservations, les comptes, le journal et les stocks. La simulation liste les possibilités de revente directe et les crafts à ingrédients entièrement tarifés ; les ingrédients inconnus ne sont pas gratuits. Fours, recettes spéciales, carburant, temps de travail et trajets ne sont pas assimilés à des coûts nuls.

Voir [ETAT.md](ETAT.md) pour les vérifications réellement exécutées, et [RECETTE.md](RECETTE.md) pour les scénarios de première recette Minecraft.

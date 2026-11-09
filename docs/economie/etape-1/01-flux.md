# Cartographie des flux et des responsabilités

## Autorités et identité

| Donnée | Actuel | Cible |
|---|---|---|
| Compte web | Firebase ; routes utilisateur par identifiant | Identité authentifiée, reliée à un personnage, jamais identifiée par pseudo |
| Personnage | Player.id et Player.id_minecraft ; création possible avec identifiant provisoire Firebase | character_id immuable ; liaison minecraft_uuid validée, UUID provisoires exclus des migrations automatiques |
| Banque | Player.money + copies PlayerCache | Back autoritaire ; cache explicitement daté |
| Espèces | Inventaire Minecraft | Serveur Minecraft ; absence de relevé ≠ zéro |
| Comptoir | counter_id, owner_type/owner_id, position et NBT | counter_id stable ; propriétaire character/guild/city/treasury identifié ; déplacement du bloc ne recrée pas une caisse |
| Stock physique | Bloc/inventaire | Serveur ; le back expose un relevé daté, pas une seconde déduction indépendante |
| Prix | Tables back + cache mod + références PNJ | Barème versionné back ; prix d’exécution conservé dans le reçu |
| Chambre | balance double, occupantUUID, chambre dans un établissement | Contrat d’occupation séparant avance/dette et compte de recettes propriétaire |

L’unicité d’id_minecraft ne garantit pas une liaison valide. Exporter collisions, UUID invalides, propriétaires absents et personnages non reliés avant toute conversion. L’adresse d’un bloc et le pseudo ne sont jamais des identités économiques.

## Matrice des écritures

Les références ci-dessous sont relatives à DEVELOPPEMENT ; `releves/sources.json` fournit empreintes et ancres de lignes des candidats identifiés. Une recherche textuelle ne prouve pas l’absence de chemins indirects.

| Circuit / entrée | Trajet actuel | Cible / incident à gérer |
|---|---|---|
| Backend players/views.py : create_player / update_player | Création du solde et modifications de profil, champs admin | Solde initial = émission documentée ; correction = opération dédiée, jamais simple édition silencieuse |
| players/views.py : deposit_player | Crédit Player.money | Dépôt d’espèces = transfert avec preuve de retrait inventaire ; don système = émission distincte |
| players/views.py : withdraw_player | Débit banque selon conversion | Réservation puis remise ; réponse perdue = interrogation du reçu |
| MedievalCoins/network : SubmitDepositMessage, DepositAllCoinsMessage | Pièces et appel dépôt + mise à jour cache | Inventaire réservé, reçu durable, restitution/reprise selon état |
| SubmitWithdrawMessage | API puis remise des pièces | Inventaire changé ou déconnexion après débit : remise en attente persistante |
| procedures : BtoC/CtoB, BtoS/StoB, GtoS/StoG | Change de dénominations | Conservation stricte, aucune émission ; vérifier tous les ratios et slots |
| api/MedievalCoinsAPI : addMoney/removeMoney | Appels asynchrones deposit/withdraw ; retour void | Retour résultat futur, erreur explicite ; débit réussi avant effet métier |
| market/service : MarketPurchaseService | Pièces retirées, stock/objet remis, journal envoyé ou en attente | Même reçu pour paiement/livraison ; aucun doublon à la relance |
| MarketSellService | Objets propres retirés, pièces données, stock accru, remontée | Budget PNJ réservé avant rachat ; remboursement complet sur échec |
| PlayerMarketPurchaseService | Stock NBT extrait, paiement physique, pendingOwnerBalance crédité | Transfert acheteur → caisse + éventuelle taxe ; propriétaire hors ligne accepté |
| MerchantCounterBlockEntity : claimOwnerBalance | Caisse locale vers pièces | Ne pas créditer à nouveau le gain au retrait ; bloc détruit = avoir récupérable |
| market/service : MarketTransactionService / PendingMarketTransactionManager | Historique différé dans market_pending_transactions.json | Rejeu idempotent avec prix accepté, pas prix courant substitué |
| Back markets/services.py : record_transaction | Validation prix courant, stock limité, transaction et owner_gain | Un prix historique reste recevable avec preuve/réservation ; définir l’unique autorité stock |
| markets/views.py : withdrawals | Enregistrement de retraits remontés | Un enregistrement seul ne constitue pas une remise bancaire ou physique supplémentaire |
| market/services.py : recalculate_prices | Références × ville × type × événements × taxe × activité × variation | Publication versionnée, stable, simulée, historique conservé |
| MedievalCoins/events/QuestObjectiveHandler : récompenses | Objets remis ; ApiClient.deposit pour quest.money | Remise unique, argent et objets suivis séparément, reprise partielle contrôlée |
| MedievalStructures/integration/MedievalCoinsIntegration | double → int ; API banque asynchrone ; donne aussi des pièces | Contrat entier commun, montant accepté explicite, pas de succès anticipé |
| MedievalStructures/inn/InnRoom, event/InnEventHandler | Prix et balance de chambre, avance positive/dette négative | **Ne pas assimiler cette balance à une caisse commerciale** ; séparer occupation, dette, recettes |
| NpcShopkeeper/manager/trade/MoneyCalculator et procedures/trade | Prix/quantités en int et conversion base 64 ; échanges et historiques locaux | Remplacer calcul/paiement par contrat commun ; conserver le contrat d’offre et les objets |
| NpcShopkeeper/manager/trade/PriceReferenceManager | Cache/fichier et recours aux prix MedievalCoins | Même version de référence ; ne pas transformer absence de prix en offre à 1 F |
| game_sessions/models/session_money.py | Photographie historique FloatField | Historique, pas un avoir additionnel ni un solde à restaurer automatiquement |
| Front : api.js, pages admin/markets, Character, MoneyDisplay | Consultations, configuration, corrections via routes existantes | Aucun calcul client autoritaire ; estimé/confirmé/périmé visibles |
| TestClientAdmin | Pas de circuit autonome trouvé dans la recherche monétaire ciblée | Tester les consommateurs API ; aucune nouvelle banque dans ce module |

## Points bloquants pour l’étape 2

- Inventorier les valeurs réellement présentes, y compris caisses NBT/chambres/fichiers PNJ.
- Vérifier si des commandes ou intégrations déployées hors sources observées créent de l’argent.
- Vérifier les transactions et mises à jour conditionnelles réellement garanties par la topologie Mongo/Djongo ; une annotation Django ne couvre pas le monde Minecraft.
- Déterminer les conditions de démantèlement/transfert d’un commerce avant d’autoriser une conversion de sa caisse.

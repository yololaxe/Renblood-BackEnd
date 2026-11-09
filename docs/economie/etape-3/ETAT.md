# État de l’étape 3 — 4 novembre 2026

**Code implémenté sur les cinq parties, contrôles automatiques exécutés. Recette en jeu et activation générale non effectuées.**

## Vérifications

- Back : **120 tests** économie/marchés/quêtes. Mongo transactionnel réel uniquement dans des bases temporaires de test à nom aléatoire ; aucune écriture de test dans le staging. Dernier résultat : **OK, 120/120**. Les classes attendues et les dépendances des JAR finaux ont été vérifiées ; chemins, tailles et SHA-256 figurent dans `build-manifest.json`.
- Front : **6 tests** monétaires et build `build:staging`. Entiers 64 bits, valeurs inconnues, moyennes et anciens flux négatifs couverts.
- Trois mods : compilation et assemblage/remappage. JAR de développement : MedievalCoins **1.0.42**, NpcShopkeeper **1.0.32**, MedievalStructures **0.1.27**. Protocole réseau Coins **3**, NPC **2**, Structures **2** ; les clients doivent correspondre au serveur.
- Compatibilité déclarée : Structures exige Coins ≥ 1.0.42 ; NPC accepte une installation indépendante mais exige cette version si Coins est présent. Une API manquante échoue avant le nouveau règlement.
- Contrat JSON de reçu commercial ajouté et validé dans les tests ; contrat bancaire de l’étape 2 toujours testé.
- Migration déclarative `markets/0008_transaction_economy_receipt.py` préparée ; contrôle de cohérence des migrations effectué. **Pas de migration générale appliquée à la base.**

Les tests couvrent notamment le dernier objet acheté concurremment, le prix figé, la caisse épuisée, le vendeur hors ligne, la réclamation concurrente, l’annulation de réservations, le dépôt/retrait NBT, le contrat PNJ unique entre acteurs, la fiscalité et son remboursement, les ajustements de stock tracés et les récompenses récupérables après suppression d’une quête.

Contrôle visuel : page publique des marchés consultée sur le site local ; achat et revente séparés, valeurs indisponibles visibles, en-tête commun. L’écran financier authentifié et le rendu Minecraft ne sont pas déclarés visuellement recettés. Les styles responsives ont été ajoutés ; une recette téléphone reste prévue.

## Rapports réels en lecture seule

La simulation charge **1 292 recettes** vanilla et des trois mods, avec **16 objets tarifés** dans le catalogue observé. Seules **3 recettes** disposent de tous les ingrédients tarifés ; **892** recettes de craft ne sont pas entièrement tarifées et les autres types de recettes sont signalés séparément. Ce relevé ne constitue donc pas une validation exhaustive de l’équilibrage.

| Scénario simulé | Reventes directes potentiellement bénéficiaires entre marchés | Crafts bénéficiaires entièrement tarifés |
|---|---:|---:|
| Tarifs actuels | 16 | 3 |
| Rachat plafonné à 70 % | 2 | 3 |

Le plafond de 70 % laisse par exemple une marge brute de 161 fer pour l’épée en fer, 53 pour la pioche en pierre et seulement 1 pour le pain. Ces chiffres excluent trajet et temps de joueur. Ils indiquent qu’un taux global unique serait un mauvais réglage de départ sans étude par activité. **Aucun de ces taux n’a été appliqué.**

Le rapprochement v1 du staging retourne zéro anomalie et zéro reçu en attente, sur un périmètre dont le total banque/caisses v1 est **0** : la migration des comptes n’est pas activée. Ce résultat ne prouve pas le rapprochement des anciennes espèces, des anciennes caisses ou d’un monde Minecraft.

Rapports : `reports/simulation-10000.json`, `reports/simulation-7000.json`, `reports/reconciliation.json`. Les outils sont réexécutables ; les comptes-rendus privés éventuels ne doivent pas être publiés sans tri.

## Limites avant ouverture

1. Créer un monde de recette jetable puis exécuter les scénarios de `RECETTE.md`, particulièrement coupure/redémarrage, inventaire plein, fermeture du menu et destruction du comptoir. Le monde réel n’existait pas au lancement du lot.
2. Mesurer le coût des sauvegardes natives vérifiées et les réponses réseau sur cette recette. Aucune mesure de ticks ni promesse d’absence de lag n’est revendiquée.
3. Compléter les prix des ingrédients et l’étude des conversions avant activation d’un nouveau barème. Les gains de craft peuvent être une rémunération voulue ; ils ne sont pas corrigés automatiquement comme des abus.
4. Finir à l’étape 4 les écrans d’administration, la visibilité des budgets au comptoir et les parcours de support. Les outils API/commandes existent déjà ; les anciennes estimations de commerce ne sont pas un solde retirable.
5. Préparer à l’étape 5 la migration des anciens mondes, caisses locales et quêtes historiques. Les soldes/dettes locaux d’auberge sont conservés pour compatibilité ; la caisse du back est l’autorité monétaire.

Aucun déploiement de site, copie de JAR dans un profil ou lancement de serveur Minecraft n’a été effectué par ce lot. Le build du site conserve des avertissements existants sur deux images anciennes et la base Browserslist ; ils ne bloquent pas l’assemblage.

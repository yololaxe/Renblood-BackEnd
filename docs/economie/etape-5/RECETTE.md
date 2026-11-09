# Recette de livraison

| Scénario | Résultat |
|---|---|
| Démarrage des trois JAR dans un nouveau monde Forge 47.4.3 | Démarrage, sauvegarde et redémarrage réussis. Les demandes PNJ aboutissent sur l’API fictive. Les erreurs de chargement Gson vues lors de la première recette ont disparu avec NpcShopkeeper 1.0.34. |
| Comptoir historique | Le montant local de 128 et le NBT `RepairCost:7` subsistent au redémarrage. La dépose du bloc rend l’épée avec son NBT. Le compteur monétaire est relevé avant dépose et traité séparément. |
| Comptoir miroir | Dépose du bloc sans seconde distribution du stock affiché. Le stock confirmé s’obtient via le registre. |
| Auberge historique | Solde local 12,5 et dette de chambre occupée −3,5 conservés, avec un identifiant d’établissement stable après sauvegarde et redémarrage. Les valeurs historiques restent des éléments de rapprochement. |
| Banque | Simulation en lecture seule, écart de solde bloqué avant écriture, trois ouvertures conservant 1 792 fer. Réexécution sans ouverture supplémentaire. Ancien dépôt HTTP refusé. |
| Comptoir et panne | Mise en stock avec NBT, achat réservé, reconnexion Mongo, reprise avec la même clé, confirmation rejouée. La caisse reçoit 64 fer une fois et le stock revient à zéro. |
| Retrait incertain | 32 fer restent réservés, statut visible pour l’intendance. Un joueur ordinaire reçoit un refus d’accès à la console admin. |
| Auberge, PNJ, progression | Location puis remboursement, contrat payé sur enveloppe finie et refus d’un second règlement, quête historique conservée sans nouveau paiement. |
| Audit de panne | État équilibré avant injection. Suppression artificielle d’un compte et d’un stock dans la base jetable, tous deux détectés comme références orphelines. |

Les scénarios Django passent par HTTP local avec identités simulées et transactions Mongo réelles. Le processus qui réserve les opérations s’arrête. Un nouveau processus Django retrouve les reçus dans la même base temporaire et rejoue la confirmation. Le test Forge est séparé et fait tourner le moteur sur un monde généré. La remise physique interservices reste dans la recette avec joueurs. Le chargement d’une ancienne auberge utilise des données synthétiques de l’ancien format.

La suite de régression compte **141 tests back** et **12 tests front**, en plus des scénarios de ce dossier. Le build staging est prêt. Il affiche encore les avertissements existants sur deux images et sur la base Browserslist. L’outil TestClientAdmin a passé `compileJava`.

## Mesures

Le rapport Forge fournit le temps moyen de tick et les TPS au repos. La mesure est effectuée juste après le redémarrage du monde jetable. La sauvegarde vérifiée d’un inventaire de joueur en charge reste à mesurer.

Le portefeuille lit désormais la banque et la page de caisses dans une seule requête Mongo indexée. La recette vérifie que les 53 caisses fictives se répartissent en deux pages, avec la même banque et sans doublon. La recherche de libellés intervient uniquement lorsqu’il y a des caisses à afficher.

Les lectures du portefeuille sur **HTTP local** donnent un p95 de **39 ms, 744 ms et 973 ms** avec respectivement **1, 10 et 30 travailleurs**, sur 30 requêtes par scénario. L’essai inclut le réseau vers Mongo et utilise une identité simulée. Les séries précédentes en processus sont conservées dans `reports`. Les deux modes de mesure et les petits échantillons ne permettent pas de chiffrer un gain causal. Avant extension, mesurer le p95 de la liste de support et du règlement complet sur l’infrastructure retenue, ainsi que les temps de tick avec des joueurs. Les scénarios sont décrits dans `TESTS_A_FAIRE.md`.

## Conditions d’ouverture encore à vérifier

1. Identifier et sauvegarder le monde représentatif et la base associée. Répéter la procédure sur cette copie avec anciens comptoirs, caisses, journaux locaux et quêtes. Le dossier jetable ne représente pas la population réelle du serveur.
2. Rejouer avec comptes réels de recette et navigateur authentifié les parcours de nouveau joueur, commerçant, aubergiste et modérateur. Rejouer côté jeu les coupures entre retrait physique, sauvegarde et confirmation, ainsi que la reconnexion avec un inventaire plein.
3. Vérifier la connexion client/serveur du lot et le refus réseau d’un client utilisant l’ancien protocole. Le contrôle actuel couvre le démarrage dédié et le refus de l’ancienne route bancaire.
4. Valider les mesures en charge, expliquer toutes les différences, puis jouer les séances du pilote Circos. La simulation et les seuils de suivi sont dans le dossier de l’étape 4.

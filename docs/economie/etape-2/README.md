# Étape 2 — socle bancaire implémenté

## Ce qui est livré

- Back : comptes `economy_accounts` et reçus `economy_operations`, montants entiers signés 64 bits, wire JSON en chaînes ; transactions Mongo natives avec snapshot/majority, index d’idempotence, contrôle des limites et absence de découvert. La capacité des dépôts en attente est réservée séparément, sans être comptée comme argent disponible.
- Dépôt : préparation sans crédit, retrait physique prouvé puis confirmation bancaire. Retrait : réservation du solde disponible puis confirmation après remise ; annulation libérant la réserve seulement si aucune remise n’a eu lieu.
- Reprises : reçu stable, conflit de contenu rejeté, preuve rejouable sans double effet, rapprochement administratif des états ambigus, compensation liée des crédits/débits système.
- Jeu : dépôt sélectionné/tout déposer, retrait, journal local durable, sauvegarde standard Minecraft vérifiée en lecture seule, dépôts conservés dans les données persistantes du joueur, change contrôlé avant consommation et conservation des restes faute de place.
- Site : route `/finances`, disponible en étant connecté, soldes disponible/réservé, historique paginé et justificatif. Les grandes valeurs ne passent jamais par Number. Les espèces inconnues ne sont pas affichées à zéro.
- Intégrations : `MedievalCoinsAPI.creditBank/debitBank` asynchrones et adaptateurs `BankAdapter` dans MedievalStructures et NpcShopkeeper. Les effets métier doivent être appliqués sur le thread serveur seulement après résultat confirmé.

Le serveur et le client MedievalCoins utilisent désormais le **protocole réseau 2**. Remplacer les deux ensemble ; un ancien client est refusé plutôt que de décoder des montants/paquets incompatibles.

## Vérifications réalisées

- `manage.py check` : aucun problème déclaré.
- 23 tests Python/Django avec transactions sur une base Mongo temporaire isolée, supprimée après les tests : idempotence, concurrence, annulation, confirmation, compensation unique, rapprochement admin, dépassement, migration répétée et contrôle des droits.
- 3 tests Node : int64 maximal exact, valeurs héritées sûres, rejet des montants invalides/fractionnaires/imprécis.
- Build staging du front réussi.
- Compilation MedievalCoins, MedievalStructures et NpcShopkeeper réussie.
- JAR MedievalCoins produit : `mods/CoinMod2025/MedievalCoins/build/libs/medieval_coins-1.0.41.jar`. Aucun déploiement automatique dans un profil/serveur.
- Simulation de migration : `migration-dry-run.json`, ignoré par Git car il contient les identifiants du relevé. Aucune migration appliquée aux personnages existants.

Ces contrôles ne remplacent pas la recette dans Minecraft. Aucun monde existant n’est à reprendre, conformément au choix du projet. La première recette en jeu doit utiliser un monde jetable et des personnages de test avant une ouverture réelle.

## Stockage et compatibilité

MongoDB doit être un replica set ou un cluster transactionnel. Aucun fallback silencieux vers de simples écritures Djongo. `Player.money` reste une projection de compatibilité ; le nouveau compte est l’autorité des opérations v1. Les écrans bancaires jeu et site lisent le compte v1 directement.

Un compte migré est marqué `economy_v1` dans la même transaction que sa création. Les anciennes écritures de dépôt/retrait utilisent un filtre atomique excluant ces comptes ; elles ne peuvent donc pas écraser le nouveau solde pendant la bascule. Le champ money ne peut plus être corrigé par une édition ordinaire de profil. Les anciennes APIs d’intégration sont conservées pour les comptes non migrés et sont dépréciées côté mod.

**Ne pas basculer tous les comptes avant l’étape 3.** Les paiements métier des quêtes, auberges, commerces et PNJ doivent encore être portés vers les adaptateurs avec des identifiants de métier stables. Pour un compte migré, les anciens appels monétaires sont refusés ; ce refus est volontaire et évite deux circuits concurrents.

## Préparer un compte de recette

Employer le Python disposant des dépendances du backend. Le venv historique pointe encore vers un ancien chemin utilisateur ; les vérifications ont utilisé Miniconda, sans réparation automatique du venv.

Depuis `Renblood-BackEnd` :

```powershell
python -m economy.migrate_accounts --env-file .env.local --database renblood_mongo_staging --player-id IDENTIFIANT_PERSONNAGE --report simulation-compte.json
```

La simulation ne crée pas d’index et ne modifie aucun compte. Un ancien solde fractionnaire, un identifiant absent/ambigu ou une liaison Minecraft invalide bloque le personnage concerné. Aucun arrondi implicite.

Sur un **personnage de recette identifié**, une fois la simulation relue :

```powershell
python -m economy.migrate_accounts --env-file .env.local --database renblood_mongo_staging --player-id IDENTIFIANT_PERSONNAGE --report migration-compte.json --apply
```

La base doit correspondre au fichier d’environnement explicitement choisi. Réexécuter la commande ne réinitialise pas un compte migré. Un solde repris crée un reçu OPENING_BALANCE. La commande ne recrée pas de pièces physiques et ne traite pas les caisses commerciales, prévues à l’étape 3.

## API livrée

Préfixe `/api/economy/v1/`, routes sans slash final :

| Méthode / route | Droit / comportement |
|---|---|
| GET accounts | Firebase du propriétaire, ou serveur Minecraft identifié |
| GET operations?before=RECU | Historique propriétaire, 50 reçus par page, curseur appartenant au compte |
| POST operations | Serveur Minecraft : type DEPOSIT/WITHDRAW ou CREDIT/DEBIT système avec motif ; amount chaîne ; idempotency_key stable |
| GET operations/UUID | Reçu propriétaire |
| POST operations/UUID/delivery | Preuve serveur, revision attendue et proof_id |
| POST operations/UUID/cancel | Aucune livraison, revision et preuve |
| POST operations/UUID/reconcile | Gèle une opération réservée ambiguë pour contrôle |
| GET admin/operations/UUID | Administrateur : reçu hors de son propre compte |
| POST admin/accounts/OWNER/adjustments | Administrateur : CREDIT/DEBIT, montant, clé et motif |
| POST admin/operations/UUID/compensations | Administrateur : compensation unique d’un crédit/débit système confirmé, motif ; une livraison physique exige un rapprochement |
| POST admin/operations/UUID/resolve | Administrateur : décision delivery/cancel, revision et preuve de vérification ; réservé aux reçus à rapprocher |

Canal jeu : clé serveur et `X-Minecraft-UUID`. Canal web : jeton Firebase ; le client finances n’envoie pas de clé serveur. Les quantités monétaires JSON sont des chaînes. Voir `contracts/bank-receipt-v1.schema.json` pour les réponses. Les devis commerciaux et transferts de caisses ne font pas partie de cette tranche bancaire.

Les mots CREDIT/DEBIT désignent provisoirement les mouvements système documentés ; ils ne doivent pas simuler une vente entre joueurs. La compensation a son propre type COMPENSATION, une direction et un original_operation_id. La taxe du marché n’est pas activée par cette étape.

## Reprise après incident

Le mod écrit sous `<monde>/data/renblood-bank/<uuid>/`. REQUESTED signifie qu’aucune remise n’a commencé ; APPLYING encadre l’étape d’inventaire ; APPLIED signifie que la sauvegarde standard a été vérifiée. Les reçus terminés sont archivés dans `completed`, sans rescanner tout l’historique à chaque opération.

À la connexion, le mod recherche les reçus non terminés :

- REQUESTED : retrouve la réservation par sa clé et l’annule si aucune remise n’a commencé.
- APPLIED : renvoie la même preuve, sans remettre ni retirer de nouvelles pièces.
- APPLYING : état ambigu, passage en RECONCILIATION_REQUIRED ; pas de remboursement automatique.
- CONFIRMED/CANCELLED côté back : clôture locale sans répéter l’inventaire.

Une corruption du journal ou l’impossibilité de le sauvegarder bloque le parcours concerné. Ne pas supprimer un journal « pour débloquer » : conserver la preuve, consulter le reçu et résoudre le cas. Une absence de réponse réseau ne signifie pas que le paiement a échoué.

L’administrateur vérifie l’inventaire et le reçu avant de choisir delivery ou cancel. Une résolution déclarée par l’admin ne remet pas automatiquement de pièces : elle enregistre le résultat d’une vérification réelle. Les crédits/débits réservés restent identifiables jusqu’à la décision.

## Recette jeu à faire sur le premier monde de test

1. Ouvrir banque, déposer un lot puis tout l’inventaire ; comparer pièces et banque.
2. Retirer chaque dénomination ; répéter avec inventaire plein, UI fermée et déconnexion pendant l’appel.
3. Rejouer le même paquet/identifiant ; confirmer un seul effet et un seul reçu. Tester le refus d’un ancien client réseau.
4. Tester le change dans les deux sens avec sortie occupée/pleine, puis fermer/réouvrir avec des pièces en attente.
5. Arrêter le serveur aux phases REQUESTED, APPLYING et APPLIED dans un monde jetable ; vérifier reprise et rapprochement sans duplication.
6. Mesurer le coût des sauvegardes standard et du journal. Le réseau est hors thread de tick ; la sauvegarde native et sa vérification restent synchrones pour établir la preuve d’inventaire. Aucun engagement « zéro lag » n’est déduit de la seule compilation.

## Suite

L’étape 3 porte les usages métier vers ce socle, avec caisses, stock, auberges, récompenses et financement des PNJ. La recette en jeu et la bascule globale restent requises avant de déclarer l’ensemble prêt à l’ouverture.

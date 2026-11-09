# Contrat économique cible v1

## Monnaie

Code : IRON ; fer=1, bronze=64, argent=4096, or=262144. Tous les montants JSON sont des chaînes décimales canoniques non signées (`"0"`, `"64"`), jamais Float ni Number JSON. Limite par montant/solde : 9 223 372 036 854 775 807 ; additions et multiplications contrôlées avant mutation. Quantité entière de 1 à 2 147 483 647, en pratique limitée par type d’opération et capacité réelle. Les limites d’interface ne remplacent pas la validation serveur.

Prix unitaire positif, montant nul autorisé seulement pour les informations/comptes. Les dettes sont des contrats séparés, jamais un solde négatif. Les fractions historiques sont des anomalies à traiter par décision tracée, sans troncature silencieuse.

Taxe en points de base : 200 = 2 %. Calcul entier avec reste conservé par caisse et version de règle : taxe = (brut × taux + ancien_reste) // 10000 ; nouveau_reste = modulo 10000. Aucune fraction débitée en pièces. Exemple : cinq ventes 10 F à 2 % produisent au total 1 F de taxe. Une annulation restitue les écritures et ajuste le reste sous contrôle de concurrence ; ne pas recalculer le remboursement au taux actuel. Vérifier le dépassement intermédiaire avec précision arbitraire côté back.

## Identités et comptes

account_id opaque, owner_type CHARACTER/CITY/GUILD/TREASURY/SYSTEM, owner_id stable, pocket BANK/CASHBOX/SYSTEM. Les espèces ne sont pas un compte bancaire fictif : leur transfert est prouvé par une étape serveur Minecraft. Les comptes SYSTEM distinguent émission et destruction. Une avance de chambre et une dette sont des engagements avec bénéficiaire, pas des recettes immédiatement dépensables.

Un acteur authentifié ne choisit pas librement un autre propriétaire. En-têtes et permissions sont définis par canal web/serveur ; jamais de secret de serveur dans le front. Le reçu garde les identifiants, pas des données d’authentification.

## Opérations et invariants

Types : DEPOSIT, WITHDRAW, CHANGE, PURCHASE, SALE, CASHBOX_CLAIM, SERVICE_PAYMENT, QUEST_REWARD, ADMIN_ADJUSTMENT, COMPENSATION. Chaque opération porte UUID, clé d’idempotence, empreinte canonique de la requête, horodatages UTC, acteur, source métier, règle, montants et lignes d’objets éventuelles. Signature d’objet = empreinte canonique incluant NBT, usure, enchantements ; ne jamais considérer item_id seul comme équivalence suffisante.

États : PREPARED → RESERVED → CONFIRMED ; PREPARED/RESERVED → CANCELLED seulement avec preuve d’absence de livraison et libération des réserves ; état ambigu → RECONCILIATION_REQUIRED. Un délai réseau ne prouve pas l’échec. Aucune compensation automatique avant résolution de cette ambiguïté.

- Même clé et même empreinte : retourner le même reçu ; même clé/autre contenu : HTTP 409 IDEMPOTENCY_CONFLICT.
- Soldes et stocks réservés ne deviennent pas négatifs. Contrôle et mutation concurrente indivisibles dans l’autorité concernée.
- Pour un transfert : total débité = total crédité, taxes incluses. Émission/destruction séparément typées et motivées.
- CONFIRMED implique paiement et livraison prouvés ; un affichage local de succès ne suffit pas.
- Compensation : nouvel identifiant lié à original_operation_id ; pas de suppression de l’original.
- Échec partiel : enregistrer les étapes connues et mettre en rapprochement, jamais prétendre qu’un rollback interservices a tout annulé.

## API cible, non implémentée

| Route | Usage |
|---|---|
| GET /api/economy/v1/accounts | Comptes autorisés avec disponible/réservé, date et révision |
| POST /api/economy/v1/quotes | Prix/version, quantités, taxe, expiration ; devis non réservé |
| POST /api/economy/v1/operations | Préparer/réserver selon type, Idempotency-Key obligatoire |
| GET /api/economy/v1/operations/{id} | État et preuve consultables après réponse perdue |
| POST /api/economy/v1/operations/{id}/delivery | Serveur jeu seul : preuve durable de remise/retrait liée au reçu |
| POST /api/economy/v1/operations/{id}/cancel | Annulation selon état, avec version attendue |
| POST /api/economy/v1/operations/{id}/compensations | Admin autorisé, motif obligatoire, compensation liée |

Révision attendue et compare-and-set pour les transitions. Le back réserve ses fonds ; Minecraft réserve ses objets ; les deux conservent leur étape durable. Le choix précis stockage/transaction ne doit pas être déclaré acquis avant validation de Djongo et Mongo.

Erreurs structurées : code stable, message français, retryable, operation_id éventuel, détails non sensibles. Codes : INSUFFICIENT_FUNDS, INSUFFICIENT_STOCK, NO_INVENTORY_SPACE, PRICE_EXPIRED, OWNER_NOT_LINKED, SYNC_REQUIRED, SERVICE_UNAVAILABLE, OPERATION_PENDING, IDEMPOTENCY_CONFLICT. Pas de retry aveugle d’un paiement avec une nouvelle clé.

Le prix est accepté lors de la réservation ; il demeure celui du reçu pendant l’exécution. Après expiration d’un simple devis, demander un nouveau consentement si le total change. Une opération hors ligne n’est admise que par une politique explicite de validité et de réservation durable, pas parce qu’un cache existe.

Compatibilité : introduire v1 à côté des routes historiques ; chaque ancien appel est répertorié avant son remplacement. `MedievalCoinsAPI.addMoney/removeMoney` doit retourner un résultat asynchrone fiable. Le front transmet/affiche les chaînes et utilise BigInt pour les décompositions locales ; pas de conversion globale en Number.

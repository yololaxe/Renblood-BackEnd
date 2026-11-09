# État de l’étape 1 — 4 novembre 2026

## Réalisé

- Cartographie des circuits et responsabilités des cinq parties, avec TestClientAdmin en compatibilité.
- Contrat cible v1 : identités, comptes, monnaie entière, représentation JSON, états, idempotence, prix accepté, preuve et compensation.
- Schéma JSON versionné `contracts/operation-v1.schema.json`. Il décrit la structure ; les invariants de livraison, limites int64, conservation et concurrence restent des validations métier à implémenter à l’étape 2.
- Catalogue des règles et paramètres pilotes distincts des règles réellement activées.
- Charte commune web/jeu avec composants, vocabulaire, états et budgets d’animation.
- Inventaire source reproductible, outils de lecture/relevé et rapprochement hors ligne.
- Export de diagnostic staging en lecture seule, sans démarrer Django ni modifier les données. Les exports restent privés sous `exports/`, ignoré par Git.
- Cinq tests de l’outil de rapprochement réussis : fractions/dettes, doublons de caisse, limites et valeurs invalides, couverture absente et doublons pending.

## Résultats observés

614 fichiers source parcourus ; 399 fichiers contiennent des candidats économiques. Les empreintes et lignes sont dans `releves/sources.json`. Ce relevé lexical n’est pas une preuve de couverture de chaque branche exécutée.

Base sélectionnée : `renblood_mongo_staging` via `.env.local`. Export de diagnostic du 2026-11-04T12:37:06.901458+00:00 au 2026-11-04T12:37:07.690807+00:00, **non atomique**. Sous-total bancaire des lignes uniques valides : **9436978 F**, pour **13 personnages**. Ce n’est pas la masse monétaire totale.

Trois identifiants Minecraft absents, invalides ou non reliés sont signalés. Ils ne sont pas corrigés ; la liaison doit être vérifiée avant migration. Aucune fraction bancaire n’a été signalée par cet export.

Collections absentes : `merchant_counters`, `merchant_counter_items`, `market_transactions`, `temporary_market_modifiers`. Leur absence ne prouve ni que le jeu ne possède pas de comptoirs ni que leur valeur est zéro.

Le premier essai de collecte utilisait le nom conventionnel players_player ; la déclaration Meta du modèle impose players. **Seul local-diagnostic-v2 est le relevé de référence** ; le premier dossier est conservé pour la traçabilité de la tentative incomplète.

| GET local | Médiane sur 3 appels | Taille du corps | Statut |
|---|---:|---:|---|
| `http://127.0.0.1:8000/ping` | 14.54 ms | 41 octets | 200 |
| `http://127.0.0.1:8000/api/public/market-prices` | 670.68 ms | 27111 octets | 200 |
| `http://localhost:5173/` | 8.54 ms | 829 octets | 200 |

La mesure Vite porte sur le HTML de développement, pas le chargement complet ni le temps jusqu’à interaction. Trois appels ne donnent pas un p95 fiable. Pas de charge appliquée. Aucun relevé de requêtes DB, de paquets de synchronisation ni de ticks n’est annoncé.

## Points non levés

1. Le venv backend est lié à un ancien chemin utilisateur et ne démarre pas. L’export a été effectué avec le Python Miniconda déjà installé et ses dépendances. Le venv n’a pas été réparé dans cette étape.
2. Le monde/profil correspondant à la base staging n’est pas identifié pour cette photographie : espèces, caisses NBT, stocks, avances/dettes de chambres et pending locaux non exportés.
3. Il reste à établir les correspondances de propriétaires entre la base et ces données locales ; notamment les trois identités signalées.
4. Mesures de ticks, volumes de synchronisation, nombre de requêtes et parcours front avec compte connecté non collectées. Protocole fourni dans `05-rapprochement-performance.md`.
5. L’arrêté cohérent base + monde et les garanties effectives de concurrence du stockage restent à valider sur l’environnement identifié.

## Conclusion de validation

**Le cadrage, les contrats, la charte et l’outillage sont livrés et vérifiés. L’étape 1 n’est pas clôturée : la photographie économique complète et le profilage du jeu restent ouverts.** Une demande d’identification du monde/profil correspondant a été adressée à l’utilisateur. Ne pas commencer une migration de soldes sur la seule base de cet export bancaire.

Aucune règle économique activée, aucune mutation d’argent, d’objets ou de stocks effectuée par ces outils. Les routes et schémas v1 sont des contrats de réalisation, pas des fonctionnalités déjà déployées.


## Précision de périmètre après retour utilisateur
Le monde Minecraft n’est pas encore créé. La collecte des caisses/stocks d’un ancien monde n’est donc pas requise. Les mesures en jeu sont reportées à la première recette ; elles ne bloquent pas le développement du socle bancaire. Voir ../etape-2/ETAT.md.

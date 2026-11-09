# Étape 4 — Interfaces, performances et préparation du pilote

Livraison de développement du 4 novembre 2026 sur les cinq parties. **Les sources et les builds sont prêts ; la recette Minecraft et le pilote avec des joueurs restent à réaliser sur le futur monde.** Aucun compte réel modifié, aucun barème activé, aucune copie de JAR dans un profil de jeu.

## Ce qui est livré

| Partie | Résultat |
|---|---|
| Front | `/finances` : disponible, réservé et entrées attendues séparés, caisses personnelles paginées, filtres et reçus partageables par référence. Comparaison des marchés accessible depuis cette page. `/admin/economie` : recherche, règlements et établissements, budgets, stock, rapprochement, compensation des crédits/débits éligibles, suspension réversible, programmation des taxes versionnées. Accès depuis le panneau d’administration existant. |
| Back | Pagination par curseur, projections légères, index, enrichissement des listes en lots, recherche par clé de demande ou reçu. Actions avec motif, idempotence et contrôle des révisions. Virement de la banque de l’administrateur vers une caisse : aucun nouvel argent créé. Worker de publication à date, conflits explicites et signal de disponibilité. |
| MedievalCoins | Retour visuel commun, aperçu du total, quantités 1/16/64, double validation verrouillée pendant le règlement, budget de rachat connu/inconnu/épuisé, adaptation de l’échelle des écrans. Cache court des métadonnées et calculs d’affichage bornés. `/economie reprendre` et diagnostic réservé aux opérateurs. |
| MedievalStructures | Écrans d’auberge adaptés aux petits affichages ; mêmes indications d’attente, de résultat et de disponibilité, tout en conservant les actions propres aux services et aux propriétaires. |
| NpcShopkeeper | Cadre pierre/or, largeur corrigée pour les boutons d’échange, emplacements d’objets lisibles, confirmation bloquée pendant un règlement et statut commun de l’enveloppe PNJ. |

Les écritures ordinaires restent automatiques ; la console sert aux exceptions et au pilotage. Un reçu incertain n’entraîne jamais une deuxième remise automatique.

## Utilisation et reprise

Le site utilise la connexion Firebase habituelle ; un personnage doit être associé au compte. Sans banque initialisée, Mes finances explique cet état et permet toujours de consulter les reçus accessibles. L’administrateur recherche un identifiant exact de reçu, personnage, établissement ou clé de demande. Le filtre « À vérifier » est sélectionné à l’ouverture ; choisir « Tous les états » pour retrouver une opération terminée. Les établissements se cherchent aussi par début de nom.

Une action administrative se prépare, affiche son effet, puis se confirme. Les corrections physiques exigent une vérification explicite des objets, pièces et XP. Une réponse réseau incertaine conserve **la même demande** pour sa reprise. Les compensations automatiques se limitent aux crédits/débits confirmés ; elles ne remplacent pas le remboursement d’une prestation commerciale.

Un budget est alimenté depuis la banque de l’administrateur, avec aperçu des deux disponibles et vérification de capacité. Une reprise d’un virement web déjà réservé confirme le même reçu sans nouveau débit. Une suspension arrête les nouvelles affaires de l’établissement et conserve les réservations déjà acceptées ; elle ne les annule pas silencieusement.

## Publication des barèmes

La programmation porte sur la fiscalité et sa version par établissement, **pas sur une modification massive des prix de tous les objets**. Une date future, un motif et la version attendue sont requis. Les reçus existants conservent leurs conditions. Une modification intermédiaire bloque la publication en `CONFLICT` ; l’administrateur prépare alors une nouvelle programmation.

Le service n’est pas installé ni démarré automatiquement par cette livraison. La console signale son absence. Depuis le back :

```powershell
python -m economy.publish_policies --env-file .env.local --database renblood_mongo_staging
```

Cette commande compte les publications dues sans les appliquer. Pour la mise en service, lancer avec `--apply --watch` sous supervision, ou avec `--apply` chaque minute via le planificateur retenu. Le passage réussi met à jour un signal de présence ; au-delà de deux minutes sans passage, la console considère le service indisponible. Un rattrapage applique les dates échues au prochain passage réussi. Ne pas démarrer ce service sur une base de production pendant une simple recette de code.

## Versions compatibles

- MedievalCoins **1.0.43**, protocole **4**.
- MedievalStructures **0.1.28**, protocole **2**, Coins ≥ **1.0.43**.
- NpcShopkeeper **1.0.33**, protocole **2** ; si Coins est installé, il doit être ≥ **1.0.43**. Les nouveaux règlements économiques exigent son API.

Installer ensemble les versions compatibles côté client et serveur lors de la recette. Les trois JAR remappés restent dans les dossiers `build/libs` de leurs projets. Tailles, empreintes et vérification du contenu : `build-manifest.json`.

## Dossier de validation

`RECETTE.md` distingue les vérifications exécutées et les essais à effectuer en jeu. `PERFORMANCES.md` expose les mesures et leurs limites. `PILOTE.md` définit le périmètre de Circos et les observations nécessaires. `CHARTE.md` fixe les états et comportements communs. Le simulateur de prix est hors ligne et ne possède aucune capacité de publication.

Le build conserve les avertissements préexistants sur deux anciennes images et la base Browserslist. Aucun déploiement du site, migration générale ou démarrage Minecraft n’a été effectué.

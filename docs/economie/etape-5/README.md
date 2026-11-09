# Étape 5 — Recette et préparation de la mise en service

Les cinq composants ont été vérifiés en développement. La répétition utilise un monde Forge jetable, une API fictive locale pour le démarrage des mods et une base Mongo temporaire pour les règlements. Deux processus Django successifs servent les requêtes de recette sur HTTP local. La mise en service du pilote reste conditionnée à la recette authentifiée, au rapprochement du monde retenu et aux mesures sous charge sur l’infrastructure cible.

| Composant | Version de recette | Contrôle |
|---|---|---|
| Back Django | `/api/economy/v1/` | 141 tests, simulation puis application de la migration sur base temporaire, reprise des reçus et rapprochement |
| Front React | Build staging | 12 tests monétaires et d’aperçu, compilation, contrats de portefeuille et de support vérifiés côté API |
| MedievalCoins | 1.0.44, protocole 4 | JAR remappé, refus visible d’un échange sur stock historique, sauvegarde et restitution d’un objet avec NBT |
| MedievalStructures | 0.1.28, protocole 2 | Démarrage avec Coins, lecture et sauvegarde d’une ancienne auberge, location et remboursement dans la recette API |
| NpcShopkeeper | 1.0.34, protocole 2 | JAR remappé, synchronisation Forge avec une API locale, contrat financé et réglé une fois dans la recette API |

TestClientAdmin compile également. Utiliser les trois JAR du manifeste pour le client et le serveur Minecraft 1.20.1. Structures exige MedievalCoins 1.0.43 minimum et les nouveaux échanges PNJ utilisent son API. La livraison fixe Coins 1.0.44. Les anciens dépôts HTTP sont refusés après migration du compte.

La migration refuse désormais les associations Minecraft ambiguës et les divergences entre marqueur de migration et compte. L’application ciblée peut prendre un rapport de simulation comme référence et refuser une ouverture dont le solde a changé. Le rapprochement détecte aussi les comptes et stocks manquants derrière des opérations confirmées.

La recette de bascule conserve **1 792 fer**. Trois ouvertures sont créées, une seule par compte. Quatre cas sont mis à part, avec une fraction, deux personnages partageant un UUID et un marqueur sans compte. Un retrait incertain reste réservé pour rapprochement. Les essais Forge confirment la restitution du stock physique et l’absence de duplication depuis le miroir.

Le relevé en lecture seule du staging trouve **10 comptes éligibles**, **3 liaisons Minecraft à vérifier** et **6 quêtes historiques terminées**. Le journal v1 du staging est encore vide. Le dossier `reports` contient les preuves synthétiques et le relevé agrégé du staging. Les recettes distinguent les erreurs observées, les contrôles passés et les conditions d’ouverture.

- [Recette et résultats](RECETTE.md)
- [Les 15 tests à faire en jeu et sur le site](TESTS_A_FAIRE.md)
- [Procédure de bascule et de retour](BASCULE.md)
- [Guide joueur et support](EXPLOITATION.md)
- [Versions et empreintes](build-manifest.json)

Le fichier `release.json` fixe aussi les empreintes des points d’entrée du front et des sources économiques du back. Pour reproduire les contrôles, copier les scripts du sous-dossier `tools` dans un espace de recette jetable. `rehearse.py` et `preflight.py` utilisent la configuration locale existante. `forge_rehearsal.py` réutilise seulement le moteur Forge installé et produit un monde de recette dans son propre dossier. Les rapports sont écrits à côté des scripts.

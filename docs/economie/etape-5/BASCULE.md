# Procédure de bascule et de retour

Cette procédure s’applique d’abord à une copie identifiée. Consigner le monde, son empreinte, la base Mongo, la date, la liste de personnages du lot et les versions du manifeste. Pour la première ouverture, choisir les participants du pilote Circos et utiliser les règles déjà validées pour eux.

## Préparer et geler

1. Ouvrir une fenêtre de maintenance sur le périmètre visé. Arrêter les sessions Minecraft, les anciens écrivains économiques et la publication de barèmes. Garder le site en maintenance sur les opérations susceptibles d’écrire.
2. Produire et tester une sauvegarde restaurable de Mongo et du dossier du monde, avec `playerdata`, régions, dimensions, `data`, journaux `renblood-bank`, fichiers historiques du marché et des PNJ. Sauvegarder les configurations de façon privée et vérifier les versions des binaires. Conserver l’export avant toute intervention sur des blocs.
3. Exécuter l’audit avec le monde arrêté et dresser la liste des reçus en attente. Classer par preuve disponible et bloquer la bascule d’une opération physique ambiguë. Une sauvegarde de joueur, le reçu et le journal doivent être rapprochés ensemble. Une réservation active reste dans le registre jusqu’à sa résolution.
4. Relever séparément espèces, banque historique, caisse de chaque comptoir, solde de chaque auberge, avances/dettes de chambres et quêtes historiques. Identifier le propriétaire et les références de chaque établissement. Séparer les objets physiques des miroirs du registre. Les estimations et les valeurs dupliquées entre sources ne constituent pas des droits supplémentaires.

Depuis le back, pour un exemple de compte ciblé sur le staging de recette, produire le rapport puis conserver le même périmètre pour l’application. Remplacer `PERSONNAGE` et choisir des noms de fichiers nouveaux. Ces fichiers contiennent des identifiants et doivent rester dans le dossier d’exploitation privé.

```powershell
python -m economy.audit --env-file .env.local --database renblood_mongo_staging --report avant-audit.json
python -m economy.migrate_accounts --env-file .env.local --database renblood_mongo_staging --player-id PERSONNAGE --report avant-banque.json
python -m economy.migrate_accounts --env-file .env.local --database renblood_mongo_staging --player-id PERSONNAGE --expected-report avant-banque.json --report ouverture-banque.json --apply
python -m economy.audit --env-file .env.local --database renblood_mongo_staging --report apres-audit.json
```

Le rapport peut contenir plusieurs `--player-id`. Contrôler chaque état de sortie. L’application est transactionnelle par compte et un lot peut donc mélanger ouvertures réussies et cas bloqués. La réexécution conserve les comptes déjà ouverts. Si un solde a changé après l’export, revenir au gel des écritures et expliquer l’écart avant un nouveau relevé.

## Traiter les données du monde

| Source | Opération et preuve |
|---|---|
| Espèces et inventaires | Conserver les sauvegardes natives. Comparer par joueur les quantités et propriétés. Les espèces restent dans l’inventaire lors de l’ouverture bancaire. |
| Comptoir historique | Photographier identifiant, coordonnées, propriétaire, NBT, quantités et gains locaux avant dépose. Sur copie, récupérer les objets physiques sous contrôle du propriétaire, les compter et les redéposer via les commandes ou l’interface du nouveau comptoir. Comparer les reçus de dépôt et le stock. |
| Comptoir miroir | Conserver la référence du registre. Vérifier le stock via les reçus de dépôt/reprise. Utiliser `/economie stock` pour récupérer les objets de la caisse de stock si le bloc a disparu. |
| Caisses et gains historiques | Rapprocher chaque montant avec l’historique, le monde et les transferts déjà faits. Tenir un relevé signé par établissement. Un transfert documenté vient d’un fonds identifié. Un passif historique avéré exige une décision explicite de reprise et un reçu motivé. Les fractions et doubles comptages restent à examiner. |
| Auberge | Démarrer puis sauvegarder la copie pour conserver `EconomyId` avant le raccordement. Préserver chambres, occupants, soldes et dettes locaux. Vérifier la caisse v1 à part. Une dette de chambre reste dans son historique de service et ne devient pas un débit bancaire par simple conversion. |
| Quêtes | Conserver progression et historiques. Les anciennes quêtes terminées sont classées séparément. Pour une remise v1 non terminée, comparer reçu, objets et XP avant toute décision. |

## Ouvrir par périmètre

Comparer les quatre quantités avant/après pour chaque périmètre utile. Il s’agit des espèces, des comptes confirmés, des montants réservés et des objets avec leurs propriétés. Le total des comptes v1 augmente uniquement des ouvertures et des crédits autorisés. Un transfert entre comptes conserve le total. Faire valider les écarts expliqués et conserver rapports, sauvegardes et références de reçus ensemble.

Installer l’ensemble de la livraison, ouvrir d’abord aux comptes pilotes et surveiller les indicateurs du guide. Traiter tout incident critique avant extension. Une programmation fiscale doit viser une caisse et une version valides. Démarrer le service de publication seulement lors de la mise en service correspondante.

## Revenir en arrière

- **Barème.** Reprendre les valeurs approuvées sous une nouvelle version de règle et garder les références historiques. Les reçus déjà acceptés gardent leur version et leurs montants.
- **Logiciel.** Avant toute réouverture, une restauration de la paire monde/base validée permet de revenir au point gelé. Après des transactions réelles, fermer les nouvelles écritures, sauvegarder l’état courant et rapprocher les reçus en vol. Reprendre avec une version qui comprend le registre, ses preuves et le protocole en vigueur. La restauration d’un ancien solde par-dessus des paiements confirmés créerait un écart à résoudre individuellement.

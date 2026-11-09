# Étape 1 — socle de l’économie

Ce dossier prépare les cinq parties : back, front, MedievalCoins, MedievalStructures, NpcShopkeeper ; TestClientAdmin est contrôlé comme outil annexe. Aucune règle métier n’est activée par ces livrables.

Lire dans cet ordre : `01-flux.md`, `02-contrat.md`, `03-regles.md`, `04-interface.md`, `05-rapprochement-performance.md`, puis `ETAT.md`.

Les contrats sont **cibles v1**, non des routes actuellement déployées. Les outils sont indépendants de Django : leur lancement ne démarre ni bot ni tâche applicative.

## Outils

Depuis la racine DEVELOPPEMENT, avec Python 3 :

```powershell
python docs/economie/etape-1/tools/baseline.py scan --root . --out docs/economie/etape-1/releves/sources.json
python docs/economie/etape-1/tools/baseline.py probe --out docs/economie/etape-1/releves/http-local.json
python docs/economie/etape-1/tools/baseline.py reconcile --input EXPORT.json --out RAPPORT.json
python -m unittest discover -s docs/economie/etape-1/tools -p 'test_*.py'
```

Les sorties sont créées exclusivement : fournir un nouveau nom si elles existent. `probe` fait seulement des GET locaux et ne modifie ni comptes ni stocks. `scan` ignore secrets, archives et dépendances ; il relève chemins, empreintes et numéros de lignes, sans recopier les lignes de code.

`snapshot_mongo.py --env-file FICHIER --database NOM --out NOUVEAU_DOSSIER` lit les collections économiques avec des projections limitées. Utiliser le Python du venv backend (pymongo/python-dotenv). Il n’importe pas Django et ne fait aucune écriture Mongo. La lecture multi-collections n’est **pas un instantané atomique** : pour un rapprochement définitif, employer une copie figée de la base et du monde correspondant. Ne pas publier ces exports privés dans Git.

Le format normalisé pour `reconcile` est `{"bank":[{"id":"…","minecraft_uuid":"…","amount":"…"}],"cashboxes":[{"id":"…","owner":"…","amount":"…"}],"room_balances":[],"pending_operations":[]}`. Les listes absentes sont signalées comme non couvertes. Les dettes de chambres sont classées à part et exclues du total des avoirs.

Les exports NBT et les mesures de ticks nécessitent une copie du monde ou un serveur identifié ; aucun chiffre n’est inventé pour les remplacer.

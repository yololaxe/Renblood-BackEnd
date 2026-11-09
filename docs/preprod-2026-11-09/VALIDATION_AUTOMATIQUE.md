# Vérifications automatiques du lot de préproduction

- Backend : 198 tests réussis (inscription, économie, marchés et quêtes), sur bases temporaires isolées.
- Front : 18 tests réussis (4 brouillons/identité, 14 monnaie/intendance) ; build staging réussi.
- Trois mods compilés et réobfusqués ; fichiers installés vérifiés par SHA-256.
- Pack serveur complet démarré sur un monde jetable, sans accès au backend réel : message Done obtenu. Les détails de sauvegarde/arrêt et de mesures au repos sont consignés dans le rapport serveur, pas présentés comme une charge à quinze joueurs.
- Base staging sauvegardée (46 collections), migration marchés 0008 appliquée, index d'inscription préparés, 100 références initiales déjà présentes (aucun prix réinitialisé).
- Avant publication, contrôle des fichiers Git : aucune clé privée/configuration réelle ajoutée ; caches et environnements locaux retirés du suivi, conservés sur disque.

Les 130 tests de la recette manuelle restent à renseigner. Les vérifications automatiques ne valident pas à elles seules Google OAuth réel, les clics Minecraft, les scénarios multijoueurs et la charge réelle.

Le déploiement doit viser uniquement `renblood-staging.web.app`, `renblood-backend-staging.up.railway.app` et `renblood_mongo_staging`. La production ne fait pas partie de ce lot.

La compilation backend utilise un Dockerfile Python 3.11 et les versions applicatives testées ; le processus Daphne conserve HTTP et WebSocket. Configuration et vérification de santé suivent la [documentation officielle Railway](https://docs.railway.com/config-as-code/reference).

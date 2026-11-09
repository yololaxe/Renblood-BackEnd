# État de livraison — étape 2

Implémentation du socle bancaire livrée, contrôles automatisés réussis. Pas d’activation générale ni de migration des comptes réels.

- Django : check sans erreur ; 23 tests réussis, y compris transactions réelles sur bases temporaires isolées et validation du schéma de reçu.
- Front : 3 tests de précision réussis, build staging réussi.
- MedievalCoins : compilation et reobfuscation réussies ; protocole réseau 2 ; classes bancaires et mixin vérifiés dans le paquet.
- MedievalStructures et NpcShopkeeper : compilation réussie avec leurs adaptateurs asynchrones.
- Simulation staging : 10 comptes prêts, 3 comptes bloqués à vérifier. Simulation seulement ; aucun solde converti par cette livraison.
- Paquet : medieval_coins-1.0.41.jar ; SHA-256 `21b856cdcdd15dda66331012ba88a920d5f04d1df84ab73fdf29407a9280f2dc`.

## Limites de validation

Le monde Minecraft n’est pas encore créé : aucune reprise d’un ancien monde n’est attendue. Les essais de crash, de reconnexion, de GUI et les mesures de sauvegarde dans Minecraft restent à exécuter sur le premier monde de recette. La page finances compile et ses montants sont testés ; son parcours avec un compte Firebase connecté n’a pas été vérifié visuellement dans cette livraison.

Les intégrations métier historiques ne sont pas toutes remplacées : leurs nouveaux adaptateurs sont disponibles et compilés, leur raccordement est le travail de l’étape 3. Les anciennes écritures sont refusées pour les comptes migrés ; ne pas activer une bascule globale avant ce raccordement.

`Player.money` est encore une projection héritée FloatField pour les anciens consommateurs ; le compte v1 entier et les routes bancaires v1 sont l’autorité. Le site finances et les écrans bancaires du jeu utilisent ce compte. Le reste des consommateurs sera porté avec les usages métier.

Aucune taxe, marge de marché ou règle d’auberge nouvelle n’est activée. Aucun JAR n’a été installé dans un profil utilisateur ou un serveur.

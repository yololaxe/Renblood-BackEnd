# Recette étape 4

## Exécuté

- **141 tests back** : économie, marchés, quêtes, dont transactions Mongo sur bases temporaires distinctes. Concurrence du socle, conservation des fonds, reprise des virements, suspension réversible, révisions, programmation différée/conflictuelle, annulation, recherche, pagination et contrôle d’accès. Cinq cas de calcul du pilote et signal de présence du service inclus.
- **12 tests front** : montants int64 exacts, inconnus, conversions, libellés, aperçus de budget et compensation, stock, dates futures et taux en points de base.
- Build front staging. Les pages de recette `dev/economy-preview.html` et `.jsx` sont des entrées de développement, absentes du build publié. Elles injectent des réponses fictives aux composants réels ; elles ne contournent pas l’authentification des routes du site et n’envoient aucune opération aux comptes.
- Recette navigateur à 1270 px environ et à **390 × 844** : finances, choix d’un reçu, références longues, absence de débordement horizontal, console, changement d’onglet, détail d’établissement, saisie et aperçu de virement. Tab atteint la confirmation ; focus du détail déplacé sur téléphone. L’avertissement React de lignes de l’ancien onglet a été corrigé. Les rechargements de recette après modification du nombre de hooks éliminent les erreurs de rafraîchissement à chaud.
- Trois mods compilés et JAR remappés ; dépendances et classes contrôlées dans le manifeste. Calcul d’adaptation testé sur **15 combinaisons taille/menu** et **60 allers-retours de coordonnées**. Cela ne prouve pas le rendu natif en jeu.
- Benchmark sur 2 000 reçus fictifs, pages disjointes, plan d’exécution indexé et réduction de charge JSON. Simulation de prix hors ligne, sans publication.

Captures `screenshots/finances-mobile.jpg` et `screenshots/intendance-pc.jpg` : données explicitement fictives. Leurs soldes ne décrivent aucun compte réel.

## À exécuter dès qu’un monde de recette existe

1. Installer la même combinaison de versions client/serveur. Banque, comptoir client/propriétaire, auberge client/propriétaire, PNJ et récompense : ouverture/fermeture, clic et glisser d’objet à toutes les échelles GUI supportées. Vérifier le rendu des infobulles, des objets tenus et des listes longues.
2. Prix modifié, caisse vide, établissement suspendu, inventaire plein, double clic et réseau lent : bouton désactivé pendant la demande, raison lisible et reçu exact. `/economie reprendre` ne redistribue pas les opérations ambiguës.
3. Couper le back pendant une demande, se reconnecter, reprendre et rapprocher en suivant la recette de l’étape 3. Contrôler pièces, objets, NBT et XP avant toute décision manuelle.
4. Avec comptes de recette et administrateur authentifiés, parcourir recherche → aperçu → confirmation → reçu → actualisation. Vérifier la même clé après réponse perdue, deux administrateurs sur la même révision et budget bancaire insuffisant. La recette navigateur fictive ne remplace pas cette intégration authentifiée.
5. Sur base de recette identifiée, démarrer le worker de publication, programmer à quelques minutes, modifier le barème avant une autre échéance et vérifier respectivement publication unique/conflit. Arrêter le worker et constater l’indisponibilité après deux minutes.
6. Relever performances API, diagnostic de sauvegarde et ticks, puis conduire les séances de Circos définies dans `PILOTE.md`. Valider les paramètres sur observations réelles avant activation générale.

La validation de développement ne vaut pas recette d’exploitation. La migration des anciens blocs, caisses, dettes d’auberge et quêtes historiques reste dans l’étape 5.

# Création et gestion du personnage après Google

## Fonctionnement livré

La connexion Google ouvre un dossier lié à l'UID authentifié. Elle ne reprend ni le nom réel ni la photo Google comme identité publique. Un utilisateur Firebase déjà ancien mais absent de la base joueurs reçoit le même parcours qu'un nouveau compte. Le front n'utilise plus les dates de première connexion pour décider de créer un joueur.

- `/welcome` : identité RP, Minecraft, récapitulatif, avec aperçu du portrait et de l'identité.
- `/account/profile` : présentation, origine RP, portrait et demandes de changement de nom ; association Minecraft, remplacement soumis au staff, annulation des demandes et historique.
- `/admin/registration` : règles d'inscription, dossiers incomplets, inscriptions et modifications à traiter. Accès depuis le panneau admin existant.
- `/auth` : connexion Google, retour vers le bon dossier et reprise explicite en cas de serveur indisponible.

Le prénom et le nom RP sont obligatoires. Présentation et origine sont facultatives par défaut. Six portraits vectoriels sont proposés. L'origine reste un élément de récit : aucune ville, maison, licence ou ressource n'est attribuée par ce choix.

Le brouillon est conservé sur l'appareil, séparément pour chaque UID. Chaque étape validée est aussi enregistrée côté serveur. Les conflits de révision empêchent d'écraser une modification effectuée dans une autre fenêtre. Un changement accepté par le serveur invalide les anciens caches de fiche. Le chargement de la fiche ignore les réponses d'un compte qui vient d'être déconnecté.

## Création différée et joueurs existants

Le dossier d'inscription est enregistré dans des collections dédiées. Tant que l'identité Minecraft n'est pas vérifiée ou que l'inscription attend le staff, il n'y a pas de nouveau document `players` ni de faux UUID.

Un personnage est matérialisé lorsque le dossier est accepté et Minecraft vérifié. Les valeurs initiales sont calculées dans le backend : rang de départ configuré, zéro monnaie, métiers non débloqués et caractéristiques de base du modèle. Les répétitions de confirmation ne créent pas de doublon. Le compte bancaire du nouveau personnage est préparé à zéro ; si la banque est indisponible, une reprise idempotente est proposée depuis le profil.

Les joueurs existants sont reconnus par leur UID et leur UUID existants. Aucun import de masse ni réinitialisation n'est effectué. Rang, argent, expérience, talents, traits, licences et reçus restent en place. Leur éventuelle migration bancaire historique conserve la procédure de rapprochement existante.

Les changements de présentation et de portrait sont libres. Après validation, un nom modifié devient une demande au staff, qui peut accepter ou refuser avec motif. Le joueur peut compléter ou annuler sa demande. Les changements d'identité sont historisés avec auteur, date et valeurs avant/après lors de la décision.

Les portraits retirés de la sélection administrative restent utilisables par les personnages qui les avaient déjà choisis. Modifier les règles ne change pas le rang des personnages existants.

## Liaison Minecraft

Le site génère une commande personnelle `/mc lier XXXXXXXX`, valable dix minutes. Elle doit être exécutée depuis le joueur Minecraft concerné. L'UUID et le pseudo proviennent de la session en jeu ; le formulaire n'autorise pas leur saisie libre. Les codes sont stockés sous forme d'empreinte, limités en fréquence, expirables et consommés une seule fois. Une répétition du même code par la même session est sans effet supplémentaire.

La commande utilise le pool HTTP borné du mod, sans appel réseau sur le thread des ticks. Elle refuse les demandes simultanées d'un même joueur et ne publie pas une réponse sur une nouvelle session ayant remplacé la précédente.

Une clé privée de preuve, propre au serveur autorisé, complète l'ancienne clé API : cette dernière est déjà présente dans des configurations du navigateur et ne constitue donc pas une preuve de présence en jeu. La nouvelle clé ne figure ni dans le front ni dans le JAR distribué. Mongo conserve uniquement son empreinte ; la configuration Minecraft conserve la clé brute. Elle ne doit pas être distribuée aux clients d'un serveur multijoueur.

Un remplacement Minecraft demande une nouvelle vérification en jeu puis une décision du staff. L'UID du dossier et ses soldes restent les mêmes. Les inventaires, positions et sauvegardes du monde attachés à l'ancien UUID ne sont pas transférés automatiquement. Après activation ou remplacement accepté, il faut se reconnecter au monde pour recharger les données en jeu.

## Préparation et activation

Les deux profils réels sont **activés depuis le 7 novembre 2026**, après accord explicite de l'utilisateur. Les index sont préparés, les accès privés enregistrés dans staging et les configurations locales sauvegardées. Le backend local reconnaît les deux preuves ; une sonde avec un code fictif invalide atteint bien la validation des codes et est rejetée sans créer de personnage. La tentative initiale avait été refusée par l'auto-review en attente de cet accord ; aucune activation n'avait alors été effectuée.

La préparation effectuée peut être reproduite avec le backend configuré sur `renblood_mongo_staging` :

```powershell
python manage.py prepare_player_profiles
python manage.py configure_player_link --profile "C:/Users/alban/AppData/Roaming/ModrinthApp/profiles/Test Mods RP" --label "Recette solo Test Mods RP"
python manage.py configure_player_link --profile "D:/Projets/Projet/localhost_server1.20.1" --label "Serveur de développement local"
```

La première commande prépare uniquement les index des nouvelles collections. Les deux suivantes autorisent chacune un profil, avec sauvegarde de sa configuration dans son propre dossier `renblood-backups`. Une relance conserve la même clé ; `--rotate` permet son renouvellement volontaire. Aucune clé n'est imprimée dans la console.

Les configurations backend locales et staging utilisent actuellement la même base `renblood_mongo_staging`. Les réglages du registre seront donc partagés. Les nouvelles routes doivent être déployées sur le backend distant pour utiliser ce parcours avec l'URL Railway ; aucun déploiement distant n'a été effectué dans ce lot. Pour les essais immédiats, employer le front et le backend locaux.

Le JAR `medieval_coins-1.0.67.jar` est compilé, réobfusqué et installé dans **Test Mods RP**, avec sauvegarde du précédent JAR. NPC Shopkeeper et Medieval Structures n'ont pas été reconstruits : aucun changement de leurs sources ou de leurs API n'est nécessaire ici. Le vieux JAR du dossier serveur n'a pas été remplacé ; le raccordement en jeu de la nouvelle commande se teste avec le profil solo livré.

## Vérifications

- **198 tests backend réussis** : inscription et transactions Mongo réelles sur bases temporaires isolées, plus non-régression économie, marchés et quêtes.
- **4 tests front réussis** : récupération de brouillon par UID/révision, stockage corrompu, envoi des seuls champs modifiés et validation des règles.
- Compilation front staging et génération du JAR réussies.
- Recette navigateur headless réussie, **7 captures** : données fictives, ordinateur 1440 px et téléphone 390 px, erreurs de champs, déplacement du focus, navigation entre étapes, génération du code, arrêt de l'attente après confirmation, pages profil et administration, et vraie page anonyme de connexion. Aucun compte Google réel n'a été utilisé.

Les captures et le résultat de recette sont conservés dans le dossier de travail `C:/Users/alban/Documents/ChatGPT/DEVELOPPEMENT/player_onboarding/`. Le dossier temporaire d'aperçu dans les sources du front est supprimé après recette.

Pour relancer les vérifications :

```powershell
# Depuis le front
npm run test:onboarding
npm run build:staging

# Depuis le backend, avec ECONOMY_TEST_URI pointant vers le cluster de test
python manage.py test players.test_onboarding economy markets quests
```

Le lanceur de recette du dossier de travail charge l'URI privée sans l'imprimer et les tests créent puis suppriment exclusivement leurs bases `rb_profiles_test_*` et `rb_econ_test_*`.

## Essais manuels

1. Ouvrir `http://localhost:5173/auth`. Avec un nouveau compte Google, vérifier que la fiche n'est pas préremplie avec l'identité réelle et que les champs de rang, argent et UUID ne sont pas proposés.
2. Saisir une identité, quitter avant de continuer, puis revenir avec le même compte : le brouillon local est retrouvé. Après une étape validée, vérifier la reprise depuis une autre session du même compte.
3. Soumettre des champs vides, puis corriger : les messages désignent les champs et le focus atteint le premier champ invalide.
4. Terminer sans Minecraft lorsque ce choix est autorisé : la fiche RP est enregistrée, mais les fonctions du personnage en jeu restent en attente de liaison.
5. Après activation des accès privés et redémarrage de Minecraft avec le JAR livré, demander un code et exécuter `/mc lier <code>` en solo. Vérifier que le site détecte l'association ; terminer la création puis se reconnecter au monde.
6. Réutiliser le même code, essayer un code expiré et un compte déjà associé : aucune double création ni association concurrente.
7. Avec un personnage existant, comparer rang, métiers et solde avant/après connexion. Modifier sa description et son portrait : la fiche est actualisée sans modification de progression.
8. Demander un nouveau nom, compléter le nom demandé puis annuler. Refaire une demande et la valider/refuser depuis `/admin/registration` ; vérifier le motif et l'historique côté joueur.
9. Ouvrir le même dossier dans deux fenêtres et enregistrer deux modifications : la seconde version périmée est refusée, avec possibilité de recharger la version enregistrée.
10. Tester les modes ouvert, validation staff et suspendu ; activer Minecraft obligatoire et une présentation obligatoire. Vérifier que le rang de départ ne peut pas être Admin et que les anciens joueurs ne sont pas réinitialisés.
11. Vérifier la file des dossiers, les demandes de remplacement Minecraft et leurs annulations. Le compte actuel doit rester associé tant que le remplacement n'est pas accepté.
12. Sur téléphone et au clavier : parcourir les trois étapes, choisir un portrait, consulter l'aide repliable, ouvrir le profil et traiter une demande admin sans débordement horizontal.

La connexion OAuth Google réelle et la confirmation depuis Minecraft restent des essais manuels : les tests automatiques utilisent un navigateur vierge, des API fictives pour l'UI et des identités Firebase simulées pour le backend.

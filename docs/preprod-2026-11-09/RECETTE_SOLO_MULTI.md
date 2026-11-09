# Recette Renblood — préproduction du 9 novembre 2026

## Périmètre et provenance

Fenêtre demandée : **du 9 juillet au 9 novembre 2026**. La recette croise les historiques des cinq dépôts, leurs changements locaux non encore publiés et les rapports d'audit/économie/inscription. L'historique contient peu de commits dans cette fenêtre : les changements non commités ne peuvent pas être datés individuellement. Cette matrice couvre tous les changements identifiés, avec une non-régression volontairement plus large des fonctions qu'ils touchent.

Parties couvertes : **front React, backend Django, Medieval Coins, NPC Shopkeeper et Medieval Structures**. Les dates et SHA de référence sont conservés dans le manifeste de livraison. Les exports de comptes, clés privées, mondes et configurations réelles restent hors Git.

## Ordre d'exécution

1. **Contrôle du lot et smoke test** : ENV, Google existant, une opération bancaire, un achat et sauvegarde/rechargement. Ne pas inviter le groupe si un P0 échoue.
2. **Solo** : exécuter les parcours fonctionnels avec le profil contenant les trois JAR du manifeste, dans un monde de recette sauvegardé et raccordé au backend staging. Refaire les cas de reconnexion et de persistance.
3. **Multi à trois comptes** : un administrateur et deux joueurs A/B distincts. Refaire les derniers stocks/chambres/contrats, les permissions et les interruptions.
4. **Modo et mobile** : tester le support sans droits admin, le site à 390 px, le clavier et les contrôles de son/carte.
5. **Groupe représentatif** : augmenter progressivement vers une quinzaine de joueurs, relever les diagnostics, rapprocher les reçus, puis arrêter/redémarrer proprement.

## Préparation des données et preuves

- Utiliser exclusivement la base **renblood_mongo_staging** et le site de staging. La production n'est pas une destination de recette.
- Garder un administrateur, un modérateur et des joueurs distincts. Pour Google, prévoir un utilisateur nouveau, un utilisateur Firebase ancien sans personnage et un personnage historique.
- Préfixer les établissements, routes, auberges, quêtes et articles de recette par **RECETTE-**. Les corrections monétaires utilisent un motif de recette et un reçu. Ne pas écraser les établissements existants pour gagner du temps.
- Ne pas connecter simultanément la même identité Minecraft depuis plusieurs copies de monde raccordées à la même base. Les contenus physiques copiés d'un monde ne constituent pas de nouvelles espèces légitimes ; séparer les fixtures solo/multi et rapprocher les données entre séries.
- Noter avant/après : banque disponible/réservée, espèces, inventaire/stock, reçu, UUID de test et heure. Les preuves nominatives restent dans le journal privé de recette, pas dans un dépôt public.
- Tester les coupures et arrêts forcés uniquement sur les copies de recette. Préférer un arrêt normal pour le serveur contenant les mondes conservés.
- Noter pour la performance : nombre de joueurs, vue/simulation, activité, matériel, version, durée, TPS et temps moyen de tick. Un relevé vide sans joueurs ne valide pas la charge à quinze joueurs. Ne pas déduire un percentile d'une simple moyenne.

## État des validations

La colonne **statut** du CSV est laissée à **À faire** pour les tests manuels. Les tests automatiques et le démarrage headless éventuellement exécutés sont consignés séparément dans `VALIDATION_AUTOMATIQUE.md` ; ils ne remplacent pas les interactions Google/Minecraft et les mesures en charge.

Statuts conseillés : À faire, Réussi, Échec, Bloqué, Non applicable (motif obligatoire). Pour chaque échec, remplir preuve et incident avec l'ID du cas, les étapes, le résultat observé et les logs utiles après retrait des secrets.

Le lot est acceptable lorsque tous les **P0** sont réussis, les P1 bloquants traités, les comptes rapprochés sans anomalie inexpliquée et la sauvegarde/retour arrière vérifiés sur copie. Aucun budget ou reçu ne doit être supprimé pour faire disparaître un incident.

## Matrice


### Installation / préproduction

Mode : Solo et multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| ENV-01 | P0 | Comparer les trois versions du manifeste avec les JAR du serveur et du client ; rechercher les doublons. | Une seule version de chaque mod du lot. Les SHA-256 correspondent au manifeste. |
| ENV-02 | P0 | Vérifier l’URL de l’API dans /mc admin config et ouvrir /api/health/ sur le backend staging. | Environnement staging, base renblood_mongo_staging et commit de livraison attendu ; aucune URL production. |
| ENV-03 | P0 | Ouvrir release.json sur le site Firebase de staging et comparer son commit avec le front livré. | Le site sert le build staging du bon commit ; aucune URL API localhost dans ce build. |
| ENV-04 | P0 | Démarrer une copie de recette du monde, attendre Done, se connecter puis quitter proprement. | Pas de crash de chargement des trois mods ; arrêt et sauvegarde propres. |
| ENV-05 | P0 | Redémarrer la même copie et vérifier blocs, inventaires et données des trois mods. | Aucun registre manquant, disparition d’objets ou retour aux valeurs initiales. |
| ENV-06 | P1 | Essayer un ancien client puis le client du manifeste. | Les protocoles incompatibles sont refusés clairement ; le client compatible entre. |
| ENV-07 | P1 | Vérifier sauvegarde des mondes, configurations, anciens JAR et procédure de restauration. | Les sauvegardes existent avant les tests ; les chemins de restauration sont identifiés. |

### Front / back — Google et dossiers

Mode : Web et jeu.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| AUTH-01 | P0 | Avec un nouveau compte Google, ouvrir le site, se connecter et commencer l’inscription. | Parcours en trois étapes ; aucun nom réel ni photo Google publiés automatiquement ; aucun choix libre de rang, monnaie ou UUID. |
| AUTH-02 | P0 | Se connecter avec un ancien compte Firebase sans personnage en base. | Le parcours se déclenche aussi ; il ne dépend pas de la date de création Google. |
| AUTH-03 | P0 | Saisir une identité, fermer la page avant de continuer, revenir avec le même compte. | Le brouillon de cet UID est récupéré sans reprendre celui d’un autre compte. |
| AUTH-04 | P0 | Valider une étape puis reprendre le dossier depuis une autre session du même compte. | Les données validées sont retrouvées côté serveur. |
| AUTH-05 | P0 | Valider prénom vide, nom vide, trop long ou uniquement des espaces. | Messages par champ, focus vers la première erreur ; aucun personnage incomplet créé. |
| AUTH-06 | P0 | Terminer sans Minecraft lorsque cette option est autorisée. | Identité RP enregistrée ; aucune fausse identité Minecraft ni accès au personnage en jeu avant association. |
| AUTH-07 | P0 | Demander un code et exécuter /mc lier <code> avec le joueur concerné. | Le site détecte la session vérifiée ; après validation du dossier, le personnage et sa banque à zéro sont préparés une seule fois. |
| AUTH-08 | P0 | Réutiliser le code, essayer un code expiré et associer le même UUID à deux dossiers. | Pas de double création, de double crédit ou de vol d’association ; refus explicites. |
| AUTH-09 | P0 | Ouvrir deux fenêtres et modifier le même dossier avec une révision ancienne. | La version périmée est refusée ; l’autre modification reste en place. |
| AUTH-10 | P0 | Fermer la fenêtre Google, couper le réseau pendant l’ouverture du dossier, puis réessayer. | Pas de création partielle ; message lisible, bouton de reprise et brouillon conservé. |
| AUTH-11 | P0 | Se connecter avec un personnage existant et comparer nom, rang, solde, talents, métiers et licences. | Aucune réinitialisation des données historiques. |
| AUTH-12 | P1 | Modifier présentation, origine et portrait ; consulter la fiche après navigation et reconnexion. | Les modifications apparaissent ; le cache ne réaffiche pas les anciennes données. |
| AUTH-13 | P1 | Demander un nouveau nom, compléter la demande, l’annuler, puis faire valider/refuser une nouvelle demande. | Nom courant conservé jusqu’à décision ; motifs et historique visibles. |
| AUTH-14 | P1 | Vérifier un compte Minecraft de remplacement, annuler puis faire accepter un remplacement. | Compte actuel conservé avant décision ; même dossier et même banque après acceptation. Aucun transfert automatique d’inventaire du monde attendu. |
| AUTH-15 | P1 | Tester les modes d’inscription ouvert, validation staff, suspendu ; rendre Minecraft ou une présentation obligatoire. | Les règles sont appliquées par le backend ; les anciens rangs et portraits choisis ne sont pas réinitialisés. |
| AUTH-16 | P1 | Changer de compte Google puis rouvrir personnage, finances et brouillon. | Aucune fiche, donnée de caisse ou saisie d’un ancien compte ne reste affichée. |
| AUTH-17 | P1 | Associer puis dissocier Discord depuis la fiche sur staging. | Retour sur le site staging avec le bon dossier. Si Discord refuse le callback, vérifier son autorisation dans le portail développeur, sans utiliser la production. |

### Front — DA et accessibilité

Mode : Ordinateur et téléphone.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| WEB-01 | P1 | Parcourir Accueil, Guide, Joueurs, Quêtes, Sessions, Talents, Carte et les pages d’information sur ordinateur. | Une seule navigation principale, DA cohérente et contenu utilisant correctement la largeur disponible. |
| WEB-02 | P1 | Parcourir les mêmes pages en 390 px puis en mode paysage et avec zoom navigateur. | Pas de débordement horizontal ; menus, textes, boutons et dialogues accessibles. |
| WEB-03 | P1 | Naviguer au clavier, ouvrir/fermer les menus, changer d’étape et fermer les dialogues avec Échap. | Focus visible, ordre logique et retour au déclencheur ; aucun piège au clavier. |
| WEB-04 | P1 | Activer la réduction des animations du système. | Les informations restent accessibles ; les animations non nécessaires sont réduites. |
| WEB-05 | P1 | Faire défiler la page Carte à la molette, puis manipuler volontairement la carte. | Le défilement de la page ne provoque plus un zoom involontaire ; les contrôles de carte restent utilisables. |
| WEB-06 | P1 | Cliquer une image d’exemple de l’accueil, zoomer, fermer et revenir à la page. | Image agrandie nette et fermeture possible ; pas de blocage du défilement. |
| WEB-07 | P1 | Changer l’arrière-plan de l’accueil, recharger puis contrôler le choix par défaut. | Le fond par défaut et les commandes de changement correspondent à l’interface et ne masquent pas le contenu. |
| WEB-08 | P1 | Démarrer la musique du site après interaction, modifier le volume, couper le son et naviguer. | Pas de superposition de lecteurs ; volume/mute fonctionnels et contrôle toujours accessible. |
| WEB-09 | P1 | Consulter soldes, taxes, grands montants et historiques de finances sur mobile. | Montants entiers exacts, disponibles/réservés/attendus distingués ; aucune valeur arrondie ou inventée pendant un chargement. |
| WEB-10 | P1 | Utiliser recherche globale, filtres, pagination, lien partagé d’un reçu et retour navigateur. | Résultats et états restent cohérents ; les pages réservées ne deviennent pas accessibles par un lien direct. |

### Commandes et tutoriels

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| CMD-01 | P0 | Tester /mc, /ns et /ms avec joueur, modo et admin. | Commandes regroupées sous le bon préfixe ; les droits sont contrôlés côté serveur. |
| CMD-02 | P1 | Utiliser Tab à chaque argument de budget, établissement, route, auberge, comptoir et article. | Suggestions adaptées au contexte, y compris noms avec espaces et données récemment créées. |
| CMD-03 | P1 | Essayer un nom inexistant, une quantité invalide et une commande avec arguments manquants. | Aucune erreur serveur générique ; l’aide indique ce qu’il manque. |
| CMD-04 | P1 | Lancer /mc tuto start, avancer, désactiver le guidage, quitter puis reprendre. | Étape et préférence persistantes ; le tutoriel n’encombre pas l’écran lorsqu’il est désactivé. |
| CMD-05 | P1 | Tester l’aide contextuelle des comptoirs, routes, auberges et explorations. | Les actions de reprise et les prérequis utiles sont expliqués au bon endroit. |
| CMD-06 | P1 | Rafraîchir plusieurs fois le statut et les données d’un joueur, puis se reconnecter et respawn. | Demandes regroupées ; HUD attaché à la bonne session ; pas d’affichage provenant de l’ancien joueur. |
| CMD-07 | P1 | Tester /ns road list et les diagnostics route/auberge après création et chargement du monde. | Liste sans exception, état des prérequis compréhensible et actualisé. |

### Banque, espèces et reçus

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| BANK-01 | P0 | Vérifier les conversions fer/bronze/argent/or, dont 64 fer, 4 096 fer et 262 144 fer. | Même valeur totale en inventaire, banque, messages et site. |
| BANK-02 | P0 | Déposer puis retirer une somme avec et sans monnaie exacte. | Espèces et solde évoluent une fois, avec reçu unique et montant exact. |
| BANK-03 | P0 | Double-cliquer dépôt/retrait et rejouer après un délai réseau. | Une seule opération financière ; pas de double remise ni de double débit. |
| BANK-04 | P0 | Retirer avec inventaire plein, puis libérer une place et reprendre. | Pas de perte de pièces ; opération refusée ou reprise avec état explicite. |
| BANK-05 | P0 | Déconnecter pendant un dépôt/retrait puis reprendre avec /mc economie reprendre. | Le même reçu est retrouvé ; une étape déjà confirmée n’est pas exécutée deux fois. |
| BANK-06 | P0 | Couper le backend pendant une opération sur une copie de recette, puis rétablir le service. | Pas de succès fictif ; réservations et incidents restent visibles jusqu’à résolution. |
| BANK-07 | P0 | Tester zéro, valeurs négatives, fractions et dépassements de limites par les interfaces disponibles. | Refus côté serveur avant mutation ; aucun contournement par un autre canal. |
| BANK-08 | P0 | Faire deux retraits concurrents sur le dernier disponible, avec deux sessions de recette autorisées. | La somme retirée ne dépasse pas le disponible ; le perdant reçoit un refus cohérent. |
| BANK-09 | P0 | Comparer le journal du site, la banque, les espèces et les reçus après redémarrage propre. | Les totaux se rapprochent ; les montants réservés ne sont pas affichés comme disponibles. |
| BANK-10 | P1 | Ouvrir un ancien compte non rapproché et un nouveau compte du parcours Google. | L’ancien suit sa procédure de préparation ; le nouveau démarre à zéro sans crédit gratuit. |
| BANK-11 | P1 | Tester bourse, change et pièces de toutes valeurs avec une quantité proche de la capacité maximale. | Valeur conservée, capacité contrôlée, retour visuel clair. |
| BANK-12 | P1 | Faire une correction admin motivée puis une compensation éligible. | Reçu et motif présents ; aucune suppression silencieuse du journal ni découvert permis. |

### Comptoir marchand et stock

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| SHOP-01 | P0 | Placer un comptoir, l’ouvrir normalement puis en shift-clic droit avec un objet en main. | Le bon menu s’ouvre une seule fois ; l’objet en main n’empêche pas l’accès propriétaire. |
| SHOP-02 | P0 | En créatif admin, ajouter un article depuis les références, régler achat/rachat/activité et enregistrer. | Article visible dans la liste configurée puis dans l’interface publique si actif. |
| SHOP-03 | P0 | En survie propriétaire, mettre un article en vente et contrôler le prix discret bronze/fer. | Prix lisible et exact ; offre visible au clic droit normal. |
| SHOP-04 | P0 | Déposer plusieurs piles de plusieurs objets dans Stock et envoyer la sélection. | Dépôt groupé ; les éléments refusés restent en inventaire ; aucune duplication. |
| SHOP-05 | P0 | Déposer dans un comptoir presque plein et reprendre une partie du stock. | Capacité et réservations prises en compte ; quantités source et destination exactes. |
| SHOP-06 | P0 | Vider une case, la réutiliser avec un autre objet puis rouvrir après synchronisation. | La case ne ressuscite pas l’ancienne offre ; l’offre courante correspond au vrai stock. |
| SHOP-07 | P0 | Tester objets avec NBT, nom personnalisé, durabilité ou enchantement différents. | Les variantes ne sont pas fusionnées ou remplacées abusivement. |
| SHOP-08 | P0 | Acheter le dernier stock avec deux joueurs simultanés. | Une seule vente réussie ; un seul débit et un seul transfert du dernier objet. |
| SHOP-09 | P0 | Vendre/acheter avec inventaire plein, argent insuffisant, comptoir fermé et synchronisation en cours. | Messages distincts et compréhensibles ; aucun débit sans remise contrôlée. |
| SHOP-10 | P0 | Modifier, supprimer puis réajouter un article pendant un envoi ou une coupure du backend. | La dernière modification confirmée subsiste ; pas de retour d’une ancienne configuration. |
| SHOP-11 | P0 | Réserver une case, tenter d’y déposer un autre article, annuler puis reprendre le premier. | Réservation respectée ; retour de l’article et référence du reçu cohérents. |
| SHOP-12 | P1 | Changer nom/propriétaire, ouvrir Articles puis Historique, redimensionner et enregistrer. | Saisies conservées ; pas de formulaire effacé ou de propriétaire incorrect après reconnexion. |
| SHOP-13 | P1 | Retirer les gains du comptoir avec propriétaire et compte non propriétaire. | Seul le propriétaire autorisé retire ; gains et reçus ne sont traités qu’une fois. |
| SHOP-14 | P1 | Détruire un comptoir contenant stock, réservation ou gains, puis tester le parcours admin de récupération. | Pas de perte silencieuse ; confirmation et traitement des incidents selon les règles affichées. |
| SHOP-15 | P1 | Consulter les références disponibles côté site et jeu. | Les 100 références proposées et les références préexistantes conservées sont accessibles ; un catalogue n’alimente pas le stock automatiquement. |

### PNJ, routes commerciales et contrats

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| NPC-01 | P0 | Créer un modèle, un PNJ décoratif et une route avec la baguette et les commandes. | Noms uniques contrôlés, droits appliqués et données sauvegardées. |
| NPC-02 | P0 | Tester /ns road list et le diagnostic d’une route incomplète puis complète. | Pas d’exception ; points/prérequis manquants expliqués. |
| NPC-03 | P0 | Acheter un contrat, livrer le bon objet et contrôler la remise d’argent. | Les PNJ paient en espèces selon le reçu ; pas de crédit bancaire arbitraire. |
| NPC-04 | P0 | Présenter un objet incorrect, une quantité insuffisante et un inventaire trop plein pour la récompense. | Refus rouge explicite et demande consultable ; réussite verte uniquement après remise effective. |
| NPC-05 | P0 | Abandonner un échange puis vérifier les objets, l’historique et la présence du marchand. | Pas d’objet perdu ni d’historique fantôme ; en cas d’échec de sauvegarde, l’état reste récupérable. |
| NPC-06 | P0 | Faire agir deux joueurs sur le même contrat/PNJ, puis rejouer la confirmation. | Une seule attribution et un seul paiement. |
| NPC-07 | P0 | Créer une auberge, associer route et menu, activer et vérifier le diagnostic de spawn. | PNJ générés lorsque tous les prérequis sont remplis ; raison visible sinon. |
| NPC-08 | P1 | Tester budget fini, allocation quotidienne et budget illimité sur un établissement de recette. | Plafonds et rechargements cohérents ; illimité explicite ; pas besoin de réapprovisionnement manuel route par route en mode illimité. |
| NPC-09 | P1 | Cliquer plusieurs fois un PNJ pour consulter sa demande sans échanger. | Pas d’écriture backend à chaque consultation ; messages non répétitifs. |
| NPC-10 | P1 | Quitter/recharger le monde et redémarrer le serveur après apparition d’un client d’auberge. | Identité, skin, demande et association de route conservés. |
| NPC-11 | P1 | Tester voyage/capitaine avec destination invalide, validation puis interruption. | Aucun ticket/argent consommé avant validation ; pas de double trajet payé. |
| NPC-12 | P1 | Tester nom de modèle déjà existant, accents, espaces et deux créations simultanées. | Doublons refusés clairement, une seule entrée durable. |
| NPC-13 | P1 | Créer/modifier pendant une indisponibilité de fichier ou de backend sur une copie de recette. | L’échec est visible, le dernier fichier confirmé est préservé ; aucun document partiel remplace les données. |

### Auberges et chambres

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| INN-01 | P0 | Définir auberge, chambres, portes et prix puis louer une chambre. | Accès, durée, paiement et chambre attribuée correspondent au reçu. |
| INN-02 | P0 | Faire louer la dernière chambre par deux joueurs simultanés. | Un seul occupant confirmé ; aucun double paiement pour la même place. |
| INN-03 | P0 | Quitter/rejoindre puis redémarrer pendant une location. | Occupant, durée et état du contrat sont conservés. |
| INN-04 | P1 | Tester expiration, libération puis nouvelle location. | Accès et disponibilité sont mis à jour sans conserver un ancien occupant. |
| INN-05 | P1 | Contrôler une auberge issue d’une ancienne sauvegarde. | Anciens montants et chambres conservés ; aucun arrondi ou crédit spontané lors de la migration de format. |
| INN-06 | P1 | Désactiver/réactiver puis changer route ou menu de l’auberge de recette. | Pas de doublon de clients ni de boucle de spawn ; diagnostic actualisé. |

### Explorations, camps et retours

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| EXP-01 | P0 | Démarrer une exploration avec groupe, durée, destination et coffre de test. | Bon groupe envoyé au bon camp ; coût payé une seule fois. |
| EXP-02 | P0 | Placer des coffres pour plusieurs participants puis comparer leurs emplacements au camp. | Cases distinctes ; contenus non mélangés. |
| EXP-03 | P0 | Terminer et comparer contenus, équipements et animaux avant/après. | Retour complet selon les règles ; aucun objet dupliqué. |
| EXP-04 | P0 | Occuper le point de retour du coffre puis terminer l’expédition. | Le contenu reste conservé et localisable ; pas d’écrasement du coffre présent. |
| EXP-05 | P0 | Exécuter /ms exploration incidents avec un admin. | Les coffres conservés et leurs coordonnées utiles sont retrouvables. |
| EXP-06 | P0 | Lancer deux groupes simultanés ; terminer le premier pendant que le second continue. | Limites, minuteurs, coffres, animaux et état de nettoyage indépendants. |
| EXP-07 | P0 | Déconnecter un participant, finir l’exploration, puis le reconnecter. | Le joueur retrouve un état de retour cohérent ; pas de maintien dans un camp nettoyé. |
| EXP-08 | P0 | Redémarrer proprement pendant un départ puis pendant un nettoyage, sur copie de recette. | Reprise durable ; ni redébit, ni suppression prématurée des coffres/animaux. |
| EXP-09 | P1 | Essayer de dépasser la taille du groupe et les limites spatiales d’un camp. | Refus explicite ; pas de superposition ni de génération infinie. |
| EXP-10 | P1 | Contrôler une ancienne exploration chargée après mise à jour. | État lisible, retour administrable et données conservées. |

### Quêtes, talents, métiers et sessions

Mode : Solo, multi et site.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| PROG-01 | P0 | Accepter une quête depuis le site puis le jeu et vérifier PNJ/objectifs associés. | Un seul état par joueur ; objectifs et PNJ attendus cohérents. |
| PROG-02 | P0 | Terminer une quête avec récompenses monnaie/objet/XP, puis rejouer la confirmation. | Récompense unique, reçu retrouvable et inventaire/XP exacts. |
| PROG-03 | P0 | Terminer avec inventaire plein puis reprendre une récompense matérielle en attente. | Aucune perte ni attribution supplémentaire ; état d’attente compréhensible. |
| PROG-04 | P1 | Annuler/reprendre une quête, compléter un parent puis une sous-quête. | Transitions et accès aux dépendances conformes aux règles. |
| PROG-05 | P1 | Débloquer un métier ou talent autorisé et contrôler ses bonus après respawn/reconnexion. | Pas d’empilement répété des bonus ; expérience et choix conservés. |
| PROG-06 | P1 | Modifier un niveau/choix en admin et consulter fiche, talents et HUD. | Les nouvelles valeurs se propagent à la bonne personne sans conserver une ancienne session. |
| PROG-07 | P1 | Créer une session et des futurs, répondre avec deux joueurs, changer le statut puis recharger. | Résultats, participations et droits cohérents entre site et jeu. |
| PROG-08 | P1 | Ouvrir la carte et le journal de quêtes pendant l’activité du serveur. | Pas de blocage du jeu lié au réseau ; contenu utilisable avec cache/erreur explicite. |

### Objets, héraldique et musique

Mode : Solo puis multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| ART-01 | P1 | Ouvrir les onglets créatifs des trois mods et rechercher les objets bonus. | Monnaies/outils économiques séparés de Maisons & étendards ; objets Structures et PNJ accessibles dans leurs onglets. |
| ART-02 | P1 | Vérifier les neuf maisons et les deux décorations royales, leurs icônes et traductions. | Aucune texture manquante ; symboles de maison cohérents ; logo royal original conservé. |
| ART-03 | P1 | Placer drapeau de tour, grande bannière et bannière 1×2 dans les quatre orientations, sur murs/angles. | Image entière sans répétition erronée ; géométrie et orientation correctes. |
| ART-04 | P0 | Casser chaque type multibloc depuis plusieurs morceaux puis replacer près d’un obstacle. | Un seul objet rendu, aucun morceau fantôme ni duplication ; obstruction gérée. |
| ART-05 | P1 | Porter l’étendard en deuxième main, marcher, courir et observer avec un second joueur. | Bon rendu en première/troisième personne, sans masquer excessivement la vue. |
| ART-06 | P1 | Équiper armures de maison et armures de cheval, puis quitter/rejoindre et changer de perspective. | Textures et emblèmes corrects, équipement fonctionnel et visible des autres joueurs. |
| ART-07 | P1 | Placer sceau/piédestal royal et observer de près/loin sous différents éclairages. | Bloc lisible et cohérent avec le symbole d’origine. |
| ART-08 | P1 | Réaliser les crafts des objets de maison et bonus proposés à la fabrication. | Ingrédients/quantités corrects ; aucune recette manquante pour un objet annoncé craftable. |
| ART-09 | P1 | Lire le disque dans un jukebox ; modifier la catégorie sonore Minecraft, arrêter puis redémarrer la lecture. | Musique jouée dans la bonne catégorie, arrêt effectif et pas de lecture doublée ; les autres joueurs proches l’entendent. |
| ART-10 | P1 | Tester torche magique, autel et comptoir de banque après placement/rechargement. | Objets accessibles, interactions et sauvegardes fonctionnelles. |

### Administration, modération et reprise

Mode : Web et multi.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| OPS-01 | P0 | Ouvrir pages admin/support avec joueur, modo et admin, y compris par URL directe. | Droits vérifiés côté backend ; le modo dispose du support prévu sans les mutations admin. |
| OPS-02 | P1 | Rechercher un reçu, le partager et ajouter une note de support. | Bonne opération retrouvée ; la note ne change ni montant ni état financier. |
| OPS-03 | P1 | Consulter établissements, budgets, stock, caisses et transactions depuis l’intendance. | Même état confirmé que dans le jeu ; actualisations et erreurs explicites. |
| OPS-04 | P1 | Préparer une taxe future puis vérifier avant et après sa date d’effet. | Pas d’application prématurée ; version et période traçables. |
| OPS-05 | P1 | Suspendre puis réactiver un établissement de recette et contrôler ses droits. | Suspension réversible ; pas de suppression de stock, soldes ou historique. |
| OPS-06 | P0 | Rapprocher les reçus après tous les scénarios de panne et lister les éléments à vérifier. | Aucune opération ambiguë masquée ; disponible/réservé/matériel en attente cohérents. |
| OPS-07 | P0 | Restaurer une sauvegarde sur une copie distincte, jamais sur le monde actif pendant un échange. | Ancien lot, monde et configurations retrouvables ; rollback documenté et redémarrage possible. |

### Charge, requêtes et persistance

Mode : Multijoueur.

| ID | Priorité | Manipulation | Résultat attendu |
|---|---|---|---|
| LOAD-01 | P0 | Relever une minute au repos puis répéter avec 3, 10 et environ 15 joueurs sur la même scène. | Nombre de joueurs, matériel, durée et activité sont consignés ; pas de crash ou croissance sans fin des files. |
| LOAD-02 | P1 | Répéter consultation PNJ, HUD, inventaires et diagnostics sans transaction. | Les lectures répétées sont regroupées/cachées ; pas d’écriture financière à chaque consultation. |
| LOAD-03 | P0 | Faire acheter, vendre, déposer du stock et prendre une chambre simultanément. | Pas de duplication, survente, découvert ou réservation abandonnée sans reçu. |
| LOAD-04 | P1 | Pendant cette activité, relever /forge tps et /mc economie diagnostic avec un admin. | Viser 20 TPS ; relever temps moyen de tick et coût des requêtes. Un budget moyen de tick supérieur à 50 ms doit être investigué, pas présenté comme 20 TPS garantis. |
| LOAD-05 | P1 | Répéter démarrages d’exploration, générations de camp et sauvegardes pendant les échanges. | Pas de blocage prolongé des ticks ; retours, coffres et transactions restent cohérents. |
| LOAD-06 | P0 | Perdre la connexion au backend puis la rétablir pendant une session active de recette. | Délais bornés, erreurs lisibles, files bornées et reprise des mêmes reçus sans remise supplémentaire. |
| LOAD-07 | P0 | Faire un arrêt propre sous activité, redémarrer puis vérifier le journal et les états en attente. | Aucune perte silencieuse ; opérations ambiguës visibles et récupérables. |
| LOAD-08 | P1 | Observer mémoire, logs et compteurs après plusieurs séries d’échanges et de reconnexions. | Pas de fuite croissante de sessions/PNJ/threads ni d’erreurs répétées masquant le diagnostic. |

**130 cas manuels** sont fournis dans le [CSV remplissable](MATRICE_TESTS.csv). Les tests regroupés sous « Solo puis multi » doivent être rejoués dans les deux modes.

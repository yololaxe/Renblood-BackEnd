# Catalogue de référence — Minecraft 1.20.1

100 objets vanilla : alimentation, agriculture, bois, pierre, métaux, construction,
outils, armes, armures, alchimie et ressources rares. Le CSV contient les prix proposés.

Les prix sont **par objet**, en pièces de fer : 64 fer = 1 bronze ; 4 096 fer = 1 argent.
Ce barème de départ prolonge les huit références initiales et reste à ajuster en recette.
Il ne modifie ni les budgets des établissements ni les offres et stocks des comptoirs.
Aucune XP n'est attribuée automatiquement : les nouvelles références commencent à zéro.

Depuis le backend, avec l'environnement choisi :

```powershell
python manage.py seed_reference_items --dry-run
python manage.py seed_reference_items
```

L'import ajoute les références absentes. Il préserve les prix, noms, XP et états désactivés
déjà configurés, y compris les objets personnalisés hors de ces 100 références.
Une interruption se reprend en relançant la commande. Ne pas employer `seed_markets`
pour cet ajout ciblé : cette ancienne commande initialise également villes et modificateurs.

Après import, en jeu : `/mc admin market reload`, ou relancer le monde pour recharger
les références du backend. Les références ne remplissent pas automatiquement un comptoir.

## Menus créatifs

- **Medieval Coins** : 11 objets généraux (monnaies, bourse, banquier, banque,
  torche magique, autel, comptoir marchand, disque).
- **Maisons & étendards** : 110 objets (sceau et piédestal royaux, puis les neuf maisons
  par ordre alphabétique : blason, bannières, drapeaux, étendard portable, armure et armure de cheval).
- Les objets de NPC Shopkeeper et Medieval Structures restent dans leurs onglets existants,
  qui contiennent déjà tous leurs objets enregistrés.

Le bloc technique de torche murale utilise l'objet de torche magique ; il n'a pas d'objet distinct.


## Import effectué le 7 novembre 2026

La configuration locale et staging pointe sur la même base `renblood_mongo_staging`.
L'import a ajouté **86 références**, conservé les **16 références existantes**, et produit
un catalogue de **102 références** : les 100 proposées plus deux références déjà présentes.
Les API locale et staging servent toutes les deux ces 102 références.
Un second import n'ajoute aucun doublon. Les documents existants sont inchangés,
y compris leurs prix, XP, noms et dates. Les sauvegardes et le bilan sont dans `imports/`.

Le catalogue sert à la configuration des objets et aux prix de référence des PNJ.
Les offres, stocks, budgets et anciens tarifs calculés par ville restent inchangés.
Le recalcul général des marchés a été refusé par la vérification automatique parce
qu'il aurait également changé les tarifs antérieurs. Aucune écriture de recalcul n'a eu lieu.
Les nouveaux objets à tarification automatique par ville devront être inclus lors
du prochain recalcul des marchés décidé par l'administrateur depuis le site.

Les caches de références du dossier `localhost_server1.20.1` et du profil solo
`Test Mods RP` sont synchronisés sur l'API, avec sauvegarde des anciens fichiers.
Le JAR **medieval_coins-1.0.65.jar** est installé dans le profil solo.
Pour voir le nouvel onglet, relancer Minecraft avec ce profil. Si le monde est déjà ouvert,
`/mc admin market reload` recharge les références ; il ne remplit pas les offres du comptoir.

Compilation et génération du JAR réussies ; 171 tests backend réussis, dont les cinq
nouveaux tests de catalogue. Les 100 identifiants vanilla ont leur modèle d'objet dans
les ressources Minecraft 1.20.1. Le rendu des onglets reste à vérifier en jeu.

# Protocole de photographie et de mesure

## Photo cohérente

Le relevé doit associer environnement, versions source/JAR, début/fin, heure UTC et identifiant de photographie. Export Mongo en lecture seule avec projection minimale ; conserver montants d’origine comme chaînes. Ne pas démarrer Django pour exporter : le démarrage de l’application peut déclencher d’autres activités.

Sources à réunir : Player.money/id/id_minecraft ; références/prix/modificateurs ; commerces/transactions/retraits ; inventaires joueurs, caisses et stocks dans les NBT ; avances/dettes de chambres ; fichiers de transactions en attente et catalogues/historiques PNJ. Inventaires de joueurs absents ou chunks non chargés = couverture inconnue, pas valeur nulle.

L’exporteur Mongo fourni ne collecte pas les NBT et ne fige pas les écritures. Une collecte pendant activité est diagnostique uniquement. Pour l’arrêté de migration, utiliser une copie figée du monde ET de la base au même point de coupure métier, après traitement/gel des opérations en vol.

## Classification

- Banque : entiers positifs, zéro, fractions, négatifs, non numériques, hors limites.
- Identité : UUID Minecraft absent/invalide/provisoire, collisions, propriétaires orphelins.
- Caisses : compte réel distinct d’un cumul de gains ; comparaison locale/web seulement à la même date et après déduplication.
- Chambres : avances et dettes classées séparément, jamais additionnées à la richesse sans interprétation du contrat.
- Stock : item/NBT/quantité, local autoritaire, référence web et date ; objet inexistant signalé.
- Pending : identifiant unique, ancienne version de prix, étape connue et preuve ; ambiguïtés envoyées en rapprochement.

Le rapport n’effectue aucune écriture correctrice. Le total de banque exporté n’est pas la masse monétaire totale. Le total « gains historiques − retraits » n’est pas une deuxième caisse à ajouter.

## Mesures initiales

`baseline.py probe` mesure uniquement des GET locaux : statut, durée, taille de réponse et médiane. Les erreurs HTTP/réseau restent visibles ; elles ne constituent pas une mesure de performance fonctionnelle réussie. La taille est celle du corps HTTP, pas un relevé de tous les paquets réseau.

Protocole complet : profiler les routes réellement consommées avec jeu de données représentatif, observer médiane/p95/p99, requêtes et cardinalité, froid/chaud, concurrence bornée. Relever les requêtes via instrumentation backend dans un environnement de recette, sans activer des logs de secrets. Mesurer les chargements front avec réseau/CPU comparables, temps jusqu’à interaction et volume de listes ; les compiler n’est pas mesurer leur réactivité.

Minecraft : même monde/copie, même machine, mêmes mods/JAR, joueurs et comptoirs représentatifs. Relever TPS/MSPT p50/p95/p99, blocages >50 ms, durée des synchronisations, volume des files et latence d’ouverture/confirmation ; avec API disponible, lente puis indisponible. Pas de charge artificielle sur un serveur non identifié. Aucune commande de profilage installée ou supposée disponible par le document.

Budget initial de recette à confronter aux mesures : aucun appel HTTP synchrone sur le thread de tick ; aucune croissance illimitée des files ; écran de consultation utilisable même en échec API ; actions monétaires affichant un état sous 300 ms et un résultat ou attente explicite sous 5 s. Ce sont des objectifs d’interface/architecture, pas des résultats observés. Les budgets p95 serveur et front seront arrêtés après données représentatives.

Statut de validation : sources et outils vérifiables localement ; arrêté économique et profilage jeu nécessitent les données/instance correspondantes. Voir ETAT.md pour les résultats réellement produits.

# Performances — mesures et limites

## Comparaison reproductible

Base Mongo temporaire distincte de l’environnement de jeu, supprimée après essai. Jeu de **2 000 reçus synthétiques**, chacun contenant un NBT de 8 192 octets ; même tri indexé et même limite de 51 documents. Douze lectures par variante. Les essais mesurent le client Python et Mongo, sans la couche HTTP et sans charge concurrente.

| Lecture | Médiane | Plus lent des 12 essais | Taille JSON |
|---|---:|---:|---:|
| Documents complets | 18,01 ms | 60,37 ms | 430 440 octets |
| Projection sans NBT | 12,36 ms | 22,35 ms | 11 832 octets |

Réduction de taille : **97,25 %** dans ce scénario. Le plan Mongo utilise l’index et examine **51 clés / 51 documents**, avec 51 résultats techniques pour déterminer s’il reste une page après les 50 affichés. Le champ `p95_ms` du rapport reprend ici le maximum selon le rang supérieur sur douze mesures ; cet échantillon reste trop court pour une garantie de percentile en exploitation.

Le benchmark compare les deux formes d’une même lecture, pas deux déploiements complets du projet. Les chiffres dépendent du NBT artificiel et du réseau ; ne pas généraliser ce gain à toutes les routes. Rapport détaillé et plan d’exécution : `reports/performance.json`. Script : `tools/measure.py` ; il exige la connexion de recette du back et crée exclusivement une base `rb_econ_test_<suffixe aléatoire>`.

L’essai HTTP initial n’a pas abouti car le back local n’était pas lancé. Il ne fournit aucune référence de latence API. Aucun monde disponible : aucun chiffre de TPS, de coût de tick ou de sauvegarde réelle n’est revendiqué.

## Optimisations livrées

- Pagination par curseur de 50 éléments et lectures bornées ; index sur date/état/établissement/propriétaire/clé, offres et programmations. Reçus listés sans NBT. Enrichissement des étiquettes et remises par requêtes groupées.
- Initialisation du client bancaire partagée sous verrou. Requêtes de support limitées en durée. Recherche des récompenses en attente par agrégation bornée plutôt que chargement de tous les accomplissements et de toutes les récompenses.
- Les métadonnées de commerce et d’offre identiques sont mémorisées **5 secondes**, au maximum 256 entrées ; un échange répété évite les deux appels de déclaration supplémentaires. Les modifications locales de prix/version/NBT provoquent une nouvelle clé. Les suspensions, réservations, soldes et stocks sont toujours contrôlés au règlement par le back.
- Le back évite la réécriture d’une offre inchangée. Le marché client réutilise sa liste filtrée pendant 250 ms ou jusqu’à modification de la recherche, au lieu de la recalculer plusieurs fois par image.
- Les statuts Minecraft sont bornés et limités en fréquence. Aucun appel périodique ajouté par tick ; pas de diffusion globale de tous les comptes. Les nouvelles réponses de statut sont ciblées sur le joueur concerné.
- Le front annule les lectures obsolètes, masque les lignes de l’ancien onglet, pagine les listes et impose un délai réseau de quinze secondes. Une réponse incertaine à une écriture conserve sa clé pour la reprise.

## Mesures à faire sur le futur monde

`/economie diagnostic` fournit pour l’instance en cours le nombre, la moyenne, une estimation p95 par classes et le maximum des appels HTTP et sauvegardes natives vérifiées. Ces agrégats sont bornés, sans URL, identité de joueur ni observation par tick. Ils repartent de zéro au redémarrage. Compléter par les métriques habituelles du serveur pour les ticks : ce diagnostic ne mesure pas le MSPT.

Budgets **proposés pour la recette**, pas résultats acquis : liste de support API p95 < 400 ms sur le réseau de référence, règlement complet p95 < 1,5 s hors incident, budget de tick 50 ms et coût additionnel des sauvegardes à relever avant fixation d’un seuil. Noter matériel, volumes, latence réseau, échelle GUI et nombre de joueurs simultanés. Tester 1, 10 puis 30 opérations concurrentes sur des comptes de recette, y compris dernier stock et dernière capacité. Bloquer l’ouverture si les incidents restent sans reçu explicable.

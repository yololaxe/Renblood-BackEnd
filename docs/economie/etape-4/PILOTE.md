# Pilote proposé — Circos

**Préparé, non démarré.** Le monde n’existe pas encore ; aucune observation de joueur, aucun budget alloué et aucun nouveau tarif publié. Le choix d’une ville et d’un petit catalogue permet une recette de bout en bout avant extension.

Périmètre initial : pain, blé, bûche de chêne, bâton, pierre taillée brute (`cobblestone`), lingot de fer, épée en fer et pioche en pierre. Ne publier un objet que lorsque ses ingrédients, conversions et débouchés sont tarifés et vérifiés ; le catalogue peut donc commencer plus petit. Garder la taxe à 0 et la dynamique désactivée. Version de travail : `pilote-circos-01`.

Ne pas appliquer un taux global de rachat à 70 % : la simulation de l’étape 3 laisse deux possibilités de revente directe et des marges de craft très différentes. Fixer les prix par filière après relevé des matières et du temps de jeu. Le coût d’un trajet ou d’un craft représente une activité possible à rémunérer ; ne pas supprimer automatiquement toute marge positive.

Les enveloppes sont finies et alimentées par transfert bancaire tracé. Dimensionner le budget de rachat à partir des volumes de la séance prévue, avec plafond validé et réserve explicitée. Épuisement : arrêt lisible du rachat, sans émission monétaire ni recharge automatique. Observer séparément contrats PNJ, clients d’auberge et comptoir de ville. Aucun montant universel de budget n’est imposé sans participants ni stock réel.

## Relevé pendant les séances

| Indicateur | Calcul / décision |
|---|---|
| Gain par activité | Évolution espèces + banque + caisses propres, diminuée des transferts reçus et augmentée des transferts envoyés, divisée par temps actif. Distinguer vente d’un stock ancien et production de la séance ; suivre matières et objets séparément. |
| Panier essentiel | Prix effectivement disponible de 8 pains + 1 pioche en pierre + 1 épée en fer ; comparer au revenu médian horaire observé. Objectif initial de discussion : accessible après une séance de 30 à 60 min, à ajuster selon progression voulue. |
| Ruptures | Minutes d’indisponibilité par offre ; distinguer stock, enveloppe et fermeture. Revoir approvisionnement si rupture > 10 % du temps de séance. |
| Support | Reçus à vérifier / 100 règlements, temps de résolution, raison. Toute duplication ou perte inexpliquée bloque l’extension. |
| Performance | Latence médiane/p95, taille des pages, mesures de sauvegarde et ticks sur le matériel retenu. |

Échantillon proposé : au moins deux séances, trois activités distinctes et vingt règlements confirmés par activité avant décision tarifaire. Ce minimum sert au démarrage ; il ne prétend pas établir une mesure statistique fiable. Les journaux donnent les flux, pas le temps actif ni la valeur de tout le stock : utiliser une fiche de séance pour compléter ces observations.

## Prix dynamiques en simulation seulement

`python -m economy.pilot --input <observations.json> --report <rapport.json>` fonctionne **hors ligne**, sans connexion à la base et sans option d’application. Entrées entières : prix de référence, prix indicatif courant, stock cible, stock observé et nombre de ventes. Avant vingt échanges, proposition inchangée. Ensuite variation indicatrice plafonnée à ±5 % par observation et ±20 % de la référence, arrondie vers le bas au fer entier. Ce calcul expérimental n’intègre pas encore trajet, saisons ou demande par joueur.

`reports/pilot-observations.json` et `reports/pilot-shadow.json` montrent quatre cas **synthétiques** : stock normal, rupture, abondance et échantillon trop petit. Les références 48 fer pour le pain et 228 pour le lingot proviennent des minima inter-marchés relevés à l’étape 3 ; **ce ne sont pas des tarifs validés pour Circos**. Cible de stock et volumes sont fictifs.

Une tâche de fond pourra fournir ces observations au simulateur pendant le pilote. Aucune tâche de collecte ou de publication dynamique n’est installée ici. La mise en service du pilote et les décisions sur des observations réelles appartiennent à la recette commune, avant généralisation.

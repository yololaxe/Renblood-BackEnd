# Catalogue des règles de départ

| ID | Décision de conception v1 | Statut |
|---|---|---|
| ECO-01 | Fer entier, base 64, montant JSON chaîne, dépassement rejeté | Contrat cible fixé |
| ECO-02 | Trois poches distinctes ; espèces inconnues ≠ zéro | Contrat cible fixé |
| ECO-03 | Dépôt/retrait/change gratuits ; change conserve la valeur | Règle initiale proposée |
| ECO-04 | Pas de crédit ni intérêt automatique ; avances/dettes de chambre séparées | Règle initiale proposée |
| ECO-05 | Commerce joueur : stock réel et recette transférée, propriétaire explicite | Contrat cible fixé |
| ECO-06 | Rachat PNJ financé et plafonné par budget ; aucune création implicite | Contrat cible fixé |
| ECO-07 | Vente PNJ à référence locale ; rachat à 70 %, arrondi inférieur ; petits prix par lot | Paramètre pilote, à simuler |
| ECO-08 | Taxe commerce joueur 2 % ; ville sinon trésor royal ; recettes détaillées | Paramètre pilote, à simuler |
| ECO-09 | Une publication quotidienne ; pas de hasard induit par recalcul | Règle initiale proposée |
| ECO-10 | Dynamique désactivée au lancement ; simulation sur volumes nets | Activation conditionnelle |
| ECO-11 | Récompense unique, argent bancaire annoncé ; livraison objets reprise | Contrat cible fixé |
| ECO-12 | Corrections par écritures liées et motivées | Contrat cible fixé |

« Fixé » désigne le contrat de réalisation, pas une fonctionnalité déployée. Les taxes, marges et limites doivent être versionnées ; un historique garde les anciennes règles. Ne pas bloquer les prix libres des joueurs avec les bornes du rachat PNJ.

Invariants de recette : double clic ; deux acheteurs du dernier objet ; prix changé ; débit répondu trop tard ; inventaire plein ; crash après remise avant confirmation ; caisse détruite/transférée ; vendeur déconnecté ; fraction de taxe ; récompense répétée ; UUID provisoire ; entier au maximum ; objet nommé/enchanté ; dette de chambre négative historique.

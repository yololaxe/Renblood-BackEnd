# Première recette Minecraft de l’étape 3

À réaliser sur un monde jetable avec les trois JAR compatibles, le back de recette et des comptes de test explicitement préparés. Aucun monde existant n’est requis pour les contrôles automatiques déjà livrés.

| Parcours | Attendu |
|---|---|
| Acheter le dernier objet avec deux joueurs | Une seule réservation et une seule remise ; l’autre demande est refusée. |
| Modifier un prix pendant une consultation | Pas de paiement au nouveau prix sans nouvelle consultation. Un reçu déjà réservé conserve son ancien prix. |
| Vendre au marchand sans budget | Aucun objet consommé et aucune monnaie émise ; le budget doit être alimenté ou recevoir des ventes. |
| Acheter avec une grosse pièce | Rendu exact et place contrôlée ; pas de monnaie perdue ou jetée si l’inventaire ne convient pas. |
| Vendre le dernier stack d’un inventaire plein | La place libérée par les objets vendus peut accueillir le paiement ; sinon refus sans consommation. |
| Déposer puis acheter/reprendre un objet personnalisé | Nom, enchantements, dégâts et autres NBT conservés ; aucune extraction directe depuis les cases d’affichage. |
| Détruire un comptoir | Pas de duplication par les drops ; caisse et stock v1 conservés au back et récupérables par leur propriétaire. |
| Propriétaire vendeur hors ligne | Recette dans sa caisse ; aucun besoin de charger son inventaire ni de le connecter. |
| Deux retraits de caisse simultanés | Un seul transfert au-delà du disponible ; pas de découvert. |
| Contrat PNJ validé deux fois | Un seul paiement ; budget effectivement débité, objets restants conservés à la fermeture/déconnexion. |
| Louer une chambre simultanément | Une occupation, un règlement conservé ; la seconde remise refusée libère sa réservation. |
| Payer une avance de loyer | Montant entier positif, caisse créditée après preuve, dette/avance persistée dans la sauvegarde native. |
| Servir un voyageur sans budget | Pas de consommation de l’objet ni de recette fictive. |
| Annuler une exploration | Seul le payeur peut annuler avant départ ; remboursement du service original, une seule fois, avec restitution fiscale. |
| Terminer une quête puis couper avant le versement | Accomplissement accepté retrouvé à la connexion ; récompense bancaire versée une seule fois. |
| Récompense avec inventaire plein | Argent en banque si accepté, objets conservés en attente, aucun drop. |
| Couper pendant une remise | `APPLIED` confirme le même reçu ; `APPLYING` ambigu demande un rapprochement et ne redonne pas les objets. |
| Consulter Mes finances | Banque, caisses, état des objets et références cohérents avec les mêmes reçus du back. |

Pour chaque incident, relever le reçu, les espèces avant/après, le stock, le disponible et le réservé des comptes, puis lancer `python -m economy.audit`. Ne pas effacer les journaux pour « débloquer » une opération. Une reprise administrateur doit vérifier les objets et les sauvegardes avant de décider livraison ou annulation.

Les exports de recette doivent comprendre les coûts des sauvegardes et les latences, puis les essais clavier, téléphone, échelles GUI Minecraft et profil serveur de référence. Les tests automatiques seuls ne remplacent pas cette recette.

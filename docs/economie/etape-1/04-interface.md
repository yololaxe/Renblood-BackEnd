# Charte commune — web et jeu

## Identité

Fond #11110F ; surface #1B1B17 ; bordure #44403C ; texte principal #FAFAF9 ; secondaire #A8A29E ; accent #D6B970, focus #FCD34D. Succès #86EFAC, alerte #FCD34D, erreur #FDA4AF ; toujours accompagnés d’un libellé ou d’une icône. Aucun état transmis par couleur seule.

Web : police sans serif existante, grands titres serrés pour les pages, chiffres tabulaires pour les montants. Ne pas charger une nouvelle police externe pour les chiffres. Minecraft : police native lisible aux échelles GUI prises en charge ; pas de imitation minuscule de la typographie web. Icônes communes fer/bronze/argent/or, toujours dans le même ordre. Texture discrète, aucun bruit derrière les montants.

Espacement web 8/16/24/32 px ; grille Minecraft adaptée à son échelle, alignements et marges proportionnels. Boutons web tactiles au moins 44 px. Contraste texte normal >= 4,5:1 à contrôler sur le rendu effectif ; ne pas supposer que chaque combinaison de la palette le satisfait.

## Composants à réaliser

MoneyAmount (chaîne canonique et pièces), PocketBalance (poche/disponible/réservé/date), QuantityPicker, PriceBreakdown, ReceiptStatus, SyncStatus, Confirmation, EmptyState, ErrorState, AdminCompensationPreview. Chaque composant a un rendu web et un rendu jeu partageant vocabulaire et états, pas forcément dimensions ni implémentation.

Libellés : « Sur vous », « En banque », « Dans votre commerce » ; « Acheter au marchand », « Vendre au marchand » ; « Vous payez », « Le vendeur reçoit », « Taxe versée à… ». Un gain cumulé n’est pas nommé solde disponible. Une dette n’est pas une caisse négative.

## Parcours

Banque : montant → aperçu des pièces/poche → confirmation → état du reçu. Commerce : prix unitaire/quantité/stock → total et recette nette → résultat. Administration : rechercher un reçu → comprendre ses étapes → aperçu de compensation → motif → confirmer. Éviter toute gestion technique obligatoire dans les parcours joueurs.

Chargement : action désactivée tant qu’elle est en cours ; reçu consultable après fermeture. Erreur réseau : « Résultat à vérifier » si l’opération a pu être exécutée, pas « Paiement échoué » par supposition. Cache périmé : date visible et action limitée selon règle ; ne pas remplacer un montant indisponible par zéro.

Animations : entrée panneau 180–240 ms, sélection 120–180 ms, mouvement caméra 250–450 ms ; aucune animation bloquante avant confirmation d’une action. Respect de la réduction des mouvements sur le web et option équivalente jeu à prévoir. Aucun clignotement, défilement permanent de montants ou effet masquant un changement de solde.

Recette : petits/grands écrans, clavier, focus restauré après fermeture, descriptions de boutons icônes, zoom navigateur, GUI Minecraft réduite/agrandie, grandes valeurs et traductions longues. Pagination/recherche pour les historiques, pas de liste illimitée en un seul chargement.

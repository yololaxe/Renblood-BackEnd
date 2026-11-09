# Charte appliquée aux interfaces économiques

L’identité existante du guide est conservée : pierre presque noire, titres clairs, or réservé aux repères et aux actions. Sur le web, compositions larges, lignes de registre et séparation liste/détail remplacent l’empilement de cartes. La navigation principale reste unique. Dans Minecraft, police native et emplacements usuels des inventaires sont conservés ; l’échelle réduit ensemble dessin, boutons, slots et coordonnées de souris.

| Sens | Libellé et comportement |
|---|---|
| Confirmé | Vert doux + texte. Seul un reçu confirmé alimente les recettes disponibles. |
| En attente | Or + texte. Validation verrouillée ; après 20 secondes, inviter à vérifier le reçu. Aucun délai ne libère automatiquement l’argent d’une remise ambiguë. |
| À vérifier / refus | Rouge doux + raison. Référence conservée et accessible à l’intendance. |
| Inconnu | Tiret ou message explicite, jamais un faux zéro. Un relevé ancien ne garantit pas la possibilité de payer. |
| Budget épuisé / établissement fermé | Motif distinct. La présence d’un stock ne garantit pas le financement du rachat. |

Le disponible, les fonds réservés et les entrées attendues sont trois valeurs distinctes. Les espaces physiques restent consultables en jeu ; le site ne prétend pas connaître en permanence le contenu d’un inventaire hors ligne. Les grandes sommes restent en entiers exacts, y compris dans les aperçus.

Le web utilise des fondus courts et un déplacement d’ouverture de six pixels au maximum ; la préférence de réduction des mouvements retire le déplacement. Focus visibles, commandes HTML natives et cibles de 44 pixels facilitent l’utilisation au clavier et au doigt. En téléphone, sélectionner un reçu amène au détail et y place le focus. Aucun défilement animé forcé. Les longues références peuvent revenir à la ligne.

Les mods affichent une révélation de progression bornée à 250 ms pendant l’attente ; pas d’animation perpétuelle. L’option Minecraft de réduction des effets supprime cette progression. Un état de disponibilité vieux de trente secondes est présenté comme ancien. Aucun cache visuel ne décide d’un débit.

L’adaptation mathématique des écrans couvre les tailles testées de 320 × 240 à 1920 × 1080. Elle ne remplace pas une observation en jeu aux différentes échelles de GUI, notamment pour les infobulles, objets glissés et interactions tactiles éventuelles.

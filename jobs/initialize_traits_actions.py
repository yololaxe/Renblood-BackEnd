import json
from jobs.models import Trait, Action

traits_data = {
    1: {"trait_id": 1, "Name": "Etudiant", "Bonus": {"skill": 2, "rethoric": 2}},
    2: {"trait_id": 2, "Name": "Iwwyn", "Bonus": {"mana": 20, "charisma": 1}},
    3: {"trait_id": 3, "Name": "Garde", "Bonus": {"resistance": 1, "strength": 1}},
    4: {"trait_id": 4, "Name": "Sang bleu", "Bonus": {"influence": 1, "life": 2}},
    5: {"trait_id": 5, "Name": "Cuisinier", "Bonus": {"life": 1, "regeneration": 1}},
    6: {"trait_id": 6, "Name": "Travailleur", "Bonus": {"skill": 2, "strength": 1}},
    7: {"trait_id": 7, "Name": "Voleur", "Bonus": {"speed": 1, "influence": -1, "discretion": 2}},
    8: {"trait_id": 8, "Name": "Vagabon", "Bonus": {"speed": 1, "dodge": 1}},
    9: {"trait_id": 9, "Name": "Lâche", "Bonus": {"reputation": -3, "charisma": -1}},
    10: {"trait_id": 10, "Name": "Guilde des créatures", "Bonus": {"life": 1, "skill": 4}},
    11: {"trait_id": 11, "Name": "Extravertie", "Bonus": {"charisma": 1, "influence": 1}},
    12: {"trait_id": 12, "Name": "Guilde maritime", "Bonus": {"mana": 20, "skill": 2}},
    13: {"trait_id": 13, "Name": "Fermier", "Bonus": {"resistance": 1, "regeneration": 1}},
    14: {"trait_id": 14, "Name": "Alcoolique", "Bonus": {"life": 1, "influence": -1}},
    15: {"trait_id": 15, "Name": "AutoEntrepreneur", "Bonus": {"skill": 2, "influence": 1, "reputation": 4}},
    16: {"trait_id": 16, "Name": "Tolard", "Bonus": {"strength": 1, "resistance": 1}},
    17: {"trait_id": 17, "Name": "Aspirante", "Bonus": {"mana": 10}},
    18: {"trait_id": 18, "Name": "Diligent", "Bonus": {"skill": 2, "speed": 2, "discretion": -2}}
}

actions_data = {
    1: {"action_id": 1, "Name": "Analyse des créatures", "Description": "Aucune", "Mana": 0, "Chance": 100},
    2: {"action_id": 2, "Name": "Contrôle mental des créatures", "Description": "Aucune", "Mana": 60, "Chance": 75},
    3: {"action_id": 3, "Name": "Arnaquer", "Description": "Manipuler quelqu'un pour un gain", "Mana": 0, "Chance": 80},
    4: {"action_id": 4, "Name": "Embobiner quelqu'un", "Description": "Convaincre par la ruse", "Mana": 0, "Chance": 85},
    5: {"action_id": 5, "Name": "Se plaindre", "Description": "Exiger du changement", "Mana": 0, "Chance": 90},
    6: {"action_id": 6, "Name": "Développer une industrie", "Description": "Accroître un commerce", "Mana": 0, "Chance": 75},
    7: {"action_id": 7, "Name": "Discuter technique", "Description": "Parler de sujets pointus", "Mana": 0, "Chance": 95},
    8: {"action_id": 8, "Name": "Enchanter un meuble", "Description": "Infuser une magie", "Mana": 110, "Chance": 25},
    9: {"action_id": 9, "Name": "Déclarer un duel", "Description": "Provoquer un adversaire", "Mana": 0, "Chance": 50},
    10: {"action_id": 10, "Name": "Se faire respecter", "Description": "Imposer son autorité", "Mana": 0, "Chance": 85},
    11: {"action_id": 11, "Name": "Renforcer un objet", "Description": "Améliorer sa durabilité", "Mana": 80, "Chance": 35},
    12: {"action_id": 12, "Name": "Faire léviter des objets", "Description": "Utiliser la télékinésie", "Mana": 20, "Chance": 90},
    13: {"action_id": 13, "Name": "Chanter magistralement", "Description": "Donner une performance vocale", "Mana": 0, "Chance": 85},
    14: {"action_id": 14, "Name": "Enchanter du bois", "Description": "Améliorer les objets en bois", "Mana": 75, "Chance": 60},
    15: {"action_id": 15, "Name": "Charmer quelqu'un", "Description": "Séduire et influencer", "Mana": 110, "Chance": 75},
    16: {"action_id": 16, "Name": "Manipuler l'esprit", "Description": "Altérer la perception", "Mana": 35, "Chance": 35},
    17: {"action_id": 17, "Name": "Protéger un bâtiment", "Description": "Créer un champ magique", "Mana": 100, "Chance": 10},
    18: {"action_id": 18, "Name": "Invoquer un élément du monde miroir", "Description": "Appeler une entité", "Mana": 180, "Chance": 5},
    19: {"action_id": 19, "Name": "Connaissance culinaire", "Description": "Maîtriser les recettes", "Mana": 0, "Chance": 100},
    20: {"action_id": 20, "Name": "Danser professionnellement", "Description": "Performance artistique", "Mana": 0, "Chance": 90},
    21: {"action_id": 21, "Name": "Festoyer", "Description": "Faire la fête avec énergie", "Mana": 0, "Chance": 95},
    22: {"action_id": 22, "Name": "Manipuler l'eau", "Description": "Contrôler les liquaction_ides", "Mana": 100, "Chance": 50},
    23: {"action_id": 23, "Name": "Démonstration de force", "Description": "Impressionner par sa puissance", "Mana": 0, "Chance": 80},
    24: {"action_id": 24, "Name": "Enchanter une pierre", "Description": "Imprégner un caillou de magie", "Mana": 110, "Chance": 25},
    25: {"action_id": 25, "Name": "Enchanter la nourriture", "Description": "Rendre les aliments magiques", "Mana": 75, "Chance": 60},
    26: {"action_id": 26, "Name": "Jouer d'un instrument", "Description": "Performance musicale", "Mana": 0, "Chance": 85}
}

for trait in traits_data.values():
    Trait.objects.get_or_create(trait_id=trait["trait_id"], name=trait["Name"], bonus=trait["Bonus"])

for action in actions_data.values():
    Action.objects.get_or_create(
        action_id=action["action_id"],
        name=action["Name"],
        description=action["Description"],
        mana=action["Mana"],
        chance=action["Chance"]
    )

print("✅ Données initiales insérées avec succès !")
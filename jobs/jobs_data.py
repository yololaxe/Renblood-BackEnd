from jobs.models import Job
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RenbloodBackEnd.settings")
django.setup()

jobs_data = [
    {
        "_id": "lumberjack",
        "name": "Lumberjack",
        "skills": {
            "choice_1": [
                {"id": "lumberjack_1_1", "name": "6% haste"},
                {"id": "lumberjack_1_2", "name": "6% haste"},
                {"id": "lumberjack_1_3", "name": "6% haste"}
            ],
            "choice_2": [
                {"id": "lumberjack_2_1", "name": "License purchase"},
                {"id": "lumberjack_2_2", "name": "0.5 Strength"},
                {"id": "lumberjack_2_3", "name": "/jump-boost"}
            ],
            "choice_3": [
                {"id": "lumberjack_3_1", "name": "0.5 Strength", "prerequisite": []},
                {"id": "lumberjack_3_2", "name": "6% haste", "prerequisite": []},
                {"id": "lumberjack_3_3", "name": "18% speed", "prerequisite": ["lumberjack_3_1"]}
            ]
        },
        "mastery": ["/fertilized", "/firecamp", "/unbark"]
    },
    {
        "_id": "naval_architect",
        "name": "Naval Architect",
        "skills": {
            "choice_1": [
                {"id": "naval_architect_1_1", "name": "Rowboat"},
                {"id": "naval_architect_1_2", "name": "Dhow"},
                {"id": "naval_architect_1_3", "name": "Brigg"}
            ],
            "choice_2": [
                {"id": "naval_architect_2_1", "name": "Cog"},
                {"id": "naval_architect_2_2", "name": "Drakkar"},
                {"id": "naval_architect_2_3", "name": "5% master guild skill"}
            ],
            "choice_3": [
                {"id": "naval_architect_3_1", "name": "Galley"},
                {"id": "naval_architect_3_2", "name": "War Galley"},
                {"id": "naval_architect_3_3", "name": "-20% travel time on ships"}
            ]
        },
        "mastery": ["???"]
    },
    {
        "_id": "miner",
        "name": "Miner",
        "skills": {
            "choice_1": [
                {"id": "miner_1_1", "name": "6% haste"},
                {"id": "miner_1_2", "name": "6% haste"},
                {"id": "miner_1_3", "name": "/torch"}
            ],
            "choice_2": [
                {"id": "miner_2_1", "name": "License creation"},
                {"id": "miner_2_2", "name": "Hire workers"},
                {"id": "miner_2_3", "name": "10% speed"}
            ],
            "choice_3": [
                {"id": "miner_3_1", "name": "5% speed", "prerequisite": []},
                {"id": "miner_3_2", "name": "6% haste", "prerequisite": []},
                {"id": "miner_3_3", "name": "18% speed", "prerequisite": ["miner_3_1"]}
            ]
        },
        "mastery": ["Guild master of miners"]
    },
    {
        "_id": "blacksmith",
        "name": "Blacksmith",
        "skills": {
            "choice_1": [
                {"id": "blacksmith_1_1", "name": "Weaponsmith"},
                {"id": "blacksmith_1_2", "name": "Armorsmith"},
                {"id": "blacksmith_1_3", "name": "Goldsmith"}
            ],
            "choice_2": [
                {"id": "blacksmith_2_1", "name": "Repair Kit"},
                {"id": "blacksmith_2_2", "name": "Advanced Sand"},
                {"id": "blacksmith_2_3", "name": "Gold Cast"}
            ],
            "choice_3": [
                {"id": "blacksmith_3_1", "name": "1 Negotiation"},
                {"id": "blacksmith_3_2", "name": "1 Negotiation"},
                {"id": "blacksmith_3_3", "name": "1 Influence"}
            ]
        },
        "mastery": ["Guild master of blacksmiths", "Nether ore mastery"]
    },
    {
        "_id": "glassmaker",
        "name": "Glassmaker",
        "skills": {
            "choice_1": [
                {"id": "glassmaker_1_1", "name": "10 Mana"},
                {"id": "glassmaker_1_2", "name": "5% speed"},
                {"id": "glassmaker_1_3", "name": "5% speed"}
            ],
            "choice_2": [
                {"id": "glassmaker_2_1", "name": "Glass Panes"},
                {"id": "glassmaker_2_2", "name": "Silk-Touch Hand"},
                {"id": "glassmaker_2_3", "name": "Glass Stuff"}
            ],
            "choice_3": [
                {"id": "glassmaker_3_1", "name": "1 HP"},
                {"id": "glassmaker_3_2", "name": "1 Discretion"},
                {"id": "glassmaker_3_3", "name": "/vanish"}
            ]
        },
        "mastery": ["Glass crafting & life mastery"]
    },
    {
        "_id": "mason",
        "name": "Mason",
        "skills": {
            "choice_1": [
                {"id": "mason_1_1", "name": "Smeltery"},
                {"id": "mason_1_2", "name": "Stone Utilities"},
                {"id": "mason_1_3", "name": "0.5 Strength"}
            ],
            "choice_2": [
                {"id": "mason_2_1", "name": "1 Place"},
                {"id": "mason_2_2", "name": "1 Place"},
                {"id": "mason_2_3", "name": "0.5 Resistance"}
            ],
            "choice_3": [
                {"id": "mason_3_1", "name": "1 Place"},
                {"id": "mason_3_2", "name": "0.5 Strength"},
                {"id": "mason_3_3", "name": "0.5 Resistance"}
            ]
        },
        "mastery": ["???"]
    },
    {
        "_id": "farmer",
        "name": "Farmer",
        "skills": {
            "choice_1": [
                {"id": "farmer_1_1", "name": "Apiculture"},
                {"id": "farmer_1_2", "name": "1 HP"},
                {"id": "farmer_1_3", "name": "2 HP"}
            ],
            "choice_2": [
                {"id": "farmer_2_1", "name": "Compost"},
                {"id": "farmer_2_2", "name": "1 HP"},
                {"id": "farmer_2_3", "name": "0.5 Resistance"}
            ],
            "choice_3": [
                {"id": "farmer_3_1", "name": "Fortune Hoe"},
                {"id": "farmer_3_2", "name": "0.5 Resistance"},
                {"id": "farmer_3_3", "name": "Fertilized Soil"}
            ]
        },
        "mastery": ["???"]
    },
    {
        "_id": "breeder",
        "name": "Breeder",
        "skills": {
            "choice_1": [
                {"id": "breeder_1_1", "name": "4 Animals in pens"},
                {"id": "breeder_1_2", "name": "4 Animals in pens"},
                {"id": "breeder_1_3", "name": "1 Regeneration"}
            ],
            "choice_2": [
                {"id": "breeder_2_1", "name": "Weaver"},
                {"id": "breeder_2_2", "name": "2 HP"},
                {"id": "breeder_2_3", "name": "2 HP"}
            ],
            "choice_3": [
                {"id": "breeder_3_1", "name": "Backpack"},
                {"id": "breeder_3_2", "name": "Leather Stuff"},
                {"id": "breeder_3_3", "name": "Backpack Upgrade"}
            ]
        },
        "mastery": ["Mythical Animals"]
    },
    {
        "_id": "fisherman",
        "name": "Fisherman",
        "skills": {
            "choice_1": [
                {"id": "fisherman_1_1", "name": "5 Mana"},
                {"id": "fisherman_1_2", "name": "5 Mana"},
                {"id": "fisherman_1_3", "name": "5 Mana"}
            ],
            "choice_2": [
                {"id": "fisherman_2_1", "name": "Participate in Fishing Contest"},
                {"id": "fisherman_2_2", "name": "National Contest"},
                {"id": "fisherman_2_3", "name": "10 Mana"}
            ],
            "choice_3": [
                {"id": "fisherman_3_1", "name": "Receive RSA"},
                {"id": "fisherman_3_2", "name": "Receive Allowances"},
                {"id": "fisherman_3_3", "name": "1 Regeneration"}
            ]
        },
        "mastery": ["I am Jesus"]
    },
    {
        "_id": "innkeeper",
        "name": "Innkeeper",
        "skills": {
            "choice_1": [
                {"id": "innkeeper_1_1", "name": "Baker (Boulanger)"},
                {"id": "innkeeper_1_2", "name": "1 Dodge"},
                {"id": "innkeeper_1_3", "name": "2 HP"}
            ],
            "choice_2": [
                {"id": "innkeeper_2_1", "name": "Restaurateur"},
                {"id": "innkeeper_2_2", "name": "1 Negotiation"},
                {"id": "innkeeper_2_3", "name": "1 Regeneration"}
            ],
            "choice_3": [
                {"id": "innkeeper_3_1", "name": "Organize a Feast"},
                {"id": "innkeeper_3_2", "name": "3 Place"},
                {"id": "innkeeper_3_3", "name": "1 Regeneration"}
            ]
        },
        "mastery": ["Guild Master of the Table", "Black Market Commerce"]
    }
]

for job in jobs_data:
    Job.objects.update_or_create(_id=job["_id"], defaults=job)

print("Jobs insérés avec succès !")

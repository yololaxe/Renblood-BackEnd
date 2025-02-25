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
                {"id": "lumberjack_3_1", "name": "0.5 Strength"},
                {"id": "lumberjack_3_2", "name": "6% haste"},
                {"id": "lumberjack_3_3", "name": "18% speed"}
            ]
        },
        "inter_choice": [],
        "mastery": ["/fertilized", "/firecamp", "/unbark"]
    },
    {
        "_id": "naval_architect",
        "name": "Naval Architect",
        "skills": {
            "choice_1": [
                {"id": "naval_architect_1_1", "name": "recipe-Rowboat"},
                {"id": "naval_architect_1_2", "name": "recipe-Dhow"},
                {"id": "naval_architect_1_3", "name": "recipe-Brigg"}
            ],
            "choice_2": [
                {"id": "naval_architect_2_1", "name": "recipe-Cog"},
                {"id": "naval_architect_2_2", "name": "recipe-Drakkar"},
                {"id": "naval_architect_2_3", "name": "5% master guild skill"}
            ],
            "choice_3": [
                {"id": "naval_architect_3_1", "name": "recipe-Galley"},
                {"id": "naval_architect_3_2", "name": "recipe-War-Galley"},
                {"id": "naval_architect_3_3", "name": "-20% travel time on ships"}
            ]
        },
        "inter_choice": [],
        "mastery": ["???"]
    },
    {
        "_id": "artisan",
        "name": "Artisan",
        "skills": {
        "choice_1": [
            { "id": "artisan_1_1", "name": "recipe-Furnitures" },
            { "id": "artisan_1_2", "name": "recipe-Advanced-Furnitures" },
            { "id": "artisan_1_3", "name": "1 Influence" }
        ],
        "choice_2": [
            { "id": "artisan_2_1", "name": "recipe-Kitchen" },
            { "id": "artisan_2_2", "name": "recipe-Advanced Kitchen" },
            { "id": "artisan_2_3", "name": "5% Competence" }
        ],
        "choice_3": [
            { "id": "artisan_3_1", "name": "recipe-Wooden Utilities" },
            { "id": "artisan_3_2", "name": "recipe-Storage" },
            { "id": "artisan_3_3", "name": "1 Negotiation" }
        ]
        },
        "inter_choice": [],
        "mastery": ["Naval + Pretend to be the master guild of artisans"]
    },
    {
        "_id": "carpenter",
        "name": "Carpenter",
        "skills": {
        "choice_1": [
            { "id": "carpenter_1_1", "name": "recipe-Roof" },
            { "id": "carpenter_1_2", "name": "recipe-Advanced Roof" },
            { "id": "carpenter_1_3", "name": "/magnet" }
        ],
        "choice_2": [
            { "id": "carpenter_2_1", "name": "recipe-Scaffolding" },
            { "id": "carpenter_2_2", "name": "1 Dodge" },
            { "id": "carpenter_2_3", "name": "/jump-boost" }
        ],
        "choice_3": [
            { "id": "carpenter_3_1", "name": "1 Place" },
            { "id": "carpenter_3_2", "name": "1 Place" },
            { "id": "carpenter_3_3", "name": "1 Place" }
        ]
        },
        "inter_choice": [],
        "mastery": ["/nofall"]
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
        "inter_choice": [],
        "mastery": ["Guild master of miners"]
    },
    {
        "_id": "blacksmith",
        "name": "Blacksmith",
        "skills": {
            "choice_1": [
                {"id": "blacksmith_1_1", "name": "recipe-Weaponsmith"},
                {"id": "blacksmith_1_2", "name": "recipe-Armorsmith"},
                {"id": "blacksmith_1_3", "name": "recipe-Goldsmith"}
            ],
            "choice_2": [
                {"id": "blacksmith_2_1", "name": "recipe-Repair-Kit"},
                {"id": "blacksmith_2_2", "name": "recipe-Advanced-Sand-Cast"},
                {"id": "blacksmith_2_3", "name": "recipe-Gold-Cast"}
            ],
            "choice_3": [
                {"id": "blacksmith_3_1", "name": "1 Negotiation"},
                {"id": "blacksmith_3_2", "name": "1 Negotiation"},
                {"id": "blacksmith_3_3", "name": "1 Influence"}
            ]
        },
        "inter_choice": [],
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
                {"id": "glassmaker_2_1", "name": "recipe-Glass-Panes"},
                {"id": "glassmaker_2_2", "name": "Silk-Touch Hand"},
                {"id": "glassmaker_2_3", "name": "recipe-Glass-Stuff"}
            ],
            "choice_3": [
                {"id": "glassmaker_3_1", "name": "1 HP"},
                {"id": "glassmaker_3_2", "name": "1 Discretion"},
                {"id": "glassmaker_3_3", "name": "/vanish"}
            ]
        },
        "inter_choice": [],
        "mastery": ["Glass crafting & life mastery"]
    },
    {
        "_id": "mason",
        "name": "Mason",
        "skills": {
            "choice_1": [
                {"id": "mason_1_1", "name": "recipe-Smeltery"},
                {"id": "mason_1_2", "name": "recipe-Stone-Utilities"},
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
        "inter_choice": [],
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
                {"id": "farmer_2_1", "name": "recipe-Compost"},
                {"id": "farmer_2_2", "name": "1 HP"},
                {"id": "farmer_2_3", "name": "0.5 Resistance"}
            ],
            "choice_3": [
                {"id": "farmer_3_1", "name": "Fortune Hoe"},
                {"id": "farmer_3_2", "name": "0.5 Resistance"},
                {"id": "farmer_3_3", "name": "recipe-Fertilized-Soil"}
            ]
        },
        "inter_choice": [],
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
                {"id": "breeder_2_1", "name": "recipe-Weaver"},
                {"id": "breeder_2_2", "name": "2 HP"},
                {"id": "breeder_2_3", "name": "2 HP"}
            ],
            "choice_3": [
                {"id": "breeder_3_1", "name": "recipe-Backpack"},
                {"id": "breeder_3_2", "name": "Leather Stuff"},
                {"id": "breeder_3_3", "name": "Backpack Upgrade"}
            ]
        },
        "inter_choice": [],
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
        "inter_choice": [],
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
        "inter_choice": [],
        "mastery": ["Guild Master of the Table", "Black Market Commerce"]
    },
    
    {
        "_id": "guard",
        "name": "Guard",
        "skills": {
        "choice_1": [
            { "id": "guard_1_1", "name": "Public Access" },
            { "id": "guard_1_2", "name": "0.5 Resistance" },
            { "id": "guard_1_3", "name": "0.5 Resistance" }
        ],
        "choice_2": [
            { "id": "guard_2_1", "name": "Engage in battle" },
            { "id": "guard_2_2", "name": "1 Strength" },
            { "id": "guard_2_3", "name": "1 Strength" }
        ],
        "choice_3": [
            { "id": "guard_3_1", "name": "Engage in war" },
            { "id": "guard_3_2", "name": "1 Strength" },
            { "id": "guard_3_3", "name": "???" }
        ]
        },
        "inter_choice": [],
        "mastery": ["Public/Mercenary/Soldier/Guardian"]
    },
    {
        "_id": "merchant",
        "name": "Merchant",
        "skills": {
        "choice_1": [
            { "id": "merchant_1_1", "name": "Itinerant Access" },
            { "id": "merchant_1_2", "name": "1 Charisma" },
            { "id": "merchant_1_3", "name": "1 Charisma" }
        ],
        "choice_2": [
            { "id": "merchant_2_1", "name": "Market Access" },
            { "id": "merchant_2_2", "name": "1 Rhetoric" },
            { "id": "merchant_2_3", "name": "1 Rhetoric" }
        ],
        "choice_3": [
            { "id": "merchant_3_1", "name": "Armor License" },
            { "id": "merchant_3_2", "name": "Weapon License" },
            { "id": "merchant_3_3", "name": "Alcohol License" }
        ]
        },
        "inter_choice": [],
        "mastery": ["Black Market", "Inter-County Trade", "Guild Management"]
    },
    {
        "_id": "transporter",
        "name": "Transporter",
        "skills": {
        "choice_1": [
            { "id": "transporter_1_1", "name": "Public Access" },
            { "id": "transporter_1_2", "name": "5% Speed" },
            { "id": "transporter_1_3", "name": "10% Speed" }
        ],
        "choice_2": [
            { "id": "transporter_2_1", "name": "Route Creation" },
            { "id": "transporter_2_2", "name": "1 Place" },
            { "id": "transporter_2_3", "name": "1 Place" }
        ],
        "choice_3": [
            { "id": "transporter_3_1", "name": "5% Speed" },
            { "id": "transporter_3_2", "name": "5% Speed" },
            { "id": "transporter_3_3", "name": "1 Place" }
        ]
        },
        "inter_choice": [],
        "mastery": ["Postal Center", "10% Cost Reduction on All Transport"]
    },
    {
        "_id": "explorer",
        "name": "Explorer",
        "skills": {
        "choice_1": [
            { "id": "explorer_1_1", "name": "1h Exploration" },
            { "id": "explorer_1_2", "name": "2h Exploration" },
            { "id": "explorer_1_3", "name": "1 Place" }
        ],
        "choice_2": [
            { "id": "explorer_2_1", "name": "-10% Travel Cost" },
            { "id": "explorer_2_2", "name": "-10% Travel Cost" },
            { "id": "explorer_2_3", "name": "1 Place" }
        ],
        "choice_3": [
            { "id": "explorer_3_1", "name": "Beds available at Lodestone" },
            { "id": "explorer_3_2", "name": "1 Place" },
            { "id": "explorer_3_3", "name": "Artifact Boots" }
        ]
        },
        "inter_choice": [],
        "mastery": ["Exploration Bonuses", "2 Free Auto Chests"]
    },
    
    {
        "_id": "bestiary",
        "name": "Bestiary",
        "skills": {
        "choice_1": [
            { "id": "bestiary_1_1", "name": "3 Health" },
            { "id": "bestiary_1_2", "name": "3 Health" },
            { "id": "bestiary_1_3", "name": "1 Regeneration" },
        ],
        "choice_2": [
            { "id": "bestiary_2_1", "name": "1 Dodge" },
            { "id": "bestiary_2_2", "name": "1 Resistance" },
            { "id": "bestiary_2_3", "name": "1 Strength" },
        ],
        "choice_3": [
            { "id": "bestiary_3_1", "name": "Dogs"},
            { "id": "bestiary_3_2", "name": "Dogs - Training 1+2" },
            { "id": "bestiary_3_3", "name": "Dogs - Training 3+4" },
        ],
        "choice_4": [
            { "id": "bestiary_4_1", "name": "Horses" },
            { "id": "bestiary_4_2", "name": "Hippogriff" },
            { "id": "bestiary_4_3", "name": "Unicorns" },
        ]
        },
        "inter_choice": ["Dragons","Guild Master of Creatures"],
        "mastery": [""]
    },
    {
        "_id": "banker",
        "name": "Banker",
        "skills": {
        "choice_1": [
            { "id": "banker_1_1", "name": "10% Speed" },
            { "id": "banker_1_2", "name": "1 Dodge" },
            { "id": "banker_1_3", "name": "1 Discretion" },
        ],
        "choice_2": [
            { "id": "banker_2_1", "name": "1 Charisma" },
            { "id": "banker_2_2", "name": "1 Rhetoric" },
            { "id": "banker_2_3", "name": "1 Influence" },

        ],
        "choice_3": [
            { "id": "banker_3_1", "name": "Book Negotiation" },
            { "id": "banker_3_2", "name": "1 Negotiation" },
            { "id": "banker_3_3", "name": "1 Negotiation" },
        ],
        "choice_4": [
            { "id": "banker_4_1", "name": "Bank Loan" },
            { "id": "banker_4_2", "name": "Insurance" },
            { "id": "banker_4_3", "name": "Notary" },
        ]
        },
        "inter_choice": ["???", "Guild Master of the Letter"],
        "mastery": ["???"]
    },
    {
        "_id": "politician",
        "name": "Politician",
        "skills": {
        "choice_1": [
            { "id": "politician_1_1", "name": "1 Charisma" },
            { "id": "politician_1_2", "name": "1 Rhetoric" },
            { "id": "politician_1_3", "name": "1 Influence" },
        ],
        "choice_2": [
            { "id": "politician_2_1", "name": "1 Charisma" },
            { "id": "politician_2_2", "name": "1 Rhetoric" },
            { "id": "politician_2_3", "name": "1 Influence" },
        ],
        "choice_3": [
            { "id": "politician_3_1", "name": "2 Health" },
            { "id": "politician_3_2", "name": "10% Speed" },
            { "id": "politician_3_3", "name": "15 Mana" },
            { "id": "politician_3_4", "name": "Start a Revolution" }
        ],
        "choice_4": [
            { "id": "politician_4_1", "name": "Start a Manifestation" },
            { "id": "politician_4_2", "name": "Change the Heritage System" },
            { "id": "politician_4_3", "name": "Notary" },
        ]
        },
        "inter_choice": [
        "3 Negotiation",
        "Change the Political System"
        ],
        "mastery": ["Launch a revolution"]
    },
    {
        "_id": "builder",
        "name": "Builder",
        "skills": {
        "choice_1": [
            { "id": "builder_1_1", "name": "10% Speed" },
            { "id": "builder_1_2", "name": "1 Discretion" },
            { "id": "builder_1_3", "name": "1 Negotiation" },
        ],
        "choice_2": [
            { "id": "builder_2_1", "name": "2 Health" },
            { "id": "builder_2_2", "name": "1 Reach" },
            { "id": "builder_2_3", "name": "3 Places" },
        ],
        "choice_3": [
            { "id": "builder_3_1", "name": "Public Access" },
            { "id": "builder_3_2", "name": "Schema Access" },
            { "id": "builder_3_3", "name": "1 Reach" },
        ],
        "choice_4": [
            { "id": "builder_4_1", "name": "20+ Blocks" },
            { "id": "builder_4_2", "name": "50+ Blocks" },
            { "id": "builder_4_3", "name": "80+ Blocks" },
        ]
        },
        "inter_choice": [
        "5% Competence",
        "???"
        ],
        "mastery": ["Mirror World Access"]
    }

]

for job in jobs_data:
    Job.objects.update_or_create(_id=job["_id"], defaults=job)

print("Jobs insérés avec succès !")

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
    }
]

for job in jobs_data:
    Job.objects.update_or_create(_id=job["_id"], defaults=job)

print("Jobs insérés avec succès !")

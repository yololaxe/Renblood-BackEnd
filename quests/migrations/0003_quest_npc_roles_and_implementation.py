from django.db import migrations, models
from djongo import models as djongo_models


def migrate_quest_npc_links(apps, schema_editor):
    Quest = apps.get_model("quests", "Quest")
    Npc = apps.get_model("npcs", "Npc")
    npcs = list(Npc.objects.all())

    for quest in Quest.objects.all():
        start_npc_id = quest.npcId or quest.npc
        completion_npc_id = None

        for npc in npcs:
            if quest.questId not in (npc.quest_ids or []):
                continue
            if not start_npc_id and npc.quest_giver:
                start_npc_id = npc.npc_id
            if not completion_npc_id and npc.quest_validator:
                completion_npc_id = npc.npc_id

        objectives = []
        for objective in quest.objectives or []:
            if not isinstance(objective, dict):
                objectives.append(objective)
                continue
            objective = dict(objective)
            npc_id = objective.pop("npcId", None) or objective.pop("npc_id", None)
            target = objective.get("target")
            if not isinstance(target, dict):
                target = {}
            if npc_id and not target.get("npcId"):
                target["npcId"] = npc_id
            objective["target"] = target
            objectives.append(objective)

        quest.startNpcId = start_npc_id
        quest.completionNpcId = completion_npc_id
        quest.objectives = objectives
        quest.save(update_fields=["startNpcId", "completionNpcId", "objectives"])


class Migration(migrations.Migration):

    dependencies = [
        ("npcs", "0004_npc_implementation"),
        ("quests", "0002_quest_npc_id_and_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="quest",
            name="startNpcId",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="quest",
            name="completionNpcId",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="quest",
            name="implementation",
            field=djongo_models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(migrate_quest_npc_links, migrations.RunPython.noop),
    ]

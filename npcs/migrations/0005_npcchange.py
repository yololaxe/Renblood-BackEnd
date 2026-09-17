from django.db import migrations, models
import djongo.models.fields


class Migration(migrations.Migration):
    dependencies = [("npcs", "0004_npc_implementation")]

    operations = [
        migrations.CreateModel(
            name="NpcChange",
            fields=[
                (
                    "revision",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "entity_type",
                    models.CharField(
                        choices=[("NPC", "NPC"), ("SPAWN", "SPAWN")],
                        max_length=16,
                    ),
                ),
                ("entity_id", models.CharField(max_length=255)),
                (
                    "action",
                    models.CharField(
                        choices=[("UPSERT", "UPSERT"), ("DELETE", "DELETE")],
                        max_length=16,
                    ),
                ),
                (
                    "payload",
                    djongo.models.fields.JSONField(blank=True, default=dict),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "npc_changes", "ordering": ["revision"]},
        ),
    ]
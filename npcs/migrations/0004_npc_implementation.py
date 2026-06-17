from django.db import migrations
from djongo import models


class Migration(migrations.Migration):

    dependencies = [
        ("npcs", "0003_npc_region"),
    ]

    operations = [
        migrations.AddField(
            model_name="npc",
            name="implementation",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

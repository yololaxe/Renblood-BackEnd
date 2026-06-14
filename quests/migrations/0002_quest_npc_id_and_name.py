from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quests", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="quest",
            name="npcId",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="quest",
            name="npcName",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

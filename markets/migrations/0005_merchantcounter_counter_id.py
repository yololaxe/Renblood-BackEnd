import uuid

from django.db import migrations, models

import markets.models


def populate_counter_ids(apps, schema_editor):
    MerchantCounter = apps.get_model("markets", "MerchantCounter")
    for counter in MerchantCounter.objects.filter(counter_id__isnull=True):
        counter.counter_id = str(uuid.uuid4())
        counter.save(update_fields=["counter_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("markets", "0004_marketcategory"),
    ]

    operations = [
        migrations.AddField(
            model_name="merchantcounter",
            name="counter_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(populate_counter_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="merchantcounter",
            name="counter_id",
            field=models.CharField(default=markets.models.new_id, max_length=255, unique=True),
        ),
    ]

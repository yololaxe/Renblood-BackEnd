from django.db import migrations, models
import django.core.validators
class Migration(migrations.Migration):
    dependencies=[('markets','0007_market_moderation_and_dynamic_economy')]
    operations=[
        migrations.AddField(model_name='markettransaction',name='operation_id',field=models.CharField(max_length=36,null=True,blank=True)),
        migrations.AddField(model_name='markettransaction',name='price_version',field=models.CharField(max_length=160,null=True,blank=True)),
        migrations.AddField(model_name='markettransaction',name='rule_version',field=models.CharField(max_length=160,null=True,blank=True)),
        migrations.AddField(model_name='markettransaction',name='tax',field=models.BigIntegerField(default=0,validators=[django.core.validators.MinValueValidator(0)])),
    ]

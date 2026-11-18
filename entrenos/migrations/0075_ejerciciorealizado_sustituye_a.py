from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("entrenos", "0074_senales_al_decidir"),
    ]

    operations = [
        migrations.AddField(
            model_name="ejerciciorealizado",
            name="sustituye_a",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]

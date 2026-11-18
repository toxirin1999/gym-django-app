from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("entrenos", "0075_ejerciciorealizado_sustituye_a"),
    ]

    operations = [
        migrations.AddField(
            model_name="ejerciciorealizado",
            name="objetivo_asignado",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

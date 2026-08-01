from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diario", "0026_interaccion_origen_sombra"),
    ]

    operations = [
        migrations.AddField(
            model_name="personaimportante",
            name="archivada",
            field=models.BooleanField(
                default=False,
                help_text="Conserva el vínculo y su historial fuera del círculo activo.",
            ),
        ),
    ]

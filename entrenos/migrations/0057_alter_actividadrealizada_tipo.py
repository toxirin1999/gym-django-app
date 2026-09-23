from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("entrenos", "0056_sesionmovilidadadaptativa")]

    operations = [
        migrations.AlterField(
            model_name="actividadrealizada",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("gym", "Gimnasio / Fuerza"), ("hyrox", "Sesión Hyrox"),
                    ("carrera", "Carrera / Running"), ("ciclismo", "Ciclismo"),
                    ("remo", "Remo / Ergómetro"), ("futbol", "Fútbol"),
                    ("natacion", "Natación"), ("yoga", "Yoga / Movilidad"),
                    ("movilidad", "Movilidad"),
                    ("estiramientos", "Estiramientos"), ("otro", "Otra Actividad"),
                ],
                default="gym", max_length=20,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('diario', '0028_alter_personaimportante_salud_relacion')]

    operations = [
        migrations.AlterField(
            model_name='personainterina',
            name='estado',
            field=models.CharField(
                choices=[
                    ('sombra', 'En la Sombra'),
                    ('radar', 'En el Radar de JOI'),
                    ('promovida', 'Promovida a Simbiosis'),
                    ('descartada', 'Descartada'),
                    ('no_persona', 'No es una persona'),
                ],
                default='sombra',
                max_length=12,
            ),
        ),
    ]

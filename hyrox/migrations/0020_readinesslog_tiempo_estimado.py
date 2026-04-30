from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hyrox', '0019_station_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='hyroxreadinesslog',
            name='tiempo_estimado_seg',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Tiempo estimado de carrera en segundos (snapshot diario del simulador)',
            ),
        ),
    ]

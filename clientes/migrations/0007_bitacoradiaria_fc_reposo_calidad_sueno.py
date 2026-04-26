from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0006_add_api_token_to_cliente'),
    ]

    operations = [
        migrations.AddField(
            model_name='bitacoradiaria',
            name='calidad_sueno',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text='Calidad del sueño (1-10)'
            ),
        ),
        migrations.AddField(
            model_name='bitacoradiaria',
            name='fc_reposo',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text='FC de reposo al despertar (lpm)'
            ),
        ),
    ]

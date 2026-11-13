from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0009_add_hrv_ms_to_bitacora'),
    ]

    operations = [
        migrations.AddField(
            model_name='bitacoradiaria',
            name='salud_importado_en',
            field=models.DateTimeField(blank=True, help_text='Cuándo se importó desde Salud del iPhone', null=True),
        ),
    ]

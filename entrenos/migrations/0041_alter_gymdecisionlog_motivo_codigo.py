from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0040_ejerciciorealizado_fallo_intencional_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gymdecisionlog',
            name='motivo_codigo',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Sin clasificar'),
                    ('tecnica_comprometida', 'Técnica comprometida'),
                    ('tope_maquina', 'Tope de máquina'),
                    ('tope_maquina_sin_margen', 'Tope de máquina sin margen'),
                    ('fallo_intencional', 'Fallo muscular previsto'),
                    ('fallo_no_controlado', 'Fallo muscular no previsto'),
                    ('fallo_repetido_no_controlado', 'Fallo muscular no previsto repetido'),
                    ('rpe_alto_sostenido', 'RPE alto sostenido'),
                    ('rpe_extremo', 'RPE extremo'),
                ],
                db_index=True,
                default='',
                help_text='Causa estable y evaluable de la decisión; el texto queda para explicación.',
                max_length=40,
            ),
        ),
    ]

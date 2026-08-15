from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0039_alter_gymdecisionlog_motivo_codigo'),
    ]

    operations = [
        migrations.AddField(
            model_name='ejerciciorealizado',
            name='fallo_intencional',
            field=models.BooleanField(
                blank=True,
                help_text='True=previsto, False=no previsto, None=sin fallo o dato legacy.',
                null=True,
            ),
        ),
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
                ],
                db_index=True,
                default='',
                help_text='Causa estable y evaluable de la decisión; el texto queda para explicación.',
                max_length=40,
            ),
        ),
    ]

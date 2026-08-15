from django.db import migrations, models


def clasificar_topes_legacy(apps, schema_editor):
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')
    GymDecisionLog.objects.filter(
        motivo_codigo='',
        accion='subir_reps',
        motivo__icontains='Tope de máquina',
    ).update(motivo_codigo='tope_maquina')


def desclasificar_topes(apps, schema_editor):
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')
    GymDecisionLog.objects.filter(
        motivo_codigo__in=('tope_maquina', 'tope_maquina_sin_margen'),
    ).update(motivo_codigo='')


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0038_gymdecisionlog_motivo_codigo'),
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
                ],
                db_index=True,
                default='',
                help_text='Causa estable y evaluable de la decisión; el texto queda para explicación.',
                max_length=40,
            ),
        ),
        migrations.RunPython(clasificar_topes_legacy, desclasificar_topes),
    ]

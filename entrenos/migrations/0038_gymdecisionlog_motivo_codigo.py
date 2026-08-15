from django.db import migrations, models
from django.db.models import Q


def clasificar_tecnica_legacy(apps, schema_editor):
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')
    GymDecisionLog.objects.filter(
        Q(motivo__icontains='técnica comprometida')
        | Q(motivo__icontains='tecnica comprometida'),
        motivo_codigo='',
    ).update(motivo_codigo='tecnica_comprometida')


def desclasificar_tecnica_legacy(apps, schema_editor):
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')
    GymDecisionLog.objects.filter(
        motivo_codigo='tecnica_comprometida',
    ).update(motivo_codigo='')


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0037_ciclodeload'),
    ]

    operations = [
        migrations.AddField(
            model_name='gymdecisionlog',
            name='motivo_codigo',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Sin clasificar'),
                    ('tecnica_comprometida', 'Técnica comprometida'),
                ],
                db_index=True,
                default='',
                help_text='Causa estable y evaluable de la decisión; el texto queda para explicación.',
                max_length=40,
            ),
        ),
        migrations.RunPython(
            clasificar_tecnica_legacy,
            desclasificar_tecnica_legacy,
        ),
    ]

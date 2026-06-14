# Generated for Phase Hábitos 2.0D

from django.db import migrations


def backfill_gesto(apps, schema_editor):
    TriggerHabito = apps.get_model('diario', 'TriggerHabito')
    Gesto = apps.get_model('diario', 'Gesto')

    for trigger in TriggerHabito.objects.select_related('habito__prosoche_mes').filter(gesto__isnull=True):
        if trigger.habito_id is None:
            continue
        habito = trigger.habito
        usuario_id = habito.prosoche_mes.usuario_id
        nombre = habito.nombre.strip()

        gesto = Gesto.objects.filter(usuario_id=usuario_id, nombre=nombre).first()
        if gesto is None:
            continue

        trigger.gesto = gesto
        trigger.save(update_fields=['gesto'])


def reverse_backfill_gesto(apps, schema_editor):
    TriggerHabito = apps.get_model('diario', 'TriggerHabito')
    TriggerHabito.objects.exclude(gesto__isnull=True).update(gesto=None)


class Migration(migrations.Migration):

    dependencies = [
        ('diario', '0019_triggerhabito_gesto_y_habito_nullable'),
    ]

    operations = [
        migrations.RunPython(backfill_gesto, reverse_backfill_gesto),
    ]

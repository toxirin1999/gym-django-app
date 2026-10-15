"""15-oct-2026: retira los "experimentos de observación" de hipótesis.

Cancela las vigilancias ("experimentos de observación") activas y da por
ignoradas las propuestas de hipótesis pendientes. Ninguna cambiaba el plan;
David decidió retirarlas tras revisar qué hacían.
"""

from django.db import migrations


def retirar(apps, schema_editor):
    IntervencionPlan = apps.get_model('entrenos', 'IntervencionPlan')
    SugerenciaPlan = apps.get_model('entrenos', 'SugerenciaPlan')
    IntervencionPlan.objects.filter(
        tipo='vigilar_senal', estado='activa',
    ).update(estado='cancelada')
    SugerenciaPlan.objects.filter(
        patron__startswith='hipotesis_senal_', estado='pendiente',
    ).update(estado='ignorada')


class Migration(migrations.Migration):
    dependencies = [('entrenos', '0063_finalizar_bloques_vencidos')]
    operations = [migrations.RunPython(retirar, migrations.RunPython.noop)]

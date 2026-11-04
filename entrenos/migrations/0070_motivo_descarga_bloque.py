"""4-nov-2026 (nota 1): el motivo de las descargas del bloque ya guardadas.

«Semana de descarga del bloque: RPE alto…» se leía como si la descarga
saliera solo del RPE. Ahora: «Toca la descarga del final del bloque y la
hago: RPE alto…».
"""

from django.db import migrations

VIEJO = 'Semana de descarga del bloque: '


def reescribir(apps, schema_editor):
    SemanaPlanGym = apps.get_model('entrenos', 'SemanaPlanGym')
    for semana in SemanaPlanGym.objects.filter(motivo__startswith=VIEJO):
        resto = semana.motivo[len(VIEJO):]
        if resto.endswith('semanas entrenando sin descargar.'):
            semana.motivo = f'Toca la descarga del final del bloque: llevas {resto}'
        else:
            semana.motivo = f'Toca la descarga del final del bloque y la hago: {resto}'
        semana.save(update_fields=['motivo'])


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0069_parada_declarada'),
    ]

    operations = [
        migrations.RunPython(reescribir, migrations.RunPython.noop),
    ]

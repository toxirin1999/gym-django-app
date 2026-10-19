"""19-oct-2026 · Elevación de Gemelos de Pie (Máquina): 100,5 kg no existe.

La máquina de David va de 5 en 5; el 100,5 era un dato mal apuntado que se
quedó como tope y como peso de las series (el 19-oct, la serie 1 se guardó
con 100,5 y las otras dos con 100). Todo pasa a 100 kg: series, ejercicios,
tope de la máquina, récords y decisiones.
"""

from decimal import Decimal

from django.db import migrations

CLIENTE = 2
NOMBRE = 'Elevación de Gemelos de Pie (Máquina)'
MAL = Decimal('100.5')
BIEN = Decimal('100')


def corregir(apps, schema_editor):
    SerieRealizada = apps.get_model('entrenos', 'SerieRealizada')
    EjercicioRealizado = apps.get_model('entrenos', 'EjercicioRealizado')
    TopeMaquinaGym = apps.get_model('entrenos', 'TopeMaquinaGym')
    RecordPersonal = apps.get_model('entrenos', 'RecordPersonal')
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')

    series = SerieRealizada.objects.filter(
        entreno__cliente_id=CLIENTE, ejercicio__nombre__iexact=NOMBRE, peso_kg=MAL,
    )
    for serie in series:
        serie.peso_kg = BIEN
        if serie.peso_total_kg is not None and Decimal(str(serie.peso_total_kg)) == MAL:
            serie.peso_total_kg = BIEN
        serie.save(update_fields=['peso_kg', 'peso_total_kg'])

    for ej in EjercicioRealizado.objects.filter(
        entreno__cliente_id=CLIENTE, nombre_ejercicio__iexact=NOMBRE,
    ):
        if ej.peso_kg is not None and abs(float(ej.peso_kg) - 100.5) < 0.01:
            ej.peso_kg = 100.0
            ej.save(update_fields=['peso_kg'])

    TopeMaquinaGym.objects.filter(
        cliente_id=CLIENTE, ejercicio__iexact=NOMBRE, peso_max_kg=MAL,
    ).update(peso_max_kg=BIEN)

    RecordPersonal.objects.filter(
        cliente_id=CLIENTE, ejercicio_nombre__iexact=NOMBRE, tipo_record='peso_maximo', valor=MAL,
    ).update(valor=BIEN)

    for log in GymDecisionLog.objects.filter(cliente_id=CLIENTE, ejercicio__iexact=NOMBRE):
        cambios = []
        if log.peso_anterior is not None and abs(log.peso_anterior - 100.5) < 0.01:
            log.peso_anterior = 100.0
            cambios.append('peso_anterior')
        if '100,5' in (log.motivo or ''):
            log.motivo = log.motivo.replace('100,5', '100')
            cambios.append('motivo')
        if cambios:
            log.save(update_fields=cambios)


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0066_farmer_zancadas_y_curl_martillo_total'),
    ]

    operations = [migrations.RunPython(corregir, migrations.RunPython.noop)]

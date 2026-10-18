"""18-oct-2026 · Revisión del Día 3 de David (2ª parte).

1. Farmer Walk: la decisión de hoy pedía "cambiar variante" por "36 kg × 0
   reps" (medía reps en un ejercicio de metros). El plan la habría usado para
   sustituirlo; pasa a "mantener".
2. Zancadas con Kettlebell: rango por pierna 8-12. La decisión de hoy se
   escribió con 16 reps frente a 20; se reescribe con 8 por pierna.
3. Curl Martillo con Mancuernas: el historial anterior al 18-oct se apuntó por
   mancuerna (17,5 en cada mano) y el de hoy en total (2 × 15 = 30). Se pasa
   el antiguo a peso total y se recalculan sus récords.
"""

from datetime import date
from decimal import Decimal

from django.db import migrations

DIA = date(2026, 10, 18)
CLIENTE = 2
CURL = 'Curl Martillo con Mancuernas'


def _decimal(valor):
    return Decimal(str(valor or 0))


def _total_serie(serie):
    total = _decimal(serie.peso_total_kg)
    if total > 0:
        return total
    return _decimal(serie.peso_kg) * Decimal(serie.multiplicador_carga or 1)


def decisiones(apps, schema_editor):
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')
    hoy = GymDecisionLog.objects.filter(cliente_id=CLIENTE, entreno_origen__fecha=DIA)

    for log in hoy.filter(ejercicio__icontains='farmer', accion='cambiar_variante'):
        log.accion = 'mantener'
        log.valor_cambio = None
        log.motivo_codigo = ''
        log.motivo = 'Peso fijo: progresa por metros. La próxima vez, algún metro más con 36 kg por mano.'
        log.save(update_fields=['accion', 'valor_cambio', 'motivo_codigo', 'motivo'])

    for log in hoy.filter(ejercicio__iexact='Zancadas con Kettlebell'):
        log.accion = 'mantener'
        log.valor_cambio = None
        log.motivo_codigo = ''
        log.motivo = (
            'Mantengo 16 kg: la próxima vez a por 9 reps por pierna. '
            'Con 12 en todas las series, subo el peso.'
        )
        log.save(update_fields=['accion', 'valor_cambio', 'motivo_codigo', 'motivo'])


def curl_a_total(apps, schema_editor):
    SerieRealizada = apps.get_model('entrenos', 'SerieRealizada')
    EjercicioRealizado = apps.get_model('entrenos', 'EjercicioRealizado')
    RecordPersonal = apps.get_model('entrenos', 'RecordPersonal')
    EntrenoRealizado = apps.get_model('entrenos', 'EntrenoRealizado')

    antiguas = SerieRealizada.objects.filter(
        entreno__cliente_id=CLIENTE, entreno__fecha__lt=DIA, ejercicio__nombre__iexact=CURL,
    ).exclude(tipo_carga='total')
    entrenos_tocados = set()
    for serie in antiguas:
        por_mancuerna = _decimal(serie.peso_kg)
        if por_mancuerna <= 0:
            continue
        total = por_mancuerna * 2
        serie.peso_kg = total
        serie.peso_total_kg = total
        serie.tipo_carga = 'total'
        serie.multiplicador_carga = 1
        serie.save(update_fields=['peso_kg', 'peso_total_kg', 'tipo_carga', 'multiplicador_carga'])
        entrenos_tocados.add(serie.entreno_id)

    for ej in EjercicioRealizado.objects.filter(
        entreno__cliente_id=CLIENTE, entreno__fecha__lt=DIA, nombre_ejercicio__iexact=CURL,
    ).exclude(tipo_carga='total'):
        if _decimal(ej.peso_kg) <= 0:
            continue
        ej.peso_kg = float(_decimal(ej.peso_kg) * 2)
        ej.tipo_carga = 'total'
        ej.multiplicador_carga = 1
        ej.save(update_fields=['peso_kg', 'tipo_carga', 'multiplicador_carga'])

    # Récords del curl martillo: se rehacen en orden con los pesos ya en total.
    RecordPersonal.objects.filter(cliente_id=CLIENTE, ejercicio_nombre__iexact=CURL).delete()
    mejor = {'peso_maximo': None, 'volumen_total': None}
    vigente = {'peso_maximo': None, 'volumen_total': None}
    entrenos = EntrenoRealizado.objects.filter(
        cliente_id=CLIENTE, series__ejercicio__nombre__iexact=CURL,
    ).distinct().order_by('fecha', 'id')
    for entreno in entrenos:
        series = [
            s for s in SerieRealizada.objects.filter(
                entreno=entreno, ejercicio__nombre__iexact=CURL, completado=True, es_aproximacion=False,
            )
            if s.distancia_metros is None
        ]
        if not series:
            continue
        valores = {
            'peso_maximo': max(_decimal(s.peso_kg) for s in series),
            'volumen_total': sum((_total_serie(s) * int(s.repeticiones or 0) for s in series), Decimal('0')),
        }
        for tipo, valor in valores.items():
            if valor <= 0 or (mejor[tipo] is not None and valor <= mejor[tipo]):
                continue
            if vigente[tipo] is not None:
                vigente[tipo].superado = True
                vigente[tipo].fecha_superado = entreno.fecha
                vigente[tipo].save(update_fields=['superado', 'fecha_superado'])
            vigente[tipo] = RecordPersonal.objects.create(
                cliente_id=CLIENTE, ejercicio_nombre=CURL, tipo_record=tipo, valor=valor, entreno=entreno,
            )
            mejor[tipo] = valor


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0065_zancadas_kettlebell_y_reps_por_brazo'),
    ]

    operations = [
        migrations.RunPython(decisiones, migrations.RunPython.noop),
        migrations.RunPython(curl_a_total, migrations.RunPython.noop),
    ]

"""18-oct-2026 · Revisión del Día 3 de David.

1. Curl martillo y zancadas del 18-oct se apuntaron como 16 reps en total;
   fueron 8 por brazo / por pierna. Se corrigen esas series (solo esa sesión,
   solo si siguen en 16) para que la próxima vez parta del dato real.
2. "Zancadas con Mancuernas" pasa a "Zancadas con Kettlebell": las hace con
   una sola kettlebell. Se renombra el ejercicio y su historial.
3. Los récords de ese día que no superan lo ya hecho en sesiones anteriores
   (gemelos a 100 kg, volumen del curl martillo contado en total) se retiran
   y vuelve a quedar vigente el récord que habían "superado".
"""

from datetime import date
from decimal import Decimal

from django.db import migrations

VIEJO = 'Zancadas con Mancuernas'
NUEVO = 'Zancadas con Kettlebell'


def aplicar(apps, schema_editor):
    EjercicioBase = apps.get_model('rutinas', 'EjercicioBase')
    EntrenoRealizado = apps.get_model('entrenos', 'EntrenoRealizado')
    EjercicioRealizado = apps.get_model('entrenos', 'EjercicioRealizado')
    SerieRealizada = apps.get_model('entrenos', 'SerieRealizada')
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')

    for entreno in EntrenoRealizado.objects.filter(fecha=date(2026, 10, 18), cliente_id=2):
        for nombre in ('Curl Martillo con Mancuernas', VIEJO):
            SerieRealizada.objects.filter(
                entreno=entreno, ejercicio__nombre__iexact=nombre, repeticiones=16,
            ).update(repeticiones=8)
            EjercicioRealizado.objects.filter(
                entreno=entreno, nombre_ejercicio__iexact=nombre, repeticiones=16,
            ).update(repeticiones=8)
            GymDecisionLog.objects.filter(
                entreno_origen=entreno, ejercicio__iexact=nombre, reps_anteriores=16,
            ).update(reps_anteriores=8)

    if not EjercicioBase.objects.filter(nombre__iexact=NUEVO).exists():
        EjercicioBase.objects.filter(nombre__iexact=VIEJO).update(nombre=NUEVO)
    EjercicioRealizado.objects.filter(nombre_ejercicio__iexact=VIEJO).update(nombre_ejercicio=NUEVO)
    GymDecisionLog.objects.filter(ejercicio__iexact=VIEJO).update(
        ejercicio=NUEVO, ejercicio_normalizado=NUEVO.lower(),
    )


def _carga(serie):
    total = Decimal(str(serie.peso_total_kg or 0))
    if total > 0:
        return total
    return Decimal(str(serie.peso_kg or 0)) * Decimal(serie.multiplicador_carga or 1)


def _valor(series, tipo):
    if tipo == 'peso_maximo':
        pesos = [Decimal(str(s.peso_kg)) for s in series if s.peso_kg is not None]
        return max(pesos) if pesos else None
    vol = sum(
        (_carga(s) * int(s.repeticiones or 0) for s in series if s.distancia_metros is None),
        Decimal('0'),
    )
    return vol or None


def limpiar_records(apps, schema_editor):
    EntrenoRealizado = apps.get_model('entrenos', 'EntrenoRealizado')
    SerieRealizada = apps.get_model('entrenos', 'SerieRealizada')
    RecordPersonal = apps.get_model('entrenos', 'RecordPersonal')
    dia = date(2026, 10, 18)

    for entreno in EntrenoRealizado.objects.filter(fecha=dia, cliente_id=2):
        for record in RecordPersonal.objects.filter(entreno=entreno, superado=False):
            if record.tipo_record not in ('peso_maximo', 'volumen_total'):
                continue
            base = SerieRealizada.objects.filter(
                ejercicio__nombre__iexact=record.ejercicio_nombre, completado=True, es_aproximacion=False,
            )
            hoy = _valor(list(base.filter(entreno=entreno)), record.tipo_record)
            previas = {}
            for s in base.filter(entreno__cliente_id=2, entreno__fecha__lte=dia).exclude(entreno=entreno):
                previas.setdefault(s.entreno_id, []).append(s)
            mejor = max(
                (v for v in (_valor(ss, record.tipo_record) for ss in previas.values()) if v is not None),
                default=None,
            )
            if hoy is not None and (mejor is None or hoy > mejor):
                if record.tipo_record == 'volumen_total' and hoy != record.valor:
                    record.valor = hoy
                    record.save(update_fields=['valor'])
                continue
            anterior = RecordPersonal.objects.filter(
                cliente_id=2, ejercicio_nombre__iexact=record.ejercicio_nombre,
                tipo_record=record.tipo_record, superado=True, fecha_superado=dia,
            ).order_by('-id').first()
            record.delete()
            if anterior:
                anterior.superado = False
                anterior.fecha_superado = None
                anterior.save(update_fields=['superado', 'fecha_superado'])


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0064_retirar_experimentos_hipotesis'),
        ('rutinas', '0005_ejerciciobase_incremento_kg'),
    ]

    operations = [
        migrations.RunPython(aplicar, migrations.RunPython.noop),
        migrations.RunPython(limpiar_records, migrations.RunPython.noop),
    ]

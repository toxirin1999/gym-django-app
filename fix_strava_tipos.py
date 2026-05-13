"""
Corrección de tipos en actividades Strava de producción.
Uso: python fix_strava_tipos.py --settings=gymproject.settings
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

import json
from entrenos.models import ActividadRealizada
from hyrox.models import HyroxObjective, HyroxSession, HyroxActivity, StravaActivityRaw
from clientes.models import Cliente
from hyrox.training_engine import HyroxLoadManager

cliente = Cliente.objects.get(user__username='david')
obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()

print(f"Cliente: {cliente}")
print(f"Objetivo Hyrox activo: {obj}")
print()

# ── 1. Actividades Strava con sport_type HIIT → cardio_sustituto ─────────────
print("=== 1. Corrigiendo HIIT/Fútbol a cardio_sustituto ===")
HIIT_SPORT_TYPES = {
    'HighIntensityIntervalTraining', 'Soccer', 'Football', 'Crossfit',
    'Elliptical', 'StairStepper',
}
corregidas = 0
for raw in StravaActivityRaw.objects.filter(cliente=cliente):
    data = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    if not data and raw.raw_json:
        try:
            data = json.loads(raw.raw_json)
        except Exception:
            pass
    sport_type = data.get('sport_type', '')
    if sport_type not in HIIT_SPORT_TYPES:
        continue
    actualizadas = ActividadRealizada.objects.filter(
        cliente=cliente,
        fuente='strava',
        titulo=raw.nombre_strava,
        fecha=raw.fecha_actividad,
        tipo='gym',
    ).update(tipo='cardio_sustituto')
    if actualizadas:
        corregidas += actualizadas
        print(f"  ✓ {raw.nombre_strava} ({raw.fecha_actividad}) → cardio_sustituto")

print(f"  Total corregidas: {corregidas}")
print()

# ── 2. Carreras Strava sin HyroxSession → crear y vincular ───────────────────
print("=== 2. Vinculando carreras a HyroxSession ===")
if not obj:
    print("  ✗ Sin objetivo Hyrox activo — saltando este paso")
else:
    carreras = ActividadRealizada.objects.filter(
        cliente=cliente,
        fuente='strava',
        tipo='carrera',
        sesion_hyrox__isnull=True,
    ).order_by('fecha')

    if not carreras.exists():
        print("  Ninguna carrera sin sesión Hyrox — nada que hacer")
    else:
        for a in carreras:
            dur = a.duracion_minutos or 30
            trimp = None
            if a.hr_media:
                trimp = HyroxLoadManager.calcular_trimp(dur, a.hr_media, obj)

            sesion = HyroxSession.objects.create(
                objective=obj,
                fecha=a.fecha,
                titulo=a.titulo,
                estado='completado',
                tiempo_total_minutos=dur,
                hr_media=a.hr_media,
                hr_maxima=a.hr_maxima,
                trimp=trimp,
            )
            HyroxActivity.objects.create(
                sesion=sesion,
                tipo_actividad='carrera',
                nombre_ejercicio=a.titulo,
                data_metricas={
                    'tiempo_minutos': dur,
                    'hr_media': a.hr_media,
                    'hr_maxima': a.hr_maxima,
                    'fuente': 'strava',
                },
            )
            # La señal post_save crea una ActividadRealizada duplicada — eliminarla
            ActividadRealizada.objects.filter(
                sesion_hyrox=sesion
            ).exclude(id=a.id).delete()

            a.sesion_hyrox = sesion
            a.save(update_fields=['sesion_hyrox'])

            trimp_str = f" | TRIMP {trimp}" if trimp else ""
            print(f"  ✓ {a.titulo} ({a.fecha}) → HyroxSession id={sesion.id}{trimp_str}")

print()
print("=== Hecho ===")

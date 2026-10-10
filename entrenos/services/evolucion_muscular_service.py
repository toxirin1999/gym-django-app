"""
Evolución por grupo muscular — alimenta el mapa corporal de "Lo que sé de ti".

Pregunta que responde: ¿cuánto ha crecido la fuerza de cada zona del cuerpo
en el periodo actual frente al anterior de la misma duración?

Método
------
1. Cada ``EjercicioRealizado`` se asigna a una zona canónica con
   ``normalizar_zona``: manda el ``grupo_muscular`` registrado (con o sin
   tilde, alias del catálogo); solo si es genérico o falta se infiere por
   el nombre del ejercicio.
2. Por ejercicio se toma el mejor 1RM estimado (Epley, carga efectiva) en
   cada ventana. Se descartan cargas de recuperación, series no completadas
   y registros sin peso.
3. Un ejercicio cuenta si tiene datos en ambas ventanas. La evolución de la
   zona es la mediana de sus ejercicios, para que un outlier (+200 % en un
   accesorio ligero) no domine.
"""
import statistics
import unicodedata
from collections import defaultdict
from datetime import date, timedelta

# Orden anatómico de presentación cuando no hay datos.
ZONAS = (
    'pecho', 'hombros', 'biceps', 'triceps', 'antebrazos', 'core',
    'espalda', 'trapecios', 'gluteos', 'cuadriceps', 'isquios', 'gemelos',
)

NOMBRES_ZONA = {
    'pecho': 'Pecho', 'hombros': 'Hombros', 'biceps': 'Bíceps',
    'triceps': 'Tríceps', 'antebrazos': 'Antebrazos', 'core': 'Core',
    'espalda': 'Espalda', 'trapecios': 'Trapecios', 'gluteos': 'Glúteos',
    'cuadriceps': 'Cuádriceps', 'isquios': 'Isquios', 'gemelos': 'Gemelos',
}

# Umbrales de estado (en % de cambio del e1RM).
UMBRAL_RETROCESO = -3.0
UMBRAL_PROGRESA = 10.0
UMBRAL_PROGRESA_MUCHO = 30.0

# Epley pierde fiabilidad con muchas repeticiones: se limita para no inflar
# el e1RM de series largas en máquina.
_MAX_REPS_E1RM = 15

_ALIAS_GRUPO = {
    'pecho': 'pecho', 'pectoral': 'pecho', 'pectorales': 'pecho', 'chest': 'pecho',
    'espalda': 'espalda', 'dorsal': 'espalda', 'dorsales': 'espalda', 'back': 'espalda',
    'rowing': 'espalda', 'dominadas': 'espalda', 'lats': 'espalda', 'lumbar': 'espalda',
    'hombro': 'hombros', 'hombros': 'hombros', 'deltoides': 'hombros', 'shoulders': 'hombros',
    'biceps': 'biceps', 'triceps': 'triceps',
    'antebrazo': 'antebrazos', 'antebrazos': 'antebrazos', 'forearms': 'antebrazos',
    'core': 'core', 'abdominales': 'core', 'abdomen': 'core', 'abs': 'core',
    'oblicuos': 'core',
    'trapecio': 'trapecios', 'trapecios': 'trapecios', 'traps': 'trapecios',
    'gluteo': 'gluteos', 'gluteos': 'gluteos', 'glutes': 'gluteos',
    'cuadriceps': 'cuadriceps', 'quads': 'cuadriceps',
    'isquio': 'isquios', 'isquios': 'isquios', 'isquiotibiales': 'isquios',
    'femoral': 'isquios', 'femorales': 'isquios', 'hamstrings': 'isquios',
    'gemelo': 'gemelos', 'gemelos': 'gemelos', 'pantorrilla': 'gemelos',
    'pantorrillas': 'gemelos', 'calves': 'gemelos',
}

# Orden importante: lo específico antes que lo genérico
# ("elevación de gemelos" antes que hombros, "curl femoral" antes que bíceps,
# "patada de tríceps" antes que glúteos, "jalón al pecho" antes que pecho).
_KEYWORDS_NOMBRE = (
    ('gemelos', ('gemelo', 'pantorrilla', 'calf', 'soleo')),
    ('isquios', ('curl femoral', 'femoral', 'isquio', 'peso muerto rumano', 'nordic',
                 'buenos dias', 'good morning')),
    ('triceps', ('tricep', 'press frances', 'press cerrado', 'fondos en banco', 'skull')),
    ('gluteos', ('hip thrust', 'glute', 'gluteo', 'abduccion', 'patada', 'puente')),
    ('cuadriceps', ('sentadilla', 'prensa', 'cuadricep', 'zancada', 'bulgara', 'hack',
                    'lunge', 'step up', 'squat')),
    ('biceps', ('curl', 'bicep', 'martillo')),
    ('antebrazos', ('antebrazo', 'muneca', 'wrist', 'farmer', 'granjero')),
    ('trapecios', ('encogimiento', 'shrug', 'trapecio')),
    ('core', ('crunch', 'plancha', 'pallof', 'abdominal', 'oblicuo', 'rueda',
              'elevacion de piernas', 'core')),
    ('hombros', ('press militar', 'elevacion lateral', 'elevaciones laterales',
                 'elevacion frontal', 'elevaciones frontales', 'pajaro', 'face pull',
                 'arnold', 'hombro', 'deltoid', 'press de hombro', 'overhead')),
    ('espalda', ('remo', 'jalon', 'dominada', 'pull', 'peso muerto', 'espalda',
                 'hiperextension', 'lat ')),
    ('pecho', ('banca', 'pecho', 'press inclinado', 'apertura', 'pec deck',
               'cruce de poleas', 'fondos', 'flexiones', 'chest', 'convergent')),
)


def _plano(texto):
    """minúsculas, sin tildes, espacios colapsados."""
    if not texto:
        return ''
    sin_tildes = ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    )
    return ' '.join(sin_tildes.lower().split())


def normalizar_zona(grupo_muscular, nombre_ejercicio):
    """Devuelve la zona canónica (ver ``ZONAS``) o ``None`` si no hay pistas."""
    zona = _ALIAS_GRUPO.get(_plano(grupo_muscular))
    if zona:
        return zona
    nombre = _plano(nombre_ejercicio)
    if not nombre:
        return None
    for zona, claves in _KEYWORDS_NOMBRE:
        if any(clave in nombre for clave in claves):
            return zona
    return None


def _e1rm(carga, reps):
    if carga <= 0 or reps < 1:
        return 0.0
    reps = min(reps, _MAX_REPS_E1RM)
    if reps == 1:
        return carga
    return carga * (1 + reps / 30.0)


def _carga(peso_total_kg, peso_kg, multiplicador):
    from entrenos.models import _carga_total_efectiva
    try:
        return float(_carga_total_efectiva(peso_total_kg, peso_kg, multiplicador))
    except Exception:
        return float(peso_kg or 0)


def _estado(pct):
    if pct is None:
        return 'sin_datos'
    if pct < UMBRAL_RETROCESO:
        return 'retrocede'
    if pct < UMBRAL_PROGRESA:
        return 'estable'
    if pct < UMBRAL_PROGRESA_MUCHO:
        return 'progresa'
    return 'progresa_mucho'


def _lectura(estado, series_semana):
    """Frase descriptiva y determinista para la fila de cada zona."""
    if estado == 'sin_datos':
        if series_semana > 0:
            return 'Lo entrenas, pero no hay ejercicios comparables entre los dos periodos.'
        return 'Sin registros de fuerza en estos periodos.'
    if estado == 'retrocede':
        return 'Tu mejor marca estimada ha bajado frente al periodo anterior.'
    if estado == 'estable':
        return 'Mantiene su nivel de fuerza.'
    if series_semana < 10:
        return 'Tu fuerza estimada ha subido, y con poco volumen: responde bien al estímulo.'
    return 'Tu fuerza estimada ha subido con un volumen ya dentro del rango útil.'


def calcular_evolucion_por_grupo(cliente, hoy=None, dias=90):
    """
    Compara el mejor e1RM de cada ejercicio en ``(hoy-dias, hoy]`` frente a
    ``(hoy-2·dias, hoy-dias]`` y lo agrega por zona.

    Devuelve::

        {
          'periodo_dias': 90,
          'media_pct': 43.7 | None,   # media de las zonas con datos
          'n_con_datos': 4,
          'grupos': [  # las 12 zonas; con datos primero (pct desc)
            {'zona', 'nombre', 'pct', 'estado', 'n_ejercicios',
             'series_semana', 'lectura',
             'mejor': {'ejercicio', 'antes', 'ahora', 'pct'} | None},
          ],
          'estado_por_zona': {'pecho': 'progresa', ...},  # para colorear el SVG
          'lider': <grupo con más progreso> | None,
        }
    """
    from entrenos.models import EjercicioRealizado

    hoy = hoy or date.today()
    inicio_actual = hoy - timedelta(days=dias)
    inicio_anterior = hoy - timedelta(days=2 * dias)
    inicio_series = hoy - timedelta(days=28)

    filas = (
        EjercicioRealizado.objects
        .filter(
            entreno__cliente=cliente,
            entreno__fecha__gt=min(inicio_anterior, inicio_series),
            entreno__fecha__lte=hoy,
            completado=True,
        )
        .values_list(
            'entreno__fecha', 'nombre_ejercicio', 'grupo_muscular', 'peso_kg',
            'peso_total_kg', 'multiplicador_carga', 'repeticiones', 'series',
            'is_recovery_load',
        )
    )

    # (zona, clave_ejercicio) -> {'antes': e1rm, 'ahora': e1rm, 'nombre': str, 'fecha': date}
    por_ejercicio = {}
    series_por_zona = defaultdict(float)

    for fecha, nombre, grupo, peso, peso_total, mult, reps, series, recuperacion in filas:
        zona = normalizar_zona(grupo, nombre)
        if zona is None:
            continue

        if fecha > inicio_series:
            series_por_zona[zona] += series or 0

        if recuperacion or fecha <= inicio_anterior:
            continue
        e1rm = _e1rm(_carga(peso_total, peso, mult), int(reps or 0))
        if e1rm <= 0:
            continue

        ventana = 'ahora' if fecha > inicio_actual else 'antes'
        clave = (zona, _plano(nombre))
        info = por_ejercicio.setdefault(clave, {'antes': 0.0, 'ahora': 0.0,
                                                'nombre': nombre.strip(), 'fecha': fecha})
        info[ventana] = max(info[ventana], e1rm)
        if fecha >= info['fecha']:
            info['nombre'], info['fecha'] = nombre.strip(), fecha

    cambios_por_zona = defaultdict(list)
    for (zona, _), info in por_ejercicio.items():
        if info['antes'] > 0 and info['ahora'] > 0:
            pct = (info['ahora'] - info['antes']) / info['antes'] * 100
            cambios_por_zona[zona].append({
                'ejercicio': info['nombre'],
                'antes': round(info['antes'], 1),
                'ahora': round(info['ahora'], 1),
                'pct': round(pct, 1),
            })

    grupos = []
    for zona in ZONAS:
        cambios = cambios_por_zona.get(zona, [])
        pct = round(statistics.median(c['pct'] for c in cambios), 1) if cambios else None
        grupos.append({
            'zona': zona,
            'nombre': NOMBRES_ZONA[zona],
            'pct': pct,
            'estado': _estado(pct),
            'n_ejercicios': len(cambios),
            'series_semana': round(series_por_zona.get(zona, 0) / 4.0, 1),
            'mejor': max(cambios, key=lambda c: c['pct']) if cambios else None,
        })
        grupos[-1]['lectura'] = _lectura(grupos[-1]['estado'], grupos[-1]['series_semana'])

    con_datos = sorted((g for g in grupos if g['pct'] is not None), key=lambda g: -g['pct'])
    sin_datos = [g for g in grupos if g['pct'] is None]
    media = (round(sum(g['pct'] for g in con_datos) / len(con_datos), 1)
             if con_datos else None)

    return {
        'periodo_dias': dias,
        'media_pct': media,
        'n_con_datos': len(con_datos),
        'grupos': con_datos + sin_datos,
        'estado_por_zona': {g['zona']: g['estado'] for g in grupos},
        'lider': con_datos[0] if con_datos else None,
        'zonas_sin_registros': [g['nombre'] for g in sin_datos if not g['series_semana']],
    }

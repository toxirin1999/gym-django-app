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
2. Por ejercicio se toma el mejor 1RM estimado (Epley) en cada ventana a
   partir de la MEJOR SERIE DE TRABAJO real (``SerieRealizada``, sin
   aproximaciones). ``EjercicioRealizado`` guarda la media de las series,
   que en una pirámide no corresponde a ninguna serie real; solo se usa en
   entrenos antiguos sin series individuales. La carga se toma POR UNIDAD (por mano / por lado, tal como se
   registra en ``peso_kg``). Así un cambio de criterio de registro (antes
   solo el peso por mano, ahora el total de las dos) no duplica la carga.
   Se descartan cargas de recuperación, series no completadas y registros
   sin peso.
3. Un ejercicio cuenta si tiene datos en ambas ventanas. Un cambio de más
   de ±``UMBRAL_DUDOSO`` % en un solo periodo es casi siempre un error de
   registro: se aparta como "dato a revisar" y no entra en la mediana.
   Si el ejercicio es ligero (e1RM previo < ``UMBRAL_LIGERO_KG``) se
   muestra como "accesorio ligero" en vez de como error.
4. La evolución de la zona es la mediana de sus ejercicios fiables.
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
# ±5 %: el e1RM varía ese margen solo por cambiar de rango de repeticiones.
UMBRAL_RETROCESO = -5.0
UMBRAL_PROGRESA = 10.0
UMBRAL_PROGRESA_MUCHO = 30.0
# Cambio por ejercicio a partir del cual se considera un posible error de registro.
UMBRAL_DUDOSO = 60.0
# Por debajo de este e1RM (kg) un ejercicio es un accesorio ligero: cada salto
# de carga es un porcentaje enorme. Esos saltos no son errores, pero tampoco
# representan la fuerza del grupo, así que se muestran aparte.
UMBRAL_LIGERO_KG = 30.0

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


def _carga_por_unidad(peso_kg, peso_total_kg, multiplicador):
    """
    Carga de una unidad (una mano, un lado, o el total si se registra así).

    ``peso_kg`` es lo que se registra en cada serie y es estable entre
    criterios de registro; ``peso_total_kg`` solo se usa si falta, dividido
    entre su multiplicador.
    """
    try:
        peso = float(peso_kg or 0)
    except (TypeError, ValueError):
        peso = 0.0
    if peso > 0:
        return peso
    try:
        total = float(peso_total_kg or 0)
        mult = max(int(multiplicador or 1), 1)
    except (TypeError, ValueError):
        return 0.0
    return total / mult if total > 0 else 0.0


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


def _lectura(estado, series_semana, n_dudosos=0, n_ligeros=0):
    """Frase descriptiva y determinista para la fila de cada zona."""
    if estado == 'sin_datos':
        if n_ligeros and not n_dudosos:
            return ('Solo hay accesorios ligeros comparables: sus saltos en % no '
                    'reflejan la fuerza del grupo.')
        if n_dudosos:
            return ('Hay cambios demasiado grandes para ser fiables: '
                    'revisa cómo se registró el peso de estos ejercicios.')
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


def _ventanas(hoy, dias):
    return hoy - timedelta(days=dias), hoy - timedelta(days=2 * dias)


def _filas(cliente, desde, hoy):
    """Agregados por ejercicio y sesión (``EjercicioRealizado``)."""
    from entrenos.models import EjercicioRealizado
    return (
        EjercicioRealizado.objects
        .filter(
            entreno__cliente=cliente,
            entreno__fecha__gt=desde,
            entreno__fecha__lte=hoy,
            completado=True,
        )
        .values_list(
            'entreno__fecha', 'nombre_ejercicio', 'grupo_muscular', 'peso_kg',
            'peso_total_kg', 'multiplicador_carga', 'tipo_carga', 'repeticiones',
            'series', 'is_recovery_load', 'entreno_id',
        )
        .order_by('entreno__fecha')
    )


def _series(cliente, desde, hoy):
    """Series de trabajo individuales (``SerieRealizada``), sin aproximaciones."""
    from entrenos.models import SerieRealizada
    return (
        SerieRealizada.objects
        .filter(
            entreno__cliente=cliente,
            entreno__fecha__gt=desde,
            entreno__fecha__lte=hoy,
            completado=True,
            es_aproximacion=False,
            distancia_metros__isnull=True,
            repeticiones__gte=1,
        )
        .values_list(
            'entreno__fecha', 'ejercicio__nombre', 'ejercicio__grupo_muscular', 'peso_kg',
            'peso_total_kg', 'multiplicador_carga', 'tipo_carga', 'repeticiones',
            'entreno_id',
        )
        .order_by('entreno__fecha')
    )


def comparar_ejercicios(cliente, hoy=None, dias=90):
    """
    Detalle por ejercicio de las dos ventanas. Lo usan el mapa y el comando
    ``diagnosticar_evolucion_muscular``.

    Devuelve una lista de dicts::

        {'zona', 'ejercicio', 'pct' | None, 'dudoso': bool, 'ligero': bool,
         'antes': {'e1rm', 'peso_kg', 'reps', 'fecha', 'tipo_carga',
                   'multiplicador', 'peso_total_kg',
                   'fuente': 'serie' | 'media'} | None,
         'ahora': {...} | None}
    """
    hoy = hoy or date.today()
    inicio_actual, inicio_anterior = _ventanas(hoy, dias)

    agregados = list(_filas(cliente, inicio_anterior, hoy))
    # Sesiones/ejercicio marcados como carga de recuperación: ni su media ni sus series cuentan.
    recuperacion = {(eid, _plano(nombre))
                    for _f, nombre, *_r, rec, eid in agregados if rec}

    candidatos = []  # (fecha, nombre, grupo, peso, total, mult, tipo, reps, fuente)
    con_series = set()
    for fecha, nombre, grupo, peso, total, mult, tipo, reps, eid in \
            _series(cliente, inicio_anterior, hoy):
        clave = (eid, _plano(nombre))
        if clave in recuperacion:
            continue
        con_series.add(clave)
        candidatos.append((fecha, nombre, grupo, peso, total, mult, tipo, reps, 'serie'))
    for fecha, nombre, grupo, peso, total, mult, tipo, reps, _series_n, rec, eid in agregados:
        if rec or (eid, _plano(nombre)) in con_series:
            continue
        candidatos.append((fecha, nombre, grupo, peso, total, mult, tipo, reps, 'media'))
    candidatos.sort(key=lambda c: c[0])

    por_ejercicio = {}
    for fecha, nombre, grupo, peso, peso_total, mult, tipo, reps, fuente in candidatos:
        zona = normalizar_zona(grupo, nombre)
        if zona is None:
            continue
        reps = int(reps or 0)
        e1rm = _e1rm(_carga_por_unidad(peso, peso_total, mult), reps)
        if e1rm <= 0:
            continue

        ventana = 'ahora' if fecha > inicio_actual else 'antes'
        info = por_ejercicio.setdefault((zona, _plano(nombre)), {
            'zona': zona, 'ejercicio': nombre.strip(), 'antes': None, 'ahora': None,
        })
        # Candidatos ordenados por fecha: el último nombre visto es el más reciente.
        info['ejercicio'] = nombre.strip()
        actual = info[ventana]
        if actual is None or e1rm > actual['e1rm']:
            info[ventana] = {
                'e1rm': e1rm, 'peso_kg': float(peso or 0), 'reps': reps, 'fecha': fecha,
                'tipo_carga': tipo, 'multiplicador': mult, 'peso_total_kg': peso_total,
                'fuente': fuente,
            }

    resultado = []
    for info in por_ejercicio.values():
        pct = None
        if info['antes'] and info['ahora']:
            pct = round((info['ahora']['e1rm'] - info['antes']['e1rm'])
                        / info['antes']['e1rm'] * 100, 1)
        info['pct'] = pct
        extremo = pct is not None and abs(pct) > UMBRAL_DUDOSO
        info['ligero'] = extremo and info['antes']['e1rm'] < UMBRAL_LIGERO_KG
        info['dudoso'] = extremo and not info['ligero']
        resultado.append(info)
    return sorted(resultado, key=lambda e: (e['zona'], e['ejercicio']))


def calcular_evolucion_por_grupo(cliente, hoy=None, dias=90):
    """
    Compara el mejor e1RM por unidad de cada ejercicio en ``(hoy-dias, hoy]``
    frente a ``(hoy-2·dias, hoy-dias]`` y lo agrega por zona.

    Devuelve::

        {
          'periodo_dias': 90,
          'media_pct': 43.7 | None,   # media de las zonas con datos
          'n_con_datos': 4,
          'n_dudosos': 2,             # ejercicios apartados como dato a revisar
          'grupos': [  # las 12 zonas; con datos primero (pct desc)
            {'zona', 'nombre', 'pct', 'estado', 'n_ejercicios',
             'series_semana', 'lectura',
             'mejor': {'ejercicio', 'antes', 'ahora', 'pct'} | None,
             'dudosos': [{'ejercicio', 'antes', 'ahora', 'pct'}],
             'ligeros': [{'ejercicio', 'antes', 'ahora', 'pct'}]},
          ],
          'estado_por_zona': {'pecho': 'progresa', ...},  # para colorear el SVG
          'lider': <grupo con más progreso> | None,
          'zonas_sin_registros': ['Antebrazos', ...],
        }
    """
    hoy = hoy or date.today()
    inicio_series = hoy - timedelta(days=28)

    series_por_zona = defaultdict(float)
    for fecha, nombre, grupo, *_resto, series, _rec, _eid in _filas(cliente, inicio_series, hoy):
        zona = normalizar_zona(grupo, nombre)
        if zona:
            series_por_zona[zona] += series or 0

    fiables = defaultdict(list)
    dudosos = defaultdict(list)
    ligeros = defaultdict(list)
    for e in comparar_ejercicios(cliente, hoy=hoy, dias=dias):
        if e['pct'] is None:
            continue
        resumen = {'ejercicio': e['ejercicio'], 'antes': round(e['antes']['e1rm'], 1),
                   'ahora': round(e['ahora']['e1rm'], 1), 'pct': e['pct']}
        destino = dudosos if e['dudoso'] else ligeros if e['ligero'] else fiables
        destino[e['zona']].append(resumen)

    grupos = []
    for zona in ZONAS:
        cambios = fiables.get(zona, [])
        pct = round(statistics.median(c['pct'] for c in cambios), 1) if cambios else None
        grupo = {
            'zona': zona,
            'nombre': NOMBRES_ZONA[zona],
            'pct': pct,
            'estado': _estado(pct),
            'n_ejercicios': len(cambios),
            'series_semana': round(series_por_zona.get(zona, 0) / 4.0, 1),
            'mejor': max(cambios, key=lambda c: c['pct']) if cambios else None,
            'dudosos': sorted(dudosos.get(zona, []), key=lambda c: -abs(c['pct'])),
            'ligeros': sorted(ligeros.get(zona, []), key=lambda c: -abs(c['pct'])),
        }
        grupo['lectura'] = _lectura(grupo['estado'], grupo['series_semana'],
                                    len(grupo['dudosos']), len(grupo['ligeros']))
        grupos.append(grupo)

    con_datos = sorted((g for g in grupos if g['pct'] is not None), key=lambda g: -g['pct'])
    sin_datos = [g for g in grupos if g['pct'] is None]
    media = (round(sum(g['pct'] for g in con_datos) / len(con_datos), 1)
             if con_datos else None)

    return {
        'periodo_dias': dias,
        'media_pct': media,
        'n_con_datos': len(con_datos),
        'n_dudosos': sum(len(g['dudosos']) for g in grupos),
        'grupos': con_datos + sin_datos,
        'estado_por_zona': {g['zona']: g['estado'] for g in grupos},
        'lider': con_datos[0] if con_datos else None,
        'zonas_sin_registros': [g['nombre'] for g in sin_datos
                                if not g['series_semana'] and not g['dudosos']
                                and not g['ligeros']],
    }

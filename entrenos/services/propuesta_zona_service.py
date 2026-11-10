"""Iniciativa del entrenador: ajustar el volumen semanal de una zona.

Las cuatro reglas del rumbo (docs/rumbo_entrenador_vivo.md) en un solo gesto:
1. Se da cuenta: una zona del mapa muscular retrocede a 90 días, o acumula
   fatiga (RPE alto o fallos no previstos en varios de sus ejercicios).
2. Propone un cambio real y acotado: ±2 series semanales en esa zona,
   repartidas en sus sesiones, durante 4 semanas (paso 5, 13-oct-2026; antes
   era +1 serie en dos ejercicios). Solo se aplica si el usuario acepta, y lo
   aplica el planificador (volumen_grupo_service).
3. Lo explica con el dato: porcentaje y marcas antes/ahora, o los ejercicios
   con fatiga.
4. Al terminar, compara las 4 semanas de la propuesta con las 4 anteriores y
   dice si funcionó. Si funcionó, el cambio se queda.

Regla de oro: si no puede citar el dato, no propone nada.

31-oct-2026 (repaso de apps, idea 2): además del retroceso, la fatiga y las
molestias, dos señales sacadas solo de lo que ya se registra:
- **Por encima del máximo** dos semanas seguidas (marcador semanal) → −2.
- **Margen sin progreso**: los ejercicios de la zona terminan 3 sesiones
  seguidas al menos un punto por debajo del RPE pedido ese día y sin subir
  su fuerza estimada, con la zona por debajo de su máximo → +2.
"""

from datetime import date, timedelta
from statistics import median

from django.db import transaction
from django.utils import timezone

SEMANAS = 4
SERIES_EXTRA = 2              # series semanales de la zona (no por ejercicio)
MIN_EJERCICIOS_FATIGA = 2
_MOTIVOS_FATIGA = (
    'rpe_alto_sostenido', 'rpe_extremo', 'fallo_no_controlado', 'fallo_repetido_no_controlado',
)
UMBRAL_EJERCICIO = -5.0      # % de caída de un ejercicio para tenerlo en cuenta
ENFRIAMIENTO_DIAS = 28       # tras rechazar o evaluar, no repetir la misma zona
MAX_EJERCICIOS = 2
SESIONES_MARGEN = 3          # sesiones seguidas con margen y sin progreso
VENTANA_MARGEN_DIAS = 35
MARGEN_RPE = 1.0             # al menos un punto por debajo del RPE pedido

# 7-nov-2026 (decisión de David): tríceps y trapecio mantienen su volumen hasta
# que cierre el bloque Fuerza — Hipertrofia (semanas 45-48 de la
# periodización; previsto el domingo 06/12/2026). La pausa va ligada al
# cierre, no a una fecha: si el bloque se retrasa, sigue hasta su revisión.
# Mientras, el entrenador los observa (Memoria anota si caen) pero no propone
# añadirles series; bajar volumen sí puede. Termina en cuanto el plan pasa a
# una semana fuera del bloque, y no se reactiva.
ZONAS_SUBIR_EN_PAUSA = ('triceps', 'trapecios')
PAUSA_DESDE = date(2026, 11, 2)              # semana de la decisión (descarga, semana 44)
PAUSA_SEMANAS = range(44, 49)                # la descarga previa y el bloque (45-48)
PAUSA_BLOQUE = 'Fuerza — Hipertrofia'


def pausa_subir_volumen(cliente, hoy):
    """{'zonas', 'fin_previsto', 'bloque'} mientras dura la pausa, o None.

    Sin periodización dinámica (``SemanaPlanGym``) no hay pausa.
    """
    from entrenos.models import SemanaPlanGym

    if cliente is None or hoy < PAUSA_DESDE:
        return None
    registros = SemanaPlanGym.objects.filter(cliente=cliente, lunes__gte=PAUSA_DESDE, lunes__lte=hoy)
    actual = registros.order_by('-lunes').first()
    if actual is None or registros.exclude(semana_plan__in=PAUSA_SEMANAS).exists():
        return None
    fin_previsto = actual.lunes + timedelta(days=7 * (PAUSA_SEMANAS[-1] - actual.semana_plan) + 6)
    return {'zonas': ZONAS_SUBIR_EN_PAUSA, 'fin_previsto': fin_previsto, 'bloque': PAUSA_BLOQUE}


def subir_en_pausa(cliente, zona, hoy):
    pausa = pausa_subir_volumen(cliente, hoy)
    return bool(pausa and zona in pausa['zonas'])


def _kg(valor):
    texto = f'{float(valor):.1f}'.replace('.', ',')
    return texto[:-2] if texto.endswith(',0') else texto


def _plano(nombre):
    from entrenos.services.evolucion_muscular_service import _plano as plano
    return plano(nombre)


def detectar_zona_en_retroceso(cliente, hoy=None):
    """La zona que más retrocede con datos fiables, o None."""
    from entrenos.services.evolucion_muscular_service import (
        NOMBRES_ZONA, calcular_evolucion_por_grupo, comparar_ejercicios,
    )

    hoy = hoy or timezone.localdate()
    evolucion = calcular_evolucion_por_grupo(cliente, hoy, 90)
    pausa = pausa_subir_volumen(cliente, hoy)
    pausadas = set(pausa['zonas']) if pausa else set()
    zonas = [z for z, estado in (evolucion.get('estado_por_zona') or {}).items()
             if estado == 'retrocede' and z not in pausadas]
    if not zonas:
        return None
    ejercicios = comparar_ejercicios(cliente, hoy, 90)
    candidatas = []
    for zona in zonas:
        caen = sorted(
            (
                e for e in ejercicios
                if e['zona'] == zona and e['pct'] is not None
                and not e['dudoso'] and not e['ligero'] and e['pct'] <= UMBRAL_EJERCICIO
            ),
            key=lambda e: e['pct'],
        )
        if not caen:
            continue
        fiables = [
            e['pct'] for e in ejercicios
            if e['zona'] == zona and e['pct'] is not None and not e['dudoso'] and not e['ligero']
        ]
        candidatas.append({
            'zona': zona,
            'nombre_zona': NOMBRES_ZONA.get(zona, zona.title()),
            'pct': round(median(fiables), 1),
            'ejercicios': caen[:MAX_EJERCICIOS],
        })
    if not candidatas:
        return None
    return min(candidatas, key=lambda c: c['pct'])


def _texto_propuesta(deteccion):
    peor = deteccion['ejercicios'][0]
    antes, ahora = peor['antes'], peor['ahora']
    nombres = [e['ejercicio'] for e in deteccion['ejercicios']]
    lista = ' y '.join(nombres)
    return (
        f"{deteccion['nombre_zona']}: {str(deteccion['pct']).replace('.', ',')} % en 90 días "
        f"({peor['ejercicio']}: {_kg(antes['peso_kg'])} kg × {antes['reps']} → "
        f"{_kg(ahora['peso_kg'])} kg × {ahora['reps']}). "
        f"Te propongo +{SERIES_EXTRA} series semanales de {deteccion['nombre_zona']} "
        f"durante {SEMANAS} semanas; lo mediré en {lista}."
    )


def detectar_zona_con_fatiga(cliente, hoy=None):
    """Zona con fatiga en varios de sus ejercicios en 14 días, o None.

    Señal: decisiones del plan por RPE alto o fallo no previsto en al menos
    dos ejercicios distintos de la misma zona. No se propone bajar en una zona
    que ya retrocede (ahí el problema puede ser falta de estímulo).
    """
    from entrenos.models import GymDecisionLog
    from entrenos.services.evolucion_muscular_service import (
        NOMBRES_ZONA, calcular_evolucion_por_grupo, normalizar_zona,
    )

    hoy = hoy or timezone.localdate()
    por_zona = {}
    for nombre in GymDecisionLog.objects.filter(
        cliente=cliente, motivo_codigo__in=_MOTIVOS_FATIGA,
        fecha_creacion__date__gte=hoy - timedelta(days=14), fecha_creacion__date__lte=hoy,
    ).values_list('ejercicio', flat=True):
        zona = normalizar_zona(None, nombre)
        if zona:
            por_zona.setdefault(zona, set()).add((nombre or '').strip())
    candidatas = {z: e for z, e in por_zona.items() if len(e) >= MIN_EJERCICIOS_FATIGA}
    if not candidatas:
        return None
    estados = (calcular_evolucion_por_grupo(cliente, hoy, 90).get('estado_por_zona') or {})
    candidatas = {z: e for z, e in candidatas.items() if estados.get(z) != 'retrocede'}
    if not candidatas:
        return None
    zona, ejercicios = max(candidatas.items(), key=lambda kv: (len(kv[1]), kv[0]))
    return {
        'zona': zona,
        'nombre_zona': NOMBRES_ZONA.get(zona, zona.title()),
        'ejercicios_fatiga': sorted(ejercicios),
    }


def _texto_propuesta_bajar(deteccion):
    lista = ' y '.join(deteccion['ejercicios_fatiga'][:3])
    n = len(deteccion['ejercicios_fatiga'])
    return (
        f"{deteccion['nombre_zona']}: RPE alto o fallos no previstos en {n} ejercicios en 14 días "
        f"({lista}). Te propongo −{SERIES_EXTRA} series semanales de {deteccion['nombre_zona']} "
        f"durante {SEMANAS} semanas para recuperar margen."
    )


def _zona_de_grupo(grupo):
    from entrenos.services.evolucion_muscular_service import normalizar_zona
    return normalizar_zona(grupo, None)


def zonas_por_encima_del_maximo(cliente, hoy=None):
    """{zona: (hechas_esta, hechas_anterior, minimo, maximo)} por encima del máximo dos semanas seguidas.

    Semana = ventana de 7 días del marcador semanal (series de trabajo, las
    indirectas cuentan media). El máximo es el de la semana del plan de hoy.
    Dos ventanas seguidas para no reaccionar a una semana de recuperar sesiones.
    """
    from entrenos.services.marcador_semanal_service import marcador_cacheado, series_hechas

    hoy = hoy or timezone.localdate()
    filas = (marcador_cacheado(cliente, hoy) or {}).get('filas') or []
    anterior = series_hechas(cliente, hoy - timedelta(days=7))
    altas = {}
    for f in filas:
        zona = _zona_de_grupo(f['clave'])
        previas = anterior.get(f['clave'], 0)
        if zona and f['hechas'] > f['maximo'] and previas > f['maximo']:
            altas[zona] = (f['hechas'], previas, f['minimo'], f['maximo'])
    return altas


def _num(valor):
    return str(int(valor)) if float(valor).is_integer() else f'{valor:g}'.replace('.', ',')


def detectar_zona_por_encima(cliente, hoy=None):
    """La zona que más se pasa de su máximo (dos semanas seguidas), o None."""
    from entrenos.services.evolucion_muscular_service import NOMBRES_ZONA

    altas = zonas_por_encima_del_maximo(cliente, hoy)
    if not altas:
        return None
    zona, (h, previas, minimo, maximo) = max(altas.items(), key=lambda kv: (kv[1][0] - kv[1][3], kv[0]))
    return {'zona': zona, 'nombre_zona': NOMBRES_ZONA.get(zona, zona.title()),
            'hechas': h, 'previas': previas, 'minimo': minimo, 'maximo': maximo}


def _texto_propuesta_por_encima(d):
    return (
        f"{d['nombre_zona']}: {_num(d['hechas'])} series esta semana y {_num(d['previas'])} la anterior, "
        f"por encima de tu máximo útil ({d['minimo']}–{d['maximo']}). Esas series no suman, solo cansan. "
        f"Te propongo −{SERIES_EXTRA} series semanales de {d['nombre_zona']} durante {SEMANAS} semanas."
    )


def _rpe_pedido(entreno, nombre):
    """RPE que se pidió ese día (con las rebajas de ese día), o None."""
    from entrenos.services.decision_log_service import normalizar_ejercicio

    version = getattr(entreno, 'gym_decision_version', None)
    snapshot = getattr(version, 'snapshot', None) or {}
    clave = normalizar_ejercicio(nombre)
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        if normalizar_ejercicio(ej.get('nombre')) == clave:
            try:
                return float(ej.get('rpe_objetivo'))
            except (TypeError, ValueError):
                return None
    return None


def _sesiones_con_margen(cliente, nombre, hoy):
    """Las últimas sesiones del ejercicio si todas tuvieron margen y no progresó, o None.

    Margen: la serie de referencia terminó al menos ``MARGEN_RPE`` por debajo
    del RPE pedido ese día. Sin progreso: la fuerza estimada de la última no
    supera la de la primera. Las sesiones de descarga no cuentan.
    """
    from entrenos.models import EjercicioRealizado
    from entrenos.services.evolucion_muscular_service import _e1rm
    from entrenos.services.sesion_descarga_service import es_sesion_descarga, periodos_descarga
    from entrenos.services.ultima_sesion_service import rango_de_sesion, serie_referencia, series_de_trabajo

    periodos = periodos_descarga(cliente.pk)
    sesiones = []
    for ej in EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, nombre_ejercicio__iexact=nombre, completado=True,
        entreno__fecha__gt=hoy - timedelta(days=VENTANA_MARGEN_DIAS), entreno__fecha__lte=hoy,
    ).select_related('entreno').order_by('-entreno__fecha', '-entreno_id'):
        if len(sesiones) >= SESIONES_MARGEN:
            break
        if es_sesion_descarga(ej.entreno, nombre, periodos):
            continue
        series = series_de_trabajo(ej.entreno, nombre)
        if not series or any(s.get('metros') for s in series):
            continue
        rango = rango_de_sesion(ej.entreno, nombre)
        ref = serie_referencia(series, rango[0] if rango else None)
        pedido = _rpe_pedido(ej.entreno, nombre)
        if ref is None or ref['peso'] <= 0 or ref.get('rpe') is None or pedido is None:
            return None
        sesiones.append({'fecha': ej.entreno.fecha, 'peso': ref['peso'], 'reps': int(ref['reps']),
                         'rpe': float(ref['rpe']), 'pedido': pedido})
    if len(sesiones) < SESIONES_MARGEN:
        return None
    if any(s['rpe'] > s['pedido'] - MARGEN_RPE for s in sesiones):
        return None
    sesiones.reverse()  # de la más antigua a la última
    primera, ultima = sesiones[0], sesiones[-1]
    if _e1rm(ultima['peso'], ultima['reps']) > _e1rm(primera['peso'], primera['reps']) + 1e-6:
        return None
    return sesiones


def detectar_zona_con_margen(cliente, hoy=None):
    """Zona por debajo de su máximo cuyos ejercicios llevan 3 sesiones con margen y sin progreso.

    Hacen falta al menos dos ejercicios de la zona así (o el único que tenga).
    Nunca en una zona por encima del máximo ni con molestia reciente.
    """
    from entrenos.models import EjercicioRealizado
    from entrenos.services.evolucion_muscular_service import NOMBRES_ZONA, normalizar_zona
    from entrenos.services.marcador_semanal_service import marcador_cacheado
    from entrenos.services.sensacion_zona_service import frena_subir

    hoy = hoy or timezone.localdate()
    filas = (marcador_cacheado(cliente, hoy) or {}).get('filas') or []
    llenas = {_zona_de_grupo(f['clave']) for f in filas if f['hechas'] >= f['maximo']}
    por_zona = {}
    for nombre, grupo in EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, completado=True,
        entreno__fecha__gt=hoy - timedelta(days=VENTANA_MARGEN_DIAS), entreno__fecha__lte=hoy,
    ).values_list('nombre_ejercicio', 'grupo_muscular').distinct():
        zona = normalizar_zona(grupo, nombre)
        if zona and nombre not in por_zona.setdefault(zona, []):
            por_zona[zona].append(nombre)
    candidatas = []
    for zona, nombres in por_zona.items():
        if zona in llenas or subir_en_pausa(cliente, zona, hoy) or frena_subir(cliente, zona, hoy):
            continue
        con_margen = {}
        for nombre in nombres:
            ses = _sesiones_con_margen(cliente, nombre, hoy)
            if ses:
                con_margen[nombre] = ses
        if not con_margen or len(con_margen) < min(2, len(nombres)):
            continue
        candidatas.append((len(con_margen), zona, con_margen))
    if not candidatas:
        return None
    _, zona, con_margen = max(candidatas, key=lambda c: (c[0], c[1]))
    return {'zona': zona, 'nombre_zona': NOMBRES_ZONA.get(zona, zona.title()), 'ejercicios': con_margen}


def _texto_propuesta_margen(d):
    nombre, ses = next(iter(d['ejercicios'].items()))
    rpes = ', '.join(_kg(s['rpe']) for s in ses)
    pedido = _kg(ses[-1]['pedido'])
    lista = ' y '.join(list(d['ejercicios'])[:MAX_EJERCICIOS])
    return (
        f"{d['nombre_zona']}: en tus últimas {len(ses)} sesiones de {nombre} terminaste a RPE {rpes} "
        f"cuando se pedía {pedido}, sin subir ({_kg(ses[0]['peso'])} kg × {ses[0]['reps']} → "
        f"{_kg(ses[-1]['peso'])} kg × {ses[-1]['reps']}). Te propongo +{SERIES_EXTRA} series semanales de "
        f"{d['nombre_zona']} durante {SEMANAS} semanas; lo mediré en {lista}."
    )


def _enfriada(cliente, zona, hoy):
    from entrenos.models import PropuestaZonaGym
    return PropuestaZonaGym.objects.filter(
        cliente=cliente, zona=zona,
        estado__in=[PropuestaZonaGym.ESTADO_RECHAZADA, PropuestaZonaGym.ESTADO_EVALUADA],
        creada_en__date__gte=hoy - timedelta(days=ENFRIAMIENTO_DIAS),
    ).exists()


def _generar_propuesta_por_encima(cliente, hoy):
    from entrenos.models import EjercicioRealizado, PropuestaZonaGym
    from entrenos.services.evolucion_muscular_service import normalizar_zona

    d = detectar_zona_por_encima(cliente, hoy)
    if d is None or _enfriada(cliente, d['zona'], hoy):
        return None
    ejercicios = []
    for ej in EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, completado=True, entreno__fecha__gte=hoy - timedelta(days=13),
    ).order_by('-entreno__fecha'):
        if (normalizar_zona(getattr(ej, 'grupo_muscular', None), ej.nombre_ejercicio) == d['zona']
                and ej.nombre_ejercicio not in ejercicios):
            ejercicios.append(ej.nombre_ejercicio)
    return PropuestaZonaGym.objects.create(
        cliente=cliente, zona=d['zona'], ejercicios=ejercicios[:MAX_EJERCICIOS],
        series_extra=SERIES_EXTRA, direccion=PropuestaZonaGym.DIRECCION_BAJAR, semanas=SEMANAS,
        deteccion={'motivo': 'por_encima_del_maximo', 'hechas': d['hechas'], 'previas': d['previas'],
                   'minimo': d['minimo'], 'maximo': d['maximo']},
        texto=_texto_propuesta_por_encima(d),
    )


def _generar_propuesta_margen(cliente, hoy):
    from entrenos.models import PropuestaZonaGym

    d = detectar_zona_con_margen(cliente, hoy)
    if d is None or _enfriada(cliente, d['zona'], hoy):
        return None
    return PropuestaZonaGym.objects.create(
        cliente=cliente, zona=d['zona'], ejercicios=list(d['ejercicios'])[:MAX_EJERCICIOS],
        series_extra=SERIES_EXTRA, direccion=PropuestaZonaGym.DIRECCION_SUBIR, semanas=SEMANAS,
        deteccion={'motivo': 'margen_sin_progreso', 'ejercicios': {
            n: [{**s, 'fecha': s['fecha'].isoformat()} for s in ses] for n, ses in d['ejercicios'].items()
        }},
        texto=_texto_propuesta_margen(d),
    )


def generar_propuesta_si_procede(cliente, hoy=None):
    """Crea una propuesta pendiente si hay una zona en retroceso y nada en curso."""
    from entrenos.models import PropuestaZonaGym

    hoy = hoy or timezone.localdate()
    en_curso = PropuestaZonaGym.objects.filter(
        cliente=cliente,
        estado__in=[PropuestaZonaGym.ESTADO_PENDIENTE, PropuestaZonaGym.ESTADO_ACEPTADA],
    )
    if en_curso.exists():
        return None
    # 31-oct-2026: pasarse del máximo dos semanas seguidas va primero, y una
    # zona así nunca recibe más series aunque retroceda.
    propuesta = _generar_propuesta_por_encima(cliente, hoy)
    if propuesta is not None:
        return propuesta
    deteccion = detectar_zona_en_retroceso(cliente, hoy)
    if deteccion is not None:
        # 24-oct-2026: no subir volumen a una zona que la última vez dolió,
        # aunque retroceda.
        from entrenos.services.sensacion_zona_service import frena_subir
        if frena_subir(cliente, deteccion['zona'], hoy) or deteccion['zona'] in zonas_por_encima_del_maximo(cliente, hoy):
            deteccion = None
    if deteccion is None:
        return _generar_propuesta_margen(cliente, hoy) or _generar_propuesta_bajar(cliente, hoy)
    reciente = PropuestaZonaGym.objects.filter(
        cliente=cliente, zona=deteccion['zona'],
        estado__in=[PropuestaZonaGym.ESTADO_RECHAZADA, PropuestaZonaGym.ESTADO_EVALUADA],
        creada_en__date__gte=hoy - timedelta(days=ENFRIAMIENTO_DIAS),
    )
    if reciente.exists():
        return None
    datos = {
        'pct': deteccion['pct'],
        'ejercicios': [
            {
                'ejercicio': e['ejercicio'], 'pct': e['pct'],
                'antes': {'peso_kg': e['antes']['peso_kg'], 'reps': e['antes']['reps'],
                          'fecha': e['antes']['fecha'].isoformat()},
                'ahora': {'peso_kg': e['ahora']['peso_kg'], 'reps': e['ahora']['reps'],
                          'fecha': e['ahora']['fecha'].isoformat()},
            }
            for e in deteccion['ejercicios']
        ],
    }
    return PropuestaZonaGym.objects.create(
        cliente=cliente,
        zona=deteccion['zona'],
        ejercicios=[e['ejercicio'] for e in deteccion['ejercicios']],
        series_extra=SERIES_EXTRA,
        direccion=PropuestaZonaGym.DIRECCION_SUBIR,
        semanas=SEMANAS,
        deteccion=datos,
        texto=_texto_propuesta(deteccion),
    )


def _generar_propuesta_bajar(cliente, hoy):
    from entrenos.models import PropuestaZonaGym

    deteccion = detectar_zona_con_fatiga(cliente, hoy)
    if deteccion is None:
        return _generar_propuesta_bajar_por_sensaciones(cliente, hoy)
    if PropuestaZonaGym.objects.filter(
        cliente=cliente, zona=deteccion['zona'],
        estado__in=[PropuestaZonaGym.ESTADO_RECHAZADA, PropuestaZonaGym.ESTADO_EVALUADA],
        creada_en__date__gte=hoy - timedelta(days=ENFRIAMIENTO_DIAS),
    ).exists():
        return None
    return PropuestaZonaGym.objects.create(
        cliente=cliente,
        zona=deteccion['zona'],
        ejercicios=deteccion['ejercicios_fatiga'][:MAX_EJERCICIOS],
        series_extra=SERIES_EXTRA,
        direccion=PropuestaZonaGym.DIRECCION_BAJAR,
        semanas=SEMANAS,
        deteccion={'ejercicios_fatiga': deteccion['ejercicios_fatiga']},
        texto=_texto_propuesta_bajar(deteccion),
    )


def _generar_propuesta_bajar_por_sensaciones(cliente, hoy):
    """24-oct-2026: molestia repetida en una zona → −2 series (agujetas fuera desde el 31-oct)."""
    from entrenos.models import EjercicioRealizado, PropuestaZonaGym
    from entrenos.services.evolucion_muscular_service import normalizar_zona
    from entrenos.services.sensacion_zona_service import zona_para_bajar

    deteccion = zona_para_bajar(cliente, hoy)
    if deteccion is None:
        return None
    if PropuestaZonaGym.objects.filter(
        cliente=cliente, zona=deteccion['zona'],
        estado__in=[PropuestaZonaGym.ESTADO_RECHAZADA, PropuestaZonaGym.ESTADO_EVALUADA],
        creada_en__date__gte=hoy - timedelta(days=ENFRIAMIENTO_DIAS),
    ).exists():
        return None
    ejercicios = []
    for ej in EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, completado=True,
        entreno__fecha__gte=hoy - timedelta(days=14),
    ).order_by('-entreno__fecha'):
        if normalizar_zona(getattr(ej, 'grupo_muscular', None), ej.nombre_ejercicio) == deteccion['zona']:
            if ej.nombre_ejercicio not in ejercicios:
                ejercicios.append(ej.nombre_ejercicio)
    fechas = ', '.join(f.strftime('%d/%m') for f in deteccion['fechas'])
    return PropuestaZonaGym.objects.create(
        cliente=cliente,
        zona=deteccion['zona'],
        ejercicios=ejercicios[:MAX_EJERCICIOS],
        series_extra=SERIES_EXTRA,
        direccion=PropuestaZonaGym.DIRECCION_BAJAR,
        semanas=SEMANAS,
        deteccion={'sensaciones': deteccion['sesiones'], 'fechas': [f.isoformat() for f in deteccion['fechas']]},
        texto=(
            f"{deteccion['nombre_zona']}: molestia articular en {deteccion['sesiones']} "
            f"sesiones en 14 días ({fechas}). Te propongo −{SERIES_EXTRA} series semanales de "
            f"{deteccion['nombre_zona']} durante {SEMANAS} semanas para recuperar margen."
        ),
    )


class PropuestaNoVigente(ValueError):
    pass


@transaction.atomic
def aceptar_propuesta(propuesta, hoy=None):
    """Se aplica desde mañana para no cambiar una sesión ya decidida hoy."""
    from entrenos.models import PropuestaZonaGym

    p = PropuestaZonaGym.objects.select_for_update().get(pk=propuesta.pk)
    if p.estado != PropuestaZonaGym.ESTADO_PENDIENTE:
        raise PropuestaNoVigente('La propuesta ya no está pendiente.')
    hoy = hoy or timezone.localdate()
    p.estado = PropuestaZonaGym.ESTADO_ACEPTADA
    p.inicio = hoy + timedelta(days=1)
    p.fin = p.inicio + timedelta(days=p.semanas * 7 - 1)
    p.respondida_en = timezone.now()
    p.save(update_fields=['estado', 'inicio', 'fin', 'respondida_en'])
    return p


@transaction.atomic
def rechazar_propuesta(propuesta):
    from entrenos.models import PropuestaZonaGym

    p = PropuestaZonaGym.objects.select_for_update().get(pk=propuesta.pk)
    if p.estado != PropuestaZonaGym.ESTADO_PENDIENTE:
        raise PropuestaNoVigente('La propuesta ya no está pendiente.')
    p.estado = PropuestaZonaGym.ESTADO_RECHAZADA
    p.respondida_en = timezone.now()
    p.save(update_fields=['estado', 'respondida_en'])
    return p


# ── Pausa por descarga (2-nov-2026) ──────────────────────────────────────
# Una semana de descarga dentro de una propuesta no le suma series (en la
# descarga se baja el volumen de todo) y tampoco cuenta como una de sus
# semanas: la propuesta se alarga una semana por cada descarga. Antes
# isquios seguía "semana 3 de 4" en plena descarga, con +2 series, y la
# comprobación final iba a comparar unas semanas con una descarga dentro.

def _lunes_descarga(cliente_id, desde, hasta):
    from entrenos.models import SemanaPlanGym

    return set(SemanaPlanGym.objects.filter(
        cliente_id=cliente_id, descarga=True, lunes__gte=desde - timedelta(days=6), lunes__lte=hasta,
    ).values_list('lunes', flat=True))


def fin_con_pausas(p):
    """Fin de la propuesta contando una semana más por cada descarga dentro."""
    if not p.inicio:
        return p.fin
    base = p.inicio + timedelta(days=p.semanas * 7 - 1)
    fin = base
    for _ in range(4):
        n = len(_lunes_descarga(p.cliente_id, p.inicio, fin))
        nuevo = base + timedelta(days=7 * n)
        if nuevo == fin:
            break
        fin = nuevo
    return fin


def sincronizar_pausas(cliente):
    """Deja ``fin`` de las propuestas aceptadas al día con sus pausas por descarga."""
    from entrenos.models import PropuestaZonaGym

    try:
        for p in PropuestaZonaGym.objects.filter(
            cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA, inicio__isnull=False,
        ):
            fin = fin_con_pausas(p)
            if fin and fin != p.fin:
                p.fin = fin
                p.save(update_fields=['fin'])
    except Exception:  # noqa: BLE001 — nunca romper una pantalla por esto
        import logging
        logging.getLogger(__name__).exception('[propuesta] pausas por descarga')


def en_pausa_por_descarga(cliente, hoy):
    from entrenos.services.sesion_descarga_service import semana_plan_descarga

    try:
        return semana_plan_descarga(cliente.id, hoy)
    except Exception:  # noqa: BLE001
        return False


def semana_de_propuesta(p, hoy):
    """Semana de la propuesta que es hoy, sin contar las de descarga."""
    if not p.inicio or hoy < p.inicio:
        return None
    lunes_hoy = hoy - timedelta(days=hoy.weekday())
    previas = {l for l in _lunes_descarga(p.cliente_id, p.inicio, hoy) if l < lunes_hoy}
    return max(1, min(p.semanas, (hoy - p.inicio).days // 7 + 1 - len(previas)))


def propuesta_activa(cliente, hoy=None):
    """La propuesta aceptada en vigor hoy, o None."""
    from entrenos.models import PropuestaZonaGym

    hoy = hoy or timezone.localdate()
    sincronizar_pausas(cliente)
    return PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA,
        inicio__lte=hoy, fin__gte=hoy,
    ).order_by('-inicio').first()


def propuesta_visible(cliente, hoy=None):
    """Lo que Ahora debe enseñar: una propuesta por responder o una en curso."""
    from entrenos.models import PropuestaZonaGym

    hoy = hoy or timezone.localdate()
    pendiente = PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_PENDIENTE,
    ).order_by('-creada_en').first()
    if pendiente:
        return {'tipo': 'pendiente', 'propuesta': pendiente}
    sincronizar_pausas(cliente)
    aceptada = PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA, fin__gte=hoy,
    ).order_by('-inicio').first()
    if aceptada:
        semana = semana_de_propuesta(aceptada, hoy)
        pausa = bool(semana) and en_pausa_por_descarga(cliente, hoy)
        return {'tipo': 'en_curso', 'propuesta': aceptada, 'semana': semana, 'pausa': pausa}
    return None


def aplicar_a_ejercicios(cliente, ejercicios, hoy, cambios, es_descarga=False):
    """Deja constancia del ajuste en la sesión (el volumen ya lo puso el planificador).

    Desde el paso 5 la propuesta cambia las series semanales de la zona dentro
    del planificador (volumen_grupo_service); aquí ya no se suman series a
    ejercicios sueltos, solo se explica el cambio si la zona sale hoy.
    """
    if es_descarga or en_pausa_por_descarga(cliente, hoy):
        return
    p = propuesta_activa(cliente, hoy)
    if p is None:
        return
    de_la_zona = [ej for ej in ejercicios if ej.get('grupo_muscular') == p.zona]
    if not de_la_zona:
        return
    signo = '−' if p.direccion == 'bajar' else '+'
    for ej in de_la_zona:
        ej['propuesta_zona_id'] = p.pk
        # 17-oct-2026: que se vea en el briefing (antes no salía en ninguna pantalla).
        ej['propuesta_zona_texto'] = (
            f'Cuenta para la propuesta: {signo}{SERIES_EXTRA} series semanales de '
            f'{p.nombre_zona.lower()} hasta el {p.fin:%d/%m}.'
        )
        # 10-nov-2026 (nota 7): si hoy el ejercicio va recortado (fútbol), no se
        # promete el volumen entero: se comprobará con las series que hagas.
        try:
            _plan, _hoy_s = int(ej.get('series_plan') or 0), int(ej.get('series') or 0)
        except (TypeError, ValueError):
            _plan = _hoy_s = 0
        if _plan and _hoy_s and _hoy_s < _plan:
            ej['propuesta_zona_texto'] = (
                f'Hoy llevas {_hoy_s} series y no {_plan}, por el fútbol: la propuesta de '
                f'{signo}{SERIES_EXTRA} series semanales de {p.nombre_zona.lower()} se comprobará '
                f'con las series que hagas de verdad.'
            )
    cambios.append({
        'tipo': 'propuesta_zona',
        'ejercicio_original': de_la_zona[0].get('nombre'),
        'ejercicio_nuevo': None,
        'razon': (f'{signo}{SERIES_EXTRA} series semanales de {p.nombre_zona} por la propuesta '
                  f'aceptada (hasta el {p.fin:%d/%m}).'),
    })


def evaluar_propuestas_vencidas(cliente, hoy=None):
    """Regla 4: al terminar, compara sus semanas con las anteriores y lo dice."""
    from entrenos.models import PropuestaZonaGym
    from entrenos.services.evolucion_muscular_service import comparar_ejercicios

    hoy = hoy or timezone.localdate()
    sincronizar_pausas(cliente)
    evaluadas = []
    for p in PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA, fin__lt=hoy,
    ):
        objetivo = {_plano(n) for n in p.ejercicios}
        # 2-nov-2026: la ventana es la de la propuesta de verdad (con sus
        # semanas de pausa), y si los ejercicios elegidos ya no están en el
        # programa (cambió el bloque), se mide con los de la zona que sí se
        # hicieron.
        dias = ((p.fin - p.inicio).days + 1) if p.inicio else p.semanas * 7
        comparables = [
            # 8-nov-2026: solo sesiones comparables (sin descarga y en el mismo
            # tramo de reps): el bloque de fuerza cambia reps y esfuerzo.
            e for e in comparar_ejercicios(cliente, p.fin, dias, estricto=True)
            if e['pct'] is not None and not e['dudoso']
        ]
        filas = [e for e in comparables if _plano(e['ejercicio']) in objetivo]
        if not filas:
            filas = [e for e in comparables if e.get('zona') == p.zona and not e.get('ligero')]
        if not filas:
            resultado = 'neutra'
            notas = ('Sin evidencia suficiente: no hubo sesiones comparables de esos ejercicios '
                     '(mismo tramo de reps y fuera de la descarga) antes y durante la propuesta')
        else:
            pct = round(median(e['pct'] for e in filas), 1)
            pct_txt = f"{'+' if pct > 0 else ''}{str(pct).replace('.', ',')} %"
            if p.direccion == 'bajar':
                # Bajar volumen funciona si se recupera margen sin perder fuerza.
                if pct >= -2:
                    resultado = 'validada'
                    notas = f'Menos volumen sin perder fuerza ({pct_txt} frente a las {p.semanas} semanas anteriores)'
                else:
                    resultado = 'fallida'
                    notas = f'Con menos volumen la fuerza bajó: {pct_txt} frente a las {p.semanas} semanas anteriores'
            elif pct >= 2:
                resultado = 'validada'
                notas = f'Fuerza estimada {pct_txt} frente a las {p.semanas} semanas anteriores'
            elif pct <= -5:
                resultado = 'fallida'
                notas = f'Siguió cayendo: {pct_txt} frente a las {p.semanas} semanas anteriores'
            else:
                resultado = 'neutra'
                notas = f'Se mantuvo ({pct_txt} frente a las {p.semanas} semanas anteriores)'
        p.estado = PropuestaZonaGym.ESTADO_EVALUADA
        p.resultado = resultado
        p.notas_resultado = notas
        p.evaluada_en = timezone.now()
        p.save(update_fields=['estado', 'resultado', 'notas_resultado', 'evaluada_en'])
        evaluadas.append(p)
    return evaluadas


def frase_evaluacion(p):
    """Para "Lo que decidí y si funcionó"."""
    from entrenos.services.aprendizaje_decisiones_service import VEREDICTO
    veredicto = VEREDICTO.get(p.resultado, '')
    signo = '−' if p.direccion == 'bajar' else '+'
    frase = (f'{p.nombre_zona}: propuse {signo}{SERIES_EXTRA} series semanales durante '
             f'{p.semanas} semanas y aceptaste.')
    if veredicto:
        frase += f' {veredicto[:1].upper()}{veredicto[1:]}: {p.notas_resultado[:1].lower()}{p.notas_resultado[1:]}.'
    return frase


def tras_guardar_sesion(cliente, hoy=None):
    """Punto de enganche tras cerrar un entreno: evaluar lo vencido y detectar."""
    evaluar_propuestas_vencidas(cliente, hoy)
    return generar_propuesta_si_procede(cliente, hoy)

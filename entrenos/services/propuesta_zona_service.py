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
# 18-nov-2026 (decisión de David): las propuestas de SUBIR volumen quedan en espera
# hasta justificar cómo se decide el ajuste. Dos ejercicios o tres sesiones
# comparables pueden apoyar una tendencia (se muestra en Memoria), pero no
# bastan por sí solos para proponer más series. Las de bajar siguen como estaban.
SUBIR_VOLUMEN_ACTIVO = False

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
    from entrenos.services.sesion_descarga_service import es_sesion_descarga, periodos_descarga

    periodos = periodos_descarga(cliente.pk)
    por_zona = {}
    for log in GymDecisionLog.objects.filter(
        cliente=cliente, motivo_codigo__in=_MOTIVOS_FATIGA,
        fecha_creacion__date__gte=hoy - timedelta(days=14), fecha_creacion__date__lte=hoy,
    ).select_related('entreno_origen'):
        nombre = log.ejercicio
        # 18-nov-2026: un RPE alto o un fallo en una sesión de descarga no es evidencia de fatiga
        # acumulada (se compara con lo previsto para esa semana, no con el bloque).
        if log.entreno_origen is not None and es_sesion_descarga(log.entreno_origen, nombre, periodos):
            continue
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
    """{zona: (series_esta, series_anterior, plan, umbral)} por encima del plan dos semanas seguidas.

    18-nov-2026: la referencia es lo que pide el plan de la semana (ya no un
    «máximo útil» de 10 + 4). Esta semana cuenta lo hecho y lo que aportan las
    sesiones pendientes; la anterior, la semana completa de lunes a domingo
    (contra el plan de esta, que suele ser el mismo bloque). Se pasa si supera
    el plan en ``MARGEN_SOBRE_PLAN`` series o más.
    """
    from entrenos.services.marcador_semanal_service import (
        MARGEN_SOBRE_PLAN, marcador_cacheado, series_hechas_detalle,
    )

    hoy = hoy or timezone.localdate()
    marcador = marcador_cacheado(cliente, hoy) or {}
    filas = marcador.get('filas') or []
    lunes = hoy - timedelta(days=hoy.weekday())
    # Una semana de descarga (esta o la anterior) no es evidencia de que el plan se pase.
    if marcador.get('descarga') or (lunes - timedelta(days=7)) in _lunes_descarga(
            cliente.pk, lunes - timedelta(days=7), lunes - timedelta(days=7)):
        return {}
    anterior = series_hechas_detalle(cliente, lunes - timedelta(days=7), lunes - timedelta(days=1))[0]
    altas = {}
    for f in filas:
        zona = _zona_de_grupo(f['clave'])
        previas = anterior.get(f['clave'], 0)
        umbral = f['plan'] + MARGEN_SOBRE_PLAN
        if zona and f['proyectadas'] > umbral and previas > umbral:
            altas[zona] = (f['proyectadas'], previas, f['plan'], umbral)
    return altas


def _num(valor):
    return str(int(valor)) if float(valor).is_integer() else f'{valor:g}'.replace('.', ',')


def detectar_zona_por_encima(cliente, hoy=None):
    """La zona que más se pasa del plan (dos semanas seguidas), o None."""
    from entrenos.services.evolucion_muscular_service import NOMBRES_ZONA

    altas = zonas_por_encima_del_maximo(cliente, hoy)
    if not altas:
        return None
    zona, (h, previas, plan, umbral) = max(altas.items(), key=lambda kv: (kv[1][0] - kv[1][3], kv[0]))
    return {'zona': zona, 'nombre_zona': NOMBRES_ZONA.get(zona, zona.title()),
            'hechas': h, 'previas': previas, 'plan': plan, 'umbral': umbral}


def _texto_propuesta_por_encima(d):
    return (
        f"{d['nombre_zona']}: {_num(d['hechas'])} series esta semana (hechas y previstas) y "
        f"{_num(d['previas'])} la anterior, frente a las {_num(d['plan'])} que pide el plan de la semana. "
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
    from entrenos.services.marcador_semanal_service import MARGEN_SOBRE_PLAN, marcador_cacheado
    from entrenos.services.sensacion_zona_service import frena_subir

    hoy = hoy or timezone.localdate()
    filas = (marcador_cacheado(cliente, hoy) or {}).get('filas') or []
    llenas = {_zona_de_grupo(f['clave']) for f in filas
              if f['proyectadas'] >= f['plan'] + MARGEN_SOBRE_PLAN}
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
        deteccion={'motivo': 'por_encima_del_plan', 'hechas': d['hechas'], 'previas': d['previas'],
                   'plan': d['plan'], 'umbral': d['umbral']},
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
    if not SUBIR_VOLUMEN_ACTIVO:
        # Una propuesta de subir en espera no bloquea las demás.
        en_curso = en_curso.exclude(
            estado=PropuestaZonaGym.ESTADO_PENDIENTE, direccion=PropuestaZonaGym.DIRECCION_SUBIR)
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
    if not SUBIR_VOLUMEN_ACTIVO:
        # 18-nov-2026: sin propuestas de subir hasta justificar la regla de decisión.
        return _generar_propuesta_bajar(cliente, hoy)
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
    if p.direccion == PropuestaZonaGym.DIRECCION_SUBIR and not SUBIR_VOLUMEN_ACTIVO:
        raise PropuestaNoVigente('Subir volumen está en espera: aún no está justificado cómo se decide el ajuste.')
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


from core.perfil_tramos import tramo_de


@tramo_de('propuesta_visible')
def propuesta_visible(cliente, hoy=None):
    """Lo que Ahora debe enseñar: una propuesta por responder o una en curso."""
    from entrenos.models import PropuestaZonaGym

    hoy = hoy or timezone.localdate()
    pendientes = PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_PENDIENTE,
    )
    if not SUBIR_VOLUMEN_ACTIVO:
        # Las de subir quedan pendientes en la base de datos, sin enseñarse ni poder aceptarse.
        pendientes = pendientes.exclude(direccion=PropuestaZonaGym.DIRECCION_SUBIR)
    pendiente = pendientes.order_by('-creada_en').first()
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


def sesiones_con_ajuste_registrado(cliente, p):
    """Fechas de las sesiones de la ventana cuya versión guardada recoge esta propuesta.

    18-nov-2026 (nota 49): sin ese registro no consta que la propuesta llegara a
    aplicarse, y su efecto no puede darse por comprobado.
    """
    from entrenos.models import EntrenoRealizado

    if not p.inicio:
        return []
    fechas = []
    entrenos = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__gte=p.inicio, fecha__lte=p.fin,
    ).select_related('gym_decision_version').order_by('fecha')
    for e in entrenos:
        snap = getattr(getattr(e, 'gym_decision_version', None), 'snapshot', None) or {}
        for ej in (snap.get('entrenamiento') or {}).get('ejercicios') or []:
            if ej.get('propuesta_zona_id') == p.pk:
                fechas.append(e.fecha)
                break
    return fechas


def _dato_txt(d):
    peso = f"{d['peso_kg']:g}".replace('.', ',')
    return f"{peso} kg × {d['reps']} ({d['fecha']:%d/%m})"


def evolucion_observada(filas):
    """«Buenos días: 40 kg × 10 (16/09) → 50 kg × 10 (12/11), +36,4 %» por ejercicio."""
    partes = []
    for e in filas:
        antes, ahora = e.get('antes'), e.get('ahora')
        if not antes or not ahora or e.get('pct') is None:
            continue
        pct = f"{'+' if e['pct'] > 0 else ''}{str(round(e['pct'], 1)).replace('.', ',')} %"
        partes.append(f"{e['ejercicio']}: {_dato_txt(antes)} → {_dato_txt(ahora)}, {pct}")
    return '; '.join(partes)


def _filas_dentro_de_la_ventana(filas, p):
    """Las que miden de verdad la propuesta: antes de que empezara y durante ella."""
    return [e for e in filas
            if e.get('antes') and e.get('ahora') and p.inicio
            and e['antes']['fecha'] < p.inicio <= e['ahora']['fecha'] <= p.fin]


def resultado_propuesta(cliente, p):
    """(resultado, notas) de una propuesta ya vencida con la regla vigente (sin guardar nada)."""
    from entrenos.services.evolucion_muscular_service import comparar_ejercicios

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
    medida = False
    filas = [e for e in comparables if _plano(e['ejercicio']) in objetivo]
    if not filas:
        filas = [e for e in comparables if e.get('zona') == p.zona and not e.get('ligero')]
    if not filas:
        resultado = 'neutra'
        notas = ('Sin evidencia suficiente: no hubo sesiones comparables de esos ejercicios '
                 '(mismo tramo de reps y fuera de la descarga) antes y durante la propuesta')
    elif not sesiones_con_ajuste_registrado(cliente, p):
        # 18-nov-2026 (nota 49): no consta que se aplicara; solo se cuenta lo observado.
        resultado = 'neutra'
        notas = (f"Resultado inconcluso: no consta que la propuesta ({p.inicio:%d/%m}–{p.fin:%d/%m}) "
                 f"se aplicara en ninguna sesión, así que su efecto queda sin determinar. "
                 f"Evolución observada: {evolucion_observada(filas)}")
    elif not _filas_dentro_de_la_ventana(filas, p):
        resultado = 'neutra'
        notas = (f"Resultado inconcluso: las marcas comparadas no caen antes y durante la propuesta "
                 f"({p.inicio:%d/%m}–{p.fin:%d/%m}), así que su efecto queda sin determinar. "
                 f"Evolución observada: {evolucion_observada(filas)}")
    else:
        filas = _filas_dentro_de_la_ventana(filas, p)
        medida = True
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
    if medida:
        notas += f". Datos: {evolucion_observada(filas)}"
    return resultado, notas


def _guardar_aplicacion(cliente, p):
    """``deteccion['aplicacion_registrada']``: cuántas sesiones recogen la propuesta y entre qué fechas."""
    fechas = sesiones_con_ajuste_registrado(cliente, p)
    deteccion = dict(p.deteccion or {})
    deteccion['aplicacion_registrada'] = {
        'sesiones': len(fechas),
        'desde': fechas[0].isoformat() if fechas else None,
        'hasta': fechas[-1].isoformat() if fechas else None,
    }
    p.deteccion = deteccion
    p.save(update_fields=['deteccion'])


def reevaluar_propuesta(cliente, p, motivo, hoy=None, aplicar=True):
    """Vuelve a evaluar una propuesta ya evaluada con la regla vigente (18-nov-2026, nota 49).

    El resultado anterior no se pierde: queda en ``deteccion['evaluacion_anterior']`` con la
    fecha y el motivo de la corrección, y ``frase_evaluacion`` lo dice. Devuelve
    ``(resultado, notas, cambio)``; con ``aplicar=False`` no guarda nada.
    """
    resultado, notas = resultado_propuesta(cliente, p)
    cambio = (resultado, notas) != (p.resultado, p.notas_resultado)
    deteccion = dict(p.deteccion or {})
    previa = deteccion.get('evaluacion_anterior')
    # El motivo también cuenta: repetir la corrección con otro motivo (mismo resultado) lo actualiza.
    motivo_nuevo = bool(previa) and previa.get('motivo') != motivo
    if aplicar and (cambio or motivo_nuevo):
        hoy = hoy or timezone.localdate()
        if previa:
            # 18-nov-2026: el resultado original (el primero) no se pisa nunca; la corrección
            # anterior pasa al historial y la vigente lleva el motivo más reciente.
            historial = list(deteccion.get('historial_correcciones') or [])
            historial.append({
                'corregida_el': previa.get('corregida_el'), 'motivo': previa.get('motivo'),
                'resultado': p.resultado, 'notas': p.notas_resultado,
            })
            deteccion['historial_correcciones'] = historial
            deteccion['evaluacion_anterior'] = dict(previa, corregida_el=hoy.isoformat(), motivo=motivo)
        else:
            deteccion['evaluacion_anterior'] = {
                'resultado': p.resultado, 'notas': p.notas_resultado,
                'evaluada_en': p.evaluada_en.isoformat() if p.evaluada_en else None,
                'corregida_el': hoy.isoformat(), 'motivo': motivo,
            }
        p.deteccion = deteccion
        p.resultado = resultado
        p.notas_resultado = notas
        p.save(update_fields=['deteccion', 'resultado', 'notas_resultado'])
    # 18-nov-2026: la aplicación registrada se guarda con la evaluación para citarla.
    if aplicar and 'aplicacion_registrada' not in (p.deteccion or {}):
        _guardar_aplicacion(cliente, p)
    return resultado, notas, cambio or motivo_nuevo


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
        resultado, notas = resultado_propuesta(cliente, p)
        p.estado = PropuestaZonaGym.ESTADO_EVALUADA
        p.resultado = resultado
        p.notas_resultado = notas
        p.evaluada_en = timezone.now()
        p.save(update_fields=['estado', 'resultado', 'notas_resultado', 'evaluada_en'])
        _guardar_aplicacion(cliente, p)
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
        notas = (p.notas_resultado or '').strip()
        if notas.startswith('Resultado inconcluso:'):
            notas = notas[len('Resultado inconcluso:'):].strip()
        frase += f' {veredicto[:1].upper()}{veredicto[1:]}: {notas[:1].lower()}{notas[1:]}'
        frase = frase.rstrip('.') + '.'
    aplicacion = (p.deteccion or {}).get('aplicacion_registrada') or {}
    if veredicto and p.resultado in ('validada', 'fallida') and aplicacion.get('sesiones'):
        def _d(iso):
            return f'{iso[8:10]}/{iso[5:7]}' if iso else '?'
        frase += (f" Aplicación registrada en {aplicacion['sesiones']} sesiones "
                  f"({_d(aplicacion.get('desde'))}–{_d(aplicacion.get('hasta'))}). "
                  f"Es lo observado durante el periodo: no prueba por sí solo que las series extra lo causaran.")
    revision = (p.deteccion or {}).get('revision')
    if veredicto and p.resultado == 'validada' and revision:
        def _dm(iso):
            return f'{iso[8:10]}/{iso[5:7]}' if iso else '?'
        estado = revision.get('estado') or 'pendiente'
        if estado == 'pendiente':
            frase += (f" El ajuste se mantiene hasta el {_dm(revision.get('fecha'))}; "
                      f"después queda pendiente de tu decisión.")
        elif estado == 'prolongada':
            frase += f" Lo prolongaste hasta el {_dm(revision.get('hasta'))}."
        elif estado == 'retirada':
            frase += ' Lo retiraste.'
    anterior = (p.deteccion or {}).get('evaluacion_anterior')
    if anterior:
        antes = VEREDICTO.get(anterior.get('resultado'), '')
        fecha = (anterior.get('corregida_el') or '')[8:10] + '/' + (anterior.get('corregida_el') or '')[5:7]
        frase += (f" Corregido el {fecha}: antes constaba «{antes}» ({(anterior.get('notas') or '').rstrip('.')}). "
                  f"Motivo: {anterior.get('motivo')}")
    return frase


def tras_guardar_sesion(cliente, hoy=None):
    """Punto de enganche tras cerrar un entreno: evaluar lo vencido y detectar."""
    evaluar_propuestas_vencidas(cliente, hoy)
    return generar_propuesta_si_procede(cliente, hoy)


def fijar_revision(p, fecha, motivo, hoy=None, aplicar=True):
    """Fija el límite de un ajuste validado: vale hasta ``fecha`` y luego queda pendiente de decisión.

    18-nov-2026: sustituye al mantenimiento automático de 182 días para esa propuesta. Devuelve la
    revisión resultante; con ``aplicar=False`` no guarda nada.
    """
    if p.resultado != 'validada':
        raise ValueError('Solo una propuesta validada tiene un ajuste que revisar.')
    hoy = hoy or timezone.localdate()
    revision = {
        'fecha': fecha.isoformat(), 'estado': 'pendiente', 'fijada_el': hoy.isoformat(), 'motivo': motivo,
        # Comportamiento sin resolver que debe tratarse en la revisión (no cambia nada hoy).
        'pendientes': [
            'Descarga: el ajuste validado no se pausa en la semana de descarga y queda en +1; '
            'decidir si debe pausarse.',
        ],
    }
    if aplicar:
        deteccion = dict(p.deteccion or {})
        deteccion['revision'] = revision
        p.deteccion = deteccion
        p.save(update_fields=['deteccion'])
    return revision


def decidir_revision(p, decision, motivo, hasta=None, hoy=None, aplicar=True):
    """Decisión explícita sobre un ajuste en revisión: ``prolongar`` (hasta una fecha) o ``retirar``."""
    revision = dict((p.deteccion or {}).get('revision') or {})
    if not revision:
        raise ValueError('La propuesta no tiene una revisión fijada.')
    if decision not in ('prolongar', 'retirar'):
        raise ValueError('La decisión debe ser prolongar o retirar.')
    if decision == 'prolongar' and not hasta:
        raise ValueError('Para prolongar hace falta una fecha límite.')
    hoy = hoy or timezone.localdate()
    historial = list(revision.get('decisiones') or [])
    historial.append({'decidida_el': hoy.isoformat(), 'decision': decision, 'motivo': motivo,
                      'hasta': hasta.isoformat() if hasta else None})
    revision.update({'estado': 'prolongada' if decision == 'prolongar' else 'retirada',
                     'hasta': hasta.isoformat() if hasta else None, 'decisiones': historial})
    if aplicar:
        deteccion = dict(p.deteccion or {})
        deteccion['revision'] = revision
        p.deteccion = deteccion
        p.save(update_fields=['deteccion'])
    return revision

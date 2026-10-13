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
"""

from datetime import timedelta
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
    zonas = [z for z, estado in (evolucion.get('estado_por_zona') or {}).items() if estado == 'retrocede']
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
    deteccion = detectar_zona_en_retroceso(cliente, hoy)
    if deteccion is None:
        return _generar_propuesta_bajar(cliente, hoy)
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
        return None
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


def propuesta_activa(cliente, hoy=None):
    """La propuesta aceptada en vigor hoy, o None."""
    from entrenos.models import PropuestaZonaGym

    hoy = hoy or timezone.localdate()
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
    aceptada = PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA, fin__gte=hoy,
    ).order_by('-inicio').first()
    if aceptada:
        semana = None
        if aceptada.inicio and hoy >= aceptada.inicio:
            semana = min(aceptada.semanas, (hoy - aceptada.inicio).days // 7 + 1)
        return {'tipo': 'en_curso', 'propuesta': aceptada, 'semana': semana}
    return None


def aplicar_a_ejercicios(cliente, ejercicios, hoy, cambios, es_descarga=False):
    """Deja constancia del ajuste en la sesión (el volumen ya lo puso el planificador).

    Desde el paso 5 la propuesta cambia las series semanales de la zona dentro
    del planificador (volumen_grupo_service); aquí ya no se suman series a
    ejercicios sueltos, solo se explica el cambio si la zona sale hoy.
    """
    if es_descarga:
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
    evaluadas = []
    for p in PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA, fin__lt=hoy,
    ):
        objetivo = {_plano(n) for n in p.ejercicios}
        filas = [
            e for e in comparar_ejercicios(cliente, p.fin, p.semanas * 7)
            if _plano(e['ejercicio']) in objetivo and e['pct'] is not None and not e['dudoso']
        ]
        if not filas:
            resultado = 'neutra'
            notas = 'No hubo sesiones suficientes de esos ejercicios para comparar'
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

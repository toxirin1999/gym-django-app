"""Revisión de bloque: la regla 4 del rumbo a escala de semanas (14-oct-2026).

Un bloque de la periodización (p. ej. "Hipertrofia — Acumulación", 7 semanas)
se cierra cuando la semana del plan pasa de su última semana (normalmente al
entrar en la descarga que lo sigue). Entonces se cuenta, con el dato:

- **Qué se entrenó**: sesiones hechas frente a las previstas.
- **Qué pasó con la fuerza**: cambio por zona durante el bloque frente a las
  mismas semanas anteriores (``calcular_evolucion_por_grupo``).
- **El objetivo por defecto, equilibrar**: las zonas que retrocedían al
  empezar (90 días) ¿se recuperaron?
- **Qué decidió el plan y si funcionó**: veredictos de las decisiones y de las
  propuestas por zona evaluadas en el bloque.
- **Qué cambia**: las zonas que siguen retrocediendo son el foco siguiente.

Las semanas de descarga intercaladas no parten el bloque. Se calcula al vuelo
desde ``SemanaPlanGym``; no persiste nada.
"""

from datetime import timedelta

from django.utils import timezone


def _bloques_de_registros(registros, periodizacion):
    """Agrupa semanas consecutivas del mismo bloque de contenido.

    Devuelve [{'bloque', 'inicio', 'fin', 'semanas_reales', 'ultima_semana_plan'}].
    """
    from entrenos.services.periodizacion_dinamica_service import bloque_para_semana

    grupos = []
    for r in registros:
        bloque, _ = bloque_para_semana({'semana_plan': r.semana_plan, 'descarga': False}, periodizacion)
        if bloque is None or bloque.get('fase') == 'descarga':
            if grupos:
                grupos[-1]['fin'] = r.lunes + timedelta(days=6)
                grupos[-1]['descargas'] += 1
            continue
        if grupos and grupos[-1]['bloque'].get('nombre') == bloque.get('nombre') and not grupos[-1]['cerrado']:
            g = grupos[-1]
        else:
            if grupos:
                grupos[-1]['cerrado'] = True
            g = {'bloque': bloque, 'inicio': r.lunes, 'fin': None, 'semanas_reales': 0,
                 'descargas': 0, 'cerrado': False, 'ultima_semana_plan': r.semana_plan}
            grupos.append(g)
        g['semanas_reales'] += 1
        g['fin'] = r.lunes + timedelta(days=6)
        g['ultima_semana_plan'] = r.semana_plan
    return grupos


def estado_bloques(cliente, hoy=None):
    """{'en_curso': {...} | None, 'ultimo_cerrado': {...} | None}."""
    from entrenos.models import SemanaPlanGym
    from entrenos.services.periodizacion_dinamica_service import _periodizacion, lunes_de

    hoy = hoy or timezone.localdate()
    registros = list(SemanaPlanGym.objects.filter(cliente=cliente, lunes__lte=lunes_de(hoy)).order_by('lunes'))
    if not registros:
        return {'en_curso': None, 'ultimo_cerrado': None}
    periodizacion = _periodizacion()
    grupos = _bloques_de_registros(registros, periodizacion)
    actual = registros[-1]
    en_curso, ultimo_cerrado = None, None
    for g in grupos:
        semanas_bloque = g['bloque'].get('semanas') or []
        # Cerrado si ya empezó otro bloque, o si la semana actual del plan va
        # más allá de su última semana (normalmente, la descarga que lo sigue).
        if g is not grupos[-1] or (semanas_bloque and actual.semana_plan > max(semanas_bloque)):
            ultimo_cerrado = g
        else:
            en_curso = g
    if en_curso:
        semanas_bloque = en_curso['bloque'].get('semanas') or []
        posicion = semanas_bloque.index(actual.semana_plan) + 1 if actual.semana_plan in semanas_bloque else None
        en_curso = {
            'nombre': en_curso['bloque'].get('nombre'),
            'semana': posicion,
            'de': len(semanas_bloque),
            'descarga_ahora': actual.descarga,
            'inicio': en_curso['inicio'],
        }
    return {'en_curso': en_curso, 'ultimo_cerrado': ultimo_cerrado}


def _sesiones_en(cliente, inicio, fin):
    from django.db.models import Q
    from entrenos.models import EntrenoRealizado
    fechas = {
        fe or f for fe, f in EntrenoRealizado.objects.filter(cliente=cliente).filter(
            Q(fecha_ejecucion__gte=inicio, fecha_ejecucion__lte=fin)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=inicio, fecha__lte=fin)
        ).values_list('fecha_ejecucion', 'fecha')
    }
    return len(fechas)


def _pct(valor):
    return f'{valor:+.0f} %'.replace('.', ',')


def revisar_bloque(cliente, grupo):
    """La revisión de un bloque cerrado, con el dato. Devuelve un dict para la plantilla."""
    from entrenos.models import GymDecisionLog, PropuestaZonaGym
    from entrenos.services.evolucion_muscular_service import calcular_evolucion_por_grupo
    from entrenos.services.periodizacion_dinamica_service import _dias_previstos
    from entrenos.services.propuesta_zona_service import frase_evaluacion

    inicio, fin = grupo['inicio'], grupo['fin']
    dias = max(7, (fin - inicio).days + 1)
    semanas_contenido = grupo['semanas_reales']
    previstas = semanas_contenido * _dias_previstos(cliente)
    hechas = _sesiones_en(cliente, inicio, fin)

    durante = calcular_evolucion_por_grupo(cliente, hoy=fin, dias=dias)
    con_datos = [g for g in durante['grupos'] if g['pct'] is not None]
    suben = sorted((g for g in con_datos if g['pct'] >= 10), key=lambda g: -g['pct'])
    bajan = sorted((g for g in con_datos if g['estado'] == 'retrocede'), key=lambda g: g['pct'])

    # Equilibrar: zonas que retrocedían al empezar (90 días) y cómo acabaron.
    al_empezar = calcular_evolucion_por_grupo(cliente, hoy=inicio - timedelta(days=1), dias=90)
    al_acabar = calcular_evolucion_por_grupo(cliente, hoy=fin, dias=90)
    final = {g['zona']: g for g in al_acabar['grupos']}
    equilibrar = []
    for g in al_empezar['grupos']:
        if g['estado'] != 'retrocede':
            continue
        despues = final.get(g['zona'])
        recuperada = bool(despues and despues['pct'] is not None and despues['estado'] != 'retrocede')
        equilibrar.append({
            'nombre': g['nombre'], 'antes': g['pct'],
            'despues': despues['pct'] if despues else None, 'recuperada': recuperada,
            'texto': (
                f"{g['nombre']}: {_pct(g['pct'])} al empezar → "
                + (f"{_pct(despues['pct'])} al acabar" if despues and despues['pct'] is not None else 'sin datos al acabar')
                + (' · recuperada' if recuperada else ' · sigue por debajo')
            ),
        })

    logs = GymDecisionLog.objects.filter(
        cliente=cliente, fecha_evaluacion__date__gte=inicio, fecha_evaluacion__date__lte=fin,
        resultado__in=('validada', 'fallida'),
    ).exclude(accion='mantener')
    funcionaron = logs.filter(resultado='validada').count()
    total_decisiones = logs.count()
    propuestas = [
        frase_evaluacion(p) for p in PropuestaZonaGym.objects.filter(
            cliente=cliente, estado=PropuestaZonaGym.ESTADO_EVALUADA,
            evaluada_en__date__gte=inicio, evaluada_en__date__lte=fin + timedelta(days=7),
        ).order_by('evaluada_en')
    ]

    siguen = [e['nombre'] for e in equilibrar if not e['recuperada']] or [g['nombre'] for g in bajan]
    if siguen:
        cambia = (
            f"En el siguiente bloque el foco es {', '.join(siguen[:3]).lower()}: "
            'si una zona sigue cayendo, el plan propondrá subirle volumen.'
        )
    else:
        cambia = 'Ninguna zona retrocede: el siguiente bloque sigue el plan sin ajustes de foco.'

    return {
        'nombre': grupo['bloque'].get('nombre'),
        'inicio': inicio,
        'fin': fin,
        'semanas': semanas_contenido,
        'descargas': grupo['descargas'],
        'sesiones': {'hechas': hechas, 'previstas': previstas,
                     'pct': round(100 * hechas / previstas) if previstas else None},
        'fuerza_media': durante['media_pct'],
        'suben': [f"{g['nombre']} {_pct(g['pct'])}" for g in suben[:3]],
        'bajan': [f"{g['nombre']} {_pct(g['pct'])}" for g in bajan[:3]],
        'equilibrar': equilibrar,
        'decisiones': {'funcionaron': funcionaron, 'total': total_decisiones},
        'propuestas': propuestas,
        'cambia': cambia,
    }


def revision_ultimo_bloque(cliente, hoy=None):
    """Revisión del último bloque cerrado + estado del bloque en curso, o None."""
    estado = estado_bloques(cliente, hoy=hoy)
    revision = revisar_bloque(cliente, estado['ultimo_cerrado']) if estado['ultimo_cerrado'] else None
    if not revision and not estado['en_curso']:
        return None
    return {'revision': revision, 'en_curso': estado['en_curso']}

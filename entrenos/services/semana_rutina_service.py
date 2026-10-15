"""La semana de Rutina contada con la misma cola que Ahora (14-oct-2026).

Antes, la tira semanal de Rutina leía el calendario fijo del plan anual: el
miércoles decía "Día 3" mientras Ahora proponía el Día 2 atrasado, y el martes
seguía enseñando "Día 2 · sesión programada" aunque ese día se hiciera el Día 1.

Aquí cada día de la semana en curso dice lo que es de verdad:

- Días pasados: la sesión que hiciste (``hecha``) o ``sin_entreno``.
- Hoy: lo mismo que Ahora (``_siguiente_de_cola``: la atrasada si la hay; si
  no, la de hoy) o ``hecha`` si ya entrenaste.
- Días que vienen: las sesiones que quedan en la cola, en orden, sobre los días
  de entreno que quedan en el plan. Lo que no cabe se nombra (la semana se
  cierra el domingo y no se arrastra).

Es de lectura: no crea ni cambia ``SesionProgramada``.
"""

from datetime import timedelta


def _entrenos_por_dia(cliente, lunes, hasta):
    from django.db.models import Q
    from entrenos.models import EntrenoRealizado

    por_dia = {}
    for e in (
        EntrenoRealizado.objects.filter(cliente=cliente)
        .filter(
            Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=hasta)
            | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=hasta)
        )
        .select_related('rutina').order_by('fecha_ejecucion', 'fecha', 'id')
    ):
        por_dia.setdefault(e.fecha_ejecucion or e.fecha, []).append(e)
    return por_dia


def entrenos_por_dia(cliente, desde, hasta):
    """{fecha: [EntrenoRealizado]} por día real de ejecución."""
    return _entrenos_por_dia(cliente, desde, hasta)


def semana_segun_cola(cliente, hoy):
    """Lo que es cada día de la semana de ``hoy``.

    Devuelve {'dias': {fecha: dia}, 'fuera': [nombre], 'hechas': n, 'previstas': n},
    con dia = {'tipo': 'hecha'|'sesion'|'sin_entreno'|'descanso', 'nombre',
    'entrenamiento', 'sp', 'entrenos', 'atrasada', 'fecha_origen'}.
    """
    from entrenos.services.sesion_recomendada import (
        _build_planificador, _es_descanso, _normalizar_entrenamiento,
        _siguiente_de_cola, cola_semana,
    )

    lunes = hoy - timedelta(days=hoy.weekday())
    fechas = [lunes + timedelta(days=i) for i in range(7)]
    planificador = _build_planificador(cliente)
    plan = {}
    for f in fechas:
        try:
            plan[f] = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(f))
        except Exception:
            plan[f] = None
    hechos = _entrenos_por_dia(cliente, lunes, hoy)

    dias = {}
    for f in fechas:
        if f < hoy or (f == hoy and hechos.get(f)):
            if hechos.get(f):
                dias[f] = {'tipo': 'hecha', 'entrenos': hechos[f],
                           'nombre': hechos[f][0].rutina.nombre if hechos[f][0].rutina else 'Sesión'}
            else:
                dias[f] = {'tipo': 'sin_entreno'}

    # Hoy, si aún no se ha entrenado: exactamente lo que propone Ahora.
    elegida_hoy = None
    if hoy not in dias:
        siguiente = _siguiente_de_cola(cliente, hoy)
        if siguiente is not None:
            elegida_hoy = siguiente
        elif not _es_descanso(plan.get(hoy)):
            elegida_hoy = {'fecha': hoy, 'nombre': plan[hoy].get('rutina_nombre') or 'Sesión',
                           'entrenamiento': plan[hoy], 'sp': None}
        if elegida_hoy:
            dias[hoy] = {'tipo': 'sesion', 'nombre': elegida_hoy['nombre'],
                         'entrenamiento': elegida_hoy.get('entrenamiento'), 'sp': elegida_hoy.get('sp'),
                         'atrasada': elegida_hoy['fecha'] != hoy, 'fecha_origen': elegida_hoy['fecha']}
        else:
            dias[hoy] = {'tipo': 'descanso'}

    # La cola que queda: sin hacer hasta hoy (menos la de hoy) y luego las futuras.
    alta = getattr(cliente, 'fecha_registro', None)
    pendientes = [
        s for s in cola_semana(cliente, hoy, planificador)
        if not s['hecha'] and not (alta and s['fecha'] < alta)
        and not (elegida_hoy and s['fecha'] == elegida_hoy['fecha'])
    ]
    futuros = [f for f in fechas if f > hoy and not _es_descanso(plan.get(f))]
    pendientes += [
        {'fecha': f, 'nombre': plan[f].get('rutina_nombre') or 'Sesión', 'entrenamiento': plan[f]}
        for f in futuros
    ]
    for f in fechas:
        if f > hoy:
            dias[f] = {'tipo': 'descanso'}
    for f, s in zip(futuros, pendientes):
        dias[f] = {'tipo': 'sesion', 'nombre': s['nombre'], 'entrenamiento': s['entrenamiento'],
                   'sp': None, 'atrasada': s['fecha'] < f, 'fecha_origen': s['fecha']}

    previstas = sum(1 for f in fechas if not _es_descanso(plan.get(f)))
    return {
        'dias': dias,
        'fuera': [s['nombre'] for s in pendientes[len(futuros):]],
        'hechas': sum(1 for d in dias.values() if d['tipo'] == 'hecha'),
        'previstas': previstas,
    }


def _etiqueta(nombre):
    """'Dia 2 - Hipertrofia — Metabólica' → 'Día 2'."""
    import re
    m = re.match(r'\s*d[ií]a\s*(\d+)', nombre or '', re.IGNORECASE)
    return f'Día {m.group(1)}' if m else (nombre or 'una sesión')


def _lista(nombres):
    nombres = [_etiqueta(n) for n in nombres]
    if len(nombres) <= 1:
        return ''.join(nombres)
    return ', '.join(nombres[:-1]) + ' y ' + nombres[-1]


def nota_semana(semana):
    """Una frase con el dato: cuántas llevas y qué no cabe ya, si algo."""
    texto = f"Llevas {semana['hechas']} de {semana['previstas']} sesiones esta semana."
    if semana['fuera']:
        texto += (
            f" Con los días que quedan no entra{'n' if len(semana['fuera']) > 1 else ''} "
            f"{_lista(semana['fuera'])}: la semana se cierra el domingo y no se arrastra."
        )
    return texto


def sesiones_para_plan(cliente, hoy):
    """La semana en curso en el formato de sesión de la trayectoria del Plan."""
    datos = semana_segun_cola(cliente, hoy)
    sesiones = []
    for f in sorted(datos['dias']):
        d = datos['dias'][f]
        if d['tipo'] == 'hecha':
            for e in d['entrenos']:
                completa = e.estado_cierre != e.ESTADO_PARCIAL
                sesiones.append({
                    'id': None, 'nombre': e.rutina.nombre if e.rutina else 'Sesión',
                    'estado': 'completada' if completa else 'parcial',
                    'fecha_prevista': f, 'fecha_pospuesta': None, 'fecha_efectiva': f,
                    'fecha_realizada': f, 'realizada': True, 'completa': completa, 'parcial': not completa,
                })
        elif d['tipo'] == 'sesion':
            origen = d.get('fecha_origen') or f
            sp = d.get('sp')
            sesiones.append({
                'id': sp.pk if sp is not None else None, 'nombre': d['nombre'], 'estado': 'prevista',
                'fecha_prevista': origen, 'fecha_pospuesta': f if origen != f else None,
                'fecha_efectiva': f, 'fecha_realizada': None, 'realizada': False,
                'completa': False, 'parcial': False, 'en_cola': origen != f,
            })
    return sesiones, datos

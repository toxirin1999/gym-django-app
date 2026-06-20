"""
Phase 62G.1 — Agrupadores para el Centro de decisiones 2.0.

CONTRATO:
    - No introduce motor nuevo: agrupa listas que el panel ya construye
      (traces humanizados de decision_trace_service, GymDecisionLog,
      preferencias/intervenciones/hipótesis activas).
    - El Centro no debe mostrar más datos; debe mostrar mejor qué
      evidencias siguen vivas (Phase 62G, frase de fase).
    - Las listas de entrada vienen ordenadas más reciente primero
      (igual que get_traces_recientes y plan_decisiones_view); los
      agrupadores conservan ese orden para "última vez" / "más reciente".
"""

# Phase 62G.1 — etiquetas de grupo para "Carga por ejercicio". Distintas de
# accion_label (que dice "Mantener"): aquí se nombra el grupo tal y como
# aparece en el Centro 2.0 ("Mantener carga", "Reducir peso", ...).
_ACCION_GROUP_LABELS = {
    'subir_peso': 'Subir peso',
    'subir_reps': 'Subir repeticiones',
    'mantener': 'Mantener carga',
    'bajar_peso': 'Reducir peso',
    'deload': 'Descarga',
    'cambiar_variante': 'Cambiar variante',
}


def agrupar_traces_recientes(traces: list[dict]) -> list[dict]:
    """
    Agrupa traces humanizados (humanizar_trace) por (decision_label, explicacion).

    Devuelve una lista de grupos, en el orden de primera aparición de
    `traces` (más reciente primero), cada uno con:
        decision_label, explicacion, lesion_label, count,
        fecha_label (de la ocurrencia más reciente), items (originales).
    """
    grupos: dict[tuple, dict] = {}
    orden: list[tuple] = []

    for trace in traces:
        clave = (trace['decision_label'], trace['explicacion'])
        if clave not in grupos:
            grupos[clave] = {
                'decision_label': trace['decision_label'],
                'explicacion': trace['explicacion'],
                'lesion_label': trace['lesion_label'],
                'fecha_label': trace['fecha_label'],
                'count': 0,
                'items': [],
            }
            orden.append(clave)
        grupo = grupos[clave]
        grupo['count'] += 1
        grupo['items'].append(trace)

    return [grupos[clave] for clave in orden]


def agrupar_decisiones_carga(decisiones: list) -> list[dict]:
    """
    Agrupa GymDecisionLog por accion.

    Devuelve una lista de grupos, en el orden de primera aparición de
    `decisiones` (más reciente primero), cada uno con:
        accion, label, count, ejercicios (nombres formateados, sin
        repetir), motivo_principal (del log más reciente del grupo),
        items (logs originales).

    Un mismo ejercicio puede tener varios logs en la ventana de 30 días
    (p.ej. subir_peso el día 10 y mantener el día 15). Solo el log más
    reciente de cada ejercicio decide su grupo — si no, el ejercicio
    aparecería repetido en dos grupos distintos a la vez.
    """
    decision_mas_reciente_por_ejercicio: dict[str, object] = {}
    orden_ejercicios: list[str] = []

    for log in decisiones:
        nombre = log.ejercicio.title()
        if nombre not in decision_mas_reciente_por_ejercicio:
            decision_mas_reciente_por_ejercicio[nombre] = log
            orden_ejercicios.append(nombre)

    grupos: dict[str, dict] = {}
    orden: list[str] = []

    for nombre in orden_ejercicios:
        log = decision_mas_reciente_por_ejercicio[nombre]
        accion = log.accion
        if accion not in grupos:
            grupos[accion] = {
                'accion': accion,
                'label': _ACCION_GROUP_LABELS.get(accion, log.accion_label),
                'count': 0,
                'ejercicios': [],
                'motivo_principal': log.motivo,
                'items': [],
            }
            orden.append(accion)
        grupo = grupos[accion]
        grupo['count'] += 1
        grupo['items'].append(log)
        grupo['ejercicios'].append(nombre)

    # Phase 62I — cuántas de las decisiones del grupo quedaron pospuestas
    # por el freno contextual la última vez que se calculó el plan.
    for grupo in grupos.values():
        grupo['pospuestas_count'] = sum(
            1 for it in grupo['items'] if it.estado_aplicacion == 'pospuesta'
        )

    return [grupos[accion] for accion in orden]


# Phase 62G.1 — narrativa del hero cuando no hay señales activas (62G.0,
# validada por el usuario). No renderizar secciones fantasma si esto aplica.
_NARRATIVA_MODO_NORMAL = (
    'El plan opera en modo normal. No hay preferencias, ajustes ni hipótesis '
    'activas — las decisiones de hoy se basan solo en lo que pasó esta semana.'
)


def construir_estado_plan(preferencias_activas, intervenciones_activas, hipotesis_abiertas) -> dict:
    """
    Construye la narrativa del hero del Centro de decisiones a partir de las
    señales activas (preferencias aprendidas, intervenciones, hipótesis).

    Devuelve {'narrativa': str, 'hay_senales_activas': bool}.
    Si no hay ninguna señal, narrativa = modo normal y hay_senales_activas=False
    (el template no debe renderizar secciones de "activo ahora").
    """
    senales = []

    for pref in preferencias_activas:
        senales.append(pref.descripcion or pref.get_tipo_display())

    for interv in intervenciones_activas:
        senales.append(interv.get_tipo_display())

    for hip in hipotesis_abiertas:
        texto = hip.get('texto') if isinstance(hip, dict) else None
        if texto:
            senales.append(texto)

    if not senales:
        return {'narrativa': _NARRATIVA_MODO_NORMAL, 'hay_senales_activas': False}

    if len(senales) == 1:
        cuerpo = senales[0]
    else:
        cuerpo = '; '.join(senales[:-1]) + ' y ' + senales[-1]

    plural = 'señal activa' if len(senales) == 1 else 'señales activas'
    narrativa = f'El plan está usando {len(senales)} {plural}: {cuerpo}.'

    return {'narrativa': narrativa, 'hay_senales_activas': True}

"""
Phase 62F — Cierre de entrenamiento.

Construye el contexto para la pantalla de cierre post-entreno: qué se hizo,
cómo lo leyó el plan, qué cambió respecto a la sesión anterior y qué espera
para la próxima vez.

CONTRATO:
    - No introduce motor nuevo: reutiliza SesionEntrenamiento (resumen),
      evaluar_permiso_progresion (lectura del plan), RecordPersonal (PRs)
      y MensajeJOI (trigger='entreno_completado').
    - "Cambios relevantes" se deriva comparando peso_kg con la última
      sesión registrada para el mismo ejercicio — sin persistir estado nuevo.
    - Si no hay nada que decir (sin freno activo, sin JOI), esos bloques
      quedan en None / lista vacía — la plantilla guarda silencio.
"""

from datetime import timedelta

from django.utils import timezone

from entrenos.models import EjercicioRealizado, GymDecisionLog
from entrenos.services.progresion_contextual_service import (
    evaluar_permiso_progresion,
    _MENSAJES_PROGRESION,
)
from joi.models import MensajeJOI


# Phase 62F.2 — el cierre pertenece al momento de guardar, no solo a la fecha
# histórica del entreno. Si JOI generó un mensaje cerca del guardado (p.ej.
# entreno registrado en retroactivo), ese mensaje es el del cierre aunque su
# creado_en no coincida con entreno.fecha.
_VENTANA_JOI_RECIENTE = timedelta(hours=2)


# Phase 62F — copy "próxima vez" por motivo de freno. Mismo vocabulario que
# _MENSAJES_PROGRESION, en clave de futuro.
_PROXIMA_VEZ = {
    'retorno_pausa': 'El plan conserva la progresión gradual. Si el RPE se mantiene controlado, podrá volver a subir.',
    'lesion_activa': 'La progresión vuelve cuando la zona afectada lo permita.',
    'lesion_retorno': 'La progresión vuelve de forma gradual según tolere la articulación.',
    'carga_alta_sostenida': 'Cuando la carga acumulada baje, el plan podrá volver a subir peso.',
    'carga_alta_semanal': 'Si esta semana se completa el bloque principal, la progresión podrá retomarse.',
    'bloque_parcial_repetido': 'Cuando el bloque principal se complete con regularidad, el plan retomará la progresión.',
    'esenciales_frecuentes': 'Si las próximas sesiones no requieren versión esencial, la progresión podrá retomarse.',
    'margen_bajo_repetido': 'El volumen accesorio podrá ajustarse cuando el margen mejore.',
    'modo_reducido': 'La próxima sesión normal podrá retomar la progresión si el patrón lo permite.',
    'intervencion_no_subir_cargas': 'La progresión vuelve cuando termine la intervención activa.',
    'intervencion_reducir_accesorios': 'El volumen accesorio vuelve cuando termine la intervención activa.',
}


# Phase 62F.1 — copy "próxima vez" derivada de GymDecisionLog cuando no hay
# freno de plan activo. Agrupa ejercicios por accion para no repetir frase.
_PROXIMA_VEZ_ACCION = {
    'mantener': 'el plan mantiene la carga en {ejercicios}',
    'subir_peso': 'el plan propondrá subir peso en {ejercicios}',
    'subir_reps': 'el plan propondrá subir repeticiones en {ejercicios}',
    'bajar_peso': 'el plan reducirá la carga en {ejercicios}',
    'deload': 'el plan aplicará una descarga en {ejercicios}',
    'cambiar_variante': 'el plan propondrá cambiar de variante en {ejercicios}',
}


def _proxima_vez_decisiones(cliente, ejercicios):
    """
    Deriva "próxima vez" de las decisiones de progresión (GymDecisionLog)
    pendientes (resultado=None) para los ejercicios de esta sesión, generadas
    por actualizar_decision_log al guardar el entreno. Solo se usa cuando no
    hay freno de plan activo (ver construir_contexto_cierre).
    """
    nombres = [ej.nombre_ejercicio.strip().lower() for ej in ejercicios if ej.nombre_ejercicio.strip()]
    if not nombres:
        return None

    logs = (
        GymDecisionLog.objects
        .filter(cliente=cliente, ejercicio__in=nombres, resultado__isnull=True)
        .order_by('ejercicio', '-fecha_creacion')
    )

    ultimo_por_ejercicio = {}
    for log in logs:
        ultimo_por_ejercicio.setdefault(log.ejercicio, log)

    grupos = {}
    for log in ultimo_por_ejercicio.values():
        plantilla = _PROXIMA_VEZ_ACCION.get(log.accion)
        if not plantilla:
            continue
        grupos.setdefault(log.accion, []).append(log.ejercicio.title())

    if not grupos:
        return None

    frases = [
        _PROXIMA_VEZ_ACCION[accion].format(ejercicios=', '.join(nombres_ej))
        for accion, nombres_ej in grupos.items()
    ]
    frase = '; '.join(frases)
    return frase[0].upper() + frase[1:] + '.'


def _resumen_sesion(entreno, ejercicios):
    titulo = entreno.rutina.nombre if entreno.rutina_id else ''
    n_series_calculado = sum(ej.series for ej in ejercicios)
    sesion = getattr(entreno, 'sesion_detalle', None)

    # Si fue versión esencial/reducida, añadir label discreta
    sesion_tipo = '· Sesión ajustada' if entreno.modo_reducido else None

    if sesion:
        return {
            'titulo': titulo,
            'n_ejercicios': sesion.ejercicios_completados or len(ejercicios),
            # La señal de gamificación crea sesion_detalle en cuanto se guarda
            # el entreno, antes de que existan ejercicios — series_completadas
            # puede quedar en 0 si nadie la recalculó después.
            'n_series': sesion.series_completadas or n_series_calculado,
            'rpe_medio': sesion.rpe_medio,
            'duracion_minutos': sesion.duracion_minutos or entreno.duracion_minutos,
            'volumen_kg': float(sesion.volumen_sesion or entreno.volumen_total_kg or 0),
            'sesion_tipo': sesion_tipo,
        }
    return {
        'titulo': titulo,
        'n_ejercicios': len(ejercicios),
        'n_series': n_series_calculado,
        'rpe_medio': None,
        'duracion_minutos': entreno.duracion_minutos,
        'volumen_kg': float(entreno.volumen_total_kg or 0),
        'sesion_tipo': sesion_tipo,
    }


def _cambios_relevantes(cliente, entreno, ejercicios):
    cambios = []
    for ej in ejercicios:
        if ej.es_tope_maquina:
            cambios.append({
                'nombre': ej.nombre_ejercicio,
                'tipo': 'tope',
                'detalle': 'tope de máquina · progresó por reps',
            })
            continue

        anterior = (
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, nombre_ejercicio=ej.nombre_ejercicio, completado=True)
            .exclude(entreno_id=entreno.id)
            .order_by('-entreno__fecha', '-id')
            .first()
        )
        if anterior is None:
            continue

        diff = round((ej.peso_kg or 0) - (anterior.peso_kg or 0), 2)

        # Detectar cambio de variante: 0↔carga (cambio de unidad, no regresión real)
        es_cambio_variante = (ej.peso_kg == 0 and anterior.peso_kg > 0) or (ej.peso_kg > 0 and anterior.peso_kg == 0)
        if es_cambio_variante:
            continue  # No mostrar cambios de variante como cambios de carga

        # Ocultar cambios irrelevantes (pero no la carga exactamente igual,
        # que abajo se etiqueta explícitamente como 'mantenida')
        if diff != 0 and abs(diff) < 0.25:
            continue

        if diff == 0:
            cambios.append({'nombre': ej.nombre_ejercicio, 'tipo': 'mantenida', 'detalle': 'carga mantenida'})
        elif diff > 0:
            cambios.append({'nombre': ej.nombre_ejercicio, 'tipo': 'subida', 'detalle': f'+{diff:g} kg'})
        else:
            cambios.append({'nombre': ej.nombre_ejercicio, 'tipo': 'bajada', 'detalle': f'{diff:g} kg'})
    return cambios


def _joi_mensaje_cierre(cliente, entreno):
    """
    Recupera el mensaje JOI (trigger='entreno_completado') para el cierre.

    MensajeJOI no tiene FK al entreno/sesión, así que se busca por:
        1. Mensaje generado en _VENTANA_JOI_RECIENTE — cerca del guardado
           actual, independientemente de entreno.fecha (cubre el registro
           retroactivo: el entreno es de hace días, pero JOI habló ahora).
        2. Si no hay nada reciente, fallback al mismo día que entreno.fecha
           (comportamiento previo, para revisitas al cierre).
        3. Si no hay nada, silencio.
    """
    base = MensajeJOI.objects.filter(user=cliente.user, trigger='entreno_completado')

    reciente = (
        base.filter(creado_en__gte=timezone.now() - _VENTANA_JOI_RECIENTE)
        .order_by('-creado_en')
        .first()
    )
    if reciente:
        return reciente.mensaje

    del_dia = base.filter(creado_en__date=entreno.fecha).order_by('-creado_en').first()
    if del_dia:
        return del_dia.mensaje

    return None


def construir_contexto_cierre(cliente, entreno):
    """
    Returns:
        resumen: dict (titulo, n_ejercicios, n_series, rpe_medio, duracion_minutos, volumen_kg)
        cambios_relevantes: list[{nombre, tipo, detalle}]
        lectura_plan: str | None
        proxima_vez: str | None
        prs: list[RecordPersonal]
        joi_mensaje: str | None
    """
    ejercicios = list(
        entreno.ejercicios_realizados.filter(completado=True).order_by('orden', 'id')
    )

    permiso = evaluar_permiso_progresion(cliente, entreno.fecha)
    motivo = permiso.get('motivo', 'ok')
    accion = permiso.get('accion', 'progresion_permitida')

    lectura_plan = None
    proxima_vez = None
    if accion != 'progresion_permitida':
        lectura_plan = _MENSAJES_PROGRESION.get(motivo)
        proxima_vez = _PROXIMA_VEZ.get(motivo)

    if proxima_vez is None:
        proxima_vez = _proxima_vez_decisiones(cliente, ejercicios)

    # Mostrar todos los PRs reales sin eliminar duplicados (ej: peso máximo + volumen total del mismo ejercicio).
    # Se devuelven los objetos RecordPersonal (no solo el nombre) para poder distinguir
    # el tipo de récord en la plantilla cuando un mismo ejercicio bate dos récords a la vez.
    prs = list(
        entreno.records_establecidos
        .filter(superado=False)
    )

    joi_mensaje = _joi_mensaje_cierre(cliente, entreno)

    return {
        'resumen': _resumen_sesion(entreno, ejercicios),
        'cambios_relevantes': _cambios_relevantes(cliente, entreno, ejercicios),
        'lectura_plan': lectura_plan,
        'proxima_vez': proxima_vez,
        'prs': prs,
        'joi_mensaje': joi_mensaje,
    }

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

from entrenos.models import EjercicioRealizado
from entrenos.services.progresion_contextual_service import (
    evaluar_permiso_progresion,
    _MENSAJES_PROGRESION,
)
from joi.models import MensajeJOI


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


def _resumen_sesion(entreno, ejercicios):
    titulo = entreno.rutina.nombre if entreno.rutina_id else ''
    n_series_calculado = sum(ej.series for ej in ejercicios)
    sesion = getattr(entreno, 'sesion_detalle', None)
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
        }
    return {
        'titulo': titulo,
        'n_ejercicios': len(ejercicios),
        'n_series': n_series_calculado,
        'rpe_medio': None,
        'duracion_minutos': entreno.duracion_minutos,
        'volumen_kg': float(entreno.volumen_total_kg or 0),
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
        if diff == 0:
            cambios.append({'nombre': ej.nombre_ejercicio, 'tipo': 'mantenida', 'detalle': 'carga mantenida'})
        elif diff > 0:
            cambios.append({'nombre': ej.nombre_ejercicio, 'tipo': 'subida', 'detalle': f'+{diff:g} kg'})
        else:
            cambios.append({'nombre': ej.nombre_ejercicio, 'tipo': 'bajada', 'detalle': f'{diff:g} kg'})
    return cambios


def construir_contexto_cierre(cliente, entreno):
    """
    Returns:
        resumen: dict (titulo, n_ejercicios, n_series, rpe_medio, duracion_minutos, volumen_kg)
        cambios_relevantes: list[{nombre, tipo, detalle}]
        lectura_plan: str | None
        proxima_vez: str | None
        prs: list[str]
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

    prs = list(
        entreno.records_establecidos
        .filter(superado=False)
        .values_list('ejercicio_nombre', flat=True)
        .distinct()
    )

    joi_mensaje = None
    mensaje_joi = (
        MensajeJOI.objects
        .filter(user=cliente.user, trigger='entreno_completado', creado_en__date=entreno.fecha)
        .order_by('-creado_en')
        .first()
    )
    if mensaje_joi:
        joi_mensaje = mensaje_joi.mensaje

    return {
        'resumen': _resumen_sesion(entreno, ejercicios),
        'cambios_relevantes': _cambios_relevantes(cliente, entreno, ejercicios),
        'lectura_plan': lectura_plan,
        'proxima_vez': proxima_vez,
        'prs': prs,
        'joi_mensaje': joi_mensaje,
    }

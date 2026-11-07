"""Regla 4 del rumbo: el entrenador vuelve a comprobar si acertó.

Cada GymDecisionLog se evalúa con la siguiente sesión del mismo ejercicio
(``resultado`` = validada / fallida / neutra). Aquí se cuenta en una frase qué
se decidió, qué pasó después (con el dato de esa sesión) y si funcionó.

Regla de oro: si no puede citar el dato, no lo dice. Las cifras salen de la
decisión (peso/reps/RPE anteriores, peso sugerido) y de la sesión que la
evaluó; si falta alguna, la frase se acorta en vez de inventar.
"""

from datetime import timedelta

from django.utils import timezone

VEREDICTO = {
    'validada': 'funcionó',
    'fallida': 'no funcionó',
    'neutra': 'aún sin conclusión',
}


def _kg(valor):
    texto = f'{float(valor):.1f}'.replace('.', ',')
    return texto[:-2] if texto.endswith(',0') else texto


def _rpe(valor):
    return f'{float(valor):g}'.replace('.', ',')


def _capitalizar(texto):
    texto = (texto or '').strip()
    return texto[:1].upper() + texto[1:]


def describir_accion(log):
    """Qué hizo el plan, con el número si lo tiene (nunca el % interno como kg)."""
    peso_objetivo = log.peso_sugerido
    if log.accion == 'subir_peso':
        return f'subí el peso a {_kg(peso_objetivo)} kg' if peso_objetivo else 'subí el peso'
    if log.accion == 'bajar_peso':
        return f'bajé el peso a {_kg(peso_objetivo)} kg' if peso_objetivo else 'bajé el peso'
    if log.accion == 'deload':
        return f'metí una descarga ({_kg(peso_objetivo)} kg)' if peso_objetivo else 'metí una descarga'
    if log.accion == 'subir_reps':
        reps = log.reps_sugeridas
        return f'subí el objetivo a {reps} reps' if reps else 'subí las repeticiones'
    if log.accion == 'mantener':
        return f'mantuve {_kg(log.peso_anterior)} kg' if log.peso_anterior else 'mantuve la carga'
    if log.accion == 'cambiar_variante':
        return 'cambié la variante'
    return log.get_accion_display().lower()


def _sesion_evaluadora(log):
    """La primera sesión del ejercicio posterior a la decisión (la que la evaluó)."""
    from entrenos.models import EjercicioRealizado
    from entrenos.services.decision_log_service import (
        _rendimiento_representativo_desde_series, normalizar_ejercicio,
    )

    qs = EjercicioRealizado.objects.filter(
        entreno__cliente=log.cliente,
        nombre_ejercicio__iexact=log.ejercicio,
        completado=True,
    ).select_related('entreno')
    if log.entreno_origen_id:
        qs = qs.exclude(entreno_id=log.entreno_origen_id).filter(
            entreno__id__gt=log.entreno_origen_id,
        )
    else:
        qs = qs.filter(entreno__fecha__gte=log.fecha_creacion.date())
    ej = qs.order_by('entreno__fecha', 'entreno__id').first()
    if ej is None:
        return None
    rendimiento = _rendimiento_representativo_desde_series(ej.entreno, normalizar_ejercicio(ej.nombre_ejercicio))
    if rendimiento is None:
        peso, reps = ej.peso_kg, ej.repeticiones
    else:
        peso, reps = rendimiento
    try:
        reps = round(float(reps))
    except (TypeError, ValueError):
        reps = None
    return {
        'peso': peso, 'reps': reps, 'rpe': ej.rpe,
        'fecha': ej.entreno.fecha_ejecucion or ej.entreno.fecha, 'entreno_id': ej.entreno_id,
    }


_SIN_DESPUES = object()


def frase_decision(log, etiqueta='Después', despues=_SIN_DESPUES):
    """'Press banca: subí el peso a 62,5 kg. Después: 62,5 kg × 10 con RPE 7. Funcionó.'

    En el cierre de la sesión que la evaluó, ``etiqueta='Hoy'``.
    """
    if despues is _SIN_DESPUES:
        despues = _sesion_evaluadora(log)
    accion = describir_accion(log)
    if despues and log.accion in ('subir_peso', 'bajar_peso', 'deload'):
        # 31-oct-2026 (nota 11): el peso que se propuso de verdad ese día (el
        # briefing recalculó 35 kg; el log guardaba los 45 del cierre anterior).
        try:
            from entrenos.models import EntrenoRealizado
            from entrenos.services.cerebro_carga_service import _peso_plan
            propuesto = _peso_plan(EntrenoRealizado.objects.get(pk=despues['entreno_id']), log.ejercicio)
        except Exception:  # noqa: BLE001
            propuesto = None
        if propuesto and (log.peso_sugerido is None or abs(float(log.peso_sugerido) - propuesto) > 0.01):
            verbo = {'subir_peso': 'subí el peso a', 'bajar_peso': 'bajé el peso a', 'deload': 'metí una descarga a'}
            accion = f'{verbo[log.accion]} {_kg(propuesto)} kg'
    partes = [f'{_capitalizar(log.ejercicio)}: {accion}.']
    if despues and despues['peso'] is not None and despues['reps']:
        if float(despues['peso'] or 0) > 0:
            dato = f"{etiqueta}: {_kg(despues['peso'])} kg × {despues['reps']}"
        else:  # peso corporal: "0 kg × 7" no dice nada
            dato = f"{etiqueta}: {despues['reps']} reps"
        if despues['rpe'] is not None:
            dato += f" con RPE {_rpe(despues['rpe'])}"
        partes.append(dato + '.')
    veredicto = VEREDICTO.get(log.resultado, '')
    if veredicto:
        frase = _capitalizar(veredicto)
        if log.resultado != 'validada' and log.notas_resultado:
            frase += f': {log.notas_resultado[:1].lower()}{log.notas_resultado[1:]}'
        partes.append(frase.rstrip('.') + '.')
    return ' '.join(partes)


def _objetivo_registrado(entreno_id, nombre):
    """Reps y RPE que se prescribieron ese día para el ejercicio (snapshot guardado), o None."""
    from entrenos.models import EntrenoRealizado
    from entrenos.services.decision_log_service import normalizar_ejercicio
    try:
        entreno = EntrenoRealizado.objects.select_related('gym_decision_version').get(pk=entreno_id)
        snapshot = getattr(getattr(entreno, 'gym_decision_version', None), 'snapshot', None) or {}
    except Exception:  # noqa: BLE001
        return None
    clave = normalizar_ejercicio(nombre)
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        if normalizar_ejercicio(ej.get('nombre')) == clave:
            partes = []
            if ej.get('repeticiones'):
                partes.append(f"{ej['repeticiones']} reps")
            rpe = ej.get('rpe_objetivo') or ej.get('rpe')
            if rpe not in (None, ''):
                try:
                    partes.append(f'RPE {_rpe(rpe)}')
                except (TypeError, ValueError):
                    pass
            return ', '.join(partes) or None
    return None


def detalle_decision(log, despues):
    """Qué se esperaba, qué ocurrió y en qué sesión se comprobó (7-nov-2026).

    Solo lo registrado: el objetivo de esa sesión sale de su snapshot; si no
    quedó guardado, basta con la sesión y lo que se observó.
    """
    if not despues:
        return None
    esperado = []
    accion = describir_accion(log)
    if accion:
        esperado.append(_capitalizar(accion) + '.')
    objetivo = _objetivo_registrado(despues['entreno_id'], log.ejercicio)
    if objetivo:
        esperado.append(f'Objetivo de esa sesión: {objetivo}.')
    ocurrido = None
    if despues.get('peso') is not None and despues.get('reps'):
        if float(despues['peso'] or 0) > 0:
            ocurrido = f"{_kg(despues['peso'])} kg × {despues['reps']}"
        else:
            ocurrido = f"{despues['reps']} reps"
        if despues.get('rpe') is not None:
            ocurrido += f" con RPE {_rpe(despues['rpe'])}"
        ocurrido += '.'
    if log.notas_resultado:
        ocurrido = f"{ocurrido + ' ' if ocurrido else ''}{_capitalizar(log.notas_resultado).rstrip('.')}."
    return {
        'esperado': ' '.join(esperado) or None,
        'ocurrido': ocurrido,
        'sesion_fecha': despues['fecha'],
        'entreno_id': despues['entreno_id'],
    }


def decisiones_evaluadas(cliente, dias=28, limite=6, hoy=None):
    """Resumen de las decisiones ya comprobadas en las últimas ``dias``."""
    from entrenos.models import GymDecisionLog

    ahora = hoy or timezone.now()
    logs = list(
        GymDecisionLog.objects.filter(
            cliente=cliente,
            resultado__isnull=False,
            fecha_evaluacion__gte=ahora - timedelta(days=dias),
        ).order_by('-fecha_evaluacion')
    )
    conteo = {clave: sum(1 for l in logs if l.resultado == clave) for clave in VEREDICTO}
    # Solo se cuentan en la lista las decisiones que cambiaron algo y tienen
    # veredicto: "mantuve la carga · sin cambio claro" no enseña nada y
    # tapaba lo importante. Una línea por ejercicio (la más reciente).
    relevantes, vistos = [], set()
    for l in logs:
        if l.resultado not in ('validada', 'fallida') or l.accion == 'mantener':
            continue
        clave = (l.ejercicio or '').strip().casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        relevantes.append(l)
    items = []
    for l in relevantes[:limite]:
        despues = _sesion_evaluadora(l)
        items.append({'fecha': l.fecha_evaluacion, 'resultado': l.resultado,
                      'texto': frase_decision(l, despues=despues), 'detalle': detalle_decision(l, despues)})
    # 7-nov-2026: la cuenta de Memoria es solo de cambios (subir, bajar, variante,
    # descarga): «mantener» casi siempre sale validada y hinchaba el acierto.
    cambios = [l for l in logs if l.accion != 'mantener']
    cambios_conteo = {clave: sum(1 for l in cambios if l.resultado == clave) for clave in VEREDICTO}
    cambios_pendientes = GymDecisionLog.objects.filter(
        cliente=cliente, resultado__isnull=True, fecha_creacion__gte=ahora - timedelta(days=dias),
    ).exclude(accion='mantener').count()
    consolidaciones = sum(1 for l in logs if l.accion == 'mantener')
    # Las propuestas por iniciativa también se comprueban: van primero.
    from entrenos.models import PropuestaZonaGym
    from entrenos.services.propuesta_zona_service import frase_evaluacion
    propuestas = list(PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_EVALUADA,
        evaluada_en__gte=ahora - timedelta(days=dias),
    ).order_by('-evaluada_en'))
    for p in propuestas:
        if p.resultado in conteo:
            conteo[p.resultado] += 1
            cambios_conteo[p.resultado] += 1
    items = [
        {'fecha': p.evaluada_en, 'resultado': p.resultado, 'texto': frase_evaluacion(p)}
        for p in propuestas
    ] + items
    return {
        'total': len(logs) + len(propuestas),
        'con_conclusion': conteo['validada'] + conteo['fallida'],
        'funcionaron': conteo['validada'],
        'no_funcionaron': conteo['fallida'],
        'sin_conclusion': conteo['neutra'],
        'cambios_funcionaron': cambios_conteo['validada'],
        'cambios_concluyentes': cambios_conteo['validada'] + cambios_conteo['fallida'],
        'cambios_sin_evidencia': cambios_conteo['neutra'],
        'cambios_pendientes': cambios_pendientes,
        'consolidaciones': consolidaciones,
        'dias': dias,
        'items': items,
    }

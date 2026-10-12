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
    return {'peso': peso, 'reps': reps, 'rpe': ej.rpe, 'fecha': ej.entreno.fecha_ejecucion or ej.entreno.fecha}


def frase_decision(log):
    """'Press banca: subí el peso a 62,5 kg. Después: 62,5 kg × 10 con RPE 7. Funcionó.'"""
    partes = [f'{_capitalizar(log.ejercicio)}: {describir_accion(log)}.']
    despues = _sesion_evaluadora(log)
    if despues and despues['peso'] is not None and despues['reps']:
        if float(despues['peso'] or 0) > 0:
            dato = f"Después: {_kg(despues['peso'])} kg × {despues['reps']}"
        else:  # peso corporal: "0 kg × 7" no dice nada
            dato = f"Después: {despues['reps']} reps"
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
    items = [
        {'fecha': l.fecha_evaluacion, 'resultado': l.resultado, 'texto': frase_decision(l)}
        for l in relevantes[:limite]
    ]
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
        'dias': dias,
        'items': items,
    }

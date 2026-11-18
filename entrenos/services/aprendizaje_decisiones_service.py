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
    'neutra': 'resultado inconcluso',
}
PENDIENTE = 'pendiente de comprobar'
_PREFIJO_INCONCLUSO = 'Resultado inconcluso:'
# Cierres que no usan los datos de ninguna sesión (decisión sustituida o bloque distinto).
_SIN_SESION = ('Resultado inconcluso: la decisión del', 'Resultado inconcluso: entre la decisión')



def _kg(valor):
    texto = f'{float(valor):.1f}'.replace('.', ',')
    return texto[:-2] if texto.endswith(',0') else texto


def _rpe(valor):
    return f'{float(valor):g}'.replace('.', ',')


def _capitalizar(texto):
    texto = (texto or '').strip()
    return texto[:1].upper() + texto[1:]


def _unidad_ejercicio(log):
    """'s' (tiempo), 'm' (distancia) o 'reps' (12-nov-2026, nota 28: «subí el objetivo a 37 reps» eran segundos)."""
    try:
        from rutinas.models import EjercicioBase
        tipo = (EjercicioBase.objects.filter(nombre__iexact=log.ejercicio)
                .values_list('tipo_progresion', flat=True).first())
    except Exception:  # noqa: BLE001
        tipo = None
    return {'progresion_tiempo': 's', 'progresion_distancia': 'm'}.get(tipo, 'reps')


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
        unidad = _unidad_ejercicio(log)
        if unidad != 'reps':
            return f'subí el objetivo a {reps} {unidad}' if reps else 'subí el objetivo'
        return f'subí el objetivo a {reps} reps' if reps else 'subí las repeticiones'
    if log.accion == 'mantener':
        return f'mantuve {_kg(log.peso_anterior)} kg' if log.peso_anterior else 'mantuve la carga'
    if log.accion == 'cambiar_variante':
        return 'cambié la variante'
    return log.get_accion_display().lower()


def _sesion_evaluadora(log):
    """La primera sesión del ejercicio posterior a la decisión (la que la evaluó)."""
    from entrenos.services.decision_log_service import (
        _rendimiento_representativo_desde_series, normalizar_ejercicio,
    )

    # 17-nov-2026: del historial del ejercicio ya leído en la petición.
    from entrenos.services.historial_ejercicio_service import posteriores

    ej = None
    if log.entreno_evaluador_id:
        # 18-nov-2026 (nota 48): la sesión que evaluó de verdad, guardada.
        from entrenos.models import EjercicioRealizado
        clave = normalizar_ejercicio(log.ejercicio)
        ej = next(
            (e for e in EjercicioRealizado.objects.filter(entreno_id=log.entreno_evaluador_id, completado=True)
             .select_related('entreno') if normalizar_ejercicio(e.nombre_ejercicio) == clave),
            None,
        )
    if ej is None and not log.entreno_evaluador_id:
        candidatas = posteriores(
            log.cliente_id, log.ejercicio,
            entreno_origen_id=log.entreno_origen_id,
            desde_fecha=None if log.entreno_origen_id else log.fecha_creacion.date(),
            limite=60,
        )
        # 12-nov-2026 (nota 28): una semana de descarga no comprueba una decisión de
        # progreso (dead hang 37 s → «30 con RPE 6, funcionó» era la descarga).
        from entrenos.services.sesion_descarga_service import es_sesion_descarga, periodos_descarga
        _periodos = periodos_descarga(log.cliente_id)
        elegibles = [c for c in candidatas
                     if not es_sesion_descarga(c.entreno, c.nombre_ejercicio, _periodos)]
        if log.resultado is not None and log.fecha_evaluacion:
            # 18-nov-2026 (nota 48): sin la sesión guardada, la que evaluó es la última elegible
            # hasta el día de la evaluación (se evalúa al guardar una sesión), no la primera
            # posterior a la decisión, que pudo ser otra semanas antes.
            from django.utils import timezone
            limite_dia = timezone.localtime(log.fecha_evaluacion).date()
            elegibles = [c for c in elegibles
                         if (c.entreno.fecha_ejecucion or c.entreno.fecha) <= limite_dia]
            ej = elegibles[-1] if elegibles else None
        else:
            ej = elegibles[0] if elegibles else None
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
    try:
        from entrenos.services.ultima_sesion_service import series_de_trabajo
        series = series_de_trabajo(ej.entreno, ej.nombre_ejercicio)
    except Exception:  # noqa: BLE001
        series = []
    return {
        'peso': peso, 'reps': reps, 'rpe': ej.rpe, 'series': series,
        'fecha': ej.entreno.fecha_ejecucion or ej.entreno.fecha, 'entreno_id': ej.entreno_id,
    }


_SIN_DESPUES = object()


def _peso_propuesto_real(log, despues):
    """El peso que se propuso de verdad en la sesión que comprobó la decisión, o None."""
    if not despues or log.accion not in ('subir_peso', 'bajar_peso', 'deload'):
        return None
    # 31-oct-2026 (nota 11): el peso que se propuso de verdad ese día (el
    # briefing recalculó 35 kg; el log guardaba los 45 del cierre anterior).
    try:
        from entrenos.models import EntrenoRealizado
        from entrenos.services.cerebro_carga_service import _peso_plan
        return _peso_plan(EntrenoRealizado.objects.get(pk=despues['entreno_id']), log.ejercicio)
    except Exception:  # noqa: BLE001
        return None


def _dato_citado(log, despues):
    """(peso, reps, RPE) de UNA misma serie para citar en «Hoy:» (17-nov-2026, nota 42).

    Antes mezclaba el peso de la serie más pesada (75 kg) con el RPE medio del
    ejercicio (6, de las series de 65 y 70). Ahora se cita el peso de la
    decisión si se hizo («subí a 65 kg» → 65 kg × 6 con su RPE); si no, la serie
    de referencia. El RPE sale siempre de las series a ese mismo peso.
    """
    peso, reps, rpe = despues.get('peso'), despues.get('reps'), despues.get('rpe')
    series = [s for s in (despues.get('series') or []) if s.get('reps', 0) > 0]
    if not series:
        return peso, reps, rpe
    objetivo = _peso_propuesto_real(log, despues)
    if objetivo is None and log.accion in ('subir_peso', 'bajar_peso', 'deload') and log.peso_sugerido is not None:
        objetivo = float(log.peso_sugerido)
    if objetivo:
        a_ese_peso = [s for s in series if abs(s['peso'] - float(objetivo)) < 0.01]
        if a_ese_peso:
            peso = a_ese_peso[0]['peso']
            reps = round(sum(s['reps'] for s in a_ese_peso) / len(a_ese_peso))
    # RPE: el más alto de las series a ese peso; sin RPE en ellas, no se inventa.
    rpes = [s['rpe'] for s in series if peso is not None and abs(s['peso'] - float(peso)) < 1e-6 and s.get('rpe') is not None]
    if rpes:
        rpe = max(rpes)
    elif len({s['peso'] for s in series}) == 1:
        rpe = despues.get('rpe')  # un solo peso: el RPE medio del ejercicio es el de esas series
    else:
        rpe = None
    return peso, reps, rpe


def _tramo_posterior(despues, c_peso):
    """(peso, reps, RPE) de las series más pesadas que la citada, o None (18-nov-2026, nota 22).

    «Subí a 105 kg. Hoy: 105 × 15 con RPE 7» callaba la serie siguiente, 110 × 15
    con RPE 8, que fue la que marcó el récord. Se cita con sus propios datos.
    """
    series = [s for s in (despues.get('series') or []) if s.get('reps', 0) > 0 and s.get('peso')]
    try:
        base = float(c_peso or 0)
    except (TypeError, ValueError):
        return None
    if base <= 0:
        return None
    mas = [s for s in series if float(s['peso']) > base + 0.01]
    if not mas:
        return None
    tope = max(float(s['peso']) for s in mas)
    a_tope = [s for s in mas if abs(float(s['peso']) - tope) < 0.01]
    reps = round(sum(s['reps'] for s in a_tope) / len(a_tope))
    rpes = [s['rpe'] for s in a_tope if s.get('rpe') is not None]
    return tope, reps, (max(rpes) if rpes else None)


def _texto_tramo(tramo):
    peso, reps, rpe = tramo
    texto = f"{_kg(peso)} kg × {reps}"
    if rpe is not None:
        texto += f" con RPE {_rpe(rpe)}"
    return texto


def _accion_real(log, despues):
    """La acción con el peso que se propuso de verdad en la sesión que la comprobó."""
    accion = describir_accion(log)
    if despues and log.accion in ('subir_peso', 'bajar_peso', 'deload'):
        propuesto = _peso_propuesto_real(log, despues)
        if propuesto and (log.peso_sugerido is None or abs(float(log.peso_sugerido) - propuesto) > 0.01):
            verbo = {'subir_peso': 'subí el peso a', 'bajar_peso': 'bajé el peso a', 'deload': 'metí una descarga a'}
            accion = f'{verbo[log.accion]} {_kg(propuesto)} kg'
    return accion


def frase_decision(log, etiqueta='Después', despues=_SIN_DESPUES):
    """'Press banca: subí el peso a 62,5 kg. Después: 62,5 kg × 10 con RPE 7. Funcionó.'

    En el cierre de la sesión que la evaluó, ``etiqueta='Hoy'``.
    """
    if despues is _SIN_DESPUES:
        despues = _sesion_evaluadora(log)
    accion = _accion_real(log, despues)
    partes = [f'{_capitalizar(log.ejercicio)}: {accion}.']
    if log.resultado is None or (log.notas_resultado or '').startswith(_SIN_SESION):
        despues = None  # sin evaluar, o cerrada sin usar los datos de ninguna sesión
    if despues and despues['peso'] is not None and despues['reps']:
        if etiqueta != 'Hoy' and despues.get('fecha'):
            etiqueta = f"{etiqueta} ({despues['fecha'].strftime('%d/%m')})"
        c_peso, c_reps, c_rpe = _dato_citado(log, despues)
        if float(c_peso or 0) > 0:
            dato = f"{etiqueta}: {_kg(c_peso)} kg × {c_reps}"
        else:  # peso corporal: "0 kg × 7" no dice nada
            dato = f"{etiqueta}: {c_reps} {_unidad_ejercicio(log)}"
        if c_rpe is not None:
            dato += f" con RPE {_rpe(c_rpe)}"
        posterior = _tramo_posterior(despues, c_peso)
        if posterior and float(c_peso or 0) > 0:
            dato += f" y después {_texto_tramo(posterior)}"
        partes.append(dato + '.')
    if log.resultado is None:
        partes.append(_capitalizar(PENDIENTE) + '.')
    else:
        if (despues is None and log.resultado in ('validada', 'fallida')
                and not (log.notas_resultado or '').startswith(_SIN_SESION)
                and log.accion in ('subir_peso', 'bajar_peso', 'deload', 'subir_reps')):
            partes.append('No consta la sesión que la evaluó.')
        veredicto = VEREDICTO.get(log.resultado, '')
        if veredicto:
            frase = _capitalizar(veredicto)
            notas = (log.notas_resultado or '').strip()
            if notas.startswith(_PREFIJO_INCONCLUSO):
                notas = notas[len(_PREFIJO_INCONCLUSO):].strip()
            if log.resultado != 'validada' and notas:
                frase += f': {notas[:1].lower()}{notas[1:]}'
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


def _lineas_sabia(log):
    from entrenos.services.senales_al_decidir_service import lineas_para_mostrar
    return lineas_para_mostrar(log) or None


def detalle_decision(log, despues):
    """Qué se esperaba, qué ocurrió y en qué sesión se comprobó (7-nov-2026).

    Solo lo registrado: el objetivo de esa sesión sale de su snapshot; si no
    quedó guardado, basta con la sesión y lo que se observó.
    """
    if not despues:
        return None
    esperado = []
    # 8-nov-2026: la misma acción que el titular (el peso propuesto de verdad).
    accion = _accion_real(log, despues)
    if accion:
        esperado.append(_capitalizar(accion) + '.')
    objetivo = _objetivo_registrado(despues['entreno_id'], log.ejercicio)
    if objetivo:
        esperado.append(f'Objetivo de esa sesión: {objetivo}.')
    ocurrido = None
    if despues.get('peso') is not None and despues.get('reps'):
        c_peso, c_reps, c_rpe = _dato_citado(log, despues)
        if float(c_peso or 0) > 0:
            ocurrido = f"{_kg(c_peso)} kg × {c_reps}"
        else:
            ocurrido = f"{c_reps} reps"
        if c_rpe is not None:
            ocurrido += f" con RPE {_rpe(c_rpe)}"
        posterior = _tramo_posterior(despues, c_peso)
        if posterior and float(c_peso or 0) > 0:
            ocurrido += f" y después {_texto_tramo(posterior)}"
        ocurrido += '.'
    if log.notas_resultado:
        ocurrido = f"{ocurrido + ' ' if ocurrido else ''}{_capitalizar(log.notas_resultado).rstrip('.')}."
    return {
        'esperado': ' '.join(esperado) or None,
        'ocurrido': ocurrido,
        'sabia': _lineas_sabia(log),
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

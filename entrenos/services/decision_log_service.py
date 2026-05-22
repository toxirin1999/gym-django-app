"""
Sistema de log de decisiones de progresión y autoaprendizaje.

Flujo:
  1. Al guardar un EntrenoRealizado → evaluar decisiones pendientes del cliente,
     luego generar nuevas decisiones para los ejercicios de esa sesión.
  2. La vista dashboard_evolucion recoge logs y precisión del sistema.
"""

from datetime import timedelta
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
# Generación de decisiones
# ─────────────────────────────────────────────────────────────

def generar_decisiones_para_entreno(entreno):
    """
    Genera (o actualiza) una decisión de progresión para cada ejercicio
    del EntrenoRealizado recibido.  Se llama justo después de guardar el entreno.
    """
    from entrenos.models import EjercicioRealizado, GymDecisionLog, GymAdaptationProfile

    cliente = entreno.cliente
    ejercicios = EjercicioRealizado.objects.filter(
        entreno=entreno, completado=True
    ).order_by('nombre_ejercicio')

    for ej in ejercicios:
        nombre = ej.nombre_ejercicio.strip().lower()
        if not nombre:
            continue

        # Historial de las últimas 5 sesiones de este ejercicio
        historial = list(
            EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__iexact=nombre,
                completado=True
            ).exclude(entreno=entreno)
            .order_by('-entreno__fecha', '-fecha_creacion')
            .select_related('entreno')[:5]
        )

        # No generar decisión si ya hay una para este ejercicio hoy
        # (evita duplicados cuando entreno.save() dispara el signal más de una vez)
        existe = GymDecisionLog.objects.filter(
            cliente=cliente,
            ejercicio__iexact=nombre,
            fecha_creacion__date=timezone.localdate(),
        ).exists()
        if existe:
            continue

        perfil, _ = GymAdaptationProfile.objects.get_or_create(
            cliente=cliente,
            ejercicio=nombre,
        )

        # Nivel de confianza basado en historial disponible
        n_logs = GymDecisionLog.objects.filter(
            cliente=cliente, ejercicio__iexact=nombre
        ).count()
        if n_logs < 3:
            confianza = 'baja'
        elif n_logs < 6:
            confianza = 'media'
        else:
            confianza = 'alta'

        peso = ej.peso_kg or 0
        reps = ej.repeticiones
        rpe = float(ej.rpe) if ej.rpe is not None else None
        fallo = ej.fallo_muscular
        es_tope = ej.es_tope_maquina

        accion, valor_cambio, motivo = _decidir_accion(
            ej, historial, perfil, rpe, fallo, es_tope
        )

        GymDecisionLog.objects.create(
            cliente=cliente,
            ejercicio=nombre,
            peso_anterior=peso,
            reps_anteriores=reps,
            rpe_anterior=rpe,
            accion=accion,
            valor_cambio=valor_cambio,
            motivo=motivo,
            confianza=confianza,
        )


def _decidir_accion(ej, historial, perfil, rpe, fallo, es_tope):
    """Devuelve (accion, valor_cambio, motivo) para un ejercicio dado."""

    # 1. Fallo muscular — distinguir intencional (RIR=0) de exceso de carga
    if fallo:
        fallo_intencional = (ej.rir is not None and ej.rir == 0)
        if fallo_intencional:
            # Fallo buscado deliberadamente — consolidar sin penalizar
            return (
                'mantener',
                None,
                'Fallo muscular intencional (RIR=0) — consolidar antes de progresar',
            )
        if rpe is not None and rpe >= 9.5:
            return (
                'bajar_peso',
                perfil.reduccion_peso_pct,
                'Fallo muscular con RPE extremo (≥9.5) — carga excesiva',
            )
        return (
            'mantener',
            None,
            'Fallo muscular sin RPE extremo — mantener carga y vigilar técnica',
        )

    # RPE extremo sin fallo → reducir
    if rpe is not None and rpe >= 9.5:
        return (
            'bajar_peso',
            perfil.reduccion_peso_pct,
            'RPE extremo (≥9.5) detectado — reducir carga',
        )

    # 2. Tope de máquina → subir reps
    if es_tope:
        return (
            'subir_reps',
            None,
            'Tope de máquina alcanzado — progresión por repeticiones',
        )

    # 3. RPE alto sostenido (≥8.5 en las últimas 2 sesiones) → reducir
    if rpe is not None and rpe >= 8.5 and len(historial) >= 2:
        rpes_prev = [h.rpe for h in historial[:2] if h.rpe is not None]
        if len(rpes_prev) >= 2 and all(r >= 8 for r in rpes_prev):
            return (
                'bajar_peso',
                perfil.reduccion_peso_pct,
                'RPE alto sostenido en múltiples sesiones consecutivas',
            )
        return (
            'mantener',
            None,
            'Sesión intensa — consolidar antes de progresar',
        )

    # 4. RPE controlado + 2 sesiones exitosas → subir peso
    if rpe is not None and rpe <= 7.5 and len(historial) >= 1:
        prev = historial[0]
        prev_rpe = prev.rpe if prev.rpe is not None else 8
        prev_fallo = prev.fallo_muscular
        if prev_rpe <= 8 and not prev_fallo:
            return (
                'subir_peso',
                perfil.incremento_peso_pct,
                'Completado con éxito en 2 sesiones consecutivas con RPE controlado',
            )

    # 5. Default: mantener
    return (
        'mantener',
        None,
        'Parámetros estables — mantener y enfocar en técnica',
    )


# ─────────────────────────────────────────────────────────────
# Evaluación de decisiones previas
# ─────────────────────────────────────────────────────────────

def evaluar_decisiones_para_entreno(entreno):
    """
    Para cada ejercicio del entreno recibido, busca la última decisión
    pendiente y la evalúa comparando con la sesión actual.
    """
    from entrenos.models import EjercicioRealizado, GymDecisionLog, GymAdaptationProfile

    cliente = entreno.cliente
    ejercicios = EjercicioRealizado.objects.filter(
        entreno=entreno, completado=True
    )

    for ej in ejercicios:
        nombre = ej.nombre_ejercicio.strip().lower()
        if not nombre:
            continue

        log = GymDecisionLog.objects.filter(
            cliente=cliente,
            ejercicio__iexact=nombre,
            resultado__isnull=True,
        ).order_by('-fecha_creacion').first()

        if not log:
            continue

        _evaluar_log(log, ej)
        _actualizar_perfil(cliente, nombre)


def _evaluar_log(log, nueva_sesion):
    """Actualiza resultado y notas del log según la nueva sesión."""
    rpe_nuevo = nueva_sesion.rpe
    fallo_nuevo = nueva_sesion.fallo_muscular
    peso_nuevo = nueva_sesion.peso_kg or 0
    reps_nuevas = nueva_sesion.repeticiones

    peso_anterior = log.peso_anterior or 0
    reps_anteriores = log.reps_anteriores or 0

    if fallo_nuevo or (rpe_nuevo is not None and rpe_nuevo >= 9.5):
        resultado = 'fallida'
        notas = 'Carga excesiva: fallo o RPE extremo en la sesión posterior'
    elif log.accion == 'subir_peso' and peso_nuevo > peso_anterior:
        if rpe_nuevo is not None and rpe_nuevo <= 8.5 and not fallo_nuevo:
            resultado = 'validada'
            notas = 'Subida de peso completada con RPE aceptable'
        else:
            resultado = 'neutra'
            notas = 'Subida realizada pero RPE elevado'
    elif log.accion == 'subir_reps' and reps_nuevas > reps_anteriores:
        resultado = 'validada'
        notas = 'Incremento de repeticiones confirmado'
    elif log.accion in ('bajar_peso', 'deload') and peso_nuevo <= peso_anterior:
        if rpe_nuevo is not None and rpe_nuevo <= 8:
            resultado = 'validada'
            notas = 'Reducción aplicada y RPE mejoró'
        else:
            resultado = 'neutra'
            notas = 'Reducción aplicada pero RPE sigue alto'
    elif log.accion == 'mantener' and abs(peso_nuevo - peso_anterior) < 0.5:
        resultado = 'validada'
        notas = 'Peso mantenido según la recomendación'
    else:
        resultado = 'neutra'
        notas = 'Sin cambio claro respecto a la decisión'

    log.resultado = resultado
    log.notas_resultado = notas
    log.fecha_evaluacion = timezone.now()
    log.save(update_fields=['resultado', 'notas_resultado', 'fecha_evaluacion'])


def _actualizar_perfil(cliente, ejercicio):
    """Recalcula estadísticas del GymAdaptationProfile y ajusta incrementos."""
    from entrenos.models import GymDecisionLog, GymAdaptationProfile

    perfil, _ = GymAdaptationProfile.objects.get_or_create(
        cliente=cliente, ejercicio=ejercicio
    )

    logs = GymDecisionLog.objects.filter(
        cliente=cliente,
        ejercicio__iexact=ejercicio,
        resultado__isnull=False,
    )

    totales = logs.count()
    validadas = logs.filter(resultado='validada').count()
    fallidas = logs.filter(resultado='fallida').count()

    perfil.decisiones_totales = totales
    perfil.decisiones_validadas = validadas
    perfil.decisiones_fallidas = fallidas

    # Ajustar incremento según tendencia de las últimas 3 subidas de peso.
    # Se aplica un único ajuste basado en la mayoría, no acumulativo.
    ultimas_subidas = list(logs.filter(accion='subir_peso').order_by('-fecha_creacion')[:3])
    if ultimas_subidas:
        n_fallidas = sum(1 for d in ultimas_subidas if d.resultado == 'fallida')
        n_validadas = sum(1 for d in ultimas_subidas if d.resultado == 'validada')
        if n_fallidas >= 2:
            perfil.incremento_peso_pct = max(perfil.incremento_peso_pct * 0.80, 2.5)
        elif n_validadas >= 2:
            perfil.incremento_peso_pct = min(perfil.incremento_peso_pct * 1.10, 7.5)

    # Ajustar reducción según tendencia de las últimas 3 bajadas de peso.
    # Fallida/neutra → la reducción no fue suficiente → aumentar %.
    # Validada → la reducción funcionó o fue excesiva → reducir %.
    ultimas_bajadas = list(
        logs.filter(accion__in=('bajar_peso', 'deload')).order_by('-fecha_creacion')[:3]
    )
    if ultimas_bajadas:
        n_insuf = sum(1 for d in ultimas_bajadas if d.resultado in ('fallida', 'neutra'))
        n_ok    = sum(1 for d in ultimas_bajadas if d.resultado == 'validada')
        if n_insuf >= 2:
            perfil.reduccion_peso_pct = min(perfil.reduccion_peso_pct * 1.20, 20.0)
        elif n_ok >= 2:
            perfil.reduccion_peso_pct = max(perfil.reduccion_peso_pct * 0.85, 5.0)

    # Confianza basada en total de logs
    if totales < 3:
        perfil.confianza = 'baja'
    elif totales < 6:
        perfil.confianza = 'media'
    else:
        perfil.confianza = 'alta'

    perfil.save()


# ─────────────────────────────────────────────────────────────
# Consultas para la vista
# ─────────────────────────────────────────────────────────────

def obtener_logs_recientes(cliente, limit=10):
    from entrenos.models import GymDecisionLog
    return list(
        GymDecisionLog.objects.filter(cliente=cliente)
        .order_by('-fecha_creacion')[:limit]
    )


def obtener_proximas_acciones(cliente):
    """
    Devuelve dict {nombre_ejercicio_lower: log} con la última
    decisión pendiente por ejercicio (para columna 'Próxima acción').
    """
    from entrenos.models import GymDecisionLog
    logs = GymDecisionLog.objects.filter(
        cliente=cliente, resultado__isnull=True
    ).order_by('ejercicio', '-fecha_creacion')

    proximas = {}
    for log in logs:
        key = log.ejercicio.lower()
        if key not in proximas:
            proximas[key] = log
    return proximas


def calcular_precision_sistema(cliente):
    """Devuelve {'precision': int, 'totales': int, 'validadas': int, 'fallidas': int}."""
    from entrenos.models import GymDecisionLog
    evaluadas = GymDecisionLog.objects.filter(
        cliente=cliente, resultado__isnull=False
    )
    totales = evaluadas.count()
    validadas = evaluadas.filter(resultado='validada').count()
    fallidas = evaluadas.filter(resultado='fallida').count()
    precision = round((validadas / totales) * 100) if totales else 0
    return {
        'precision': precision,
        'totales': totales,
        'validadas': validadas,
        'fallidas': fallidas,
    }


def resumen_decisiones_recientes(cliente, dias=30):
    """
    Devuelve un dict con conteo de acciones recientes para el bloque Coach IA.
    """
    from entrenos.models import GymDecisionLog
    desde = timezone.now() - timedelta(days=dias)
    logs = GymDecisionLog.objects.filter(cliente=cliente, fecha_creacion__gte=desde)

    subidas = logs.filter(accion='subir_peso').count()
    reducciones = logs.filter(accion__in=['bajar_peso', 'deload']).count()
    mantenidos = logs.filter(accion='mantener').count()
    total = logs.count()

    return {
        'subidas': subidas,
        'reducciones': reducciones,
        'mantenidos': mantenidos,
        'total': total,
    }

"""
Continuidad de entrenamiento — fuente ÚNICA de lectura de pausa/ausencia.

Phase Continuidad 1.0 — "La pausa no es deuda".

Principio: la app no interpreta una pausa como fallo. Detecta la interrupción
del ritmo y describe (todavía sin ejecutar) cómo debería ser una vuelta segura.

Contrato de esta fase (1.0):
  - Servicio PURO: no persiste nada, no toca cargas, no pide motivo, no UI.
  - Fuente única: el semáforo consume esta lectura en vez de calcular ausencia
    por su cuenta (consolidación), manteniendo el mismo comportamiento visible.
  - Los campos de acción (congelar_progresion, factor_*, bloquear_pr) son
    DESCRIPTIVOS aquí. Quien los ejecuta es Continuidad 1.1+.

Separación madre (decisión de diseño):
  - prudencia física = f(duración)   → aplicar_prudencia_retorno, factores
  - narrativa        = f(motivo)     → activar_narrativa_pausa (1.2+), motivo (1.3+)
  La duración manda sobre la prudencia; el motivo solo modula el relato.
  Un descanso planificado NO debe sonar a ruptura, pero si fueron muchos días
  sin carga, la vuelta sigue siendo prudente.
"""

from __future__ import annotations

from django.utils import timezone


# ── Umbrales por días sin gym (constantes tunables) ──────────────────────────
# 0-3 silencio · 4-5 leve · 6-10 clara · 11-20 larga · 21+ recalibración
NIVEL_NORMAL = 'normal'
NIVEL_LEVE = 'leve'
NIVEL_CLARA = 'clara'
NIVEL_LARGA = 'larga'
NIVEL_RECALIBRACION = 'recalibracion'

_UMBRAL_LEVE = 4
_UMBRAL_CLARA = 6
_UMBRAL_LARGA = 11
_UMBRAL_RECALIBRACION = 21

# Niveles que cuentan como pausa significativa (a partir de 'clara').
_NIVELES_PAUSA = {NIVEL_CLARA, NIVEL_LARGA, NIVEL_RECALIBRACION}

# Factores DESCRIPTIVOS de prudencia física por nivel (los ejecuta 1.1+).
# Conservadores a propósito: congelar antes que bajar; reducir volumen antes
# que peso. La recalibración real (cargas base, RM, PRs) es Continuidad 1.5.
_FACTOR_VOLUMEN = {
    NIVEL_NORMAL: 1.0, NIVEL_LEVE: 1.0,
    NIVEL_CLARA: 0.85, NIVEL_LARGA: 0.75, NIVEL_RECALIBRACION: 0.75,
}
_FACTOR_CARGA = {
    NIVEL_NORMAL: 1.0, NIVEL_LEVE: 1.0,
    NIVEL_CLARA: 1.0,          # clara: mantener carga, no bajar
    NIVEL_LARGA: 0.95, NIVEL_RECALIBRACION: 0.90,
}


# ── Auditoría de lenguaje SEMÁNTICA (no blacklist ciega) ─────────────────────
# Prohibido: expresiones de DEUDA (culpa). Permitido: uso protector
# ("No tienes que compensar", "sin compensar de golpe").
EXPRESIONES_DEUDA_PROHIBIDAS = (
    'tienes que compensar',
    'recuperar lo perdido',
    'ponerte al día',
    'ponerte al dia',
    'has perdido',
    'te alejaste',
)


def auditar_lenguaje_continuidad(texto: str) -> list[str]:
    """Devuelve las expresiones de deuda encontradas (vacío = limpio).

    Semántico, no blacklist ciega: la forma NEGADA protectora se permite.
    'No tienes que compensar' es válido; 'tienes que compensar' no.
    """
    if not texto:
        return []
    import re
    bajo = texto.lower()
    encontradas = []
    for e in EXPRESIONES_DEUDA_PROHIBIDAS:
        if e == 'tienes que compensar':
            # permitir "no tienes que compensar" (uso protector)
            if re.search(r'(?<!no )tienes que compensar', bajo):
                encontradas.append(e)
        elif e in bajo:
            encontradas.append(e)
    return encontradas


def _nivel_por_dias(dias_sin_gym):
    if dias_sin_gym is None:
        return NIVEL_NORMAL
    if dias_sin_gym >= _UMBRAL_RECALIBRACION:
        return NIVEL_RECALIBRACION
    if dias_sin_gym >= _UMBRAL_LARGA:
        return NIVEL_LARGA
    if dias_sin_gym >= _UMBRAL_CLARA:
        return NIVEL_CLARA
    if dias_sin_gym >= _UMBRAL_LEVE:
        return NIVEL_LEVE
    return NIVEL_NORMAL


def _dias_desde_ultima(cliente, hoy, tipo=None):
    """Días desde la última ActividadRealizada (de un tipo, o cualquiera).

    Replica la lógica histórica de DailyDecisionEngine._calcular_ausencia_dias
    para 'cualquiera': 0 si no hay actividad; max(delta, 0) en otro caso.
    Para un tipo concreto devuelve None si nunca hubo actividad de ese tipo
    (distingue 'nunca ha hecho gym' de 'hizo gym hoy').
    """
    from entrenos.models import ActividadRealizada
    qs = ActividadRealizada.objects.filter(cliente=cliente)
    if tipo is not None:
        qs = qs.filter(tipo=tipo)
    ultima = qs.order_by('-fecha').values_list('fecha', flat=True).first()
    if ultima is None:
        return 0 if tipo is None else None
    return max((hoy - ultima).days, 0)


def evaluar_continuidad_entrenamiento(cliente, fecha_ref=None, es_descanso_plan=None) -> dict:
    """Lectura única de continuidad de entrenamiento.

    Args:
        cliente: Cliente.
        fecha_ref: fecha de referencia (default hoy). Útil para tests.
        es_descanso_plan: si el plan marca hoy como descanso/no-sesión. Señal
            de hoy (no de toda la ventana); se usa para no narrar como ruptura
            algo que el propio plan programó. Si None → no se asume descanso.

    Returns: dict descriptivo (ver módulo). Los campos de acción NO se ejecutan
    en 1.0.
    """
    hoy = fecha_ref or timezone.now().date()

    dias_sin_gym = _dias_desde_ultima(cliente, hoy, tipo='gym')
    dias_sin_actividad = _dias_desde_ultima(cliente, hoy, tipo=None)  # paridad semáforo

    nivel = _nivel_por_dias(dias_sin_gym)
    hay_pausa_significativa = nivel in _NIVELES_PAUSA
    es_descanso_planificado = bool(es_descanso_plan)

    # tipo de pausa (en 1.0 el motivo aún no se captura → nunca 'pausa_declarada')
    if es_descanso_planificado:
        tipo = 'descanso_planificado'
    elif hay_pausa_significativa:
        tipo = 'pausa_no_declarada'
    else:
        tipo = 'sin_pausa'

    # narrativa: NO sonar a ruptura si fue descanso planificado.
    activar_narrativa_pausa = hay_pausa_significativa and not es_descanso_planificado
    # prudencia física: aplica aunque fuera planificado, si hubo muchos días.
    aplicar_prudencia_retorno = hay_pausa_significativa

    return {
        'nivel': nivel,
        'dias_sin_gym': dias_sin_gym,
        'dias_sin_actividad': dias_sin_actividad,
        'hay_pausa_significativa': hay_pausa_significativa,
        'es_descanso_planificado': es_descanso_planificado,
        'tipo': tipo,
        'activar_narrativa_pausa': activar_narrativa_pausa,
        'aplicar_prudencia_retorno': aplicar_prudencia_retorno,
        # ── acción (DESCRIPTIVO en 1.0; ejecuta 1.1+) ──
        'congelar_progresion': hay_pausa_significativa,
        'factor_volumen': _FACTOR_VOLUMEN[nivel],
        'factor_carga': _FACTOR_CARGA[nivel],
        'bloquear_pr': hay_pausa_significativa,
        # ── motivo (lo declara el usuario en 1.3; aquí siempre desconocido) ──
        'motivo': 'desconocido',
        'fuente': 'continuidad_service',
    }

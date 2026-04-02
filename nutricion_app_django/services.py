"""
Motor nutricional v2 — Sistema de Bloques + PAS
────────────────────────────────────────────────
Funciones principales:
  - generar_target_diario()        Sprint 2
  - get_tipo_sesion_hoy()          Sprint 2
  - analisis_semanal_pas()         Sprint 5 (esqueleto)
  - _safety_lock_check()           Sprint 5
"""

import math
from datetime import date, timedelta

from .bloques_alimentos import (
    calcular_bloques_dia,
    distribuir_bloques_comidas,
    GRAMOS_POR_BLOQUE,
)


# ─────────────────────────────────────────────────────────────
# DETECCIÓN DE TIPO DE SESIÓN
# ─────────────────────────────────────────────────────────────

def get_tipo_sesion_hoy(cliente, fecha=None):
    """
    Determina el tipo de sesión para una fecha dada.

    Jerarquía de detección:
    1. [FUTURO] Sesión Hyrox registrada → 'hyrox'
    2. EntrenoRealizado ese día → 'gym'
    3. Default → 'descanso'

    Returns: 'gym' | 'hyrox' | 'descanso'
    """
    if fecha is None:
        fecha = date.today()

    if _detectar_sesion_hyrox(cliente, fecha):
        return 'hyrox'

    if _detectar_sesion_gym(cliente, fecha):
        return 'gym'

    return 'descanso'


def _detectar_sesion_gym(cliente, fecha):
    """Comprueba si hay un EntrenoRealizado ese día para el cliente."""
    try:
        from entrenos.models import EntrenoRealizado
        return EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha=fecha
        ).exists()
    except Exception:
        return False


def _detectar_sesion_hyrox(cliente, fecha):
    """
    Hook de integración futura con el módulo Hyrox.
    Cuando Hyrox guarde sesiones, implementar aquí.
    """
    # TODO: cuando HyroxSesion exista:
    # from hyrox.models import HyroxSesion
    # return HyroxSesion.objects.filter(cliente=cliente, fecha=fecha).exists()
    return False


# ─────────────────────────────────────────────────────────────
# GENERACIÓN DE TARGET DIARIO
# ─────────────────────────────────────────────────────────────

def generar_target_diario(cliente, fecha=None, tipo_sesion=None):
    """
    Crea o actualiza el TargetNutricionalDiario para un cliente y fecha.

    Args:
        cliente:      instancia de clientes.Cliente
        fecha:        date (default: hoy)
        tipo_sesion:  'gym' | 'hyrox' | 'descanso' | None (auto-detect)

    Returns:
        TargetNutricionalDiario instance
    """
    from .models import TargetNutricionalDiario

    if fecha is None:
        fecha = date.today()

    try:
        perfil = cliente.perfil_nutricional
    except Exception:
        return None

    if tipo_sesion is None:
        tipo_sesion = get_tipo_sesion_hoy(cliente, fecha)

    bloques = calcular_bloques_dia(
        lean_mass_kg=perfil.masa_magra_kg,
        fase=perfil.fase,
        tipo_sesion=tipo_sesion,
    )

    bloques = _aplicar_ajustes_historicos(cliente, bloques, tipo_sesion)
    distribucion = distribuir_bloques_comidas(bloques, tipo_sesion)

    target, _ = TargetNutricionalDiario.objects.update_or_create(
        cliente=cliente,
        fecha=fecha,
        defaults={
            'tipo_sesion':          tipo_sesion,
            'bloques_proteina':     bloques["P"],
            'bloques_carbos':       bloques["C"],
            'bloques_grasas':       bloques["G"],
            'bloques_verduras':     3,
            'proteina_g_ref':       bloques["P_g"],
            'carbos_g_ref':         bloques["C_g"],
            'grasas_g_ref':         bloques["G_g"],
            'distribucion_comidas': distribucion,
        }
    )
    return target


def _aplicar_ajustes_historicos(cliente, bloques, tipo_sesion):
    """Aplica el último ajuste aceptado del PAS a los bloques calculados."""
    try:
        from .models import InformeOptimizacion
        ultimo = InformeOptimizacion.objects.filter(
            cliente=cliente,
            estado='aceptado',
        ).order_by('-semana').first()

        if not ultimo:
            return bloques

        aplica = ultimo.ajuste_aplica_a
        if aplica not in ('todos', tipo_sesion):
            return bloques

        bloques["P"] = max(1, bloques["P"] + ultimo.ajuste_bloques_proteina)
        bloques["C"] = max(1, bloques["C"] + ultimo.ajuste_bloques_carbos)
        bloques["G"] = max(1, bloques["G"] + ultimo.ajuste_bloques_grasas)
        bloques["P_g"] = bloques["P"] * GRAMOS_POR_BLOQUE["P"]
        bloques["C_g"] = bloques["C"] * GRAMOS_POR_BLOQUE["C"]
        bloques["G_g"] = bloques["G"] * GRAMOS_POR_BLOQUE["G"]
    except Exception:
        pass

    return bloques


# ─────────────────────────────────────────────────────────────
# MÉTRICAS SEMANALES
# ─────────────────────────────────────────────────────────────

def calcular_cumplimiento_semana(cliente, lunes):
    from .models import CheckNutricionalDiario
    domingo = lunes + timedelta(days=6)
    checks = CheckNutricionalDiario.objects.filter(
        cliente=cliente, fecha__range=(lunes, domingo)
    )
    if not checks.exists():
        return 0.0
    return round(sum(c.cumplimiento_pct for c in checks) / checks.count(), 1)


def calcular_media_peso_semana(cliente, lunes):
    """Returns: (media: float | None, n_pesajes: int)"""
    from clientes.models import PesoDiario
    domingo = lunes + timedelta(days=6)
    pesos = list(
        PesoDiario.objects
        .filter(cliente=cliente, fecha__range=(lunes, domingo))
        .values_list('peso_kg', flat=True)
    )
    if len(pesos) < 2:
        return None, len(pesos)
    return round(sum(pesos) / len(pesos), 2), len(pesos)


def calcular_rendimiento_gym_delta(cliente, lunes):
    """% de cambio en volumen total gym respecto a la semana anterior."""
    try:
        domingo      = lunes + timedelta(days=6)
        lunes_prev   = lunes - timedelta(days=7)
        domingo_prev = lunes - timedelta(days=1)
        vol_actual   = _volumen_semana(cliente, lunes, domingo)
        vol_prev     = _volumen_semana(cliente, lunes_prev, domingo_prev)
        if not vol_prev or not vol_actual:
            return None
        return round((vol_actual - vol_prev) / vol_prev * 100, 1)
    except Exception:
        return None


def _volumen_semana(cliente, inicio, fin):
    try:
        from entrenos.models import EntrenoRealizado
        from django.db.models import Sum
        result = EntrenoRealizado.objects.filter(
            cliente=cliente, fecha__range=(inicio, fin)
        ).aggregate(total=Sum('volumen_total_kg'))
        return result['total'] or 0
    except Exception:
        return 0


def _fatiga_media_semana(cliente, lunes):
    from .models import CheckNutricionalDiario
    domingo = lunes + timedelta(days=6)
    valores = list(
        CheckNutricionalDiario.objects.filter(
            cliente=cliente,
            fecha__range=(lunes, domingo),
            fatiga_percibida__isnull=False,
        ).values_list('fatiga_percibida', flat=True)
    )
    if not valores:
        return None
    return round(sum(valores) / len(valores), 1)


# ─────────────────────────────────────────────────────────────
# SAFETY LOCK
# ─────────────────────────────────────────────────────────────

def _safety_lock_check(cliente, bloques_nuevos):
    """
    Returns: (es_seguro: bool, motivo: str | None)
    """
    try:
        perfil = cliente.perfil_nutricional
        peso_actual = perfil._get_peso_actual()

        min_proteina_g = perfil.masa_magra_kg * perfil.safety_proteina_min_g_kg
        min_grasa_g    = peso_actual * perfil.safety_grasa_min_g_kg

        min_bloques_p = math.ceil(min_proteina_g / GRAMOS_POR_BLOQUE["P"])
        min_bloques_g = math.ceil(min_grasa_g    / GRAMOS_POR_BLOQUE["G"])

        if bloques_nuevos.get("P", 99) < min_bloques_p:
            return False, (
                f"Safety lock: proteína mínima {min_proteina_g:.0f}g "
                f"({min_bloques_p} bloques)."
            )
        if bloques_nuevos.get("G", 99) < min_bloques_g:
            return False, (
                f"Safety lock: grasa mínima {min_grasa_g:.0f}g "
                f"({min_bloques_g} bloques)."
            )
        return True, None
    except Exception:
        return True, None


# ─────────────────────────────────────────────────────────────
# PAS — PROTOCOLO DE AJUSTE SEMANAL
# ─────────────────────────────────────────────────────────────

UMBRAL_CUMPLIMIENTO_MINIMO = 90.0

def analisis_semanal_pas(cliente, lunes=None):
    """
    Genera el InformeOptimizacion de la semana.
    Llamado por Celery cada lunes a las 7:00.
    """
    from .models import InformeOptimizacion, TargetNutricionalDiario

    if lunes is None:
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())

    lunes_anterior = lunes - timedelta(days=7)

    cumplimiento   = calcular_cumplimiento_semana(cliente, lunes_anterior)
    media_nueva,  _= calcular_media_peso_semana(cliente, lunes_anterior)
    media_previa, _= calcular_media_peso_semana(cliente, lunes_anterior - timedelta(days=7))
    fatiga_media   = _fatiga_media_semana(cliente, lunes_anterior)
    delta_gym      = calcular_rendimiento_gym_delta(cliente, lunes_anterior)

    # REGLA 0: cumplimiento insuficiente → no ajustar
    if cumplimiento < UMBRAL_CUMPLIMIENTO_MINIMO:
        informe, _ = InformeOptimizacion.objects.update_or_create(
            cliente=cliente, semana=lunes,
            defaults={
                'media_peso_anterior':     media_previa,
                'media_peso_nueva':        media_nueva,
                'cumplimiento_semana_pct': cumplimiento,
                'fatiga_media':            fatiga_media,
                'rendimiento_gym_delta_pct': delta_gym,
                'escenario':    'X',
                'justificacion': (
                    f"Cumplimiento: {cumplimiento:.0f}% "
                    f"(mínimo requerido: {UMBRAL_CUMPLIMIENTO_MINIMO:.0f}%). "
                    "No puedo ajustar sin datos fiables. "
                    "Apunta al 90%+ esta semana y decidimos juntos."
                ),
                'ajuste_bloques_proteina': 0,
                'ajuste_bloques_carbos':   0,
                'ajuste_bloques_grasas':   0,
                'estado': 'pendiente',
            }
        )
        return informe

    # Clasificar escenario
    escenario, ajuste, justificacion, aplica_a = _clasificar_escenario(
        cliente=cliente,
        media_nueva=media_nueva,
        media_previa=media_previa,
        fatiga_media=fatiga_media,
        delta_gym=delta_gym,
    )

    # Safety lock
    safety_ok  = True
    diet_break = False
    target_actual = TargetNutricionalDiario.objects.filter(
        cliente=cliente, fecha__gte=lunes_anterior,
    ).order_by('-fecha').first()

    if target_actual and ajuste:
        bloques_prop = {
            "P": target_actual.bloques_proteina + ajuste.get("P", 0),
            "C": target_actual.bloques_carbos   + ajuste.get("C", 0),
            "G": target_actual.bloques_grasas   + ajuste.get("G", 0),
        }
        safety_ok, safety_msg = _safety_lock_check(cliente, bloques_prop)
        if not safety_ok:
            diet_break = True
            justificacion += (
                f" {safety_msg} "
                "Recomiendo una semana de mantenimiento (Diet Break) antes de reducir más."
            )
            ajuste = {"P": 0, "C": 0, "G": 0}

    alerta = _detectar_contradiccion(cumplimiento, media_nueva, media_previa, delta_gym)

    informe, _ = InformeOptimizacion.objects.update_or_create(
        cliente=cliente, semana=lunes,
        defaults={
            'media_peso_anterior':          media_previa,
            'media_peso_nueva':             media_nueva,
            'cumplimiento_semana_pct':      cumplimiento,
            'fatiga_media':                 fatiga_media,
            'rendimiento_gym_delta_pct':    delta_gym,
            'escenario':                    escenario,
            'alerta_honestidad':            alerta,
            'ajuste_bloques_proteina':      ajuste.get("P", 0) if ajuste else 0,
            'ajuste_bloques_carbos':        ajuste.get("C", 0) if ajuste else 0,
            'ajuste_bloques_grasas':        ajuste.get("G", 0) if ajuste else 0,
            'ajuste_aplica_a':              aplica_a,
            'justificacion':                justificacion,
            'safety_lock_activado':         not safety_ok,
            'diet_break_sugerido':          diet_break,
            'estado':                       'pendiente',
        }
    )
    return informe


def _clasificar_escenario(cliente, media_nueva, media_previa,
                           fatiga_media, delta_gym):
    """Matriz de decisión del PAS."""
    try:
        fase = cliente.perfil_nutricional.fase
    except Exception:
        fase = 'mantenimiento'

    delta_peso_pct = None
    if media_nueva and media_previa and media_previa > 0:
        delta_peso_pct = (media_nueva - media_previa) / media_previa * 100

    # Escenario C: fatiga alta o pérdida de peso demasiado rápida
    if (fatiga_media and fatiga_media >= 7.0) or (delta_peso_pct and delta_peso_pct < -1.0):
        return (
            'C',
            {"P": 0, "C": +3, "G": 0},
            "Tu fatiga es elevada o estás perdiendo peso demasiado rápido. "
            "He añadido 3 bloques de hidratos en tus días de Hyrox (Refeed técnico). "
            "Rendimiento y recuperación son la prioridad esta semana.",
            'hyrox',
        )

    # Escenario D: peso sube en definición
    if delta_peso_pct and delta_peso_pct > 0.3 and fase == 'definicion':
        return (
            'D',
            None,
            "Tu peso ha subido esta semana y tu objetivo es definición. "
            "Antes de ajustar, revisa si las porciones de los bloques fueron correctas. "
            "¿Seguro que el tamaño de cada bloque fue el indicado?",
            'todos',
        )

    # Escenario B: estancamiento
    if delta_peso_pct is not None and abs(delta_peso_pct) <= 0.2:
        if fase == 'definicion':
            return (
                'B',
                {"P": 0, "C": -1, "G": -1},
                "Tu peso no se mueve. He reducido 1 bloque de grasa en días de entreno "
                "y 1 bloque de hidratos en días de descanso. "
                "La proteína no se toca — es tu herramienta de recuperación.",
                'descanso',
            )
        elif fase == 'volumen':
            return (
                'B',
                {"P": 0, "C": +1, "G": 0},
                "Tu peso no sube y estás en volumen. "
                "He añadido 1 bloque de hidratos en la ventana peri-entrenamiento.",
                'gym',
            )

    # Escenario A: óptimo
    return (
        'A',
        {"P": 0, "C": 0, "G": 0},
        "Tus datos están en el rango óptimo. "
        "No hay cambios en tus bloques esta semana. "
        "No toques lo que funciona.",
        'todos',
    )


def _detectar_contradiccion(cumplimiento, media_nueva, media_previa, delta_gym):
    """Alerta de honestidad: cumplimiento alto pero resultados negativos."""
    if cumplimiento < 85:
        return False
    if not (media_nueva and media_previa and media_previa > 0):
        return False
    delta_peso_pct = (media_nueva - media_previa) / media_previa * 100
    return delta_peso_pct > 0.5 and delta_gym is not None and delta_gym < -3

# core/daily_decision.py
# detectar_patron_resistencia() está al final del módulo.
"""
DailyDecisionEngine — Semáforo de Intención.

Funde ACWR, TSB, Readiness, HRV y energía subjetiva en un único estado accionable.
El usuario nunca ve los números; ve el veredicto.
"""
from __future__ import annotations
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class DailyDecisionEngine:

    VERDE    = 'verde'
    AMARILLO = 'amarillo'
    NARANJA  = 'naranja'
    ROJO     = 'rojo'

    _TITULOS = {
        'verde':    'SISTEMA NOMINAL',
        'amarillo': 'GESTIÓN DE DAÑOS',
        'naranja':  'DRENAJE VITAL',
        'rojo':     'PARADA TÉCNICA',
    }

    # Mensajes base (sin paradoja)
    _MENSAJES = {
        'verde':    "Hoy eres peligroso. Tienes permiso para romper tus límites. No te guardes nada.",
        'amarillo': "Estás en el filo. Puedes entrenar, pero no busques récords hoy. Escucha a tu cuerpo, no a tu ego.",
        'naranja':  "Te estás volviendo blando. Has bajado tanto el ritmo que el próximo esfuerzo fuerte te puede romper. Muévete ya.",
        'rojo':     "Hoy el gimnasio es tu enemigo. Si vas, te vas a lesionar. Tu única tarea hoy es descansar y habitar el vacío.",
    }

    # Paradoja A: cabeza dice "sigue" / cuerpo dice "para"
    _PARADOJA_A = (
        "Esa voz que te pide seguir no es disciplina, es miedo a perder el control. "
        "Para ahora o el cuerpo parará por ti con una lesión."
    )

    # Paradoja B: cabeza dice "para" / cuerpo dice "sigue"
    _PARADOJA_B = (
        "Tus datos dicen que estás perfecto. No estás cansado, estás aburrido o complaciente. "
        "Ve al gimnasio y cumple."
    )

    @classmethod
    def get_estado_hoy(cls, cliente) -> Dict[str, Any]:
        """
        Devuelve el estado unificado del día.

        Returns dict con:
            estado       – verde / amarillo / naranja / rojo
            titulo       – etiqueta corta para el UI
            tipo_fatiga  – alineado / mecanica / vital / fragilidad / flojera
            mensaje      – lo que JOI dice (incluye paradoja si aplica)
            paradoja     – 'A' | 'B' | None
            datos_raw    – números técnicos ocultos al usuario (para JOI context)
        """
        from core.bio_context import BioContextProvider

        # ── 1. Bio signals ────────────────────────────────────────
        bio = BioContextProvider.get_bio_signals(cliente)
        readiness_data = BioContextProvider.get_readiness_score(cliente)
        readiness_pct = readiness_data['score'] * 100

        # ── 2. ACWR unificado (gym + hyrox + carrera) ─────────────
        acwr = None
        try:
            from entrenos.services.services import EstadisticasService
            acwr_data = EstadisticasService.analizar_acwr_unificado(cliente)
            v = acwr_data.get('acwr_actual')
            acwr = float(v) if v else None
        except Exception:
            pass

        # ── 3. TSB (Hyrox si hay objetivo activo) ─────────────────
        tsb = None
        try:
            from hyrox.models import HyroxObjective
            from hyrox.training_engine import HyroxLoadManager
            objetivo = HyroxObjective.objects.filter(
                cliente=cliente, estado='activo'
            ).first()
            if objetivo:
                carga = HyroxLoadManager.calcular_ctl_atl_tsb(objetivo)
                tsb = carga.get('tsb')
                if tsb is not None:
                    tsb = float(tsb)
        except Exception:
            pass

        # ── 4. HRV: comparar con media 14 días ────────────────────
        hrv_hundido = False
        if bio['has_data'] and bio['hrv_ms']:
            try:
                from clientes.models import BitacoraDiaria
                from django.utils import timezone
                from django.db.models import Avg
                hoy = timezone.now().date()
                hrv_mean = BitacoraDiaria.objects.filter(
                    cliente=cliente,
                    hrv_ms__isnull=False,
                    fecha__gte=hoy - timezone.timedelta(days=14),
                    fecha__lt=hoy,
                ).aggregate(avg=Avg('hrv_ms'))['avg']
                if hrv_mean and bio['hrv_ms'] < hrv_mean * 0.85:
                    hrv_hundido = True
            except Exception:
                pass

        energia = bio.get('energia')  # 1-10 subjetivo

        # ── 5. Lógica de estados (prioridad: ROJO > NARANJA > AMARILLO > VERDE) ──

        # ROJO: cuerpo al límite — no negociar
        cond_rojo = (
            readiness_pct < 40
            or (hrv_hundido and tsb is not None and tsb < -25)
            or (readiness_pct < 50 and tsb is not None and tsb < -20)
        )

        # AMARILLO: carga mecánica alta — entrenar con cuidado
        cond_amarillo = (
            (acwr is not None and acwr > 1.5)
            or (tsb is not None and tsb < -20)
        )

        # NARANJA: subutilización + cuerpo fresco — riesgo de fragilidad
        cond_naranja = (
            acwr is not None
            and acwr < 0.7
            and readiness_pct > 60
        )

        if cond_rojo:
            estado     = cls.ROJO
            tipo       = 'mecanica' if (tsb is not None and tsb < -20) else 'vital'
        elif cond_amarillo:
            estado     = cls.AMARILLO
            tipo       = 'mecanica'
        elif cond_naranja:
            estado     = cls.NARANJA
            tipo       = 'fragilidad'
        else:
            estado     = cls.VERDE
            tipo       = 'alineado'

        # ── 6. Detección de paradojas ─────────────────────────────
        paradoja = None

        # Paradoja A: métricas dicen STOP, cabeza quiere seguir (energía reportada alta)
        if estado in (cls.ROJO, cls.AMARILLO) and energia is not None and energia >= 7:
            paradoja = 'A'
            tipo     = 'mecanica'

        # Paradoja B: métricas dicen GO, cabeza quiere parar (energía baja pero números verdes)
        if estado == cls.VERDE and energia is not None and energia <= 4:
            paradoja = 'B'
            tipo     = 'flojera'

        # ── 7. Mensaje final ──────────────────────────────────────
        if paradoja == 'A':
            mensaje = cls._PARADOJA_A
        elif paradoja == 'B':
            mensaje = cls._PARADOJA_B
        else:
            mensaje = cls._MENSAJES[estado]

        return {
            'estado':      estado,
            'titulo':      cls._TITULOS[estado],
            'tipo_fatiga': tipo,
            'mensaje':     mensaje,
            'paradoja':    paradoja,
            'datos_raw': {
                'acwr':          round(acwr, 2) if acwr is not None else None,
                'tsb':           round(tsb, 1) if tsb is not None else None,
                'readiness_pct': round(readiness_pct, 1),
                'hrv_ms':        bio.get('hrv_ms'),
                'hrv_hundido':   hrv_hundido,
                'energia':       energia,
                'horas_sueno':   bio.get('horas_sueno'),
            },
        }


def detectar_patron_resistencia(cliente) -> bool:
    """
    Detector de resistencia psicológica al entrenamiento.

    Condición de disparo:
      - Hoy hay paradoja B (semáforo verde + energía subjetiva ≤ 4)
      - En los últimos 14 días hay ≥ 3 entradas en BitacoraDiaria con energía ≤ 4
      - No existe ya un patrón similar en ManualDavid (últimos 30 días)

    Si se cumplen todas → escribe automáticamente en ManualDavid con metadatos
    (frecuencia, día de semana más común, correlación con sueño).

    Returns True si se escribió una nueva entrada, False si no.
    """
    from collections import Counter
    from datetime import timedelta
    from django.utils import timezone
    from clientes.models import BitacoraDiaria
    from joi.models import ManualDavid

    # 1. Confirmar paradoja B activa hoy
    try:
        estado_hoy = DailyDecisionEngine.get_estado_hoy(cliente)
    except Exception:
        return False
    if estado_hoy.get('paradoja') != 'B':
        return False

    # 2. Contar ocurrencias de energía baja en 14 días
    hoy = timezone.now().date()
    ocurrencias = list(
        BitacoraDiaria.objects.filter(
            cliente=cliente,
            fecha__gte=hoy - timedelta(days=14),
            energia_subjetiva__lte=4,
        ).order_by('fecha')
    )
    if len(ocurrencias) < 3:
        return False

    # 3. Deduplicar: no escribir si ya hay un patrón reciente
    ya_existe = ManualDavid.objects.filter(
        user=cliente.user,
        origen='patron_detectado',
        entrada__contains='resistencia psicológica',
        creado_en__gte=timezone.now() - timedelta(days=30),
    ).exists()
    if ya_existe:
        return False

    # 4. Construir metadatos ricos
    n = len(ocurrencias)
    DIAS_ES = {
        'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles',
        'Thursday': 'jueves', 'Friday': 'viernes',
        'Saturday': 'sábado', 'Sunday': 'domingo',
    }
    dias = [DIAS_ES.get(o.fecha.strftime('%A'), o.fecha.strftime('%A')) for o in ocurrencias]
    dia_comun, freq_dia = Counter(dias).most_common(1)[0]
    dia_txt = (
        f" Día más frecuente: {dia_comun} ({freq_dia}/{n} veces)."
        if freq_dia >= 2 else ""
    )

    sueno_bajo = sum(1 for o in ocurrencias if o.horas_sueno and float(o.horas_sueno) < 6)
    sueno_txt = (
        f" Correlación con sueño <6h: {sueno_bajo}/{n} veces."
        if sueno_bajo >= 2 else ""
    )

    energia_media = round(
        sum(o.energia_subjetiva for o in ocurrencias if o.energia_subjetiva) / n, 1
    )

    entrada = (
        f"Patrón detectado: reporte de energía baja ({energia_media}/10 de media) "
        f"con semáforo en VERDE — {n} veces en 14 días.{dia_txt}{sueno_txt} "
        f"Los datos objetivos no respaldan el cansancio declarado. "
        f"Posible resistencia psicológica al entrenamiento."
    )

    ManualDavid.objects.create(
        user=cliente.user,
        entrada=entrada.strip(),
        origen='patron_detectado',
    )
    logger.info('[PatronResistencia] Nuevo patrón escrito en Manual de %s', cliente.user.username)
    return True

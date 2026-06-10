# core/daily_decision.py
# detectar_patron_resistencia() está al final del módulo.
"""
DailyDecisionEngine — Semáforo de Intención.

Funde ACWR, TSB, Readiness, HRV, energía subjetiva y ausencia en
cuatro estados accionables: empujar / sostener / recuperar / volver.
El usuario nunca ve los números; ve el veredicto.
"""
from __future__ import annotations
from typing import Any, Dict
import logging

# Phase 59X.B: imports al nivel de módulo para que los tests puedan
# parchear correctamente con @patch('core.daily_decision.<nombre>').
from core.bio_context import BioContextProvider
from core.context.actividad_context import get_actividad_context

logger = logging.getLogger(__name__)


class DailyDecisionEngine:

    EMPUJAR  = 'empujar'
    SOSTENER = 'sostener'
    RECUPERAR = 'recuperar'
    VOLVER   = 'volver'

    _TITULOS = {
        'empujar':  'EMPUJAR',
        'sostener': 'SOSTENER',
        'recuperar': 'RECUPERAR',
        'volver':   'VOLVER',
    }

    # Phase 59X.D: título override por causa (no cambia 'estado', solo la
    # etiqueta visible). Fragilidad = subutilización/margen, no "recuperar".
    _TITULOS_POR_CAUSA = {
        'fragilidad': 'EJECUTAR CON MARGEN',
    }

    # Mensajes base por estado (sin paradoja)
    # recuperar tiene dos variantes según tipo_recuperar
    _MENSAJES = {
        'empujar':             "Tus señales acompañan. Hoy puedes entrenar con intensidad.",
        'sostener':            "Hay margen, pero no sobra. Haz la sesión, sin perseguir el límite.",
        'recuperar_movimiento': "El cuerpo pide bajar intensidad. Puedes moverte, pero no apretar.",
        'recuperar_descanso':  "Hoy el progreso probablemente está en recuperar, no en forzar.",
        # Phase 59X.0: fragilidad = subutilización (ACWR bajo, estás fresco), no
        # fatiga. Marco de retorno, no de calma.
        'recuperar_fragilidad': "Vienes de menos carga de la habitual. La energía juega a favor: úsala para volver con margen, no para compensar de golpe.",
        'volver':              "No tienes que compensar la pausa. Haz algo posible y deja que la historia continúe.",
    }

    _RECOMENDACIONES_GYM = {
        'empujar':             "Progresión posible. Carga objetivo, rango completo.",
        'sostener':            "Versión normal sin llegar al fallo. Técnica primero.",
        'recuperar_movimiento': "Tren superior ligero o movilidad. Evita carga pesada.",
        'recuperar_descanso':  "Movilidad o descanso activo.",
        'recuperar_fragilidad': "Sesión ligera para recuperar el patrón. Sube carga poco a poco, sin saltos.",
        'volver':              "Una sesión mínima posible. Sin deuda, sin compensación.",
    }

    _RECOMENDACIONES_HYROX = {
        'empujar':             "Buen día para intensidad o umbral.",
        'sostener':            "Técnica de estaciones y carrera controlada.",
        'recuperar_movimiento': "Zona 2 suave o técnica sin carga.",
        'recuperar_descanso':  "Pausa. Zona 2 muy suave si necesitas moverte.",
        'recuperar_fragilidad': "Zona 2 o técnica para reenganchar. Recupera ritmo sin forzar.",
        'volver':              "Carrera suave o técnica básica. Recupera el ritmo.",
    }

    # Phase 59X.D: copy reasegurador para RECUPERAR durante una descarga
    # planificada (fase_plan.es_descarga=True). Sustituye al copy de
    # fatiga/fragilidad sin cambiar estado/causa/tipo_recuperar — evita
    # lenguaje de abandono, compensación o "volver con margen".
    _MENSAJE_RECUPERAR_DESCARGA_PLAN = (
        "Esta semana de descarga está calculada por el plan — no es una "
        "pausa que tengas que recuperar. Aprovecha el margen para "
        "consolidar lo trabajado, sin buscar compensar nada."
    )
    _RECOMENDACION_GYM_DESCARGA_PLAN = (
        "Sigue la sesión de descarga marcada por el plan: técnica y "
        "volumen reducido, sin buscar el límite."
    )
    _RECOMENDACION_HYROX_DESCARGA_PLAN = (
        "Zona 2 suave o técnica ligera según la descarga del plan. "
        "No hay nada que recuperar."
    )

    # Paradoja A: estado pide calma pero energía subjetiva alta
    _PARADOJA_A = (
        "Esa energía que sientes hoy puede ser real. "
        "Pero los datos piden calma. Escucha a ambos."
    )

    # Paradoja B: estado pide moverse pero energía subjetiva baja
    _PARADOJA_B = (
        "Los números dicen que estás bien. "
        "Si no te apetece, está bien también. Muévete, aunque sea poco."
    )

    @classmethod
    def _calcular_ausencia_dias(cls, cliente) -> int:
        """
        Días transcurridos desde la última ActividadRealizada del cliente.
        Devuelve 0 si el cliente no tiene ninguna actividad registrada
        (usuario nuevo — no disparar 'volver' en ese caso).

        Phase Continuidad 1.0: consolidado. La lógica de ausencia vive ahora en
        core.continuidad (fuente única); este método delega para no mantener un
        cálculo paralelo. La salida visible del semáforo no cambia: usa
        'dias_sin_actividad' (cualquier tipo), idéntico al cálculo anterior.
        """
        try:
            from core.continuidad import evaluar_continuidad_entrenamiento
            lectura = evaluar_continuidad_entrenamiento(cliente)
            return lectura.get('dias_sin_actividad') or 0
        except Exception:
            return 0

    @classmethod
    def get_estado_hoy(cls, cliente, es_descanso_plan: bool = None) -> Dict[str, Any]:
        """
        Devuelve el estado unificado del día.

        Parámetro opcional:
            es_descanso_plan – True si el plan gym marca hoy como descanso.
                               None = no se conoce (no fuerza el estado).

        Returns dict con:
            estado           – empujar / sostener / recuperar / volver
            titulo           – etiqueta corta para el UI
            causa            – lesion | descanso_plan | ausencia | fatiga |
                               fragilidad | carga | normal
            tipo_fatiga      – alineado / mecanica / vital / fragilidad / retorno
            tipo_recuperar   – 'movimiento' | 'descanso' | 'lesion' | None
            mensaje          – decisión final (incluye paradoja si aplica)
            recomendacion_gym    – acción concreta para el gimnasio
            recomendacion_hyrox  – acción concreta para Hyrox
            paradoja         – 'A' | 'B' | None
            datos_raw        – números técnicos (para JOI context)
        """
        # ── 0. Actividad context (Phase 59X.B) ───────────────────
        act_ctx = get_actividad_context(cliente)
        es_descarga_plan = bool(
            act_ctx.get('fase_plan') and act_ctx['fase_plan'].get('es_descarga')
        )

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

        energia = bio.get('energia')  # 1–10 subjetivo

        # ── 5. Ausencia ───────────────────────────────────────────
        ausencia_dias = cls._calcular_ausencia_dias(cliente)

        # ── 6. Lesión activa ──────────────────────────────────────
        lesion_aguda = False
        lesion_zona  = None
        try:
            from hyrox.models import UserInjury
            lesion = (
                UserInjury.objects
                .filter(cliente=cliente, fase__in=('AGUDA', 'SUB_AGUDA'))
                .first()
            )
            if lesion:
                lesion_aguda = True
                lesion_zona  = getattr(lesion, 'zona_afectada', None)
        except Exception:
            pass

        # ── 7. Clasificación de condiciones ───────────────────────

        # recuperar/descanso: cuerpo al límite fisiológico
        cond_recuperar_descanso = (
            readiness_pct < 40
            or (hrv_hundido and tsb is not None and tsb < -25)
            or (readiness_pct < 50 and tsb is not None and tsb < -20)
        )

        # recuperar/movimiento: fragilidad por subutilización
        cond_recuperar_movimiento = (
            acwr is not None
            and acwr < 0.7
            and readiness_pct > 60
        )

        # sostener: carga mecánica alta
        cond_sostener = (
            (acwr is not None and acwr > 1.5)
            or (tsb is not None and tsb < -20)
        )

        # ── 8. Prioridad de estados (causa soberana) ──────────────
        # Lesión → Descanso plan → Ausencia → Fatiga → Carga → Normal
        tipo_recuperar = None
        causa = 'normal'

        if lesion_aguda:
            estado = cls.RECUPERAR
            tipo   = 'vital'
            tipo_recuperar = 'lesion'
            causa  = 'lesion'
        elif es_descanso_plan:
            estado = cls.RECUPERAR
            tipo   = 'vital'
            tipo_recuperar = 'movimiento'
            causa  = 'descanso_plan'
        elif ausencia_dias >= 5 and not (
            act_ctx.get('fase_plan') and act_ctx['fase_plan'].get('es_descarga')
        ):
            estado = cls.VOLVER
            tipo   = 'retorno'
            causa  = 'ausencia'
        elif cond_recuperar_descanso:
            estado = cls.RECUPERAR
            tipo   = 'mecanica' if (tsb is not None and tsb < -20) else 'vital'
            tipo_recuperar = 'descanso'
            causa  = 'fatiga'
        elif cond_recuperar_movimiento:
            estado = cls.RECUPERAR
            tipo   = 'fragilidad'
            # Phase 59X.0: tipo_recuperar propio 'fragilidad' (antes reutilizaba
            # 'movimiento', que daba copy de fatiga "el cuerpo pide bajar
            # intensidad" a alguien fresco/subutilizado).
            tipo_recuperar = 'fragilidad'
            causa  = 'fragilidad'
        elif cond_sostener:
            estado = cls.SOSTENER
            tipo   = 'mecanica'
            causa  = 'carga'
        else:
            estado = cls.EMPUJAR
            tipo   = 'alineado'

        # ── 8. Detección de paradojas (solo cuando no es 'volver') ──
        paradoja = None

        # Las causas determinísticas no se anulan con paradojas
        _causa_deterministica = causa in ('lesion', 'descanso_plan')

        if estado != cls.VOLVER and not _causa_deterministica:
            # Paradoja A: métricas piden calma, energía subjetiva alta.
            # Phase 59X.0: NO aplica a 'fragilidad' — ahí las métricas NO piden
            # calma (estás fresco/subutilizado); "datos piden calma" sería al
            # revés. La energía alta en fragilidad refuerza el retorno, no lo
            # contradice.
            if (estado in (cls.RECUPERAR, cls.SOSTENER)
                    and causa != 'fragilidad'
                    and energia is not None and energia >= 7):
                paradoja = 'A'
                if estado == cls.RECUPERAR and tipo_recuperar != 'descanso':
                    tipo = 'mecanica'

            # Paradoja B: métricas dicen GO, energía subjetiva baja
            if estado == cls.EMPUJAR and energia is not None and energia <= 4:
                paradoja = 'B'
                tipo = 'flojera'

        # ── 10. Mensaje y recomendaciones según causa ────────────────
        _mensajes_causa = {
            'lesion':       f"{'Lesión activa en ' + lesion_zona + '. ' if lesion_zona else ''}El sistema ha ajustado la sesión para proteger la zona.",
            'descanso_plan': "El plan marca descanso hoy. Movilidad o recuperación activa.",
        }
        _gym_causa = {
            'lesion':       f"Tren compatible con la lesión.{' Evita carga en ' + lesion_zona + '.' if lesion_zona else ''}",
            'descanso_plan': "Movilidad o descanso activo. No hay entreno programado.",
        }
        _hyrox_causa = {
            'lesion':       f"{'Evitar estaciones que carguen ' + lesion_zona + '.' if lesion_zona else 'Técnica sin carga.'} Zona 2 si necesitas moverte.",
            'descanso_plan': "Sesión de recuperación o descanso. Sin intensidad.",
        }

        if paradoja == 'A':
            mensaje = cls._PARADOJA_A
        elif paradoja == 'B':
            mensaje = cls._PARADOJA_B
        elif causa in _mensajes_causa:
            mensaje = _mensajes_causa[causa]
        elif estado == cls.RECUPERAR and es_descarga_plan:
            # Phase 59X.D: descarga planificada — copy reasegurador,
            # no el de fatiga/fragilidad (evita lenguaje de abandono).
            mensaje = cls._MENSAJE_RECUPERAR_DESCARGA_PLAN
        elif estado == cls.RECUPERAR:
            clave_msg = f'recuperar_{tipo_recuperar}'
            mensaje = cls._MENSAJES.get(clave_msg, cls._MENSAJES['recuperar_descanso'])
        else:
            mensaje = cls._MENSAJES.get(estado, '')

        if causa in _gym_causa:
            recomendacion_gym   = _gym_causa[causa]
            recomendacion_hyrox = _hyrox_causa[causa]
        elif estado == cls.RECUPERAR and es_descarga_plan:
            recomendacion_gym   = cls._RECOMENDACION_GYM_DESCARGA_PLAN
            recomendacion_hyrox = cls._RECOMENDACION_HYROX_DESCARGA_PLAN
        elif estado == cls.RECUPERAR:
            clave_rec = f'recuperar_{tipo_recuperar}'
            recomendacion_gym   = cls._RECOMENDACIONES_GYM.get(clave_rec, '')
            recomendacion_hyrox = cls._RECOMENDACIONES_HYROX.get(clave_rec, '')
        else:
            recomendacion_gym   = cls._RECOMENDACIONES_GYM.get(estado, '')
            recomendacion_hyrox = cls._RECOMENDACIONES_HYROX.get(estado, '')

        return {
            'estado':            estado,
            'titulo':            cls._TITULOS_POR_CAUSA.get(causa, cls._TITULOS[estado]),
            'causa':             causa,
            'tipo_fatiga':       tipo,
            'tipo_recuperar':    tipo_recuperar,
            'mensaje':           mensaje,
            'recomendacion_gym':   recomendacion_gym,
            'recomendacion_hyrox': recomendacion_hyrox,
            'paradoja':          paradoja,
            'datos_raw': {
                'acwr':               round(acwr, 2) if acwr is not None else None,
                'tsb':                round(tsb, 1) if tsb is not None else None,
                'readiness_pct':      round(readiness_pct, 1),
                'hrv_ms':             bio.get('hrv_ms'),
                'hrv_hundido':        hrv_hundido,
                'energia':            energia,
                'horas_sueno':        bio.get('horas_sueno'),
                'ausencia_dias':      ausencia_dias,
                'lesion_zona':        lesion_zona,
                # Phase 59X.B — actividad context
                'sesiones_gym_semana':   act_ctx.get('sesiones_gym_semana', 0),
                'sesiones_hyrox_semana': act_ctx.get('sesiones_hyrox_semana', 0),
                'racha_dias':            act_ctx.get('racha_dias', 0),
                'fase_plan':             act_ctx.get('fase_plan'),
            },
        }


def detectar_patron_resistencia(cliente) -> bool:
    """
    Detector de resistencia psicológica al entrenamiento.

    Condición de disparo:
      - Hoy hay paradoja B (estado empujar + energía subjetiva ≤ 4)
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
        f"con semáforo en EMPUJAR — {n} veces en 14 días.{dia_txt}{sueno_txt} "
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

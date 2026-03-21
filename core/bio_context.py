# core/bio_context.py
"""
BioContextProvider — Servicio centralizado de contexto biomédico.

Cualquier motor de entrenamiento (Helms, Hyrox, rutinas del gym, etc.)
puede importar este servicio para saber si debe aplicar restricciones
o reducir volumen de forma global.

Uso:
    from core.bio_context import BioContextProvider

    restricciones = BioContextProvider.get_current_restrictions(cliente)
    readiness     = BioContextProvider.get_readiness_score(cliente)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class BioContextProvider:
    """
    Fuente de verdad única para el estado biomédico del usuario.
    Todos los métodos son @staticmethod: no requiere instanciación.
    """

    # ──────────────────────────────────────────────────────────
    #  1) RESTRICCIONES (Risk Tags)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def get_current_restrictions(cliente) -> Dict[str, Any]:
        """
        Devuelve una vista unificada de todas las restricciones biomecánicas
        activas del usuario, provenientes de sus lesiones ``UserInjury``.

        Args:
            cliente: instancia de ``clientes.models.Cliente``

        Returns:
            dict con:
                tags            – set[str] con todos los risk-tags prohibidos
                injuries        – list[dict] resumen de cada lesión activa
                has_restrictions – bool rápido para condicionales
        """
        from hyrox.models import UserInjury

        lesiones_activas = UserInjury.objects.filter(
            cliente=cliente,
            activa=True,
        ).exclude(
            fase=UserInjury.Fase.RECUPERADO,
        )

        tags: Set[str] = set()
        injuries_summary: List[Dict[str, Any]] = []

        for inj in lesiones_activas:
            # Unificar tags
            if inj.tags_restringidos:
                tags.update(inj.tags_restringidos)
                
            # Generar tag virtual para lesión aguda en tren inferior
            inferior_keywords = ['gemelo', 'rodilla', 'pierna', 'pie', 'tobillo', 'cadera', 'femoral', 'cuadriceps', 'gluteo']
            zona_lower = inj.zona_afectada.lower() if inj.zona_afectada else ""
            if inj.fase == UserInjury.Fase.AGUDA and any(k in zona_lower for k in inferior_keywords):
                tags.add('__aguda_tren_inferior')

            injuries_summary.append({
                'id': inj.pk,
                'zona': inj.zona_afectada,
                'fase': inj.fase,
                'gravedad': inj.gravedad,
                'fecha_inicio': inj.fecha_inicio,
                'tags': list(inj.tags_restringidos or []),
            })

        return {
            'tags': tags,
            'injuries': injuries_summary,
            'has_restrictions': bool(tags),
        }

    # ──────────────────────────────────────────────────────────
    #  2) READINESS SCORE
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def get_readiness_score(cliente) -> Dict[str, Any]:
        """
        Calcula un score unificado de «preparación para entrenar» fusionando:

        1. **Helms Recovery Factor** (0.7 – 1.3) basado en los últimos datos
           de dolor, inflamación y rango de movimiento del
           ``DailyRecoveryEntry``.
        2. **Hyrox Pain Score** (0 – 10) — promedio ponderado de dolor en
           reposo y en movimiento de las últimas 3 entradas.

        El score final se normaliza a un rango 0.0 – 1.0 donde 1.0 es
        «plenamente listo».

        Args:
            cliente: instancia de ``clientes.models.Cliente``

        Returns:
            dict con:
                score            – float 0.0-1.0
                helms_factor     – float (0.7-1.3)
                pain_score       – float (0-10, menor = mejor)
                needs_deload     – bool
                volume_modifier  – float (multiplicador sugerido)
                sources          – dict con las fuentes de datos usadas
        """
        from hyrox.models import UserInjury, DailyRecoveryEntry
        from analytics.planificador_helms.recuperacion.optimizador import (
            OptimizadorRecuperacion,
        )

        # ── Recoger lesiones activas ────────────────────────────
        lesiones_activas = UserInjury.objects.filter(
            cliente=cliente,
            activa=True,
        ).exclude(
            fase=UserInjury.Fase.RECUPERADO,
        )

        # ── Últimas 3 entradas de DailyRecoveryEntry ────────────
        recent_entries = list(
            DailyRecoveryEntry.objects.filter(
                lesion__cliente=cliente,
                lesion__activa=True,
            )
            .exclude(lesion__fase=UserInjury.Fase.RECUPERADO)
            .order_by('-fecha')[:3]
        )

        has_pain_data = len(recent_entries) > 0
        has_injuries = lesiones_activas.exists()

        # ── Hyrox Pain Score (0-10, menor = mejor) ──────────────
        if has_pain_data:
            pain_values = []
            for entry in recent_entries:
                # Ponderación: dolor_movimiento pesa más que dolor_reposo
                combined = (entry.dolor_movimiento * 0.6) + (entry.dolor_reposo * 0.4)
                pain_values.append(combined)
            pain_score = sum(pain_values) / len(pain_values)
        else:
            # Sin datos de dolor → asumimos 0 (sin dolor conocido)
            pain_score = 0.0

        # ── Mapear datos de DRE a inputs de Helms ───────────────
        # OptimizadorRecuperacion espera (nivel_estres, calidad_sueño,
        # nivel_energia) en escala 1-10.
        #
        # Mapeamos:
        #   dolor promedio (0-10)          → nivel_estres         (directo)
        #   inflamacion_percibida (1-10)   → calidad_sueño inv.   (11 - inflam)
        #   rango_movimiento (1-10)        → nivel_energia        (directo)

        if has_pain_data:
            last = recent_entries[0]  # Más reciente
            nivel_estres   = max(1, min(10, round(pain_score)))
            calidad_sueño  = max(1, min(10, 11 - last.inflamacion_percibida))
            nivel_energia  = max(1, min(10, last.rango_movimiento))
        else:
            # Defaults neutros
            nivel_estres  = 3
            calidad_sueño = 7
            nivel_energia = 7

        optimizador = OptimizadorRecuperacion(nivel_estres, calidad_sueño, nivel_energia)
        helms_factor = optimizador.calcular_factor_recuperacion()
        needs_deload = optimizador.necesita_descarga()

        # ── Score unificado (0.0 – 1.0) ─────────────────────────
        # Componentes:
        #   helms_component: normalizado de [0.7, 1.3] → [0.0, 1.0]
        #   pain_component:  normalizado de [10, 0]    → [0.0, 1.0]
        #   phase_penalty:   si fase AGUDA, penalización extra

        helms_component = (helms_factor - 0.7) / 0.6          # 0.0 – 1.0
        pain_component  = max(0.0, (10.0 - pain_score) / 10.0)  # 0.0 – 1.0

        # Penalización por fase aguda
        phase_penalty = 0.0
        if has_injuries:
            for inj in lesiones_activas:
                if inj.fase == UserInjury.Fase.AGUDA:
                    phase_penalty = max(phase_penalty, 0.3)
                elif inj.fase == UserInjury.Fase.SUB_AGUDA:
                    phase_penalty = max(phase_penalty, 0.15)

        # Ponderación: Helms 40% + Pain 40% + Fase 20% (como penalización)
        raw_score = (helms_component * 0.4) + (pain_component * 0.4) + ((1.0 - phase_penalty) * 0.2)
        score = max(0.0, min(1.0, raw_score))

        # ── Volume modifier & Max RPE ───────────────────────────
        # Traducción directa del score a un multiplicador de volumen y límite de intensidad
        max_rpe = 10
        if score >= 0.8:
            volume_modifier = 1.0       # Volumen completo
        elif score >= 0.6:
            volume_modifier = 0.85      # Reducción leve
        elif score >= 0.4:
            volume_modifier = 0.70      # Reducción moderada
            max_rpe = 7                 # Cap de intensidad
        else:
            volume_modifier = 0.50      # Reducción severa
            max_rpe = 7                 # Cap de intensidad

        # ── Phase 13: Load Transition Phase (Post-Injury) ────────
        from django.utils import timezone
        hoy = timezone.now().date()
        is_in_transition = False
        transition_days_left = 0

        # Buscar lesiones recientemente recuperadas (últimos 7 días)
        lesiones_recientes = UserInjury.objects.filter(
            cliente=cliente,
            fase=UserInjury.Fase.RECUPERADO,
            fecha_resolucion__gte=hoy - timezone.timedelta(days=7)
        ).order_by('-fecha_resolucion')

        if lesiones_recientes.exists():
            lesion_transicion = lesiones_recientes.first()
            dias_desde_resolucion = (hoy - lesion_transicion.fecha_resolucion).days
            
            # Verificar salida anticipada (>= 3 sesiones y dolor = 0)
            from hyrox.models import HyroxSession
            sesiones_post_recuperacion = HyroxSession.objects.filter(
                objective__cliente=cliente,
                estado='completado',
                fecha__gte=lesion_transicion.fecha_resolucion
            ).count()
            
            ultimo_reporte = DailyRecoveryEntry.objects.filter(
                lesion=lesion_transicion
            ).order_by('-fecha').first()
            
            dolor_cero = ultimo_reporte and ultimo_reporte.dolor_movimiento == 0

            # Si se cumplen las condiciones de salida anticipada, anulamos la transición
            if sesiones_post_recuperacion >= 3 and dolor_cero:
                pass # Salida anticipada validada
            else:
                is_in_transition = True
                transition_days_left = 7 - dias_desde_resolucion
                # Capar máximo a 0.85 incluso si el score es perfecto
                volume_modifier = min(volume_modifier, 0.85)

        return {
            'score': round(score, 3),
            'helms_factor': round(helms_factor, 3),
            'pain_score': round(pain_score, 2),
            'needs_deload': needs_deload,
            'volume_modifier': volume_modifier,
            'max_rpe': max_rpe,
            'is_in_transition': is_in_transition,
            'transition_days_left': transition_days_left,
            'sources': {
                'has_pain_data': has_pain_data,
                'pain_entries_count': len(recent_entries),
                'has_active_injuries': has_injuries,
                'injury_count': lesiones_activas.count() if has_injuries else 0,
                'helms_inputs': {
                    'nivel_estres': nivel_estres,
                    'calidad_sueño': calidad_sueño,
                    'nivel_energia': nivel_energia,
                },
            },
        }

    # ──────────────────────────────────────────────────────────
    #  3) BIO-PURGE (FORCE CLEAN FUTURE WORKOUTS)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def force_clean_future_workouts(cliente) -> int:
        """
        Borra físicamente todas las actividades de las sesiones con estado 'planificado'
        (futuras) para forzar al sistema a regenerarlas pasando por los filtros
        de bioseguridad del SelectorEjercicios.
        
        Se debe llamar a este método cuando un usuario reporta una nueva lesión
        o hay un cambio significativo en el estado de una lesión (ej. entra en fase aguda).

        Args:
            cliente: instancia de ``clientes.models.Cliente``

        Returns:
            int: Cantidad de sesiones planificadas que fueron eliminadas.
        """
        from django.utils import timezone as tz
        from hyrox.models import HyroxSession, HyroxObjective
        from hyrox.training_engine import HyroxTrainingEngine

        objetivo_activo = HyroxObjective.objects.filter(
            cliente=cliente, estado__in=['activo', 'active']
        ).first()

        # Solo borramos las sesiones planificadas si el evento es futuro y
        # generate_training_plan podrá recrearlas. Si no, solo rellenamos huecos.
        hoy = tz.now().date()
        puede_regenerar = (
            objetivo_activo is not None
            and objetivo_activo.fecha_evento is not None
            and objetivo_activo.fecha_evento >= hoy  # incluye evento hoy o futuro
        )

        sesiones_futuras = HyroxSession.objects.filter(
            objective__cliente=cliente,
            estado='planificado'
        )
        count = sesiones_futuras.count()

        if puede_regenerar and count > 0:
            logger.info(f"Bio-Purge: Eliminando {count} sesiones planificadas para cliente {cliente.id} — se regenerarán con nuevos filtros.")
            sesiones_futuras.delete()
        elif not puede_regenerar:
            logger.info(f"Bio-Purge: Evento pasado o sin objetivo activo para cliente {cliente.id} — se omite el borrado para conservar el plan.")

        # Regenerar (o rellenar huecos si no se borró)
        if objetivo_activo:
            HyroxTrainingEngine.generate_training_plan(objetivo_activo)
            logger.info(f"Bio-Purge: Plan regenerado para cliente {cliente.id}.")

        return count

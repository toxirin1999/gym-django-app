"""
Servicio de determinación del Pulso del organismo.

El Pulso traduce visualmente el estado vital del sistema.
No decide. Solo traduce señales que ya existen.
"""

from django.utils import timezone


class PulsoService:
    """Determina el estado vital (Pulso) del organismo."""

    PULSO_PROTEGIENDO = "protegiendo"
    PULSO_PROGRESANDO = "progresando"
    PULSO_SILENCIOSO = "silencioso"

    @classmethod
    def determinar_pulso(cls, objetivo, readiness_score, lesion_activa=None, historial_reciente=None):
        """
        Determina el estado vital del sistema.

        Args:
            objetivo: HyroxObjective del usuario
            readiness_score: int (0-100) — score actual de readiness
            lesion_activa: UserInjury o None
            historial_reciente: dict con señales recientes (opcional)

        Returns:
            dict con:
            - pulso: str (protegiendo/progresando/silencioso)
            - contexto: str descriptivo
            - postura: dict con instrucciones visuales
        """
        import logging
        _log = logging.getLogger('hyrox.pulso')

        # Regla 1: Lesión activa o readiness muy bajo → PROTEGIENDO
        if lesion_activa and lesion_activa.activa:
            _log.info(f'[Pulso] PROTEGIENDO por lesión_activa (fase={lesion_activa.fase})')
            return cls._pulso_protegiendo(
                motivo="lesión_activa",
                readiness_score=readiness_score
            )

        if readiness_score < 40:
            _log.info(f'[Pulso] PROTEGIENDO por readiness_bajo (score={readiness_score})')
            return cls._pulso_protegiendo(
                motivo="readiness_bajo",
                readiness_score=readiness_score
            )

        # Regla 1b: Sesión muy reciente con RPE extremo → PROTEGIENDO (sensibilidad a sesiones actuales)
        from datetime import datetime, time
        ultima_sesion = objetivo.sessions.filter(estado='completado').order_by('-fecha', '-id').first()
        if ultima_sesion:
            sesion_datetime = timezone.make_aware(datetime.combine(ultima_sesion.fecha, time.min))
            hace = timezone.now() - sesion_datetime
            es_reciente = hace.days == 0  # Sesión de hoy
            _log.info(f'[Pulso] ultima_sesion: id={ultima_sesion.id} fecha={ultima_sesion.fecha} rpe={ultima_sesion.rpe_global} es_reciente={es_reciente}')
            if es_reciente and ultima_sesion.rpe_global and ultima_sesion.rpe_global >= 10:
                _log.info(f'[Pulso] PROTEGIENDO por esfuerzo_extremo (RPE={ultima_sesion.rpe_global})')
                return cls._pulso_protegiendo(
                    motivo="esfuerzo_extremo",
                    readiness_score=readiness_score
                )

        # Regla 2: Progreso reciente → PROGRESANDO
        if historial_reciente:
            hay_progreso = (
                historial_reciente.get("nuevo_rm") or
                historial_reciente.get("peso_subio") or
                historial_reciente.get("molestia_resuelta")
            )
            if hay_progreso and readiness_score >= 50:
                _log.info(f'[Pulso] PROGRESANDO por progreso reciente')
                return cls._pulso_progresando(
                    historial_reciente=historial_reciente
                )

        # Regla 3: Default → SILENCIOSO (presente sin fuerza)
        _log.info(f'[Pulso] SILENCIOSO (readiness={readiness_score}, historial_reciente={bool(historial_reciente)})')
        return cls._pulso_silencioso(readiness_score=readiness_score)

    @classmethod
    def _pulso_protegiendo(cls, motivo, readiness_score):
        """Estado: sistema se contrae, recuperación dirigida."""
        return {
            "pulso": cls.PULSO_PROTEGIENDO,
            "contexto": f"Carga reciente + señal de protección",
            "motivo": motivo,
            "postura": {
                "estructura": "compacta",
                "rutas": 1,
                "metricas_secundarias_visible": False,
                "opciones_exploración": False,
                "joi_modo": "observa_sin_lectura",
                "accion_principal": "Registrar recuperación",
                "fondo_intensidad": "media",
            },
            "mostrando": ["contexto_inmediato", "accion_prudente"],
            "ocultando": ["evolución_semanal", "opciones_plan_completo", "metricas_secundarias"],
        }

    @classmethod
    def _pulso_progresando(cls, historial_reciente):
        """Estado: sistema se abre, evidencia de continuidad."""
        cambios = []
        if historial_reciente.get("nuevo_rm"):
            cambios.append("Nuevo RM alcanzado")
        if historial_reciente.get("peso_subio"):
            cambios.append(f"Peso: +{historial_reciente.get('peso_subio')} kg")
        if historial_reciente.get("molestia_resuelta"):
            cambios.append("Molestia resuelta")

        return {
            "pulso": cls.PULSO_PROGRESANDO,
            "contexto": "Tendencia real, continúa apertura",
            "cambios": cambios,
            "postura": {
                "estructura": "abierta",
                "rutas": 3,
                "metricas_secundarias_visible": True,
                "opciones_exploración": True,
                "joi_modo": "lectura_pendiente",
                "accion_principal": "Entrenar completo",
                "fondo_intensidad": "alta",
            },
            "mostrando": ["continuidad", "evidencia", "opciones_multiples"],
            "ocultando": [],
        }

    @classmethod
    def _pulso_silencioso(cls, readiness_score):
        """Estado: sistema en reposo, escucha sin forzar."""
        return {
            "pulso": cls.PULSO_SILENCIOSO,
            "contexto": "Sin señal concluyente",
            "readiness_score": readiness_score,
            "postura": {
                "estructura": "minima",
                "rutas": 1,
                "metricas_secundarias_visible": False,
                "opciones_exploración": False,
                "joi_modo": "ausente",
                "accion_principal": "Continuar plan",
                "fondo_intensidad": "baja",
            },
            "mostrando": ["plan_abierto", "frase_madre"],
            "ocultando": ["metricas", "evoluciones", "decisiones_secundarias"],
        }

"""
HyroxDiagnosticEngine — motor de diagnóstico post-entreno.

Combina tres capas:
  1. Datos objetivos  (tiempo, RPE, FC, interferencia, pausas)
  2. Percepción       (feedback del usuario: sensación, qué falló)
  3. Interpretación   (el sistema decide; la percepción es solo contexto)

Regla de oro: el usuario aporta contexto, el sistema decide.
"""

from .station_intelligence import HyroxStationIntelligence as _SI


# ── Palabras clave para localizar actividades por estación ────────────────────
_STATION_KEYWORDS = {
    'skierg':         ['skierg', 'ski erg'],
    'sled_push':      ['sled push'],
    'sled_pull':      ['sled pull'],
    'burpees':        ['burpee'],
    'rowing':         ['rowing', 'remo'],
    'farmers_carry':  ['farmer', 'carry'],
    'sandbag_lunges': ['sandbag', 'lunge'],
    'wall_balls':     ['wall ball'],
}


def _station_display(key):
    return _SI.STATIONS.get(key, {}).get('display_name', (key or '').replace('_', ' ').title())


class HyroxDiagnosticEngine:
    """
    Entrada:  HyroxSession completada (con station_feedback y datos de sesión).
    Salida:   dict {global, stations} con diagnósticos tipificados.
    """

    # ── 8 tipos canónicos de diagnóstico ─────────────────────────────────────
    TIPOS = {
        'mejora_objetiva':                    {'color': '#1DC8B8', 'icon': '↑'},
        'entreno_duro_util':                  {'color': '#1DC8B8', 'icon': '⚡'},
        'entreno_estable':                    {'color': '#64748b', 'icon': '→'},
        'fatiga_acumulada':                   {'color': '#EF4444', 'icon': '⚠'},
        'problema_tecnico':                   {'color': '#F59E0B', 'icon': '◈'},
        'mala_estrategia_ritmo':              {'color': '#F59E0B', 'icon': '◷'},
        'percepcion_negativa_no_confirmada':  {'color': '#1DC8B8', 'icon': '✓'},
        'percepcion_positiva_enganosa':       {'color': '#F59E0B', 'icon': '!'},
    }

    # ── API pública ───────────────────────────────────────────────────────────

    @classmethod
    def evaluate_session(cls, sesion):
        """
        Punto de entrada principal.
        Devuelve None si no hay feedback o datos suficientes.
        """
        if not sesion or not sesion.station_feedback:
            return None

        station_diags = []
        for fb in sesion.station_feedback:
            key = fb.get('estacion', '')
            if not key:
                continue
            obj  = cls._build_objective(sesion, key, fb)
            subj = cls._build_subjective(fb)
            diag = cls._evaluate_station(obj, subj, key)
            station_diags.append({'estacion': key, 'display_name': _station_display(key), 'diagnosis': diag})

        global_diag = cls._evaluate_global(sesion, station_diags)

        return {
            'global':   global_diag,
            'stations': station_diags,
        }

    # ── Construcción de datos ─────────────────────────────────────────────────

    @classmethod
    def _build_objective(cls, sesion, station_key, fb):
        act        = cls._find_activity(sesion, station_key)
        tiempo_r   = (act.data_metricas or {}).get('tiempo_s') if act else None
        hist       = cls._historical_times(sesion, station_key)
        tiempo_a   = hist[0] if hist else None
        pausas_str = fb.get('pausas', '0')
        pausas_num = 0 if pausas_str == '0' else (2 if pausas_str == '1-2' else 4)

        mejora = None
        if tiempo_r and tiempo_a:
            mejora = tiempo_r < tiempo_a  # menor tiempo = mejora en estaciones

        return {
            'tiempo_real':    tiempo_r,
            'tiempo_anterior': tiempo_a,
            'mejora_tiempo':  mejora,
            'rpe':            sesion.rpe_global or 0,
            'fc_media':       sesion.hr_media or 0,
            'pausas':         pausas_num,
            'tsb':            sesion.tsb or 0,
        }

    @classmethod
    def _build_subjective(cls, fb):
        sensacion = fb.get('sensacion', 'fluida')
        # normalizar (muy_mala → muy mala, etc.)
        percepcion = 'malo' if sensacion in ('muy_mala', 'torpe') else 'bueno'
        return {
            'sensacion':  sensacion,
            'percepcion': percepcion,
            'fallos':     fb.get('fallos', []),
            'pausas_str': fb.get('pausas', '0'),
        }

    # ── Lógica central de diagnóstico por estación ───────────────────────────

    @classmethod
    def _evaluate_station(cls, obj, subj, station_key):
        score = 0
        flags = []
        display = _station_display(station_key)
        mejora  = obj['mejora_tiempo']
        rpe     = obj['rpe']
        pausas  = obj['pausas']
        percepcion = subj['percepcion']
        fallos     = subj['fallos']

        # ── Scoring objetivo ─────────────────────────────────────────────────
        if mejora is True:
            score += 2
            flags.append('mejora_tiempo')
        elif mejora is False:
            score -= 1
            flags.append('peor_tiempo')

        if pausas >= 4:
            score -= 2
            flags.append('muchas_pausas')
        elif pausas >= 2:
            score -= 1
            flags.append('algunas_pausas')
        elif pausas == 0 and mejora is not None:
            score += 1
            flags.append('sin_pausas')

        if rpe >= 9:
            score -= 2
            flags.append('rpe_muy_alto')
        elif rpe >= 7:
            score -= 1
            flags.append('rpe_alto')

        # ── Detección de señales específicas ────────────────────────────────
        # Pacing: muchas pausas + usuario dice brazos/técnica (probablemente salió fuerte)
        ritmo_probable = (
            'muchas_pausas' in flags or 'algunas_pausas' in flags
        ) and any(f in fallos for f in ['brazos', 'tecnica']) and 'ritmo' not in fallos

        # Técnica probable: no hay mejora, sensación torpe/muy mala, pero pocas pausas
        tecnica_probable = (
            mejora is False
            and subj['sensacion'] in ('torpe', 'muy_mala')
            and pausas == 0
            and rpe < 8
        )

        # ── Árbol de diagnóstico ─────────────────────────────────────────────

        # Sin historial: primera referencia
        if mejora is None:
            return cls._diag(
                'entreno_estable',
                'Sin referencia histórica aún',
                f'Es la primera vez que registramos {display} con datos comparables. Sirve como línea base.',
                'Registra más sesiones para activar el análisis comparativo.',
                flags,
            )

        # Caso D — Pacing probable (pausas + usuario culpa a brazos/técnica)
        # Va primero: señal específica que el score genérico enmascararía
        if ritmo_probable:
            return cls._diag(
                'mala_estrategia_ritmo',
                'Posible problema de ritmo, no de técnica',
                f'Las pausas en {display} sugieren una estrategia demasiado agresiva. '
                f'El usuario indica {", ".join(fallos)}, pero la causa probable es el pacing.',
                'Sal un 10-15% más suave en los primeros metros y conserva para la segunda mitad.',
                flags,
            )

        # Caso A — Datos buenos + percepción mala → "fue duro, no malo"
        if score >= 2 and percepcion == 'malo':
            return cls._diag(
                'percepcion_negativa_no_confirmada',
                'Fue duro, no malo',
                f'{display} mejoró objetivamente (menos tiempo, menos pausas). '
                f'Tu sensación negativa no refleja el rendimiento real.',
                'Mantén la intensidad. Trabaja respiración para que el esfuerzo se sienta más controlado.',
                flags,
            )

        # Caso B — Datos malos + percepción buena → "se sintió bien pero cayó"
        if score <= -2 and percepcion == 'bueno':
            return cls._diag(
                'percepcion_positiva_enganosa',
                'Se sintió bien, pero el rendimiento cayó',
                f'{display} se percibió como normal, pero los datos muestran caída de eficiencia '
                f'({"peor tiempo, " if "peor_tiempo" in flags else ""}{"más pausas" if "muchas_pausas" in flags else ""}).',
                'Revisa estrategia de ritmo. Puede que estés saliendo demasiado cómodo al inicio.',
                flags,
            )

        # Caso C — Datos malos + percepción mala → coinciden
        if score <= -2 and percepcion == 'malo':
            return cls._diag(
                'fatiga_acumulada',
                'Rendimiento y sensación coinciden: sesión difícil',
                f'{display} estuvo objetivamente por debajo hoy. Tu percepción es correcta.',
                'Reduce intensidad en la próxima sesión y trabaja técnica base a RPE bajo.',
                flags,
            )

        # Caso E — Técnica probable (mal resultado sin exceso de esfuerzo)
        if tecnica_probable:
            mis = _SI.get_common_mistakes(station_key)
            hint = mis[0] if mis else 'Revisa patrón técnico básico.'
            return cls._diag(
                'problema_tecnico',
                'Probable limitante técnico',
                f'{display} no mejoró y la sensación fue técnicamente mala, '
                f'sin señales de fatiga excesiva.',
                f'Error habitual: {hint}',
                flags,
            )

        # Caso F — Mejora objetiva clara
        if score >= 2 and percepcion == 'bueno':
            return cls._diag(
                'mejora_objetiva',
                'Mejora objetiva',
                f'{display} mejoró hoy: mejor tiempo y sensación técnica positiva.',
                'Mantén el plan. Progresión en la dirección correcta.',
                flags,
            )

        # Fallback — sesión estable
        return cls._diag(
            'entreno_estable',
            'Sesión estable',
            f'{display} sin señales claras de problema ni mejora significativa.',
            'Mantén el plan y acumula sesiones para tendencia más clara.',
            flags,
        )

    # ── Diagnóstico global de la sesión ──────────────────────────────────────

    @classmethod
    def _evaluate_global(cls, sesion, station_diags):
        rpe   = sesion.rpe_global or 0
        tsb   = sesion.tsb or 0
        tipos = [sd['diagnosis']['tipo'] for sd in station_diags]

        if 'percepcion_negativa_no_confirmada' in tipos:
            return cls._diag(
                'entreno_duro_util',
                'Entreno duro, pero útil',
                'La sesión fue exigente pero los datos muestran progresión. '
                'No confundas sufrimiento con fracaso.',
                'Sigue el plan. El esfuerzo percibido alto con mejora objetiva es exactamente lo que buscamos.',
                [],
            )

        if rpe >= 9 and tsb < -15:
            return cls._diag(
                'fatiga_acumulada',
                'Fatiga acumulada alta',
                'TSB negativo elevado + RPE muy alto sugieren fatiga sistémica, no solo de sesión.',
                'Considera una sesión de recuperación activa antes de volver a alta intensidad.',
                ['rpe_muy_alto', 'tsb_negativo'],
            )

        if 'percepcion_positiva_enganosa' in tipos:
            return cls._diag(
                'percepcion_positiva_enganosa',
                'Percepción engañosa en alguna estación',
                'Una o más estaciones se sintieron bien pero los datos muestran caída.',
                'Revisa estrategia de pacing. El cuerpo puede no percibir bien el nivel de esfuerzo real.',
                [],
            )

        if 'fatiga_acumulada' in tipos or 'mala_estrategia_ritmo' in tipos:
            return cls._diag(
                'entreno_estable',
                'Sesión con áreas a corregir',
                'Hay señales puntuales de mejora posible. Ver análisis por estación.',
                'Aplica las correcciones específicas por estación en los próximos entrenos.',
                [],
            )

        return cls._diag(
            'entreno_estable',
            'Sesión registrada sin alertas',
            'Sin señales de fatiga acumulada ni caídas objetivas significativas.',
            'Mantén el plan.',
            [],
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _diag(tipo, titulo, mensaje, accion, flags):
        meta = HyroxDiagnosticEngine.TIPOS.get(tipo, {'color': '#64748b', 'icon': '→'})
        return {
            'tipo':   tipo,
            'titulo': titulo,
            'mensaje': mensaje,
            'accion': accion,
            'flags':  flags,
            'color':  meta['color'],
            'icon':   meta['icon'],
        }

    @classmethod
    def _find_activity(cls, sesion, station_key):
        keywords = _STATION_KEYWORDS.get(station_key, [])
        for act in sesion.activities.all():
            name = act.nombre_ejercicio.lower()
            for kw in keywords:
                if kw in name:
                    return act
        return None

    @classmethod
    def _historical_times(cls, sesion, station_key, limit=5):
        from .models import HyroxSession
        keywords = _STATION_KEYWORDS.get(station_key, [])
        times = []
        previas = (
            HyroxSession.objects
            .filter(objective=sesion.objective, estado='completado', fecha__lt=sesion.fecha)
            .order_by('-fecha')
            .prefetch_related('activities')[:limit]
        )
        for prev in previas:
            for act in prev.activities.all():
                name = act.nombre_ejercicio.lower()
                for kw in keywords:
                    if kw in name:
                        t = (act.data_metricas or {}).get('tiempo_s')
                        if t and t > 0:
                            times.append(t)
                        break
                else:
                    continue
                break
        return times

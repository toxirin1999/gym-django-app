"""
Voz del Entrenador — Capa 1 del sistema proactivo.

Genera instrucciones concretas y dirigidas al usuario antes de cada sesión,
basadas en las señales que el sistema ha aprendido:
  - GymDecisionLog (estancamiento, molestia, tope, deload)
  - Técnica comprometida recurrente
  - RPE alto acumulado por ejercicio
  - Récords personales recientes

La diferencia con briefing.mensajes (descriptivo):
  mensajes:     "Sentadilla: sin progresión en 3 sesiones."
  instrucciones: "Sentadilla — prueba tempo 3-1-2 hoy. 3 sesiones sin subir: cambia el estímulo antes que el peso."
"""
from datetime import date, timedelta

_PRIORIDAD = {'critica': 0, 'alerta': 1, 'info': 2, 'positivo': 3}

_TEMPO_SUGERIDO = {
    'sentadilla': '3-1-2', 'press banca': '3-1-2', 'peso muerto': '2-1-3',
    'press militar': '2-1-2', 'remo': '2-1-2', 'jalón': '2-1-2',
    'hip thrust': '2-1-2', 'zancada': '2-1-2', 'prensa': '3-1-2',
}

_VARIANTE_SUGERIDA = {
    'sentadilla': 'sentadilla búlgara o sentadilla pausa', 'press banca': 'press inclinado o press pausa',
    'peso muerto': 'peso muerto rumano o trap bar', 'press militar': 'press Arnold o mancuernas',
    'remo': 'remo unilateral o cable', 'jalón': 'dominada o jalón neutro',
    'curl': 'curl martillo o curl concentrado', 'extensión': 'fondos o cable press abajo',
}


def _tempo_para(nombre):
    nl = nombre.lower()
    for k, v in _TEMPO_SUGERIDO.items():
        if k in nl:
            return v
    return '3-1-2'


def _variante_para(nombre):
    nl = nombre.lower()
    for k, v in _VARIANTE_SUGERIDA.items():
        if k in nl:
            return v
    return 'una variante diferente'


def get_instrucciones(cliente, nombres_hoy, hoy=None):
    """
    Retorna lista de instrucciones para la sesión de hoy.
    Cada item: {prioridad, icono, ejercicio, instruccion, razon}
    Máximo 4 instrucciones, ordenadas por prioridad.
    """
    if hoy is None:
        hoy = date.today()

    instrucciones = []
    hace_21 = hoy - timedelta(days=21)
    hace_14 = hoy - timedelta(days=14)
    hace_7  = hoy - timedelta(days=7)

    try:
        from entrenos.models import GymDecisionLog, EjercicioRealizado, RecordPersonal
        from entrenos.services.briefing_service import necesita_deload_gym

        # ── 1. DELOAD ACTIVO (global) ─────────────────────────────────────────
        if necesita_deload_gym(cliente, hoy):
            instrucciones.append({
                'prioridad': 'critica',
                'icono': '🔄',
                'ejercicio': None,
                'instruccion': 'Hoy al 70% en todos los compuestos — semana de descarga.',
                'razon': 'El sistema detecta fatiga acumulada. Menos series, más control técnico.',
            })

        # ── 2. ESTANCAMIENTO POR EJERCICIO ───────────────────────────────────
        estancados = (
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    motivo__icontains='Sin progresión',
                    fecha_creacion__date__gte=hace_21,
                    ejercicio__in=nombres_hoy)
            .order_by('ejercicio', '-fecha_creacion')
            .distinct()
        )
        vistos = set()
        for log in estancados:
            if log.ejercicio in vistos:
                continue
            vistos.add(log.ejercicio)
            sesiones_str = _contar_sesiones_sin_progresion(cliente, log.ejercicio, hace_21)
            tempo = _tempo_para(log.ejercicio)
            variante = _variante_para(log.ejercicio)
            instrucciones.append({
                'prioridad': 'alerta',
                'icono': '📊',
                'ejercicio': log.ejercicio,
                'instruccion': f'Prueba tempo {tempo} en lugar de subir peso.',
                'razon': f'{sesiones_str} sin progresar — cambia el estímulo: {variante}.',
            })

        # ── 3. MOLESTIA RECURRENTE ────────────────────────────────────────────
        molestias = (
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    motivo__icontains='Molestia',
                    fecha_creacion__date__gte=hace_21,
                    ejercicio__in=nombres_hoy)
            .order_by('ejercicio', '-fecha_creacion')
            .distinct()
        )
        for log in molestias:
            if log.ejercicio in vistos:
                continue
            vistos.add(log.ejercicio)
            instrucciones.append({
                'prioridad': 'alerta',
                'icono': '⚠️',
                'ejercicio': log.ejercicio,
                'instruccion': 'Reduce el rango o baja el peso un escalón.',
                'razon': 'Molestia recurrente detectada. Prioridad: no agravar.',
            })

        # ── 4. TOPE DE MÁQUINA ────────────────────────────────────────────────
        topes = (
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='subir_reps',
                    motivo__icontains='tope',
                    fecha_creacion__date__gte=hace_14,
                    ejercicio__in=nombres_hoy)
            .order_by('ejercicio', '-fecha_creacion')
        )
        for log in topes:
            if log.ejercicio in vistos:
                continue
            vistos.add(log.ejercicio)
            reps_obj = int(log.reps_anteriores or 0) + 1
            instrucciones.append({
                'prioridad': 'info',
                'icono': '🔝',
                'ejercicio': log.ejercicio,
                'instruccion': f'Mismo peso — apunta a {reps_obj} reps.',
                'razon': 'Llegaste al tope de la máquina. Progresión por reps hasta el siguiente salto.',
            })

        # ── 5. TÉCNICA COMPROMETIDA RECURRENTE ───────────────────────────────
        for nombre in nombres_hoy:
            if nombre in vistos:
                continue
            tecnica_mala = (
                EjercicioRealizado.objects
                .filter(entreno__cliente=cliente, nombre_ejercicio=nombre,
                        tecnica='Comprometida',
                        fecha_creacion__date__gte=hace_14)
                .count()
            )
            if tecnica_mala >= 2:
                vistos.add(nombre)
                instrucciones.append({
                    'prioridad': 'alerta',
                    'icono': '🎯',
                    'ejercicio': nombre,
                    'instruccion': 'Baja el peso un escalón y prioriza técnica perfecta.',
                    'razon': f'Técnica comprometida {tecnica_mala}x en 2 semanas — el sistema lo registra.',
                })

        # ── 6. RPE ALTO RECURRENTE POR EJERCICIO ─────────────────────────────
        for nombre in nombres_hoy:
            if nombre in vistos:
                continue
            rpes_recientes = list(
                EjercicioRealizado.objects
                .filter(entreno__cliente=cliente, nombre_ejercicio=nombre,
                        rpe__gte=9, fecha_creacion__date__gte=hace_14)
                .values_list('rpe', flat=True)
            )
            if len(rpes_recientes) >= 2:
                vistos.add(nombre)
                instrucciones.append({
                    'prioridad': 'info',
                    'icono': '🛡️',
                    'ejercicio': nombre,
                    'instruccion': 'Para en RIR 2 hoy — no llegues al límite.',
                    'razon': f'RPE ≥9 en {len(rpes_recientes)} sesiones recientes. Deja margen para recuperar.',
                })

        # ── 7. PR RECIENTE (positivo) ─────────────────────────────────────────
        for nombre in nombres_hoy:
            if nombre in vistos:
                continue
            pr = (
                RecordPersonal.objects
                .filter(cliente=cliente, ejercicio_nombre=nombre,
                        tipo_record='peso_maximo', superado=False,
                        fecha_logrado__gte=hace_7)
                .order_by('-valor').first()
            )
            if pr:
                vistos.add(nombre)
                instrucciones.append({
                    'prioridad': 'positivo',
                    'icono': '🏆',
                    'ejercicio': nombre,
                    'instruccion': f'Tu RM actualizado es {pr.valor} kg — trabaja desde ahí.',
                    'razon': 'PR registrado esta semana. El plan ya usa el nuevo máximo.',
                })

    except Exception:
        pass

    instrucciones.sort(key=lambda x: _PRIORIDAD.get(x['prioridad'], 9))
    return instrucciones[:4]


def _contar_sesiones_sin_progresion(cliente, ejercicio, desde):
    try:
        from entrenos.models import GymDecisionLog
        n = (GymDecisionLog.objects
             .filter(cliente=cliente, ejercicio=ejercicio,
                     accion='cambiar_variante', motivo__icontains='Sin progresión',
                     fecha_creacion__date__gte=desde)
             .count())
        return f'{n} sesión{"es" if n != 1 else ""}'
    except Exception:
        return '3 sesiones'

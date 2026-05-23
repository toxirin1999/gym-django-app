"""
Phase 30 — Explicación unificada de la decisión diaria del plan.

CONTRACT:
- Read-only: no escribe en BD.
- Toma el dict de decisión de obtener_sesion_recomendada_hoy() y produce
  una explicación coherente para el usuario.
- Evita solapamientos: si distribucion_aviso y preferencia_aplicada se refieren
  al mismo patrón (ej. pierna/fútbol), suprime el aviso de distribución
  (la preferencia es la señal más madura y toma el protagonismo).
- Produce una lista ordenada de señales activas, no una por cada sistema.
"""

from __future__ import annotations

# Etiquetas legibles por el usuario para causa_principal
_CAUSAS = {
    'lesion':               '🛑 Lesión activa',
    'fatiga_alta':          '⚡ Readiness bajo',
    'energia_baja':         '🔋 Energía baja hoy',
    'futbol_reciente':      '⚽ Actividad intensa reciente',
    'pendiente_prioritaria':'📌 Sesión estructural pendiente',
    'pendiente_normal':     '📋 Sesión accesoria pendiente',
    'sesion_hoy':           '✓ Sesión del plan de hoy',
    'descanso_planificado': '🌙 Descanso planificado',
}

# Si distribucion_aviso y preferencia_aplicada tratan el mismo patrón,
# la preferencia (señal más madura) suprime el aviso de distribución.
_PREF_SUPLANTA_DISTRIB = {
    'evitar_pierna_tras_futbol': 'redistrib_pierna_futbol',
    'evitar_dia_frecuente':      'redistrib_dia_frecuente',
    'preferir_menos_dias':       'redistrib_dias_menores',
    'aligerar_dia_concreto':     'redistrib_aligerar_dia',
}


def construir_explicacion_decision(decision: dict, senal_diario: dict | None = None) -> dict:
    """
    Returns a structured explanation of today's plan decision.

    Result:
        causa_label:      str  — human-readable main cause
        senales_activas:  list[str]  — ordered active signals
        supresiones:      list[str]  — signals suppressed to avoid overlap
        todo_limpio:      bool  — True when no special conditions active
    """
    senales = []
    supresiones = []

    causa = decision.get('causa_principal') or ''
    estado = decision.get('estado', 'entrenar')
    causa_label = _CAUSAS.get(causa, causa)

    # Lesión aviso (highest priority signal)
    lesion_aviso = decision.get('lesion_aviso')
    if lesion_aviso:
        fase = lesion_aviso.get('fase', '')
        zona = lesion_aviso.get('zona', 'zona afectada')
        ejs = lesion_aviso.get('ejercicios_en_riesgo', [])
        if lesion_aviso.get('es_bloqueante'):
            senales.append(
                f"Lesión activa en {zona} ({fase.lower()}). "
                f"La progresión está frenada en: {', '.join(ejs[:3])}."
            )
        else:
            senales.append(
                f"Zona {zona} en {fase.lower()}. "
                f"Ejercicios a revisar: {', '.join(ejs[:3])}."
            )

    # Determinar si preferencia suprime el aviso de distribución
    preferencia_aplicada = decision.get('preferencia_aplicada')
    distribucion_aviso = decision.get('distribucion_aviso')
    pref_tipo = preferencia_aplicada.get('tipo', '') if preferencia_aplicada else ''
    distrib_tipo = distribucion_aviso.get('tipo', '') if distribucion_aviso else ''

    pref_suplanta = (
        pref_tipo in _PREF_SUPLANTA_DISTRIB
        and _PREF_SUPLANTA_DISTRIB.get(pref_tipo) == distrib_tipo
    )

    # Preferencia aplicada
    if preferencia_aplicada:
        senales.append(
            f"Preferencia activa: {preferencia_aplicada.get('mensaje', '')}"
        )

    # Distribución aviso (solo si no suprimido por preferencia)
    if distribucion_aviso and not pref_suplanta:
        senales.append(distribucion_aviso.get('texto', ''))
    elif distribucion_aviso and pref_suplanta:
        supresiones.append(
            f"Aviso de distribución suprimido (la preferencia aprendida es más específica)."
        )

    # Freno contextual de progresión
    permiso = (decision.get('entrenamiento') or {}).get('permiso_progresion')
    if permiso and permiso.get('accion') != 'progresion_permitida':
        senales.append(permiso.get('mensaje', ''))

    # Modo esencial
    if decision.get('modo_reducido'):
        senales.append('Sesión en versión esencial: accesorios opcionales, principales primero.')

    # Señal corporal del diario (siempre la última — contexto, no decisión)
    if senal_diario and senal_diario.get('hay_senal'):
        _textos_diario = {
            'suave':    'El diario registra algo de carga corporal reciente. No cambia la sesión, pero vale observar cómo responde el cuerpo.',
            'moderada': 'El diario registra varios cierres con cuerpo cargado o apagado. No cambia la sesión por sí solo, aunque una versión esencial es válida.',
            'alta':     'El diario registra cuerpo dolorido en días recientes. No cambia la sesión por sí solo, pero conviene revisar la carga.',
        }
        senales.append(_textos_diario.get(senal_diario['intensidad'], senal_diario.get('texto', '')))

    todo_limpio = len(senales) == 0 and estado == 'entrenar'

    return {
        'causa_label':                 causa_label,
        'senales_activas':             senales,
        'supresiones':                 supresiones,
        'todo_limpio':                 todo_limpio,
        'distribucion_aviso_suprimido': pref_suplanta,
    }

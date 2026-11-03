"""Sesiones de descarga: no sirven de "la última vez" (31-oct-2026).

En una descarga el peso se baja a propósito (semana de descarga del bloque,
``recalculado_descarga``) o se limita el esfuerzo (ciclo de deload: una serie
menos y RPE 7 como máximo). Si esa sesión se lee como "la última vez", la
semana siguiente el techo del peso (que solo baja o limita) deja al ejercicio
en el peso de descarga más un salto de máquina, y se tarda varias sesiones en
volver sin ningún motivo real. Lo mismo con el ancla del planificador.

Una sesión cuenta como descarga si:
- el ejercicio venía marcado así en el snapshot de esa sesión (``deload``,
  ``_deload_aplicado`` o ``motivo_peso = recalculado_descarga``), o
- su fecha cae en una semana de descarga del plan (``SemanaPlanGym``) o en un
  ciclo de deload (``CicloDeload``) vigente ese día.
"""

from datetime import timedelta


def periodos_descarga(cliente_id):
    """Lista de (inicio, fin) con las fechas de descarga del cliente."""
    from entrenos.models import CicloDeload, SemanaPlanGym

    periodos = [
        (lunes, lunes + timedelta(days=6))
        for lunes in SemanaPlanGym.objects.filter(
            cliente_id=cliente_id, descarga=True,
        ).values_list('lunes', flat=True)
    ]
    for inicio, fin, cierre in CicloDeload.objects.filter(cliente_id=cliente_id).values_list(
        'fecha_inicio', 'fecha_fin_prevista', 'fecha_cierre',
    ):
        if cierre and cierre <= fin:
            # Cerrado antes de tiempo: desde el día del cierre ya no es descarga.
            fin = cierre - timedelta(days=1)
        if fin >= inicio:
            periodos.append((inicio, fin))
    return periodos


def fecha_en_descarga(fecha, periodos):
    return any(inicio <= fecha <= fin for inicio, fin in periodos or ())


def ejercicio_marcado_descarga(entreno, nombre):
    """¿El snapshot de esa sesión prescribió el ejercicio como descarga?"""
    from entrenos.services.decision_log_service import normalizar_ejercicio

    version = getattr(entreno, 'gym_decision_version', None)
    snapshot = getattr(version, 'snapshot', None) or {}
    clave = normalizar_ejercicio(nombre)
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        if normalizar_ejercicio(ej.get('nombre')) != clave:
            continue
        motivo = ej.get('motivo_peso') or {}
        return bool(
            ej.get('deload') or ej.get('_deload_aplicado')
            or (isinstance(motivo, dict) and motivo.get('tipo') == 'recalculado_descarga')
        )
    return False


def es_sesion_descarga(entreno, nombre, periodos=None):
    """True si en esa sesión el ejercicio se hizo en descarga."""
    try:
        if ejercicio_marcado_descarga(entreno, nombre):
            return True
    except Exception:
        pass
    if periodos is None:
        periodos = periodos_descarga(entreno.cliente_id)
    return fecha_en_descarga(entreno.fecha, periodos)


# ── Semana de descarga del plan: peso y reps (2-nov-2026) ──────────────────
# Lo que se busca en una descarga es bajar el esfuerzo, no seguir progresando:
# mismos ejercicios, menos series (lo pone el planificador), RPE 6 y, para que
# ese RPE salga de verdad, un poco menos de peso. Antes el briefing de la
# descarga decía "mismo peso: hoy a por 10 (la última vez 9)" con los 16 kg de
# siempre: una subida en la semana de bajar.

FACTOR_PESO_DESCARGA = 0.9
# 3-nov-2026 (nota 1): con un 10 % menos de peso y las mismas reps de la última
# vez (que salieron a RPE 8-9) la descarga sale a RPE 7-8, no a 6. Para que
# sobren 3 o 4 reps, 3 menos que la última vez, sin bajar del mínimo del rango
# y sin pasar de 3 por debajo del máximo (10-15 → como mucho 12).
REPS_MENOS_DESCARGA = 3


def reps_descarga(reps_ref, minimo, maximo):
    """Reps de una serie de descarga a partir de las de la última vez.

    15 en 10-15 → 12; 13 → 10; 11 → 10. Si la última vez ya fue el mínimo del
    rango, las mismas (el peso más bajo hace el resto).
    """
    reps_ref = int(reps_ref)
    if reps_ref <= minimo:
        return max(1, min(reps_ref, maximo))
    techo = max(minimo, maximo - REPS_MENOS_DESCARGA)
    return max(minimo, min(reps_ref - REPS_MENOS_DESCARGA, techo))


def semana_plan_descarga(cliente_id, fecha):
    """True si la semana de ``fecha`` es de descarga en el plan (SemanaPlanGym)."""
    from entrenos.models import SemanaPlanGym

    lunes = fecha - timedelta(days=fecha.weekday())
    return SemanaPlanGym.objects.filter(cliente_id=cliente_id, lunes=lunes, descarga=True).exists()


def _limpiar_progresion(ej):
    for clave in ('progresion_pospuesta', 'progresion_aplicada', 'sugerencia_tope'):
        if clave in ej:
            ej[clave] = False
    ej.pop('progresion_accion', None)
    ej.pop('reps_sugeridas_tope', None)
    ej.pop('motivo_peso', None)


def ajustar_a_descarga(cliente, ej, hoy):
    """Pone peso y reps de descarga a partir de la última sesión normal.

    Con carga: un 10 % menos de peso (al menos un salto) y como mucho las reps
    de la última vez. Si el rango de la descarga es de otra familia (venías de
    6-8), el peso se estima para el mínimo del rango a RPE 6. Sin carga: las
    reps de la última vez, no una más. Devuelve la frase o None si no toca.
    """
    from analytics.planificador_helms.calculo.compatibilidad_fase import son_rangos_compatibles
    from entrenos.services.maquina_service import a_escala, peso_minimo, salto_carga, tope_de
    from entrenos.services.ultima_sesion_service import kg, peso_para_reps, rango_reps, ultima_sesion

    nombre = ej.get('nombre') or ''
    tipo = ej.get('tipo_progresion') or 'peso_reps'
    if tipo == 'progresion_tiempo' and nombre:
        return _ajustar_tiempo_a_descarga(cliente, ej, nombre, hoy)
    rango_txt = ej.get('repeticiones_plan') or ej.get('repeticiones')
    rango = rango_reps(rango_txt)
    if not nombre or not rango or tipo not in ('peso_reps', 'peso_corporal_lastre', 'progresion_reps'):
        return None
    minimo, maximo = rango
    lectura = ultima_sesion(cliente, nombre, hoy, reps_min=minimo)
    if not lectura or lectura.get('descarga'):
        return None
    ref = lectura['referencia']
    reps_ref = int(round(float(ref.get('reps_mediana') if ref.get('reps_mediana') is not None else ref['reps'])))
    rpe = ej.get('rpe_objetivo') or 6
    dias = (hoy - lectura['fecha']).days
    cuando = 'la última vez' if dias <= 14 else f"el {lectura['fecha']:%d/%m}"

    if tipo == 'progresion_reps':
        reps = reps_descarga(reps_ref, minimo, maximo)
        ej['reps_objetivo_hoy'] = reps
        if reps < reps_ref:
            frase = (f'Semana de descarga: {reps} reps ({cuando} {reps_ref}), sin apurar (RPE {kg(rpe)}): '
                     f'que te sobren 3 o 4. No se busca una más.')
        else:
            frase = (f'Semana de descarga: {reps} reps, las de {cuando}, sin apurar (RPE {kg(rpe)}). '
                     f'No se busca una más.')
    else:
        peso_ref = float(ref['peso'] or 0)
        if peso_ref <= 0:
            return None
        salto = salto_carga(cliente, nombre)
        if son_rangos_compatibles(reps_ref, rango_txt):
            peso = a_escala(peso_ref * FACTOR_PESO_DESCARGA, salto, 'cerca')
            if peso >= peso_ref - 1e-6:
                peso = peso_ref - salto
            reps = reps_descarga(reps_ref, minimo, maximo)
        else:
            estimado = peso_para_reps(peso_ref, reps_ref, ref.get('rpe'), minimo, float(rpe))
            peso = a_escala(estimado or peso_ref * FACTOR_PESO_DESCARGA, salto, 'cerca')
            reps = minimo
        tope = tope_de(cliente, nombre)
        if tope:
            peso = min(peso, float(tope))
        suelo = peso_minimo(nombre)
        if suelo:
            peso = max(peso, suelo)
        if peso <= 0:
            peso = peso_ref
        ej['peso_kg_anterior'] = peso_ref
        ej['peso_kg'] = peso
        if 'peso_recomendado_kg' in ej:
            ej['peso_recomendado_kg'] = peso
        ej['reps_objetivo_hoy'] = reps
        sobra = ': que te sobren 3 o 4' if reps < reps_ref else ''
        frase = (f'Semana de descarga: {kg(peso)} kg × {reps} ({cuando} {kg(peso_ref)} kg × {reps_ref}), '
                 f'sin apurar (RPE {kg(rpe)}){sobra}. No se busca subir.')
    _limpiar_progresion(ej)
    ej['regla_carga'] = 'descarga'
    ej['deload'] = True
    ej['progresion_motivo'] = frase
    ej['progresion_motivo_local'] = 'descarga'
    return frase


FACTOR_TIEMPO_DESCARGA = 0.8


def _ajustar_tiempo_a_descarga(cliente, ej, nombre, hoy):
    """3-nov-2026: ejercicios por tiempo (dead hang) en descarga.

    El briefing del Día 3 decía «Hoy a por 37 s (la última vez 36)»: buscar
    marca en la semana de bajar. Ahora, un 20 % menos que la última vez,
    redondeado a 5 s (36 s → 30 s), y sin buscar marca.
    """
    from entrenos.services.ultima_sesion_service import ultima_sesion

    lectura = ultima_sesion(cliente, nombre, hoy)
    if not lectura or lectura.get('descarga'):
        return None
    valores = [int(s['reps']) for s in lectura.get('series') or [] if s.get('reps')]
    if not valores:
        return None
    ref = max(valores)
    segundos = max(10, int(round(ref * FACTOR_TIEMPO_DESCARGA / 5.0)) * 5)
    if segundos >= ref:
        segundos = max(5, ref - 5)
    dias = (hoy - lectura['fecha']).days
    cuando = 'la última vez' if dias <= 14 else f"el {lectura['fecha']:%d/%m}"
    ej['reps_objetivo_hoy'] = segundos
    ej['reps_objetivo'] = segundos
    frase = (f'Semana de descarga: {segundos} s ({cuando} {ref} s), sin apurar. '
             f'No se busca marca.')
    _limpiar_progresion(ej)
    ej['regla_carga'] = 'descarga'
    ej['deload'] = True
    ej['progresion_motivo'] = frase
    ej['progresion_motivo_local'] = 'descarga'
    return frase


def aplicar_semana_descarga(cliente, ejercicios, hoy, cambios):
    """En la semana de descarga del plan, peso y reps de descarga en todos los ejercicios.

    Quita del briefing los avisos de progresión de esos ejercicios ("progresión
    pospuesta", "subir") y deja uno solo que explica la semana.
    """
    import logging

    if not semana_plan_descarga(cliente.id, hoy):
        return False
    ajustados = set()
    for ej in ejercicios:
        try:
            if ajustar_a_descarga(cliente, ej, hoy):
                ajustados.add(ej.get('nombre'))
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception('[descarga] ajuste de %s falló', ej.get('nombre'))
    cambios[:] = [
        c for c in cambios
        if not (str(c.get('tipo', '')).startswith('progresion_') and c.get('ejercicio_original') in ajustados)
    ]
    if ajustados:
        cambios.append({
            'tipo': 'deload', 'ejercicio_original': None, 'ejercicio_nuevo': None,
            'razon': ('Semana de descarga: mismos ejercicios, la mitad de series, RPE 6 y algo menos de '
                      'peso. Ningún ejercicio busca subir esta semana.'),
        })
    return bool(ajustados)

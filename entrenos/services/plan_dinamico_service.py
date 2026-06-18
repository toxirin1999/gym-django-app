"""
Plan Dinámico — Capa 2 del sistema proactivo.

Toma la lista de ejercicios del plan estático (generada por PlanificadorHelms)
y aplica modificaciones automáticas basadas en las señales acumuladas:

  - Estancamiento (3+ sesiones sin progresión)  → sustituye el ejercicio
  - Molestia recurrente                          → sustituye por variante más segura
  - Deload activo                                → reduce series y capa RPE
  - Progresión ejecutiva (Phase 62H)             → aplica/pospone subir_peso y bajar_peso

El plan original en BD no se toca. Las modificaciones ocurren en memoria
justo antes de que el usuario vea el briefing y la sesión.
"""
import copy
from datetime import date, timedelta

from django.utils import timezone

# ── Alternativas por grupo muscular y patrón ─────────────────────────────────
# Estructura: grupo_muscular → lista de candidatos (nombre, razon_cambio)
_ALTERNATIVAS = {
    'pecho': [
        ('Press Inclinado con Mancuernas', 'ángulo diferente, más rango de movimiento'),
        ('Dips (Fondos en Pecho)', 'patrón de empuje con cadena cinética distinta'),
        ('Cruce de Poleas', 'tensión constante — estimulo diferente al press'),
        ('Press Cerrado en Banca', 'activa más trícep y zona medial del pecho'),
    ],
    'espalda': [
        ('Remo con Mancuerna a una mano', 'unilateral — corrige desequilibrios'),
        ('Remo en Polea Baja (Gironda)', 'perfil de acortamiento distinto'),
        ('Pull-over con Mancuerna', 'énfasis en serrato y porción larga del dorsal'),
        ('Face Pulls', 'activa manguito rotador y retractores'),
    ],
    'piernas': [
        ('Sentadilla Búlgara', 'unilateral — mayor reclutamiento por pierna'),
        ('Peso Muerto Rumano', 'énfasis en femoral y glúteo en elongación'),
        ('Prensa 45º', 'misma cadena, sin carga axial'),
        ('Hip Thrust con Barra', 'glúteo en posición de acortamiento'),
    ],
    'hombros': [
        ('Press Arnold', 'mayor rango de rotación, más fibras activadas'),
        ('Elevaciones Laterales en Cable', 'tensión constante vs mancuerna'),
        ('Press Militar con Mancuernas (sentado)', 'reduce carga lumbar, más ROM'),
        ('Face Pulls', 'equilibra el ratio empuje/tracción en hombro'),
    ],
    'bíceps': [
        ('Curl Martillo con Mancuernas', 'activa braquiorradial y braquial'),
        ('Curl Concentrado', 'aislamiento máximo en posición de acortamiento'),
        ('Curl en Polea Baja', 'tensión constante en todo el recorrido'),
    ],
    'tríceps': [
        ('Fondos en paralelas', 'cadena cerrada, más masa muscular activa'),
        ('Press francés con Mancuernas', 'mayor ROM que con barra'),
        ('Extensión de Tríceps en Polea Alta', 'tensión en acortamiento'),
    ],
    'glúteos': [
        ('Hip Thrust con Barra', 'máxima activación de glúteo mayor'),
        ('Patada de Glúteo en Cable', 'aislamiento en extensión de cadera'),
        ('Sentadilla Búlgara', 'unilateral — corrige desequilibrios'),
    ],
}

# Palabras clave para detectar grupo muscular desde nombre de ejercicio
_KEYWORDS_GRUPO = {
    'pecho':    ['pecho', 'press banca', 'banca', 'press inclinado', 'aperturas', 'dips', 'pec deck', 'fly'],
    'espalda':  ['espalda', 'jalón', 'remo', 'dominada', 'pull', 'face pull', 'pull-over'],
    'piernas':  ['sentadilla', 'prensa', 'peso muerto', 'femoral', 'glúteo', 'zancada', 'hip thrust',
                 'extensión de cuad', 'leg curl', 'leg press', 'rdl', 'rumano'],
    'hombros':  ['press militar', 'elevacion', 'elevación', 'hombro', 'arnold', 'lateral'],
    'bíceps':   ['curl', 'bícep', 'bicep'],
    'tríceps':  ['trícep', 'tricep', 'fondos', 'extensión de trícep', 'press francés'],
    'glúteos':  ['glúteo', 'hip thrust', 'patada'],
}


def _grupo_desde_nombre(nombre, grupo_declarado=None):
    """Detecta el grupo muscular desde el nombre o usa el declarado."""
    if grupo_declarado:
        g = grupo_declarado.lower()
        for k in _ALTERNATIVAS:
            if k in g:
                return k
    nl = nombre.lower()
    for grupo, keywords in _KEYWORDS_GRUPO.items():
        if any(kw in nl for kw in keywords):
            return grupo
    return None


def _elegir_alternativa(nombre_original, grupo, ejercicios_recientes_nombres):
    """
    Elige la primera alternativa del grupo que no sea el ejercicio original
    ni haya aparecido en las últimas 4 sesiones.
    """
    candidatos = _ALTERNATIVAS.get(grupo, [])
    nl_original = nombre_original.lower()
    for candidato, razon in candidatos:
        if candidato.lower() == nl_original:
            continue
        if candidato in ejercicios_recientes_nombres:
            continue
        return candidato, razon
    # Si todos están recientes, devuelve el primero que no sea el original
    for candidato, razon in candidatos:
        if candidato.lower() != nl_original:
            return candidato, razon
    return None, None


def _normalizar(nombre):
    """Normaliza un nombre de ejercicio para comparación fuzzy."""
    import unicodedata
    s = unicodedata.normalize('NFD', nombre.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')  # quita tildes
    # quita palabras genéricas que no aportan identidad
    for stop in ('con', 'de', 'en', 'al', 'la', 'el', 'las', 'los', 'una', 'un'):
        s = s.replace(f' {stop} ', ' ')
    return s.strip()


def _match_nombre(nombre_plan, nombre_log):
    """
    True si nombre_plan y nombre_log se refieren al mismo ejercicio.
    Acepta variaciones como:
      "Press Banca con Barra" ↔ "press banca"
      "Jalón al Pecho"        ↔ "Jalon Pecho"
      "Sentadilla con Barra"  ↔ "Sentadilla"
    """
    np = _normalizar(nombre_plan)
    nl = _normalizar(nombre_log)
    # Exacto después de normalizar
    if np == nl:
        return True
    # Uno contiene al otro (el más corto dentro del más largo)
    shorter, longer = (np, nl) if len(np) <= len(nl) else (nl, np)
    # Solo si el fragmento más corto tiene ≥6 caracteres (evita falsos positivos)
    return len(shorter) >= 6 and shorter in longer


def _ejercicios_recientes(cliente, dias=21):
    """Nombres de ejercicios realizados en los últimos N días (para no repetir sustitución)."""
    try:
        from entrenos.models import EjercicioRealizado
        desde = date.today() - timedelta(days=dias)
        return set(
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, fecha_creacion__date__gte=desde)
            .values_list('nombre_ejercicio', flat=True)
            .distinct()
        )
    except Exception:
        return set()


def _persistir_estado_aplicacion(log, nuevo_estado, nuevo_motivo):
    """
    Phase 62I — persiste si esta progresión se aplicó o se pospuso la última
    vez que se calculó el plan, para que la transparencia (plan_decisiones)
    pueda mostrarlo sin recalcular el freno contextual fuera de contexto.

    Solo escribe si algo cambió, para no tocar `fecha_aplicacion` en cada
    render del briefing mientras el estado se mantiene igual.
    """
    if log.estado_aplicacion != nuevo_estado or log.motivo_postergacion != nuevo_motivo:
        log.estado_aplicacion = nuevo_estado
        log.motivo_postergacion = nuevo_motivo
        log.fecha_aplicacion = timezone.now()
        log.save(update_fields=['estado_aplicacion', 'motivo_postergacion', 'fecha_aplicacion'])


def _aplicar_progresion_ejecutiva(cliente, ejercicios_mod, hoy, cambios):
    """
    Phase 62H — Progresión ejecutiva.

    Regla madre: si el sistema calcula un peso_sugerido (GymDecisionLog
    pendiente de evaluar, accion subir_peso/bajar_peso), la siguiente sesión
    debe usarlo — salvo que un freno contextual tenga una razón explícita
    para posponerlo.

    - bajar_peso: ajuste de seguridad (RPE alto, fallo, fatiga). Se aplica
      siempre, no se pospone por freno contextual.
    - subir_peso: se pospone si el freno contextual semanal frena la
      progresión (mantener_carga / reducir_accesorios según tipo de
      ejercicio) o si el freno local por ejercicio detecta deload activo,
      fallo repetido no controlado, técnica comprometida o molestia reciente
      en ESTE ejercicio (Phase 62K).
    - mantener / cambiar_variante / deload: no se tocan aquí.
    """
    import logging
    logger = logging.getLogger(__name__)

    from entrenos.models import GymDecisionLog
    from entrenos.services.progresion_contextual_service import (
        evaluar_permiso_progresion, _es_ejercicio_principal,
        evaluar_permiso_local_ejercicio,
    )

    logs_pendientes = list(
        GymDecisionLog.objects
        .filter(cliente=cliente, accion__in=('subir_peso', 'bajar_peso'), resultado__isnull=True)
        .order_by('-fecha_creacion')
    )
    logger.debug(f"[progresion_ejecutiva] cliente={cliente.id}: {len(logs_pendientes)} logs subir/bajar")
    if not logs_pendientes:
        logger.debug(f"[progresion_ejecutiva] cliente={cliente.id}: sin logs pendientes")
        return

    permiso = None  # calculado solo si hace falta (subir_peso)

    for ej in ejercicios_mod:
        nombre = ej.get('nombre', '')
        if not nombre:
            continue
        nombre_norm = _normalizar(nombre)

        log = next(
            (l for l in logs_pendientes if _match_nombre(nombre_norm, _normalizar(l.ejercicio))),
            None,
        )
        if log:
            logger.debug(f"[progresion_ejecutiva] MATCH: '{nombre}' → log accion={log.accion}")
        else:
            logger.debug(f"[progresion_ejecutiva] sin match para '{nombre}'")
        if not log:
            continue

        peso_sugerido = log.peso_sugerido
        if peso_sugerido is None:
            continue

        if log.accion == 'bajar_peso':
            ej['peso_kg'] = peso_sugerido
            ej['progresion_aplicada'] = True
            ej['progresion_accion'] = 'bajar_peso'
            ej['progresion_motivo'] = log.motivo
            cambios.append({
                'tipo': 'progresion_aplicada',
                'ejercicio_original': nombre,
                'ejercicio_nuevo': None,
                'accion': 'bajar_peso',
                'peso_sugerido': peso_sugerido,
                'razon': log.motivo,
            })
            _persistir_estado_aplicacion(log, 'aplicada', None)
            continue

        # subir_peso → respeta freno contextual semanal + freno local por ejercicio
        if permiso is None:
            permiso = evaluar_permiso_progresion(cliente, hoy)

        bloquea_semanal = (
            permiso['aplica_a_principales']
            or (permiso['aplica_a_accesorios'] and not _es_ejercicio_principal(ej))
        )

        permiso_local = evaluar_permiso_local_ejercicio(cliente, nombre, hoy)
        bloquea_local = not permiso_local['puede_subir']

        bloquea = bloquea_semanal or bloquea_local

        if bloquea:
            motivo_texto = permiso_local['mensaje'] if bloquea_local else permiso['mensaje']

            ej['progresion_pospuesta'] = True
            ej['progresion_accion'] = 'subir_peso'
            ej['progresion_motivo'] = motivo_texto
            if bloquea_local:
                ej['progresion_motivo_local'] = permiso_local['motivo']
            cambios.append({
                'tipo': 'progresion_pospuesta',
                'ejercicio_original': nombre,
                'ejercicio_nuevo': None,
                'accion': 'subir_peso',
                'peso_sugerido': peso_sugerido,
                'razon': motivo_texto,
            })
            _persistir_estado_aplicacion(log, 'pospuesta', motivo_texto)
        else:
            ej['peso_kg'] = peso_sugerido
            ej['progresion_aplicada'] = True
            ej['progresion_accion'] = 'subir_peso'
            ej['progresion_motivo'] = log.motivo
            cambios.append({
                'tipo': 'progresion_aplicada',
                'ejercicio_original': nombre,
                'ejercicio_nuevo': None,
                'accion': 'subir_peso',
                'peso_sugerido': peso_sugerido,
                'razon': log.motivo,
            })
            _persistir_estado_aplicacion(log, 'aplicada', None)


def aplicar_plan_dinamico(cliente, ejercicios, hoy=None):
    """
    Modifica la lista de ejercicios del plan basándose en señales del sistema.

    Returns:
        ejercicios_mod  — lista de dicts (deep copy con modificaciones aplicadas)
        cambios         — lista de dicts describiendo cada cambio para mostrar al usuario
    """
    import logging
    logger = logging.getLogger(__name__)

    if hoy is None:
        hoy = date.today()

    if not ejercicios:
        logger.debug(f"[plan_dinamico] cliente={cliente.id}: ejercicios vacío")
        return ejercicios, []

    hace_21 = hoy - timedelta(days=21)
    hace_14 = hoy - timedelta(days=14)

    ejercicios_mod = copy.deepcopy(ejercicios)
    cambios = []

    logger.debug(f"[plan_dinamico] cliente={cliente.id}: {len(ejercicios)} ejercicios")

    try:
        from entrenos.models import GymDecisionLog
        from entrenos.services.briefing_service import necesita_deload_gym

        recientes = _ejercicios_recientes(cliente)

        # ── Progresión ejecutiva (Phase 62H) ────────────────────────────────────
        _aplicar_progresion_ejecutiva(cliente, ejercicios_mod, hoy, cambios)

        # ── Deload activo ─────────────────────────────────────────────────────
        deload = necesita_deload_gym(cliente, hoy)
        if deload:
            for ej in ejercicios_mod:
                series_orig = ej.get('series', 3)
                rpe_orig    = ej.get('rpe_objetivo', 8)
                series_new  = max(2, int(series_orig) - 1)
                rpe_new     = min(int(rpe_orig), 7)
                if series_new != series_orig or rpe_new != rpe_orig:
                    ej['series']       = series_new
                    ej['rpe_objetivo'] = rpe_new
                    ej['deload']       = True
            cambios.append({
                'tipo': 'deload',
                'ejercicio_original': None,
                'ejercicio_nuevo': None,
                'razon': 'Semana de descarga automática — series reducidas, RPE limitado a 7.',
            })

        # ── Señales por ejercicio — fetch amplio + match normalizado ──────────
        # Se traen todos los logs recientes sin filtrar por nombre exacto.
        # El match se hace en Python con _match_nombre() para tolerar variaciones
        # entre nombres del planificador ("Press Banca con Barra") y los almacenados
        # en GymDecisionLog ("press banca", "Press de Banca", etc.).
        logs_recientes = list(
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    fecha_creacion__date__gte=hace_21)
            .values('ejercicio', 'motivo')
        )

        # Construir sets normalizados por tipo de señal
        logs_estancados_norm = {
            _normalizar(l['ejercicio'])
            for l in logs_recientes
            if 'Sin progresión' in l['motivo'] or 'sin progresion' in l['motivo'].lower()
        }
        logs_molestia_norm = {
            _normalizar(l['ejercicio'])
            for l in logs_recientes
            if 'molestia' in l['motivo'].lower()
        }

        for ej in ejercicios_mod:
            nombre = ej.get('nombre', '')
            grupo  = _grupo_desde_nombre(nombre, ej.get('grupo_muscular'))

            if not grupo:
                continue

            nombre_norm = _normalizar(nombre)
            es_estancado = any(
                _match_nombre(nombre_norm, log_norm)
                for log_norm in logs_estancados_norm
            )
            es_molestia = any(
                _match_nombre(nombre_norm, log_norm)
                for log_norm in logs_molestia_norm
            )

            # Estancamiento → sustituir ejercicio
            if es_estancado and not es_molestia:
                alternativa, razon_alt = _elegir_alternativa(nombre, grupo, recientes)
                if alternativa:
                    ej['nombre_original']    = nombre
                    ej['nombre']             = alternativa
                    ej['sustituido']         = True
                    ej['motivo_sustitucion'] = 'estancamiento'
                    ej['razon_sustitucion']  = razon_alt or 'cambio de estímulo'
                    recientes.add(alternativa)
                    cambios.append({
                        'tipo': 'sustitucion_estancamiento',
                        'ejercicio_original': nombre,
                        'ejercicio_nuevo': alternativa,
                        'razon': f'Sin progresión en 3+ sesiones → {razon_alt}.',
                    })

            # Molestia → sustituir por variante más segura
            elif es_molestia:
                alternativa, razon_alt = _elegir_alternativa(nombre, grupo, recientes)
                if alternativa:
                    ej['nombre_original']    = nombre
                    ej['nombre']             = alternativa
                    ej['sustituido']         = True
                    ej['motivo_sustitucion'] = 'molestia'
                    ej['razon_sustitucion']  = razon_alt or 'reducir carga en zona afectada'
                    recientes.add(alternativa)
                    cambios.append({
                        'tipo': 'sustitucion_molestia',
                        'ejercicio_original': nombre,
                        'ejercicio_nuevo': alternativa,
                        'razon': f'Molestia recurrente → {razon_alt}.',
                    })

    except Exception as e:
        logger.error(f"[plan_dinamico] cliente={cliente.id}: excepción: {e}", exc_info=True)

    logger.debug(f"[plan_dinamico] cliente={cliente.id}: retorna {len(cambios)} cambios")
    return ejercicios_mod, cambios

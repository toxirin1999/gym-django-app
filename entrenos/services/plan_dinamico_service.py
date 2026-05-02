"""
Plan Dinámico — Capa 2 del sistema proactivo.

Toma la lista de ejercicios del plan estático (generada por PlanificadorHelms)
y aplica modificaciones automáticas basadas en las señales acumuladas:

  - Estancamiento (3+ sesiones sin progresión)  → sustituye el ejercicio
  - Molestia recurrente                          → sustituye por variante más segura
  - Deload activo                                → reduce series y capa RPE

El plan original en BD no se toca. Las modificaciones ocurren en memoria
justo antes de que el usuario vea el briefing y la sesión.
"""
import copy
from datetime import date, timedelta

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


def aplicar_plan_dinamico(cliente, ejercicios, hoy=None):
    """
    Modifica la lista de ejercicios del plan basándose en señales del sistema.

    Returns:
        ejercicios_mod  — lista de dicts (deep copy con modificaciones aplicadas)
        cambios         — lista de dicts describiendo cada cambio para mostrar al usuario
    """
    if hoy is None:
        hoy = date.today()

    if not ejercicios:
        return ejercicios, []

    hace_21 = hoy - timedelta(days=21)
    hace_14 = hoy - timedelta(days=14)

    ejercicios_mod = copy.deepcopy(ejercicios)
    cambios = []

    try:
        from entrenos.models import GymDecisionLog
        from entrenos.services.briefing_service import necesita_deload_gym

        nombres_hoy = [ej.get('nombre', '') for ej in ejercicios_mod]
        recientes = _ejercicios_recientes(cliente)

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

        # ── Señales por ejercicio ─────────────────────────────────────────────
        logs_estancados = set(
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    motivo__icontains='Sin progresión',
                    fecha_creacion__date__gte=hace_21,
                    ejercicio__in=nombres_hoy)
            .values_list('ejercicio', flat=True)
            .distinct()
        )

        logs_molestia = set(
            GymDecisionLog.objects
            .filter(cliente=cliente, accion='cambiar_variante',
                    motivo__icontains='Molestia',
                    fecha_creacion__date__gte=hace_21,
                    ejercicio__in=nombres_hoy)
            .values_list('ejercicio', flat=True)
            .distinct()
        )

        for ej in ejercicios_mod:
            nombre = ej.get('nombre', '')
            grupo  = _grupo_desde_nombre(nombre, ej.get('grupo_muscular'))

            if not grupo:
                continue

            # Estancamiento → sustituir ejercicio
            if nombre in logs_estancados and nombre not in logs_molestia:
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

            # Molestia → sustituir por variante más segura (mismo grupo, alta estabilidad)
            elif nombre in logs_molestia:
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

    except Exception:
        pass

    return ejercicios_mod, cambios

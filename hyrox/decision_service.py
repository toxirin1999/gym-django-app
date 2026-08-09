"""Autoridad pública y única para la decisión diaria Hyrox."""

from datetime import timedelta

from django.utils import timezone


HYROX_STATION_RISK_TAGS = {
    'Sled Push': {'triple_extension_explosiva', 'flexion_rodilla_profunda'},
    'Sled Pull': {'triple_extension_explosiva', 'flexion_rodilla_profunda'},
    'Burpee Broad Jumps': {'impacto_vertical', 'triple_extension_explosiva'},
    'Sandbag Lunges': {'triple_extension_explosiva', 'flexion_rodilla_profunda', 'impacto_vertical', 'lumbar_carga'},
    'Wall Balls': {'impacto_vertical', 'triple_extension_explosiva', 'flexion_rodilla_profunda'},
    'Rowing': {'flexion_rodilla_profunda'},
    'Running (1 km)': {'impacto_vertical'},
}


def normalizar_tags_restringidos(lesion_activa):
    if not lesion_activa:
        return []
    raw = getattr(lesion_activa, 'tags_restringidos', None)
    if not raw:
        return []
    if isinstance(raw, str):
        return [tag.strip() for tag in raw.split(',') if tag.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    return []


def estaciones_bloqueadas_por_tags(tags):
    tags = set(tags or [])
    return [
        estacion for estacion, riesgos in HYROX_STATION_RISK_TAGS.items()
        if tags.intersection(riesgos)
    ]


def leer_senales_secundarias(cliente):
    """Lee señales que solo pueden modular una decisión base favorable."""
    resultado = {
        'senal_corporal': {'hay_senal': False},
        'vigilar_senal_activa': False,
        'futbol_reciente': False,
    }
    try:
        from diario.services.senales_entrenamiento import obtener_senal_corporal_diario
        resultado['senal_corporal'] = obtener_senal_corporal_diario(cliente.usuario)
    except Exception:
        pass
    try:
        from entrenos.models import IntervencionPlan
        hoy = timezone.now().date()
        resultado['vigilar_senal_activa'] = IntervencionPlan.objects.filter(
            cliente=cliente,
            tipo=IntervencionPlan.TIPO_VIGILAR_SENAL,
            estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
        ).exists()
    except Exception:
        pass
    try:
        from entrenos.models import ActividadRealizada
        hoy = timezone.now().date()
        resultado['futbol_reciente'] = ActividadRealizada.objects.filter(
            cliente=cliente,
            tipo='futbol',
            fecha__gte=hoy - timedelta(days=2),
        ).exists()
    except Exception:
        pass
    return resultado


def _decision(estado, causa, titulo, subtitulo, mensaje, accion_label,
              puede_ejecutar_plan, permitido, evitar, **extra):
    payload = {
        'estado': estado,
        'causa': causa,
        'titulo': titulo,
        'subtitulo': subtitulo,
        'mensaje': mensaje,
        'accion_label': accion_label,
        'puede_ejecutar_plan': puede_ejecutar_plan,
        'permitido': permitido,
        'evitar': evitar,
        'tags_restringidos': [],
        'estaciones_bloqueadas': [],
    }
    payload.update(extra)
    return payload


def calcular_hyrox_decision(current_score, resumen_semanal=None, lesion_activa=None,
                            es_descanso_plan=False, estado_entreno=None,
                            senales_secundarias=None):
    """Calcula la decisión soberana: lesión > descanso > TSB > ACWR > readiness."""
    if lesion_activa:
        tags = normalizar_tags_restringidos(lesion_activa)
        estaciones = estaciones_bloqueadas_por_tags(tags)
        zona = getattr(lesion_activa, 'zona_afectada', None) or 'zona lesionada'
        return _decision(
            'recuperar', 'lesion', 'Recuperar', f'Lesión activa en {zona}',
            f'El sistema ha ajustado la sesión para proteger {zona}.', 'Sesión adaptada', False,
            ['Trabajo sin dolor', 'Movilidad controlada', 'Cardio de bajo impacto si no molesta'],
            estaciones or ['Ejercicios asociados a la lesión activa'],
            tags_restringidos=tags, estaciones_bloqueadas=estaciones,
        )
    if es_descanso_plan or estado_entreno == 'descanso':
        return _decision(
            'recuperar', 'descanso_plan', 'Descanso', 'El plan global marca descanso hoy',
            'Tus señales Hyrox acompañan, pero el plan de entrenamiento tiene asignado hoy como día de recuperación. Mañana con más intención.',
            'Día de descanso', False,
            ['Movilidad suave', 'Paseo tranquilo', 'Técnica sin carga'],
            ['Sesión intensa', 'Series Hyrox', 'Trabajo al límite'],
        )

    tsb = resumen_semanal.get('tsb') if isinstance(resumen_semanal, dict) else getattr(resumen_semanal, 'tsb', None)
    acwr = resumen_semanal.get('acwr') if isinstance(resumen_semanal, dict) else getattr(resumen_semanal, 'acwr', None)
    if tsb is not None and tsb <= -20:
        return _decision(
            'recuperar', 'fatiga', 'Recuperar', 'Fatiga acumulada alta',
            'La carga reciente pesa demasiado. Hoy conviene bajar intensidad y conservar continuidad.',
            'Recuperación activa', False,
            ['Zona 2 suave', 'Movilidad', 'Técnica sin fatiga'],
            ['Series duras', 'Simulación', 'Trabajo al fallo'],
        )
    if acwr is not None and acwr > 1.7:
        return _decision(
            'recuperar', 'carga', 'Recuperar', 'Carga aguda muy elevada',
            'La carga acumulada supera claramente tu base crónica. Añadir sesión hoy aumenta el riesgo de lesión.',
            'Descanso activo', False,
            ['Cardio bajo impacto', 'Movilidad', 'Técnica sin carga'],
            ['Volumen extra', 'Sled pesado', 'Compromised Running intenso', 'Sesión Hyrox completa'],
        )
    if acwr is not None and acwr >= 1.5:
        return _decision(
            'sesion_protegida', 'carga_elevada', 'Sesión Protegida',
            'Carga reciente por encima de tu línea habitual',
            'La carga reciente ha cruzado una zona de prudencia. Hoy conviene mantener movimiento, pero reducir volumen e intensidad.',
            'Sesión reducida', True,
            ['Técnica sin carga extra', 'Cardio de baja intensidad', 'Movilidad', 'Volumen reducido (−30 %)'],
            ['Intensidad alta', 'Series al límite', 'Sled pesado', 'Piernas con carga alta'],
        )
    if current_score is not None and current_score < 45:
        return _decision(
            'sostener', 'readiness_bajo', 'Sostener', 'Readiness limitado',
            'Puedes entrenar, pero sin perseguir el límite. El objetivo es cumplir sin acumular deuda.',
            'Sesión moderada', True,
            ['Sesión planificada con RPE controlado', 'Recortar volumen si hace falta'],
            ['Competir contra el reloj', 'Añadir trabajo extra'],
        )
    if current_score is not None and current_score < 70:
        return _decision(
            'ejecutar_con_margen', 'readiness_reducido', 'Ejecutar con margen',
            'Disponibilidad fisiológica por debajo de tu línea habitual',
            'Las señales no piden parar, pero el margen no es amplio. Ejecuta lo previsto sin buscar límite.',
            'Sesión con margen', True,
            ['Sesión planificada', 'RPE controlado', 'Recortar accesorios si hace falta'],
            ['Perseguir récords', 'Añadir series extra', 'Competir contra el reloj'],
        )

    base = _decision(
        'empujar', 'normal', 'Empujar', 'Señales favorables',
        'Tus señales acompañan. Hoy puedes ejecutar la sesión con intención.', 'Ejecutar plan', True,
        ['Sesión planificada', 'Intensidad prevista', 'Registrar RPE al final'],
        ['Improvisar volumen innecesario'],
    )
    if senales_secundarias:
        corporal = senales_secundarias.get('senal_corporal', {})
        intensidad = corporal.get('intensidad') if corporal.get('hay_senal') else None
        futbol = senales_secundarias.get('futbol_reciente', False)
        vigilar = senales_secundarias.get('vigilar_senal_activa', False)
        if intensidad in ('alta', 'moderada') or futbol:
            bullets = []
            if intensidad in ('alta', 'moderada'):
                bullets.append(f'Diario: {corporal.get("texto", "Carga corporal registrada en los últimos días.")}')
            if futbol:
                bullets.append('Fútbol reciente: las piernas ya recibieron carga en los últimos dos días.')
            base.update({
                'estado': 'sostener',
                'causa': 'senal_corporal' if intensidad in ('alta', 'moderada') else 'actividad_reciente',
                'titulo': 'Sostener',
                'subtitulo': 'Señal corporal reciente',
                'mensaje': 'Las métricas Hyrox acompañan, pero el sistema detecta carga reciente. Hoy conviene ejecutar con margen.',
                'accion_label': 'Sesión con margen',
                'evitar': ['Perseguir récords', 'Añadir volumen extra'],
                'explicacion_modulacion': {
                    'intro': 'Tus métricas Hyrox permitirían empujar, pero el sistema detecta carga reciente:',
                    'bullets': bullets,
                    'cierre': 'Hoy no se cancela el plan; se reduce la intención.',
                },
            })
        elif intensidad == 'suave' or vigilar:
            nota = ' El plan observa una señal activa.' if vigilar else ''
            base['mensaje'] += f' El diario apunta algo de carga corporal.{nota} Observa cómo responde el cuerpo.'
    return base

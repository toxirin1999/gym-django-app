"""
Phase Organismo 1 — Resolver estado global del sistema.

Función determinista que lee señales de múltiples módulos
y devuelve el estado global + acción principal del día.

PRINCIPIO MADRE:
El organismo no habla más. Coordina mejor.

PRIORIDAD:
PROTEGIENDO > EN_MARGEN > OBSERVANDO > SILENCIO

REGLAS CLAVE:
1. EN_MARGEN solo si hay acción viable AHORA (entrenar hoy)
2. La acción viene del módulo dominante (no mezclar)
3. PROTEGIENDO gana sobre todo
4. No modifica nada, solo lee

SEÑALES LEÍDAS:
- Hyrox: Pulso, RPE, UserInjury
- JOI: estado (SILENCIO, OBSERVANDO, PRESENTE, PROTEGIENDO)
- Gym: sesión viable, frenos
- Diario: si disponible, entrada pendiente cierre

NOTA: El resolver es defensivo; degrada gracefully si algún módulo no está disponible.
"""

import logging
from datetime import date
from django.utils import timezone

logger = logging.getLogger(__name__)


def resolver_estado_sistema_hoy(usuario):
    """
    Determina el estado global del sistema para el usuario HOY.

    RETORNA:
    {
        "estado": "SILENCIO" | "OBSERVANDO" | "EN_MARGEN" | "PROTEGIENDO",
        "motivo": str (clave interna para debugging),
        "texto": str (texto mínimo visible),
        "accion_label": str (ej: "Registrar recuperación"),
        "accion_url": str (ej: "/hyrox/..."),
        "modulo_principal": str (ej: "hyrox" | "gym" | "diario"),
    }

    PRIORIDAD DE CÁLCULO:
    1. Verificar PROTEGIENDO (cualquier señal fuerte)
    2. Si no: verificar EN_MARGEN (acción viable ahora)
    3. Si no: verificar OBSERVANDO (hay movimiento, no conclusión)
    4. Si no: SILENCIO (reposo)
    """
    try:
        # 1. PROTEGIENDO — señales fuertes
        protegiendo = _check_protegiendo(usuario)
        if protegiendo:
            return protegiendo

        # 2. EN_MARGEN — acción viable ahora
        en_margen = _check_en_margen(usuario)
        if en_margen:
            return en_margen

        # 3. OBSERVANDO — hay movimiento sin conclusión
        observando = _check_observando(usuario)
        if observando:
            return observando

        # 4. SILENCIO — reposo
        return _estado_silencio()

    except Exception as e:
        logger.exception(f"resolver_estado_sistema_hoy: error para usuario {usuario.id}: {e}")
        # Degradación: SILENCIO seguro
        return _estado_silencio()


# ────────────────────────────────────────────────────────────────────
# 1. PROTEGIENDO — Señales fuertes (cualquiera activa)
# ────────────────────────────────────────────────────────────────────

def _check_protegiendo(usuario):
    """
    Retorna dict PROTEGIENDO si hay alguna señal fuerte, None si no.

    Señales de PROTEGIENDO:
    1. Hyrox Pulso PROTEGIENDO
    2. RPE extremo en sesión reciente (≥ 9)
    3. Lesión AGUDA / SUB_AGUDA activa
    4. Recuperación pendiente sin registrar
    5. JOI Habitación está PROTEGIENDO (validación)
    6. Gym tiene freno por lesión
    """
    motivo = None
    modulo_principal = None
    accion_label = None
    accion_url = None

    # Check 1: Hyrox Pulso PROTEGIENDO
    try:
        from hyrox.models import HyroxObjective
        objetivo = HyroxObjective.objects.filter(usuario=usuario).first()
        if objetivo and objetivo.get_pulso() == 'PROTEGIENDO':
            motivo = 'pulso_protegiendo'
            modulo_principal = 'hyrox'
            accion_label = 'Registrar recuperación'
            accion_url = '/hyrox/registrar-recuperacion/'
            return _estado_dict(
                'PROTEGIENDO', motivo,
                'El sistema baja el tono hoy.',
                accion_label, accion_url, modulo_principal
            )
    except Exception:
        pass

    # Check 2: RPE extremo reciente
    try:
        from entrenos.models import EntrenoRealizado
        sesion = EntrenoRealizado.objects.filter(
            cliente__user=usuario,
            fecha=date.today()
        ).order_by('-id').first()
        if sesion and sesion.sesion_detalle and sesion.sesion_detalle.get('rpe_medio', 0) >= 9:
            motivo = 'rpe_extremo'
            modulo_principal = 'gym'
            accion_label = 'Entrenar con margen'
            accion_url = '/entrenos/cliente/{}/entrenamiento-activo/?modo=conservador'.format(
                usuario.cliente_perfil.id
            )
            return _estado_dict(
                'PROTEGIENDO', motivo,
                'El sistema baja el tono hoy.',
                accion_label, accion_url, modulo_principal
            )
    except Exception:
        pass

    # Check 3: Lesión AGUDA / SUB_AGUDA
    try:
        from hyrox.models import UserInjury
        lesion = UserInjury.objects.filter(
            cliente__user=usuario,
            activa=True,
            fase__in=['AGUDA', 'SUB_AGUDA']
        ).first()
        if lesion:
            motivo = 'lesion_activa'
            modulo_principal = 'hyrox'
            accion_label = 'Ver zona afectada'
            accion_url = '/hyrox/lesiones/'
            return _estado_dict(
                'PROTEGIENDO', motivo,
                'El sistema baja el tono hoy.',
                accion_label, accion_url, modulo_principal
            )
    except Exception:
        pass

    # Check 4: Recuperación pendiente
    try:
        from hyrox.models import RecoveryTestLog
        recovery_pending = RecoveryTestLog.objects.filter(
            cliente__user=usuario,
            fecha=date.today(),
            es_apto=False
        ).exists()
        if recovery_pending:
            motivo = 'recuperacion_pendiente'
            modulo_principal = 'hyrox'
            accion_label = 'Registrar recuperación'
            accion_url = '/hyrox/registrar-recuperacion/'
            return _estado_dict(
                'PROTEGIENDO', motivo,
                'El sistema baja el tono hoy.',
                accion_label, accion_url, modulo_principal
            )
    except Exception:
        pass

    # Check 5: JOI Habitación está PROTEGIENDO (validación)
    try:
        from joi.services import determinar_estado_habitacion_joi
        estado, _ = determinar_estado_habitacion_joi(usuario)
        if estado == 'PROTEGIENDO':
            motivo = 'joi_protegiendo'
            modulo_principal = 'joi'
            accion_label = 'Ver habitación'
            accion_url = '/joi/habitacion/'
            return _estado_dict(
                'PROTEGIENDO', motivo,
                'El sistema baja el tono hoy.',
                accion_label, accion_url, modulo_principal
            )
    except Exception:
        pass

    return None


# ────────────────────────────────────────────────────────────────────
# 2. EN_MARGEN — Acción viable AHORA
# ────────────────────────────────────────────────────────────────────

def _check_en_margen(usuario):
    """
    Retorna dict EN_MARGEN si hay acción viable ahora, None si no.

    Condiciones (DEBEN cumplirse TODAS):
    1. Hay entrenamiento viable HOY (Gym)
    2. NO hay freno fuerte en Gym
    3. NO hay Pulso PROTEGIENDO en Hyrox
    4. NO hay lesión AGUDA/SUB_AGUDA
    5. NO hay RPE extremo reciente
    6. Diario ciclo está normal (no pendiente)

    EN_MARGEN = acción viable real, no solo ausencia de problemas.
    """
    try:
        # Check 1: ¿Hay sesión viable hoy?
        from entrenos.services.sesion_recomendada import obtener_sesion_recomendada_hoy

        # Guard: usuario debe tener cliente_perfil
        cliente = getattr(usuario, 'cliente_perfil', None)
        if not cliente:
            return None

        decision = obtener_sesion_recomendada_hoy(cliente)

        # Si estado es 'descanso' o no hay entrenamiento: no es EN_MARGEN
        # Estados viables: 'entrenar' normal o 'version_reducida' (margen con prudencia)
        estados_viables = {'entrenar', 'version_reducida'}
        if not decision or decision.get('estado') not in estados_viables:
            return None

        estado_gym = decision.get('estado')

        entrenamiento = decision.get('entrenamiento')
        if not entrenamiento or not entrenamiento.get('ejercicios'):
            return None

        # Check 2: ¿Hay freno fuerte?
        # Si hay freno contextual suave está OK, pero no lesión/deload
        if decision.get('entrenamiento', {}).get('permiso_progresion'):
            permiso = decision['entrenamiento']['permiso_progresion']
            accion = permiso.get('accion', 'progresion_permitida')
            # 'reducir_accesorios' es OK, 'mantener_carga' por lesión NO
            if accion == 'mantener_carga' and permiso.get('motivo') in ('lesion_activa', 'lesion_retorno'):
                return None

        # Check 3: ¿Hyrox protegiendo?
        try:
            from hyrox.models import HyroxObjective
            objetivo = HyroxObjective.objects.filter(usuario=usuario).first()
            if objetivo and objetivo.get_pulso() == 'PROTEGIENDO':
                return None
        except Exception:
            pass

        # Check 4: ¿Lesión AGUDA/SUB_AGUDA?
        try:
            from hyrox.models import UserInjury
            if UserInjury.objects.filter(
                cliente__user=usuario,
                activa=True,
                fase__in=['AGUDA', 'SUB_AGUDA']
            ).exists():
                return None
        except Exception:
            pass

        # Check 5: ¿RPE extremo?
        try:
            from entrenos.models import EntrenoRealizado
            sesion = EntrenoRealizado.objects.filter(
                cliente__user=usuario,
                fecha=date.today()
            ).order_by('-id').first()
            if sesion and sesion.sesion_detalle and sesion.sesion_detalle.get('rpe_medio', 0) >= 9:
                return None
        except Exception:
            pass

        # Check 6: ¿Diario ciclo normal?
        try:
            from diario.models import BitacoraDiaria
            diario = BitacoraDiaria.objects.filter(
                cliente__user=usuario,
                fecha=date.today()
            ).first()
            if diario and diario.estado in ['sin_entrada']:
                # Sin entrada = no hay pendiente, está OK para EN_MARGEN
                pass
            elif diario and diario.estado in ['manana_hecha']:
                # Cierre pendiente = OBSERVANDO, no EN_MARGEN
                return None
        except Exception:
            pass

        # Check 7: ¿Sesión principal del día ya fue completada?
        # Si existe EntrenoRealizado hoy, la acción principal ya se consumió.
        # Retorna None para que resolver pase a OBSERVANDO/SILENCIO.
        try:
            from entrenos.models import EntrenoRealizado
            if EntrenoRealizado.objects.filter(
                cliente=cliente,
                fecha=date.today()
            ).exists():
                # Sesión principal ya completada hoy → no hay EN_MARGEN activo
                logger.debug(f"Check 7: EntrenoRealizado hoy encontrado para {cliente.id} → retornando None")
                return None
        except Exception as e:
            logger.debug(f"Check 7 exception: {e}")

        # ✅ Todas las condiciones se cumplen: EN_MARGEN
        # Matizar texto según estado de sesión
        if estado_gym == 'version_reducida':
            motivo = 'gym_version_reducida'
            texto = 'Hay margen, con carga ajustada.'
            modo_reducido = 1
        else:  # 'entrenar' normal
            motivo = 'gym_sesion_viable'
            texto = 'Hay margen para seguir el plan.'
            modo_reducido = 0

        # Construir URL con parámetros para briefing
        from urllib.parse import urlencode, quote
        import json as json_module

        rutina_nombre = entrenamiento.get('rutina_nombre') or entrenamiento.get('nombre_rutina') or ''
        ejercicios = entrenamiento.get('ejercicios', [])

        params = {
            'fecha': date.today().strftime('%Y-%m-%d'),
            'rutina_nombre': rutina_nombre,
            'ejercicios': json_module.dumps(ejercicios),
            'modo_reducido': modo_reducido,
        }

        accion_url = '/entrenos/cliente/{}/briefing/?{}'.format(
            cliente.id,
            urlencode(params)
        )

        return _estado_dict(
            'EN_MARGEN',
            motivo,
            texto,
            'Empezar entrenamiento',
            accion_url,
            'gym'
        )


    except Exception as e:
        logger.debug(f"_check_en_margen: {e}")
        return None


# ────────────────────────────────────────────────────────────────────
# 3. OBSERVANDO — Hay movimiento, no conclusión
# ────────────────────────────────────────────────────────────────────

def _check_observando(usuario):
    """
    Retorna dict OBSERVANDO si hay movimiento sin conclusión, None si no.

    Señales de OBSERVANDO:
    1. JOI Habitación está OBSERVANDO (principal)
    """
    try:
        # ¿JOI Habitación está OBSERVANDO?
        from joi.services import determinar_estado_habitacion_joi
        estado, motivo = determinar_estado_habitacion_joi(usuario)
        if estado == 'OBSERVANDO':
            return _estado_dict(
                'OBSERVANDO',
                'joi_observando',
                'Hay movimiento, pero aún no hay lectura formada.',
                'Ver habitación',
                '/joi/habitacion/',
                'joi'
            )
    except Exception as e:
        logger.debug(f"_check_observando: {e}")

    return None


# ────────────────────────────────────────────────────────────────────
# 4. SILENCIO — Reposo (estado por defecto)
# ────────────────────────────────────────────────────────────────────

def _estado_silencio():
    """Estado SILENCIO: no hay señales relevantes."""
    return _estado_dict(
        'SILENCIO',
        'sin_senales',
        'No hay nada que forzar ahora.',
        None,
        None,
        None
    )


# ────────────────────────────────────────────────────────────────────
# Helper: construir dict de estado
# ────────────────────────────────────────────────────────────────────

def _estado_dict(estado, motivo, texto, accion_label, accion_url, modulo):
    """Construye dict estandarizado de estado."""
    # Etiqueta humanizada del estado (para renderización correcta en template)
    estado_labels = {
        'SILENCIO': 'Silencio',
        'OBSERVANDO': 'Observando',
        'EN_MARGEN': 'En Margen',
        'PROTEGIENDO': 'Protegiendo',
    }

    return {
        'estado': estado,
        'estado_label': estado_labels.get(estado, estado),
        'motivo': motivo,
        'texto': texto,
        'accion_label': accion_label,
        'accion_url': accion_url,
        'modulo_principal': modulo,
    }

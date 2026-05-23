"""
Intensidad contextual de la pregunta JOI en la apertura del día.

Regla madre: JOI no debe empezar el día con más profundidad de la que
el usuario ha dado permiso contextual para sostener.
"""
from django.utils import timezone


def calcular_intensidad_pregunta_apertura(contexto: dict) -> str:
    """
    Devuelve 'suave' | 'media' | 'afilada' de forma determinista.
    No llama a ninguna API. Solo lee el contexto.
    """
    if not contexto.get('hay_datos_suficientes'):
        return 'suave'

    if contexto.get('energia_baja') or contexto.get('sueno_bajo') or contexto.get('molestia_zona'):
        return 'suave'

    if contexto.get('patron_reciente_detectado'):
        return 'media'

    if contexto.get('modo_joi') == 'empujar' and contexto.get('senal_suficiente'):
        return 'afilada'

    return 'media'


def construir_contexto_intensidad(cliente, vires, semaforo) -> dict:
    """
    Construye el dict de señales que necesita calcular_intensidad_pregunta_apertura.
    Lee ProsocheDiario + SeguimientoVires recientes.
    """
    from diario.models import ProsocheDiario, SeguimientoVires

    # ── Datos suficientes: al menos 3 entradas de mañana previas ──
    n_entradas = (
        ProsocheDiario.objects
        .filter(prosoche_mes__usuario=cliente.user)
        .exclude(persona_quiero_ser='')
        .count()
    )
    hay_datos = n_entradas >= 3

    # ── Señales del vires de hoy ──
    energia = getattr(vires, 'nivel_energia', None) or 3
    sueno = getattr(vires, 'calidad_sueno', None) or 3
    molestia = getattr(vires, 'molestia_zona', '') or ''
    tiene_molestia = bool(molestia and molestia != 'ninguna')

    # ── Semáforo ──
    modo_joi = (semaforo or {}).get('estado', 'sostener')

    # ── Patrón reciente: últimas 3 semanas con energía ≥ 3 y sin molestia ──
    fecha_limite = timezone.now().date() - timezone.timedelta(days=7)
    vires_recientes = list(
        SeguimientoVires.objects
        .filter(usuario=cliente.user, fecha__gte=fecha_limite)
        .order_by('-fecha')[:3]
    )
    patron_reciente = (
        len(vires_recientes) >= 2
        and all((v.nivel_energia or 3) >= 3 for v in vires_recientes)
        and not any(
            v.molestia_zona and v.molestia_zona != 'ninguna'
            for v in vires_recientes
        )
    )

    senal_suficiente = (
        hay_datos
        and modo_joi == 'empujar'
        and energia > 2
        and sueno > 2
    )

    return {
        'hay_datos_suficientes': hay_datos,
        'energia_baja': energia <= 2,
        'sueno_bajo': sueno <= 2,
        'molestia_zona': tiene_molestia,
        'patron_reciente_detectado': patron_reciente,
        'modo_joi': modo_joi,
        'senal_suficiente': senal_suficiente,
    }

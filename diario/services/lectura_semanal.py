"""
Servicio de lectura semanal prudente — Phase Diario 2.0.

Agrega señales de los últimos 7 días sin interpretarlas.
JOI las traduce con prudencia: una semana no genera identidad.
"""
from collections import Counter
from datetime import timedelta
from django.utils import timezone
from diario.models import ProsocheDiario, SeguimientoVires
from diario.services.estado_diario import tiene_apertura_manana, tiene_cierre_noche


def agregar_semana(usuario, dias=7):
    """
    Devuelve un dict con señales brutas de los últimos `dias` días.
    No interpreta. No concluye. Solo cuenta y nombra.
    """
    hoy = timezone.localdate()
    inicio = hoy - timedelta(days=dias - 1)

    entradas = list(
        ProsocheDiario.objects.filter(
            prosoche_mes__usuario=usuario,
            fecha__range=[inicio, hoy],
        )
    )

    n_aperturas = sum(1 for e in entradas if tiene_apertura_manana(e))
    n_cierres = sum(1 for e in entradas if tiene_cierre_noche(e))
    n_con_joi = sum(1 for e in entradas if e.respuesta_joi_cierre)

    vires = list(
        SeguimientoVires.objects.filter(
            usuario=usuario,
            fecha__range=[inicio, hoy],
        )
    )
    energia_baja_dias = sum(1 for v in vires if v.nivel_energia and v.nivel_energia <= 2)
    cuerpos = Counter(v.cuerpo_cierre for v in vires if v.cuerpo_cierre)
    cuerpo_frecuente = cuerpos.most_common(1)[0][0] if cuerpos else None

    from diario.models import InteraccionSombra
    sombras_semana = list(
        InteraccionSombra.objects.filter(
            fecha__range=[inicio, hoy],
            persona_interina__usuario=usuario,
        ).values_list('persona_interina__nombre', flat=True)
    )
    conteo_personas = Counter(sombras_semana)
    personas_repetidas = [nombre for nombre, n in conteo_personas.items() if n >= 2]

    # Phase 3.3 — contraste señal diario vs entreno completado
    from diario.services.senales_entrenamiento import contrastar_senal_vs_entreno
    from datetime import date as date_type
    contrastes = []
    fecha_iter = inicio
    while fecha_iter <= hoy:
        c = contrastar_senal_vs_entreno(usuario, fecha_iter)
        if c:
            contrastes.append({'fecha': fecha_iter, **c})
        fecha_iter = date_type(fecha_iter.year, fecha_iter.month, fecha_iter.day)
        fecha_iter = fecha_iter + timedelta(days=1)

    hay_datos = (n_aperturas + n_cierres) > 0

    return {
        'n_aperturas': n_aperturas,
        'n_cierres': n_cierres,
        'n_con_joi': n_con_joi,
        'n_dias': dias,
        'energia_baja_dias': energia_baja_dias,
        'cuerpos': dict(cuerpos),
        'cuerpo_frecuente': cuerpo_frecuente,
        'personas_repetidas': personas_repetidas,
        'contrastes': contrastes,
        'hay_datos': hay_datos,
        'inicio': inicio,
        'fin': hoy,
    }


_CUERPO_LABEL = {
    'ligero': 'el cuerpo terminó ligero',
    'cargado': 'algo de carga corporal al cierre',
    'dolorido': 'algo de dolor corporal al cierre',
    'apagado': 'el cuerpo terminó apagado',
}


def _continuidad(n_aperturas, n_dias):
    ratio = n_aperturas / n_dias if n_dias else 0
    if ratio >= 0.7:
        return 'hubo continuidad'
    if ratio >= 0.4:
        return 'hubo continuidad parcial'
    if ratio >= 0.1:
        return 'apareció de forma puntual'
    return None


def generar_lectura_joi(datos):
    """
    Devuelve dos strings: una frase de encuadre y una de señales.
    Nunca interpreta. No concluye sobre la identidad del usuario.
    """
    if not datos['hay_datos']:
        return None, None

    señales = []

    cont = _continuidad(datos['n_aperturas'], datos['n_dias'])
    if cont:
        señales.append(cont)

    if datos['cuerpo_frecuente']:
        señales.append(_CUERPO_LABEL.get(datos['cuerpo_frecuente'], ''))

    if datos['personas_repetidas']:
        señales.append('algunos nombres repitiéndose')

    if datos['energia_baja_dias'] >= 2:
        señales.append('energía baja al menos dos días')

    if not señales:
        return (
            'Esta semana dejó poca huella visible.',
            'Eso también es información.',
        )

    frase_señales = ', '.join(s for s in señales if s)
    return (
        'Esta semana no dice quién eres.',
        f'Solo deja una forma: {frase_señales}.',
    )

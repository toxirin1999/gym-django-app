def _tiene_contenido(valor):
    return bool((valor or '').strip())


def tiene_apertura_manana(prosoche):
    if prosoche is None:
        return False
    campos = [
        prosoche.persona_quiero_ser,
        prosoche.gratitud_1,
        prosoche.gratitud_2,
        prosoche.gratitud_3,
        prosoche.gratitud_4,
        prosoche.gratitud_5,
    ]
    return any(_tiene_contenido(c) for c in campos)


def tiene_cierre_noche(prosoche):
    if prosoche is None:
        return False
    campos = [
        prosoche.que_ha_ido_bien,
        prosoche.reflexiones_dia,
        prosoche.que_puedo_mejorar,
        prosoche.felicidad,
    ]
    return any(_tiene_contenido(c) for c in campos)


def calcular_estado_diario_hoy(prosoche_hoy):
    manana_hecha = tiene_apertura_manana(prosoche_hoy)
    noche_hecha = tiene_cierre_noche(prosoche_hoy)
    tiene_lectura_joi = bool(
        prosoche_hoy and _tiene_contenido(prosoche_hoy.respuesta_joi_cierre)
    )

    if not manana_hecha and not noche_hecha:
        estado = 'sin_entrada'
    elif manana_hecha and not noche_hecha:
        estado = 'manana_hecha'
    elif not manana_hecha and noche_hecha:
        estado = 'solo_noche'
    else:
        estado = 'dia_completo'

    return {
        'manana_hecha': manana_hecha,
        'noche_hecha': noche_hecha,
        'tiene_lectura_joi': tiene_lectura_joi,
        'estado': estado,
    }

"""Una sola lectura y una sola escritura del día de la bitácora.

20-nov-2026: el 20/11 hubo dos filas de ``BitacoraDiaria`` (pk 142 y 143): dos
importaciones casi simultáneas de Salud crearon cada una la suya. La importación
de las 07:40 completó la 142 (variabilidad 130 ms, sueño 7,99 h) y la 143 se quedó
solo con el pulso. Los lectores que toman «la última fila» (snapshot físico,
señales al decidir) veían variabilidad y sueño vacíos.

Lectura: ``lectura_del_dia`` combina las filas del día por campo y dice de qué fila
y fecha sale cada valor. No modifica ni borra ninguna fila.

Escritura: ``fila_del_dia_para_escribir`` es la única puerta para crear o localizar la
fila de hoy; serializa por cliente con un bloqueo sobre la fila del cliente (el
``select_for_update`` sobre un día sin filas no bloquea nada). Siempre devuelve la fila
más antigua del día, así un duplicado ya existente no se agrava.
"""
CAMPOS_SALUD = ('horas_sueno', 'energia_subjetiva', 'calidad_sueno', 'fc_reposo', 'hrv_ms', 'dolor_articular')

# Un cero es un dato válido (energía 0, dolor 0, calidad 0), pero no es una medida
# fisiológica: sueño, pulso en reposo y variabilidad a 0 significan «no medido».
# Al combinar filas, ese cero no tapa una medida real de otra fila del mismo día.
CERO_ES_VALIDO = {
    'energia_subjetiva': True, 'dolor_articular': True, 'calidad_sueno': True,
    'horas_sueno': False, 'fc_reposo': False, 'hrv_ms': False,
}


def filas_del_dia(cliente, fecha):
    from clientes.models import BitacoraDiaria
    return list(BitacoraDiaria.objects.filter(cliente=cliente, fecha=fecha).order_by('pk'))


def lectura_del_dia(filas, campos=CAMPOS_SALUD):
    """({campo: valor}, {campo: {'record_id', 'fecha', 'ultima_importacion_de_la_fila'}}) del día.

    Por campo gana la última fila (por pk) con valor; un cero solo cuenta si el campo
    admite cero (``CERO_ES_VALIDO``) o si no hay ningún otro valor.
    """
    valores, fuentes = {}, {}
    for campo in campos:
        elegido = None
        respaldo = None  # cero de un campo que no lo admite: solo si no hay nada mejor
        for fila in filas:  # orden por pk: la última con dato gana
            v = getattr(fila, campo, None)
            if v is None:
                continue
            if v == 0 and not CERO_ES_VALIDO.get(campo, True):
                respaldo = fila
                continue
            elegido = fila
        fila = elegido or respaldo
        valores[campo] = getattr(fila, campo) if fila is not None else None
        if fila is not None:
            imp = getattr(fila, 'salud_importado_en', None)
            fuentes[campo] = {
                'record_id': fila.pk,
                'fecha': fila.fecha.isoformat() if getattr(fila, 'fecha', None) else None,
                # Hora de la ÚLTIMA importación de esa fila (``salud_importado_en`` se sobrescribe en
                # cada importación): no es la hora en que llegó este valor concreto.
                'ultima_importacion_de_la_fila': imp.isoformat() if imp else None,
            }
    return valores, fuentes


def valores_del_dia(filas, campos=CAMPOS_SALUD):
    return lectura_del_dia(filas, campos)[0]


def importado_en(filas):
    """Última importación entre las filas (no la recepción de un valor concreto)."""
    marcas = [f.salud_importado_en for f in filas if getattr(f, 'salud_importado_en', None)]
    return max(marcas) if marcas else None


def fila_del_dia_para_escribir(cliente, fecha, valores_creacion=None):
    """(fila, creada). Debe llamarse dentro de ``transaction.atomic()``.

    Bloquea la fila del cliente (serializa a todos los escritores del día), localiza la
    fila más antigua del día y, si no hay ninguna, la crea con ``valores_creacion`` y la
    deja en ``fecha`` (``fecha`` es auto_now_add).
    """
    from clientes.models import BitacoraDiaria
    type(cliente).objects.select_for_update().filter(pk=cliente.pk).first()
    fila = (BitacoraDiaria.objects.select_for_update()
            .filter(cliente=cliente, fecha=fecha).order_by('pk').first())
    if fila is not None:
        return fila, False
    fila = BitacoraDiaria.objects.create(cliente=cliente, **(valores_creacion or {}))
    if fila.fecha != fecha:
        BitacoraDiaria.objects.filter(pk=fila.pk).update(fecha=fecha)
        fila.fecha = fecha
    return fila, True


NOTA_HORA = ('hora de la última importación de la fila, no de la recepción de cada valor '
             '(se sobrescribe en cada importación)')


def _combinar(filas):
    """Objeto de solo lectura con la interpretación del día: valores combinados por campo.

    Conserva el resto de campos de la última fila; ``salud_importado_en`` es la última importación
    entre las filas; ``fuentes`` dice de qué fila y fecha sale cada valor. Nunca se guarda.
    """
    from types import SimpleNamespace

    ultima = filas[-1]
    datos = {f.attname: getattr(ultima, f.attname) for f in ultima._meta.concrete_fields}
    valores, fuentes = lectura_del_dia(filas)
    datos.update(valores)
    datos['salud_importado_en'] = importado_en(filas)
    datos['pk'] = datos['id'] = ultima.pk
    datos['filas_ids'] = [f.pk for f in filas]
    datos['fuentes'] = fuentes
    return SimpleNamespace(**datos)


def combinada_del_dia(cliente, fecha):
    """La bitácora del día como la interpretan los motores, o None. Con una fila, esa fila."""
    filas = filas_del_dia(cliente, fecha)
    if not filas:
        return None
    return filas[0] if len(filas) == 1 else _combinar(filas)


def combinadas_por_dia(cliente, desde=None, hasta=None, antes_de=None):
    """{fecha: bitácora del día} en una consulta; con varias filas en un día, la combinación."""
    from clientes.models import BitacoraDiaria

    qs = BitacoraDiaria.objects.filter(cliente=cliente)
    if desde is not None:
        qs = qs.filter(fecha__gte=desde)
    if hasta is not None:
        qs = qs.filter(fecha__lte=hasta)
    if antes_de is not None:
        qs = qs.filter(fecha__lt=antes_de)
    por_dia = {}
    for fila in qs.order_by('fecha', 'pk'):
        por_dia.setdefault(fila.fecha, []).append(fila)
    return {f: (v[0] if len(v) == 1 else _combinar(v)) for f, v in por_dia.items()}


def serie_por_dia(cliente, campo, desde=None, hasta=None, antes_de=None):
    """[(fecha, valor)] con un valor por día (combinado), más reciente primero; sin vacíos."""
    dias = combinadas_por_dia(cliente, desde, hasta, antes_de)
    out = []
    for fecha in sorted(dias, reverse=True):
        v = getattr(dias[fecha], campo, None)
        if v is not None:
            out.append((fecha, v))
    return out

import unicodedata
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from diario.models import (
    AliasSimbiosis,
    OperacionIdentidadSimbiosis,
    PersonaImportante,
    PersonaInterina,
)


def normalizar_nombre_identidad(nombre):
    """Clave estable de identidad; no elimina tildes ni otros diacríticos."""
    return ' '.join(unicodedata.normalize('NFKC', nombre or '').split()).casefold()


def _operacion_existente(operacion_id, *, usuario_id, tipo):
    if operacion_id is None:
        return None
    operacion = OperacionIdentidadSimbiosis.objects.filter(pk=operacion_id).first()
    if operacion and (operacion.usuario_id != usuario_id or operacion.tipo != tipo):
        raise ValidationError('La clave idempotente ya pertenece a otra operación.')
    return operacion


def _validar_tipo(tipo):
    validos = {valor for valor, _ in PersonaImportante.TIPO_ENTIDAD_CHOICES}
    if tipo not in validos:
        raise ValidationError({'tipo_entidad': 'Tipo de entidad inválido.'})


@transaction.atomic
def corregir_identidad(entidad, *, nombre=None, tipo_entidad=None, operacion_id=None):
    existente = _operacion_existente(
        operacion_id, usuario_id=entidad.usuario_id, tipo='corregir',
    )
    if existente:
        return existente
    modelo = type(entidad)
    if modelo not in (PersonaImportante, PersonaInterina):
        raise ValidationError('La entidad no pertenece a Simbiosis.')
    entidad = modelo.objects.select_for_update().get(pk=entidad.pk)
    nuevo_nombre = ' '.join((nombre if nombre is not None else entidad.nombre).split())
    nuevo_tipo = tipo_entidad or entidad.tipo_entidad
    _validar_tipo(nuevo_tipo)
    anterior = {'nombre': entidad.nombre, 'tipo_entidad': entidad.tipo_entidad}
    objetivo = {'nombre': nuevo_nombre, 'tipo_entidad': nuevo_tipo}

    if normalizar_nombre_identidad(entidad.nombre):
        campos = {'persona_confirmada': entidad} if modelo is PersonaImportante else {'persona_interina': entidad}
        AliasSimbiosis.objects.get_or_create(
            usuario=entidad.usuario,
            nombre_normalizado=normalizar_nombre_identidad(entidad.nombre),
            defaults={'nombre': entidad.nombre, 'origen': 'correccion', **campos},
            **campos,
        )
    entidad.nombre = nuevo_nombre
    entidad.tipo_entidad = nuevo_tipo
    entidad.full_clean(exclude=['nombre_normalizado'])
    entidad.save(update_fields=['nombre', 'nombre_normalizado', 'tipo_entidad'])
    kwargs = {'origen': entidad} if modelo is PersonaImportante else {'interina': entidad}
    return OperacionIdentidadSimbiosis.objects.create(
        id=operacion_id or uuid.uuid4(), usuario=entidad.usuario, tipo='corregir',
        payload={'antes': anterior, 'despues': objetivo}, **kwargs,
    )


def _raiz(persona):
    visitadas = set()
    actual = persona
    while actual.fusionada_en_id:
        if actual.pk in visitadas:
            raise ValidationError('Se detectó un ciclo en las identidades fusionadas.')
        visitadas.add(actual.pk)
        actual = actual.fusionada_en
    return actual


@transaction.atomic
def fusionar_personas(origen, destino, *, operacion_id=None):
    existente = _operacion_existente(
        operacion_id, usuario_id=origen.usuario_id, tipo='fusionar',
    )
    if existente:
        return existente
    if origen.pk == destino.pk:
        raise ValidationError('Origen y destino deben ser distintos.')
    ids = sorted([origen.pk, destino.pk])
    bloqueadas = {
        p.pk: p for p in PersonaImportante.objects.select_for_update().filter(pk__in=ids).order_by('pk')
    }
    if len(bloqueadas) != 2:
        raise ValidationError('Identidad inexistente.')
    origen, destino = bloqueadas[origen.pk], bloqueadas[destino.pk]
    if origen.usuario_id != destino.usuario_id:
        raise ValidationError('No se pueden cruzar identidades de usuarios distintos.')
    if origen.tipo_entidad != destino.tipo_entidad:
        raise ValidationError('No se pueden fusionar tipos de entidad distintos.')
    if origen.fusionada_en_id or destino.fusionada_en_id:
        raise ValidationError('La fusión solo puede realizarse entre identidades raíz.')
    if _raiz(destino).pk == origen.pk:
        raise ValidationError('La fusión crearía un ciclo.')

    alias, _ = AliasSimbiosis.objects.get_or_create(
        usuario=origen.usuario, persona_confirmada=destino,
        nombre_normalizado=origen.nombre_normalizado,
        defaults={'nombre': origen.nombre, 'origen': 'fusion'},
    )
    origen.fusionada_en = destino
    origen.full_clean()
    origen.save(update_fields=['fusionada_en'])
    return OperacionIdentidadSimbiosis.objects.create(
        id=operacion_id or uuid.uuid4(), usuario=origen.usuario, tipo='fusionar',
        origen=origen, destino=destino,
        payload={'alias_creado_id': alias.pk},
    )


@transaction.atomic
def deshacer_operacion_identidad(operacion, *, operacion_id=None):
    operacion = OperacionIdentidadSimbiosis.objects.select_for_update().get(pk=operacion.pk)
    if hasattr(operacion, 'operacion_deshacer'):
        return operacion.operacion_deshacer
    existente = _operacion_existente(
        operacion_id, usuario_id=operacion.usuario_id, tipo='deshacer',
    )
    if existente:
        return existente
    if operacion.tipo == 'deshacer':
        raise ValidationError('No se puede deshacer una operación de deshacer.')

    if operacion.tipo == 'fusionar':
        origen = PersonaImportante.objects.select_for_update().get(pk=operacion.origen_id)
        if origen.fusionada_en_id != operacion.destino_id:
            raise ValidationError('La identidad cambió después de la operación.')
        origen.fusionada_en = None
        origen.save(update_fields=['fusionada_en'])
        alias_id = operacion.payload.get('alias_creado_id')
        if alias_id:
            AliasSimbiosis.objects.filter(pk=alias_id).update(activo=False)
    elif operacion.tipo == 'corregir':
        entidad = operacion.origen or operacion.interina
        entidad = type(entidad).objects.select_for_update().get(pk=entidad.pk)
        antes = operacion.payload['antes']
        entidad.nombre = antes['nombre']
        entidad.tipo_entidad = antes['tipo_entidad']
        entidad.save(update_fields=['nombre', 'nombre_normalizado', 'tipo_entidad'])

    return OperacionIdentidadSimbiosis.objects.create(
        id=operacion_id or uuid.uuid4(), usuario=operacion.usuario, tipo='deshacer',
        origen=operacion.origen, destino=operacion.destino, interina=operacion.interina,
        deshace_a=operacion, payload={'tipo_deshago': operacion.tipo},
    )


def resolver_alias(usuario, nombre):
    clave = normalizar_nombre_identidad(nombre)
    aliases = list(
        AliasSimbiosis.objects.filter(
            usuario=usuario, nombre_normalizado=clave, activo=True,
        ).select_related('persona_confirmada__fusionada_en', 'persona_interina')
    )
    objetivos = {}
    for alias in aliases:
        objetivo = alias.persona_confirmada or alias.persona_interina
        if isinstance(objetivo, PersonaImportante):
            objetivo = _raiz(objetivo)
        objetivos[(type(objetivo), objetivo.pk)] = objetivo
    if len(objetivos) != 1:
        return None
    return next(iter(objetivos.values()))

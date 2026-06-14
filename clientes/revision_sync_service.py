"""
Phase 63.1 — sincroniza medidas corporales (cintura, peso_corporal, grasa_corporal)
hacia el historial `RevisionProgreso` cuando cambian de verdad.

Sin esto, `entrenos.services.revision_progreso_service._calcular_senal_medidas`
(Phase 63) nunca tiene los ≥2 registros que necesita, porque el snapshot en
`Cliente` no genera histórico por sí solo.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from clientes.models import RevisionProgreso

CAMPOS_REVISION = ['cintura', 'peso_corporal', 'grasa_corporal']


def _a_decimal(valor):
    if valor is None or valor == '':
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        return None


def crear_revision_si_medidas_cambiaron(cliente, valores_anteriores, valores_nuevos, fecha=None):
    """
    Crea un RevisionProgreso si cintura/peso_corporal/grasa_corporal cambiaron
    respecto a `valores_anteriores`. No crea nada si no hay cambios reales, si
    todos los valores nuevos vienen vacíos, o si ya existe una revisión en
    `fecha` con esos mismos valores.
    """
    nuevos = {campo: _a_decimal(valores_nuevos.get(campo)) for campo in CAMPOS_REVISION}

    if all(valor is None for valor in nuevos.values()):
        return None

    anteriores = {campo: _a_decimal(valores_anteriores.get(campo)) for campo in CAMPOS_REVISION}

    if nuevos == anteriores:
        return None

    fecha = fecha or date.today()

    ya_existe = RevisionProgreso.objects.filter(cliente=cliente, fecha=fecha, **nuevos).exists()
    if ya_existe:
        return None

    revision = RevisionProgreso.objects.create(cliente=cliente, **nuevos)
    if fecha != date.today():
        RevisionProgreso.objects.filter(pk=revision.pk).update(fecha=fecha)
        revision.refresh_from_db()
    return revision

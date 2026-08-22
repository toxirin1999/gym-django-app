"""Sello causal entre una autoridad Gym supervisada y su ejecución real."""

from dataclasses import dataclass
from datetime import datetime

from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from entrenos.models import GymDecisionVersion


SELLO_SCHEMA_VERSION = 1
SELLO_SALT = "entrenos.sello-ejecucion-gym.v1"
SELLO_MAX_AGE_SECONDS = 24 * 60 * 60


class SelloEjecucionGymInvalido(ValueError):
    """El sello no permite atribuir causalmente una ejecución."""


@dataclass(frozen=True)
class SelloEjecucionGymValidado:
    version: GymDecisionVersion
    emitida_en: datetime
    estado_causal: str


def emitir_sello_ejecucion_gym(*, version, user, emitida_en=None):
    """Firma la versión exacta mostrada al usuario al abrir la sesión."""
    if not user or not user.is_authenticated:
        raise SelloEjecucionGymInvalido("El usuario del sello no es válido.")
    if version.cliente.user_id != user.pk or not version.vigente:
        raise SelloEjecucionGymInvalido("La autoridad ya no es emitible.")

    emitida_en = emitida_en or timezone.now()
    payload = {
        "schema": SELLO_SCHEMA_VERSION,
        "user_id": user.pk,
        "cliente_id": version.cliente_id,
        "fecha": version.fecha.isoformat(),
        "decision_pk": version.pk,
        "decision_id": version.decision_id,
        "base_fingerprint": version.base_fingerprint,
        "issued_at": emitida_en.isoformat(),
    }
    return signing.dumps(payload, salt=SELLO_SALT, compress=True)


@transaction.atomic
def validar_sello_ejecucion_gym(*, sello, user, cliente, fecha_autoridad):
    """Valida identidad y bloquea la versión hasta que el POST la vincule."""
    try:
        payload = signing.loads(
            sello,
            salt=SELLO_SALT,
            max_age=SELLO_MAX_AGE_SECONDS,
        )
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise SelloEjecucionGymInvalido("El sello de autoridad no es válido.") from exc

    if not isinstance(payload, dict) or payload.get("schema") != SELLO_SCHEMA_VERSION:
        raise SelloEjecucionGymInvalido("La versión del sello no es compatible.")
    if not user or not user.is_authenticated:
        raise SelloEjecucionGymInvalido("El sello requiere una sesión autenticada.")
    if payload.get("user_id") != user.pk or payload.get("cliente_id") != cliente.pk:
        raise SelloEjecucionGymInvalido("El sello pertenece a otro usuario.")
    if payload.get("fecha") != fecha_autoridad.isoformat():
        raise SelloEjecucionGymInvalido("El sello pertenece a otra fecha del plan.")

    emitida_en = parse_datetime(payload.get("issued_at") or "")
    if emitida_en is None:
        raise SelloEjecucionGymInvalido("El sello no contiene una emisión válida.")
    if timezone.is_naive(emitida_en):
        emitida_en = timezone.make_aware(emitida_en, timezone.get_current_timezone())

    try:
        version = (
            GymDecisionVersion.objects.select_for_update()
            .select_related("cliente__user")
            .get(pk=payload.get("decision_pk"))
        )
    except (GymDecisionVersion.DoesNotExist, TypeError, ValueError) as exc:
        raise SelloEjecucionGymInvalido("La autoridad sellada ya no existe.") from exc

    if (
        version.cliente_id != cliente.pk
        or version.fecha != fecha_autoridad
        or version.decision_id != payload.get("decision_id")
        or version.base_fingerprint != payload.get("base_fingerprint")
        or version.creado_en > emitida_en
    ):
        raise SelloEjecucionGymInvalido("La identidad causal del sello no coincide.")

    if version.vigente:
        estado_causal = "exacta"
    else:
        reemplazo_posterior = GymDecisionVersion.objects.filter(
            cliente_id=cliente.pk,
            fecha=fecha_autoridad,
            creado_en__gte=emitida_en,
        ).exclude(pk=version.pk).exists()
        if not reemplazo_posterior:
            raise SelloEjecucionGymInvalido("La autoridad fue invalidada sin reemplazo trazable.")
        estado_causal = "superada_durante_ejecucion"

    return SelloEjecucionGymValidado(
        version=version,
        emitida_en=emitida_en,
        estado_causal=estado_causal,
    )

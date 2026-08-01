from django.db import transaction

from diario.models import Interaccion, InteraccionSombra


PREFIJO_TITULO_LEGACY = 'Mención detectada · '


def _sombras_coincidentes(interaccion):
    """Devuelve solo orígenes cuya identidad y contenido son inequívocos."""
    personas_ids = list(interaccion.personas.values_list('pk', flat=True))
    if not personas_ids:
        return InteraccionSombra.objects.none()

    return (
        InteraccionSombra.objects.filter(
            persona_interina__usuario_id=interaccion.usuario_id,
            persona_interina__persona_importante_id__in=personas_ids,
            persona_interina__persona_importante__usuario_id=interaccion.usuario_id,
            fecha=interaccion.fecha,
            tipo_interaccion=interaccion.tipo_interaccion,
            descripcion=interaccion.descripcion,
            mi_sentir=interaccion.mi_sentir,
            aprendizaje=interaccion.aprendizaje,
            interaccion_migrada__isnull=True,
        )
        .filter(
            persona_interina__nombre=interaccion.titulo[len(PREFIJO_TITULO_LEGACY):]
        )
        .order_by('pk')
    )


def reconciliar_simbiosis_legacy(*, apply=False, user_id=None, limit=100):
    candidatos = Interaccion.objects.filter(
        origen_sombra__isnull=True,
        titulo__startswith=PREFIJO_TITULO_LEGACY,
    ).order_by('pk')
    if user_id is not None:
        candidatos = candidatos.filter(usuario_id=user_id)
    candidatos = list(candidatos[:max(0, limit)])

    hallazgos = []
    elegibles = 0
    aplicados = 0
    ambiguos = 0

    for interaccion in candidatos:
        sombras = list(_sombras_coincidentes(interaccion)[:2])
        if len(sombras) == 1:
            sombra = sombras[0]
            confianza = 'high'
            propuesta = {'origen_sombra_id': sombra.pk}
            elegibles += 1
            aplicado = False
            if apply:
                with transaction.atomic():
                    aplicado = bool(
                        Interaccion.objects.filter(
                            pk=interaccion.pk,
                            origen_sombra__isnull=True,
                        ).update(origen_sombra_id=sombra.pk)
                    )
                aplicados += int(aplicado)
        elif len(sombras) > 1:
            confianza = 'ambiguous'
            propuesta = None
            ambiguos += 1
            aplicado = False
        else:
            confianza = 'none'
            propuesta = None
            aplicado = False

        hallazgos.append({
            'applied': aplicado,
            'before': {'origen_sombra_id': None},
            'code': 'interaccion_legacy_sin_origen_sombra',
            'confidence': confianza,
            'evidence': {
                'candidate_shadow_ids': [sombra.pk for sombra in sombras],
                'user_id': interaccion.usuario_id,
            },
            'model': 'diario.Interaccion',
            'pk': interaccion.pk,
            'proposed': propuesta,
            'reversible': True,
        })

    return {
        'hallazgos': hallazgos,
        'candidatos': len(candidatos),
        'elegibles': elegibles,
        'aplicados': aplicados,
        'ambiguos': ambiguos,
    }

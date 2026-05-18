"""
Phase 29 — Alternativas revisables por lesión.

CONTRACT:
- The system does NOT substitute automatically.
- It offers candidate alternatives that the user reviews and optionally accepts.
- Alternatives are exercises from the same muscle group WITHOUT restricted risk_tags.
- Language: "a valorar", "si molesta" — never "haz esto" or "sustitución segura".
- If accepted, saved as motivo_sustitucion='lesion_retorno' or 'lesion_activa'.
  This is a manual decision, not an algorithmic one.

The service is read-only: no DB writes, no session modification.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Notes that explain why an alternative is gentler with the injury
_NOTAS_ALTERNATIVAS = {
    'lesion_retorno': (
        'Alternativa a valorar si el ejercicio principal molesta durante la ejecución. '
        'No la apliques si no la conoces bien.'
    ),
    'lesion_activa': (
        'Opción más suave para considerar si decides entrenar pese a la lesión activa. '
        'Consulta si hay duda sobre el rango apropiado.'
    ),
}

_NOTA_DEFAULT = 'Alternativa a valorar. Prueba con rango reducido primero.'


def buscar_alternativas_lesion(
    nombre_ejercicio: str,
    grupo_muscular: str,
    tags_restringidos: list,
    fase_lesion: str = 'RETORNO',
    limite: int = 4,
) -> list[dict]:
    """
    Phase 29A — Returns safe exercise alternatives for an injury-flagged exercise.

    Criteria for an alternative:
    - Same muscle group (partial match on grupo_muscular)
    - Does NOT have any of the restricted tags in its risk_tags
    - Is not the same exercise (by name, case-insensitive)
    - Sorted: fewer risk_tags = safer = higher priority

    Returns list of dicts:
        nombre:         str
        grupo_muscular: str
        risk_tags:      list[str]
        nota:           str  — contextual prudent note
    """
    try:
        from rutinas.models import EjercicioBase

        restringidos = set(tags_restringidos or [])
        nombre_lower = nombre_ejercicio.lower().strip()

        # Partial group match (first 12 chars to handle "Cuadriceps" vs "Cuádriceps/Pierna")
        grupo_prefix = grupo_muscular.strip()[:12] if grupo_muscular else ''

        candidatos = (
            EjercicioBase.objects
            .filter(grupo_muscular__icontains=grupo_prefix)
            .exclude(nombre__iexact=nombre_ejercicio)
        ) if grupo_prefix else EjercicioBase.objects.none()

        alternativas = []
        for ej in candidatos:
            if ej.nombre.lower().strip() == nombre_lower:
                continue  # same name, different case
            ej_tags = set(ej.risk_tags or [])
            if ej_tags & restringidos:  # has at least one restricted tag → not safe
                continue
            alternativas.append({
                'nombre':         ej.nombre,
                'grupo_muscular': ej.grupo_muscular,
                'risk_tags':      sorted(ej_tags),
                'nota':           _NOTA_DEFAULT,
            })

        # Sort: fewer risk_tags first (safer), then alphabetically
        alternativas.sort(key=lambda x: (len(x['risk_tags']), x['nombre']))

        nota_fase = _NOTAS_ALTERNATIVAS.get(
            'lesion_activa' if fase_lesion in ('AGUDA', 'SUB_AGUDA') else 'lesion_retorno',
            _NOTA_DEFAULT,
        )
        for alt in alternativas:
            alt['nota'] = nota_fase

        return alternativas[:limite]

    except Exception as e:
        logger.warning('buscar_alternativas_lesion: error para %s — %s', nombre_ejercicio, e)
        return []


def nota_prudente_lesion(fase_lesion: str) -> str:
    """Returns the prudent contextual note for the UI based on injury phase."""
    if fase_lesion in ('AGUDA', 'SUB_AGUDA'):
        return (
            'Opciones más suaves a valorar si decides entrenar. '
            'En fase aguda, prioriza el descanso relativo.'
        )
    return (
        'Alternativas a valorar si el ejercicio principal genera molestia durante la ejecución. '
        'No sustituyas automáticamente — prueba el ejercicio original primero con rango reducido.'
    )

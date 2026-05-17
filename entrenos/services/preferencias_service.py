"""
Phase 22 — Learned plan preferences.

CONTRACT:
- A preference is created only after the SAME probe type was favorable ≥ 2 times
  AND the user explicitly consented (accepted 'Repetir' at least once).
- A preference is a soft inclination, not a rule. The motor may respect it when possible.
- NEVER silently reprograms the plan.
- Reversible: user can suspend or revoke at any time.
- Does NOT write to ManualDavid.

The first learnable preference: evitar_pierna_tras_futbol (clearest sports logic).
"""

import logging
from datetime import timedelta

from django.utils import timezone

from entrenos.models import IntervencionPlan, PreferenciaPlanAprendida

logger = logging.getLogger(__name__)

# Mapping from redistrib probe type → preference type
_REDISTRIB_A_PREFERENCIA = {
    IntervencionPlan.TIPO_REDISTRIB_PIERNA: PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL,
    IntervencionPlan.TIPO_REDISTRIB_DIA:    PreferenciaPlanAprendida.TIPO_EVITAR_DIA,
    IntervencionPlan.TIPO_REDISTRIB_DIAS:   PreferenciaPlanAprendida.TIPO_MENOS_DIAS,
    IntervencionPlan.TIPO_REDISTRIB_LIGERO: PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA,
}

_DESCRIPCION_PREFERENCIA = {
    PreferenciaPlanAprendida.TIPO_EVITAR_PIERNA_FUTBOL:
        'El plan intentará no colocar sesión de pierna dentro de las 48h posteriores al fútbol.',
    PreferenciaPlanAprendida.TIPO_EVITAR_DIA:
        'El plan intentará evitar sesiones principales en el día que caía con frecuencia.',
    PreferenciaPlanAprendida.TIPO_MENOS_DIAS:
        'El plan tomará como referencia real la estructura de menos días semanales.',
    PreferenciaPlanAprendida.TIPO_ALIGERAR_DIA:
        'El plan marcará los accesorios como opcionales en el día que concentraba versiones esenciales.',
}


def detectar_candidata_preferencia(cliente, fecha_ref=None):
    """
    Phase 22B — Returns a preference candidate if the same probe type has been
    favorable ≥ 2 times (original probe + at least one repeat from 'continuidad_fase21').

    Returns dict or None:
        tipo_preferencia: str
        tipo_intervencion: str
        descripcion: str
        evidencia_count: int
    """
    from entrenos.services.sugerencias_service import evaluar_prueba_distribucion

    fecha_ref = fecha_ref or timezone.localdate()

    for tipo_redistrib, tipo_pref in _REDISTRIB_A_PREFERENCIA.items():
        # Skip if preference already exists and is active
        if PreferenciaPlanAprendida.objects.filter(
            cliente=cliente, tipo=tipo_pref, estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
        ).exists():
            continue

        # Count completed probes of this type (original + repetitions)
        probes = list(IntervencionPlan.objects.filter(
            cliente=cliente,
            tipo=tipo_redistrib,
            estado__in=[IntervencionPlan.ESTADO_ACTIVA, IntervencionPlan.ESTADO_EXPIRADA],
        ).order_by('-fecha_fin'))

        if len(probes) < 2:
            continue

        # Check the two most recent evaluations
        favorable_count = 0
        for probe in probes[:3]:  # look at last 3 probes max
            # Temporarily fake fecha_ref to evaluate that probe's period
            mock_fecha = probe.fecha_fin + timedelta(days=1)
            try:
                evaluacion = evaluar_prueba_distribucion(cliente, mock_fecha)
                if evaluacion and evaluacion.get('resultado') == 'favorable':
                    favorable_count += 1
            except Exception:
                continue

        if favorable_count >= 2:
            return {
                'tipo_preferencia': tipo_pref,
                'tipo_intervencion': tipo_redistrib,
                'descripcion': _DESCRIPCION_PREFERENCIA.get(tipo_pref, ''),
                'evidencia_count': favorable_count,
            }

    return None


def crear_preferencia(cliente, tipo_preferencia, tipo_intervencion, evidencia_count=2, metadata=None, fecha_ref=None):
    """
    Phase 22C — Creates a PreferenciaPlanAprendida when the user accepts.
    Safe to call multiple times: updates existing suspended preference instead of duplicating.
    """
    fecha_ref = fecha_ref or timezone.localdate()

    existente = PreferenciaPlanAprendida.objects.filter(
        cliente=cliente, tipo=tipo_preferencia,
    ).order_by('-fecha_inicio').first()

    if existente and existente.estado == PreferenciaPlanAprendida.ESTADO_ACTIVA:
        return existente  # already active

    if existente and existente.estado == PreferenciaPlanAprendida.ESTADO_SUSPENDIDA:
        existente.estado = PreferenciaPlanAprendida.ESTADO_ACTIVA
        existente.ultima_confirmacion = fecha_ref
        existente.evidencia_count = evidencia_count
        existente.save(update_fields=['estado', 'ultima_confirmacion', 'evidencia_count'])
        return existente

    return PreferenciaPlanAprendida.objects.create(
        cliente=cliente,
        tipo=tipo_preferencia,
        estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
        evidencia_count=evidencia_count,
        origen_patron=tipo_intervencion,
        descripcion=_DESCRIPCION_PREFERENCIA.get(tipo_preferencia, ''),
        fecha_inicio=fecha_ref,
        ultima_confirmacion=fecha_ref,
        metadata=metadata or {},
    )


def get_preferencias_activas(cliente):
    """Returns all active preferences for a client."""
    return list(PreferenciaPlanAprendida.objects.filter(
        cliente=cliente, estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
    ))


def tiene_preferencia_activa(cliente, tipo_preferencia):
    """Quick boolean check for a specific preference type."""
    return PreferenciaPlanAprendida.objects.filter(
        cliente=cliente, tipo=tipo_preferencia, estado=PreferenciaPlanAprendida.ESTADO_ACTIVA,
    ).exists()

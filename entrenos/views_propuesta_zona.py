"""Responder a una propuesta del entrenador (aceptar o ahora no)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from entrenos.models import PropuestaZonaGym
from entrenos.services.propuesta_zona_service import (
    PropuestaNoVigente, aceptar_propuesta, rechazar_propuesta,
)


def _propuesta_del_usuario(request, propuesta_id):
    return get_object_or_404(PropuestaZonaGym, pk=propuesta_id, cliente__user=request.user)


@login_required
@require_POST
def aceptar(request, propuesta_id):
    propuesta = _propuesta_del_usuario(request, propuesta_id)
    try:
        aceptar_propuesta(propuesta)
    except PropuestaNoVigente:
        pass  # ya respondida: Ahora muestra su estado real
    return redirect('clientes:dashboard_silencioso_preview')


@login_required
@require_POST
def rechazar(request, propuesta_id):
    propuesta = _propuesta_del_usuario(request, propuesta_id)
    try:
        rechazar_propuesta(propuesta)
    except PropuestaNoVigente:
        pass
    return redirect('clientes:dashboard_silencioso_preview')

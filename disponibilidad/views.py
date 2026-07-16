from datetime import timedelta

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from clientes.models import Cliente

from .models import RegistroDisponibilidad

HACE_HORAS_MAX = 24.0  # más allá de esto, pedir que se registre como estaba (evita cronologías disparatadas)


@require_POST
def registrar(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    nivel = request.POST.get('nivel')
    origen = request.POST.get('origen', '')

    if nivel not in dict(RegistroDisponibilidad.NIVEL_CHOICES):
        return HttpResponseBadRequest('nivel inválido')

    momento_ingesta = None
    hace_horas = request.POST.get('hace_horas')
    if hace_horas:
        try:
            horas = float(hace_horas)
        except ValueError:
            return HttpResponseBadRequest('hace_horas inválido')
        if not (0 < horas <= HACE_HORAS_MAX):
            return HttpResponseBadRequest('hace_horas fuera de rango')
        momento_ingesta = timezone.now() - timedelta(hours=horas)

    RegistroDisponibilidad.objects.create(
        cliente=cliente, nivel=nivel, origen=origen, momento_ingesta=momento_ingesta,
    )
    return JsonResponse({'ok': True})

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from clientes.models import Cliente

from .models import RegistroDisponibilidad


@require_POST
def registrar(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    nivel = request.POST.get('nivel')
    origen = request.POST.get('origen', '')

    if nivel not in dict(RegistroDisponibilidad.NIVEL_CHOICES):
        return HttpResponseBadRequest('nivel inválido')

    RegistroDisponibilidad.objects.create(cliente=cliente, nivel=nivel, origen=origen)
    return JsonResponse({'ok': True})

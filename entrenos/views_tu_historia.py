"""Tu historia en el gym (14-nov-2026) · panel provisional tipo resumen anual."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from clientes.views import _obtener_cliente_autorizado
from entrenos.services.tu_historia_service import calcular_historia


@login_required
def tu_historia(request, cliente_id):
    cliente = _obtener_cliente_autorizado(request, cliente_id)
    return render(request, 'entrenos/tu_historia.html', {
        'cliente': cliente,
        'h': calcular_historia(cliente),
    })

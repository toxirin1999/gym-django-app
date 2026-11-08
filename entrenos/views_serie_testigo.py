"""Serie testigo: registrar la del día (8-nov-2026). Vive aparte de views.py."""

import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from clientes.models import Cliente
from entrenos.services import serie_testigo_service as st


@login_required
@require_POST
def registrar_serie_testigo(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)
    try:
        datos = json.loads(request.body or '{}')
    except ValueError:
        datos = request.POST
    try:
        fecha = datetime.strptime(datos.get('fecha') or '', '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'ok': False, 'msg': 'Fecha no válida.'}, status=400)
    try:
        serie = st.registrar(cliente, fecha, datos.get('reps'), datos.get('quedaban'))
    except (TypeError, ValueError) as exc:
        return JsonResponse({'ok': False, 'msg': str(exc) or 'Datos no válidos.'}, status=400)
    return JsonResponse({'ok': True, 'msg': st.frase_serie(serie, st.resumen(cliente, hasta=fecha))})

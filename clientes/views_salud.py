"""Check-in automático desde la app Salud del iPhone (Health Auto Export)."""

import json

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from clientes.models import Cliente
from clientes.salud_iphone_service import guardar_checkin_iphone


def _token_de(request):
    """Cabecera ``Authorization: Bearer <token>`` (o ``X-Api-Token``)."""
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return (request.headers.get('X-Api-Token') or '').strip()


@csrf_exempt
@require_POST
def api_salud_iphone(request):
    token = _token_de(request)
    if not token:
        return JsonResponse({'ok': False, 'error': 'Falta la cabecera Authorization: Bearer <token>.'}, status=401)
    cliente = Cliente.objects.filter(api_token=token).first()
    if cliente is None:
        return JsonResponse({'ok': False, 'error': 'Token no válido.'}, status=401)
    try:
        payload = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'El cuerpo no es JSON.'}, status=400)
    guardado = guardar_checkin_iphone(cliente, payload)
    return JsonResponse({'ok': True, 'dias': guardado})


@login_required
def salud_iphone(request):
    """Cómo configurar Health Auto Export y qué ha llegado por última vez."""
    cliente = get_object_or_404(Cliente, user=request.user)
    return render(request, 'clientes/salud_iphone.html', {
        'cliente': cliente,
        'token': cliente.get_or_create_api_token(),
        'endpoint': request.build_absolute_uri(reverse('clientes:api_salud_iphone')),
        'ultimo': cache.get(f'salud_iphone_ultimo_{cliente.id}'),
    })

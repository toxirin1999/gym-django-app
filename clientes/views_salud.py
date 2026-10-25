"""Check-in automático desde la app Salud del iPhone (Atajo de iOS o Health Auto Export)."""

import json
import logging
import re

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from clientes.models import Cliente
from clientes.salud_iphone_service import guardar_checkin_iphone

logger = logging.getLogger(__name__)


_BEARER = re.compile(r'^\s*bearer\s+', re.IGNORECASE)
_HEX = re.compile(r'[0-9a-f]{64}')


def _limpiar_token(texto):
    """'Bearer <token>' (con espacio, salto de línea o guion de corte) o el token solo → token."""
    texto = _BEARER.sub('', str(texto or ''))
    compacto = re.sub(r'[\s\-\u00ad]', '', texto).lower()
    m = _HEX.search(compacto)
    return m.group(0) if m else compacto


def _token_de(request, payload=None):
    """Cabecera ``Authorization``, ``X-Api-Token`` o, si iOS quita la cabecera, ``token`` en el JSON."""
    for valor in (request.headers.get('Authorization'), request.headers.get('X-Api-Token'),
                  (payload or {}).get('token') if isinstance(payload, dict) else None):
        token = _limpiar_token(valor)
        if token:
            return token
    return ''


@csrf_exempt
@require_POST
def api_salud_iphone(request):
    try:
        payload = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        payload = None
    token = _token_de(request, payload)
    if not token:
        # 24-oct-2026: qué llegó (sin valores) para no ir a ciegas.
        logger.warning('salud-iphone 401 sin token: cabeceras=%s claves_json=%s',
                       sorted(request.headers.keys()),
                       sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
        return JsonResponse({'ok': False, 'error': 'Falta la cabecera Authorization: Bearer <token>.'}, status=401)
    cliente = Cliente.objects.filter(api_token=token).first()
    if cliente is None:
        logger.warning('salud-iphone 401 token no válido (longitud %s)', len(token))
        return JsonResponse({'ok': False, 'error': 'Token no válido.'}, status=401)
    if payload is None:
        return JsonResponse({'ok': False, 'error': 'El cuerpo no es JSON.'}, status=400)
    guardado = guardar_checkin_iphone(cliente, payload)
    if not guardado:
        sin_token = {k: v for k, v in payload.items() if k != 'token'} if isinstance(payload, dict) else payload
        logger.warning('salud-iphone: llegó sin datos útiles: %s', str(sin_token)[:500])
    return JsonResponse({'ok': True, 'dias': guardado})


def _con_sueno_texto(fila):
    """7.85 → '7 h 51' para la página."""
    if fila.horas_sueno:
        from entrenos.services.recuperacion_service import horas_texto
        fila.sueno_texto = horas_texto(fila.horas_sueno)
    return fila


@login_required
def salud_iphone(request):
    """Cómo configurar el Atajo y qué ha llegado por última vez."""
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from clientes.models import BitacoraDiaria

    cliente = get_object_or_404(Cliente, user=request.user)
    # 24-oct-2026: se lee de la base de datos, no de la caché (en producción la
    # caché es por proceso y se borra al recargar: decía "no ha llegado nada"
    # aunque los datos estuvieran guardados).
    hoy = timezone.localdate()
    recibidos = (
        BitacoraDiaria.objects.filter(cliente=cliente, fecha__gte=hoy - timedelta(days=6))
        .filter(Q(hrv_ms__isnull=False) | Q(fc_reposo__isnull=False) | Q(horas_sueno__isnull=False))
        .order_by('-fecha', '-pk')
    )
    from entrenos.services.estado_carga_service import parada_en
    return render(request, 'clientes/salud_iphone.html', {
        'parada': parada_en(cliente, hoy),
        'cliente': cliente,
        'token': cliente.get_or_create_api_token(),
        'endpoint': request.build_absolute_uri(reverse('clientes:api_salud_iphone')),
        'recibidos': [_con_sueno_texto(b) for b in recibidos],
    })


@login_required
@require_POST
def parada_declarada(request):
    """25-oct-2026: «estoy enfermo» / «estoy de parada» / «ya he vuelto»."""
    from django.shortcuts import redirect
    from django.utils import timezone

    from entrenos.services.estado_carga_service import declarar_parada, terminar_parada

    cliente = get_object_or_404(Cliente, user=request.user)
    hoy = timezone.localdate()
    accion = request.POST.get('accion', '')
    if accion == 'terminar':
        terminar_parada(cliente, hoy)
    elif accion in ('enfermo', 'parada'):
        declarar_parada(cliente, accion, hoy)
    return redirect('clientes:salud_iphone')

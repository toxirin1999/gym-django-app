"""Errores del servidor de los últimos días (8-nov-2026). Vive aparte de views.py."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.errores import errores_recientes, resumen_errores


@login_required
def errores_servidor(request):
    dias = 30
    return render(request, 'clientes/errores_servidor.html', {
        'dias': dias,
        'errores': errores_recientes(dias)[:100],
        'resumen': resumen_errores(dias),
    })

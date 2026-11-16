"""Agenda de pendientes con fecha (16-nov-2026)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from core import pendientes


@login_required
def agenda_pendientes(request):
    hoy = timezone.localdate()
    tareas = pendientes.cargar()
    return render(request, 'clientes/pendientes.html', {
        'hoy': hoy,
        'grupos': pendientes.agrupar(tareas, hoy),
        'resumen': pendientes.resumen(tareas, hoy),
    })

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services
from .forms import IniciarEpisodioForm, RegistrarSesionForm, RegistroDiarioForm
from .models import EpisodioRehab


def placeholder(request):
    return HttpResponse("Rehab: en construcción.")


@login_required
def iniciar_episodio_view(request):
    cliente = request.user.cliente_perfil
    if request.method == 'POST':
        form = IniciarEpisodioForm(request.POST)
        if form.is_valid():
            try:
                services.iniciar_episodio(
                    cliente=cliente,
                    protocolo=form.cleaned_data['protocolo'],
                    lateralidad=form.cleaned_data['lateralidad'],
                    fecha_inicio=form.cleaned_data['fecha_inicio'],
                    dolor_basal_inicial=form.cleaned_data['dolor_basal_inicial'],
                    notas=form.cleaned_data['notas'],
                )
            except ValidationError as e:
                form.add_error(None, e)
            else:
                messages.success(request, 'Episodio de rehabilitación iniciado.')
                return redirect('rehab:placeholder')
    else:
        form = IniciarEpisodioForm()
    return render(request, 'rehab/iniciar_episodio.html', {'form': form})


@login_required
def registrar_dolor_view(request, episodio_id):
    cliente = request.user.cliente_perfil
    episodio = get_object_or_404(EpisodioRehab, pk=episodio_id, cliente=cliente)
    if request.method == 'POST':
        form = RegistroDiarioForm(request.POST)
        if form.is_valid():
            services.registrar_dolor_diario(
                episodio=episodio,
                fecha=form.cleaned_data['fecha'],
                dolor_manana=form.cleaned_data['dolor_manana'],
                rigidez_manana=form.cleaned_data['rigidez_manana'],
                notas=form.cleaned_data['notas'],
            )
            messages.success(request, 'Registro diario guardado.')
            return redirect('rehab:placeholder')
    else:
        form = RegistroDiarioForm()
    return render(request, 'rehab/registrar_dolor.html', {'form': form, 'episodio': episodio})


@login_required
def registrar_sesion_view(request, episodio_id):
    cliente = request.user.cliente_perfil
    episodio = get_object_or_404(EpisodioRehab, pk=episodio_id, cliente=cliente)
    prescripciones = (
        episodio.fase_actual.prescripciones.select_related('ejercicio').all()
        if episodio.fase_actual else []
    )
    if request.method == 'POST':
        form = RegistrarSesionForm(request.POST)
        if form.is_valid():
            ejercicios_data = []
            for prescripcion in prescripciones:
                prefix = f'presc_{prescripcion.id}_'
                if f'{prefix}series_completadas' not in request.POST:
                    continue
                carga_kg = request.POST.get(f'{prefix}carga_kg') or None
                dolor_ejercicio = request.POST.get(f'{prefix}dolor_ejercicio') or None
                ejercicios_data.append({
                    'prescripcion_id': prescripcion.id,
                    'series_completadas': int(request.POST.get(f'{prefix}series_completadas') or 0),
                    'carga_kg': carga_kg,
                    'dolor_ejercicio': int(dolor_ejercicio) if dolor_ejercicio else None,
                    'completado': f'{prefix}completado' in request.POST,
                })
            services.registrar_sesion(
                episodio=episodio,
                fecha=form.cleaned_data['fecha'],
                estado=form.cleaned_data['estado'],
                dolor_durante=form.cleaned_data['dolor_durante'],
                ejercicios_data=ejercicios_data,
                dolor_post_24h=form.cleaned_data['dolor_post_24h'],
                duracion_min=form.cleaned_data['duracion_min'],
                notas=form.cleaned_data['notas'],
            )
            messages.success(request, 'Sesión registrada.')
            return redirect('rehab:placeholder')
    else:
        form = RegistrarSesionForm()
    return render(request, 'rehab/registrar_sesion.html', {
        'form': form,
        'episodio': episodio,
        'prescripciones': prescripciones,
    })


@login_required
def proponer_avance_view(request):
    cliente = request.user.cliente_perfil
    episodio = (
        EpisodioRehab.objects.filter(cliente=cliente, estado='ACTIVO')
        .order_by('fecha_inicio')
        .first()
    )
    resultado = None
    if episodio is not None and episodio.fase_actual is not None:
        resultado = services.evaluar_elegibilidad_avance(episodio, timezone.localdate())
    return render(request, 'rehab/proponer_avance.html', {
        'episodio': episodio,
        'resultado': resultado,
    })


@login_required
def confirmar_avance_view(request, episodio_id):
    cliente = request.user.cliente_perfil
    episodio = get_object_or_404(EpisodioRehab, pk=episodio_id, cliente=cliente)
    if request.method == 'POST':
        forzado = request.POST.get('forzado') == 'on'
        try:
            services.confirmar_avance(episodio, timezone.localdate(), forzado=forzado)
        except ValidationError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, 'Fase avanzada correctamente.')
    return redirect('rehab:proponer_avance')

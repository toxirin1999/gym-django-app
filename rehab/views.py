from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services
from .forms import IniciarEpisodioForm, RegistrarSesionForm, RegistroDiarioForm
from .models import EpisodioRehab


@login_required
def hoy_view(request):
    cliente = request.user.cliente_perfil
    episodio = (
        EpisodioRehab.objects.filter(cliente=cliente, estado='ACTIVO')
        .order_by('fecha_inicio')
        .first()
    )
    if episodio is None:
        return render(request, 'rehab/hoy.html', {'episodio': None, 'prescripcion': None})

    fecha = timezone.localdate()
    prescripcion = services.prescripcion_de_hoy(cliente)
    estancamiento = None
    elegibilidad = None
    if episodio.fase_actual is not None:
        estancamiento = services.detectar_estancamiento(episodio, fecha)
        elegibilidad = services.evaluar_elegibilidad_avance(episodio, fecha)

    return render(request, 'rehab/hoy.html', {
        'episodio': episodio,
        'prescripcion': prescripcion,
        'estancamiento': estancamiento,
        'elegibilidad': elegibilidad,
    })


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
                return redirect('rehab:hoy')
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
            return redirect('rehab:hoy')
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
            return redirect('rehab:hoy')
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
def recorrido_view(request):
    cliente = request.user.cliente_perfil
    episodio = (
        EpisodioRehab.objects.filter(cliente=cliente, estado='ACTIVO')
        .order_by('fecha_inicio')
        .first()
    )
    if episodio is None:
        return render(request, 'rehab/recorrido.html', {'episodio': None, 'recorrido': None})

    recorrido = services.construir_recorrido(episodio)
    return render(request, 'rehab/recorrido.html', {
        'episodio': episodio,
        'recorrido': recorrido,
    })


_EVOLUCION_VIEWBOX_ANCHO = 600
_EVOLUCION_VIEWBOX_ALTO = 240
_EVOLUCION_MARGEN_IZQ = 30
_EVOLUCION_MARGEN_DER = 20
_EVOLUCION_MARGEN_SUP = 48
_EVOLUCION_MARGEN_INF = 20


def _coordenadas_evolucion(evolucion):
    puntos = evolucion['puntos']
    area_x0 = _EVOLUCION_MARGEN_IZQ
    area_x1 = _EVOLUCION_VIEWBOX_ANCHO - _EVOLUCION_MARGEN_DER
    area_y0 = _EVOLUCION_MARGEN_SUP
    area_y1 = _EVOLUCION_VIEWBOX_ALTO - _EVOLUCION_MARGEN_INF
    area_ancho = area_x1 - area_x0
    area_alto = area_y1 - area_y0

    n = len(puntos)
    # Eje X repartido por índice de punto, no por fecha proporcional: con datos
    # irregulares (días sin registro) una escala temporal real dejaría huecos
    # visuales confusos; el índice mantiene los puntos legibles y espaciados.
    def x_de_indice(i):
        if n <= 1:
            return area_x0 + area_ancho / 2
        return area_x0 + (area_ancho * i / (n - 1))

    def y_de_dolor(valor):
        return area_y1 - (valor / 10 * area_alto)

    puntos_manana = []
    puntos_durante = []
    circulos_manana = []
    circulos_durante = []
    for i, punto in enumerate(puntos):
        x = x_de_indice(i)
        if punto['dolor_manana'] is not None:
            y = y_de_dolor(punto['dolor_manana'])
            puntos_manana.append(f"{x:.1f},{y:.1f}")
            circulos_manana.append({'x': round(x, 1), 'y': round(y, 1)})
        if punto['dolor_durante'] is not None:
            y = y_de_dolor(punto['dolor_durante'])
            puntos_durante.append(f"{x:.1f},{y:.1f}")
            circulos_durante.append({'x': round(x, 1), 'y': round(y, 1)})

    # A media altura entre el techo del viewBox y el inicio de la cuadrícula:
    # deja hueco por encima de la fila de la etiqueta "10" del eje Y, que se
    # dibuja justo debajo de area_y0.
    evento_label_y = round(area_y0 / 2, 1)

    fechas_indice = {punto['fecha']: i for i, punto in enumerate(puntos)}
    eventos_x = []
    for evento in evolucion['eventos']:
        indice = fechas_indice.get(evento['fecha'])
        if indice is None:
            continue
        eventos_x.append({
            'x': round(x_de_indice(indice), 1),
            'label_y': evento_label_y,
            'direccion': evento['direccion'],
            'fase_nombre': evento['fase_nombre'],
        })

    lineas_grid = [
        {'y': round(y_de_dolor(v), 1), 'valor': v}
        for v in range(0, 11, 2)
    ]

    return {
        'viewbox': f'0 0 {_EVOLUCION_VIEWBOX_ANCHO} {_EVOLUCION_VIEWBOX_ALTO}',
        'area_x0': area_x0,
        'area_x1': area_x1,
        'area_y0': area_y0,
        'area_y1': area_y1,
        'polilinea_manana': ' '.join(puntos_manana),
        'polilinea_durante': ' '.join(puntos_durante),
        'circulos_manana': circulos_manana,
        'circulos_durante': circulos_durante,
        'eventos': eventos_x,
        'lineas_grid': lineas_grid,
    }


@login_required
def evolucion_view(request):
    cliente = request.user.cliente_perfil
    episodio = (
        EpisodioRehab.objects.filter(cliente=cliente, estado='ACTIVO')
        .order_by('fecha_inicio')
        .first()
    )
    if episodio is None:
        return render(request, 'rehab/evolucion.html', {'episodio': None, 'evolucion': None, 'grafico': None})

    evolucion = services.construir_evolucion(episodio)
    grafico = _coordenadas_evolucion(evolucion) if evolucion['puntos'] else None
    return render(request, 'rehab/evolucion.html', {
        'episodio': episodio,
        'evolucion': evolucion,
        'grafico': grafico,
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


@login_required
def confirmar_alta_view(request, episodio_id):
    """Confirmación humana de retorno sin restricciones; no es un alta médica."""
    from hyrox.models import UserInjury
    from .services.alta_service import confirmar_alta_rehab

    cliente = request.user.cliente_perfil
    episodio = get_object_or_404(
        EpisodioRehab.objects.select_related('lesion_hyrox', 'protocolo'),
        pk=episodio_id,
        cliente=cliente,
    )
    lesiones = UserInjury.objects.filter(
        cliente=cliente, activa=True
    ).order_by('-fecha_inicio', '-pk')
    if request.method == 'POST':
        try:
            confirmar_alta_rehab(
                episodio=episodio,
                actor=request.user,
                confirmacion_usuario=request.POST.get('confirmacion_usuario') == 'on',
                nota_evidencia=request.POST.get('nota_evidencia', ''),
                lesion_hyrox_id=request.POST.get('lesion_hyrox_id') or None,
            )
        except (ValidationError, ValueError) as exc:
            return render(request, 'rehab/confirmar_alta.html', {
                'episodio': episodio,
                'lesiones': lesiones,
                'error': '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc),
            }, status=400)
        messages.success(request, 'Episodio Rehab cerrado con tu confirmación.')
        return redirect('rehab:hoy')
    return render(request, 'rehab/confirmar_alta.html', {
        'episodio': episodio,
        'lesiones': lesiones,
    })

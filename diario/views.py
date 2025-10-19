from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta, date
import json
from .insights_engine import generar_insights_semanales
import calendar  # <-- ¡AÑADE ESTA LÍNEA!
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from .forms import PersonaImportanteForm, InteraccionForm

# Importar los modelos (asumiendo que están en models.py)
from .models import (
    ProsocheMes, ProsocheSemana, ProsocheDiario, ProsocheHabito, ProsocheHabitoDia,
    AreaVida, Eudaimonia, TrimestreEudaimonia,
    EjercicioArete, Gnosis, EntrenamientoSemanal,
    SeguimientoVires, EventoKairos, PlanificacionDiaria, PersonaImportante, Interaccion, RevisionSemanal
)


# ========================================
# VISTA PRINCIPAL DEL DIARIO
# ========================================

@login_required
def dashboard_diario(request):
    """
    Dashboard principal del diario con una vista conectada y contextual del día.
    VERSIÓN FINAL UNIFICADA.
    """
    hoy = timezone.now().date()
    hora_actual = timezone.now().hour

    # --- MÓDULO PROSOCHE ---
    entrada_hoy = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha=hoy
    ).first()

    # --- MÓDULO VIRES ---
    seguimiento_vires_hoy = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha=hoy
    ).first()

    # --- MÓDULO KAIROS ---
    eventos_hoy = EventoKairos.objects.filter(
        usuario=request.user,
        fecha_inicio__date=hoy
    ).order_by('fecha_inicio')

    # --- MÓDULO EUDAIMONIA ---
    area_prioritaria = Eudaimonia.objects.filter(
        usuario=request.user,
        prioridad='alta'
    ).order_by('-puntuacion').first()

    # --- MÓDULO ARETÉ ---
    proximo_arete = EjercicioArete.objects.filter(
        usuario=request.user,
        estado='sin_completar'
    ).order_by('numero_orden').first()

    # --- MÓDULO SIMBIOSIS (NUEVO) ---
    # Sugerencia: ¿Hay alguna relación que necesite atención? (Salud < 3)
    relacion_a_mejorar = PersonaImportante.objects.filter(
        usuario=request.user,
        salud_relacion__lt=3
    ).order_by('salud_relacion').first()

    # Sugerencia: ¿Hay alguna interacción reciente sin reflexión?
    interaccion_sin_reflexion = Interaccion.objects.filter(
        usuario=request.user,
        aprendizaje__exact=''  # Busca interacciones donde el campo 'aprendizaje' esté vacío
    ).order_by('-fecha').first()

    # --- MÓDULO ORÁCULO ---
    insights = generar_insights_semanales(request.user)
    insight_principal = insights[0] if insights else None

    context = {
        'hoy': hoy,
        'hora_actual': hora_actual,
        'entrada_hoy': entrada_hoy,
        'seguimiento_vires_hoy': seguimiento_vires_hoy,
        'eventos_hoy': eventos_hoy,
        'area_prioritaria': area_prioritaria,
        'proximo_arete': proximo_arete,
        'insight_principal': insight_principal,
        'relacion_a_mejorar': relacion_a_mejorar,  # <-- Nuevo contexto
        'interaccion_sin_reflexion': interaccion_sin_reflexion,  # <-- Nuevo contexto
    }
    return render(request, 'diario/dashboard.html', context)


from .models import ProsocheMes, ProsocheSemana, ProsocheDiario, ProsocheHabito, ProsocheHabitoDia


@login_required
def prosoche_entrada_form(request, entrada_id=None):
    # ... (el código de esta vista que ya tienes es correcto)
    # ... (no lo modifico, solo confirmo que debe estar aquí)
    entrada_existente = None
    if entrada_id:
        entrada_existente = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)
        prosoche_mes = entrada_existente.prosoche_mes
        fecha = entrada_existente.fecha
    else:
        fecha = timezone.now().date()
        mes_nombre = fecha.strftime('%B')
        año = fecha.year
        prosoche_mes, _ = ProsocheMes.objects.get_or_create(
            usuario=request.user, mes=mes_nombre, año=año
        )

    if request.method == 'POST':
        try:
            data = {
                'etiquetas': request.POST.get('etiquetas', ''),
                'estado_animo': int(request.POST.get('estado_animo', 3)),
                'persona_quiero_ser': request.POST.get('persona_quiero_ser', ''),
                'gratitud_1': request.POST.get('gratitud_1', ''),
                'gratitud_2': request.POST.get('gratitud_2', ''),
                'gratitud_3': request.POST.get('gratitud_3', ''),
                'gratitud_4': request.POST.get('gratitud_4', ''),
                'gratitud_5': request.POST.get('gratitud_5', ''),
                'podcast_libro_dia': request.POST.get('podcast_libro_dia', ''),
                'felicidad': request.POST.get('felicidad', ''),
                'que_ha_ido_bien': request.POST.get('que_ha_ido_bien', ''),
                'que_puedo_mejorar': request.POST.get('que_puedo_mejorar', ''),
                'reflexiones_dia': request.POST.get('reflexiones_dia', ''),
            }
            tareas_json = request.POST.get('tareas_dia', '[]')
            data['tareas_dia'] = json.loads(tareas_json)

            if entrada_existente:
                for key, value in data.items():
                    setattr(entrada_existente, key, value)
                entrada_existente.save()
                messages.success(request, 'Entrada actualizada correctamente.')
            else:
                data['prosoche_mes'] = prosoche_mes
                data['fecha'] = fecha
                ProsocheDiario.objects.create(**data)
                messages.success(request, 'Nueva entrada creada correctamente.')

            return redirect('prosoche_dashboard')

        except Exception as e:
            messages.error(request, f'Error al guardar la entrada: {str(e)}')

    form_data = {}
    if entrada_existente:
        form_data = {
            'etiquetas': entrada_existente.etiquetas,
            'estado_animo': entrada_existente.estado_animo,
            'persona_quiero_ser': entrada_existente.persona_quiero_ser,
            'tareas_dia': entrada_existente.tareas_dia,
            'gratitud_1': entrada_existente.gratitud_1,
            'gratitud_2': entrada_existente.gratitud_2,
            'gratitud_3': entrada_existente.gratitud_3,
            'gratitud_4': entrada_existente.gratitud_4,
            'gratitud_5': entrada_existente.gratitud_5,
            'podcast_libro_dia': entrada_existente.podcast_libro_dia,
            'felicidad': entrada_existente.felicidad,
            'que_ha_ido_bien': entrada_existente.que_ha_ido_bien,
            'que_puedo_mejorar': entrada_existente.que_puedo_mejorar,
            'reflexiones_dia': entrada_existente.reflexiones_dia,
        }

    context = {
        'fecha': fecha,
        'prosoche_mes': prosoche_mes,
        'form': type('Form', (), form_data)(),
        'entrada_existente': entrada_existente,
        'es_edicion': entrada_existente is not None,
    }

    return render(request, 'diario/prosoche_entrada_form.html', context)


@login_required
@require_http_methods(["POST"])  # Asegura que solo se pueda acceder por método POST
def prosoche_eliminar_entrada(request, entrada_id):
    """
    Elimina una entrada del diario.
    """
    # Busca la entrada asegurándose de que pertenece al usuario logueado
    entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)

    try:
        entrada.delete()
        messages.success(request, 'La entrada del diario ha sido eliminada correctamente.')
    except Exception as e:
        messages.error(request, f'Ocurrió un error al eliminar la entrada: {e}')

    return redirect('prosoche_dashboard')


@login_required
@require_http_methods(["POST"])
def prosoche_auto_save_entrada(request):
    """Vista para auto-guardado de entrada (AJAX)"""
    try:
        data = json.loads(request.body)
        fecha_str = data.get('fecha')
        campo = data.get('campo')
        valor = data.get('valor')

        if not all([fecha_str, campo]):
            return JsonResponse({'success': False, 'error': 'Datos incompletos'})

        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # Obtener o crear el mes de Prosoche
        mes_nombre = fecha.strftime('%B')
        año = fecha.year

        prosoche_mes, created = ProsocheMes.objects.get_or_create(
            usuario=request.user,
            mes=mes_nombre,
            año=año
        )

        # Obtener o crear la entrada
        entrada, created = ProsocheDiario.objects.get_or_create(
            prosoche_mes=prosoche_mes,
            fecha=fecha,
            defaults={'estado_animo': 3}
        )

        # Actualizar el campo específico
        if hasattr(entrada, campo):
            setattr(entrada, campo, valor)
            entrada.save()

            return JsonResponse({
                'success': True,
                'message': f'Campo {campo} guardado automáticamente'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Campo {campo} no válido'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def prosoche_entrada_detalle(request, entrada_id):
    """Vista para mostrar detalle de una entrada específica"""
    entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)

    context = {
        'entrada': entrada,
        'prosoche_mes': entrada.prosoche_mes,
        'tareas_completadas': entrada.get_tareas_completadas(),
        'total_tareas': entrada.get_total_tareas(),
        'gratitud_items': entrada.get_gratitud_items(),
        'porcentaje_completado': entrada.get_porcentaje_completado(),
    }

    return render(request, 'diario/prosoche_entrada_detalle.html', context)


@login_required
@require_http_methods(["POST"])
def prosoche_toggle_tarea(request):
    """Vista para marcar/desmarcar tarea como completada (AJAX)"""
    try:
        data = json.loads(request.body)
        entrada_id = data.get('entrada_id')
        tarea_index = data.get('tarea_index')
        completada = data.get('completada', False)

        entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)

        if 0 <= tarea_index < len(entrada.tareas_dia):
            entrada.tareas_dia[tarea_index]['completada'] = completada
            entrada.save()

            return JsonResponse({
                'success': True,
                'tareas_completadas': entrada.get_tareas_completadas(),
                'total_tareas': entrada.get_total_tareas()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Índice de tarea no válido'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def prosoche_entradas_mes(request, mes, año):
    """Vista para mostrar todas las entradas de un mes específico"""
    try:
        prosoche_mes = get_object_or_404(
            ProsocheMes,
            usuario=request.user,
            mes=mes,
            año=año
        )

        entradas = ProsocheDiario.objects.filter(
            prosoche_mes=prosoche_mes
        ).order_by('-fecha')

        context = {
            'prosoche_mes': prosoche_mes,
            'entradas': entradas,
            'mes': mes,
            'año': año,
        }

        return render(request, 'diario/prosoche_entradas_mes.html', context)

    except ProsocheMes.DoesNotExist:
        messages.error(request, f'No se encontraron datos para {mes} {año}')
        return redirect('prosoche_dashboard')


# Template filter personalizado para acceder a campos dinámicos
from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """Filtro para acceder a valores dinámicos en templates"""
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    return dictionary.get(key, '')


@register.filter
def add(value, arg):
    """Filtro para sumar valores"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value


@login_required
def eudaimonia_dashboard(request):
    """Dashboard de la sección Eudaimonia."""
    areas_usuario = Eudaimonia.objects.filter(usuario=request.user).select_related('area')

    # Organizar por prioridad
    areas_alta = areas_usuario.filter(prioridad='alta')
    areas_media = areas_usuario.filter(prioridad='media')
    areas_baja = areas_usuario.filter(prioridad='baja')

    context = {
        'areas_alta': areas_alta,
        'areas_media': areas_media,
        'areas_baja': areas_baja,
        'total_areas': areas_usuario.count()
    }
    return render(request, 'diario/eudaimonia_dashboard.html', context)


@login_required
def eudaimonia_area_detalle(request, area_id):
    """Detalle de un área de vida específica."""
    eudaimonia = get_object_or_404(Eudaimonia, id=area_id, usuario=request.user)
    trimestres = TrimestreEudaimonia.objects.filter(eudaimonia=eudaimonia).order_by('-año', '-trimestre')

    context = {
        'eudaimonia': eudaimonia,
        'trimestres': trimestres
    }
    return render(request, 'diario/eudaimonia_detalle.html', context)


@login_required
def eudaimonia_actualizar(request):
    """Actualizar puntuación y prioridad de un área de vida."""
    if request.method == 'POST':
        data = json.loads(request.body)
        eudaimonia = get_object_or_404(Eudaimonia, id=data['area_id'], usuario=request.user)

        if 'puntuacion' in data:
            eudaimonia.puntuacion = data['puntuacion']
        if 'prioridad' in data:
            eudaimonia.prioridad = data['prioridad']

        eudaimonia.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ========================================
# ARETÉ - DESARROLLO PERSONAL
# ========================================

# diario/views.py

# REEMPLAZA tu vista arete_dashboard con esta versión completa

# REEMPLAZA tu vista arete_dashboard con esta versión final y completa

@login_required
def arete_dashboard(request):
    """Dashboard de la sección Areté."""
    # Obtener todos los ejercicios del usuario para los cálculos totales
    todos_los_ejercicios = EjercicioArete.objects.filter(usuario=request.user).order_by('numero_orden')
    total_ejercicios = todos_los_ejercicios.count()
    completados = todos_los_ejercicios.filter(estado='completado').count()
    a_repetir_count = todos_los_ejercicios.filter(estado='a_repetir').count()

    # Calcular el número de ejercicios pendientes
    pendientes = total_ejercicios - completados - a_repetir_count

    # Calcular el ángulo para el círculo de progreso en grados
    progreso_deg = 0
    if total_ejercicios > 0:
        progreso_deg = int((completados * 360) / total_ejercicios)

    # Calcular el porcentaje de completitud
    porcentaje_completado = 0
    if total_ejercicios > 0:
        porcentaje_completado = int((completados * 100) / total_ejercicios)

    # --- INICIO DE LA NUEVA MODIFICACIÓN ---
    # Encontrar el próximo ejercicio pendiente
    proximo_ejercicio = todos_los_ejercicios.filter(estado='sin_completar').first()
    # --- FIN DE LA NUEVA MODIFICACIÓN ---

    # Aplicar filtros para la lista que se muestra en la página
    ejercicios_filtrados = todos_los_ejercicios
    filtro = request.GET.get('filtro', 'todos')
    if filtro == 'completados':
        ejercicios_filtrados = ejercicios_filtrados.filter(estado='completado')
    elif filtro == 'a_repetir':
        ejercicios_filtrados = ejercicios_filtrados.filter(estado='a_repetir')
    elif filtro == 'sin_completar':
        ejercicios_filtrados = ejercicios_filtrados.filter(estado='sin_completar')

    context = {
        'ejercicios': ejercicios_filtrados,
        'filtro_actual': filtro,
        'total_ejercicios': total_ejercicios,
        'completados': completados,
        'pendientes': pendientes,
        'a_repetir_count': a_repetir_count,
        'progreso_deg': progreso_deg,
        'porcentaje_completado': porcentaje_completado,
        'proximo_ejercicio': proximo_ejercicio,  # <-- Pasamos el próximo ejercicio a la plantilla
    }
    return render(request, 'diario/arete_dashboard.html', context)


@login_required
def arete_ejercicio_actualizar(request, ejercicio_id):
    """Actualizar estado de un ejercicio Areté."""
    ejercicio = get_object_or_404(EjercicioArete, id=ejercicio_id, usuario=request.user)

    if request.method == 'POST':
        data = request.POST
        ejercicio.estado = data.get('estado')
        if data.get('reflexiones'):
            ejercicio.reflexiones = data.get('reflexiones')

        if ejercicio.estado == 'completado' and not ejercicio.fecha_completado:
            ejercicio.fecha_completado = timezone.now()

        ejercicio.save()
        messages.success(request, 'Ejercicio actualizado correctamente.')
        return redirect('arete_dashboard')

    context = {'ejercicio': ejercicio}
    return render(request, 'diario/arete_ejercicio_detalle.html', context)


# ========================================
# GNOSIS - GESTIÓN DE CONOCIMIENTO
# ========================================

@login_required
def gnosis_dashboard(request):
    """Dashboard de la sección Gnosis."""
    contenido = Gnosis.objects.filter(usuario=request.user)

    # Filtros
    categoria = request.GET.get('categoria', 'todos')
    if categoria != 'todos':
        contenido = contenido.filter(categoria=categoria)

    # Búsqueda
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        contenido = contenido.filter(
            Q(titulo__icontains=busqueda) |
            Q(autor__icontains=busqueda) |
            Q(tematica__icontains=busqueda)
        )

    context = {
        'contenido': contenido.order_by('-fecha_creacion'),
        'categoria_actual': categoria,
        'busqueda_actual': busqueda,
        'categorias': Gnosis.CATEGORIA_CHOICES,
        'total_contenido': Gnosis.objects.filter(usuario=request.user).count()
    }
    return render(request, 'diario/gnosis_dashboard.html', context)


@login_required
def gnosis_crear(request):
    """Crear nuevo contenido en Gnosis."""
    if request.method == 'POST':
        data = request.POST
        Gnosis.objects.create(
            usuario=request.user,
            titulo=data.get('titulo'),
            categoria=data.get('categoria'),
            estado=data.get('estado', 'no_empezado'),
            tematica=data.get('tematica', ''),
            autor=data.get('autor', ''),
            url=data.get('url', ''),
            notas=data.get('notas', '')
        )
        messages.success(request, 'Contenido agregado correctamente.')
        return redirect('gnosis_dashboard')

    context = {
        'categorias': Gnosis.CATEGORIA_CHOICES,
        'estados': Gnosis.ESTADO_CHOICES,
        'puntuaciones': Gnosis.PUNTUACION_CHOICES
    }
    return render(request, 'diario/gnosis_crear.html', context)


# ========================================
# VIRES - SALUD Y DEPORTE
# ========================================

@login_required
def vires_dashboard(request):
    """Dashboard de la sección Vires."""
    fecha_hoy = timezone.now().date()
    seguimiento_hoy = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha=fecha_hoy
    ).first()

    # Entrenamientos de la semana actual
    inicio_semana = fecha_hoy - timedelta(days=fecha_hoy.weekday())
    entrenamientos_semana = EntrenamientoSemanal.objects.filter(
        usuario=request.user,
        semana_inicio=inicio_semana
    )

    # Últimos seguimientos
    seguimientos_recientes = SeguimientoVires.objects.filter(
        usuario=request.user
    ).order_by('-fecha')[:7]

    context = {
        'seguimiento_hoy': seguimiento_hoy,
        'entrenamientos_semana': entrenamientos_semana,
        'seguimientos_recientes': seguimientos_recientes,
        'fecha_hoy': fecha_hoy
    }
    return render(request, 'diario/vires_dashboard.html', context)


# diario/views.py

@login_required
def vires_seguimiento_crear(request):
    """Crear o actualizar seguimiento diario de Vires."""
    if request.method == 'POST':
        data = request.POST
        fecha_str = data.get('fecha', timezone.now().date())
        # Convertir a objeto date si es una cadena
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if isinstance(fecha_str, str) else fecha_str

        # --- Diccionario con los datos a guardar/actualizar ---
        # Usamos .get() con un valor por defecto de None para manejar campos vacíos
        defaults = {
            'peso': data.get('peso') or None,
            'grasa_corporal': data.get('grasa_corporal') or None,
            'masa_muscular': data.get('masa_muscular') or None,
            'horas_sueno': data.get('horas_sueno') or None,
            'calidad_sueno': data.get('calidad_sueno') or None,
            'nivel_energia': data.get('nivel_energia') or None,
            'nivel_estres': data.get('nivel_estres') or None,
            'pasos': data.get('pasos') or None,
            'entrenamiento_realizado': data.get('entrenamiento_realizado') == 'on',
            'alimentacion_saludable': data.get('alimentacion_saludable') == 'on',
            'hidratacion_adecuada': data.get('hidratacion_adecuada') == 'on',
            'descanso_suficiente': data.get('descanso_suficiente') == 'on',
            'notas': data.get('notas', '')
        }

        # get_or_create es más limpio para este caso de uso
        seguimiento, created = SeguimientoVires.objects.update_or_create(
            usuario=request.user,
            fecha=fecha,
            defaults=defaults
        )

        if created:
            messages.success(request, 'Seguimiento guardado correctamente.')
        else:
            messages.success(request, 'Seguimiento actualizado correctamente.')

        return redirect('diario:vires_dashboard')

    # Lógica para el método GET
    fecha_hoy = timezone.now().date()
    seguimiento_existente = SeguimientoVires.objects.filter(usuario=request.user, fecha=fecha_hoy).first()

    context = {
        'fecha_hoy': fecha_hoy,
        'seguimiento': seguimiento_existente
    }
    return render(request, 'diario/vires_seguimiento_form.html', context)


# ========================================
# KAIROS - CALENDARIO Y EVENTOS
# ========================================

@login_required
def kairos_dashboard(request):
    """Dashboard de la sección Kairos - Calendario."""
    fecha_actual = timezone.now().date()
    mes_actual = request.GET.get('mes', fecha_actual.month)
    año_actual = request.GET.get('año', fecha_actual.year)

    # Eventos del mes
    eventos_mes = EventoKairos.objects.filter(
        usuario=request.user,
        fecha_inicio__month=mes_actual,
        fecha_inicio__year=año_actual
    ).order_by('fecha_inicio')

    # Eventos de hoy
    eventos_hoy = EventoKairos.objects.filter(
        usuario=request.user,
        fecha_inicio__date=fecha_actual
    ).order_by('fecha_inicio')

    context = {
        'eventos_mes': eventos_mes,
        'eventos_hoy': eventos_hoy,
        'mes_actual': int(mes_actual),
        'año_actual': int(año_actual),
        'fecha_actual': fecha_actual
    }
    return render(request, 'diario/kairos_dashboard.html', context)


@login_required
def kairos_evento_crear(request):
    """Crear nuevo evento en Kairos."""
    if request.method == 'POST':
        data = request.POST
        EventoKairos.objects.create(
            usuario=request.user,
            titulo=data.get('titulo'),
            descripcion=data.get('descripcion', ''),
            tipo=data.get('tipo', 'personal'),
            fecha_inicio=data.get('fecha_inicio'),
            fecha_fin=data.get('fecha_fin') if data.get('fecha_fin') else None,
            todo_el_dia=data.get('todo_el_dia') == 'on',
            recordatorio=data.get('recordatorio') == 'on',
            color=data.get('color', '#00ffff')
        )
        messages.success(request, 'Evento creado correctamente.')
        return redirect('kairos_dashboard')

    context = {
        'tipos_evento': EventoKairos.TIPO_CHOICES
    }
    return render(request, 'diario/kairos_evento_form.html', context)


@login_required
def kairos_eventos_api(request):
    """API para obtener eventos en formato JSON para el calendario."""
    eventos = EventoKairos.objects.filter(usuario=request.user)

    eventos_json = []
    for evento in eventos:
        eventos_json.append({
            'id': evento.id,
            'title': evento.titulo,
            'start': evento.fecha_inicio.isoformat(),
            'end': evento.fecha_fin.isoformat() if evento.fecha_fin else None,
            'color': evento.color,
            'allDay': evento.todo_el_dia,
            'description': evento.descripcion
        })

    return JsonResponse(eventos_json, safe=False)


# Pega esto en la sección PROSOCHE de tu views.py

@login_required
def habito_prosoche_crear(request):
    """Crea un nuevo hábito para un diario Prosoche existente."""
    if request.method == 'POST':
        data = request.POST
        prosoche_id = data.get('prosoche_id')
        nombre_habito = data.get('nombre')
        descripcion_habito = data.get('descripcion', '')

        if not prosoche_id or not nombre_habito:
            messages.error(request, 'Faltan datos para crear el hábito.')
            return redirect('prosoche_dashboard')

        prosoche = get_object_or_404(Prosoche, id=prosoche_id, usuario=request.user)

        HabitoProsoche.objects.create(
            prosoche=prosoche,
            nombre=nombre_habito,
            descripcion=descripcion_habito
        )

        messages.success(request, f'Hábito "{nombre_habito}" creado correctamente.')
        return redirect('prosoche_dashboard')

    return redirect('prosoche_dashboard')


# Pega esto en la sección EUDAIMONIA de tu views.py
# diario/views.py

@login_required
def eudaimonia_crear_area(request):
    """
    Crea una nueva AreaVida y la asocia al perfil Eudaimonia del usuario.
    """
    if request.method == 'POST':
        data = request.POST
        nombre_area = data.get('nombre')
        puntuacion = data.get('puntuacion', 5)
        prioridad = data.get('prioridad', 'media')
        descripcion = data.get('descripcion', '')  # Capturamos la descripción

        # --- VALIDACIÓN CORREGIDA ---
        # Ahora comprobamos si se ha proporcionado un nombre
        if not nombre_area:
            messages.error(request, 'Debes proporcionar un nombre para el área de vida.')
            return redirect('diario:eudaimonia_dashboard')

        # --- LÓGICA DE CREACIÓN CORREGIDA ---
        # 1. Creamos o encontramos el objeto AreaVida (el modelo "maestro").
        #    Usamos get_or_create para evitar duplicados si un área "Salud" ya existe.
        area_vida, created = AreaVida.objects.get_or_create(
            nombre=nombre_area,
            defaults={'descripcion': descripcion}
        )
        # Si no fue creada, pero el usuario envió una nueva descripción, la actualizamos.
        if not created and descripcion:
            area_vida.descripcion = descripcion
            area_vida.save()

        # 2. Verificamos si el usuario YA tiene esta área en su perfil Eudaimonia.
        if Eudaimonia.objects.filter(usuario=request.user, area=area_vida).exists():
            messages.warning(request, f'Ya tienes el área "{area_vida.nombre}" en tu dashboard.')
            return redirect('diario:eudaimonia_dashboard')

        # 3. Creamos la conexión en Eudaimonia para este usuario.
        Eudaimonia.objects.create(
            usuario=request.user,
            area=area_vida,
            puntuacion=puntuacion,
            prioridad=prioridad
        )

        messages.success(request, f'Área "{area_vida.nombre}" añadida a tu dashboard.')
        return redirect('diario:eudaimonia_dashboard')

    # Si el método no es POST, simplemente redirigimos (el formulario está en la misma página)
    return redirect('diario:eudaimonia_dashboard')


@login_required
def prosoche_crear_habito(request):
    """Crear nuevo hábito"""
    if request.method == 'POST':
        prosoche_id = request.POST.get('prosoche_id')
        prosoche_mes = get_object_or_404(ProsocheMes, id=prosoche_id, usuario=request.user)

        nombre = request.POST.get('nombre')
        if nombre:
            habito, created = ProsocheHabito.objects.get_or_create(
                prosoche_mes=prosoche_mes,
                nombre=nombre,
                defaults={
                    'descripcion': request.POST.get('descripcion', ''),
                    'color': request.POST.get('color', '#00ffff')
                }
            )

            if created:
                messages.success(request, f'Hábito "{nombre}" creado correctamente.')
            else:
                messages.info(request, f'El hábito "{nombre}" ya existe.')

        return redirect('prosoche_dashboard')

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# diario/views.py

@login_required
def prosoche_dashboard(request):
    """Dashboard principal de Prosoche (VERSIÓN FUNCIONAL RESTAURADA)"""
    hoy = timezone.now()
    mes_actual_str = hoy.strftime('%B')
    año_actual = hoy.year

    # 1. Obtenemos o creamos el mes actual. Simple y directo.
    prosoche_mes, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_actual_str,
        año=año_actual
    )

    # 2. Obtenemos los datos relacionados de forma separada. Es más claro y evita los problemas del prefetch.
    semanas = ProsocheSemana.objects.filter(prosoche_mes=prosoche_mes).order_by('numero_semana')
    entradas_del_mes = ProsocheDiario.objects.filter(prosoche_mes=prosoche_mes).order_by('-fecha')
    habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

    # 3. Lógica para la semana actual (sin cambios, es correcta)
    numero_semana_actual = (hoy.day - 1) // 7 + 1
    semana_actual = semanas.filter(numero_semana=numero_semana_actual).first()

    # 4. Lógica para preparar los datos de hábitos (¡AQUÍ ESTÁ LA CLAVE!)
    # Esta es la lógica que funciona. La ejecutamos para cada hábito por separado.
    dias_mes = list(range(1, calendar.monthrange(año_actual, hoy.month)[1] + 1))
    habitos_con_dias = []
    for habito in habitos:
        # Obtenemos SOLO los días completados PARA ESTE HÁBITO.
        dias_completados_query = ProsocheHabitoDia.objects.filter(
            habito=habito,
            completado=True
        ).values_list('dia', flat=True)

        # Convertimos a un conjunto para búsquedas rápidas (eficiente).
        dias_completados_set = set(dias_completados_query)

        dias_para_plantilla = []
        for dia_num in dias_mes:
            dias_para_plantilla.append({
                'dia': dia_num,
                'completado': dia_num in dias_completados_set
            })

        porcentaje = round((len(dias_completados_set) / len(dias_mes)) * 100) if dias_mes else 0
        habitos_con_dias.append({'habito': habito, 'dias': dias_para_plantilla, 'porcentaje': porcentaje})

    # 5. Obtenemos los meses anteriores (sin cambios)
    meses_anteriores = ProsocheMes.objects.filter(
        usuario=request.user
    ).exclude(id=prosoche_mes.id).order_by('-año', '-mes')[:6]

    # 6. Construimos el contexto final
    context = {
        'prosoche_mes': prosoche_mes,
        'semanas': semanas,
        'semana_actual': semana_actual,
        'entradas_del_mes': entradas_del_mes,
        'habitos_con_dias': habitos_con_dias,
        'dias_mes': dias_mes,
        'meses_anteriores': meses_anteriores,
        'mes_actual': mes_actual_str,
        'año_actual': año_actual,
    }

    return render(request, 'diario/prosoche_dashboard.html', context)


@login_required
@require_http_methods(["POST"])  # Es buena práctica restringir el método
def prosoche_actualizar_objetivos(request):
    """
    Actualiza objetivos mensuales y semanales de forma dinámica.
    """
    try:
        data = json.loads(request.body)
        prosoche_id = data.get('prosoche_id')
        tipo = data.get('tipo')

        prosoche_mes = get_object_or_404(ProsocheMes, id=prosoche_id, usuario=request.user)

        if tipo == 'mensual':
            # --- LÓGICA CORREGIDA ---
            # Itera sobre los datos recibidos y actualiza solo los campos correspondientes.
            for key, value in data.items():
                # Solo actualiza los campos que existen en el modelo ProsocheMes
                if hasattr(prosoche_mes, key):
                    setattr(prosoche_mes, key, value)
            prosoche_mes.save()

        elif tipo == 'semanal':
            semana_num = data.get('semana')
            if semana_num is None:
                return JsonResponse({'success': False, 'error': 'Número de semana no proporcionado'}, status=400)

            semana = get_object_or_404(ProsocheSemana, prosoche_mes=prosoche_mes, numero_semana=semana_num)

            # Lógica dinámica también para las semanas
            for key, value in data.items():
                if hasattr(semana, key):
                    setattr(semana, key, value)
            semana.save()

        return JsonResponse({'success': True, 'message': 'Objetivo actualizado'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# diario/views.py

@login_required
def prosoche_toggle_habito(request):
    """
    Marcar/desmarcar hábito para un día específico (VERSIÓN FINAL Y ROBUSTA).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        habito_id = data.get('habito_id')
        dia = data.get('dia')

        if not all([habito_id, dia]):
            return JsonResponse({'success': False, 'error': 'Faltan datos.'}, status=400)

        # 1. Obtenemos el hábito para asegurar que pertenece al usuario.
        habito = get_object_or_404(ProsocheHabito, id=habito_id, prosoche_mes__usuario=request.user)

        # 2. Intentamos obtener el registro del día para ese hábito.
        dia_habito = ProsocheHabitoDia.objects.filter(habito=habito, dia=dia).first()

        # 3. Lógica de decisión clara:
        if dia_habito:
            # Si el registro existe, lo eliminamos. Esto equivale a "desmarcar".
            dia_habito.delete()
            estado_final = False
            mensaje = f"Día {dia} para '{habito.nombre}' desmarcado."
        else:
            # Si el registro no existe, lo creamos. Esto equivale a "marcar".
            ProsocheHabitoDia.objects.create(habito=habito, dia=dia, completado=True)
            estado_final = True
            mensaje = f"Día {dia} para '{habito.nombre}' marcado como completado."

        print(mensaje)  # Para depuración en la consola del servidor.

        return JsonResponse({
            'success': True,
            'completado': estado_final,
            'message': mensaje
        })

    except Exception as e:
        # Capturamos cualquier otro error para depuración.
        print(f"ERROR en prosoche_toggle_habito: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def prosoche_revision_mes(request):
    """Actualizar revisión del mes"""
    if request.method == 'POST':
        prosoche_id = request.POST.get('prosoche_id')
        prosoche_mes = get_object_or_404(ProsocheMes, id=prosoche_id, usuario=request.user)

        prosoche_mes.logro_principal = request.POST.get('logro_principal', '')
        prosoche_mes.obstaculo_principal = request.POST.get('obstaculo_principal', '')
        prosoche_mes.aprendizaje_principal = request.POST.get('aprendizaje_principal', '')
        prosoche_mes.momento_felicidad = request.POST.get('momento_felicidad', '')
        prosoche_mes.save()

        messages.success(request, 'Revisión del mes guardada correctamente.')
        return redirect('diario:prosoche_dashboard')

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def prosoche_mes_anterior(request, mes, año):
    """Ver mes anterior específico"""
    prosoche_mes = get_object_or_404(
        ProsocheMes,
        usuario=request.user,
        mes=mes,
        año=año
    )

    semanas = ProsocheSemana.objects.filter(prosoche_mes=prosoche_mes).order_by('numero_semana')
    entradas = ProsocheDiario.objects.filter(prosoche_mes=prosoche_mes).order_by('fecha')
    habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

    # Preparar datos de hábitos con seguimiento
    dias_mes = list(range(1, 32))  # Máximo 31 días
    habitos_con_dias = []

    for habito in habitos:
        dias_habito = []
        for dia in dias_mes:
            try:
                dia_obj = ProsocheHabitoDia.objects.get(habito=habito, dia=dia)
                dias_habito.append(dia_obj)
            except ProsocheHabitoDia.DoesNotExist:
                dias_habito.append(None)

        habitos_con_dias.append({
            'habito': habito,
            'dias': dias_habito
        })

    context = {
        'prosoche_mes': prosoche_mes,
        'semanas': semanas,
        'entradas': entradas,
        'habitos_con_dias': habitos_con_dias,
        'dias_mes': dias_mes,
        'es_mes_anterior': True
    }

    return render(request, 'diario/prosoche_mes_anterior.html', context)


# diario/views.py

from .models import RevisionSemanal  # Asegúrate de que esta importación está al principio

from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Avg
from django.db.models import Avg, Count
from collections import Counter


@login_required
def prosoche_revision_semanal(request):
    """
    Vista para la revisión semanal guiada, AHORA CON ANÁLISIS DE SIMBIOSIS.
    """
    hoy = timezone.now().date()
    inicio_semana_pasada = hoy - timedelta(days=hoy.weekday() + 7)
    fin_semana_pasada = inicio_semana_pasada + timedelta(days=6)

    # --- ANÁLISIS DE PROSOCHE (Lógica existente) ---
    entradas_semana_pasada = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha__range=[inicio_semana_pasada, fin_semana_pasada]
    ).order_by('fecha')

    animo_promedio = entradas_semana_pasada.aggregate(Avg('estado_animo'))['estado_animo__avg']
    if animo_promedio:
        animo_promedio = round(animo_promedio, 1)

    total_tareas = sum(e.get_total_tareas() for e in entradas_semana_pasada)
    tareas_completadas = sum(e.get_tareas_completadas() for e in entradas_semana_pasada)
    porcentaje_tareas = round((tareas_completadas / total_tareas) * 100) if total_tareas > 0 else 0

    # --- ANÁLISIS DE SIMBIOSIS (¡NUEVA LÓGICA!) ---
    interacciones_semana_pasada = Interaccion.objects.filter(
        usuario=request.user,
        fecha__range=[inicio_semana_pasada, fin_semana_pasada]
    ).prefetch_related('personas')

    # Contar tipos de interacción
    balance_interacciones = dict(Counter(interacciones_semana_pasada.values_list('tipo_interaccion', flat=True)))

    # Encontrar la persona con más interacciones
    personas_interactuadas = []
    for interaccion in interacciones_semana_pasada:
        personas_interactuadas.extend(interaccion.personas.all())

    persona_mas_frecuente = None
    if personas_interactuadas:
        top_persona = Counter(personas_interactuadas).most_common(1)[0]
        persona_mas_frecuente = {
            'persona': top_persona[0],
            'count': top_persona[1]
        }

    # --- LÓGICA DE FORMULARIOS (sin cambios) ---
    # (El resto de la vista para manejar la planificación y la revisión sigue igual)
    # ... (código para obtener semana_actual, semana_pasada, revision, y manejar el POST)
    prosoche_mes_actual = ProsocheMes.objects.filter(usuario=request.user, año=hoy.year, mes=hoy.strftime('%B')).first()
    numero_semana_actual = (hoy.day - 1) // 7 + 1
    semana_actual = None
    if prosoche_mes_actual:
        semana_actual, _ = ProsocheSemana.objects.get_or_create(
            prosoche_mes=prosoche_mes_actual,
            numero_semana=numero_semana_actual
        )

    numero_semana_pasada = (inicio_semana_pasada.day - 1) // 7 + 1
    prosoche_mes_pasado = ProsocheMes.objects.filter(año=inicio_semana_pasada.year,
                                                     mes=inicio_semana_pasada.strftime('%B'),
                                                     usuario=request.user).first()
    semana_pasada = None
    if prosoche_mes_pasado:
        semana_pasada, _ = ProsocheSemana.objects.get_or_create(prosoche_mes=prosoche_mes_pasado,
                                                                numero_semana=numero_semana_pasada)

    revision = None
    if semana_pasada:
        revision, created = RevisionSemanal.objects.get_or_create(semana=semana_pasada, usuario=request.user)
        if created and entradas_semana_pasada.exists():
            logros_sugeridos = [e.que_ha_ido_bien for e in entradas_semana_pasada if e.que_ha_ido_bien]
            revision.logro_principal = " - " + "\n - ".join(logros_sugeridos)
            aprendizajes_sugeridos = [e.que_puedo_mejorar for e in entradas_semana_pasada if e.que_puedo_mejorar]
            revision.aprendizaje_principal = " - " + "\n - ".join(aprendizajes_sugeridos)

    if request.method == 'POST':
        if revision:
            revision.logro_principal = request.POST.get('logro_principal', '')
            revision.obstaculo_principal = request.POST.get('obstaculo_principal', '')
            revision.aprendizaje_principal = request.POST.get('aprendizaje_principal', '')
            revision.save()
            messages.info(request, 'Revisión de la semana guardada.')
        if semana_actual:
            semana_actual.objetivo_1 = request.POST.get('objetivo_1', '')
            semana_actual.objetivo_2 = request.POST.get('objetivo_2', '')
            semana_actual.objetivo_3 = request.POST.get('objetivo_3', '')
            semana_actual.save()
            messages.success(request, '¡Planificación para la nueva semana guardada con éxito!')
        return redirect('diario:prosoche_dashboard')

    # --- CONTEXTO FINAL (con los nuevos datos) ---
    context = {
        'inicio_semana_pasada': inicio_semana_pasada,
        'fin_semana_pasada': fin_semana_pasada,
        'entradas_semana': entradas_semana_pasada,
        'animo_promedio': animo_promedio,
        'total_tareas': total_tareas,
        'tareas_completadas': tareas_completadas,
        'porcentaje_tareas': porcentaje_tareas,
        'semana_actual': semana_actual,
        'prosoche_mes_actual': prosoche_mes_actual,
        'revision': revision,
        # ¡Nuevos datos para la plantilla!
        'interacciones_semana': interacciones_semana_pasada,
        'balance_interacciones': balance_interacciones,
        'persona_mas_frecuente': persona_mas_frecuente,
    }
    return render(request, 'diario/prosoche_revision_semanal.html', context)


@login_required
def oraculo_insights(request):
    """
    Página que muestra los insights generados por el motor de análisis.
    """
    insights = generar_insights_semanales(request.user)

    context = {
        'insights': insights
    }
    return render(request, 'diario/oraculo_insights.html', context)


@login_required
def analiticas_personales(request):
    """
    Página de visualización de datos históricos y tendencias.
    """
    periodo_dias = int(request.GET.get('periodo', 30))
    fecha_fin = timezone.now().date()
    fecha_inicio = fecha_fin - timedelta(days=periodo_dias - 1)

    entradas = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('fecha')

    seguimientos_vires = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('fecha')

    # --- LÓGICA DE DATOS MEJORADA ---
    labels = []
    animo_data = []
    peso_data = []
    sueno_data = []
    energia_data = []
    estres_data = []

    # Creamos un mapa de seguimientos para un acceso rápido
    vires_map = {s.fecha: s for s in seguimientos_vires}

    # Iteramos sobre el rango de fechas para asegurar que todos los días estén en el gráfico
    for i in range(periodo_dias):
        fecha_actual = fecha_inicio + timedelta(days=i)
        labels.append(fecha_actual.strftime('%d/%m'))

        entrada_dia = next((e for e in entradas if e.fecha == fecha_actual), None)
        seguimiento_dia = vires_map.get(fecha_actual)

        animo_data.append(entrada_dia.estado_animo if entrada_dia else 'NaN')
        peso_data.append(float(seguimiento_dia.peso) if seguimiento_dia and seguimiento_dia.peso else 'NaN')
        sueno_data.append(
            float(seguimiento_dia.horas_sueno) if seguimiento_dia and seguimiento_dia.horas_sueno else 'NaN')
        energia_data.append(
            seguimiento_dia.nivel_energia if seguimiento_dia and seguimiento_dia.nivel_energia else 'NaN')
        estres_data.append(seguimiento_dia.nivel_estres if seguimiento_dia and seguimiento_dia.nivel_estres else 'NaN')

    context = {
        'periodo_actual': periodo_dias,
        'chart_data': json.dumps({
            'labels': labels,
            'animo_data': animo_data,
            'peso_data': peso_data,
            'sueno_data': sueno_data,
            'energia_data': energia_data,
            'estres_data': estres_data,
        })
    }
    return render(request, 'diario/analiticas_personales.html', context)


# diario/views.py

@login_required
def simbiosis_dashboard(request):
    """Dashboard de Simbiosis (VERSIÓN OPTIMIZADA)"""

    # OPTIMIZACIÓN: No hay mucho que optimizar aquí ya que son dos listas separadas,
    # pero es una buena práctica ser explícito.
    personas = PersonaImportante.objects.filter(usuario=request.user).order_by('tipo_relacion', 'nombre')

    # OPTIMIZACIÓN: Usamos prefetch_related para cargar las personas asociadas a cada interacción.
    ultimas_interacciones = Interaccion.objects.filter(
        usuario=request.user
    ).prefetch_related('personas').order_by('-fecha')[:10]

    context = {
        'personas': personas,
        'ultimas_interacciones': ultimas_interacciones,
    }
    return render(request, 'diario/simbiosis_dashboard.html', context)


@login_required
def persona_crear_editar(request, persona_id=None):
    """
    Vista para crear o editar una PersonaImportante.
    """
    instance = None
    if persona_id:
        instance = get_object_or_404(PersonaImportante, id=persona_id, usuario=request.user)

    if request.method == 'POST':
        form = PersonaImportanteForm(request.POST, instance=instance)
        if form.is_valid():
            persona = form.save(commit=False)
            persona.usuario = request.user
            persona.save()
            messages.success(request, f'Se ha guardado a "{persona.nombre}" correctamente.')
            return redirect('diario:simbiosis_dashboard')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = PersonaImportanteForm(instance=instance)

    context = {
        'form': form,
        'instance': instance,  # Para saber en la plantilla si estamos editando o creando
    }
    return render(request, 'diario/persona_form.html', context)


@login_required
def interaccion_crear_editar(request, interaccion_id=None):
    """
    Vista para crear o editar una Interaccion.
    """
    instance = None
    if interaccion_id:
        instance = get_object_or_404(Interaccion, id=interaccion_id, usuario=request.user)

    if request.method == 'POST':
        # Pasamos el usuario al formulario para que pueda filtrar el campo 'personas'
        form = InteraccionForm(request.POST, instance=instance, usuario=request.user)
        if form.is_valid():
            interaccion = form.save(commit=False)
            interaccion.usuario = request.user
            interaccion.save()
            # El método .set() es la forma correcta de guardar relaciones ManyToMany
            form.save_m2m()
            messages.success(request, f'Interacción "{interaccion.titulo}" guardada correctamente.')
            return redirect('diario:simbiosis_dashboard')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        # Pasamos el usuario también en el método GET
        form = InteraccionForm(instance=instance, usuario=request.user)

    context = {
        'form': form,
        'instance': instance,
    }
    return render(request, 'diario/interaccion_form.html', context)


# diario/views.py

@login_required
def persona_detalle(request, persona_id):
    """
    Muestra el perfil de una PersonaImportante y todas las interacciones asociadas.
    """
    persona = get_object_or_404(PersonaImportante, id=persona_id, usuario=request.user)

    # Obtenemos todas las interacciones donde esta persona estuvo involucrada
    interacciones_con_persona = persona.interaccion_set.all().order_by('-fecha')

    context = {
        'persona': persona,
        'interacciones': interacciones_con_persona,
    }
    return render(request, 'diario/persona_detalle.html', context)

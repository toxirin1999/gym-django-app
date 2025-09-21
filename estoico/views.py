from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime, timedelta

from .models import (
    ContenidoDiario, PerfilEstoico, ReflexionDiaria,
    LogroEstoico, LogroUsuario, EstadisticaUsuario,
    ConfiguracionNotificacion
)
from .forms import ReflexionDiariaForm, ConfiguracionPerfilForm, ConfiguracionNotificacionForm
from .utils import obtener_contenido_dia, verificar_logros, calcular_estadisticas


@login_required
def dashboard_estoico(request):
    """
    Dashboard principal de la sección estoica
    """
    # Obtener o crear perfil estoico
    perfil, created = PerfilEstoico.objects.get_or_create(usuario=request.user)

    # Obtener contenido del día actual
    dia_actual = timezone.now().timetuple().tm_yday
    contenido_hoy = get_object_or_404(ContenidoDiario, dia=dia_actual)

    # Verificar si ya reflexionó hoy
    hoy = timezone.now().date()
    reflexion_hoy = ReflexionDiaria.objects.filter(
        usuario=request.user,
        fecha=hoy
    ).first()

    # Obtener estadísticas
    estadisticas, _ = EstadisticaUsuario.objects.get_or_create(usuario=request.user)

    # Obtener logros recientes
    logros_recientes = LogroUsuario.objects.filter(
        usuario=request.user,
        visto=False
    ).select_related('logro')[:3]

    # Obtener reflexiones recientes
    reflexiones_recientes = ReflexionDiaria.objects.filter(
        usuario=request.user
    ).select_related('contenido_dia')[:5]

    context = {
        'perfil': perfil,
        'contenido_hoy': contenido_hoy,
        'reflexion_hoy': reflexion_hoy,
        'estadisticas': estadisticas,
        'logros_recientes': logros_recientes,
        'reflexiones_recientes': reflexiones_recientes,
        'dia_actual': dia_actual,
    }

    return render(request, 'estoico/dashboard.html', context)


@login_required
def diario_dia(request, dia=None):
    """
    Vista para mostrar y crear reflexión del día específico
    """
    if dia is None:
        dia = timezone.now().timetuple().tm_yday

    contenido_dia = get_object_or_404(ContenidoDiario, dia=dia)

    # Obtener reflexión existente si existe
    fecha_dia = timezone.now().date()  # Simplificado, en producción calcular fecha real del día
    reflexion_existente = ReflexionDiaria.objects.filter(
        usuario=request.user,
        contenido_dia=contenido_dia
    ).first()

    if request.method == 'POST':
        form = ReflexionDiariaForm(request.POST, instance=reflexion_existente)
        if form.is_valid():
            reflexion = form.save(commit=False)
            reflexion.usuario = request.user
            reflexion.contenido_dia = contenido_dia
            reflexion.fecha = fecha_dia
            reflexion.save()

            # Actualizar estadísticas
            estadisticas, _ = EstadisticaUsuario.objects.get_or_create(usuario=request.user)
            estadisticas.actualizar_racha()

            # Verificar logros
            verificar_logros(request.user)

            messages.success(request, '¡Reflexión guardada exitosamente!')
            return redirect('estoico:dashboard')
    else:
        form = ReflexionDiariaForm(instance=reflexion_existente)

    # Navegación entre días
    dia_anterior = dia - 1 if dia > 1 else 366
    dia_siguiente = dia + 1 if dia < 366 else 1

    context = {
        'contenido_dia': contenido_dia,
        'form': form,
        'reflexion_existente': reflexion_existente,
        'dia_anterior': dia_anterior,
        'dia_siguiente': dia_siguiente,
    }

    return render(request, 'estoico/diario_dia.html', context)


@login_required
def calendario_estoico(request):
    """
    Vista del calendario con progreso mensual
    """
    # Obtener año actual o del parámetro
    año = request.GET.get('año', timezone.now().year)
    mes = request.GET.get('mes', timezone.now().month)

    # Obtener reflexiones del usuario para el mes
    reflexiones_mes = ReflexionDiaria.objects.filter(
        usuario=request.user,
        fecha__year=año,
        fecha__month=mes
    ).select_related('contenido_dia')

    # Crear diccionario de días con reflexiones
    dias_con_reflexion = {r.fecha.day: r for r in reflexiones_mes}

    # Obtener contenido de todos los días del mes
    import calendar
    dias_mes = calendar.monthrange(int(año), int(mes))[1]

    calendario_datos = []
    for dia in range(1, dias_mes + 1):
        # Calcular día del año
        fecha = datetime(int(año), int(mes), dia).date()
        dia_año = fecha.timetuple().tm_yday

        contenido = ContenidoDiario.objects.filter(dia=dia_año).first()
        reflexion = dias_con_reflexion.get(dia)

        calendario_datos.append({
            'dia': dia,
            'dia_año': dia_año,
            'contenido': contenido,
            'reflexion': reflexion,
            'completado': reflexion is not None,
        })

    context = {
        'año': año,
        'mes': mes,
        'calendario_datos': calendario_datos,
        'nombre_mes': calendar.month_name[int(mes)],
    }

    return render(request, 'estoico/calendario.html', context)


@login_required
def progreso_usuario(request):
    """
    Vista de progreso y estadísticas del usuario
    """
    estadisticas, _ = EstadisticaUsuario.objects.get_or_create(usuario=request.user)

    # Calcular estadísticas actualizadas
    calcular_estadisticas(request.user)
    estadisticas.refresh_from_db()

    # Obtener logros del usuario
    logros_usuario = LogroUsuario.objects.filter(
        usuario=request.user
    ).select_related('logro').order_by('-fecha_obtenido')

    # Obtener todos los logros disponibles
    todos_logros = LogroEstoico.objects.filter(activo=True)
    logros_obtenidos_ids = logros_usuario.values_list('logro_id', flat=True)
    logros_pendientes = todos_logros.exclude(id__in=logros_obtenidos_ids)

    # Datos para gráficos (últimos 30 días)
    fecha_inicio = timezone.now().date() - timedelta(days=30)
    reflexiones_periodo = ReflexionDiaria.objects.filter(
        usuario=request.user,
        fecha__gte=fecha_inicio
    ).order_by('fecha')

    # Preparar datos para gráfico de actividad
    datos_actividad = []
    for i in range(30):
        fecha = fecha_inicio + timedelta(days=i)
        reflexion = reflexiones_periodo.filter(fecha=fecha).first()
        datos_actividad.append({
            'fecha': fecha.strftime('%Y-%m-%d'),
            'activo': reflexion is not None,
            'calificacion': reflexion.calificacion_dia if reflexion else 0,
        })

    context = {
        'estadisticas': estadisticas,
        'logros_obtenidos': logros_usuario,
        'logros_pendientes': logros_pendientes,
        'datos_actividad': json.dumps(datos_actividad),
        'total_logros': todos_logros.count(),
        'porcentaje_logros': (logros_usuario.count() / todos_logros.count() * 100) if todos_logros.count() > 0 else 0,
    }

    return render(request, 'estoico/progreso.html', context)


@login_required
def configuracion_estoica(request):
    """
    Vista de configuración del perfil estoico
    """
    perfil, _ = PerfilEstoico.objects.get_or_create(usuario=request.user)
    config_notif, _ = ConfiguracionNotificacion.objects.get_or_create(usuario=request.user)

    if request.method == 'POST':
        form_perfil = ConfiguracionPerfilForm(request.POST, instance=perfil)
        form_notif = ConfiguracionNotificacionForm(request.POST, instance=config_notif)

        if form_perfil.is_valid() and form_notif.is_valid():
            form_perfil.save()
            form_notif.save()
            messages.success(request, 'Configuración actualizada exitosamente!')
            return redirect('estoico:configuracion')
    else:
        form_perfil = ConfiguracionPerfilForm(instance=perfil)
        form_notif = ConfiguracionNotificacionForm(instance=config_notif)

    context = {
        'form_perfil': form_perfil,
        'form_notif': form_notif,
        'perfil': perfil,
    }

    return render(request, 'estoico/configuracion.html', context)


@login_required
@require_http_methods(["POST"])
def marcar_logro_visto(request, logro_id):
    """
    Marcar un logro como visto (AJAX)
    """
    try:
        logro_usuario = LogroUsuario.objects.get(
            usuario=request.user,
            logro_id=logro_id
        )
        logro_usuario.visto = True
        logro_usuario.save()
        return JsonResponse({'success': True})
    except LogroUsuario.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Logro no encontrado'})


@login_required
def buscar_contenido(request):
    """
    Búsqueda de contenido estoico
    """
    query = request.GET.get('q', '')
    autor = request.GET.get('autor', '')
    tema = request.GET.get('tema', '')

    contenidos = ContenidoDiario.objects.all()

    if query:
        contenidos = contenidos.filter(
            Q(cita__icontains=query) |
            Q(reflexion__icontains=query) |
            Q(pregunta__icontains=query)
        )

    if autor:
        contenidos = contenidos.filter(autor__icontains=autor)

    if tema:
        contenidos = contenidos.filter(tema__icontains=tema)

    # Paginación
    paginator = Paginator(contenidos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'autor': autor,
        'tema': tema,
    }

    return render(request, 'estoico/busqueda.html', context)


@login_required
def exportar_reflexiones(request):
    """
    Exportar reflexiones del usuario en formato JSON
    """
    reflexiones = ReflexionDiaria.objects.filter(
        usuario=request.user
    ).select_related('contenido_dia').order_by('fecha')

    datos_exportacion = []
    for reflexion in reflexiones:
        datos_exportacion.append({
            'fecha': reflexion.fecha.isoformat(),
            'dia_año': reflexion.contenido_dia.dia,
            'tema': reflexion.contenido_dia.tema,
            'cita': reflexion.contenido_dia.cita,
            'autor': reflexion.contenido_dia.autor,
            'reflexion_personal': reflexion.reflexion_personal,
            'calificacion': reflexion.calificacion_dia,
            'marcado_favorito': reflexion.marcado_favorito,
        })

    response = JsonResponse({
        'usuario': request.user.username,
        'fecha_exportacion': timezone.now().isoformat(),
        'total_reflexiones': len(datos_exportacion),
        'reflexiones': datos_exportacion,
    }, json_dumps_params={'indent': 2})

    response['Content-Disposition'] = f'attachment; filename="reflexiones_estoicas_{request.user.username}.json"'
    return response


@login_required
@require_POST  # Asegura que esta vista solo se pueda llamar con el método POST
def eliminar_todos_datos_usuario(request):
    """
    Vista para eliminar todos los datos asociados al usuario actual.
    """
    # Doble verificación de seguridad
    try:
        data = json.loads(request.body)
        if data.get('confirmacion') != 'ELIMINAR TODO':
            return JsonResponse({'success': False, 'error': 'Confirmación incorrecta.'}, status=400)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Petición inválida.'}, status=400)

    usuario = request.user

    try:
        # Aquí va la lógica de eliminación. ¡CON MUCHO CUIDADO!
        # Elimina los datos en el orden correcto para evitar problemas de claves foráneas.
        ReflexionDiaria.objects.filter(usuario=usuario).delete()
        LogroUsuario.objects.filter(usuario=usuario).delete()
        EstadisticaUsuario.objects.filter(usuario=usuario).delete()

        # Puedes añadir más modelos aquí si es necesario
        # PerfilEstoico.objects.filter(usuario=usuario).delete()

        # Si todo sale bien, devuelve una respuesta de éxito
        return JsonResponse({'success': True})

    except Exception as e:
        # Si algo sale mal, registra el error y notifica al usuario
        print(f"Error al eliminar datos para {usuario.username}: {e}")
        return JsonResponse({'success': False, 'error': 'Ocurrió un error inesperado durante la eliminación.'},
                            status=500)


@login_required
def exportar_reflexiones_pdf(request):
    """
    Vista placeholder para generar un PDF con las reflexiones del usuario.
    Por ahora, solo devuelve un mensaje simple.
    """
    # Aquí iría la lógica compleja para generar un PDF con librerías como
    # ReportLab, WeasyPrint, o FPDF.

    # Por ahora, devolvemos una respuesta simple para que la URL funcione.
    return HttpResponse(f"Funcionalidad de exportar a PDF para el usuario {request.user.username} en desarrollo.")

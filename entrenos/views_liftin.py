from entrenos.models import EjercicioBase
from rutinas.models import Rutina, Programa
from .forms import ImportarLiftinCompletoForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg, Max
import json
import csv
from django.forms import formset_factory
from .forms import EjercicioLiftinForm
from logros.utils import obtener_datos_logros

from datetime import datetime, timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import EntrenoRealizado, EjercicioLiftinDetallado, DatosLiftinDetallados
from .forms import (
    ImportarLiftinCompletoForm,
    ImportarLiftinBasicoForm,
    BuscarEntrenamientosLiftinForm,
    ExportarDatosForm,
    EjercicioLiftinFormSet
)
from clientes.models import Cliente
from entrenos.models import EjercicioRealizado

# ============================================================================
# VISTAS PRINCIPALES DE IMPORTACIÓN
# ============================================================================

from django.utils import timezone
from .models import EjercicioLiftin, activar_logros_liftin
from django.forms import modelformset_factory

# Crear formset para ejercicios
EjercicioLiftinFormSet = modelformset_factory(
    EjercicioLiftin,
    fields=['nombre', 'peso_texto', 'repeticiones_texto', 'estado'],
    extra=8,  # Para 8 ejercicios por defecto
    can_delete=True
)


@login_required
def dashboard_liftin_cliente(request, cliente_id):
    """
    Dashboard de Liftin para un cliente específico
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Redirigir al dashboard principal con filtro de cliente
    return redirect(f"{reverse('entrenos:dashboard_liftin')}?cliente={cliente_id}")


@login_required
def dashboard_liftin_cliente(request, cliente_id):
    """
    Dashboard de Liftin para un cliente específico
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Redirigir al dashboard principal con filtro de cliente
    return redirect(f"{reverse('entrenos:dashboard_liftin')}?cliente={cliente_id}")


from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
import logging

# Configurar logging
logger = logging.getLogger(__name__)

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import mark_safe
import json


@csrf_protect
@require_http_methods(["GET", "POST"])
def importar_liftin_completo(request):
    from datetime import date
    from entrenos.models import Cliente, EntrenoRealizado, EjercicioRealizado, EjercicioBase
    from rutinas.models import Rutina

    if request.method == 'GET':
        clientes = Cliente.objects.all().order_by('nombre')
        rutinas = Rutina.objects.all().order_by('nombre')
        ejercicios_disponibles = EjercicioBase.objects.all().order_by('nombre')

        ejercicios_json = json.dumps(
            list(ejercicios_disponibles.values("nombre", "grupo_muscular")),
            cls=DjangoJSONEncoder
        )

        context = {
            'clientes': clientes,
            'rutinas': rutinas,
            'hoy': date.today(),
            'ejercicios': mark_safe(ejercicios_json),  # para usarlo como JSON directamente en el script
        }

        return render(request, 'entrenos/importar_liftin_completo.html', context)

    elif request.method == 'POST':
        try:
            cliente_id = request.POST.get('cliente')
            fecha_str = request.POST.get('fecha')
            rutina_id = request.POST.get('rutina')
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

            cliente = Cliente.objects.get(id=cliente_id)
            rutina = Rutina.objects.get(id=rutina_id) if rutina_id else Rutina.objects.first()

            datos_entrenamiento = {
                'cliente': cliente,
                'rutina': rutina,
                'fecha': fecha,
                'fuente_datos': 'liftin',
                'procesado_gamificacion': False,
                'notas_liftin': '',
            }

            for campo in ['duracion_minutos', 'calorias_quemadas', 'volumen_total_kg']:
                valor = request.POST.get(campo)
                if valor:
                    try:
                        datos_entrenamiento[campo] = int(valor) if 'minutos' in campo or 'calorias' in campo else float(
                            valor)
                    except ValueError:
                        pass

            # ✅ Parseo especial para hora_inicio
            try:
                hora_inicio_str = request.POST.get('hora_inicio')
                if hora_inicio_str:
                    datos_entrenamiento['hora_inicio'] = datetime.strptime(hora_inicio_str, '%H:%M').time()


            except Exception as e:
                print("Error procesando hora:", e)

            # Calcular hora_fin si ambos valores están disponibles
            try:
                hora_inicio_str = request.POST.get('hora_inicio')
                if hora_inicio_str:
                    datos_entrenamiento['hora_inicio'] = datetime.strptime(hora_inicio_str, '%H:%M').time()

                duracion_str = request.POST.get('duracion_minutos')
                if duracion_str and 'hora_inicio' in datos_entrenamiento:
                    duracion = int(duracion_str)
                    hora_inicio_dt = datetime.combine(datetime.today(), datos_entrenamiento['hora_inicio'])
                    hora_fin_dt = hora_inicio_dt + timedelta(minutes=duracion)
                    datos_entrenamiento['duracion_minutos'] = duracion  # ahora sí como int
                    datos_entrenamiento['hora_fin'] = hora_fin_dt.time()
            except Exception as e:
                print("❌ ERROR calculando hora_fin:", e)

            # Crear entrenamiento
            entrenamiento = EntrenoRealizado.objects.create(**datos_entrenamiento)
            print("=== DEBUG hora_inicio_str ===", hora_inicio_str)
            print("=== DEBUG datos_entrenamiento ===", datos_entrenamiento)

            ejercicios_texto = []
            for i in range(1, 9):
                nombre = request.POST.get(f'ejercicio_{i}_nombre', '').strip()
                if nombre:
                    estado = request.POST.get(f'ejercicio_{i}_estado', '')
                    peso_texto = request.POST.get(f'ejercicio_{i}_peso', '').strip()
                    series_texto = request.POST.get(f'ejercicio_{i}_series', '').strip()
                    notas = request.POST.get(f'ejercicio_{i}_notas', '').strip()

                    # Interpretar series y repeticiones
                    try:
                        series = int(series_texto)
                    except:
                        series = 1

                    try:
                        repeticiones = int(request.POST.get(f'ejercicio_{i}_reps', '1').strip())
                    except:
                        repeticiones = 1

                    peso = 0.0
                    try:
                        peso = float(str(peso_texto).replace(',', '.').split()[0])
                    except:
                        pass

                    EjercicioRealizado.objects.create(
                        entreno=entrenamiento,
                        nombre_ejercicio=nombre,
                        grupo_muscular=request.POST.get(f'ejercicio_{i}_grupo') or '',
                        peso_kg=peso,
                        series=series,
                        repeticiones=repeticiones,
                        tempo=request.POST.get(f'ejercicio_{i}_tempo') or None,
                        rpe=request.POST.get(f'ejercicio_{i}_rpe') or None,
                        rir=request.POST.get(f'ejercicio_{i}_rir') or None,
                        fallo_muscular=request.POST.get(f'ejercicio_{i}_fallo') == '1',
                        completado=(estado == 'completado'),
                        orden=i,
                        nuevo_record=request.POST.get(f'ejercicio_{i}_nuevo_record') == '1',
                        fuente_datos='liftin',
                    )

                    simbolo = {'completado': '✓', 'fallado': '✗', 'nuevo': 'N'}.get(estado, '')
                    linea = f"{simbolo} {nombre}"
                    if peso_texto:
                        linea += f": {peso_texto}"
                    if series_texto:
                        linea += f", {series_texto}"
                    ejercicios_texto.append(linea)

            notas_generales = request.POST.get('notas', '').strip()
            texto_completo = [notas_generales] if notas_generales else []
            if ejercicios_texto:
                texto_completo.append("\n\nEjercicios Detallados:")
                texto_completo.extend(ejercicios_texto)

            entrenamiento.notas_liftin = "\n".join(texto_completo)
            entrenamiento.numero_ejercicios = len(ejercicios_texto)
            entrenamiento.save()

            try:
                from logros.services import GamificacionService
                GamificacionService.procesar_entreno(entrenamiento)
                print("✅ GAMIFICACIÓN PROCESADA")

            except:
                pass

            messages.success(request,
                             f"Entrenamiento de Liftin guardado correctamente con {len(ejercicios_texto)} ejercicios.")
            return redirect('entrenos:dashboard_liftin')


        except Exception as e:

            from datetime import date

            from entrenos.models import Cliente, EjercicioBase

            from rutinas.models import Rutina

            clientes = Cliente.objects.all().order_by('nombre')

            rutinas = Rutina.objects.all().order_by('nombre')

            ejercicios_disponibles = EjercicioBase.objects.all().order_by('nombre')

            ejercicios_json = json.dumps(

                list(ejercicios_disponibles.values("nombre", "grupo_muscular")),

                cls=DjangoJSONEncoder

            )

            messages.error(request, f"Error al importar entrenamiento: {str(e)}")

            context = {

                'clientes': clientes,

                'rutinas': rutinas,

                'hoy': date.today(),

                'ejercicios': mark_safe(ejercicios_json),

            }

            return render(request, 'entrenos/importar_liftin_completo.html', context)


@login_required
def logros_liftin(request):
    """
    Vista detallada de logros de Liftin
    """
    cliente_id = request.GET.get('cliente')
    cliente_seleccionado = None

    if cliente_id:
        try:
            cliente_seleccionado = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            cliente_seleccionado = None

    # Si no hay cliente seleccionado, usar el primer cliente con entrenamientos de Liftin
    if not cliente_seleccionado:
        primer_entrenamiento = EntrenoRealizado.objects.filter(fuente_datos='liftin').first()
        if primer_entrenamiento:
            cliente_seleccionado = primer_entrenamiento.cliente

    # Obtener datos de logros
    if cliente_seleccionado:
        datos_logros = obtener_logros_cliente(cliente_seleccionado)

        # Obtener todos los logros completados (no solo los recientes)
        try:
            perfil = PerfilGamificacion.objects.get(cliente=cliente_seleccionado)
            todos_logros_completados = LogroUsuario.objects.filter(
                perfil=perfil,
                completado=True
            ).select_related('logro', 'logro__tipo').order_by('-fecha_desbloqueo')

            # Agrupar logros por tipo
            logros_por_tipo = {}
            for logro_usuario in todos_logros_completados:
                tipo = logro_usuario.logro.tipo.nombre
                if tipo not in logros_por_tipo:
                    logros_por_tipo[tipo] = []
                logros_por_tipo[tipo].append(logro_usuario)

            datos_logros['todos_logros_completados'] = todos_logros_completados
            datos_logros['logros_por_tipo'] = logros_por_tipo

        except PerfilGamificacion.DoesNotExist:
            datos_logros['todos_logros_completados'] = []
            datos_logros['logros_por_tipo'] = {}
    else:
        datos_logros = {
            'perfil': None,
            'logros_completados': [],
            'logros_progreso': [],
            'todos_logros_completados': [],
            'logros_por_tipo': {},
            'total_logros': 0,
            'puntos_totales': 0,
            'nivel_actual': None,
            'racha_actual': 0,
            'racha_maxima': 0,
        }

    # Clientes disponibles
    clientes_disponibles = Cliente.objects.filter(entrenorealizado__fuente_datos='liftin').distinct().order_by('nombre')

    context = {
        'datos_logros': datos_logros,
        'cliente_seleccionado': cliente_seleccionado,
        'clientes_disponibles': clientes_disponibles,
        'titulo': 'Logros de Liftin',
    }

    return render(request, 'entrenos/logros_liftin.html', context)


# ============================================================================
# FUNCIÓN PARA NOTIFICACIONES DE LOGROS
# ============================================================================

@login_required
def notificaciones_logros(request):
    """
    Vista para mostrar notificaciones de logros
    """
    cliente_id = request.GET.get('cliente')

    if cliente_id:
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            notificaciones = Notificacion.objects.filter(
                cliente=cliente,
                tipo__in=['logro', 'nivel']
            ).order_by('-fecha')[:20]

            # Marcar como leídas
            notificaciones.update(leida=True)

        except Cliente.DoesNotExist:
            notificaciones = []
    else:
        notificaciones = []

    context = {
        'notificaciones': notificaciones,
        'titulo': 'Notificaciones de Logros',
    }

    return render(request, 'entrenos/notificaciones_logros.html', context)


@login_required
def importar_liftin_basico(request):
    """
    Vista para importación básica de Liftin (versión simplificada)
    """
    if request.method == 'POST':
        form = ImportarLiftinBasicoForm(request.POST)

        if form.is_valid():
            entrenamiento = form.save(commit=False)
            entrenamiento.rutina = rutina  # asignada manualmente
            entrenamiento.save()
            print("✅ Entrenamiento guardado con éxito:", entrenamiento)

            messages.success(request, '✅ Entrenamiento básico de Liftin importado exitosamente!')
            return redirect('entrenos:dashboard_liftin')
        else:
            messages.error(request, '❌ Error en el formulario. Revisa los datos ingresados.')
    else:
        form = ImportarLiftinBasicoForm()

    context = {
        'form': form,
        'title': 'Importar Entrenamiento Básico de Liftin',
    }

    return render(request, 'entrenos/importar_liftin_basico.html', context)


# ============================================================================
# VISTAS DE BÚSQUEDA Y LISTADO
# ============================================================================

@login_required
def buscar_entrenamientos_liftin(request):
    """
    Vista para buscar entrenamientos con filtros específicos de Liftin
    """
    form = BuscarEntrenamientosLiftinForm(request.GET or None)
    entrenamientos = EntrenoRealizado.objects.all().order_by('-fecha', '-hora_inicio')

    if form.is_valid():
        # Aplicar filtros
        if form.cleaned_data['cliente']:
            entrenamientos = entrenamientos.filter(cliente=form.cleaned_data['cliente'])

        if form.cleaned_data['fuente_datos']:
            entrenamientos = entrenamientos.filter(fuente_datos=form.cleaned_data['fuente_datos'])

        if form.cleaned_data['volumen_rango']:
            volumen = form.cleaned_data['volumen_rango']
            if volumen == 'bajo':
                entrenamientos = entrenamientos.filter(volumen_total_kg__lt=10000)
            elif volumen == 'medio':
                entrenamientos = entrenamientos.filter(volumen_total_kg__gte=10000, volumen_total_kg__lte=20000)
            elif volumen == 'alto':
                entrenamientos = entrenamientos.filter(volumen_total_kg__gt=20000)

        if form.cleaned_data['numero_ejercicios_min']:
            entrenamientos = entrenamientos.filter(numero_ejercicios__gte=form.cleaned_data['numero_ejercicios_min'])

        if form.cleaned_data['numero_ejercicios_max']:
            entrenamientos = entrenamientos.filter(numero_ejercicios__lte=form.cleaned_data['numero_ejercicios_max'])

        if form.cleaned_data['fecha_desde']:
            entrenamientos = entrenamientos.filter(fecha__gte=form.cleaned_data['fecha_desde'])

        if form.cleaned_data['fecha_hasta']:
            entrenamientos = entrenamientos.filter(fecha__lte=form.cleaned_data['fecha_hasta'])

    # Paginación
    paginator = Paginator(entrenamientos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Estadísticas de la búsqueda
    stats = {
        'total': entrenamientos.count(),
        'liftin': entrenamientos.filter(fuente_datos='liftin').count(),
        'manual': entrenamientos.filter(fuente_datos='manual').count(),
        'volumen_total': entrenamientos.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0,
    }

    context = {
        'form': form,
        'page_obj': page_obj,
        'stats': stats,
        'title': 'Buscar Entrenamientos',
    }

    return render(request, 'entrenos/buscar_entrenamientos_liftin.html', context)


@login_required
def detalle_ejercicios_liftin(request, entrenamiento_id):
    """
    Vista para mostrar detalles de ejercicios específicos de un entrenamiento de Liftin
    """
    entrenamiento = get_object_or_404(EntrenoRealizado, id=entrenamiento_id)
    ejercicios = EjercicioLiftinDetallado.objects.filter(entreno=entrenamiento).order_by('orden_ejercicio')

    # Calcular estadísticas de ejercicios
    stats_ejercicios = {
        'total_ejercicios': ejercicios.count(),
        'completados': ejercicios.filter(estado_liftin='completado').count(),
        'fallados': ejercicios.filter(estado_liftin='fallado').count(),
        'nuevos': ejercicios.filter(estado_liftin='nuevo').count(),
        'volumen_total': sum([ej.volumen_ejercicio for ej in ejercicios]),
    }

    context = {
        'entrenamiento': entrenamiento,
        'ejercicios': ejercicios,
        'stats': stats_ejercicios,
        'title': f'Ejercicios - {entrenamiento.nombre_rutina_liftin or entrenamiento.rutina.nombre}',
    }

    return render(request, 'entrenos/detalle_ejercicios_liftin.html', context)


# ============================================================================
# VISTAS DE EXPORTACIÓN Y ANÁLISIS
# ============================================================================


@login_required
def exportar_datos_liftin(request):
    """
    Vista para exportar datos específicos de Liftin
    """
    if request.method == 'POST':
        # Lógica de exportación (simplificada)
        formato = request.POST.get('formato', 'csv')

        if formato == 'csv':
            return exportar_csv_liftin_simple()
        elif formato == 'json':
            return exportar_json_liftin_simple()

    # Si es GET, mostrar formulario de exportación
    context = {
        'title': 'Exportar Datos de Liftin',
    }
    return render(request, 'entrenos/exportar_datos_liftin.html', context)


def exportar_csv_liftin_simple():
    """
    Exportación simple a CSV
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="entrenamientos_liftin_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Cliente', 'Rutina', 'Fuente', 'Duración', 'Calorías', 'Volumen'])

    entrenamientos = EntrenoRealizado.objects.filter(fuente_datos='liftin').order_by('-fecha')

    for entreno in entrenamientos:
        writer.writerow([
            entreno.fecha,
            entreno.cliente.nombre,
            entreno.rutina.nombre,
            'Liftin',
            entreno.duracion_minutos or '',
            entreno.calorias_quemadas or '',
            entreno.volumen_total_kg or ''
        ])

    return response


def exportar_json_liftin_simple():
    """
    Exportación simple a JSON
    """
    import json
    from django.http import HttpResponse

    entrenamientos = EntrenoRealizado.objects.filter(fuente_datos='liftin').order_by('-fecha')

    data = []
    for entreno in entrenamientos:
        data.append({
            'fecha': entreno.fecha.isoformat(),
            'cliente': entreno.cliente.nombre,
            'rutina': entreno.rutina.nombre,
            'fuente': 'Liftin',
            'duracion_minutos': entreno.duracion_minutos,
            'calorias_quemadas': entreno.calorias_quemadas,
            'volumen_total_kg': float(entreno.volumen_total_kg) if entreno.volumen_total_kg else None,
        })

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    response[
        'Content-Disposition'] = f'attachment; filename="entrenamientos_liftin_{timezone.now().strftime("%Y%m%d")}.json"'

    return response


def exportar_csv_liftin(entrenamientos):
    """
    Exportar entrenamientos a formato CSV
    """
    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="entrenamientos_liftin_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Fecha', 'Cliente', 'Rutina', 'Fuente', 'Hora Inicio', 'Hora Fin',
        'Duración (min)', 'Ejercicios', 'Volumen (kg)', 'Calorías',
        'FC Promedio', 'FC Máxima', 'Notas'
    ])

    for entreno in entrenamientos:
        writer.writerow([
            entreno.fecha,
            entreno.cliente.nombre,
            entreno.nombre_rutina_liftin or entreno.rutina.nombre,
            entreno.get_fuente_datos_display(),
            entreno.hora_inicio or '',
            entreno.hora_fin or '',
            entreno.duracion_minutos or '',
            entreno.numero_ejercicios or '',
            entreno.volumen_total_kg or '',
            entreno.calorias_quemadas or '',
            entreno.frecuencia_cardiaca_promedio or '',
            entreno.frecuencia_cardiaca_maxima or '',
            entreno.notas_liftin or ''
        ])

    return response


def exportar_json_liftin(entrenamientos):
    """
    Exportar entrenamientos a formato JSON
    """
    data = []

    for entreno in entrenamientos:
        ejercicios = []
        if hasattr(entreno, 'ejercicios_liftin'):
            ejercicios = [
                {
                    'nombre': ej.nombre_ejercicio,
                    'peso_formateado': ej.peso_formateado,
                    'repeticiones_formateado': ej.repeticiones_formateado,
                    'estado': ej.estado_liftin,
                    'orden': ej.orden_ejercicio,
                }
                for ej in entreno.ejercicios_liftin.all()
            ]

        data.append({
            'id': entreno.id,
            'fecha': entreno.fecha.isoformat(),
            'cliente': entreno.cliente.nombre,
            'rutina': entreno.nombre_rutina_liftin or entreno.rutina.nombre,
            'fuente_datos': entreno.fuente_datos,
            'hora_inicio': entreno.hora_inicio.isoformat() if entreno.hora_inicio else None,
            'hora_fin': entreno.hora_fin.isoformat() if entreno.hora_fin else None,
            'duracion_minutos': entreno.duracion_minutos,
            'numero_ejercicios': entreno.numero_ejercicios,
            'volumen_total_kg': float(entreno.volumen_total_kg) if entreno.volumen_total_kg else None,
            'volumen_total_formateado': entreno.volumen_total_formateado,
            'calorias_quemadas': entreno.calorias_quemadas,
            'frecuencia_cardiaca_promedio': entreno.frecuencia_cardiaca_promedio,
            'frecuencia_cardiaca_maxima': entreno.frecuencia_cardiaca_maxima,
            'notas_liftin': entreno.notas_liftin,
            'ejercicios': ejercicios,
        })

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    response[
        'Content-Disposition'] = f'attachment; filename="entrenamientos_liftin_{timezone.now().strftime("%Y%m%d")}.json"'

    return response


@login_required
def comparar_liftin_manual(request):
    """
    Vista para comparar entrenamientos de Liftin vs manuales
    """
    # Estadísticas comparativas
    stats_liftin = EntrenoRealizado.objects.filter(fuente_datos='liftin').aggregate(
        total=Count('id'),
        duracion_promedio=Avg('duracion_minutos'),
        calorias_promedio=Avg('calorias_quemadas'),
        volumen_total=Sum('volumen_total_kg'),
        ejercicios_promedio=Avg('numero_ejercicios'),
    )

    stats_manual = EntrenoRealizado.objects.filter(fuente_datos='manual').aggregate(
        total=Count('id'),
        duracion_promedio=Avg('duracion_minutos'),
        calorias_promedio=Avg('calorias_quemadas'),
        volumen_total=Sum('volumen_total_kg'),
        ejercicios_promedio=Avg('numero_ejercicios'),
    )

    # Entrenamientos recientes de cada tipo
    liftin_recientes = EntrenoRealizado.objects.filter(fuente_datos='liftin').order_by('-fecha')[:10]
    manual_recientes = EntrenoRealizado.objects.filter(fuente_datos='manual').order_by('-fecha')[:10]

    context = {
        'stats_liftin': stats_liftin,
        'stats_manual': stats_manual,
        'liftin_recientes': liftin_recientes,
        'manual_recientes': manual_recientes,
        'title': 'Comparación Liftin vs Manual',
    }

    return render(request, 'entrenos/comparar_liftin_manual.html', context)


# ============================================================================
# APIS PARA DATOS DINÁMICOS
# ============================================================================


@login_required
def api_stats_liftin(request):
    """
    API para obtener estadísticas de Liftin en formato JSON
    """
    cliente_id = request.GET.get('cliente')

    entrenamientos = EntrenoRealizado.objects.filter(fuente_datos='liftin')
    if cliente_id:
        entrenamientos = entrenamientos.filter(cliente_id=cliente_id)

    stats = {
        'total_entrenamientos': entrenamientos.count(),
        'total_calorias': entrenamientos.aggregate(Sum('calorias_quemadas'))['calorias_quemadas__sum'] or 0,
        'total_duracion': entrenamientos.aggregate(Sum('duracion_minutos'))['duracion_minutos__sum'] or 0,
        'fc_promedio': entrenamientos.aggregate(Avg('frecuencia_cardiaca_promedio'))[
                           'frecuencia_cardiaca_promedio__avg'] or 0,
        'volumen_total': entrenamientos.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0,
    }

    return JsonResponse(stats)


@login_required
def api_ejercicios_liftin(request, entrenamiento_id):
    """
    API para obtener ejercicios de un entrenamiento de Liftin en formato JSON
    """
    entrenamiento = get_object_or_404(EntrenoRealizado, id=entrenamiento_id, fuente_datos='liftin')

    # Procesar ejercicios desde las notas
    ejercicios = procesar_ejercicios_desde_notas(entrenamiento.notas_liftin)

    return JsonResponse({'ejercicios': ejercicios})


def procesar_ejercicios_desde_notas(notas_liftin):
    """
    Procesa los ejercicios desde las notas de Liftin para mostrarlos estructurados
    """
    ejercicios = []

    if not notas_liftin or "Ejercicios Detallados:" not in notas_liftin:
        return ejercicios

    try:
        seccion_ejercicios = notas_liftin.split("Ejercicios Detallados:")[1].strip()
        lineas_ejercicios = seccion_ejercicios.split('\n')

        for linea in lineas_ejercicios:
            linea = linea.strip()
            if not linea:
                continue

            # Formato esperado: "✓ Prensa: 268.5 kg, 3x5-10"
            if any(icono in linea for icono in ['✓', '✗', 'N']):
                try:
                    # Extraer estado
                    estado_icon = linea[0]
                    estado_map = {'✓': 'completado', '✗': 'fallado', 'N': 'nuevo'}
                    estado = estado_map.get(estado_icon, 'completado')

                    # Extraer nombre y datos
                    resto = linea[1:].strip()
                    if ':' in resto:
                        nombre, datos = resto.split(':', 1)
                        nombre = nombre.strip()
                        datos = datos.strip()

                        # Separar peso y repeticiones
                        if ',' in datos:
                            peso, repeticiones = datos.split(',', 1)
                            peso = peso.strip()
                            repeticiones = repeticiones.strip()
                        else:
                            peso = datos
                            repeticiones = ''

                        ejercicios.append({
                            'nombre': nombre,
                            'peso': peso,
                            'repeticiones': repeticiones,
                            'estado': estado,
                            'estado_icon': estado_icon,
                        })
                except:
                    continue
    except:
        pass

    return ejercicios


def valores_por_defecto_logros():
    """
    Valores por defecto para logros cuando no hay datos
    """
    return {
        'puntos_totales': 0,
        'logros_desbloqueados': 0,
        'racha_actual': 0,
        'racha_maxima': 0,
        'nivel_actual': 1,
        'nivel_nombre': 'Principiante',
        'progreso_nivel': 0,
        'puntos_nivel_actual': 0,
        'puntos_siguiente_nivel': 1000,
    }


# ============================================================================
# VISTAS DE UTILIDADES
# ============================================================================

@login_required
def validar_datos_liftin(request):
    """
    Vista para validar y limpiar datos de Liftin
    """
    if request.method == 'POST':
        # Lógica para validar y limpiar datos
        entrenamientos_problemas = EntrenoRealizado.objects.filter(
            fuente_datos='liftin'
        ).filter(
            Q(volumen_total_kg__isnull=True) |
            Q(numero_ejercicios__isnull=True) |
            Q(duracion_minutos__isnull=True)
        )

        # Intentar corregir datos faltantes
        corregidos = 0
        for entreno in entrenamientos_problemas:
            if not entreno.numero_ejercicios:
                ejercicios_count = entreno.ejercicios_liftin.count()
                if ejercicios_count > 0:
                    entreno.numero_ejercicios = ejercicios_count
                    entreno.save()
                    corregidos += 1

        messages.success(request, f'✅ Se corrigieron {corregidos} entrenamientos.')
        return redirect('entrenos:dashboard_liftin')

    # Mostrar problemas encontrados
    problemas = EntrenoRealizado.objects.filter(
        fuente_datos='liftin'
    ).filter(
        Q(volumen_total_kg__isnull=True) |
        Q(numero_ejercicios__isnull=True) |
        Q(duracion_minutos__isnull=True)
    )

    context = {
        'problemas': problemas,
        'title': 'Validar Datos de Liftin',
    }

    return render(request, 'entrenos/validar_datos_liftin.html', context)


@login_required
def preview_importacion(request):
    """
    Vista para previsualizar datos antes de importar
    """
    if request.method == 'POST':
        # Procesar datos de preview
        data = json.loads(request.body)

        # Validar datos
        errores = []
        warnings = []

        # Validaciones básicas
        if not data.get('cliente_id'):
            errores.append('Cliente es requerido')

        if not data.get('nombre_rutina'):
            errores.append('Nombre de rutina es requerido')

        # Validaciones de formato
        if data.get('tiempo_total') and not data['tiempo_total'].count(':') == 2:
            warnings.append('Formato de tiempo puede ser incorrecto (use H:MM:SS)')

        response_data = {
            'valido': len(errores) == 0,
            'errores': errores,
            'warnings': warnings,
            'datos_procesados': data,
        }

        return JsonResponse(response_data)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def detalle_ejercicios_liftin(request, entreno_id):
    """
    Vista para mostrar ejercicios detallados de un entrenamiento de Liftin
    """
    entreno = get_object_or_404(EntrenoRealizado, id=entreno_id)
    ejercicios = entreno.ejercicios_liftin.all().order_by('orden')

    context = {
        'entreno': entreno,
        'ejercicios': ejercicios,
        'total_ejercicios': ejercicios.count()
    }

    return render(request, 'entrenos/detalle_ejercicios_liftin.html', context)


@login_required
def detalle_ejercicios_liftin(request, entreno_id):
    """
    Vista para mostrar ejercicios detallados de un entrenamiento de Liftin
    """
    from django.shortcuts import get_object_or_404
    from .models import EntrenoRealizado

    entreno = get_object_or_404(EntrenoRealizado, id=entreno_id)

    # Intentar obtener ejercicios de Liftin si existen
    ejercicios = []
    if hasattr(entreno, 'ejercicios_liftin'):
        ejercicios = entreno.ejercicios_liftin.all().order_by('orden')

    context = {
        'entreno': entreno,
        'ejercicios': ejercicios,
        'total_ejercicios': len(ejercicios)
    }

    return render(request, 'entrenos/detalle_ejercicios_liftin.html', context)


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q, Max
from django.utils import timezone

import logging

# Importar modelos principales
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado

logger = logging.getLogger(__name__)

# entrenos/views.py

# en entrenos/views.py

from logros.models import PruebaLegendaria, PruebaUsuario

"""
Versión Corregida de la Función obtener_contexto_dashboard
=========================================================

Esta es la versión corregida que debe reemplazar la función existente
en entrenos/views.py (líneas aproximadamente 1000-1100).

La nueva versión:
1. Simplifica la lógica de cálculo de nivel
2. Maneja casos edge y datos inconsistentes
3. Es más robusta y fácil de mantener
4. Calcula correctamente el progreso de próximos logros
"""


def obtener_contexto_dashboard_corregido(cliente_seleccionado):
    """
    Función centralizada que prepara todo el contexto para el dashboard.
    VERSIÓN CORREGIDA Y SIMPLIFICADA.
    """
    # Filtro base de entrenamientos
    entrenamientos_base = EntrenoRealizado.objects.all()
    if cliente_seleccionado:
        entrenamientos_base = entrenamientos_base.filter(cliente=cliente_seleccionado)

    # Estadísticas generales (esta parte está bien)
    stats = {
        'total_entrenamientos': entrenamientos_base.count(),
        'entrenamientos_liftin': entrenamientos_base.filter(fuente_datos='liftin').count(),
    }
    stats['entrenamientos_manual'] = stats['total_entrenamientos'] - stats['entrenamientos_liftin']

    entrenamientos_liftin_qs = entrenamientos_base.filter(fuente_datos='liftin')
    stats['calorias_totales'] = entrenamientos_liftin_qs.aggregate(total=Sum('calorias_quemadas'))['total'] or 0
    stats['volumen_total'] = entrenamientos_liftin_qs.aggregate(total=Sum('volumen_total_kg'))['total'] or 0
    stats['duracion_promedio'] = entrenamientos_liftin_qs.aggregate(promedio=Avg('duracion_minutos'))['promedio'] or 0

    # --- DATOS DE GAMIFICACIÓN (LÓGICA CORREGIDA) ---
    logros_data = valores_por_defecto_logros()  # Valores por defecto

    if cliente_seleccionado:
        try:
            from logros.models import PerfilGamificacion, Nivel, LogroUsuario, Logro

            perfil = PerfilGamificacion.objects.select_related('nivel_actual').get(
                cliente=cliente_seleccionado
            )

            # 1. Datos básicos del perfil (fuente de verdad)
            logros_data['puntos_totales'] = perfil.puntos_totales
            logros_data['logros_desbloqueados'] = LogroUsuario.objects.filter(
                perfil=perfil,
                completado=True
            ).count()
            logros_data['racha_actual'] = perfil.racha_actual
            logros_data['racha_maxima'] = perfil.racha_maxima

            # 2. Cálculo de nivel y progreso (LÓGICA CORREGIDA)
            nivel_info = calcular_nivel_y_progreso_corregido(perfil.puntos_totales)
            logros_data.update(nivel_info)

            # 3. Logros recientes
            logros_data['logros_recientes'] = LogroUsuario.objects.filter(
                perfil=perfil,
                completado=True
            ).select_related('logro').order_by('-fecha_desbloqueo')[:3]

            # 4. Próximos logros (LÓGICA CORREGIDA)
            logros_data['proximos_logros'] = obtener_proximos_logros_corregido(perfil)

        except PerfilGamificacion.DoesNotExist:
            # Si no hay perfil, usar valores por defecto
            pass
        except ImportError:
            # Si no está disponible el módulo de logros
            pass

    # Entrenamientos recientes para la tabla
    entrenamientos_recientes = entrenamientos_base.select_related(
        'cliente', 'rutina'
    ).order_by('-fecha', '-id')[:10]

    return {
        'estadisticas': stats,
        'logros': logros_data,
        'entrenamientos_recientes': entrenamientos_recientes,
    }


def calcular_nivel_y_progreso_corregido(puntos_totales):
    """
    Calcula el nivel actual y progreso basado en puntos totales.
    VERSIÓN CORREGIDA que maneja casos edge.
    """
    # Validar entrada
    if puntos_totales is None or puntos_totales < 0:
        puntos_totales = 0

    # Sistema de niveles: cada 1000 puntos = 1 nivel
    # Nivel 1: 0-999 puntos
    # Nivel 2: 1000-1999 puntos
    # etc.

    if puntos_totales < 1000:
        nivel_numero = 1
        puntos_base_nivel = 0
        puntos_siguiente_nivel = 1000
    else:
        nivel_numero = (puntos_totales // 1000) + 1
        puntos_base_nivel = (nivel_numero - 1) * 1000
        puntos_siguiente_nivel = nivel_numero * 1000

    # Calcular progreso en el nivel actual
    puntos_en_nivel = puntos_totales - puntos_base_nivel
    rango_nivel = puntos_siguiente_nivel - puntos_base_nivel

    if rango_nivel > 0:
        progreso_porcentaje = int((puntos_en_nivel / rango_nivel) * 100)
    else:
        progreso_porcentaje = 0

    # Asegurar que el progreso esté entre 0 y 100
    progreso_porcentaje = max(0, min(100, progreso_porcentaje))

    # Nombres de niveles
    nombres_niveles = {
        1: 'Principiante',
        2: 'Novato',
        3: 'Intermedio',
        4: 'Avanzado',
        5: 'Experto',
        6: 'Maestro',
        7: 'Leyenda'
    }

    nombre_nivel = nombres_niveles.get(nivel_numero, f'Leyenda Nivel {nivel_numero}')

    return {
        'nivel_actual': nivel_numero,
        'nivel_nombre': nombre_nivel,
        'progreso_nivel': progreso_porcentaje,
        'puntos_nivel_actual': puntos_totales,
        'puntos_siguiente_nivel': puntos_siguiente_nivel,
        'puntos_en_nivel': puntos_en_nivel
    }


def obtener_proximos_logros_corregido(perfil):
    """
    Obtiene los próximos logros con su progreso real.
    VERSIÓN CORREGIDA que calcula el progreso correctamente.
    """
    try:
        from logros.models import Logro, LogroUsuario

        # Obtener logros que el usuario AÚN NO ha completado
        logros_pendientes = Logro.objects.exclude(
            usuarios__perfil=perfil,
            usuarios__completado=True
        ).order_by('puntos_recompensa')[:3]  # Los 3 más fáciles

        proximos_logros = []

        for logro in logros_pendientes:
            # Calcular progreso actual para este logro
            progreso_actual = calcular_progreso_logro_especifico(perfil, logro)

            # Asegurar que el progreso no exceda la meta
            progreso_actual = min(progreso_actual, logro.meta_valor)

            proximos_logros.append({
                'logro': logro,
                'progreso_actual': progreso_actual,
                'meta_valor': logro.meta_valor,
                'porcentaje': int((progreso_actual / logro.meta_valor) * 100) if logro.meta_valor > 0 else 0
            })

        return proximos_logros

    except Exception as e:
        print(f"Error obteniendo próximos logros: {e}")
        return []


def calcular_progreso_logro_especifico(perfil, logro):
    """
    Calcula el progreso actual para un logro específico.
    VERSIÓN CORREGIDA que maneja diferentes tipos de logros.
    """
    try:
        cliente = perfil.cliente
        nombre_logro = logro.nombre.lower()

        # LOGROS DE LIFTIN
        if "liftin" in nombre_logro:
            entrenamientos_liftin = EntrenoRealizado.objects.filter(
                cliente=cliente,
                fuente_datos='liftin'
            ).count()
            return entrenamientos_liftin

        # LOGROS DE ENTRENAMIENTOS GENERALES
        if "hito" in nombre_logro or "entrenamientos" in nombre_logro:
            return perfil.entrenos_totales

        # LOGROS DE CALORÍAS (por entrenamiento individual)
        if "quemador" in nombre_logro or "calorias" in nombre_logro:
            # Buscar el entrenamiento con más calorías del usuario
            max_calorias = EntrenoRealizado.objects.filter(
                cliente=cliente,
                calorias_quemadas__isnull=False
            ).aggregate(
                max_calorias=Max('calorias_quemadas')
            )['max_calorias'] or 0
            return max_calorias

        # LOGROS DE VOLUMEN (por entrenamiento individual)
        if "levantador" in nombre_logro or "volumen" in nombre_logro:
            max_volumen = EntrenoRealizado.objects.filter(
                cliente=cliente,
                volumen_total_kg__isnull=False
            ).aggregate(
                max_volumen=Max('volumen_total_kg')
            )['max_volumen'] or 0
            return int(max_volumen)

        # LOGROS DE RACHA
        if "racha" in nombre_logro:
            return perfil.racha_actual

        # LOGROS DE DURACIÓN
        if "duracion" in nombre_logro or "tiempo" in nombre_logro:
            max_duracion = EntrenoRealizado.objects.filter(
                cliente=cliente,
                duracion_minutos__isnull=False
            ).aggregate(
                max_duracion=Max('duracion_minutos')
            )['max_duracion'] or 0
            return max_duracion

        # Si no coincide con ningún patrón, devolver 0
        return 0

    except Exception as e:
        print(f"Error calculando progreso para logro {logro.nombre}: {e}")
        return 0


def valores_por_defecto_logros():
    """
    Valores por defecto para logros cuando no hay datos.
    """
    return {
        'puntos_totales': 0,
        'logros_desbloqueados': 0,
        'racha_actual': 0,
        'racha_maxima': 0,
        'nivel_actual': 1,
        'nivel_nombre': 'Principiante',
        'progreso_nivel': 0,
        'puntos_nivel_actual': 0,
        'puntos_siguiente_nivel': 1000,
        'puntos_en_nivel': 0,
        'logros_recientes': [],
        'proximos_logros': []
    }


@login_required
def dashboard_liftin(request):
    """
    Vista principal del dashboard de Liftin - Refactorizada y Limpia
    """
    cliente_seleccionado = None
    cliente_id = request.GET.get('cliente')

    clientes_disponibles = Cliente.objects.filter(
        entrenorealizado__fuente_datos='liftin'
    ).distinct().order_by('nombre')

    if cliente_id:
        cliente_seleccionado = get_object_or_404(Cliente, id=cliente_id)
    elif clientes_disponibles.exists():
        cliente_seleccionado = clientes_disponibles.first()

    # Obtener todo el contexto desde la función centralizada
    contexto_dashboard = obtener_contexto_dashboard_corregido(cliente_seleccionado)

    context = {
        'clientes_disponibles': clientes_disponibles,
        'cliente_seleccionado': cliente_seleccionado,
        **contexto_dashboard  # Desempaquetar el diccionario de contexto
    }

    return render(request, 'entrenos/dashboard_liftin.html', context)


# ============================
# FUNCIONES AUXILIARES SIMPLIFICADAS
# ============================

def verificar_datos_dashboard():
    """
    Función de diagnóstico para verificar datos del dashboard
    """
    print("=== DIAGNÓSTICO DE DATOS DEL DASHBOARD ===")

    # Verificar entrenamientos
    total_entrenamientos = EntrenoRealizado.objects.count()
    entrenamientos_liftin = EntrenoRealizado.objects.filter(fuente_datos='liftin').count()

    print(f"Total entrenamientos en BD: {total_entrenamientos}")
    print(f"Entrenamientos Liftin: {entrenamientos_liftin}")

    # Verificar clientes
    clientes_con_liftin = Cliente.objects.filter(
        entrenorealizado__fuente_datos='liftin'
    ).distinct()

    print(f"Clientes con entrenamientos Liftin: {clientes_con_liftin.count()}")
    for cliente in clientes_con_liftin:
        entrenamientos_cliente = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fuente_datos='liftin'
        ).count()
        print(f"  - {cliente.nombre} (ID: {cliente.id}): {entrenamientos_cliente} entrenamientos")

    # Verificar logros
    try:
        from logros.models import PerfilGamificacion, LogroUsuario

        perfiles = PerfilGamificacion.objects.all()
        print(f"Perfiles de gamificación: {perfiles.count()}")

        for perfil in perfiles:
            logros = LogroUsuario.objects.filter(perfil=perfil, completado=True).count()
            print(f"  - {perfil.cliente.nombre}: {perfil.puntos_totales} puntos, {logros} logros")

    except ImportError:
        print("Modelos de logros no disponibles")
    except Exception as e:
        print(f"Error verificando logros: {str(e)}")

    print("=== FIN DIAGNÓSTICO ===")


def test_dashboard_context():
    """
    Función para probar el contexto del dashboard
    """
    from django.test import RequestFactory
    from django.contrib.auth.models import User

    # Crear request de prueba
    factory = RequestFactory()
    request = factory.get('/dashboard/liftin/')
    request.user = User.objects.first() or User.objects.create_user('test')

    # Simular vista
    try:
        response = dashboard_liftin(request)
        print("✅ Dashboard funciona correctamente")
        return True
    except Exception as e:
        print(f"❌ Error en dashboard: {str(e)}")
        return False


def calcular_fechas_periodo(periodo):
    """Calcular fechas de inicio y fin según el período"""
    hoy = timezone.now().date()

    if periodo == 'week':
        inicio = hoy - timedelta(days=hoy.weekday())  # Lunes de esta semana
        fin = inicio + timedelta(days=6)  # Domingo de esta semana
    elif periodo == 'month':
        inicio = hoy.replace(day=1)  # Primer día del mes
        if hoy.month == 12:
            fin = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            fin = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)
    elif periodo == 'year':
        inicio = hoy.replace(month=1, day=1)  # 1 de enero
        fin = hoy.replace(month=12, day=31)  # 31 de diciembre
    else:
        # Por defecto, última semana
        inicio = hoy - timedelta(days=7)
        fin = hoy

    return {'inicio': inicio, 'fin': fin}


def calcular_estadisticas_principales(entrenamientos_base):
    """
    Calcula las estadísticas principales del dashboard
    """
    try:
        # Total de entrenamientos
        total_entrenamientos = entrenamientos_base.count()

        # Entrenamientos por fuente
        entrenamientos_liftin = entrenamientos_base.filter(fuente_datos='liftin').count()
        entrenamientos_manual = total_entrenamientos - entrenamientos_liftin

        # Calorías totales de Liftin
        calorias_totales = entrenamientos_base.filter(
            fuente_datos='liftin'
        ).aggregate(
            total=Sum('calorias_quemadas')
        )['total'] or 0

        return {
            'total_entrenamientos': total_entrenamientos,
            'entrenamientos_liftin': entrenamientos_liftin,
            'entrenamientos_manual': entrenamientos_manual,
            'calorias_totales': int(calorias_totales),
        }

    except Exception as e:
        logger.error(f"Error calculando estadísticas principales: {str(e)}")
        return {
            'total_entrenamientos': 0,
            'entrenamientos_liftin': 0,
            'entrenamientos_manual': 0,
            'calorias_totales': 0,
        }


def calcular_estadisticas_logros_corregidas(cliente_seleccionado):
    """
    Calcula las estadísticas del sistema de logros CORREGIDAS
    """
    try:
        if not LOGROS_DISPONIBLES or not cliente_seleccionado:
            return valores_por_defecto_logros()

        # Obtener perfil de gamificación
        perfil = PerfilGamificacion.objects.filter(
            cliente=cliente_seleccionado
        ).first()

        if not perfil:
            logger.warning(f"No se encontró perfil de gamificación para cliente {cliente_seleccionado.id}")
            return valores_por_defecto_logros()

        # Logros desbloqueados CORREGIDO
        logros_desbloqueados = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=True
        ).count()

        # Calcular puntos reales CORREGIDO
        puntos_reales = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=True
        ).aggregate(
            total=Sum('logro__puntos_recompensa')
        )['total'] or 0

        # Sincronizar puntos si hay diferencia
        if perfil.puntos_totales != puntos_reales:
            logger.info(f"Sincronizando puntos: {perfil.puntos_totales} -> {puntos_reales}")
            perfil.puntos_totales = puntos_reales
            perfil.save()

        # Calcular nivel y progreso
        nivel_info = calcular_nivel_y_progreso(puntos_reales)

        return {
            'puntos_totales': puntos_reales,
            'logros_desbloqueados': logros_desbloqueados,
            'racha_actual': perfil.racha_actual,
            'racha_maxima': perfil.racha_maxima,
            'nivel_actual': nivel_info['nivel'],
            'nivel_nombre': nivel_info['nombre'],
            'progreso_nivel': nivel_info['progreso'],
            'puntos_nivel_actual': nivel_info['puntos_nivel_actual'],
            'puntos_siguiente_nivel': nivel_info['puntos_siguiente_nivel'],
        }

    except Exception as e:
        logger.error(f"Error calculando estadísticas de logros: {str(e)}")
        return valores_por_defecto_logros()


def generar_datos_graficos(entrenamientos_base, periodo):
    """Generar datos para los gráficos"""

    # Datos para gráfico de progreso temporal
    if periodo == 'week':
        # Últimos 7 días
        datos_temporales = []
        for i in range(7):
            fecha = timezone.now().date() - timedelta(days=6 - i)
            entrenamientos_dia = entrenamientos_base.filter(fecha=fecha)
            liftin_dia = entrenamientos_dia.filter(fuente_datos='liftin').count()
            manual_dia = entrenamientos_dia.exclude(fuente_datos='liftin').count()

            datos_temporales.append({
                'fecha': fecha.strftime('%d/%m'),
                'liftin': liftin_dia,
                'manual': manual_dia
            })
    elif periodo == 'month':
        # Últimas 4 semanas
        datos_temporales = []
        for i in range(4):
            inicio_semana = timezone.now().date() - timedelta(weeks=3 - i)
            fin_semana = inicio_semana + timedelta(days=6)
            entrenamientos_semana = entrenamientos_base.filter(
                fecha__gte=inicio_semana, fecha__lte=fin_semana
            )
            liftin_semana = entrenamientos_semana.filter(fuente_datos='liftin').count()
            manual_semana = entrenamientos_semana.exclude(fuente_datos='liftin').count()

            datos_temporales.append({
                'fecha': f'S{i + 1}',
                'liftin': liftin_semana,
                'manual': manual_semana
            })
    else:
        # Últimos 6 meses
        datos_temporales = []
        for i in range(6):
            fecha_mes = timezone.now().date().replace(day=1) - timedelta(days=30 * i)
            entrenamientos_mes = entrenamientos_base.filter(
                fecha__year=fecha_mes.year,
                fecha__month=fecha_mes.month
            )
            liftin_mes = entrenamientos_mes.filter(fuente_datos='liftin').count()
            manual_mes = entrenamientos_mes.exclude(fuente_datos='liftin').count()

            datos_temporales.append({
                'fecha': fecha_mes.strftime('%b'),
                'liftin': liftin_mes,
                'manual': manual_mes
            })
        datos_temporales.reverse()

    # Datos para gráfico de distribución
    total_liftin = entrenamientos_base.filter(fuente_datos='liftin').count()
    total_manual = entrenamientos_base.exclude(fuente_datos='liftin').count()

    return {
        'temporal': datos_temporales,
        'distribucion': {
            'liftin': total_liftin,
            'manual': total_manual
        }
    }


def obtener_entrenamientos_recientes(cliente_seleccionado, limite=10):
    """
    Obtiene los entrenamientos más recientes
    """
    try:
        entrenamientos = EntrenoRealizado.objects.all()

        if cliente_seleccionado:
            entrenamientos = entrenamientos.filter(cliente=cliente_seleccionado)

        return entrenamientos.select_related(
            'cliente', 'rutina'
        ).order_by('-fecha', '-id')[:limite]

    except Exception as e:
        logger.error(f"Error obteniendo entrenamientos recientes: {str(e)}")
        return []


def generar_desafios_activos(cliente_seleccionado):
    """Generar desafíos activos para el cliente"""

    if not cliente_seleccionado:
        return []

    # Obtener estadísticas del cliente para calcular progreso
    entrenamientos_mes = EntrenoRealizado.objects.filter(
        cliente=cliente_seleccionado,
        fecha__gte=timezone.now().date().replace(day=1)
    )

    entrenamientos_liftin_mes = entrenamientos_mes.filter(fuente_datos='liftin').count()
    calorias_mes = entrenamientos_mes.aggregate(Sum('calorias_quemadas'))['calorias_quemadas__sum'] or 0
    volumen_mes = entrenamientos_mes.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0

    desafios = [
        {
            'id': 'liftin_mensual',
            'titulo': 'Maestro Liftin Mensual',
            'descripcion': 'Completa 20 entrenamientos de Liftin este mes',
            'progreso_actual': entrenamientos_liftin_mes,
            'progreso_meta': 20,
            'progreso_porcentaje': min((entrenamientos_liftin_mes / 20) * 100, 100),
            'recompensa': '500 puntos + Badge especial',
            'icono': '🏋️‍♂️',
            'tipo': 'mensual',
            'completado': entrenamientos_liftin_mes >= 20
        },
        {
            'id': 'calorias_semanales',
            'titulo': 'Quemador Semanal',
            'descripcion': 'Quema 2000 calorías esta semana',
            'progreso_actual': min(calorias_mes, 2000),
            'progreso_meta': 2000,
            'progreso_porcentaje': min((calorias_mes / 2000) * 100, 100),
            'recompensa': '300 puntos',
            'icono': '🔥',
            'tipo': 'semanal',
            'completado': calorias_mes >= 2000
        },
        {
            'id': 'volumen_mensual',
            'titulo': 'Levantador de Hierro',
            'descripcion': 'Levanta 50,000 kg este mes',
            'progreso_actual': min(volumen_mes, 50000),
            'progreso_meta': 50000,
            'progreso_porcentaje': min((volumen_mes / 50000) * 100, 100),
            'recompensa': '750 puntos + Título especial',
            'icono': '💪',
            'tipo': 'mensual',
            'completado': volumen_mes >= 50000
        }
    ]

    return desafios


from django.contrib.auth.decorators import login_required


@login_required
def tabla_ejercicio(request):
    return render(request, 'entrenos/tabla_ejercicios.html')


def generar_insights_automaticos(cliente_seleccionado, entrenamientos_base, estadisticas):
    """Generar insights automáticos basados en los datos"""

    insights = []

    if not cliente_seleccionado:
        insights.append({
            'tipo': 'info',
            'titulo': 'Selecciona un Cliente',
            'descripcion': 'Selecciona un cliente específico para ver insights personalizados.',
            'accion': 'Filtrar por Cliente',
            'icono': '👤'
        })
        return insights

    # Insight sobre frecuencia de entrenamientos
    if estadisticas['total_entrenamientos'] > 0:
        if estadisticas['entrenamientos_liftin'] > estadisticas['entrenamientos_manual']:
            insights.append({
                'tipo': 'success',
                'titulo': 'Excelente uso de Liftin',
                'descripcion': f'Has realizado {estadisticas["entrenamientos_liftin"]} entrenamientos con Liftin vs {estadisticas["entrenamientos_manual"]} manuales. ¡Sigue así!',
                'accion': 'Ver Detalles',
                'icono': '📱'
            })
        else:
            insights.append({
                'tipo': 'warning',
                'titulo': 'Oportunidad de mejora',
                'descripcion': f'Podrías aprovechar más Liftin. Solo {estadisticas["entrenamientos_liftin"]} de {estadisticas["total_entrenamientos"]} entrenamientos son de Liftin.',
                'accion': 'Importar más de Liftin',
                'icono': '📈'
            })

    # Insight sobre calorías
    if estadisticas['calorias_totales'] > 2000:
        insights.append({
            'tipo': 'success',
            'titulo': 'Gran quema de calorías',
            'descripcion': f'Has quemado {estadisticas["calorias_totales"]} calorías. ¡Excelente trabajo!',
            'accion': 'Ver Progreso',
            'icono': '🔥'
        })
    elif estadisticas['calorias_totales'] > 0:
        insights.append({
            'tipo': 'info',
            'titulo': 'Aumenta la intensidad',
            'descripcion': f'Con {estadisticas["calorias_totales"]} calorías quemadas, podrías aumentar la intensidad para mejores resultados.',
            'accion': 'Ver Recomendaciones',
            'icono': '⚡'
        })

    # Insight sobre volumen
    if estadisticas['volumen_total'] > 10000:
        insights.append({
            'tipo': 'success',
            'titulo': 'Volumen impresionante',
            'descripción': f'Has levantado {estadisticas["volumen_total"]} kg. ¡Eres una máquina!',
            'accion': 'Compartir Logro',
            'icono': '💪'
        })

    return insights


def generar_rankings(periodo):
    """Generar rankings de clientes"""

    fechas = calcular_fechas_periodo(periodo)

    # Ranking por entrenamientos de Liftin
    ranking_entrenamientos = Cliente.objects.filter(
        entrenorealizado__fuente_datos='liftin',
        entrenorealizado__fecha__gte=fechas['inicio'],
        entrenorealizado__fecha__lte=fechas['fin']
    ).annotate(
        total_entrenamientos=Count('entrenorealizado')
    ).order_by('-total_entrenamientos')[:5]

    # Ranking por calorías
    ranking_calorias = Cliente.objects.filter(
        entrenorealizado__fecha__gte=fechas['inicio'],
        entrenorealizado__fecha__lte=fechas['fin']
    ).annotate(
        total_calorias=Sum('entrenorealizado__calorias_quemadas')
    ).order_by('-total_calorias')[:5]

    # Ranking por volumen
    ranking_volumen = Cliente.objects.filter(
        entrenorealizado__fecha__gte=fechas['inicio'],
        entrenorealizado__fecha__lte=fechas['fin']
    ).annotate(
        total_volumen=Sum('entrenorealizado__volumen_total_kg')
    ).order_by('-total_volumen')[:5]

    return {
        'entrenamientos': ranking_entrenamientos,
        'calorias': ranking_calorias,
        'volumen': ranking_volumen
    }


def obtener_logros_recientes(cliente_seleccionado, limite=5):
    """
    btiene los logros más recientes del cliente CORREGIDO
    """
    try:
        if not LOGROS_DISPONIBLES or not cliente_seleccionado:
            return []

        # Obtener perfil
        perfil = PerfilGamificacion.objects.filter(
            cliente=cliente_seleccionado
        ).first()

        if not perfil:
            return []

        # Logros recientes CORREGIDO
        logros_recientes = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=True
        ).select_related('logro').order_by('-fecha_desbloqueo')[:limite]

        # Formatear datos para el template
        logros_formateados = []
        for logro_usuario in logros_recientes:
            logros_formateados.append({
                'nombre': logro_usuario.logro.nombre,
                'puntos': logro_usuario.logro.puntos_recompensa,
                'fecha_obtenido': logro_usuario.fecha_desbloqueo,
                'descripcion': logro_usuario.logro.descripcion,
            })

        return logros_formateados

    except Exception as e:
        logger.error(f"Error obteniendo logros recientes: {str(e)}")
        return []


def calcular_nivel_y_progreso(puntos_totales):
    """
    Calcula el nivel actual y progreso basado en puntos
    """
    # Sistema de niveles: cada 1000 puntos = 1 nivel
    nivel = max(1, puntos_totales // 1000 + 1)

    # Puntos en el nivel actual
    puntos_nivel_actual = puntos_totales % 1000
    puntos_siguiente_nivel = 1000

    # Progreso en porcentaje
    progreso = int((puntos_nivel_actual / puntos_siguiente_nivel) * 100)

    # Nombres de niveles
    nombres_niveles = {
        1: 'Principiante',
        2: 'Novato',
        3: 'Intermedio',
        4: 'Avanzado',
        5: 'Experto',
        6: 'Maestro',
        7: 'Leyenda',
    }

    nombre_nivel = nombres_niveles.get(nivel, 'Leyenda Suprema')

    return {
        'nivel': nivel,
        'nombre': nombre_nivel,
        'progreso': progreso,
        'puntos_nivel_actual': puntos_nivel_actual,
        'puntos_siguiente_nivel': puntos_siguiente_nivel,
    }


def calcular_estadisticas_principales(entrenamientos_base):
    """
    Calcula las estadísticas principales del dashboard
    """
    try:
        # Total de entrenamientos
        total_entrenamientos = entrenamientos_base.count()

        # Entrenamientos por fuente
        entrenamientos_liftin = entrenamientos_base.filter(fuente_datos='liftin').count()
        entrenamientos_manual = total_entrenamientos - entrenamientos_liftin

        # Calorías totales de Liftin
        calorias_totales = entrenamientos_base.filter(
            fuente_datos='liftin'
        ).aggregate(
            total=Sum('calorias_quemadas')
        )['total'] or 0

        return {
            'total_entrenamientos': total_entrenamientos,
            'entrenamientos_liftin': entrenamientos_liftin,
            'entrenamientos_manual': entrenamientos_manual,
            'calorias_totales': int(calorias_totales),
        }

    except Exception as e:
        logger.error(f"Error calculando estadísticas principales: {str(e)}")
        return {
            'total_entrenamientos': 0,
            'entrenamientos_liftin': 0,
            'entrenamientos_manual': 0,
            'calorias_totales': 0,
        }


def calcular_progreso_nivel(cliente_seleccionado):
    """Calcular progreso de nivel del cliente"""

    if not cliente_seleccionado:
        return {'nivel': 1, 'progreso': 0, 'puntos_siguiente': 1000}

    try:
        perfil = PerfilGamificacion.objects.get(cliente=cliente_seleccionado)
        nivel_actual = (perfil.puntos_totales // 1000) + 1
        puntos_en_nivel = perfil.puntos_totales % 1000
        puntos_siguiente_nivel = 1000 - puntos_en_nivel
        progreso_porcentaje = (puntos_en_nivel / 1000) * 100

        return {
            'nivel': nivel_actual,
            'progreso': round(progreso_porcentaje, 1),
            'puntos_siguiente': puntos_siguiente_nivel,
            'puntos_actuales': puntos_en_nivel,
            'puntos_totales': perfil.puntos_totales
        }
    except PerfilGamificacion.DoesNotExist:
        return {'nivel': 1, 'progreso': 0, 'puntos_siguiente': 1000}


def calcular_racha_actual(cliente_seleccionado):
    """Calcular racha actual de entrenamientos"""

    if not cliente_seleccionado:
        return {'dias': 0, 'record': 0}

    try:
        perfil = PerfilGamificacion.objects.get(cliente=cliente_seleccionado)
        return {
            'dias': perfil.racha_actual,
            'record': perfil.mejor_racha or 0
        }
    except PerfilGamificacion.DoesNotExist:
        return {'dias': 0, 'record': 0}


# ===================================
# VISTAS AJAX PARA FUNCIONALIDAD AVANZADA
# ===================================

@login_required
def dashboard_liftin_ajax_data(request):
    """Vista AJAX para actualizar datos del dashboard en tiempo real"""

    cliente_id = request.GET.get('cliente')
    periodo = request.GET.get('periodo', 'week')

    try:
        # Recalcular datos
        fechas = calcular_fechas_periodo(periodo)

        entrenamientos_base = EntrenoRealizado.objects.filter(
            fecha__gte=fechas['inicio'],
            fecha__lte=fechas['fin']
        )

        if cliente_id:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            entrenamientos_base = entrenamientos_base.filter(cliente=cliente)
        else:
            cliente = None

        estadisticas = calcular_estadisticas_principales(entrenamientos_base)
        datos_graficos = generar_datos_graficos(entrenamientos_base, periodo)

        return JsonResponse({
            'success': True,
            'estadisticas': estadisticas,
            'datos_graficos': datos_graficos,
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error en dashboard_liftin_ajax_data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def dashboard_liftin_export_data(request):
    """Vista para exportar datos del dashboard"""

    cliente_id = request.GET.get('cliente')
    periodo = request.GET.get('periodo', 'week')
    formato = request.GET.get('formato', 'json')  # json, csv, excel

    try:
        # Obtener datos
        fechas = calcular_fechas_periodo(periodo)
        entrenamientos_base = EntrenoRealizado.objects.filter(
            fecha__gte=fechas['inicio'],
            fecha__lte=fechas['fin']
        )

        if cliente_id:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            entrenamientos_base = entrenamientos_base.filter(cliente=cliente)

        # Preparar datos para exportación
        datos_exportacion = {
            'periodo': periodo,
            'fecha_inicio': fechas['inicio'].isoformat(),
            'fecha_fin': fechas['fin'].isoformat(),
            'estadisticas': calcular_estadisticas_principales(entrenamientos_base),
            'entrenamientos': list(entrenamientos_base.values(
                'fecha', 'cliente__nombre', 'rutina__nombre',
                'fuente_datos', 'calorias_quemadas', 'volumen_total_kg'
            )),
            'fecha_exportacion': timezone.now().isoformat()
        }

        if formato == 'json':
            response = JsonResponse(datos_exportacion)
            response['Content-Disposition'] = f'attachment; filename="dashboard_liftin_{periodo}.json"'
            return response

        # Aquí se pueden agregar otros formatos (CSV, Excel)

    except Exception as e:
        logger.error(f"Error en dashboard_liftin_export_data: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# FUNCIÓN PARA ACTIVAR LOGROS DE LIFTIN
# ============================================================================


def activar_logros_liftin(cliente, entrenamiento):
    """
    Activa logros automáticamente al importar entrenamientos de Liftin
    """
    try:
        if not LOGROS_DISPONIBLES:
            logger.warning("Sistema de logros no disponible")
            return

        logger.info(f"Activando logros para cliente: {cliente.nombre}")

        # Obtener o crear perfil de gamificación
        perfil, created = PerfilGamificacion.objects.get_or_create(
            cliente=cliente,
            defaults={
                'puntos_totales': 0,
                'nivel_actual': 1,
                'racha_actual': 0,
                'racha_maxima': 0,
            }
        )

        # Contar entrenamientos de Liftin del cliente
        entrenamientos_liftin = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fuente_datos='liftin'
        ).count()

        # Calorías totales quemadas
        calorias_totales = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fuente_datos='liftin'
        ).aggregate(total=Sum('calorias_quemadas'))['total'] or 0

        # Volumen total levantado
        volumen_total = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fuente_datos='liftin'
        ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0

        # Logros por entrenamientos de Liftin
        logros_entrenamientos = [
            (1, 'Primera Importación Liftin', 100),
            (5, 'Liftin Principiante', 200),
            (10, 'Liftin Intermedio', 300),
            (25, 'Liftin Avanzado', 500),
            (50, 'Liftin Master', 1000),
        ]

        for cantidad, nombre, puntos in logros_entrenamientos:
            if entrenamientos_liftin >= cantidad:
                crear_logro_si_no_existe(cliente, nombre, puntos, perfil)

        # Logros por calorías
        logros_calorias = [
            (300, 'Quemador Principiante', 100),
            (500, 'Quemador Intermedio', 200),
            (700, 'Quemador Avanzado', 300),
            (1000, 'Incinerador', 500),
        ]

        for cantidad, nombre, puntos in logros_calorias:
            if calorias_totales >= cantidad:
                crear_logro_si_no_existe(cliente, nombre, puntos, perfil)

        # Logros por volumen
        logros_volumen = [
            (5000, 'Levantador Principiante', 150),
            (10000, 'Levantador Intermedio', 250),
            (15000, 'Levantador Avanzado', 400),
            (20000, 'Titán del Hierro', 600),
        ]

        for cantidad, nombre, puntos in logros_volumen:
            if volumen_total >= cantidad:
                crear_logro_si_no_existe(cliente, nombre, puntos, perfil)

        # Actualizar racha
        actualizar_racha(cliente, perfil)

        # Guardar perfil actualizado
        perfil.save()

        logger.info(f"Logros activados exitosamente para {cliente.nombre}")

    except Exception as e:
        logger.error(f"Error activando logros: {str(e)}")


@login_required
def importar_liftin(request):
    """
    Importación básica de Liftin (versión simplificada)
    Redirige a la importación completa por ahora
    """
    # Por simplicidad, redirigir a la importación completa
    # Puedes personalizar esto más tarde si necesitas una versión más simple
    return importar_liftin_completo(request)


@login_required
def editar_entrenamiento_liftin(request, entrenamiento_id):
    """
    Vista para editar un entrenamiento de Liftin
    """
    entrenamiento = get_object_or_404(EntrenoRealizado, id=entrenamiento_id, fuente_datos='liftin')

    if request.method == 'POST':
        # Aquí iría la lógica del formulario cuando esté disponible
        # Por ahora, redirigir con mensaje
        messages.info(request, 'Funcionalidad de edición en desarrollo.')
        return redirect('entrenos:detalle_entrenamiento', entrenamiento_id=entrenamiento.id)

    # Datos básicos para el template
    context = {
        'entrenamiento': entrenamiento,
        'titulo': f'Editar Entrenamiento de {entrenamiento.cliente.nombre}',
    }

    return render(request, 'entrenos/editar_entrenamiento_liftin.html', context)


@login_required
def eliminar_entrenamiento_liftin(request, entrenamiento_id):
    """
    Vista para eliminar un entrenamiento de Liftin
    """
    entrenamiento = get_object_or_404(EntrenoRealizado, id=entrenamiento_id, fuente_datos='liftin')

    if request.method == 'POST':
        cliente_nombre = entrenamiento.cliente.nombre
        fecha = entrenamiento.fecha

        # Eliminar el entrenamiento
        entrenamiento.delete()

        messages.success(
            request,
            f'🗑️ Entrenamiento de {cliente_nombre} del {fecha.strftime("%d/%m/%Y")} eliminado exitosamente!'
        )

        return redirect('entrenos:dashboard_liftin')

    context = {
        'entrenamiento': entrenamiento,
        'titulo': f'Eliminar Entrenamiento de {entrenamiento.cliente.nombre}',
    }

    return render(request, 'entrenos/eliminar_entrenamiento_liftin.html', context)


@login_required
def estadisticas_liftin(request):
    """
    Página de estadísticas detalladas de Liftin
    """
    from django.db.models import Count, Sum, Avg, Max, Min

    entrenamientos_liftin = EntrenoRealizado.objects.filter(fuente_datos='liftin')

    # Estadísticas generales
    stats_generales = {
        'total_entrenamientos': entrenamientos_liftin.count(),
        'volumen_total': entrenamientos_liftin.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0,
        'calorias_total': entrenamientos_liftin.aggregate(Sum('calorias_quemadas'))['calorias_quemadas__sum'] or 0,
        'duracion_total': entrenamientos_liftin.aggregate(Sum('duracion_minutos'))['duracion_minutos__sum'] or 0,
        'ejercicios_total': entrenamientos_liftin.aggregate(Sum('numero_ejercicios'))['numero_ejercicios__sum'] or 0,
    }

    # Promedios
    stats_promedios = {
        'duracion_promedio': entrenamientos_liftin.aggregate(Avg('duracion_minutos'))['duracion_minutos__avg'] or 0,
        'calorias_promedio': entrenamientos_liftin.aggregate(Avg('calorias_quemadas'))['calorias_quemadas__avg'] or 0,
        'volumen_promedio': entrenamientos_liftin.aggregate(Avg('volumen_total_kg'))['volumen_total_kg__avg'] or 0,
        'ejercicios_promedio': entrenamientos_liftin.aggregate(Avg('numero_ejercicios'))['numero_ejercicios__avg'] or 0,
        'fc_promedio': entrenamientos_liftin.aggregate(Avg('frecuencia_cardiaca_promedio'))[
                           'frecuencia_cardiaca_promedio__avg'] or 0,
        'fc_maxima': entrenamientos_liftin.aggregate(Max('frecuencia_cardiaca_maxima'))[
                         'frecuencia_cardiaca_maxima__max'] or 0,
    }

    # Estadísticas por cliente
    stats_por_cliente = entrenamientos_liftin.values('cliente__nombre').annotate(
        total_entrenamientos=Count('id'),
        volumen_total=Sum('volumen_total_kg'),
        calorias_total=Sum('calorias_quemadas'),
        duracion_total=Sum('duracion_minutos')
    ).order_by('-total_entrenamientos')[:10]

    # Entrenamientos por mes (últimos 6 meses)
    entrenamientos_por_mes = []
    for i in range(6):
        fecha = timezone.now().date() - timedelta(days=30 * i)
        mes_inicio = fecha.replace(day=1)
        if i == 0:
            mes_fin = fecha
        else:
            mes_fin = (mes_inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        count = entrenamientos_liftin.filter(fecha__gte=mes_inicio, fecha__lte=mes_fin).count()
        volumen = entrenamientos_liftin.filter(fecha__gte=mes_inicio, fecha__lte=mes_fin).aggregate(
            Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0

        entrenamientos_por_mes.append({
            'mes': mes_inicio.strftime('%Y-%m'),
            'mes_nombre': mes_inicio.strftime('%B %Y'),
            'entrenamientos': count,
            'volumen': volumen
        })

    entrenamientos_por_mes.reverse()  # Mostrar del más antiguo al más reciente

    # Top rutinas más realizadas
    top_rutinas = entrenamientos_liftin.values('nombre_rutina_liftin').annotate(
        total=Count('id')
    ).exclude(nombre_rutina_liftin__isnull=True).order_by('-total')[:5]

    context = {
        'stats_generales': stats_generales,
        'stats_promedios': stats_promedios,
        'stats_por_cliente': stats_por_cliente,
        'entrenamientos_por_mes': entrenamientos_por_mes,
        'top_rutinas': top_rutinas,
        'title': 'Estadísticas de Liftin',
    }

    return render(request, 'entrenos/estadisticas_liftin.html', context)


# ============================================================================
# SISTEMA DE LOGROS AUTOMÁTICO PARA LIFTIN
# ============================================================================

# AGREGAR estas funciones a views_liftin.py

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

# Importar modelos de logros
try:
    from logros.models import (
        PerfilGamificacion, Logro, LogroUsuario, HistorialPuntos,
        TipoLogro, Notificacion
    )

    LOGROS_DISPONIBLES = True
except ImportError:
    LOGROS_DISPONIBLES = False


def activar_logros_liftin_completo(entrenamiento):
    """
    Sistema completo de activación de logros para entrenamientos de Liftin
    """
    if not LOGROS_DISPONIBLES:
        return []

    try:
        with transaction.atomic():
            # Obtener o crear perfil de gamificación
            perfil, created = PerfilGamificacion.objects.get_or_create(
                cliente=entrenamiento.cliente,
                defaults={
                    'puntos_totales': 0,
                    'entrenos_totales': 0,
                    'racha_actual': 0,
                    'racha_maxima': 0,
                }
            )

            # Actualizar estadísticas del perfil
            perfil.entrenos_totales += 1
            perfil.fecha_ultimo_entreno = timezone.now()

            # Calcular racha
            actualizar_racha_cliente(perfil, entrenamiento.fecha)

            perfil.save()

            # Lista de logros nuevos desbloqueados
            logros_nuevos = []

            # 1. LOGROS DE LIFTIN ESPECÍFICOS
            logros_nuevos.extend(verificar_logros_liftin(perfil, entrenamiento))

            # 2. LOGROS DE ENTRENAMIENTOS GENERALES
            logros_nuevos.extend(verificar_logros_entrenamientos(perfil))

            # 3. LOGROS DE CALORÍAS
            logros_nuevos.extend(verificar_logros_calorias(perfil, entrenamiento))

            # 4. LOGROS DE VOLUMEN
            logros_nuevos.extend(verificar_logros_volumen(perfil, entrenamiento))

            # 5. LOGROS DE DURACIÓN
            logros_nuevos.extend(verificar_logros_duracion(perfil, entrenamiento))

            # 6. LOGROS DE RACHA
            logros_nuevos.extend(verificar_logros_racha(perfil))

            # Actualizar nivel del usuario
            subio_nivel = perfil.actualizar_nivel()

            # Crear notificaciones para logros nuevos
            for logro in logros_nuevos:
                crear_notificacion_logro(perfil.cliente, logro)

            # Crear notificación de subida de nivel
            if subio_nivel:
                crear_notificacion_nivel(perfil.cliente, perfil.nivel_actual)

            return logros_nuevos

    except Exception as e:
        print(f"Error activando logros: {e}")
        return []


def verificar_logros_liftin(perfil, entrenamiento):
    """
    Verifica logros específicos de Liftin
    """
    logros_nuevos = []

    # Crear tipo de logro si no existe
    tipo_liftin, _ = TipoLogro.objects.get_or_create(
        nombre="Liftin",
        defaults={'categoria': 'especial', 'descripcion': 'Logros relacionados con la app Liftin'}
    )

    # Contar entrenamientos de Liftin del cliente
    entrenamientos_liftin = EntrenoRealizado.objects.filter(
        cliente=perfil.cliente,
        fuente_datos='liftin'
    ).count()

    # LOGRO: Primera importación de Liftin
    if entrenamientos_liftin == 1:
        logro, created = Logro.objects.get_or_create(
            nombre="Primera Importación Liftin",
            defaults={
                'descripcion': '¡Bienvenido a Liftin! Has importado tu primer entrenamiento desde la app.',
                'tipo': tipo_liftin,
                'puntos_recompensa': 100,
                'meta_valor': 1,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, 1)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 5 entrenamientos de Liftin
    if entrenamientos_liftin >= 5:
        logro, created = Logro.objects.get_or_create(
            nombre="Liftin Principiante",
            defaults={
                'descripcion': 'Has importado 5 entrenamientos desde Liftin. ¡Vas por buen camino!',
                'tipo': tipo_liftin,
                'puntos_recompensa': 200,
                'meta_valor': 5,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, entrenamientos_liftin)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 10 entrenamientos de Liftin
    if entrenamientos_liftin >= 10:
        logro, created = Logro.objects.get_or_create(
            nombre="Liftin Intermedio",
            defaults={
                'descripcion': '10 entrenamientos importados desde Liftin. ¡Eres constante!',
                'tipo': tipo_liftin,
                'puntos_recompensa': 300,
                'meta_valor': 10,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, entrenamientos_liftin)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 25 entrenamientos de Liftin
    if entrenamientos_liftin >= 25:
        logro, created = Logro.objects.get_or_create(
            nombre="Liftin Avanzado",
            defaults={
                'descripcion': '25 entrenamientos desde Liftin. ¡Eres un usuario experto!',
                'tipo': tipo_liftin,
                'puntos_recompensa': 500,
                'meta_valor': 25,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, entrenamientos_liftin)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 50 entrenamientos de Liftin
    if entrenamientos_liftin >= 50:
        logro, created = Logro.objects.get_or_create(
            nombre="Liftin Master",
            defaults={
                'descripcion': '50 entrenamientos desde Liftin. ¡Eres un verdadero maestro!',
                'tipo': tipo_liftin,
                'puntos_recompensa': 1000,
                'meta_valor': 50,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, entrenamientos_liftin)
        if logro_nuevo:
            logros_nuevos.append(logro)

    return logros_nuevos


def verificar_logros_entrenamientos(perfil):
    """
    Verifica logros generales de entrenamientos
    """
    logros_nuevos = []

    # Crear tipo de logro si no existe
    tipo_hito, _ = TipoLogro.objects.get_or_create(
        nombre="Hitos",
        defaults={'categoria': 'hito', 'descripcion': 'Logros por alcanzar hitos importantes'}
    )

    total_entrenamientos = perfil.entrenos_totales

    # LOGRO: 10 entrenamientos totales
    if total_entrenamientos >= 10:
        logro, created = Logro.objects.get_or_create(
            nombre="Primer Hito",
            defaults={
                'descripcion': '¡Has completado 10 entrenamientos! Un gran comienzo.',
                'tipo': tipo_hito,
                'puntos_recompensa': 150,
                'meta_valor': 10,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, total_entrenamientos)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 25 entrenamientos totales
    if total_entrenamientos >= 25:
        logro, created = Logro.objects.get_or_create(
            nombre="Constancia",
            defaults={
                'descripcion': '25 entrenamientos completados. ¡La constancia es clave!',
                'tipo': tipo_hito,
                'puntos_recompensa': 250,
                'meta_valor': 25,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, total_entrenamientos)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 50 entrenamientos totales
    if total_entrenamientos >= 50:
        logro, created = Logro.objects.get_or_create(
            nombre="Medio Centenar",
            defaults={
                'descripcion': '50 entrenamientos completados. ¡Vas por la mitad del camino!',
                'tipo': tipo_hito,
                'puntos_recompensa': 400,
                'meta_valor': 50,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, total_entrenamientos)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 100 entrenamientos totales
    if total_entrenamientos >= 100:
        logro, created = Logro.objects.get_or_create(
            nombre="Centenario",
            defaults={
                'descripcion': '¡100 entrenamientos! Eres oficialmente un atleta dedicado.',
                'tipo': tipo_hito,
                'puntos_recompensa': 750,
                'meta_valor': 100,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, total_entrenamientos)
        if logro_nuevo:
            logros_nuevos.append(logro)

    return logros_nuevos


def verificar_logros_calorias(perfil, entrenamiento):
    """
    Verifica logros relacionados con calorías quemadas
    """
    logros_nuevos = []

    if not entrenamiento.calorias_quemadas:
        return logros_nuevos

    # Crear tipo de logro si no existe
    tipo_calorias, _ = TipoLogro.objects.get_or_create(
        nombre="Calorías",
        defaults={'categoria': 'superacion', 'descripcion': 'Logros por quemar calorías'}
    )

    calorias = entrenamiento.calorias_quemadas

    # LOGRO: 300 calorías en un entrenamiento
    if calorias >= 300:
        logro, created = Logro.objects.get_or_create(
            nombre="Quemador Principiante",
            defaults={
                'descripcion': '¡Has quemado 300 calorías en un solo entrenamiento!',
                'tipo': tipo_calorias,
                'puntos_recompensa': 100,
                'meta_valor': 300,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, calorias)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 500 calorías en un entrenamiento
    if calorias >= 500:
        logro, created = Logro.objects.get_or_create(
            nombre="Quemador Intermedio",
            defaults={
                'descripcion': '¡500 calorías quemadas! Tu metabolismo está en llamas.',
                'tipo': tipo_calorias,
                'puntos_recompensa': 200,
                'meta_valor': 500,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, calorias)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 700 calorías en un entrenamiento
    if calorias >= 700:
        logro, created = Logro.objects.get_or_create(
            nombre="Quemador Avanzado",
            defaults={
                'descripcion': '¡700 calorías! Eres una máquina de quemar calorías.',
                'tipo': tipo_calorias,
                'puntos_recompensa': 300,
                'meta_valor': 700,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, calorias)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 1000 calorías en un entrenamiento
    if calorias >= 1000:
        logro, created = Logro.objects.get_or_create(
            nombre="Incinerador",
            defaults={
                'descripcion': '¡1000 calorías en un entrenamiento! Eres imparable.',
                'tipo': tipo_calorias,
                'puntos_recompensa': 500,
                'meta_valor': 1000,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, calorias)
        if logro_nuevo:
            logros_nuevos.append(logro)

    return logros_nuevos


def verificar_estado_logros(cliente_id):
    """
    Función para verificar el estado actual de los logros
    """
    try:
        if not LOGROS_DISPONIBLES:
            return {"error": "Sistema de logros no disponible"}

        cliente = Cliente.objects.get(id=cliente_id)
        perfil = PerfilGamificacion.objects.filter(cliente=cliente).first()

        if not perfil:
            return {"error": "No se encontró perfil de gamificación"}

        # Datos del perfil
        logros_desbloqueados = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=True
        )

        puntos_calculados = logros_desbloqueados.aggregate(
            total=Sum('logro__puntos_recompensa')
        )['total'] or 0

        entrenamientos_reales = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).count()

        return {
            "perfil_id": perfil.id,
            "puntos_en_perfil": perfil.puntos_totales,
            "puntos_calculados": puntos_calculados,
            "diferencia_puntos": puntos_calculados - perfil.puntos_totales,
            "logros_desbloqueados": logros_desbloqueados.count(),
            "entrenamientos_en_perfil": perfil.entrenos_totales,
            "entrenamientos_reales": entrenamientos_reales,
            "diferencia_entrenamientos": entrenamientos_reales - perfil.entrenos_totales,
            "racha_actual": perfil.racha_actual,
            "racha_maxima": perfil.racha_maxima,
            "logros_detalle": [
                {
                    "nombre": lu.logro.nombre,
                    "puntos": lu.logro.puntos_recompensa,
                    "fecha": lu.fecha_desbloqueo,
                    "completado": lu.completado
                }
                for lu in logros_desbloqueados
            ]
        }

    except Exception as e:
        logger.error(f"Error verificando estado de logros: {str(e)}")
        return {"error": str(e)}


def sincronizar_datos_logros(cliente_id):
    """
    Función para sincronizar datos de logros manualmente
    """
    try:
        if not LOGROS_DISPONIBLES:
            logger.warning("Sistema de logros no disponible")
            return False

        cliente = Cliente.objects.get(id=cliente_id)
        perfil = PerfilGamificacion.objects.filter(cliente=cliente).first()

        if not perfil:
            logger.warning(f"No se encontró perfil para cliente {cliente_id}")
            return False

        # Calcular puntos reales
        puntos_reales = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=True
        ).aggregate(
            total=Sum('logro__puntos_recompensa')
        )['total'] or 0

        # Contar entrenamientos reales
        entrenamientos_reales = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).count()

        # Actualizar perfil
        perfil.puntos_totales = puntos_reales
        perfil.entrenos_totales = entrenamientos_reales
        perfil.save()

        logger.info(
            f"Datos sincronizados para cliente {cliente_id}: {puntos_reales} puntos, {entrenamientos_reales} entrenamientos")
        return True

    except Exception as e:
        logger.error(f"Error sincronizando datos de logros: {str(e)}")
        return False


def verificar_logros_volumen(perfil, entrenamiento):
    """
    Verifica logros relacionados con volumen de entrenamiento
    """
    logros_nuevos = []

    if not entrenamiento.volumen_total_kg:
        return logros_nuevos

    # Crear tipo de logro si no existe
    tipo_volumen, _ = TipoLogro.objects.get_or_create(
        nombre="Volumen",
        defaults={'categoria': 'superacion', 'descripcion': 'Logros por volumen de entrenamiento'}
    )

    volumen = float(entrenamiento.volumen_total_kg)

    # LOGRO: 10,000 kg en un entrenamiento
    if volumen >= 10000:
        logro, created = Logro.objects.get_or_create(
            nombre="Levantador Principiante",
            defaults={
                'descripcion': '¡Has levantado 10,000 kg en un entrenamiento!',
                'tipo': tipo_volumen,
                'puntos_recompensa': 150,
                'meta_valor': 10000,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, volumen)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 15,000 kg en un entrenamiento
    if volumen >= 15000:
        logro, created = Logro.objects.get_or_create(
            nombre="Levantador Intermedio",
            defaults={
                'descripcion': '15,000 kg de volumen. ¡Tu fuerza está creciendo!',
                'tipo': tipo_volumen,
                'puntos_recompensa': 250,
                'meta_valor': 15000,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, volumen)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 20,000 kg en un entrenamiento
    if volumen >= 20000:
        logro, created = Logro.objects.get_or_create(
            nombre="Levantador Avanzado",
            defaults={
                'descripcion': '20,000 kg de volumen. ¡Eres increíblemente fuerte!',
                'tipo': tipo_volumen,
                'puntos_recompensa': 400,
                'meta_valor': 20000,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, volumen)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 25,000 kg en un entrenamiento
    if volumen >= 25000:
        logro, created = Logro.objects.get_or_create(
            nombre="Titán del Hierro",
            defaults={
                'descripcion': '25,000 kg de volumen. ¡Eres un verdadero titán!',
                'tipo': tipo_volumen,
                'puntos_recompensa': 600,
                'meta_valor': 25000,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, volumen)
        if logro_nuevo:
            logros_nuevos.append(logro)

    return logros_nuevos


def verificar_logros_duracion(perfil, entrenamiento):
    """
    Verifica logros relacionados con duración del entrenamiento
    """
    logros_nuevos = []

    if not entrenamiento.duracion_minutos:
        return logros_nuevos

    # Crear tipo de logro si no existe
    tipo_duracion, _ = TipoLogro.objects.get_or_create(
        nombre="Resistencia",
        defaults={'categoria': 'superacion', 'descripcion': 'Logros por duración de entrenamiento'}
    )

    duracion = entrenamiento.duracion_minutos

    # LOGRO: 60 minutos de entrenamiento
    if duracion >= 60:
        logro, created = Logro.objects.get_or_create(
            nombre="Hora de Poder",
            defaults={
                'descripcion': '¡Has entrenado durante una hora completa!',
                'tipo': tipo_duracion,
                'puntos_recompensa': 100,
                'meta_valor': 60,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, duracion)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 90 minutos de entrenamiento
    if duracion >= 90:
        logro, created = Logro.objects.get_or_create(
            nombre="Resistencia Superior",
            defaults={
                'descripcion': '90 minutos de entrenamiento. ¡Tu resistencia es impresionante!',
                'tipo': tipo_duracion,
                'puntos_recompensa': 200,
                'meta_valor': 90,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, duracion)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 120 minutos de entrenamiento
    if duracion >= 120:
        logro, created = Logro.objects.get_or_create(
            nombre="Maratonista del Gym",
            defaults={
                'descripcion': '2 horas de entrenamiento. ¡Eres incansable!',
                'tipo': tipo_duracion,
                'puntos_recompensa': 300,
                'meta_valor': 120,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, duracion)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 150 minutos de entrenamiento
    if duracion >= 150:
        logro, created = Logro.objects.get_or_create(
            nombre="Guerrero Incansable",
            defaults={
                'descripcion': '2.5 horas de entrenamiento. ¡Eres un verdadero guerrero!',
                'tipo': tipo_duracion,
                'puntos_recompensa': 500,
                'meta_valor': 150,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, duracion)
        if logro_nuevo:
            logros_nuevos.append(logro)

    return logros_nuevos


def verificar_logros_racha(perfil):
    """
    Verifica logros relacionados con rachas de entrenamiento
    """
    logros_nuevos = []

    # Crear tipo de logro si no existe
    tipo_racha, _ = TipoLogro.objects.get_or_create(
        nombre="Consistencia",
        defaults={'categoria': 'consistencia', 'descripcion': 'Logros por entrenar de forma consistente'}
    )

    racha = perfil.racha_actual

    # LOGRO: 3 días consecutivos
    if racha >= 3:
        logro, created = Logro.objects.get_or_create(
            nombre="Racha Inicial",
            defaults={
                'descripcion': '¡3 días consecutivos entrenando! Buen comienzo.',
                'tipo': tipo_racha,
                'puntos_recompensa': 100,
                'meta_valor': 3,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, racha)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 7 días consecutivos
    if racha >= 7:
        logro, created = Logro.objects.get_or_create(
            nombre="Semana Perfecta",
            defaults={
                'descripcion': '¡Una semana completa entrenando! Excelente consistencia.',
                'tipo': tipo_racha,
                'puntos_recompensa': 250,
                'meta_valor': 7,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, racha)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 14 días consecutivos
    if racha >= 14:
        logro, created = Logro.objects.get_or_create(
            nombre="Dos Semanas Imparable",
            defaults={
                'descripcion': '14 días consecutivos. ¡Tu disciplina es admirable!',
                'tipo': tipo_racha,
                'puntos_recompensa': 500,
                'meta_valor': 14,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, racha)
        if logro_nuevo:
            logros_nuevos.append(logro)

    # LOGRO: 30 días consecutivos
    if racha >= 30:
        logro, created = Logro.objects.get_or_create(
            nombre="Mes de Hierro",
            defaults={
                'descripcion': '¡30 días consecutivos! Has formado un hábito inquebrantable.',
                'tipo': tipo_racha,
                'puntos_recompensa': 1000,
                'meta_valor': 30,
            }
        )
        logro_nuevo = desbloquear_logro(perfil, logro, racha)
        if logro_nuevo:
            logros_nuevos.append(logro)

    return logros_nuevos


def desbloquear_logro(perfil, logro, progreso_actual):
    """
    Desbloquea un logro para el usuario si cumple los requisitos
    """
    try:
        # Verificar si ya tiene el logro
        logro_usuario, created = LogroUsuario.objects.get_or_create(
            perfil=perfil,
            logro=logro,
            defaults={
                'progreso_actual': progreso_actual,
                'completado': progreso_actual >= logro.meta_valor,
                'fecha_desbloqueo': timezone.now()
            }
        )

        # Si ya existía pero no estaba completado, verificar si ahora sí
        if not created and not logro_usuario.completado:
            logro_usuario.progreso_actual = max(logro_usuario.progreso_actual, progreso_actual)
            if logro_usuario.progreso_actual >= logro.meta_valor:
                logro_usuario.completado = True
                logro_usuario.fecha_desbloqueo = timezone.now()
                logro_usuario.save()

                # Agregar puntos al perfil
                perfil.puntos_totales += logro.puntos_recompensa
                perfil.save()

                # Crear registro en historial de puntos
                HistorialPuntos.objects.create(
                    perfil=perfil,
                    puntos=logro.puntos_recompensa,
                    logro=logro,
                    descripcion=f"Logro desbloqueado: {logro.nombre}"
                )

                return True

        # Si es nuevo y ya cumple los requisitos
        elif created and logro_usuario.completado:
            # Agregar puntos al perfil
            perfil.puntos_totales += logro.puntos_recompensa
            perfil.save()

            # Crear registro en historial de puntos
            HistorialPuntos.objects.create(
                perfil=perfil,
                puntos=logro.puntos_recompensa,
                logro=logro,
                descripcion=f"Logro desbloqueado: {logro.nombre}"
            )

            return True

        return False

    except Exception as e:
        print(f"Error desbloqueando logro {logro.nombre}: {e}")
        return False


def actualizar_racha(cliente, perfil):
    """
    Actualiza la racha de entrenamientos del cliente
    """
    try:
        # Obtener entrenamientos ordenados por fecha
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).order_by('-fecha')

        if not entrenamientos.exists():
            return

        # Calcular racha actual
        racha_actual = 1
        fecha_anterior = entrenamientos.first().fecha

        for entrenamiento in entrenamientos[1:]:
            diferencia = (fecha_anterior - entrenamiento.fecha).days
            if diferencia <= 2:  # Máximo 2 días de diferencia
                racha_actual += 1
                fecha_anterior = entrenamiento.fecha
            else:
                break

        # Actualizar perfil
        perfil.racha_actual = racha_actual
        if racha_actual > perfil.racha_maxima:
            perfil.racha_maxima = racha_actual

        # Logros por racha
        logros_racha = [
            (3, 'Racha Inicial', 100),
            (7, 'Semana Perfecta', 250),
            (14, 'Dos Semanas Imparable', 500),
            (30, 'Mes de Hierro', 1000),
        ]

        for cantidad, nombre, puntos in logros_racha:
            if racha_actual >= cantidad:
                crear_logro_si_no_existe(cliente, nombre, puntos, perfil)

    except Exception as e:
        logger.error(f"Error actualizando racha: {str(e)}")


def crear_logro_si_no_existe(cliente, nombre_logro, puntos, perfil):
    """
    Crea un logro si no existe ya para el cliente
    """
    try:
        # Verificar si el logro ya existe
        logro_existente = LogroUsuario.objects.filter(
            cliente=cliente,
            logro__nombre=nombre_logro
        ).exists()

        if not logro_existente:
            # Obtener o crear el logro
            logro, created = Logro.objects.get_or_create(
                nombre=nombre_logro,
                defaults={
                    'descripcion': f'Logro: {nombre_logro}',
                    'puntos': puntos,
                    'tipo': 'liftin',
                }
            )

            # Crear LogroUsuario
            LogroUsuario.objects.create(
                cliente=cliente,
                logro=logro,
                fecha_obtenido=timezone.now()
            )

            # Agregar puntos al perfil
            perfil.puntos_totales += puntos

            # Crear entrada en historial de puntos
            HistorialPuntos.objects.create(
                cliente=cliente,
                puntos=puntos,
                razon=f'Logro desbloqueado: {nombre_logro}',
                fecha=timezone.now()
            )

            logger.info(f"Logro creado: {nombre_logro} (+{puntos} puntos)")

    except Exception as e:
        logger.error(f"Error creando logro {nombre_logro}: {str(e)}")


def crear_notificacion_logro(cliente, logro):
    """
    Crea una notificación para un logro desbloqueado
    """
    try:
        Notificacion.objects.create(
            cliente=cliente,
            tipo='logro',
            titulo=f'¡Logro Desbloqueado!',
            mensaje=f'Has desbloqueado "{logro.nombre}": {logro.descripcion}',
            icono='🏆',
            url_accion='/entrenos/liftin/'
        )
    except Exception as e:
        print(f"Error creando notificación de logro: {e}")


def crear_notificacion_nivel(cliente, nivel):
    """
    Crea una notificación para subida de nivel
    """
    try:
        Notificacion.objects.create(
            cliente=cliente,
            tipo='nivel',
            titulo=f'¡Subiste de Nivel!',
            mensaje=f'¡Felicidades! Ahora eres {nivel.nombre} (Nivel {nivel.numero})',
            icono='⭐',
            url_accion='/entrenos/liftin/'
        )
    except Exception as e:
        print(f"Error creando notificación de nivel: {e}")


def obtener_logros_cliente(cliente):
    """
    Obtiene los logros del cliente para mostrar en el dashboard
    """
    try:
        perfil = PerfilGamificacion.objects.get(cliente=cliente)

        # Logros completados
        logros_completados = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=True
        ).select_related('logro', 'logro__tipo').order_by('-fecha_desbloqueo')[:5]

        # Logros en progreso
        logros_progreso = LogroUsuario.objects.filter(
            perfil=perfil,
            completado=False
        ).select_related('logro', 'logro__tipo').order_by('-progreso_actual')[:3]
        print("DEBUG - Puntos totales desde perfil:", perfil.puntos_totales)
        print("DEBUG - Contexto puntos_totales:", contexto.get('puntos_totales'))

        return {
            'perfil': perfil,
            'logros_completados': logros_completados,
            'logros_progreso': logros_progreso,
            'total_logros': logros_completados.count(),
            'puntos_totales': perfil.puntos_totales,
            'nivel_actual': perfil.nivel_actual,
            'racha_actual': perfil.racha_actual,
            'racha_maxima': perfil.racha_maxima,
        }

    except PerfilGamificacion.DoesNotExist:
        return {
            'perfil': None,
            'logros_completados': [],
            'logros_progreso': [],
            'total_logros': 0,
            'puntos_totales': 0,
            'nivel_actual': None,
            'racha_actual': 0,
            'racha_maxima': 0,
        }

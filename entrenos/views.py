from datetime import date, timedelta
from django.core.cache import cache
from django.views.decorators.http import require_POST, require_GET
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Avg, Count, Sum, Max, F, ExpressionWrapper, fields
from analytics.sistema_educacion_helms import agregar_educacion_a_plan

from collections import defaultdict
from analytics.monitor_adherencia import MonitorAdherencia, SesionEntrenamiento
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json
from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
from typing import Dict
from django.core.serializers.json import DjangoJSONEncoder
from .models import LogroDesbloqueado, EstadoEmocional
from decimal import Decimal
from .forms import ImportarLiftinCompletoForm
from joi.utils import generar_respuesta_joi
from .forms import (
    SeleccionClienteForm,
    DetalleEjercicioForm,
    FiltroClienteForm,
    BuscarEntrenamientosLiftinForm,  # ← AGREGAR ESTA LÍNEA
    ImportarLiftinCompletoForm,
    ImportarLiftinBasicoForm,
    ExportarDatosForm
)
from django.utils.dateformat import DateFormat
from django.utils.translation import gettext as _
from .utils.utils import normalizar_nombre_ejercicio, nombres_ejercicio_equivalentes, parsear_ejercicios_de_notas, parse_reps_and_series
from types import SimpleNamespace
import copy
from types import SimpleNamespace
from django.shortcuts import render, get_object_or_404
from .models import EntrenoRealizado, SerieRealizada
from django.db.models import Count, Avg, Sum
import json
from .forms import EjercicioForm
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from decimal import Decimal, getcontext
from datetime import date
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django import forms
from django.db.models import Avg, Sum
from django.db import transaction
from rutinas.models import Rutina, RutinaEjercicio
from clientes.models import Cliente
from .models import EntrenoRealizado, SerieRealizada, PlanPersonalizado
from .forms import SeleccionClienteForm, DetalleEjercicioForm, FiltroClienteForm
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import EntrenoRealizado, SerieRealizada
from django.db.models import Count, Avg, Sum

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging

# Gamificación
from .models import (
    SesionEntrenamiento as SesionGamificacion,
    RecordPersonal,
    LogroAutomatico,
    ClienteLogroAutomatico,
    DesafioSemanal,
    ProgresoDesafio
)
from .services.logros_service import LogrosService
from .services.records_service import RecordsService


# --- FUNCIÓN DE UTILIDAD PARA OBTENER DATOS DEL ENTRENAMIENTO ANTERIOR ---
def obtener_ultimo_peso_ejercicio(cliente_id, nombre_ejercicio, fecha_actual):
    """
    Busca el último registro de un ejercicio específico de un cliente
    antes de la fecha actual (o en el mismo día si no hay datos previos).

    Busca en los modelos EjercicioRealizado y EjercicioLiftinDetallado.

    Retorna un diccionario con 'peso', 'fecha', 'series', 'repeticiones' y 'volumen',
    o None si no se encuentra.
    """
    from clientes.models import Cliente
    from .models import EntrenoRealizado, EjercicioRealizado, EjercicioLiftinDetallado
    from django.db.models import Q

    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        return None

    nombre_normalizado = normalizar_nombre_ejercicio(nombre_ejercicio)

    # Construir variantes de nombre para filtro DB (primera palabra y nombre completo)
    palabras = nombre_ejercicio.strip().split()
    nombre_icontains = palabras[0] if palabras else nombre_ejercicio

    # --- OPCIÓN 1: Buscar en EjercicioRealizado ---
    # Filtro por nombre a nivel de BD (icontains sobre la primera palabra) para evitar
    # cargar todos los ejercicios del cliente en Python.
    # Incluimos ejercicios con peso >= 0 (el filtro peso>0 excluía ejercicios de peso corporal).
    candidatos = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente,
        entreno__fecha__lte=fecha_actual,  # lte para incluir mismo día
        nombre_ejercicio__icontains=nombre_icontains,
    ).select_related('entreno').order_by('-entreno__fecha')

    for ej in candidatos:
        if nombres_ejercicio_equivalentes(ej.nombre_ejercicio, nombre_ejercicio):
            peso = round(float(ej.peso_kg or 0), 2)
            series = ej.series or 1
            repeticiones = ej.repeticiones or 0
            volumen = round(peso * series * repeticiones, 2)
            return {
                'peso': peso,
                'fecha': ej.entreno.fecha,
                'series': series,
                'repeticiones': repeticiones,
                'volumen': volumen
            }

    # --- OPCIÓN 2: Buscar en EjercicioLiftinDetallado ---
    candidatos_liftin = EjercicioLiftinDetallado.objects.filter(
        entreno__cliente=cliente,
        entreno__fecha__lte=fecha_actual,
        nombre_ejercicio__icontains=nombre_icontains,
    ).select_related('entreno').order_by('-entreno__fecha')

    for ej in candidatos_liftin:
        if nombres_ejercicio_equivalentes(ej.nombre_ejercicio, nombre_ejercicio):
            peso = round(float(ej.peso_kg or 0), 2)
            series = ej.series_realizadas or 1
            if ej.repeticiones_min and ej.repeticiones_max:
                repeticiones = (ej.repeticiones_min + ej.repeticiones_max) // 2
            elif ej.repeticiones_min:
                repeticiones = ej.repeticiones_min
            else:
                repeticiones = 0
            volumen = round(peso * series * repeticiones, 2)
            return {
                'peso': peso,
                'fecha': ej.entreno.fecha,
                'series': series,
                'repeticiones': repeticiones,
                'volumen': volumen
            }

    # --- OPCIÓN 3: Buscar en notas_liftin (fallback) ---
    entrenos_anteriores = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__lte=fecha_actual,
    ).exclude(
        notas_liftin__isnull=True
    ).exclude(
        notas_liftin=''
    ).order_by('-fecha')

    for entreno in entrenos_anteriores:
        try:
            ejercicios = parsear_ejercicios_de_notas(entreno.notas_liftin)
            for e in ejercicios:
                if nombres_ejercicio_equivalentes(e.get("nombre", ""), nombre_ejercicio):
                    peso_str = str(e.get("peso", "")).replace(",", ".")
                    try:
                        peso = round(float(peso_str), 2)
                        if peso > 0:
                            reps_str = e.get("repeticiones", "")
                            series, repeticiones = parse_reps_and_series(reps_str)
                            volumen = round(peso * series * repeticiones, 2)
                            return {
                                'peso': peso,
                                'fecha': entreno.fecha,
                                'series': series,
                                'repeticiones': repeticiones,
                                'volumen': volumen
                            }
                    except ValueError:
                        continue
        except Exception:
            continue

    return None  # No se encontró un registro anterior válido


# -----------------------------------------------------

# Archivo: entrenos/views.py - VISTAS PARA LIFTIN

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
from .gamificacion_service import EntrenamientoGamificacionService
from .models import EntrenoRealizado, DatosLiftinDetallados
# from .forms import ImportarLiftinForm, BuscarEntrenamientosForm, ExportarDatosForm
from clientes.models import Cliente

from django.db.models import Avg

from django.shortcuts import render
from entrenos.models import DetalleEjercicioRealizado

from django.shortcuts import render
from entrenos.models import EntrenoRealizado
from entrenos.utils.utils import parse_reps_and_series  # crea este archivo o añade allí la función

from django.shortcuts import render
from .models import EntrenoRealizado
from entrenos.utils.utils import parsear_ejercicios_de_notas, normalizar_nombre_ejercicio, parse_reps_and_series

from collections import Counter
from django.core.paginator import Paginator

from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from analytics.planificador import PlanificadorAvanzadoHelms, generar_contexto_calendario
from analytics.views import CalculadoraEjerciciosTabla
from analytics.utils import estimar_1rm, estimar_1rm_con_rpe


def detalle_ejercicio(request, nombre):
    registros = []
    nombre_normalizado = normalizar_nombre_ejercicio(nombre)

    entrenos = EntrenoRealizado.objects.exclude(notas_liftin__isnull=True).exclude(notas_liftin='')

    for entreno in entrenos:
        ejercicios = parsear_ejercicios_de_notas(entreno.notas_liftin)
        for e in ejercicios:
            if normalizar_nombre_ejercicio(e["nombre"]) == nombre_normalizado:
                e["fecha"] = entreno.fecha
                e["cliente"] = getattr(entreno.cliente, 'nombre', str(entreno.cliente))
                try:
                    e["peso_float"] = float(str(e["peso"]).replace(",", "."))
                except:
                    e["peso_float"] = None
                registros.append(e)

    registros = sorted(registros, key=lambda x: x["fecha"])

    return render(request, "entrenos/detalle_ejercicio.html", {
        "nombre": nombre_normalizado,
        "registros": registros
    })


def ejercicios_realizados_view(request):
    filtro = request.GET.get('filtro')
    if filtro:
        filtro = filtro.strip().title()

    ejercicios = []
    contador = Counter()

    entrenos = EntrenoRealizado.objects.exclude(notas_liftin__isnull=True).exclude(notas_liftin='').order_by('-fecha')

    for entreno in entrenos:
        ejercicios_parsed = parsear_ejercicios_de_notas(entreno.notas_liftin)
        for e in ejercicios_parsed:
            e['fecha'] = entreno.fecha
            e['cliente'] = getattr(entreno.cliente, 'nombre', str(entreno.cliente))
            if not filtro or e['nombre'] == filtro:
                ejercicios.append(e)
            nombre_normalizado = e['nombre'].strip().title()  # Ejemplo: "press banca" → "Press Banca"
            e['nombre'] = nombre_normalizado
            contador[nombre_normalizado] += 1

    ejercicios_mas_realizados = sorted(
        [{'nombre': nombre, 'veces': veces} for nombre, veces in contador.items()],
        key=lambda x: x['veces'],
        reverse=True
    )

    # ✅ paginar todos los ejercicios (10 por página)
    paginator = Paginator(ejercicios, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # === Tabla de mayor peso por ejercicio ===
    def convertir_peso(p):
        try:
            return float(str(p).replace(",", "."))
        except:
            return None

    # Clonar para evitar modificar el original
    ejercicios_para_max = ejercicios.copy()
    for e in ejercicios_para_max:
        e["peso_float"] = convertir_peso(e["peso"])

    # Filtrar válidos y quedarnos con el de mayor peso por nombre
    mayores_por_ejercicio = {}
    for e in ejercicios_para_max:
        if e["peso_float"] is None:
            continue
        nombre = e["nombre"]
        if nombre not in mayores_por_ejercicio or e["peso_float"] > mayores_por_ejercicio[nombre]["peso_float"]:
            mayores_por_ejercicio[nombre] = e

    mayores_list = sorted(mayores_por_ejercicio.values(), key=lambda x: x["nombre"])

    return render(request, 'entrenos/tabla_ejercicios.html', {
        'ejercicios': page_obj,
        'page_obj': page_obj,
        'ejercicios_mas_realizados': ejercicios_mas_realizados,
        'filtro': filtro,
        'mayores_por_ejercicio': mayores_list,
    })


# en entrenos/views.py (o donde esté la vista)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import EntrenoRealizado, Cliente
from logros.utils import obtener_datos_logros
from django.db.models import Sum, Avg, Count


def dashboard_liftin(request, cliente_id):  # <-- Acepta el ID desde la URL
    """
    Dashboard de entrenamientos para un cliente específico.
    """
    # 1. Obtenemos el cliente usando el ID de la URL.
    cliente_seleccionado = get_object_or_404(Cliente, id=cliente_id)

    # 2. Creamos un QuerySet base FILTRADO por este cliente.
    entrenamientos_qs = EntrenoRealizado.objects.filter(cliente=cliente_seleccionado)

    # 3. Calculamos TODAS las estadísticas y listas a partir del queryset ya filtrado.
    estadisticas_generales = entrenamientos_qs.aggregate(
        total_entrenamientos=Count('id'),
        calorias_totales=Sum('calorias_quemadas'),
        volumen_total=Sum('volumen_total_kg'),
        duracion_promedio=Avg('duracion_minutos')
    )

    entrenamientos_recientes = entrenamientos_qs.select_related(
        'cliente', 'rutina'
    ).order_by('-fecha')[:10]

    logros = obtener_datos_logros(cliente_seleccionado)

    context = {
        'cliente': cliente_seleccionado,
        'estadisticas': estadisticas_generales,
        'entrenamientos_recientes': entrenamientos_recientes,
        'logros': logros
    }

    return render(request, 'entrenos/dashboard_liftin.html', context)


from rutinas.models import Programa, Rutina


def importar_liftin(request):
    if request.method == 'POST':
        form = ImportarLiftinForm(request.POST)
        if form.is_valid():
            entrenamiento = form.save(commit=False)

            # Asegurar que haya un programa por defecto
            programa, creado = Programa.objects.get_or_create(nombre="Importado de Liftin")

            # Crear una rutina asociada si es necesario
            rutina = Rutina.objects.create(
                nombre=form.cleaned_data['nombre_rutina_liftin'],
                cliente=form.cleaned_data['cliente'],
                programa=programa,
                orden=1
            )

            entrenamiento.rutina = rutina
            entrenamiento.save()

            messages.success(request, "Entrenamiento importado exitosamente desde Liftin.")
            return redirect('entrenos:dashboard_liftin')
    else:
        form = ImportarLiftinCompletoForm()

    return render(request, 'entrenos/importar_liftin.html', {'form': form})


def lista_entrenamientos(request):
    """
    Vista para listar entrenamientos con búsqueda
    """
    # CORRECCIÓN: Usar el formulario correcto
    form = BuscarEntrenamientosLiftinForm(request.GET or None)

    entrenamientos = EntrenoRealizado.objects.all().order_by('-fecha')

    if form and form.is_valid():
        # Aplicar filtros del formulario
        if form.cleaned_data.get('cliente'):
            entrenamientos = entrenamientos.filter(cliente=form.cleaned_data['cliente'])

        if form.cleaned_data.get('fuente_datos'):
            entrenamientos = entrenamientos.filter(fuente_datos=form.cleaned_data['fuente_datos'])

        if form.cleaned_data.get('fecha_desde'):
            entrenamientos = entrenamientos.filter(fecha__gte=form.cleaned_data['fecha_desde'])

        if form.cleaned_data.get('fecha_hasta'):
            entrenamientos = entrenamientos.filter(fecha__lte=form.cleaned_data['fecha_hasta'])

    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(entrenamientos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'form': form,
        'page_obj': page_obj,
        'entrenamientos': page_obj,
        'title': 'Lista de Entrenamientos'
    }

    return render(request, 'entrenos/lista_entrenamientos.html', context)


def detalle_entrenamiento(request, entrenamiento_id):
    """
    Vista detallada de un entrenamiento
    """
    entrenamiento = get_object_or_404(EntrenoRealizado, id=entrenamiento_id)

    # Obtener datos adicionales de Liftin si existen
    datos_liftin = None
    if hasattr(entrenamiento, 'datos_liftin'):
        datos_liftin = entrenamiento.datos_liftin

    context = {
        'entrenamiento': entrenamiento,
        'datos_liftin': datos_liftin,
    }

    return render(request, 'entrenos/detalle_entrenamiento.html', context)


def estadisticas_liftin(request):
    """
    Vista para mostrar estadísticas específicas de Liftin
    """
    from django.db.models import Count, Sum, Avg

    # CORRECCIÓN: Usar nombres de campos correctos
    entrenamientos_liftin = EntrenoRealizado.objects.filter(fuente_datos='liftin')
    entrenamientos_manual = EntrenoRealizado.objects.filter(fuente_datos='manual')

    # Estadísticas básicas
    stats = {
        'total_liftin': entrenamientos_liftin.count(),
        'total_manual': entrenamientos_manual.count(),
        'total_general': EntrenoRealizado.objects.count(),
    }

    # Estadísticas de Liftin
    stats_liftin = entrenamientos_liftin.aggregate(
        volumen_total=Sum('volumen_total_kg'),
        calorias_total=Sum('calorias_quemadas'),
        duracion_promedio=Avg('duracion_minutos'),
        ejercicios_promedio=Avg('numero_ejercicios'),
        fc_promedio=Avg('frecuencia_cardiaca_promedio')
    )

    # Estadísticas por cliente
    stats_por_cliente = entrenamientos_liftin.values('cliente__nombre').annotate(
        total=Count('id'),
        volumen=Sum('volumen_total_kg')
    ).order_by('-total')[:10]

    # Entrenamientos recientes
    entrenamientos_recientes = entrenamientos_liftin.order_by('-fecha', '-hora_inicio')[:10]

    context = {
        'stats': stats,
        'stats_liftin': stats_liftin,
        'stats_por_cliente': stats_por_cliente,
        'entrenamientos_recientes': entrenamientos_recientes,
        'title': 'Estadísticas de Liftin'
    }

    return render(request, 'entrenos/estadisticas_liftin.html', context)


def exportar_datos(request):
    """
    Vista para exportar datos de entrenamientos
    """
    if request.method == 'POST':
        form = ExportarDatosForm(request.POST)
        if form.is_valid():
            # Construir queryset basado en filtros
            entrenamientos = EntrenoRealizado.objects.select_related('cliente', 'rutina')

            # Aplicar filtros
            incluir = form.cleaned_data['incluir']
            if incluir == 'solo_liftin':
                entrenamientos = entrenamientos.filter(fuente_datos='liftin')
            elif incluir == 'solo_manual':
                entrenamientos = entrenamientos.filter(fuente_datos='manual')

            if form.cleaned_data['cliente']:
                entrenamientos = entrenamientos.filter(cliente=form.cleaned_data['cliente'])

            if form.cleaned_data['fecha_desde']:
                entrenamientos = entrenamientos.filter(fecha__gte=form.cleaned_data['fecha_desde'])

            if form.cleaned_data['fecha_hasta']:
                entrenamientos = entrenamientos.filter(fecha__lte=form.cleaned_data['fecha_hasta'])

            # Exportar según formato
            formato = form.cleaned_data['formato']
            if formato == 'csv':
                return exportar_csv(entrenamientos)
            elif formato == 'json':
                return exportar_json(entrenamientos)
    else:
        form = ExportarDatosForm()

    context = {
        'form': form,
    }

    return render(request, 'entrenos/exportar_datos.html', context)


def exportar_csv(entrenamientos):
    """
    Exporta entrenamientos a formato CSV
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="entrenamientos_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)

    # Cabeceras
    writer.writerow([
        'Cliente',
        'Rutina',
        'Fecha',
        'Fuente',
        'Duración (min)',
        'Calorías',
        'FC Promedio',
        'FC Máxima',
        'Notas'
    ])

    # Datos
    for entreno in entrenamientos:
        writer.writerow([
            entreno.cliente.nombre,
            entreno.rutina.nombre,
            entreno.fecha.strftime('%Y-%m-%d'),
            entreno.get_fuente_datos_display(),
            entreno.duracion_minutos or '',
            entreno.calorias_quemadas or '',
            entreno.frecuencia_cardiaca_promedio or '',
            entreno.frecuencia_cardiaca_maxima or '',
            entreno.notas_liftin or ''
        ])

    return response


def exportar_json(entrenamientos):
    """
    Exporta entrenamientos a formato JSON
    """
    data = []

    for entreno in entrenamientos:
        data.append({
            'id': entreno.id,
            'cliente': entreno.cliente.nombre,
            'rutina': entreno.rutina.nombre,
            'fecha': entreno.fecha.isoformat(),
            'fuente_datos': entreno.fuente_datos,
            'duracion_minutos': entreno.duracion_minutos,
            'calorias_quemadas': entreno.calorias_quemadas,
            'frecuencia_cardiaca_promedio': entreno.frecuencia_cardiaca_promedio,
            'frecuencia_cardiaca_maxima': entreno.frecuencia_cardiaca_maxima,
            'notas_liftin': entreno.notas_liftin,
            'liftin_workout_id': entreno.liftin_workout_id,
            'fecha_importacion': entreno.fecha_importacion.isoformat() if entreno.fecha_importacion else None
        })

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="entrenamientos_{timezone.now().strftime("%Y%m%d")}.json"'

    return response


def api_stats_dashboard(request):
    """
    API endpoint para obtener estadísticas para el dashboard
    """
    # Datos para gráficos de los últimos 30 días
    fecha_limite = timezone.now().date() - timedelta(days=30)

    # Entrenamientos por día
    entrenamientos_por_dia = []
    for i in range(30):
        fecha = fecha_limite + timedelta(days=i)
        manual = EntrenoRealizado.objects.filter(fecha=fecha, fuente_datos='manual').count()
        liftin = EntrenoRealizado.objects.filter(fecha=fecha, fuente_datos='liftin').count()

        entrenamientos_por_dia.append({
            'fecha': fecha.isoformat(),
            'manual': manual,
            'liftin': liftin,
            'total': manual + liftin
        })

    # Distribución por fuente
    distribucion = {
        'manual': EntrenoRealizado.objects.filter(fuente_datos='manual').count(),
        'liftin': EntrenoRealizado.objects.filter(fuente_datos='liftin').count()
    }

    data = {
        'entrenamientos_por_dia': entrenamientos_por_dia,
        'distribucion': distribucion
    }

    return JsonResponse(data)


def entrenos_filtrados(request, rango):
    """
    Filtra los entrenamientos realizados según diferentes rangos temporales.

    Args:
        request: Objeto HttpRequest
        rango: Cadena que indica el rango temporal ('hoy', 'semana', 'mes', 'anio', o cualquier otro valor para todos)

    Returns:
        HttpResponse con la plantilla renderizada
    """
    hoy = date.today()

    if rango == "hoy":
        queryset = EntrenoRealizado.objects.filter(fecha=hoy)
        titulo = "Entrenamientos de hoy"
    elif rango == "semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        queryset = EntrenoRealizado.objects.filter(fecha__gte=inicio)
        titulo = "Entrenamientos de esta semana"
    elif rango == "mes":
        inicio = hoy.replace(day=1)
        queryset = EntrenoRealizado.objects.filter(fecha__gte=inicio)
        titulo = "Entrenamientos de este mes"
    elif rango == "anio":
        inicio = hoy.replace(month=1, day=1)
        queryset = EntrenoRealizado.objects.filter(fecha__gte=inicio)
        titulo = "Entrenamientos de este año"
    else:
        queryset = EntrenoRealizado.objects.all()
        titulo = "Todos los entrenamientos"

    queryset = queryset.select_related('cliente', 'rutina').order_by('-fecha')

    return render(request, 'entrenos/entrenos_filtrados.html', {
        'entrenos': queryset,
        'titulo': titulo
    })


def historial_entrenos(request):
    """
    Muestra un historial de entrenamientos con posibilidad de filtrar por cliente.

    Args:
        request: Objeto HttpRequest

    Returns:
        HttpResponse con la plantilla renderizada
    """
    from django.core.paginator import Paginator

    form = FiltroClienteForm(request.GET or None)
    entrenos = EntrenoRealizado.objects.select_related('cliente', 'rutina').prefetch_related('series__ejercicio')

    if form.is_valid() and form.cleaned_data['cliente']:
        cliente = form.cleaned_data['cliente']
        entrenos = entrenos.filter(cliente=cliente)
    else:
        cliente = None

    entrenos = entrenos.order_by('-fecha')

    # Agregar atributo .perfecto a cada entreno
    for entreno in entrenos:
        total = entreno.series.count()
        completadas = entreno.series.filter(completado=True).count()
        entreno.perfecto = total > 0 and completadas == total

        # Formatear fecha como "26 de mayo de 2025"
        df = DateFormat(entreno.fecha)
        entreno.fecha_formateada = df.format("j \\d\\e F \\d\\e Y")
    # Paginación
    paginator = Paginator(entrenos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'entrenos/vista_historial_detallado.html', {
        'entrenos': page_obj,
        'form': form,
        'cliente': cliente,
        'page_obj': page_obj,
    })


def crear_entreno(entreno, ejercicios_forms, request, cliente, rutina):
    """
    Crea un nuevo entrenamiento con sus series realizadas.

    Args:
        entreno: Objeto EntrenoRealizado
        ejercicios_forms: Lista de tuplas (ejercicio, form)
        request: Objeto HttpRequest
        cliente: Objeto Cliente
        rutina: Objeto Rutina

    Returns:
        None
    """
    for ejercicio, _ in ejercicios_forms:
        i = 1
        while True:
            reps_key = f"{ejercicio.id}_reps_{i}"
            peso_key = f"{ejercicio.id}_peso_{i}"
            completado_key = f"{ejercicio.id}_completado_{i}"

            try:
                reps = request.POST.get(reps_key)
                peso = request.POST.get(peso_key)
                completado = request.POST.get(completado_key) == "1"

                if reps is None or peso is None:
                    break

                if reps.strip() == '' and peso.strip() == '':
                    i += 1
                    continue

                SerieRealizada.objects.create(
                    entreno=entreno,
                    ejercicio=ejercicio,
                    serie_numero=i,
                    repeticiones=int(reps),
                    peso_kg=float(peso.replace(',', '.')),
                    completado=completado,
                    rpe_real=rpe_real
                )
                print(
                    f"Serie creada: {ejercicio.nombre}, Serie {i}, Reps: {reps}, Peso: {peso}, Completado: {completado}")
            except (ValueError, TypeError) as e:
                messages.error(request, f"⚠️ Error al procesar serie {i} de {ejercicio.nombre}: {str(e)}")
                break

            i += 1


from django.db import transaction
from decimal import Decimal

from datetime import date
from django.core.serializers.json import DjangoJSONEncoder

from decimal import Decimal, getcontext
from datetime import date
from django.core.serializers.json import DjangoJSONEncoder

from decimal import Decimal, getcontext
from django.db import transaction

from decimal import Decimal, getcontext
from django.db import transaction


def adaptar_plan_personalizado(entreno, ejercicios_forms, cliente, rutina, request):
    """
    Versión final con reinicio de contador después de reducción
    """
    # Configurar precisión decimal
    getcontext().prec = 8

    with transaction.atomic():
        try:
            cliente_real = Cliente.objects.get(id=entreno.cliente_id)
            print(f"\nProcesando cliente: {cliente_real.nombre}")
        except Exception as e:
            print(f"❌ Error al obtener cliente: {str(e)}")
            return

        # Inicializar estructuras de seguimiento
        session_key = f'adaptacion_{cliente_real.id}_{rutina.id}'
        if session_key not in request.session:
            request.session[session_key] = {}

        datos_adaptacion = request.session[session_key]

        for ejercicio, _ in ejercicios_forms:
            try:
                ejercicio_obj = ejercicio if isinstance(ejercicio, Ejercicio) else Ejercicio.objects.get(id=ejercicio)
                ejercicio_id = str(ejercicio_obj.id)

                print(f"\n--- Procesando ejercicio: {ejercicio_obj.nombre} ---")

                # Obtener o inicializar registro para este ejercicio
                if ejercicio_id not in datos_adaptacion:
                    datos_adaptacion[ejercicio_id] = {
                        'nombre': ejercicio_obj.nombre,
                        'fallos_consecutivos': 0,
                        'historial': []
                    }

                registro = datos_adaptacion[ejercicio_id]

                # Obtener configuración actual del ejercicio
                try:
                    asignacion = RutinaEjercicio.objects.get(
                        rutina=rutina,
                        ejercicio=ejercicio_obj
                    )
                    plan, created = PlanPersonalizado.objects.get_or_create(
                        cliente=cliente_real,
                        ejercicio=ejercicio_obj,
                        rutina=rutina,
                        defaults={
                            'repeticiones_objetivo': asignacion.repeticiones,
                            'peso_objetivo': Decimal(str(asignacion.peso_kg))
                        }
                    )
                except RutinaEjercicio.DoesNotExist:
                    print(f"No hay asignación para {ejercicio_obj.nombre} en esta rutina")
                    continue

                # Guardar peso anterior antes de cualquier modificación
                peso_anterior = Decimal(str(plan.peso_objetivo))
                print(f"Peso actual: {float(peso_anterior)}kg")
                print(f"Fallos consecutivos actuales: {registro['fallos_consecutivos']}")

                # Analizar rendimiento
                series = SerieRealizada.objects.filter(
                    entreno=entreno,
                    ejercicio=ejercicio_obj
                )
                total_series = series.count()

                if total_series == 0:
                    print("No hay series registradas")
                    continue

                series_completadas = sum(
                    1 for s in series
                    if s.completado and s.repeticiones >= plan.repeticiones_objetivo
                )
                porcentaje_exito = float(series_completadas) / float(total_series)
                fue_exitoso = porcentaje_exito >= 0.8

                # Calcular peso promedio del entreno actual
                peso_promedio = sum(Decimal(str(s.peso_kg)) for s in series) / Decimal(str(total_series))
                print(f"Peso promedio en este entreno: {float(peso_promedio)}kg")

                # Actualizar historial de rendimiento
                registro['historial'].append({
                    'fecha': entreno.fecha.isoformat(),
                    'porcentaje_exito': porcentaje_exito,
                    'peso_promedio': float(peso_promedio),
                    'fue_exitoso': fue_exitoso
                })
                registro['historial'] = registro['historial'][-3:]  # Mantener solo últimos 3

                # Lógica de adaptación
                if fue_exitoso:
                    # Aumentar peso y reiniciar contador
                    nuevo_peso = (peso_anterior * Decimal('1.10')).quantize(Decimal('0.1'))
                    plan.peso_objetivo = nuevo_peso
                    plan.save()
                    registro['fallos_consecutivos'] = 0  # Reiniciar contador

                    print(f"✅ ÉXITO - Peso aumentado a {float(nuevo_peso)}kg | Contador reiniciado")

                    if 'adaptaciones_positivas' not in request.session:
                        request.session['adaptaciones_positivas'] = []
                    request.session['adaptaciones_positivas'].append({
                        'ejercicio_id': ejercicio_obj.id,
                        'nombre': ejercicio_obj.nombre,
                        'peso_anterior': float(peso_anterior),
                        'nuevo_peso': float(nuevo_peso)
                    })
                else:
                    # Incrementar contador de fallos
                    registro['fallos_consecutivos'] += 1
                    print(f"❌ FALLO - Conteo actual: {registro['fallos_consecutivos']}/3")

                    # Verificar si aplica reducción
                    if registro['fallos_consecutivos'] >= 3:
                        nuevo_peso = (peso_promedio * Decimal('0.90')).quantize(Decimal('0.1'))
                        plan.peso_objetivo = nuevo_peso
                        plan.save()
                        registro['fallos_consecutivos'] = 0  # Reiniciar contador después de reducción

                        print(f"🔽 REDUCCIÓN APLICADA - Nuevo peso: {float(nuevo_peso)}kg | Contador reiniciado")

                        if 'adaptaciones_negativas' not in request.session:
                            request.session['adaptaciones_negativas'] = []
                        request.session['adaptaciones_negativas'].append({
                            'ejercicio_id': ejercicio_obj.id,
                            'nombre': ejercicio_obj.nombre,
                            'peso_anterior': float(peso_promedio),
                            'nuevo_peso': float(nuevo_peso),
                            'razon': '3 fallos consecutivos'
                        })

                # Actualizar sesión
                request.session.modified = True

            except Exception as e:
                print(
                    f"Error procesando {ejercicio_obj.nombre if 'ejercicio_obj' in locals() else 'UNKNOWN'}: {str(e)}")
                continue


def actualizar_rutina_cliente(cliente, rutina):
    """
    Actualiza la rutina actual del cliente al completar un entrenamiento.

    Args:
        cliente: Objeto Cliente
        rutina: Objeto Rutina

    Returns:
        tuple: (bool, str) - Éxito y mensaje
    """
    try:
        rutinas_ordenadas = cliente.programa.rutinas.order_by('orden')
        rutinas = list(rutinas_ordenadas)

        if not rutinas:
            return False, "No hay rutinas disponibles"

        try:
            index = rutinas.index(rutina)
            siguiente = rutinas[(index + 1) % len(rutinas)]
            cliente.rutina_actual = siguiente
            cliente.save()

            if siguiente == rutinas[0]:
                return True, f"¡Ciclo completado! Se reinicia con: {siguiente.nombre}"
            else:
                return True, f"Se asignó la siguiente rutina: {siguiente.nombre}"
        except (ValueError, ZeroDivisionError):
            return False, "No se pudo determinar la siguiente rutina"
    except Exception as e:
        return False, f"Error al actualizar rutina: {str(e)}"


def empezar_entreno(request, rutina_id):
    """
    Muestra el formulario para empezar un entrenamiento con manejo seguro de valores decimales.
    Versión adaptada para procesar correctamente los datos del formulario según el formato
    de la plantilla actual.
    """
    from decimal import Decimal, InvalidOperation
    import logging
    from django.db import connection

    logger = logging.getLogger(__name__)

    # Obtener rutina y ejercicios
    try:
        rutina = get_object_or_404(Rutina, id=rutina_id)
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT re.id,
                                  re.rutina_id,
                                  re.ejercicio_id,
                                  re.series,
                                  re.repeticiones,
                                  re.peso_kg,
                                  e.id     as ej_id,
                                  e.nombre as ej_nombre,
                                  e.grupo_muscular,
                                  e.equipo
                           FROM rutinas_rutinaejercicio re
                                    JOIN rutinas_ejercicio e ON re.ejercicio_id = e.id
                           WHERE re.rutina_id = %s
                           """, [rutina_id])
            columns = [col[0] for col in cursor.description]
            ejercicios_rutina = [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error al obtener rutina y ejercicios: {str(e)}")
        messages.error(request, "Error al cargar la rutina. Por favor, inténtalo de nuevo.")
        return redirect('hacer_entreno')

    cliente_id = request.GET.get('cliente_id')
    cliente_inicial = None

    if cliente_id and cliente_id.isdigit():
        try:
            cliente_inicial = Cliente.objects.get(id=int(cliente_id))
        except Cliente.DoesNotExist:
            cliente_inicial = None

    ejercicios_forms = []
    cliente_form = None
    datos_previos = {}
    fallos_anteriores = set()

    if request.method == 'POST':
        cliente_form = SeleccionClienteForm(request.POST)

        if cliente_form.is_valid():
            cliente = cliente_form.cleaned_data['cliente']

            # Validar cliente
            if not isinstance(cliente, Cliente):
                try:
                    cliente = Cliente.objects.get(id=int(cliente))
                except (ValueError, Cliente.DoesNotExist, TypeError):
                    messages.error(request, "⚠️ Cliente inválido. No se puede continuar.")
                    return redirect('hacer_entreno')

            entreno = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina)

            try:
                # Procesar cada ejercicio de la rutina
                for asignacion in ejercicios_rutina:
                    ejercicio_id = asignacion['ejercicio_id']  # ID del ejercicio (FK)
                    form_id = asignacion['ej_id']  # IMPORTANTE: coincide con ejercicio.form_id en el template

                    # Contar cuántas series hay para este ejercicio en el POST
                    series_count = 0
                    prefix = f"{form_id}_reps_"
                    for key in request.POST.keys():
                        if key.startswith(prefix):
                            series_count += 1

                    if series_count == 0:
                        continue

                    # Procesar cada serie
                    for i in range(1, series_count + 1):
                        try:
                            reps_key = f"{form_id}_reps_{i}"
                            peso_key = f"{form_id}_peso_{i}"
                            rpe_key = f"{form_id}_rpe_{i}"
                            completado_key = f"{form_id}_completado_{i}"

                            # Reps (int)
                            repeticiones = 0
                            if reps_key in request.POST:
                                try:
                                    repeticiones = int(request.POST[reps_key])
                                except (ValueError, TypeError):
                                    repeticiones = 0

                            # Peso (float robusto)
                            peso_kg = 0.0
                            if peso_key in request.POST:
                                try:
                                    peso_kg = float(request.POST[peso_key])
                                except (ValueError, TypeError, InvalidOperation):
                                    try:
                                        valor_str = str(request.POST[peso_key]).replace(',', '.')
                                        valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                                        peso_kg = float(valor_limpio) if valor_limpio else 0.0
                                    except Exception:
                                        peso_kg = 0.0

                            # RPE real (float robusto) ✅ NUEVO
                            rpe_real = None
                            if rpe_key in request.POST:
                                try:
                                    rpe_real = float(str(request.POST[rpe_key]).replace(',', '.'))
                                except (ValueError, TypeError, InvalidOperation):
                                    try:
                                        valor_str = str(request.POST[rpe_key]).replace(',', '.')
                                        valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                                        rpe_real = float(valor_limpio) if valor_limpio else None
                                    except Exception:
                                        rpe_real = None

                            # Completado (checkbox)
                            completado = False
                            if completado_key in request.POST:
                                completado = request.POST[completado_key] == "1"

                            # Crear serie realizada ✅ ya no rompe por rpe_real
                            SerieRealizada.objects.create(
                                entreno=entreno,
                                ejercicio_id=ejercicio_id,
                                serie_numero=i,
                                repeticiones=repeticiones,
                                peso_kg=peso_kg,
                                completado=completado,
                                rpe_real=rpe_real
                            )

                        except Exception as e:
                            logger.error(
                                f"Error al crear serie {i} para ejercicio {asignacion.get('ej_nombre')}: {str(e)}"
                            )

                # Adaptar plan personalizado
                adaptar_plan_personalizado(
                    entreno,
                    [(Ejercicio.objects.get(id=a['ejercicio_id']), None) for a in ejercicios_rutina],
                    cliente,
                    rutina,
                    request
                )

                # Actualizar rutina del cliente
                exito, mensaje = actualizar_rutina_cliente(cliente, rutina)

                messages.success(request, "✅ Entreno guardado con éxito.")
                if exito:
                    messages.success(request, mensaje)
                else:
                    messages.warning(request, mensaje)

                return redirect('resumen_entreno', entreno_id=entreno.id)

            except Exception as e:
                logger.error(f"Error general al procesar formulario: {str(e)}")
                messages.error(request, f"Error al guardar el entreno: {str(e)}")
                # sigue a render

    else:
        cliente_form = SeleccionClienteForm(initial={'cliente': cliente_inicial})

        if cliente_form is not None:
            cliente_form.fields['cliente'].widget = forms.HiddenInput()

        # Datos previos (sin cambios funcionales)
        if cliente_inicial:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                                   SELECT id, fecha
                                   FROM entrenos_entrenorealizado
                                   WHERE cliente_id = %s
                                     AND rutina_id = %s
                                   ORDER BY fecha DESC, id DESC LIMIT 1
                                   """, [cliente_inicial.id, rutina_id])
                    ultimo_entreno_row = cursor.fetchone()

                if ultimo_entreno_row:
                    ultimo_entreno_id = ultimo_entreno_row[0]

                    with connection.cursor() as cursor:
                        cursor.execute("""
                                       SELECT sr.id,
                                              sr.entreno_id,
                                              sr.ejercicio_id,
                                              sr.serie_numero,
                                              sr.repeticiones,
                                              sr.peso_kg,
                                              sr.completado,
                                              e.id     as ej_id,
                                              e.nombre as ej_nombre
                                       FROM entrenos_serierealizada sr
                                                JOIN rutinas_ejercicio e ON sr.ejercicio_id = e.id
                                       WHERE sr.entreno_id = %s
                                       """, [ultimo_entreno_id])
                        columns = [col[0] for col in cursor.description]
                        series_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

                    for serie in series_rows:
                        try:
                            ejercicio_id = serie['ejercicio_id']

                            peso_kg = 0.0
                            if serie['peso_kg'] is not None:
                                try:
                                    peso_kg = float(serie['peso_kg'])
                                except (ValueError, TypeError, InvalidOperation):
                                    try:
                                        valor_str = str(serie['peso_kg']).replace(',', '.')
                                        valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                                        peso_kg = float(valor_limpio) if valor_limpio else 0.0
                                    except Exception:
                                        peso_kg = 0.0

                            repeticiones = 0
                            if serie['repeticiones'] is not None:
                                try:
                                    repeticiones = int(serie['repeticiones'])
                                except (ValueError, TypeError):
                                    repeticiones = 0

                            datos_previos.setdefault(ejercicio_id, []).append({
                                'repeticiones': repeticiones,
                                'peso_kg': peso_kg
                            })

                            if not serie['completado']:
                                fallos_anteriores.add(ejercicio_id)

                        except Exception as e:
                            logger.error(f"Error al procesar serie {serie.get('id')}: {str(e)}")
                            continue

                    for ejercicio_id in set(s['ejercicio_id'] for s in series_rows):
                        series_ejercicio = [s for s in series_rows if s['ejercicio_id'] == ejercicio_id]
                        total = len(series_ejercicio)
                        if total > 0:
                            completadas = sum(1 for s in series_ejercicio if s['completado'])
                            if completadas / total < 0.75:
                                fallos_anteriores.add(ejercicio_id)

            except Exception as e:
                logger.error(f"Error al obtener datos previos: {str(e)}")
                datos_previos = {}
                fallos_anteriores = set()

    # Preparar formularios para cada ejercicio
    for asignacion in ejercicios_rutina:
        try:
            ejercicio_dict = {
                'id': asignacion['ej_id'],
                'form_id': asignacion['ej_id'],  # ✅ para que el template tenga ejercicio.form_id
                'nombre': asignacion['ej_nombre'],
                'grupo_muscular': asignacion.get('grupo_muscular', 'general'),
                'equipo': asignacion.get('equipo', ''),
                'series_datos': []
            }

            plan = None
            adaptado = False
            registro_fallos = 0

            if isinstance(cliente_inicial, Cliente):
                try:
                    plan = PlanPersonalizado.objects.filter(
                        cliente_id=cliente_inicial.id,
                        ejercicio_id=asignacion['ejercicio_id'],
                        rutina_id=rutina_id
                    ).first()
                except Exception as e:
                    logger.error(f"Error al obtener plan personalizado: {str(e)}")
                    plan = None

            if plan:
                reps_plan = 0
                if plan.repeticiones_objetivo is not None:
                    try:
                        reps_plan = int(plan.repeticiones_objetivo)
                    except (ValueError, TypeError):
                        reps_plan = 0

                peso_plan = 0.0
                if plan.peso_objetivo is not None:
                    try:
                        peso_plan = float(plan.peso_objetivo)
                    except (ValueError, TypeError, InvalidOperation):
                        try:
                            peso_plan = float(str(plan.peso_objetivo).replace(',', '.'))
                        except Exception:
                            peso_plan = 0.0

                adaptado = True

                try:
                    num_series = int(asignacion['series'])
                except (ValueError, TypeError):
                    num_series = 3

                session_key = f'adaptacion_{cliente_inicial.id}_{rutina_id}'
                if session_key in request.session:
                    registro = request.session[session_key].get(str(asignacion['ejercicio_id']))
                    if registro:
                        registro_fallos = registro.get('fallos_consecutivos', 0)

                for idx in range(num_series):
                    ejercicio_dict['series_datos'].append({
                        'repeticiones': reps_plan,
                        'peso_kg': peso_plan,
                        'numero': idx + 1,
                        'adaptado': True,
                        'peso_adaptado': True,
                        'fallo_anterior': asignacion['ejercicio_id'] in fallos_anteriores,
                        'fallos_consecutivos': registro_fallos
                    })
            else:
                previas = datos_previos.get(asignacion['ejercicio_id'], [])

                reps_plan = 0
                if asignacion['repeticiones'] is not None:
                    try:
                        reps_plan = int(asignacion['repeticiones'])
                    except (ValueError, TypeError):
                        reps_plan = 0

                peso_plan = 0.0
                if asignacion['peso_kg'] is not None:
                    try:
                        peso_plan = float(asignacion['peso_kg'])
                    except (ValueError, TypeError, InvalidOperation):
                        try:
                            peso_plan = float(str(asignacion['peso_kg']).replace(',', '.'))
                        except Exception:
                            peso_plan = 0.0

                num_series = len(previas) if previas else int(asignacion['series'])

                for idx in range(num_series):
                    rep_valor = reps_plan
                    peso_valor = peso_plan

                    if idx < len(previas):
                        rep_valor = previas[idx]['repeticiones']
                        peso_valor = previas[idx]['peso_kg']

                    ejercicio_dict['series_datos'].append({
                        'repeticiones': rep_valor,
                        'peso_kg': peso_valor,
                        'numero': idx + 1,
                        'adaptado': False,
                        'peso_adaptado': False,
                        'fallo_anterior': asignacion['ejercicio_id'] in fallos_anteriores,
                        'fallos_consecutivos': registro_fallos
                    })

            initial_data = {
                'ejercicio_id': asignacion['ejercicio_id'],
                'series': len(ejercicio_dict['series_datos']),
                'repeticiones': ejercicio_dict['series_datos'][0]['repeticiones'] if ejercicio_dict[
                    'series_datos'] else 0,
                'peso_kg': ejercicio_dict['series_datos'][0]['peso_kg'] if ejercicio_dict['series_datos'] else 0,
                'completado': True
            }

            form = DetalleEjercicioForm(initial=initial_data, prefix=str(asignacion['ejercicio_id']))
            ejercicios_forms.append((ejercicio_dict, form))

        except Exception as e:
            logger.error(f"Error al preparar formulario para ejercicio {asignacion.get('ej_nombre')}: {str(e)}")
            try:
                initial_data = {
                    'ejercicio_id': asignacion.get('ejercicio_id', 0),
                    'series': 0,
                    'repeticiones': 0,
                    'peso_kg': 0,
                    'completado': True
                }
                form = DetalleEjercicioForm(initial=initial_data, prefix=str(asignacion.get('ejercicio_id', 0)))

                ejercicio_dict = {
                    'id': asignacion.get('ej_id', 0),
                    'form_id': asignacion.get('ej_id', 0),
                    'nombre': asignacion.get('ej_nombre', 'Ejercicio sin nombre'),
                    'grupo_muscular': asignacion.get('grupo_muscular', 'general'),
                    'equipo': asignacion.get('equipo', ''),
                    'series_datos': []
                }

                ejercicios_forms.append((ejercicio_dict, form))
            except Exception:
                continue

    return render(request, 'entrenos/empezar_entreno.html', {
        'rutina': rutina,
        'cliente_form': cliente_form,
        'ejercicios_forms': ejercicios_forms,
        'cliente_inicial': cliente_inicial
    })


def adaptar_plan_personalizado_manual(entreno, request, cliente, rutina):
    """
    Versión adaptada de adaptar_plan_personalizado que procesa los datos del formulario
    según el formato de la plantilla actual.

    Args:
        entreno: Objeto EntrenoRealizado
        request: Objeto HttpRequest
        cliente: Objeto Cliente
        rutina: Objeto Rutina
    """
    import logging
    from decimal import Decimal, InvalidOperation
    from django.db import connection

    logger = logging.getLogger(__name__)

    try:
        adaptaciones_positivas = []
        adaptaciones_negativas = []

        # Obtener ejercicios de la rutina con SQL directo
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT re.id,
                                  re.rutina_id,
                                  re.ejercicio_id,
                                  re.series,
                                  re.repeticiones,
                                  re.peso_kg,
                                  e.id     as ej_id,
                                  e.nombre as ej_nombre
                           FROM rutinas_rutinaejercicio re
                                    JOIN rutinas_ejercicio e ON re.ejercicio_id = e.id
                           WHERE re.rutina_id = %s
                           """, [rutina.id])
            columns = [col[0] for col in cursor.description]
            ejercicios_rutina = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Obtener series realizadas con SQL directo
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT sr.id,
                                  sr.entreno_id,
                                  sr.ejercicio_id,
                                  sr.serie_numero,
                                  sr.repeticiones,
                                  sr.peso_kg,
                                  sr.completado,
                                  e.id     as ej_id,
                                  e.nombre as ej_nombre
                           FROM entrenos_serierealizada sr
                                    JOIN rutinas_ejercicio e ON sr.ejercicio_id = e.id
                           WHERE sr.entreno_id = %s
                           """, [entreno.id])
            columns = [col[0] for col in cursor.description]
            series_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Agrupar series por ejercicio
        series_por_ejercicio = {}
        for serie in series_rows:
            ejercicio_id = serie['ejercicio_id']
            if ejercicio_id not in series_por_ejercicio:
                series_por_ejercicio[ejercicio_id] = []
            series_por_ejercicio[ejercicio_id].append(serie)

        # Procesar cada ejercicio
        for asignacion in ejercicios_rutina:
            try:
                ejercicio_id = asignacion['ejercicio_id']
                ej_id = asignacion['ej_id']

                # Verificar si hay series para este ejercicio
                if ejercicio_id not in series_por_ejercicio or not series_por_ejercicio[ejercicio_id]:
                    continue

                # Obtener series del ejercicio
                series = series_por_ejercicio[ejercicio_id]

                # Verificar si todas las series están completadas
                completado = all(serie['completado'] for serie in series)

                # Obtener peso y repeticiones (de la primera serie)
                peso_kg = 0.0
                if series[0]['peso_kg'] is not None:
                    try:
                        peso_kg = float(series[0]['peso_kg'])
                    except (ValueError, TypeError, InvalidOperation):
                        try:
                            valor_str = str(series[0]['peso_kg']).replace(',', '.')
                            valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                            if valor_limpio:
                                peso_kg = float(valor_limpio)
                        except:
                            peso_kg = 0.0

                repeticiones = 0
                if series[0]['repeticiones'] is not None:
                    try:
                        repeticiones = int(series[0]['repeticiones'])
                    except (ValueError, TypeError):
                        repeticiones = 0

                # Obtener o crear plan personalizado
                plan, created = PlanPersonalizado.objects.get_or_create(
                    cliente=cliente,
                    rutina=rutina,
                    ejercicio_id=ejercicio_id,
                    defaults={
                        'series': len(series),
                        'repeticiones_objetivo': repeticiones,
                        'peso_objetivo': peso_kg
                    }
                )

                # Procesar adaptaciones según el resultado del entreno
                if completado:
                    # Éxito: aumentar peso
                    peso_anterior = plan.peso_objetivo
                    plan.peso_objetivo = round(float(peso_kg) * 1.05, 1)  # Incremento del 5%
                    plan.save()

                    adaptaciones_positivas.append({
                        'ejercicio': asignacion['ej_nombre'],
                        'peso_anterior': peso_anterior,
                        'peso_nuevo': plan.peso_objetivo
                    })

                    # Actualizar registro de fallos
                    session_key = f'adaptacion_{cliente.id}_{rutina.id}'
                    if session_key not in request.session:
                        request.session[session_key] = {}

                    if str(ejercicio_id) not in request.session[session_key]:
                        request.session[session_key][str(ejercicio_id)] = {'fallos_consecutivos': 0}
                    else:
                        request.session[session_key][str(ejercicio_id)]['fallos_consecutivos'] = 0

                    request.session.modified = True
                else:
                    # Fallo: disminuir peso si hay fallos consecutivos
                    session_key = f'adaptacion_{cliente.id}_{rutina.id}'
                    if session_key not in request.session:
                        request.session[session_key] = {}

                    if str(ejercicio_id) not in request.session[session_key]:
                        request.session[session_key][str(ejercicio_id)] = {'fallos_consecutivos': 1}
                    else:
                        request.session[session_key][str(ejercicio_id)]['fallos_consecutivos'] += 1

                    fallos = request.session[session_key][str(ejercicio_id)]['fallos_consecutivos']
                    request.session.modified = True

                    if fallos >= 2:
                        # Dos fallos consecutivos: reducir peso
                        peso_anterior = plan.peso_objetivo
                        plan.peso_objetivo = round(float(peso_kg) * 0.9, 1)  # Reducción del 10%
                        plan.save()

                        adaptaciones_negativas.append({
                            'ejercicio': asignacion['ej_nombre'],
                            'peso_anterior': peso_anterior,
                            'peso_nuevo': plan.peso_objetivo,
                            'fallos_consecutivos': fallos
                        })
            except Exception as e:
                logger.error(f"Error al adaptar plan para ejercicio {asignacion.get('ej_nombre')}: {str(e)}")
                continue

        # Guardar adaptaciones en la sesión para mostrarlas en el resumen
        request.session['adaptaciones_positivas'] = adaptaciones_positivas
        request.session['adaptaciones_negativas'] = adaptaciones_negativas
        request.session.modified = True

    except Exception as e:
        logger.error(f"Error general en adaptar_plan_personalizado_manual: {str(e)}")


def crear_entreno_seguro(entreno, ejercicios_forms, request):
    """
    Versión segura que no usa form.cleaned_data y toma los datos directamente del POST.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        for ejercicio_dict, _ in ejercicios_forms:
            try:
                ejercicio_id = int(ejercicio_dict['id'])

                i = 1
                while True:
                    reps_key = f"{ejercicio_id}_reps_{i}"
                    peso_key = f"{ejercicio_id}_peso_{i}"
                    completado_key = f"{ejercicio_id}_completado_{i}"

                    reps = request.POST.get(reps_key)
                    peso = request.POST.get(peso_key)
                    completado = request.POST.get(completado_key) == "1"

                    if reps is None or peso is None:
                        break

                    if reps.strip() == '' and peso.strip() == '':
                        i += 1
                        continue

                    SerieRealizada.objects.create(
                        entreno=entreno,
                        ejercicio_id=ejercicio_id,
                        serie_numero=i,
                        repeticiones=int(reps),
                        peso_kg=float(peso.replace(',', '.')),
                        completado=completado,
                        rpe_real=rpe_real
                    )
                    i += 1

            except Exception as e:
                logger.error(f"Error al procesar serie para ejercicio {ejercicio_dict.get('nombre')}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error general en crear_entreno_seguro: {str(e)}")


def adaptar_plan_personalizado_seguro(entreno, ejercicios_forms, cliente_id, rutina_id, request):
    """
    Versión segura de adaptar_plan_personalizado que usa solo IDs y no objetos simulados.

    Args:
        entreno: Objeto EntrenoRealizado
        ejercicios_forms: Lista de tuplas (ejercicio_dict, form)
        cliente_id: ID del cliente
        rutina_id: ID de la rutina
        request: Objeto HttpRequest
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        adaptaciones_positivas = []
        adaptaciones_negativas = []

        # Procesar cada ejercicio
        for ejercicio_dict, form in ejercicios_forms:
            if form.is_valid():
                # Obtener datos del formulario
                ejercicio_id = form.cleaned_data.get('ejercicio_id')
                series = form.cleaned_data.get('series', 0)
                repeticiones = form.cleaned_data.get('repeticiones', 0)
                peso_kg = form.cleaned_data.get('peso_kg', 0)
                completado = form.cleaned_data.get('completado', False)

                # Validar que ejercicio_id sea un ID válido
                if not isinstance(ejercicio_id, int) and not (isinstance(ejercicio_id, str) and ejercicio_id.isdigit()):
                    logger.error(
                        f"Error procesando {ejercicio_dict['nombre']}: Field 'id' expected a number but got {type(ejercicio_id)}.")
                    continue

                # Convertir a entero si es necesario
                if isinstance(ejercicio_id, str):
                    ejercicio_id = int(ejercicio_id)

                # Obtener o crear plan personalizado
                plan, created = PlanPersonalizado.objects.get_or_create(
                    cliente_id=cliente_id,
                    rutina_id=rutina_id,
                    ejercicio_id=ejercicio_id,  # Usar ID, no objeto
                    defaults={
                        'series': series,
                        'repeticiones_objetivo': repeticiones,
                        'peso_objetivo': peso_kg
                    }
                )

                # Procesar adaptaciones según el resultado del entreno
                if completado:
                    # Éxito: aumentar peso
                    peso_anterior = plan.peso_objetivo
                    plan.peso_objetivo = round(float(peso_kg) * 1.05, 1)  # Incremento del 5%
                    plan.save()

                    adaptaciones_positivas.append({
                        'ejercicio': ejercicio_dict['nombre'],
                        'peso_anterior': peso_anterior,
                        'peso_nuevo': plan.peso_objetivo
                    })

                    # Actualizar registro de fallos
                    session_key = f'adaptacion_{cliente_id}_{rutina_id}'
                    if session_key not in request.session:
                        request.session[session_key] = {}

                    if str(ejercicio_id) not in request.session[session_key]:
                        request.session[session_key][str(ejercicio_id)] = {'fallos_consecutivos': 0}
                    else:
                        request.session[session_key][str(ejercicio_id)]['fallos_consecutivos'] = 0

                    request.session.modified = True
                else:
                    # Fallo: disminuir peso si hay fallos consecutivos
                    session_key = f'adaptacion_{cliente_id}_{rutina_id}'
                    if session_key not in request.session:
                        request.session[session_key] = {}

                    if str(ejercicio_id) not in request.session[session_key]:
                        request.session[session_key][str(ejercicio_id)] = {'fallos_consecutivos': 1}
                    else:
                        request.session[session_key][str(ejercicio_id)]['fallos_consecutivos'] += 1

                    fallos = request.session[session_key][str(ejercicio_id)]['fallos_consecutivos']
                    request.session.modified = True

                    if fallos >= 2:
                        # Dos fallos consecutivos: reducir peso
                        peso_anterior = plan.peso_objetivo
                        plan.peso_objetivo = round(float(peso_kg) * 0.9, 1)  # Reducción del 10%
                        plan.save()

                        adaptaciones_negativas.append({
                            'ejercicio': ejercicio_dict['nombre'],
                            'peso_anterior': peso_anterior,
                            'peso_nuevo': plan.peso_objetivo,
                            'fallos_consecutivos': fallos
                        })

        # Guardar adaptaciones en la sesión para mostrarlas en el resumen
        request.session['adaptaciones_positivas'] = adaptaciones_positivas
        request.session['adaptaciones_negativas'] = adaptaciones_negativas
        request.session.modified = True

    except Exception as e:
        logger.error(f"Error general en adaptar_plan_personalizado_seguro: {str(e)}")


def crear_entreno_seguro(entreno, ejercicios_forms, request):
    """
    Versión segura de crear_entreno que usa solo IDs y no objetos simulados.

    Args:
        entreno: Objeto EntrenoRealizado
        ejercicios_forms: Lista de tuplas (ejercicio_dict, form)
        request: Objeto HttpRequest
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Procesar cada ejercicio
        for ejercicio_dict, form in ejercicios_forms:
            if form.is_valid():
                # Obtener datos del formulario
                ejercicio_id = form.cleaned_data.get('ejercicio_id')
                series = form.cleaned_data.get('series', 0)
                repeticiones = form.cleaned_data.get('repeticiones', 0)
                peso_kg = form.cleaned_data.get('peso_kg', 0)
                completado = form.cleaned_data.get('completado', False)

                # Validar que ejercicio_id sea un ID válido
                if not isinstance(ejercicio_id, int) and not (isinstance(ejercicio_id, str) and ejercicio_id.isdigit()):
                    logger.error(
                        f"Error procesando {ejercicio_dict['nombre']}: Field 'id' expected a number but got {type(ejercicio_id)}.")
                    continue

                # Convertir a entero si es necesario
                if isinstance(ejercicio_id, str):
                    ejercicio_id = int(ejercicio_id)

                # Crear series realizadas
                for i in range(1, series + 1):
                    try:
                        # Crear serie con ID de ejercicio, no con objeto
                        SerieRealizada.objects.create(
                            entreno=entreno,
                            ejercicio_id=ejercicio_id,  # Usar ID, no objeto
                            serie_numero=i,
                            repeticiones=repeticiones,
                            peso_kg=peso_kg,
                            completado=completado,
                            rpe_real=rpe_real
                        )
                    except Exception as e:
                        logger.error(f"Error al crear serie {i} para ejercicio {ejercicio_dict['nombre']}: {str(e)}")
            else:
                logger.error(f"Formulario inválido para ejercicio {ejercicio_dict['nombre']}: {form.errors}")
    except Exception as e:
        logger.error(f"Error general en crear_entreno_seguro: {str(e)}")


def adaptar_plan_personalizado_seguro(entreno, ejercicios_forms, cliente_id, rutina_id, request):
    """
    Versión segura de adaptar_plan_personalizado que usa solo IDs y no objetos simulados.

    Args:
        entreno: Objeto EntrenoRealizado
        ejercicios_forms: Lista de tuplas (ejercicio_dict, form)
        cliente_id: ID del cliente
        rutina_id: ID de la rutina
        request: Objeto HttpRequest
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        adaptaciones_positivas = []
        adaptaciones_negativas = []

        # Procesar cada ejercicio
        for ejercicio_dict, form in ejercicios_forms:
            if form.is_valid():
                # Obtener datos del formulario
                ejercicio_id = form.cleaned_data.get('ejercicio_id')
                series = form.cleaned_data.get('series', 0)
                repeticiones = form.cleaned_data.get('repeticiones', 0)
                peso_kg = form.cleaned_data.get('peso_kg', 0)
                completado = form.cleaned_data.get('completado', False)

                # Validar que ejercicio_id sea un ID válido
                if not isinstance(ejercicio_id, int) and not (isinstance(ejercicio_id, str) and ejercicio_id.isdigit()):
                    logger.error(
                        f"Error procesando {ejercicio_dict['nombre']}: Field 'id' expected a number but got {type(ejercicio_id)}.")
                    continue

                # Convertir a entero si es necesario
                if isinstance(ejercicio_id, str):
                    ejercicio_id = int(ejercicio_id)

                # Obtener o crear plan personalizado
                plan, created = PlanPersonalizado.objects.get_or_create(
                    cliente_id=cliente_id,
                    rutina_id=rutina_id,
                    ejercicio_id=ejercicio_id,  # Usar ID, no objeto
                    defaults={
                        'series': series,
                        'repeticiones_objetivo': repeticiones,
                        'peso_objetivo': peso_kg
                    }
                )

                # Procesar adaptaciones según el resultado del entreno
                if completado:
                    # Éxito: aumentar peso
                    peso_anterior = plan.peso_objetivo
                    plan.peso_objetivo = round(float(peso_kg) * 1.05, 1)  # Incremento del 5%
                    plan.save()

                    adaptaciones_positivas.append({
                        'ejercicio': ejercicio_dict['nombre'],
                        'peso_anterior': peso_anterior,
                        'peso_nuevo': plan.peso_objetivo
                    })

                    # Actualizar registro de fallos
                    session_key = f'adaptacion_{cliente_id}_{rutina_id}'
                    if session_key not in request.session:
                        request.session[session_key] = {}

                    if str(ejercicio_id) not in request.session[session_key]:
                        request.session[session_key][str(ejercicio_id)] = {'fallos_consecutivos': 0}
                    else:
                        request.session[session_key][str(ejercicio_id)]['fallos_consecutivos'] = 0

                    request.session.modified = True
                else:
                    # Fallo: disminuir peso si hay fallos consecutivos
                    session_key = f'adaptacion_{cliente_id}_{rutina_id}'
                    if session_key not in request.session:
                        request.session[session_key] = {}

                    if str(ejercicio_id) not in request.session[session_key]:
                        request.session[session_key][str(ejercicio_id)] = {'fallos_consecutivos': 1}
                    else:
                        request.session[session_key][str(ejercicio_id)]['fallos_consecutivos'] += 1

                    fallos = request.session[session_key][str(ejercicio_id)]['fallos_consecutivos']
                    request.session.modified = True

                    if fallos >= 2:
                        # Dos fallos consecutivos: reducir peso
                        peso_anterior = plan.peso_objetivo
                        plan.peso_objetivo = round(float(peso_kg) * 0.9, 1)  # Reducción del 10%
                        plan.save()

                        adaptaciones_negativas.append({
                            'ejercicio': ejercicio_dict['nombre'],
                            'peso_anterior': peso_anterior,
                            'peso_nuevo': plan.peso_objetivo,
                            'fallos_consecutivos': fallos
                        })

        # Guardar adaptaciones en la sesión para mostrarlas en el resumen
        request.session['adaptaciones_positivas'] = adaptaciones_positivas
        request.session['adaptaciones_negativas'] = adaptaciones_negativas
        request.session.modified = True

    except Exception as e:
        logger.error(f"Error general en adaptar_plan_personalizado_seguro: {str(e)}")


def hacer_entreno(request):
    """
    Muestra una lista de clientes para seleccionar al iniciar un entrenamiento.

    Args:
        request: Objeto HttpRequest

    Returns:
        HttpResponse con la plantilla renderizada
    """
    clientes = Cliente.objects.select_related('programa', 'rutina_actual').all()
    return render(request, 'entrenos/hacer_entreno.html', {
        'clientes': clientes
    })


def eliminar_entreno(request, pk):
    """
    Elimina un entrenamiento específico.

    Args:
        request: Objeto HttpRequest
        pk: ID del entrenamiento a eliminar

    Returns:
        HttpResponseRedirect a la página de historial de entrenamientos
    """
    if request.method == 'POST':
        try:
            entreno = get_object_or_404(EntrenoRealizado, pk=pk)
            entreno.delete()
            messages.success(request, "✅ Entrenamiento eliminado con éxito.")
        except Exception as e:
            messages.error(request, f"⚠️ Error al eliminar entrenamiento: {str(e)}")
    return redirect('historial_entrenos')


def mostrar_entreno_anterior(request, cliente_id, rutina_id):
    """
    Muestra los detalles de un entrenamiento anterior con manejo seguro de valores decimales.
    Versión final robusta que usa SQL directo para evitar errores de conversión decimal
    y diccionarios simples en lugar de objetos simulados.

    Args:
        request: Objeto HttpRequest
        cliente_id: ID del cliente
        rutina_id: ID de la rutina

    Returns:
        HttpResponse con la plantilla renderizada
    """
    from decimal import Decimal, InvalidOperation
    import logging
    from django.db import connection
    from django.utils.dateformat import DateFormat
    from django.db.models import Sum
    import json

    # Configurar logging para depuración
    logger = logging.getLogger(__name__)

    # Obtenemos el cliente y la rutina por ID de forma segura
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        rutina = get_object_or_404(Rutina, id=rutina_id)
    except Exception as e:
        logger.error(f"Error al obtener cliente o rutina: {str(e)}")
        messages.error(request, "Error al cargar los datos. Por favor, inténtalo de nuevo.")
        return redirect('home')

    # Último entreno realizado - Usando SQL directo para evitar errores de conversión
    entreno_anterior = None
    series_procesadas = []

    try:
        # Obtener último entreno con SQL directo
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT id, fecha
                           FROM entrenos_entrenorealizado
                           WHERE cliente_id = %s
                             AND rutina_id = %s
                           ORDER BY fecha DESC, id DESC LIMIT 1
                           """, [cliente_id, rutina_id])
            entreno_row = cursor.fetchone()

        if entreno_row:
            entreno_id = entreno_row[0]
            fecha = entreno_row[1]

            # IMPORTANTE: Usar diccionario en lugar de objeto simulado
            entreno_anterior = {
                'id': entreno_id,
                'fecha': fecha,
                'cliente_id': cliente_id,
                'rutina_id': rutina_id,
                'cliente_nombre': cliente.nombre if hasattr(cliente, 'nombre') else str(cliente),
                'rutina_nombre': rutina.nombre if hasattr(rutina, 'nombre') else str(rutina)
            }

            # Obtener series con SQL directo
            with connection.cursor() as cursor:
                cursor.execute("""
                               SELECT sr.id,
                                      sr.entreno_id,
                                      sr.ejercicio_id,
                                      sr.serie_numero,
                                      sr.repeticiones,
                                      sr.peso_kg,
                                      sr.completado,
                                      e.id     as ej_id,
                                      e.nombre as ej_nombre
                               FROM entrenos_serierealizada sr
                                        JOIN rutinas_ejercicio e ON sr.ejercicio_id = e.id
                               WHERE sr.entreno_id = %s
                               """, [entreno_id])
                columns = [col[0] for col in cursor.description]
                series_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Procesar series de forma segura
            for serie in series_rows:
                try:
                    # IMPORTANTE: Usar diccionario en lugar de objeto simulado para ejercicio
                    ejercicio_dict = {
                        'id': serie['ej_id'],
                        'nombre': serie['ej_nombre']
                    }

                    # Convertir peso de forma segura
                    peso_kg = 0.0
                    if serie['peso_kg'] is not None:
                        try:
                            # Intentar convertir directamente
                            peso_kg = float(serie['peso_kg'])
                        except (ValueError, TypeError, InvalidOperation):
                            try:
                                # Intentar limpiar y convertir
                                valor_str = str(serie['peso_kg']).replace(',', '.')
                                valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                                if valor_limpio:
                                    peso_kg = float(valor_limpio)
                            except:
                                peso_kg = 0.0

                    # Convertir repeticiones de forma segura
                    repeticiones = 0
                    if serie['repeticiones'] is not None:
                        try:
                            repeticiones = int(serie['repeticiones'])
                        except (ValueError, TypeError):
                            repeticiones = 0

                    # IMPORTANTE: Crear diccionario en lugar de objeto simulado para serie
                    serie_procesada = {
                        'id': serie['id'],
                        'serie_numero': serie['serie_numero'],
                        'repeticiones': repeticiones,
                        'peso_kg': peso_kg,
                        'completado': serie['completado'],
                        'ejercicio': ejercicio_dict  # Usar diccionario, no objeto simulado
                    }
                    series_procesadas.append(serie_procesada)
                except Exception as e:
                    logger.error(f"Error al procesar serie {serie.get('id')}: {str(e)}")
                    continue
    except Exception as e:
        logger.error(f"Error al obtener entreno anterior: {str(e)}")
        entreno_anterior = None
        series_procesadas = []

    # Plan personalizado o rutina original - Usando SQL directo
    ejercicios_planificados = []

    try:
        # Obtener ejercicios de la rutina con SQL directo
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT re.id,
                                  re.rutina_id,
                                  re.ejercicio_id,
                                  re.series,
                                  re.repeticiones,
                                  re.peso_kg,
                                  e.id     as ej_id,
                                  e.nombre as ej_nombre
                           FROM rutinas_rutinaejercicio re
                                    JOIN rutinas_ejercicio e ON re.ejercicio_id = e.id
                           WHERE re.rutina_id = %s
                           """, [rutina_id])
            columns = [col[0] for col in cursor.description]
            ejercicios_rutina = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Obtener planes personalizados con SQL directo
        planes_personalizados = {}
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT id, cliente_id, ejercicio_id, rutina_id, repeticiones_objetivo, peso_objetivo
                           FROM entrenos_planpersonalizado
                           WHERE cliente_id = %s
                             AND rutina_id = %s
                           """, [cliente_id, rutina_id])
            columns = [col[0] for col in cursor.description]
            planes_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Indexar planes por ejercicio_id para acceso rápido
            for plan in planes_rows:
                planes_personalizados[plan['ejercicio_id']] = plan

        # Procesar cada ejercicio de la rutina
        for asignacion in ejercicios_rutina:
            try:
                ejercicio_id = asignacion['ejercicio_id']

                # Obtener plan personalizado si existe
                plan = planes_personalizados.get(ejercicio_id)

                # Manejo seguro de valores decimales
                peso_base = 0.0
                if asignacion['peso_kg'] is not None:
                    try:
                        peso_base = float(asignacion['peso_kg'])
                    except (ValueError, TypeError, InvalidOperation):
                        try:
                            valor_str = str(asignacion['peso_kg']).replace(',', '.')
                            valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                            if valor_limpio:
                                peso_base = float(valor_limpio)
                        except:
                            peso_base = 0.0

                peso_adaptado = False
                peso_objetivo = peso_base

                if plan and plan['peso_objetivo'] is not None:
                    try:
                        plan_peso_objetivo = float(plan['peso_objetivo'])
                        if abs(plan_peso_objetivo - peso_base) > 0.001:  # Comparación con tolerancia para decimales
                            peso_objetivo = plan_peso_objetivo
                            peso_adaptado = True
                    except (ValueError, TypeError, InvalidOperation):
                        try:
                            valor_str = str(plan['peso_objetivo']).replace(',', '.')
                            valor_limpio = ''.join(c for c in valor_str if c.isdigit() or c == '.')
                            if valor_limpio:
                                plan_peso_objetivo = float(valor_limpio)
                                if abs(plan_peso_objetivo - peso_base) > 0.001:
                                    peso_objetivo = plan_peso_objetivo
                                    peso_adaptado = True
                        except:
                            peso_objetivo = peso_base

                ejercicios_planificados.append({
                    'nombre': asignacion['ej_nombre'],
                    'series': asignacion['series'],
                    'repeticiones': asignacion['repeticiones'],
                    'peso_kg': peso_objetivo,
                    'peso_adaptado': peso_adaptado,
                    'peso_base': peso_base
                })
            except Exception as e:
                logger.error(f"Error al procesar ejercicio {asignacion.get('ej_nombre')}: {str(e)}")
                # Intentamos añadir información básica incluso si hay error
                try:
                    ejercicios_planificados.append({
                        'nombre': asignacion.get('ej_nombre', 'Ejercicio sin nombre'),
                        'series': asignacion.get('series', 0),
                        'repeticiones': asignacion.get('repeticiones', 0),
                        'peso_kg': 0.0,
                        'peso_adaptado': False,
                        'peso_base': 0.0
                    })
                except:
                    pass
    except Exception as e:
        logger.error(f"Error al procesar ejercicios planificados: {str(e)}")
        ejercicios_planificados = []
    # Cargar último logro

    ultimo_logro = LogroDesbloqueado.objects.filter(cliente=cliente).order_by('-fecha').first()

    # Estado emocional más reciente

    estado_emocional = EstadoEmocional.objects.filter(cliente=cliente).order_by('-fecha').first()

    # Progreso semanal simulado (reemplazar por datos reales si los tienes)
    # Obtener últimos 7 días de entrenamientos reales del cliente
    # ✅ Gráfica real con progreso de volumen total por día
    try:
        ultimos_entrenos = (
            EntrenoRealizado.objects.filter(cliente=cliente)
            .order_by('-fecha')
            .values('fecha')
            .annotate(volumen_total=Sum('series__peso_kg'))
            [:7][::-1]
        )
        progreso_fechas = [DateFormat(e['fecha']).format("d M") for e in ultimos_entrenos]
        progreso_valores = [float(e['volumen_total'] or 0.0) for e in ultimos_entrenos]
    except Exception as e:
        logger.error(f"Error al generar datos de gráfico: {str(e)}")
        progreso_fechas = []
        progreso_valores = []
    # Añadir información de depuración al contexto
    # --- Comparativa de progreso respecto al entreno anterior ---
    volumen_actual = 0
    volumen_anterior = 0
    dias_entre_entrenos = None
    diferencia_porcentual = 0
    mensaje_comparativa = ""

    try:
        entrenos = (
            EntrenoRealizado.objects
            .filter(cliente=cliente, rutina=rutina)
            .annotate(total_series=Count('series'))
            .filter(total_series__gt=0)
            .order_by('-id')

        )

        if entrenos.count() >= 2:
            actual = entrenos[0]
            anterior = entrenos[1]
            print("▶️ ENTRENOS DETECTADOS:")
            print(f"   Actual ID: {actual.id}, Fecha: {actual.fecha}")
            print(f"   Anterior ID: {anterior.id}, Fecha: {anterior.fecha}")
            series_actual = SerieRealizada.objects.filter(entreno=actual)
            series_anterior = SerieRealizada.objects.filter(entreno=anterior)

            print("🔍 SERIES ACTUAL:")
            for s in series_actual:
                print(f"{s.ejercicio.nombre} - {s.peso_kg} kg")

            print("🔍 SERIES ANTERIOR:")
            for s in series_anterior:
                print(f"{s.ejercicio.nombre} - {s.peso_kg} kg")

            dias_entre_entrenos = (actual.fecha - anterior.fecha).days

            volumen_actual = SerieRealizada.objects.filter(entreno=actual).aggregate(
                total=Sum('peso_kg'))['total'] or 0
            volumen_anterior = SerieRealizada.objects.filter(entreno=anterior).aggregate(
                total=Sum('peso_kg'))['total'] or 0

            if volumen_anterior > 0:
                diferencia_porcentual = round(((volumen_actual - volumen_anterior) / volumen_anterior) * 100, 1)
                if diferencia_porcentual > 0:
                    mensaje_comparativa = f"Subiste el volumen total un {diferencia_porcentual} % 💪"
                elif diferencia_porcentual < 0:
                    mensaje_comparativa = f"Bajaste el volumen total un {abs(diferencia_porcentual)} % 💤"
                else:
                    mensaje_comparativa = "Mantuviste el mismo volumen que el entreno anterior. 🎯"
        else:
            mensaje_comparativa = "Aún no hay suficientes datos para comparar el volumen."
    except Exception as e:
        logger.error(f"Error al calcular la comparativa de volumen: {str(e)}")
        mensaje_comparativa = "No se pudo calcular la comparativa de volumen."

    # --- Comparativa por ejercicio: mejora o estancamiento ---
    mejor_ejercicio = None
    mejora_kg = 0
    ejercicio_estancado = None

    try:
        if entrenos.count() >= 2:
            actual = entrenos[0]
            anterior = entrenos[1]

            max_mejora = -999
            max_bajada = 0
            ejercicios_actual = (
                SerieRealizada.objects
                .filter(entreno=actual)
                .values('ejercicio__id', 'ejercicio__nombre')
                .annotate(peso_prom=Avg('peso_kg'))
            )

            ejercicios_anterior = {
                e['ejercicio__id']: e for e in SerieRealizada.objects
                .filter(entreno=anterior)
                .values('ejercicio__id', 'ejercicio__nombre')
                .annotate(peso_prom=Avg('peso_kg'))
            }

            max_mejora = -999
            max_bajada = 0

            for e in ejercicios_actual:
                eid = e['ejercicio__id']
                nombre = e['ejercicio__nombre']
                peso_actual = e['peso_prom'] or 0
                anterior_data = ejercicios_anterior.get(eid)
                peso_anterior = anterior_data['peso_prom'] if anterior_data else 0

                diferencia = round(peso_actual - peso_anterior, 1)

                if diferencia > max_mejora:
                    max_mejora = diferencia
                    mejor_ejercicio = nombre
                    mejora_kg = diferencia
                    peso_anterior_ej = peso_anterior
                    peso_actual_ej = peso_actual

                if diferencia <= 0 and abs(diferencia) > max_bajada:
                    max_bajada = abs(diferencia)
                    ejercicio_estancado = nombre

            mejora_kg = round(mejora_kg, 1)
        else:
            logger.info(f"✅ Comparación realizada: mejor ejercicio = {mejor_ejercicio}, mejora = {mejora_kg} kg")


    except Exception as e:
        logger.error(f"Error al calcular mejora por ejercicio: {str(e)}")

    # --- Logros recientes del cliente ---
    logros_recientes = []
    try:
        logros_recientes = LogroDesbloqueado.objects.filter(
            cliente=cliente
        ).order_by('-fecha')[:3]
    except Exception as e:
        logger.error(f"Error al obtener logros recientes: {str(e)}")
    volumen_actual = round(volumen_actual, 1)
    volumen_anterior = round(volumen_anterior, 1)
    mejora_kg = round(mejora_kg, 1)
    context = {
        'cliente': cliente,
        'rutina': rutina,
        'mejor_ejercicio': mejor_ejercicio,
        'logros_recientes': logros_recientes,
        'mejora_kg': mejora_kg,
        'ejercicio_estancado': ejercicio_estancado,
        'volumen_actual': volumen_actual,
        'volumen_anterior': volumen_anterior,
        'mensaje_comparativa': mensaje_comparativa,
        'peso_anterior_ej': round(peso_anterior_ej, 1) if 'peso_anterior_ej' in locals() else None,
        'peso_actual_ej': round(peso_actual_ej, 1) if 'peso_actual_ej' in locals() else None,
        'ultimo_logro': ultimo_logro,
        'estado_emocional': estado_emocional,
        'progreso_fechas': json.dumps(progreso_fechas),
        'progreso_valores': json.dumps(progreso_valores),
        'entreno': entreno_anterior,
        'series_procesadas': series_procesadas,  # ¡Clave para la plantilla corregida!
        'plan': ejercicios_planificados,
        'debug_info': {
            'tiene_entreno': entreno_anterior is not None,
            'num_series_procesadas': len(series_procesadas),
            'num_ejercicios': len(ejercicios_planificados),
        },
        'estado_joi': 'normal',  # también puedes probar con 'feliz', 'triste', 'glitch'
        'frase_forma_joi': "¿Listo para continuar lo que empezaste ayer?",
        'frase_extra_joi': "",
        'frase_recaida': "",
    }

    return render(request, 'entrenos/entreno_anterior.html', context)


import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateformat import DateFormat

from clientes.models import Cliente
from .models import EntrenoRealizado, PlanPersonalizado, SerieRealizada
from rutinas.models import Rutina, RutinaEjercicio
from .models import EjercicioBase

logger = logging.getLogger(__name__)


# Clase para codificar Decimal y datetime en JSON (Mantén solo una vez)
class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# entrenos/views.py

# Asegúrate de tener estos imports al principio de tu archivo
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Avg, Count, Sum, Max, F, ExpressionWrapper, fields
from decimal import Decimal

from django.utils.dateformat import DateFormat
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Avg, Count, Sum, F, ExpressionWrapper, fields
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateformat import DateFormat

from clientes.models import Cliente
from .models import EntrenoRealizado, SerieRealizada, EjercicioBase
from rutinas.models import Rutina

logger = logging.getLogger(__name__)


# Clase para codificar datos complejos a JSON (si no la tienes ya)
class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# En entrenos/views.py

from django.template import loader, Template, Context
from django.http import HttpResponse

# En entrenos/views.py

# Asegúrate de tener todas estas importaciones al principio del archivo:
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Avg, Count, Sum, Max, F, ExpressionWrapper, fields
from collections import defaultdict
from decimal import Decimal
import json
from django.utils.dateformat import DateFormat
from .models import EntrenoRealizado, SerieRealizada, Cliente

import logging

logger = logging.getLogger(__name__)


def resumen_entreno(request, pk):
    """
    VISTA FINAL Y ROBUSTA: Muestra un resumen detallado y motivador
    del entrenamiento realizado.
    """
    try:
        # --- 1. OBTENER DATOS BÁSICOS ---
        entreno_actual = get_object_or_404(
            EntrenoRealizado.objects.select_related('cliente', 'rutina'),
            pk=pk
        )
        cliente = entreno_actual.cliente

        # --- 2. DETALLES DEL ENTRENAMIENTO ACTUAL ---
        series_actuales = SerieRealizada.objects.filter(entreno=entreno_actual).select_related('ejercicio')

        # Si no hay series, preparamos un contexto básico y evitamos cálculos
        if not series_actuales.exists():
            messages.warning(request,
                             "El entrenamiento guardado no contiene series. No se pueden mostrar estadísticas detalladas.")
            context = {
                'entreno': entreno_actual, 'cliente': cliente, 'stats': {}, 'comparativa': {'disponible': False},
                'medallas': [], 'ejercicios_realizados': {}, 'progreso_chart_data_json': json.dumps({})
            }
            # return render(request, 'entrenos/resumen_entreno.html', context)

            return redirect('entrenos:dashboard_liftin')

        ejercicios_realizados = defaultdict(list)
        for serie in series_actuales:
            ejercicios_realizados[serie.ejercicio.nombre].append({
                'reps': serie.repeticiones,
                'peso': round(serie.peso_kg, 1)
            })

        stats_actual = series_actuales.aggregate(
            total_series=Count('id'),
            series_completadas=Count('id', filter=F('completado')),
            volumen_total=Sum(ExpressionWrapper(F('repeticiones') * F('peso_kg'), output_field=fields.DecimalField())),
            peso_maximo=Max('peso_kg')
        )

        entreno_perfecto = (stats_actual.get('total_series', 0) > 0 and
                            stats_actual['total_series'] == stats_actual['series_completadas'])

        # --- 3. COMPARATIVA CON EL ENTRENAMIENTO ANTERIOR ---
        entreno_anterior = EntrenoRealizado.objects.filter(
            cliente=cliente, rutina=entreno_actual.rutina, pk__lt=entreno_actual.pk
        ).order_by('-fecha', '-id').first()

        comparativa = {'disponible': False}
        if entreno_anterior:
            stats_anterior = SerieRealizada.objects.filter(entreno=entreno_anterior).aggregate(
                volumen_total=Sum(
                    ExpressionWrapper(F('repeticiones') * F('peso_kg'), output_field=fields.DecimalField()))
            )
            vol_actual = stats_actual.get('volumen_total') or Decimal('0')
            vol_anterior = stats_anterior.get('volumen_total') or Decimal('0')

            if vol_anterior > 0:
                diferencia_vol = vol_actual - vol_anterior
                porcentaje_vol = round(float((diferencia_vol / vol_anterior) * 100), 1)
                comparativa = {
                    'disponible': True,
                    'volumen_actual': round(float(vol_actual), 1),
                    'volumen_anterior': round(float(vol_anterior), 1),
                    'diferencia_porcentual': porcentaje_vol
                }

        # --- 4. LOGROS Y MEDALLAS ---
        medallas = []
        if entreno_perfecto:
            medallas.append(
                {'icono': '🎯', 'nombre': 'Precisión Absoluta', 'desc': 'Completaste todas las series al 100%.'})
        if (stats_actual.get('peso_maximo') or 0) > 100:
            medallas.append({'icono': '🏋️', 'nombre': 'Club de los 100kg', 'desc': 'Levantaste más de 100kg.'})
        if comparativa.get('diferencia_porcentual', 0) > 10:
            medallas.append({'icono': '🚀', 'nombre': 'Salto Cuántico', 'desc': 'Aumentaste tu volumen más de un 10%.'})

        # --- 5. GRÁFICO DE PROGRESO DE VOLUMEN ---
        ultimos_entrenos = EntrenoRealizado.objects.filter(
            cliente=cliente, rutina=entreno_actual.rutina
        ).order_by('fecha', 'id').values('fecha').annotate(
            volumen=Sum(
                ExpressionWrapper(F('series__repeticiones') * F('series__peso_kg'), output_field=fields.DecimalField()))
        )
        progreso_chart_data = {
            "labels": [DateFormat(e['fecha']).format("d M") for e in ultimos_entrenos],
            "data": [float(e['volumen'] or 0) for e in ultimos_entrenos]
        }

        # --- 6. CONTEXTO PARA LA PLANTILLA ---
        context = {
            'entreno': entreno_actual, 'cliente': cliente, 'ejercicios_realizados': dict(ejercicios_realizados),
            'stats': {
                'volumen_total': round(float(stats_actual.get('volumen_total') or 0), 1),
                'peso_maximo': round(float(stats_actual.get('peso_maximo') or 0), 1),
                'total_series': stats_actual.get('total_series', 0),
                'series_completadas': stats_actual.get('series_completadas', 0),
                'duracion': entreno_actual.duracion_minutos,
            },
            'entreno_perfecto': entreno_perfecto, 'comparativa': comparativa, 'medallas': medallas,
            'progreso_chart_data_json': json.dumps(progreso_chart_data, cls=CustomJSONEncoder)
        }
        return render(request, 'entrenos/resumen_entreno.html', context)

    except Exception as e:
        logger.error(f"Error al generar el resumen del entreno {pk}: {e}", exc_info=True)
        messages.error(request,
                       f"Ocurrió un error crítico al generar el resumen: {e}. Por favor, contacta al administrador.")
        return redirect('home')  # Redirige a la página de inicio como último recurso


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
import json
import csv
from datetime import datetime, timedelta

from .models import EntrenoRealizado, EjercicioLiftinDetallado, DatosLiftinDetallados
from .forms import (
    ImportarLiftinCompletoForm,
    ImportarLiftinBasicoForm,
    BuscarEntrenamientosLiftinForm,
    ExportarDatosForm,
    EjercicioLiftinFormSet
)
from clientes.models import Cliente


# ============================================================================
# VISTAS PRINCIPALES DE IMPORTACIÓN
# ============================================================================


def importar_liftin_completo(request):
    """
    Vista definitiva basada en la estructura real de la base de datos
    """
    try:
        # ============================================================================
        # MÉTODO GET - MOSTRAR FORMULARIO
        # ============================================================================
        from datetime import date

        if request.method == 'GET':
            logger.info("Mostrando formulario de importación Liftin")

            try:
                from entrenos.models import Cliente
                from rutinas.models import Rutina  # Rutina está en app rutinas, no entrenos

                clientes = Cliente.objects.all().order_by('nombre')
                rutinas = Rutina.objects.all().order_by('nombre')

                context = {
                    'clientes': clientes,
                    'rutinas': rutinas,
                    'hoy': date.today(),  # ✅ Esta línea permite que el campo <input type="date"> funcione correctamente
                }

                return render(request, 'entrenos/importar_liftin_completo.html', context)

            except Exception as e:
                logger.error(f"Error al obtener datos para formulario: {str(e)}")
                messages.error(request, f"Error al cargar el formulario: {str(e)}")
                return redirect('entrenos:dashboard_liftin')
        # ============================================================================
        # MÉTODO POST - PROCESAR FORMULARIO
        # ============================================================================
        elif request.method == 'POST':
            logger.info("Procesando formulario de importación Liftin")

            try:
                # ============================================================================
                # VALIDAR DATOS ESENCIALES
                # ============================================================================
                cliente_id = request.POST.get('cliente')
                from datetime import datetime

                fecha_str = request.POST.get('fecha')
                try:
                    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    messages.error(request, "Fecha inválida")
                    return redirect('entrenos:importar_liftin_completo')

                rutina_id = request.POST.get('rutina')

                if not cliente_id:
                    messages.error(request, "Debe seleccionar un cliente")
                    return redirect('entrenos:importar_liftin_completo')

                if not fecha:
                    messages.error(request, "Debe proporcionar una fecha")
                    return redirect('entrenos:importar_liftin_completo')

                # ============================================================================
                # OBTENER CLIENTE
                # ============================================================================
                from entrenos.models import Cliente, EntrenoRealizado
                from rutinas.models import Rutina

                try:
                    cliente = Cliente.objects.get(id=cliente_id)
                    logger.info(f"Cliente encontrado: {cliente.nombre}")
                except Cliente.DoesNotExist:
                    messages.error(request, "Cliente seleccionado no válido")
                    return redirect('entrenos:importar_liftin_completo')

                # ============================================================================
                # MANEJAR RUTINA OBLIGATORIA - USAR ESTRUCTURA REAL
                # ============================================================================
                rutina = None

                if rutina_id:
                    # Si se seleccionó una rutina, usarla
                    try:
                        rutina = Rutina.objects.get(id=rutina_id)
                        logger.info(f"Rutina seleccionada: {rutina.nombre}")
                    except Rutina.DoesNotExist:
                        logger.warning(f"Rutina con ID {rutina_id} no existe")
                        rutina = None

                if not rutina:
                    # Si no hay rutina seleccionada, usar la primera disponible (ID=1)
                    try:
                        rutina = Rutina.objects.get(id=1)  # "Dia1 - torso" que existe en la DB
                        logger.info(f"Usando rutina por defecto: {rutina.nombre}")
                    except Rutina.DoesNotExist:
                        # Si no existe ID=1, usar la primera disponible
                        rutina = Rutina.objects.first()
                        if rutina:
                            logger.info(f"Usando primera rutina disponible: {rutina.nombre}")
                        else:
                            messages.error(request, "No hay rutinas disponibles en el sistema")
                            return redirect('entrenos:importar_liftin_completo')

                # ============================================================================
                # PROCESAR EJERCICIOS
                # ============================================================================
                ejercicios_texto = []

                for i in range(1, 9):  # 8 ejercicios
                    nombre = request.POST.get(f'ejercicio_{i}_nombre', '').strip()

                    if nombre:
                        estado = request.POST.get(f'ejercicio_{i}_estado', '')
                        peso = request.POST.get(f'ejercicio_{i}_peso', '').strip()
                        series = request.POST.get(f'ejercicio_{i}_series', '').strip()

                        # Formatear ejercicio
                        estado_simbolo = ''
                        if estado == 'completado':
                            estado_simbolo = '✓ '
                        elif estado == 'fallado':
                            estado_simbolo = '✗ '
                        elif estado == 'nuevo':
                            estado_simbolo = 'N '

                        linea = f"{estado_simbolo}{nombre}"
                        if peso:
                            linea += f": {peso}"
                        if series:
                            linea += f", {series}"

                        ejercicios_texto.append(linea)

                # ============================================================================
                # PREPARAR NOTAS COMPLETAS
                # ============================================================================
                notas_generales = request.POST.get('notas', '').strip()
                texto_completo = []

                if notas_generales:
                    texto_completo.append(notas_generales)

                if ejercicios_texto:
                    texto_completo.append("\\n\\nEjercicios Detallados:")
                    texto_completo.extend(ejercicios_texto)

                notas_liftin_completas = "\\n".join(texto_completo)

                # ============================================================================
                # PREPARAR DATOS DEL ENTRENAMIENTO - ESTRUCTURA REAL
                # ============================================================================

                # Datos básicos obligatorios según estructura real
                datos_entrenamiento = {
                    'cliente': cliente,
                    'rutina': rutina,  # ✅ OBLIGATORIO según DB
                    'fecha': fecha,
                    'fuente_datos': 'liftin',
                    'procesado_gamificacion': False,  # ✅ Campo obligatorio según DB
                    'notas_liftin': notas_liftin_completas,  # ✅ Campo correcto para notas
                }

                # Campos opcionales según estructura real
                hora_inicio = request.POST.get('hora_inicio')
                if hora_inicio:
                    datos_entrenamiento['hora_inicio'] = hora_inicio

                duracion_minutos = request.POST.get('duracion_minutos')
                if duracion_minutos:
                    try:
                        datos_entrenamiento['duracion_minutos'] = int(duracion_minutos)
                    except ValueError:
                        pass

                calorias_quemadas = request.POST.get('calorias_quemadas')
                if calorias_quemadas:
                    try:
                        datos_entrenamiento['calorias_quemadas'] = int(calorias_quemadas)
                    except ValueError:
                        pass

                volumen_total_kg = request.POST.get('volumen_total_kg')
                if volumen_total_kg:
                    try:
                        datos_entrenamiento['volumen_total_kg'] = float(volumen_total_kg)
                    except ValueError:
                        pass

                # Campos adicionales específicos de Liftin según estructura real
                if ejercicios_texto:
                    datos_entrenamiento['numero_ejercicios'] = len(ejercicios_texto)

                # ============================================================================
                # CREAR ENTRENAMIENTO
                # ============================================================================
                logger.info(f"Creando entrenamiento con datos: {datos_entrenamiento}")
                entrenamiento = EntrenoRealizado.objects.create(**datos_entrenamiento)
                logger.info(f"Entrenamiento creado exitosamente con ID: {entrenamiento.id}")

                # ============================================================================
                # ACTIVAR LOGROS (SI EXISTE EL SISTEMA)
                # ============================================================================
                try:
                    # Intentar activar logros si el sistema existe
                    activar_logros_liftin(cliente, entrenamiento)
                    logger.info("Logros activados correctamente")
                except Exception as e:
                    logger.warning(f"No se pudieron activar logros: {str(e)}")

                # ============================================================================
                # ÉXITO - REDIRECCIONAR
                # ============================================================================
                mensaje_exito = f"Entrenamiento de Liftin importado exitosamente para {cliente.nombre}"
                if rutina:
                    mensaje_exito += f" (Rutina: {rutina.nombre})"
                if ejercicios_texto:
                    mensaje_exito += f" con {len(ejercicios_texto)} ejercicios"

                messages.success(request, mensaje_exito)
                logger.info("Importación exitosa - Redirigiendo al dashboard")

                return redirect('entrenos:dashboard_liftin')

            except Exception as e:
                logger.error(f"Error al procesar formulario: {str(e)}")
                logger.exception("Traceback completo:")
                messages.error(request, f"Error al importar entrenamiento: {str(e)}")
                return redirect('entrenos:importar_liftin_completo')

    except Exception as e:
        logger.error(f"Error general: {str(e)}")
        logger.exception("Traceback completo:")
        messages.error(request, f"Error inesperado: {str(e)}")
        return redirect('entrenos:dashboard_liftin')


def importar_liftin_basico(request):
    """
    Vista para importación básica de Liftin (versión simplificada)
    """
    if request.method == 'POST':
        form = ImportarLiftinBasicoForm(request.POST)

        if form.is_valid():
            entrenamiento = form.save()
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


def exportar_datos_liftin(request):
    """
    Vista para exportar datos específicos de Liftin
    """
    if request.method == 'POST':
        form = ExportarDatosForm(request.POST)

        if form.is_valid():
            formato = form.cleaned_data['formato']
            incluir_liftin = form.cleaned_data['incluir_liftin']
            incluir_manual = form.cleaned_data['incluir_manual']
            fecha_desde = form.cleaned_data['fecha_desde']
            fecha_hasta = form.cleaned_data['fecha_hasta']

            # Filtrar entrenamientos
            entrenamientos = EntrenoRealizado.objects.all()

            fuentes = []
            if incluir_liftin:
                fuentes.append('liftin')
            if incluir_manual:
                fuentes.append('manual')

            if fuentes:
                entrenamientos = entrenamientos.filter(fuente_datos__in=fuentes)

            if fecha_desde:
                entrenamientos = entrenamientos.filter(fecha__gte=fecha_desde)

            if fecha_hasta:
                entrenamientos = entrenamientos.filter(fecha__lte=fecha_hasta)

            # Generar exportación según formato
            if formato == 'csv':
                return exportar_csv_liftin(entrenamientos)
            elif formato == 'json':
                return exportar_json_liftin(entrenamientos)
            elif formato == 'pdf':
                return exportar_pdf_liftin(entrenamientos)
    else:
        form = ExportarDatosForm()

    context = {
        'form': form,
        'title': 'Exportar Datos de Liftin',
    }

    return render(request, 'entrenos/exportar_datos_liftin.html', context)


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


def api_stats_liftin(request):
    """
    API para estadísticas específicas de Liftin
    """
    entrenamientos_liftin = EntrenoRealizado.objects.filter(fuente_datos='liftin')

    stats = {
        'total_entrenamientos': entrenamientos_liftin.count(),
        'volumen_total': entrenamientos_liftin.aggregate(Sum('volumen_total_kg'))['volumen_total_kg__sum'] or 0,
        'calorias_total': entrenamientos_liftin.aggregate(Sum('calorias_quemadas'))['calorias_quemadas__sum'] or 0,
        'duracion_promedio': entrenamientos_liftin.aggregate(Avg('duracion_minutos'))['duracion_minutos__avg'] or 0,
        'ejercicios_promedio': entrenamientos_liftin.aggregate(Avg('numero_ejercicios'))['numero_ejercicios__avg'] or 0,
        'fc_promedio': entrenamientos_liftin.aggregate(Avg('frecuencia_cardiaca_promedio'))[
                           'frecuencia_cardiaca_promedio__avg'] or 0,
    }

    # Datos para gráficos por mes
    entrenamientos_por_mes = []
    for i in range(6):  # Últimos 6 meses
        fecha = timezone.now().date() - timedelta(days=30 * i)
        mes_inicio = fecha.replace(day=1)
        if i == 0:
            mes_fin = fecha
        else:
            mes_fin = (mes_inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        count = entrenamientos_liftin.filter(fecha__gte=mes_inicio, fecha__lte=mes_fin).count()
        entrenamientos_por_mes.append({
            'mes': mes_inicio.strftime('%Y-%m'),
            'count': count
        })

    stats['entrenamientos_por_mes'] = list(reversed(entrenamientos_por_mes))

    return JsonResponse(stats)


def api_ejercicios_liftin(request, entrenamiento_id):
    """
    API para obtener ejercicios específicos de un entrenamiento de Liftin
    """
    entrenamiento = get_object_or_404(EntrenoRealizado, id=entrenamiento_id)
    ejercicios = EjercicioLiftinDetallado.objects.filter(entreno=entrenamiento).order_by('orden_ejercicio')

    data = [
        {
            'id': ej.id,
            'nombre': ej.nombre_ejercicio,
            'orden': ej.orden_ejercicio,
            'peso_formateado': ej.peso_formateado,
            'peso_kg': float(ej.peso_kg) if ej.peso_kg else None,
            'repeticiones_formateado': ej.repeticiones_formateado,
            'series': ej.series_realizadas,
            'repeticiones_min': ej.repeticiones_min,
            'repeticiones_max': ej.repeticiones_max,
            'estado': ej.estado_liftin,
            'completado': ej.completado,
            'volumen': ej.volumen_ejercicio,
            'notas': ej.notas_ejercicio,
        }
        for ej in ejercicios
    ]

    return JsonResponse({'ejercicios': data})


# ============================================================================
# VISTAS DE UTILIDADES
# ============================================================================


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


def gestionar_ejercicios_base(request):
    # Lógica para AÑADIR un nuevo ejercicio
    # Usamos un nombre único para el botón de submit para diferenciar acciones
    if request.method == 'POST' and 'add_exercise' in request.POST:
        form = EjercicioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Ejercicio añadido a la base de datos correctamente!')
            return redirect('gestionar_ejercicios_base')  # Redirigimos a la misma página
        else:
            # Si el formulario no es válido, los errores se mostrarán en el template
            messages.error(request, 'Hubo un error. Por favor, revisa los campos del formulario.')

    # Lógica para ELIMINAR los ejercicios seleccionados
    if request.method == 'POST' and 'delete_selected' in request.POST:
        ejercicio_ids_a_eliminar = request.POST.getlist('ejercicio_ids')
        if not ejercicio_ids_a_eliminar:
            messages.warning(request, 'No has seleccionado ningún ejercicio para eliminar.')
        else:
            # Eliminamos los ejercicios de la BD que coincidan con los IDs seleccionados
            EjercicioBase.objects.filter(id__in=ejercicio_ids_a_eliminar).delete()
            count = len(ejercicio_ids_a_eliminar)
            messages.success(request, f'Se han eliminado {count} ejercicio(s) correctamente.')
        return redirect('gestionar_ejercicios_base')

    # Lógica para MOSTRAR la lista (método GET o después de una acción)

    # Búsqueda
    query = request.GET.get('buscar', '')
    ejercicios_list = EjercicioBase.objects.all().order_by('grupo_muscular', 'nombre')
    if query:
        ejercicios_list = ejercicios_list.filter(nombre__icontains=query)

    # Paginación
    paginator = Paginator(ejercicios_list, 15)  # 15 ejercicios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Creamos una instancia vacía del formulario para el panel de "Añadir Ejercicio"
    form_para_anadir = EjercicioForm()

    context = {
        'page_obj': page_obj,
        'form_para_anadir': form_para_anadir,
        'total_ejercicios': paginator.count,
        'query': query,
    }
    # Asegúrate de que la ruta al template sea correcta
    return render(request, 'entrenos/gestionar_ejercicios_base.html', context)


# entrenos/views.py

# ... (otros imports que ya tengas) ...
from django.shortcuts import render
from clientes.models import Cliente
# entrenos/views.py

# entrenos/views.py

# ... (tus otros imports) ...
import json
from datetime import datetime  # Asegúrate de que este import esté presente


# en entrenos/views.py

def vista_entrenamiento_activo(request, cliente_id):
    """
    Muestra el formulario interactivo para que el usuario registre su entrenamiento.
    VERSIÓN FINAL: Los cálculos de aproximación se hacen aquí.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        fecha_str = request.GET.get('fecha')
        if not fecha_str:
            from django.utils import timezone
            fecha_obj = timezone.now().date()
            fecha_str = fecha_obj.strftime('%Y-%m-%d')
        else:
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        fecha_para_template = fecha_obj.strftime('%Y-%m-%d')

        rutina_nombre = request.GET.get('rutina_nombre')
        ejercicios_planificados_json = request.GET.get('ejercicios', '[]')
        ejercicios_planificados = json.loads(ejercicios_planificados_json)

        leyenda_rpe = {
            "10": "Máximo esfuerzo, no podrías hacer ni una repetición más.",
            "9": "Muy intenso, podrías hacer 1 repetición más como máximo.",
            "8": "Intenso, podrías hacer 2-3 repeticiones más.",
            "7": "Moderado, podrías hacer 3-4 repeticiones más.",
            "6": "Fácil, podrías hacer muchas repeticiones más.",
        }

        # --- BIO-BRIDGE: VALIDACIÓN EN TIEMPO REAL Y AJUSTE DE CARGA ---
        from core.bio_context import BioContextProvider

        bio_readiness = BioContextProvider.get_readiness_score(cliente)
        vol_mod = bio_readiness.get('volume_modifier', 1.0)

        bio_rest = BioContextProvider.get_current_restrictions(cliente)
        tags_bloqueados = bio_rest.get('tags', set())

        # --- INICIO DE LA MODIFICACIÓN CLAVE ---
        for i, ejercicio in enumerate(ejercicios_planificados):
            ejercicio['form_id'] = f'ejercicio_{i}'

            # --- Ajuste de Volumen (Bio-Safety) ---
            try:
                series_orig = int(ejercicio.get('series', 3))
                # Si vol_mod < 1.0, reducimos las series de forma proporcional
                series_adj = max(1, round(series_orig * vol_mod))
                ejercicio['series'] = series_adj
            except ValueError:
                pass

            # --- Validación en Tiempo Real (Bio-Safety) ---
            ejercicio['is_bio_blocked'] = False
            ejercicio['bio_blocked_tag'] = ""
            ejercicio['is_hot_substituted'] = False
            if tags_bloqueados:
                # Buscar el ejercicio en la BD de Helms para cruzar tags
                nombre_ej = ejercicio.get('nombre', '')
                from analytics.planificador_helms.utils.helpers import buscar_ejercicio_por_nombre, \
                    obtener_sustituto_en_caliente
                ej_db = buscar_ejercicio_por_nombre(nombre_ej)
                if ej_db:
                    ej_tags = set(ej_db.get('risk_tags', []))
                    interseccion = ej_tags.intersection(tags_bloqueados)
                    if interseccion:
                        # Intentar sustitución en caliente
                        sustituto = obtener_sustituto_en_caliente(nombre_ej, tags_bloqueados)
                        if sustituto:
                            ejercicio['is_hot_substituted'] = True
                            ejercicio['original_name'] = nombre_ej
                            ejercicio['hot_sub_tag'] = list(interseccion)[0].replace('_', ' ').title()
                            ejercicio['nombre'] = sustituto.get('nombre', '')
                            ejercicio['patron'] = sustituto.get('patron', ejercicio.get('patron', ''))
                        else:
                            ejercicio['is_bio_blocked'] = True
                            ejercicio['bio_blocked_tag'] = list(interseccion)[0].replace('_', ' ').title()

            # ── Bio-Safe Substitute detection ──
            ejercicio['is_bio_substitute'] = ejercicio.get('was_bio_substituted', False)
            if ejercicio['is_bio_substitute']:
                ejercicio['bio_substitution_reason'] = ejercicio.get('bio_substitution_reason', {})

            # ── HYROX ICON SYNC & METRIC ASSIGNMENT ──
            nombre_ej_lower = ejercicio.get('nombre', '').lower()
            ejercicio['is_hyrox_station'] = True
            if 'ski' in nombre_ej_lower:
                ejercicio['hyrox_icon'] = '⛷️'
                ejercicio['metric_type'] = 'distance_time'
            elif 'sled push' in nombre_ej_lower:
                ejercicio['hyrox_icon'] = '🛷💨'
                ejercicio['metric_type'] = 'distance_time'
            elif 'sled pull' in nombre_ej_lower:
                ejercicio['hyrox_icon'] = '🛷⛓️'
                ejercicio['metric_type'] = 'distance_time'
            elif 'burpee' in nombre_ej_lower:
                ejercicio['hyrox_icon'] = '🐸'
                ejercicio['metric_type'] = 'reps_weight'
            elif 'row' in nombre_ej_lower or 'remo' in nombre_ej_lower:  # Catch Remo as well just in case
                ejercicio['hyrox_icon'] = '🚣'
                ejercicio['metric_type'] = 'distance_time'
            elif 'farmer' in nombre_ej_lower or 'granjero' in nombre_ej_lower:
                ejercicio['hyrox_icon'] = '⚖️'
                ejercicio['metric_type'] = 'distance_time'
            elif 'sandbag' in nombre_ej_lower or 'zancada' in nombre_ej_lower:  # In hyrox context lunges
                ejercicio['hyrox_icon'] = '🎒'
                ejercicio['metric_type'] = 'reps_weight'
            elif 'wall ball' in nombre_ej_lower:
                ejercicio['hyrox_icon'] = '🏐🎯'
                ejercicio['metric_type'] = 'reps_weight'
            else:
                ejercicio['is_hyrox_station'] = False
                ejercicio['metric_type'] = 'reps_weight'

            # --- Procesamiento de datos del ejercicio (como ya lo tenías) ---
            try:
                reps_str = str(ejercicio.get('repeticiones', '8'))
                ejercicio['reps_objetivo'] = int(reps_str.split('-')[0].strip())
            except (ValueError, AttributeError):
                ejercicio['reps_objetivo'] = 8

            ejercicio['peso_recomendado_kg'] = ejercicio.get('peso_kg', 0.0)

            # --- TIPO DE PROGRESIÓN ---
            # 1. Del planificador (EJERCICIOS_DATABASE ya tiene tipo_progresion)
            # 2. Fallback: EjercicioBase en BD
            # 3. Fallback final: peso_reps
            tipo_prog = None  # Siempre releer desde BD/EJERCICIOS_DATABASE
            if not tipo_prog:
                try:
                    from analytics.planificador_helms.utils.helpers import buscar_ejercicio_por_nombre
                    ej_dict = buscar_ejercicio_por_nombre(ejercicio.get('nombre', ''))
                    tipo_prog = ej_dict.get('tipo_progresion') if ej_dict else None
                except Exception:
                    tipo_prog = None
            if not tipo_prog:
                try:
                    from rutinas.models import EjercicioBase as _EjBase
                    _ej = _EjBase.objects.filter(nombre__iexact=ejercicio.get('nombre', '')).first()
                    tipo_prog = _ej.tipo_progresion if _ej else None
                except Exception:
                    tipo_prog = None
            ejercicio['tipo_progresion'] = tipo_prog or 'peso_reps'

            # Flags de conveniencia para el template
            ejercicio['usa_peso'] = ejercicio['tipo_progresion'] in ('peso_reps', 'peso_corporal_lastre')
            ejercicio['usa_tiempo'] = ejercicio['tipo_progresion'] == 'progresion_tiempo'
            ejercicio['usa_distancia'] = ejercicio['tipo_progresion'] == 'progresion_distancia'
            ejercicio['solo_reps'] = ejercicio['tipo_progresion'] in ('progresion_reps', 'progresion_variante')

            # --- Ajuste de intensidad (Bio-Safety Max RPE) ---
            base_rpe = int(ejercicio.get('rpe_objetivo', 8))
            max_rpe = int(bio_readiness.get('max_rpe', 10))
            ejercicio['rpe_objetivo'] = min(base_rpe, max_rpe)

            ejercicio['tempo'] = ejercicio.get('tempo', '2-0-X-0')
            ejercicio['descanso_minutos'] = ejercicio.get('descanso_minutos', 2)

            # --- OBTENER DATOS DEL ENTRENAMIENTO ANTERIOR ---
            datos_anterior = obtener_ultimo_peso_ejercicio(
                cliente_id=cliente.id,
                nombre_ejercicio=ejercicio.get('nombre', ''),
                fecha_actual=fecha_obj
            )
            if datos_anterior:
                ejercicio['peso_anterior_kg'] = datos_anterior['peso']
                # --- PESO INICIAL PARA INPUTS (prioriza última vez si existe) ---
                try:
                    peso_rec = float(ejercicio.get('peso_recomendado_kg', 0) or 0)
                except:
                    peso_rec = 0.0

                try:
                    peso_ant = float(ejercicio.get('peso_anterior_kg', 0) or 0)
                except:
                    peso_ant = 0.0

                # Si hay peso anterior válido, úsalo como valor inicial (más “real”)
                # Si no, usa el recomendado
                if peso_ant > 0:
                    ejercicio['peso_inicial_kg'] = peso_ant
                else:
                    ejercicio['peso_inicial_kg'] = peso_rec

                ejercicio['fecha_anterior'] = datos_anterior['fecha']
                ejercicio['series_anterior'] = datos_anterior['series']
                ejercicio['repeticiones_anterior'] = datos_anterior['repeticiones']
                ejercicio['volumen_anterior'] = datos_anterior['volumen']
                # Calcular diferencia de peso
                peso_actual = float(ejercicio.get('peso_recomendado_kg', 0) or 0)
                peso_anterior = float(datos_anterior['peso'] or 0)
                ejercicio['diferencia_peso'] = round(peso_actual - peso_anterior, 2)

                # --- OBTENER RÉCORD PERSONAL (PR) ---
                from analytics.utils import estimar_1rm
                try:
                    pr = RecordsService.obtener_mejor_marca(cliente, ejercicio.get('nombre', ''))
                    if pr:
                        ejercicio['pr_peso'] = float(pr.peso_kg)
                        ejercicio['pr_reps'] = pr.repeticiones
                        ejercicio['one_rm_estimado'] = estimar_1rm(float(pr.peso_kg), pr.repeticiones)
                    else:
                        ejercicio['pr_peso'] = 0.0
                        ejercicio['pr_reps'] = 0
                        ejercicio['one_rm_estimado'] = estimar_1rm(float(datos_anterior.get('peso', 0)),
                                                                   int(datos_anterior.get('repeticiones', 1)))
                except Exception:
                    ejercicio['pr_peso'] = 0.0
                    ejercicio['pr_reps'] = 0
                    ejercicio['one_rm_estimado'] = estimar_1rm(float(datos_anterior.get('peso', 0)),
                                                               int(datos_anterior.get('repeticiones', 1)))
            else:
                ejercicio['peso_anterior_kg'] = 0.0
                ejercicio['fecha_anterior'] = None
                ejercicio['series_anterior'] = 0
                ejercicio['repeticiones_anterior'] = 0
                ejercicio['volumen_anterior'] = 0.0
                ejercicio['diferencia_peso'] = 0.0
                ejercicio['one_rm_estimado'] = 0.0
                ejercicio['pr_peso'] = 0.0
                ejercicio['pr_reps'] = 0
                ejercicio['peso_inicial_kg'] = float(ejercicio.get('peso_recomendado_kg', 0) or 0)

            # Calcular aproximaciones basadas en el peso de trabajo
            try:
                peso_trabajo = float(ejercicio.get('peso_inicial_kg') or ejercicio.get('peso_recomendado_kg') or 0)
                if peso_trabajo > 0 and ejercicio.get('usa_peso', True):
                    def redondear_peso(p):
                        return round(round(p / 2.5) * 2.5, 1)
                    ejercicio['aproximaciones'] = {
                        'peso1': redondear_peso(peso_trabajo * 0.50),
                        'peso2': redondear_peso(peso_trabajo * 0.70),
                        'peso3': redondear_peso(peso_trabajo * 0.85),
                    }
                else:
                    ejercicio['aproximaciones'] = None
            except Exception:
                ejercicio['aproximaciones'] = None

    except Exception as e:
        messages.error(request, f"Error al cargar los datos del entrenamiento: {e}")
        return redirect('entrenos:vista_plan_anual', cliente_id=cliente.id)

    # Construir resumen bio para el banner del template
    bio_adjustments = []
    for ej in ejercicios_planificados:
        if ej.get('is_hot_substituted'):
            bio_adjustments.append({
                'tipo': 'sustitucion',
                'mensaje': f"{ej.get('original_name', '')} → {ej.get('nombre', '')} (restricción: {ej.get('hot_sub_tag', '')})"
            })
        if ej.get('is_bio_blocked'):
            bio_adjustments.append({
                'tipo': 'bloqueo',
                'mensaje': f"{ej.get('nombre', '')} bloqueado por restricción: {ej.get('bio_blocked_tag', '')}"
            })
    vol_mod_pct = int(vol_mod * 100)

    # Separar "DÍA 3 - DESCARGA ACTIVA" en dos partes para el header
    _sep = ' - ' if ' - ' in rutina_nombre else (' · ' if ' · ' in rutina_nombre else None)
    if _sep:
        _parts = rutina_nombre.split(_sep, 1)
        rutina_dia = _parts[0].strip()
        rutina_tipo = _parts[1].strip()
    else:
        rutina_dia = ''
        rutina_tipo = rutina_nombre

    context = {
        'cliente': cliente,
        'fecha': fecha_para_template,
        'rutina_nombre': rutina_nombre,
        'rutina_dia': rutina_dia,
        'rutina_tipo': rutina_tipo,
        'ejercicios_planificados': ejercicios_planificados,
        'leyenda_rpe': leyenda_rpe,
        'is_in_transition': bio_readiness.get('is_in_transition', False),
        'transition_days_left': bio_readiness.get('transition_days_left', 0),
        'vol_mod': vol_mod,
        'vol_mod_pct': vol_mod_pct,
        'bio_score': bio_readiness.get('score', 100),
        'bio_adjustments': bio_adjustments,
        'has_bio_adjustments': vol_mod < 1.0 or bool(bio_adjustments),
    }

    # Añadir contexto de gamificación (sin cambios)
    try:
        from .gamificacion_service import EntrenamientoGamificacionService
        resumen_gamificacion = EntrenamientoGamificacionService.obtener_resumen_gamificacion(cliente)
        context['resumen_gamificacion'] = resumen_gamificacion
    except Exception as e:
        logger.warning("Error obteniendo resumen gamificación: %s", e)
        context['resumen_gamificacion'] = {'tiene_perfil': False}

    return render(request, 'entrenos/entrenamiento_activo.html', context)


# en entrenos/views.py

# --- Asegúrate de tener estas importaciones al principio del archivo ---
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import EntrenoRealizado, EjercicioRealizado
from rutinas.models import Rutina
from clientes.models import Cliente
from analytics.utils import estimar_1rm  # ¡La importación que ya solucionamos!


# --------------------------------------------------------------------
# en entrenos/views.py

# ... (importaciones)


def guardar_entrenamiento_activo(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:

        # --- PASO 1: Crear el EntrenoRealizado ---
        fecha = datetime.strptime(request.POST.get('fecha'), '%Y-%m-%d').date()
        rutina_nombre = request.POST.get('rutina_nombre')
        rutina_obj, _ = Rutina.objects.get_or_create(nombre=rutina_nombre)

        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, fecha=fecha, rutina=rutina_obj, fuente_datos='manual',
            duracion_minutos=request.POST.get('duracion_minutos') or None,
            calorias_quemadas=request.POST.get('calorias_quemadas') or None,
            notas_liftin=request.POST.get('notas_liftin', '').strip()
        )

        # --- PASO 2: Procesar ejercicios, calcular 1RM y VOLUMEN ---
        nuevos_rms_sesion = {}
        volumen_total_entreno = Decimal('0.0')
        ejercicios_procesados_count = 0
        todos_rpes_sesion = []

        ejercicio_form_ids = [k.replace('_nombre', '') for k in request.POST if k.endswith('_nombre')]
        for form_id in ejercicio_form_ids:
            ejercicio_nombre = request.POST.get(f'{form_id}_nombre', '').strip().title()
            if not ejercicio_nombre: continue

            nombre_normalizado = ejercicio_nombre.lower()
            mejor_rm_ejercicio = 0
            volumen_ejercicio = Decimal('0.0')  # Inicializamos el volumen por ejercicio

            series_data_para_guardar = []

            tipo_progresion = request.POST.get(f'{form_id}_tipo_progresion', 'peso_reps')
            usa_peso = tipo_progresion in ('peso_reps', 'peso_corporal_lastre')

            for i in range(1, 11):
                peso_key, reps_key = f"{form_id}_peso_{i}", f"{form_id}_reps_{i}"
                if reps_key not in request.POST: break

                try:
                    peso_str = request.POST.get(peso_key, '0').replace(',', '.')
                    reps_str = request.POST.get(reps_key, '0')
                    rpe_str = request.POST.get(f"{form_id}_rpe_{i}", '')

                    peso = float(peso_str) if peso_str else 0.0
                    reps = int(reps_str) if reps_str else 0
                    rpe_real = float(rpe_str.replace(',', '.')) if rpe_str else None

                    serie_valida = (peso > 0 and reps > 0) if usa_peso else (reps > 0)

                    if serie_valida:
                        if peso > 0:
                            volumen_ejercicio += (Decimal(str(peso)) * Decimal(reps))
                        if peso > 0 and reps > 0:
                            rpe_a_usar = rpe_real if rpe_real is not None else 8
                            rm_serie_actual = estimar_1rm_con_rpe(peso, reps, rpe_a_usar)
                            if rm_serie_actual > mejor_rm_ejercicio:
                                mejor_rm_ejercicio = rm_serie_actual
                        series_data_para_guardar.append(
                            {'peso': peso, 'reps': reps, 'rpe_real': rpe_real, 'tipo_progresion': tipo_progresion})
                        if rpe_real is not None:
                            todos_rpes_sesion.append(rpe_real)

                except (ValueError, TypeError, InvalidOperation):
                    continue

            if series_data_para_guardar:
                if mejor_rm_ejercicio > 0:
                    nuevos_rms_sesion[nombre_normalizado] = round(mejor_rm_ejercicio, 2)

                # Guardar el EjercicioRealizado (agregado)
                pesos_validos = [s['peso'] for s in series_data_para_guardar if s['peso'] > 0]
                peso_promedio = sum(pesos_validos) / len(pesos_validos) if pesos_validos else 0.0
                reps_promedio = sum(s['reps'] for s in series_data_para_guardar) // len(series_data_para_guardar)

                # Calcular RPE promedio (si hay datos)
                rpes_validos = [s['rpe_real'] for s in series_data_para_guardar if s['rpe_real'] is not None]
                rpe_promedio_ejercicio = None
                if rpes_validos:
                    rpe_promedio_ejercicio = int(round(sum(rpes_validos) / len(rpes_validos)))

                # Intentar obtener el grupo muscular desde EjercicioBase para clasificar y para crear SeriesRealizadas
                grupo = None
                ej_base = None
                try:
                    ej_base = EjercicioBase.objects.filter(nombre__iexact=ejercicio_nombre).first()
                    if ej_base:
                        grupo = ej_base.grupo_muscular
                except Exception:
                    pass

                # Extraer is_recovery_load del formulario (campo por ejercicio)
                is_recovery_load_str = request.POST.get(f'{form_id}_is_recovery_load', 'false').lower()
                is_recovery_load = is_recovery_load_str == 'true'

                # Extraer datos de molestia reportada intra-entreno
                molestia_reportada = request.POST.get(f'{form_id}_molestia_reportada', 'false').lower() == 'true'
                molestia_zona = request.POST.get(f'{form_id}_molestia_zona', '')
                molestia_sev_str = request.POST.get(f'{form_id}_molestia_severidad', '')
                molestia_severidad = int(molestia_sev_str) if molestia_sev_str.isdigit() else None
                molestia_descripcion = request.POST.get(f'{form_id}_molestia_descripcion', '')

                ej_realizado = EjercicioRealizado.objects.create(
                    entreno=entreno, nombre_ejercicio=ejercicio_nombre,
                    peso_kg=peso_promedio, series=len(series_data_para_guardar),
                    repeticiones=reps_promedio, fuente_datos='manual',
                    grupo_muscular=grupo, completado=True,
                    rpe=rpe_promedio_ejercicio,
                    is_recovery_load=is_recovery_load,
                    molestia_reportada=molestia_reportada,
                    molestia_zona=molestia_zona,
                    molestia_severidad=molestia_severidad,
                    molestia_descripcion=molestia_descripcion,
                )

                # CREAR SERIES REALIZADAS INDIVIDUALES (Importante para gráficas de detalle)
                if ej_base:
                    for idx, s_data in enumerate(series_data_para_guardar, 1):
                        SerieRealizada.objects.create(
                            entreno=entreno,
                            ejercicio=ej_base,
                            serie_numero=idx,
                            repeticiones=int(s_data['reps']),
                            peso_kg=Decimal(str(s_data['peso'])),
                            rpe_real=s_data['rpe_real'],
                            completado=True
                        )

                # Acumulamos el volumen de este ejercicio al total del entreno
                volumen_total_entreno += volumen_ejercicio
                ejercicios_procesados_count += 1

        # =======================================================
        # ¡PASO 3: ACTUALIZAR EL ENTRENAMIENTO CON LOS TOTALES!
        # =======================================================
        if ejercicios_procesados_count > 0:
            entreno.volumen_total_kg = volumen_total_entreno
            entreno.numero_ejercicios = ejercicios_procesados_count
            entreno.save(update_fields=['volumen_total_kg', 'numero_ejercicios'])
        # =======================================================

        # --- PASO 4: Actualizar el perfil del cliente con los nuevos 1RM ---
        if nuevos_rms_sesion:
            # ... (lógica de actualización de one_rm_data sin cambios) ...
            if not cliente.one_rm_data:
                cliente.one_rm_data = {}
            cliente.one_rm_data.update(nuevos_rms_sesion)
            cliente.save(update_fields=['one_rm_data'])
            messages.info(request, "¡Récords de fuerza actualizados!")

        messages.success(request, "¡Entrenamiento guardado con éxito!")

        # ============================================================================
        # INTEGRACIÓN SISTEMA DE GAMIFICACIÓN
        # ============================================================================
        try:
            # Capturar métricas de la sesión (vienen de inputs hidden inyectados por JS)
            duracion_real = request.POST.get('duracion_minutos_real')
            series_comp = request.POST.get('series_completadas')
            series_tot = request.POST.get('series_totales')
            ejs_comp = request.POST.get('ejercicios_completados')
            ejs_tot = request.POST.get('ejercicios_totales')
            volumen_sesion = request.POST.get('volumen_total_sesion')
            rpe_medio = request.POST.get('rpe_medio_sesion')

            # Calcular RPE medio real de la sesión basado en los datos guardados
            rpe_medio_calculado = None
            if todos_rpes_sesion:
                rpe_medio_calculado = sum(todos_rpes_sesion) / len(todos_rpes_sesion)

            # Usar el calculado si existe, si no intentar con el del POST
            rpe_final = rpe_medio_calculado if rpe_medio_calculado is not None else (
                float(rpe_medio) if rpe_medio else None)

            # Solo si tenemos datos mínimos, creamos la sesión de gamificación
            if any([series_comp, series_tot, ejs_comp, volumen_sesion]):
                # Calcular ACWR real usando el servicio de estadísticas
                acwr_actual = 1.0
                try:
                    from .services.estadisticas_service import EstadisticasService
                    acwr_data = EstadisticasService.analizar_acwr(cliente)
                    acwr_actual = acwr_data.get('acwr_actual', 1.0)
                except Exception as e:
                    logger.warning("Error calculando ACWR: %s", e)

                sesion_gam = SesionGamificacion.objects.create(
                    entreno=entreno,
                    duracion_minutos=int(duracion_real) if duracion_real else (entreno.duracion_minutos or 0),
                    series_completadas=int(series_comp) if series_comp else 0,
                    series_totales=int(series_tot) if series_tot else 0,
                    ejercicios_completados=int(ejs_comp) if ejs_comp else 0,
                    ejercicios_totales=int(ejs_tot) if ejs_tot else 0,
                    volumen_sesion=Decimal(str(volumen_sesion)) if volumen_sesion else (entreno.volumen_total_kg or 0),
                    rpe_medio=rpe_final,
                    acwr=acwr_actual
                )

                # 1. Detectar Récords Personales
                records_nuevos = RecordsService.detectar_records_sesion(entreno)
                sesion_gam.nuevos_records = len(records_nuevos)
                sesion_gam.save()

                if records_nuevos:
                    messages.success(request, f"🏆 ¡HAS LOGRADO {len(records_nuevos)} NUEVOS RÉCORDS PERSONALES!")

                # 2. Verificar Logros
                logros_nuevos = LogrosService.verificar_logros_sesion(sesion_gam)
                for logro in logros_nuevos:
                    messages.success(request, f"🌟 ¡LOGRO DESBLOQUEADO: {logro.nombre}! {logro.icono}")

                # 3. Actualizar Desafíos Semanales
                desafios_activos = DesafioSemanal.objects.filter(
                    activo=True,
                    fecha_inicio__lte=entreno.fecha,
                    fecha_fin__gte=entreno.fecha
                )

                for desafio in desafios_activos:
                    progreso, _ = ProgresoDesafio.objects.get_or_create(
                        cliente=cliente,
                        desafio=desafio
                    )

                    # Calcular incremento según el tipo de objetivo
                    incremento = 0
                    if desafio.objetivo_tipo == 'sesiones':
                        incremento = 1
                    elif desafio.objetivo_tipo == 'volumen':
                        incremento = sesion_gam.volumen_sesion
                    elif desafio.objetivo_tipo == 'ejercicios':
                        incremento = sesion_gam.ejercicios_completados
                    elif desafio.objetivo_tipo == 'rachas':
                        incremento = LogrosService._calcular_racha_actual(cliente)

                    if incremento > 0:
                        is_newly_completed = progreso.actualizar_progreso(incremento)
                        if is_newly_completed:
                            messages.success(request,
                                             f"🎯 ¡HAS COMPLETADO EL DESAFÍO: {desafio.nombre}! +{desafio.recompensa_puntos} pts")

        except Exception as e:
            logger.warning("Error en sistema de gamificación: %s", e)
            # No bloqueamos el flujo principal si falla algo de gamificación
        # ============================================================================

        return redirect('entrenos:dashboard_evolucion', cliente_id=cliente.id)

    except Exception as e:
        # ... (manejo de errores sin cambios) ...
        messages.error(request, f"Hubo un error crítico al guardar: {e}")
        return redirect('clientes:panel_cliente')


# --- Asegúrate de tener todas estas importaciones al principio del archivo ---
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from clientes.models import Cliente
from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
from analytics.views import CalculadoraEjerciciosTabla
from analytics.validador_jerarquia_helms import validar_adherencia_basica
from analytics.sistema_educacion_helms import agregar_educacion_a_plan
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
# ========== VISTA ACTUALIZADA CON SERIALIZACIÓN ==========

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import date, timedelta
import calendar
import json

# ✅ IMPORTAR LA FUNCIÓN DE SERIALIZACIÓN
from entrenos.serializador_plan import serializar_plan_para_sesion


def vista_plan_anual(request, cliente_id):
    """
    Vista para generar y mostrar el plan anual de Helms.
    VERSIÓN OPTIMIZADA CON SERIALIZACIÓN CORRECTA.
    """
    try:
        # --- PASO 1: Obtener cliente y datos de navegación del calendario ---
        cliente_obj = get_object_or_404(Cliente, id=cliente_id)

        # Definir año y mes solicitados (o actuales)
        año_param = request.GET.get('año', '')
        mes_param = request.GET.get('mes', '')

        # Manejar strings vacíos
        try:
            año_solicitado = int(año_param) if año_param else date.today().year
        except ValueError:
            año_solicitado = date.today().year

        try:
            mes_solicitado = int(mes_param) if mes_param else date.today().month
        except ValueError:
            mes_solicitado = date.today().month

        año_actual = año_solicitado  # Usar el solicitado para el calendario
        mes_actual = mes_solicitado  # Usar el solicitado para el calendario

        # --- PASO 2: Calcular 1RM ---
        maximos_actuales = cliente_obj.one_rm_data or {}

        # --- PASO 3: Crear perfil y VALIDAR ADHERENCIA ---
        perfil = crear_perfil_desde_cliente(cliente_obj)
        perfil.maximos_actuales = maximos_actuales

        # ✅ PASAR EL AÑO SOLICITADO AL PERFIL PARA QUE EL PLANIFICADOR LO USE
        perfil.año_planificacion = año_solicitado

        validacion_adherencia = validar_adherencia_basica(perfil)

        if not validacion_adherencia.puede_avanzar:
            context = {
                'cliente': cliente_obj, 'error': True, 'validacion_fallida': True,
                'validacion': validacion_adherencia,
            }
            return render(request, 'entrenos/vista_plan_calendario.html', context)

        # --- PASO 4: Generar y Enriquecer el Plan (con caché 30 min) ---
        _plan_cache_key = f'plan_anual_{cliente_id}_{año_solicitado}'
        plan = cache.get(_plan_cache_key)
        if plan is None:
            planificador = PlanificadorHelms(perfil)
            plan_original = planificador.generar_plan_anual()
            plan = agregar_educacion_a_plan(plan_original)
            if plan and isinstance(plan, dict):
                cache.set(_plan_cache_key, plan, 1800)

        if not plan or not isinstance(plan, dict):
            raise Exception("El plan generado está vacío o tiene un formato incorrecto.")

        # --- PASO 5: SERIALIZAR EL PLAN ANTES DE GUARDAR EN SESIÓN ---
        plan_serializado = serializar_plan_para_sesion(plan)
        request.session[f'plan_anual_{cliente_id}'] = plan_serializado
        request.session.modified = True

        # === DETECCIÓN DE FASE ACTUAL Y TEMA DINÁMICO ===
        hoy = date.today()

        # Detectar fase actual basada en la semana actual
        fase_actual = None
        semana_actual = 1
        total_semanas_fase = 1
        progreso_fase = 0

        # Acceder a la estructura correcta del plan y calcular fechas
        bloques = plan.get('plan_por_bloques', [])

        # Calcular fechas para cada bloque basándose en la duración
        from datetime import timedelta
        fecha_inicio_plan = date(año_solicitado, 1, 1)  # Empezar desde enero del año solicitado

        # Ajustar al próximo lunes si no es lunes
        dias_hasta_lunes = (7 - fecha_inicio_plan.weekday()) % 7  # 0 = lunes, 6 = domingo
        if dias_hasta_lunes > 0:
            fecha_cursor = fecha_inicio_plan + timedelta(days=dias_hasta_lunes)
        else:
            fecha_cursor = fecha_inicio_plan

        for bloque in bloques:
            duracion_semanas = bloque.get('duracion', 4)  # Default 4 semanas si no está definido

            # Calcular fechas (las fases siempre comienzan en lunes)
            bloque['fecha_inicio'] = fecha_cursor
            bloque['fecha_fin'] = fecha_cursor + timedelta(weeks=duracion_semanas) - timedelta(days=1)

            # Mover el cursor para el siguiente bloque (próximo lunes)
            fecha_cursor = bloque['fecha_fin'] + timedelta(days=1)

        # Buscar la fase actual
        for bloque in bloques:
            fecha_inicio = bloque.get('fecha_inicio')
            fecha_fin = bloque.get('fecha_fin')

            if fecha_inicio and fecha_fin:
                if fecha_inicio <= hoy <= fecha_fin:
                    fase_actual = bloque
                    # Calcular progreso basado en días (no semanas)
                    dias_transcurridos = (hoy - fecha_inicio).days
                    duracion_total_dias = (fecha_fin - fecha_inicio).days + 1  # +1 para incluir el último día
                    progreso_fase = min((dias_transcurridos / duracion_total_dias) * 100, 100)

                    # Calcular semana actual para display
                    semana_actual = (dias_transcurridos // 7) + 1
                    total_semanas_fase = bloque.get('duracion', 1)

                    break

        # === CALCULAR PRÓXIMA FASE ===
        proxima_fase = None
        dias_hasta_proxima_fase = 0

        for bloque in bloques:
            fecha_inicio = bloque.get('fecha_inicio')
            if fecha_inicio and fecha_inicio > hoy:
                proxima_fase = bloque
                dias_hasta_proxima_fase = (fecha_inicio - hoy).days
                break

        # === CALCULAR PROYECCIONES DE EJERCICIOS (PARA TODAS LAS FASES) ===
        proyecciones_totales = {}
        proyecciones_fase = []

        # Definir configuración por tipo de fase
        config_fases = {
            'hipertrofia': {
                'ejercicios': ['Press Banca', 'Sentadilla', 'Peso Muerto', 'Press Militar'],
                'incremento': 3.5  # 3-5% en 6 semanas
            },
            'fuerza': {
                'ejercicios': ['Press Banca', 'Sentadilla', 'Peso Muerto', 'Press Militar'],
                'incremento': 7.5  # 5-10% en 4 semanas
            },
            'potencia': {
                'ejercicios': ['Press Banca', 'Sentadilla', 'Power Clean'],
                'incremento': 2.5  # 2-3% en 3 semanas
            }
        }

        from entrenos.models import EjercicioRealizado
        from django.db.models import Max

        # Bulk query: máximo peso por ejercicio para este cliente (1 query total)
        # Usamos keywords flexibles para tolerar variantes de nombres ("Press de Banca", "Sentadilla Libre", etc.)
        _EJERCICIO_KEYWORDS = {
            'Press Banca':   ['banca', 'bench'],
            'Sentadilla':    ['sentadilla', 'squat'],
            'Peso Muerto':   ['muerto', 'deadlift'],
            'Press Militar': ['militar', 'overhead', ' ohp'],
            'Power Clean':   ['power clean', 'cargada'],
        }
        _proy_cache_key = f'proyecciones_plan_{cliente_id}'
        _pesos_max = cache.get(_proy_cache_key)
        if _pesos_max is None:
            _pesos_max = {}
            _registros = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente_obj,
                peso_kg__isnull=False,
            ).values('nombre_ejercicio').annotate(max_peso=Max('peso_kg'))
            for r in _registros:
                nombre_lower = r['nombre_ejercicio'].lower()
                for canonical, keywords in _EJERCICIO_KEYWORDS.items():
                    if any(kw in nombre_lower for kw in keywords):
                        if canonical not in _pesos_max or float(r['max_peso']) > _pesos_max[canonical]:
                            _pesos_max[canonical] = float(r['max_peso'])
            cache.set(_proy_cache_key, _pesos_max, 1800)

        # Calcular proyecciones para CADA tipo de fase usando los pesos en memoria
        for tipo, config in config_fases.items():
            proyecciones_tipo = []
            for ejercicio_nombre in config['ejercicios']:
                peso_actual = _pesos_max.get(ejercicio_nombre)
                if peso_actual:
                    peso_proyectado = peso_actual * (1 + config['incremento'] / 100)
                    incremento = peso_proyectado - peso_actual
                    proyecciones_tipo.append({
                        'nombre': ejercicio_nombre,
                        'peso_actual': peso_actual,
                        'peso_proyectado': round(peso_proyectado, 1),
                        'incremento': round(incremento, 1),
                        'incremento_porcentaje': config['incremento']
                    })
            proyecciones_totales[tipo] = proyecciones_tipo

        # Asignar proyecciones de la fase actual para renderizado inicial
        if fase_actual:
            objetivo = fase_actual.get('objetivo', '').lower()
            tipo_fase = fase_actual.get('tipo_fase', '').lower()

            fase_key = None
            if 'hipertrofia' in objetivo or 'hipertrofia' in tipo_fase:
                fase_key = 'hipertrofia'
            elif 'fuerza' in objetivo or 'fuerza' in tipo_fase:
                fase_key = 'fuerza'
            elif 'potencia' in objetivo or 'potencia' in tipo_fase:
                fase_key = 'potencia'

            # En descarga: buscar el próximo bloque no-descarga para mostrar sus objetivos
            if fase_key is None:
                idx_actual = next((i for i, b in enumerate(bloques) if b is fase_actual), None)
                if idx_actual is not None:
                    for bloque_sig in bloques[idx_actual + 1:]:
                        obj_sig = bloque_sig.get('objetivo', '').lower()
                        if 'hipertrofia' in obj_sig:
                            fase_key = 'hipertrofia'
                            break
                        elif 'fuerza' in obj_sig:
                            fase_key = 'fuerza'
                            break
                        elif 'potencia' in obj_sig:
                            fase_key = 'potencia'
                            break

            if fase_key:
                # Recalcular proyecciones ESPECÍFICAS para la fase actual con fechas
                # Queremos mostrar: Peso Inicial (Al empezar fase) -> Peso Actual (Max en fase) -> Objetivo (Basado en inicial)

                proyecciones_fase = []
                config_actual = config_fases.get(fase_key)
                fecha_inicio_fase = fase_actual.get('fecha_inicio')

                if config_actual and fecha_inicio_fase:
                    # Helper: colapsa filas DB (nombres variantes) a nombres canónicos tomando el máximo
                    def _colapsar_con_keywords(qs):
                        resultado = {}
                        for r in qs:
                            nombre_lower = r['nombre_ejercicio'].lower()
                            for canonical, kws in _EJERCICIO_KEYWORDS.items():
                                if any(kw in nombre_lower for kw in kws):
                                    v = float(r['max_peso'])
                                    if canonical not in resultado or v > resultado[canonical]:
                                        resultado[canonical] = v
                        return resultado

                    _antes = _colapsar_con_keywords(
                        EjercicioRealizado.objects.filter(
                            entreno__cliente=cliente_obj,
                            peso_kg__isnull=False,
                            entreno__fecha__lt=fecha_inicio_fase
                        ).values('nombre_ejercicio').annotate(max_peso=Max('peso_kg'))
                    )
                    _durante = _colapsar_con_keywords(
                        EjercicioRealizado.objects.filter(
                            entreno__cliente=cliente_obj,
                            peso_kg__isnull=False,
                            entreno__fecha__gte=fecha_inicio_fase
                        ).values('nombre_ejercicio').annotate(max_peso=Max('peso_kg'))
                    )

                    for ejercicio_nombre in config_actual['ejercicios']:
                        peso_inicial = _antes.get(ejercicio_nombre, 0)
                        peso_max_fase = _durante.get(ejercicio_nombre, 0)

                        # Peso Actual es el mayor entre el inicial y el logrado en fase
                        # (Si no ha entrenado en la fase, es el inicial. Si ha mejorado, es el de fase)
                        peso_actual = max(peso_inicial, peso_max_fase)

                        # 3. Objetivo: Basado en el peso INICIAL (Meta fija para la fase)
                        # Si no hay peso inicial, usamos el actual como base (o 0)
                        base_calculo = peso_inicial if peso_inicial > 0 else peso_actual

                        if base_calculo > 0:
                            peso_objetivo = base_calculo * (1 + config_actual['incremento'] / 100)
                            incremento = peso_objetivo - base_calculo

                            # Calcular progreso real
                            # (Actual - Inicial) / (Objetivo - Inicial)
                            # Si Actual > Objetivo, es > 100%
                            progreso_real = 0
                            if peso_objetivo > base_calculo:
                                progreso_real = (peso_actual - base_calculo) / (peso_objetivo - base_calculo) * 100
                                progreso_real = max(0, min(progreso_real,
                                                           100))  # Limitar 0-100 para barra (o dejar pasar 100 para celebrar)

                            proyecciones_fase.append({
                                'nombre': ejercicio_nombre,
                                'peso_inicial': round(peso_inicial, 1),  # NUEVO
                                'peso_actual': round(peso_actual, 1),
                                'peso_objetivo': round(peso_objetivo, 1),  # NUEVO NOMBRE COMPATIBLE
                                'peso_proyectado': round(peso_objetivo, 1),  # MANTENER COMPATIBILIDAD
                                'incremento': round(incremento, 1),
                                'incremento_porcentaje': config_actual['incremento'],
                                'progreso_pct': round(progreso_real, 1)  # NUEVO CAMPO PROGRESO REAL
                            })
                else:
                    # Fallback si no hay fechas (usar lógica generica)
                    proyecciones_fase = proyecciones_totales.get(fase_key, [])

                # IMPORTANT: Actualizar el diccionario total para que el JSON del frontend tenga los datos correctos
                proyecciones_totales[fase_key] = proyecciones_fase


        # Calcular tema de colores según tipo de fase
        tema_fase = {
            'primary': '#00D4FF',
            'secondary': '#8B5CF6',
            'glow': 'rgba(0, 212, 255, 0.5)',
            'bg': 'rgba(0, 212, 255, 0.15)',
            'r1': 0, 'g1': 212, 'b1': 255,  # Cyan
            'r2': 139, 'g2': 92, 'b2': 246,  # Purple
            'icon': '💪'
        }

        objetivo_fase = "Entrenamiento general"

        if fase_actual:
            objetivo = fase_actual.get('objetivo', '').lower()
            tipo_fase = fase_actual.get('tipo_fase', '').lower()

            # Hipertrofia - Azul/Cyan
            if 'hipertrofia' in objetivo or 'hipertrofia' in tipo_fase:
                tema_fase = {
                    'primary': '#00D4FF',
                    'secondary': '#0EA5E9',
                    'glow': 'rgba(0, 212, 255, 0.5)',
                    'bg': 'rgba(0, 212, 255, 0.15)',
                    'r1': 0, 'g1': 212, 'b1': 255,
                    'r2': 14, 'g2': 165, 'b2': 233,
                    'icon': '💪'
                }
                objetivo_fase = "Maximizar volumen muscular y crecimiento"

            # Fuerza - Rosa/Magenta
            elif 'fuerza' in objetivo or 'fuerza' in tipo_fase:
                tema_fase = {
                    'primary': '#FF2D92',
                    'secondary': '#EC4899',
                    'glow': 'rgba(255, 45, 146, 0.5)',
                    'bg': 'rgba(255, 45, 146, 0.15)',
                    'r1': 255, 'g1': 45, 'b1': 146,
                    'r2': 236, 'g2': 72, 'b2': 153,
                    'icon': '⚡'
                }
                objetivo_fase = "Incrementar fuerza máxima (1RM)"

            # Potencia - Amarillo/Naranja
            elif 'potencia' in objetivo or 'potencia' in tipo_fase:
                tema_fase = {
                    'primary': '#FFB800',
                    'secondary': '#F59E0B',
                    'glow': 'rgba(255, 184, 0, 0.5)',
                    'bg': 'rgba(255, 184, 0, 0.15)',
                    'r1': 255, 'g1': 184, 'b1': 0,
                    'r2': 245, 'g2': 158, 'b2': 11,
                    'icon': '🔥'
                }
                objetivo_fase = "Desarrollar velocidad y explosividad"

            # Descarga - Morado/Violeta
            elif 'descarga' in objetivo or 'descarga' in tipo_fase or 'deload' in objetivo:
                tema_fase = {
                    'primary': '#A855F7',
                    'secondary': '#9333EA',
                    'glow': 'rgba(168, 85, 247, 0.5)',
                    'bg': 'rgba(168, 85, 247, 0.15)',
                    'r1': 168, 'g1': 85, 'b1': 247,
                    'r2': 147, 'g2': 51, 'b2': 234,
                    'icon': '🌙'
                }
                objetivo_fase = "Recuperación activa y regeneración"

        # Extraer parámetros de la fase
        parametros_fase = {
            'rpe_min': 6,
            'rpe_max': 10,
            'reps_min': 1,
            'reps_max': 20,
            'series': '3-5'
        }

        if fase_actual:
            parametros_fase = {
                'rpe_min': fase_actual.get('rpe_min', 6),
                'rpe_max': fase_actual.get('rpe_max', 10),
                'reps_min': fase_actual.get('reps_min', 1),
                'reps_max': fase_actual.get('reps_max', 20),
                'series': fase_actual.get('series', '3-5')
            }

        # --- PASO 6: Preparar el contexto SOLO con datos del calendario ---
        matriz_mes = calendar.monthcalendar(año_actual, mes_actual)
        primer_dia_mes = date(año_actual, mes_actual, 1)
        mes_anterior = primer_dia_mes - timedelta(days=1)
        mes_siguiente = (primer_dia_mes + timedelta(days=31)).replace(day=1)
        semanas_calendario = []

        for semana_matriz in matriz_mes:
            dias_semana = []
            for dia_num in semana_matriz:
                if dia_num == 0:
                    dias_semana.append(None)
                else:
                    fecha_actual = date(año_actual, mes_actual, dia_num)
                    dias_semana.append({
                        "numero": dia_num,
                        "es_hoy": fecha_actual == hoy,
                        "fecha_iso": fecha_actual.isoformat()
                    })
            semanas_calendario.append(dias_semana)

        # --- PASO 7: Contexto LIGERO para la plantilla ---
        import json

        # Preparar bloques para JSON (convertir dates a strings)
        bloques_para_json = [{
            'nombre': b.get('nombre'),
            'objetivo': b.get('objetivo'),
            'fecha_inicio': b.get('fecha_inicio').isoformat() if b.get('fecha_inicio') else None,
            'fecha_fin': b.get('fecha_fin').isoformat() if b.get('fecha_fin') else None,
            'duracion': b.get('duracion'),
            'rpe_min': b.get('rpe_min', 6),
            'rpe_max': b.get('rpe_max', 10),
            'reps_min': b.get('reps_min', 1),
            'reps_max': b.get('reps_max', 20),
            'descripcion': b.get('descripcion', ''),
        } for b in bloques]

        context = {
            'cliente': cliente_obj,
            'plan': plan,  # Añadir el plan completo para acceder a bloques
            'calendario': {
                'semanas': semanas_calendario,
                'nombre_mes': calendar.month_name[mes_actual],
                'año': año_actual,
                'mes_num': mes_actual
            },
            'nav': {
                'anterior': {'año': mes_anterior.year, 'mes': mes_anterior.month},
                'siguiente': {'año': mes_siguiente.year, 'mes': mes_siguiente.month}
            },
            # Tema dinámico de fase
            'fase_actual': fase_actual,
            'tema_fase': tema_fase,
            'objetivo_fase': objetivo_fase,
            'parametros_fase': parametros_fase,
            'semana_actual': semana_actual,
            'total_semanas_fase': total_semanas_fase,
            'progreso_fase': float(f"{progreso_fase:.1f}"),
            'today': hoy,  # Para comparaciones en el template
            # Próxima fase
            'proxima_fase': proxima_fase,
            'dias_hasta_proxima_fase': dias_hasta_proxima_fase,
            # Proyecciones de ejercicios
            'proyecciones_fase': proyecciones_fase,
            'proyecciones_json': json.dumps(proyecciones_totales),
            # Bloques en JSON para JavaScript
            'bloques_json': json.dumps(bloques_para_json),
        }

        return render(request, 'entrenos/vista_plan_calendario.html', context)

    except Exception as e:
        logger.exception("Error en vista_plan_anual: %s", e)
        error_context = {
            'error': True,
            'error_message': str(e),
            'error_type': type(e).__name__,
            'cliente': cliente_obj if 'cliente_obj' in locals() else None,
        }
        return render(request, 'entrenos/vista_plan_calendario.html', error_context)


# Archivo: entrenos/views.py
# AGREGAR ESTA FUNCIÓN ANTES DE ajax_obtener_entrenamiento_dia
def obtener_o_generar_plan(request, cliente_id):
    """
    Función auxiliar que obtiene el plan de la sesión o lo genera si no existe.
    Útil para endpoints API que no tienen sesión activa (app móvil).

    ✅ Además NORMALIZA el formato de ejercicios para que coincida con:
      - vista_plan_calendario.html (JS): ej.rpe, entrenamiento.fase_css
      - entrenamiento_activo.html (Django): peso_recomendado_kg, reps_objetivo, form_id
    """
    from clientes.models import Cliente
    from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
    from analytics.sistema_educacion_helms import agregar_educacion_a_plan
    from .serializador_plan import serializar_plan_para_sesion
    from datetime import date

    # -------------------------
    # Normalizadores internos
    # -------------------------
    def _derivar_fase_css(nombre_rutina: str) -> str:
        # nombre_rutina típico: "Día 1 - Hipertrofia"
        try:
            fase_nombre = (nombre_rutina or "").split(" - ")[1].lower().strip()
            fase_css_safe = fase_nombre.replace(" ", "_").replace("-", "_")
            fase_base = fase_css_safe.split("_")[0]  # hipertrofia/fuerza/potencia/descarga
            return f"fase-{fase_base}"
        except Exception:
            return "fase-default"

    def _normalizar_ejercicio_ui(ej: dict, idx: int) -> dict:
        # Mantén todo lo que ya existe, y añade aliases/compatibilidad UI
        out = dict(ej or {})

        nombre = (out.get("nombre") or "").strip()
        nombre_l = nombre.lower()

        # Alias para el template Django del entreno diario
        # - espera: peso_recomendado_kg, reps_objetivo, form_id
        if "peso_recomendado_kg" not in out:
            out["peso_recomendado_kg"] = out.get("peso_kg")
        if "reps_objetivo" not in out:
            out["reps_objetivo"] = out.get("repeticiones")
        if "form_id" not in out:
            out["form_id"] = f"ej_{idx}"

        # Alias para el calendario (tu JS intenta leer ej.rpe)
        if "rpe" not in out:
            out["rpe"] = out.get("rpe_objetivo")

        # Mancuernas (si quieres display por mano sin romper estándar interno)
        es_mancuerna = any(k in nombre_l for k in ["mancuerna", "mancuernas", "db "])
        if es_mancuerna:
            if "peso_formato" not in out:
                out["peso_formato"] = "por_mancuerna"
            if "peso_por_mancuerna_kg" not in out:
                peso_total = out.get("peso_kg")
                if isinstance(peso_total, (int, float)):
                    out["peso_por_mancuerna_kg"] = round(peso_total / 2.0, 1)
        else:
            if "peso_formato" not in out:
                out["peso_formato"] = "total"

        return out

    def _normalizar_plan_ui(plan: dict) -> dict:
        if not isinstance(plan, dict):
            return plan

        entrenos = plan.get("entrenos_por_fecha")
        if not isinstance(entrenos, dict):
            return plan

        for fecha_iso, entreno in entrenos.items():
            if not isinstance(entreno, dict):
                continue

            # Asegurar fase_css (tu calendario lo usa; si no, cae a hipertrofia)
            entreno["fase_css"] = entreno.get("fase_css") or _derivar_fase_css(entreno.get("nombre_rutina", ""))

            # Normalizar ejercicios
            ejercicios = entreno.get("ejercicios") or []
            if isinstance(ejercicios, list):
                entreno["ejercicios"] = [_normalizar_ejercicio_ui(ej, i) for i, ej in enumerate(ejercicios)]

        return plan

    # -------------------------
    # Lógica original
    # -------------------------

    from django.core.cache import cache
    if cache.get(f"bio_needs_regen_{cliente_id}"):
        logger.info("Regenerando plan anual: lesiones cambiaron (bio_needs_regen).")
        request.session.pop(f'plan_anual_{cliente_id}', None)
        request.session.pop(f'plan_anual_v2_{cliente_id}', None)
        cache.delete(f"bio_needs_regen_{cliente_id}")

    # Obtener el año solicitado (si no se especifica, se asume el año actual)
    try:
        año_solicitado = int(request.GET.get('año'))
    except (TypeError, ValueError):
        año_solicitado = date.today().year

    # 1. Intentar obtener del caché Django (compartido entre views y AJAX)
    _cache_key = f'plan_anual_{cliente_id}_{año_solicitado}'
    plan = cache.get(_cache_key)
    if plan:
        return plan

    # 2. Fallback: intentar obtener de la sesión
    plan = request.session.get(f'plan_anual_v2_{cliente_id}')

    # Si el plan existe en sesión, verificar si el año del plan coincide
    if plan:
        año_del_plan = plan.get('metadata', {}).get('año_generacion', date.today().year)
        if año_del_plan != año_solicitado:
            logger.info("Plan anual obsoleto (año plan: %s, solicitado: %s). Regenerando.", año_del_plan, año_solicitado)
            plan = None
        else:
            cache.set(_cache_key, plan, 1800)  # promover sesión al caché
            return plan

    # Si no existe, generarlo
    try:
        cliente_obj = Cliente.objects.get(id=cliente_id)

        # Calcular 1RM
        maximos_actuales = cliente_obj.one_rm_data or {}

        # Crear perfil
        perfil = crear_perfil_desde_cliente(cliente_obj)
        perfil.maximos_actuales = maximos_actuales

        # ✅ PASAR EL AÑO SOLICITADO AL PERFIL PARA QUE EL PLANIFICADOR LO USE
        perfil.año_planificacion = año_solicitado

        # Generar plan
        planificador = PlanificadorHelms(perfil)
        plan_original = planificador.generar_plan_anual()

        # Enriquecer con educación
        plan = agregar_educacion_a_plan(plan_original)

        # Asegurar metadatos y año de generación
        if 'metadata' not in plan:
            plan['metadata'] = {}
        plan['metadata']['año_generacion'] = año_solicitado

        # ✅ NORMALIZAR ANTES DE SERIALIZAR (clave para que UI no “cancele” campos)
        plan = _normalizar_plan_ui(plan)

        # Serializar y guardar en sesión y en caché Django
        plan_serializado = serializar_plan_para_sesion(plan)
        request.session[f'plan_anual_{cliente_id}'] = plan_serializado
        request.session[f'plan_anual_v2_{cliente_id}'] = plan_serializado
        request.session.modified = True
        cache.set(f'plan_anual_{cliente_id}_{año_solicitado}', plan_serializado, 1800)

        return plan_serializado

    except Exception as e:
        logger.exception("Error al generar plan: %s", e)
        return None


def ajax_obtener_entrenamiento_dia(request, cliente_id):
    """
    Vista AJAX que devuelve el entrenamiento de un día específico.
    """
    try:
        fecha_str = request.GET.get('fecha')

        if not fecha_str:
            return JsonResponse({'error': 'Fecha no proporcionada'}, status=400)

        plan = obtener_o_generar_plan(request, cliente_id)

        if not plan:
            return JsonResponse({'error': 'No se pudo generar el plan'}, status=500)

        entrenos_del_plan = plan.get('entrenos_por_fecha', {})

        entrenamiento_dia = None
        for k, v in entrenos_del_plan.items():
            try:
                from datetime import date, datetime
                if isinstance(k, date):
                    k_obj = k
                elif isinstance(k, datetime):
                    k_obj = k.date()
                else:
                    k_obj = datetime.fromisoformat(str(k)).date()

                if k_obj.isoformat() == fecha_str:
                    entrenamiento_dia = v
                    break
            except (ValueError, TypeError, AttributeError):
                continue

        if not entrenamiento_dia:
            return JsonResponse({'entrenamiento': None, 'fecha': fecha_str})

        # -------------------------
        # NORMALIZACIÓN defensiva (por si el plan de sesión es viejo)
        # -------------------------
        def _normalizar_ejercicio_ui(ej: dict, idx: int) -> dict:
            out = dict(ej or {})
            nombre = (out.get("nombre") or "").strip().lower()

            # Aliases para template entreno diario
            out.setdefault("peso_recomendado_kg", out.get("peso_kg"))
            out.setdefault("reps_objetivo", out.get("repeticiones"))
            out.setdefault("form_id", f"ej_{idx}")

            # Alias para calendario (tu JS lee ej.rpe a veces)
            out.setdefault("rpe", out.get("rpe_objetivo"))

            # Mancuernas opcional (si quieres usarlo en UI)
            es_mancuerna = any(k in nombre for k in ["mancuerna", "mancuernas", "db "])
            if es_mancuerna:
                out.setdefault("peso_formato", "por_mancuerna")
                if "peso_por_mancuerna_kg" not in out:
                    peso_total = out.get("peso_kg")
                    if isinstance(peso_total, (int, float)):
                        out["peso_por_mancuerna_kg"] = round(peso_total / 2.0, 1)
            else:
                out.setdefault("peso_formato", "total")

            return out

        if isinstance(entrenamiento_dia, dict):
            ejercicios = entrenamiento_dia.get("ejercicios") or []

            # --- Phase 16: Bio-Restrictions and Exercise Substitution ---
            try:
                from core.bio_context import BioContextProvider
                from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
                from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE
                from clientes.models import Cliente

                cliente = Cliente.objects.get(id=cliente_id)
                bio_data = BioContextProvider.get_current_restrictions(cliente)
                restricted_tags = bio_data.get('tags', set())

                if restricted_tags and isinstance(ejercicios, list):
                    # Process current day phase
                    fase_nombre_temp = ''
                    try:
                        fase_nombre_temp = entrenamiento_dia['nombre_rutina'].split(' - ')[1].lower().strip()
                    except (IndexError, AttributeError, KeyError):
                        fase_nombre_temp = 'hipertrofia'

                    safe_replacements_cache = {}

                    for idx, ej in enumerate(ejercicios):
                        grupo = ej.get('grupo_muscular', '')
                        nombre = ej.get('nombre', '').lower()

                        # Find original risk tags
                        ej_tags = set()
                        if grupo in EJERCICIOS_DATABASE:
                            for cat in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
                                for e in EJERCICIOS_DATABASE[grupo].get(cat, []):
                                    if isinstance(e, dict) and e.get('nombre', '').lower() == nombre:
                                        ej_tags = set(e.get('risk_tags', []))
                                        break
                                if ej_tags: break

                        # Check if blocked
                        if ej_tags.intersection(restricted_tags):
                            # Blocked! Find safe replacement
                            if grupo not in safe_replacements_cache:
                                safe_groups = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
                                    numero_bloque=1,
                                    fase=fase_nombre_temp,
                                    cliente=cliente
                                )
                                safe_replacements_cache[grupo] = safe_groups.get(grupo, [])

                            # Swap if a replacement is available
                            safe_opts = safe_replacements_cache[grupo]
                            if safe_opts:
                                substitute = safe_opts[0]
                                ej['nombre'] = substitute.get('nombre', ej['nombre'])
                                ej['es_adaptado'] = True
                                ej['explicacion_ejercicio'] = "🛡️ Adaptado por precaución biomecánica."
            except Exception as e:
                logger.warning("Error applying Bio-Restrictions: %s", e)

            if isinstance(ejercicios, list):
                entrenamiento_dia["ejercicios"] = [_normalizar_ejercicio_ui(ej, i) for i, ej in enumerate(ejercicios)]

        # Procesar fase_css (tu lógica actual)
        try:
            fase_nombre = entrenamiento_dia['nombre_rutina'].split(' - ')[1].lower().strip()
            fase_css_safe = fase_nombre.replace(' ', '_').replace('-', '_')
            fase_base = fase_css_safe.split('_')[0]
            entrenamiento_dia['fase_css'] = f"fase-{fase_base}"
        except (IndexError, AttributeError, KeyError):
            entrenamiento_dia['fase_css'] = "fase-default"

        return JsonResponse({
            'entrenamiento': entrenamiento_dia,
            'fecha': fecha_str,
            'success': True
        })

    except Exception as e:
        logger.exception("Error en ajax_obtener_entrenamiento_dia: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


def ajax_obtener_entrenamientos_mes(request, cliente_id):
    """
    Vista AJAX que devuelve TODOS los entrenamientos de un mes.
    """
    try:
        # Conversión robusta para evitar NaN
        try:
            año = int(request.GET.get('año'))
            mes = int(request.GET.get('mes'))
        except (TypeError, ValueError):
            from datetime import date
            año = date.today().year
            mes = date.today().month

        plan = obtener_o_generar_plan(request, cliente_id)

        if not plan:
            return JsonResponse({'error': 'No se pudo generar el plan'}, status=500)

        entrenos_del_plan = plan.get('entrenos_por_fecha', {})
        entrenamientos_mes = {}

        # -------------------------
        # NORMALIZACIÓN defensiva (por si el plan de sesión es viejo)
        # -------------------------
        def _normalizar_ejercicio_ui(ej: dict, idx: int) -> dict:
            out = dict(ej or {})
            nombre = (out.get("nombre") or "").strip().lower()

            out.setdefault("peso_recomendado_kg", out.get("peso_kg"))
            out.setdefault("reps_objetivo", out.get("repeticiones"))
            out.setdefault("form_id", f"ej_{idx}")
            out.setdefault("rpe", out.get("rpe_objetivo"))

            es_mancuerna = any(k in nombre for k in ["mancuerna", "mancuernas", "db "])
            if es_mancuerna:
                out.setdefault("peso_formato", "por_mancuerna")
                if "peso_por_mancuerna_kg" not in out:
                    peso_total = out.get("peso_kg")
                    if isinstance(peso_total, (int, float)):
                        out["peso_por_mancuerna_kg"] = round(peso_total / 2.0, 1)
            else:
                out.setdefault("peso_formato", "total")

            return out

        for fecha_str, entrenamiento in entrenos_del_plan.items():
            try:
                from datetime import date, datetime
                if isinstance(fecha_str, date):
                    fecha_obj = fecha_str
                elif isinstance(fecha_str, datetime):
                    fecha_obj = fecha_str.date()
                else:
                    fecha_obj = datetime.fromisoformat(str(fecha_str)).date()

                if fecha_obj.year == año and fecha_obj.month == mes:
                    if isinstance(entrenamiento, dict):
                        ejercicios = entrenamiento.get("ejercicios") or []

                        # --- Phase 16: Bio-Restrictions ---
                        try:
                            from core.bio_context import BioContextProvider
                            from analytics.planificador_helms.ejercicios.selector import SelectorEjercicios
                            from analytics.planificador_helms.database.ejercicios import EJERCICIOS_DATABASE
                            from clientes.models import Cliente

                            cliente = Cliente.objects.get(id=cliente_id)
                            bio_data = BioContextProvider.get_current_restrictions(cliente)
                            restricted_tags = bio_data.get('tags', set())

                            if restricted_tags and isinstance(ejercicios, list):
                                fase_nombre_temp = ''
                                try:
                                    fase_nombre_temp = entrenamiento['nombre_rutina'].split(' - ')[1].lower().strip()
                                except (IndexError, AttributeError, KeyError):
                                    fase_nombre_temp = 'hipertrofia'

                                safe_replacements_cache = {}

                                for idx, ej in enumerate(ejercicios):
                                    grupo = ej.get('grupo_muscular', '')
                                    nombre = ej.get('nombre', '').lower()

                                    ej_tags = set()
                                    if grupo in EJERCICIOS_DATABASE:
                                        for cat in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
                                            for e in EJERCICIOS_DATABASE[grupo].get(cat, []):
                                                if isinstance(e, dict) and e.get('nombre', '').lower() == nombre:
                                                    ej_tags = set(e.get('risk_tags', []))
                                                    break
                                            if ej_tags: break

                                    if ej_tags.intersection(restricted_tags):
                                        if grupo not in safe_replacements_cache:
                                            safe_groups = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
                                                numero_bloque=1,
                                                fase=fase_nombre_temp,
                                                cliente=cliente
                                            )
                                            safe_replacements_cache[grupo] = safe_groups.get(grupo, [])

                                        safe_opts = safe_replacements_cache[grupo]
                                        if safe_opts:
                                            substitute = safe_opts[0]
                                            ej['nombre'] = substitute.get('nombre', ej['nombre'])
                                            ej['es_adaptado'] = True
                                            ej['explicacion_ejercicio'] = "🛡️ Adaptado por precaución biomecánica."
                        except Exception as e:
                            logger.warning("Error applying Bio-Restrictions directly: %s", e)

                        if isinstance(ejercicios, list):
                            entrenamiento["ejercicios"] = [_normalizar_ejercicio_ui(ej, i) for i, ej in
                                                           enumerate(ejercicios)]

                    # Tu lógica de fase_css (igual que antes)
                    try:
                        fase_nombre = entrenamiento['nombre_rutina'].split(' - ')[1].lower().strip()
                        fase_css_safe = fase_nombre.replace(' ', '_').replace('-', '_')
                        fase_base = fase_css_safe.split('_')[0]
                        entrenamiento['fase_css'] = f"fase-{fase_base}"
                    except (IndexError, AttributeError, KeyError):
                        entrenamiento['fase_css'] = "fase-default"

                    # Almacenar usando la fecha en formato YYYY-MM-DD estricto
                    entrenamientos_mes[fecha_obj.isoformat()] = entrenamiento
            except (ValueError, TypeError, AttributeError):
                continue

        return JsonResponse({
            'entrenamientos': entrenamientos_mes,
            'año': año,
            'mes': mes,
            'success': True
        })

    except Exception as e:
        logger.exception("Error en ajax_obtener_entrenamientos_mes: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


# views.py - Actualizar tu vista existente
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from analytics.planificador_integrado import PlanificadorIntegrado


def vista_plan_calendario(request, cliente_id):
    """
    Vista principal del plan - ahora con integración Helms
    """
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)

    try:
        # Cachear el plan anual 30 minutos — es costoso de generar y cambia raramente
        _plan_cache_key = f'plan_anual_{cliente_id}'
        _plan_cached = cache.get(_plan_cache_key)
        if _plan_cached is not None:
            plan, estadisticas = _plan_cached
        else:
            planificador = PlanificadorIntegrado(cliente_id)
            plan = planificador.generar_plan_anual()
            estadisticas = planificador.obtener_estadisticas_integracion()
            cache.set(_plan_cache_key, (plan, estadisticas), 1800)  # 30 min

        # === DETECCIÓN DE FASE ACTUAL Y TEMA DINÁMICO ===
        from datetime import date
        hoy = date.today()

        # Detectar fase actual basada en la semana actual
        fase_actual = None
        semana_actual = 1
        total_semanas_fase = 1
        progreso_fase = 0

        bloques = (
            plan.get('bloques', []) or 
            plan.get('fases', []) or 
            plan.get('plan_por_bloques', [])
        )
        if not bloques and 'datos_helms' in plan:
            bloques = (
                plan['datos_helms'].get('plan_por_bloques', []) or 
                plan['datos_helms'].get('fases', []) or 
                plan['datos_helms'].get('bloques', [])
            )

        # Calcular fechas si faltan (Helms format uses 'duracion' in weeks)
        fecha_cursor = None
        if bloques:
            # Fallback: primer lunes del año actual
            primer_dia = date(hoy.year, 1, 1)
            fecha_cursor = primer_dia + timedelta(days=(0 - primer_dia.weekday() + 7) % 7)

            # Intentar ajustar si el primer bloque tiene fecha
            for b in bloques:
                if b.get('fecha_inicio'):
                    f_ini = b.get('fecha_inicio')
                    if isinstance(f_ini, str):
                        f_ini = date.fromisoformat(f_ini[:10])
                    fecha_cursor = f_ini
                    break

        for i, bloque in enumerate(bloques):
            # Normalizar parámetros básicos si faltan
            if 'rpe_min' not in bloque: bloque['rpe_min'] = 6
            if 'rpe_max' not in bloque: bloque['rpe_max'] = 10
            if 'reps_min' not in bloque: bloque['reps_min'] = 1
            if 'reps_max' not in bloque: bloque['reps_max'] = 20
            if 'series' not in bloque: bloque['series'] = '3-5'
            if 'nombre' not in bloque: bloque['nombre'] = bloque.get('tipo_fase', f'Fase {i + 1}')

            # Normalizar fechas
            fecha_inicio = bloque.get('fecha_inicio')
            if isinstance(fecha_inicio, str):
                fecha_inicio = date.fromisoformat(fecha_inicio[:10])
                bloque['fecha_inicio'] = fecha_inicio

            duracion_semanas = bloque.get('duracion') or bloque.get('duracion_semanas') or 1
            if not isinstance(duracion_semanas, int):
                try:
                    duracion_semanas = len(bloque.get('semanas', [])) or 1
                except:
                    duracion_semanas = 1

            if not fecha_inicio and fecha_cursor:
                fecha_inicio = fecha_cursor
                bloque['fecha_inicio'] = fecha_inicio

            fecha_fin = bloque.get('fecha_fin')
            if isinstance(fecha_fin, str):
                fecha_fin = date.fromisoformat(fecha_fin[:10])
                bloque['fecha_fin'] = fecha_fin

            if not fecha_fin and fecha_inicio:
                fecha_fin = fecha_inicio + timedelta(days=(duracion_semanas * 7) - 1)
                bloque['fecha_fin'] = fecha_fin

            # Avanzar cursor
            if fecha_fin:
                fecha_cursor = fecha_fin + timedelta(days=1)

            if fecha_inicio and fecha_fin:
                if fecha_inicio <= hoy <= fecha_fin:
                    fase_actual = bloque
                    # Calcular progreso basado en días para una barra más precisa
                    dias_transcurridos = (hoy - fecha_inicio).days
                    duracion_total_dias = (fecha_fin - fecha_inicio).days + 1
                    
                    if duracion_total_dias > 0:
                        progreso_fase = min(max((dias_transcurridos / duracion_total_dias) * 100, 0), 100)
                    else:
                        progreso_fase = 0
                        
                    # Mantener variables para display
                    semana_actual = (dias_transcurridos // 7) + 1
                    total_semanas_fase = duracion_semanas

                    # Detectar próxima fase
                    if i + 1 < len(bloques):
                        proxima_fase = bloques[i + 1]
                        # Calcular fecha inicio de la próxima si no tiene
                        prox_inicio = proxima_fase.get('fecha_inicio')
                        if isinstance(prox_inicio, str):
                            prox_inicio = date.fromisoformat(prox_inicio[:10])

                        if not prox_inicio:
                            prox_inicio = fecha_fin + timedelta(days=1)
                            proxima_fase['fecha_inicio'] = prox_inicio

                        dias_hasta_proxima_fase = (prox_inicio - hoy).days
                        if dias_hasta_proxima_fase < 0:
                            dias_hasta_proxima_fase = 0

                    break

        if not fase_actual:
            pass

        # Calcular tema de colores según tipo de fase
        tema_fase = {
            'primary': '#00D4FF',
            'secondary': '#8B5CF6',
            'glow': 'rgba(0, 212, 255, 0.5)',
            'bg': 'rgba(0, 212, 255, 0.15)',
            'r1': 0, 'g1': 212, 'b1': 255,  # Cyan
            'r2': 139, 'g2': 92, 'b2': 246,  # Purple
            'icon': '💪'
        }

        objetivo_fase = "Entrenamiento general"

        if fase_actual:
            objetivo = (fase_actual.get('objetivo') or '').lower()
            tipo_fase = (fase_actual.get('tipo_fase') or '').lower()

            # Hipertrofia - Azul/Cyan
            if 'hipertrofia' in objetivo or 'hipertrofia' in tipo_fase:
                tema_fase = {
                    'primary': '#00D4FF',
                    'secondary': '#0EA5E9',
                    'glow': 'rgba(0, 212, 255, 0.5)',
                    'bg': 'rgba(0, 212, 255, 0.15)',
                    'r1': 0, 'g1': 212, 'b1': 255,
                    'r2': 14, 'g2': 165, 'b2': 233,
                    'icon': '💪'
                }
                objetivo_fase = "Maximizar volumen muscular y crecimiento"

            # Fuerza - Rosa/Magenta
            elif 'fuerza' in objetivo or 'fuerza' in tipo_fase:
                tema_fase = {
                    'primary': '#FF2D92',
                    'secondary': '#EC4899',
                    'glow': 'rgba(255, 45, 146, 0.5)',
                    'bg': 'rgba(255, 45, 146, 0.15)',
                    'r1': 255, 'g1': 45, 'b1': 146,
                    'r2': 236, 'g2': 72, 'b2': 153,
                    'icon': '⚡'
                }
                objetivo_fase = "Incrementar fuerza máxima (1RM)"

            # Potencia - Amarillo/Naranja
            elif 'potencia' in objetivo or 'potencia' in tipo_fase:
                tema_fase = {
                    'primary': '#FFB800',
                    'secondary': '#F59E0B',
                    'glow': 'rgba(255, 184, 0, 0.5)',
                    'bg': 'rgba(255, 184, 0, 0.15)',
                    'r1': 255, 'g1': 184, 'b1': 0,
                    'r2': 245, 'g2': 158, 'b2': 11,
                    'icon': '🔥'
                }
                objetivo_fase = "Desarrollar velocidad y explosividad"

            # Descarga - Morado/Violeta
            elif 'descarga' in objetivo or 'descarga' in tipo_fase or 'deload' in objetivo:
                tema_fase = {
                    'primary': '#A855F7',
                    'secondary': '#9333EA',
                    'glow': 'rgba(168, 85, 247, 0.5)',
                    'bg': 'rgba(168, 85, 247, 0.15)',
                    'r1': 168, 'g1': 85, 'b1': 247,
                    'r2': 147, 'g2': 51, 'b2': 234,
                    'icon': '🌙'
                }
                objetivo_fase = "Recuperación activa y regeneración"

        # Extraer parámetros de la fase
        parametros_fase = {
            'rpe_min': 6,
            'rpe_max': 10,
            'reps_min': 1,
            'reps_max': 20,
            'series': '3-5'
        }

        if fase_actual:
            parametros_fase = {
                'rpe_min': fase_actual.get('rpe_min', 6),
                'rpe_max': fase_actual.get('rpe_max', 10),
                'reps_min': fase_actual.get('reps_min', 1),
                'reps_max': fase_actual.get('reps_max', 20),
                'series': fase_actual.get('series', '3-5')
            }

        # === CALCULAR PROYECCIONES DE EJERCICIOS (PARA TODAS LAS FASES) ===
        proyecciones_totales = {}
        proyecciones_fase = []

        # Definir configuración por tipo de fase
        config_fases = {
            'hipertrofia': {
                'ejercicios': ['Press Banca', 'Sentadilla', 'Peso Muerto', 'Press Militar'],
                'incremento': 3.5  # 3-5% en 6 semanas
            },
            'fuerza': {
                'ejercicios': ['Press Banca', 'Sentadilla', 'Peso Muerto', 'Press Militar'],
                'incremento': 7.5  # 5-10% en 4 semanas
            },
            'potencia': {
                'ejercicios': ['Press Banca', 'Sentadilla', 'Power Clean'],
                'incremento': 2.5  # 2-3% en 3 semanas
            }
        }

        from entrenos.models import EjercicioRealizado

        # --- Proyecciones: 1 sola query en lugar de 12+ queries con icontains ---
        _proy_cache_key = f'proyecciones_plan_{cliente_id}'
        _proy_cached = cache.get(_proy_cache_key)

        if _proy_cached is not None:
            proyecciones_totales = _proy_cached
        else:
            # Todos los nombres de ejercicios que necesitamos buscar
            _ejercicios_buscar = set()
            for config in config_fases.values():
                _ejercicios_buscar.update(config['ejercicios'])

            # Una sola query trae todos los registros relevantes, filtramos en Python
            from django.db.models import Q
            _q_filter = Q()
            for nombre in _ejercicios_buscar:
                _q_filter |= Q(nombre_ejercicio__icontains=nombre)

            _todos_registros = (
                EjercicioRealizado.objects
                .filter(_q_filter, entreno__cliente=cliente)
                .values('nombre_ejercicio', 'peso_kg', 'entreno__fecha')
                .order_by('-peso_kg')
            )

            # Indexar por nombre normalizado para lookup O(1)
            _mejor_peso = {}  # nombre_lower → max peso_kg
            _mejor_peso_antes = {}  # (nombre_lower, fecha_inicio) → max peso antes de fecha
            _mejor_peso_desde = {}  # (nombre_lower, fecha_inicio) → max peso desde fecha

            for r in _todos_registros:
                nombre_r = (r['nombre_ejercicio'] or '').lower()
                peso_r = float(r['peso_kg'] or 0)
                fecha_r = r['entreno__fecha']

                for ej_nombre in _ejercicios_buscar:
                    if ej_nombre.lower() in nombre_r:
                        key = ej_nombre.lower()
                        if key not in _mejor_peso or peso_r > _mejor_peso[key]:
                            _mejor_peso[key] = peso_r

            # Calcular proyecciones por tipo de fase
            for tipo, config in config_fases.items():
                proyecciones_tipo = []
                for ejercicio_nombre in config['ejercicios']:
                    key = ejercicio_nombre.lower()
                    peso_actual = _mejor_peso.get(key, 0)
                    if peso_actual > 0:
                        peso_proyectado = peso_actual * (1 + config['incremento'] / 100)
                        proyecciones_tipo.append({
                            'nombre': ejercicio_nombre,
                            'peso_actual': peso_actual,
                            'peso_proyectado': round(peso_proyectado, 1),
                            'incremento': round(peso_proyectado - peso_actual, 1),
                            'incremento_porcentaje': config['incremento']
                        })
                proyecciones_totales[tipo] = proyecciones_tipo

            cache.set(_proy_cache_key, proyecciones_totales, 1800)  # 30 min

        # Asignar proyecciones de la fase actual
        if fase_actual:
            tipo_fase = (fase_actual.get('tipo_fase', '') or '').lower()
            fase_key = None
            if 'hiper' in tipo_fase:
                fase_key = 'hipertrofia'
            elif 'fuerza' in tipo_fase:
                fase_key = 'fuerza'
            elif 'poten' in tipo_fase:
                fase_key = 'potencia'

            if fase_key:
                proyecciones_fase = proyecciones_totales.get(fase_key, [])

        import json

        def safe_json_dumps(data):
            try:
                # Custom encoder for dates might be needed, assuming custom DateEncoder or str fallback
                return json.dumps(data, default=str)
            except Exception as e:
                print(f"Error serializando JSON: {e}")
                return "[]"

        # Preparar contexto para el template
        contexto = {
            'cliente': cliente,
            'plan': plan,
            'estadisticas_helms': estadisticas,
            'tiene_datos_helms': 'datos_helms' in plan,
            'generado_por_helms': plan.get('metadata', {}).get('generado_por') == 'helms',

            # Tema dinámico de fase
            'fase_actual': fase_actual,
            'proxima_fase': proxima_fase,
            'dias_hasta_proxima_fase': dias_hasta_proxima_fase,
            'tema_fase': tema_fase,
            'objetivo_fase': objetivo_fase,
            'parametros_fase': parametros_fase,
            'semana_actual': semana_actual,
            'total_semanas_fase': total_semanas_fase,
            'progreso_fase': round(progreso_fase, 1),
            'progreso_fase_css': str(round(progreso_fase, 1)).replace(',', '.'),
            'proyecciones_fase': proyecciones_fase,

            # JSON para JS
            'bloques_json': safe_json_dumps(bloques),
            'proyecciones_json': safe_json_dumps(proyecciones_totales),

            # Información educativa sobre Helms
            'info_rpe': {
                6: "Muy fácil - Podrías hacer muchas repeticiones más",
                7: "Moderado - Podrías hacer 3-4 repeticiones más",
                8: "Intenso - Podrías hacer 2-3 repeticiones más",
                9: "Muy intenso - Podrías hacer 1-2 repeticiones más",
                10: "Máximo esfuerzo - Al fallo muscular"
            },

            'info_tempo': {
                'descripcion': 'Formato: Excéntrica-Pausa-Concéntrica-Pausa',
                'ejemplo': '2-0-X-0 = 2 seg bajada, sin pausa, explosiva subida, sin pausa'
            }
        }

        return render(request, 'entrenos/vista_plan_calendario.html', contexto)

    except Exception as e:
        logger.exception("Error en vista_plan_calendario: %s", e)

        # Fallback a tu sistema actual
        from analytics.planificador import PlanificadorAnualIA
        planificador_fallback = PlanificadorAnualIA(cliente_id)
        plan_fallback = planificador_fallback.generar_plan()

        contexto = {
            'cliente': cliente,
            'plan': plan_fallback,
            'error_helms': True,
            'mensaje_error': 'Usando planificador de respaldo'
        }

        return render(request, 'entrenos/vista_plan_calendario.html', contexto)


def api_regenerar_plan_helms(request, cliente_id):
    """
    API endpoint para regenerar plan con configuración específica
    """
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)

        # Obtener configuración del request
        usar_helms = request.POST.get('usar_helms', 'true') == 'true'
        incluir_validacion = request.POST.get('incluir_validacion', 'true') == 'true'

        try:
            planificador = PlanificadorIntegrado(cliente_id)
            planificador.usar_helms_como_principal = usar_helms
            planificador.incluir_validacion_helms = incluir_validacion

            plan = planificador.generar_plan_anual()
            estadisticas = planificador.obtener_estadisticas_integracion()

            return JsonResponse({
                'success': True,
                'plan_id': plan.get('id'),
                'generado_por': plan.get('metadata', {}).get('generado_por'),
                'estadisticas': estadisticas,
                'mensaje': '✅ Plan regenerado exitosamente'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'mensaje': '❌ Error al regenerar el plan'
            })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


def dashboard_comparacion_planificadores(request, cliente_id):
    """
    Dashboard para comparar tu planificador actual vs Helms
    """
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)

    try:
        # Generar plan con ambos sistemas
        planificador_integrado = PlanificadorIntegrado(cliente_id)

        # Plan con Helms
        planificador_integrado.usar_helms_como_principal = True
        plan_helms = planificador_integrado.generar_plan_anual()

        # Plan con tu sistema actual
        planificador_integrado.usar_helms_como_principal = False
        plan_actual = planificador_integrado.generar_plan_anual()

        # Comparar métricas
        comparacion = {
            'volumen_total': {
                'helms': sum(plan_helms.get('datos_helms', {}).get('volumen_semanal', {}).values()),
                'actual': _calcular_volumen_plan(plan_actual)
            },
            'ejercicios_por_semana': {
                'helms': len(plan_helms.get('ejercicios_por_semana', {}).get('1', [])),
                'actual': len(plan_actual.get('ejercicios_por_semana', {}).get('1', []))
            },
            'tiempo_estimado': {
                'helms': _calcular_tiempo_plan(plan_helms),
                'actual': _calcular_tiempo_plan(plan_actual)
            }
        }

        contexto = {
            'cliente': cliente,
            'plan_helms': plan_helms,
            'plan_actual': plan_actual,
            'comparacion': comparacion
        }

        return render(request, 'dashboard_comparacion.html', contexto)

    except Exception as e:
        return render(request, 'error.html', {'error': str(e)})


def _calcular_volumen_plan(plan: Dict) -> int:
    """Calcula volumen total de un plan"""
    volumen_total = 0
    for ejercicios in plan.get('ejercicios_por_semana', {}).values():
        for ejercicio in ejercicios:
            volumen_total += ejercicio.get('series', 0)
    return volumen_total


def _calcular_tiempo_plan(plan: Dict) -> int:
    """Calcula tiempo estimado de un plan en minutos"""
    tiempo_total = 0
    for ejercicios in plan.get('ejercicios_por_semana', {}).values():
        for ejercicio in ejercicios:
            series = ejercicio.get('series', 0)
            descanso = ejercicio.get('descanso_minutos', 3)
            tiempo_ejercicio = series * 2 + (series - 1) * descanso  # 2 min por serie + descansos
            tiempo_total += tiempo_ejercicio
    return tiempo_total // 7  # Promedio por día


# views.py - Uso del convertidor
from .utils.convertidor_formatos import ConvertidorFormatos, convertir_plan_para_vista, extraer_datos_educativos


def vista_plan_calendario_con_conversion(request, cliente_id):
    """
    Vista que usa el convertidor para mantener compatibilidad
    """
    cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)

    try:
        # Generar plan con el sistema integrado
        planificador = PlanificadorIntegrado(cliente_id)
        plan_helms = planificador.generar_plan_anual()

        # Convertir a formato actual si es necesario
        if plan_helms.get('metadata', {}).get('generado_por') == 'helms':
            resultado_conversion = convertir_plan_para_vista(plan_helms)
            plan = resultado_conversion['plan']
            validacion = resultado_conversion['validacion']
        else:
            plan = plan_helms
            validacion = {'exitosa': True}

        # Extraer datos educativos
        datos_educativos = extraer_datos_educativos(plan)

        # Preparar contexto
        contexto = {
            'cliente': cliente,
            'plan': plan,
            'validacion_conversion': validacion,
            'datos_educativos': datos_educativos,
            'tiene_datos_helms': 'datos_helms' in plan,
            'generado_por_helms': plan.get('metadata', {}).get('generado_por') == 'helms'
        }

        return render(request, 'entrenos/vista_plan_calendario.html', contexto)

    except Exception as e:
        # Manejo de errores con logging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en vista_plan_calendario: {str(e)}")

        return render(request, 'error.html', {
            'error': 'Error al generar el plan',
            'detalle': str(e) if settings.DEBUG else 'Contacta al soporte'
        })


# en entrenos/views.py

# --- Asegúrate de que estas importaciones estén al principio del archivo ---
from .models import EntrenoRealizado, EjercicioRealizado
from clientes.models import Cliente
from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente  # <-- ¡USA ESTE!
from analytics.views import CalculadoraEjerciciosTabla
from decimal import Decimal, InvalidOperation


# ... (otras importaciones que ya tengas)

def vista_resumen_anual(request, cliente_id):
    """
    Muestra una vista de alto nivel de todo el plan anual,
    organizado por mesociclos o bloques.
    VERSIÓN CORREGIDA para usar el planificador unificado.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # --- PASO 1: Calcular 1RM (Lógica idéntica a la vista del calendario) ---
    maximos_actuales = {}
    try:
        calculadora_rm = CalculadoraEjerciciosTabla(cliente)
        ejercicios_con_rm = calculadora_rm.obtener_ejercicios_tabla()
        for e in ejercicios_con_rm:
            try:
                nombre_limpio = e.get('nombre', '').strip().lower()
                peso_str = str(e.get('peso', '0')).replace(',', '.')
                reps_valor = e.get('repeticiones', '0')
                reps_str = str(reps_valor).split('-')[0].strip() if isinstance(reps_valor, str) else str(reps_valor)
                if nombre_limpio and peso_str.replace('.', '', 1).isdigit() and reps_str.isdigit():
                    peso, reps = Decimal(peso_str), int(reps_str)
                    if peso > 0 and reps > 0:
                        rm_estimado = peso * (1 + Decimal(reps) / Decimal(30))
                        if nombre_limpio not in maximos_actuales or rm_estimado > maximos_actuales[nombre_limpio]:
                            maximos_actuales[nombre_limpio] = float(rm_estimado)
            except (ValueError, TypeError, InvalidOperation):
                continue
    except Exception:
        maximos_actuales = {'press_banca': 80.0, 'sentadilla': 100.0}

    # --- PASO 2: Crear perfil y generar plan con el planificador correcto ---
    perfil = crear_perfil_desde_cliente(cliente)
    perfil.maximos_actuales = maximos_actuales

    # ¡Usamos el PlanificadorHelms que ya hemos corregido!
    planificador = PlanificadorHelms(perfil)
    plan_completo = planificador.generar_plan_anual()

    # --- PASO 3: Preparar el contexto para la plantilla ---
    plan_por_bloques = plan_completo.get('plan_por_bloques', [])

    # Calcular el total de semanas sumando la duración de cada bloque
    total_semanas = sum(bloque.get('duracion', 0) for bloque in plan_por_bloques)

    context = {
        'cliente': cliente,
        'plan_por_bloques': plan_por_bloques,
        'total_semanas': total_semanas  # Ahora esto debería ser 52
    }

    return render(request, 'entrenos/vista_resumen_anual.html', context)


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from .gamificacion_service import EntrenamientoGamificacionService
from clientes.models import Cliente
import logging

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def gamificacion_resumen(request, cliente_id):
    """
    Endpoint para obtener el resumen de gamificación de un cliente.
    VERSIÓN DEFINITIVA: Incluye todos los campos necesarios para los widgets.
    """
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        resumen = EntrenamientoGamificacionService.obtener_resumen_gamificacion(cliente)

        # Inicializamos el diccionario con valores por defecto
        resumen_limpio = {
            'tiene_perfil': resumen.get('tiene_perfil', False),
            'nivel_actual': 'El Aspirante Calvo',
            'puntos_actuales': 0,
            'puntos_siguiente': 500,
            'porcentaje_progreso': 0,
            'siguiente_nivel': 'Próximo Nivel',
            'racha_actual': 0,
            'filosofia': '"El poder comienza con el primer paso."',
            'imagen_url': None,
            'nivel_numero': 1,
            'total_entrenamientos': 0,
            'icono': '🥊',
            'pruebas_activas': []
        }

        # Si el perfil existe, sobrescribimos con los datos reales
        if resumen.get('perfil'):
            perfil = resumen['perfil']

            # --- INICIO DE LA CORRECCIÓN ---
            # Leemos los datos directamente del objeto 'perfil'
            resumen_limpio['puntos_actuales'] = perfil.puntos_totales
            resumen_limpio['racha_actual'] = perfil.racha_actual
            resumen_limpio['total_entrenamientos'] = perfil.entrenos_totales
            # --- FIN DE LA CORRECCIÓN ---

            # Leemos los datos del arquetipo (nivel) si existe
            if perfil.nivel_actual:
                arquetipo = perfil.nivel_actual
                resumen_limpio['nivel_actual'] = arquetipo.titulo_arquetipo
                resumen_limpio['filosofia'] = getattr(arquetipo, 'filosofia', '')
                resumen_limpio['imagen_url'] = getattr(arquetipo, 'imagen_url', None)
                resumen_limpio['nivel_numero'] = getattr(arquetipo, 'nivel', 1)
                resumen_limpio['icono'] = getattr(arquetipo, 'icono_fa', '🥊')

            # Los datos que vienen del 'resumen' del servicio
            resumen_limpio['puntos_siguiente'] = resumen.get('puntos_siguiente', 500)
            resumen_limpio['porcentaje_progreso'] = resumen.get('porcentaje_progreso', 0)
            resumen_limpio['siguiente_nivel'] = resumen.get('siguiente_nivel', 'Próximo Nivel')

        # Convertir pruebas activas (código sin cambios)
        if resumen.get('pruebas_activas'):
            pruebas_serializables = []
            for prueba_usuario in resumen['pruebas_activas']:
                if hasattr(prueba_usuario, 'prueba'):
                    prueba_data = {
                        'nombre': prueba_usuario.prueba.nombre,
                        'descripcion': getattr(prueba_usuario.prueba, 'descripcion', 'Desafío legendario'),
                    }
                    pruebas_serializables.append({'prueba': prueba_data})
            resumen_limpio['pruebas_activas'] = pruebas_serializables

        logger.info(f"Resumen de gamificación generado para cliente {cliente_id}")
        return JsonResponse(resumen_limpio)

    except Exception as e:
        logger.error(f"Error en gamificacion_resumen para cliente {cliente_id}: {e}", exc_info=True)
        # Devolvemos un JSON de error consistente
        return JsonResponse({
            'error': str(e),
            'tiene_perfil': False,
            'nivel_actual': 'Error de Conexión',
            'puntos_actuales': 0, 'puntos_siguiente': 500, 'porcentaje_progreso': 0,
            'pruebas_activas': [], 'racha_actual': 0, 'siguiente_nivel': 'Error',
            'filosofia': 'Incluso los errores forjan el carácter del guerrero',
            'imagen_url': None, 'nivel_numero': 1, 'total_entrenamientos': 0
        }, status=500)


# entrenos/views.py - Vista para Dashboard de Ejercicios

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Min, Avg, Sum, F, Q
from django.db.models.functions import TruncDate
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import EntrenoRealizado, EjercicioRealizado, EjercicioLiftinDetallado
from clientes.models import Cliente


def calcular_1rm_epley(peso, repeticiones):
    """
    Calcula el 1RM usando la fórmula de Epley
    1RM = peso × (1 + repeticiones / 30)
    """
    if not peso or not repeticiones or repeticiones == 0:
        return None
    if repeticiones == 1:
        return float(peso)
    return float(peso) * (1 + float(repeticiones) / 30)


def calcular_1rm_brzycki(peso, repeticiones):
    """
    Calcula el 1RM usando la fórmula de Brzycki
    1RM = peso × (36 / (37 - repeticiones))
    Válida para repeticiones entre 2 y 10
    """
    if not peso or not repeticiones or repeticiones >= 37:
        return None
    if repeticiones == 1:
        return float(peso)
    return float(peso) * (36 / (37 - float(repeticiones)))


def dashboard_ejercicios(request, cliente_id):
    """
    Vista principal del dashboard de análisis de ejercicios
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Obtener todos los entrenos del cliente
    entrenos = EntrenoRealizado.objects.filter(cliente=cliente).order_by('fecha')

    if not entrenos.exists():
        return render(request, 'entrenos/dashboard_ejercicios.html', {
            'cliente': cliente,
            'sin_datos': True
        })

    # Obtener todos los ejercicios realizados
    ejercicios_realizados = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente
    ).select_related('entreno').order_by('entreno__fecha')

    # Agrupar ejercicios por nombre
    ejercicios_agrupados = defaultdict(list)
    for ejercicio in ejercicios_realizados:
        nombre_normalizado = ejercicio.nombre_ejercicio.strip().title()
        ejercicios_agrupados[nombre_normalizado].append({
            'fecha': ejercicio.entreno.fecha.strftime('%Y-%m-%d'),  # Convertir a string
            'peso': float(ejercicio.peso_kg) if ejercicio.peso_kg else 0,
            'series': ejercicio.series,
            'repeticiones': ejercicio.repeticiones,
            'rpe': ejercicio.rpe,
            'rir': ejercicio.rir,
            'volumen': ejercicio.volumen(),
            'completado': ejercicio.completado,
            'nuevo_record': ejercicio.nuevo_record,
            # Phase 15: is_recovery_load
            'is_recovery_load': getattr(ejercicio, 'is_recovery_load', False)
        })

    # Calcular estadísticas por ejercicio
    estadisticas_ejercicios = []

    for nombre_ejercicio, registros in ejercicios_agrupados.items():
        # Ordenar registros por fecha
        registros_ordenados = sorted(registros, key=lambda x: x['fecha'])

        # Filtrar solo ejercicios completados con peso válido
        registros_validos = [r for r in registros_ordenados if r['completado'] and r['peso'] > 0]

        if not registros_validos:
            continue

        # Datos básicos
        veces_realizado = len(registros_validos)
        primera_fecha = registros_validos[0]['fecha']
        ultima_fecha = registros_validos[-1]['fecha']

        # Pesos
        pesos = [r['peso'] for r in registros_validos]
        peso_maximo = max(pesos)
        peso_minimo = min(pesos)
        peso_inicial = registros_validos[0]['peso']
        peso_actual = registros_validos[-1]['peso']
        peso_promedio = sum(pesos) / len(pesos)

        # Progresión
        progresion_kg = peso_actual - peso_inicial
        progresion_porcentaje = (progresion_kg / peso_inicial * 100) if peso_inicial > 0 else 0

        # Volumen total
        volumen_total = sum(r['volumen'] for r in registros_validos)

        # RPE promedio
        rpes = [r['rpe'] for r in registros_validos if r['rpe']]
        rpe_promedio = sum(rpes) / len(rpes) if rpes else None

        # 1RM estimado (usando el registro con mayor peso)
        registro_max = max(registros_validos, key=lambda x: x['peso'])
        rm_epley = calcular_1rm_epley(registro_max['peso'], registro_max['repeticiones'])
        rm_brzycki = calcular_1rm_brzycki(registro_max['peso'], registro_max['repeticiones'])
        rm_estimado = rm_epley if rm_epley else rm_brzycki

        # Frecuencia (veces por mes)
        # Convertir strings de fecha a objetos date para el cálculo
        from datetime import datetime as dt
        primera_fecha_obj = dt.strptime(primera_fecha, '%Y-%m-%d').date()
        ultima_fecha_obj = dt.strptime(ultima_fecha, '%Y-%m-%d').date()
        dias_totales = (ultima_fecha_obj - primera_fecha_obj).days
        meses_totales = max(dias_totales / 30, 1)
        frecuencia_mensual = veces_realizado / meses_totales

        # Tendencia (últimos 3 vs primeros 3 registros)
        if len(registros_validos) >= 6:
            peso_promedio_inicial = sum(r['peso'] for r in registros_validos[:3]) / 3
            peso_promedio_reciente = sum(r['peso'] for r in registros_validos[-3:]) / 3
            tendencia = 'subiendo' if peso_promedio_reciente > peso_promedio_inicial else 'bajando'
        else:
            tendencia = 'estable'

        # Récord reciente (si el peso máximo fue en los últimos 30 días)
        dias_desde_max = (datetime.now().date() - ultima_fecha_obj).days
        es_record_reciente = peso_actual == peso_maximo and dias_desde_max <= 30

        # Preparar historial para gráficos (últimos 20 registros)
        historial_grafico = registros_validos[-20:]

        # Convertir historial a JSON serializable
        historial_json = json.dumps([{
            'nombre': nombre_ejercicio,
            'fecha': h['fecha'],
            'peso': h['peso'],
            'series': h['series'],
            'repeticiones': h['repeticiones'],
            'volumen': h['volumen'],
            'rpe': h['rpe'],
            # Phase 15: is_recovery_load
            'is_recovery_load': h.get('is_recovery_load', False)
        } for h in historial_grafico])

        estadisticas_ejercicios.append({
            'nombre': nombre_ejercicio,
            'veces_realizado': veces_realizado,
            'peso_maximo': round(peso_maximo, 2),
            'peso_minimo': round(peso_minimo, 2),
            'peso_inicial': round(peso_inicial, 2),
            'peso_actual': round(peso_actual, 2),
            'peso_promedio': round(peso_promedio, 2),
            'progresion_kg': round(progresion_kg, 2),
            'progresion_porcentaje': round(progresion_porcentaje, 1),
            'volumen_total': round(volumen_total, 2),
            'rpe_promedio': round(rpe_promedio, 1) if rpe_promedio else None,
            '1rm_estimado': round(rm_estimado, 2) if rm_estimado else None,
            'primera_fecha': primera_fecha_obj,
            'ultima_fecha': ultima_fecha_obj,
            'frecuencia_mensual': round(frecuencia_mensual, 1),
            'tendencia': tendencia,
            'es_record_reciente': es_record_reciente,
            'historial': historial_json  # Ya es un string JSON
        })

    # Ordenar por diferentes criterios según el filtro
    orden = request.GET.get('orden', 'frecuencia')

    if orden == 'frecuencia':
        estadisticas_ejercicios.sort(key=lambda x: x['veces_realizado'], reverse=True)
    elif orden == 'progresion':
        estadisticas_ejercicios.sort(key=lambda x: x['progresion_porcentaje'], reverse=True)
    elif orden == 'peso_maximo':
        estadisticas_ejercicios.sort(key=lambda x: x['peso_maximo'], reverse=True)
    elif orden == 'volumen':
        estadisticas_ejercicios.sort(key=lambda x: x['volumen_total'], reverse=True)
    elif orden == 'reciente':
        estadisticas_ejercicios.sort(key=lambda x: x['ultima_fecha'], reverse=True)
    else:
        estadisticas_ejercicios.sort(key=lambda x: x['nombre'])

    # Filtrar por búsqueda
    busqueda = request.GET.get('buscar', '').strip()
    if busqueda:
        estadisticas_ejercicios = [
            e for e in estadisticas_ejercicios
            if busqueda.lower() in e['nombre'].lower()
        ]

    # Calcular estadísticas globales
    total_ejercicios_unicos = len(estadisticas_ejercicios)
    total_sesiones = entrenos.count()

    if estadisticas_ejercicios:
        ejercicio_mas_frecuente = max(estadisticas_ejercicios, key=lambda x: x['veces_realizado'])
        mayor_progresion = max(estadisticas_ejercicios, key=lambda x: x['progresion_porcentaje'])
        volumen_total_global = sum(e['volumen_total'] for e in estadisticas_ejercicios)

        # Ejercicios con récords recientes
        records_recientes = [e for e in estadisticas_ejercicios if e['es_record_reciente']]
    else:
        ejercicio_mas_frecuente = None
        mayor_progresion = None
        volumen_total_global = 0
        records_recientes = []

    # Preparar datos para gráficos globales
    # Volumen por mes
    volumen_por_mes = defaultdict(float)
    for ejercicio in ejercicios_realizados:
        mes_key = ejercicio.entreno.fecha.strftime('%Y-%m')
        volumen_por_mes[mes_key] += ejercicio.volumen()

    volumen_mensual_labels = sorted(volumen_por_mes.keys())
    volumen_mensual_data = [round(volumen_por_mes[mes], 2) for mes in volumen_mensual_labels]

    # Top 10 ejercicios por frecuencia
    top_10_ejercicios = estadisticas_ejercicios[:10]

    context = {
        'cliente': cliente,
        'estadisticas_ejercicios': estadisticas_ejercicios,
        'total_ejercicios_unicos': total_ejercicios_unicos,
        'total_sesiones': total_sesiones,
        'ejercicio_mas_frecuente': ejercicio_mas_frecuente,
        'mayor_progresion': mayor_progresion,
        'volumen_total_global': round(volumen_total_global, 2),
        'records_recientes': records_recientes,
        'top_10_ejercicios': top_10_ejercicios,
        'volumen_mensual_labels': json.dumps(volumen_mensual_labels),
        'volumen_mensual_data': json.dumps(volumen_mensual_data),
        'orden_actual': orden,
        'busqueda_actual': busqueda,
    }

    return render(request, 'entrenos/dashboard_ejercicios.html', context)


def detalle_ejercicio_especifico(request, cliente_id, nombre_ejercicio):
    """
    Vista detallada de un ejercicio específico con gráficos de progresión
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Obtener todos los registros de este ejercicio
    ejercicios = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente,
        nombre_ejercicio__iexact=nombre_ejercicio
    ).select_related('entreno').order_by('entreno__fecha')

    if not ejercicios.exists():
        return render(request, 'entrenos/detalle_ejercicio_especifico.html', {
            'cliente': cliente,
            'nombre_ejercicio': nombre_ejercicio,
            'sin_datos': True
        })

    # Preparar datos para gráficos
    historial_completo = []
    for ejercicio in ejercicios:
        if ejercicio.completado and ejercicio.peso_kg > 0:
            historial_completo.append({
                'fecha': ejercicio.entreno.fecha.strftime('%Y-%m-%d'),
                'peso': float(ejercicio.peso_kg),
                'series': ejercicio.series,
                'repeticiones': ejercicio.repeticiones,
                'volumen': ejercicio.volumen(),
                'rpe': ejercicio.rpe,
                '1rm_estimado': calcular_1rm_epley(ejercicio.peso_kg, ejercicio.repeticiones)
            })

    # Calcular estadísticas
    pesos = [h['peso'] for h in historial_completo]
    volumenes = [h['volumen'] for h in historial_completo]

    estadisticas = {
        'nombre': nombre_ejercicio,
        'total_registros': len(historial_completo),
        'peso_maximo': max(pesos) if pesos else 0,
        'peso_minimo': min(pesos) if pesos else 0,
        'peso_promedio': sum(pesos) / len(pesos) if pesos else 0,
        'volumen_total': sum(volumenes),
        'primera_fecha': historial_completo[0]['fecha'] if historial_completo else None,
        'ultima_fecha': historial_completo[-1]['fecha'] if historial_completo else None,
    }

    context = {
        'cliente': cliente,
        'nombre_ejercicio': nombre_ejercicio,
        'historial_completo': json.dumps(historial_completo),
        'estadisticas': estadisticas,
    }

    return render(request, 'entrenos/detalle_ejercicio_especifico.html', context)


# Archivo: entrenos/views.py
# AGREGAR ESTOS ENDPOINTS AL FINAL DEL ARCHIVO

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime, date
from decimal import Decimal
from .models import EntrenoRealizado, SerieRealizada, DetalleEjercicioRealizado
from clientes.models import Cliente
from django.db.models import Sum, Avg, Count, Max
from django.utils import timezone


@require_http_methods(["POST"])
@csrf_exempt  # TODO: Implementar autenticación con token JWT
def api_registrar_ejercicio(request):
    """
    API Endpoint para registrar un ejercicio completado desde la app móvil.

    POST /api/ejercicios/registrar/

    Body (JSON):
    {
        "cliente_id": 2,
        "ejercicio_id": "1",
        "ejercicio_nombre": "Press Inclinado con Barra",
        "fecha": "2025-12-17",
        "series": [
            {"reps": 12, "peso": 60, "rpe": 8, "completado": true},
            {"reps": 10, "peso": 65, "rpe": 9, "completado": true},
            {"reps": 10, "peso": 65, "rpe": 7, "completado": false},
            {"reps": 8, "peso": 70, "rpe": 9, "completado": false}
        ],
        "notas": "Sentí buen pump en pectorales"
    }

    Response (JSON):
    {
        "success": true,
        "entreno_id": 123,
        "message": "Ejercicio registrado correctamente"
    }
    """
    try:
        # Parsear el body JSON
        data = json.loads(request.body)

        cliente_id = data.get('cliente_id')
        ejercicio_nombre = data.get('ejercicio_nombre')
        fecha_str = data.get('fecha')
        series = data.get('series', [])
        notas = data.get('notas', '')

        # Validaciones
        if not cliente_id or not ejercicio_nombre or not fecha_str:
            return JsonResponse({
                'success': False,
                'error': 'Faltan campos requeridos: cliente_id, ejercicio_nombre, fecha'
            }, status=400)

        # Obtener el cliente
        try:
            cliente = Cliente.objects.get(id=cliente_id, user=request.user)
        except Cliente.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Cliente no encontrado'
            }, status=404)

        # Parsear la fecha
        try:
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
            }, status=400)

        # Buscar o crear el EntrenoRealizado para este día
        entreno, created = EntrenoRealizado.objects.get_or_create(
            cliente=cliente,
            fecha=fecha_obj,
            defaults={
                'notas_generales': f'Entrenamiento registrado desde app móvil - {fecha_str}'
            }
        )

        # Crear el DetalleEjercicioRealizado
        detalle_ejercicio = DetalleEjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio=ejercicio_nombre,
            notas=notas
        )

        # Crear las series
        for idx, serie_data in enumerate(series, start=1):
            SerieRealizada.objects.create(
                detalle_ejercicio=detalle_ejercicio,
                numero_serie=idx,
                reps=serie_data.get('reps', 0),
                peso=Decimal(str(serie_data.get('peso', 0))),
                rpe=serie_data.get('rpe', 5),
                completada=serie_data.get('completado', False)
            )

        return JsonResponse({
            'success': True,
            'entreno_id': entreno.id,
            'detalle_ejercicio_id': detalle_ejercicio.id,
            'message': f'Ejercicio "{ejercicio_nombre}" registrado correctamente con {len(series)} series'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido en el body'
        }, status=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_obtener_estadisticas(request):
    """
    API Endpoint para obtener estadísticas del usuario.

    GET /api/estadisticas/?cliente_id=2

    Response (JSON):
    {
        "success": true,
        "volumen_semanal": 45000,
        "intensidad": "Alta - 92%",
        "acwr": 1.2,
        "racha_dias": 7,
        "proximo_entrenamiento": "Pierna Potencia - Mañana 18:00",
        "total_entrenamientos": 45,
        "ejercicios_completados": 320
    }
    """
    try:
        cliente_id = request.GET.get('cliente_id')

        if not cliente_id:
            return JsonResponse({
                'success': False,
                'error': 'Falta parámetro: cliente_id'
            }, status=400)

        # Obtener el cliente
        try:
            cliente = Cliente.objects.get(id=cliente_id, user=request.user)
        except Cliente.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Cliente no encontrado'
            }, status=404)

        # Calcular volumen semanal (últimos 7 días)
        hace_7_dias = timezone.now().date() - timedelta(days=7)

        volumen_semanal = SerieRealizada.objects.filter(
            detalle_ejercicio__entreno__cliente=cliente,
            detalle_ejercicio__entreno__fecha__gte=hace_7_dias,
            completada=True
        ).aggregate(
            total=Sum(F('reps') * F('peso'))
        )['total'] or 0

        # Calcular intensidad promedio (RPE promedio de la semana)
        rpe_promedio = SerieRealizada.objects.filter(
            detalle_ejercicio__entreno__cliente=cliente,
            detalle_ejercicio__entreno__fecha__gte=hace_7_dias,
            completada=True
        ).aggregate(
            promedio=Avg('rpe')
        )['promedio'] or 0

        # Clasificar intensidad
        if rpe_promedio >= 8:
            intensidad = f"Alta - {int(rpe_promedio * 10)}%"
        elif rpe_promedio >= 6:
            intensidad = f"Media - {int(rpe_promedio * 10)}%"
        else:
            intensidad = f"Baja - {int(rpe_promedio * 10)}%"

        # Calcular racha de días consecutivos
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).order_by('-fecha').values_list('fecha', flat=True)

        racha_dias = 0
        fecha_esperada = timezone.now().date()

        for fecha in entrenamientos:
            if fecha == fecha_esperada or fecha == fecha_esperada - timedelta(days=1):
                racha_dias += 1
                fecha_esperada = fecha - timedelta(days=1)
            else:
                break

        # Total de entrenamientos
        total_entrenamientos = EntrenoRealizado.objects.filter(cliente=cliente).count()

        # Total de ejercicios completados
        ejercicios_completados = DetalleEjercicioRealizado.objects.filter(
            entreno__cliente=cliente
        ).count()

        return JsonResponse({
            'success': True,
            'volumen_semanal': float(volumen_semanal),
            'intensidad': intensidad,
            'acwr': 1.2,  # TODO: Implementar cálculo real de ACWR
            'racha_dias': racha_dias,
            'proximo_entrenamiento': 'Próximamente',  # TODO: Obtener del plan
            'total_entrenamientos': total_entrenamientos,
            'ejercicios_completados': ejercicios_completados
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_obtener_perfil(request):
    """
    API Endpoint para obtener el perfil del usuario.

    GET /api/usuario/perfil/

    Response (JSON):
    {
        "success": true,
        "nombre": "Juan Pérez",
        "email": "juan@example.com",
        "clientes": [
            {"id": 2, "nombre": "Juan Pérez", "activo": true}
        ]
    }
    """
    try:
        user = request.user

        # Obtener todos los clientes del usuario
        clientes = Cliente.objects.filter(user=user).values(
            'id', 'nombre', 'apellido', 'email'
        )

        clientes_list = []
        for cliente in clientes:
            clientes_list.append({
                'id': cliente['id'],
                'nombre': f"{cliente['nombre']} {cliente['apellido']}".strip(),
                'email': cliente['email'],
                'activo': True
            })

        return JsonResponse({
            'success': True,
            'nombre': user.get_full_name() or user.username,
            'email': user.email,
            'username': user.username,
            'clientes': clientes_list
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)


# ============================================================================
# NUEVO DASHBOARD DE EVOLUCIÓN FÍSICA
# ============================================================================

def dashboard_evolucion(request, cliente_id):
    """
    Dashboard de evolución física con logros, récords, progresión y motivación.
    """
    from .services.estadisticas_service import EstadisticasService
    from .services.services import EstadisticasService as EstadisticasServiceV2
    from .models import RecordPersonal, ClienteLogroAutomatico, DesafioSemanal, ProgresoDesafio, SesionEntrenamiento

    cliente = get_object_or_404(Cliente, id=cliente_id)
    rango = request.GET.get('rango', '30d')

    # 1. Usar servicios de estadísticas para cálculos pesados
    stats = EstadisticasService.calcular_estadisticas_globales(cliente, rango)
    progresion = EstadisticasService.calcular_progresion_ejercicios(cliente, rango)
    distribucion = EstadisticasService.calcular_distribucion_muscular(cliente, rango)
    vol_semanal = EstadisticasService.calcular_volumen_semanal(cliente, rango)
    heatmap = EstadisticasService.generar_heatmap_actividad(cliente)
    acwr = EstadisticasServiceV2.analizar_acwr_unificado(cliente)
    balance = EstadisticasService.analizar_equilibrio_muscular(cliente)

    # 🎯 Nuevos Paneles Final Tier
    vol_optimo = EstadisticasService.analizar_volumen_optimo(cliente, rango)
    intensidad = EstadisticasService.analizar_intensidad_historica(cliente, rango)
    predicciones = EstadisticasService.generar_predicciones_ia(cliente)
    estancamientos = EstadisticasService.detectar_estancamientos(cliente)
    glosario = EstadisticasService.obtener_mapeo_muscular_completo()

    # 2. Obtener logros recientes
    logros_desbloqueados = ClienteLogroAutomatico.objects.filter(
        cliente=cliente
    ).select_related('logro').order_by('-fecha_desbloqueo')[:12]

    # 3. Obtener récords vigentes
    records_vigentes = RecordPersonal.objects.filter(
        cliente=cliente,
        superado=False
    ).order_by('-fecha_logrado')[:10]

    # 4. Obtener últimas sesiones (gamificadas)
    ultimas_sesiones = SesionEntrenamiento.objects.filter(
        entreno__cliente=cliente
    ).select_related('entreno', 'entreno__rutina').order_by('-entreno__fecha')[:10]

    # 5. Obtener desafíos activos
    hoy = timezone.now().date()
    desafios_activos = DesafioSemanal.objects.filter(
        activo=True,
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy
    )

    progreso_desafios = []
    for desafio in desafios_activos:
        progreso, _ = ProgresoDesafio.objects.get_or_create(
            cliente=cliente,
            desafio=desafio
        )
        progreso_desafios.append(progreso)

    # 6. Obtener Perfil de Gamificación (Nivel y Arquetipo)
    from logros.models import PerfilGamificacion, Arquetipo
    perfil_gamificacion, _ = PerfilGamificacion.objects.get_or_create(
        cliente=cliente,
        defaults={'nivel_actual': Arquetipo.objects.order_by('nivel').first()}
    )

    # --- FASE ACTUAL Y DATOS REALES DE RPE/FASES ---
    from clientes.models import FaseCliente
    fase_obj = FaseCliente.objects.filter(cliente=cliente).order_by('-fecha_inicio').first()
    fase_actual = fase_obj.fase if fase_obj else 'volumen'

    # RPE semanal real desde SesionEntrenamiento / SerieRealizada
    rpe_data = EstadisticasService.calcular_rpe_semanal(cliente, rango)
    rpe_semanal = rpe_data['data']

    # Fases históricas reales desde FaseCliente
    fases_historicas = EstadisticasService.obtener_fases_historicas(cliente, rango)

    context = {
        'cliente': cliente,
        'rango_seleccionado': rango,
        'estadisticas_globales': stats,
        'progresion_ejercicios': progresion,
        'glosario': glosario,
        'distribucion_muscular_labels': json.dumps(distribucion['labels']),
        'distribucion_muscular_data': json.dumps(distribucion['data']),
        'volumen_semanal_labels': json.dumps(vol_semanal['labels']),
        'volumen_semanal_data': json.dumps(vol_semanal['data']),
        'volumen_semanal_rpe': json.dumps(rpe_semanal),
        'volumen_semanal_fases': json.dumps(fases_historicas),
        'actividad_anual_data': json.dumps(heatmap),
        'logros_desbloqueados': logros_desbloqueados,
        'records_personales': records_vigentes,
        'ultimas_sesiones': ultimas_sesiones,
        'desafios_activos': progreso_desafios,
        'acwr': acwr,
        'acwr_data_json': json.dumps(acwr.get('dataframe', [])),
        'equilibrio_radar_json': json.dumps(balance.get('datos_radar', {})),

        # Nuevos datos
        'volumen_optimo_json': json.dumps(vol_optimo),
        'intensidad_json': json.dumps(intensidad),
        'predicciones_ia': predicciones,
        'estancamientos': estancamientos,
        'fase_actual': fase_actual,

        # Gamificación perfil
        'perfil_gamificacion': perfil_gamificacion,

        # AI Coach (usando datos ya calculados — evita recalcular)
        'coach_data': EstadisticasService.analizar_estado_coach(
            cliente,
            acwr_data=acwr,
            stats_globales=stats,
            estancados=estancamientos,
            equilibrio_data=balance,
            volumen_optimo_data=vol_optimo
        ),
    }

    return render(request, 'entrenos/dashboard_evolucion.html', context)


"""
Vista para la Evaluación Profesional de Entrenamiento
=====================================================
Integra el servicio de evaluación profesional con el dashboard existente.

Añadir a: entrenos/views.py (o crear entrenos/views/evaluacion_views.py)
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from clientes.models import Cliente
from entrenos.services.evaluacion_profesional_service import EvaluacionProfesionalService


@login_required
@require_GET
def evaluacion_api_view(request, cliente_id):
    """
    API endpoint para obtener la evaluación en formato JSON.
    Útil para actualizaciones AJAX o integración con el dashboard existente.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    semanas = int(request.GET.get('semanas', 4))

    evaluacion = EvaluacionProfesionalService.generar_evaluacion_completa(cliente, semanas=semanas)

    # Serializar fechas para JSON
    if evaluacion.get('evaluacion_posible'):
        evaluacion['fecha_evaluacion'] = evaluacion['fecha_evaluacion'].isoformat()
        evaluacion['periodo_analizado']['fecha_inicio'] = evaluacion['periodo_analizado']['fecha_inicio'].isoformat()
        evaluacion['periodo_analizado']['fecha_fin'] = evaluacion['periodo_analizado']['fecha_fin'].isoformat()

        # Eliminar datos raw muy grandes para la API
        if 'metricas_raw' in evaluacion:
            del evaluacion['metricas_raw']

    return JsonResponse(evaluacion)


# =============================================================================
# INTEGRACIÓN CON DASHBOARD EXISTENTE
# =============================================================================

def integrar_evaluacion_en_dashboard(request, cliente_id):
    """
    Ejemplo de cómo integrar la evaluación profesional en el dashboard_evolucion existente.

    Modificar tu vista dashboard_evolucion para incluir:
    """
    from entrenos.services.estadisticas_service import EstadisticasService
    from entrenos.services.records_service import RecordsService
    from .models import RecordPersonal, ClienteLogroAutomatico, DesafioSemanal, ProgresoDesafio, SesionEntrenamiento

    cliente = get_object_or_404(Cliente, id=cliente_id)
    rango_seleccionado = request.GET.get('rango', '30d')

    # 1. Usar servicios de estadísticas para cálculos pesados
    stats = EstadisticasService.calcular_estadisticas_globales(cliente, rango_seleccionado)
    progresion = EstadisticasService.calcular_progresion_ejercicios(cliente, rango_seleccionado)
    distribucion = EstadisticasService.calcular_distribucion_muscular(cliente, rango_seleccionado)
    vol_semanal = EstadisticasService.calcular_volumen_semanal(cliente, rango_seleccionado)
    heatmap = EstadisticasService.generar_heatmap_actividad(cliente)
    acwr = EstadisticasService.analizar_acwr(cliente)
    balance = EstadisticasService.analizar_equilibrio_muscular(cliente)
    # 🎯 Nuevos Paneles Final Tier
    vol_optimo = EstadisticasService.analizar_volumen_optimo(cliente, rango_seleccionado)
    intensidad = EstadisticasService.analizar_intensidad_historica(cliente, rango_seleccionado)
    predicciones = EstadisticasService.generar_predicciones_ia(cliente)
    estancamientos = EstadisticasService.detectar_estancamientos(cliente)
    glosario = EstadisticasService.obtener_mapeo_muscular_completo()
    # 2. Obtener logros recientes
    logros_desbloqueados = ClienteLogroAutomatico.objects.filter(
        cliente=cliente
    ).select_related('logro').order_by('-fecha_desbloqueo')[:12]

    # 3. Obtener récords vigentes
    records_vigentes = RecordPersonal.objects.filter(
        cliente=cliente,
        superado=False
    ).order_by('-fecha_logrado')[:10]

    # 4. Obtener últimas sesiones (gamificadas)
    ultimas_sesiones = SesionEntrenamiento.objects.filter(
        entreno__cliente=cliente
    ).select_related('entreno', 'entreno__rutina').order_by('-entreno__fecha')[:10]

    # 5. Obtener desafíos activos
    hoy = timezone.now().date()
    desafios_activos = DesafioSemanal.objects.filter(
        activo=True,
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy
    )
    progreso_desafios = []
    for desafio in desafios_activos:
        progreso, _ = ProgresoDesafio.objects.get_or_create(
            cliente=cliente,
            desafio=desafio
        )
        progreso_desafios.append(progreso)

    # --- LÓGICA DE FASE Y COACH IA ---
    from clientes.models import FaseCliente
    fase_obj = FaseCliente.objects.filter(cliente=cliente, fecha_fin__isnull=True).first()
    fase_actual = fase_obj.fase if fase_obj else 'mantenimiento'

    # Datos Reales de RPE y Fases
    rpe_data = EstadisticasService.calcular_rpe_semanal(cliente, rango)
    rpe_semanal = rpe_data['data']

    # Asegurar que las listas tengan la misma longitud que volumen_semanal['data']
    # Si las cronologías no coinciden perfectamente, rellenamos o recortamos
    target_len = len(vol_semanal['data'])
    current_len = len(rpe_semanal)

    if current_len < target_len:
        rpe_semanal.extend([0] * (target_len - current_len))
    elif current_len > target_len:
        rpe_semanal = rpe_semanal[:target_len]

    fases_historicas = EstadisticasService.obtener_fases_historicas(cliente, rango)

    # Ajustar longitud de fases también
    current_fase_len = len(fases_historicas)
    if current_fase_len < target_len:
        last_fase = fases_historicas[-1] if fases_historicas else 'Mantenimiento'
        fases_historicas.extend([last_fase] * (target_len - current_fase_len))
    elif current_fase_len > target_len:
        fases_historicas = fases_historicas[:target_len]
    # =============================================
    # TU CÓDIGO EXISTENTE AQUÍ
    # =============================================
    estadisticas_globales = EstadisticasService.calcular_estadisticas_globales(cliente, rango_seleccionado)
    coach_data = EstadisticasService.analizar_estado_coach(cliente)
    # ... etc

    # =============================================
    # NUEVA INTEGRACIÓN: Evaluación Profesional
    # =============================================
    # Mapear rango a semanas
    rango_a_semanas = {
        '30d': 4,
        '90d': 12,
        '180d': 24,
        'todo': 52
    }
    semanas = rango_a_semanas.get(rango_seleccionado, 4)

    # Generar evaluación profesional
    evaluacion_profesional = EvaluacionProfesionalService.generar_evaluacion_completa(
        cliente,
        semanas=min(semanas, 12)  # Máximo 12 semanas para evaluación significativa
    )

    context = {
        # ... tu contexto existente ...
        'cliente': cliente,
        'estadisticas_globales': estadisticas_globales,
        'coach_data': coach_data,
        'rango_seleccionado': rango,

        'progresion_ejercicios': progresion,
        'glosario': glosario,
        'distribucion_muscular_labels': json.dumps(distribucion['labels']),
        'distribucion_muscular_data': json.dumps(distribucion['data']),
        'volumen_semanal_labels': json.dumps(vol_semanal['labels']),
        'volumen_semanal_data': json.dumps(vol_semanal['data']),
        'volumen_semanal_rpe': json.dumps(rpe_semanal),
        'volumen_semanal_fases': json.dumps(fases_historicas),
        'actividad_anual_data': json.dumps(heatmap),
        'logros_desbloqueados': logros_desbloqueados,
        'records_personales': records_vigentes,
        'ultimas_sesiones': ultimas_sesiones,
        'desafios_activos': progreso_desafios,
        'acwr': acwr,
        'acwr_data_json': json.dumps(acwr.get('dataframe', [])),
        'equilibrio_radar_json': json.dumps(balance.get('datos_radar', {})),
        # Nuevos datos
        'volumen_optimo_json': json.dumps(vol_optimo),
        'intensidad_json': json.dumps(intensidad),
        'predicciones_ia': predicciones,
        'estancamientos': estancamientos,
        'fase_actual': fase_actual,

        # AI Coach (Lógica Real)
        'coach_data': EstadisticasService.analizar_estado_coach(cliente),
        # NUEVO: Añadir evaluación profesional
        'evaluacion_profesional': evaluacion_profesional,
    }

    return render(request, 'entrenos/dashboard_evolucion.html', context)


# =============================================================================
# AÑADIR ESTO A TU entrenos/views.py
# Reemplaza la vista evaluacion_profesional_view anterior
# =============================================================================

from entrenos.services.evaluacion_profesional_service_v2 import EvaluacionProfesionalServiceV2


@login_required
def evaluacion_profesional_view(request, cliente_id):
    """
    Vista para la evaluación profesional de entrenamiento v2.0
    Genera análisis científico basado en los datos de entrenamiento.

    NOVEDADES v2.0:
    - Comparativa con Plan Helms
    - Distribución de RPE en gráfico
    - Desglose de puntuación global
    - Rangos ideales en ratios
    - Tooltips explicativos
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Obtener parámetro de semanas (default 4 = 1 mesociclo)
    semanas = int(request.GET.get('semanas', 4))

    # Generar evaluación completa usando el servicio v2
    evaluacion = EvaluacionProfesionalServiceV2.generar_evaluacion_completa(cliente, semanas=semanas)

    context = {
        'cliente': cliente,
        'evaluacion': evaluacion,
        'semanas_analizadas': semanas,
        'opciones_semanas': [2, 4, 8, 12],
    }

    return render(request, 'entrenos/evaluacion_profesional.html', context)


# =============================================================================
# OPCIONAL: Endpoint API para obtener evaluación en JSON
# =============================================================================

from django.http import JsonResponse
from django.views.decorators.http import require_GET
import json
from datetime import date, datetime


class CustomJSONEncoder(json.JSONEncoder):
    """Encoder personalizado para manejar fechas y Decimals."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if hasattr(obj, '__float__'):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


@login_required
@require_GET
def evaluacion_profesional_api(request, cliente_id):
    """
    API endpoint para obtener la evaluación en formato JSON.
    Útil para integraciones o aplicaciones móviles.

    Uso: GET /entrenos/cliente/<id>/evaluacion-profesional/api/?semanas=4
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    semanas = int(request.GET.get('semanas', 4))

    evaluacion = EvaluacionProfesionalServiceV2.generar_evaluacion_completa(cliente, semanas=semanas)

    # Eliminar datos raw para reducir tamaño de respuesta
    if 'metricas_raw' in evaluacion:
        del evaluacion['metricas_raw']

    return JsonResponse(evaluacion, encoder=CustomJSONEncoder, safe=False)


@login_required
@require_POST
def actualizar_fase_cliente(request, cliente_id):
    """
    Actualiza la fase de entrenamiento del cliente vía AJAX.
    Crea un nuevo registro FaseCliente y cierra el anterior si existe.
    """
    import json
    from clientes.models import FaseCliente

    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        data = json.loads(request.body)
        nueva_fase = data.get('fase')

        if not nueva_fase:
            return JsonResponse({'status': 'error', 'message': 'Fase no proporcionada'}, status=400)

        # 1. Buscar fase activa actual y cerrarla
        fase_anterior = FaseCliente.objects.filter(
            cliente=cliente,
            fecha_fin__isnull=True
        ).first()

        if fase_anterior:
            # Si es la misma fase, no hacer nada (pero devolvemos OK)
            if fase_anterior.fase == nueva_fase:
                return JsonResponse({'status': 'ok', 'message': f'Fase {nueva_fase} ya estaba activa'})

            fase_anterior.fecha_fin = timezone.now().date()
            fase_anterior.save()

        # 2. Crear nueva fase
        FaseCliente.objects.create(
            cliente=cliente,
            fase=nueva_fase,
            fecha_inicio=timezone.now().date()
        )

        return JsonResponse({'status': 'ok', 'message': f'Fase actualizada a {nueva_fase}'})

    except Exception as e:
        import traceback
        return JsonResponse({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}, status=500)


# =============================================================================
# API BIO CORRELATION
# =============================================================================

@login_required
@require_GET
def api_bio_correlation(request, cliente_id):
    """
    Returns the last 30 days of Readiness Score vs Total Volume (kg) for the correlation chart.
    """
    from datetime import timedelta
    from django.utils import timezone
    from core.bio_context import BioContextProvider

    # 1. Verification
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.user != cliente.user and not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    hoy = timezone.now().date()
    hace_30_dias = hoy - timedelta(days=29)

    # Generate dates list
    dates = [hace_30_dias + timedelta(days=i) for i in range(30)]
    labels = [d.strftime('%d %b') for d in dates]

    # Arrays for the chart
    readiness_data = []
    volume_data = []

    # 2. Get Volume Data (group by date)
    entrenos_periodo = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__gte=hace_30_dias,
        fecha__lte=hoy
    )
    volumen_por_dia = {}
    for e in entrenos_periodo:
        vol = float(e.volumen_total_kg) if e.volumen_total_kg else 0.0
        volumen_por_dia[e.fecha] = volumen_por_dia.get(e.fecha, 0.0) + vol

    # 3. Assemble Data points per day
    for d in dates:
        # Calculate historical readiness for that day.
        # Since BioContextProvider doesn't have a historical method yet,
        # we try fetching daily recovery entry.
        from hyrox.models import DailyRecoveryEntry, UserInjury
        import math

        # This mirrors a simplified `get_readiness_score` logic for historical dates
        score = 1.0

        # a) Recovery Helms (optional simplification if not tracked historically)

        # b) Pain/Inflammation for the day
        entries = DailyRecoveryEntry.objects.filter(lesion__cliente=cliente, fecha=d)
        for entry in entries:
            pain = max(entry.dolor_reposo, entry.dolor_movimiento)
            pain_penalty = (pain / 10.0) * 0.4
            infl_penalty = (entry.inflamacion_percibida / 10.0) * 0.3
            score -= (pain_penalty + infl_penalty)

        # c) Active injuries on that day
        active_injuries = UserInjury.objects.filter(
            cliente=cliente,
            fecha_inicio__lte=d,
            activa=True  # Asuming they were active or still active
        )
        if active_injuries.exists():
            for inj in active_injuries:
                if inj.fase == 'AGUDA':
                    score *= 0.5
                elif inj.fase == 'SUB_AGUDA':
                    score *= 0.8

        score = max(0.0, min(1.0, score)) * 100
        readiness_data.append(round(score, 1))

        # Volume
        volume_data.append(round(volumen_por_dia.get(d, 0.0), 1))

    return JsonResponse({
        'labels': labels,
        'readiness': readiness_data,
        'volume': volume_data
    })


from django.views.decorators.http import require_POST


@require_POST
def api_save_hot_swap(request, cliente_id):
    """
    API endpoint para persistir una sustitución en caliente (hot swap) en el plan anual del cliente en la sesión.
    """
    try:
        data = json.loads(request.body)
        original_name = data.get('original_name')
        substitute_name = data.get('substitute_name')
        fecha_str = data.get('fecha')

        if not all([original_name, substitute_name, fecha_str]):
            return JsonResponse({'status': 'error', 'message': 'Faltan datos requeridos'}, status=400)

        # Obtener el plan de la sesión
        plan_str = request.session.get(f'plan_anual_{cliente_id}')
        if not plan_str:
            return JsonResponse({'status': 'error', 'message': 'No se encontró el plan en la sesión'}, status=404)

        try:
            plan = json.loads(plan_str)
        except TypeError:
            # It might already be a dictionary in some cases depends on serializer
            plan = plan_str

        entrenos_dict = plan.get('entrenos_por_fecha', {})

        entreno_dia = entrenos_dict.get(fecha_str)
        if not entreno_dia:
            return JsonResponse(
                {'status': 'error', 'message': f'No se encontró entrenamiento para la fecha {fecha_str}'}, status=404)

        # Buscar el ejercicio a sustituir
        ejercicios = entreno_dia.get('ejercicios', [])
        sustituido = False

        for ej in ejercicios:
            if ej.get('nombre', '').lower() == original_name.lower():
                # Actualizamos el nombre y documentamos la sustitución
                ej['nombre'] = substitute_name
                ej['was_bio_substituted'] = True
                if 'bio_substitution_reason' not in ej:
                    ej['bio_substitution_reason'] = {}
                ej['bio_substitution_reason']['original'] = original_name
                ej['bio_substitution_reason']['reason'] = 'Sustitución en caliente guardada permanentemente'

                sustituido = True
                break

        if sustituido:
            # Guardar el plan actualizado en la sesión
            request.session[f'plan_anual_{cliente_id}'] = json.dumps(plan)
            request.session.modified = True
            return JsonResponse({'status': 'success', 'message': 'Sustitución guardada exitosamente'})
        else:
            return JsonResponse({'status': 'error',
                                 'message': 'No se encontró el ejercicio original en el plan de hoy (quizás ya fue sustituido o borrado).'},
                                status=404)

    except Exception as e:
        logger.warning("Error en api_save_hot_swap: %s", e)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# MOLESTIA EN TIEMPO REAL
# ─────────────────────────────────────────────────────────────────────────────

# Mapa zona corporal → risk_tags que deben bloquearse
ZONA_TAGS_MAP = {
    'hombro':  ['empuje_horizontal', 'empuje_vertical', 'rotacion_interna_hombro'],
    'rodilla': ['flexion_rodilla_profunda', 'impacto_vertical', 'triple_extension_explosiva'],
    'cadera':  ['flexion_cadera_profunda', 'triple_extension_explosiva', 'bisagra_cadera_cargada'],
    'lumbar':  ['flexion_lumbar', 'carga_axial', 'bisagra_cadera_cargada'],
    'muñeca':  ['agarre_pesado', 'apoyo_muñeca'],
    'cuello':  ['carga_cervical'],
    'tobillo': ['impacto_vertical', 'dorsiflexion_tobillo'],
    'pecho':   ['empuje_horizontal'],
    'codo':    ['traccion_codo', 'empuje_codo'],
    'otro':    [],
}

SEVERIDAD_FASE = {
    2: 'SUB_AGUDA',
    3: 'AGUDA',
}
SEVERIDAD_GRAVEDAD = {
    2: 4,
    3: 7,
}


@require_POST
def api_reportar_molestia(request, cliente_id):
    """
    Recibe un reporte de molestia intra-entreno.
    - Severidad 1 (leve): solo registra, no crea UserInjury.
    - Severidad 2-3: crea/actualiza UserInjury y retorna alternativas de ejercicio.
    """
    from hyrox.models import UserInjury
    from analytics.planificador_helms.utils.helpers import (
        obtener_sustituto_en_caliente,
        buscar_ejercicio_por_nombre,
    )

    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        data = json.loads(request.body)

        ejercicio_nombre = data.get('ejercicio_nombre', '').strip()
        zona = data.get('zona', 'otro').lower().strip()
        severidad = int(data.get('severidad', 1))
        descripcion = data.get('descripcion', '').strip()

        tags_zona = ZONA_TAGS_MAP.get(zona, [])
        alternativas = []
        lesion_creada = False

        # ── Severidad 2-3: crear/actualizar UserInjury ──────────────────
        if severidad >= 2 and tags_zona:
            fase_str = SEVERIDAD_FASE.get(severidad, 'SUB_AGUDA')
            gravedad_val = SEVERIDAD_GRAVEDAD.get(severidad, 4)

            # Buscar lesión activa en la misma zona para no duplicar
            lesion_existente = UserInjury.objects.filter(
                cliente=cliente,
                zona_afectada__icontains=zona,
                activa=True,
            ).first()

            if lesion_existente:
                # Escalar si la nueva severidad es mayor
                fases_orden = ['RECUPERADO', 'RETORNO', 'SUB_AGUDA', 'AGUDA']
                if fases_orden.index(fase_str) > fases_orden.index(lesion_existente.fase):
                    lesion_existente.fase = fase_str
                    lesion_existente.gravedad = max(lesion_existente.gravedad, gravedad_val)
                    if descripcion:
                        lesion_existente.notas_medicas = (lesion_existente.notas_medicas or '') + f'\n[{zona.title()}] {descripcion}'
                    lesion_existente.save()
                lesion_creada = True
            else:
                notas = f'Reportada durante entrenamiento activo. Ejercicio: {ejercicio_nombre}.'
                if descripcion:
                    notas += f' Descripción: {descripcion}'
                UserInjury.objects.create(
                    cliente=cliente,
                    zona_afectada=zona.title(),
                    fase=fase_str,
                    gravedad=gravedad_val,
                    activa=True,
                    tags_restringidos=tags_zona,
                    notas_medicas=notas,
                )
                lesion_creada = True

        # ── Buscar alternativas siempre que haya tags ────────────────────
        if ejercicio_nombre and tags_zona:
            try:
                tags_bloqueados = set(tags_zona)
                sustituto = obtener_sustituto_en_caliente(ejercicio_nombre, tags_bloqueados)
                if sustituto:
                    alternativas.append({
                        'nombre': sustituto.get('nombre', ''),
                        'patron': sustituto.get('patron', ''),
                        'motivo': f'Sin carga en {zona}',
                    })
                # Buscar más opciones con tags parciales
                for tag in tags_zona[:2]:
                    alt = obtener_sustituto_en_caliente(ejercicio_nombre, {tag})
                    if alt and alt.get('nombre') not in [a['nombre'] for a in alternativas]:
                        alternativas.append({
                            'nombre': alt.get('nombre', ''),
                            'patron': alt.get('patron', ''),
                            'motivo': f'Evita {tag.replace("_", " ")}',
                        })
                        if len(alternativas) >= 3:
                            break
            except Exception as e:
                logger.warning("Error buscando alternativas molestia: %s", e)

        # Enriquecer alternativas con peso histórico del cliente
        from django.utils import timezone as _tz
        fecha_hoy = _tz.now().date()
        for alt in alternativas:
            try:
                datos_alt = obtener_ultimo_peso_ejercicio(cliente.id, alt['nombre'], fecha_hoy)
                alt['peso_anterior'] = datos_alt['peso'] if datos_alt else 0
                alt['fecha_anterior'] = datos_alt['fecha'].strftime('%d/%m') if datos_alt and datos_alt.get('fecha') else None
            except Exception:
                alt['peso_anterior'] = 0
                alt['fecha_anterior'] = None

        return JsonResponse({
            'status': 'ok',
            'severidad': severidad,
            'zona': zona,
            'lesion_creada': lesion_creada,
            'alternativas': alternativas,
            'mensaje': {
                1: 'Molestia leve anotada. Continúa con precaución.',
                2: 'Molestia moderada registrada. Se ha creado una restricción activa.',
                3: 'Dolor agudo registrado. Se recomienda parar este ejercicio.',
            }.get(severidad, ''),
        })

    except Exception as e:
        logger.warning("Error en api_reportar_molestia: %s", e)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================================================
# FASE 5 — TIMELINE UNIFICADO DEL ATLETA
# ============================================================================

@login_required
def timeline_atleta(request, cliente_id):
    """
    Timeline cronológico unificado: muestra cada día con sus actividades físicas
    (ActividadRealizada) y su entrada de diario (BitacoraDiaria) juntas.
    """
    from .models import ActividadRealizada
    from clientes.models import BitacoraDiaria
    from entrenos.services.services import EstadisticasService
    from collections import defaultdict, Counter

    cliente = get_object_or_404(Cliente, id=cliente_id)
    dias_rango = max(1, min(int(request.GET.get('dias', 30)), 90))

    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=dias_rango - 1)

    actividades_raw = list(
        ActividadRealizada.objects
        .filter(cliente=cliente, fecha__range=(fecha_inicio, hoy))
        .select_related('entreno_gym', 'sesion_hyrox')
        .order_by('fecha', 'hora_inicio')
    )
    # Deduplicar: si hay dos entradas para el mismo EntrenoRealizado, quedarse con una
    seen_gym = set()
    actividades = []
    for a in actividades_raw:
        if a.entreno_gym_id:
            if a.entreno_gym_id in seen_gym:
                continue
            seen_gym.add(a.entreno_gym_id)
        actividades.append(a)

    bitacoras = list(
        BitacoraDiaria.objects
        .filter(cliente=cliente, fecha__range=(fecha_inicio, hoy))
    )

    actos_por_dia = defaultdict(list)
    for a in actividades:
        actos_por_dia[a.fecha].append(a)

    bitacora_por_dia = {b.fecha: b for b in bitacoras}

    ICONOS = {
        'gym': '🏋️', 'hyrox': '⚡', 'carrera': '🏃', 'ciclismo': '🚴',
        'remo': '🚣', 'futbol': '⚽', 'natacion': '🏊',
        'yoga': '🧘', 'estiramientos': '🤸', 'otro': '🎯',
    }
    HUMOR_EMOJI = {'verde': '😊', 'amarillo': '😐', 'rojo': '😞'}
    DIAS_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    dias = []
    for i in range(dias_rango - 1, -1, -1):
        f = hoy - timedelta(days=i)
        actos = actos_por_dia.get(f, [])
        bitacora = bitacora_por_dia.get(f)
        carga_dia = sum(float(a.carga_ua) for a in actos if a.carga_ua)
        tipos = list({a.tipo for a in actos})

        dias.append({
            'fecha': f,
            'fecha_dia': f.day,
            'dia_semana': DIAS_ES[f.weekday()],
            'es_hoy': f == hoy,
            'actividades': actos,
            'iconos': [ICONOS.get(t, '🎯') for t in tipos],
            'carga_dia': round(carga_dia, 1) if carga_dia else None,
            'n_actividades': len(actos),
            'bitacora': bitacora,
            'humor_emoji': HUMOR_EMOJI.get(bitacora.humor, '') if bitacora and bitacora.humor else '',
            'energia': bitacora.energia_subjetiva if bitacora else None,
            'emocion_dia': bitacora.emocion_dia if bitacora else '',
            'nota': (bitacora.nota_personal or '')[:100] if bitacora else '',
        })

    acwr = EstadisticasService.analizar_acwr_unificado(cliente, periodo_dias=dias_rango)
    total_actividades = sum(d['n_actividades'] for d in dias)
    dias_activos = sum(1 for d in dias if d['n_actividades'] > 0)
    carga_total = sum(d['carga_dia'] or 0 for d in dias)

    # Desglose calculado en Python desde datos ya cargados — sin query extra
    conteo_tipos = Counter(a.tipo for a in actividades)
    desglose = [
        {'tipo': tipo, 'icono': ICONOS.get(tipo, '🎯'), 'total': total}
        for tipo, total in conteo_tipos.most_common()
    ]

    return render(request, 'entrenos/timeline_atleta.html', {
        'cliente': cliente,
        'dias': dias,
        'dias_rango': dias_rango,
        'acwr': acwr,
        'total_actividades': total_actividades,
        'dias_activos': dias_activos,
        'carga_total': round(carga_total, 1),
        'desglose': desglose,
        'rangos': [7, 30, 90],
    })


# ============================================================================
# FASE 2 — REGISTRO DE ACTIVIDAD LIBRE + AUTOCOMPLETE DE EJERCICIOS
# ============================================================================

@require_GET
def api_buscar_ejercicios(request, cliente_id):
    """
    API de autocomplete: devuelve sugerencias de actividades del cliente.
    Busca en EjercicioRealizado (gym) y en ActividadRealizada.titulo (actividades libres).
    """
    from .utils.utils import normalizar_nombre_ejercicio
    from .models import EjercicioRealizado, ActividadRealizada

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'resultados': []})

    q_norm = normalizar_nombre_ejercicio(q)

    # Fuente 1: ejercicios de gym
    nombres_gym = (
        EjercicioRealizado.objects
        .filter(entreno__cliente_id=cliente_id)
        .values_list('nombre_ejercicio', flat=True)
        .distinct()
    )
    # Fuente 2: títulos de actividades libres previas
    nombres_libres = (
        ActividadRealizada.objects
        .filter(cliente_id=cliente_id, titulo__isnull=False)
        .exclude(titulo='')
        .values_list('titulo', flat=True)
        .distinct()
    )

    vistos = set()
    resultados = []
    for nombre in list(nombres_libres) + list(nombres_gym):
        nombre_norm = normalizar_nombre_ejercicio(nombre)
        if q_norm in nombre_norm and nombre_norm not in vistos:
            vistos.add(nombre_norm)
            resultados.append(nombre.strip().title())
        if len(resultados) >= 10:
            break

    resultados.sort()
    return JsonResponse({'resultados': resultados})


def registrar_actividad_libre(request, cliente_id):
    """
    Formulario para registrar cualquier actividad física libre
    (fútbol, ciclismo, natación, etc.) que no pasa por el motor de gym ni hyrox.
    Crea directamente un registro en ActividadRealizada (hub central).
    """
    from .models import ActividadRealizada
    from .utils.utils import normalizar_nombre_ejercicio

    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        try:
            tipo = request.POST.get('tipo', 'otro')
            titulo_raw = request.POST.get('titulo', '').strip()
            fecha_str = request.POST.get('fecha', '')
            hora_str = request.POST.get('hora_inicio', '')
            duracion = request.POST.get('duracion_minutos', '') or None
            distancia = request.POST.get('distancia_metros', '') or None
            rpe = request.POST.get('rpe_medio', '') or None
            calorias = request.POST.get('calorias', '') or None
            notas = request.POST.get('notas', '').strip()

            # Normalizar título si es nombre de ejercicio
            titulo = titulo_raw.title() if titulo_raw else tipo.replace('_', ' ').title()

            from datetime import date as date_type, datetime as datetime_type
            fecha = date_type.fromisoformat(fecha_str) if fecha_str else date_type.today()

            hora = None
            if hora_str:
                try:
                    hora = datetime_type.strptime(hora_str, '%H:%M').time()
                except ValueError:
                    pass

            duracion = int(duracion) if duracion else None
            distancia = int(distancia) if distancia else None
            rpe = float(rpe) if rpe else None
            calorias = int(calorias) if calorias else None

            carga_ua = round(rpe * duracion, 1) if (rpe and duracion) else None

            ActividadRealizada.objects.create(
                cliente=cliente,
                tipo=tipo,
                titulo=titulo,
                fecha=fecha,
                hora_inicio=hora,
                duracion_minutos=duracion,
                distancia_metros=distancia,
                rpe_medio=rpe,
                calorias=calorias,
                carga_ua=carga_ua,
                notas=notas,
                fuente='manual',
            )

            messages.success(request, f'✅ Actividad "{titulo}" registrada correctamente.')
            return redirect('entrenos:timeline_atleta', cliente_id=cliente.id)

        except Exception as e:
            logger.warning("Error registrando actividad libre: %s", e)
            messages.error(request, f'Error al registrar la actividad: {e}')

    # GET — mostrar formulario
    from .models import ActividadRealizada
    context = {
        'cliente': cliente,
        'tipo_choices': ActividadRealizada.TIPO_CHOICES,
        'hoy': date.today().isoformat(),
    }
    return render(request, 'entrenos/registrar_actividad_libre.html', context)


# ── Editar actividad libre ────────────────────────────────────────────────────
@login_required
def editar_actividad_libre(request, cliente_id, actividad_id):
    from .models import ActividadRealizada
    from .utils.utils import normalizar_nombre_ejercicio

    cliente = get_object_or_404(Cliente, id=cliente_id)
    actividad = get_object_or_404(ActividadRealizada, id=actividad_id, cliente=cliente)

    # Solo actividades manuales son editables desde aquí
    if actividad.entreno_gym or actividad.sesion_hyrox:
        messages.warning(request, "Este registro se edita desde su sección original (Gym o Hyrox).")
        return redirect('entrenos:timeline_atleta', cliente_id=cliente.id)

    if request.method == 'POST':
        actividad.tipo = request.POST.get('tipo', actividad.tipo)
        actividad.titulo = request.POST.get('titulo', '').strip()
        actividad.fecha = request.POST.get('fecha', actividad.fecha)
        actividad.hora_inicio = request.POST.get('hora_inicio') or None
        actividad.duracion_minutos = request.POST.get('duracion_minutos') or None
        actividad.distancia_metros = request.POST.get('distancia_metros') or None
        actividad.rpe_medio = request.POST.get('rpe_medio') or None
        actividad.calorias = request.POST.get('calorias') or None
        actividad.notas = request.POST.get('notas', '')
        actividad.carga_ua = actividad.calcular_carga_ua()
        actividad.save()
        messages.success(request, '✅ Actividad actualizada.')
        return redirect('entrenos:timeline_atleta', cliente_id=cliente.id)

    context = {
        'cliente': cliente,
        'actividad': actividad,
        'tipo_choices': ActividadRealizada.TIPO_CHOICES,
    }
    return render(request, 'entrenos/editar_actividad_libre.html', context)


# ── Eliminar actividad libre ──────────────────────────────────────────────────
@login_required
@require_POST
def eliminar_actividad_libre(request, cliente_id, actividad_id):
    from .models import ActividadRealizada

    cliente = get_object_or_404(Cliente, id=cliente_id)
    actividad = get_object_or_404(ActividadRealizada, id=actividad_id, cliente=cliente)

    if actividad.entreno_gym or actividad.sesion_hyrox:
        messages.warning(request, "Este registro se elimina desde su sección original.")
        return redirect('entrenos:timeline_atleta', cliente_id=cliente.id)

    actividad.delete()
    messages.success(request, '🗑️ Actividad eliminada.')
    return redirect('entrenos:timeline_atleta', cliente_id=cliente.id)

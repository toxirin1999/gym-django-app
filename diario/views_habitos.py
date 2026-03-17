from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import json

from .models import ProsocheMes, ProsocheHabito, ProsocheHabitoDia
from .forms import ProsocheHabitoForm, TriggerHabitoForm
from .services import HabitosService, InsigniasService

# ========================================
# HÁBITOS - DASHBOARD UNIFICADO
# ========================================

@login_required
def habitos_dashboard(request):
    """
    Dashboard unificado de hábitos que muestra hábitos positivos (a formar)
    y hábitos negativos (a eliminar) por separado con su progreso.
    """
    hoy = timezone.now().date()
    mes_nombre = hoy.strftime('%B')
    año = hoy.year
    
    # Obtener o crear el mes actual
    prosoche_mes, _ = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_nombre,
        año=año
    )
    
    # Obtener todos los hábitos separados por tipo usando el servicio
    habitos_data = HabitosService.obtener_habitos_por_tipo(prosoche_mes)
    
    # Generar insights y días del mes para cada hábito
    for habito_item in habitos_data['positivos'] + habitos_data['negativos']:
        habito_item['insights'] = HabitosService.generar_insights_basicos(habito_item['habito'])
        
        # Obtener días del mes (1-31)
        dias_mes = []
        for dia_num in range(1, 32):
            dia_obj = ProsocheHabitoDia.objects.filter(
                habito=habito_item['habito'],
                dia=dia_num
            ).first()
            
            dias_mes.append({
                'numero': dia_num,
                'completado': dia_obj.completado if dia_obj else False
            })
        
        habito_item['dias_mes'] = dias_mes
    
    context = {
        'hoy': hoy,
        'prosoche_mes': prosoche_mes,
        'habitos_positivos': habitos_data['positivos'],
        'habitos_negativos': habitos_data['negativos'],
        'total_positivos': habitos_data['total_positivos'],
        'total_negativos': habitos_data['total_negativos'],
    }
    
    return render(request, 'diario/habitos_dashboard.html', context)


@login_required
def habito_crear(request):
    """Vista para crear un nuevo hábito"""
    if request.method == 'POST':
        form = ProsocheHabitoForm(request.POST)
        if form.is_valid():
            hoy = timezone.now().date()
            mes_nombre = hoy.strftime('%B')
            año = hoy.year
            
            # Obtener o crear el mes actual
            prosoche_mes, _ = ProsocheMes.objects.get_or_create(
                usuario=request.user,
                mes=mes_nombre,
                año=año
            )
            
            habito = form.save(commit=False)
            habito.prosoche_mes = prosoche_mes
            habito.save()
            
            messages.success(request, f'Hábito "{habito.nombre}" creado exitosamente!')
            return redirect('diario:habitos_dashboard')
    else:
        form = ProsocheHabitoForm()
    
    context = {
        'form': form,
        'titulo': 'Crear Nuevo Hábito',
        'boton_texto': 'Crear Hábito'
    }
    
    return render(request, 'diario/habito_form.html', context)


@login_required
def habito_editar(request, habito_id):
    """Vista para editar un hábito existente"""
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user
    )
    
    if request.method == 'POST':
        form = ProsocheHabitoForm(request.POST, instance=habito)
        if form.is_valid():
            form.save()
            messages.success(request, f'Hábito "{habito.nombre}" actualizado exitosamente!')
            return redirect('diario:habitos_dashboard')
    else:
        form = ProsocheHabitoForm(instance=habito)
    
    context = {
        'form': form,
        'habito': habito,
        'titulo': f'Editar: {habito.nombre}',
        'boton_texto': 'Guardar Cambios'
    }
    
    return render(request, 'diario/habito_form.html', context)


@login_required
@require_http_methods(["POST"])
def habito_toggle_dia(request):
    """Vista AJAX para marcar/desmarcar un día como completado"""
    try:
        # Parse JSON body
        data = json.loads(request.body)
        habito_id = data.get('habito_id')
        dia = data.get('dia')
        
        habito = get_object_or_404(
            ProsocheHabito,
            id=habito_id,
            prosoche_mes__usuario=request.user
        )
        
        # Obtener o crear el día
        dia_obj, created = ProsocheHabitoDia.objects.get_or_create(
            habito=habito,
            dia=dia
        )
        
        # Toggle completado
        dia_obj.completado = not dia_obj.completado
        dia_obj.save()
        
        # Calcular progreso actualizado
        progreso = HabitosService.calcular_progreso(habito)
        milestone = HabitosService.verificar_milestone(habito)
        
        # Verificar insignias
        insignias_data = []
        insignias_nuevas = InsigniasService.verificar_insignias_habito(habito, request.user)
        if insignias_nuevas:
            for insignia in insignias_nuevas:
                insignias_data.append({
                    'nombre': insignia.nombre,
                    'descripcion': insignia.descripcion,
                    'icono': insignia.icono
                })
        
        return JsonResponse({
            'success': True,
            'completado': dia_obj.completado,
            'progreso': progreso,
            'milestone': milestone,
            'insignias_nuevas': insignias_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def habito_wizard_4leyes(request, habito_id):
    """Vista del wizard para configurar las 4 Leyes de Atomic Habits"""
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user
    )
    
    if request.method == 'POST':
        # Guardar las 4 leyes y el habit loop
        habito.ley_1_obvio = request.POST.get('ley_1_obvio', '')
        habito.ley_2_atractivo = request.POST.get('ley_2_atractivo', '')
        habito.ley_3_facil = request.POST.get('ley_3_facil', '')
        habito.ley_4_satisfactorio = request.POST.get('ley_4_satisfactorio', '')
        habito.senal_cue = request.POST.get('senal_cue', '')
        habito.anhelo_craving = request.POST.get('anhelo_craving', '')
        habito.recompensa_reward = request.POST.get('recompensa_reward', '')
        habito.identidad_objetivo = request.POST.get('identidad_objetivo', '')
        habito.save()
        
        messages.success(
            request, 
            f'¡Hábito "{habito.nombre}" diseñado con las 4 Leyes! Ahora es inevitable que lo logres. 🎯'
        )
        return redirect('diario:habitos_dashboard')
    
    context = {
        'habito': habito
    }
    
    return render(request, 'diario/habito_wizard_4leyes.html', context)


@login_required
@require_http_methods(["POST"])
def habito_eliminar(request, habito_id):
    """Vista para eliminar un hábito"""
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user
    )
    
    nombre_habito = habito.nombre
    habito.delete()
    
    messages.success(request, f'Hábito "{nombre_habito}" eliminado correctamente.')
    return redirect('diario:habitos_dashboard')

# ========================================
# TRIGGERS - ANÁLISIS DE RECAÍDAS
# ========================================

@login_required
def habito_registrar_trigger(request, habito_id):
    """Vista para registrar un trigger/impulso de un hábito negativo"""
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user,
        tipo_habito='negativo'  # Solo para hábitos negativos
    )
    
    if request.method == 'POST':
        form = TriggerHabitoForm(request.POST)
        if form.is_valid():
            trigger = form.save(commit=False)
            trigger.habito = habito
            trigger.save()
            
            if trigger.cediste:
                messages.warning(
                    request,
                    f'Impulso registrado. No te rindas, cada recaída es una oportunidad de aprender. 💪'
                )
            else:
                messages.success(
                    request,
                    f'¡Resististe el impulso! Eso es fortaleza real. Sigue así. 🛡️'
                )
            
            return redirect('diario:habito_analisis_patrones', habito_id=habito.id)
    else:
        form = TriggerHabitoForm()
    
    context = {
        'habito': habito,
        'form': form
    }
    
    return render(request, 'diario/habito_registrar_trigger.html', context)


@login_required
def habito_analisis_patrones(request, habito_id):
    """Vista del dashboard de análisis de patrones de recaída"""
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user,
        tipo_habito='negativo'
    )
    
    # Obtener análisis de patrones
    from .services import TriggersService
    analisis = TriggersService.analizar_patrones_recaida(habito)
    recomendaciones = TriggersService.generar_recomendaciones(analisis)
    
    # Obtener últimos triggers
    ultimos_triggers = habito.triggers.all()[:10]
    
    context = {
        'habito': habito,
        'analisis': analisis,
        'recomendaciones': recomendaciones,
        'ultimos_triggers': ultimos_triggers
    }
    
    return render(request, 'diario/habito_analisis_patrones.html', context)

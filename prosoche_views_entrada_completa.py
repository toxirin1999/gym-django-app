# ========================================
# VISTAS ACTUALIZADAS PARA PROSOCHE ENTRADA COMPLETA
# ========================================

import json
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import ProsocheMes, ProsocheDiario

@login_required
def prosoche_nueva_entrada(request):
    """Vista para crear nueva entrada del diario"""
    # Obtener fecha actual o fecha específica
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha = date.today()
    else:
        fecha = date.today()
    
    # Obtener o crear el mes de Prosoche
    mes_nombre = fecha.strftime('%B')
    año = fecha.year
    
    prosoche_mes, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_nombre,
        año=año,
        defaults={
            'objetivo_mes_1': '',
            'objetivo_mes_2': '',
            'objetivo_mes_3': ''
        }
    )
    
    # Verificar si ya existe una entrada para esta fecha
    entrada_existente = ProsocheDiario.objects.filter(
        prosoche_mes=prosoche_mes,
        fecha=fecha
    ).first()
    
    if request.method == 'POST':
        try:
            # Procesar datos del formulario
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
            
            # Procesar tareas del día
            tareas_json = request.POST.get('tareas_dia', '[]')
            try:
                data['tareas_dia'] = json.loads(tareas_json)
            except json.JSONDecodeError:
                data['tareas_dia'] = []
            
            # Crear o actualizar entrada
            if entrada_existente:
                # Actualizar entrada existente
                for key, value in data.items():
                    setattr(entrada_existente, key, value)
                entrada_existente.save()
                messages.success(request, f'Entrada del {fecha.strftime("%d/%m/%Y")} actualizada correctamente.')
            else:
                # Crear nueva entrada
                data['prosoche_mes'] = prosoche_mes
                data['fecha'] = fecha
                ProsocheDiario.objects.create(**data)
                messages.success(request, f'Nueva entrada del {fecha.strftime("%d/%m/%Y")} creada correctamente.')
            
            return redirect('prosoche_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error al guardar la entrada: {str(e)}')
    
    # Preparar datos para el formulario
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
        'form': type('Form', (), form_data)(),  # Objeto simulado para el template
        'entrada_existente': entrada_existente,
        'es_edicion': entrada_existente is not None,
    }
    
    return render(request, 'diario/prosoche_entrada_form.html', context)

@login_required
def prosoche_editar_entrada(request, entrada_id):
    """Vista para editar entrada existente del diario"""
    entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)
    
    # Redirigir a la vista de nueva entrada con la fecha específica
    return redirect(f"{reverse('prosoche_nueva_entrada')}?fecha={entrada.fecha.strftime('%Y-%m-%d')}")

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

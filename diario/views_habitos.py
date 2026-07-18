from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import calendar
import json

from .models import Gesto, ProsocheHabito
from .forms import CadenciaGestoForm, GestoForm, TriggerHabitoForm
from .insights_engine import lectura_principal_cultivo
from .services import HabitosService, InsigniasService

# ========================================
# GESTOS - DASHBOARD UNIFICADO (Phase 2.0D)
# ========================================


def _legacy_prosoche_habito_id(usuario, nombre):
    """
    Lookup del ProsocheHabito legacy más reciente para un Gesto, por nombre
    (normalizando espacios — la auditoría mostró nombres como "Nfp ").
    Devuelve el pk o None si no hay match. Cardinalidad pequeña (~32 filas
    legacy), así que se compara en Python tras un único .all().
    """
    nombre_normalizado = nombre.strip().lower()
    candidatos = ProsocheHabito.objects.filter(
        prosoche_mes__usuario=usuario
    ).order_by('-fecha_creacion')

    for candidato in candidatos:
        if candidato.nombre.strip().lower() == nombre_normalizado:
            return candidato.id
    return None


def _cadencia_label(gesto):
    """Etiqueta estructural de la cadencia configurada — solo describe
    la configuración, no interpreta nada (Fase 5B; el lenguaje analítico
    conservador es competencia de la Fase 5C)."""
    if gesto.tipo_cadencia == Gesto.CADENCIA_DIARIA:
        return 'Diaria'
    if gesto.tipo_cadencia == Gesto.CADENCIA_SEMANAL:
        if gesto.frecuencia_semanal_objetivo:
            return f'{gesto.frecuencia_semanal_objetivo}x por semana'
        return 'Semanal'
    if gesto.tipo_cadencia == Gesto.CADENCIA_DIAS_CONCRETOS:
        dias = gesto.dias_semana_objetivo or []
        if dias:
            return 'Días concretos: ' + ', '.join(dia.capitalize() for dia in dias)
        return 'Días concretos'
    return 'Libre'


@login_required
def habitos_dashboard(request):
    """
    Dashboard unificado de Gestos (Phase 2.0D): muestra Gesto activos
    separados por tipo (cultivo/suelto) con su proyección mensual y racha.
    No depende de ProsocheMes para el mes actual.
    """
    hoy = timezone.localdate()

    gestos_por_tipo = HabitosService.obtener_gestos_por_tipo(request.user)

    habitos_positivos = []
    habitos_negativos = []

    for gesto in gestos_por_tipo['cultivo'] + gestos_por_tipo['suelto']:
        dias_mes = HabitosService.proyeccion_mensual(gesto, hoy.year, hoy.month)
        insights = HabitosService.generar_insights_basicos(gesto)

        # Fase 5A: la racha (actual y mejor) solo es una lectura honesta
        # para tipo_cadencia='diaria'. suelto no tiene cadencia y queda
        # fuera de esta política — su racha ya era correcta.
        racha_aplicable = gesto.tipo == 'suelto' or gesto.tipo_cadencia == Gesto.CADENCIA_DIARIA
        racha = gesto.get_racha_actual() if racha_aplicable else 0
        mejor_racha_visible = gesto.mejor_racha if racha_aplicable else 0

        # Fase 5C: lectura principal del analizador — una sola por
        # hábito, solo para cultivo. suelto sigue con TriggerHabito.
        lectura_cultivo = lectura_principal_cultivo(gesto, hoy) if gesto.tipo == 'cultivo' else None

        item = {
            'habito': gesto,
            'dias_mes': dias_mes,
            'progreso': {'racha': racha},
            'mejor_racha_visible': mejor_racha_visible,
            'insights': insights,
            'cadencia_label': _cadencia_label(gesto),
            'lectura_cultivo': lectura_cultivo,
            'prosoche_habito_legacy_id': _legacy_prosoche_habito_id(request.user, gesto.nombre),
        }

        if gesto.tipo == 'suelto':
            habitos_negativos.append(item)
        else:
            habitos_positivos.append(item)

    context = {
        'hoy': hoy,
        'habitos_positivos': habitos_positivos,
        'habitos_negativos': habitos_negativos,
        'total_positivos': len(habitos_positivos),
        'total_negativos': len(habitos_negativos),
        'habitos_cerrados_cultivo': HabitosService.obtener_gestos_cerrados_cultivo(request.user),
    }

    return render(request, 'diario/habitos_dashboard.html', context)


@login_required
def habito_crear(request):
    """Vista para crear un nuevo Gesto (Phase 2.0D)."""
    if request.method == 'POST':
        form = GestoForm(request.POST)
        if form.is_valid():
            gesto = form.save(commit=False)
            gesto.usuario = request.user
            gesto.save()

            messages.success(request, f'Gesto "{gesto.nombre}" registrado.')
            return redirect('diario:habitos_dashboard')
    else:
        form = GestoForm()

    context = {
        'form': form,
        'titulo': 'Nuevo Gesto',
        'boton_texto': 'Registrar Gesto'
    }

    return render(request, 'diario/habito_form.html', context)


@login_required
def habito_editar(request, habito_id):
    """Vista para editar un Gesto existente (Phase 2.0D)."""
    gesto = get_object_or_404(Gesto, id=habito_id, usuario=request.user)

    if request.method == 'POST':
        form = GestoForm(request.POST, instance=gesto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Gesto "{gesto.nombre}" actualizado.')
            return redirect('diario:habitos_dashboard')
    else:
        form = GestoForm(instance=gesto)

    context = {
        'form': form,
        'habito': gesto,
        'titulo': f'Editar: {gesto.nombre}',
        'boton_texto': 'Guardar Cambios'
    }

    return render(request, 'diario/habito_form.html', context)


@login_required
def habito_configurar_cadencia(request, habito_id):
    """
    Configura o cambia la cadencia de un Gesto tipo='cultivo' (Fase 5B).

    La advertencia de reinicio del análisis solo se muestra cuando ya
    existía una cadencia configurada (cadencia_configurada_en no nulo) Y
    los valores enviados son distintos de los actuales — nunca en la
    primera configuración de un hábito histórico, tal como exige el
    contrato. Es un flujo de dos pasos: si hace falta advertencia, se
    vuelve a renderizar el mismo formulario con los valores ya
    introducidos y un aviso; solo se persiste al reenviar con
    confirmado=1.
    """
    gesto = get_object_or_404(Gesto, id=habito_id, usuario=request.user, tipo='cultivo')

    if request.method == 'POST':
        form = CadenciaGestoForm(request.POST)
        if form.is_valid():
            nuevo_tipo = form.cleaned_data['tipo_cadencia']
            nueva_frecuencia = form.cleaned_data.get('frecuencia_semanal_objetivo')
            nuevos_dias = form.cleaned_data.get('dias_semana_objetivo') or []

            hay_cambio = (
                nuevo_tipo != gesto.tipo_cadencia
                or nueva_frecuencia != gesto.frecuencia_semanal_objetivo
                or set(nuevos_dias) != set(gesto.dias_semana_objetivo or [])
            )
            sin_cadencia_previa = gesto.cadencia_configurada_en is None
            requiere_advertencia = hay_cambio and not sin_cadencia_previa
            confirmado = request.POST.get('confirmado') == '1'

            if requiere_advertencia and not confirmado:
                context = {
                    'gesto': gesto,
                    'form': form,
                    'requiere_confirmacion': True,
                }
                return render(request, 'diario/habito_configurar_cadencia.html', context)

            # configurar_cadencia() siempre reinicia cadencia_configurada_en
            # a hoy (Fase 3) — solo se llama si hay algo que de verdad
            # configurar o cambiar. Reenviar el formulario sin ningún
            # cambio real no debe desplazar el ancla del análisis.
            if sin_cadencia_previa or hay_cambio:
                gesto.configurar_cadencia(nuevo_tipo, nueva_frecuencia, nuevos_dias)
                messages.success(request, f'Cadencia de "{gesto.nombre}" configurada.')
            return redirect('diario:habitos_dashboard')
    else:
        form = CadenciaGestoForm(initial={
            'tipo_cadencia': gesto.tipo_cadencia,
            'frecuencia_semanal_objetivo': gesto.frecuencia_semanal_objetivo,
            'dias_semana_objetivo': gesto.dias_semana_objetivo or [],
        })

    context = {
        'gesto': gesto,
        'form': form,
        'requiere_confirmacion': False,
    }
    return render(request, 'diario/habito_configurar_cadencia.html', context)


@login_required
@require_http_methods(["POST"])
def habito_toggle_dia(request):
    """Vista AJAX para marcar/desmarcar un día del mes actual como cumplido."""
    try:
        data = json.loads(request.body)
        habito_id = data.get('habito_id')
        dia = data.get('dia')

        # Fase 3: un Gesto pausado o cerrado no admite registros manuales
        # desde el dashboard — evita filas de RegistroGesto en fechas que
        # la taxonomía del analizador clasificaría como pausado/fuera_de_vida.
        gesto = get_object_or_404(Gesto, id=habito_id, usuario=request.user, estado='activo')

        hoy = timezone.localdate()
        dia_num = int(dia)
        _, dias_en_mes = calendar.monthrange(hoy.year, hoy.month)
        if dia_num < 1 or dia_num > dias_en_mes:
            return JsonResponse({'success': False, 'error': 'Día fuera de rango para el mes actual.'}, status=400)

        fecha = date(hoy.year, hoy.month, dia_num)
        completado = HabitosService.toggle_dia(gesto, fecha)

        insignias_data = []
        insignias_nuevas = InsigniasService.verificar_insignias_habito(gesto, request.user)
        if insignias_nuevas:
            for insignia in insignias_nuevas:
                insignias_data.append({
                    'nombre': insignia.nombre,
                    'descripcion': insignia.descripcion,
                    'icono': insignia.icono
                })

        return JsonResponse({
            'success': True,
            'completado': completado,
            'insignias_nuevas': insignias_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def habito_wizard_4leyes(request, habito_id):
    """Vista del wizard para configurar las 4 Leyes de Atomic Habits.

    Sigue operando sobre ProsocheHabito legacy (sin cambios en Phase 2.0D).
    """
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user
    )

    if request.method == 'POST':
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
    """Vista para eliminar un hábito legacy (ProsocheHabito).

    No usada por el dashboard de Gestos (que usa pausar/cerrar), se conserva
    para no romper enlaces legacy existentes.
    """
    habito = get_object_or_404(
        ProsocheHabito,
        id=habito_id,
        prosoche_mes__usuario=request.user
    )

    nombre_habito = habito.nombre
    habito.delete()

    messages.success(request, f'Hábito "{nombre_habito}" eliminado correctamente.')
    return redirect('diario:habitos_dashboard')


@login_required
@require_http_methods(["POST"])
def habito_pausar(request, habito_id):
    """Pausa un Gesto (Phase 2.0D). Conserva todo el historial de registros.
    Fase 3: además abre una PausaGesto (ver HabitosService.pausar_gesto)."""
    gesto = get_object_or_404(Gesto, id=habito_id, usuario=request.user)
    HabitosService.pausar_gesto(gesto)
    messages.success(request, f'Gesto "{gesto.nombre}" pausado.')
    return redirect('diario:habitos_dashboard')


@login_required
@require_http_methods(["POST"])
def habito_reactivar(request, habito_id):
    """Reactiva un Gesto pausado (Fase 3). Cierra la PausaGesto abierta
    y vuelve a estado='activo'. No existe transición inversa para
    hábitos 'cerrado' — cerrar es definitivo."""
    gesto = get_object_or_404(Gesto, id=habito_id, usuario=request.user, estado='pausado')
    HabitosService.reactivar_gesto(gesto)
    messages.success(request, f'Gesto "{gesto.nombre}" reactivado.')
    return redirect('diario:habitos_dashboard')


@login_required
@require_http_methods(["POST"])
def habito_cerrar(request, habito_id):
    """Cierra un Gesto (Phase 2.0D). Conserva todo el historial de registros.
    Fase 3: si había una pausa abierta, se cierra en el mismo movimiento
    (misma regla de colapso que reactivar) para no dejar un intervalo
    huérfano tras el cierre definitivo."""
    gesto = get_object_or_404(Gesto, id=habito_id, usuario=request.user)
    fecha_cierre = timezone.localdate()
    HabitosService._cerrar_pausa_abierta(gesto, fecha_cierre)
    gesto.estado = 'cerrado'
    gesto.fecha_cierre = fecha_cierre
    gesto.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, f'Gesto "{gesto.nombre}" cerrado.')
    return redirect('diario:habitos_dashboard')


# ========================================
# TRIGGERS - ANÁLISIS DE RECAÍDAS (Phase 2.0D: sobre Gesto)
# ========================================

@login_required
def habito_registrar_trigger(request, habito_id):
    """Vista para registrar un trigger/impulso de un Gesto tipo 'suelto'."""
    gesto = get_object_or_404(
        Gesto,
        id=habito_id,
        usuario=request.user,
        tipo='suelto',
    )

    if request.method == 'POST':
        form = TriggerHabitoForm(request.POST)
        if form.is_valid():
            trigger = form.save(commit=False)
            trigger.gesto = gesto
            trigger.habito = None
            trigger.save()

            if trigger.cediste:
                messages.warning(
                    request,
                    'Impulso registrado. No te rindas, cada recaída es una oportunidad de aprender. 💪'
                )
            else:
                messages.success(
                    request,
                    '¡Resististe el impulso! Eso es fortaleza real. Sigue así. 🛡️'
                )

            return redirect('diario:habito_analisis_patrones', habito_id=gesto.id)
    else:
        form = TriggerHabitoForm()

    context = {
        'habito': gesto,
        'form': form
    }

    return render(request, 'diario/habito_registrar_trigger.html', context)


@login_required
def habito_analisis_patrones(request, habito_id):
    """Vista del dashboard de análisis de patrones de recaída para un Gesto 'suelto'."""
    gesto = get_object_or_404(
        Gesto,
        id=habito_id,
        usuario=request.user,
        tipo='suelto',
    )

    from .services import TriggersService
    analisis = TriggersService.analizar_patrones_recaida(gesto)
    recomendaciones = TriggersService.generar_recomendaciones(analisis)

    ultimos_triggers = gesto.triggers.all()[:10]

    context = {
        'habito': gesto,
        'analisis': analisis,
        'recomendaciones': recomendaciones,
        'ultimos_triggers': ultimos_triggers
    }

    return render(request, 'diario/habito_analisis_patrones.html', context)

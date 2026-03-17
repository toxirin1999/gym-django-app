
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

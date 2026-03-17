from django.shortcuts import render, get_object_or_404
from django.http import Http404
from .models import EstiramientoPlan
import json


def panel_estiramientos(request):
    planes = EstiramientoPlan.objects.filter(activo=True).order_by("fase")
    return render(request, "estiramientos/panel.html", {"planes": planes})


def iniciar_plan(request, plan_id: int):
    plan = get_object_or_404(EstiramientoPlan, id=plan_id, activo=True)

    pasos = list(
        plan.pasos.select_related("ejercicio").all()
    )
    if not pasos:
        raise Http404("Este plan todavía no tiene pasos.")

    # Datos serializables para JS
    steps = []
    for p in pasos:
        ej = p.ejercicio
        steps.append({
            "name": ej.nombre,
            "duration": int(p.duracion_segundos),
            "note": ej.descripcion_corta or "",
            "muscle": ej.musculo_objetivo or "",
            "image": ej.imagen.url if ej.imagen else "",
        })

    return render(request, "estiramientos/player.html", {
        "plan": plan,
        "steps": json.dumps(steps),  # Convertir a JSON string
        "transition": int(plan.transicion_segundos),
    })

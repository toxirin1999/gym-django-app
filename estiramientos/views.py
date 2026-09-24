from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from entrenos.models import SesionProgramada
from entrenos.services.sesion_movilidad_adaptativa_service import completar_sesion_movilidad
from .models import EstiramientoPlan
import json


def panel_estiramientos(request):
    planes = EstiramientoPlan.objects.filter(activo=True).order_by("fase", "nombre")
    planes_movilidad = planes.filter(
        modalidad=EstiramientoPlan.MODALIDAD_MOVILIDAD,
    ).exclude(fase="CARDIO")
    planes_cardio = planes.filter(
        modalidad=EstiramientoPlan.MODALIDAD_MOVILIDAD, fase="CARDIO",
    )
    planes_estiramientos = planes.filter(
        modalidad=EstiramientoPlan.MODALIDAD_ESTIRAMIENTOS,
    )
    sesion = None
    sesion_id = request.GET.get("sesion_programada_id")
    if request.user.is_authenticated and sesion_id:
        sesion = get_object_or_404(
            SesionProgramada,
            pk=sesion_id,
            cliente__user=request.user,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )

    # Sesión de fuerza de HOY detectada automáticamente (sin necesidad de un
    # ?sesion_programada_id= en la URL), para el checkbox "Contabilizar como
    # sustituto de la sesión de fuerza de hoy" en la tarjeta principal. Solo
    # se calcula cuando no llegamos ya con una sesión explícita por URL, para
    # no interferir con ese flujo ya existente y probado.
    sesion_hoy = None
    if sesion is None and request.user.is_authenticated:
        cliente = getattr(request.user, "cliente_perfil", None)
        if cliente is not None:
            sesion_hoy = SesionProgramada.objects.filter(
                cliente=cliente,
                fecha_prevista=date.today(),
                estado=SesionProgramada.ESTADO_PENDIENTE,
            ).first()

    return render(request, "estiramientos/panel.html", {
        "planes": planes,
        "planes_movilidad": planes_movilidad,
        "planes_cardio": planes_cardio,
        "planes_estiramientos": planes_estiramientos,
        "sesion_programada": sesion,
        "sesion_hoy": sesion_hoy,
    })


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

    sesion = None
    sesion_id = request.GET.get("sesion_programada_id")
    if (
        plan.modalidad == EstiramientoPlan.MODALIDAD_MOVILIDAD
        and request.user.is_authenticated and sesion_id
    ):
        sesion = get_object_or_404(
            SesionProgramada, pk=sesion_id, cliente__user=request.user,
            estado=SesionProgramada.ESTADO_PENDIENTE,
        )
    resolucion = request.GET.get("resolucion", "anadir")
    if resolucion not in {"anadir", "posponer", "sustituir"}:
        resolucion = "anadir"

    return render(request, "estiramientos/player.html", {
        "plan": plan,
        "steps": json.dumps(steps),  # Convertir a JSON string
        "total_steps": len(steps),
        "transition": int(plan.transicion_segundos),
        "sesion_programada": sesion,
        "resolucion": resolucion,
        "fecha_destino": request.GET.get("fecha_destino", ""),
    })


@login_required
@require_POST
def completar_plan(request, plan_id: int):
    plan = get_object_or_404(EstiramientoPlan, pk=plan_id, activo=True)
    try:
        payload = json.loads(request.body or "{}")
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)

    sesion = None
    sesion_id = payload.get("sesion_programada_id")
    if sesion_id:
        sesion = get_object_or_404(
            SesionProgramada, pk=sesion_id, cliente__user=request.user,
        )
    cliente = request.user.cliente_perfil
    try:
        fecha = date.fromisoformat(payload.get("fecha"))
        fecha_destino_raw = payload.get("fecha_destino")
        fecha_destino = date.fromisoformat(fecha_destino_raw) if fecha_destino_raw else None
        registro = completar_sesion_movilidad(
            cliente=cliente,
            plan=plan,
            fecha=fecha,
            duracion_minutos=payload.get("duracion_minutos"),
            rpe=payload.get("rpe"),
            resolucion=payload.get("resolucion"),
            sesion_programada=sesion,
            fecha_destino=fecha_destino,
            idempotency_key=payload.get("idempotency_key"),
        )
    except (TypeError, ValueError) as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse({
        "success": True,
        "sesion_movilidad_id": registro.pk,
        "actividad_id": registro.actividad_id,
    })

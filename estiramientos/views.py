from datetime import date

from django.db.models import Case, IntegerField, Value, When
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.templatetags.static import static
from django.views.decorators.http import require_POST

from entrenos.models import SesionProgramada
from entrenos.services.sesion_movilidad_adaptativa_service import completar_sesion_movilidad
from .models import EstiramientoPlan
import json


# Ilustraciones editoriales del reproductor inmersivo. Son un fallback: una
# imagen que el entrenador haya subido para el ejercicio conserva prioridad.
PLAYER_MOBILITY_IMAGE_FALLBACKS = {
    "CARs de cadera en cuadrupedia": "estiramientos/images/mobility/hip-cars.png",
    "Transición shin box 90/90": "estiramientos/images/mobility/shin-box-9090.png",
    "Adductor rock back": "estiramientos/images/mobility/adductor-rock-back.png",
    "Rodilla a pared para tobillo": "estiramientos/images/mobility/knee-to-wall.png",
    "Elevación activa de puntas y talones": "estiramientos/images/mobility/toe-heel-raises.png",
}


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
    # La portada de recuperación no es una clasificación de la base de
    # datos: es una decisión editorial. Mantenerla explícita evita que un
    # nombre nuevo o un cambio de fase desplace la CTA o las dos sesiones
    # recomendadas que componen la pantalla.
    hero_mobility_plan = (
        planes_movilidad.filter(codigo="mobility-recovery-global").first()
        or planes_movilidad.first()
    )
    featured_codes = ("mobility-hip-ankle", "mobility-thoracic-shoulder")
    featured_mobility_plans = planes_movilidad.filter(codigo__in=featured_codes).order_by(
        Case(
            When(codigo=featured_codes[0], then=Value(0)),
            When(codigo=featured_codes[1], then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
    )
    remaining_mobility_plans = planes_movilidad.exclude(
        codigo__in=("mobility-recovery-global", *featured_codes),
    )
    sesion = None
    sesion_id = request.GET.get("sesion_programada_id")
    resolucion = request.GET.get("resolucion", "anadir")
    if resolucion not in {"anadir", "posponer", "sustituir"}:
        resolucion = "anadir"
    fecha_destino = request.GET.get("fecha_destino", "")
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
        "hero_mobility_plan": hero_mobility_plan,
        "featured_mobility_plans": featured_mobility_plans,
        "remaining_mobility_plans": remaining_mobility_plans,
        "sesion_programada": sesion,
        "sesion_hoy": sesion_hoy,
        # Al salir del reproductor volvemos a este panel con la misma
        # decisión. Sin ello, una sesión aplazada recuperaba visualmente la
        # opción "añadir" y el usuario podía guardar otra intención por
        # accidente.
        "movilidad_resolucion": resolucion,
        "movilidad_fecha_destino": fecha_destino,
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
        fallback_image = PLAYER_MOBILITY_IMAGE_FALLBACKS.get(ej.nombre)
        image_url = (
            ej.imagen.url
            if ej.imagen
            else static(fallback_image) if fallback_image else ""
        )
        steps.append({
            "name": ej.nombre,
            "duration": int(p.duracion_segundos),
            "note": ej.descripcion_corta or "",
            "muscle": ej.musculo_objetivo or "",
            "image": image_url,
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

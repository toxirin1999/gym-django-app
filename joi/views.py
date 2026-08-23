import logging
import uuid

from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@login_required
@require_POST
def marcar_mensaje_leido(request, mensaje_id):
    from joi.services import marcar_leido
    ok = marcar_leido(mensaje_id, request.user)
    from django.core.cache import cache
    cache.delete(f'joi_ctx_{request.user.id}')
    return JsonResponse({'ok': ok})


@login_required
@require_POST
def registrar_mood(request):
    from joi.models import RecuerdoEmocional
    texto = request.POST.get('texto', '').strip()[:300]
    if texto:
        RecuerdoEmocional.objects.create(
            user=request.user,
            contenido=texto,
            contexto='mood_habitacion',
        )
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)


@login_required
def narrativa_joi_view(request):
    from .models import NarrativaActiva, ManualDavid, JoiSintesisLog
    from joi.services_manual_authority import resolver_autoridad_manual

    narrativa = None
    try:
        narrativa = NarrativaActiva.objects.get(
            user=request.user, estado__in=('borrador', 'activa')
        )
    except NarrativaActiva.DoesNotExist:
        pass

    autoridad_manual = resolver_autoridad_manual(request.user)[:8]
    manual_by_id = {
        item.pk: item
        for item in ManualDavid.objects.filter(
            pk__in=[entry['id'] for entry in autoridad_manual],
        )
    }
    manual_activo = [
        manual_by_id[entry['id']]
        for entry in autoridad_manual
        if entry['id'] in manual_by_id
    ]

    ultimo_log = (
        JoiSintesisLog.objects
        .filter(user=request.user)
        .order_by('-creado_en')
        .first()
    )

    from django.core.cache import cache
    cache_key = f'joi_razon_legible_v5_{request.user.id}_{narrativa.version if narrativa else 0}'
    razon_partes = cache.get(cache_key)
    if not razon_partes and narrativa:
        from joi.services import generar_razon_legible
        razon_partes = generar_razon_legible(narrativa, manual_activo, ultimo_log)
        if razon_partes:
            cache.set(cache_key, razon_partes, 60 * 60 * 6)

    # Extraer categorías resumidas del ManualDavid para el rastro técnico
    _PREFIJOS = ['Tema abierto: ', 'Cuando ', 'Si ', 'Al ', 'No ']
    _VERBOS_INICIO = {'esperas', 'asumo', 'asumes', 'priorizamos', 'confundas', 'honrarlo', 'escucharlo'}
    categorias = []
    _vistos = set()
    for e in manual_activo:
        if e.entrada.startswith('Entidad'):
            continue
        label = e.entrada
        for p in _PREFIJOS:
            if label.startswith(p):
                label = label[len(p):]
                break
        # Saltar verbo inicial si procede
        palabras = label.split()
        if palabras and palabras[0].lower().rstrip('.,;') in _VERBOS_INICIO:
            palabras = palabras[1:]
        # Tomar hasta 4 palabras con corte en separadores
        frase = ' '.join(palabras)
        for sep in [',', ';', '—', ':', '.', ' para ', ' pero ', ' versus ', ' sobre ']:
            if sep in frase[:45]:
                frase = frase[:frase.index(sep, 0, 45)].strip()
                break
        # Truncar en frontera de palabra (no a mitad de palabra)
        if len(frase) > 38:
            frase = frase[:38].rsplit(' ', 1)[0]
        label = frase.strip().lower()
        if label and label not in _vistos:
            categorias.append(label)
            _vistos.add(label)

    # Preferir categorías del LLM si están disponibles
    categorias_llm = (razon_partes or {}).get('categorias_llm', [])
    categorias_finales = categorias_llm if categorias_llm else categorias

    return render(request, 'joi/narrativa.html', {
        'narrativa': narrativa,
        'manual_activo': manual_activo,
        'ultimo_log': ultimo_log,
        'razon_partes': razon_partes or {},
        'categorias_hipotesis': categorias_finales,
    })


@login_required
def poda_manual_joi(request):
    from joi.models import ManualDavid
    entradas = ManualDavid.objects.filter(user=request.user, activa=True)
    return render(request, 'joi/manual_poda.html', {'entradas': entradas})


@login_required
def habitacion_joi(request):
    from clientes.models import Cliente
    from .models import MensajeJOI
    from core.daily_decision import DailyDecisionEngine
    from entrenos.models import ActividadRealizada

    cliente = get_object_or_404(Cliente, user=request.user)

    # Si viene desde un popup con id concreto, mostrar ese mensaje
    _msg_id = request.GET.get('mensaje')
    if _msg_id:
        mensaje = MensajeJOI.objects.filter(
            id=_msg_id, user=request.user
        ).first()
    else:
        mensaje = None

    if not mensaje:
        # Mensaje más reciente de los últimos 7 días
        mensaje = (
            MensajeJOI.objects
            .filter(user=request.user,
                    creado_en__gte=timezone.now() - timedelta(days=7))
            .order_by('-creado_en')
            .first()
        )

    # ── Regeneración condicional ──────────────────────────────────
    # Si hay actividad nueva registrada DESPUÉS del último mensaje, JOI
    # actualiza su síntesis. Así el usuario nunca lee "no has entrenado"
    # tras haber completado una sesión.
    regenerado = False
    if mensaje:
        ultima_actividad = (
            ActividadRealizada.objects
            .filter(cliente=cliente, tipo__in=['gym', 'hyrox', 'carrera'])
            .order_by('-fecha', '-id')
            .first()
        )
        hay_actividad_nueva = (
            ultima_actividad is not None
            and ultima_actividad.fecha > mensaje.creado_en.date()
        )
        if hay_actividad_nueva:
            try:
                from joi.services import generar_mensaje_joi
                nuevo = generar_mensaje_joi(cliente, 'apertura_manana', {})
                if nuevo:
                    mensaje    = nuevo
                    regenerado = True
            except Exception as e:
                logger.warning('Regeneración JOI fallida: %s', e)

    if mensaje and not mensaje.leido:
        mensaje.leido = True
        mensaje.save(update_fields=['leido'])


    # NarrativaActiva — para mostrar fragmento y habilitar DialogoNarrativa
    narrativa = None
    try:
        from .models import NarrativaActiva
        narrativa = NarrativaActiva.objects.get(
            user=request.user, estado__in=('borrador', 'activa')
        )
    except Exception:
        pass

    # ── Estado de presencia: SILENCIO / PRESENTE / PROTEGIENDO / OBSERVANDO ─────────
    # Determina la postura de JOI según señales reales del organismo
    from joi.services import determinar_estado_habitacion_joi
    joi_estado, joi_motivo = determinar_estado_habitacion_joi(request.user)

    # Mapeo de motivos a textos humanos
    _motivo_textos = {
        'sin_senales': "No hay señales nuevas que leer ahora.",
        'diario_hoy_sin_lectura': "Hay una entrada de diario reciente, pero todavía no hay lectura formada.",
        'mensaje_joi_hoy': "Hay una lectura activa disponible.",
        'narrativa_activa': "Hay una narrativa activa que sostiene este estado.",
        'rpe_extremo': "La última sesión registró un esfuerzo extremo.",
        'lesion_activa': "Hay una lesión activa que pide bajar el tono.",
        'pulso_protegiendo': "El sistema está en modo protección.",
    }
    joi_texto_motivo = _motivo_textos.get(joi_motivo, "")

    # Visibilidad de mensaje: solo si tiene_mensaje_activo Y joi_estado permite
    tiene_mensaje_activo = mensaje and not mensaje.feedback
    # En SILENCIO, ocultar mensaje incluso si existe (estado 'calla')
    # En PRESENTE/PROTEGIENDO, mostrar si hay mensaje activo
    if joi_estado == 'SILENCIO':
        estado = 'calla'
    else:
        estado = 'habla' if tiene_mensaje_activo else 'calla'

    # ── Señal de sedimento: algo cambió desde la última visita ───────────────
    from django.core.cache import cache as _cache
    last_visit_key = f'joi_hab_lastvisit_{request.user.id}'
    last_visit = _cache.get(last_visit_key)
    _cache.set(last_visit_key, timezone.now(), 60 * 60 * 24 * 30)

    hay_sedimento = False
    if last_visit:
        try:
            from .models import DialogoNarrativa
            if narrativa and narrativa.actualizado_en and narrativa.actualizado_en > last_visit:
                hay_sedimento = True
            if not hay_sedimento:
                hay_sedimento = DialogoNarrativa.objects.filter(
                    user=request.user, procesado=True, procesado_en__gt=last_visit
                ).exists()
        except Exception:
            pass

    # ── Texto de vigilia: cambia con el estado de la relación, no con datos ──
    _ausencia = last_visit is not None and (timezone.now() - last_visit).days > 5
    if narrativa and getattr(narrativa, 'estado', None) == 'borrador':
        texto_vigilia = "Todavía no voy a nombrarlo."
    elif hay_sedimento:
        texto_vigilia = "Algo ha quedado aquí."
    elif _ausencia:
        texto_vigilia = "La habitación siguió aquí."
    elif joi_estado == 'OBSERVANDO':
        texto_vigilia = "Observando aquí."
    else:
        texto_vigilia = "Presente. Observando."

    # ── Retorno discreto (solo en ausencia) ─────────────────────────────────
    entrenos_totales = None
    if _ausencia:
        try:
            from logros.models import PerfilGamificacion
            perfil_gam = PerfilGamificacion.objects.get(cliente=cliente)
            entrenos_totales = perfil_gam.entrenos_totales
        except Exception:
            pass

    # Supervisión epistemológica: una sola memoria, siempre read-only.
    from joi.services_memoria_habitacion import construir_memoria_habitacion
    memoria_revision = construir_memoria_habitacion(
        cliente=cliente,
        as_of=timezone.localdate(),
        requested_id=request.GET.get('memoria'),
    )
    revision_feedback = request.session.pop('joi_revision_feedback', None)

    return render(request, 'joi/habitacion.html', {
        'mensaje':             mensaje,
        'estado':              estado,
        'joi_estado':          joi_estado,
        'joi_motivo':          joi_motivo,
        'joi_texto_motivo':    joi_texto_motivo,
        'regenerado':          regenerado,
        'narrativa':           narrativa,
        'hay_sedimento':       hay_sedimento,
        'texto_vigilia':       texto_vigilia,
        'entrenos_totales':    entrenos_totales,
        'memoria_revision':    memoria_revision,
        'revision_feedback':   revision_feedback,
    })


def _uuid_post(request, field='idempotency_key'):
    try:
        return uuid.UUID(request.POST.get(field, ''))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('solicitud inválida') from exc


@login_required
@require_POST
def revision_memoria(request, manual_id, accion):
    """Aplica una decisión humana y vuelve a la Habitación mediante PRG."""
    from clientes.models import Cliente
    from joi.services_revision_memoria import aplicar_revision_memoria

    try:
        cliente = Cliente.objects.get(user=request.user)
        receipt = aplicar_revision_memoria(
            cliente=cliente,
            actor=request.user,
            manual_id=manual_id,
            accion=accion,
            expected_fingerprint=request.POST.get('expected_fingerprint', ''),
            idempotency_key=_uuid_post(request),
            as_of=timezone.localdate(),
        )
    except (Cliente.DoesNotExist, ValueError):
        messages.info(request, 'No se pudo aplicar esa revisión.')
        return redirect('joi:joi_habitacion')

    request.session['joi_revision_undo_operation'] = receipt.pk
    request.session['joi_revision_feedback'] = {
        'texto': 'Revisión guardada.',
        'undo_operation_id': receipt.pk,
        'undo_idempotency_key': str(uuid.uuid4()),
    }
    return redirect('joi:joi_habitacion')


@login_required
@require_POST
def deshacer_revision_memoria_view(request, operacion_id):
    """Deshace únicamente el recibo propio ofrecido por el último PRG."""
    from clientes.models import Cliente
    from joi.services_revision_memoria import deshacer_revision_memoria

    if request.session.get('joi_revision_undo_operation') != operacion_id:
        messages.info(request, 'No se pudo deshacer esa revisión.')
        return redirect('joi:joi_habitacion')
    try:
        cliente = Cliente.objects.get(user=request.user)
        deshacer_revision_memoria(
            cliente=cliente,
            actor=request.user,
            operacion_id=operacion_id,
            idempotency_key=_uuid_post(request),
            as_of=timezone.localdate(),
        )
    except (Cliente.DoesNotExist, ValueError):
        messages.info(request, 'No se pudo deshacer esa revisión.')
        return redirect('joi:joi_habitacion')

    request.session.pop('joi_revision_undo_operation', None)
    request.session['joi_revision_feedback'] = {'texto': 'Revisión deshecha.'}
    return redirect('joi:joi_habitacion')


@login_required
@require_POST
def feedback_joi(request, mensaje_id):
    from .models import MensajeJOI
    from django.core.cache import cache

    mensaje = get_object_or_404(MensajeJOI, id=mensaje_id, user=request.user)
    feedback = request.POST.get('feedback')
    if feedback in ('clavado', 'equivocado'):
        mensaje.feedback = feedback
        mensaje.save(update_fields=['feedback'])
        cache.delete(f'joi_ctx_{request.user.id}')

        if feedback == 'equivocado':
            from joi.services import generar_entrada_manual_desde_error
            generar_entrada_manual_desde_error(mensaje)

        respuesta = (
            'Seguiré mirando.'
            if feedback == 'clavado'
            else 'He interpretado mal tu señal. Reajustando mi lente.'
        )
        return JsonResponse({'ok': True, 'respuesta': respuesta})
    return JsonResponse({'ok': False}, status=400)


@login_required
@require_POST
def crear_dialogo_narrativa(request):
    """
    El usuario deja algo en la habitación sobre la narrativa de JOI.
    No hay confirmación inmediata. El procesamiento ocurre ≥4h después
    en ciclo_sintesis_joi(). La respuesta, si existe, llega como MensajeJOI.
    """
    from .models import NarrativaActiva, DialogoNarrativa
    texto = request.POST.get('texto', '').strip()[:500]
    if not texto:
        return JsonResponse({'ok': False}, status=400)
    try:
        narrativa = NarrativaActiva.objects.get(user=request.user)
        DialogoNarrativa.objects.create(
            user=request.user,
            narrativa=narrativa,
            texto_usuario=texto,
        )
        return JsonResponse({'ok': True})
    except NarrativaActiva.DoesNotExist:
        return JsonResponse({'ok': False, 'motivo': 'sin_narrativa'}, status=404)


@login_required
@require_POST
def feedback_estado_encaje(request):
    """
    Registra si el estado actual de JOI (SILENCIO, OBSERVANDO, PRESENTE, PROTEGIENDO)
    encaja con la experiencia del usuario.

    POST data:
    - estado: str (SILENCIO, OBSERVANDO, PRESENTE, PROTEGIENDO)
    - motivo: str (sin_senales, diario_hoy_sin_lectura, etc.)
    - feedback: str ('encaja' o 'no_encaja')

    Respuesta:
    - {'ok': true, 'saved': true} si se guardó
    - {'ok': false} si validación falla
    """
    import json
    from django.utils import timezone
    from .models import EstadoFeedback

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False}, status=400)

    estado = data.get('estado', '').strip()
    motivo = data.get('motivo', '').strip()
    feedback = data.get('feedback', '').strip()

    # Validación
    estados_validos = {'SILENCIO', 'OBSERVANDO', 'PRESENTE', 'PROTEGIENDO'}
    feedback_valido = {'encaja', 'no_encaja'}

    if not estado or estado not in estados_validos:
        return JsonResponse({'ok': False, 'error': 'estado_invalido'}, status=400)
    if not motivo:
        return JsonResponse({'ok': False, 'error': 'motivo_requerido'}, status=400)
    if not feedback or feedback not in feedback_valido:
        return JsonResponse({'ok': False, 'error': 'feedback_invalido'}, status=400)

    hoy = timezone.now().date()

    # Upsert: actualizar si existe, crear si no
    obj, created = EstadoFeedback.objects.update_or_create(
        usuario=request.user,
        fecha=hoy,
        estado=estado,
        motivo=motivo,
        defaults={'feedback': feedback}
    )

    logger.info(
        f"[JOI Feedback] {request.user.username}: {estado}/{motivo} = {feedback} "
        f"({'created' if created else 'updated'})"
    )

    return JsonResponse({'ok': True, 'saved': True})


@login_required
@require_http_methods(["GET"])
def pulso_actual_api(request):
    """
    Endpoint AJAX que devuelve el estado actual de JOI (Pulso).
    Usado por app viva para actualizar JOI sin recargar página.

    Respuesta:
    {
        'estado': 'SILENCIO' | 'OBSERVANDO' | 'PRESENTE' | 'PROTEGIENDO',
        'motivo': 'sin_senales' | 'diario_hoy_sin_lectura' | ...,
        'texto_motivo': 'descripción legible',
        'mensaje_activo': bool,
    }
    """
    from joi.services import determinar_estado_habitacion_joi
    from .models import MensajeJOI
    from django.utils import timezone

    joi_estado, joi_motivo = determinar_estado_habitacion_joi(request.user)

    # Mapeo de motivos a textos humanos (mismo que en habitacion_joi)
    motivo_textos = {
        'sin_senales': "No hay señales nuevas que leer ahora.",
        'diario_hoy_sin_lectura': "Hay una entrada de diario reciente, pero todavía no hay lectura formada.",
        'mensaje_joi_hoy': "Hay una lectura activa disponible.",
        'narrativa_activa': "Hay una narrativa activa que sostiene este estado.",
        'rpe_extremo': "La última sesión registró un esfuerzo extremo.",
        'lesion_activa': "Hay una lesión activa que pide bajar el tono.",
        'pulso_protegiendo': "El sistema está en modo protección.",
    }
    joi_texto_motivo = motivo_textos.get(joi_motivo, "")

    # Verificar si hay mensaje activo del día
    hoy = timezone.now().date()
    mensaje_hoy = MensajeJOI.objects.filter(
        user=request.user,
        creado_en__date=hoy,
        feedback__isnull=True,
    ).order_by('-creado_en').first()
    tiene_mensaje_activo = mensaje_hoy is not None

    return JsonResponse({
        'estado': joi_estado,
        'motivo': joi_motivo,
        'texto_motivo': joi_texto_motivo,
        'mensaje_activo': tiene_mensaje_activo,
    })

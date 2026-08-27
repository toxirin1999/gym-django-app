from celery import shared_task
import datetime
import logging
from django.utils import timezone


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def generar_resultado_intervencion_joi(self, intervencion_id):
    """Publica una vez la lectura JOI; la llamada al modelo ocurre fuera del lock."""
    from django.db import transaction
    from django.utils import timezone
    from datetime import timedelta
    from entrenos.models import IntervencionPlan
    from joi.services import generar_mensaje_joi

    with transaction.atomic():
        iv = IntervencionPlan.objects.select_for_update().select_related('sugerencia', 'cliente__user').get(pk=intervencion_id)
        snap = dict(iv.sugerencia.contrato_snapshot or {})
        evaluacion = dict(snap.get('evaluacion') or {})
        if not evaluacion.get('resultado'):
            return {'omitido': 'sin_evaluacion'}
        joi = dict(evaluacion.get('joi') or {})
        if joi.get('mensaje_id'):
            return {'mensaje_id': joi['mensaje_id'], 'duplicado': True}
        if joi.get('estado') == 'generando':
            started_at = joi.get('started_at')
            try:
                inicio = timezone.datetime.fromisoformat(started_at)
                if timezone.is_naive(inicio):
                    inicio = timezone.make_aware(inicio)
            except (TypeError, ValueError):
                inicio = None
            if inicio and timezone.now() - inicio < timedelta(minutes=15):
                return {'omitido': 'en_progreso'}
        joi.update({'estado': 'generando', 'started_at': timezone.now().isoformat()})
        evaluacion['joi'] = joi; snap['evaluacion'] = evaluacion
        iv.sugerencia.contrato_snapshot = snap
        iv.sugerencia.save(update_fields=['contrato_snapshot'])

    datos = {k: evaluacion.get(k) for k in (
        'resultado', 'sesiones_completadas', 'sesiones_esenciales',
        'porcentaje_esenciales', 'ventana',
    )}
    datos['evaluacion_v1'] = snap.get('evaluacion_v1')
    mensaje = generar_mensaje_joi(iv.cliente, 'resultado_intervencion', datos)

    with transaction.atomic():
        sugerencia = type(iv.sugerencia).objects.select_for_update().get(pk=iv.sugerencia_id)
        snap = dict(sugerencia.contrato_snapshot or {})
        evaluacion = dict(snap.get('evaluacion') or {})
        joi = dict(evaluacion.get('joi') or {})
        if mensaje:
            joi.update({'estado': 'publicado', 'mensaje_id': mensaje.pk, 'started_at': None})
        else:
            joi.update({'estado': 'pendiente', 'started_at': None})
        evaluacion['joi'] = joi; snap['evaluacion'] = evaluacion
        sugerencia.contrato_snapshot = snap
        sugerencia.save(update_fields=['contrato_snapshot'])
    return {'mensaje_id': mensaje.pk if mensaje else None}


@shared_task(bind=True, max_retries=2)
def generar_apertura_manana(self):
    """
    Genera un mensaje JOI de apertura matutina para cada usuario activo.
    Se programa via Celery Beat cada día a las 07:30 (hora México/Madrid).
    Solo genera si el usuario no tiene ya un mensaje sin leer del día de hoy.
    """
    from clientes.models import Cliente
    from joi.services_eventos_entrenador import resolver_apertura_diaria_entrenador

    hoy = timezone.localdate()
    generados = 0
    errores = 0

    for cliente in Cliente.objects.select_related('user').all():
        try:
            mensaje = resolver_apertura_diaria_entrenador(cliente)
            if mensaje is not None:
                generados += 1
        except Exception:
            errores += 1

    return {'generados': generados, 'errores': errores, 'fecha': str(hoy)}


@shared_task(bind=True, max_retries=2)
def verificar_cuenta_regresiva_hyrox(self):
    """
    Comprueba si algún usuario está a 30, 14 o 7 días de su carrera Hyrox
    y genera un mensaje JOI de cuenta regresiva.
    """
    import datetime
    from hyrox.models import ContratoCampanaHyrox
    from hyrox.campaign_authority import (
        objetivo_autorizado_campana,
        resolver_autoridad_campana,
    )
    from joi.services import generar_mensaje_joi
    from joi.models import MensajeJOI

    hoy = datetime.date.today()
    hitos = {30, 14, 7}
    generados = 0

    contratos = ContratoCampanaHyrox.objects.filter(
        estado='activa', objetivo__fecha_evento__gte=hoy
    ).select_related('cliente__user', 'objetivo')
    for contrato in contratos:
        autoridad = resolver_autoridad_campana(contrato.cliente, hoy)
        if autoridad.get('contrato_id') != contrato.pk:
            continue
        objetivo = objetivo_autorizado_campana(
            contrato.cliente, accion='joi_hyrox', fecha=hoy
        )
        if objetivo is None or objetivo.pk != contrato.objetivo_id:
            continue
        dias_restantes = (objetivo.fecha_evento - hoy).days
        if dias_restantes not in hitos:
            continue
        cliente = objetivo.cliente
        ya_enviado = MensajeJOI.objects.filter(
            user=cliente.user,
            trigger='hyrox_cuenta_regresiva',
            contexto__dias=dias_restantes,
        ).exists()
        if ya_enviado:
            continue
        try:
            generar_mensaje_joi(cliente, 'hyrox_cuenta_regresiva', {'dias': dias_restantes})
            generados += 1
        except Exception:
            pass

    return {'generados': generados, 'fecha': str(hoy)}


@shared_task(bind=True, max_retries=2)
def generar_resumen_semanal_joi(self):
    """Genera el lunes la revisión canónica de la semana anterior."""
    from clientes.models import Cliente
    from diario.services.lectura_semanal import buscar_revision_semanal, generar_revision_semanal

    hoy = timezone.localdate()
    if hoy.weekday() != 0:  # Solo lunes
        return {'omitido': 'no es lunes', 'fecha': str(hoy)}

    inicio = hoy - datetime.timedelta(days=7)
    fin = hoy - datetime.timedelta(days=1)
    generados = 0
    for cliente in Cliente.objects.select_related('user').all():
        try:
            clave = f'{inicio.isoformat()}_{fin.isoformat()}'
            if buscar_revision_semanal(cliente.user, clave):
                continue
            mensaje = generar_revision_semanal(cliente, inicio=inicio, fin=fin)
            if mensaje is not None:
                generados += 1
        except Exception:
            logger.exception('Falló la tarea de revisión semanal para user=%s', cliente.user_id)

    return {'generados': generados, 'fecha': str(hoy)}


@shared_task(bind=True, max_retries=2)
def verificar_ausencia_hyrox(self):
    """
    Detecta usuarios con objetivo Hyrox activo que llevan 7+ días sin completar
    una HyroxSession y genera un mensaje JOI de ausencia.
    Se programa via Celery Beat cada día a las 09:00.
    Solo genera si no hay ya un mensaje de ausencia hyrox en las últimas 48h.
    """
    import datetime
    from hyrox.models import ContratoCampanaHyrox, HyroxSession
    from hyrox.campaign_authority import (
        objetivo_autorizado_campana,
        resolver_autoridad_campana,
    )
    from joi.services import generar_mensaje_joi
    from joi.models import MensajeJOI

    hoy = datetime.date.today()
    umbral_ausencia = hoy - datetime.timedelta(days=7)
    hace_48h = datetime.datetime.now() - datetime.timedelta(hours=48)
    generados = 0

    contratos = ContratoCampanaHyrox.objects.filter(
        estado='activa'
    ).select_related('cliente__user', 'objetivo')
    for contrato in contratos:
        autoridad = resolver_autoridad_campana(contrato.cliente, hoy)
        if autoridad.get('contrato_id') != contrato.pk:
            continue
        objetivo = objetivo_autorizado_campana(
            contrato.cliente, accion='joi_hyrox', fecha=hoy
        )
        if objetivo is None or objetivo.pk != contrato.objetivo_id:
            continue
        cliente = objetivo.cliente

        # Un objetivo recién creado no ha tenido ni la oportunidad de acumular
        # 7 días de "ausencia" — antes, sin ultima_sesion (None), el chequeo de
        # abajo no se ejecutaba y se generaba igualmente un mensaje de "llevas
        # 7 días sin entrenar" el día después de crear el objetivo.
        if objetivo.fecha_creacion.date() > umbral_ausencia:
            continue

        ultima_sesion = HyroxSession.objects.filter(
            objective=objetivo, estado='completado'
        ).order_by('-fecha').first()

        dias_sin_sesion = (hoy - ultima_sesion.fecha).days if ultima_sesion else None
        if ultima_sesion and ultima_sesion.fecha > umbral_ausencia:
            continue

        ya_enviado = MensajeJOI.objects.filter(
            user=cliente.user,
            trigger='hyrox_ausencia',
            creado_en__gte=hace_48h,
        ).exists()
        if ya_enviado:
            continue

        try:
            generar_mensaje_joi(cliente, 'hyrox_ausencia', {
                'dias_sin_sesion': dias_sin_sesion or 7,
            })
            generados += 1
        except Exception:
            pass

    return {'generados': generados, 'fecha': str(hoy)}


@shared_task(bind=True, max_retries=2)
def ciclo_sintesis_joi(self):
    """
    JOI en su propio tiempo — Modelo C (Híbrido).

    Cada ejecución tiene dos modos independientes:

    MODO REVISIÓN (siempre corre, sin generar mensaje):
    - Evalúa hipótesis del ManualDavid contra contexto actual
    - Actualiza confianza/estado de cada entrada
    - Reescribe NarrativaActiva si hay hipótesis suficientes

    MODO GENERACIÓN (solo si hay trigger, decide LLM):
    - Trigger 1: >48h desde el último MensajeJOI
    - Trigger 2: actividad nueva (gym/hyrox/carrera) desde el último mensaje
    - Trigger 3: entrada de diario nueva desde el último mensaje
    - Si trigger activo: LLM recibe contexto completo y decide hablar o [SILENCE]

    Programar via Celery Beat cada 4 horas.
    """
    from clientes.models import Cliente
    from joi.models import MensajeJOI, NarrativaActiva
    from joi.services import (generar_sintesis_joi, revisar_manual_david,
                               registrar_sintesis_log,
                               _hay_contexto_para_revision, _revision_antigua,
                               _actualizar_narrativa_activa, construir_contexto,
                               procesar_dialogo_narrativa)
    from entrenos.models import ActividadRealizada

    ahora = datetime.datetime.now()
    generados = 0
    silenciados = 0
    saltados = 0
    revisiones = 0
    dialogos_procesados = 0

    for cliente in Cliente.objects.select_related('user').all():
        try:
            # ── DIÁLOGOS PENDIENTES: procesar antes que revisión ─────────────
            try:
                resultado_dialogos = procesar_dialogo_narrativa(cliente)
                dialogos_procesados += resultado_dialogos.get('procesados', 0)
            except Exception:
                pass

            # ── MODO REVISIÓN: solo si hay contexto nuevo o revisión antigua ──
            try:
                ultima_revision = None
                try:
                    narrativa = NarrativaActiva.objects.get(user=cliente.user)
                    ultima_revision = narrativa.ultima_revision_manual
                except NarrativaActiva.DoesNotExist:
                    pass

                debe_revisar = (
                    _revision_antigua(ultima_revision, dias=7)
                    or _hay_contexto_para_revision(cliente, ultima_revision)
                )

                if debe_revisar:
                    narrativa_existia = NarrativaActiva.objects.filter(
                        user=cliente.user
                    ).exists()
                    capas_antes = {}
                    try:
                        n = NarrativaActiva.objects.get(user=cliente.user)
                        capas_antes = {
                            'capa_corta': n.capa_corta or '',
                            'capa_media': n.capa_media or '',
                            'capa_larga': n.capa_larga or '',
                        }
                    except NarrativaActiva.DoesNotExist:
                        pass

                    resultado_revision = revisar_manual_david(cliente)
                    revisiones += 1

                    narrativa_existe = NarrativaActiva.objects.filter(
                        user=cliente.user
                    ).exists()
                    if resultado_revision.get('cambio_significativo') or not narrativa_existe:
                        try:
                            ctx = construir_contexto(cliente)
                            _actualizar_narrativa_activa(
                                cliente, ctx,
                                cambio_significativo=True,
                            )
                        except Exception:
                            pass

                    try:
                        n = NarrativaActiva.objects.get(user=cliente.user)
                        capas_despues = {
                            'capa_corta': n.capa_corta or '',
                            'capa_media': n.capa_media or '',
                            'capa_larga': n.capa_larga or '',
                        }
                    except NarrativaActiva.DoesNotExist:
                        capas_despues = {}

                    try:
                        registrar_sintesis_log(
                            cliente=cliente,
                            tipo='auto',
                            resultado_revision=resultado_revision,
                            narrativa_existia=narrativa_existia,
                            capas_antes=capas_antes,
                            capas_despues=capas_despues,
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            ultimo_msg = (
                MensajeJOI.objects
                .filter(user=cliente.user)
                .order_by('-creado_en')
                .first()
            )

            # No interrumpir si hay un mensaje de síntesis pendiente de leer
            if ultimo_msg and not ultimo_msg.leido and ultimo_msg.trigger == 'sintesis_joi':
                saltados += 1
                continue

            ultimo_ts = ultimo_msg.creado_en if ultimo_msg else None

            # ── FILTRO TRIGGER (sin LLM) ──────────────────────────────────
            trigger_activo = False

            # Trigger 1: >48h de silencio
            if not ultimo_ts:
                trigger_activo = True
            else:
                ts_naive = ultimo_ts.replace(tzinfo=None)
                if (ahora - ts_naive).total_seconds() > 48 * 3600:
                    trigger_activo = True

            # Trigger 2: nueva actividad desde el último mensaje
            if not trigger_activo and ultimo_ts:
                if ActividadRealizada.objects.filter(
                    cliente=cliente,
                    tipo__in=['gym', 'hyrox', 'carrera'],
                    fecha__gte=ultimo_ts.date(),
                ).exists():
                    trigger_activo = True

            # Trigger 3: nueva entrada de diario desde el último mensaje
            if not trigger_activo and ultimo_ts:
                try:
                    from diario.models import ProsocheDiario, ReflexionLibre
                    limite_fecha = ultimo_ts.date() if hasattr(ultimo_ts, 'date') else ultimo_ts
                    if (
                        ProsocheDiario.objects
                        .filter(prosoche_mes__usuario=cliente.user,
                                fecha__gte=limite_fecha)
                        .exists()
                        or
                        ReflexionLibre.objects
                        .filter(usuario=cliente.user, fecha__gte=ultimo_ts)
                        .exists()
                    ):
                        trigger_activo = True
                except Exception:
                    pass

            if not trigger_activo:
                saltados += 1
                continue

            # ── MODO GENERACIÓN: LLM decide hablar o [SILENCE] ────────────
            resultado = generar_sintesis_joi(cliente)
            if resultado:
                generados += 1
            else:
                silenciados += 1

        except Exception:
            pass

    return {
        'generados':            generados,
        'silenciados':          silenciados,
        'saltados':             saltados,
        'revisiones':           revisiones,
        'dialogos_procesados':  dialogos_procesados,
        'fecha':                str(ahora.date()),
    }


@shared_task(bind=True, max_retries=2)
def generar_poda_mensual(self):
    """
    El 1 de cada mes, JOI invita al usuario a revisar el Manual de David.
    Solo genera el mensaje si hay entradas activas en el manual.
    """
    from clientes.models import Cliente
    from joi.models import MensajeJOI
    from joi.services import generar_mensaje_joi
    from joi.services_manual_authority import resolver_autoridad_manual

    hoy = datetime.date.today()
    generados = 0

    for cliente in Cliente.objects.select_related('user').all():
        try:
            entradas = [
                item['entrada']
                for item in resolver_autoridad_manual(cliente.user, as_of=hoy)
            ]
            if not entradas:
                continue

            ya_enviado = MensajeJOI.objects.filter(
                user=cliente.user,
                trigger='poda_manual',
                creado_en__year=hoy.year,
                creado_en__month=hoy.month,
            ).exists()
            if ya_enviado:
                continue

            generar_mensaje_joi(cliente, 'poda_manual', {'entradas': entradas})
            generados += 1
        except Exception:
            pass

    return {'generados': generados, 'fecha': str(hoy)}


@shared_task(bind=True, max_retries=2)
def generar_lectura_plan_async(self, cliente_id):
    """
    Genera el mensaje JOI de lectura del plan para un cliente concreto.

    Disparado de forma asíncrona (.delay) desde joi.services.generar_lectura_plan
    cuando el último mensaje tiene más de 8h — nunca se genera de forma síncrona
    dentro de un request de dashboard (una llamada a Haiku ahí bloqueaba la
    carga, especialmente notorio en la primera apertura del día).
    """
    from clientes.models import Cliente
    from joi.services import generar_mensaje_joi

    try:
        cliente = Cliente.objects.get(id=cliente_id)
        generar_mensaje_joi(cliente, 'lectura_plan')
    except Exception:
        pass

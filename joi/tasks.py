from celery import shared_task
import datetime


@shared_task(bind=True, max_retries=2)
def generar_apertura_manana(self):
    """
    Genera un mensaje JOI de apertura matutina para cada usuario activo.
    Se programa via Celery Beat cada día a las 07:30 (hora México/Madrid).
    Solo genera si el usuario no tiene ya un mensaje sin leer del día de hoy.
    """
    from datetime import date
    from django.contrib.auth.models import User
    from joi.models import MensajeJOI
    from joi.services import generar_mensaje_joi
    from clientes.models import Cliente

    hoy = date.today()
    generados = 0
    errores = 0

    for cliente in Cliente.objects.select_related('user').all():
        try:
            ya_tiene = MensajeJOI.objects.filter(
                user=cliente.user,
                trigger='apertura_manana',
                creado_en__date=hoy,
            ).exists()
            if ya_tiene:
                continue

            generar_mensaje_joi(cliente, 'apertura_manana')
            generados += 1
        except Exception as e:
            errores += 1

    return {'generados': generados, 'errores': errores, 'fecha': str(hoy)}


@shared_task(bind=True, max_retries=2)
def verificar_cuenta_regresiva_hyrox(self):
    """
    Comprueba si algún usuario está a 30, 14 o 7 días de su carrera Hyrox
    y genera un mensaje JOI de cuenta regresiva.
    """
    import datetime
    from clientes.models import Cliente
    from hyrox.models import HyroxObjective
    from joi.services import generar_mensaje_joi
    from joi.models import MensajeJOI

    hoy = datetime.date.today()
    hitos = {30, 14, 7}
    generados = 0

    for objetivo in HyroxObjective.objects.filter(estado='activo', fecha_evento__gte=hoy):
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
    """
    Cada lunes genera un mensaje JOI de resumen de la semana anterior
    usando get_resumen_semanal_gym. Solo genera si no hay ya uno del día.
    """
    import datetime
    from clientes.models import Cliente
    from joi.models import MensajeJOI
    from joi.services import generar_mensaje_joi
    from entrenos.services.resumen_semanal_service import get_resumen_semanal_gym
    from django.db.models import Avg

    hoy = datetime.date.today()
    if hoy.weekday() != 0:  # Solo lunes
        return {'omitido': 'no es lunes', 'fecha': str(hoy)}

    generados = 0
    for cliente in Cliente.objects.select_related('user').all():
        try:
            ya_tiene = MensajeJOI.objects.filter(
                user=cliente.user,
                trigger='resumen_semanal',
                creado_en__date=hoy,
            ).exists()
            if ya_tiene:
                continue

            items = get_resumen_semanal_gym(cliente)
            if not items:
                continue

            # Extraer datos estructurados de los items
            sesiones = next((i['texto'] for i in items if i['tipo'] == 'sesiones'), '')
            num_sesiones = 0
            volumen_kg = 0
            if sesiones:
                import re
                m = re.search(r'(\d+) sesion', sesiones)
                if m:
                    num_sesiones = int(m.group(1))
                m2 = re.search(r'([\d,]+) kg', sesiones)
                if m2:
                    volumen_kg = float(m2.group(1).replace(',', ''))

            prs = [i['texto'].replace('Nuevo PR en ', '').split(' —')[0]
                   for i in items if i['tipo'] == 'record']

            rpe_item = next((i for i in items if i['tipo'] == 'rpe'), None)
            rpe_medio = None
            if rpe_item:
                m = re.search(r'RPE medio ([\d.]+)', rpe_item['texto'])
                if m:
                    rpe_medio = float(m.group(1))

            tecnica_ok = any(
                i['tipo'] == 'tecnica' and 'limpia' in i['texto']
                for i in items
            )

            molestias = []
            mol_item = next((i for i in items if i['tipo'] == 'molestia'), None)
            if mol_item:
                m = re.search(r'en (.+?) —', mol_item['texto'])
                if m:
                    molestias = [z.strip() for z in m.group(1).split(',')]

            energia_media = None
            en_item = next((i for i in items if i['tipo'] == 'energia'), None)
            if en_item:
                m = re.search(r'media: ([\d.]+)', en_item['texto'])
                if m:
                    energia_media = float(m.group(1))

            decisiones = [
                {'ejercicio': i.get('texto', '').split(':')[0],
                 'accion': i.get('accion', '')}
                for i in items if i['tipo'] in ('decision', 'progresion')
            ][:3]

            hyrox_sesiones = 0
            try:
                from hyrox.models import HyroxObjective, HyroxSession
                objetivo = HyroxObjective.objects.filter(
                    cliente=cliente, estado='activo'
                ).first()
                if objetivo:
                    lunes = hoy - datetime.timedelta(days=7)
                    hyrox_sesiones = HyroxSession.objects.filter(
                        objective=objetivo,
                        estado='completado',
                        fecha__range=(lunes, hoy - datetime.timedelta(days=1)),
                    ).count()
            except Exception:
                pass

            generar_mensaje_joi(cliente, 'resumen_semanal', {
                'sesiones':      num_sesiones,
                'volumen_kg':    volumen_kg,
                'prs':           prs,
                'rpe_medio':     rpe_medio,
                'decisiones':    decisiones,
                'tecnica_ok':    tecnica_ok,
                'molestias':     molestias,
                'energia_media': energia_media,
                'hyrox_sesiones': hyrox_sesiones,
            })
            generados += 1
        except Exception:
            pass

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
    from hyrox.models import HyroxObjective, HyroxSession
    from joi.services import generar_mensaje_joi
    from joi.models import MensajeJOI

    hoy = datetime.date.today()
    umbral_ausencia = hoy - datetime.timedelta(days=7)
    hace_48h = datetime.datetime.now() - datetime.timedelta(hours=48)
    generados = 0

    for objetivo in HyroxObjective.objects.filter(estado='activo').select_related('cliente__user'):
        cliente = objetivo.cliente
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

    1. Filtro de trigger (sin coste LLM):
       - Han pasado >48h desde el último MensajeJOI, O
       - Hay actividad nueva (gym/hyrox/carrera) desde el último mensaje, O
       - Hay entrada de diario nueva desde el último mensaje.
    2. Si hay trigger: LLM recibe el contexto completo y decide hablar o [SILENCE].

    Programar via Celery Beat cada 4 horas.
    """
    from clientes.models import Cliente
    from joi.models import MensajeJOI
    from joi.services import generar_sintesis_joi
    from entrenos.models import ActividadRealizada

    ahora = datetime.datetime.now()
    generados = 0
    silenciados = 0
    saltados = 0

    for cliente in Cliente.objects.select_related('user').all():
        try:
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
                        # Journaling Prosoche (AM o PM) escrito después del último mensaje
                        ProsocheDiario.objects
                        .filter(prosoche_mes__usuario=cliente.user,
                                fecha__gte=limite_fecha)
                        .exists()
                        or
                        # Reflexión libre (Logos)
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

            # ── LLM decide: habla o [SILENCE] ─────────────────────────────
            resultado = generar_sintesis_joi(cliente)
            if resultado:
                generados += 1
            else:
                silenciados += 1

        except Exception:
            pass

    return {
        'generados':   generados,
        'silenciados': silenciados,
        'saltados':    saltados,
        'fecha':       str(ahora.date()),
    }


@shared_task(bind=True, max_retries=2)
def generar_poda_mensual(self):
    """
    El 1 de cada mes, JOI invita al usuario a revisar el Manual de David.
    Solo genera el mensaje si hay entradas activas en el manual.
    """
    from clientes.models import Cliente
    from joi.models import MensajeJOI, ManualDavid
    from joi.services import generar_mensaje_joi

    hoy = datetime.date.today()
    generados = 0

    for cliente in Cliente.objects.select_related('user').all():
        try:
            entradas = list(
                ManualDavid.objects
                .filter(user=cliente.user, activa=True)
                .values_list('entrada', flat=True)
            )
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

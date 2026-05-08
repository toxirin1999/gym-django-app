from celery import shared_task


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

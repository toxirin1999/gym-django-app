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

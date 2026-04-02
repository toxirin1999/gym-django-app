from celery import shared_task


@shared_task
def tarea_analisis_semanal_nutricional():
    """
    Analiza el progreso de todos los clientes con perfil nutricional
    y ajusta los targets si es necesario.
    Se ejecuta cada lunes a las 7:00.
    """
    from clientes.models import Cliente
    from .services import analisis_semanal_pas

    clientes = Cliente.objects.filter(
        perfil_nutricional__isnull=False,
        membresia_activa=True,
    )

    procesados = 0
    for cliente in clientes:
        try:
            analisis_semanal_pas(cliente)
            procesados += 1
        except Exception as e:
            pass  # log en producción

    return f"PAS completado: {procesados}/{clientes.count()} clientes procesados."

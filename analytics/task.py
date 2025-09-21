# Si usas Celery, en tasks.py
from celery import shared_task
from analytics.ia_modelos_predictivos import ModelosPredictivosIA
from clientes.models import Cliente


@shared_task
def entrenar_modelos_ia_periodico():
    """Entrena modelos de IA periódicamente"""
    clientes = Cliente.objects.all()
    for cliente in clientes:
        modelos_ia = ModelosPredictivosIA(cliente)
        modelos_ia.entrenar_modelos_rendimiento()
    return f"Modelos entrenados para {clientes.count()} clientes"

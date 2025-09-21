# Archivo: entrenos/urls_api.py - URLs PARA LA API

from django.urls import path
from .api import (
    ImportarEntrenamientoAPI,
    ListarEntrenamientosAPI,
    EstadisticasAPI,
    ClientesAPI,
    webhook_liftin,
    health_check
)

app_name = 'api_liftin'

urlpatterns = [
    # Health check
    path('health/', health_check, name='health_check'),

    # Endpoints principales
    path('entrenamientos/', ImportarEntrenamientoAPI.as_view(), name='importar_entrenamiento'),
    path('entrenamientos/lista/', ListarEntrenamientosAPI.as_view(), name='listar_entrenamientos'),
    path('estadisticas/', EstadisticasAPI.as_view(), name='estadisticas'),
    path('clientes/', ClientesAPI.as_view(), name='clientes'),

    # Webhook para integración automática futura
    path('webhook/', webhook_liftin, name='webhook_liftin'),
]

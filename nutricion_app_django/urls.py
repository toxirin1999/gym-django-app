from django.urls import path
from . import views

app_name = 'nutricion_app_django'

urlpatterns = [
    # Vista principal de la pirámide
    path('', views.piramide_principal, name='piramide_principal'),

    # Configuración de perfil
    path('perfil/', views.configurar_perfil, name='configurar_perfil'),
    path('niveles/', views.vista_lista_niveles, name='vista_lista_niveles'),
    # Niveles de la pirámide
    path('nivel1/', views.nivel1_balance, name='nivel1_balance'),
    path('nivel2/', views.nivel2_macros, name='nivel2_macros'),
    path('nivel-3-micronutrientes/', views.nivel3_micros, name='nivel3_micros'),
    path('nivel-4-timing/', views.nivel4_timing, name='nivel4_timing'),
    path('nivel-5-suplementos/', views.nivel5_suplementos, name='nivel5_suplementos'),

    # Seguimiento
    path('seguimiento-peso/', views.seguimiento_peso, name='seguimiento_peso'),

    # Dashboard completo
    path('dashboard/', views.dashboard_completo, name='dashboard_completo'),

    # AJAX endpoints
    path('ajax/calcular-preview/', views.ajax_calcular_preview, name='ajax_calcular_preview'),
]

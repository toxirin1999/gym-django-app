from django.urls import path
from . import views

app_name = 'nutricion_app_django'

urlpatterns = [
    # Módulo nutricional científico
    path('onboarding/', views.onboarding_nutricional, name='onboarding_nutricional'),
    path('mi-nutricion/', views.dashboard_nutricional, name='dashboard_nutricional'),
    path('recalcular/', views.recalcular_perfil, name='recalcular_perfil'),

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

    # Calculadora de bloques
    path('bloques/', views.calculadora_bloques, name='calculadora_bloques'),

    # Informe semanal PAS
    path('informe/', views.informe_semanal, name='informe_semanal'),

    # Monitor de progreso + recuperación
    path('progreso/', views.monitor_progreso, name='monitor_progreso'),

    # Manifiesto del atleta híbrido
    path('manifiesto/', views.manifiesto_atleta, name='manifiesto_atleta'),

    # AJAX endpoints
    path('ajax/calcular-preview/', views.ajax_calcular_preview, name='ajax_calcular_preview'),
    path('ajax/guardar-bloques/', views.ajax_guardar_bloques, name='ajax_guardar_bloques'),
    path('ajax/eliminar-bloque/', views.ajax_eliminar_bloque, name='ajax_eliminar_bloque'),
    path('ajax/accion-informe/', views.ajax_accion_informe, name='ajax_accion_informe'),
]

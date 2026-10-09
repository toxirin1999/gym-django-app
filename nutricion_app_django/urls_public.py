"""Superficie pública y mantenida del módulo nutricional.

El paquete aún conserva rutas educativas antiguas que dependen de modelos
anteriores. No se incluyen aquí para que ``/nutricion/`` sea una entrada
canónica y operativa del flujo V2 de bloques y biofeedback.
"""

from django.urls import path

from . import views


app_name = 'nutricion_app_django'

urlpatterns = [
    path('', views.dashboard_nutricional, name='dashboard_nutricional'),
    path('onboarding/', views.onboarding_nutricional, name='onboarding_nutricional'),
    path('recalcular/', views.recalcular_perfil, name='recalcular_perfil'),
    path('bloques/', views.calculadora_bloques, name='calculadora_bloques'),
    path('informe/', views.informe_semanal, name='informe_semanal'),
    path('progreso/', views.monitor_progreso, name='monitor_progreso'),
    path('ajax/calcular-preview/', views.ajax_calcular_preview, name='ajax_calcular_preview'),
    path('ajax/guardar-bloques/', views.ajax_guardar_bloques, name='ajax_guardar_bloques'),
    path('ajax/eliminar-bloque/', views.ajax_eliminar_bloque, name='ajax_eliminar_bloque'),
    path('ajax/accion-informe/', views.ajax_accion_informe, name='ajax_accion_informe'),
]

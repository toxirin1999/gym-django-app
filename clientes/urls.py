# clientes/urls.py

from django.urls import path
from . import views
from .views import calendario_bitacoras
from .views import registrar_bitacora
from clientes import views as clientes_views
from .views import historial_cliente, redirigir_usuario, panel_cliente
from django.contrib.auth.decorators import login_required
from joi import views as joi_views
from .views import recuerdos_semanales

# =================================================================
# ### AÑADE ESTA LÍNEA ###
# Esto soluciona el error 'NoReverseMatch'
# =================================================================
app_name = 'clientes'
# =================================================================

urlpatterns = [
    # Vista raíz: lista de clientes (entrenador)
    path('', views.lista_clientes, name='lista_clientes'),
    path('bitacora/calendario/', calendario_bitacoras, name='calendario_bitacoras'),
    path('bitacora/registrar/', registrar_bitacora, name='registrar_bitacora'),
    path('bitacora/ajax/', views.obtener_bitacora_dia, name='bitacora_ajax'),
    path('mapa/energia/', views.mapa_energia, name='mapa_energia'),
    path('joi/cuidado/', views.recomendacion_cuidado, name='recomendacion_cuidado'),
    path('blade-demo/', views.blade_runner_demo, name='blade_runner_demo'),
    path('api/lista-clientes/', views.api_lista_clientes, name='api_lista_clientes'),
    # Clientes
    path('asignar_programa/<int:cliente_id>/', views.asignar_programa, name='asignar_programa'),
    path('asignar_rutina/<int:cliente_id>/', views.asignar_rutina, name='asignar_rutina'),
    path('agregar/', views.agregar_cliente, name='agregar_cliente'),
    path('editar/<int:cliente_id>/', views.editar_cliente, name='editar_cliente'),
    path('eliminar/<int:cliente_id>/', views.eliminar_cliente, name='eliminar_cliente'),

    # --- Esta es la URL que estamos buscando ---
    path('cliente/<int:cliente_id>/preferencias-helms/', views.configurar_preferencias_helms,
         name='configurar_preferencias_helms'),
    path("cliente/<int:cliente_id>/control-peso/", views.control_peso_cliente, name="control_peso_cliente"),
    path("cliente/<int:cliente_id>/registrar-peso/", views.registrar_peso, name="registrar_peso"),
    path("cliente/<int:cliente_id>/establecer-objetivo-peso/", views.establecer_objetivo_peso,
         name="establecer_objetivo_peso"),
    path('portal/guardar/<int:cliente_id>/', views.guardar_entrenamiento_activo, name='guardar_entrenamiento_activo'),

    path('cliente/<int:cliente_id>/dashboard-adherencia/', views.dashboard_adherencia, name='dashboard_adherencia'),
    path('sesion/<int:cliente_id>/', views.portal_sesion_unificado, name='portal_sesion'),
    path('detalle/<int:cliente_id>/', views.detalle_cliente, name='detalle_cliente'),
    path('cliente/<int:cliente_id>/educacion/', views.vista_educacion_helms, name='vista_educacion_helms'),
    path('programa/<int:programa_id>/asignar_cliente/', views.asignar_programa_a_cliente,
         name='asignar_programa_a_cliente'),
    path('cliente/<int:cliente_id>/revisiones/', views.lista_revisiones, name='lista_revisiones'),
    path('cliente/<int:cliente_id>/revisiones/agregar/', views.agregar_revision, name='agregar_revision'),
    path('historial/exportar/<int:cliente_id>/', views.exportar_historial, name='exportar_historial'),

    # Paneles
    path('panel/', clientes_views.dashboard, name='dashboard'),
    path('mi-panel/', panel_cliente, name='panel_cliente'),

    # Nutrición
    path('nutricion/calcular/', views.calcular_plan_nutricional, name='calcular_plan_nutricional'),
    path('recuerdos/semana/', recuerdos_semanales, name='recuerdos_semanales'),

    # Inicio Joi personalizado
    # path('mockup_inicio/', views.inicio_cliente, name='inicio_cliente'),

    # Datos y medidas
    path('datos-graficas/<int:cliente_id>/', views.datos_graficas, name='datos_graficas'),
    path('medidas/', views.lista_medidas, name='lista_medidas'),
    path('medidas/agregar/', views.agregar_medida, name='agregar_medida'),
    # path('mockup-demo/', views.mockup_demo, name='mockup_demo'),
    path('responder-sugerencia/', views.responder_sugerencia, name='responder_sugerencia'),

    # Historial
    path('historial/<int:cliente_id>/', historial_cliente, name='historial_cliente'),

    # Joi
    path('inicio-joi/', joi_views.inicio_view, name='joi_inicio'),

    # Emoción y objetivos
    path('registrar_emocion/', views.registrar_emocion, name='registrar_emocion'),
    path('cliente/<int:cliente_id>/recordatorio/', views.actualizar_recordatorio_peso,
         name='actualizar_recordatorio_peso'),
    path('cliente/<int:cliente_id>/objetivo/', views.definir_objetivo, name='definir_objetivo'),
    path('revision/<int:revision_id>/eliminar/', views.eliminar_revision, name='eliminar_revision'),
    path('objetivo/<int:pk>/editar/', views.editar_objetivo, name='editar_objetivo'),
    path('objetivo/<int:pk>/eliminar/', views.eliminar_objetivo, name='eliminar_objetivo'),

    # Comparación
    path('comparar/', views.comparar_clientes, name='comparar_clientes'),
    path('comparar/datos/', views.datos_comparacion, name='datos_comparacion'),
    path('panel-entrenador/', views.panel_entrenador, name='panel_entrenador'),

    path('<int:cliente_id>/filosofia-plan/', views.vista_educacion_helms, name='vista_educacion_helms'),
]

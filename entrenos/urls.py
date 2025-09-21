# entrenos/urls.py

from django.urls import path
from . import views
from . import views_liftin
from .views import ejercicios_realizados_view
from clientes import views as vistas_clientes

app_name = 'entrenos'

urlpatterns = [
    # ============================================================================
    # URLs ORIGINALES (Se mantienen)
    # ============================================================================
    path('resumen/<int:pk>/', views.resumen_entreno, name='resumen_entreno'),
    path('gamificacion-resumen/<int:cliente_id>/', views.gamificacion_resumen, name='gamificacion_resumen'),
    path('resumen/<str:rango>/', views.entrenos_filtrados, name='entrenos_filtrados_rango'),
    path('plan-anual/<int:cliente_id>/', views.vista_plan_anual, name='vista_plan_anual'),
    path('historial-detallado/', views.historial_entrenos, name='historial_entrenos'),
    path('ejercicio/<str:nombre>/', views.detalle_ejercicio, name='detalle_ejercicio'),
    path('tabla-ejercicios/', views.ejercicios_realizados_view, name='tabla_ejercicios'),
    path('gestionar-base/', views.gestionar_ejercicios_base, name='gestionar_ejercicios_base'),

    # ============================================================================
    # VISTAS DEL PLANIFICADOR Y ENTRENAMIENTO ACTIVO (SECCIÓN MODIFICADA)
    # ============================================================================

    # Muestra la página para registrar el entreno
    path('cliente/<int:cliente_id>/entrenamiento-activo/', views.vista_entrenamiento_activo,
         name='entrenamiento_activo'),

    # ¡URL CORREGIDA Y ÚNICA PARA GUARDAR! Esta es la que usará el formulario.
    # El nombre ('name') se mantiene, pero la ruta es más específica.
    path('cliente/<int:cliente_id>/guardar-entrenamiento-activo/', views.guardar_entrenamiento_activo,
         name='guardar_entrenamiento_activo'),

    # ============================================================================
    # URLs DE LIFTIN (Se mantienen)
    # ============================================================================
    path('dashboard/<int:cliente_id>/', views.dashboard_liftin, name='dashboard_liftin'),
    path('liftin/cliente/<int:cliente_id>/', views_liftin.dashboard_liftin_cliente, name='dashboard_liftin_cliente'),
    path('liftin/importar/', views_liftin.importar_liftin, name='importar_liftin'),
    path('liftin/importar-completo/', views_liftin.importar_liftin_completo, name='importar_liftin_completo'),
    path('liftin/estadisticas/', views_liftin.estadisticas_liftin, name='estadisticas_liftin'),
    path('liftin/exportar/', views_liftin.exportar_datos_liftin, name='exportar_datos_liftin'),
    path('liftin/ejercicios/<int:entreno_id>/', views_liftin.detalle_ejercicios_liftin,
         name='detalle_ejercicios_liftin'),
    path('liftin/editar/<int:entrenamiento_id>/', views_liftin.editar_entrenamiento_liftin,
         name='editar_entrenamiento_liftin'),
    path('liftin/eliminar/<int:entrenamiento_id>/', views_liftin.eliminar_entrenamiento_liftin,
         name='eliminar_entrenamiento_liftin'),
    path('liftin/buscar/', views_liftin.buscar_entrenamientos_liftin, name='buscar_entrenamientos_liftin'),
    path('liftin/comparar/', views_liftin.comparar_liftin_manual, name='comparar_liftin_manual'),

    # ============================================================================
    # APIs (Se mantienen)
    # ============================================================================
    path('api/liftin/stats/', views_liftin.api_stats_liftin, name='api_stats_liftin'),
    path('api/liftin/ejercicios/<int:entrenamiento_id>/', views_liftin.api_ejercicios_liftin,
         name='api_ejercicios_liftin'),
    path('api/cliente/<int:cliente_id>/regenerar-plan/', views.api_regenerar_plan_helms, name='api_regenerar_plan'),

    # ============================================================================
    # URLs DE GESTIÓN GENERAL (Se mantienen)
    # ============================================================================
    path('lista/', views.lista_entrenamientos, name='lista_entrenamientos'),
    path('detalle/<int:entrenamiento_id>/', views.detalle_entrenamiento, name='detalle_entrenamiento'),
    path('cliente/<int:cliente_id>/plan/', views.vista_plan_calendario, name='vista_plan_calendario'),
    path('cliente/<int:cliente_id>/preferencias-helms/', vistas_clientes.configurar_preferencias_helms,
         name='configurar_preferencias_helms'),
    path('cliente/<int:cliente_id>/dashboard-adherencia/', vistas_clientes.dashboard_adherencia,
         name='dashboard_adherencia'),
    path('cliente/<int:cliente_id>/comparacion/', views.dashboard_comparacion_planificadores,
         name='dashboard_comparacion'),
    path('resumen-anual/<int:cliente_id>/', views.vista_resumen_anual, name='vista_resumen_anual'),
]

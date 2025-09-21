# analytics/urls.py

from django.urls import path
from . import views
from . import views_ia
from .analisis_intensidad import dashboard_intensidad_avanzado
from .analisis_progresion import dashboard_progresion_avanzado

app_name = 'analytics'

urlpatterns = [
    # =================================================================
    # ### NUEVA FUNCIONALIDAD DE ANÁLISIS DE PROGRAMAS (IA) ###
    # Esta es la secuencia correcta de URLs para la nueva funcionalidad.
    # =================================================================

    # 1. URL para la página principal de análisis del programa
    path('cliente/<int:cliente_id>/optimizar-programa/', views_ia.vista_optimizacion_programa,
         name='vista_optimizacion_programa'),

    path('cliente/<int:cliente_id>/resumen-anual/', views.vista_resumen_anual, name='vista_resumen_anual'),
    path('api/cliente/<int:cliente_id>/marcar-completado/', views.api_marcar_entreno_completado,
         name='api_marcar_completado'),

    # 2. URL para la página de comparación (antes de guardar)
    path('cliente/<int:cliente_id>/comparar-programa/', views_ia.vista_comparacion_programa,
         name='vista_comparacion_programa'),

    # 3. URL que recibe el POST para guardar el programa en la BD
    path('cliente/<int:cliente_id>/guardar-programa/', views_ia.guardar_programa_optimizado,
         name='guardar_programa_optimizado'),

    # =================================================================
    # ### DASHBOARDS Y VISTAS PRINCIPALES ###
    # =================================================================
    path('cliente/<int:cliente_id>/fatiga/', views.dashboard_fatiga, name='dashboard_fatiga'),
    path('dashboard/<int:cliente_id>/', views.dashboard, name='dashboard_cliente'),
    path('ia/dashboard/<int:cliente_id>/', views_ia.dashboard_ia_principal, name='dashboard_ia_principal'),

    # =================================================================
    # ### MÓDULOS DE ANÁLISIS DETALLADOS ###
    # =================================================================

    path('progresion/<int:cliente_id>/', views.analisis_progresion, name='progresion'),
    path('comparativas/<int:cliente_id>/', views.comparativas, name='comparativas'),
    path('recomendaciones/<int:cliente_id>/', views.recomendaciones, name='recomendaciones'),
    path('predicciones/<int:cliente_id>/', views.predicciones, name='predicciones'),

    # Módulos de IA (los que ya tenías)
    path('ia/predicciones/<int:cliente_id>/', views_ia.predicciones_avanzadas, name='predicciones_avanzadas'),
    path('ia/recomendaciones/<int:cliente_id>/', views_ia.recomendaciones_inteligentes,
         name='recomendaciones_inteligentes'),
    path('ia/patrones/<int:cliente_id>/', views_ia.deteccion_patrones_automatica, name='deteccion_patrones'),
    path('ia/optimizacion/<int:cliente_id>/', views_ia.vista_optimizacion_entrenamientos,
         name='vista_optimizacion_entrenamientos'),

    # =================================================================
    # ### APIs Y FUNCIONES INTERNAS ###
    # =================================================================

    path('calcular-metricas/<int:cliente_id>/', views.calcular_metricas, name='calcular_metricas'),
    path('generar-recomendaciones/<int:cliente_id>/', views.generar_recomendaciones, name='generar_recomendaciones'),
    path('recomendacion/<int:recomendacion_id>/aplicar/', views.marcar_recomendacion_aplicada,
         name='aplicar_recomendacion'),
    path('actualizar_tendencias/<int:cliente_id>/', views.actualizar_tendencias, name='actualizar_tendencias'),

    # APIs para AJAX/JS
    path('api/ejercicios/<int:cliente_id>/', views.api_ejercicios_tabla, name='api_ejercicios'),
    path('api/metricas/<int:cliente_id>/', views.api_metricas_tabla, name='api_metricas'),
    path('api/progresion/<int:cliente_id>/<str:ejercicio>/', views.api_progresion, name='api_progresion'),
    path('api/dashboard-refresh/<int:cliente_id>/', views_ia.api_dashboard_refresh, name='api_dashboard_refresh'),
    path('api/prediccion-tiempo-real/<int:cliente_id>/', views_ia.api_prediccion_tiempo_real,
         name='api_prediccion_tiempo_real'),
    path('api/recomendacion-tiempo-real/<int:cliente_id>/', views_ia.api_recomendacion_tiempo_real,
         name='api_recomendacion_tiempo_real'),
    path('api/deteccion-patrones-tiempo-real/<int:cliente_id>/', views_ia.api_deteccion_patrones_tiempo_real,
         name='api_deteccion_patrones_tiempo_real'),
    path('api/optimizacion-tiempo-real/<int:cliente_id>/', views_ia.api_optimizacion_tiempo_real,
         name='api_optimizacion_tiempo_real'),
    path('intensidad-avanzado/<int:cliente_id>/', dashboard_intensidad_avanzado, name='intensidad_avanzado'),
    path('progresion-avanzado/<int:cliente_id>/', dashboard_progresion_avanzado, name='progresion_avanzado'),
    path('api/cliente/<int:cliente_id>/guardar_meta/', views.api_guardar_meta, name='api_guardar_meta'),
    path('api/cliente/<int:cliente_id>/guardar_anotacion/', views.api_guardar_anotacion, name='api_guardar_anotacion'),
    path('cliente/<int:cliente_id>/equilibrio/', views.dashboard_equilibrio, name='dashboard_equilibrio'),
]

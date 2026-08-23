# entrenos/urls.py

from functools import wraps

from django.conf import settings
from django.http import Http404
from django.urls import path
from . import views
from . import views_liftin
from .views import ejercicios_realizados_view
from clientes import views as vistas_clientes
from .views import evaluacion_profesional_view

app_name = 'entrenos'


def liftin_ui_required(view_func):
    """Impide ejecutar una vista Liftin mientras su UX esté archivada."""
    @wraps(view_func)
    def guarded_view(request, *args, **kwargs):
        if not getattr(settings, 'LIFTIN_UI_ENABLED', False):
            raise Http404("La interfaz Liftin está archivada")
        return view_func(request, *args, **kwargs)

    return guarded_view

urlpatterns = [
    # ============================================================================
    # URLs ORIGINALES (Se mantienen)
    # ============================================================================
    path('resumen/<int:pk>/', views.resumen_entreno, name='resumen_entreno'),
    path('pausa/<int:pausa_id>/motivo/', views.guardar_motivo_pausa, name='guardar_motivo_pausa'),
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

    # Briefing pre-sesión
    path('cliente/<int:cliente_id>/briefing/', views.briefing_entrenamiento,
         name='briefing_entrenamiento'),
    path(
        'cliente/<int:cliente_id>/autoridad-gym/corregir/',
        views.corregir_autoridad_gym,
        name='corregir_autoridad_gym',
    ),
    path(
        'cliente/<int:cliente_id>/autoridad-gym/revertir/',
        views.revertir_autoridad_gym,
        name='revertir_autoridad_gym',
    ),

    # Muestra la página para registrar el entreno
    path('cliente/<int:cliente_id>/entrenamiento-activo/', views.vista_entrenamiento_activo,
         name='entrenamiento_activo'),

    # ¡URL CORREGIDA Y ÚNICA PARA GUARDAR! Esta es la que usará el formulario.
    # El nombre ('name') se mantiene, pero la ruta es más específica.
    path('cliente/<int:cliente_id>/guardar-entrenamiento-activo/', views.guardar_entrenamiento_activo,
         name='guardar_entrenamiento_activo'),
    
    # API para persistir sustituciones en caliente
    path('api/cliente/<int:cliente_id>/save-hot-swap/', views.api_save_hot_swap, name='api_save_hot_swap'),

    # API para alternativas cuando máquina ocupada
    path('api/cliente/<int:cliente_id>/alternativas-maquina/', views.api_alternativas_maquina, name='api_alternativas_maquina'),

    # Phase 29 — Alternativas revisables por lesión (no sustitución automática)
    path('api/cliente/<int:cliente_id>/alternativas-lesion/', views.api_alternativas_lesion, name='api_alternativas_lesion'),

    # API para reportar molestia intra-entreno
    path('api/cliente/<int:cliente_id>/reportar-molestia/', views.api_reportar_molestia, name='api_reportar_molestia'),

    # ============================================================================
    # URLs DE LIFTIN (Se mantienen)
    # ============================================================================
    path('dashboard/<int:cliente_id>/', liftin_ui_required(views.dashboard_liftin), name='dashboard_liftin'),
    path('liftin/cliente/<int:cliente_id>/', liftin_ui_required(views_liftin.dashboard_liftin_cliente), name='dashboard_liftin_cliente'),
    path('liftin/importar/', liftin_ui_required(views_liftin.importar_liftin), name='importar_liftin'),
    path('liftin/importar-completo/', liftin_ui_required(views_liftin.importar_liftin_completo), name='importar_liftin_completo'),
    path('liftin/estadisticas/', liftin_ui_required(views_liftin.estadisticas_liftin), name='estadisticas_liftin'),
    path('liftin/exportar/', liftin_ui_required(views_liftin.exportar_datos_liftin), name='exportar_datos_liftin'),
    path('liftin/ejercicios/<int:entreno_id>/', liftin_ui_required(views_liftin.detalle_ejercicios_liftin),
         name='detalle_ejercicios_liftin'),
    path('liftin/editar/<int:entrenamiento_id>/', liftin_ui_required(views_liftin.editar_entrenamiento_liftin),
         name='editar_entrenamiento_liftin'),
    path('liftin/eliminar/<int:entrenamiento_id>/', liftin_ui_required(views_liftin.eliminar_entrenamiento_liftin),
         name='eliminar_entrenamiento_liftin'),
    path('liftin/buscar/', liftin_ui_required(views_liftin.buscar_entrenamientos_liftin), name='buscar_entrenamientos_liftin'),
    path('liftin/comparar/', liftin_ui_required(views_liftin.comparar_liftin_manual), name='comparar_liftin_manual'),

    # ============================================================================
    # APIs (Se mantienen)
    # ============================================================================
    path('api/liftin/stats/', liftin_ui_required(views_liftin.api_stats_liftin), name='api_stats_liftin'),
    path('api/liftin/ejercicios/<int:entrenamiento_id>/', liftin_ui_required(views_liftin.api_ejercicios_liftin),
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
    path('cliente/<int:cliente_id>/dashboard-ejercicios/',
         views.dashboard_ejercicios,
         name='dashboard_ejercicios'),

    # Detalle de ejercicio específico (opcional)
    path('cliente/<int:cliente_id>/ejercicio/<str:nombre_ejercicio>/',
         views.detalle_ejercicio_especifico,
         name='detalle_ejercicio_especifico'),
    path('ajax/entrenamiento/<int:cliente_id>/',
         views.ajax_obtener_entrenamiento_dia,
         name='ajax_entrenamiento_dia'),

    path('ajax/entrenamientos-mes/<int:cliente_id>/',
         views.ajax_obtener_entrenamientos_mes,
         name='ajax_entrenamientos_mes'),
    # path('api/ejercicios/registrar/', views.api_registrar_ejercicio, name='api_registrar_ejercicio'),
    # Desactivada (25-jul-2026): csrf_exempt sin auth real, 0 registros creados nunca (DetalleEjercicioRealizado
    # count=0) y bug de campo inexistente ('notas_generales') que la haría fallar si se usara. Ver
    # api_apple_health (línea ~8350) para el patrón correcto (Cliente.api_token) si se reactiva en el futuro.
    path('api/estadisticas/', views.api_obtener_estadisticas, name='api_estadisticas'),
    path('api/usuario/perfil/', views.api_obtener_perfil, name='api_perfil'),
    path('api/bio-correlation/<int:cliente_id>/', views.api_bio_correlation, name='api_bio_correlation'),

    # ============================================================================
    # NUEVO DASHBOARD DE EVOLUCIÓN
    # ============================================================================
    path('cliente/<int:cliente_id>/dashboard-evolucion/', views.dashboard_evolucion, name='dashboard_evolucion'),
    path('cliente/<int:cliente_id>/entreno/<int:entreno_id>/cierre/', views.post_entreno_resumen, name='post_entreno_resumen'),
    path('cliente/<int:cliente_id>/actualizar-fase/', views.actualizar_fase_cliente, name='actualizar_fase_cliente'),
    path('cliente/<int:cliente_id>/evaluacion-profesional/', evaluacion_profesional_view,
         name='evaluacion_profesional'),

    # ── Fase 2: Actividades libres ────────────────────────────────────────────
    path('cliente/<int:cliente_id>/registrar-actividad/', views.registrar_actividad_libre,
         name='registrar_actividad_libre'),
    path('api/cliente/<int:cliente_id>/buscar-ejercicios/', views.api_buscar_ejercicios,
         name='api_buscar_ejercicios'),

    # ── Fase 5: Timeline unificado ────────────────────────────────────────────
    path('cliente/<int:cliente_id>/timeline/', views.timeline_atleta,
         name='timeline_atleta'),
    path('cliente/<int:cliente_id>/actividad/<int:actividad_id>/editar/', views.editar_actividad_libre,
         name='editar_actividad_libre'),
    path('cliente/<int:cliente_id>/actividad/<int:actividad_id>/eliminar/', views.eliminar_actividad_libre,
         name='eliminar_actividad_libre'),

    # ── Apple Health / Shortcuts API ──────────────────────────────────────────
    path('api/apple-health/', views.api_apple_health, name='api_apple_health'),
]

# logros/urls.py

from django.urls import path
from . import views

app_name = 'logros'

urlpatterns = [
    # Vista principal del Códice de las Leyendas
    path('', views.perfil_gamificacion, name='perfil_gamificacion'),
    path('cliente/<int:cliente_id>/', views.perfil_gamificacion, name='perfil_gamificacion'),

    # Vistas de Arquetipos (antes Niveles)
    path('cliente/<int:cliente_id>/arquetipo/<int:arquetipo_nivel>/', views.detalle_arquetipo,
         name='detalle_arquetipo'),

    # Vistas de Pruebas Legendarias (antes Logros)
    path('pruebas-legendarias/', views.lista_pruebas_legendarias, name='lista_pruebas_legendarias'),

    # Ranking y competición
    path('ranking/', views.ranking_clientes, name='ranking_clientes'),

    # Procesamiento manual
    path('procesar-entreno/<int:entreno_id>/', views.procesar_entreno, name='procesar_entreno'),

    # Análisis y reportes
    path('analisis/cliente/<int:cliente_id>/', views.analisis_cliente, name='analisis_cliente'),
    path('analisis/global/', views.analisis_global, name='analisis_global'),
    path('analisis/cliente/<int:cliente_id>/pdf/', views.exportar_analisis_cliente_pdf,
         name='exportar_analisis_cliente_pdf'),

    # Notificaciones
    path('cliente/<int:cliente_id>/notificaciones/', views.listar_notificaciones, name='listar_notificaciones'),
    path('notificacion/<int:notificacion_id>/marcar-leida/', views.marcar_notificacion_leida,
         name='marcar_notificacion_leida'),
    path('cliente/<int:cliente_id>/notificaciones/ajax/', views.obtener_notificaciones_ajax,
         name='obtener_notificaciones_ajax'),
    path('codice/<int:cliente_id>/', views.ver_codice_completo, name='ver_codice_completo'),
    path('gamificacion-resumen/<int:cliente_id>/', views.gamificacion_resumen_json, name='gamificacion_resumen_json'),
    # En logros/urls.py añadir:
    # path('arquetipo/<int:cliente_id>/<int:arquetipo_id>/', views.arquetipo_detalle, name='arquetipo_detalle'),

    # Misiones (Quests) - mantienen la funcionalidad original
    path('misiones/', views.lista_misiones, name='lista_misiones'),
    path('mision/<int:mision_id>/', views.detalle_mision, name='detalle_mision'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    # URLs de compatibilidad (para no romper enlaces existentes)
    path('logros/', views.lista_pruebas_legendarias, name='lista_logros'),  # Redirige a pruebas legendarias
]

from django.urls import path
from . import views

app_name = 'estoico'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_estoico, name='dashboard'),

    # Diario y reflexiones
    path('diario/', views.diario_dia, name='diario_hoy'),
    path('diario/<int:dia>/', views.diario_dia, name='diario_dia'),

    # Calendario
    path('calendario/', views.calendario_estoico, name='calendario'),

    # Progreso y estadísticas
    path('progreso/', views.progreso_usuario, name='progreso'),

    # Configuración
    path('configuracion/', views.configuracion_estoica, name='configuracion'),
    path('exportar/', views.exportar_reflexiones, name='exportar_reflexiones'),

    # --- AÑADE ESTA LÍNEA AL FINAL DE TUS URLS ---
    # Ruta para la eliminación de datos
    path('eliminar-datos/', views.eliminar_todos_datos_usuario, name='eliminar_todos_datos'),
    path('exportar/pdf/', views.exportar_reflexiones_pdf, name='exportar_pdf'),  # <-- AÑADE ESTA LÍNEA
    # Búsqueda
    path('buscar/', views.buscar_contenido, name='buscar'),

    # AJAX endpoints
    path('logro/<int:logro_id>/visto/', views.marcar_logro_visto, name='marcar_logro_visto'),

    # Exportación
    path('exportar/', views.exportar_reflexiones, name='exportar_reflexiones'),
]

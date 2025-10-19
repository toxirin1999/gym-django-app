from django.urls import path
from . import views

app_name = 'diario'
urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_diario, name='dashboard_diario'),

    # ========================================
    # PROSOCHE - Diario Mensual
    # ========================================
    path('prosoche/', views.prosoche_dashboard, name='prosoche_dashboard'),
    path('prosoche/objetivos/actualizar/', views.prosoche_actualizar_objetivos, name='prosoche_actualizar_objetivos'),
    path('prosoche/revision-semanal/', views.prosoche_revision_semanal, name='prosoche_revision_semanal'),
    path('oraculo/', views.oraculo_insights, name='oraculo_insights'),
    # --- LÍNEA INCORRECTA ELIMINADA ---

    path('prosoche/habito/crear/', views.prosoche_crear_habito, name='prosoche_crear_habito'),
    path('prosoche/habito/toggle/', views.prosoche_toggle_habito, name='prosoche_toggle_habito'),
    path('prosoche/revision/', views.prosoche_revision_mes, name='prosoche_revision_mes'),
    path('prosoche/mes/<str:mes>/<int:año>/', views.prosoche_mes_anterior, name='prosoche_mes_anterior'),

    # URL para CREAR una nueva entrada (CORRECTA)
    path('prosoche/entrada/nueva/', views.prosoche_entrada_form, name='prosoche_nueva_entrada'),

    # URL para EDITAR una entrada existente (CORRECTA)
    path('prosoche/entrada/editar/<int:entrada_id>/', views.prosoche_entrada_form, name='prosoche_editar_entrada'),
    path('prosoche/entrada/eliminar/<int:entrada_id>/', views.prosoche_eliminar_entrada,
         name='prosoche_eliminar_entrada'),
    # EUDAIMONIA - Áreas de la Vida
    # ========================================
    path('eudaimonia/', views.eudaimonia_dashboard, name='eudaimonia_dashboard'),
    path('eudaimonia/area/<int:area_id>/', views.eudaimonia_area_detalle, name='eudaimonia_area_detalle'),
    path('eudaimonia/actualizar/', views.eudaimonia_actualizar, name='eudaimonia_actualizar'),
    path('eudaimonia/crear/', views.eudaimonia_crear_area, name='eudaimonia_crear_area'),
    # ========================================
    # ARETÉ - Desarrollo Personal
    # ========================================
    path('arete/', views.arete_dashboard, name='arete_dashboard'),
    path('arete/ejercicio/<int:ejercicio_id>/', views.arete_ejercicio_actualizar, name='arete_ejercicio_actualizar'),

    # ========================================
    # GNOSIS - Gestión de Conocimiento
    # ========================================
    path('gnosis/', views.gnosis_dashboard, name='gnosis_dashboard'),
    path('gnosis/crear/', views.gnosis_crear, name='gnosis_crear'),

    # ========================================
    # VIRES - Salud y Deporte
    # ========================================
    path('vires/', views.vires_dashboard, name='vires_dashboard'),
    path('vires/seguimiento/crear/', views.vires_seguimiento_crear, name='vires_seguimiento_crear'),

    # ========================================
    # KAIROS - Calendario y Eventos
    # ========================================
    path('kairos/', views.kairos_dashboard, name='kairos_dashboard'),
    path('kairos/evento/crear/', views.kairos_evento_crear, name='kairos_evento_crear'),
    path('kairos/api/eventos/', views.kairos_eventos_api, name='kairos_eventos_api'),

    path('analiticas/', views.analiticas_personales, name='analiticas_personales'),

    path('simbiosis/', views.simbiosis_dashboard, name='simbiosis_dashboard'),
    path('simbiosis/persona/crear/', views.persona_crear_editar, name='persona_crear'),
    path('simbiosis/persona/editar/<int:persona_id>/', views.persona_crear_editar, name='persona_editar'),
    path('simbiosis/interaccion/crear/', views.interaccion_crear_editar, name='interaccion_crear'),
    path('simbiosis/interaccion/editar/<int:interaccion_id>/', views.interaccion_crear_editar,
         name='interaccion_editar'),
    path('simbiosis/persona/<int:persona_id>/', views.persona_detalle, name='persona_detalle'),

]

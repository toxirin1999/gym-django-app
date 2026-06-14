from django.urls import path
from . import views
from . import views_habitos

app_name = 'diario'
urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_diario, name='dashboard_diario'),
    path('lectura/semana/', views.lectura_semanal, name='lectura_semanal'),

    # ========================================
    # PROSOCHE - Diario Mensual
    # ========================================
    path('prosoche/', views.prosoche_dashboard, name='prosoche_dashboard'),
    path('prosoche/objetivos/actualizar/', views.prosoche_actualizar_objetivos, name='prosoche_actualizar_objetivos'),
    path('prosoche/revision-semanal/', views.prosoche_revision_semanal, name='prosoche_revision_semanal'),
    path('oraculo/', views.oraculo_insights, name='oraculo_insights'),
    path('prosoche/entrada/rapida/', views.prosoche_entrada_rapida, name='prosoche_entrada_rapida'),

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
    # ARETÉ, GNOSIS, VIRES — ocultos (datos preservados, UI desactivada)
    # path('arete/', views.arete_dashboard, name='arete_dashboard'),
    # path('arete/ejercicio/<int:ejercicio_id>/', views.arete_ejercicio_actualizar, name='arete_ejercicio_actualizar'),
    # path('gnosis/', views.gnosis_dashboard, name='gnosis_dashboard'),
    # path('gnosis/crear/', views.gnosis_crear, name='gnosis_crear'),
    # path('vires/', views.vires_dashboard, name='vires_dashboard'),
    # path('vires/seguimiento/crear/', views.vires_seguimiento_crear, name='vires_seguimiento_crear'),

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
    path('simbiosis/persona/<int:persona_id>/eliminar/', views.eliminar_persona, name='eliminar_persona'),
    # Logos
    path('logos/', views.logos_dashboard, name='logos_dashboard'),
    path('logos/escribir/', views.logos_escritura_libre, name='logos_escritura_libre'),
    path('logos/reflexion/<int:reflexion_id>/', views.logos_ver_reflexion, name='logos_ver_reflexion'),
    path('logos/reflexion/<int:reflexion_id>/editar/', views.logos_editar_reflexion, name='logos_editar_reflexion'),
    path('logos/mis-reflexiones/', views.logos_lista_reflexiones, name='logos_lista_reflexiones'),
    path('logos/guiada/<slug:slug>/', views.logos_reflexion_guiada, name='logos_reflexion_guiada'),
    path('logos/calendario/', views.logos_calendario_reflexiones, name='logos_calendario'),
    path('guardar-estado-animo/', views.guardar_estado_animo, name='guardar_estado_animo'),

    # Virtudes
    path('virtudes/', views.virtudes_dashboard, name='virtudes_dashboard'),
    path('virtudes/<str:tipo>/', views.virtud_detalle, name='virtud_detalle'),
    path('insignias/', views.insignias_lista, name='insignias_lista'),
    path('analisis-habitos/', views.analisis_habitos_mes_actual, name='analisis_habitos_mes_actual'),
    path('analisis-habitos/anual/', views.analisis_habitos_anual, name='analisis_habitos_anual'),
    path('analisis-habitos/anual/<int:año>/', views.analisis_habitos_anual, name='analisis_habitos_anual_año'),
    path('analisis-habitos/historico/', views.analisis_habitos_historico, name='analisis_habitos_historico'),
    path('prosoche/copiar-habitos-mes-anterior/', views.copiar_habitos_mes_anterior,
         name='copiar_habitos_mes_anterior'),
    path('prosoche/eliminar-habito/<int:habito_id>/', views.eliminar_habito, name='eliminar_habito'),

    # ========================================
    # HÁBITOS - Dashboard Unificado (Fase 1)
    # ========================================
    path('habitos/', views_habitos.habitos_dashboard, name='habitos_dashboard'),
    path('habitos/crear/', views_habitos.habito_crear, name='habito_crear'),
    path('habitos/editar/<int:habito_id>/', views_habitos.habito_editar, name='habito_editar'),
    path('habitos/<int:habito_id>/wizard-4leyes/', views_habitos.habito_wizard_4leyes, name='habito_wizard_4leyes'),
    path('habitos/<int:habito_id>/registrar-trigger/', views_habitos.habito_registrar_trigger, name='habito_registrar_trigger'),
    path('habitos/<int:habito_id>/analisis-patrones/', views_habitos.habito_analisis_patrones, name='habito_analisis_patrones'),
    path('habitos/toggle-dia/', views_habitos.habito_toggle_dia, name='habito_toggle_dia'),
    path('habitos/eliminar/<int:habito_id>/', views_habitos.habito_eliminar, name='habito_eliminar'),
    path('habitos/<int:habito_id>/pausar/', views_habitos.habito_pausar, name='habito_pausar'),
    path('habitos/<int:habito_id>/cerrar/', views_habitos.habito_cerrar, name='habito_cerrar'),

    # ========================================
    # PRESENCIA — Ritual unificado
    # ========================================
    path('presencia/apertura/', views.presencia_apertura, name='presencia_apertura'),
    path('presencia/cierre/', views.presencia_cierre, name='presencia_cierre'),
    path('presencia/check-simbiosis/', views.check_simbiosis_api, name='check_simbiosis_api'),
    path('presencia/habito-invitacion/', views.aceptar_habito_invitacion, name='aceptar_habito_invitacion'),
    path('presencia/panico/', views.panico_impulso_api, name='panico_impulso_api'),
    path('presencia/promover-interina/', views.promover_persona_interina, name='promover_persona_interina'),
    path('reprocesar-cierres/', views.reprocesar_cierres, name='reprocesar_cierres'),
]

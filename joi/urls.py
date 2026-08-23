from django.urls import path
from . import views

app_name = 'joi'

urlpatterns = [
    path('mensaje/<int:mensaje_id>/leido/', views.marcar_mensaje_leido, name='joi_marcar_leido'),
    path('habitacion/', views.habitacion_joi, name='joi_habitacion'),
    path(
        'habitacion/memoria/<int:manual_id>/<str:accion>/',
        views.revision_memoria,
        name='joi_revision_memoria',
    ),
    path(
        'habitacion/memoria/operacion/<int:operacion_id>/deshacer/',
        views.deshacer_revision_memoria_view,
        name='joi_deshacer_revision_memoria',
    ),
    path('mensaje/<int:mensaje_id>/feedback/', views.feedback_joi, name='joi_feedback'),
    path('manual/', views.poda_manual_joi, name='joi_manual'),
    path('mood/', views.registrar_mood, name='joi_mood'),
    path('narrativa/', views.narrativa_joi_view, name='joi_narrativa'),
    path('narrativa/dialogo/', views.crear_dialogo_narrativa, name='joi_dialogo_narrativa'),
    path('api/feedback-estado/', views.feedback_estado_encaje, name='joi_feedback_estado_encaje'),
    path('api/pulso-actual/', views.pulso_actual_api, name='joi_pulso_actual'),
]

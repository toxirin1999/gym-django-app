from django.urls import path
from . import views

app_name = 'joi'

urlpatterns = [
    path('mensaje/<int:mensaje_id>/leido/', views.marcar_mensaje_leido, name='joi_marcar_leido'),
    path('habitacion/', views.habitacion_joi, name='joi_habitacion'),
    path('mensaje/<int:mensaje_id>/feedback/', views.feedback_joi, name='joi_feedback'),
    path('manual/', views.poda_manual_joi, name='joi_manual'),
    path('manual/<int:entrada_id>/desactivar/', views.desactivar_entrada_manual, name='joi_desactivar_entrada'),
    path('mood/', views.registrar_mood, name='joi_mood'),
    path('narrativa/', views.narrativa_joi_view, name='joi_narrativa'),
    path('narrativa/dialogo/', views.crear_dialogo_narrativa, name='joi_dialogo_narrativa'),
    path('api/feedback-estado/', views.feedback_estado_encaje, name='joi_feedback_estado_encaje'),
    path('api/pulso-actual/', views.pulso_actual_api, name='joi_pulso_actual'),
]

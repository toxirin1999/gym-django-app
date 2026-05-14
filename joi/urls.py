from django.urls import path
from .views import diario_view, home_redirect
from .views import logros_view, inicio_view
from .views import diario_view, historial_view, entrenar_view
from .views import recuerdos_view
from django.urls import path
from . import views

urlpatterns = [
    path('', home_redirect),  # 👈 redirige /
    path('inicio/', inicio_view, name='inicio'),
    path('diario/', diario_view, name='diario'),
    path('historial/', historial_view, name='historial'),
    path('entrenar/', entrenar_view, name='entrenar'),
    path('logros/', logros_view, name='logros'),
    path('recuerdos/', recuerdos_view, name='recuerdos'),
    path('mensaje/<int:mensaje_id>/leido/', views.marcar_mensaje_leido, name='joi_marcar_leido'),
    path('habitacion/', views.habitacion_joi, name='joi_habitacion'),
    path('mensaje/<int:mensaje_id>/feedback/', views.feedback_joi, name='joi_feedback'),
    path('manual/', views.poda_manual_joi, name='joi_manual'),
    path('manual/<int:entrada_id>/desactivar/', views.desactivar_entrada_manual, name='joi_desactivar_entrada'),
    path('mood/', views.registrar_mood, name='joi_mood'),
    path('narrativa/', views.narrativa_joi_view, name='joi_narrativa'),
    path('narrativa/dialogo/', views.crear_dialogo_narrativa, name='joi_dialogo_narrativa'),
]

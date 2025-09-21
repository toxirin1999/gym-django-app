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
]

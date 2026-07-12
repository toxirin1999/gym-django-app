from django.urls import path

from . import views

app_name = 'disponibilidad'

urlpatterns = [
    path('registrar/<int:cliente_id>/', views.registrar, name='registrar'),
]

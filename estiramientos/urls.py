from django.urls import path
from . import views

app_name = "estiramientos"

urlpatterns = [
    path("", views.panel_estiramientos, name="panel"),
    path("plan/<int:plan_id>/", views.iniciar_plan, name="iniciar_plan"),
]

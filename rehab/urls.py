from django.urls import path

from . import views

app_name = "rehab"

urlpatterns = [
    path("", views.hoy_view, name="hoy"),
    path("episodio/nuevo/", views.iniciar_episodio_view, name="iniciar_episodio"),
    path("episodio/<int:episodio_id>/dolor/", views.registrar_dolor_view, name="registrar_dolor"),
    path("episodio/<int:episodio_id>/sesion/", views.registrar_sesion_view, name="registrar_sesion"),
    path("propuesta-avance/", views.proponer_avance_view, name="proponer_avance"),
    path("recorrido/", views.recorrido_view, name="recorrido"),
    path("evolucion/", views.evolucion_view, name="evolucion"),
    path("episodio/<int:episodio_id>/avance/confirmar/", views.confirmar_avance_view, name="confirmar_avance"),
]

from django.contrib import admin

from .models import (
    EjercicioRehab,
    EjercicioSesionRehab,
    EpisodioRehab,
    FaseProtocolo,
    PrescripcionEjercicio,
    ProtocoloRehab,
    RegistroDiarioRehab,
    SesionRehab,
    TransicionFase,
)

admin.site.register(ProtocoloRehab)
admin.site.register(FaseProtocolo)
admin.site.register(EjercicioRehab)
admin.site.register(PrescripcionEjercicio)
admin.site.register(EpisodioRehab)
admin.site.register(RegistroDiarioRehab)
admin.site.register(SesionRehab)
admin.site.register(EjercicioSesionRehab)
admin.site.register(TransicionFase)

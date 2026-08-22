from django.contrib import admin

from .models import (
    EjercicioRehab,
    ContratoRiesgoGymFaseRehab,
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


@admin.register(ContratoRiesgoGymFaseRehab)
class ContratoRiesgoGymFaseRehabAdmin(admin.ModelAdmin):
    list_display = ('fase', 'version', 'schema_version', 'action', 'scope', 'activo', 'vigente_desde')
    list_filter = ('activo', 'action', 'scope', 'schema_version')
    readonly_fields = ('creado_en',)

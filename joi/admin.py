from django.contrib import admin
from .models import Entrenamiento, EstadoEmocional, ManualDavid, NarrativaActiva

admin.site.register(Entrenamiento)
admin.site.register(EstadoEmocional)


@admin.register(ManualDavid)
class ManualDavidAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo', 'estado', 'confianza', 'activa', 'creado_en', 'entrada_corta')
    list_filter  = ('tipo', 'estado', 'activa', 'origen')
    search_fields = ('user__username', 'entrada')
    readonly_fields = ('creado_en', 'fuente_mensaje')

    def entrada_corta(self, obj):
        return obj.entrada[:60]
    entrada_corta.short_description = 'Entrada'


@admin.register(NarrativaActiva)
class NarrativaActivaAdmin(admin.ModelAdmin):
    list_display = ('user', 'estado', 'confianza', 'version', 'actualizado_en')
    list_filter  = ('estado',)
    readonly_fields = ('creado_en', 'actualizado_en', 'version')

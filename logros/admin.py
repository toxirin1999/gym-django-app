# logros/admin.py

from django.contrib import admin
from .models import (
    Arquetipo, PruebaLegendaria, PerfilGamificacion, PruebaUsuario,
    Quest, TipoQuest, QuestUsuario, HistorialPuntos, Notificacion, Liga, Temporada, RankingEntry, TituloEspecial,
    PerfilTitulo
)


@admin.register(Arquetipo)
class ArquetipoAdmin(admin.ModelAdmin):
    list_display = ('nivel', 'titulo_arquetipo', 'nombre_personaje', 'puntos_requeridos')
    list_filter = ('nivel',)
    search_fields = ('nombre_personaje', 'titulo_arquetipo')
    ordering = ('nivel',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('nivel', 'nombre_personaje', 'titulo_arquetipo')
        }),
        ('Descripción', {
            'fields': ('filosofia',)
        }),
        ('Configuración', {
            'fields': ('puntos_requeridos', 'icono_fa', 'imagen_url')
        }),
    )


@admin.register(PruebaLegendaria)
class PruebaLegendariaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'arquetipo', 'clave_calculo', 'meta_valor', 'puntos_recompensa', 'es_secreta')
    list_filter = ('arquetipo', 'es_secreta', 'puntos_recompensa')
    search_fields = ('nombre', 'descripcion', 'clave_calculo')
    ordering = ('arquetipo__nivel', 'nombre')

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'arquetipo')
        }),
        ('Configuración Técnica', {
            'fields': ('clave_calculo', 'meta_valor')
        }),
        ('Recompensas', {
            'fields': ('puntos_recompensa', 'es_secreta')
        }),
    )


@admin.register(PerfilGamificacion)
class PerfilGamificacionAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'puntos_totales', 'nivel_actual', 'racha_actual', 'entrenos_totales')
    list_filter = ('nivel_actual', 'fecha_ultimo_entreno')
    search_fields = ('cliente__nombre', 'cliente__apellido')
    readonly_fields = ('fecha_actualizacion',)
    raw_id_fields = ('cliente', 'nivel_actual')

    fieldsets = (
        ('Cliente', {
            'fields': ('cliente',)
        }),
        ('Progreso', {
            'fields': ('puntos_totales', 'nivel_actual')
        }),
        ('Estadísticas', {
            'fields': ('racha_actual', 'racha_maxima', 'entrenos_totales', 'fecha_ultimo_entreno')
        }),
        ('Metadatos', {
            'fields': ('fecha_actualizacion',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PruebaUsuario)
class PruebaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'prueba', 'progreso_actual', 'completada', 'fecha_completada')
    list_filter = ('completada', 'prueba__arquetipo', 'fecha_completada')
    search_fields = ('perfil__cliente__nombre', 'prueba__nombre')
    raw_id_fields = ('perfil', 'prueba')
    readonly_fields = ('fecha_completada',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('perfil__cliente', 'prueba__arquetipo')


@admin.register(TipoQuest)
class TipoQuestAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'icono')
    search_fields = ('nombre', 'descripcion')


@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'periodo', 'puntos_recompensa', 'activa', 'fecha_creacion')
    list_filter = ('tipo', 'periodo', 'activa', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    ordering = ('-fecha_creacion',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'tipo')
        }),
        ('Configuración', {
            'fields': ('periodo', 'puntos_recompensa', 'activa')
        }),
    )


@admin.register(QuestUsuario)
class QuestUsuarioAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'quest', 'progreso_actual', 'completada', 'fecha_inicio', 'fecha_completada')
    list_filter = ('completada', 'quest__periodo', 'fecha_inicio')
    search_fields = ('perfil__cliente__nombre', 'quest__nombre')
    raw_id_fields = ('perfil', 'quest')
    readonly_fields = ('fecha_inicio', 'fecha_completada')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('perfil__cliente', 'quest')


@admin.register(HistorialPuntos)
class HistorialPuntosAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'puntos', 'fecha', 'descripcion', 'get_fuente')
    list_filter = ('fecha', 'puntos')
    search_fields = ('perfil__cliente__nombre', 'descripcion')
    raw_id_fields = ('perfil', 'entreno', 'prueba_legendaria', 'quest')
    readonly_fields = ('fecha',)
    ordering = ('-fecha',)

    def get_fuente(self, obj):
        if obj.prueba_legendaria:
            return f"Prueba: {obj.prueba_legendaria.nombre}"
        elif obj.quest:
            return f"Quest: {obj.quest.nombre}"
        elif obj.entreno:
            return f"Entreno: {obj.entreno.id}"
        return "Actividad general"

    get_fuente.short_description = "Fuente"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'perfil__cliente', 'prueba_legendaria', 'quest', 'entreno'
        )


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'tipo', 'titulo', 'leida', 'fecha_creacion')
    list_filter = ('tipo', 'leida', 'fecha_creacion')
    search_fields = ('perfil__cliente__nombre', 'titulo', 'mensaje')
    raw_id_fields = ('perfil',)
    readonly_fields = ('fecha_creacion',)
    ordering = ('-fecha_creacion',)

    actions = ['marcar_como_leidas', 'marcar_como_no_leidas']

    def marcar_como_leidas(self, request, queryset):
        updated = queryset.update(leida=True)
        self.message_user(request, f'{updated} notificaciones marcadas como leídas.')

    marcar_como_leidas.short_description = "Marcar seleccionadas como leídas"

    def marcar_como_no_leidas(self, request, queryset):
        updated = queryset.update(leida=False)
        self.message_user(request, f'{updated} notificaciones marcadas como no leídas.')

    marcar_como_no_leidas.short_description = "Marcar seleccionadas como no leídas"


@admin.register(Liga)
class LigaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'puntos_minimos', 'puntos_maximos', 'icono']
    list_filter = ['nombre']
    ordering = ['puntos_minimos']


@admin.register(Temporada)
class TemporadaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'fecha_inicio', 'fecha_fin', 'activa']
    list_filter = ['tipo', 'activa']
    ordering = ['-fecha_inicio']


@admin.register(RankingEntry)
class RankingEntryAdmin(admin.ModelAdmin):
    list_display = ['perfil', 'tipo_ranking', 'posicion', 'valor', 'temporada']
    list_filter = ['tipo_ranking', 'temporada']
    ordering = ['posicion']


@admin.register(TituloEspecial)
class TituloEspecialAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'icono', 'condicion_tipo', 'condicion_valor', 'es_temporal']
    list_filter = ['es_temporal', 'condicion_tipo']


@admin.register(PerfilTitulo)
class PerfilTituloAdmin(admin.ModelAdmin):
    list_display = ['perfil', 'titulo', 'fecha_obtencion', 'activo']
    list_filter = ['activo', 'titulo']
    ordering = ['-fecha_obtencion']

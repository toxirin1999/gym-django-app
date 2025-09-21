from django.contrib import admin
from .models import (
    MetricaRendimiento, AnalisisEjercicio, TendenciaProgresion,
    PrediccionRendimiento, RecomendacionEntrenamiento,
    ComparativaRendimiento, CacheAnalisis
)

@admin.register(MetricaRendimiento)
class MetricaRendimientoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'fecha', 'volumen_total', 'intensidad_promedio', 'entrenamientos_dia']
    list_filter = ['fecha', 'cliente']
    search_fields = ['cliente__nombre']
    date_hierarchy = 'fecha'
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AnalisisEjercicio)
class AnalisisEjercicioAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'nombre_ejercicio', 'fecha', 'peso_maximo', 'one_rm_estimado']
    list_filter = ['fecha', 'nombre_ejercicio', 'completado_exitosamente']
    search_fields = ['cliente__nombre', 'nombre_ejercicio']
    date_hierarchy = 'fecha'

@admin.register(TendenciaProgresion)
class TendenciaProgresionAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'nombre_ejercicio', 'tipo_tendencia', 'velocidad_progresion', 'consistencia']
    list_filter = ['tipo_tendencia', 'fecha_fin']
    search_fields = ['cliente__nombre', 'nombre_ejercicio']

@admin.register(PrediccionRendimiento)
class PrediccionRendimientoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'tipo_prediccion', 'valor_predicho', 'fecha_prediccion', 'confianza']
    list_filter = ['tipo_prediccion', 'activa', 'verificada']
    search_fields = ['cliente__nombre', 'nombre_ejercicio']

@admin.register(RecomendacionEntrenamiento)
class RecomendacionEntrenamientoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'titulo', 'tipo', 'prioridad', 'aplicada', 'esta_vigente']
    list_filter = ['tipo', 'prioridad', 'aplicada']
    search_fields = ['cliente__nombre', 'titulo', 'descripcion']
    actions = ['marcar_como_aplicadas']
    
    def marcar_como_aplicadas(self, request, queryset):
        for recomendacion in queryset:
            recomendacion.marcar_como_aplicada()
        self.message_user(request, f"{queryset.count()} recomendaciones marcadas como aplicadas.")
    marcar_como_aplicadas.short_description = "Marcar como aplicadas"

@admin.register(ComparativaRendimiento)
class ComparativaRendimientoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'tipo_comparativa', 'metrica_principal', 'clasificacion', 'percentil']
    list_filter = ['tipo_comparativa', 'clasificacion', 'significancia']
    search_fields = ['cliente__nombre', 'metrica_principal']

@admin.register(CacheAnalisis)
class CacheAnalisisAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'tipo_analisis', 'tiempo_calculo', 'datos_utilizados', 'esta_vigente']
    list_filter = ['tipo_analisis', 'expires_at']
    search_fields = ['cliente__nombre', 'tipo_analisis']
    readonly_fields = ['parametros_hash', 'tiempo_calculo', 'created_at']
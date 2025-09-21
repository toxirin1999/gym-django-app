from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    EntrenoRealizado,
    EjercicioRealizado,
    DetalleEjercicioRealizado,
    SerieRealizada,
    DatosLiftinDetallados,
    LogroDesbloqueado
)


# ✅ CORRECCIÓN 1: Inline de EjercicioRealizado ACTIVADO
class EjercicioRealizadoInline(admin.TabularInline):
    model = EjercicioRealizado
    extra = 0
    fields = ['nombre_ejercicio', 'grupo_muscular', 'peso_kg', 'series', 'repeticiones', 'completado']
    readonly_fields = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('entreno')


# ✅ CORRECCIÓN 2: Inline de SerieRealizada (para compatibilidad)
class SerieRealizadaInline(admin.TabularInline):
    model = SerieRealizada
    extra = 0
    fields = ['ejercicio', 'serie_numero', 'repeticiones', 'peso_kg', 'completado']
    readonly_fields = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ejercicio')


@admin.register(EntrenoRealizado)
class EntrenoRealizadoAdmin(admin.ModelAdmin):
    # ✅ CORRECCIÓN 3: Inlines ACTIVADOS
    inlines = [EjercicioRealizadoInline, SerieRealizadaInline]

    list_display = [
        'cliente',
        'fecha',
        'rutina_nombre',
        'fuente_datos_badge',
        'duracion_formateada',
        'volumen_formateado',
        'numero_ejercicios_display',
        'completado_badge'
    ]
    list_filter = ['fuente_datos', 'fecha', 'rutina']
    search_fields = ['cliente__nombre', 'nombre_rutina_liftin', 'rutina__nombre']
    date_hierarchy = 'fecha'

    fieldsets = (
        ('Información Básica', {
            'fields': ('cliente', 'rutina', 'fecha')
        }),
        ('Métricas del Entrenamiento', {
            'fields': ('volumen_total_kg', 'numero_ejercicios', 'duracion_minutos', 'calorias_quemadas'),
            'classes': ('wide',)
        }),
        ('Datos de Liftin', {
            'fields': (
                'fuente_datos',
                'liftin_workout_id',
                'frecuencia_cardiaca_promedio',
                'frecuencia_cardiaca_maxima',
                'notas_liftin',
                'fecha_importacion'
            ),
            'classes': ('collapse',),
            'description': 'Datos específicos importados desde la aplicación Liftin'
        }),
        ('Sistema', {
            'fields': ('procesado_gamificacion',),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ['fecha_importacion']

    # ✅ CORRECCIÓN 4: Métodos de visualización IMPLEMENTADOS
    def rutina_nombre(self, obj):
        if obj.rutina:
            return obj.rutina.nombre
        elif obj.nombre_rutina_liftin:
            return obj.nombre_rutina_liftin
        return "Sin rutina"

    rutina_nombre.short_description = 'Rutina'

    def fuente_datos_badge(self, obj):
        if obj.fuente_datos == 'liftin':
            return format_html(
                '<span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">📱 LIFTIN</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">✏️ MANUAL</span>'
            )

    fuente_datos_badge.short_description = 'Fuente'

    def duracion_formateada(self, obj):
        return obj.duracion_formateada

    duracion_formateada.short_description = 'Duración'

    def volumen_formateado(self, obj):
        if obj.volumen_total_kg:
            return f"{obj.volumen_total_kg} kg"
        return "No calculado"

    volumen_formateado.short_description = 'Volumen Total'

    def numero_ejercicios_display(self, obj):
        # Contar ejercicios de ambos modelos para compatibilidad
        ejercicios_realizados = obj.ejercicios_realizados.count()
        series_agrupadas = obj.series.values('ejercicio').distinct().count()

        total = max(ejercicios_realizados, series_agrupadas)
        if obj.numero_ejercicios:
            total = max(total, obj.numero_ejercicios)

        return f"{total} ejercicios"

    numero_ejercicios_display.short_description = 'Ejercicios'

    def completado_badge(self, obj):
        # Verificar si hay ejercicios completados
        ejercicios_completados = obj.ejercicios_realizados.filter(completado=True).count()
        total_ejercicios = obj.ejercicios_realizados.count()

        if total_ejercicios == 0:
            # Verificar en series si no hay ejercicios
            series_completadas = obj.series.filter(completado=True).count()
            total_series = obj.series.count()
            if total_series > 0:
                porcentaje = (series_completadas / total_series) * 100
            else:
                porcentaje = 0
        else:
            porcentaje = (ejercicios_completados / total_ejercicios) * 100

        if porcentaje == 100:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">✅ COMPLETO</span>'
            )
        elif porcentaje > 0:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 2px 6px; border-radius: 3px; font-size: 10px;">⚠️ PARCIAL</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">❌ INCOMPLETO</span>'
            )

    completado_badge.short_description = 'Estado'

    actions = ['marcar_como_liftin', 'marcar_como_manual', 'recalcular_volumen']

    def marcar_como_liftin(self, request, queryset):
        updated = queryset.update(fuente_datos='liftin')
        self.message_user(request, f'{updated} entrenamientos marcados como de Liftin.')

    marcar_como_liftin.short_description = "Marcar como datos de Liftin"

    def marcar_como_manual(self, request, queryset):
        updated = queryset.update(fuente_datos='manual')
        self.message_user(request, f'{updated} entrenamientos marcados como manuales.')

    marcar_como_manual.short_description = "Marcar como datos manuales"

    def recalcular_volumen(self, request, queryset):
        from decimal import Decimal
        updated = 0
        for entreno in queryset:
            volumen_total = Decimal('0.0')

            # Calcular desde EjercicioRealizado
            for ejercicio in entreno.ejercicios_realizados.all():
                volumen_total += Decimal(str(ejercicio.peso_kg)) * ejercicio.series * ejercicio.repeticiones

            # Si no hay datos en EjercicioRealizado, calcular desde SerieRealizada
            if volumen_total == 0:
                for serie in entreno.series.all():
                    volumen_total += serie.peso_kg * serie.repeticiones

            entreno.volumen_total_kg = volumen_total
            entreno.save(update_fields=['volumen_total_kg'])
            updated += 1

        self.message_user(request, f'Volumen recalculado para {updated} entrenamientos.')

    recalcular_volumen.short_description = "Recalcular volumen total"


# ✅ CORRECCIÓN 5: Registro independiente de EjercicioRealizado
@admin.register(EjercicioRealizado)
class EjercicioRealizadoAdmin(admin.ModelAdmin):
    list_display = [
        'entreno_info',
        'nombre_ejercicio',
        'grupo_muscular',
        'peso_kg',
        'series',
        'repeticiones',
        'volumen_total',
        'completado_badge'
    ]
    list_filter = [
        'grupo_muscular',
        'completado',
        'fuente_datos',
        'entreno__fecha',
        'entreno__cliente'
    ]
    search_fields = [
        'nombre_ejercicio',
        'entreno__cliente__nombre',
        'grupo_muscular'
    ]
    date_hierarchy = 'entreno__fecha'

    fieldsets = (
        ('Información del Ejercicio', {
            'fields': ('entreno', 'nombre_ejercicio', 'grupo_muscular')
        }),
        ('Datos de Rendimiento', {
            'fields': ('peso_kg', 'series', 'repeticiones', 'completado'),
            'classes': ('wide',)
        }),
        ('Metadatos', {
            'fields': ('fuente_datos',),
            'classes': ('collapse',)
        })
    )

    def entreno_info(self, obj):
        return f"{obj.entreno.cliente.nombre} - {obj.entreno.fecha}"

    entreno_info.short_description = 'Entrenamiento'

    def volumen_total(self, obj):
        volumen = obj.peso_kg * obj.series * obj.repeticiones
        return f"{volumen} kg"

    volumen_total.short_description = 'Volumen'

    def completado_badge(self, obj):
        if obj.completado:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">✅</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">❌</span>'
            )

    completado_badge.short_description = 'Completado'


@admin.register(DetalleEjercicioRealizado)
class DetalleEjercicioRealizadoAdmin(admin.ModelAdmin):
    list_display = [
        'entreno',
        'ejercicio',
        'series',
        'repeticiones',
        'peso_kg',
        'completado'
    ]
    list_filter = ['completado', 'ejercicio', 'entreno__fuente_datos']
    search_fields = ['ejercicio__nombre', 'entreno__cliente__nombre']


@admin.register(SerieRealizada)
class SerieRealizadaAdmin(admin.ModelAdmin):
    list_display = [
        'entreno_info',
        'ejercicio_nombre',
        'serie_numero',
        'repeticiones',
        'peso_kg',
        'volumen_serie',
        'completado_badge'
    ]
    list_filter = ['completado', 'ejercicio', 'entreno__fuente_datos', 'entreno__fecha']
    search_fields = ['ejercicio__nombre', 'entreno__cliente__nombre']
    date_hierarchy = 'entreno__fecha'

    def entreno_info(self, obj):
        return f"{obj.entreno.cliente.nombre} - {obj.entreno.fecha}"

    entreno_info.short_description = 'Entrenamiento'

    def ejercicio_nombre(self, obj):
        return obj.ejercicio.nombre if obj.ejercicio else "Sin ejercicio"

    ejercicio_nombre.short_description = 'Ejercicio'

    def volumen_serie(self, obj):
        volumen = obj.peso_kg * obj.repeticiones
        return f"{volumen} kg"

    volumen_serie.short_description = 'Volumen'

    def completado_badge(self, obj):
        if obj.completado:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">✅</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">❌</span>'
            )

    completado_badge.short_description = 'Completado'


@admin.register(DatosLiftinDetallados)
class DatosLiftinDetalladosAdmin(admin.ModelAdmin):
    list_display = [
        'entreno',
        'version_liftin',
        'dispositivo_origen',
        'sincronizado_health',
        'fecha_creacion'
    ]
    list_filter = ['sincronizado_health', 'version_liftin', 'dispositivo_origen', 'fecha_creacion']
    search_fields = ['entreno__cliente__nombre', 'health_workout_uuid', 'version_liftin']

    fieldsets = (
        ('Entrenamiento Asociado', {
            'fields': ('entreno',)
        }),
        ('Datos de Liftin', {
            'fields': (
                'version_liftin',
                'dispositivo_origen',
                'datos_frecuencia_cardiaca',
                'metadatos_adicionales'
            )
        }),
        ('Sincronización con Apple Health', {
            'fields': (
                'sincronizado_health',
                'health_workout_uuid'
            ),
            'classes': ('collapse',)
        }),
        ('Información del Sistema', {
            'fields': (
                'fecha_creacion',
                'fecha_actualizacion'
            ),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']


@admin.register(LogroDesbloqueado)
class LogroDesbloqueadoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'nombre', 'descripcion', 'fecha']
    list_filter = ['fecha', 'cliente']
    search_fields = ['cliente__nombre', 'nombre', 'descripcion']


# Personalización del admin site
admin.site.site_header = "Gym Project - Administración"
admin.site.site_title = "Gym Project Admin"
admin.site.index_title = "Panel de Administración del Gimnasio"

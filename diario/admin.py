from django.contrib import admin
from .models import (
    ProsocheMes, ProsocheSemana, ProsocheDiario, ProsocheHabito, ProsocheHabitoDia,
    AreaVida, Eudaimonia, TrimestreEudaimonia,
    EjercicioArete, Gnosis, EntrenamientoSemanal,
    SeguimientoVires, EventoKairos, PlanificacionDiaria
)


# ========================================
# PROSOCHE - ADMINISTRACIÓN
# ========================================

class ProsocheSemanaInline(admin.TabularInline):
    model = ProsocheSemana
    extra = 0
    fields = ('numero_semana', 'objetivo_1', 'objetivo_2', 'objetivo_3',
              'objetivo_1_completado', 'objetivo_2_completado', 'objetivo_3_completado')


class ProsocheDiarioInline(admin.TabularInline):
    model = ProsocheDiario
    extra = 0
    fields = ('fecha', 'entrada', 'estado_animo', 'etiquetas')
    readonly_fields = ('fecha_creacion',)


class ProsocheHabitoInline(admin.TabularInline):
    model = ProsocheHabito
    extra = 0
    fields = ('nombre', 'descripcion', 'color')


@admin.register(ProsocheMes)
class ProsocheMesAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'mes', 'año', 'fecha_creacion', 'objetivos_completados')
    list_filter = ('año', 'mes', 'fecha_creacion')
    search_fields = ('usuario__username', 'mes')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')

    fieldsets = (
        ('Información General', {'fields': ('usuario', 'mes', 'año')}),
        ('Objetivos del Mes', {'fields': (
            ('objetivo_mes_1', 'objetivo_mes_1_completado'), ('objetivo_mes_2', 'objetivo_mes_2_completado'),
            ('objetivo_mes_3', 'objetivo_mes_3_completado'))}),
        ('Revisión del Mes',
         {'fields': ('logro_principal', 'obstaculo_principal', 'aprendizaje_principal', 'momento_felicidad'),
          'classes': ('collapse',)}),
        ('Fechas', {'fields': ('fecha_creacion', 'fecha_actualizacion'), 'classes': ('collapse',)})
    )

    inlines = [ProsocheSemanaInline, ProsocheDiarioInline, ProsocheHabitoInline]

    def objetivos_completados(self, obj):
        completados = sum([obj.objetivo_mes_1_completado, obj.objetivo_mes_2_completado, obj.objetivo_mes_3_completado])
        return f"{completados}/3"

    objetivos_completados.short_description = "Objetivos Completados"


@admin.register(ProsocheSemana)
class ProsocheSemanaAdmin(admin.ModelAdmin):
    list_display = ('prosoche_mes', 'numero_semana', 'objetivos_completados')
    list_filter = ('numero_semana', 'prosoche_mes__año', 'prosoche_mes__mes')
    search_fields = ('prosoche_mes__usuario__username',)

    def objetivos_completados(self, obj):
        completados = sum([obj.objetivo_1_completado, obj.objetivo_2_completado, obj.objetivo_3_completado])
        return f"{completados}/3"

    objetivos_completados.short_description = "Objetivos Completados"


@admin.register(ProsocheDiario)
class ProsocheDiarioAdmin(admin.ModelAdmin):
    list_display = ('prosoche_mes', 'fecha', 'estado_animo', 'etiquetas_display')
    list_filter = ('estado_animo', 'fecha', 'prosoche_mes__año', 'prosoche_mes__mes')
    search_fields = ('prosoche_mes__usuario__username', 'entrada', 'etiquetas')
    date_hierarchy = 'fecha'
    readonly_fields = ('fecha_creacion',)

    def etiquetas_display(self, obj):
        if obj.etiquetas:
            return ', '.join(obj.etiquetas.split(',')[:3])
        return '-'

    etiquetas_display.short_description = "Etiquetas"


class ProsocheHabitoDiaInline(admin.TabularInline):
    model = ProsocheHabitoDia
    extra = 0
    fields = ('dia', 'completado', 'notas')


@admin.register(ProsocheHabito)
class ProsocheHabitoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'prosoche_mes', 'color', 'dias_completados', 'porcentaje_completado')
    list_filter = ('prosoche_mes__año', 'prosoche_mes__mes')
    search_fields = ('nombre', 'prosoche_mes__usuario__username')
    readonly_fields = ('fecha_creacion',)
    inlines = [ProsocheHabitoDiaInline]

    def dias_completados(self, obj):
        return obj.dias.filter(completado=True).count()

    dias_completados.short_description = "Días Completados"

    def porcentaje_completado(self, obj):
        total_dias = obj.dias.count()
        if total_dias == 0: return "0%"
        completados = obj.dias.filter(completado=True).count()
        porcentaje = round((completados / total_dias) * 100)
        return f"{porcentaje}%"

    porcentaje_completado.short_description = "% Completado"


@admin.register(ProsocheHabitoDia)
class ProsocheHabitoDiaAdmin(admin.ModelAdmin):
    list_display = ('habito', 'dia', 'completado', 'fecha_actualizacion')
    list_filter = ('completado', 'dia', 'habito__prosoche_mes__año')
    search_fields = ('habito__nombre', 'habito__prosoche_mes__usuario__username')
    readonly_fields = ('fecha_actualizacion',)


# ========================================
# EUDAIMONIA - ADMINISTRACIÓN
# ========================================

@admin.register(AreaVida)
class AreaVidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion_corta', 'color', 'icono')
    search_fields = ('nombre', 'descripcion')

    def descripcion_corta(self, obj):
        if obj.descripcion:
            return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion
        return '-'

    descripcion_corta.short_description = "Descripción"


@admin.register(Eudaimonia)
class EudaimoniaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'area', 'puntuacion', 'prioridad', 'fecha_actualizacion')
    list_filter = ('prioridad', 'puntuacion', 'area')
    search_fields = ('usuario__username', 'area__nombre')
    readonly_fields = ('fecha_actualizacion',)  # Corregido: 'fecha_creacion' no existe


@admin.register(TrimestreEudaimonia)
class TrimestreEudaimoniaAdmin(admin.ModelAdmin):
    list_display = ('eudaimonia', 'trimestre', 'año', 'estado', 'fecha_inicio', 'fecha_fin')  # Corregido
    list_filter = ('trimestre', 'año', 'estado')
    search_fields = ('eudaimonia__usuario__username', 'eudaimonia__area__nombre')


# ========================================
# ARETÉ - ADMINISTRACIÓN
# ========================================

@admin.register(EjercicioArete)
class EjercicioAreteAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'usuario', 'estado', 'numero_orden', 'fecha_completado')  # Corregido: 'titulo' -> 'nombre'
    list_filter = ('estado',)  # Corregido: 'virtudes' no existe
    search_fields = ('nombre', 'usuario__username', 'descripcion')  # Corregido: 'titulo' -> 'nombre'
    # Corregido: 'fecha_creacion' no existe


# ========================================
# GNOSIS - ADMINISTRACIÓN
# ========================================

@admin.register(Gnosis)
class GnosisAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario', 'categoria', 'estado', 'puntuacion', 'fecha_creacion')
    list_filter = ('categoria', 'estado', 'puntuacion')
    search_fields = ('titulo', 'autor', 'usuario__username', 'tematica')
    readonly_fields = ('fecha_creacion',)


# ========================================
# VIRES - ADMINISTRACIÓN
# ========================================

@admin.register(EntrenamientoSemanal)
class EntrenamientoSemanalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'semana_inicio', 'tipo', 'fecha_creacion')  # Corregido
    list_filter = ('tipo', 'semana_inicio')  # Corregido
    search_fields = ('usuario__username',)
    date_hierarchy = 'semana_inicio'


@admin.register(SeguimientoVires)
class SeguimientoViresAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha', 'peso', 'entrenamiento_realizado', 'alimentacion_saludable')
    list_filter = ('entrenamiento_realizado', 'alimentacion_saludable', 'hidratacion_adecuada', 'descanso_suficiente')
    search_fields = ('usuario__username',)
    date_hierarchy = 'fecha'


# ========================================
# KAIROS - ADMINISTRACIÓN
# ========================================

@admin.register(EventoKairos)
class EventoKairosAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario', 'tipo', 'fecha_inicio', 'todo_el_dia', 'recordatorio')
    list_filter = ('tipo', 'todo_el_dia', 'recordatorio')
    search_fields = ('titulo', 'usuario__username', 'descripcion')
    date_hierarchy = 'fecha_inicio'


@admin.register(PlanificacionDiaria)
class PlanificacionDiariaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha', 'hora', 'actividad', 'completado')  # Corregido
    list_filter = ('completado', 'fecha')  # Corregido
    search_fields = ('usuario__username', 'actividad')
    date_hierarchy = 'fecha'

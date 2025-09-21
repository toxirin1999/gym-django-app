# rutinas/admin.py

from django.contrib import admin
from .models import Programa, Rutina, EjercicioBase, Asignacion, RutinaEjercicio


# ------------------------------------------------------------------
# VERSIÓN CORREGIDA DE TODO EL ARCHIVO
# ------------------------------------------------------------------

@admin.register(Programa)
class ProgramaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'fecha_creacion')
    search_fields = ('nombre',)


# ### PASO 1: Definimos el 'inline' para la relación Rutina-Ejercicio
class RutinaEjercicioInline(admin.TabularInline):
    model = RutinaEjercicio
    extra = 1  # Cuántos campos vacíos para añadir ejercicios nuevos se muestran
    # autocomplete_fields = ['ejercicio']  # Facilita la búsqueda de ejercicios


@admin.register(Rutina)
class RutinaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'programa', 'orden')
    list_filter = ('programa',)
    search_fields = ('nombre',)
    # ### PASO 2: Reemplazamos 'filter_horizontal' con el 'inline'
    # inlines = [RutinaEjercicioInline]


@admin.register(EjercicioBase)
class EjercicioBaseAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'grupo_muscular', 'equipo')
    search_fields = ('nombre',)  # Necesario para el autocomplete_fields de arriba
    list_filter = ('grupo_muscular', 'equipo')


@admin.register(RutinaEjercicio)
class RutinaEjercicioAdmin(admin.ModelAdmin):
    list_display = ('rutina', 'ejercicio', 'series', 'repeticiones')
    list_filter = ('rutina__programa', 'rutina')
    # autocomplete_fields = ['rutina', 'ejercicio']


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'programa')
    search_fields = ('cliente__nombre', 'programa__nombre')
    autocomplete_fields = ['cliente', 'programa']

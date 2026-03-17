from django.contrib import admin
from .models import EstiramientoEjercicio, EstiramientoPlan, EstiramientoPaso


@admin.register(EstiramientoEjercicio)
class EstiramientoEjercicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fase_recomendada", "musculo_objetivo", "activo")
    list_filter = ("fase_recomendada", "activo")
    search_fields = ("nombre", "musculo_objetivo")


class PasoInline(admin.TabularInline):
    model = EstiramientoPaso
    extra = 0
    autocomplete_fields = ("ejercicio",)


@admin.register(EstiramientoPlan)
class EstiramientoPlanAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fase", "transicion_segundos", "activo")
    list_filter = ("fase", "activo")
    inlines = [PasoInline]

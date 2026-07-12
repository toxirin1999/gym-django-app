from django.contrib import admin

from .models import RegistroDisponibilidad


@admin.register(RegistroDisponibilidad)
class RegistroDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'timestamp', 'nivel', 'origen')
    list_filter = ('nivel',)
    date_hierarchy = 'timestamp'

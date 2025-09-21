# en estoico/admin.py

from django.contrib import admin
from .models import (
    ContenidoDiario,
    PerfilEstoico,
    ReflexionDiaria,
    LogroEstoico,
    LogroUsuario,
    EstadisticaUsuario,
    ConfiguracionNotificacion
)


# --- Configuración para ContenidoDiario ---
@admin.register(ContenidoDiario)
class ContenidoDiarioAdmin(admin.ModelAdmin):
    list_display = ('dia', 'mes', 'tema', 'autor')  # Columnas que se verán en la lista
    list_filter = ('mes', 'autor', 'tema')  # Filtros en la barra lateral derecha
    search_fields = ('cita', 'reflexion', 'pregunta', 'tema')  # Campos por los que se puede buscar
    ordering = ('dia',)  # Ordenar por el día del año


# --- Configuración para ReflexionDiaria ---
@admin.register(ReflexionDiaria)
class ReflexionDiariaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha', 'contenido_dia', 'calificacion_dia', 'marcado_favorito')
    list_filter = ('usuario', 'fecha', 'marcado_favorito', 'calificacion_dia')
    search_fields = ('reflexion_personal',)
    autocomplete_fields = ['usuario', 'contenido_dia']  # Mejora la selección de usuario y contenido


# --- Configuración para PerfilEstoico ---
@admin.register(PerfilEstoico)
class PerfilEstoicoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha_inicio', 'dias_consecutivos', 'total_reflexiones', 'filosofo_favorito')
    search_fields = ('usuario__username',)


# --- Configuración para LogroEstoico (el tipo de logro) ---
@admin.register(LogroEstoico)
class LogroEstoicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'criterio_valor', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre', 'descripcion')


# --- Configuración para LogroUsuario (qué logros tiene cada usuario) ---
@admin.register(LogroUsuario)
class LogroUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'logro', 'fecha_obtenido', 'visto')
    list_filter = ('usuario', 'logro', 'visto')
    autocomplete_fields = ['usuario', 'logro']


# --- Configuración para EstadisticaUsuario ---
@admin.register(EstadisticaUsuario)
class EstadisticaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'racha_actual', 'racha_maxima', 'dias_activos', 'promedio_calificacion')
    search_fields = ('usuario__username',)


# --- Configuración para ConfiguracionNotificacion ---
@admin.register(ConfiguracionNotificacion)
class ConfiguracionNotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'notificacion_matutina', 'hora_matutina', 'notificacion_vespertina', 'hora_vespertina')
    search_fields = ('usuario__username',)

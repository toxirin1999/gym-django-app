from django.contrib import admin
from .models import (
    UserProfile, CalculoNivel1, CalculoNivel2, ProgresoNivel,
    SeguimientoPeso, ConfiguracionNivel3, ConfiguracionNivel4, ConfiguracionNivel5
)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'edad', 'sexo', 'peso', 'altura', 'objetivo', 'fecha_creacion')
    list_filter = ('sexo', 'objetivo', 'nivel_actividad', 'experiencia')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('fecha_creacion',)
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Información Personal', {
            'fields': ('edad', 'sexo', 'peso', 'altura')
        }),
        ('Objetivos y Actividad', {
            'fields': ('nivel_actividad', 'objetivo', 'experiencia')
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion',),
            'classes': ('collapse',)
        }),
    )

@admin.register(CalculoNivel1)
class CalculoNivel1Admin(admin.ModelAdmin):
    list_display = ('user_profile', 'calorias_mantenimiento', 'calorias_objetivo', 'deficit_superavit_porcentaje', 'fecha_calculo')
    list_filter = ('metodo_calculo', 'fecha_calculo')
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('fecha_calculo',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_profile__user')

@admin.register(CalculoNivel2)
class CalculoNivel2Admin(admin.ModelAdmin):
    list_display = ('user_profile', 'proteina_gramos', 'grasa_gramos', 'carbohidratos_gramos', 'fecha_calculo')
    list_filter = ('fecha_calculo',)
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('fecha_calculo',)
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user_profile',)
        }),
        ('Macronutrientes (Gramos)', {
            'fields': ('proteina_gramos', 'grasa_gramos', 'carbohidratos_gramos')
        }),
        ('Macronutrientes (Calorías)', {
            'fields': ('proteina_calorias', 'grasa_calorias', 'carbohidratos_calorias')
        }),
        ('Macronutrientes (Porcentajes)', {
            'fields': ('proteina_porcentaje', 'grasa_porcentaje', 'carbohidratos_porcentaje')
        }),
        ('Metadatos', {
            'fields': ('fecha_calculo',),
            'classes': ('collapse',)
        }),
    )

@admin.register(ProgresoNivel)
class ProgresoNivelAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'nivel', 'completado', 'fecha_completado')
    list_filter = ('nivel', 'completado', 'fecha_completado')
    search_fields = ('user_profile__user__username',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_profile__user')

@admin.register(SeguimientoPeso)
class SeguimientoPesoAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'peso', 'fecha_registro', 'tiene_notas')
    list_filter = ('fecha_registro',)
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('fecha_registro',)
    
    def tiene_notas(self, obj):
        return bool(obj.notas)
    tiene_notas.boolean = True
    tiene_notas.short_description = 'Tiene notas'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_profile__user')

@admin.register(ConfiguracionNivel3)
class ConfiguracionNivel3Admin(admin.ModelAdmin):
    list_display = ('user_profile', 'agua_litros', 'frutas_porciones', 'verduras_porciones', 'fecha_configuracion')
    list_filter = ('fecha_configuracion',)
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('fecha_configuracion',)

@admin.register(ConfiguracionNivel4)
class ConfiguracionNivel4Admin(admin.ModelAdmin):
    list_display = ('user_profile', 'comidas_por_dia', 'refeeds_configurados', 'fecha_configuracion')
    list_filter = ('refeeds_configurados', 'fecha_configuracion')
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('fecha_configuracion',)

@admin.register(ConfiguracionNivel5)
class ConfiguracionNivel5Admin(admin.ModelAdmin):
    list_display = ('user_profile', 'creatina', 'proteina_polvo', 'multivitaminico', 'omega3', 'vitamina_d', 'fecha_configuracion')
    list_filter = ('creatina', 'proteina_polvo', 'multivitaminico', 'omega3', 'vitamina_d', 'fecha_configuracion')
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('fecha_configuracion',)
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user_profile',)
        }),
        ('Suplementos Básicos', {
            'fields': ('creatina', 'proteina_polvo', 'multivitaminico')
        }),
        ('Suplementos Adicionales', {
            'fields': ('omega3', 'vitamina_d')
        }),
        ('Otros', {
            'fields': ('otros_suplementos',)
        }),
        ('Metadatos', {
            'fields': ('fecha_configuracion',),
            'classes': ('collapse',)
        }),
    )

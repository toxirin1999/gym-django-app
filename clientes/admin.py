from django.contrib import admin
from .models import Cliente


# =================================================================
# ### CÓDIGO CORREGIDO Y VERIFICADO PARA ESTE ARCHIVO ###
# =================================================================
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """
    Configuración para que el modelo Cliente aparezca en el panel de admin.
    """
    # --- CORRECCIÓN ---
    # Eliminamos 'apellido' porque no existe en el modelo.
    # Mostramos campos que sí existen como 'nombre', 'email' y 'membresia_activa'.
    list_display = ('id', 'nombre', 'email', 'telefono', 'membresia_activa', 'objetivo_principal')

    # Hacemos que la lista sea filtrable por estos campos
    list_filter = ('membresia_activa', 'genero', 'objetivo_principal')

    # --- CORRECCIÓN ---
    # Eliminamos 'apellido' de los campos de búsqueda.
    # Ahora se puede buscar por nombre o email.
    search_fields = ['nombre', 'email']


# =================================================================
from django.contrib import admin
from .models import PesoDiario, ObjetivoPeso


@admin.register(PesoDiario)
class PesoDiarioAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'fecha', 'peso_kg')
    list_filter = ('fecha', 'cliente')
    search_fields = ('cliente__nombre', 'cliente__email')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Si estamos editando un objeto existente
            return ('fecha',)  # La fecha no se puede cambiar una vez creado
        return ()


@admin.register(ObjetivoPeso)
class ObjetivoPesoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'peso_objetivo_kg', 'fecha_inicio', 'fecha_fin', 'alcanzado')
    list_filter = ('alcanzado', 'fecha_inicio', 'cliente')
    search_fields = ('cliente__nombre', 'cliente__email')
    date_hierarchy = 'fecha_inicio'
    ordering = ('-fecha_inicio',)

    actions = ['marcar_como_alcanzado', 'marcar_como_no_alcanzado']

    def marcar_como_alcanzado(self, request, queryset):
        queryset.update(alcanzado=True)
        self.message_user(request, f"{queryset.count()} objetivos marcados como alcanzados.")

    marcar_como_alcanzado.short_description = "Marcar objetivos seleccionados como alcanzados"

    def marcar_como_no_alcanzado(self, request, queryset):
        queryset.update(alcanzado=False)
        self.message_user(request, f"{queryset.count()} objetivos marcados como no alcanzados.")

    marcar_como_no_alcanzado.short_description = "Marcar objetivos seleccionados como no alcanzados"

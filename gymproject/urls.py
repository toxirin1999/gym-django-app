# gymproject/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from clientes import views as clientes_views

urlpatterns = [
    path('diario/', include('diario.urls')),
    # --- Rutas Principales y de Autenticación ---
    path('admin/', admin.site.urls),
    path('', clientes_views.redirigir_usuario, name='home'),
    path('redirigir/', clientes_views.redirigir_usuario, name='redirigir_usuario'),
    path('register/', clientes_views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    # --- Inclusión de Aplicaciones ---
    path('clientes/', include('clientes.urls')),
    path('panel/', clientes_views.dashboard, name='dashboard'),  # Considera mover esto a clientes.urls
    path('mi-panel/', clientes_views.panel_cliente, name='panel_cliente'),  # Considera mover esto a clientes.urls

    path('rutinas/', include('rutinas.urls')),
    path('entrenos/', include('entrenos.urls')),
    path('logros/', include('logros.urls')),  # <-- ÚNICA INCLUSIÓN
    path('joi/', include('joi.urls')),
    path('estoico/', include('estoico.urls')),
    path('analytics/', include('analytics.urls')),
    path('nutricion/', include('nutricion_app_django.urls')),

    # --- APIs ---
    path('api/liftin/', include('entrenos.urls_api')),
]

# --- Configuración para Servir Archivos Estáticos y de Medios en Desarrollo ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Nota: La siguiente línea no suele ser necesaria si usas `runserver` con DEBUG=True,
    # pero no hace daño tenerla.
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

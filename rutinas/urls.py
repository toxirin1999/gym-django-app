from django.urls import path
from . import views

urlpatterns = [
    # Página principal
    path('', views.lista_programas, name='lista_programas'),

    # Programas
    path('programas/agregar/', views.agregar_programa, name='agregar_programa'),
    path('programa/<int:programa_id>/', views.detalle_programa, name='detalle_programa'),
    path('programa/<int:programa_id>/editar/', views.editar_programa, name='editar_programa'),
    path('programa/<int:programa_id>/eliminar/', views.eliminar_programa, name='eliminar_programa'),
    # DESPUÉS (Correcto)
    path("cliente/<int:cliente_id>/asignar-programa/", views.asignar_programa_a_cliente, name="asignar_programa"),

    path('programa/<int:programa_id>/asignar_cliente/', views.asignar_programa_a_cliente,
         name='asignar_programa_a_cliente'),
    path('programa/<int:programa_id>/agregar_rutina/', views.agregar_rutina, name='agregar_rutina'),

    # Ejercicios generales
    path('ejercicios/', views.lista_ejercicios, name='lista_ejercicios'),
    path('ejercicios/agregar/', views.agregar_ejercicio_general, name='agregar_ejercicio_general'),
    # rutinas/urls.py
    path('programas/editar/<int:programa_id>/', views.editar_programa, name='editar_programa'),

    # Cambiar el nombre a algo más descriptivo

    # Rutinas
    path('rutinas/agregar/', views.agregar_rutina, name='agregar_rutina'),
    path('rutinas/<int:rutina_id>/agregar-ejercicio/', views.agregar_ejercicio, name='agregar_ejercicio'),
    path('rutinas/<int:rutina_id>/eliminar/', views.eliminar_rutina, name='eliminar_rutina'),
    path('rutinas/rutina/<int:rutina_id>/', views.detalle_rutina, name='detalle_rutina'),

    # Rutina-Ejercicio edición/eliminación
    path('rutina-ejercicio/<int:pk>/editar/', views.editar_rutina_ejercicio, name='editar_rutina_ejercicio'),
    path('rutina-ejercicio/<int:pk>/eliminar/', views.eliminar_rutina_ejercicio, name='eliminar_rutina_ejercicio'),
]

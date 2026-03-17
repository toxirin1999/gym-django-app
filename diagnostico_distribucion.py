import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from django.db import models
from entrenos.models import EjercicioRealizado
from rutinas.models import EjercicioBase

print("--- DIAGNÓSTICO DE DATOS PARA DISRIBUCIÓN MUSCULAR ---")
total_ej = EjercicioRealizado.objects.count()
con_grupo = EjercicioRealizado.objects.filter(grupo_muscular__isnull=False).exclude(grupo_muscular="").count()
sin_grupo = EjercicioRealizado.objects.filter(models.Q(grupo_muscular__isnull=True) | models.Q(grupo_muscular="")).count()

print(f"Total EjercicioRealizado: {total_ej}")
print(f"Con grupo muscular: {con_grupo}")
print(f"Sin grupo muscular: {sin_grupo}")

if sin_grupo > 0:
    print("\nEjemplos de ejercicios sin grupo:")
    ejemplos = EjercicioRealizado.objects.filter(models.Q(grupo_muscular__isnull=True) | models.Q(grupo_muscular="")).values_list('nombre_ejercicio', flat=True).distinct()[:10]
    for e in ejemplos:
        print(f"- {e}")

print(f"\nTotal EjercicioBase registrados: {EjercicioBase.objects.count()}")

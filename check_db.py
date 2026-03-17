import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from django.db import models
from entrenos.models import EjercicioRealizado
from rutinas.models import EjercicioBase

print("--- DIAGNÓSTICO DE DATOS PARA DISRIBUCIÓN MUSCULAR ---")
total_ej = EjercicioRealizado.objects.count()
con_grupo = EjercicioRealizado.objects.exclude(grupo_muscular__isnull=True).exclude(grupo_muscular="").count()
sin_grupo = EjercicioRealizado.objects.filter(models.Q(grupo_muscular__isnull=True) | models.Q(grupo_muscular="")).count()

print(f"Total EjercicioRealizado: {total_ej}")
print(f"Con grupo muscular: {con_grupo}")
print(f"Sin grupo muscular: {sin_grupo}")

if sin_grupo > 0:
    print("\nEjercicios sin grupo (primeros 20):")
    ejemplos = EjercicioRealizado.objects.filter(models.Q(grupo_muscular__isnull=True) | models.Q(grupo_muscular="")).values('nombre_ejercicio').annotate(count=models.Count('id')).order_by('-count')[:20]
    for e in ejemplos:
        print(f"- {e['nombre_ejercicio']} ({e['count']} veces)")

print(f"\nTotal EjercicioBase registrados: {EjercicioBase.objects.count()}")

# Probar si coinciden
if sin_grupo > 0:
    match_count = 0
    for e in ejemplos:
        if EjercicioBase.objects.filter(nombre__iexact=e['nombre_ejercicio']).exists():
            match_count += 1
    print(f"\nEjercicios sin grupo que TIENEN coincidencia en EjercicioBase: {match_count}")

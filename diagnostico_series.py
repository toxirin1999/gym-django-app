"""
Script de Diagnóstico para el Panel de Series por Grupo Muscular
==================================================================

Ejecutar este script en la consola de Django para diagnosticar el problema:
python manage.py shell < diagnostico_series.py

O copiar y pegar en la consola de Django (python manage.py shell)
"""

from clientes.models import Cliente
from entrenos.services.estadisticas_service import EstadisticasService, MAPEO_MUSCULAR_DYNAMIC
from entrenos.models import EjercicioRealizado, EjercicioLiftinDetallado
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("DIAGNÓSTICO DEL PANEL DE SERIES POR GRUPO MUSCULAR")
print("=" * 80)

# 1. Verificar el mapeo muscular
print("\n1. VERIFICANDO MAPEO MUSCULAR DYNAMIC")
print(f"   Total de ejercicios en el mapeo: {len(MAPEO_MUSCULAR_DYNAMIC)}")
print("\n   Primeros 20 ejercicios del mapeo:")
for i, (ej, grupo) in enumerate(list(MAPEO_MUSCULAR_DYNAMIC.items())[:20]):
    print(f"   {i+1:2d}. '{ej}' -> {grupo}")

# 2. Seleccionar un cliente para analizar
print("\n2. SELECCIONANDO CLIENTE PARA ANÁLISIS")
cliente = Cliente.objects.first()
if not cliente:
    print("   ❌ No hay clientes en la base de datos")
    exit()

print(f"   ✓ Cliente seleccionado: {cliente.nombre} (ID: {cliente.id})")

# 3. Ver ejercicios del cliente en los últimos 30 días
print("\n3. EJERCICIOS DEL CLIENTE (últimos 30 días)")
fecha_inicio = timezone.now().date() - timedelta(days=30)

# Ejercicios manuales
ejs_manuales = EjercicioRealizado.objects.filter(
    entreno__cliente=cliente,
    entreno__fecha__gte=fecha_inicio,
    completado=True
).values('nombre_ejercicio', 'series').distinct()

print(f"\n   Ejercicios Manuales: {len(ejs_manuales)}")
ejercicios_manuales_unicos = set()
for ej in ejs_manuales:
    ejercicios_manuales_unicos.add(ej['nombre_ejercicio'])

for i, nombre in enumerate(sorted(ejercicios_manuales_unicos)[:15], 1):
    nombre_norm = nombre.lower().strip()
    grupo = MAPEO_MUSCULAR_DYNAMIC.get(nombre_norm, '❌ NO MAPEADO')
    print(f"   {i:2d}. '{nombre}'")
    print(f"       -> normalizado: '{nombre_norm}'")
    print(f"       -> grupo: {grupo}")

# Ejercicios Liftin
ejs_liftin = EjercicioLiftinDetallado.objects.filter(
    entreno__cliente=cliente,
    entreno__fecha__gte=fecha_inicio,
    completado=True
).values('nombre_ejercicio', 'series_realizadas').distinct()

print(f"\n   Ejercicios Liftin: {len(ejs_liftin)}")
ejercicios_liftin_unicos = set()
for ej in ejs_liftin:
    ejercicios_liftin_unicos.add(ej['nombre_ejercicio'])

for i, nombre in enumerate(sorted(ejercicios_liftin_unicos)[:15], 1):
    nombre_norm = nombre.lower().strip()
    grupo = MAPEO_MUSCULAR_DYNAMIC.get(nombre_norm, '❌ NO MAPEADO')
    print(f"   {i:2d}. '{nombre}'")
    print(f"       -> normalizado: '{nombre_norm}'")
    print(f"       -> grupo: {grupo}")

# 4. Ejecutar el análisis de volumen óptimo
print("\n4. EJECUTANDO ANÁLISIS DE VOLUMEN ÓPTIMO")
print("   (Revisa los logs del servidor para ver los detalles)")

resultado = EstadisticasService.analizar_volumen_optimo(cliente, '30d')

print("\n   RESULTADO DEL ANÁLISIS:")
print(f"   Rango: 30 días")
print(f"   Grupos analizados: {len(resultado['labels'])}")
print("\n   Series por semana por grupo muscular:")
for i, grupo in enumerate(resultado['labels']):
    series = resultado['series_reales'][i]
    min_rec = resultado['min_recomendado']
    max_rec = resultado['max_recomendado']
    
    # Indicador visual
    if series == 0:
        indicador = "⚠️  SIN DATOS"
    elif series < min_rec:
        indicador = "📉 BAJO"
    elif series > max_rec:
        indicador = "📈 ALTO"
    else:
        indicador = "✅ ÓPTIMO"
    
    print(f"   {grupo:15s}: {series:6.1f} series/semana  {indicador}")

# 5. Verificar ejercicios no mapeados
if 'ejercicios_no_mapeados' in resultado and resultado['ejercicios_no_mapeados']:
    print("\n5. ⚠️  EJERCICIOS NO MAPEADOS DETECTADOS:")
    print(f"   Total: {len(resultado['ejercicios_no_mapeados'])}")
    for i, nombre in enumerate(resultado['ejercicios_no_mapeados'][:10], 1):
        print(f"   {i:2d}. '{nombre}'")
    
    if len(resultado['ejercicios_no_mapeados']) > 10:
        print(f"   ... y {len(resultado['ejercicios_no_mapeados']) - 10} más")
else:
    print("\n5. ✅ TODOS LOS EJERCICIOS ESTÁN CORRECTAMENTE MAPEADOS")

# 6. Resumen y recomendaciones
print("\n" + "=" * 80)
print("RESUMEN Y RECOMENDACIONES")
print("=" * 80)

total_series = sum(resultado['series_reales'])
grupos_con_datos = sum(1 for s in resultado['series_reales'] if s > 0)

print(f"\n✓ Total de series/semana: {total_series:.1f}")
print(f"✓ Grupos musculares con datos: {grupos_con_datos}/{len(resultado['labels'])}")

if grupos_con_datos == 0:
    print("\n❌ PROBLEMA CRÍTICO: No hay datos en ningún grupo muscular")
    print("   Posibles causas:")
    print("   1. No hay ejercicios completados en los últimos 30 días")
    print("   2. Todos los ejercicios están siendo mapeados a 'Otros'")
    print("   3. Los nombres de ejercicios no coinciden con el mapeo")
elif grupos_con_datos < len(resultado['labels']) / 2:
    print("\n⚠️  ADVERTENCIA: Pocos grupos musculares tienen datos")
    print("   Revisa los ejercicios no mapeados arriba")
else:
    print("\n✅ Los datos parecen estar correctos")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO")
print("=" * 80)

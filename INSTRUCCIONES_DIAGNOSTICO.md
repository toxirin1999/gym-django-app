# Instrucciones para Ejecutar el Diagnóstico

## Opción 1: Ejecutar el Script de Diagnóstico (Recomendado)

Abre una terminal en el directorio del proyecto y ejecuta:

```bash
# Activar el entorno virtual primero
.venv\Scripts\activate

# Ejecutar el script de diagnóstico
python manage.py shell
```

Luego, dentro de la consola de Django, copia y pega el contenido del archivo `diagnostico_series.py`.

## Opción 2: Ver los Logs en Tiempo Real

1. **Inicia el servidor de desarrollo** (si no está corriendo):
   ```bash
   python manage.py runserver
   ```

2. **Accede al dashboard de evolución** de un cliente en tu navegador:
   ```
   http://localhost:8000/entrenos/cliente/<ID_CLIENTE>/dashboard-evolucion/
   ```

3. **Observa los logs** en la terminal donde corre el servidor. Deberías ver mensajes como:
   ```
   [Cliente X] Rango: 30d, Semanas: 4.3
   [Cliente X] Series totales por grupo: {'Pecho': 24, 'Espalda': 18, ...}
   [Cliente X] Ejercicio manual no mapeado: 'press inclinado' (original: 'Press Inclinado')
   ```

4. **Cambia el rango de fechas** en el dashboard (30d, 90d, 180d) y observa si:
   - Los logs muestran datos diferentes
   - El gráfico se actualiza correctamente

## Opción 3: Verificación Rápida en la Consola

Ejecuta estos comandos uno por uno en la consola de Django:

```python
from clientes.models import Cliente
from entrenos.services.estadisticas_service import EstadisticasService

# Seleccionar un cliente
cliente = Cliente.objects.first()
print(f"Cliente: {cliente.nombre} (ID: {cliente.id})")

# Ejecutar el análisis
resultado = EstadisticasService.analizar_volumen_optimo(cliente, '30d')

# Ver el resultado
print("\nSeries por semana:")
for i, grupo in enumerate(resultado['labels']):
    print(f"{grupo:15s}: {resultado['series_reales'][i]:6.1f} series/semana")

# Ver ejercicios no mapeados
if 'ejercicios_no_mapeados' in resultado:
    print(f"\nEjercicios no mapeados: {len(resultado['ejercicios_no_mapeados'])}")
    print(resultado['ejercicios_no_mapeados'][:5])
```

## Qué Buscar en los Logs

### ✅ Señales de que está funcionando correctamente:
- Los logs muestran diferentes valores de series para cada grupo muscular
- Los ejercicios se mapean correctamente a sus grupos
- Al cambiar el rango de fechas, los valores cambian

### ⚠️ Señales de problemas:
- Muchos ejercicios aparecen como "no mapeados"
- Todos los grupos musculares muestran 0 series
- Los valores no cambian al modificar el rango de fechas
- Los ejercicios tienen nombres con caracteres especiales o acentos que no coinciden con el mapeo

## Próximos Pasos Según el Resultado

### Si hay muchos ejercicios no mapeados:
Necesitaremos actualizar el diccionario `MAPEO_MUSCULAR_DYNAMIC` o mejorar la normalización de nombres.

### Si los valores son todos 0:
Verificar que hay ejercicios completados en la base de datos para el cliente y rango seleccionado.

### Si los valores no cambian:
Puede haber un problema de caché o los datos realmente son similares en diferentes rangos.

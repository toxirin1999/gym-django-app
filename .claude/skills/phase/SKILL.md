---
name: phase
description: Implementa una fase del proyecto gym usando TDD estricto. Escribe tests que fallen primero, implementa hasta que pasen, se autocorrige en bucle, y solo commitea cuando el suite está verde al 100%.
---

# Phase — TDD Autónomo

Implementa una fase completa del proyecto usando Test-Driven Development. No para hasta que todos los tests pasen.

## Cómo usar

```
/phase <descripción de la fase>
```

Ejemplo:
```
/phase Añadir campo energía_pre_sesion al modelo EntrenoRealizado y mostrarlo en el resumen semanal
```

## Lo que hace siempre (en este orden)

### 1. Entender el alcance
- Lee el código existente relevante antes de tocar nada.
- Identifica los archivos que se van a modificar.
- Confirma que no hay conflictos con fases en curso.

### 2. Escribir los tests PRIMERO (red)
- Escribe todos los tests de aceptación antes de implementar.
- Los tests deben fallar en este punto — eso es correcto.
- Corre el suite para confirmar que los nuevos tests fallan por las razones correctas.

### 3. Implementar (green)
- Implementa el mínimo código necesario para que los tests pasen.
- Corre el suite completo tras cada cambio significativo.
- Si introduce un test roto que antes pasaba: para, diagnostica, corrige.

### 4. Bucle automático fix-run
- Repite: editar → `python3 manage.py test --settings=gymproject.settings_local` → leer fallos → corregir.
- No para hasta que el output sea `OK` con 0 failures, 0 errors.

### 5. Revisión de calidad antes del commit
Antes de commitear, revisa específicamente:
- **Duplicados UI**: ¿hay algún componente/card que aparece dos veces?
- **CSS legibilidad**: ¿hay texto claro sobre fondo claro (light-on-light)?
- **URLs con namespace**: ¿todos los `{% url %}` y `reverse()` existen realmente en urls.py?
- **Migraciones**: `python3 manage.py makemigrations --check --settings=gymproject.settings_local`

### 6. Commit y push
- Solo commitea si el suite está 100% verde.
- Usa el agente `sonnet-builder` para implementación, `haiku-explorer` para búsquedas.
- Commit con mensaje descriptivo de la fase.
- Push a `origin main`.

### 7. Resumen
Reporta: tests antes/después, archivos modificados, hash del commit.

## Reglas que nunca se rompen

- Nunca commitear con tests rotos.
- Nunca implementar sin haber escrito el test primero.
- Si el suite tarda más de 60s, correr solo los tests del app afectada.
- Si un test es imposible de pasar por un bug externo, documentarlo y continuar — nunca borrarlo.

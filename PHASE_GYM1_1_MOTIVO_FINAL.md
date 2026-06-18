# ✅ PHASE GYM 1.1 — MOTIVO FINAL POST-FRENOS (COMPLETADA)

**Fecha**: 2026-06-18  
**Commits**: b644f51  
**Status**: ✅ **FASE COMPLETADA**

---

## 🎯 Problema Resuelto

Phase Gym 1 mostró `motivo_peso` basándose en **intención inicial** (RPE comparison).
Pero luego se aplican **frenos** (contextual, lesión, modo) que modifican el peso real.

**El problema**: Usuario ve motivo que dice "Sube por..." pero el peso está congelado.
**La contradicción**: El motivo explica la intención, no la decisión final.

---

## ✅ Solución Implementada

### Principio Madre
> **El motivo mostrado debe explicar exactamente por qué ESE peso, después de todos los frenos.**

No es: "Te explico qué habría hecho el plan sin frenos"  
Es: "Te explico por qué este peso, hoy, con el contexto real"

### Arquitectura

#### 1. Nueva función: `construir_motivo_final()`
**Ubicación**: `entrenos/services/progresion_contextual_service.py` (línea 347)

```python
def construir_motivo_final(ejercicio_dict, cliente):
    """
    Determina motivo_peso final basado en decisión real DESPUÉS de frenos.
    
    FLUJO:
    1. Si progresion_bloqueada=False → mantener motivo inicial (no hay freno)
    2. Si progresion_bloqueada=True:
       a. Lesión activa/retorno → motivo='mantiene', texto menciona "protección"
       b. Freno contextual → motivo='mantiene', texto menciona "margen"
       c. Otro freno → motivo actualizado según causa
    
    PRIORIDAD si hay múltiples frenos:
    1. Lesión (máxima protección)
    2. Freno contextual (carga, modo)
    3. Intención original (nunca se muestra si hay freno)
    """
```

#### 2. Integración en flujo
**Archivo**: `entrenos/services/sesion_recomendada.py`

Dos ubicaciones donde se aplican frenos:

**Ubicación 1** (línea ~1096-1108): Sesiones pendientes
```python
entrenamiento = aplicar_freno_contextual(cliente, entrenamiento, permiso, ...)
entrenamiento = aplicar_freno_lesion(cliente, entrenamiento)
# ← NUEVO: ajustar motivo post-frenos
if entrenamiento and entrenamiento.get('ejercicios'):
    entrenamiento['ejercicios'] = [
        construir_motivo_final(ej, cliente)
        for ej in entrenamiento['ejercicios']
    ]
```

**Ubicación 2** (línea ~1162-1174): Sesión de hoy
```python
entrenamiento_hoy = aplicar_freno_contextual(cliente, entrenamiento_hoy, permiso)
entrenamiento_hoy = aplicar_freno_lesion(cliente, entrenamiento_hoy)
# ← NUEVO: ajustar motivo post-frenos
if entrenamiento_hoy and entrenamiento_hoy.get('ejercicios'):
    entrenamiento_hoy['ejercicios'] = [
        construir_motivo_final(ej, cliente)
        for ej in entrenamiento_hoy['ejercicios']
    ]
```

---

## 🔄 Flujo Completo (Antes vs Después)

### ANTES (Phase Gym 1 — sin coherencia)
```
core.py:
  RPE anterior = 6, objetivo = 8
  → diferencia = -2
  → motivo_peso_tipo = 'sube'
  → motivo_peso_texto = "Sube por: últimas sesiones completadas con margen."
  → peso_propuesto = 95 kg

sesion_recomendada.py:
  aplicar_freno_contextual()
  → permiso = 'mantener_carga' (carga_alta_semanal)
  → peso = 90 kg (congelado)
  ← motivo_peso SIGUE siendo 'sube' ❌ CONTRADICCIÓN

Usuario ve:
  Peso: 90 kg
  Motivo: "Sube por..."
  → Confusión: El motivo no explica por qué el peso no subió
```

### DESPUÉS (Phase Gym 1.1 — coherente)
```
core.py:
  RPE anterior = 6, objetivo = 8
  → diferencia = -2
  → motivo_peso_initial = 'sube'
  → motivo_peso_texto = "Sube por: últimas sesiones completadas con margen."
  → peso_propuesto = 95 kg

sesion_recomendada.py:
  aplicar_freno_contextual()
  → permiso = 'mantener_carga' (carga_alta_semanal)
  → peso = 90 kg (congelado)
  
  construir_motivo_final() ← NUEVO
  → progresion_bloqueada = True
  → motivo_bloqueo = 'carga_alta_semanal'
  → motivo_peso_type = 'mantiene' ✅ CAMBIO
  → motivo_peso_texto = "Carga mantenida: el plan prioriza margen esta semana."

Usuario ve:
  Peso: 90 kg
  Motivo: "Carga mantenida: el plan prioriza margen esta semana."
  → Claridad: El motivo EXPLICA por qué el peso no subió, aunque RPE fue baja
```

---

## 📊 Matriz de Decisión (Prioridad)

| Señal | Si bloqueado | Nuevo motivo_tipo | Nuevo texto |
|---|---|---|---|
| **Lesión AGUDA** | True | 'mantiene' | "Progresión frenada: hay una señal de protección activa." |
| **Lesión RETORNO** | True | 'mantiene' | "Carga mantenida por recuperación articular gradual." |
| **Freno contextual** | True | 'mantiene' | "Carga mantenida: el plan prioriza margen esta semana." |
| **Modo reducido** | True | 'mantiene' | "Carga mantenida: el plan prioriza margen esta semana." |
| **Retorno pausa** | True | 'mantiene' | "Carga mantenida: el plan prioriza margen esta semana." |
| **Sin frenos** | False | (no cambia) | (se mantiene inicial) |

---

## 🧪 Validación: Tests (15/15 ✅)

**Suite**: `entrenos/test_phase_gym1_1_motivo_final.TestMotivoPesoFinal`

### Tests Principales (8)
1. ✅ `test_motivo_final_sube_sin_frenos()` — intención 'sube' sin bloqueo
2. ✅ `test_motivo_final_mantiene_por_freno_contextual()` — contextual brake
3. ✅ `test_motivo_final_mantiene_por_lesion_aguda()` — lesión AGUDA
4. ✅ `test_motivo_final_mantiene_por_lesion_retorno()` — lesión RETORNO
5. ✅ `test_motivo_final_frenado_sin_frenos()` — intención 'frenado' sin bloqueo
6. ✅ `test_motivo_final_sin_datos_sin_frenos()` — intención 'sin_datos'
7. ✅ `test_motivo_final_mantiene_por_modo_reducido()` — modo_reducido
8. ✅ `test_motivo_final_mantiene_por_retorno_pausa()` — retorno_pausa

### Tests de Validación (7)
- ✅ `test_texto_motivo_final_coherente_con_tipo()` — global: tipo + texto coherentes
- ✅ `test_prioridad_lesion_over_freno_contextual()` — lesión > contextual
- ✅ `test_motivo_final_mantiene_preserva_rpe_base()` — edge: intención 'mantiene'
- ✅ `test_motivo_final_es_json_serializable()` — serialización JSON
- ✅ `test_construir_motivo_final_preserva_otros_campos()` — no corrupta otros campos
- ✅ `test_construir_motivo_final_con_none_motivo_peso()` — edge: None
- ✅ `test_construir_motivo_final_con_empty_dict()` — edge: dict vacío

**Comando**:
```bash
python3 manage.py test entrenos.test_phase_gym1_1_motivo_final --settings=gymproject.settings_local
```

**Resultado**: 15/15 tests passing ✅

---

## ✅ No Breaking Changes

### Phase Gym 1 Tests: 7/7 Still Passing ✅
La función `construir_motivo_final()` es una capa NUEVA post-frenos:
- No modifica la lógica del planificador
- No cambia cálculos de peso propuesto
- No toca `aplicar_freno_contextual()` o `aplicar_freno_lesion()`
- Solo ajusta la **visualización** del motivo para que sea coherente

```bash
python3 manage.py test entrenos.test_phase_gym1_motivo_peso --settings=gymproject.settings_local
# Resultado: 7/7 passing ✅
```

---

## 🎯 Principio Madre Sellado

**Phase Gym 1 Promesa**:
> "Te explico por qué este peso hoy"

**Phase Gym 1.1 Garantía**:
> "El motivo que ves SIEMPRE explica la decisión final, no una intención previa"

Si hay freno, el motivo lo nombra.  
Si no hay freno, el motivo refleja la intención original.  
En ambos casos: **coherencia determinista, sin ambigüedad**.

---

## 📝 Cambios Sumario

| Archivo | Cambios |
|---|---|
| `entrenos/services/progresion_contextual_service.py` | +71 líneas: función `construir_motivo_final()` |
| `entrenos/services/sesion_recomendada.py` | +18 líneas: llamadas a `construir_motivo_final()` en 2 ubicaciones |
| `entrenos/test_phase_gym1_1_motivo_final.py` | +390 líneas: suite de 15 tests |

---

## 🚀 Impacto Esperado

### Antes (Phase Gym 1 — sin Phase 1.1)
```
Usuario entrena con RPE 6 (baja)
Plan propone subir a 95 kg
Pero hay carga alta → freno congela a 90 kg
Usuario ve:
  - Peso: 90 kg
  - Motivo: "Sube por: últimas sesiones completadas con margen."
  
Resultado: Confusión → "¿Por qué dice que sube si no subió?"
```

### Después (Phase Gym 1.1 — coherencia sellada)
```
Usuario entrena con RPE 6 (baja)
Plan propone subir a 95 kg
Pero hay carga alta → freno congela a 90 kg
Usuario ve:
  - Peso: 90 kg
  - Motivo: "Carga mantenida: el plan prioriza margen esta semana."

Resultado: Claridad → "Entiendo: el plan frenar por carga alta"
```

---

## ✅ Checklist Final

- ✅ Función `construir_motivo_final()` implementada
- ✅ Integrada en ambos flujos (pendiente + hoy)
- ✅ Prioridad jerarquizada: lesión > contextual > intention
- ✅ 15/15 tests pasando
- ✅ Phase Gym 1 tests aún pasan (no breaking changes)
- ✅ Texto coherente con tipo (validación global)
- ✅ JSON serializable
- ✅ Preserva otros campos de ejercicio
- ✅ Maneja edge cases (None, dict vacío)

---

## 📋 Commits

```
b644f51 feat(Phase Gym 1.1): Final motivo layer for coherence after frenos
```

---

## 🎯 Pregunta Central Respondida (Nuevamente)

> **¿El motivo que veo explica el peso que tengo?**

**Antes Phase 1.1**: A veces no (si hay freno).  
**Después Phase 1.1**: Siempre sí. **Garantizado.**

---

**Status Final**: ✅ **PHASE GYM 1.1 COMPLETADA**

**Siguiente**: Observación real (3-5 usos). Validar que la coherencia se siente natural en contexto real y que el usuario entiende por qué el motivo no siempre dice "sube".

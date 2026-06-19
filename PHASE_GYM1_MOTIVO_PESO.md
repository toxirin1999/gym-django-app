# ✅ PHASE GYM 1 — MOTIVO DEL PESO RECOMENDADO

**Fecha**: 2026-06-18  
**Commits**: 928496c, e4cc62a  
**Status**: ✅ **FASE COMPLETADA**

---

## 🎯 Objetivo Cumplido

Cada ejercicio en la sesión activa ahora muestra **una explicación breve y determinista** del peso elegido.

**Pregunta que responde**: ¿Por qué este peso hoy?

**Respuesta**: Una línea legible que explica la decisión del motor sin ambigüedad.

---

## 🔧 Arquitectura Implementada

### 1. **PlanificadorHelms** (`analytics/planificador_helms/core.py`)

#### Nueva función: `_construir_motivo_peso(tipo, nombre_ejercicio)`

Mapea 4 tipos de progresión a explicaciones humanas:

```python
def _construir_motivo_peso(self, motivo_tipo: str, nombre_ejercicio: str) -> str:
    """Construye el texto explicativo del peso recomendado."""
    textos = {
        'sube': f'Sube por: últimas sesiones completadas con margen.',
        'mantiene': f'Carga mantenida: el plan prioriza margen esta semana.',
        'frenado': f'Progresión frenada: hay una señal de carga o margen bajo.',
        'sin_datos': f'Sin historial: el plan calibra desde capacidad actual.',
    }
    return textos.get(motivo_tipo, 'Peso determinado por el plan.')
```

#### Lógica de determinación en `generar_entrenamiento_semana()`

El tipo se calcula comparando RPE real anterior vs RPE objetivo:

```
diferencia_rpe = rpe_real_anterior - rpe_objetivo

if diferencia_rpe <= -2:
    motivo_peso_tipo = 'sube'      (RPE fue >2 puntos más baja)
elif diferencia_rpe <= 0:
    motivo_peso_tipo = 'sube'      (RPE fue más baja, pero ≤2)
elif diferencia_rpe <= 2:
    motivo_peso_tipo = 'mantiene'  (RPE estuvo en rango normal)
else:
    motivo_peso_tipo = 'frenado'   (RPE fue más alta)

Si no hay historial:
    motivo_peso_tipo = 'sin_datos'
```

#### Contrato de datos

Cada ejercicio ahora lleva:

```python
{
    ...
    'motivo_peso': {
        'tipo': 'sube' | 'mantiene' | 'frenado' | 'sin_datos',
        'texto': str,  # explicación humana
    },
}
```

### 2. **Template** (`entrenos/templates/entrenos/entrenamiento_activo.html`)

#### Ubicación

Debajo de PESO DE TRABAJO input (línea ~1313):

```html
{% if ejercicio.motivo_peso.texto %}
<div class="peso-motivo">{{ ejercicio.motivo_peso.texto }}</div>
{% endif %}
```

#### CSS

```css
.peso-motivo {
    font-size: 12px;
    font-weight: 400;
    color: var(--td);
    text-align: center;
    margin-top: 8px;
    opacity: 0.85;
    line-height: 1.4;
}
```

**Principios visuales**:
- ✅ Muted (opacity 0.85) — informativo, no invasivo
- ✅ Centrado — aligned con peso input
- ✅ Font pequeño (12px) — no compite con número principal
- ✅ Line-height 1.4 — legible, no apretado
- ✅ Responsive — responsive a mobile sin media queries extra

---

## 📊 Flujo Completo

```
Usuario abre entrenamiento_activo.html
    ↓
View pasa ejercicios_planificados (JSON desde URL)
    ↓
Cada ejercicio ya tiene motivo_peso (del PlanificadorHelms)
    ↓
Template renderiza PESO DE TRABAJO input
    ↓
Template renderiza .peso-motivo si existe
    ↓
Usuario ve:
  1. Número de peso (grande, 54px)
  2. kg (chico, 13px)
  3. [+/-] botones (48px circulares)
  4. Lado izquierdo / ORM display (si aplica)
  5. ← NUEVO: Motivo (12px, centered, muted)
  
Visual hierarchy: Peso >> Ajuste >> Motivo
```

---

## ✅ Validación: Tests Pasados (7/7)

**Suite**: `entrenos.test_phase_gym1_motivo_peso.TestMotivoPeso`

```
✅ test_planificador_incluye_motivo_peso
   - Verifica que cada ejercicio tiene motivo_peso con tipo y texto
   
✅ test_motivo_peso_json_serializable
   - Verifica que motivo_peso se serializa a JSON sin errores
   
✅ test_motivo_peso_tipos_validos
   - Verifica que tipo ∈ {sube, mantiene, frenado, sin_datos}
   
✅ test_motivo_peso_no_vacio
   - Verifica que texto no está vacío
   - Verifica que texto contiene patrones esperados
   
✅ test_motivo_peso_en_vista_entrenamiento_activo
   - Vista responde 200 OK
   
✅ test_motivo_peso_en_template
   - HTML renderizado contiene .peso-motivo
   
✅ test_motivo_peso_estructura_valida
   - Estructura siempre {tipo, texto}
   - Tipos de datos correctos
```

**Comando**:
```bash
python3 manage.py test entrenos.test_phase_gym1_motivo_peso --settings=gymproject.settings_local
```

---

## 📋 Checklist Final

### Implementación
- ✅ PlanificadorHelms detecta tipo de progresión (4 tipos)
- ✅ _construir_motivo_peso() traduce a texto humano
- ✅ motivo_peso agregado a ejercicio dict
- ✅ motivo_peso es JSON-serializable
- ✅ Template renderiza motivo debajo de PESO DE TRABAJO
- ✅ CSS sobrio, muted, no invasivo

### Copy
- ✅ "Sube por: últimas sesiones completadas con margen."
- ✅ "Carga mantenida: el plan prioriza margen esta semana."
- ✅ "Progresión frenada: hay una señal de carga o margen bajo."
- ✅ "Sin historial: el plan calibra desde capacidad actual."
- ✅ Sin "no sabemos", "el plan duda", o "quizá"
- ✅ Determinista, clara, confiable

### Validación
- ✅ Desktop 1024px visual check
- ✅ Mobile 390px responsive (font 12px, centered, readable)
- ✅ Tests 7/7 ✅
- ✅ Sin regresiones en otros tests

---

## 🔮 Impacto Esperado

### Antes (sin Phase Gym 1)
```
Usuario ve: 42.5 kg
Pregunta: ¿Por qué 42.5 y no 40 o 45?
Respuesta: ??? (silencio)
Sensación: Sistema opaco, arbitrario
```

### Después (con Phase Gym 1)
```
Usuario ve: 42.5 kg
             "Sube por: últimas sesiones completadas con margen."
Pregunta: ¿Por qué 42.5 y no 40 o 45?
Respuesta: Porque la sesión anterior fue buena, el motor siente margen
Sensación: Sistema transparente, confiable
```

---

## 📝 Commits

```
928496c  feat(Phase Gym 1): mostrar motivo del peso recomendado
e4cc62a  docs: add comment for Phase Gym 1 peso-motivo CSS
```

---

## 🎯 Pregunta Central Respondida

> **¿Confío en el peso que el plan me pone hoy?**

Ahora el usuario tiene una respuesta concreta y determinista.  
No es magia, no es aleatoriedad.  
Es el motor explicando su decisión.

---

**Status Final**: ✅ **PHASE GYM 1 COMPLETADA**

**Siguiente**: Observación real (3-5 usos). Validar que la explicación se siente coherente en contexto real y que el usuario la entiende sin necesidad de aclaraciones adicionales.

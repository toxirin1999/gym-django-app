# 📋 PHASE ORGANISMO 0 — CONTRATO DEL ESTADO GLOBAL

**Status**: FASE DE DISEÑO (sin código)  
**Objetivo**: Definir contrato mínimo de coordinación entre módulos  
**Principio**: El organismo no habla más. Coordina mejor.

---

## 🎯 Qué Resuelve

Hasta ahora:
- Gym tiene vida (motivo_peso coherente post-frenos)
- Hyrox tiene vida (Pulso + reactividad)
- JOI Habitación tiene vida (4 estados + motivo + feedback)
- Diario tiene vida (ciclo día)

**Falta**: El usuario no siente que pertenezcan al mismo cuerpo.

**Solución**: Una capa mínima que lea señales de los 4 módulos y devuelva un único estado global del sistema + una acción principal.

**No es**: Un dashboard. Un resumidor. Un nuevo panel.

**Es**: Un "nervio central" que coordina sin crear ruido.

---

## 📊 ESTADOS GLOBALES INICIALES (4)

### 1. SILENCIO
**Significado**:  
No hay señales nuevas relevantes.  
El sistema está en reposo.

**Se activa cuando**:
- No hay entrenamiento hoy
- Diario no tiene entrada nueva
- JOI Habitación está SILENCIO
- Hyrox no está PROTEGIENDO
- Sin lesión activa
- Sin RPE extremo

**Texto mínimo mostrado**:  
"No hay nada que forzar ahora."

**Acción principal**:  
Ninguna / continuar como estás.

**URL acción**:  
Ninguna (o volver a home).

---

### 2. OBSERVANDO
**Significado**:  
Hay movimiento, pero todavía no hay lectura formada.  
El sistema está viendo.

**Se activa cuando**:
- Diario abierto sin cierre registrado HOY
- O: entrada reciente sin lectura JOI generada
- O: señales registradas recientemente pero sin conclusión
- O: JOI Habitación está OBSERVANDO

**Pero NO si**:
- Hyrox está PROTEGIENDO (eso gana)
- Hay lesión activa (eso gana)
- Hay RPE extremo (eso gana)

**Texto mínimo mostrado**:  
"Hay movimiento, pero aún no hay lectura formada."

**Acción principal**:  
Completar cierre del día / continuar registrando.

**URL acción**:  
`/diario/cierre/` o `/joi/habitacion/`

---

### 3. EN_MARGEN
**Significado**:  
Hay UNA ACCIÓN VIABLE ahora.  
El sistema permite seguir el plan con acción clara.

**Se activa cuando** (debe cumplir TODOS):
- Hay entrenamiento viable HOY (Gym tiene sesión)
- Gym NO tiene freno fuerte (contextual OK, lesión/deload NO)
- Hyrox Pulso NO está PROTEGIENDO
- NO hay lesión activa
- RPE reciente NO fue extrema
- Diario ciclo está en estado normal (no pendiente cierre)

**Importante**: No basta con "ausencia de problemas".  
Debe haber UNA ACCIÓN REAL DISPONIBLE (entrenar hoy).

**Pero NO si**:
- Hyrox está PROTEGIENDO (eso gana)
- Hay lesión activa (eso gana)
- Hay RPE extremo (eso gana)
- Diario está pendiente de cierre (eso es OBSERVANDO)

**Texto mínimo mostrado**:  
"Hay margen para seguir el plan."

**Acción principal**:  
Empezar entrenamiento de hoy.

**URL acción**:  
`/entrenos/cliente/{id}/entrenamiento-activo/`

---

### 4. PROTEGIENDO
**Significado**:  
Hay señal fuerte de carga, lesión o recuperación.  
El sistema baja el tono.

**Se activa cuando (cualquiera de)**:
- Hyrox Pulso está PROTEGIENDO
- RPE extremo registrada hoy (≥ 9)
- Lesión activa AGUDA / SUB_AGUDA
- Recuperación pendiente sin registrar
- Gym tiene freno fuerte activo (lesión o deload)
- JOI Habitación está PROTEGIENDO

**Prioridad**:  
Si hay CUALQUIERA de estas, PROTEGIENDO gana sobre todo.

**Texto mínimo mostrado**:  
"El sistema baja el tono hoy."

**Acción principal**:  
Registrar recuperación / descansar / entrenar con margen.

**URL acción**:  
`/hyrox/registrar-recuperacion/` o `/entrenos/cliente/{id}/entrenamiento-activo/?modo=conservador`

---

## 🔀 MATRIZ DE PRIORIDAD

```
PROTEGIENDO > EN_MARGEN > OBSERVANDO > SILENCIO
```

**Regla de oro**:  
Si hay CUALQUIER señal de PROTEGIENDO, ese estado gana.  
Los otros estados solo se activan si PROTEGIENDO es false.

**Ejemplo 1**:
```
Diario: abierto sin cierre    → sería OBSERVANDO
Hyrox: Pulso PROTEGIENDO     → PERO gana PROTEGIENDO
Resultado: PROTEGIENDO
```

**Ejemplo 2**:
```
Gym: sesión viable hoy        → sería EN_MARGEN
Diario: ciclo completo        → refuerza EN_MARGEN
Hyrox: Pulso no protegiendo   → permite EN_MARGEN
Resultado: EN_MARGEN
```

**Ejemplo 3**:
```
Nada nuevo registrado         → sería SILENCIO
Pero Diario tiene entrada sin cierre → OBSERVANDO
Resultado: OBSERVANDO
```

---

## 📡 SEÑALES DISPONIBLES (módulos que se leen)

### De Hyrox
- `HyroxObjective.get_pulso()` → booleano PROTEGIENDO sí/no
- Sesión más reciente: `rpe_global` si ≥ 9 → señal extrema
- `RecoveryTestLog` pendiente sin completar → señal pendiente

### De JOI Habitación
- Estado actual (`determinar_estado_habitacion_joi()`) 
- Valores válidos: SILENCIO, OBSERVANDO, PRESENTE, PROTEGIENDO
- Usar para confirmar/reforzar el estado global

### De Diario
- Estado del día (`BitacoraDiaria` para hoy):
  - sin_entrada
  - manana_hecha
  - solo_noche
  - dia_completo
- Si sin_entrada O solo_noche = OBSERVANDO
- Si dia_completo = neutral (permite otros estados)

### De Gym
- Sesión viable hoy: booleano (hay entrenamiento planificado)
- Freno activo: tipo de freno (lesion, contextual, etc.)
- `motivo_peso_final` (si bloqueado por lesión → PROTEGIENDO)

---

## ❌ QUÉ NO HACE (IMPORTANTE)

🚫 **No crea pantalla nueva todavía**  
Solo define estados. Mostrada será después.

🚫 **No usa IA**  
Es determinista. Lógica pura basada en señales existentes.

🚫 **No resume todos los módulos**  
No dice "aquí está todo". Solo dice "esto es lo que marca el sistema hoy".

🚫 **No genera narrativa nueva**  
Usa texto mínimo, pre-definido. No genera con IA.

🚫 **No cambia decisiones de Gym/Hyrox/Diario**  
Solo las Lee. No modifica.

🚫 **No modifica estados de JOI Habitación**  
JOI sigue calculando su estado. Esto solo lo Lee.

🚫 **No añade feedback**  
Sin "¿te sirvió este estado?" todavía.

🚫 **No hace análisis semanal**  
Solo el estado de hoy.

🚫 **No es un dashboard organismo**  
Es una lectura mínima: 1 estado + 1 motivo + 1 acción.

---

## 🔧 PROPUESTA: FUNCIÓN LÓGICA

Esto se implementaría en Phase Organismo 1 (aún sin código hoy).

```
resolver_estado_sistema_hoy(usuario) → dict

Devuelve:
{
    "estado": "PROTEGIENDO" | "EN_MARGEN" | "OBSERVANDO" | "SILENCIO",
    "motivo": "pulso_protegiendo" | "rpe_extremo" | "lesion_activa" | "diario_sin_cierre" | "sesion_viable" | "sin_senales",
    "texto": str (texto mínimo pre-definido),
    "accion_label": str (ej: "Registrar recuperación"),
    "accion_url": str (ej: "/hyrox/registrar-recuperacion/"),
    "modulo_principal": str (ej: "hyrox" | "gym" | "diario" | "joi"),
}
```

**Lógica pseudo**:
```
1. Verificar PROTEGIENDO (cualquier señal):
   - Hyrox Pulso PROTEGIENDO → return PROTEGIENDO
   - RPE reciente ≥ 9 → return PROTEGIENDO
   - Lesión AGUDA/SUB_AGUDA → return PROTEGIENDO
   - Recuperación pendiente → return PROTEGIENDO
   
2. Si no PROTEGIENDO:
   - Si Diario sin_cierre O JOI OBSERVANDO → OBSERVANDO
   
3. Si no OBSERVANDO:
   - Si Gym sesión viable Y no freno fuerte → EN_MARGEN
   
4. Si ninguno:
   - SILENCIO
```

---

## 📍 DÓNDE SE MOSTRARÍA (FUTURO)

No ahora, pero cuando Phase Organismo 1 esté listo:

**Ubicación**: Card mínima en dashboard principal o home.

**Tamaño**: 1 card pequeña, no panel.

**Contenido**:
```
Sistema hoy
━━━━━━━━━━━━━
PROTEGIENDO

El sistema baja el tono hoy.

[Registrar recuperación]
```

O:
```
Sistema hoy
━━━━━━━━━━━━━
OBSERVANDO

Hay diario abierto, pero falta cierre.

[Completar cierre]
```

**Principio**: 1 estado visible, 1 acción disponible. Nada más.

---

## ✅ CONTRATO VALIDADO POR

Para que Phase Organismo 0 se considere **APROBADO**, debe responder claro a:

1. **¿Qué estado global puede tener el sistema hoy?**  
   Respuesta: SILENCIO, OBSERVANDO, EN_MARGEN, PROTEGIENDO

2. **¿Por qué entraría en cada uno?**  
   Respuesta: Señales definidas arriba para cada estado

3. **¿Qué acción propone cada uno?**  
   Respuesta: Acción principal definida en cada sección

4. **¿Qué módulos lee?**  
   Respuesta: Hyrox (Pulso, RPE), JOI (estado), Diario (ciclo), Gym (viable, frenos)

5. **¿Qué NO toca?**  
   Respuesta: No modifica nada. Solo lee y coordina.

6. **¿Es un dashboard?**  
   Respuesta: No. Es una lectura mínima que después se mostrará como 1 card.

7. **¿Usa IA?**  
   Respuesta: No. Es determinista.

---

## 🚀 PRÓXIMO PASO: PHASE ORGANISMO 1

Una vez aprobado este contrato:

Phase Organismo 1 — Función determinista
- Implementar `resolver_estado_sistema_hoy()`
- Tests para cada estado
- Validar prioridad
- No UI todavía

---

## 📝 NOTAS IMPORTANTES

**Sobre sobrecarga**:  
El riesgo más alto es que esto se convierta en "otro dashboard". La defensa es:
- Máximo 1 estado visible
- Máximo 1 acción visible
- Máximo 1 card pequeña en home
- Sin resumen, sin gráficos, sin historiales

**Sobre determinismo**:  
No usa IA porque:
- Las señales ya existen (Pulso, RPE, Diario, JOI)
- La lógica es clara y auditable
- Permite aprender si funciona sin cambiar variables
- Si después necesita IA, se añade con evidencia

**Sobre JOI**:  
JOI Habitación sigue siendo dueño de su estado.  
Esto solo lo Lee para validar/reforzar el estado global.  
JOI NO es el "sistema organismo".

---

## ✅ CHECKLIST PARA APROBACIÓN

- [ ] Los 4 estados están claros
- [ ] Cada estado tiene: significado, activadores, texto, acción
- [ ] Prioridad es sin ambigüedad
- [ ] Señales disponibles son reales (ya existen)
- [ ] Se define QUÉ NO hace (defensas contra sobrecarga)
- [ ] Propuesta de función es clara
- [ ] Contrato es validable (responde las 7 preguntas)

---

**Esperando validación antes de Phase Organismo 1.**

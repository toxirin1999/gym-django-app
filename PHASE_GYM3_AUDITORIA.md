# Phase Gym 3 — Auditoría del Cierre Post-Sesión

**Estado:** 🔍 AUDITORÍA (sin código aún)  
**Propósito:** Validar continuidad de postura global después de entrenar  
**Contexto:** Organismo está listo en entrada y briefing. ¿Lo está en salida?

---

## La Pregunta Central

Cuando el usuario termina un entrenamiento desde el flujo:

```
Dashboard (EN_MARGEN / carga ajustada)
  ↓
Briefing (SISTEMA HOY · EN_MARGEN / carga ajustada)
  ↓
Entrenamiento (Versión esencial)
  ↓
FINALIZAR
  ↓
¿QUÉ VE EL USUARIO?
```

**La pregunta:** ¿El cierre es coherente con lo que prometió el organismo?

---

## Escenarios a Auditar

### Escenario 1: EN_MARGEN con carga ajustada

**Promesa inicial:**
```
Dashboard: EN_MARGEN · Hay margen, con carga ajustada.
Briefing:  Versión esencial · carga ajustada
```

**¿Qué debería pasar después de entrenar?**
- Usuario ve cierre de sesión
- Resumen de la sesión completada
- RPE registrado (¿bajo, medio?)
- Plan recibe feedback
- JOI aparece (¿cuándo? ¿con qué tono?)
- Sistema hoy se actualiza (¿a qué?)

**¿Hay contradicción?**
- ¿El cierre dice "bien hecho" cuando fue "carga ajustada"?
- ¿Celebra progreso cuando era margen?
- ¿Pide más cuando fue prudencia?

---

### Escenario 2: PROTEGIENDO

**Promesa inicial:**
```
Dashboard: PROTEGIENDO · El sistema baja el tono hoy.
Briefing:  Lesión en seguimiento
```

**¿Qué debería pasar?**
- Sesión restringida (sin ciertos ejercicios)
- RPE bajo esperado
- Recuperación prioritaria
- JOI refuerza "baja el tono"
- Plan no registra "progresión"

**¿Hay contradicción?**
- ¿El cierre muestra "progreso" cuando fue protección?
- ¿Hay señal de recuperación registrada?

---

### Escenario 3: SILENCIO

**Promesa inicial:**
```
Dashboard: SILENCIO · No hay nada que forzar ahora.
(usuario no entra al briefing — no hay acción propuesta)
```

**¿Qué debería pasar?**
- Si usuario no entrenó: OK
- Si usuario decidió entrenar solo: ¿qué pasa?

---

## Auditoría: Puntos a Revisar

### 1. ¿Dónde aterriza después de "Finalizar"?

```
Pregunta: ¿Cuál es la pantalla inmediata post-sesión?

Opciones:
a) Resumen de sesión (foto final)
b) Redirect al dashboard
c) Popup JOI
d) Página de gratitud
e) Formulario RPE/molestia
```

**Acción:** Completar sesión desde briefing y capturar pantalla.

---

### 2. ¿Qué mensaje ve en los primeros 5 segundos?

```
Pregunta: ¿Hay texto visible o solo UI?

¿Dice "Sesión completada"? 
¿Dice "Bien hecho"?
¿Dice nada?
¿Celebra? ¿Instruye? ¿Informa?
```

**Acción:** Anotar los textos que aparecen post-entrenamiento.

---

### 3. ¿Se actualiza "Sistema hoy"?

```
Pregunta: ¿Si paso a dashboard post-sesión, cambió el estado?

Antes: EN_MARGEN
Después: ¿SILENCIO? ¿EN_MARGEN? ¿Otro?

¿Por qué cambió o no cambió?
```

**Acción:** Completar sesión, volver a dashboard, revisar Sistema hoy.

---

### 4. ¿JOI aparece? ¿Cuándo? ¿Qué dice?

```
Pregunta: ¿La voz del entrenador aparece post-sesión?

Si aparece:
- ¿En qué momento? (inmediatamente, after save, in dashboard)
- ¿Qué tono? (celebración, instrucción, pregunta, silencio)
- ¿Es coherente con EN_MARGEN/carga ajustada?
```

**Acción:** Revisar flujo de JOI post-sesión, ver si hay trigger.

---

### 5. ¿El plan registra señales?

```
Pregunta: ¿El backend captura lo que ocurrió?

Debe registrar:
- RPE de la sesión
- Molestias reportadas
- Carga total
- Frenos aplicados
- Decisión de margen respetada

¿Se registra correctamente?
¿Influye en el plan siguiente?
```

**Acción:** Completar sesión, revisar BD y GymDecisionLog.

---

### 6. ¿Hay contradicción entre promesa y resultado?

```
Ejemplo de contradicción:
Dashboard dice: "Hay margen, con carga ajustada"
Post-sesión dice: "Progresión bloqueada, carga máxima registrada"
→ CONTRADICCIÓN

Ejemplo de coherencia:
Dashboard dice: "Hay margen, con carga ajustada"
Post-sesión dice: "Sesión completada, carga dentro del margen"
→ COHERENCIA
```

**Acción:** Listar todas las contradicciones encontradas.

---

## Mapa Actual (Antes de Auditoría)

Basado en estructura del código:

```
Entrada (Dashboard)
✅ Sistema hoy · EN_MARGEN
✅ Postura clara
✅ Acción propuesta

Tránsito (Briefing)
✅ Postura se mantiene
✅ No contradice

Ejecución (Entrenamiento)
? ¿Se registra el margen?
? ¿JOI aparece?
? ¿Plan actualiza?

Salida (Post-sesión)
? ¿Mensaje coherente?
? ¿Sistema hoy se actualiza?
? ¿Hay ciclo cerrado?
```

---

## Hipótesis Inicial

**Si la sesión fue EN_MARGEN/version_reducida:**

- ✅ Debería registrarse RPE bajo/medio
- ✅ Debería NO registrar "progresión"
- ✅ Debería registrar "sesión dentro de margen"
- ✅ Post-sesión debería confirmar margen, no celebrar
- ⚠️ JOI podría aparecer o no (TBD)
- ? Sistema hoy post-sesión: ¿vuelve a SILENCIO o sigue EN_MARGEN?

---

## Entregable de Auditoría

Una vez completada:

```
Mapa de flujo post-sesión actual (con screenshots)
├─ Pantalla inmediata post-"Finalizar"
├─ Mensajes visibles (textos, tonos)
├─ Actualización de Sistema hoy
├─ Aparición y contenido de JOI
├─ Registros en BD (RPE, decisión, carga)
└─ Análisis de coherencia

Lista de:
├─ ✅ Puntos que funcionan
├─ ⚠️ Puntos ambiguos
└─ ❌ Contradicciones claras
```

---

## Siguiente Paso

1. **Completar auditoría** (sin código)
2. **Reportar hallazgos**
3. **Proponer microfase si hace falta**

No implementar nada hasta tener clara la auditoría.


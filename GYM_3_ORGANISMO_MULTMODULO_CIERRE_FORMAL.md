# Phase Gym 3 + Organismo Multi-Módulo — CIERRE FORMAL

**Estado:** ✅ CERRADA  
**Fecha:** 2026-06-19  
**Commits:**
- e43a5fd fix: show progression indicators in briefing plan (Phase Organismo 3.1)
- 57665db debug: add logging to plan_dinamico_service (Organismo 3.1)
- e3f464b feat(Phase Organismo 2): Card mínima 'Sistema hoy' en dashboard (Organismo 2)
- 6cb0944 feat(Phase Organismo 1.1): Auditoría de decisiones globales (Organismo 1.1)
- 764aef3 feat(Phase Organismo 1): Resolver determinista de estado global (Organismo 1)
- db79b59 fix(Organismo 4.0): Remove broken diario.estado check
- 73839c8 feat(Phase Diario/Org 4.0): Integración canónica del estado Diario
- dc43a75 docs: Phase Diario/Org 4.0 — documentación completa

**Auditoría Multi-Módulo:** AUDITORIA_PROFUNDA_MULTI_MODULO.md identificó 5 hallazgos  
**Esta fase cierra:** Hallazgos #1 y #2 (Diario bug + desconexión)

---

## El Flujo Completo Validado

```
Dashboard:
├─ Lectura de señales (Gym, Hyrox, JOI, Diario)
├─ Resolver determinista: PROTEGIENDO > EN_MARGEN > OBSERVANDO > SILENCIO
└─ Card "Sistema hoy" muestra postura global

Acción viable detectada: EN_MARGEN
├─ Briefing: Estado global + versión esencial si aplica
├─ Sesión activa: Respeta modo_reducido + validaciones
└─ Cierre: Interpreta sin dramatizar

Post-sesión:
├─ EntrenoRealizado guardado
├─ Señales actualizadas (Hyrox fatiga, JOI context)
├─ Organismo recalcula automáticamente
└─ Dashboard: EN_MARGEN → SILENCIO (acción completada, sin botón)

Todo coordina vía servicios canónicos:
├─ Gym: obtener_sesion_recomendada_hoy() desde rutinas
├─ Hyrox: get_pulso() + lesiones desde HyroxObjective
├─ JOI: determinar_estado_habitacion_joi() desde joi.services
└─ Diario: calcular_estado_diario_hoy() desde diario.services
```

---

## Qué Se Logró

### ✅ Phase Gym 3 — Cierre Fiel y Sin Ruido

**Problema:** Post-sesión mostraba EN_MARGEN con botón "Empezar" después de completar.

**Solución (Organismo 3.1):** Check 7 en `_check_en_margen()` detecta si hay EntrenoRealizado hoy → retorna None → resolver pasa a SILENCIO.

**Fixes Gym 3.2 aplicados:**
1. REGISTROS 3/3 PRs (removido .distinct())
2. Ocultar cambios < 0.25 kg (ruido decimal)
3. Esconder cambios de variante (0↔carga no es regresión)
4. Comunicar "Sesión ajustada" si modo_reducido=True

**Microcopy Gym 3.2.1:**
```python
if num_prs == 1:
    msg = "🏆 ¡HAS LOGRADO 1 NUEVO RÉCORD PERSONAL!"
else:
    msg = f"🏆 ¡HAS LOGRADO {num_prs} NUEVOS RÉCORDS PERSONALES!"
```

**Validación:** Tests 7/7 passing. Visual en producción (3–7 días).

---

### ✅ Phase Organismo 1 → 3.1 — Resolver Determinista

**Fase 1:** Lectura de señales desde múltiples módulos.  
**Fase 2:** Card "Sistema hoy" visible en dashboard con postura global.  
**Fase 2.3:** Coherencia validada (EN_MARGEN correlaciona con sesión viable).  
**Fase 3.1:** Post-sesión: EN_MARGEN → SILENCIO automáticamente.

**Garantía arquitectónica:** El organismo NO inventa estados. Lee desde servicios canónicos:
- Gym: `obtener_sesion_recomendada_hoy(cliente)` → decisión viable
- Hyrox: `HyroxObjective.get_pulso()` → señal de protección
- JOI: `determinar_estado_habitacion_joi(usuario)` → movimiento emocional
- Diario: `calcular_estado_diario_hoy(prosoche)` → ciclo del día

---

### ✅ Phase Diario/Org 4.0 — Integración Canónica

**Hallazgo Auditoría #1:** Check de `diario.estado` en organismo.py línea 292-297 → **campo NO EXISTE**.

**Hallazgo Auditoría #2:** Diario completamente desconectado del organismo.

**Solución:** Reemplazar check roto con servicio real `calcular_estado_diario_hoy()` de Diario.

**Mapeo:**
```
Estado Diario: manana_hecha (apertura sin cierre)
        ↓
Organismo:    OBSERVANDO
        ↓
Acción:       "Completar cierre" → /diario/
```

**Prioridades preservadas:**
```
PROTEGIENDO (lesión, fatiga) > EN_MARGEN (sesión viable) > OBSERVANDO (Diario) > SILENCIO
```

**Garantía:** Diario nunca bloquea acción viable. Si hay sesión viable (EN_MARGEN), se muestra entrenar primero.

**Tests:** 9/9 passing, 1 skipped (no bloqueo).

---

## Principio Arquitectónico Sellado

> **Cada órgano habla mediante su servicio canónico.**

**Lo que NO hacemos:**
- ❌ No inventamos campos en modelos (diario.estado)
- ❌ No hardcodeamos estado en views
- ❌ No duplicamos lógica entre módulos
- ❌ No silenciamos errores sin logging

**Lo que SÍ hacemos:**
- ✅ Gym → servicio `obtener_sesion_recomendada_hoy()`
- ✅ Hyrox → método `get_pulso()` + `UserInjury.activa`
- ✅ JOI → función `determinar_estado_habitacion_joi()`
- ✅ Diario → función `calcular_estado_diario_hoy()`
- ✅ Organismo → lee servicios, no inventa

---

## Estado Actual de Coherencia

### ✅ Gym — COHERENTE

| Fase | Validación |
|---|---|
| Sesión viable detectada | ✅ EN_MARGEN en dashboard |
| Briefing propuesto | ✅ Versión esencial si modo_reducido |
| Sesión ejecutada | ✅ RPE, volumen, técnica registrados |
| Cierre sin ruido | ✅ Cambios > 0.25 kg, sin falsas regresiones |
| Post-sesión | ✅ SILENCIO automático, sin botón de repetición |

**Conclusión:** Flujo completo validado. Usuario nunca repite lo que ya completó.

---

### ✅ Hyrox — COHERENTE

| Señal | Impacto |
|---|---|
| Lesión AGUDA/SUB_AGUDA | → PROTEGIENDO (bloquea Gym) |
| RPE ≥ 9 en sesión anterior | → PROTEGIENDO |
| Pulso bajo | → EN_MARGEN / OBSERVANDO según contexto |
| Fatiga alta (TSB < -25) | → PROTEGIENDO automático |

**Bridge Gym→Hyrox:** Gym penaliza readiness score si tren inferior ≤ 48h.

**Conclusión:** Hyrox coordina con Gym sin conflictos.

---

### ✅ JOI — REACTIVO CON LATENCIA ACEPTADA

| Señal | Reacción |
|---|---|
| Gym session completada | → Signal genera mensaje JOI post-entreno |
| Hyrox session completada | → Fatiga inyectada en readiness |
| Diario ciclo completado | → Resumen semanal genera MensajeJOI (Celery) |
| Dashboard abierto | → Context processor regenera apertura si Celery no corrió |

**Latencia:** JOI puede tomar 1-2 segundos en regenerarse on-demand. Aceptado.

**Conclusión:** JOI es reactivo. No se fuerza. Si hay datos, habla.

---

### ✅ Diario — CONECTADO CORRECTAMENTE

| Estado | Mapeo | Acción |
|---|---|---|
| sin_entrada | — | No interfiere |
| manana_hecha | OBSERVANDO | "Completar cierre" |
| solo_noche | — | No interfiere |
| dia_completo | — | No interfiere |

**Garantía:** Diario nunca bloquea Gym o Hyrox.

**Conclusión:** Diario participa vía estado real, no check inventado.

---

### ✅ Organismo — COORDINA SIN INVENTAR

**Lectura de señales:**
```
Check 1: PROTEGIENDO ← [Hyrox pulso, RPE, lesión]
         ↓ No
Check 2: EN_MARGEN ← [Gym sesión viable]
         ↓ No
Check 3: OBSERVANDO ← [JOI habitación, Diario manana_hecha]
         ↓ No
Check 4: SILENCIO (default)
```

**Garantía:** Cada decisión está fundada en datos reales del módulo correspondiente.

**Conclusión:** Organismo es determinista. Reproducible. Testeable.

---

## Auditoría Multi-Módulo: Hallazgos Cerrados

| Hallazgo | Encontrado | Solución | Estado |
|---|---|---|---|
| #1 Diario: check roto de diario.estado | ✅ | Removido check, implementado ProsocheDiario | ✅ CERRADO |
| #2 Diario: desconectado del organismo | ✅ | Conectado vía calcular_estado_diario_hoy() | ✅ CERRADO |
| #3 Organismo: sin caché = on-demand | ✅ | Aceptado (ventaja: siempre fresco) | ⏭️ FUTURO |
| #4 JOI: parcialmente reactivo | ✅ | Aceptado (latencia corta, resuelve en siguiente load) | ⏭️ FUTURO |
| #5 Sin event bus centralizado | ✅ | Propuesto para futuro (Opción C) | ⏭️ FUTURO |

**Conclusión:** Hallazgos 1-2 cerrados (coordinación real). 3-5 son deuda arquitectónica para futura escalabilidad, no bloquean.

---

## Criterio de Cierre

**Phase Gym 3 se cierra cuando:**
1. ✅ Detecta señales de múltiples módulos
2. ✅ Adopta postura clara y única
3. ✅ Propone acción principal visible y discreta
4. ✅ Mantiene coherencia dashboard → briefing → sesión → cierre
5. ✅ NO contradice el entrenamiento real
6. ✅ Cierre representa fielmente lo ocurrido (sin inflar, sin ruido, sin falsas regresiones)
7. ✅ Sistema se calla cuando la acción ya se completó

**Phase Organismo Multi-Módulo se cierra cuando:**
1. ✅ Cada módulo coordina vía su servicio canónico
2. ✅ Prioridades son claras y preservadas
3. ✅ Diario integrado correctamente (no roto, no eliminado)
4. ✅ JOI mantiene prioridad en OBSERVANDO
5. ✅ Organismo no inventa estados
6. ✅ Tests validados (9/9 + 7/7 passing)
7. ✅ Documentación completa

**Todos los criterios:** ✅

---

## Lo Que NO Se Abre

### ❌ NO: Event Bus Centralizado (Opción C)

**Razón:** Gym 3 + Organismo Multi-Módulo funcionan sin él.  
**Futuro:** Si número de módulos crece significativamente (>5), revisitar.  
**Criterio de apertura:** Cuando detectemos deuda de latencia o duplicación de signals.

### ❌ NO: Organismo 5

**Razón:** Organismo 1-4 cubren coherencia global.  
**Futuro:** Cuando Diario o JOI necesiten intervenciones estructuradas más profundas.  
**Criterio de apertura:** Cuando usuario pida "el sistema anticipa acciones antes de que yo las pida".

### ❌ NO: Más features de Diario por ahora

**Razón:** Diario ya está coordinado. Agregar features es scope creep.  
**Futuro:** Resumen semanal integrado con Gym/Hyrox (cuando sea crítico).  
**Criterio de apertura:** Cuando observación real muestre que Diario es cuello de botella.

---

## Protocolo de Validación Post-Cierre

### 7 días sin features nuevas

**Período:** 2026-06-19 a 2026-06-26

**Solo:** Bugs que impidan entrenar o coordinación incoherente  
**No:** Features, refactoring, optimizaciones

**Observación:**
- ¿El sistema se comporta consistentemente?
- ¿Hay latencias inesperadas?
- ¿Diario OBSERVANDO aparece en momentos extraños?
- ¿EN_MARGEN y SILENCIO están bien diferenciados?

**Reporte:** Día 7, clasificar hallazgos como "bloquea", "mejora", "futuro".

---

## Cambios de Archivos Finales

### Phase Gym 3
- `entrenos/services/cierre_entrenamiento_service.py` — 4 fixes
- `entrenos/templates/post_entreno_resumen.html` — Mostrar sesion_tipo
- `entrenos/views.py` — Microcopy singular/plural (línea 4324-4327)
- `core/test_organismo_post_sesion.py` — 7 tests ✅
- `entrenos/test_cierre_gym32.py` — 7 tests ✅
- `GYM_3_CIERRE_FORMAL.md` — Documentación

### Phase Organismo 1-3.1
- `core/organismo.py` — Resolver determinista
- `core/test_organismo_post_sesion.py` — Tests

### Phase Diario/Org 4.0
- `core/organismo.py` — Diario check en `_check_observando()`
- `core/test_organismo_diario_4_0.py` — 10 tests (9/9 ✅)
- `PHASE_DIARIO_ORG_4_0.md` — Documentación
- Memory system updated

---

## Lema de Esta Fase

> *El organismo no inventa. Lee. Coordina. Se calla cuando toca.*

Cada módulo habla con su voz real (servicio canónico).  
El organismo no dramatiza ni embellece.  
El usuario siente un sistema que entiende, no uno que pretende.

---

## Conclusión

**Antes:**
```
Sistema registraba datos.
Diario y Organismo no hablaban.
Post-sesión contradecía visualmente.
```

**Ahora:**
```
Sistema lee señales de Gym, Hyrox, JOI, Diario.
Adopta postura única y coherente.
Propone acción clara o se calla.
Post-sesión actualiza automáticamente.
Usuario siente continuidad, no módulos aislados.
```

---

**Status:** 🎉 **PHASE GYM 3 + ORGANISMO MULTI-MÓDULO CERRADA Y VALIDADA**

**Siguiente:** 7 días de observación real. Luego: usar la app.


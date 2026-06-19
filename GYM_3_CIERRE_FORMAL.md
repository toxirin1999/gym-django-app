# Phase Gym 3 — Auditoría del Cierre Post-Sesión · CERRADA

**Estado:** ✅ VALIDADA EN PRODUCCIÓN  
**Fecha:** 2026-06-19  
**Commits:** 4 (Organismo 3.1 + Gym 3.1 + Gym 3.2 + PR banner microfix)  
**Validación:** Visual en producción + tests + coherencia del flujo completo

---

## El Flujo Completo (Validado)

```
Dashboard:
EN MARGEN
Hay margen, con carga ajustada.
        ↓
Briefing:
SISTEMA HOY · EN MARGEN
Versión esencial activa
Sin alertas. Sigue el plan — todo en orden.
        ↓
Sesión activa:
Día 5 - Potencia — Resensibilización
11 series · 31 min · RPE 7.0 · Carga mantenida
        ↓
Guardado:
Overlay "Guardando entrenamiento..."
(bloquea interacción, no permite navegación)
        ↓
Cierre:
✓ Sesión guardada
11 series · 31 min · RPE 7.0 · 2498 kg · Sesión ajustada
🏆 1 nuevo récord personal (Curl Femoral Tumbado)
Cambios relevantes: +0.53 kg (sin ruido decimal)
JOI: "El cuerpo responde sin ruido..."
        ↓
Dashboard:
SILENCIO
No hay nada que forzar ahora.
(sin botón "Empezar entrenamiento")
```

---

## Qué Se Logró

### ✅ Organismo 3.1 — Post-Sesión Coherente

**Problema:** Dashboard mostraba EN_MARGEN [Empezar entrenamiento] DESPUÉS de completar sesión.

**Solución:** Check 7 en `_check_en_margen()` detecta si hay EntrenoRealizado hoy. Si existe → retorna None → resolver pasa a SILENCIO.

**Resultado:** Dashboard se actualiza post-sesión: EN_MARGEN → SILENCIO (acción completada, sin botón).

**Tests:** 7/7 passing

---

### ✅ Gym 3.1 — Coherencia del Cierre (auditoría)

**Hallazgos de auditoría:**
1. Banner 3 PRs vs REGISTROS 2 — gap visual
2. +0.02 kg ruido innecesario
3. Dead Hang -35 kg falsamente interpretado como regresión
4. Sesión ajustada no comunicada

**Entrada:** Documento AUDITORÍA_GYM3_FLUJO_CÓDIGO.md + análisis BD

---

### ✅ Gym 3.2 — Cierre Fiel y Sin Ruido

**4 Fixes aplicados:**

1. **REGISTROS 3/3 PRs** — Cambio: `.distinct()` removido
   - Ahora: Si hay peso máximo + volumen total del mismo ejercicio, ambos se muestran
   - Resultado: Banner y REGISTROS coinciden (no parecen inconsistentes)

2. **Ocultar cambios < 0.25 kg** — Cambio: filtro en `_cambios_relevantes()`
   - Ahora: Si abs(delta) < 0.25 kg → no mostrar
   - Resultado: +0.02 kg desaparece, cierre más limpio

3. **No mostrar 0↔carga como regresión** — Cambio: detectar cambio de variante
   - Ahora: Si ejercicio pasa de 0 kg a carga (o viceversa) → ocultiar
   - Resultado: Dead Hang 35→0 kg no aparece como -35 kg falso

4. **Comunicar sesión ajustada** — Cambio: `_resumen_sesion()` añade `sesion_tipo` si `modo_reducido=True`
   - Ahora: "Sesión ajustada" aparece discretamente en el resumen
   - Resultado: Usuario entiende que fue versión esencial, no sesión incompleta

**Tests:** 7/7 passing

---

### ✅ Microfix Copy — Singular/Plural PR Banner

**Problema:** "¡HAS LOGRADO 1 NUEVOS RÉCORDS PERSONALES!" (gramatically wrong)

**Solución:** Cambio dinámico en views.py línea 4323
- Si num_prs == 1: "🏆 ¡HAS LOGRADO 1 NUEVO RÉCORD PERSONAL!"
- Si num_prs > 1: "🏆 ¡HAS LOGRADO {N} NUEVOS RÉCORDS PERSONALES!"

**Resultado:** Copy coherente en ambos casos

---

## Lo Que Significa Este Cierre

**Antes de Gym 3:**
```
El usuario entrena.
El sistema registra datos.
Fin.
```

**Ahora (Gym 3 completo):**
```
El sistema lee señales del día.
Adopta postura global (EN_MARGEN: hay acción viable).
Propone sesión ajustada.
Guía al usuario durante ejecución (versión esencial, carga mantenida).
Registra resultado (RPE, volumen, cambios reales).
Interpreta sin dramatizar (oculta ruido, comunica sesión ajustada).
Actualiza postura global (SILENCIO: acción completada, sin botón).
Deja de empujar cuando ya no toca.
```

**Eso es un organismo.**

---

## Fricciones Identificadas (Futuro)

No se cierran en esta fase. Solo se vigilan:

1. **Bloque "Activa Strava antes de empezar"** — Pesa visualmente
   - Futuro: Hacer más compacto si es operativamente posible

2. **Card "Sistema hoy" posición en dashboard** — Cae baja en orden de lectura
   - Futuro: Revisar si hay demasiado texto antes del botón de entrenamiento

3. **Singular/plural en otros banners** — Revisar si hay más casos como PR

---

## Arquitectura Utilizada

| Componente | Rol | Archivo |
|---|---|---|
| `resolver_estado_sistema_hoy()` | Lee señales, retorna postura | `core/organismo.py` |
| `_check_en_margen()` + Check 7 | Detecta si sesión completada hoy | `core/organismo.py` |
| `construir_contexto_cierre()` | Construye contexto de post-sesión | `entrenos/services/cierre_entrenamiento_service.py` |
| `_cambios_relevantes()` | Filtra cambios (variante + threshold) | `entrenos/services/cierre_entrenamiento_service.py` |
| `_resumen_sesion()` | Añade sesion_tipo si modo_reducido | `entrenos/services/cierre_entrenamiento_service.py` |
| `post_entreno_resumen.html` | Renderiza resumen + sesion_tipo | `entrenos/templates/` |
| PR banner copy | Singular/plural dinámico | `entrenos/views.py` línea 4323 |

---

## Validación Visual (Producción)

✅ Todos los 7 puntos verificados:
1. REGISTROS muestra PRs coherentes
2. Banner coincide con REGISTROS
3. Sin ruido decimal (+0.02 oculto)
4. Sin falsas regresiones (Dead Hang no -35)
5. "Sesión ajustada" comunicada
6. JOI coherente sin dramatizar
7. Dashboard post SILENCIO sin botón

---

## Impacto del Cierre

**Para el usuario:**
- El sistema nunca propone repetir lo que ya se completó
- El cierre reconoce que fue sesión ajustada (no "incompleta")
- Los cambios reales se ven limpios (sin ruido 0.02 kg)
- JOI no dramatiza, solo interpreta
- La sensación global: "Mi sistema me acompañó desde antes de entrenar hasta después"

**Para la arquitectura:**
- Organismo 3.1: Post-sesión actualización clara (EN_MARGEN → SILENCIO)
- Gym 3.2: Cierre sin ruido, fiel a lo ocurrido
- Sistema completo: decisión → acción → registro → interpretación → reposo

---

## Siguiente Frontera

Phase Gym 3 está cerrada.

El siguiente trabajo no es "más entrenamientos" sino **cerrar otros ciclos:**
- ¿Qué pasa con Hyrox post-sesión?
- ¿Qué pasa con Diario post-sesión?
- ¿El sistema es coherente en TODOS los módulos, o solo en Gym?

La respuesta determina si Organismo está viva de verdad o solo en Gym.

---

## Criterio de Cierre

✅ **Phase Gym 3 queda cerrada cuando:**
1. Detecta señales de múltiples módulos (Gym, Hyrox, JOI, Diario) ✅
2. Adopta postura clara y única ✅
3. Propone acción principal visible y discreta ✅
4. Mantiene coherencia del dashboard → briefing → sesión → cierre ✅
5. NO contradice el entrenamiento real ✅
6. Cierre representa fielmente lo ocurrido (sin inflar, sin ruido, sin falsas regresiones) ✅
7. Sistema se calla cuando la acción ya se completó ✅

**Todos los criterios:** ✅

---

**Lema de Gym 3:**
> *El organismo actúa cuando toca. Se calla cuando ya no toca. El usuario siente continuidad, no módulos aislados.*

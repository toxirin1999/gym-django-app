# Auditoría Profunda: Coherencia del Organismo Multi-Módulo

**Estado:** 🔍 HALLAZGOS CRÍTICOS IDENTIFICADOS  
**Fecha:** 2026-06-19  
**Alcance:** Gym, Hyrox, Diario, JOI  
**Conclusión:** Gym ✅ Coherente | Hyrox ✅ Coherente | Diario ❌ BUG CRÍTICO | JOI ⚠️ Parcialmente reactivo

---

## HALLAZGO CRÍTICO #1: BUG EN DIARIO

**Ubicación:** `core/organismo.py` líneas 292-297

```python
try:
    from diario.models import BitacoraDiaria
    diario = BitacoraDiaria.objects.filter(
        cliente__user=usuario,
        fecha=date.today()
    ).first()
    if diario and diario.estado in ['sin_entrada']:  # ← CAMPO NO EXISTE
        pass
    elif diario and diario.estado in ['manana_hecha']:  # ← CAMPO NO EXISTE
        return None
except Exception:
    pass  # ← SILENCIA EL ERROR
```

**Realidad:** `BitacoraDiaria` (clientes/models.py:60) NO tiene campo `estado`. Solo tiene:
- `horas_sueno`, `humor`, `rpe`, `nota_personal`, `mindfulness_am/pm`, `peso_kg`, `energia_subjetiva`, `calidad_sueno`, `fc_reposo`, `hrv_ms`

**Impacto:** 
- El check del diario **nunca funciona**
- Si un usuario tiene entrada de diario pendiente de cierre, el organismo NO lo sabe
- EN_MARGEN puede retornarse incorrectamente

**Severidad:** ⚠️ CRÍTICA — Rompe coordin ación con Diario module.

---

## HALLAZGO CRÍTICO #2: DIARIO COMPLETAMENTE DESCONECTADO

**Problema:** No hay ningún signal, caché invalido, o comunicación que haga que Diario afecte al organismo.

**Búsqueda:** `grep -r "resolver_estado_sistema_hoy\|BitacoraDiaria" diario/`  
**Resultado:** NADA. El módulo Diario no sabe que existe un organismo.

**Impacto:** 
- Diario es totalmente aislado
- Completar una entrada de diario no afecta si Sistema Hoy muestra EN_MARGEN o SILENCIO
- Organismo no tiene visibilidad de estado del usuario a nivel emocional/ciclo

**Severidad:** ⚠️ CRÍTICA — Falta coherencia Diario ↔ Organismo.

---

## HALLAZGO #3: ORGANISMO SIN CACHÉ = ON-DEMAND

**Observación:** El resolver no usa caché. Siempre recalcula en cada invocación.

**Ubicación:** `core/organismo.py:35-77`

**Consecuencia:**
- ✅ VENTAJA: Siempre fresco, no hay stale state
- ❌ DESVENTAJA: Si la vista no lo llama, "no se despierta"
- ⚠️ PROBLEMA: Después de Gym guarda sesión, el organismo no se invalida; no hay signal que diga "hey, recalcula"

**Impacto:** Pequeñas ventanas donde el dashboard muestra viejo estado.

**Severidad:** MEDIA — Solo si las vistas son lentas en llamar al resolver.

---

## HALLAZGO #4: JOI PARCIALMENTE REACTIVO

**Observación:** Cuando Gym o Hyrox guardan datos, **invalidan caché JOI**, pero el organismo NO se invalida.

**Ubicación:** 
- `joi/signals.py:23-24` — Invalida `joi_estado_{usuario.id}`
- `joi/signals.py:39-40` — Invalida `joi_estado_{usuario.id}`

**Pero:** No hay signal que invalide el organismo (porque no tiene caché, pero sí hay latencia en la reactividad visual).

**Impacto:** Momentos de desincronización entre:
- JOI actualiza (visible vía context processor)
- Organismo aún retorna estado viejo (hasta que se llame la vista de nuevo)

**Severidad:** BAJA — Latencia corta, se resuelve en siguiente view load.

---

## HALLAZGO #5: SIN EVENT BUS CENTRALIZADO

**Observación:** No hay un pub/sub o event bus que centralice las notificaciones de cambios.

**Cada módulo hace su propia cosa:**
- Gym: invalida dashboard caché, genera GymDecisionLog, genera JOI msg
- Hyrox: injec fatiga en readiness, calcula TSB, genera JOI msgs
- JOI: invalida su propio caché
- Diario: completamente desconectado

**Falta:** Un mecanismo que diga "el estado global cambió, recalcula decisiones".

**Severidad:** MEDIA — Funciona, pero es frágil y difícil de mantener.

---

## COHERENCIA POR MÓDULO

### ✅ GYM — COHERENTE (validado en Gym 3)

```
EntrenoRealizado guardado
  ↓
Signal: Invalida caché dashboard, genera GymDecisionLog, genera JOI msg
  ↓
Siguiente view: Organismo recalcula
  ↓
Dashboard muestra estado actualizado
```

**Estado:** ✅ Funcionando bien.

---

### ✅ HYROX — COHERENTE

```
HyroxSession completada
  ↓
Signal: Calcula TRIMP, fatiga, genera JOI msgs
  ↓
Gym: Lee fatiga Hyrox e inyecta en próxima sesión
  ↓
Organismo: Ve lesión activa si fue AGUDA
```

**Estado:** ✅ Funcionando bien.

---

### ⚠️ JOI — PARCIALMENTE REACTIVO

```
Eventos de Gym/Hyrox
  ↓
Signal: Invalidan caché JOI
  ↓
Context processor: Regenera on-demand
  ↓
UI: Muestra JOI actualizado
```

**Estado:** ⚠️ Funciona pero con latencia posible.

---

### ❌ DIARIO — COMPLETAMENTE DESCONECTADO

```
Entrada de diario guardada
  ↓
¿Signal? NO
  ↓
¿Organismo se entera? NO (por bug + falta de comunicación)
  ↓
¿Afecta a Gym? NO
  ↓
Dashboard sigue igual
```

**Estado:** ❌ No hay coherencia. Bug + falta de arquitectura.

---

## IMPACTO DE DIARIO BUG EN GYM 3

**Pregunta:** ¿Gym 3 está realmente coherente si Diario falla?

**Respuesta:** Sí, pero es suerte. Porque:
1. GymDecisionLog se crea independientemente
2. Organismo se recalcula sin necesitar Diario
3. Si `diario.estado` hubiera estado implementado, Gym 3 podría estar roto

**Pero:** Si en el futuro un usuario depende de Diario para EN_MARGEN/SILENCIO, fallará silenciosamente.

---

## MICROFASES CORRECTIVAS PROPUESTAS

### Opción A: ARREGLAR DIARIO (si se usa)

**Si BitacoraDiaria.estado es relevante:**
1. Verificar qué estados reales existen en Diario
2. Implementar lógica correcta en organismo.py líneas 292-297
3. Agregar signal Diario → invalidar organismo (si implementar caché)
4. Agregar tests

**Esfuerzo:** 2-3 commits

---

### Opción B: REMOVER CHECK DIARIO (si no se usa)

**Si Diario NO afecta a MARGEN:**
1. Remover líneas 286-299 en organismo.py
2. Remover intento de coordinación con Diario
3. Documentar que Diario es observador, no coordinador

**Esfuerzo:** 1 commit

---

### Opción C: EVENT BUS FUTURO

**Para coherencia robusta a largo plazo:**
1. Implementar pub/sub centralizado (Redis, Celery, o similar)
2. Cada módulo publica "estado cambió"
3. Organismo se suscribe y se invalida
4. Garantizar consistencia incluso con latencias

**Esfuerzo:** 5-10 commits (arquitectura mayor)

---

## RECOMENDACIÓN

**Para Phase Gym 3:**
- ✅ Gym 3 es coherente (validado)
- ✅ No depende de Diario (por el bug, es suerte)
- ⚠️ Pero el sistema está en deuda: Diario bug + falta de event bus

**Acción inmediata:**
1. **Aplicar Opción B** (remover check Diario roto)
   - Documenta decisión: "Diario es observador"
   - Evita confusión futura
   - 1 commit, bajo riesgo

2. **Documentar:** Módulos coordinan vía Gym/Hyrox bridge
   - Diario es independiente (futuro: implementar si es crítico)

**Acción futura:**
3. Cuando Diario sea crítico: Opción A + tests
4. Cuando crezcamos: Opción C (event bus)

---

## ARCHIVOS A REVISAR

- `core/organismo.py` líneas 286-299 — Bug Diario
- `clientes/models.py` línea 60 — BitacoraDiaria modelo
- `joi/signals.py` líneas 23-24, 39-40 — Invalidaciones
- `hyrox/signals.py` líneas 394-476 — Bridge Hyrox-Gym
- `entrenos/signals.py` líneas 173-175 — Invalidaciones Gym

---

## CONCLUSIÓN

**Phase Gym 3 coherencia es REAL, pero el sistema multi-módulo está en deuda.**

- Gym-Hyrox: ✅ Coordinados
- JOI: ⚠️ Reactivo con latencia
- Diario: ❌ Roto (bug + desconectado)
- Falta: Event bus centralizado para escalar

**Recomendación:** Arreglar el bug de Diario (Opción B) antes de usar Diario en decisiones de Organismo.

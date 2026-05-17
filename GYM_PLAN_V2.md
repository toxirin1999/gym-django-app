# Gym Plan V2 — Sesiones vivas

> Mayo 2026 — Phase 1 a Phase 12.2

Reemplaza el plan por calendario rígido (fecha → rutina) por un sistema de **cola de sesiones con estado**, freno contextual de progresión e intervenciones temporales reversibles.

---

## Regla madre

> El plan no avanza por el calendario; avanza por sesiones completadas.
> El estímulo no realizado no cuenta, pero tampoco se acumula como deuda infinita.

---

## Modelos nuevos

| Modelo | App | Propósito |
|---|---|---|
| `SesionProgramada` | `entrenos` | Estado de cada sesión prevista (pendiente / completada / saltada / pospuesta / omitida) |
| `SugerenciaPlan` | `entrenos` | Sugerencia al usuario con cooldown de 7 días al ignorar |
| `IntervencionPlan` | `entrenos` | Política temporal semanal (hasta el domingo) creada al aceptar una sugerencia |

**Campos nuevos en modelos existentes:**

- `EntrenoRealizado.modo_reducido` — sesión hecha en versión esencial
- `EntrenoRealizado.principales_planificados / opcionales_planificados` — denominadores para calcular completitud esencial
- `EjercicioRealizado.es_bloque_principal` — `True/False/None` según si fue ejercicio principal, opcional o sesión normal
- `EjercicioRealizado.origen_opcional` — `'modo_reducido' | 'intervencion_reducir_accesorios' | 'ambos' | None`
- `PlanificadorHelms` output → cada ejercicio ahora incluye `tipo_ejercicio` (compuesto_principal / compuesto_secundario / aislamiento)

---

## Servicios

```
entrenos/services/
  sesion_recomendada.py          Motor diario. Pendientes primero → plan algorítmico → descanso.
  progresion_contextual_service.py   Freno de progresión contextual.
  analisis_semanal_service.py    Lectura semanal + patrón multisemanal + bloque JOI.
  sugerencias_service.py         Gestión de sugerencias e intervenciones. Phase 12 evaluación.

joi/services.py                  Inyecta bloque_semanal_gym y patron_multisemanal_gym en construir_contexto().
```

---

## Flujo

```
PlanificadorHelms (algoritmo) → propone peso_kg
         ↓
SesionProgramada (cola de estado)
         ↓
obtener_sesion_recomendada_hoy()
  → pendiente más antigua válida | sesión de hoy | descanso
  → contexto físico: lesión / fatiga / fútbol / energía
  → estado: entrenar | recuperar | posponer | version_reducida | descanso
         ↓
evaluar_permiso_progresion()         ← IntervencionPlan tiene prioridad
  → progresion_permitida | mantener_carga | reducir_accesorios
         ↓
aplicar_freno_contextual()
  → peso_kg revertido a actual si bloqueado
  → progresion_bloqueada / motivo_bloqueo / peso_kg_propuesto / origen_opcional
         ↓
Panel: "Qué hago hoy" + "Esta semana" + "Lo que el plan está observando"
         ↓
analizar_semana_entrenamiento()  →  estado_semana / continuidad / suficiencia / margen
detectar_patron_multisemanal()   →  observación (2-3 semanas con repetición)
generar_sugerencia_plan()        →  SugerenciaPlan(pendiente)
         ↓
Usuario: Aplicar esta semana / Ignorar
  → Ignorar: cooldown 7 días
  → Aceptar: IntervencionPlan (tipo: no_subir_cargas | reducir_accesorios | mantener_estructura)
              fecha_fin = próximo domingo
         ↓
evaluar_intervencion_semana()    →  favorable | neutral (semana siguiente)
```

---

## Reglas permanentes

1. Sesión no completada → pendiente (no desaparece)
2. `modo_reducido = True` → nunca auto-sube cargas
3. `IntervencionPlan` activa → tiene prioridad sobre patrón inferido
4. Sugerencia ignorada → silencio 7 días
5. `bloque_semanal_para_joi` → NUNCA escribe ManualDavid
6. Degradación graceful en todos los servicios: si falla, comportamiento base intacto

---

## Tests (~149)

```
entrenos/tests_sesion_programada.py      76  sesiones, reconciliación, prioridad, contexto, esencial, análisis, JOI
entrenos/tests_progresion_contextual.py  15  freno de progresión
entrenos/tests_sugerencias.py            29  sugerencias, intervenciones, evaluación
joi/tests_bloque_semanal.py              29  integración JOI, lenguaje
```

---

## Siguiente: Phase 13

Recomendación de continuidad basada en evaluación de intervención.
- Favorable → proponer mantener el ajuste una semana más.
- Neutral → proponer ajuste más profundo (repetir microciclo).
- Sin automatización. El usuario decide.

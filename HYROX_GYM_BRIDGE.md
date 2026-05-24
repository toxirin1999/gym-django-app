# Hyrox-Gym Bridge — Estado global compartido de decisión

> Phases 1.0–1.3 — Mayo 2026 — ESTADO ESTABLE · 32 tests de auditoría

---

## Principio rector

> Gym y Hyrox no son dos cuerpos. Son dos disciplinas sobre el mismo cuerpo.

Hyrox puede proponer trabajo específico de estaciones, carrera o fuerza. Pero no puede contradecir el estado global del cuerpo que ya ha calculado el plan principal.

---

## Jerarquía de decisión (irrompible)

```
1. Lesión activa (AGUDA / SUB_AGUDA)
   → siempre recuperar; filtra estaciones por tags

2. Descanso global del plan gym              ← Phase 1.0
   → hereda el estado del plan aunque las métricas Hyrox sean buenas

3. Fatiga fisiológica alta
   → TSB ≤ -20: recuperar
   → ACWR ≥ 1.5: recuperar

4. Readiness bajo
   → score < 45: sostener

5. Señal corporal del diario                 ← Phase 1.1
   → intensidad alta o moderada: EMPUJAR → SOSTENER
   → intensidad suave: nota en mensaje, sin cambio de estado
   → vigilar_senal_activa solo: nota en mensaje, sin cambio de estado

6. Actividad intensa reciente (fútbol)       ← Phase 1.1
   → fútbol en últimas 48h: EMPUJAR → SOSTENER

7. Normal → Empujar
```

Las capas 5 y 6 solo pueden bajar de EMPUJAR a SOSTENER. Nunca pueden superar las capas 1–4.

---

## Bloques cerrados (mayo 2026)

### Phase 1.0 — Estado global compartido de descanso

- `_crear_hyrox_decision()` recibe `es_descanso_plan` y `estado_entreno`
- Si cualquiera de los dos señala descanso → devuelve `causa='descanso_plan'`, `puede_ejecutar_plan=False`
- La comprobación ocurre **antes** de mirar TSB/ACWR/readiness — así las métricas no contaminan la decisión
- `hyrox_dashboard()` calcula `es_descanso_plan` llamando a `obtener_sesion_recomendada_hoy(cliente, hoy)`
- El semáforo Hyrox recibe `es_descanso_plan` → `DailyDecisionEngine.get_estado_hoy(cliente, es_descanso_plan=...)`
- El botón "EJECUTAR PLAN" es un `<a>` real solo cuando `puede_ejecutar_plan=True`; en descanso queda como `<div>` atenuado sin acción

### Phase 1.1 — Señales compartidas no dominantes

- `_leer_senales_secundarias(cliente)` — función independiente, 3 `try/except` separados:
  - `senal_corporal` ← `obtener_senal_corporal_diario(cliente.usuario)` (últimos 5 días de `SeguimientoVires`)
  - `vigilar_senal_activa` ← `IntervencionPlan.TIPO_VIGILAR_SENAL` activa hoy
  - `futbol_reciente` ← `ActividadRealizada(tipo='futbol')` en últimas 48h
- `_crear_hyrox_decision()` recibe `senales_secundarias=None`
- Las señales actúan **solo si el resultado base es `empujar`** (tier 5/6 no pisan tiers 1–4)
- Si falla cualquier lectura → `try/except` silencioso; las demás señales siguen funcionando

### Phase 1.3 — Jerarquía visual por estado

- Cuando `puede_ejecutar_plan=False`, el panel entra en **modo recuperación**:
  - La `Lectura del sistema` se ancla inmediatamente después de la decisión soberana (posición prioritaria)
  - Todo el bloque competitivo (Race Command, Station Intelligence, Race Card, Perfil Atlético, Estándares...) se colapsa en un `<details>` cerrado por defecto: `Análisis de rendimiento y Race Command`
  - El `Plan de entrenamiento` sigue visible — el usuario necesita ver continuidad ("hoy descanso, pero el plan sigue")
  - El bloque histórico (Evolución Carrera, Análisis, Splits, Índice Interferencia, Historial) se colapsa en un segundo `<details>`: `Historial y análisis de carrera`
  - Race Command cambia el label de "Tiempo estimado hoy" → "Última estimación disponible" con nota explicativa
- Los datos no desaparecen — solo cambian de jerarquía. El usuario puede desplegarlos si los necesita.
- En día de entrenamiento (`puede_ejecutar_plan=True`): sin cambios, layout original completo.

**Regla nueva:** Si `puede_ejecutar_plan=False`, el panel Hyrox entra en modo recuperación — la decisión y la lectura del sistema dominan; las métricas competitivas pasan a detalle secundario.

### Phase 1.2 — Explicación visible de señales compartidas

- Cuando la modulación reduce de empujar a sostener, la decisión incluye `explicacion_modulacion`:
  ```python
  {
    'intro':   'Tus métricas Hyrox permitirían empujar, pero el sistema detecta carga reciente:',
    'bullets': ['Diario: ...', 'Fútbol reciente: ...'],
    'cierre':  'Hoy no se cancela el plan; se reduce la intención.',
  }
  ```
- El template renderiza el bloque `.hd-modulacion` solo cuando el campo existe
- `explicacion_modulacion` **no aparece** en descanso global ni en fatiga fisiológica — esas decisiones ya son explícitas por título y subtítulo

---

## Lo que el sistema YA hace

- Hyrox hereda descanso global del plan gym antes de evaluar sus propias métricas
- Hyrox hereda señal corporal del diario (alta/moderada → sostener; suave → nota)
- Hyrox detecta fútbol reciente como carga compartida
- Cuando modera el empuje, explica el motivo con bullets concretos
- El semáforo Hyrox y el semáforo del panel principal comparten `es_descanso_plan`
- El botón "EJECUTAR PLAN" es funcionalmente no clicable cuando `puede_ejecutar_plan=False`
- Si cualquier lectura secundaria falla, Hyrox sigue funcionando (degradación silenciosa)
- En modo recuperación, la Lectura del sistema sube al primer plano y los bloques competitivos se colapsan en `<details>` cerrados por defecto — los datos no desaparecen, solo cambian de jerarquía

---

## Lo que el sistema NO hace todavía (intencionalmente)

- ❌ No cruza señal corporal alta con tipo de sesión Hyrox (ej: "si el diario dice dolor y hoy es día de Sled, reducir carga Sled")
- ❌ No integra `IntervencionPlan.TIPO_VIGILAR_SENAL` como modulador activo — solo aparece en mensaje informativo
- ❌ No genera `SugerenciaPlan` desde señal corporal en el contexto Hyrox — solo informa
- ❌ No ajusta cargas de estaciones basándose en señal del diario — la señal informa, no actúa
- ❌ No hay Race Card ni predicción de tiempo que integre señal corporal
- ❌ Simbiosis no tiene puente con Hyrox

---

## Modelos y servicios involucrados

| Elemento | App | Rol |
|---|---|---|
| `_crear_hyrox_decision()` | `hyrox/views.py` | Decisión soberana del día; recibe todos los parámetros |
| `_leer_senales_secundarias()` | `hyrox/views.py` | Lectura de señales del diario y actividad reciente |
| `obtener_sesion_recomendada_hoy()` | `entrenos/services/sesion_recomendada.py` | Fuente de verdad del estado gym (`entrenar`/`descanso`) |
| `DailyDecisionEngine.get_estado_hoy()` | `core/daily_decision.py` | Semáforo unificado; recibe `es_descanso_plan` |
| `obtener_senal_corporal_diario()` | `diario/services/senales_entrenamiento.py` | Señal de últimos 5 días de `SeguimientoVires` |
| `IntervencionPlan.TIPO_VIGILAR_SENAL` | `entrenos/models.py` | Observación 2 semanas sin cambio de cargas |
| `ActividadRealizada(tipo='futbol')` | `entrenos/models.py` | Detección de carga compartida reciente |
| `UserInjury(fase=AGUDA/SUB_AGUDA)` | `hyrox/models.py` | Lesión activa — siempre tier 1 |

---

## Flujo de datos en `hyrox_dashboard()`

```
hyrox_dashboard(request)
│
├─ obtener_sesion_recomendada_hoy()     → _es_descanso_plan, _estado_entreno
│
├─ _leer_senales_secundarias(cliente)   → _senales_secundarias
│   ├─ obtener_senal_corporal_diario()
│   ├─ IntervencionPlan query
│   └─ ActividadRealizada query
│
├─ _crear_hyrox_decision(
│     current_score, resumen_semanal,
│     lesion_activa,
│     es_descanso_plan, estado_entreno,   ← tier 1-2
│     senales_secundarias                 ← tier 5-6
│   )
│
└─ DailyDecisionEngine.get_estado_hoy(
      cliente,
      es_descanso_plan=_es_descanso_plan  ← semáforo hereda
   )
```

---

## Reglas permanentes (no romper)

1. **El descanso global domina siempre.** Si `obtener_sesion_recomendada_hoy` devuelve `estado='descanso'`, Hyrox no evalúa TSB/ACWR/readiness como si fuese un día de entrenamiento.
2. **Las señales secundarias solo bajan de EMPUJAR.** No pueden elevar una decisión de RECUPERAR a SOSTENER, ni de SOSTENER a EMPUJAR. Solo comprimen el margen de empuje.
3. **SOSTENER no cancela el plan.** El botón de registrar entreno sigue activo cuando `puede_ejecutar_plan=True`. La explicación lo dice explícito: "se reduce la intención."
4. **`vigilar_senal_activa` no modifica estado.** Su contrato es "observar 2 semanas sin cambiar cargas". Aparece en el mensaje como contexto, nunca como freno.
5. **Degradación silenciosa obligatoria.** Si `_leer_senales_secundarias` falla total o parcialmente, la decisión Hyrox sigue funcionando. Los `try/except` son independientes por señal.
6. **`explicacion_modulacion` solo cuando hay modulación real.** Si la causa es descanso_plan, fatiga o lesión, el título y subtítulo ya son la explicación. No añadir el bloque de modulación en esos casos.
7. **El semáforo Hyrox y el panel principal comparten `es_descanso_plan`.** No pueden contradecirse sobre si hoy es día de descanso.
8. **El botón "EJECUTAR PLAN" es funcionalmente inerte en descanso.** No solo visualmente distinto — es un `<div>` sin `href`, no un `<a>`. La UI no invita a saltarse la decisión.
9. **En modo recuperación, la UI no estimula rendimiento.** La Lectura del sistema sube; los bloques competitivos se colapsan. Los datos siguen accesibles, pero no gritan. La lógica y la UI deben decir lo mismo.
10. **El Plan de entrenamiento siempre visible.** En descanso, el usuario necesita ver continuidad — "hoy descanso, pero el plan sigue". Ese bloque nunca se colapsa.

---

## Tests

```
hyrox/tests.py

TestHyroxDecisionDescansoGlobal          (Phase 1.0 — 6 tests)
  test_es_descanso_plan_true_no_devuelve_empujar
  test_estado_entreno_descanso_no_devuelve_empujar
  test_readiness_alto_tsb_positivo_pero_descanso_global_gana
  test_sin_descanso_global_decide_por_metricas
  test_mensaje_explica_descanso_plan_no_metricas
  test_semaforo_hereda_descanso_global

TestHyroxDecisionSenalesSecundarias      (Phase 1.1 — 7 tests)
  test_senal_alta_nudge_a_sostener
  test_senal_moderada_nudge_a_sostener
  test_senal_suave_no_cambia_estado
  test_futbol_reciente_nudge_a_sostener
  test_vigilar_senal_solo_no_cambia_estado
  test_secundaria_no_supera_descanso_global_tier1
  test_secundaria_no_supera_tsb_alto_tier2

TestHyroxDecisionExplicacionModulacion   (Phase 1.2 — 4 tests)
  test_explicacion_presente_en_senal_alta
  test_explicacion_contiene_futbol_si_aplica
  test_sin_modulacion_no_hay_explicacion
  test_descanso_plan_no_genera_explicacion_modulacion

Phase 1.3 — sin tests de lógica (es puramente visual/template).
La condición `not hyrox_decision.puede_ejecutar_plan` es el mismo invariant
ya cubierto por Phase 1.0 tests. Lo que cambia es el template, no la lógica.
```

---

## Backlog consciente

| Item | Por qué no está aún |
|---|---|
| Cruce señal corporal × tipo de estación Hyrox | Requiere saber qué músculos usa cada estación y contrastarlos con `molestia_zona`. Diseño cuidadoso antes de actuar. |
| `IntervencionPlan.TIPO_VIGILAR_SENAL` como freno activo | Por contrato actual no cambia cargas. Si se decide que en Hyrox sí modera, requiere cambiar el contrato explícitamente. |
| `SugerenciaPlan` desde señal corporal en contexto Hyrox | La señal corporal ya llega; falta definir qué tipo de sugerencia tendría sentido aquí. |
| Race Card integrando señal corporal | Requiere primero estabilizar la predicción de tiempo. |
| Simbiosis × Hyrox | Simbiosis no tiene puente con ningún módulo de entrenamiento todavía. |

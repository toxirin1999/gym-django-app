# Gym Plan V2 — Sesiones vivas + Preferencias aprendidas

> Phase 1–25 — Mayo 2026 — ESTADO ESTABLE · 82 tests de preferencias · ~250+ tests total

---

## Regla madre

> El plan no avanza por el calendario; avanza por sesiones completadas.
> El estímulo no realizado no cuenta, pero tampoco se acumula como deuda infinita.

---

## Lo que el sistema YA hace (mayo 2026)

- Sesiones pendientes tienen prioridad sobre el plan algorítmico de hoy
- Reconciliación semanal con criterio de prioridad (alta / normal)
- Contexto físico: lesión, fatiga, fútbol, energía baja
- Modo esencial: separa bloque principal y opcional
- Freno contextual de progresión: propone → autoriza → bloquea si hace falta
- Análisis semanal: lectura + estado semántico (solida, carga_alta, margen_extra…)
- Patrón multisemanal: 5 patrones detectables, lenguaje prudente
- Sugerencias de carga: con cooldown, intervención temporal hasta el domingo
- Evaluación de intervención de carga: antes vs durante
- Continuidad de intervención favorable: con cooldown específico por tipo
- Análisis de distribución semanal: 4 patrones (día que cae, días menores, esenciales concentradas, pierna/fútbol)
- Sugerencias de redistribución: prueba de 2 semanas
- Evaluación de prueba de distribución: antes vs durante
- Continuidad de prueba de distribución favorable
- Calendario/memoria visual: dot grid 4 semanas con estados por color
- JOI recibe señales semanales, multisemana y distribución (una por tipo, no lista)

- ✅ Preferencias aprendidas del plan (Phase 22–25)

## Lo que el sistema NO hace todavía (intencionalmente)

- ❌ No modifica `PlanificadorHelms` automáticamente
- ❌ No reemplaza ejercicios por lesión activa (solo filtra en UI)
- ❌ No reorganiza la semana en silencio
- ❌ No escribe en `ManualDavid` desde el análisis semanal
- ❌ No usa IA generativa para decidir sesiones

---

## Modelos nuevos / modificados

| Modelo | App | Propósito |
|---|---|---|
| `SesionProgramada` | `entrenos` | Estado de cada sesión prevista |
| `SugerenciaPlan` | `entrenos` | Sugerencias con cooldown (carga y distribución) |
| `IntervencionPlan` | `entrenos` | Políticas temporales de carga (hasta domingo) y distribución (14 días) |
| `EntrenoRealizado.modo_reducido` | `entrenos` | Bool: versión esencial |
| `EntrenoRealizado.principales/opcionales_planificados` | `entrenos` | Denominadores para bloque esencial |
| `EjercicioRealizado.es_bloque_principal` | `entrenos` | True/False/None — clasificación en modo esencial |
| `EjercicioRealizado.origen_opcional` | `entrenos` (campo en memoria) | 'modo_reducido' / 'intervencion_reducir_accesorios' / 'ambos' |
| `PlanificadorHelms` output → `tipo_ejercicio` | `analytics` | 'compuesto_principal' / 'compuesto_secundario' / 'aislamiento' |

---

## Dos ciclos paralelos

```
CICLO CARGA
observa patrón multisemanal
  ↓ SugerenciaPlan(patron='carga_alta_sostenida'|...)
usuario acepta → IntervencionPlan(fecha_fin=domingo)
  ↓ evaluar_permiso_progresion() lee IntervencionPlan PRIMERO
  ↓ aplicar_freno_contextual() → peso_kg revertido, motivo_bloqueo
evaluar_intervencion_semana() → favorable|neutral
  ↓ generar_recomendacion_continuidad() con cooldown 'continuidad_X'

CICLO DISTRIBUCIÓN
observa fricción (dia_pospone, dias_menores, esenciales_concentradas, pierna_futbol)
  ↓ get_sugerencia_distribucion_activa() → SugerenciaPlan(patron='distribucion_X')
usuario acepta → IntervencionPlan(fecha_fin=+14d, tipo=redistrib_*)
  ↓ _aplicar_efecto_distribucion() → aviso contextual en workout card
evaluar_prueba_distribucion() → favorable|neutral
  ↓ generar_recomendacion_continuidad_distribucion() con cooldown 'continuidad_distribucion_X'
```

---

## Servicios

```
entrenos/services/
  sesion_recomendada.py         Motor diario. Aplica freno y efecto distribución.
  progresion_contextual_service.py  Freno de progresión.
  analisis_semanal_service.py   Lectura semanal + patrón + distribución + bloque JOI.
  sugerencias_service.py        Sugerencias, intervenciones, evaluaciones, continuidad.
  calendario_plan_service.py    Calendario visual: dot grid por estado.

joi/services.py                 Inyecta bloque semanal + patrón + distribución (1 obs cada uno).
```

---

## Reglas permanentes (no romper)

1. `SesionProgramada` avanza por sesiones completadas, no por fechas.
2. `modo_reducido=True` completado ≠ permiso para subir cargas.
3. `IntervencionPlan` activa > patrón inferido (en evaluar_permiso_progresion).
4. Sugerencia ignorada → cooldown 7 días. Tipo específico, no global.
5. `bloque_semanal_para_joi` NUNCA escribe en ManualDavid.
6. Todos los servicios degradan silenciosamente: JOI sigue funcionando si algo falla.
7. Distribución no se cambia en silencio. Solo aviso contextual cuando aplica.
8. Una prueba favorable gana derecho a repetirse, no a volverse permanente.

---

## Tests (~252+)

```
entrenos/tests_sesion_programada.py      76  sesiones, contexto, esencial, análisis, JOI
entrenos/tests_progresion_contextual.py  15  freno de progresión
entrenos/tests_sugerencias.py            38  sugerencias, intervenciones, evaluación, continuidad
entrenos/tests_distribucion_semanal.py   24  distribución, Phase 20/21
clientes/tests_panel_ux.py               17  regresión del contexto del panel
joi/tests_bloque_semanal.py              29  integración JOI, lenguaje

— Ciclo de preferencias (Phase 22–25) —
entrenos/tests_preferencias.py           17  modelo, detección, creación, revocación
entrenos/tests_joi_preferencias.py       13  signal, lock, prompt, contexto JOI
entrenos/tests_auditoria_semantica.py    17  sin identidad, sin ManualDavid, etiqueta
entrenos/tests_preferencia_motor.py      21  motor, jerarquía, lenguaje, PlanificadorHelms
entrenos/tests_preferencia_ui.py         14  template, guard recuperar, hints, contexto

— Ciclo de lesión (Phase 28–29.1) —
entrenos/tests_lesion_aviso.py           20  aviso visual: zona, fase, ejercicios afectados
entrenos/tests_freno_lesion.py           18  freno per-ejercicio (congela peso_kg afectados)
entrenos/tests_freno_lesion_ui.py        12  UI diferenciada: rojo/ámbar/violeta por causa
entrenos/tests_convivencia_frenos.py     15  jerarquía auditada: contextual vs lesión vs preferencia
entrenos/tests_alternativas_lesion.py    12  service + API de alternativas revisables
entrenos/tests_cierre_lesion.py          16  checklist cierre: 10 items (sin prescripción médica)

— Sesiones pendientes —
entrenos/tests_marcar_completadas.py      9  detecta sesiones hechas en fecha posterior (7 días)
```

---

## Ciclo completo de preferencias aprendidas (Phase 22–25)

```
Pruebas favorables repetidas del mismo tipo
    ↓
detectar_candidata_preferencia() → candidata propuesta
    ↓ usuario acepta
crear_preferencia() → PreferenciaPlanAprendida(estado=ACTIVA)
    ↓ signal post_save
joi_preferencia_aprendida() → generar_mensaje_joi('preferencia_aprendida')
    ↓
JOI verbaliza con tono protegido (sujeto: "el plan", no el usuario)
    ↓
apertura_mañana() conoce preferencias como [Memoria operativa del plan]
    ↓
_obtener_contexto_fisico() carga preferencias_activas
    ↓
_aplicar_preferencia_activa() → preferencia_aplicada (causa secundaria)
    ↓ solo si causa_principal no es 'lesion' ni 'fatiga_alta'
UI: bloque PRF en workout card (teal, lenguaje blando)
    ↓
Usuario mantiene agencia: puede entrenar, posponer o revocar la preferencia
```

### Jerarquía de decisión

```
lesión activa → recuperar (bloquea todo)
    ↓
intervención explícita aceptada (IntervencionPlan)
    ↓
fatiga / readiness_bajo → recuperar
    ↓
energía baja → version_reducida
    ↓
fútbol reciente → posponer
    ↓
[preferencia_aplicada] (secundaria — no cambia estado ni causa_principal)
    ↓
plan normal → entrenar
```

### Qué es una preferencia aprendida

- Una inclinación blanda. No una regla.
- Sujeto siempre es "el plan", nunca el usuario.
- Sin absolutos: sin "siempre", "nunca", "debes".
- Revocable en un clic. Estado: `ACTIVA | SUSPENDIDA | REVOCADA`.
- No escribe en `ManualDavid`. No toca `PlanificadorHelms`.
- Lock JOI 24h por `(cliente, tipo)`: un mensaje por activación.

### Tipos disponibles

| Tipo | Condición motor |
|---|---|
| `evitar_pierna_tras_futbol` | `futbol_reciente=True` + sesión de pierna |
| `evitar_dia_frecuente` | weekday = `metadata.dia_semana` |
| `preferir_menos_dias` | sesión de `PRIORIDAD_NORMAL` |
| `aligerar_dia_concreto` | cualquier sesión con ejercicios |

---

---

## Capa de seguridad por lesión (Phase 28–29.1)

> Ante lesión, el plan no decide por el cuerpo; reduce riesgo, muestra contexto y deja la elección visible.

### Qué hace

- **Detecta** ejercicios sensibles cruzando `UserInjury.tags_restringidos` con `EjercicioBase.risk_tags`.
- **Frena progresión** per-ejercicio: solo congela el peso en los ejercicios afectados (no toda la sesión).
- **Diferencia por fase**: AGUDA/SUB_AGUDA → bloqueante (rojo), RETORNO → carga conservadora (ámbar).
- **Muestra alternativas revisables**: ejercicios del mismo grupo sin tags restringidos. El usuario elige, no el sistema.
- **Explica el motivo**: en briefing y entrenamiento activo, con tono y color distintos al freno contextual.

### Qué NO hace

- ❌ No diagnostica la lesión — eso es del médico.
- ❌ No sustituye ejercicios automáticamente.
- ❌ No garantiza seguridad en ningún caso.
- ❌ No modifica `PlanificadorHelms`.
- ❌ No elimina ejercicios sin elección explícita del usuario.
- ❌ No usa lenguaje absoluto: sin "prohibido", "nunca", "debes", "seguro".

### Jerarquía de frenos

```
1. aplicar_freno_contextual  → intervención / modo_esencial / carga/patrón semanal
2. aplicar_freno_lesion      → solo ejercicios con tags coincidentes (no sobreescribe el contextual)
Paralelo: lesion_aviso, preferencia_aplicada (siempre secundarios, no cambian estado)
```

### Cómo poblar risk_tags

```bash
python manage.py seed_risk_tags               # preview
python manage.py seed_risk_tags --dry-run     # aplicar
python manage.py seed_risk_tags --overwrite   # forzar actualización
```

21 ejercicios cubiertos: sentadilla, prensa, zancadas, hack, búlgara, sissy, saltos,
press militar, elevaciones, face pull, peso muerto, curl femoral, etc.

---

---

## Bloque 26–39 — Centro de decisiones, memoria y gobernanza

> El sistema no muestra todo lo que sabe; muestra primero lo que puede ayudarte a decidir.

### Capas del Centro de decisiones (`/clientes/plan/decisiones/`)

| Capa | Qué muestra | Cuándo aparece |
|---|---|---|
| Hero | Contadores: preferencias + ajustes + hipótesis | Siempre |
| Propuesta de experimento | Sugerencia experimental activa | Solo si existe |
| Lo que el plan recuerda | Preferencias aprendidas activas | Solo si hay |
| Ajuste activo | IntervencionPlan activa | Solo si hay |
| Señales acumuladas | Hipótesis desde senal_no_captada | Solo si hay (gobernada) |
| Por qué decidió así | Historial humanizado + evaluación | Solo si hay traces |
| Historial técnico | Pruebas + decisiones + esenciales | Colapsado |

### Ciclo completo de memoria (Phase 32–39)

```
dato → motor → decisión
                  ↓
               GymDecisionTrace (Phase 32)
                  ↓
               GymDecisionTraceEvaluation (Phase 34)
                  ↓                    ↓
            libero_margen          senal_no_captada ×3
            neutral                     ↓
            insuficiente          hipótesis acumulada (Phase 36)
                  ↓                     ↓
         Centro humanizado       sugerencia experimental (Phase 37)
         (Phase 33/35)                  ↓ usuario acepta
                             IntervencionPlan(vigilar_senal, 14 días)
                                         ↓
                             evaluar_fin_experimento → atenuada/persiste
```

### Gobernanza del silencio (Phase 38)

El sistema aprende cuándo dejar de insistir:

| Regla | Umbral | Resultado |
|---|---|---|
| Sin ocurrencias recientes | > 30 días | Silencio |
| Hipótesis demasiado antigua | > 60 días sin experimento | Silencio |
| Experimento atenuado reciente | < 45 días | Cooldown |
| Ignorada demasiadas veces | ≥ 2 en < 21 días | Pausa |
| Exceso de hipótesis | > 2 activas | Solo las más repetidas |

**Fallback**: si la gobernanza falla, devuelve hipótesis sin filtrar (no rompe el Centro).

### `vigilar_senal` — el tipo que no manda

`IntervencionPlan.TIPO_VIGILAR_SENAL = 'vigilar_senal'`:
- Creado cuando el usuario acepta una propuesta experimental.
- Solo observa. NO modifica cargas, distribución ni progresión.
- Explícitamente excluido de `get_intervencion_activa` y `evaluar_permiso_progresion`.
- Dura 14 días. Al expirar, `evaluar_fin_experimento` lee si la señal disminuyó.

> Una hipótesis puede ganar derecho a ser observada, no derecho a mandar.

### Evaluación posterior — vocabulario sellado (Phase 34, auditado Phase 31)

| Resultado | Cuándo | Lenguaje |
|---|---|---|
| `libero_margen` | Señal positiva posterior | "pareció", "señal refuerza provisionalmente" |
| `neutral` | Sin evidencia clara | "inconcluso", "sin señal clara" |
| `senal_no_captada` | Señal negativa posterior | "quizá", "puede que", "no hay suficiente evidencia" |
| `datos_insuficientes` | Sin sesión posterior | Silencio — no se muestra en Centro |

**Nunca**: "acertó", "falló", "correcto", "incorrecto", "el motor falló".

### Reglas narrativas permanentes (Phase 31 — 26 tests, 6ms, sin BD)

Auditadas en cada commit. Aplican a todos los mensajes del motor:
- Sin absolutos: "siempre", "nunca", "debes", "tienes que"
- Sin identidad: "eres alguien que", "esto te define"
- Sin diagnóstico: "garantizado", "sustitución segura", "esto es peligroso"
- Sin culpa: "no cumpliste", "fallaste", "incumplimiento"

### Tests del bloque (Phase 26–39)

```
clientes/tests_plan_decisiones.py        19  Centro: acceso, contexto, filtros
clientes/tests_trace_historial.py        14  Historial humanizado: sin JSON, sin técnico
clientes/tests_evaluacion_centro.py      12  Evaluación en Centro: sin veredicto
entrenos/tests_decision_trace.py         16  GymDecisionTrace: creación, campos, sin culpa
entrenos/tests_evaluacion_trace.py       16  Evaluación posterior: 4 resultados, vocabulario
entrenos/tests_hipotesis.py              12  Hipótesis acumuladas: detección, gobernanza
entrenos/tests_hipotesis_sugerencia.py   16  Propuesta experimental: ciclo completo
entrenos/tests_gobernanza.py             13  Gobernanza: silencio, max, cooldowns
entrenos/tests_auditoria_narrativa.py    26  Auditoría: sin absolutos, sin culpa, sin identidad
```

---

## Auditoría de integración global (Phase 46)

> El sistema ya tiene muchas capas. Ahora debe demostrar que juntas no pesan más que la decisión que ayudan a tomar.

### Tests automáticos — `entrenos/tests_integracion_global.py` (15 tests)

| Contrato | Verificado |
|---|---|
| `vigilar_senal` nunca afecta cargas | ✓ |
| JOI silencio si texto vacío | ✓ |
| Panel ≤3 señales en día complejo | ✓ |
| Distribución suprimida por PRF mismo patrón | ✓ |
| `¿Por qué hoy?` no renderiza en día limpio | ✓ |
| Centro sin historial si no hay traces | ✓ |
| `datos_insuficientes` no aparece en Centro | ✓ |
| Hipótesis stale (>30 días) silenciada | ✓ |
| Sin lenguaje prohibido en motor | ✓ |
| Fallo en capas no rompe panel ni Centro | ✓ |

### Checklist visual (manual — aplicar con el sistema real)

```
¿Entiendo qué toca hoy en 5 segundos?
¿Entiendo por qué sin abrir 3 secciones?
¿JOI suma o distrae?
¿El Centro ordena o abruma?
¿Hay alguna frase que suene demasiado segura?
¿Hay algo repetido en panel + Centro?
¿Hay tarjetas vacías?
```

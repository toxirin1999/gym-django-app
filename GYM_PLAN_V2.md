# Gym Plan V2 — Sesiones vivas

> Phase 1–21.1 — Mayo 2026 — ESTADO ESTABLE

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

## Lo que el sistema NO hace todavía (intencionalmente)

- ❌ No convierte pruebas favorables en preferencias permanentes (Phase 22)
- ❌ No modifica PlanificadorHelms automáticamente
- ❌ No reemplaza ejercicios por lesión activa
- ❌ No reorganiza la semana en silencio
- ❌ No escribe en ManualDavid desde el análisis semanal
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

## Tests (~170+)

```
entrenos/tests_sesion_programada.py      76  sesiones, contexto, esencial, análisis, JOI
entrenos/tests_progresion_contextual.py  15  freno de progresión
entrenos/tests_sugerencias.py            38  sugerencias, intervenciones, evaluación, continuidad
entrenos/tests_distribucion_semanal.py   24  distribución, Phase 20/21
clientes/tests_panel_ux.py               17  regresión del contexto del panel
joi/tests_bloque_semanal.py              29  integración JOI, lenguaje
```

---

## Próxima fase: Phase 22 — Preferencias aprendidas

**Pregunta filosófica antes de implementar:**
> ¿Cuánta evidencia necesita el sistema antes de dejar de "probar" y empezar a "preferir"?

**Condición mínima propuesta:**
- Misma prueba favorable ≥ 2 veces
- Usuario aceptó repetir o consolidar ambas veces
- Sin cooldown activo de ese tipo

**Modelo conceptual:** `PreferenciaPlanAprendida` (nueva tabla)

**Regla madre de Phase 22:**
> Una preferencia aprendida no es una orden; es una inclinación del plan basada en evidencia repetida y aceptada.

**Orden de implementación:**
- Phase 22A: modelo + flujo de aceptación
- Phase 22B: mostrar "Preferencia activa"
- Phase 22C: señal blanda en el motor (no cambia plan)
- Phase 22D: afecta generación de sesiones (Phase futura)

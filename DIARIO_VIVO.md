# Diario Vivo — Sistema de presencia, gestos y señales

> Diario base + Simbiosis 1.1–1.4 + Hábitos/Gestos 1.1–1.5 + Puente Diario-Gym 3.0–3.5 — Mayo 2026 — ESTADO ESTABLE · 5 tests de auditoría vocabulario

---

## Regla madre

> El Diario no mide. Observa.
> No hay cumplimiento, no hay racha, no hay fallo.
> Hay presencia, ausencia y repetición — y JOI los nombra solo cuando hay señal clara.

---

## Bloques cerrados (mayo 2026)

### 1. Diario base

- Apertura de mañana: intención del día, semáforo libre (sin presión de la noche anterior)
- Cierre de noche: reflexión + estado de ánimo + etiquetas + Acto de Soberanía
- Lectura de la semana: síntesis semanal accesible desde el cierre
- Portada semanal: vista de la semana en curso (objetivos, días, estado)

### 2. Simbiosis — red de personas (1.1–1.4)

- **Radar legible** (1.1): personas que aparecen en el diario, ordenadas por señal reciente, no por acumulación histórica
- **Añadir/Ignorar** (1.2): consecuencias reversibles — añadir vincula interacciones previas; ignorar descarta sin borrar historial
- **Perfil trazable** (1.3): tipo de relación, frecuencia, rol, notas — editable
- **Reaparición por señal viva** (1.4): una persona reaparece en el radar porque fue mencionada recientemente, no porque tenga muchas entradas antiguas

Regla ética de Simbiosis: **JOI no decide quién importa. Solo muestra lo que se repite.**

### 3. Hábitos → Gestos (1.1–1.5)

- **Dashboard** (1.1): hábitos presentados como gestos/señales — sin rachas, sin porcentajes visibles
- **Formulario** (1.2): creación sin lenguaje moralizante — sin "deberías", "tienes que", "logra"
- **Rutas** (1.3): acceso secundario desde Diario (Explorar → Gestos), no protagonista
- **JOI lee gestos** (1.4): presencia ≥4/7 → apareció varias veces; ausencia tras actividad previa → sin aparecer; reaparición de gesto negativo → volvió a aparecer. Máximo 2 gestos en el prompt. Silencio si no hay señal clara.
- **Auditoría vocabulario** (1.5): templates limpios en todo el módulo; 5 tests de auditoría protegen el contrato de JOI

Cadena completa: UI → gestos → JOI → prompts → tests de auditoría

### 4. Puente Diario-Gym (3.0–3.5)

- **Señal corporal** (3.0): `obtener_senal_corporal_diario()` clasifica la señal de los últimos 5 días de `SeguimientoVires` — badge informativo en el dashboard, nunca bloquea ni modifica cargas
- **¿Por qué hoy?** (3.1): `explicacion_decision_service.py` integra la señal corporal del diario como bullet final en la explicación colapsable de la sesión
- **Sugerencia de margen** (3.2): si la señal corporal es negativa y la carga es alta, se genera una `SugerenciaPlan` autorizable — el usuario decide si aplica
- **Contraste post-entreno** (3.3): `contrastar_senal_vs_entreno()` compara señal declarada antes vs RPE real después de la sesión
- **Tendencia multi-semana** (3.4): `calcular_tendencia_senal()` agrega 4 semanas para detectar patrón sostenido (no evento aislado)
- **Vigilancia autorizada** (3.5): `IntervencionPlan.TIPO_VIGILAR_SENAL` — el plan observa la señal durante 2 semanas sin cambiar cargas; JOI la nombra si es relevante

---

## Lo que el sistema YA hace

**Gestos:**
- Detección automática desde `ProsocheHabito` + `ProsocheHabitoDia` + `TriggerHabito`
- Ventana de 7 días para señal de presencia; comparativa con semana anterior para señal de ausencia
- `construir_contexto()` sección 10.5: `gestos_señales` (máx. 3); `_prompt_apertura_manana()` inyecta máx. 2

**JOI:**
- `cierre_ayer` en contexto: reflexión nocturna, estado de ánimo, Acto de Soberanía
- Vocabulario prohibido verificado: racha, cumplimiento, lograste, fallaste, %, recaída (fuera de contexto técnico)
- Semáforo sincronizado: `estado_entreno == 'descanso'` → semáforo no muestra EMPUJAR

**Puente Diario-Gym:**
- Badge corporal en dashboard (Phase 3.0) — informativo, sin bloqueo
- Señal integrada en "¿Por qué hoy?" (Phase 3.1)
- `SugerenciaPlan` desde señal corporal negativa + carga alta (Phase 3.2)
- Contraste señal vs entreno real (Phase 3.3)
- Tendencia 4 semanas (Phase 3.4)
- `IntervencionPlan.TIPO_VIGILAR_SENAL` — vigilancia 2 semanas sin cambiar cargas (Phase 3.5)

---

## Lo que el sistema NO hace todavía (intencionalmente)

- ❌ No muestra "rachas" visibles — el campo interno `racha` existe pero no se muestra como logro
- ❌ No genera notificaciones push por inactividad de gestos
- ❌ No cruza gestos con métricas de entrenamiento (ej: "cuando no meditas, tu RPE sube")
- ❌ No modifica cargas basándose en el diario — la señal corporal informa y sugiere, pero no actúa sin autorización explícita del usuario
- ❌ No genera informe semanal de gestos — JOI menciona señales, no resúmenes de cumplimiento
- ❌ No puntúa ni gamifica gestos
- ❌ Simbiosis no tiene puente con el plan de entrenamiento todavía

---

## Modelos clave

| Modelo | App | Propósito |
|---|---|---|
| `ProsocheMes` | `diario` | Contenedor mensual: objetivos, revisión final |
| `ProsocheHabito` | `diario` | Gesto del mes: nombre, tipo (positivo/negativo), diseño habit loop |
| `ProsocheHabitoDia` | `diario` | Presencia diaria: `dia` (1-31), `completado` bool |
| `TriggerHabito` | `diario` | Registro de impulso: `cediste` bool, emoción, situación, aprendizaje |
| `ProsocheDiario` | `diario` | Entrada diaria: reflexión, tareas, soberanía |
| `BitacoraDiaria` | `clientes` | Checkin biométrico: energía, sueño, FC, HRV — alimenta JOI y semáforo |
| `SeguimientoVires` | `diario` | Seguimiento corporal diario: energía, estrés, sueño, molestia, cierre |
| `IntervencionPlan` (`TIPO_VIGILAR_SENAL`) | `entrenos` | Vigilancia 2 semanas sin cambiar cargas |

---

## Servicios

```
diario/services/
  estado_diario.py                  Estado mañana/noche — visible en dashboard
  senales_entrenamiento.py          Señal corporal del diario (Phase 3.0–3.5)
    obtener_senal_corporal_diario() Clasifica señal de últimos 5 días de SeguimientoVires
    contrastar_senal_vs_entreno()   Compara señal declarada vs RPE real post-sesión
    calcular_tendencia_senal()      Agrega 4 semanas para detectar patrón sostenido

diario/
  insights_engine.py                Detección automática de patrones del diario

entrenos/services/
  explicacion_decision_service.py   Integra señal corporal como bullet en "¿Por qué hoy?"

joi/services.py
  construir_contexto()              Sección 10.5: gestos_señales (máx. 3)
  _prompt_apertura_manana()         Inyección de gestos con label de tono (máx. 2)
  gestos_txt                        Instrucción final: solo presencia/ausencia/repetición

joi/tests.py
  TestGestosVocabularioJOI          5 tests — vocabulario prohibido en datos de gestos
```

---

## Reglas permanentes (no romper)

1. **JOI observa, no empuja.** El prompt de gestos tiene instrucción inline + instrucción final. Si se modifica el prompt, preservar ambas.
2. **Gestos = presencia/ausencia/repetición.** Nunca racha, porcentaje, cumplido, fallado, recaída, cediste en texto visible ni en salida de JOI para gestos.
3. **Silencio válido.** Si `gestos_señales` está vacío, JOI no menciona gestos. No añadir fallback que fuerce mención.
4. **Máximo 2 gestos en el prompt.** El límite existe para que JOI no convierta la apertura en informe de hábitos.
5. **Umbrales sanos.** `aparecio_varias` requiere ≥4/7 días. `ausente` requiere ≥3 presencias la semana anterior. No bajar sin revisar el contrato de JOI.
6. **`recaídas` solo en contexto técnico.** Permitido en `habito_analisis_patrones.html` (análisis de triggers clínico). No en dashboard, no en JOI, no en seguimiento diario.
7. **El semáforo hereda `estado_entreno`.** Si el motor de sesiones dice descanso, `_es_descanso_plan` incluye `estado_entreno == 'descanso'` — el semáforo no puede decir EMPUJAR.
8. **La señal corporal informa, nunca bloquea.** `obtener_senal_corporal_diario()` genera badge y sugerencia; nunca modifica cargas directamente. La `IntervencionPlan` requiere autorización del usuario.
9. **JOI no decide quién importa en Simbiosis.** Solo muestra lo que se repite. El radar refleja menciones recientes, no jerarquía histórica acumulada.
10. **Todos los servicios del Diario degradan silenciosamente.** Si falla la detección de gestos o la señal corporal, JOI sigue funcionando. El `try/except` es obligatorio en `construir_contexto`.

---

## Tests

```
joi/tests.py
  TestGestosVocabularioJOI
    test_aparecio_varias_sin_palabras_prohibidas
    test_ausente_sin_palabras_prohibidas
    test_reaparecio_sin_palabras_prohibidas
    test_sin_gestos_no_genera_seccion
    test_maximo_dos_gestos_en_prompt
```

---

## Backlog consciente

| Item | Por qué no está aún |
|---|---|
| Cruce gestos × métricas de entrenamiento | Requiere ≥4 semanas de datos reales para tener señal fiable |
| Notificación de ausencia prolongada de gestos | Riesgo de convertirse en recordatorio de cumplimiento — necesita diseño cuidadoso |
| Informe semanal de gestos para JOI | Se añadiría cuando haya patrón claro en los datos reales |
| Cruce Simbiosis × estado del diario | Simbiosis está estable pero sin puente con el plan todavía |
| JOI integra tendencia corporal multi-semana | `calcular_tendencia_senal()` existe; pendiente de inyección en `construir_contexto` |
| Panel de sueño / histórico nocturno | `horas_sueno` y `calidad_sueno` ya existen en `BitacoraDiaria` y entran en JOI/semáforo. Aplazar hasta tener ≥4 semanas de datos reales. Antes de construirlo, comprobar si JOI ya nombra el sueño cuando hay señal clara. Si no lo traduce bien, primero mejorar la traducción en JOI; después, si sigue faltando, Phase Sueño 1.0 (histórico 7/14/30 días + horas + calidad + relación con energía del día siguiente + mensaje determinista). Sin score de sueño, sin consejos genéricos, sin medicalizar. |

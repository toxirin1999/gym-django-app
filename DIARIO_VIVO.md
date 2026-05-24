# Diario Vivo — Sistema de presencia, gestos y señales

> Phases 1.1–1.5 (Hábitos) + Phases Diario base + Simbiosis + Diario-Gym — Mayo 2026 — ESTADO ESTABLE · 5 tests de auditoría vocabulario

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

### 2. Simbiosis — red de personas

- Radar de relaciones (energía bilateral)
- Perfiles: tipo de relación, frecuencia, rol, notas
- Gobernanza: reglas propias de cada relación

### 3. Hábitos → Gestos (1.1–1.5)

- **Dashboard** (1.1): hábitos presentados como gestos/señales — sin rachas, sin porcentajes visibles
- **Formulario** (1.2): creación sin lenguaje moralizante — sin "deberías", "tienes que", "logra"
- **Rutas** (1.3): acceso secundario desde el Diario (Explorar → Gestos), no protagonista
- **JOI lee gestos** (1.4): presencia ≥4/7 → apareció varias veces; ausencia tras actividad previa → sin aparecer; reaparición de gesto negativo → volvió a aparecer. Máximo 2 gestos en el prompt. Silencio si no hay señal clara.
- **Auditoría vocabulario** (1.5): templates limpios en todo el módulo; 5 tests de auditoría protegen el contrato de JOI

### 4. Puente Diario-Gym

- Señal corporal del cierre → contexto de JOI al día siguiente
- Contraste energía declarada vs carga real del plan
- Tendencia detectada (energía baja + carga alta → semáforo vigilado)
- Vigilancia autorizada: si el sistema detecta fatiga extradeportiva, JOI lo nombra sin empujar

---

## Lo que el sistema YA hace

- Gestos detectados automáticamente desde `ProsocheHabito` + `ProsocheHabitoDia` + `TriggerHabito`
- Ventana de 7 días para señal de presencia; comparativa con semana anterior para señal de ausencia
- `construir_contexto()` en `joi/services.py` incluye sección `gestos_señales` (máx. 3)
- `_prompt_apertura_manana()` inyecta máx. 2 gestos con instrucción de tono inline
- Vocabulario prohibido en texto visible: racha (fuera de variable interna), cumplimiento, lograste, fallaste, %, recaída (fuera de análisis de triggers)
- `cierre_ayer` en contexto JOI: reflexión nocturna, estado de ánimo, Acto de Soberanía
- Semáforo sincronizado: si `estado_entreno == 'descanso'`, el semáforo no muestra EMPUJAR
- CTA de descanso neutral: "Ver plan de la semana" (no invita a saltarse el descanso)

---

## Lo que el sistema NO hace todavía (intencionalmente)

- ❌ No calcula "rachas" visibles — el campo interno `racha` existe pero no se muestra como logro
- ❌ No genera notificaciones push por inactividad de gestos
- ❌ No cruza gestos con métricas de entrenamiento (ej: "cuando no meditas, tu RPE sube")
- ❌ No modifica el plan de entrenamiento basándose en el estado del diario (solo informa a JOI)
- ❌ No genera informe de gestos por semana — JOI menciona señales, no hace resúmenes de cumplimiento
- ❌ No puntúa ni gamifica gestos

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

---

## Servicios

```
diario/
  services/estado_diario.py        Estado mañana/noche — visible en dashboard
  insights_engine.py               Detección automática de patrones del diario

joi/services.py
  construir_contexto()             Sección 10.5: gestos_señales (máx. 3)
  _prompt_apertura_manana()        Inyección de gestos con label de tono (máx. 2)
  gestos_txt                       Instrucción final: solo presencia/ausencia/repetición

joi/tests.py
  TestGestosVocabularioJOI         5 tests — vocabulario prohibido en datos de gestos
```

---

## Reglas permanentes (no romper)

1. **JOI observa, no empuja.** El prompt de gestos tiene instrucción inline + instrucción final. Si se modifica el prompt, preservar ambas.
2. **Gestos = presencia/ausencia/repetición.** Nunca racha, porcentaje, cumplido, fallado, recaída, cediste en texto visible ni en salida de JOI para gestos.
3. **Silencio válido.** Si `gestos_señales` está vacío, JOI no menciona gestos. No añadir fallback que fuerce mención.
4. **Máximo 2 gestos en el prompt.** El límite existe para que JOI no convierta la apertura en informe de hábitos.
5. **Umbrales sanos.** `aparecio_varias` requiere ≥4/7 días. `ausente` requiere ≥3 presencias la semana anterior. No bajar estos umbrales sin revisar el contrato de JOI.
6. **`recaídas` solo en contexto técnico.** El término está permitido en `habito_analisis_patrones.html` (análisis de triggers clínico). No en dashboard, no en JOI, no en textos de seguimiento diario.
7. **El semáforo hereda `estado_entreno`.** Si el motor de sesiones dice descanso, el semáforo no puede decir EMPUJAR. El cálculo de `_es_descanso_plan` incluye `estado_entreno == 'descanso'`.
8. **Todos los servicios del Diario degradan silenciosamente.** Si falla la detección de gestos, JOI sigue funcionando sin gestos. El `try/except` es obligatorio en `construir_contexto`.

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

## Lo que falta (backlog consciente)

| Item | Por qué no está aún |
|---|---|
| Cruce gestos × métricas de entrenamiento | Requiere ≥4 semanas de datos reales para tener señal fiable |
| Notificación de ausencia prolongada | Riesgo de convertirse en recordatorio de cumplimiento — necesita diseño cuidadoso |
| Informe semanal de gestos para JOI | Existe el resumen semanal gym; gestos se añadirían cuando haya patrón claro en los datos |
| Cruce Simbiosis × estado del diario | Simbiosis está estable pero sin puente con el plan todavía |

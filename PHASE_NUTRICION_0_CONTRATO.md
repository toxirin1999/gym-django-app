# 📋 PHASE NUTRICIÓN 0 — CONTRATO DEL PRIMER SENSOR

> 🔒 **Congelado hasta que termine el bootstrap.** Solo se edita para corregir errores o ambigüedades — no para enriquecerlo. Describe qué intentamos demostrar, cómo lo intentamos demostrar y cuándo aceptaremos que la hipótesis era incorrecta. Todo lo demás es implementación (o, antes, diseño experimental) y vive en otro documento. `PHASE_NUTRICION_1` no se abre — ni como borrador — hasta que Nutrición 0 se la haya ganado.

**Status**: FASE DE DISEÑO (sin código)
**Objetivo**: Validar si una señal nutricional mínima puede vivir dentro del organismo sin convertirse en otra app de hábitos
**Principio**: El usuario nunca registra una comida. Le dice al organismo si ha podido alimentarlo.
**Dirección arquitectónica**: [[DISPONIBILIDAD_RECURSOS]] — este documento es el experimento concreto, no la identidad final del órgano

---

## 🎯 Qué resuelve

El sistema antiguo de nutrición (`nutricion_app_django`) responde:

> ¿Cuál es la dieta óptima?

Nutrición 0 responde una pregunta distinta:

> ¿Ha tenido hoy el organismo los recursos mínimos para seguir construyéndose?

No son el mismo dominio aunque compartan el tema. Por eso Fase 0 no reutiliza modelos, servicios ni pantallas del sistema antiguo.

**No es**: una pantalla nueva de "modo nutrición". **Es**: un momento donde el organismo pregunta "¿has podido alimentarme?" y la respuesta tarda dos segundos.

---

## 🔒 Bounded context — separación absoluta

Durante toda la Fase 0, el bootstrap no debe conocer la existencia del sistema antiguo de nutrición.

- Sin imports cruzados hacia `nutricion_app_django`.
- Sin reutilización de `PerfilNutricional`, `RegistroBloques`, `TargetNutricionalDiario` ni ningún modelo del sistema Zona.
- Si algún día ambos convergen, será mediante una migración deliberada, nunca mediante reutilización oportunista.

---

## 📐 MODELO MÍNIMO (3 campos)

```
RegistroDisponibilidad
  timestamp   — cuándo
  nivel       — cuánto (A / B / C, o escala equivalente a definir)
  origen      — de dónde (casa / fuera / recurso rápido, etc.)
```

Deliberadamente fuera del modelo persistido:

| Candidato descartado | Por qué no se persiste |
|---|---|
| `función` (Activación, Construcción, Estabilidad, Reposición, Recuperación) | Se infiere de `timestamp` + entrenamientos ya registrados. Preguntarlo mezcla observación con interpretación y añade fricción que el organismo puede evitarse. |
| `entrenamiento_cercano` (FK) | Ya existe en `entrenos`. Se infiere por proximidad temporal, no se duplica como campo propio. |

Casi toda la inteligencia pertenece al organismo, no al formulario.

---

## 🧠 Inferencias derivadas (no persistidas)

```
inferir_funcion(registro, entrenamientos_usuario) → función

1. Si es la primera ingesta del día (no hay registro previo hoy)
   → Activación

2. Si existe un EntrenoRealizado / HyroxSession cerrado en las
   últimas N horas (umbral a validar en implementación, ej. 60 min)
   → Reposición

3. Si no aplica ninguna de las anteriores
   → Construcción / Estabilidad (a diferenciar por franja horaria —
     pendiente de definir el corte exacto en Phase Nutrición 1)
```

Este pseudocódigo es la propuesta de partida, no el contrato cerrado — se valida con datos reales antes de fijar los umbrales.

---

## 📍 Puntos de entrada permitidos

Ninguna pantalla nueva. El registro habita momentos que ya existen:

- Apertura de mañana (JOI)
- Cierre de entrenamiento (`entrenos`)
- Cierre de noche (`diario`)

*(Pendiente de decidir en la siguiente iteración: si estos tres bastan para Fase 0 o si se reduce a uno solo para minimizar superficie.)*

---

## ✅ GATES DE SALIDA

**Gate 0 — Principio de falsabilidad** (protege el método, no el bootstrap)

Los Gates 1–4 validan si el bootstrap funciona. El Gate 0 pertenece a otra categoría: valida que seguimos siendo fieles al método con el que se construye JOI.

> La existencia del órgano de Disponibilidad de Recursos es una hipótesis arquitectónica, no un objetivo del proyecto.
>
> Si Nutrición 0 no supera los criterios definidos en esta fase, el proyecto acepta explícitamente que este órgano puede no construirse, rediseñarse o posponerse indefinidamente.
>
> Ninguna fase posterior podrá utilizar la metáfora o el atractivo conceptual del órgano como justificación para continuar una implementación cuya señal no haya sido demostrada.

Este gate existe porque la idea es elegante, y precisamente por eso es peligrosa: protege el proyecto de enamorarse de una buena idea en lugar de exigirle evidencia.

> **Los gates no son objetivos de implementación. Son criterios de aprendizaje.**
>
> Su función no es demostrar que Nutrición 0 funciona, sino determinar honestamente si la hipótesis arquitectónica dispone de evidencia suficiente para continuar.

**Gate 1 — Fricción sostenida**

*Hipótesis*: el registro puede mantenerse de forma continuada sin convertirse en una tarea.

*Criterios de éxito*:
- Registro presente en al menos 5 de cada 7 días.
- Durante 3 semanas consecutivas.
- Tiempo medio de registro inferior a 10 segundos.

*Qué valida*: que el punto de entrada y el modelo de interacción tienen una fricción suficientemente baja para integrarse en la vida real del usuario.

*Qué invalida*: si este gate falla, la conclusión no es que el usuario "no sea constante". La primera hipótesis que debe revisarse es que el diseño del registro introduce demasiada fricción.

**Gate 2 — Consistencia semántica**

*Hipótesis*: la clasificación A/B/C es lo bastante intuitiva como para que el usuario la aplique de forma consistente.

*Criterios de éxito*: tasa de corrección posterior (cambiar un A por un B, etc.) inferior al 15 %.

*Qué valida*: que el modelo mental del usuario coincide con el modelo conceptual del sistema.

*Qué invalida*: si este gate falla, el problema no debe atribuirse al usuario sino a la taxonomía. El sistema deberá simplificar o redefinir las categorías antes de continuar.

**Gate 3 — Señal útil**

*Hipótesis*: los datos recogidos contienen información suficiente para revelar patrones que no puedan obtenerse razonablemente sin el sistema — no basta con confirmar lo evidente.

Que David cene peor tras 8 horas sin comer es una intuición obvia y no cuenta. Lo que sí cuenta es descubrir, por ejemplo, que ese efecto solo aparece los días con entrenamiento, que desaparece cuando hay un recurso C a media tarde, o que ocurre únicamente cuando la primera ingesta del día también fue insuficiente.

*Criterios de éxito*: debe aparecer al menos un patrón claramente observable en los datos recogidos durante el piloto — no plausible, apreciable objetivamente. Ejemplos: huecos superiores a seis horas → aumento visible de recursos C; entrenamientos sin reposición → deterioro consistente de la siguiente ingesta; diferencias repetidas entre días laborales y fines de semana.

*Qué valida*: que existe una señal real susceptible de convertirse en conocimiento para el organismo — conocimiento que justifique la existencia del sistema, no una confirmación de lo que ya se sabía.

*Qué invalida*: si este gate falla, no significa necesariamente que el órgano sea incorrecto. Puede significar que el modelo mínimo no está capturando la información adecuada. Antes de ampliar el alcance del órgano deberá revisarse el modelo de observación.

**Gate 4 — Capacidad de intervención** (filosófico, no técnico)

Durante el piloto debe existir al menos un caso documentado donde una lectura del sistema haya provocado una decisión distinta del usuario. Ejemplos:

- Merendar antes porque el organismo detectó un hueco excesivo.
- Elegir un recurso C en lugar de saltarse completamente la ingesta.
- Añadir proteína a la cena después de detectar un patrón repetido.

No importa cuál. Importa demostrar que el dato puede modificar comportamiento. Si en tres semanas el sistema produce datos precisos pero el usuario sigue llegando vacío a las nueve de la noche, Fase 0 ha construido un sistema de observación — no un órgano. Eso es fallo de gate, no éxito parcial.

---

## ❌ QUÉ NO HACE (Fase 0)

🚫 No implementa hidratación, sueño ni ningún otro recurso — eso es dirección futura de [[DISPONIBILIDAD_RECURSOS]], no alcance de esta fase
🚫 No pregunta la función de la ingesta — se infiere
🚫 No persiste el entrenamiento cercano — se infiere por proximidad
🚫 No reutiliza modelos ni pantallas del sistema antiguo de nutrición
🚫 No puntúa, no gamifica, no compensa, no castiga
🚫 No genera una pantalla o "modo nutrición" nuevo

---

## 🚀 PRÓXIMO PASO

Contrato de gates cerrado (Gate 0 + Gates 1–4). Queda pendiente: fijar el umbral temporal de `inferir_funcion` y decidir cuántos de los tres puntos de entrada entran en el piloto real.

---

**Esperando validación antes de Phase Nutrición 1.**

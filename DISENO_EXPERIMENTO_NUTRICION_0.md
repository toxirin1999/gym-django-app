# 🧪 DISEÑO DEL EXPERIMENTO — Nutrición 0

**Status**: FASE DE DISEÑO EXPERIMENTAL (sin código, sin decisiones de implementación)
**Relación con el contrato**: desarrolla las preguntas abiertas de [[PHASE_NUTRICION_0_CONTRATO]] (puntos de entrada, sección "Puntos de entrada permitidos") bajo los principios de [[DISPONIBILIDAD_RECURSOS]]
**Ver también**: `EXPERIENCIAS_ORGANISMO.md` — documento vivo (no congelado) con las escenas que este experimento intenta hacer posibles
**Qué es este documento**: un protocolo experimental — hipótesis, justificación, riesgo, qué observaríamos, qué decisión tomaríamos si falla
**Qué NO es**: una especificación técnica. Si al final de este documento ya sabemos qué punto de entrada vamos a implementar, hemos ido demasiado deprisa. El objetivo es llegar a "estas son las hipótesis que merece la pena poner a prueba", no a "esta es la solución". El diseño técnico (modelo, migración, servicio, tests) es un documento posterior y distinto.

---

## H0 — ¿Son realmente cinco preguntas, o es una sola?

**Hipótesis**: Las preguntas de entrada del contrato (puntos de entrada candidatos, criterio de selección, qué ocurre si no se usa ninguno, recuperación de dato perdido, datos transitorios no persistidos) no son cinco decisiones independientes. Son distintas caras de una única pregunta:

> ¿Cómo llega una observación nutricional al organismo con la mínima fricción posible?

**Justificación**: todas comparten la misma variable subyacente — fricción de captura — y no un trade-off propio de dominio distinto.

**Riesgo**: forzar la reducción puede ocultar un problema real que no es de fricción (por ejemplo, validez de medición o alcance del modelo persistido), y tratarlo como si lo fuera lleva a una solución equivocada.

**Qué observamos al desarrollar las cuatro ramas** (abajo): si conservan un análisis independiente o colapsan sobre la misma evidencia.

**Resultado de la observación**: H0 se sostiene solo parcialmente. Rama 1 (puntos de entrada) y Rama 2 (criterio de selección) sí resultan ser la misma pregunta vista desde dos ángulos — "dónde" y "cuál", ambos gobernados por fricción. Ramas 3 y 4, en cambio, no se resuelven optimizando fricción: Rama 3 es un problema de validez de medición del Gate 1, y Rama 4 es un problema de alcance del modelo persistido frente a instrumentación del piloto. **No se fuerza una unificación en un solo bloque.** Se mantienen cuatro ramas, pero 1 y 2 quedan marcadas como acopladas.

---

## Concepto transversal — Oportunidad de observación

Gate 1 no pretende responder "¿cuántos registros hubo?". Pretende responder: "¿era razonablemente fácil registrar cuando existía una oportunidad real de hacerlo?". Esa pregunta no se puede leer directamente sobre el calendario — no todas las jornadas ofrecen la misma oportunidad de registrar (un día sin abrir JOI no es comparable a un día con check-in matutino y entrenamiento).

El experimento distingue tres estados, no dos:

- **Observación posible**: el sistema tuvo una ocasión razonable de preguntar (se activó al menos un punto de entrada ese día).
- **Observación realizada**: el usuario respondió.
- **Observación perdida**: existía observación posible pero no hubo respuesta.

Solo la observación perdida aporta información sobre fricción. Un día sin ninguna observación posible no dice nada sobre el punto de entrada — dice que no hubo ocasión de usarlo, y confundir ambas cosas mide dos fenómenos distintos como si fueran uno solo:

> "El usuario no registró la nutrición" ≠ "el punto de entrada tenía demasiada fricción".

**Regla metodológica**: el experimento nunca evalúa la fricción sobre unidades temporales (días), sino sobre oportunidades de observación generadas por el propio diseño experimental.

Esto no modifica el contrato. `PHASE_NUTRICION_0_CONTRATO.md` sigue congelado y el texto del Gate 1 no cambia — lo que cambia es cómo el protocolo experimental lo interpreta: "5 de cada 7 días" se lee sobre días con al menos una observación posible, no sobre el calendario natural del piloto. Esta definición es independiente de la implementación concreta (app abierta, widget futuro, notificación contextual) y seguiría siendo válida aunque cambie la tecnología del punto de entrada.

---

## Rama 1+2 — Punto de entrada y criterio de selección (acopladas por H0)

**Hipótesis H1**: distribuir la pregunta en varios puntos de contacto que ya existen (apertura de mañana, cierre de entrenamiento, cierre de noche) reduce la fricción total frente a concentrarla en uno solo, porque cada punto captura la ingesta más reciente y relevante a ese momento del día.

- *Justificación*: cierre de entrenamiento es el momento natural para capturar la ingesta de Reposición; cierre de noche, la cena. Concentrar todo en un único punto (p. ej. solo apertura de mañana) obliga al usuario a recordar ingesta de horas antes.
- *Riesgo*: multiplicar puntos de contacto multiplica también el número de veces que el organismo "pregunta" — puede violar el principio madre de [[DISPONIBILIDAD_RECURSOS]] (el organismo no persigue al usuario).
- *Qué observaríamos*: cuántos de los tres puntos de entrada se usan realmente durante el piloto, y si alguno queda sistemáticamente ignorado.
- *Decisión si falla*: colapsar a un único punto de entrada — el de mayor uso real, no el que parecía más lógico a priori.

**Hipótesis H2**: no hace falta fijar de antemano un criterio de selección entre puntos de entrada. El sistema puede ofrecer la pregunta en cualquiera de los puntos disponibles y quedarse con la primera respuesta del día; el propio comportamiento del usuario revela cuál es el punto dominante, sin que el organismo tenga que decidirlo ni preguntarlo.

- *Justificación*: coherente con "el organismo infiere, no pregunta" (nota abierta de [[DISPONIBILIDAD_RECURSOS]]).
- *Riesgo*: sin criterio explícito, un mismo día podría activar la pregunta en más de un punto de contacto, sintiéndose como insistencia — exactamente lo que el principio madre prohíbe.
- *Qué observaríamos*: frecuencia con la que un mismo día dispara la pregunta en más de un punto de entrada.
- *Decisión si falla*: fijar un orden de prioridad determinista (si ya hubo respuesta en apertura de mañana, no se repregunta en cierre de entrenamiento el mismo día).

---

## Rama 3 — Ausencia total y oportunidad de observación

**Hipótesis H3**: el silencio de un día sin ninguna observación posible es un dato válido en sí mismo y no requiere ninguna acción de recuperación. Es distinto de una observación perdida (hubo observación posible, no hubo respuesta), que sí es información sobre fricción.

- *Justificación*: coherente con "nunca se registra manualmente una ausencia" de [[DISPONIBILIDAD_RECURSOS]], precisado ahora con el concepto de oportunidad de observación — el organismo no confunde "no tuvo ocasión" con "tuvo ocasión y no respondió".
- *Riesgo*: si el diseño de los puntos de entrada no genera una señal explícita de cuándo hubo observación posible, no hay forma de distinguirla de la ausencia total, y la hipótesis se vuelve imposible de comprobar.
- *Qué observaríamos*: para cada día del piloto, clasificar en observación posible / realizada / perdida (ver sección "Oportunidad de observación" arriba); comparar si el ratio observación perdida / observación posible es una medida más estable de fricción que el ratio original sobre días naturales de calendario.
- *Decisión si falla*: si las tres categorías no resultan detectables de forma fiable con los puntos de entrada actuales, esta hipótesis cae — no se toca el Gate 1, se revisa si el diseño de puntos de entrada necesita producir esa señal explícita de oportunidad.

---

## Rama 4 — Datos transitorios que necesita el piloto pero no el modelo

**Hipótesis H4**: el piloto necesita capturar, temporalmente, más contexto del que `RegistroDisponibilidad` persistirá — por ejemplo, qué punto de entrada concreto se usó, cuánto tardó el usuario en responder, si hubo una corrección posterior de nivel — sin que estos campos formen parte del modelo mínimo de 3 campos del contrato.

- *Justificación*: los Gates 1 y 2 exigen medir tiempo de registro y tasa de corrección; esa telemetría es instrumentación del experimento, no conocimiento que el organismo deba conservar a largo plazo.
- *Riesgo*: si esta instrumentación se mezcla con el modelo persistido, "el modelo mínimo de 3 campos" deja de ser mínimo, y el contrato quedaría desactualizado sin haberlo decidido explícitamente.
- *Qué observaríamos*: si es viable capturar esta telemetría en una capa completamente separada (logs de evento, no un modelo de base de datos) sin tocar `RegistroDisponibilidad`.
- *Decisión si falla*: aceptar 1–2 campos adicionales transitorios en el modelo, marcados explícitamente como "solo piloto — eliminar en Nutrición 1 si el órgano se aprueba".

---

## Hipótesis de destino (no normativa)

Añadido tras la comprobación de propósito del 2026-07-11 (¿qué comportamiento nuevo adquiere el organismo?). No autoriza wiring en Fase 0. No toca el contrato ni el modelo.

**H-D1 — Señal para mecanismos existentes**: si el modelo de observación supera los gates, el destino más parsimonioso del dato nutricional sería integrarse como señal contextual en los mecanismos de atribución causal y decisión de entrenamiento que ya existen (puente Diario↔Gym, `explicacion_decision_service.py`, `GymDecisionLog`) — no crear maquinaria decisoria propia.

**H-D2 — Estado global autónomo**: la disponibilidad insuficiente produce efectos suficientemente fuertes y autónomos como para entrar en la matriz de prioridad del estado global del organismo (`PHASE_ORGANISMO_0_CONTRATO.md`), junto a lesión / RPE extremo / Pulso.

**Estado actual**: H-D1 es la hipótesis de trabajo más coherente con la arquitectura existente. H-D2 carece de evidencia y no forma parte del alcance actual. Ninguna de las dos autoriza wiring durante Fase 0.

**Comportamiento concreto que justificaría explorar el dato** (no "JOI sabe de nutrición"): JOI mejora su atribución causal y evita modificar el entrenamiento cuando la señal apunta a recursos insuficientes en vez de a exceso de carga.

---

## Dos niveles de intervención a observar en el análisis final

Complementa — no sustituye — el Gate 4 congelado de `PHASE_NUTRICION_0_CONTRATO.md`, que solo exige un caso de intervención humana. El análisis final del piloto distinguirá dos preguntas:

**Intervención humana** (la que ya pide Gate 4): la observación provoca que David cambie una conducta — merienda antes, usa un recurso rápido, evita un hueco, modifica una cena.

**Intervención del organismo** (pregunta experimental adicional — no gate, no congelada): ¿hubo algún episodio en el que disponer de esta señal habría cambiado razonablemente una decisión que JOI tomó con los datos actuales — no recomendar deload, mantener volumen y señalar falta de recursos, reducir confianza en una atribución de fatiga, vigilar antes de intervenir, explicar una caída de rendimiento de forma distinta?

"Razonablemente" queda protegido: exige coincidencia temporal repetida y contraste con rendimiento posterior — no una explicación retrospectiva conveniente construida después de ver el resultado.

---

## Límite de integración futura (no normativa — guía si algún día existe Fase 1)

Si el piloto resulta prometedor, la nutrición no debería anular por sí sola señales fuertes de carga o lesión. Funcionaría como señal de atribución y reducción de confianza, no como reemplazo automático de la decisión:

- carga alta + recursos insuficientes → no atribuir toda la fatiga a una sola causa;
- carga normal + recursos insuficientes repetidos + peor rendimiento → aumenta la hipótesis de combustible;
- lesión aguda o bloqueo duro de ACWR → la nutrición no elimina la protección.

---

## Hipótesis sobre el método del piloto (no normativa)

Añadido 2026-07-11 tras una duda legítima sobre si un piloto narrado manualmente por chat podría terminar validando un flujo que nunca existirá en la app real.

**H-P1**: un piloto manual (narración por chat, sin interfaz) da mejor calidad de observación para validar el modelo conceptual — menos fricción técnica, foco puro en la unidad de observación y en la taxonomía.

**H-P2**: un piloto integrado desde el principio en un punto de contacto real de la app da una evidencia más representativa del uso futuro — al coste de construir interfaz antes de saber qué merece la pena programar.

**Estado actual**: sin evidencia todavía para elegir entre ambas. Se mantiene el protocolo manual ya en marcha (`PILOTO_NUTRICION_0_BITACORA.md`) hasta que aparezca evidencia de que el propio método de observación está distorsionando el comportamiento — no se decide por intuición.

---

## Qué no resuelve este documento

- No decide cuál punto de entrada se implementa.
- No decide el criterio de selección final.
- No decide si el Gate 1 se reformula.
- No decide el esquema de instrumentación del piloto.

Todo eso pertenece al Diseño técnico, que no se escribe hasta que estas hipótesis se hayan discutido.

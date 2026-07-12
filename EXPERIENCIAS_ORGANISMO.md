# EXPERIENCIAS DEL ORGANISMO

**Status**: VIVO, en construcción — no congelado, a diferencia de `DISPONIBILIDAD_RECURSOS.md` y `PHASE_NUTRICION_0_CONTRATO.md`
**Qué es**: momentos concretos en los que el organismo se manifiesta ante David. No son casos de uso de un módulo. Son escenas — cómo se siente convivir con JOI, no qué botones existen.
**Qué NO es**: un documento normativo. Ninguna escena de aquí autoriza una decisión de arquitectura por sí sola. Sirve para que, cuando volvamos a diseñar algo técnico, no se nos olvide para qué era.
**Por qué este nombre y no uno atado a nutrición**: las primeras escenas nacieron de Nutrición 0, pero el patrón no es de nutrición — es de cómo se comporta el organismo en general. Si dentro de unos meses aparecen escenas de entrenamiento, descanso, diario o relaciones, viven aquí también, no en un documento nuevo por dominio.
**Relación con el resto**: aplica en concreto el filtro de decisión de `ORGANISMO.md` y el filtro de aparición de JOI de `gymproject/CLAUDE.md` ("¿esto acelera demasiado el feedback loop? ¿convierte la habitación en feed? ¿hace que JOI persiga al usuario? ¿el texto viene del sistema JOI o es hardcoded?"). Las escenas de Nutrición 0 concretan esos filtros para un caso real; sirven de precedente, no de excepción.

---

## Criterio de entrada (propuesto, no cerrado)

Para que no se convierta en una colección de ideas bonitas, una escena entra solo si cumple las tres condiciones:

1. **Es real.** Nace de una situación que David ha vivido o es muy probable que viva.
2. **Cambia una decisión o una percepción.** Si JOI no estuviera, ese momento sería distinto.
3. **No depende de una implementación concreta.** La escena sigue teniendo sentido aunque mañana cambie por completo el código.

Marcado como propuesto porque quien debe cerrarlo es David (y quien le acompañe en esa conversación), no una decisión tomada dentro de este hilo con la IA.

---

## Principios que han aparecido escribiendo estas escenas

**El organismo comprende ≠ el organismo ayuda a decidir ≠ el organismo recomienda.** Son tres capas distintas, no una:

1. *Comprensión* — el órgano sabe algo de su propio estado (p. ej. disponibilidad de recursos). Esto es lo único que pertenece a `DISPONIBILIDAD_RECURSOS.md`.
2. *Ayuda a la decisión* — el sistema usa ese conocimiento para señalar que una decisión importa ahora. Ya existe en JOI para otros dominios (explicación de sesión, sugerencias de plan); no es exclusivo de nutrición.
3. *Recomendación concreta* — el sistema propone una acción específica ("un yogur, un bocadillo o un Huel"). Es la capa más alejada del órgano y la que más fácilmente se convierte en ruido si se construye antes de tiempo.

Mezclar las tres en una sola escena parece inofensivo pero no lo es: hace que una capacidad simple (comprensión) arrastre el diseño de una capacidad mucho más compleja (recomendación) sin haberlo decidido explícitamente.

**No todo dato merece convertirse en patrón.** Un día raro (viaje, imprevisto) no se compara contra la normalidad ni se marca como anomalía. El organismo reconoce cuándo un día no tiene valor predictivo y lo deja fuera del aprendizaje, en vez de forzarlo a encajar.

**JOI no necesita apropiarse de las buenas decisiones del usuario.** El objetivo no es que David haga cosas para que JOI las celebre. Es que David acabe tomando buenas decisiones sin necesitar a JOI. Cuanto mejor funciona el organismo, menos tiene que hablar — el silencio ante una buena decisión espontánea es tan deliberado como la frase ante un patrón repetido negativo.

---

## Escenas — Disponibilidad de recursos (origen: Nutrición 0)

**1. Por la mañana.** JOI ya abre el día. Si hay algo que merece mencionarse de ayer (un hueco largo, varios días de recurso rápido), aparece como una frase dentro de lo que ya dice — no como sección nueva. Si no hay nada, no dice nada.

**2. Cuando comes.** No se abre nada. Un gesto de tres segundos, disponible, nunca obligatorio, en un punto de contacto que ya existe. Si no se usa, mañana JOI no lo reclama como tarea pendiente — simplemente no supo qué comiste, y eso también es un dato.

**3. Después de entrenar.** No pregunta "¿qué has comido?". Pregunta "¿has podido reponer lo que acabas de gastar?". No habla de alimentos, habla del organismo. Vive en el cierre de entrenamiento que ya existe — no crea un flujo nuevo.

**4. Por la noche.** Si algo de esto entra en el cierre de noche, entra como una línea más, con el mismo tono que ya usa para sueño o estado de ánimo. Sin cifras, sin barra de progreso, sin "5 de 7 días".

**5. El día malo.** Si aparece un patrón repetido (varias horas sin comer + sesión claramente peor), JOI puede sostener en vez de callar — pero como hipótesis, no como diagnóstico: *"no parece un problema de disciplina, hoy el organismo ha tenido pocos recursos para responder al entrenamiento"*. Reduce culpa sin convertirse en excusa. Un día suelto, sin patrón, sigue mereciendo silencio.

**6. Antes de entrenar (17:30).** David abre JOI porque quiere entrenar a las 19:00 y quiere que el entrenamiento tenga sentido. Tres actos, no uno:
   - *Acto 1 — comprensión* (esto sí es Disponibilidad de Recursos): "ahora mismo el organismo lleva bastantes horas sin recibir recursos."
   - *Acto 2 — ayuda a decidir* (capa distinta, ya existe en JOI para otros dominios): "si quieres entrenar con mejores sensaciones, ahora tendría sentido reponer antes."
   - *Acto 3 — recomendación concreta* (no es el órgano; es un sistema de ayuda a la decisión que usa el conocimiento del órgano, mucho más adelante si acaso): "podría servir un yogur, un bocadillo o un Huel."
   
   Se salva de violar "JOI no persigue" porque el usuario abre JOI primero — JOI no interrumpe sin que se lo pidan.

**7. El día raro.** Viaje, imprevisto, horario roto — comes a las 11 y a las 22, nada en medio. JOI no lo compara contra un patrón normal ni lo marca como hueco. Reconoce que hoy no es un día de referencia, igual que ya hace con una sesión de viaje en Hyrox, y no dice nada esa noche.

**8. Cuando decides tú, sin que nadie pregunte.** Un domingo comes distinto porque te apetece, no porque JOI lo sugiera. Se registra igual, en tres segundos, y JOI no lo comenta como logro ni lo compara con la semana anterior. Se limita a saberlo.

---

## Escenas — Relación David↔organismo

Las ocho escenas anteriores hablan de comida. Estas hablan de la relación en sí, no de un dominio concreto — por eso viven en su propia sección, no dentro de "Disponibilidad de recursos".

**9. El día en que no abres JOI.** Tres semanas comiendo razonable, entrenando, durmiendo. Nada destacable. No abres JOI durante dos días. Cuando vuelves, la aplicación no intenta recuperar el tiempo perdido. No pregunta "¿qué comiste ayer?". No reconstruye la historia. No muestra "tienes dos días sin registrar". Simplemente continúa — como haría un organismo, que no lleva hoja de asistencia. Sigue vivo. Esta escena protege a JOI de convertirse en una aplicación que exige atención constante para seguir siendo útil.

> **JOI nunca castiga una ausencia. Solo trabaja con la presencia que tiene disponible.**

**10. — sin escribir todavía.** Pregunta guía, no escena: ¿cuál es el momento en el que David siente que JOI le ha ayudado sin darse cuenta de que JOI estaba ayudando? No se fuerza — si aparece de forma natural (en el piloto, en otra conversación, viviendo con la app), se escribe aquí. Si nunca aparece con esa naturalidad, eso también sería un dato.

---

## Escenas de otros dominios

*(vacío — este documento crece cuando aparezcan, no antes)*

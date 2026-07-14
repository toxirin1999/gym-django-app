# SEMÁNTICA — Estado de Recursos (previo al diseño)

**Status**: borrador en construcción. Documento corto, previo a `PLAN_RECURSOS_DISPONIBLES.md`. Objetivo único: cerrar QUÉ representa el estado antes de decidir CÓMO se calcula o se representa visualmente. No sustituye al plan de Fase 1 ya implementado — lo precede para la siguiente iteración (la "batería"). Cubre solo la capa presente — la capa prospectiva ("¿todavía estoy a tiempo?") vive en `MARGEN_PARA_ACTUAR.md`.

## Qué representa

No es una medida fisiológica. No es un balance calórico. Es **la confianza estimada del organismo en que dispone de recursos suficientes según la evidencia disponible** — una interpretación, no una medición. El mismo movimiento epistemológico que JOI ya usa en diario o en la lectura del sueño: trabaja con la mejor evidencia disponible, no con la realidad absoluta.

El estado describe el presente, no una demanda futura. No sabe si lo siguiente será caminar hasta la cocina o una sesión pesada de piernas — eso pertenece al motor de decisiones que lo consulte, no al estado en sí.

> El estado de recursos no representa la energía del organismo; representa el grado de confianza que el organismo puede tener en la disponibilidad de recursos a partir de la evidencia que posee.

**Principio cerrado — persistencia entre días**: el estado persiste, no se resetea a medianoche. El organismo no sabe cuándo cambia el calendario, solo cuándo aparece o falta evidencia — un reseteo diario contradice "el estado describe el presente basado en evidencia real", porque a las 00:05 no ha cambiado nada del organismo respecto a las 23:55.

## Qué sabe y qué no sabe el organismo

**Sabe** (evidencia observable, ya registrada o de mínimo coste añadir):
- Que hubo una ingesta, de qué nivel (Completa / Base / Recurso — niveles ya definidos en `RegistroDisponibilidad`), y cuándo.
- Que hubo un entrenamiento y cuándo — deliberadamente sin duración, sin intensidad, sin tipo. Extender esto es una decisión futura explícita, no un supuesto de partida.
- Cuánto tiempo ha pasado desde la última evidencia relevante.

**No sabe, y nunca debe fingir saber:**
- Calorías ingeridas o gastadas.
- TMB, glucógeno, digestión, absorción, composición de la comida.
- Estado metabólico real.

## Qué eventos tienen autoridad para modificar el estado

**Autoridad directa** (mueven el estado en el momento en que ocurren):
- Ingesta registrada → sube, en función del nivel (Completa > Base > Recurso). Completa tiene la mayor autoridad para subir el estado, pero **no garantiza por sí sola el estado máximo** — el historial reciente del día (horas vacías, registros previos de nivel bajo) sigue pesando. Una Completa tras varias horas sin nada sube fuerte, pero no necesariamente hasta el tramo más alto de golpe.
- Entrenamiento completado → baja, sin gradiente de intensidad por ahora.

**Pregunta abierta**: ¿todo registro de nivel Recurso sube el estado, o algunos registros de baja entidad (ej. un café) solo deberían "interrumpir el silencio" sin aportar una subida significativa? No se resuelve aquí ni se toca la taxonomía existente (Completa/Suficiente/Recurso) — se deja anotada explícitamente para que la autoridad de un Recurso no se dé por hecha por defecto. Si cualquier café sube el estado, el modelo puede transmitir una seguridad que la ingesta real no justifica.

**Autoridad condicional** (el paso del tiempo, solo bajo condiciones):
- Hay un periodo estable tras cada observación: durante un intervalo razonable, el tiempo no modifica el estado — el organismo mantiene la confianza de la última observación.
- Cuando el silencio supera un umbral contextual, deja de ser ausencia de datos y se convierte en una observación derivada ("ha pasado un intervalo relevante sin evidencia de reposición"), y el estado empieza a erosionarse gradualmente.
- El umbral no es un valor único global — es contextual: más corto antes de entrenar y después de entrenar sin reposición; más largo tras una comida completa.

**Persistencia frente a evolución nocturna — son decisiones distintas:**
- *Persistencia* (cerrada): el estado no se resetea a medianoche. El organismo no sabe cuándo cambia el calendario.
- *Evolución nocturna* (propuesta abierta, no cerrada): de que no se resetee no se deduce que deba amanecer con el valor exacto con el que se acostó. El sueño no es un hueco diurno — no debería erosionar como ocho horas despierto sin comer — pero tampoco debería congelar el estado como si nada ocurriera durante la noche. La propuesta: durante el sueño el estado converge suavemente hacia una banda basal de mañana, sin fijar aún valores ni curva. Ejemplo cualitativo: acostarse en Alta → amanecer en Suficiente-alta; acostarse en Suficiente → amanecer en Suficiente; acostarse en Baja tras entrenar sin reponer → no debería amanecer recuperado.

**Sin autoridad:**
- El tiempo, en solitario, mientras no se supere el umbral contextual vigente — el estado permanece estable.

*(Resuelto en conversación: el modelo es "híbrido con umbral" — ni puramente event-driven, ni erosión continua desde el segundo cero. Ver ejemplo conceptual: 08:00 comida → sube; 10:00 estable; 12:00 empieza a erosionar si se superó el umbral; 14:30 comida completa → sube; 17:00 entreno → baja; 18:00 sin reposición → sigue baja o vuelve a erosionar.)*

## Naturaleza del estado — abierto

Pendiente decidir: ¿el estado se resuelve internamente en un continuo (aunque no se comunique con esa precisión) y solo se **representa** en tramos/bloques discretos (▰▰▰▱▱), o el estado en sí mismo vive en categorías discretas con nombre (Alta / Suficiente / Baja / Crítica) y la erosión mueve de una categoría a otra?

Propuesta a confirmar: resolución interna continua (para que la erosión se sienta suave y explicable paso a paso) + representación discreta (para no fingir precisión que no existe) — el mismo principio de separar modelo y representación que abrió esta conversación, aplicado ahora al propio estado.

**Relacionada, pero distinta, y aparcada**: ¿el estado tiene memoria de tendencia (varios días de buen historial amortiguan una caída puntual), o es puramente instantáneo con herencia de valor? Ver "Intuición aparcada" en `SIMULACION_DIA_RECURSOS.md` — no se resuelve aquí todavía.

## Tres piezas, no dos — principio cerrado

El estado de recursos (esta capa, presente), el margen para actuar (capa prospectiva, ver `MARGEN_PARA_ACTUAR.md`) y la decisión nutricional asistida (frontera nombrada, no construida) son cosas distintas que no deben mezclarse:

- **Estado de recursos** (aquí): responde *"¿qué confianza tiene el organismo, ahora mismo, en que ha recibido recursos con una continuidad razonable?"*. Solo mira evidencia pasada. No sabe qué viene después.
- **Margen para actuar** (capa superior, motor): responde *"¿sigo a tiempo de hacer algo útil antes de lo que viene?"*. Cruza el estado presente con una demanda concreta (ej. entrenamiento a una hora dada). Solo esta capa mira hacia delante. Su salida es una banda cualitativa (Amplio/Reducido/Cerrado), no una recomendación.
- **Decisión nutricional asistida** (no construida): qué acción concreta, si alguna, tiene sentido dentro del margen disponible. Requiere conocimiento que hoy nadie tiene modelado (qué recursos son adecuados, tolerancia, tiempo de absorción) — Fase 3, aparcada. Se nombra aquí solo para que sus responsabilidades no se filtren dentro de la capa de margen.

Esto implica **dos umbrales distintos**, no uno:
- *Umbral de erosión* (de esta capa): cuándo la ausencia de evidencia empieza a reducir la confianza del estado — descrito arriba en "Autoridad condicional".
- *Umbral de intervención* (de la capa de margen, no de esta): cuándo, dado un evento futuro concreto, todavía merece la pena actuar. No depende de que el estado esté en Baja — un estado Suficiente con un entrenamiento en 90 minutos puede disparar aviso; un estado Bajo sin nada próximo puede quedarse en observación, sin urgencia.

No se fusionan estos dos umbrales ni se hace que el umbral de erosión "avise antes" de forma general — eso volvería a mezclar presente y futuro en una sola capa.

## Qué decisiones puede informar / qué nunca debe decidir por sí solo

**Puede informar**: la capa de margen para actuar (`MARGEN_PARA_ACTUAR.md`), que a su vez informa decisiones de entrenamiento, recuperación y disponibilidad del organismo, siguiendo el patrón ya establecido en la app — Observación → Motor determinista → Decisión → JOI la expresa. Nunca una plantilla de texto fija. El estado en sí no decide nada — solo es la evidencia que otra capa consulta.

**Nunca debe**: bloquear el plan de entrenamiento, competir con o sustituir a `hyrox_decision` (lesión / TSB / ACWR siguen teniendo prioridad sobre esto), ni generar consejos nutricionales concretos — eso sigue siendo Fase 3, aparcada hasta que este estado lleve tiempo demostrando ser fiable.

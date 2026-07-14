# MARGEN PARA ACTUAR — capa prospectiva

**Status**: aparcado deliberadamente, no implementar todavía. Bloqueado por una falta de señal, no por falta de diseño: el sistema no conoce de antemano la hora prevista de entreno (solo la fecha), así que hoy no puede distinguir margen Amplio/Reducido/Cerrado con sentido. Activarlo solo al abrir la pantalla de pre-entreno sería una lectura inmediata, no el margen prospectivo aquí definido — se descartó explícitamente construir esa versión degradada para no sesgar la observación (podría parecer que "el margen no ayuda" cuando el problema real sería que el sistema se entera tarde). Retomar tras las dos semanas de observación del Estado, cuando haya datos reales de cuánta antelación hace falta y qué señal de demanda (sesión con hora, aviso manual de David, u otra) puede alimentarlo con honestidad.

Capa separada de `SEMANTICA_ESTADO_RECURSOS.md` — ese documento cubre el estado presente ("¿qué confianza tiene el organismo ahora?"); este cubre la lectura prospectiva ("¿sigo a tiempo de hacer algo útil antes de lo que viene?"). No se fusionan: el estado no sabe qué viene, esta capa sí lo cruza. Es la pieza intermedia de tres — ver "Tres piezas, no dos" al final.

## Qué representa

> Llegar a tiempo, no llegar a cero.

No mide cuánto queda. Mide **si todavía hay ventana para intervenir** antes de que la falta de recursos se convierta en un problema frente a algo concreto que va a pasar. No decide qué hacer con esa ventana — eso es de otra capa (ver abajo).

## Cómo se construye

Cruza:
- El **estado de recursos** en este momento (capa presente, sin cambios) — pero la banda visual (Alta/Suficiente/Baja) no basta por sí sola. Dos estados dentro de la misma banda pueden producir lecturas distintas según la antigüedad de la evidencia y su tendencia (¿subiendo o bajando?).
- Una **demanda concreta próxima**, cuando exista — hoy la única fuente real es un entrenamiento planificado o iniciado. No se inventa una demanda genérica para días sin nada agendado.

## Salida semántica del margen

No son valores de tiempo fijos ("90 minutos es pronto", "30 minutos es tarde") — son tres lecturas cualitativas, y los inputs que las resuelven (tiempo hasta la demanda, antigüedad de la evidencia, tendencia) se diseñan después, a partir de qué escenario debe caer en cada banda:

- **Amplio**: todavía caben varias intervenciones razonables. Normalmente no hay nada que decir.
- **Reducido**: queda una ventana limitada; conviene decidir pronto si se va a hacer algo.
- **Cerrado o casi cerrado**: ya no cabe una intervención completa antes de la demanda.

## Escenarios

### 1. Estado Suficiente, sin entrenamiento próximo
No hay demanda que cruzar. **Silencio absoluto.** No es que el organismo esté "bien" — es que la pregunta "¿a tiempo de qué?" no tiene objeto hoy. Esta capa no se activa solo porque el estado exista.

### 2A. Estado Suficiente, evidencia reciente, entrenamiento en 90 minutos
Margen: **Amplio**. **Sin recomendación, silencio.** El mero hecho de que exista un entrenamiento próximo no justifica intervenir — hay margen y no hace falta usarlo. Esta capa no habla solo porque se activó el cruce con una demanda; habla solo cuando el margen deja de ser amplio.

### 2B. Estado Suficiente pero ajustado, o con evidencia antigua, entrenamiento en 90 minutos
Margen: **Reducido**, aunque la banda visual del estado (Suficiente) sea la misma que en 2A. **Aviso temprano.** Todavía no hay un problema presente, pero el margen empieza a cerrarse. Esta es la escena 6 de `EXPERIENCIAS_ORGANISMO.md` ("Antes de entrenar, 17:30") en su Acto 2 — solo se llega ahí cuando el margen es Reducido, no por defecto.

### 3. Estado Bajo, sin demanda próxima
**Margen para Actuar no emite ninguna salida** — no existe una demanda concreta que cruzar, así que no hay "a tiempo para qué". El estado bajo sigue existiendo y disponible para otras capas (narrativa general de JOI, lectura de la mañana en `SEMANTICA_ESTADO_RECURSOS.md`), pero esta capa prospectiva no lo verbaliza ni lo convierte en urgencia — mezclar esto aquí volvería a juntar presente y futuro justo después de haberlos separado.

### 4. Estado Bajo, entrenamiento en 30 minutos
Margen: **Cerrado o casi cerrado.** Esta capa se detiene aquí: concluye que ya no cabe una intervención completa antes de la demanda. **No decide qué ofrecer** — no le corresponde saber si un recurso rápido, tolerancia digestiva o tiempo de absorción son adecuados; eso es conocimiento de otra capa (Decisión nutricional asistida, ver abajo, no construida todavía). Lo único que esta capa aporta es la frontera: si algo se propone después, tiene que ser compatible con que el margen ya es prácticamente nulo.

## Tres piezas, no dos

1. **Estado de Recursos** (`SEMANTICA_ESTADO_RECURSOS.md`) — qué confianza existe en el presente.
2. **Margen para Actuar** (este documento) — cuánto tiempo útil queda frente a una demanda concreta. Salida: Amplio / Reducido / Cerrado.
3. **Decisión nutricional asistida** (frontera nombrada, no construida) — qué acción, si alguna, tiene sentido dentro de ese margen. Necesitaría conocimiento que hoy el sistema no tiene (qué recursos son adecuados, tolerancia, tiempo de absorción, intensidad de sesión) — es territorio de Fase 3, aparcada.

El estado describe el presente. El margen describe la oportunidad temporal. Otro motor, todavía sin construir, decide qué hacer con ella.

## Lo que esto NO decide todavía

- Qué inputs concretos (tiempo hasta la demanda, antigüedad de evidencia, tendencia, otros) resuelven cada banda de margen, y con qué peso.
- Si "entrenamiento próximo" se amplía en el futuro a otras demandas (una reunión larga, un viaje) — hoy la única demanda real y disponible es entrenamiento.
- La forma visual de esta capa (¿aparece junto al estado, o solo como frase de JOI cuando el margen no es Amplio?).
- Todo lo que pertenece a la capa 3 (Decisión nutricional asistida) — no se diseña hasta que esta capa lleve tiempo demostrando ser fiable.

## Siguiente paso

Si estos escenarios se sostienen, el resto de la mecánica (qué resuelve cada banda de margen, cómo se representa) puede diseñarse a partir de ellos en vez de al revés — igual que se hizo con `SIMULACION_DIA_RECURSOS.md`.

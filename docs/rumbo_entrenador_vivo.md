# Rumbo: un entrenador con vida propia

12 de octubre de 2026 · propuesta acordada con David

## Decisión de fondo

La app debe parecer viva porque **actúa y explica**, no porque tenga un personaje que habla.
Cuando hubo que elegir entre "un entrenador que te habla" y "un entrenador que actúa y te
explica", David eligió lo segundo.

## La regla: cuatro cosas que haría un buen entrenador

1. **Se da cuenta de cosas que no le has dicho.**
   "Llevas tres sesiones sin subir en sentadilla."
2. **Cambia lo que hace por ellas.**
   "Hoy cambio la variante."
3. **Te dice por qué en una frase y con el dato.**
   "Llevas un 60 % más de carga que tu media de cuatro semanas; hoy, versión reducida."
4. **Vuelve después a comprobar si acertó.**
   "Hace dos semanas te bajé el volumen por fatiga. Tu RPE pasó de 8,6 a 7,4: funcionó."

Toda funcionalidad nueva se mide contra estos cuatro puntos. Si solo muestra datos y no
cumple ninguno, está incompleta.

## Diagnóstico (12-oct-2026)

- La "vida" ya existe, pero en las decisiones: el ACWR reduce la sesión, la doble
  progresión, el plan reconoce lo hecho y la técnica frena subidas. Desde hoy asoma en
  Ahora con "Lo que el plan aprendió".
- JOI vive aparte: ~15.000 líneas, 25 tipos de mensaje y una habitación (narrativa,
  manual, memoria) que no está en la navegación. Solo 4 de 224 commits desde septiembre
  la tocan: la app ha crecido sin ella.
- Lo que dice JOI no se puede comprobar. El mensaje del 11-oct afirma "has dormido bien",
  "ACWR bajito" y "el esfuerzo duele menos que hace cuatro semanas" sin dato que lo
  respalde. Un entrenador que inventa pierde la confianza, que es lo que lo hace valioso.
- El punto 4 (comprobar si acertó) casi no se ve, aunque la base existe: `GymDecisionLog`
  tiene `resultado` (validada / fallida / neutra) y `fecha_evaluacion`.

## Principios

- **La voz va pegada a la decisión.** Cada vez que el sistema cambia algo, lo dice en una
  frase con el dato, donde ocurre: Ahora, briefing o cierre del entreno. Sin pantalla aparte.
- **Si no puede citar el dato, no lo dice.** Si se usa IA, solo redacta a partir de una lista
  cerrada de hechos; nunca interpreta ni rellena huecos. Para la mayoría bastan plantillas.
- **Iniciativa, pero poca.** Habla por su cuenta solo cuando detecta algo realmente nuevo, no
  cada mañana.
- **La habitación se convierte en la memoria del entrenador**, integrada en Memoria: qué
  aprendió, qué acertó y qué falló. Sin narrativa diaria y sin pedir al usuario que revise
  el trabajo del entrenador (hoy hay "57 por revisar").

## Orden de trabajo propuesto

1. **El "por qué" con número en cada decisión de Ahora** (y en briefing y cierre).
   Ej.: "Versión reducida: ACWR 1,62 — un 62 % más de carga que tu media."
2. **"Lo que decidí y si funcionó"** en Memoria, semanal, a partir de `GymDecisionLog`
   (`resultado`, `fecha_evaluacion`), con antes/después medibles (RPE, reps, e1RM).
3. **Primera propuesta con iniciativa: la caída del tren inferior** detectada por el mapa
   muscular (cuádriceps −10 %, isquios −17 % a 90 días). Formato: "He visto esto → te
   propongo esto para el próximo bloque → ¿lo aplico?". Aplicar solo con confirmación.
4. **Congelar la habitación y la apertura diaria generada** (sin borrar), reutilizando las
   piezas que sirvan para los puntos 1–3.

## Lo que no hacer

- Mensajes diarios generados que no cambian nada.
- Texto con afirmaciones que no salen de un dato registrado.
- Nuevas pantallas para la voz del entrenador: la voz vive junto a la decisión.

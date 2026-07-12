# DISPONIBILIDAD DE RECURSOS — Definición operativa

> 🔒 **Congelado hasta que termine el bootstrap de Nutrición 0.** Solo se edita para corregir errores o ambigüedades — no para enriquecerlo. La fase de diseño conceptual está cerrada; lo que sigue es diseño experimental y técnico, no arquitectura.

## Qué es

No es un órgano de nutrición.

Es el órgano que responde a una única pregunta:

> ¿Dispongo de los materiales necesarios para sostener lo que estoy intentando hacer?

La nutrición es la primera fuente observada de esa respuesta. No es la identidad del órgano.

## Por qué no se llama "nutrición"

Si el nombre del órgano queda atado a su primer caso de uso, la arquitectura hereda los límites de ese caso de uso.

Hidratación, sueño insuficiente, enfermedad o agotamiento extremo son, potencialmente, otras formas de responder a la misma pregunta sobre disponibilidad de recursos — no módulos separados que algún día haya que "cruzar" con nutrición.

No se implementa nada de eso ahora. Se nombra así para no cerrar la puerta.

## Principio madre

El usuario nunca debería sentir que **está registrando algo**.

No rellena un formulario de comida, igual que no rellena un formulario al terminar un entrenamiento o al hacer el check-in de la mañana. Le está diciendo al organismo cómo ha despertado, o que acaba de gastar recursos, o que ha podido alimentarlo.

La pregunta del organismo tarda dos segundos en responderse. Si tarda más, ha dejado de ser este órgano.

## Principios estables

- El organismo no pregunta si el usuario ha cumplido una dieta. Pregunta si dispone de materiales suficientes.
- El registro debe habitar puntos de contacto que ya existen (apertura de mañana, cierre de entrenamiento, cierre de noche) — no una pantalla nueva, no un "modo nutrición".
- Observación e interpretación están separadas: el usuario declara hechos mínimos (cuándo, cuánto, de dónde) y el organismo infiere función y contexto. La función de una ingesta (Activación, Construcción, Estabilidad, Reposición, Recuperación) no se le pregunta al usuario — se deriva de la hora del día y de la proximidad a un entrenamiento ya registrado.
- Nunca se registra manualmente una ausencia. El silencio es un dato válido, no un formulario pendiente.
- Nunca se castiga ni se compensa. El órgano informa disponibilidad, no cumplimiento.
- El sistema antiguo de nutrición (`nutricion_app_django` — bloques Zona, pirámide educativa) pertenece a otro bounded context. Responde "¿cuál es la dieta óptima?". Este órgano responde "¿ha tenido hoy el organismo los recursos mínimos para seguir construyéndose?". Son dominios distintos aunque compartan el tema.
- Nutrición es la primera fuente observada, no necesariamente la única fuente futura.
- Cualquier ampliación futura a hidratación, sueño u otros recursos requiere su propio contrato y su propia evidencia. No se presupone desde ahora.

## Qué NO es

✗ Un dashboard nutricional
✗ Un sustituto del sistema de bloques Zona existente
✗ Un tracker de cumplimiento o adherencia
✗ Una fuente de puntuación o gamificación
✗ Un lugar donde el usuario decide la función de lo que registra

## Nota de arquitectura — "órgano" es terminología provisional

Este documento habla de "órgano" por continuidad con `ORGANISMO.md`, pero es posible que sea impreciso.

Lo que describimos podría ser una **capacidad fisiológica transversal** del organismo, no un órgano aislado. Si en el futuro se añade hidratación, enfermedad, déficit energético u otra fuente, probablemente no serán órganos nuevos — serán nuevos sensores de la misma capacidad de disponibilidad de recursos.

No se propone renombrar nada ahora — sería abrir un debate antes de tener evidencia. Esta nota solo existe para que, si dentro de un año aparece esa evidencia, no nos sintamos atados por la terminología inicial.

## Nota abierta — posible principio general de JOI

En Nutrición 0 aparece un patrón que podría no ser exclusivo de este órgano:

> El organismo nunca persiste interpretaciones. Persiste observaciones mínimas e infiere significado a partir del contexto.

Ejemplo concreto: el usuario no registra "Reposición" — registra una ingesta, y el organismo deduce que era reposición porque conoce el entrenamiento cercano.

Si este patrón reaparece de forma natural en otras fases, pertenecería al núcleo de la arquitectura de JOI (`gymproject/CLAUDE.md`), no a este documento. Por ahora se deja constancia aquí, sin elevarlo a contrato general — es una observación a vigilar, no una regla todavía.

## Relación con Nutrición 0

`DISPONIBILIDAD_RECURSOS.md` define la capacidad del organismo.
`PHASE_NUTRICION_0_CONTRATO.md` define el primer sensor experimental de esa capacidad.

Que hayamos identificado esta abstracción mayor no autoriza a implementarla ahora. Fase 0 solo registra nutrición y solo valida la señal nutricional. Disponibilidad de recursos es dirección arquitectónica, no alcance técnico inmediato.

## Filtro de decisión

Antes de añadir cualquier campo, pantalla o pregunta a este órgano:

1. ¿El usuario siente que está rellenando algo, o que está informando al organismo?
2. ¿Este dato lo puede inferir el sistema, o realmente solo lo sabe el usuario?
3. ¿Esto vive en un punto de contacto que ya existe, o es una pantalla nueva?
4. ¿Esto amplía silenciosamente el alcance hacia hidratación/sueño/enfermedad sin un contrato propio?

Si la respuesta a la 4 es sí, parar. Eso es Fase 1 de otro sensor, no Fase 0 de este.

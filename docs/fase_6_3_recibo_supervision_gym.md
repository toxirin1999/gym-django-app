# Fase 6.3 — Recibo de supervisión Gym

La portada muestra un recibo factual dentro del único bloque de corrección Gym
cuando la autoridad vigente procede de una corrección o reversión manual.

El recibo se proyecta en Python desde `GymDecisionVersion` vigente y su relación
`reemplaza`. Expone versión, transición de postura, motivo y confirma de forma
factual que se conservan ejercicios, cambios dinámicos y evidencia física de la
propuesta motor. La ejecutabilidad se copia de la sesión Gym dominante ya
compuesta en `portada_hoy` (o de la autoridad canónica ya proyectada); no se
vuelve a calcular seguridad ni autoridad. El estado aparece como indicador
visible y accesible: `Ejecutable` en color `--ok` o `No ejecutable` en `--warn`.

En postura `proteger` el recibo permanece visible y el formulario de nuevas
correcciones se oculta. La acción «Restaurar propuesta» solo se ofrece para una
corrección manual vigente, nunca para una reversión.

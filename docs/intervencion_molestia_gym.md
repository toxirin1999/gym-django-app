# Intervención de molestia Gym

Las molestias leves recurrentes se gestionan en `IntervencionMolestiaGym`, separadas de lesiones clínicas y de experimentos por estancamiento.

- Se necesitan tres entrenamientos distintos en 21 días efectivos, todos con severidad 1.
- Una evidencia de severidad 2 o superior deriva el caso al circuito de lesión y bloquea esta intervención.
- La alternativa se selecciona una sola vez con el catálogo seguro por `risk_tags`.
- La intervención termina tras dos ejecuciones o 21 días. No modifica preferencias ni perfiles adaptativos.
- Prioridad: lesión activa, molestia leve recurrente y, finalmente, estancamiento.

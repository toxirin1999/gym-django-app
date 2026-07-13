# PLAN — Marcador de Energía Disponible

**Status**: dirección aprobada, Fase 1 sin empezar
**Relación con lo existente**: `DISPONIBILIDAD_RECURSOS.md` sigue siendo la filosofía (sin tocar). `PHASE_NUTRICION_0_CONTRATO.md` sigue congelado y describe el modelo de datos (sin tocar). Este documento es la extensión hacia decisión/consejo que antes dejamos aparcada — ahora se activa por decisión directa de David, no porque el piloto haya terminado.
**Referencia de diseño**: seguir el mismo patrón que ya funciona en Hyrox (`HyroxReadinessLog`, `hyrox_decision` en `hyrox/views.py`) — score determinista, sin IA, calculado de señales ya existentes, que primero informa y solo más adelante interviene.

## Visión

Un marcador que responde, en cualquier momento, "¿tiene hoy el organismo energía suficiente para lo que le estás pidiendo?" — calculado a partir de lo que ya registras en `disponibilidad`, igual que el readiness de Hyrox se calcula de HRV/TSB/RPE. Empieza siendo solo un número visible. Con el tiempo, si demuestra ser fiable, empieza a aparecer en las explicaciones que JOI ya da. Solo al final, si todo lo anterior funcionó, da consejos concretos.

## Fase 1 — Score determinista (ahora)

- Función pura en `disponibilidad/services.py`: `calcular_energia_disponible(cliente) -> dict`.
- Inputs, solo de `RegistroDisponibilidad` (nada nuevo que registrar):
  - horas desde la última observación;
  - niveles de las últimas observaciones (últimas 24h);
  - si hubo un registro de tipo "Reposición" cerca del último entreno.
- Fórmula de partida (ajustable con uso real, no es definitiva):
  - empieza en 100;
  - resta puntos por cada hora sin registro más allá de un umbral (ej. 4h);
  - resta más si las últimas observaciones son mayoritariamente "Recurso";
  - suma si la más reciente es "Completa".
- Se muestra como un número/badge simple en el panel — sin explicación larga, sin consejo, sin narrativa JOI todavía.
- Validación: los primeros días se comprueba a ojo si el número coincide con cómo te sientes. Se ajustan los pesos de la fórmula libremente — es calibración de un número, no una decisión de arquitectura, así que no hace falta esperar semanas para tocarlo.

## Fase 2 — Señal en lo que JOI ya explica

- Mismo patrón que la señal corporal del diario: si el marcador está bajo, aparece como una línea más en "¿Por qué hoy?" (`entrenos/services/explicacion_decision_service.py`).
- Pendiente de decidir con evidencia real (no ahora): si el marcador debería entrar en la matriz de prioridad del estado global del organismo (`PHASE_ORGANISMO_0_CONTRATO.md`) junto a lesión/RPE extremo/Pulso, o quedarse como bullet informativo. Esto sigue necesitando patrón demostrado antes de decidirse.

## Fase 3 — Consejos y recursos concretos

- Aquí es donde JOI sugiere algo específico ("un yogur, un bocadillo, un Huel te vendría bien ahora").
- Se construye solo cuando las Fases 1 y 2 llevan tiempo funcionando y el número se siente acertado — no antes, porque es la parte con más riesgo de sonar a ruido si se acierta mal.

## Lo que no se construye en ninguna fase

- Conteo de calorías o macros.
- Inventario de comida en casa.
- Un estado global de nutrición separado del que ya existe para todo el organismo.

## Próximo paso

Implementar Fase 1: la función de score + el badge en el panel. Antes de escribir código, confirmar contigo los pesos de partida de la fórmula (umbral de horas, cuánto penaliza el "Recurso" repetido, cuánto suma el "Completa" reciente).

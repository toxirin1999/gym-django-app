# SIMULACIÓN DE UN DÍA — Estado de Recursos

**Status**: paso 2 de la hoja de ruta (Semántica ✅ → **Simulación** → Mecánica → Implementación → Calibración). Sin fórmulas. El objetivo es leer la secuencia y comprobar si el comportamiento propuesto parece humano — no si los números cuadran. Cada tramo es una propuesta a validar contra `SEMANTICA_ESTADO_RECURSOS.md`, no una decisión cerrada. Narra el estado **y** la experiencia de David — la escena 6 de `EXPERIENCIAS_ORGANISMO.md` ("Antes de entrenar, 17:30") ya anticipaba este patrón; esta simulación lo desarrolla en un día completo.

Bandas usadas solo para narrar (no implican mecánica de representación todavía): **Crítica → Baja → Suficiente → Alta**.

**Principio ya cerrado**: el estado persiste de un día a otro. No se resetea a medianoche — el organismo no sabe cuándo cambia el calendario, solo cuándo aparece o falta evidencia. El 07:00 de hoy hereda literalmente el valor con el que David se durmió anoche.

---

## Escenario 1 — Día normal

*(El estado con el que empieza hoy es Suficiente — herencia de anoche, sin necesidad de inventar un origen.)*

### 07:00 — ☕ Café con leche
Nivel: **Recurso** (C).

**Pregunta abierta que esto revela**: ¿un Recurso como este sube el estado (aunque sea poco), o solo interrumpe el silencio sin aportar una subida real? Un café con leche puede registrarse como ingesta, pero su autoridad sobre la confianza en recursos quizá deba ser mínima o nula — si cualquier café sube la batería, el modelo puede transmitir una seguridad que la ingesta real no justifica. No se decide aquí; las dos lecturas quedan abiertas hasta que se resuelva en la semántica.

### 08:00 — 🥪 Bocadillo de pavo y queso
Nivel: **Suficiente** (B), una hora después del café.

**Pregunta que abre esto**: ¿café + bocadillo en una hora son dos eventos independientes que se suman, o el organismo debería leerlos como un único "desayuno"? Propuesta: cada registro pesa por sí mismo, sin agregación artificial — más simple, más fiel a "solo evidencia real, sin inferencias de intención". Estado: sube a Alta-baja / roza Alta.

### 14:30 — 🍗 Carne con patatas
Nivel: **Completa** (A).

**Corregido**: una Completa tiene la **mayor autoridad para subir el estado, pero no garantiza por sí sola el estado máximo** — el historial reciente del día sigue pesando. Aquí, como el día ya traía evidencia razonable (café + bocadillo), la Completa consolida el estado en Alta. Pero esto no es automático: si esta hubiera sido la *primera* evidencia sólida del día — por ejemplo, solo café a las 07:00 y nada más hasta las 14:30, siete horas después — la misma Completa subiría fuerte pero probablemente no bastaría para llegar a Alta de golpe. El organismo recordaría las horas vacías, no solo el plato de ahora.

*David no interactúa con nada en este momento — solo ha comido. El registro es el gesto de tres segundos ya existente, sin narrativa.*

### 17:30 — ¿Entrenar?
Han pasado 3h desde la Completa. Según la semántica ya cerrada, tras una comida Completa el periodo estable dura más que tras un Recurso.

**Propuesta**: el estado sigue en Alta — 3h está dentro del periodo estable post-Completa, no se ha cruzado el umbral de erosión.

*David abre JOI porque va a entrenar a las 19:00 y quiere que la sesión tenga sentido. No recibe ninguna sugerencia — el organismo considera que hay evidencia suficiente y reciente para afrontar la sesión sin necesidad de reponer antes. David cierra la app sin hacer nada más. No fue silencio por falta de datos: fue una decisión visible de no decir nada, exactamente el Acto 1 (comprensión) de la escena 6, sin que hiciera falta llegar al Acto 2 (ayuda a decidir) porque no había nada que decidir.*

### 19:00 — Entrenas
Evento discreto con autoridad directa.

**Propuesta**: baja un tramo (Alta → Suficiente). No colapsa a Crítica de golpe — un entreno gasta recursos, no los agota, y el estado previo a entrenar era alto.

*David termina la sesión y cierra el entreno como siempre. No hay ninguna pregunta nueva sobre recursos en este punto — el cierre de entrenamiento ya tiene su propio flujo (RPE, técnica, molestias); esto no le añade una pregunta más.*

### 20:30 — Cenas
**Pregunta abierta que esto revela**: el escenario no especifica el nivel de la cena. Si es Suficiente o Completa, sube de nuevo hacia Alta. Si fuera Recurso, subiría menos y quedaría en Suficiente — señal correcta, porque un entreno sin reposición real después sí debería quedar reflejado, no maquillarse con cualquier ingesta.

*David cena sin que JOI diga nada — es un registro más, de los que "no se comentan como logro ni se comparan con el día anterior" (principio ya escrito en `EXPERIENCIAS_ORGANISMO.md`).*

### 22:30 — Te acuestas
El estado al acostarse depende de cómo haya ido la cena — llamémoslo Alta o Suficiente-alta para este escenario.

**Propuesta (evolución nocturna, distinta de persistencia)**: el sueño no es un hueco diurno — no erosiona como ocho horas despierto sin comer — pero tampoco queda congelado como si nada ocurriera. Durante la noche el estado converge suavemente hacia una banda basal de mañana, no se mantiene intacto.

### 07:00 (día siguiente)
**Propuesta**: si se acostó en Alta, amanece en Suficiente-alta — no en Alta intacta. Si se hubiera acostado en Suficiente, amanecería en Suficiente. Si se hubiera acostado en Baja tras entrenar sin reponer, no debería amanecer mágicamente recuperado. Esto es lo que persiste de un día a otro: no el valor exacto de anoche, sino una versión convergida hacia la banda basal — coherente con "el estado no se resetea" sin caer en "el estado queda congelado ocho horas".

---

## Preguntas descubiertas al narrar esto (no estaban en el documento semántico)

1. **¿Eventos próximos en el tiempo se suman o se agregan como uno solo?** Propuesto: no se agregan — cada registro pesa por separado, con su propio nivel.
2. **¿Qué pasa si entrenas dos veces el mismo día?** No aparece en este escenario. Intuición: cada entreno tiene autoridad propia y baja un tramo adicional, pero valdría la pena un Escenario 2 dedicado a esto antes de cerrar la mecánica.
3. **¿Cuándo empieza realmente la erosión — a partir de la última ingesta, o a partir del último evento de cualquier tipo (incluido un entreno)?** En este escenario el entreno de las 19:00 también debería abrir su propia ventana de "umbral más corto para reposición" (ya mencionado en la semántica: "después de entrenar, la ausencia de reposición adquiere relevancia antes") — falta decidir si esa ventana convive con la ventana normal de comidas o la sustituye temporalmente.
4. **¿Cuál es la autoridad mínima de un Recurso?** Ver 07:00 arriba — pendiente de resolver en la semántica, no solo en esta simulación.
5. **¿Cómo es exactamente la convergencia nocturna hacia la banda basal?** Ver 22:30/07:00 arriba — la dirección está decidida (converge, no se congela ni erosiona como de día), falta la curva.

---

## Intuición aparcada — no resolver ahora

¿Y si el estado tuviera memoria de tendencia, no solo persistencia de valor? Ejemplo: tres días seguidos comiendo bien, y hoy una comida Recurso — ¿debería caer igual que si llevaras tres días comiendo mal? La intuición dice que no debería caer igual de fuerte. Esto cambiaría el estado de "instantáneo con herencia" a "instantáneo con una componente de historia reciente" — una capa más de complejidad que merece su propia discusión, no colarse dentro de esta simulación. Se anota aquí para no perderla, sin decidir nada todavía.

---

## Siguiente paso

Antes de casos excepcionales, validar el Escenario 1 tal cual con David — en lenguaje llano, sin pedirle validar arquitectura ni principios, solo si algún tramo no se parece a su experiencia real de un día.

Una vez validado, los escenarios de tensión siguientes, en este orden — priorizando los que prueban el problema real que originó el sistema, dejando para el final el que solo prueba acumulación mecánica de gasto:

1. Comida completa muy tardía tras muchas horas sin comer.
2. Entrenamiento después de un hueco largo.
3. Entrenamiento seguido de cena Recurso.
4. Día raro o de viaje.
5. Doble entrenamiento el mismo día — último, porque prueba acumulación de gasto, no el problema original.

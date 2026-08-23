# Mapa de transición — De la app actual al entrenador Gym

**Estado:** hoja de ruta conceptual; no es un plan de implementación aprobado.  
**Regla:** conservar el Gym funcional y transformar por contratos verificables,
no mediante un rediseño total.

## 1. Diagnóstico verificado

### Fortalezas que deben preservarse

- progresión Gym peso/repeticiones con decisión, aplicación y evaluación;
- RPE/RIR, técnica, topes de máquina y registro por series;
- rutinas, sesiones pendientes y versión esencial;
- frenos contextuales, intervenciones y preferencias reversibles;
- gestión de lesiones y alternativas;
- memoria mediante `GymDecisionLog`, traces y evaluaciones;
- check-in, Strava, Diario y JOI como fuentes existentes;
- motor Hyrox potente, conservado como campaña opcional.

### Problema de producto

Las capacidades están distribuidas entre motores, vistas, signals, paneles y
mensajes. No siempre existe una única autoridad; algunas decisiones se muestran
sin aplicarse, otras se aplican sin evaluación alineada y algunos aprendizajes
no se comunican o ascienden demasiado pronto a memoria.

## 2. Conflictos técnicos conocidos

### Gym

- técnica y molestias bloquean progresiones, pero carecen de evaluación
  específica;
- el cambio por estancamiento se reaplica y no evalúa la nueva variante;
- una molestia recurrente guardada como `ZONA:<zona>` probablemente no coincide
  con el nombre del ejercicio que el motor intenta sustituir;
- el deload reduce series/RPE objetivo, pero su evaluación observa sobre todo el
  peso;
- la versión esencial registra cumplimiento, pero no demuestra todavía su
  efecto en continuidad o recuperación;
- el motor dinámico se materializa en el briefing; rutas alternativas pueden
  eludir ajustes.

### Hyrox/carga/lesión

- `hyrox_decision` gobierna UI, pero no siempre modifica la sesión que describe;
- la adaptación continua puede invocarse desde dos rutas;
- existen dos deloads automáticos con umbrales y efectos distintos;
- un mismo evento Gym puede influir por fatiga, readiness y carga unificada;
- `RETORNO` es permitido por el generador y bloqueado por la decisión diaria;
- existen varias autoridades de alta de lesión y escalas de inflamación
  incompatibles;
- las rutas de referencia 5K no comparten la misma regla;
- los correctivos de simulación pueden nacer sin validar restricciones activas.

### Memoria/JOI/Diario

- una microverdad de IA puede ascender a `ManualDavid` sin confirmación;
- algunas evaluaciones de intervención no persisten;
- traces pueden quedar abiertos si no se generan otros nuevos;
- al crear una preferencia puede perderse el recuento exacto de evidencia;
- JOI verbaliza decisiones de manera desigual y no siempre comunica cierres;
- el context processor actual no cumple la apertura on-demand documentada;
- existen fallbacks narrativos sin decisión o aprendizaje subyacente.

## 3. Principio de transición

No se creará un cerebro paralelo. Se elegirá una autoridad canónica por familia y
los servicios existentes se convertirán en productores de señales, ejecutores o
evaluadores explícitos.

Secuencia obligatoria:

```text
contrato → tests de caracterización → adaptación mínima → evaluación real
→ comunicación → retirada de duplicidad
```

No se rediseñará la portada antes de estabilizar la semántica que debe mostrar.

## 4. Fase 0 — Congelar visión y medir uso

### Objetivo

Usar `PRODUCTO_ENTRENADOR_GYM.md` como autoridad de producto y dejar de ampliar
módulos legacy.

### Trabajo

- etiquetar módulos: núcleo, contextual, campaña, herramienta, experimental,
  archivado o legacy;
- documentar rutas de uso real de mañana, entrenamiento y noche;
- identificar procesos programados/signals de módulos archivados que siguen
  consumiendo recursos o generando mensajes;
- registrar dependencias antes de ocultar o retirar accesos.

### Salida

Inventario vivo y ninguna funcionalidad nueva fuera del núcleo.

## 5. Fase 1 — Caracterizar el Gym actual

### Objetivo

Proteger el motor que funciona antes de cambiar su autoridad.

### Trabajo

- tests de extremo a extremo para progresar, mantener, bajar, técnica, tope,
  molestia, estancamiento, deload y versión esencial;
- verificar briefing → sesión preparada → entrenamiento activo → resultado;
- comprobar todas las rutas de entrada al entrenamiento;
- distinguir `decidida`, `preparada`, `presentada`, `iniciada` y `completada`.

### Criterio de salida

Toda decisión Gym visible puede trazarse hasta el contenido real de la sesión.

### Inventario de rutas de finalización (cierre de Fase 1)

- **Núcleo:** `entrenos:guardar_entrenamiento_activo`, ruta principal del
  entrenamiento activo. Construye la sesión completa y ejecuta el cierre causal
  explícito una sola vez.
- **Núcleo:** `clientes:guardar_entrenamiento_activo`, guardado del portal. Su
  save final, ya con hijos, conserva compatibilidad con el cierre causal y la
  actividad unificada.
- **Compatible, UI huérfana:** `analytics:api_marcar_completado`. Mantiene el
  contrato de guardado y aprendizaje para consumidores existentes, aunque no se
  ha encontrado una interfaz activa que la invoque.
- **Legacy/inactivas:** importación Liftin, API móvil y `empezar_entreno`. Se
  inventarían garantías si se adaptaran sin confirmar uso y contrato; quedan
  fuera del núcleo y de esta fase.
- **Mantenimiento:** altas o ediciones desde Django Admin. Son operaciones de
  reparación/gestión y no garantizan ejecutar el ciclo de aprendizaje Gym.

## 6. Fase 2 — Autoridad diaria Gym

### Objetivo

Producir una única decisión soberana sin reescribir progresiones.

### Trabajo

- definir contrato de entrada: estrategia, semana, seguridad, recuperación,
  carga externa, adaptaciones y progresiones;
- resolver postura proteger/sostener/empujar;
- conservar causa principal, causas secundarias y capas suprimidas;
- materializar la decisión en una sesión preparada idempotente;
- dar vigencia/versionado y permitir corrección.

### Criterio de salida

Portada, briefing y entrenamiento consumen la misma decisión y no pueden
contradecirse.

### Primer corte implementado — contrato canónico reversible

- `resolver_autoridad_diaria_gym()` envuelve el motor existente; no crea un
  segundo planificador ni modifica sus umbrales.
- La salida declara `postura` (`proteger`, `sostener` o `empujar`), causa
  principal, causas secundarias, capas suprimidas, versión de esquema,
  vigencia diaria e identidad determinista.
- Las progresiones, frenos y deload se materializan una sola vez antes de que
  la sesión llegue a la portada. Cada ejercicio transporta la identidad de la
  decisión que lo produjo.
- El briefing reconoce una sesión materializada y no vuelve a aplicar el plan
  dinámico. Los accesos legacy sin esa marca conservan el fallback anterior.
- El semáforo se convierte en una proyección visual de esta autoridad, y
  `Organismo` respeta su evaluación de seguridad específica en lugar de
  imponer otra lectura Gym por encima.
- La caché se indexa por la huella de la decisión base: un cambio de check-in,
  lesión, carga externa o sesión prevista produce una nueva identidad.
- Desde la versión 2, cada propuesta se conserva como una versión inmutable de
  `GymDecisionVersion`. El historial incluye motor, correcciones supervisadas y
  reversiones; ninguna operación reescribe ni elimina la versión anterior.
- Cada corrección exige el identificador que el usuario está viendo, registra
  un motivo y solo puede mantener o aumentar la protección. Nunca puede relajar
  un freno fisiológico decidido por el sistema.

Este corte unifica **qué sesión se muestra y se ejecuta** y elimina los
veredictos Gym paralelos en portada. El control de supervisión permanece
plegado dentro de «Decisión hoy» y permite restaurar la propuesta del motor
creando otra versión de auditoría. Se conserva así todo el aprendizaje sin
convertir la portada en un editor permanente del plan.

## 7. Fase 3 — Estrategia, bloque y semana

### Objetivo

Dar contexto longitudinal a la decisión diaria.

### Trabajo

- auditoría semanal de solo lectura como puerta de entrada: versiones de la
  decisión, sesiones prescritas/realizadas, RPE, biometría y carga externa se
  extraen en un contrato JSONL sin interpretar todavía causalidad;
- contrato de bloque propuesto y aprobado;
- plan objetivo, mínimo y protegido;
- semana prescrita, viable y realizada;
- estados precisos de sesión: reubicada, omitida, cancelada, protegida;
- control de deriva entre bloque aprobado y bloque ejecutado;
- evaluación semanal y cierre de bloque multidimensional.

### Criterio de salida

Una sesión perdida no crea deuda infinita y una semana mínima válida sigue
contando como estímulo útil.

### Entrada de fase implementada — auditoría de evidencia real

`auditar_semana_gym` recibe cliente y ventana inclusiva y emite registros JSONL
deterministas. Usa `GymDecisionVersion` para el historial de autoridad,
`ActividadRealizada` para sesiones y carga, `BitacoraDiaria` para el check-in y
`StravaActivityRaw` únicamente como evidencia de procedencia o fusión. El
comando no ofrece `--apply` y no persiste ningún cálculo. Las sesiones
reubicadas entran por su fecha planificada o por su fecha real, evitando perder
justo la deriva que esta fase necesita estudiar.

### Primer contrato semanal aprobado

La estrategia semanal ya no depende de reinterpretar `dias_disponibles`. Se
conserva en `EstrategiaSemanalGym` como una política versionada y aprobada, y
cada lunes puede abrir un `ContratoSemanalGym` con una copia inmutable de sus
umbrales. El primer acuerdo confirmado establece **5 sesiones objetivo** y
**3 sesiones como mínimo válido**.

`SesionProgramada` puede quedar anclada al contrato y a su lunes de
prescripción. Su identidad y fecha prevista no cambian al reubicarla; la fecha
real se registra aparte. La evaluación semanal cuenta una reubicación una sola
vez, reconoce tres sesiones como semana válida y declara siempre cero deuda
automática hacia la semana siguiente. Durante la transición,
`dias_disponibles` se actualiza como proyección legacy para que Helms genere los
cinco días, pero la autoridad histórica reside en la estrategia versionada.

La materialización del contrato calcula primero la semana completa desde ese
snapshot y solo persiste si obtiene exactamente las cinco sesiones acordadas.
Es idempotente: adopta sesiones ya existentes sin duplicarlas ni alterar su
estado o reubicación, y enlaza entrenamientos reales inequívocos que ya se
hubieran completado. El comando `materializar_contrato_semanal_gym` funciona en
modo de lectura por defecto y exige `--apply` para escribir.

### Fase 3B — contrato longitudinal de bloque

`ContratoBloqueGym` añade el horizonte longitudinal sin sustituir al
planificador Helms. Una propuesta captura de forma inmutable el objetivo Gym,
los objetivos secundarios, límites, versión del motor y la estrategia semanal
5/3 vigente. Su `fingerprint` hace idempotente la misma propuesta y toda
corrección posterior debe publicarse como una versión sucesora.

La activación es explícita, transaccional y exige la versión que el usuario
está viendo. Solo puede existir un bloque activo o pausado por cliente y no se
permiten rangos abiertos solapados. Al abrir una semana dentro de un bloque
activo, `ContratoSemanalGym` queda vinculado con un índice 1..N únicamente si
estrategia y umbrales coinciden exactamente con el snapshot. Una divergencia
aborta la apertura; un bloque pausado no captura nuevas semanas y los contratos
legacy continúan siendo válidos con bloque nulo.

`auditar_bloque_gym` recorre exclusivamente sus contratos semanales enlazados,
clasifica objetivo, mínimo válido, insuficiente o aún no materializada y emite
JSONL determinista de solo lectura. No arrastra sesiones, no genera deuda y no
ajusta el plan. Los comandos de propuesta y activación son también dry-run por
defecto y requieren `--apply` para escribir.

El dry-run de `configurar_bloque_gym` resuelve la estrategia aprobada real y
emite el mismo snapshot y `fingerprint` que consumirá `--apply`: rango, versión
de estrategia, umbrales 5/3, objetivos, límites y versión de Helms. Si no hay
estrategia vigente falla explícitamente; nunca presenta como válida una
propuesta que después no podría persistirse.

### Fase 3C — cierre longitudinal supervisado

`EvaluacionBloqueGym` conserva versiones append-only de la evidencia de cierre.
Su única fuente son los `ContratoSemanalGym` enlazados y sus
`EvaluacionSemanalGym` persistidas y aceptadas: no busca entrenamientos libres
ni recalcula retrospectivamente una semana. El fingerprint de evidencia hace
idempotente el mismo cierre; una evidencia distinta solo abre otra versión si
la anterior no fue aceptada.

El preview puede declarar evidencia insuficiente y enumerar semanas ausentes,
no materializadas o sin revisión aceptada. `--apply` rechaza el cierre mientras
el bloque siga abierto o falte cualquiera de esas puertas. Con evidencia
completa clasifica `objetivo_sostenido`, `minimo_sostenido`,
`deriva_observada` o `interrumpido_seguridad`. Las sesiones canceladas por
lesión se conservan como protección y nunca se reinterpretan como fracaso de
adherencia.

La evaluación nace pendiente. Solo el propietario puede aceptarla o
rechazarla; aceptar finaliza el bloque y congela su evidencia, mientras que
rechazar mantiene el bloque abierto. Ninguna respuesta modifica estrategia,
sesiones, autoridad diaria ni `dias_disponibles`, y nunca se crea
automáticamente el bloque siguiente. `cerrar_bloque_gym` y
`responder_evaluacion_bloque_gym` son dry-run por defecto y exigen `--apply`.

## 8. Fase 4 — Cerrar ciclos Gym

### Objetivo

Evaluar las adaptaciones que hoy quedan abiertas o mal medidas.

Orden recomendado:

1. cambio de variante por estancamiento;
2. molestia recurrente por zona;
3. deload;
4. versión esencial;
5. técnica comprometida;
6. freno por molestia reciente;
7. distribución semanal.

Cada una debe declarar resultado esperado, ventana, métrica, reversión y
promoción —o no— a conocimiento.

### Ciclo 1 implementado — variante por estancamiento

El cambio de variante deja de ser una sustitución efímera y pasa a ser un
experimento causal independiente. La alternativa se fija una sola vez durante
un máximo de dos ejecuciones o 21 días; cada ejecución queda vinculada al
experimento y su resultado se cierra como favorable, fallido o insuficiente.
Al cerrarse, el plan vuelve automáticamente al ejercicio original porque la
rutina nunca se muta. Este resultado permanece como evidencia local y no se
promueve todavía a preferencia ni a conocimiento longitudinal.

### Ciclo 2 implementado — molestia recurrente por zona

Las molestias leves solo activan una intervención tras aparecer en tres
sesiones distintas dentro de 21 días. La zona se normaliza y se traduce a
`risk_tags`; la alternativa queda fijada y no comparte los riesgos
restringidos. La intervención dura dos ejecuciones o 21 días y termina como
favorable, fallida o insuficiente, volviendo después al ejercicio original.
Una molestia moderada o severa queda fuera de este ciclo y conserva la
autoridad de lesión. Esta evidencia tampoco se convierte en preferencia ni en
conocimiento longitudinal.

## 9. Fase 5 — Carga externa y recuperación

### Objetivo

Usar Strava y check-in sin duplicar carga.

### Trabajo

- evento físico canónico y reconciliación de duplicados;
- dimensiones de carga en lugar de sumas opacas;
- línea base personal de HRV, FC en reposo y sueño;
- disponibilidad general y local por zona/estímulo;
- calibración individual de respuesta a fútbol y otras actividades;
- calidad, vigencia y ausencia explícita de datos manuales.

### Criterio de salida

Un evento externo se cuenta una vez y su efecto puede explicarse en la decisión
Gym.

## 10. Fase 6 — Lesión y retorno

### Objetivo

Una sola autoridad de seguridad y retorno.

### Trabajo

- vocabulario y escalas compartidas;
- fases con permisos explícitos;
- diferencia entre bloqueo, adaptación y retorno;
- una única vía canónica de alta, con acciones manuales como supervisión;
- respuesta durante y 24 horas después;
- filtros de seguridad obligatorios para cualquier sesión generada.

### Criterio de salida

La fase `RETORNO` produce una sesión compatible, no una contradicción entre motor
y UI.

## 11. Fase 7 — Campañas y encapsulación de Hyrox

### Objetivo

Conservar capacidades Hyrox sin permitir autoridad permanente.

### Trabajo

- estados inactiva/exploración/activa/finalizada;
- contrato de campaña con prioridad respecto a Gym;
- desactivar automatizaciones específicas fuera de campaña;
- unificar adaptación continua, deload, referencia 5K y correctivos;
- transferir aprendizajes al Gym al finalizar.

### Criterio de salida

Sin campaña activa, Hyrox no genera una segunda decisión soberana.

## 12. Fase 8 — Memoria y epistemología

### Objetivo

Recordar correctamente y permitir olvidar o superar.

### Trabajo

- estados hecho/señal/patrón/hipótesis/conocimiento/preferencia;
- vigencia, caducidad, confianza y evidencia;
- impedir promoción automática de inferencias narrativas;
- persistir evaluaciones relevantes;
- cerrar backlog sin depender de nuevos traces;
- conservar correcciones y revocaciones.

### Criterio de salida

Toda afirmación longitudinal puede explicar de dónde procede y qué autoridad
tiene hoy.

## 13. Fase 9 — Puente Diario ↔ entrenador

### Objetivo

Mantener el Diario personal y compartir solo contexto autorizado.

### Trabajo

- clasificar disponibilidad, recuperación, continuidad y relación con entrenar;
- transmitir señal mínima, no texto íntimo;
- confirmación y alcance temporal;
- registro de decisiones influidas;
- corrección o retirada sencilla.

### Criterio de salida

Un cierre puede tener valor personal sin convertirse en dato deportivo.

## 14. Fase 10 — JOI

### Objetivo

Dar voz a decisiones y cierres verificados.

### Trabajo

- fuente estructurada obligatoria para afirmaciones deportivas;
- lenguaje según nivel epistemológico;
- síntesis de varias decisiones bajo lock, en lugar de pérdida silenciosa;
- comunicación de resultados, no solo triggers;
- reconciliar la apertura on-demand documentada con el comportamiento real;
- retirar fallbacks que simulan aprendizaje.

### Criterio de salida

Si JOI dice que el entrenador aprendió algo, existe una evaluación que lo
respalda.

## 15. Fase 11 — Experiencia y navegación

Solo después de las fases semánticas:

- Hoy;
- Entrenar;
- Plan;
- Memoria.

La portada se rediseña desde contratos estables y conserva acceso a decisión,
estado, pendientes, aprendizaje, sesiones recientes y herramientas. No se
eliminan capacidades útiles para conseguir una pantalla aparentemente simple.

## 16. Fase 12 — Archivo y simplificación

### Objetivo

Reducir superficie sin destrucción prematura.

### Trabajo

- retirar gamificación, Liftin, gestión de gimnasio y experimentos de la
  experiencia activa;
- desactivar sus mensajes y tareas cuando sea seguro;
- mantener datos históricos;
- medir dependencias antes de eliminar código o modelos;
- decidir más adelante qué merece borrado físico.

## 17. Orden de riesgo

### Bajo riesgo

- documentación y clasificación;
- tests de caracterización;
- ocultar navegación legacy sin desactivar procesos;
- corregir textos que afirman acciones no aplicadas.

### Riesgo medio

- decisión soberana;
- persistencia de evaluaciones;
- reconciliación de carga;
- puente contextual del Diario;
- JOI basada en contratos.

### Alto riesgo

- cambiar generación de sesiones;
- unificar deloads;
- modificar fases de lesión;
- encapsular automatizaciones Hyrox;
- retirar modelos o signals legacy.

El trabajo de alto riesgo exige tests de caracterización, datos reales de
PythonAnywhere cuando correspondan y migraciones reversibles.

## 18. Primera entrega recomendada

Antes de cualquier nuevo diseño visual:

1. caracterizar progresión y aplicación Gym de extremo a extremo;
2. elaborar el mapa ejecutable de autoridades actuales;
3. seleccionar una sola decisión diaria canónica;
4. demostrar que la sesión preparada refleja el cambio;
5. cerrar una adaptación incompleta —preferentemente cambio de variante—;
6. comunicar su evaluación mediante JOI solo cuando exista.

Esta entrega prueba el ciclo completo sin reconstruir el motor.

## 19. Reglas de ejecución futura

- una fase cada vez, con contrato y TDD;
- pruebas dirigidas durante iteración; suite amplia antes de publicar cambios de
  autoridad;
- sin migraciones irreversibles para estados aún experimentales;
- sin usar datos locales como prueba de comportamiento productivo cuando la
  actividad real vive en PythonAnywhere;
- solicitar únicamente consultas de producción anonimizadas y de solo lectura;
- no dar por implementada una capacidad porque figure en documentación;
- actualizar este mapa cuando una fase cierre un conflicto.

## 20. Condición de éxito de la transición

La transición termina cuando:

- Gym conserva su funcionamiento y gana una estrategia explícita;
- cada día existe una sola decisión coherente y realmente aplicada;
- semana y bloque aprenden de la ejecución real;
- seguridad y carga no se duplican;
- las adaptaciones importantes se evalúan;
- la memoria distingue hipótesis y conocimiento;
- JOI comunica cierres verificables;
- Diario comparte únicamente contexto autorizado;
- los módulos archivados dejan de competir por atención.

Después, el producto podrá evolucionar sin volver a perder su identidad.


---

## Ciclo 3 · Fase 4 — ciclo de descarga global

`entrenos.CicloDeload` es la fuente persistida compartida. Gym abre y gobierna el
ciclo global; Hyrox aporta la señal TSB y consume su política. `GymDecisionLog`
solo registra el evento derivado de apertura, no el lifecycle.

La prioridad operativa es lesión activa, descanso planificado, ciclo de descarga
de seguridad y estrategia/progresión ordinaria.

Política V1:

- Gym: 7 días; resta una serie (mínimo dos) y limita el RPE a 7.
- Hyrox: 9 días; factor 0.55 al materializar métricas.
- Los overlays son idempotentes y nunca guardan cambios en sesiones futuras.
- El calendario Hyrox y su taper permanecen intactos.
- La apertura usa transacción y bloqueo del cliente para un único ciclo activo en MySQL.
- El cierre clasifica el resultado como favorable, fallido o insuficiente.

El signal Hyrox TSB < -30 dejó de mutar sesiones. `DeloadAutoTrigger` conserva
TSB < -25 como detector puro. JOI recibe un evento al abrir y otro al cerrar
mediante sus generadores existentes; no se hardcodea su voz aquí.

## Ciclo 4 · Evaluación de la versión esencial V1

Al aceptar `esenciales_frecuentes`, el snapshot contractual conserva un bloque
aditivo `evaluacion_v1`: congela los 21 días anteriores como baseline y las
fechas efectivas de la prueba. Los snapshots antiguos siguen siendo válidos.

La medición usa `SesionProgramada`, excluye omisiones de sistema y cancelaciones
por lesión, cuenta una reubicación una sola vez y atribuye una completada al día
real (`fecha_ejecucion`). Registra cobertura de principales, RPE y energía, y
lee el objetivo/mínimo del `ContratoSemanalGym`; el fallback histórico 5/3 solo
se usa cuando aún no existe contrato.

El veredicto legacy se conserva. La comparación con baseline es descriptiva,
marca el abandono evitado como no demostrable y revierte el freeze al terminar
o cancelarlo. Nunca crea preferencias, escribe ManualDavid, cambia estrategia
ni promociona automáticamente la observación.

## Ciclo 5 · Técnica comprometida V1

La técnica por serie deja de ser solo un freno momentáneo. Una sesión con al
menos una serie comprometida genera una `GymDecisionLog` causal de tipo
`tecnica_comprometida`, mantiene la carga y bloquea la progresión. El fallo
muscular o un RPE extremo conservan prioridad y pueden ordenar una reducción.

La siguiente ejecución del mismo ejercicio cierra la decisión:

- técnica buena o aceptable con carga consolidada: validada;
- técnica comprometida de nuevo: fallida y se abre un nuevo freno;
- sin valoración técnica: neutra por evidencia insuficiente;
- técnica recuperada sin respetar la consolidación: neutra.

El ciclo es local, automático y reversible. No crea preferencias, no cambia la
estrategia semanal y no convierte una observación técnica en conocimiento
permanente. Los logs históricos reconocibles se clasifican durante la migración
para que las decisiones aún pendientes puedan evaluarse con el contrato nuevo.

## Ciclo 6 · Tope de máquina V1

Un tope físico mantiene el peso disponible y propone progresar `+1 rep` o
`+5 m` cuando el ejercicio usa distancia. La decisión queda clasificada como
`tope_maquina` y la siguiente ejecución solo la valida si alcanza el objetivo
sin cambiar el peso; fallo, RPE crítico, cambio de carga o rendimiento inferior
se distinguen explícitamente.

Si tres topes consecutivos repiten el mismo peso y las mismas repeticiones, el
sistema deja de insistir con una progresión imposible y crea una propuesta
colaborativa `cambiar_variante`, con causa `tope_maquina_sin_margen`. Cualquier
ganancia de repeticiones reinicia el conteo. Las señales de seguridad —fallo,
RPE extremo y técnica comprometida— conservan prioridad.

El tope no se convierte en preferencia ni modifica la estrategia semanal. Los
logs históricos reconocibles se clasifican para evaluar correctamente las
decisiones que aún estuvieran pendientes al desplegar esta versión.

## Ciclo 7 · Fallo muscular V1

El entrenamiento activo captura de forma explícita si el fallo fue `previsto`
o `no previsto`. `RIR=0` deja de utilizarse como proxy de intención: los datos
legacy sin clasificación se tratan como no controlados por seguridad.

Un fallo previsto consolida la carga sin penalizar la sesión. El primer fallo
no previsto mantiene la carga y abre una evaluación; dos fallos no previstos
consecutivos reducen el peso. La siguiente ejecución valida el ajuste cuando
recupera margen sin un nuevo fallo accidental ni RPE crítico. Un tope de
máquina no anula esta señal de seguridad.

La interfaz presenta un único control compacto y pide la intención en un diálogo
de tres opciones. El ciclo es local y reversible, no modifica la estrategia
semanal ni genera preferencias. JOI solo verbaliza el fallo no previsto; un
fallo deliberado no produce una intervención narrativa innecesaria.

## Ciclo 8 · RPE alto sostenido V1

El RPE local se evalúa según su almacenamiento real entero. Tres ejecuciones
consecutivas del mismo ejercicio con RPE `≥9` generan una reducción de carga;
una ejecución aislada no. Un RPE `10` sigue siendo una señal extrema que actúa
sin esperar historial. Los umbrales decimales permanecen únicamente en métricas
agregadas donde sí pueden existir promedios.

La siguiente ejecución cierra causalmente la reducción: queda validada si el
peso baja y el RPE vuelve a `≤8`, fallida si la reducción se aplica pero el RPE
sigue en `≥9`, y neutra si la reducción no llegó a aplicarse o falta evidencia.
Una sesión controlada interrumpe la consecutividad.

Este ajuste es local, diario y reversible. No sustituye al ciclo de deload
global basado en fatiga acumulada, no cambia la estrategia semanal y no genera
preferencias. JOI usa la decisión existente de reducción para verbalizarla sin
crear una segunda presencia paralela.

## Ciclo 9 · Progresión positiva V1

Las progresiones ordinarias de peso y repeticiones quedan identificadas con una
causa estable. Solo se evalúan cuando el plan las materializó con estado
`aplicada`; una decisión pendiente o pospuesta no puede aprender por accidente
de una ejecución que no siguió esa prescripción.

La siguiente ejecución valida el ajuste únicamente si alcanza el objetivo
completo con RPE `≤8`, sin fallo muscular y sin técnica comprometida. Un avance
parcial o la falta de RPE quedan como evidencia neutra; alcanzar el objetivo con
RPE alto, fallo o técnica comprometida lo marca como fallido. La progresión por
distancia usa el mismo contrato mediante su objetivo concreto de repeticiones.

El cambio conserva los contratos especiales de tope de máquina, técnica, fallo
y RPE sostenido. No altera la estrategia semanal ni crea preferencias: solo
evita que el perfil de adaptación aprenda de progresiones no aplicadas o
incompletas.

## Ciclo 10 · Perfil de adaptación causal e idempotente V1

El perfil personal de incremento de peso aprende exclusivamente de decisiones
`progresion_peso` que el plan aplicó y cuya evaluación terminó como validada o
fallida. Las progresiones pospuestas, resultados neutros, progresiones de
repeticiones y ciclos protectores no aumentan sus contadores ni su confianza.

La calibración se reconstruye siempre desde la base explícita histórica del
5 % y la evidencia pertinente más reciente. Por ello, procesar dos veces los
mismos resultados produce exactamente el mismo perfil: dos validaciones llevan
al 5,5 % y dos fallos al 4 %, sin multiplicaciones acumulativas accidentales.

La reducción de peso se conserva intacta. Deloads, RPE alto, técnica o fallos
son intervenciones de seguridad con contratos propios y no se reutilizan para
calibrar una progresión positiva. La confianza baja, media o alta depende solo
del número de progresiones de peso aplicadas y concluyentes.

## Ciclo 11 · Cierre semanal causal V1

Cada contrato semanal completamente materializado puede producir una única
evaluación versionada cuando termina su semana. El cumplimiento distingue el
objetivo completo, la mínima válida y una semana insuficiente usando los
umbrales inmutables del propio contrato. Las sesiones reubicadas conservan su
identidad prescrita y se cuentan una sola vez; las pendientes nunca pasan a la
semana siguiente como deuda.

La evidencia se construye exclusivamente desde las sesiones ancladas al
contrato. Volumen, duración, energía y RPE solo entran mediante el vínculo
explícito con `EntrenoRealizado`; una coincidencia de cliente o fecha no basta.
Cada métrica declara su cobertura y mantiene `None` cuando falta información,
sin completar huecos mediante heurísticas.

El cálculo es transaccional e idempotente. Mientras la revisión siga pendiente,
una evidencia nueva actualiza el mismo cierre; después de aceptarlo o rechazarlo,
el snapshot queda protegido frente a sobrescrituras automáticas. La respuesta
del usuario solo registra su revisión: no cambia la estrategia, el contrato, las
sesiones ni `dias_disponibles`.

# Operación e interfaz del cierre semanal (Ciclo 11)

El Centro de decisiones consulta, sin crear ni recalcular, la evaluación más
reciente de una semana cerrada. Si está pendiente presenta una única card de
`Cierre semanal` dentro de `Activo ahora`; aceptar o rechazar solo registra la
revisión humana y no cambia la estrategia 5/3 ni los días disponibles.

El cierre se ejecuta de forma explícita. Por defecto el comando previsualiza la
semana anterior y no escribe; `--apply` persiste la evaluación:

```bash
python manage.py cerrar_semana_gym --cliente <ID>
python manage.py cerrar_semana_gym --cliente <ID> --semana AAAA-MM-DD --apply
```

La semana debe estar cerrada y el contrato debe contener exactamente todas sus
sesiones prescritas. La salida es JSON estable para facilitar su operación y
auditoría.

# Ciclo 12 — molestia reciente causal V1

- Severidad exactamente 1 genera una decisión causal e idempotente `molestia_reciente`.
- La decisión conserva peso, repeticiones, RPE y zona como snapshot estructurado.
- Durante 14 días limita únicamente el mismo ejercicio; después caduca de forma neutra.
- La primera reexposición cierra la evaluación como validada, fallida o neutra.
- Fallo, RPE extremo, técnica comprometida, reducción y deload conservan prioridad.
- El modo API `solo_alternativas` es una previsualización sin mutaciones clínicas.

# Fase 5.1–5.2 — snapshot físico canónico V1

La evidencia física diaria dispone de un contrato de solo lectura común en
`core`. El snapshot conserva la procedencia y antigüedad del check-in, el
readiness Hyrox exacto del día, las lesiones activas y la actividad de las
últimas 48 horas. La actividad reubicada declara como fecha efectiva
`fecha_realizado` y usa `fecha` únicamente como fallback; los datos ausentes o
obsoletos se mantienen explícitos, sin inventar valores neutros.

La autoridad Gym adjunta esta fotografía y su huella SHA-256 a la versión de la
decisión como evidencia en sombra. Todavía no interviene en el fingerprint
ejecutivo, los umbrales, la postura, el volumen ni la sesión recomendada. Las
correcciones y reversiones reutilizan la evidencia ya capturada, y un fallo al
leer una fuente no bloquea el comportamiento vigente del entrenador.

Este corte no añade tablas ni migraciones. Su objetivo es medir divergencias
entre las lecturas históricas antes de sustituirlas de forma gradual.

## Fase 5.3 — lectura canónica con equivalencia legacy

La autoridad construye una sola captura física por resolución y entrega esa
misma evidencia al motor Gym y a `GymDecisionVersion`. Energía, sueño, frecuencia
cardiaca en reposo, HRV, dolor, readiness y lesión se derivan ya desde el
snapshot. Se conservan exactamente los umbrales y prioridades anteriores: el
check-in solo gobierna en su fecha exacta y únicamente una lesión aguda o
subaguda activa la protección existente.

El snapshot se recaptura antes de consultar la caché ejecutiva, de modo que un
check-in o readiness recién guardado puede cambiar la decisión inmediatamente.
Las correcciones y reversiones, en cambio, reutilizan la captura de su versión
vigente para no reescribir la evidencia histórica. Si el constructor falla, el
motor degrada temporalmente a las consultas legacy.

Fútbol e Hyrox reciente continúan leyendo la fecha planificada antigua durante
este corte. El paso a `fecha_realizado` queda reservado como cambio funcional
aislado para la Fase 5.4.

## Fase 5.4 — carga reciente por fecha efectiva

La señal de actividad previa se deriva ya del snapshot físico y usa como fecha
efectiva `fecha_realizado`, con `fecha` como fallback cuando no existe una fecha
de ejecución. Al trabajar con `DateField`, la ventana de 48 horas comprende los
dos días naturales anteriores a la sesión; excluye el propio día, fechas futuras
y registros de tres o más días atrás.

El fútbol genera la señal de carga reciente con cualquier RPE. Hyrox conserva
el umbral anterior de RPE `≥7`, por lo que una sesión de recuperación no reduce
la sesión Gym. Ambas señales solo modifican una sesión de tren inferior, como
antes. La consulta histórica por fecha planificada permanece únicamente como
fallback operativo si el snapshot completo no está disponible.

## Fase 5.5 — evidencia física trazable para JOI

JOI puede leer los hechos físicos desde la `GymDecisionVersion` vigente ya
materializada, sin resolver otra vez el plan ni construir un segundo snapshot.
La proyección valida cliente, fecha, versión de esquema y procedencia, conserva
los ceros reales y aplica una whitelist para no trasladar datos internos.

El bloque factual solo se incorpora cuando el flujo existente genera una
apertura de mañana o verbaliza una decisión del plan. Incluye fecha de corte,
referencia de huella y fuente de cada hecho disponible; nunca convierte una
señal ausente u obsoleta en normalidad y prohíbe atribuir causalidad. No crea
triggers, cards, mensajes adicionales ni presencias fuera de la habitación de
JOI. El resumen semanal queda excluido porque usa evidencia propia del periodo.

## Fase 5.6 — auditoría pasiva de divergencias

El comando `auditar_snapshot_fisico_gym` compara la evidencia física persistida
con el `contexto_fisico` que quedó materializado en cada decisión. Es siempre de
solo lectura: no ofrece `--apply`, no resuelve la autoridad y no reconstruye
snapshots desde fuentes vivas.

La salida JSONL diferencia versiones legacy sin captura, capturas no disponibles,
contratos inválidos y divergencias campo a campo. Las correcciones y reversiones
se auditan contra su versión motor base para no confundir una intervención humana
con una incoherencia física. El rango predeterminado usa la fecha local de Django,
cubre 30 días y admite como máximo 500 autoridades por ejecución.

```bash
python manage.py auditar_snapshot_fisico_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```

### Promoción de una autoridad legacy del día actual

Si la autoridad vigente se creó antes del contrato físico V1, el comando de
materialización permite inspeccionarla en dry-run y promocionarla explícitamente:

```bash
python manage.py materializar_snapshot_fisico_gym \
  --cliente <ID> \
  --settings=gymproject.settings

python manage.py materializar_snapshot_fisico_gym \
  --cliente <ID> \
  --apply \
  --settings=gymproject.settings
```

La promoción no modifica la fila legacy: crea una sucesora motor enlazada que
mantiene `decision_id`, fingerprints, postura y causa, y añade el snapshot V1.
Solo puede aplicarse a la fecha local actual, ocurre una vez y no atraviesa una
corrección o reversión manual. El modo `--apply` omite de forma selectiva una
posible respuesta ejecutiva antigua en caché y la actualiza al terminar.

## Fase 5.7 — autoridad única durante la ejecución

La pantalla de entrenamiento activo reconoce una prescripción materializada
cuando todos sus ejercicios llevan `_autoridad_gym_materializada=True`. En ese
caso presenta exactamente la decisión ejecutiva ya resuelta: no vuelve a aplicar
BioContext, hot-swap, límites de RPE, progresión por historial, topes ni deload.
Estos factores ya fueron considerados al construir la autoridad y una segunda
pasada podía alterar series, repeticiones, peso o incluso la identidad del
ejercicio sin dejar una nueva versión trazable.

La vista conserva únicamente enriquecimientos de interfaz y aliases compatibles
con el formulario. Las rutas explícitas de intervención durante la sesión siguen
disponibles y deberán crear o registrar su propia decisión. Las sesiones legacy,
listas mixtas y accesos directos sin autoridad materializada mantienen el flujo
anterior como fallback de transición.

## Fase 6.1 — supervisión manual sobre base inmutable

Una corrección manual se construye siempre desde el snapshot completo de la
versión `motor` que comparte el `base_fingerprint` de la autoridad vigente. No
encadena el contenido de una corrección anterior: únicamente aplica los campos
supervisables permitidos y conserva sin reinterpretar el snapshot físico, la
base, el entrenamiento y los cambios ejecutivos materializados por el motor.

La supervisión sólo puede mantener o aumentar seguridad. `sostener` materializa
`estado=version_reducida` y `modo_reducido=true`; `proteger` materializa
`estado=recuperar`, `postura=proteger` y queda no ejecutable por ese estado, sin
inventar otra propuesta ni borrar la evidencia del entrenamiento original.

La reversión tampoco parchea la corrección vigente: copia íntegramente el
snapshot motor compatible y sólo añade la identidad y metadatos de una nueva
versión con origen `reversion_manual`. Correcciones y reversiones mantienen el
historial inmutable, el control optimista mediante `decision_id` y el guard que
impide relajar seguridad. Si cambia la evidencia y, por tanto, el
`base_fingerprint`, la versión manual deja de ser compatible y el motor crea la
nueva autoridad; nunca se arrastra una intervención de una base anterior.

## Fase 6.2 — identidad ejecutiva entre CTA, briefing y sesión

El CTA Gym emitido por el Organismo incluye el `decision_id` de la autoridad
vigente. El briefing conserva esa identidad al construir el enlace hacia la
sesión activa, de modo que los dos saltos forman una única intención ejecutiva
trazable.

Cuando existe `decision_id`, cada vista vuelve a resolver la autoridad para el
usuario, cliente y fecha antes de leer o transformar el payload. Si una
corrección o nueva evidencia cambió la versión entre pasos, la petición se
rechaza con conflicto y pide recargar el plan; nunca ejecuta silenciosamente la
prescripción anterior. También se comprueba que cualquier identidad embebida en
los ejercicios coincida con la URL. Los enlaces legacy sin identidad conservan
el fallback previo durante la transición. Briefing y sesión activa exigen que
el cliente pertenezca al usuario autenticado.

Cada corrección o reversión reestampa además el nuevo `decision_id` en todos los
ejercicios materializados. El contenido ejecutivo sigue siendo una copia exacta
del motor compatible; sólo cambian los metadatos de identidad y supervisión.
Una autoridad vigente en `proteger`, `recuperar`, `descanso` o `posponer` puede
abrirse como revisión en el briefing, pero no ofrece CTA de comienzo y la sesión
activa la rechaza antes de recuperar el payload. El acceso legacy sin identidad
mantiene su comportamiento histórico.

## Fase 5.8 — auditoría de identidad del evento físico

Antes de reconciliar carga se incorpora una auditoría estrictamente pasiva sobre
`ActividadRealizada` y la bandeja procesada de Strava. Agrupa eventos del mismo
cliente, fecha efectiva y modalidad, pero los etiqueta como ambiguos: dos
sesiones Gym o dos carreras el mismo día pueden ser esfuerzos reales distintos
y nunca deben fusionarse por una coincidencia superficial.

También declara actividades Strava marcadas como procesadas que no conservan un
vínculo al entrenamiento Gym o Hyrox. El comando no corrige, suma de nuevo ni
modifica el histórico; aporta IDs, fuentes, duración y carga para diseñar la
reconciliación con evidencia de producción.

```bash
python manage.py auditar_eventos_fisicos_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```

## Fase 5.9 — identidad Strava → evento canónico

Cada actividad Strava procesada puede conservar un enlace uno-a-uno al
`ActividadRealizada` que creó o enriqueció. `create_gym` lo asigna al crear el
evento; `merge_gym` lo asigna al hub de la sesión; los flujos Hyrox lo asignan
solo cuando ya existe una actividad realizada. Una sesión Hyrox todavía
planificada conserva únicamente su enlace a `HyroxSession`, sin fingir que el
esfuerzo ya ocurrió.

La auditoría deja de presentar varias actividades Strava del mismo tipo y día
como posibles duplicados. Solo eleva como probable una coincidencia entre
fuentes con duraciones próximas o dos filas manuales con el mismo título. Los
registros `created` anteriores al nuevo vínculo se clasifican como deuda de
trazabilidad legacy, no como prueba de carga duplicada.

## Fase 5.10 — recuperación de identidad Strava legacy

El comando `vincular_strava_hub_legacy` recupera enlaces anteriores al contrato
5.9 únicamente cuando existe un candidato inequívoco: misma fecha efectiva,
fuente Strava, título normalizado y duración con un margen máximo de dos minutos.
Cuando hay empate, falta candidato o el registro figura como `merged` sin una
autoridad Gym/Hyrox, el caso queda ambiguo y no se modifica.

El modo predeterminado es dry-run; `--apply` solo escribe la relación uno-a-uno,
sin cambiar carga, fechas, estado ni contenido del evento. Repetirlo es neutro.

```bash
python manage.py vincular_strava_hub_legacy \
  --cliente <ID> \
  --settings=gymproject.settings
```

## Fase 5.11 — fecha efectiva Gym reconciliada con Strava

Cuando Strava se fusiona con un entrenamiento Gym, su fecha observada gobierna
`EntrenoRealizado.fecha_ejecucion` y `ActividadRealizada.fecha_realizado`. La
fecha planificada de la rutina permanece intacta en los campos `fecha`, por lo
que corregir el día real no altera la pertenencia de la sesión al plan.

Para datos legacy, `reconciliar_fechas_strava_gym` compara únicamente registros
`merged` que conservan los tres enlaces Strava, Gym y hub. Un desfase exacto de
un día se propone en dry-run; diferencias mayores o desacuerdo previo entre Gym
y hub quedan ambiguos. `--apply` actualiza ambas fechas efectivas en una sola
transacción y repetir el comando es neutro.

Los registros legacy que conservan `entreno_gym` pero no el vínculo nuevo al hub
derivan este último mediante la relación uno-a-uno del entrenamiento. El dry-run
lo declara y `--apply` persiste el enlace junto con la eventual corrección de
fecha. Un entrenamiento sin hub nunca se reconstruye por semejanza.

Si varios registros Strava legacy apuntan al mismo entrenamiento, solo se acepta
automáticamente uno cuando coincide de forma única con la fecha efectiva ya
persistida. Los restantes se mantienen ambiguos; nunca compiten por el mismo
enlace uno-a-uno ni desplazan una fecha basándose en el orden de procesamiento.

```bash
python manage.py reconciliar_fechas_strava_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```

## Fase 5.12 — cumplimiento Gym por fecha efectiva

La recomendación diaria y la reconciliación batch de sesiones programadas usan
la fecha real del esfuerzo como autoridad. Para `EntrenoRealizado`, la fecha
efectiva es `fecha_ejecucion` cuando existe y, solo para registros legacy sin
ese dato, `fecha`. Para `ActividadRealizada` Gym se aplica el mismo contrato con
`fecha_realizado` y el fallback `fecha`.

El fallback es exclusivo: una sesión con fecha efectiva no cuenta también en
su fecha planificada. Esto evita cerrar una prescripción histórica o impedir la
sesión de hoy porque el entrenamiento pertenecía originalmente a otro día del
plan. El cambio se limita a comprobar cumplimiento y a formar el conjunto batch
de fechas completadas; no modifica carga, duración, RPE, estrategia ni JOI.

## Fase 5.13 — auditoría de métricas Strava, Gym y hub

`auditar_metricas_strava_gym` comprueba, sin escribir, los raws Strava `merged`
que conservan enlaces explícitos al entrenamiento Gym y a su evento canónico.
Antes de comparar valida el mismo cliente, el mismo entrenamiento en el hub y
la existencia de un único raw por sesión.

Gym y hub deben tener idéntica duración. Strava se deriva de segundos y admite
solo el truncado a minutos enteros (delta menor de un minuto); diferencias
mayores quedan con procedencia desconocida. La carga se compara únicamente en
el hub contra `rpe_medio × duracion_minutos`, con tolerancia de 0,1 UA. No se
compara volumen kg. Una carga sin duración o sin RPE queda informativa como
posible fallback, pero nunca se reconstruye.

El resumen distingue los candidatos totales de los evaluados: `truncated`
cuenta los registros omitidos por `--limit`. Las diferencias fraccionales de
duración aceptadas se reportan aparte en `duration_truncations_tolerated`.

```bash
python manage.py auditar_metricas_strava_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```

## Fase 5.14 — partición de identidad Strava, Gym y hub

`clasificar_identidad_strava_gym` produce una partición exhaustiva y disjunta
de los raws Strava `merged` del cliente y rango. Ese estado es el alcance por
defecto y cada raw candidato aparece exactamente una vez. La prioridad es: conflictos de cliente o
FK; actividad no Gym; multiplicidad de raws; y finalmente identidad completa,
hub canónico ausente o enlace al hub recuperable de forma inequívoca.

Las actividades sin `entreno_gym` quedan fuera del alcance Gym y se
subclasifican por estado, tipo normalizado y presencia de `hyrox_session`. No se
interpretan como Gym incompleto. Para una sesión Gym sin enlace directo al hub,
la recuperación solo se considera posible si existe su hub inverso canónico,
del mismo cliente y tipo Gym, y hay un único raw para esa sesión. Además, las
fechas efectivas Gym y hub deben coincidir y Strava debe quedar como máximo a un
día de Gym. Si no se cumple, el raw queda en
`gym_missing_hub_date_conflict`; la categoría de múltiples raws conserva mayor
prioridad para que una divergencia temporal no oculte la ambigüedad estructural.
Cada fila expone fechas planificadas y efectivas, además del delta absoluto en
días entre Strava y Gym, para hacer auditable esta decisión.

El comando selecciona `merged` por defecto; no mezcla pendientes, creados o
ignorados con la deuda de identidad Gym. `--limit` solo trunca la presentación: `total` y
`gym_raw_count` se calculan sobre todo el rango, de modo que nunca oculta una
multiplicidad. El resumen prueba la partición mediante `partition_count` y
`partition_complete`. Es estrictamente de solo lectura y no ofrece `--apply`.

```bash
python manage.py clasificar_identidad_strava_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```
# Fase 6.4A — sello causal de ejecución supervisada

- La sesión activa emite un sello firmado de la `GymDecisionVersion` exacta
  que fue validada y mostrada al usuario.
- El cierre persiste esa versión en `EntrenoRealizado`, junto con la hora de
  emisión y el estado causal `exacta` o `superada_durante_ejecucion`.
- Una corrección creada mientras el usuario entrena no invalida ni reasigna la
  sesión: se conserva la versión que realmente guio la ejecución.
- Los flujos históricos sin sello siguen siendo válidos y mantienen los tres
  campos causales a `NULL`; no se hace backfill inferido por fecha.
- Un sello alterado, ajeno o incoherente se rechaza antes de crear datos.
- El sello V1 caduca a las 24 horas y cualquier fallo tardío del guardado
  revierte atómicamente la sesión completa.
# Fase 6.4B — cierre factual de supervisión diaria

- Las correcciones y reversiones manuales vigentes se evalúan solo después de terminar el día.
- Una ejecución favorable exige el vínculo causal exacto con `GymDecisionVersion`; los registros legacy no se reinterpretan por fecha.
- `proteger` distingue protección cumplida, ejecución posterior incompatible y actividad previa no atribuible.
- El cierre es explícito, auditable e idempotente mediante `cerrar_supervision_gym` (dry-run por defecto).
- Esta fase no modifica estrategia, contratos, autoridad diaria ni JOI.

# Fase 6.5 — auditoría pasiva de autoridad de lesión Gym

- `auditar_autoridad_lesion_gym` revisa dos planos independientes y nunca
  escribe: la propagación de la lesión capturada dentro de la decisión diaria
  y la alineación actual entre `EpisodioRehab` y `UserInjury`.
- El plano histórico usa exclusivamente la `GymDecisionVersion` final y
  vigente y su `physical_snapshot` persistido. No reconstruye el pasado desde
  lesiones vivas, no resuelve una autoridad nueva y no consulta etiquetas de
  ejercicios en la base de datos.
- Las restricciones AGUDA/SUB_AGUDA y los avisos RETORNO quedan clasificados
  de forma exclusiva, incluyendo contratos inválidos, etiquetas no
  verificables, protección incumplida, advertencia ausente y ausencia real de
  conflicto con la sesión.
- La alineación de fuentes es conservadora y se emite por episodio Rehab:
  zona y lateralidad normalizadas producen `aligned`, `probable_alignment`,
  `ambiguous_alignment`, `rehab_without_injury` o `unmatchable_zone`. Las
  lesiones Hyrox sin episodio compatible aparecen aparte como
  `injury_without_rehab`. No crea enlaces ni declara que ambos modelos
  representen necesariamente la misma lesión.
- Cada episodio incorpora como evidencia su última sesión hasta la fecha de
  corte y distingue respuesta a 24 horas presente, ausente o no disponible.
  Los episodios futuros y las lesiones ya resueltas quedan fuera del corte.
- `IntervencionMolestiaGym` aparece solo como inventario por estado. No se usa
  para completar ni corregir ninguna de las dos autoridades.

```bash
python manage.py auditar_autoridad_lesion_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```

# Fase 6.6 — observación Rehab dentro del snapshot físico

- `physical_snapshot.signals.active_rehab` captura los episodios Rehab activos
  conocidos en el momento de decidir, junto con su fase y la última observación
  diaria o sesión cuya fecha no sea futura respecto al corte.
- El contrato es factual y mínimo: no incorpora notas, texto clínico ni reglas
  médicas. Cada episodio declara
  `executive_capacity.can_derive_restrictions=false`, porque Rehab todavía no
  dispone de un contrato de riesgo Gym capaz de sustituir a `UserInjury`.
- La capability `active_rehab_v1` permite distinguir snapshots nuevos de los
  V1 anteriores. Una autoridad motor vigente puede promocionarse mediante una
  sucesora inmutable con `contract_upgrade=active_rehab_observation_v1`, sin
  cambiar `decision_id`, fingerprint, postura ni causa. Correcciones y
  reversiones manuales nunca se actualizan automáticamente. Esta promoción es
  exclusivamente explícita mediante `materializar_snapshot_fisico_gym
  --apply`: las lecturas normales del resolver y del dashboard reutilizan la
  versión vigente y nunca crean una sucesora por faltar esta capability.
- La señal es deliberadamente no ejecutiva: con o sin Rehab observado, el
  estado, contexto, sesión y postura de la decisión son idénticos. Tampoco crea
  o modifica episodios, lesiones, intervenciones ni sesiones Rehab.
- La auditoría de lesión conserva `no_injury_in_snapshot` como clasificación de
  autoridad y añade únicamente un inventario agregado
  `rehab_observation_inventory` para evidenciar episodios observados sin
  atribuirles poder de bloqueo.

Para inspeccionar o materializar la capability en la autoridad motor de hoy:

```bash
python manage.py materializar_snapshot_fisico_gym \
  --cliente <ID> \
  --settings=gymproject.settings
```

# Fase 6.7A — contrato Rehab→Gym y auditoría pasiva

- `ContratoRiesgoGymFaseRehab` publica, por fase y versión, un contrato tipado
  e inmutable: tags de riesgo, umbral de dolor, frescura, acción, alcance y
  acción explícita ante bandera roja. Solo puede haber uno activo por fase.
- Una actualización se publica como sucesora; la versión anterior se conserva
  inmutable y pasa a inactiva. El contrato inicial de la Fase 1 de tendinopatía
  rotuliana propone el tag curado `carga_dominante_rodilla`.
- El seed es seguro por defecto y solo escribe con `--apply`:

```bash
python manage.py sembrar_contrato_riesgo_gym_rehab --settings=gymproject.settings
python manage.py sembrar_contrato_riesgo_gym_rehab --apply --settings=gymproject.settings
```

- `auditar_cobertura_riesgo_gym_rehab` emite JSONL determinista y de solo
  lectura. Usa un catálogo versionado de nombres exactos normalizados; informa
  coincidencias, ausencias, ambigüedades, cobertura preexistente y episodios
  que cumplirían el caso conceptual de `sostener` (dolor >= 5 y edad <= 3 días).
  No deduce categorías desde texto libre ni modifica `EjercicioBase`.
- La ejecución permanece desactivada (`execution_enabled=false`): esta fase no
  cambia decisiones, sesiones, snapshots, UI, JOI ni la autoridad de lesión.

```bash
python manage.py auditar_cobertura_riesgo_gym_rehab \
  --today 2026-08-22 \
  --settings=gymproject.settings
```

# Fase 6.7B — etiquetado curado y reversible del catálogo Gym

- El catálogo V2 contiene exclusivamente los ocho nombres confirmados en
  producción: sentadillas trasera, frontal, Hack y búlgara; prensa de piernas;
  zancadas con mancuernas; extensiones de cuádriceps en máquina; y Sissy Squat.
- La selección usa solo nombre exacto normalizado (mayúsculas, acentos y espacios).
  Nunca infiere riesgo por grupo muscular, coincidencias parciales ni texto libre.
- Abducción de cadera, Hip Thrust, patada de glúteo y peso muerto sumo quedan
  explícitamente fuera de este catálogo.
- El comando es `dry-run` por defecto. `--apply` añade
  `carga_dominante_rodilla` sin alterar otros tags; `--revert` elimina solamente
  ese tag de los mismos ocho ejercicios. Ambas operaciones son idempotentes,
  transaccionales y mutuamente exclusivas.
- Si falta cualquier nombre o una normalización produce más de un candidato, la
  operación aborta completa sin escrituras. La salida JSONL conserva evidencia de
  ID, nombre y estado `before`/`after` para cada candidato.
- Esta fase sigue siendo preparatoria: `execution_enabled=false`. No modifica
  decisiones, sesiones, UI, JOI ni la autoridad vigente de lesiones.

```bash
# Inspección sin escrituras
python manage.py etiquetar_catalogo_riesgo_gym_rehab \
  --settings=gymproject.settings

# Aplicación curada
python manage.py etiquetar_catalogo_riesgo_gym_rehab \
  --apply \
  --settings=gymproject.settings

# Reversión segura
python manage.py etiquetar_catalogo_riesgo_gym_rehab \
  --revert \
  --settings=gymproject.settings
```

# Fase 6.7C — motor selectivo Rehab post-plan y preview

- Cada contrato incorpora `execution_enabled`, desactivado por defecto y preservado
  por publicaciones sucesoras. Solo contratos activos y habilitados pueden derivar
  un freno desde un registro diario fresco, sin bandera roja y sobre el umbral.
- El snapshot físico embebe el contrato exacto y su evaluación ejecutiva. El overlay
  final consume exclusivamente ese snapshot, después del plan dinámico, y limita solo
  ejercicios cuyos `risk_tags` intersectan con el contrato. Nunca eleva carga ni
  revierte una sustitución protectora.
- El techo es la última ejecución efectiva anterior identificable. Sin baseline se
  conserva el plan y se declara evidencia insuficiente.
- La postura Gym global no cambia; una sesión puede declarar postura local `mixed`.
  No se activa ninguna superficie de UI, JOI ni ejecución de producción.
- El preview es JSONL y de solo lectura:

```bash
python manage.py previsualizar_freno_rehab_gym --cliente <ID> --fecha YYYY-MM-DD \
  --settings=gymproject.settings
```
# Fase 7A — autoridad pasiva de campaña Hyrox

Hyrox queda encapsulado por `ContratoCampanaHyrox`, un contrato append-only con
estados `inactiva`, `exploracion`, `activa` y `finalizada`. En este corte no se
conecta el contrato a vistas, signals, tareas, dashboard ni al motor: por tanto,
no cambia ninguna sesión existente. Sin contrato, la autoridad resuelve como
`inactiva_legacy`.

La carga física, Strava y la seguridad permanecen siempre permitidas. Generar
planes o programar sesiones solo se autoriza en estado `activa`, que exige un
objetivo Hyrox futuro del mismo cliente y un bloque Gym activo o pausado. Gym
continúa siendo autoridad soberana (`competir_con_gym=false`).

`configurar_campana_hyrox` es dry-run por defecto y `--apply` solo añade una
versión del contrato. La huella representa la semántica dentro de su transición
(incluye el predecesor, no el número de versión): repetir la configuración
vigente la reutiliza, pero volver a una configuración histórica crea sucesora.
Las transiciones están cerradas y `finalizada` es terminal; el actor aprobado
debe ser el usuario propietario del cliente. `auditar_campana_hyrox` es JSONL y solo lectura; publica
un inventario estático explícito de superficies legacy (`views`, `signals`,
`services`, `training_engine`, métodos de `HyroxObjective`, `decision_service`,
`pulso_service` y `urls`) y detecta objetivos
activos sin campaña, multiplicidad, objetivos vencidos, sesiones futuras sin
campaña activa y divergencia del snapshot. La conexión ejecutiva de esas
superficies queda para 7B.
# Fase 7B1 — Gate de prescripción Hyrox

- Toda creación, regeneración o autoajuste de sesiones futuras pasa por
  `hyrox.campaign_authority.exigir_prescripcion`.
- Solo una campaña `activa` y válida permite prescribir. Los estados
  `inactiva`, `exploracion` y `finalizada` conservan intactas las sesiones
  legacy; no se borran ni migran.
- Editar el objetivo sigue siendo posible sin campaña activa, pero se guarda
  sin regenerar el plan y se informa al usuario.
- Registrar/completar sesiones existentes, Strava, carga física y seguridad
  permanecen disponibles. Registrar una lesión no autoriza por sí mismo a
  reescribir un plan Hyrox inactivo.
- El dashboard no autoajusta y devuelve una decisión Hyrox neutra cuando no
  existe campaña activa. Gym conserva la autoridad soberana.

# Fase 7B2-A — Separación entre hechos y efectos de campaña

- Completar una sesión y persistir sus actividades, carga unificada, TRIMP o
  importación Strava/manual son hechos y siguen disponibles con la campaña
  inactiva.
- Escalar volumen, adaptar sesiones futuras, actualizar RM o ritmos, recalibrar
  el 5K, abrir un deload y crear correctivos requieren una campaña `activa`
  cuyo objetivo sea exactamente el objetivo contractual vigente.
- El guardado de sesión es el único orquestador de la adaptación continua. El
  signal factual ya no repite el ajuste, de modo que una sesión activa adapta
  el plan una sola vez.
- La bitácora y el puente Gym → Hyrox no pueden alterar fatiga futura ni RM del
  objetivo sin esa autoridad exacta. En estado inactivo realizan un no-op
  silencioso sobre la prescripción, sin impedir el registro de evidencia.
- Las restricciones de lesión y seguridad no quedan subordinadas a la campaña.
  Las superficies JOI y la presentación de autoridad en dashboards permanecen
  pendientes para 7B2-B/7B2-C.

# Fase 7B2-B — Voz JOI subordinada a campaña Hyrox

- Los triggers específicamente Hyrox pasan por una defensa central en
  `generar_mensaje_joi`: sin campaña activa y objetivo contractual exacto no se
  llama al modelo ni se persiste `MensajeJOI`.
- Esta defensa usa una allowlist explícita. Los triggers generales, Gym,
  decisiones del plan, lesión y carga conservan su voz aunque su evidencia
  incluya actividad Hyrox.
- Las tareas de cuenta regresiva y ausencia recorren exclusivamente la campaña
  activa vigente; dejan de inferir autoridad desde un `HyroxObjective` legacy.
- El contexto Hyrox desaparece cuando la campaña está inactiva y el context
  processor no muestra mensajes Hyrox históricos, pero tampoco los elimina.
- El signal post-sesión conserva carga y readiness como hechos. Solo verbaliza
  la sesión cuando la campaña autoriza JOI. No se genera ningún mensaje del tipo
  «Hyrox apagado».
- El dashboard continúa pendiente de 7B2-C.

# Fase 7B2-C — Dashboard Hyrox como proyección de Gym

- `/hyrox/dashboard/` deja de invocar `_crear_hyrox_decision` como autoridad.
  La identidad ejecutiva procede de `GymDecisionVersion` y el payload declara
  `source=gym_decision_version`, `hyrox_es_proyeccion=true`, `decision_id` y
  `gym_decision_version`.
- Con campaña activa se usa `resolver_autoridad_diaria_gym`, el servicio
  canónico. La proyección Hyrox hereda postura y restricciones; lesión,
  readiness o carga solo pueden aumentar protección, nunca elevar `proteger` o
  `sostener` a `empujar`.
- Sin campaña activa, el dashboard solo lee una versión Gym ya materializada.
  No crea autoridad, readiness ni overrides, ofrece `Explorar Hyrox` y mantiene
  `puede_ejecutar_plan=false`.
- `_crear_hyrox_decision` se conserva temporalmente para consumidores legacy,
  pero el dashboard Hyrox ya no depende de ella.

# Fase 7B3 — Estado visual de archivo Hyrox

- El template recibe `campana_hyrox_activa` de forma explícita; no deduce
  autoridad de la existencia de un objetivo Hyrox legacy.
- Una campaña inactiva presenta `HYROX EN PAUSA` como archivo de solo lectura.
  Explica que Gym dirige el entrenamiento y que datos, conexiones e historial
  permanecen conservados.
- En pausa no se renderizan Race Bib, Race Command, readiness competitivo,
  planes futuros, estaciones a reforzar, macrociclo, hitos ni mensajes de lo
  que el plan aprenderá o reajustará. Tampoco existe CTA hacia la ejecución de
  una sesión.
- Se mantienen accesos seguros a Panel, Strava, lesión/recuperación y guía
  técnica, además de un resumen factual de las sesiones históricas.
- La campaña activa conserva el dashboard competitivo existente. El cambio es
  exclusivamente de proyección visual y no añade migraciones ni mutaciones GET.
- El encabezado solo declara `LIVE` cuando la campaña está activa. En archivo
  usa un indicador neutro `ARCHIVO`, sin pulso. La disponibilidad de Strava se
  expresa como `STRAVA DISPONIBLE`; no se afirma conexión sin evidencia fiable.

# Fase 8.0-A — Registro epistemológico de solo lectura

- `core.services.epistemic_registry` proyecta memoria legacy al contrato
  determinista `EpistemicRecordV1` (`schema_version=1`). No crea modelos, no
  corrige registros, no usa IA, caché ni backfill y no contiene gates de
  ejecución.
- Los adaptadores cubren preferencias Gym, decisiones y traces con evaluación,
  perfiles de adaptación, ManualDavid, NarrativaActiva, RecuerdoEmocional,
  cierres versionados y el puente corporal estructurado `SeguimientoVires`.
- La procedencia usa referencias `app.model:pk`. Los textos libres de Diario,
  recuerdos y narrativa no salen en la auditoría; una contradicción textual se
  representa mediante huella SHA-256 y nunca se elige un ganador.
- Los campos que el esquema legacy no puede sostener se enumeran en
  `missing_fields`. En particular, no se inventan ventanas, evidencias,
  consentimiento ni supersesión. El consentimiento de
  `PreferenciaPlanAprendida` se marca `contract_asserted` porque es una
  precondición documentada de creación; una negación explícita en metadata sí
  produce hallazgo.
- Un `GymDecisionLog` con `resultado=validada` sigue siendo conocimiento
  provisional: el resultado individual solo lo convierte en candidato. La
  consolidación exige una regla explícita y evaluaciones independientes, que el
  modelo legacy no demuestra y quedan declaradas en `missing_fields`.
- En `ManualDavid`, `activa=True` significa inclusión operativa y es compatible
  con los estados `activa`, `cuestionada` y `debilitada`; `activa=False` puede
  representar poda legítima. Solo `estado=descartada` junto con `activa=True`
  produce `manual_descartada_aun_incluida`.
- La revisión temporal de hipótesis es semántica y reproducible. Una corrección
  `feedback_error` es persistente; no caduca como un patrón automático. Para
  `patron_detectado`, `ultima_evidencia=NULL` significa revisión contextual
  pendiente: hasta 30 días se clasifica `pendiente_revision` y después
  `revision_vencida`. Una revisión antigua vuelve a solicitar revisión y conserva
  la distinción `activa`/`cuestionada`, sin declarar falsa la hipótesis. El corte
  temporal es `--hasta`; sin él se deriva de las fechas del propio lote, nunca
  del reloj del proceso.
- Fase 8.0-C añade `planificar_revision_memoria --cliente --as-of --limit`, una
  cola JSONL estrictamente read-only. Solo considera entradas activas de
  `ManualDavid` originadas como patrón y de tipo patrón, hipótesis o
  contradicción; excluye correcciones `feedback_error`, descartadas, podadas y
  revisiones recientes. Ordena primero revisiones vencidas cuestionadas,
  después las demás vencidas y finalmente las pendientes, conservando orden
  temporal y PK.
- La cola no emite `entrada`, `notas_revision` ni `hipotesis_contraria`. Solo
  publica indicadores booleanos y una huella SHA-256 que sí incorpora esos
  contenidos internamente, junto con los campos de control, para detectar
  cambios sin revelar memoria privada. No ofrece `--apply`, no usa IA ni caché
  y no escribe en base de datos.
- Fase 8.0-D añade `preparar_lote_revision_memoria --cliente --as-of --item
  id:fingerprint` para preparar, sin ejecutar, un lote explícito de 1 a 8
  elementos. Cada referencia se vuelve a validar contra la cola actual; se
  rechazan duplicados, elementos no elegibles y huellas obsoletas. El manifiesto
  JSONL es público, mantiene `execution_enabled=false` y nunca incorpora textos
  privados. La carga privada existe como función interna separada y no participa
  en la salida del comando.
- El validador puro de una futura propuesta exige cobertura exacta 1:1, IDs y
  fingerprints del manifiesto, motivo de 1 a 240 caracteres y solo las acciones
  `mantener`, `debilitar`, `cuestionar` o `descartar`. El delta es obligatorio y
  queda entre 0 y +0.05 para mantener, exactamente -0.10 para debilitar y -0.20
  para cuestionar; descartar no admite delta. Esta fase no llama a ningún
  proveedor, no persiste propuestas, no cambia modelos y no ofrece `--apply`.
- Fase 8.0-E lleva la supervisión read-only a `/joi/habitacion/` sin convertir
  la presencia de JOI en un feed. Después de «Por qué este estado» aparece, solo
  cuando existe cola, un único `<details>` cerrado con una memoria candidata,
  clasificación humana, estado, antigüedad y ordinal. La navegación anterior/
  siguiente es GET dentro de la propia habitación; una ID inválida o ajena cae
  silenciosamente en la primera candidata propia.
- `joi.services_memoria_habitacion` reutiliza la cola 8.0-C, carga exclusivamente
  la `entrada` seleccionada del usuario y no expone notas ni contradicciones. No
  usa IA o caché, no escribe `ManualDavid` y no ofrece acciones POST, propuestas
  ni aplicación. La nota visual es neutral y no simula una nueva voz de JOI.
- La habitación traduce los estados internos a lenguaje de interfaz (`En uso`,
  `Cuestionada`, `Con reservas`; fallback `En revisión`) y limita visualmente
  textos extensos mediante ajuste de línea y scroll local, evitando que una sola
  memoria domine la presencia en pantallas móviles.
- Fase 8.0-F1 introduce `RevisionManualDavidOperacion`, ledger humano reversible
  y MySQL-safe para `confirmar`, `cuestionar`, `descartar`, `posponer` y
  `deshacer`. Cada operación conserva actor, clave idempotente, fingerprint
  esperado y snapshots semánticos antes/después; no almacena una copia nueva de
  notas privadas ni sobrescribe `notas_revision`.
- `joi.services_revision_memoria` bloquea la memoria y revalida ownership,
  elegibilidad y fingerprint dentro de una transacción. Confirmar suma hasta
  +0.05 y registra evidencia; cuestionar resta 0.20 y aplaza 14 días; descartar
  desactiva con confianza cero; posponer solo crea el recibo. Deshacer restaura
  el snapshot previo únicamente si no hubo cambios posteriores. Repetir la misma
  clave y payload devuelve el recibo; una colisión diferente se rechaza.
- La cola omite cuestionamientos y aplazamientos humanos hasta el día 14 exacto
  y vuelve a mostrarlos entonces; una reversión cancela ese efecto. Una
  confirmación vigente aporta procedencia y consentimiento `user_confirmed` al
  registro epistemológico, sin promoverlo a conocimiento consolidado.
- El revisor legacy `revisar_manual_david` queda subordinado a la cola: excluye
  correcciones `feedback_error`, evidencia reciente, decisiones humanas
  aplazadas y elementos aún pendientes de primera revisión. La propuesta 8.0-D
  conserva su vocabulario de proveedor; la traducción futura es explícita
  `mantener → confirmar`, mientras `debilitar` no es acción humana del ledger.
- `auditar_memoria_epistemica --cliente --desde --hasta --limit` emite JSONL en
  orden estable y termina con un resumen. Es estrictamente de solo lectura y no
  ofrece `--apply`.
- Los hallazgos se basan solo en campos y relaciones estructuradas. Se omiten
  `narrativa_usada_como_fuente` y `texto_diario_cruzado` cuando no hay una
  relación demostrable; no se realizan coincidencias heurísticas de texto.
- Fase 8.0-F2 convierte la única memoria abierta de `/joi/habitacion/` en una
  supervisión humana accionable, sin añadir feed ni una voz JOI simulada. Las
  decisiones visibles son exactamente «Sigue siendo cierto», «No estoy
  seguro», «Ya no encaja» y «Ahora no»; usan formularios POST con CSRF y no
  requieren JavaScript.
- Los endpoints derivan siempre `Cliente` del usuario autenticado y delegan toda
  mutación en el servicio transaccional F1. Validan UUID y fingerprint, aplican
  Post/Redirect/Get y traducen ownership, stale, cooldown o payload inválido a
  feedback neutral que no revela si una memoria u operación ajena existe.
- Tras una operación correcta se ofrece una sola reversión efímera, ligada en
  sesión al recibo propio recién creado. No se expone historial de operaciones;
  un deshacer ajeno, doble u obsoleto se rechaza de forma neutral. Confirmar y
  descartar sacan la memoria de la cola; cuestionar y posponer respetan el
  aplazamiento de 14 días definido por F1.
- Fase 8.0-G centraliza en `joi.services_manual_authority` qué memoria puede
  alimentar contexto, prompts y narrativa. La selección excluye siempre
  `activa=False` y `estado=descartada`, resuelve la última operación humana
  efectiva no revertida en una segunda consulta única y evita N+1.
- La prioridad determinista es: corrección explícita `feedback_error`,
  confirmación humana, datos/preferencias/límites en uso, hipótesis automáticas
  e hipótesis inciertas. Una confirmación se etiqueta como procedencia humana y
  gana a patrones automáticos, pero el prompt declara que no es verdad absoluta
  ni conocimiento consolidado. Las cuestionadas solo aparecen como hipótesis
  explícitamente inciertas y nunca como hecho o instrucción.
- `cuestionar` y `posponer` silencian esa memoria para generación durante los
  primeros 13 días; el día 14 reaparece con su semántica correspondiente. Una
  reversión elimina el efecto de la operación y recupera exactamente la
  autoridad derivada del estado anterior. Las correcciones explícitas conservan
  máxima prioridad.
- `construir_contexto` incorpora únicamente provenance estructurada mínima
  (`manual_id`, autoridad, fuente y, cuando existe, ID de operación). No incluye
  texto, snapshots, motivo ni notas. `_bloque_manual`, actualización narrativa,
  narrativa de cierre de bloque, razón legible y poda mensual reutilizan la
  política; no se crean triggers, mensajes, apariciones ni llamadas IA nuevas.
- Gap previo no abordado en esta fase: la rama Paradoja B de
  `_prompt_apertura_manana` intenta leer `cliente.user` fuera de ámbito y atrapa
  silenciosamente el error. Se mantiene sin cambios para no mezclar un bugfix de
  apertura con el contrato de autoridad 8.0-G.
- Fase 8.0-H retira la segunda vía humana de mutación que sobrevivía en
  `/joi/manual/`. El manual conserva su función de inventario informativo y
  enlaza a la Habitación, pero ya no ofrece descarte directo, JavaScript de
  escritura ni endpoint propio.
- La única revisión humana permanece en `/joi/habitacion/`, subordinada a la
  elegibilidad 8.0-C y al ledger F1: fingerprint, UUID idempotente, PRG, recibo
  y deshacer efímero. Así, correcciones estables `feedback_error`, datos y otras
  entradas no elegibles pueden seguir visibles en el inventario sin inventar
  una decisión ni forzar su entrada en la cola.
- La URL legacy `/joi/manual/<id>/desactivar/` deja de resolver para cualquier
  método o propietario. No se migra ni reinterpreta ninguna poda histórica, no
  se añade voz JOI, trigger o llamada a IA y la Paradoja B continúa fuera de
  alcance.

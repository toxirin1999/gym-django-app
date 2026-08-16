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

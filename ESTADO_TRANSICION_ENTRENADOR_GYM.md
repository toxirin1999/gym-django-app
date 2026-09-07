# Estado canónico de la transición al entrenador Gym

**Fecha de corte:** 7 de septiembre de 2026.
**Ámbito:** estado editorial contrastado con el repositorio local y con tres
recibos de consultas de solo lectura ejecutadas en PythonAnywhere.
**Autoridad de producto:** [PRODUCTO_ENTRENADOR_GYM.md](PRODUCTO_ENTRENADOR_GYM.md).  
**Historia técnica detallada:** [TRANSICION_ENTRENADOR_GYM.md](TRANSICION_ENTRENADOR_GYM.md).

Este documento es la lista de estado vigente. Resume qué existe en código, qué
ha recibido alguna comprobación real comunicada durante la transición y qué se
ha aplazado de forma deliberada. No demuestra por sí mismo que una migración se
haya desplegado, que una tarea esté programada o que el comportamiento de
PythonAnywhere coincida con el entorno local.

## Auditoría de corte — 7 de septiembre de 2026

Este corte distingue dos fuentes. La comprobación **local y no productiva** tomó
como origen `db_local.sqlite3`, cuya fecha de modificación es
**18 de agosto de 2026**, y trabajó sobre una copia temporal migrada para no
alterar la base original. En ella se localizó `Cliente 2` (`david`). Además se
recibió la salida de tres comandos de solo lectura ejecutados en
**PythonAnywhere** para `--cliente 2` y la ventana
**31/08/2026–06/09/2026**. Un segundo recibo productivo confirmó mediante
consulta ORM que `Cliente 2` corresponde al usuario `david` y que la consulta
por cliente y semana resuelve un único contrato, con id `3`. El tercer recibo
contrastó la evaluación persistida, su snapshot y la fase Helms en solo lectura.

| Evidencia auditada | Resultado local | Recibo productivo PythonAnywhere |
|---|---|---|
| Ventana y autoridad diaria | **0** días con datos o decisión | **7** días con datos y **7** con decisión; **19** versiones de decisión |
| Sesiones Gym | **0** | **5** contractualmente completadas, **2** reubicadas y **0** pendientes, omitidas, saltadas o canceladas; solo **3/5** tienen `EntrenoRealizado` explícito |
| Recuperación y carga externa | **0** check-ins | **7** check-ins y una actividad Strava de bicicleta de **300,6 UA** |
| Cierre semanal | Sin evaluación | Evaluación id `2`, contrato id `3`, aceptada por `david` (usuario id `3`) el `2026-09-07T04:23:34.798934Z`; cumplimiento `objetivo` |
| Contrato semanal y bloque | Sin evidencia | `Cliente 2` = `david`; contrato id `3`, **5 objetivo / 3 mínimo**, cinco sesiones; bloque id `1` activo del **24/08/2026** al **20/09/2026** |
| Snapshot y fase Helms | Sin evidencia | Snapshot persistido = recalculado; SHA-256 iguales: `423e53b1cae27dbdb00ed516c50940c44dd4936bed419f1076204ad454b83628`. **Fuerza — Avanzada**, objetivo `fuerza`, fase `11`, **24/08–20/09**, semana **2/4**, fuente `PlanificadorHelms.generar_plan_anual`, sin limitaciones |
| Auditor JOI | `contract_ok`, pero **0 evaluados** | Corte real `2026-09-07T17:11:13+00:00`: `contract_ok: false`; **33** evaluados, **32** pendientes, **1** publicado, backlog **32**, **0** procesando y **26** `pending_over_48h`; los **6** `future_occurred_at` anteriores desaparecen |

Los recibos productivos demuestran actividad real y cumplimiento contractual
de la semana: **5/5** sesiones completadas, **2** reubicadas y ninguna
pendiente, omitida, saltada o cancelada. Solo **3/5** sesiones tienen enlace
explícito a `EntrenoRealizado`: ids `356`, `360` y `357`; las sesiones
programadas `38` y `39` conservan ese enlace a `null`. Por ello las métricas
del snapshot cubren las tres enlazadas: **18 040 kg**, **123 min**, energía
media **7,0** y RPE medio **8,03**, con cobertura **3/3** para esas métricas y
**3/5** para enlaces. Separadamente, `auditar_semana` reportó totales globales
de **36 870 kg** y **1728 UA**; esos totales no prueban cobertura completa de
cinco entrenos enlazados ni deben atribuirse así.

La evaluación id `2` del contrato id `3` está aceptada por `david` (usuario id
`3`) desde `2026-09-07T04:23:34.798934Z`. Su snapshot persistido coincide con
el recalculado y ambos producen el SHA-256
`423e53b1cae27dbdb00ed516c50940c44dd4936bed419f1076204ad454b83628`.
La fase Helms también queda confirmada: **Fuerza — Avanzada**, objetivo
`fuerza`, fase `11`, del **24/08/2026** al **20/09/2026**, semana **2 de 4**,
fuente `PlanificadorHelms.generar_plan_anual` y sin limitaciones. La consulta
con `get` devolvió el contrato id `3` sin multiplicidad para ese cliente y
semana. La idempotencia de la materialización sigue sin demostrarse: el
`dry-run` propuso cinco fechas, pero no se repitió. El inventario resultó
correcto y declaró `solo_lectura: true`, pero no prueba que las migraciones
estén aplicadas en producción. También deja hallazgos que no deben
inferirse ni repararse automáticamente: el `decision_id` de las versiones 1 y
3 del **05/09** está repetido; la evidencia Strava `WeightTraining` del
**05/09** permanece `pending`; ningún check-in trae HRV o FC en reposo y tres
no traen calidad de sueño. Las ausencias se conservan como ausencias.

El preflight local detectó **12 migraciones pendientes** en esa base. El smoke
suite ejecutó **424 tests**, con **4 fallos y 1 skipped**; por tanto, este corte
no permite declarar el entorno verde. Durante la auditoría ya existían cambios
locales en `clientes/views.py` y
`clientes/tests_aviso_revisiones_gym.py`; no forman parte de esta actualización
ni fueron modificados para obtener estas conclusiones.

## Leyenda

| Estado | Significado |
|---|---|
| **Terminado** | Contrato y código presentes, con pruebas automatizadas. No significa despliegue productivo salvo evidencia explícita separada. |
| **En observación** | Implementación disponible, pero necesita uso real, una ventana temporal o validación operativa adicional antes de cerrar producto. |
| **Pospuesto conscientemente** | Se conserva la capacidad o la historia, pero no se continúa ahora por una decisión explícita de producto. |
| **Pendiente** | Falta una capacidad necesaria o un cierre verificable. No equivale a un bug urgente. |

## Decisiones vigentes

- **Gym es el eje principal y permanente.** Helms sigue aportando la
  periodización; la autoridad Gym contractual decide qué se ejecuta y cómo se
  adapta.
- **Hyrox está subordinado a Gym.** Puede conservar campaña, dashboard,
  historial, Strava y registro puntual, pero no debe competir por la decisión
  soberana del día.
- **Rehab queda pospuesto mientras David está recuperado.** Se conserva el
  contrato y la instrumentación construida; no se activa automáticamente un
  freno clínico sin necesidad real y validación nueva.
- **Gamificación queda postergada.** Se mantiene su integridad causal e
  histórica, pero no dirige el próximo ciclo de producto ni la portada.
- **Nutrición está fuera de uso actual.** No forma parte de esta transición y
  no se reabre hasta que exista una necesidad de uso concreta.
- **Diario conserva autonomía personal.** Solo comparte señales deportivas
  estructuradas, explícitas y revocables.
- **JOI concentra su presencia en la Habitación.** Los módulos aportan hechos;
  no crean voces paralelas ni convierten propuestas en resultados.

## Matriz de fases 0–12

### Fases 0–4 — núcleo Gym

| Fase / subárea | Estado | Evidencia en el repositorio | Validación que aún importa |
|---|---|---|---|
| **0. Visión e inventario** | **Terminado** | Producto definido en [PRODUCTO_ENTRENADOR_GYM.md](PRODUCTO_ENTRENADOR_GYM.md); contrato canónico y runbook en [docs/fase0_inventario_vivo.md](docs/fase0_inventario_vivo.md); auditor `auditar_inventario_transicion_gym` con módulos, rutas, comandos, procesos, dependencias y autoridad validados. | Mantener el catálogo y sus referencias resolubles en cada cambio de superficie. |
| **1. Caracterización Gym** | **Terminado** | Rutas causales y pruebas de sesión programada en [`tests_sesion_programada.py`](entrenos/tests_sesion_programada.py), además de suites de progresión y cierre. | Las rutas legacy siguen siendo compatibilidad, no núcleo. |
| **2. Autoridad diaria soberana** | **En observación** | [`autoridad_diaria_gym_service.py`](entrenos/services/autoridad_diaria_gym_service.py), `GymDecisionVersion` en [`models.py`](entrenos/models.py), tests de autoridad, portada y briefing. | Confirmar durante varias semanas que portada, briefing, sesión y cierre mantienen la misma identidad ante correcciones reales. |
| **3A. Estrategia semanal 5/3** | **Terminado** | `EstrategiaSemanalGym`, `ContratoSemanalGym` y `SesionProgramada`; [`estrategia_semanal_gym_service.py`](entrenos/services/estrategia_semanal_gym_service.py); comandos de configuración y materialización. | La política aprobada es 5 objetivo / 3 mínimo; no reinterpretar `dias_disponibles` como autoridad histórica. |
| **3B. Bloque longitudinal** | **Terminado** | `ContratoBloqueGym`; [`contrato_bloque_gym_service.py`](entrenos/services/contrato_bloque_gym_service.py); comandos `configurar_bloque_gym` y `activar_bloque_gym`. | No confundir objetivo contractual del bloque con la fase anual Helms. |
| **3C. Cierre de bloque** | **En observación** | `EvaluacionBloqueGym`; comandos `cerrar_bloque_gym` y `responder_evaluacion_bloque_gym`; pruebas del cierre longitudinal. | No puede validarse realmente hasta completar y revisar las semanas del bloque. |
| **3D. Apertura semanal** | **En observación** | [`apertura_semanal_gym_service.py`](entrenos/services/apertura_semanal_gym_service.py) y `preparar_semana_gym`, dry-run por defecto e idempotente. | Verificar cada domingo/lunes que abre una sola semana, sin duplicar sesiones ni alterar la fase Helms. |
| **3D. Operación semanal unificada** | **Implementado; pendiente de observación** | [`ciclo_semanal_gym_service.py`](entrenos/services/ciclo_semanal_gym_service.py) y `operar_semana_gym`: dry-run por defecto, `--apply` explícito; domingo abre, lunes cierra y martes–sábado no opera. | La evaluación queda pendiente y nunca se acepta automáticamente. La repetición preserva semanas/evaluaciones existentes, respuestas y timestamps. Para programarlo, usar una única tarea externa diaria. |
| **3E. Activación colaborativa** | **Terminado** | [`forms_bloque_gym.py`](clientes/forms_bloque_gym.py), [`tests_bloque_gym_colaborativo.py`](clientes/tests_bloque_gym_colaborativo.py) y Centro de decisiones. | Las acciones estratégicas siguen requiriendo aprobación humana. |
| **4. Ciclos de adaptación Gym** | **En observación** | Ciclos persistidos y pruebas para variante, molestia, deload, versión esencial, técnica, tope, fallo, RPE, progresión, perfil causal, cierre semanal, molestia reciente y distribución contractual. | Código amplio no equivale a aprendizaje demostrado: observar resultados reales y cobertura por ciclo. |
| **4. Resumen semanal semántico** | **Terminado** | [`analisis_semanal_service.py`](entrenos/services/analisis_semanal_service.py), [`evaluacion_semanal_gym_service.py`](entrenos/services/evaluacion_semanal_gym_service.py) y sus tests. | La evidencia real confirma que dos sesiones reubicadas conservan cumplimiento objetivo 5/5; deben nombrarse como adaptaciones y no como “sin adaptaciones”. |

### Fases 5–7 — evidencia física, seguridad y campañas

| Fase / subárea | Estado | Evidencia en el repositorio | Validación que aún importa |
|---|---|---|---|
| **5.1–5.7 Snapshot y consumo físico** | **En observación** | Snapshot canónico en `core`, [`auditoria_snapshot_fisico_service.py`](entrenos/services/auditoria_snapshot_fisico_service.py), `materializar_snapshot_fisico_gym`, consumo por autoridad y JOI. | Auditar autoridades nuevas con datos productivos; los snapshots legacy ausentes son historia, no prueba de fallo actual. |
| **5.8–5.14 Identidad Strava/Gym/hub** | **En observación** | Comandos de auditoría, clasificación, vínculo legacy y reconciliación de fechas/métricas; vínculos explícitos en los modelos. | Revisar solo casos inequívocos con datos reales; no fusionar dos entrenamientos legítimos por fecha o parecido. |
| **5. Carga externa y recuperación** | **En observación** | Fecha efectiva, carga unificada, check-in, HRV, FC en reposo y sueño consumidos por la autoridad física. | Calibrar la respuesta personal a fútbol y otras cargas con más historial real. |
| **6.1–6.4 Supervisión causal** | **Terminado** | [`evaluacion_supervision_gym_service.py`](entrenos/services/evaluacion_supervision_gym_service.py), sello de `GymDecisionVersion`, comando `cerrar_supervision_gym` y tests de identidad ejecutiva. | Mantener fallback legacy sin atribuirle causalidad inferida. |
| **6.5–6.7B Autoridad y catálogo Rehab** | **Terminado** | Auditoría de lesión, `ContratoRiesgoGymFaseRehab` en [`rehab/models.py`](rehab/models.py), servicio de contrato, seed, auditoría y etiquetado reversible del catálogo. | La existencia del contrato no significa que el freno esté activado. |
| **6.7C Freno selectivo Rehab** | **Pospuesto conscientemente** | [`freno_rehab_gym_service.py`](entrenos/services/freno_rehab_gym_service.py) y `previsualizar_freno_rehab_gym`; `execution_enabled` permanece explícito. | David ha comunicado recuperación. Solo reabrir ante nueva necesidad, evidencia reciente y revisión de alcance local. |
| **7A–7B2 Campaña Hyrox subordinada** | **Terminado** | `ContratoCampanaHyrox` en [`hyrox/models.py`](hyrox/models.py), autoridad de campaña, comandos de configurar/auditar y pruebas 7A/7B. Gates separan hechos de efectos prescriptivos. | No asumir despliegue o campaña activa por la mera existencia del código. |
| **7B3 Proyección visual Hyrox** | **En observación** | Dashboard conserva modo campaña y estado en pausa sin autoridad paralela; pruebas de campaña y presentación. | Mantener el dashboard útil sin permitir que Hyrox sustituya la sesión Gym del día salvo acción explícita. |

### Fases 8–12 — memoria, voz, experiencia y archivo

| Fase / subárea | Estado | Evidencia en el repositorio | Validación que aún importa |
|---|---|---|---|
| **8.0A–D Registro y cola epistemológica** | **Terminado** | [`epistemic_registry.py`](core/services/epistemic_registry.py), cola/propuesta en `core.services`, comandos `auditar_memoria_epistemica`, `planificar_revision_memoria` y `preparar_lote_revision_memoria`. | Las clasificaciones legacy expresan límites; no convierten ausencia de vigencia en falsedad. |
| **8.0E–J Revisión humana y autoridad** | **En observación** | `RevisionManualDavidOperacion` en [`joi/models.py`](joi/models.py), [`services_revision_memoria.py`](joi/services_revision_memoria.py), [`services_manual_authority.py`](joi/services_manual_authority.py), UI y auditoría. | La auditoría comunicada quedó sin hallazgos, pero permanecía una cola amplia; validar utilidad y cadencia sin convertir JOI en feed. |
| **9A–9B Diario → Gym** | **Terminado** | `SenalEntrenamientoAutorizada`, productor `recuperacion`, contrato semántico, revocación y tests del puente. | No ampliar a energía, hábitos o texto íntimo sin fuente estructurada y consentimiento propio. |
| **10A Aplicaciones verbalizadas** | **Terminado** | Transición aplicada → evento estructurado, DTO allowlisted y pruebas de JOI. | JOI puede afirmar aplicación, no resultado. |
| **10B Outbox sin pérdidas** | **Terminado** | `EventoEntrenadorJOI` en [`joi/models.py`](joi/models.py) y [`tests_fase10b_outbox_entrenador.py`](joi/tests_fase10b_outbox_entrenador.py). | Observar backlog e intentos en operación real. |
| **10C Resultados evaluados** | **Terminado** | Productor explícito de evaluación y pruebas del cierre; aplicación y resultado conservan niveles distintos. | No promover una evaluación aislada a conocimiento estable. |
| **10D–E Apertura canónica** | **En observación** | Resolver compartido por web/tarea, reconciliación transaccional y `auditar_outbox_entrenador_joi`; pruebas 10D/10E. | Verificar en producción que no haya aperturas duplicadas, claims abandonados ni backlog envejecido. |
| **11A–C Portada y Centro contractuales** | **En observación** | [`proyeccion_bloque_gym_service.py`](entrenos/services/proyeccion_bloque_gym_service.py), [`portada_hoy_service.py`](clientes/portada_hoy_service.py), tests de portada, cierre semanal/bloque y UX móvil. | Continuar evaluación visual en móvil sin retirar paneles de memoria, sesiones, plan o vida. |
| **11D Trayectoria del plan** | **Implementado; pendiente de observación** | [`trayectoria_plan_service.py`](entrenos/services/trayectoria_plan_service.py), GET autoservicio y línea temporal año → bloque → semana → sesiones. Compone el plan anual Helms y autoridad contractual sin materializar ni evaluar. | Validar legibilidad móvil y coincidencia con producción durante el bloque activo. Los límites explícitos no se sustituyen por ceros. |
| **11E Evolución de rendimiento** | **Pendiente; bloqueada** | El usuario ha comunicado que producción conserva más de 200 sesiones históricas, útiles para tendencias y líneas base retrospectivas; este conteo no ha sido verificado desde el repositorio. La Semana 2 sí tiene evaluación contractual productiva revisada y aceptada. | No abrir diseño ni implementación hasta cerrar y aceptar todo el primer bloque contractual con evidencia productiva. Debe separar tendencia histórica de atribución causal por contratos nuevos. |
| **12.1 Auditoría de superficies** | **Terminado** | [`auditar_superficies_archivo.py`](entrenos/management/commands/auditar_superficies_archivo.py) y [docs/fase12_archive_audit.md](docs/fase12_archive_audit.md). | Repetir antes de retirar una nueva superficie. |
| **12.2 Gestión multi-cliente** | **Terminado** | Política staff/superusuario y pruebas de autorización. | La app sigue siendo de un solo usuario; conservar la superficie protegida, no convertirla en prioridad. |
| **12.3 Liftin** | **Pospuesto conscientemente** | UX archivada por flag, rutas reversibles e historia conservada. | No borrar modelos o sesiones históricas. |
| **12.4 Gamificación** | **Pospuesto conscientemente** | Finalizador causal idempotente y auditoría histórica disponibles. | No dedicar ahora trabajo de producto o UI; atender solo integridad o seguridad. |
| **12. Simplificación física** | **Pendiente** | Existe archivo reversible, no eliminación de modelos/signals/datos. | Decidir únicamente tras una ventana de desuso y nueva auditoría de dependencias. |
| **Nutrición** | **Pospuesto conscientemente** | El módulo queda fuera de esta matriz ejecutiva aunque su código e historia se conservan. | Reabrir con un caso de uso real, no para completar el inventario. |

## Lectura ejecutiva

La transición ya no está en fase de construir otro motor. El núcleo contractual
existe: autoridad diaria, estrategia 5/3, bloque, semana, decisiones locales,
evidencia física, memoria y comunicación. El trabajo inmediato es demostrar que
esas piezas sobreviven al uso continuado sin contradicciones.

Los pendientes reales son:

1. comprobar la idempotencia de la materialización sin escribir y observar la
   apertura y evaluación de semanas consecutivas;
2. confirmar la misma identidad causal desde portada hasta cierre, incluido el
   `decision_id` repetido del 05/09;
3. inventariar por ORM y en solo lectura los 33 eventos del outbox JOI, junto
   con el estado de sus mensajes y aperturas, y verificar Celery Beat, worker y
   logs; conservar el JSONL y un backup antes de cualquier mutación;
4. mantener Rehab, gamificación, Liftin y nutrición fuera del camino crítico;
5. aplazar cualquier borrado físico hasta medir dependencias y reversibilidad.

## 11D — Trayectoria del plan

La pantalla canónica de trayectoria es una lectura autoservicio y de solo
lectura. Separa dos carriles que no deben confundirse: **Fase de
periodización**, obtenida del mismo generador Helms que alimenta el calendario
anual, y **Objetivo del bloque**, obtenido del contrato longitudinal vigente.
Expone la semana materializada, sus fechas previstas, pospuestas, efectivas y
realizadas, únicamente evaluaciones persistidas y un próximo hito determinista.
No abre contratos, no materializa sesiones, no evalúa y no cierra ciclos.

## Pantalla futura — Evolución de rendimiento (11E)

**Estado:** pendiente planificado y bloqueado; no se abre antes de cerrar y
aceptar el primer bloque contractual con evidencia productiva.

La futura pantalla debe responder preguntas concretas del entrenador, no
convertirse en otro dashboard genérico:

1. **Progreso global:** cómo cambia el rendimiento en el tiempo y respecto a la
   línea base personal.
2. **Patrones:** qué mejoras, estancamientos o retrocesos se repiten y con qué
   cobertura de datos.
3. **Eficiencia del entrenamiento:** relación entre carga, repeticiones, RPE,
   técnica y tiempo, preservando los datos ausentes como ausentes.
4. **Comparación por bloque:** diferencias entre bloques cerrados con ventanas,
   objetivos y criterios equivalentes o claramente declarados.
5. **Resultado causal:** qué decisiones del entrenador fueron aplicadas, cómo
   se evaluaron y si quedaron validadas, fallidas, neutras o inconclusas.

### Evidencia histórica y causalidad

El usuario ha comunicado que producción contiene **más de 200 sesiones
históricas**. Ese dato permite planificar tendencias y baselines retrospectivos,
pero no se presenta aquí como un conteo de base de datos verificado. Tampoco
convierte automáticamente esas sesiones en evidencia causal.

- Las sesiones históricas sirven para describir trayectoria, referencias y
  distribución observada.
- Las semanas y bloques contractuales nuevos aportan identidad prescrita,
  decisión aplicada y evaluación, necesarias para atribuir resultados al
  entrenador.
- Una coincidencia temporal entre una decisión y una mejora no basta para
  declarar causalidad si falta el vínculo contractual.

### Criterio de apertura

Iniciar diseño e implementación solo después de que el primer bloque Gym haya
terminado, tenga todas sus semanas contractuales cerradas y su
`EvaluacionBloqueGym` haya sido revisada y aceptada. En ese momento se definirá
un contrato de lectura único antes de diseñar el template: métricas, cobertura,
comparadores válidos, niveles causales y tratamiento del histórico legacy.

## Recibo actual del outbox JOI y próximo paso exacto

La reauditoría productiva de solo lectura, con corte real
`2026-09-07T17:11:13+00:00`, devolvió `contract_ok: false`: **33** eventos
evaluados, **32** pendientes, **1** publicado, backlog **32** y **0** en
procesamiento. El único código que rompe el contrato es `pending_over_48h`,
presente en **26** eventos. Los **6** `future_occurred_at` del recibo anterior
desaparecen con este corte y se consideran un artefacto de haber usado entonces
un `as_of` anterior a su `occurred_at`, no un defecto vigente de los eventos.

Todos los eventos envejecidos son `gym_decision_outcome`, proceden de
`entrenos.GymDecisionLog` y pertenecen al usuario id `3`. La auditoría no
detectó duplicados, diferencias de payload, claims obsoletos, publicados sin
mensaje ni intentos incoherentes. La interpretación operativa es por tanto:
**el productor mantiene la integridad, pero el consumidor no está drenando la
cola**.

El próximo paso es un inventario ORM, exclusivamente de lectura, de los **33**
eventos y del estado de los mensajes/aperturas asociados, seguido de la
verificación de Celery Beat, worker y logs. Se debe conservar la salida JSONL y
crear un backup antes de cualquier mutación. No usar la UI como prueba, ni
procesar o reintentar eventos durante el diagnóstico: no existe un comando de
drenaje con modos `dry-run`/`apply` que permita hacerlo de forma controlada.

El primer preview de cierre permaneció en `dry-run` e informó
`evaluacion_id: null`; la evaluación id `2` ya existe y su aceptación ya
ocurrió. Ejecutar ahora `cerrar_semana_gym --apply` sería potencialmente un
no-op y es innecesario. La Semana 2 queda contractualmente revisada y aceptada.
**11E continúa bloqueada** hasta el cierre y la aceptación de todo el primer
bloque contractual.

## Ventana objetivo auditada — Semana 2

**Inicio:** lunes 31 de agosto de 2026.  
**Objetivo:** validar la segunda semana operativa consecutiva del bloque Gym,
sin ampliar alcance ni reabrir módulos pospuestos.

### Checklist previo — domingo 30 / lunes 31

- [x] Confirmar que el bloque aprobado sigue activo y cubre el 31/08/2026:
      bloque id `1`, activo del 24/08/2026 al 20/09/2026.
- [ ] Previsualizar la apertura semanal; comprobar que propone exactamente una
      semana y no materializa nada en dry-run.
- [ ] Aplicar la apertura una sola vez desde el flujo operativo autorizado.
- [x] Confirmar un único `ContratoSemanalGym` para el lunes 31/08/2026: la
      consulta con `get` resolvió el contrato id `3`.
- [x] Confirmar **5 sesiones objetivo** y **3 como mínimo válido** desde el
      snapshot contractual.
- [x] Verificar que las sesiones corresponden a la fase anual Helms vigente:
      Fuerza — Avanzada, objetivo `fuerza`, fase `11`, semana 2/4, fuente
      `PlanificadorHelms.generar_plan_anual`, sin limitaciones.
- [ ] Confirmar que repetir la operación responde de forma idempotente y no
      duplica contratos o sesiones; el `dry-run` recibido propuso cinco fechas,
      pero no fue repetido.

### Checklist durante la semana

- [ ] Portada, briefing y entrenamiento activo muestran la misma
      `GymDecisionVersion` en cada ejecución causal.
- [ ] Una corrección supervisada, si ocurre, crea una versión nueva y no
      reescribe la versión motor.
- [ ] Una sesión reubicada conserva su fecha prevista y registra por separado
      `pospuesta_hasta` y `fecha_realizada`.
- [ ] Strava o una actividad externa se enlaza al evento físico canónico una
      sola vez; los casos ambiguos quedan sin reparación automática.
- [ ] JOI solo verbaliza decisiones aplicadas o resultados evaluados y mantiene
      su presencia completa en la Habitación.

### Checklist de cierre — después del domingo 6 de septiembre

- [x] Previsualizar `cerrar_semana_gym` antes de escribir: el primer resultado
      fue `objetivo`, 5 sesiones y `evaluacion_id: null`; la consulta posterior
      encontró la evaluación id `2` ya existente.
- [x] Comparar el snapshot persistido de la evaluación id `2` con `_snapshot`
      y revisar `estado_revision`: snapshot igual, hashes iguales y estado
      `aceptada`.
- [x] Confirmar la clasificación contractual: cumplimiento `objetivo`, 5
      completadas, 2 reubicadas y 0 pendientes, omitidas, saltadas o canceladas.
- [x] Revisar cobertura de RPE, energía, duración y volumen: las tres sesiones
      enlazadas suman 18 040 kg y 123 min, con energía media 7,0 y RPE medio
      8,03; los totales globales de `auditar_semana` (36 870 kg/1728 UA) se
      conservan separados.
- [x] Registrar la aceptación colaborativa: evaluación id `2` aceptada por
      `david` (usuario id `3`) el `2026-09-07T04:23:34.798934Z`.
- [ ] Registrar cualquier contradicción como hallazgo de producto; no parchear
      datos productivos sin auditoría y backup.

## Reglas para actualizar esta matriz

1. Actualizar primero este documento cuando cambie el estado de una fase; el
   mapa histórico solo recibe detalle técnico nuevo, no vuelve a ser checklist.
2. Cambiar a **Terminado** únicamente con evidencia concreta en el repositorio:
   contrato o servicio, tests focalizados y, cuando aplique, comando auditable.
3. Registrar por separado la validación productiva. Un test local, una migración
   creada o un `git pull` no prueban que PythonAnywhere esté desplegado.
4. Mantener **En observación** cuando el criterio dependa de varias semanas,
   datos reales, una tarea programada o comportamiento móvil sostenido.
5. Usar **Pospuesto conscientemente** solo con una decisión de producto escrita
   y una condición explícita para reabrir el tema.
6. No borrar filas cerradas ni historia. Si una fase cambia, conservar la
   evidencia anterior en el mapa histórico o en un documento de cierre.
7. Toda nueva subárea debe declarar autoridad, efecto, reversibilidad, prueba y
   evidencia operativa pendiente.
8. En cada actualización revisar enlaces, fecha de corte, próximo hito y
   coherencia con [PRODUCTO_ENTRENADOR_GYM.md](PRODUCTO_ENTRENADOR_GYM.md).

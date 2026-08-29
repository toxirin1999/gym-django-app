# Estado canónico de la transición al entrenador Gym

**Fecha de corte:** 29 de agosto de 2026.  
**Ámbito:** estado editorial contrastado con el repositorio local.  
**Autoridad de producto:** [PRODUCTO_ENTRENADOR_GYM.md](PRODUCTO_ENTRENADOR_GYM.md).  
**Historia técnica detallada:** [TRANSICION_ENTRENADOR_GYM.md](TRANSICION_ENTRENADOR_GYM.md).

Este documento es la lista de estado vigente. Resume qué existe en código, qué
ha recibido alguna comprobación real comunicada durante la transición y qué se
ha aplazado de forma deliberada. No demuestra por sí mismo que una migración se
haya desplegado, que una tarea esté programada o que el comportamiento de
PythonAnywhere coincida con el entorno local.

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
| **3E. Activación colaborativa** | **Terminado** | [`forms_bloque_gym.py`](clientes/forms_bloque_gym.py), [`tests_bloque_gym_colaborativo.py`](clientes/tests_bloque_gym_colaborativo.py) y Centro de decisiones. | Las acciones estratégicas siguen requiriendo aprobación humana. |
| **4. Ciclos de adaptación Gym** | **En observación** | Ciclos persistidos y pruebas para variante, molestia, deload, versión esencial, técnica, tope, fallo, RPE, progresión, perfil causal, cierre semanal, molestia reciente y distribución contractual. | Código amplio no equivale a aprendizaje demostrado: observar resultados reales y cobertura por ciclo. |
| **4. Resumen semanal semántico** | **Terminado** | [`analisis_semanal_service.py`](entrenos/services/analisis_semanal_service.py), [`evaluacion_semanal_gym_service.py`](entrenos/services/evaluacion_semanal_gym_service.py) y sus tests. | Una sesión reubicada conserva 5/5, pero debe nombrarse como adaptación y no como “sin adaptaciones”. |

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
| **11E Evolución de rendimiento** | **Pendiente** | El usuario ha comunicado que producción conserva más de 200 sesiones históricas, útiles para tendencias y líneas base retrospectivas; este conteo no ha sido verificado desde el repositorio. | Abrir diseño e implementación después de aceptar el cierre del primer bloque contractual. Debe separar tendencia histórica de atribución causal por contratos nuevos. |
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

1. completar una ventana real suficiente del bloque activo;
2. observar la apertura y evaluación de semanas consecutivas;
3. confirmar la misma identidad causal desde portada hasta cierre;
4. acumular resultados reales para los ciclos de adaptación, no solo tests;
5. auditar el outbox JOI y la autoridad física con datos posteriores al corte;
6. mantener Rehab, gamificación, Liftin y nutrición fuera del camino crítico;
7. aplazar cualquier borrado físico hasta medir dependencias y reversibilidad.

## 11D — Trayectoria del plan

La pantalla canónica de trayectoria es una lectura autoservicio y de solo
lectura. Separa dos carriles que no deben confundirse: **Fase de
periodización**, obtenida del mismo generador Helms que alimenta el calendario
anual, y **Objetivo del bloque**, obtenido del contrato longitudinal vigente.
Expone la semana materializada, sus fechas previstas, pospuestas, efectivas y
realizadas, únicamente evaluaciones persistidas y un próximo hito determinista.
No abre contratos, no materializa sesiones, no evalúa y no cierra ciclos.

## Pantalla futura — Evolución de rendimiento (11E)

**Estado:** pendiente planificado; no es urgente antes de cerrar el primer
bloque contractual.

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

## Próximo hito exacto — Semana 2

**Inicio:** lunes 31 de agosto de 2026.  
**Objetivo:** validar la segunda semana operativa consecutiva del bloque Gym,
sin ampliar alcance ni reabrir módulos pospuestos.

### Checklist previo — domingo 30 / lunes 31

- [ ] Confirmar que el bloque aprobado sigue activo y cubre el 31/08/2026.
- [ ] Previsualizar la apertura semanal; comprobar que propone exactamente una
      semana y no materializa nada en dry-run.
- [ ] Aplicar la apertura una sola vez desde el flujo operativo autorizado.
- [ ] Confirmar un único `ContratoSemanalGym` para el lunes 31/08/2026.
- [ ] Confirmar **5 sesiones objetivo** y **3 como mínimo válido** desde el
      snapshot contractual.
- [ ] Verificar que las sesiones corresponden a la fase anual Helms vigente;
      el bloque no debe sustituir ni renombrar esa periodización.
- [ ] Confirmar que repetir la operación responde de forma idempotente y no
      duplica contratos o sesiones.

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

- [ ] Previsualizar `cerrar_semana_gym` antes de escribir.
- [ ] Confirmar que cumplimiento, reubicaciones, protecciones y omisiones se
      clasifican desde las sesiones del contrato, no por coincidencia de fecha.
- [ ] Revisar cobertura de RPE, energía, duración y volumen sin rellenar
      ausencias con valores inventados.
- [ ] Aceptar o rechazar la evaluación desde el flujo colaborativo solo después
      de leer su evidencia.
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

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
  lesión, carga externa o sesión prevista produce una nueva identidad sin
  requerir un modelo persistente todavía.

Este corte unifica **qué sesión se muestra y se ejecuta** y elimina los
veredictos Gym paralelos en portada. La corrección manual persistente y el
historial de versiones continúan dentro de la Fase 2; requieren decidir antes
si su valor justifica un modelo nuevo en vez de una identidad diaria derivada.

## 7. Fase 3 — Estrategia, bloque y semana

### Objetivo

Dar contexto longitudinal a la decisión diaria.

### Trabajo

- contrato de bloque propuesto y aprobado;
- plan objetivo, mínimo y protegido;
- semana prescrita, viable y realizada;
- estados precisos de sesión: reubicada, omitida, cancelada, protegida;
- control de deriva entre bloque aprobado y bloque ejecutado;
- evaluación semanal y cierre de bloque multidimensional.

### Criterio de salida

Una sesión perdida no crea deuda infinita y una semana mínima válida sigue
contando como estímulo útil.

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

# Fase 12.1–12.4.2 — auditoría, archivo y cierre causal

## Fase 12.4.2 — auditoría de integridad histórica de gamificación

La auditoría histórica es deliberadamente pasiva: compara los entrenos reales
del cliente, el latch `procesado_gamificacion`, el perfil y el ledger
`HistorialPuntos`, pero no ejecuta `save`, `update`, `delete`, backfill ni el
finalizador. No existe opción `--apply`.

```bash
python manage.py auditar_integridad_gamificacion \
  --cliente 2 \
  --limit 1000 \
  --settings=gymproject.settings
```

`--cliente` es obligatorio y solo admite un cliente. `--limit` (1–10.000)
limita las filas `hallazgo`, no el análisis: el `resumen` final conserva los
conteos globales en `counts_by_code`, los agregados en `totals` y declara
`truncados`. La salida es JSON Lines canónico, ordenado y reproducible, con
`schema_version=1`, `solo_lectura=true` y fingerprint SHA-256.

Se clasifican de forma independiente: totales de entrenos y puntos divergentes,
múltiples eventos base para un entreno, enlaces entre clientes, latch cerrado
sin ledger propio, latch abierto con ledger, historiales sin entreno, perfiles
ausentes/múltiples y duplicados de `PruebaUsuario` si un esquema legacy los
permite. Un historial sin entreno puede proceder de pruebas, quests o de un
enlace perdido por `SET_NULL`; se informa como origen desconocido y nunca se
etiqueta automáticamente como duplicado. Las divergencias tampoco constituyen
una propuesta de reparación.

## Fase 12.4.1 — finalización causal de gamificación

La creación de `EntrenoRealizado` ya no concede puntos. El productor
`post_save` se retiró y la autoridad canónica es
`finalizar_gamificacion_entreno`, invocada explícitamente cuando ejercicios y
métricas ya están persistidos. El servicio bloquea el padre con
`select_for_update` y usa `procesado_gamificacion` como latch: una primera
ejecución concede premios y marca el latch en la misma transacción; un retry
devuelve `already_processed` sin tocar perfil, ledger o notificaciones; un
fallo revierte todas las mutaciones y conserva el latch abierto.

El cierre está conectado a Gym activo, portal, API analytics y al importador
Liftin conservado bajo su flag de archivo. La ruta manual
`logros/procesar-entreno` permanece registrada por compatibilidad, pero responde
404 y no puede reproducir premios. No se reinterpreta ni reprocesa historia y
no hay cambio de esquema. Las rutas activas de cierre y notificaciones aplican
propietario exacto o staff/superusuario; un tercero obtiene 404 conservador.

## Fase 12.3 — Liftin archivado en UX

Liftin conserva su valor histórico: modelos, filas, detalle general, listado,
analytics, signals, consumidores, admin y comandos siguen intactos. Solo se
archiva la superficie operativa mediante `LIFTIN_UI_ENABLED`, desactivado por
defecto. Las 13 URLs conservan path y nombre para permitir `reverse()`, pero el
guard de URL responde 404 antes de ejecutar la vista, incluidos los POST de
importación, edición y eliminación y las APIs internas.

La auditoría mantiene `classification=historical_required` y añade una dimensión
independiente: `ux_status=archived`, `ui_enabled=false`, las 13
`registered_routes` y `reachable_route_count=0`. Esto evita confundir una UX
retirada con datos candidatos a eliminación. Para una reversión controlada se
puede definir `LIFTIN_UI_ENABLED=True`; no requiere restaurar rutas ni migrar BD.

Este primer corte inventaría dependencias sin ocultar, desactivar, archivar ni
modificar datos. La salida no recomienda borrados: la versión 1 nunca emite
`archive_candidate`.

## Uso

```bash
python manage.py auditar_superficies_archivo \
  --cliente 2 \
  --hasta 2026-08-23 \
  --ventana-dias 90 \
  --settings=gymproject.settings
```

`--cliente` acepta exactamente un ID entero; no existe modo para todos los
clientes. `--hasta` usa `YYYY-MM-DD`. `--ventana-dias` es positivo y vale 90
por defecto. La ventana es inclusiva: 90 días terminados el 23 de agosto
comienzan el 26 de mayo.

## Contrato de salida

El JSON determinista contiene `schema_version=1`, `cliente_id`, `ventana`,
`evidence`, `findings`, `limitations`, `summary` y `fingerprint`. La huella es
SHA-256 del documento canónico sin el propio campo `fingerprint`; no existe
`generated_at`, por lo que dos consultas sobre el mismo estado producen el
mismo documento.

Cada evidencia distingue `query_status` de sus conteos. Un cero significa
ausencia demostrada solo con estado `success`; una consulta o ruta que no puede
resolverse se declara como limitación y clasificación `unknown`.

## Allowlist y privacidad

- Liftin: conteos del cliente, filas detalle, presencia agregada de workout ID,
  escrituras recientes por fecha real y rutas reverse allowlisted.
- Gamificación: existencia del perfil, historial propio, fecha real de puntos,
  productor automático declarado y rutas alcanzables.
- Gestión multi-cliente: evidencia estática de rutas CRUD/staff y únicamente la
  existencia del cliente pedido; nunca enumera otros clientes.
- `ExperimentoVarianteGym`: conteos propios, estados, actividad reciente y el
  productor automático declarado.
- Strava: política `protected_integration`; solo conteos demostrablemente
  ligados por `cliente_id` y presencia booleana de credencial.

No se serializan nombres de usuario o cliente, descripciones, notas, JSON libre,
tokens, identificadores externos, lesiones ni biometría. El auditor usa ORM y
`reverse()` explícitos; no inspecciona source en runtime ni importa callbacks.

Las clasificaciones v1 son conservadoras: `core_active`, `active_support`,
`historical_required`, `security_exposed`, `protected_integration` y `unknown`.

## Fase 12.2 — cierre de autorización de gestión multi-cliente

La superficie inventariada como gestión multi-cliente queda protegida por una
política común: puede operar un usuario con `is_staff` **o** `is_superuser`.
Una petición anónima conserva el contrato de Django y redirige al login; una
sesión autenticada sin ese rol recibe 403 antes de consultar formularios o
ejecutar escrituras.

El guard cubre listado, panel de entrenador, API de listado, alta, edición,
eliminación y las tres rutas de asignación de programa/rutina. Los POST
rechazados no crean usuarios o clientes, no cambian credenciales y no asignan
programas ni rutinas. La fase no corrige la semántica legacy de
`asignar_rutina`: únicamente garantiza que el bloqueo ocurre antes de ella.

`detalle_cliente` mantiene una excepción mínima para autoservicio: un cliente
puede consultar exactamente el perfil cuyo `user` coincide con la sesión. El
staff/superusuario puede consultar cualquier cliente. Para otra sesión se usa
un queryset ya restringido y se devuelve 404 tanto si el ID existe como si no,
evitando convertir la ruta en un oráculo de existencia. El enlace «Editar» se
muestra únicamente a staff/superusuarios.

No se han extendido estos permisos a `mockup_demo`, `panel_cliente` ni a rutas
personales de entrenamiento. No hay cambios de modelos o migraciones.

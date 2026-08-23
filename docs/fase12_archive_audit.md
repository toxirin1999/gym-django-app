# Fase 12.1 — auditoría pasiva de superficies legacy

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

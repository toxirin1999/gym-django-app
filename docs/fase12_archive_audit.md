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

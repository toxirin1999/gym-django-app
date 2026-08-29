# Fase 0 — inventario vivo y runbook de Semana 2

## Contrato del inventario

`auditar_inventario_transicion_gym` emite un único documento JSON canónico,
determinista y sin timestamps. No acepta cliente, rango ni `--apply`; no lee ni
modifica base de datos. El inventario declara módulos, rutas, comandos,
procesos, dependencias y autoridad de cada superficie.

```bash
python manage.py auditar_inventario_transicion_gym \
  --settings=gymproject.settings
```

La salida incluye `schema_version`, `solo_lectura`, enums del contrato,
superficies ordenadas y una huella SHA-256 calculada sobre el JSON sin
`fingerprint`. Las superficies `archived`, `postponed` y `legacy_compat`
declaran siempre `autoridad=none`.

El catálogo es deliberadamente explícito. Una ruta, comando o proceso nuevo no
entra por introspección accidental: debe añadirse con estado, autoridad y
dependencias revisadas, junto con su prueba de resolución.

## Runbook — Semana 2 (31/08/2026–06/09/2026)

Los ejemplos usan el cliente `2`. Sustituirlo por el ID propio cuando se use en
otro entorno. Ejecutar primero todos los modos dry-run; `--apply` solo aparece
en los pasos que materializan o cierran un contrato de forma explícita.

### 1. Inventario y evidencia previa

```bash
python manage.py auditar_inventario_transicion_gym \
  --settings=gymproject.settings

python manage.py auditar_semana_gym \
  --cliente 2 \
  --desde 2026-08-31 \
  --hasta 2026-09-06 \
  --settings=gymproject.settings
```

La segunda consulta puede no contener sesiones antes de abrir la semana; eso es
ausencia de evidencia, no un error ni autorización para reconstruir datos.

### 2. Previsualizar la apertura el domingo 30

```bash
python manage.py preparar_semana_gym \
  --fecha-referencia 2026-08-30 \
  --solo-domingo \
  --settings=gymproject.settings
```

Comprobar que la propuesta corresponde al lunes 31, al bloque activo y a una
única semana. Este paso es dry-run y no debe crear contrato ni sesiones.

### 3. Abrir la semana una sola vez

```bash
python manage.py preparar_semana_gym \
  --fecha-referencia 2026-08-30 \
  --solo-domingo \
  --apply \
  --settings=gymproject.settings
```

Repetir primero el comando sin `--apply`: debe responder como ya materializada,
sin duplicar contrato o sesiones.

### 4. Verificación dirigida del contrato

La apertura operativa ya materializa el contrato. El comando siguiente se usa
como comprobación idempotente, primero sin escritura:

```bash
python manage.py materializar_contrato_semanal_gym \
  --cliente 2 \
  --semana 2026-08-31 \
  --settings=gymproject.settings
```

Solo si el contrato existiera pero sus sesiones no se hubieran materializado y
el dry-run fuese inequívoco, repetir con `--apply`. No usarlo para regenerar o
reordenar una semana ya existente.

### 5. Auditoría durante la semana

```bash
python manage.py auditar_semana_gym \
  --cliente 2 \
  --desde 2026-08-31 \
  --hasta 2026-09-06 \
  --settings=gymproject.settings
```

Revisar identidades de decisión y sesión, fechas efectivas, RPE, check-in y
carga externa sin inferir valores ausentes. Las reubicaciones conservan la
fecha prevista y registran separadamente la fecha efectiva.

### 6. Cierre después del domingo 6

Previsualizar siempre antes de persistir:

```bash
python manage.py cerrar_semana_gym \
  --cliente 2 \
  --semana 2026-08-31 \
  --settings=gymproject.settings

python manage.py cerrar_semana_gym \
  --cliente 2 \
  --semana 2026-08-31 \
  --apply \
  --settings=gymproject.settings
```

El cierre debe clasificar objetivo, mínimo o insuficiente usando únicamente las
sesiones ancladas al contrato. No arrastra deuda a la semana siguiente.

### 7. Comprobación del bloque

`auditar_bloque_gym` requiere el ID real del bloque, no el cliente:

```bash
python manage.py auditar_bloque_gym \
  --bloque <BLOQUE_ID> \
  --settings=gymproject.settings
```

No sustituir `<BLOQUE_ID>` por `2` salvo que ese sea realmente el ID mostrado
por el contrato. La auditoría es read-only.

## Actualización del catálogo

1. Añadir o retirar una superficie únicamente mediante revisión de código.
2. Mantener IDs, dependencias, módulos, rutas, comandos y procesos ordenados.
3. Resolver toda referencia en tests; una superficie no desaparece porque su
   ruta deje de resolver.
4. No conceder autoridad a superficies archivadas, pospuestas o legacy.
5. No añadir IDs de usuario, biometría, texto libre, secretos ni valores de
   configuración.
6. Actualizar el estado canónico y este runbook en el mismo cambio.


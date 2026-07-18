# 📋 CONTRATO DEL ANALIZADOR DE GESTOS — v0.3 — APROBADO PARA IMPLEMENTACIÓN

> Contrato cerrado. Las tres auditorías (trazabilidad técnica, auditoría de fechas/cadencia, auditoría de cierre) no dejaron hallazgos de diseño sin resolver — solo quedaba una pregunta fáctica (zona horaria real del usuario), ya respondida. A partir de aquí, cualquier cambio de alcance en §5 debería abrir una nueva versión, no editarse en silencio sobre esta.

**Status**: **IMPLEMENTADO** (2026-07-18). Fases 1 → 5C completas y verificadas (235/235 tests). En periodo de Post-implementación (§19) antes de considerar cualquier Fase 6 — ver anotaciones de uso real ahí.
**Alcance**: `Gesto` con `tipo='cultivo'`. **No** sustituye ni toca `TriggerHabito`/`TriggersService` (`tipo='suelto'`) — ver §3.
**Pregunta que este contrato debe poder responder siempre**:

> Dada cualquier frase mostrada en la app, ¿podemos recorrer hacia atrás exactamente qué registros, cierres, cadencia y periodos activos justifican esa frase?

## Registro de cambios v0.2 → v0.3

Las cuatro decisiones pendientes de la auditoría de cierre quedaron resueltas. Ninguna reabre §5.1-§5.2/§5.4 (taxonomía y métricas observacionales) ni el dataset de Hábitos A, C, D — solo afectan §2, §4 y M11/Hábito B.

1. **Zona horaria — decisión cerrada, no aplazada.** `TIME_ZONE = "Europe/Madrid"`, `USE_TZ = True` (ya estaba en `True`). Toda fecha civil se obtiene vía `timezone.localdate()`, nunca `timezone.now().date()` ni `date.today()`. Lista concreta de puntos a corregir en §4.
2. **`cadencia_configurada_en` — cuatro casos explícitos** en vez de un único valor por defecto (§2.2): gesto nuevo con cadencia elegida al crear, gesto histórico migrado a `libre` (queda `null` hasta configuración explícita), primera configuración explícita de un gesto existente, cambio posterior — los tres últimos casos usan "hoy".
3. **`insights_engine.py` — retirada de su fórmula propia para `cultivo`**, no reescritura sobre M10 (M10 no cubre `libre` ni `semanal`). Nueva regla arquitectónica: ninguna superficie recalcula frecuencia/densidad/adherencia por su cuenta — todas consumen la salida del analizador. Ver §3bis.
4. **M11 reescrita con clasificación de cuatro estados** (`semana_completa` / `semana_parcial_alcanzable` / `semana_no_evaluable` / `semana_en_curso`), sustituyendo la tricotomía de v0.2 por una que sí distingue si el objetivo era matemáticamente alcanzable dentro de los días activos disponibles — no solo si hubo algún día activo.

Además, corrección aceptada sobre la escritura de `cierre_confirmado_en`: no basta con colocarla después del bucle de hábitos si las escrituras previas no están en la misma transacción — se extrae un servicio transaccional (§2.1).

---

## 1. Qué resuelve

(sin cambios) Ver v0.1/v0.2 — el click nocturno guarda ejecución pero casi no genera conocimiento posterior.

---

## 2. Modelo de datos que este contrato asume

### 2.1 Cierre confirmado — núcleo transaccional (reescrito)

La auditoría de cierre detectó que "escribir `cierre_confirmado_en` después del bucle de hábitos" no garantiza nada si `SeguimientoVires`, `entrada.reflexiones_dia` y la sincronización de `RegistroGesto` ya se guardaron como operaciones independientes antes de llegar ahí — un fallo intermedio deja un cierre parcial sin que el marcador lo refleje. La corrección es extraer el núcleo a un servicio transaccional:

```python
# diario/services/cierre_service.py (nuevo)

@transaction.atomic
def persistir_nucleo_cierre(usuario, fecha, entrada, texto_libre, friccion_raw, cuerpo_raw, habitos_completados_ids, gestos_activos):
    if texto_libre:
        entrada.reflexiones_dia = texto_libre
        entrada.save(update_fields=['reflexiones_dia'])

    if friccion_raw or cuerpo_raw:
        vires, _ = SeguimientoVires.objects.get_or_create(usuario=usuario, fecha=fecha)
        if friccion_raw:
            vires.nivel_estres = int(friccion_raw)
        if cuerpo_raw:
            vires.cuerpo_cierre = cuerpo_raw
        vires.save()

    cumplidos_hoy_ids = set(
        RegistroGesto.objects.filter(gesto__in=gestos_activos, fecha=fecha, estado='cumplido')
        .values_list('gesto_id', flat=True)
    )
    for gesto in gestos_activos:
        deseado = gesto.id in habitos_completados_ids
        actual = gesto.id in cumplidos_hoy_ids
        if deseado != actual:
            HabitosService.toggle_dia(gesto, fecha)

    if entrada.cierre_confirmado_en is None:
        entrada.cierre_confirmado_en = timezone.now()
        entrada.save(update_fields=['cierre_confirmado_en'])
```

`presencia_cierre` pasa a llamar primero a `persistir_nucleo_cierre(...)` (una sola transacción — si algo falla dentro, no se persiste nada de ese bloque, incluido el marcador) y **después**, fuera del `atomic`, el enriquecimiento JOI/Gemini ya existente (`parsear_cierre_diario`, `enriquecer_cierre`, `generar_respuesta_cierre`, la comprobación de Simbiosis), sin cambios en su propio `try/except` best-effort. Esto invierte el orden actual del código (hoy el guardado de `reflexiones_dia` está intercalado *dentro* del bloque de enriquecimiento JOI) pero no cambia ningún dato que JOI necesite — JOI lee `texto_libre` como entrada, no depende de que el núcleo ya esté guardado.

Efecto secundario positivo: el bloqueo de Simbiosis (que hoy puede interrumpir la vista con un `return` antes de terminar) pasa a ocurrir *después* de que el día ya esté cerrado de verdad, no a mitad de un guardado ambiguo.

```python
# ProsocheDiario
cierre_confirmado_en = models.DateTimeField(null=True, blank=True)

@property
def esta_cerrado(self):
    return self.cierre_confirmado_en is not None
```

Migración: filas históricas con `cierre_confirmado_en = null`. No se infiere retroactivamente.

### 2.2 Cadencia esperada (reescrito — corrección 2)

```python
# Gesto — aplica solo si tipo == 'cultivo'
tipo_cadencia = models.CharField(max_length=20, choices=[...], default=CADENCIA_LIBRE)
frecuencia_semanal_objetivo = models.PositiveSmallIntegerField(null=True, blank=True)
dias_semana_objetivo = models.JSONField(default=list, blank=True)
cadencia_configurada_en = models.DateField(null=True, blank=True)
```

**Valor inicial de `cadencia_configurada_en` — cuatro casos, no uno solo**:

| Caso | Valor |
|---|---|
| `Gesto` nuevo, creado ya con una cadencia elegida (no `libre` por omisión sin querer) | `cadencia_configurada_en = fecha_inicio` (fecha de creación efectiva) |
| `Gesto` histórico, migrado a `tipo_cadencia='libre'` por la migración de v0.1 | `cadencia_configurada_en = null` — se queda así hasta que el usuario configure algo explícitamente |
| Primera configuración explícita de un `Gesto` que ya existía (el usuario le pone cadencia por primera vez tras la migración) | `cadencia_configurada_en = hoy` |
| Cambio posterior de una cadencia ya configurada (con `RegistroGesto` existentes) | `cadencia_configurada_en = hoy` de nuevo — se reinicia |

Las métricas de §5.3 (cumplimiento) solo usan datos desde `cadencia_configurada_en` en adelante; si es `null`, esas métricas no son calculables (`motivo_no_calculable='cadencia_no_configurada'`) aunque el `Gesto` tenga años de `RegistroGesto`. §5.2 (observacionales) no depende de este campo.

**Advertencia de UI obligatoria antes de guardar un cambio de cadencia sobre un `Gesto` con registros existentes** (no es parte del modelo, pero el contrato la exige como condición de uso): *"Cambiar la frecuencia reiniciará el análisis de cumplimiento desde hoy. Los registros anteriores se conservarán, pero solo como historial observacional."* Sin este aviso, el usuario puede sorprenderse de que su adherencia "se resetee" sin haber tocado ningún dato.

No se usa `fecha_creacion`/`fecha_inicio` retroactivamente para hábitos existentes que se configuran ahora por primera vez — eso reinterpretaría con una intención el pasado que nunca se registró como tal.

(Invariantes de configuración por `tipo_cadencia`: sin cambios respecto a v0.2 — ver tabla original.)

### 2.3 Pausas con transición completa

(sin cambios respecto a v0.2 — `PausaGesto`, intervalo semiabierto, `habito_reactivar` nueva, colapso de intervalo de longitud cero, `fecha_cierre` exclusiva.)

---

## 3. Alcance y exclusiones explícitas

(sin cambios de fondo) Cubre solo `tipo='cultivo'`. `tipo='suelto'` sigue con `TriggerHabito`/`TriggersService`.

## 3bis. Principio arquitectónico nuevo — fuente única de verdad (corrección 3)

> Ninguna superficie de la app recalcula frecuencia, densidad o adherencia por su cuenta. Todas consumen la misma salida trazable del analizador (§5).

Esto se añade porque la auditoría encontró una tercera fuente de "progreso" ya viva y no contemplada: `insights_engine.py:79-109` calcula `porcentaje = registros_mes / gesto.periodo_observacion_dias` para `Gesto` `cultivo` — una fórmula distinta a M10, con un denominador que no es ni una ventana de cumplimiento ni una densidad observacional coherente. Decisión (no se reescribe sobre M10 porque M10 no cubre `libre` ni `semanal`):

| Fase | Comportamiento de `insights_engine.py` para `Gesto` `cultivo` |
|---|---|
| Antes de que exista el analizador (fase de zona horaria + núcleo transaccional, §9) | Se **desactiva** el insight de porcentaje actual — no se sustituye por nada todavía, mejor ausente que contradictorio. |
| Después de que exista el analizador | Consume el servicio canónico, eligiendo la lectura según cadencia: `libre` → M1/M2/M7 con lenguaje puramente descriptivo; `diaria`/`dias_concretos` → M10 si `confianza` es suficiente; `semanal` → M11, usando solo `semana_completa` para la tasa. No recalcula nada por su cuenta. |

`InsigniasService` (insignias por días acumulados) y `Gesto.get_racha_actual()` no están cubiertas por esta regla en v0.3 — su tratamiento sigue siendo el de §7 (dirección adoptada, pendiente de implementar: conservar solo para `diaria`, ocultar para el resto). No se amplía su alcance en esta versión.

---

## 4. Convenciones compartidas

### Zona horaria — decisión cerrada, confirmada con evidencia de dominio, no de configuración heredada

```python
# gymproject/settings.py
TIME_ZONE = "Europe/Madrid"
USE_TZ = True  # ya estaba en True
```

Justificación (importante distinguirla de la evidencia de código, que apuntaba a otro sitio): `TIME_ZONE` determina cómo Django interpreta las fechas locales (`timezone.localdate()`, conversión de `DateTimeField`) — es un concepto de **dominio**, no de infraestructura. Todo lo que este contrato modela (cierres diarios, hábitos, semanas) gira alrededor del día civil del usuario real de la app, que vive en Marbella (España). Esa es la evidencia que decide `TIME_ZONE`, no `CELERY_TIMEZONE` (ver nota separada abajo).

**Precisión importante sobre lo que cambia y lo que no**: cambiar `TIME_ZONE` no altera los instantes ya almacenados en campos `DateTimeField` — Django sigue guardándolos en UTC internamente (`USE_TZ=True` ya lo garantiza). Lo que cambia es la conversión a fecha/hora local al leerlos, que es exactamente lo que hace falta para que "hoy" signifique el día civil real del usuario.

**Regla contractual**: toda fecha civil de `diario` y hábitos se obtiene mediante `timezone.localdate()` bajo la zona horaria configurada del proyecto — nunca `timezone.now().date()` ni `date.today()` (este último ignora por completo la configuración de Django). No se añade middleware de activación de zona horaria por usuario en esta versión — no compensa el coste mientras la app tenga un único usuario real; se reconsiderará si algún día hay usuarios en zonas horarias distintas.

**Nota explícita — `CELERY_TIMEZONE` queda fuera de este contrato**: `gymproject/settings.py:69` tiene `CELERY_TIMEZONE = 'America/Mexico_City'`, desacoplado de `TIME_ZONE` a propósito por Celery (determina cuándo se disparan tareas programadas — JOI matutino, resumen semanal —, no qué día civil vive el usuario). No se toca ni se alinea automáticamente con `Europe/Madrid` en este contrato. Es una auditoría independiente pendiente (¿resto de una configuración antigua, decisión operativa consciente, u olvido?) que no bloquea ni forma parte de la aprobación de este documento.

**Puntos concretos a corregir** (verificado por grep contra el código real, todos dentro de `diario/`):

| Archivo | Líneas con `timezone.now().date()` a sustituir por `timezone.localdate()` |
|---|---|
| `views.py` | 67, 99, 134, 629, 663, 700, 717, 1426, 1540, 1766, 1839, 1985, 2437, 2641, 2833, 3079, 3217, 3359, 3502, 3595 |
| `views.py:3533` | `date.today()` dentro de `_generar_pregunta_simbiosis` (import local `from datetime import date as _date`) → también a `timezone.localdate()` |

Ya cumplen la regla y no requieren cambio: `views_habitos.py` (líneas 46, 141, 247, ya usan `timezone.localdate()`), `models.py:801` (`Gesto.get_racha_actual`), y `services/lectura_semanal.py`, `services/senales_entrenamiento.py`, `services/intensidad_apertura.py`, `services/sugerencias_diario.py` (todos ya usan `timezone.localdate()`). Estos no necesitan tocarse — con el cambio de `TIME_ZONE` empiezan a devolver la fecha correcta automáticamente, sin cambio de código.

*(El resto de `views.py` fuera del alcance de este contrato — p. ej. `RachaEscritura.actualizar_racha` en líneas 1839/1985 — también usa `timezone.now().date()`; se corrige igual por consistencia del archivo, pero no es analizado por este contrato.)*

### Ventanas temporales, niveles de confianza, forma de resultado, precedencia de estado

(sin cambios respecto a v0.2)

---

## 5. Familias de métricas

### 5.1 Taxonomía diaria, 5.2 Observacionales, 5.4 Contextuales

(sin cambios respecto a v0.2)

### 5.3 Métricas de cumplimiento

**M8, M9, M10, M12, M13**: sin cambios de fondo respecto a v0.2 (alcance ya restringido a `diaria`/`dias_concretos` desde v0.2; `M13` semanal ya usaba semanas, ver ajuste de vocabulario abajo).

**M11 — Evaluación semanal, reescrita (corrección 4)**

La regla de v0.2 ("0 días pausados/no_observados → completa, si no → parcial o no_evaluable") no distinguía si el objetivo era matemáticamente alcanzable dentro de los días que sí estuvieron disponibles. Ejemplo que la auditoría usó para forzar la corrección: objetivo 4/semana, reactivación en viernes → quedan 3 días activos (viernes, sábado, domingo) — con la regla de v0.2 esto sería "parcial" y se mostraría junto a semanas donde sí era posible llegar a 4, cuando en realidad **nunca pudo cumplirse matemáticamente**.

Dos magnitudes distintas por semana, que no deben confundirse:

- **`dias_activos_disponibles`** = días de la semana calendario que **no** son `pausado` ni `fuera_de_vida` (si el día es `no_observado` pero activo, **sí** cuenta aquí — la oportunidad existía, solo falta el dato).
- **`dias_activos_observados_cumplidos`** = subconjunto de los anteriores que además son `observado` y tienen `RegistroGesto` cumplido (el único conjunto sobre el que se puede afirmar nada, porque es el único con dato real).

```python
objetivo_alcanzable = dias_activos_disponibles >= frecuencia_semanal_objetivo
```

Clasificación de cuatro estados:

| Estado | Condición | Entra en la tasa principal | Qué se puede afirmar |
|---|---|---|---|
| `semana_completa` | 0 días `pausado` y 0 días `no_observado` (semana ya terminada) | Sí | `cumplida` / `no_cumplida` |
| `semana_parcial_alcanzable` | Semana ya terminada, tiene algún día `pausado` o `no_observado`, pero `objetivo_alcanzable=True` | **No** | *"Semana parcial: alcanzó / no alcanzó el objetivo (X de Y días activos)."* — lectura separada, nunca mezclada con la tasa |
| `semana_no_evaluable` | Semana ya terminada y `objetivo_alcanzable=False` (incluye el caso de 0 días activos) | No | Nada — no puede calificarse como incumplida porque el propio periodo activo hacía imposible lograrlo |
| `semana_en_curso` | Contiene `fecha_referencia`, no ha terminado | No | Progreso provisional: si ya alcanzó el número requerido dentro de los días transcurridos, puede mostrarse como *"objetivo alcanzado provisionalmente"* — nunca como `cumplida` hasta el cierre de la semana |

**Prohibición explícita**: las semanas `parcial_alcanzable` nunca se mezclan con `completa` en la tasa principal, **incluso si hay pocas semanas completas disponibles**. Si la muestra de `semana_completa` es insuficiente, la respuesta correcta es `confianza='insuficiente'`, nunca rebajar el estándar incorporando parciales para tener "más datos".

**M13 (recuperación, cadencia `semanal`)** — ajuste de vocabulario, sin cambio de fondo respecto a v0.2: una `semana_parcial_alcanzable` que sí alcanzó su objetivo dentro de los días disponibles puede cerrar la cuenta de recuperación (es evidencia de que volvió a pasar), aunque no cuente como `semana_completa` a efectos de M11 — sigue siendo la asimetría deliberada ya documentada en v0.2 (M11 estricta para no inflar la tasa, M13 más permisiva porque solo necesita evidencia).

---

## 6. Dataset de referencia

Ventana **2026-06-15 a 2026-07-15**, `fecha_referencia = 2026-07-15`. Hábitos A y C sin cambios respecto a v0.2.

**Corrección encontrada al implementar la Fase 4 (no en una auditoría de lectura — al escribir el código contra el dataset)**: el ejemplo de M3/M4 de Hábito D (`libre`) en v0.1/v0.2 calculaba "intervalo activo" como el delta natural entre fechas (`[3, 5, 6, 8, 6] → mediana 6, máximo 8`). Eso es inconsistente con la propia definición de "intervalo activo" que el contrato ya fijaba en el ejemplo dedicado de M4 (`cumplido 2026-06-20 → pausa → cumplido 2026-07-11`, activo=1): el intervalo activo es el **nº de días estrictamente entre dos fechas** que no son `pausado`/`fuera_de_vida`, no el delta natural — y el nº de días estrictamente entre dos fechas es siempre un día menos que su delta natural. Para D, sin pausas, eso solo se notó al implementar el código fielmente a esa definición (`diario/services/analizador_gestos.py`) y comparar contra el dataset a mano — la vieja tabla nunca se había ejecutado. Corregido: intervalos activos = `[2, 4, 5, 7, 5]` → **mediana = 5, máximo = 7**. Los deltas naturales (`[3, 5, 6, 8, 6]`) siguen siendo correctos como dato auxiliar — el error estaba en tratarlos como si fueran también el valor activo.

### 6.2 Hábito B — Gimnasio (`semanal`, objetivo=4) — tabla reclasificada con M11 v0.3

Pausa `[2026-06-22, 2026-07-01)` → pausado 22–30 jun (9 días).

| Semana | Pausado | No observado | `dias_activos_disponibles` | `objetivo_alcanzable` (≥4) | Cumplidos | Clasificación |
|---|---|---|---|---|---|---|
| 15–21 jun | 0 | 0 | 7 | Sí | 3 | `semana_completa` → **no_cumplida** |
| 22–28 jun | 7 | 0 | 0 | No | 0 | `semana_no_evaluable` |
| 29 jun–5 jul | 2 (29,30 jun) | 1 (5 jul) | 5 (7−2) | Sí | 2 (2,4 jul) | `semana_parcial_alcanzable` → no alcanzó (2 de 4) |
| 6–12 jul | 0 | 1 (6 jul) | 7 | Sí | 2 (9,12 jul) | `semana_parcial_alcanzable` → no alcanzó (2 de 4) — nótese que esta semana no tiene ninguna pausa, es "parcial" únicamente por el día `no_observado`; `dias_activos_disponibles` no se reduce por `no_observado`, solo por `pausado` |
| 13–15 jul | 0 | 0 | 3 (transcurridos) | indeterminado (aún puede llegar a 4 con los 4 días que faltan) | 0 hasta ahora | `semana_en_curso` — progreso provisional 0/4, no cerrada |

Tasa principal = 0 semanas cumplidas / 1 semana completa evaluada = 0%, `confianza='insuficiente'` (sin cambio respecto a v0.2).

**Ejemplo adicional para `semana_no_evaluable` con pausa parcial** (caso que motivó la corrección, tomado literal de la auditoría): objetivo 4/semana, reactivación en viernes → `dias_activos_disponibles` = 3 (viernes, sábado, domingo) → `3 < 4` → `objetivo_alcanzable=False` → `semana_no_evaluable`, aunque hubiera 3 días activos y en todos ellos se hubiera cumplido el hábito. No se puede llamar "incumplida" a una semana que nunca pudo alcanzar el objetivo.

---

## 7. Preguntas abiertas restantes

1. **§5.1** — la taxonomía diaria sigue sin ser uniforme entre cadencias. Sin cambios, sigue siendo una decisión aceptada, no un pendiente.
2. **§4** — umbrales de confianza (80/50/25%) y de regularidad (M5) siguen sin validar con datos reales.
3. **§3bis** — dirección adoptada, no implementada: `get_racha_actual()`/`InsigniasService` se conservan solo para `tipo_cadencia='diaria'`; se ocultan para el resto hasta diseñar badges compatibles con cada cadencia. No incluido en el alcance de v0.3.
4. ~~`habito_toggle_dia` no filtra por `estado='activo'`~~ — **resuelto en Fase 3** (`views_habitos.py`, el `get_object_or_404` ahora exige `estado='activo'`).
5. **`dias_semana_objetivo`** debe compararse contra `fecha.weekday()` vía un mapeo fijo en código, no contra nombres dependientes de locale (mismo riesgo que ya existe hoy en `ProsocheMes.mes = hoy.strftime('%B')`) — a confirmar como requisito de implementación, no de este contrato.

---

## 8. Qué NO hace este contrato

🚫 No define UI ni copy final — salvo el texto de advertencia obligatorio de §2.2 (cambio de cadencia), que sí es una exigencia del contrato porque protege contra una sorpresa de datos, no es solo estilo.
🚫 No toca `TriggerHabito`/`TriggersService` ni el dominio `suelto`.
🚫 No migra los campos del habit loop de `ProsocheHabito` a `Gesto`.
🚫 No implementa captura contextual para `cultivo` (§5.4).
🚫 No implementa el rediseño de insignias/racha por cadencia (§7.3) — solo fija la dirección.
🚫 No fija umbrales de confianza como definitivos.
🚫 No añade middleware de zona horaria por usuario — decisión explícita, no un olvido.

---

## 9. Orden de fases de implementación

Aprobado. Ninguna fase empieza sin que la anterior esté cerrada — en particular, el analizador (fase 4) no se escribe sobre un modelo todavía inestable (fases 1-3).

**Fase 1 — Infraestructura de fecha lógica** (§4)
`TIME_ZONE = "Europe/Madrid"` en `gymproject/settings.py`. Sustituir `timezone.now().date()` / `date.today()` por `timezone.localdate()` en el dominio de `diario` y hábitos (lista exacta de líneas en §4). No toca `CELERY_TIMEZONE`.

**Fase 2 — Núcleo transaccional de `presencia_cierre`** (§2.1)
Extraer `persistir_nucleo_cierre()` a `diario/services/cierre_service.py`. Reordenar la vista para que el núcleo (reflexión + `SeguimientoVires` + sincronización de `RegistroGesto`) se ejecute primero, dentro de `@transaction.atomic`, y el enriquecimiento JOI/Simbiosis después, fuera de la transacción. Esta fase todavía no toca `cierre_confirmado_en` como campo — deja el terreno listo para la fase 3.

**Fase 3 — Modelo**
`ProsocheDiario.cierre_confirmado_en`, `Gesto.tipo_cadencia`/`frecuencia_semanal_objetivo`/`dias_semana_objetivo`/`cadencia_configurada_en`, `PausaGesto` + vista `habito_reactivar`. Migraciones conservadoras (histórico a `null`/`libre`, sin inferencia retroactiva — §2). Invariantes de cadencia validadas en `Gesto.clean()`.

**Fase 4 — Analizador**
Servicio de métricas sobre §5 (taxonomía, familias de métricas, dataset de referencia como suite de tests). Se apoya en un modelo ya estable desde la fase 3 — ninguna métrica se escribe antes de que `cierre_confirmado_en`/cadencia/`PausaGesto` existan de verdad.

**Fase 5 — Migración de superficies existentes**
`insights_engine.py` deja de calcular su propio porcentaje para `cultivo` (§3bis) y consume el analizador. `get_racha_actual()`/`InsigniasService` quedan con su tratamiento provisional de §7.3 (conservar solo para `diaria`, ocultar para el resto) — su rediseño completo no es parte de esta fase.

Este contrato no vuelve a abrirse por avances de implementación normales. Si una fase descubre que una métrica de §5 no se sostiene con datos reales, eso sí reabre el contrato — no se parchea en el código en silencio.

---

## 10. Registro de ejecución — Fase 1 (completada, 2026-07-18)

**Qué se cambió:**

- `gymproject/settings.py:180` — `TIME_ZONE = 'UTC'` → `TIME_ZONE = 'Europe/Madrid'`. `USE_TZ` ya estaba en `True`, sin cambio.
- Sustituido `timezone.now().date()` por `timezone.localdate()` en: `diario/views.py` (20 ocurrencias), `diario/insights_engine.py` (1), `diario/services/intensidad_apertura.py` (1), `diario/services/lectura_semanal.py` (1), `diario/services/senales_entrenamiento.py` (2).
- Casos que no seguían el patrón literal, corregidos individualmente:
  - `views.py:904` (`prosoche_dashboard`) — `hoy = timezone.now()` → `timezone.localdate()` (solo se usaban `.strftime()`/`.year`, ambos disponibles en `date`).
  - `views.py:1830` — título de reflexión con `timezone.now().strftime('%d/%m/%Y')` → `timezone.localdate().strftime(...)`.
  - `views.py:2724` (`analisis_habitos_anual`) — `timezone.now().year` → `timezone.localdate().year`.
  - `views.py:3533` (`_generar_pregunta_simbiosis`) — `date.today()` (import local `from datetime import date as _date`) → `timezone.localdate()`; import local eliminado por quedar sin uso.
  - `views.py:1839, 1985` (`RachaEscritura.actualizar_racha(timezone.now().date())`) → `timezone.localdate()` — fuera del dominio de hábitos estrictamente, pero en el mismo archivo y con el mismo riesgo; corregido por consistencia, tal como ya anticipaba §4 en v0.2/v0.3.
- Tests actualizados para no depender de `date.today()` (hora del SO, no de `TIME_ZONE` de Django — un tercer criterio de "hoy" distinto tanto del bug como de la corrección): `diario/tests_gestos_2e_cierre.py`, `diario/tests_gestos_2d1.py`.
- Test nuevo: `diario/tests_fase1_zona_horaria.py` — fija un instante concreto (23:30 UTC del 17 de julio de 2026 = 01:30 del 18 en Madrid) donde UTC y Europe/Madrid discrepan de día civil, y verifica: (1) `timezone.localdate()` devuelve el día de Madrid; (2) un cierre (`presencia_cierre`) en ese instante registra `RegistroGesto.fecha` en el día de Madrid, no en el de UTC; (3) `Gesto.get_racha_actual()` cuenta ese registro como "hoy".

**Qué NO se cambió, y por qué:**

- `CELERY_TIMEZONE = 'America/Mexico_City'` (`settings.py:69`) — decisión explícita, ver §4. Concepto operativo distinto (cuándo disparan las tareas de Celery), no de dominio (qué día civil vive el usuario). Auditoría independiente pendiente, fuera de este contrato.
- `models.py:65` — `TrimestreEudaimonia.año = models.IntegerField(default=timezone.now().year)`. Encontrado durante el barrido, **no tocado**: no es un `.date()`/`date.today()` de los que pedía esta fase, y además tiene un bug propio no relacionado con zona horaria (el `default` se evalúa una sola vez al importar el módulo, no por instancia — un `IntegerField(default=...)` no es un default perezoso salvo que sea `callable`). Ni pertenece al dominio de hábitos/cierre ni lo introduce ni lo agrava este cambio. Se deja documentado para una fase aparte, no de este contrato.
- `views.py:553`, `views.py:3875`, `models.py:1066` — asignaciones directas a campos `DateTimeField` (`ejercicio.fecha_completado`, `entrada.respuesta_joi_cierre_generada_en`, `self.fecha_ultimo_nivel`) con `timezone.now()`. Son instantes, no fechas civiles derivadas — su semántica se mantiene intacta a propósito, tal como exigía el alcance de esta fase.
- `views_habitos.py` (líneas 46, 141, 247), `models.py:801` (`Gesto.get_racha_actual`), `services/sugerencias_diario.py:35` — ya usaban `timezone.localdate()` antes de esta fase. No requerían cambio de código; con el nuevo `TIME_ZONE` devuelven automáticamente el día correcto.
- Tests de `tests_senales_entrenamiento.py` y `tests_sugerencias_diario.py` siguen usando `date.today()` (hora del SO) para construir sus fixtures, mientras que el código de producción que ejercitan (`services/senales_entrenamiento.py`, `services/sugerencias_diario.py`) ya usa `timezone.localdate()`. **No corregidos en esta fase** por quedar fuera del alcance declarado ("tests para cierres y hábitos") — quedan como riesgo de fragilidad latente documentado: si la máquina donde corren los tests tiene una zona horaria de sistema distinta de Europe/Madrid, podrían volverse inestables cerca de medianoche. Candidato claro para una fase de limpieza de tests posterior.
- No se añadió middleware de activación de zona horaria por usuario — decisión ya cerrada en §4, no revisada en esta fase.

**Validación ejecutada:**

- `python3 manage.py check --settings=gymproject.settings_local` — sin errores (2 warnings preexistentes de nombres de `templatetags` duplicados entre apps, no relacionados con este cambio).
- `python3 manage.py test diario.tests_fase1_zona_horaria --settings=gymproject.settings_local` — 3/3 tests nuevos, `OK`.
- `python3 manage.py test diario --settings=gymproject.settings_local` — suite completa de `diario`, **110/110 tests, `OK`**, sin regresiones.
- No se ejecutó la suite completa del proyecto (todas las apps) — fuera del alcance declarado de esta fase (dominio `diario`); un cambio de `TIME_ZONE` es de configuración global, así que en sentido estricto otras apps con tests sensibles a fecha no quedaron verificadas contra el nuevo valor. Riesgo bajo (ninguna otra app fue tocada, y `diario` es con diferencia el dominio con más lógica de fecha), pero queda anotado como no verificado.

**Fase 2 completada** (2026-07-18) — ver §11.

---

## 11. Registro de ejecución — Fase 2 (completada, 2026-07-18)

**Precisión de alcance respecto al §9 original**: §9 había separado "núcleo transaccional" (Fase 2) de "modelo" (Fase 3), dejando `cierre_confirmado_en` como campo para la Fase 3. Al ejecutar, quedó claro que el núcleo no puede marcar un cierre confirmado sin que el campo exista — así que esta fase incorporó únicamente ese campo (una migración aditiva de una sola columna, nullable, sin inferencia retroactiva), dejando cadencia y `PausaGesto` intactos para la Fase 3, tal como se pidió explícitamente.

**Qué se cambió:**

- `ProsocheDiario.cierre_confirmado_en` (`DateTimeField null=True blank=True`) + propiedad `esta_cerrado` — migración `0021_prosochediario_cierre_confirmado_en.py`, aditiva, sin tocar filas existentes.
- Nuevo servicio `diario/services/cierre_service.py::persistir_nucleo_cierre()`, decorado con `@transaction.atomic`. Agrupa, en este orden: (1) `SeguimientoVires` (con su try/except local de `ValueError`/`TypeError` ya existente, preservado tal cual), (2) `entrada.reflexiones_dia` si hay texto, (3) sincronización de `RegistroGesto` vía `HabitosService.toggle_dia` (con su try/except local de JSON malformado, preservado tal cual), (4) marcador `cierre_confirmado_en`, escrito solo si era `None` (idempotente).
- `presencia_cierre` (`views.py`) reordenada: la llamada al núcleo ahora ocurre primero, seguida de `_construir_habitos_con_estado()`, y solo después el enriquecimiento JOI/Gemini y la comprobación de Simbiosis — antes estaban intercalados. Verificado que ningún paso de JOI/Simbiosis lee estado de hábitos o de `SeguimientoVires`, así que el reordenamiento no cambia ninguna salida observable del "camino feliz".
- Eliminado el bucle de sincronización de hábitos y el parseo de `habitos_completados` que vivían directamente en la vista — ahora viven exclusivamente dentro del servicio.

**Qué NO se cambió:**

- Los dos `try/except` locales (fricción no numérica, JSON de hábitos malformado) se conservaron *dentro* del bloque atómico, a propósito: capturar la excepción ahí evita que un dato malformado haga rollback del resto del núcleo — exactamente el comportamiento de antes, ahora con la garantía añadida de que un fallo *no capturado* sí revierte todo.
- No se tocaron cadencia, `PausaGesto`, `habito_reactivar` ni ningún analizador — tal como se pidió.
- No se tocó el `get_or_create` de `ProsocheDiario` al inicio de la vista (se sigue ejecutando también en GET) — es un problema ya documentado (§ auditoría de cierre), pero no es parte del alcance de esta fase.

**Tests añadidos** (`diario/tests_fase2_nucleo_transaccional.py`, 5 tests):

- Camino feliz: persiste las cuatro piezas y marca el cierre.
- Fricción no numérica y JSON de hábitos malformado no bloquean el resto del núcleo (dos tests que reproducen exactamente el comportamiento previo — uno de ellos detectó que mi primera versión del test asumía mal que `SeguimientoVires` no llegaba a crearse con fricción inválida; `get_or_create()` ya persiste la fila antes de que falle la conversión, así que la fila existe con `nivel_estres=None`. Corregido antes de dar la fase por buena, no es un bug del código — era una aserción incorrecta en el test).
- **Rollback parcial**: un fallo simulado a mitad de la sincronización de hábitos (segundo de dos gestos) revierte también la reflexión, el `SeguimientoVires` y el `RegistroGesto` del *primer* gesto, que había llegado a escribirse físicamente en la base de datos antes del fallo.
- **Idempotencia**: cerrar dos veces el mismo día conserva el `cierre_confirmado_en` de la primera vez, aunque el resto del contenido (reflexión, hábitos) sí se actualice.

**Validación ejecutada:**

- `python3 manage.py check` — limpio (mismos 2 warnings preexistentes de Fase 1, no relacionados).
- `python3 manage.py test diario.tests_fase2_nucleo_transaccional` — 5/5, `OK`.
- `python3 manage.py test diario` — suite completa, **115/115 tests, `OK`** (110 preexistentes + 5 nuevos), sin regresiones sobre el comportamiento ya cubierto por los tests de `tests_gestos_2e_cierre.py` y compañía.

**Fase 3 completada** (2026-07-18) — ver §12.

---

## 12. Registro de ejecución — Fase 3 (completada, 2026-07-18)

**Qué se cambió:**

- `Gesto`: nuevos campos `tipo_cadencia` (choices, default `'libre'`), `frecuencia_semanal_objetivo` (`PositiveSmallIntegerField`, null), `dias_semana_objetivo` (`JSONField`, default `[]`), `cadencia_configurada_en` (`DateField`, null). Migración `0022_gesto_cadencia_configurada_en_and_more.py` — aditiva, todo `Gesto` existente queda en `tipo_cadencia='libre'`, `cadencia_configurada_en=null`, satisfaciendo la migración pedida sin necesitar un `RunPython` — los defaults del campo ya lo garantizan.
- `Gesto._validar_invariantes_cadencia()` — implementa la tabla de invariantes del §2.2 exacta; se invoca desde `clean()` (para que Forms/Admin la respeten de forma estándar) y explícitamente desde `configurar_cadencia()`. Deliberadamente **no** se llama `full_clean()` desde `save()` — eso habría activado validación de *todos* los campos (incluida `unique_together`) en cualquier `Gesto.objects.create()` existente en el código, un cambio de alcance mucho mayor que "invariantes de cadencia".
- `Gesto.DIAS_SEMANA_VALIDOS` — lista fija (`lunes`…`domingo`, sin acentos), no dependiente de locale, con el mismo criterio que evitó el riesgo de `ProsocheMes.mes = hoy.strftime('%B')` señalado en la auditoría de cierre.
- `Gesto.save()` — override mínimo: si el `Gesto` es nuevo (`_state.adding`) y se crea ya con una cadencia distinta de `libre`, fija `cadencia_configurada_en = fecha_inicio` (caso 1 del §2.2).
- `Gesto.configurar_cadencia(tipo_cadencia, frecuencia_semanal_objetivo=None, dias_semana_objetivo=None)` — cubre los casos 3 y 4 del §2.2 (primera configuración explícita y cambio posterior son el mismo código: ambos fijan `cadencia_configurada_en = hoy`). Valida antes de guardar; si la combinación es inválida, no persiste nada.
- `PausaGesto` — modelo nuevo, intervalo semiabierto, con `models.UniqueConstraint(condition=Q(fecha_fin__isnull=True))` para que **la base de datos**, no solo el código de aplicación, impida más de una pausa abierta por `Gesto`.
- `HabitosService.pausar_gesto()` / `.reactivar_gesto()` / `._cerrar_pausa_abierta()` — orquestan `Gesto.estado` + `PausaGesto` juntos. `reactivar_gesto` y `_cerrar_pausa_abierta` colapsan (borran) la pausa si se cierra el mismo día que se abrió.
- `views_habitos.py`: `habito_pausar` y `habito_cerrar` ahora usan el servicio; `habito_cerrar` cierra cualquier pausa abierta antes de fijar `estado='cerrado'`. Nueva vista `habito_reactivar` (solo actúa si `estado='pausado'`, 404 en cualquier otro caso). Nueva ruta `habitos/<id>/reactivar/`.
- `habito_toggle_dia` (AJAX): el `get_object_or_404` ahora exige `estado='activo'` — un intento de marcar un hábito pausado o cerrado devuelve `{'success': False, ...}` en vez de crear un `RegistroGesto` en una fecha que la taxonomía del contrato clasificaría como `pausado`/`fuera_de_vida`.
- `PausaGesto` registrado en el admin, junto a `Gesto`/`RegistroGesto` (ya estaban).

**Qué NO se cambió, y por qué:**

- No hay ningún botón ni formulario en `habitos_dashboard.html` para configurar cadencia ni para reactivar — los endpoints/servicios existen y están probados, pero no hay UI que los dispare todavía. No estaba en el alcance declarado de esta fase (que era modelo + transiciones, no interfaz).
- No se tocó `insights_engine.py` ni se implementó ninguna métrica — tal como se pidió explícitamente.
- No se migró ningún `Gesto` legacy a una cadencia distinta de `libre` — la migración es deliberadamente conservadora, igual que con `cierre_confirmado_en` en la Fase 1.
- `get_racha_actual()` sigue sin saber nada de pausas ni cadencia — un `Gesto` `semanal` pausado y reactivado seguirá mostrando una racha calculada como si fuera diario. Es la misma inconsistencia ya documentada en §7.3, no se amplía ni se corrige aquí.

**Tests añadidos** (`diario/tests_fase3_cadencia_pausas.py`, 33 tests): migración (2), los cuatro casos de `cadencia_configurada_en` (4), invariantes de validación — una por cada combinación válida/inválida de la tabla del §2.2 (14), transiciones de `PausaGesto` incluida la restricción de base de datos (8), casos límite de `habito_toggle_dia`/`habito_reactivar` sobre hábitos pausados/cerrados/activos (5).

**Validación ejecutada:**

- `python3 manage.py check` — limpio (mismos 2 warnings preexistentes).
- `python3 manage.py test diario.tests_fase3_cadencia_pausas` — 33/33, `OK`.
- `python3 manage.py test diario` — suite completa, **148/148 tests, `OK`** (115 previos + 33 nuevos), sin regresiones.

**Fase 4 completada** (2026-07-18) — ver §13.

---

## 13. Registro de ejecución — Fase 4 (completada, 2026-07-18)

**Qué se creó:**

`diario/services/analizador_gestos.py` — servicio único, sin integración con ninguna vista/plantilla/insight. Estructura:

- `EstadoDia` / `MotivoNoCalculable` — constantes (enum interno), no texto libre, tal como exigía el alcance.
- `construir_ledger_diario(gesto, desde, hasta)` — el clasificador temporal canónico del §5.1: precedencia `fuera_de_vida > pausado > no_observado > (refinado por cadencia)`. Confirmado que los cierres anteriores a la introducción de `cierre_confirmado_en` quedan `no_observado` sin tratamiento especial — se deriva solo del filtro `cierre_confirmado_en__isnull=False`, tal como pedía el alcance.
- 13 funciones de métrica (`apariciones`, `densidad_sobre_dias_observados_activos`, `intervalo_mediano_activo`, `intervalo_maximo_activo`, `regularidad`, `dias_activos_desde_ultima_aparicion`, `comparacion_entre_periodos`, `oportunidades_previstas`, `oportunidades_cumplidas`, `adherencia`, `evaluacion_semanal`, `incumplimientos_observados`, `recuperacion`), todas devolviendo la estructura trazable exacta del §4 (`valor`/`confianza`/`motivo_no_calculable`/`explicacion`), y todas decoradas con `@requiere_cultivo` (rechazan `tipo='suelto'` con `motivo_no_calculable='tipo_no_cultivo'`).
- `metrica_contextual()` — declara las 6 métricas de §5.4 como `sin_modelo_de_captura`, sin inferir nada.

**Dos hallazgos reales durante la implementación (no solo bugs de test):**

1. **`Gesto.fecha_inicio = models.DateField(default=timezone.now)`** — el default es un `datetime`, no un `date`. Django lo normaliza al escribir en la base de datos, pero un `Gesto` recién creado en memoria sin recargar (`Gesto.objects.create(...)` sin `refresh_from_db()`) conserva el `datetime` crudo, y compararlo con un `date` lanza `TypeError`. Corregido con una normalización defensiva (`_como_fecha()`) dentro del analizador, **sin tocar el modelo** — está fuera del alcance declarado de esta fase, y la normalización local es suficiente para que el analizador sea robusto a esto sin depender de que quien lo llame siempre recargue desde BD primero. Queda anotado como candidato a arreglo mínimo futuro (`default=timezone.localdate`), no urgente.
2. **El ejemplo de M3/M4 de Hábito D en el dataset de referencia (§6, v0.1/v0.2) estaba mal calculado** — trataba el delta natural entre fechas como si fuera también el "intervalo activo", cuando el intervalo activo es el nº de días *estrictamente entre* dos fechas que no son pausado/fuera_de_vida (un día menos que el delta cuando no hay pausas). El ejemplo dedicado de pausa de M4 ya aplicaba la definición correcta (activo=1) desde v0.2, pero nadie había ejecutado el ejemplo de D contra esa misma definición hasta implementar el código. Corregido en §6: mediana 5 (no 6), máximo 7 (no 8). Encontrado escribiendo el test contra el dataset, no en una auditoría de lectura — la clase de hallazgo que este contrato existe para producir.

**Qué NO se tocó** (tal como se acotó explícitamente): `insights_engine.py`, dashboard, plantillas, badges, `get_racha_actual()`, formularios/botones, JOI, dominio `suelto`. La salida de todas las funciones es una estructura de datos — ninguna genera una frase.

**Tests añadidos** (`diario/tests_fase4_analizador_gestos.py`, 33 tests):

- `DatasetReferenciaTestCase` reproduce los Hábitos A/B/C/D completos del §6 y verifica las cifras exactas del contrato (incluida la corrección de M3/M4).
- Casos límite pedidos explícitamente: registro dentro de una pausa retroactiva, registro/día posterior a `fecha_cierre`, hábito histórico con `cadencia_configurada_en=null`, cambio de cadencia con corte del pasado (verificado que meses de historial bajo la cadencia anterior no se cuelan en `evaluacion_semanal` tras el cambio), dos ventanas con cobertura muy distinta (M7 baja la confianza), intervalo que atraviesa una pausa (el ejemplo literal del contrato), semana parcial alcanzable que cumple y que no cumple, semana parcial no alcanzable, semana en curso, recuperación diaria/días concretos/semanal, hábito libre con cero cierres confirmados (`valor=0` con `confianza='insuficiente'`, nunca `None` silencioso), y rechazo explícito de `tipo='suelto'` en las seis métricas representativas.
- Durante la escritura de los tests se corrigió también un bug real en `_contar_recuperaciones()`: incumplimientos consecutivos no incrementaban el contador de oportunidades transcurridas (solo se detectó al trazar a mano la recuperación semanal del Hábito B). Corregido antes de ejecutar la suite.

**Validación ejecutada:**

- `python3 manage.py test diario.tests_fase4_analizador_gestos` — 33/33, `OK` (tras corregir los dos hallazgos de arriba y dos errores propios en las expectativas de los tests, documentados en línea en el propio archivo de tests).
- `python3 manage.py test diario` — suite completa, **181/181 tests, `OK`** (148 previos + 33 nuevos), sin regresiones.

**Fase 4.1 completada** (2026-07-18, antes de abrir Fase 5) — ver §14.

---

## 14. Registro de ejecución — Fase 4.1 (completada, 2026-07-18)

Fase mínima e intermedia, deliberadamente separada de la Fase 5 para no mezclar una corrección de modelo con la integración del analizador.

**Qué se cambió:**

- `Gesto.fecha_inicio`: `default=timezone.now` → `default=timezone.localdate` (el *callable*, sin paréntesis — con paréntesis se evaluaría una sola vez al importar el módulo, no por instancia). Migración `0023_alter_gesto_fecha_inicio.py`.
- **Verificado que la migración es solo de estado**: `sqlmigrate diario 0023` muestra que SQLite reconstruye la tabla (patrón habitual de Django en SQLite para `AlterField`), pero el `INSERT INTO ... SELECT ...` copia `fecha_inicio` tal cual desde la tabla vieja — no aplica el nuevo default a ninguna fila existente. El `CREATE TABLE` tampoco declara el default a nivel de SQL (Django aplica los defaults en Python antes del INSERT, no vía `DEFAULT` de la columna). Confirmado con un test dedicado (`MigracionNoAlteraDatosExistentesTestCase`): una `fecha_inicio` explícita persistida antes de la migración se recarga idéntica después.
- La normalización defensiva del analizador (`_como_fecha()`) se mantiene sin cambios — deja de ser el mecanismo principal, pero sigue protegiendo frente a instancias antiguas, factories o asignaciones manuales incorrectas (verificado con un test que fuerza un `datetime` a mano sobre `fecha_inicio` después de crear el `Gesto`, y confirma que el analizador lo sigue tolerando).

**Qué NO se tocó**: `insights_engine.py`, UI, rachas, formularios — tal como se acotó.

**Tests añadidos** (`diario/tests_fase4_1_saneamiento_fecha_inicio.py`, 7 tests): `Gesto()` recién instanciado sin guardar ya tiene un `date` (no un `datetime`); `Gesto.objects.create()` conserva el mismo tipo antes y después de `refresh_from_db()`; el default es efectivamente "hoy"; el analizador sigue aceptando defensivamente un `datetime` asignado a mano sin romperse; y la migración no altera una `fecha_inicio` ya persistida.

**Validación ejecutada:**

- `python3 manage.py test diario.tests_fase4_1_saneamiento_fecha_inicio` — 7/7, `OK`.
- `python3 manage.py test diario` — suite completa, **188/188 tests, `OK`** (181 previos + 7 nuevos), sin regresiones.

---

## 15. Próximo paso — Fase 5

Orden recomendado, sin abrir todavía:

1. Retirar el cálculo propio de `insights_engine.py` para `Gesto` `cultivo`.
2. Hacer que consuma exclusivamente el analizador (`diario/services/analizador_gestos.py`).
3. Aplicar la política de rachas de §3bis/§7.3: conservar `get_racha_actual()`/`InsigniasService` solo para `tipo_cadencia='diaria'`, ocultar para `libre`/`semanal`/`dias_concretos`.
4. UI mínima: configurar cadencia, pausar, reactivar (los servicios ya existen desde Fase 3 — falta el botón/formulario).
5. Integrar primero datos estructurados y copy conservador — no frases entusiastas antes de que el dato lo sostenga.
6. Probar explícitamente que no aparezcan contradicciones entre superficies (p. ej. que `insights_engine` y el analizador no digan cosas distintas del mismo hábito el mismo día).

**Fase 5A completada** (2026-07-18) — ver §16. Quedan pendientes 5B (UI de gestión) y 5C (presentación y lenguaje), ninguna de las dos abierta.

---

## 16. Registro de ejecución — Fase 5A (completada, 2026-07-18)

**Barrido previo** (obligatorio antes de tocar nada): `grep` de `periodo_observacion_dias|get_racha_actual|mejor_racha|generar_insights_basicos|verificar_insignias_habito` en todo `diario/` (excluidas migraciones y tests). Inventario completo de superficies con progreso/racha/insignias para `Gesto`: `insights_engine.py` (cálculo propio de % + insight de racha para `suelto`), `views_habitos.py::habitos_dashboard` (racha + `mejor_racha` sin condición), `habitos_dashboard.html` (renderiza ambos), `HabitosService.generar_insights_basicos` (mensaje de racha), `InsigniasService.verificar_insignias_habito` (insignias por días acumulados).

**Qué se cambió:**

- `insights_engine.py`: el bloque de progreso para `Gesto` `cultivo` (antes `registros_mes / periodo_observacion_dias`) se sustituyó por `_insight_progreso_cultivo()`, que llama exclusivamente a `analizador_gestos` y elige la métrica por cadencia: `libre` → M2 para la puerta de confianza + M1 para el mensaje (solo apariciones, sin porcentaje); `diaria`/`dias_concretos` → M10 (adherencia); `semanal` → M11, usando únicamente `semanas_completas`/`semanas_cumplidas` (las parciales nunca entran en el mensaje). Sin insight si la confianza de la métrica relevante es `'insuficiente'`. Copy deliberadamente mínimo (`tipo='info'` siempre, sin "¡Excelente!"/"Refuerza" ni umbrales de éxito/aviso) — el lenguaje conservador definitivo es competencia de la Fase 5C, no de esta; no tenía sentido escribir copy que 5C tendría que rehacer.
- `HabitosService.generar_insights_basicos`: el mensaje de racha para `cultivo` ahora solo se genera si `tipo_cadencia == 'diaria'`. El de `suelto` queda sin cambios (no tiene cadencia).
- `views_habitos.py::habitos_dashboard`: `racha` y el nuevo `mejor_racha_visible` se calculan como 0 (ocultos) salvo `tipo == 'suelto'` o `tipo_cadencia == 'diaria'`.
- `habitos_dashboard.html`: la sección de `cultivo` pasa de leer `item.habito.mejor_racha` directamente a leer `item.mejor_racha_visible` (ya gateado por la vista). La sección de `suelto` no se tocó — sigue leyendo `item.habito.mejor_racha` sin condición, correcto porque `suelto` no tiene cadencia.

**Qué NO se tocó, y por qué:**

- `InsigniasService` (insignias por días acumulados, `habito_positivo_7dias`, `habito_positivo_66dias`, etc.) — revisado, no modificado. Usa `registros.filter(estado='cumplido').count()` (total histórico, sin excluir `pausado`/`fuera_de_vida`), un criterio distinto tanto de M1 (que sí excluye esos días) como de la política de rachas. Es un sistema de gamificación (hitos acumulados), no una lectura analítica de continuidad — no compite con "adherencia" ni "densidad" de forma que pueda contradecirlas visiblemente hoy. Queda flagged como candidato a la misma política de rachas (ocultar para no-diaria) en una fase posterior, no resuelto aquí para no ampliar el alcance de 5A más allá de "insights_engine + racha".
- No se tocó la asimetría ya conocida de que `InsigniasService` solo se verifica desde `habito_toggle_dia` (AJAX del dashboard), no desde `presencia_cierre` — es una desconexión técnica anterior a este contrato, no forma parte del alcance de coherencia analítica de 5A.
- Ningún formulario, botón ni copy nuevo más allá del mínimo del insight — tal como se acotó. Configurar cadencia, pausar y reactivar desde la UI siguen sin tener ningún punto de entrada (Fase 5B).

**Tests añadidos** (`diario/tests_fase5a_fuente_canonica.py`, 17 tests): que `_insight_progreso_cultivo` seleccione la métrica correcta por cadencia y no genere nada con confianza insuficiente (7 tests, incluida una prueba explícita de que una única semana completa no evaluable no se disfraza mezclando semanas parciales); la política de rachas en las cuatro combinaciones de cadencia más `suelto` (5 tests); `generar_insights_basicos` respetando la misma política (3 tests); y dos tests de contradicción entre superficies que verifican, para el mismo `Gesto`, que ninguna de las tres superficies (`insights_engine`, `generar_insights_basicos`, `habitos_dashboard`) menciona "racha" cuando no aplica, y que ninguna inventa una cifra cuando no hay confianza suficiente.

Durante la escritura de los tests se encontraron y corrigieron dos bugs propios (no del código de producción): dos tests llamaban a `gesto.configurar_cadencia()` inmediatamente después de crear el `Gesto` ya con su cadencia definida en `objects.create(...)` — como `configurar_cadencia()` usa `timezone.localdate()` real (no la fecha simulada del test), esa llamada redundante reiniciaba `cadencia_configurada_en` a la fecha real de ejecución de los tests, invirtiendo la ventana de cumplimiento. Corregido eliminando la llamada redundante — el caso 1 del §2.2 (`Gesto.save()`) ya deja `cadencia_configurada_en` correcto al crear el gesto con una cadencia elegida.

**Validación ejecutada:**

- `python3 manage.py test diario.tests_fase5a_fuente_canonica` — 17/17, `OK`.
- `python3 manage.py test diario` — suite completa, **205/205 tests, `OK`** (188 previos + 17 nuevos), sin regresiones.

**Fase 5B completada** (2026-07-18) — ver §17. Fase 5C (presentación y lenguaje) no iniciada.

---

## 17. Registro de ejecución — Fase 5B (completada, 2026-07-18)

**Qué se creó/cambió:**

- `CadenciaGestoForm` (`forms.py`) — no es `ModelForm`: reutiliza literalmente `Gesto._validar_invariantes_cadencia()` dentro de `clean()` (construye un `Gesto` temporal sin guardar y llama al mismo método que usa el modelo), en vez de duplicar las reglas — formulario y modelo no pueden divergir por construcción.
- `habito_configurar_cadencia` (`views_habitos.py`) — nueva vista, solo para `tipo='cultivo'` (404 en `suelto`). Flujo de dos pasos para la advertencia: si `cadencia_configurada_en` ya existía y los valores cambian de verdad, se vuelve a renderizar el mismo formulario con un aviso y no se persiste nada hasta reenviar con `confirmado=1`. Nueva ruta `habitos/<id>/cadencia/`.
- `HabitosService.obtener_gestos_por_tipo` — ahora incluye `estado='pausado'` para `cultivo` (para poder verlos y reactivarlos), pero deja `suelto` exactamente como estaba (`estado='activo'` únicamente) — tal como se pidió mantener la UI de `suelto` fuera de este cambio. Nuevo `obtener_gestos_cerrados_cultivo()` — lectura, sin acciones, porque cerrar es definitivo.
- `habitos_dashboard.html` (sección `cultivo` únicamente): badge "Pausado" junto al nombre; el grid de días deja de tener la clase `dia-toggle` (y por tanto de ser clicable — el `querySelectorAll('.dia-toggle')` del script ni siquiera lo encuentra) cuando el gesto no está `activo`; botón "Reactivar" en vez de "Pausar" cuando está pausado; nuevo enlace "Cadencia"; etiqueta de cadencia configurada (`Diaria`, `3x por semana`, `Días concretos: lunes, miércoles`, `Libre`) — deliberadamente descriptiva, no interpretativa. Nueva sección "Cerrados" (solo lectura). La sección `suelto` no se tocó.
- `views_habitos.py::_cadencia_label()` — helper de texto puramente estructural (qué cadencia hay configurada), no analítico — no es la frase conservadora de la Fase 5C, es metadata de configuración.

**Qué NO se tocó:** ninguna frase analítica nueva (ninguna referencia a M1-M13 en esta fase), ni rediseño de presentación — ambos quedan para 5C, tal como se acotó.

**Bug propio encontrado y corregido antes de dar la fase por buena** (no de Fase 3, de la vista nueva): la vista llamaba a `gesto.configurar_cadencia(...)` incluso cuando el formulario se reenviaba con los mismos valores (sin cambio real). Como `configurar_cadencia()` siempre reinicia `cadencia_configurada_en` a hoy por diseño de Fase 3, esto desplazaba el ancla del análisis sin que hubiera ningún cambio que lo justificara. Corregido en la vista (no en el modelo): solo se llama a `configurar_cadencia()` si es la primera configuración o si hay un cambio real; un reenvío idéntico no escribe nada.

**Tests añadidos** (`diario/tests_fase5b_ui_gestion.py`, 20 tests): formulario (9 — las mismas combinaciones válidas/inválidas del §2.2, vía HTTP); permisos (3 — login requerido, no acceso a gesto ajeno, 404 sobre `suelto`); advertencia de reinicio (4 — primera configuración sin aviso, cambio real con aviso y sin persistir hasta confirmar, confirmación sí persiste, reenvío idéntico sin aviso ni escritura); transiciones visibles en el dashboard (4 — pausar/reactivar/cerrar reflejados con claridad, grid no interactivo cuando no está activo).

**Validación ejecutada:**

- `python3 manage.py makemigrations --check --dry-run` — sin cambios pendientes (fase sin modelo nuevo).
- `python3 manage.py test diario.tests_fase5b_ui_gestion` — 20/20, `OK`.
- `python3 manage.py test diario` — suite completa, **225/225 tests, `OK`** (205 previos + 20 nuevos), sin regresiones.

**Fase 5C completada** (2026-07-18) — ver §18. Con esto, las tres subfases de la Fase 5 quedan cerradas.

---

## 18. Registro de ejecución — Fase 5C (completada, 2026-07-18)

**Qué se creó:**

- `insights_engine.py::lectura_principal_cultivo(gesto, fecha_referencia)` — la única lectura visible por hábito `cultivo`, sustituyendo/ampliando `_insight_progreso_cultivo` de la Fase 5A (que ahora es un adaptador delgado sobre esta función, usado solo por el feed de insights). Selecciona la métrica por cadencia exactamente como se pidió: `libre` → M2 (densidad, puerta de confianza) + M1 (apariciones, texto); `diaria`/`dias_concretos` → M10 (adherencia) + M8/M9 (para mostrar "X de Y oportunidades"); `semanal` → M11, usando solo `semanas_completas`/`semanas_cumplidas` para la lectura principal. Cuatro tipos de lectura con etiqueta explícita (`Descriptivo`, `Cumplimiento`, `Semana parcial`, `No evaluable`) más `Datos insuficientes` — nunca mezclados en el mismo texto.
- `_nota_semana_actual()` — para `semanal`, añade una nota **aparte** (nunca mezclada en la tasa principal) sobre la semana en curso, la última semana parcial alcanzable, o la última semana no evaluable, en ese orden de prioridad.
- Trazabilidad mínima expuesta en cada lectura `ok`: periodo (desde/hasta) y total de días excluidos (pausado + no observado), derivados de la `explicacion` que el analizador ya devuelve — sin inventar un cálculo nuevo.
- `az.ventana_cumplimiento` — renombrada de `_ventana_cumplimiento` (antes privada) para poder reutilizarla desde `insights_engine.py` sin duplicar la lógica de "desde cuándo cuenta el cumplimiento".
- `habitos_dashboard.html` (sección `cultivo`): nuevo bloque de lectura principal, con la etiqueta de tipo, el texto, la nota secundaria si existe, y un `<details>` nativo (sin JS adicional) con la trazabilidad — periodo y nº de días excluidos.

**Barrido de copy existente** (tal como pedía la fase):

- `insights_engine.py`: reescrito, ya reportado arriba.
- `habitos_dashboard.html`: `item.insights` (el mensaje de racha de `HabitosService.generar_insights_basicos`) **nunca se renderiza en ningún template** — es una computación muerta desde el punto de vista de la UI. No se eliminó (fuera del alcance de esta fase, y podría usarse en el futuro), pero queda documentado: la política de rachas de la Fase 5A ya lo protegía correctamente aunque hoy no sea visible en ningún sitio.
- **Hallazgo real, deliberadamente no corregido**: `diario/templates/diario/analisis_habitos_completo.html` (servido por `analisis_habitos_mes_actual`, `/diario/analisis-habitos/`, enlazado desde `analisis_habitos_historico.html` y `analisis_habitos_anual.html`) contiene exactamente el lenguaje que este contrato prohíbe — "¡Excelente trabajo! Vas muy bien con este hábito. Mantén el ritmo.", racha y "Consistencia" (%) sin cadencia, todo con umbrales de color éxito/aviso. **No se tocó**: esa vista opera enteramente sobre `ProsocheHabito`/`ProsocheHabitoDia` (el sistema legacy), no sobre `Gesto` — no es una superficie del dominio que cubre este contrato, igual que `ProsocheHabito` ha quedado fuera de alcance en todas las fases anteriores. Queda flagged como una decisión pendiente real para otra conversación: retirar la página, redirigirla al nuevo dashboard, o migrarla — no es una tarea de "revisar copy", es una decisión de producto sobre qué hacer con todo un sistema legacy paralelo.
- `InsigniasService`: verificado que no se renderiza en ningún lugar visible de `habitos_dashboard.html` ni de su plantilla base — no hay contradicción visible real que justifique tocarlo, tal como exigía la condición explícita de la fase. No modificado.

**Qué NO se tocó:** `InsigniasService` (condición cumplida: sin contradicción visible), `ProsocheHabito`/`analisis_habitos_completo.html` (fuera de dominio, no de "falta de tiempo"), ningún rediseño estructural de la página — solo un bloque nuevo dentro de la tarjeta existente.

**Tests añadidos** (`diario/tests_fase5c_presentacion_lenguaje.py`, 10 tests): lista de frases prohibidas (mejorando/empeorando, compromiso, abandono, racha, causal, ánimo genérico) verificada contra las tres cadencias con datos suficientes; confianza insuficiente para gestos recién creados en las tres cadencias (siempre el mismo texto exacto, nunca relleno genérico); días pausados reflejados en la trazabilidad; semana parcial alcanzable y no evaluable como nota aparte, nunca mezcladas en el texto principal; hábito libre usando "Apareció" en vez de cualquier lenguaje de cumplimiento.

**Validación ejecutada:**

- `python3 manage.py makemigrations --check --dry-run` — sin cambios pendientes (fase sin modelo nuevo).
- `python3 manage.py test diario.tests_fase5c_presentacion_lenguaje` — 10/10, `OK`.
- `python3 manage.py test diario` — suite completa, **235/235 tests, `OK`** (225 previos + 10 nuevos), sin regresiones.

**Estado del contrato tras Fase 5C**: las cinco fases principales (1, 2, 3, 4, 5) y la fase intermedia 4.1 están completas y verificadas. El analizador es la fuente canónica para `Gesto` `cultivo`, con UI de gestión funcional y lenguaje conservador trazable. Quedan como decisiones pendientes reales, no resueltas por este contrato: el destino de `analisis_habitos_completo.html`/legacy `ProsocheHabito`, el rediseño de insignias por cadencia (§3bis/§7.3), y los umbrales de confianza/regularidad sin validar con datos reales (§4).

---

## 19. Contrato dado por implementado (2026-07-18)

Las fases 1 → 5C quedan cerradas. El flujo conceptual final:

```
RegistroGesto ── ProsocheDiario ── PausaGesto ── Cadencia
                         │
                 AnalizadorGestos
                         │
              lectura_principal_cultivo()
                         │
                Dashboard · Insights
```

Una sola fuente de verdad analítica para `Gesto` `cultivo`. El cambio de fondo no fue añadir cadencias o pausas — fue que el dominio dejó de responder "¿cuántos días seguidos llevas?" para responder "¿qué puedo afirmar con los datos que realmente tengo?".

**No se abre una Fase 6 todavía.** Antes de considerar el trabajo sellado, toca un periodo de **Post-implementación**: 2-3 semanas de uso real, sin añadir funcionalidad, registrando únicamente fricción — no features. Se valida el contrato contra una persona usándolo, no contra los tests.

### Qué registrar durante el periodo de observación

Cualquier situación del tipo:
- "esto no se entiende"
- "la lectura sorprende"
- "esperaba otra cosa"
- "la confianza era demasiado optimista" (o pesimista)
- "la semana parcial confunde"
- "nunca miro el `<details>` de trazabilidad"
- "esta métrica no me aporta nada"

### Anotaciones

**2026-07-18 — Despliegue a producción, hallazgo confirmado (no post-implementación de uso, sino del propio despliegue)**: `PausaGesto.Meta.constraints` usa `UniqueConstraint(condition=Q(fecha_fin__isnull=True))`, que solo `sqlmigrate` había mostrado como "descartada en silencio" contra MySQL (§13 mencionaba el riesgo sin confirmarlo). Al aplicar `migrate` en producción (MySQL, PythonAnywhere), Django lo confirmó explícitamente: `models.W036: MySQL does not support unique constraints with conditions. A constraint won't be created.` — no es un error, la migración se aplicó limpia, pero la tabla `diario_pausagesto` en producción **no tiene** la restricción a nivel de base de datos que sí existe en SQLite (dev/tests).

Decisión tomada en el momento (opción elegida conscientemente, no por defecto): seguir adelante. El único punto de escritura de `PausaGesto` es `HabitosService.pausar_gesto()`, que ya comprueba antes de crear si hay una pausa abierta — la protección de aplicación cubre el único camino real que existe hoy. El hueco solo importaría si algo creara una `PausaGesto` saltándose el servicio (admin, shell).

Pendiente real, no urgente: o bien (a) quitar la restricción condicional del modelo para que el contrato deje de afirmar una garantía que en producción no existe — y ajustar el test `test_pausa_abierta_duplicada_viola_restriccion_de_base_de_datos` (`tests_fase3_cadencia_pausas.py`) para que dependa del entorno, o (b) implementar el equivalente compatible con MySQL (p. ej. una columna generada que sea `NULL` salvo cuando `fecha_fin IS NULL`, con un índice único sobre ella — MySQL sí permite múltiples `NULL` en una columna única). Ninguna de las dos se ha hecho todavía.

De esta lista saldrá, si acaso, una fase de ajuste de UX/calibración — con motivo real, no anticipado. Hasta entonces, el contrato queda como está.

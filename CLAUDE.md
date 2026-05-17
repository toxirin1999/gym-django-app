# CLAUDE.md — Gym Django App

This file provides context for AI assistants working on this codebase.

---

## AGENTES Y DELEGACIÓN DE COSTES

Hay tres subagentes en `.claude/agents/`. Úsalos para optimizar coste y velocidad.

### Reglas de delegación

| Tarea | Agente | Cuándo NO usarlo |
|---|---|---|
| Buscar archivos, leer código, localizar una función, listar estructura | **haiku-explorer** | — |
| Escribir/modificar vistas, modelos, servicios, templates, tests, bugfix | **sonnet-builder** | — |
| Diseño de arquitectura multi-app, decisión irreversible de modelo de datos, trade-off crítico | **opus-architect** | Para cualquier tarea de código rutinario |

### Regla de oro

```
¿Solo necesito leer o buscar?  → haiku-explorer
¿Necesito escribir o cambiar código? → sonnet-builder
¿La decisión incorrecta costaría días de refactoring? → opus-architect
```

**Opus solo se activa cuando:**
- Se cambia el esquema de BD de forma irreversible
- Se diseña un sistema que cruza ≥3 apps
- Hay un trade-off de rendimiento/seguridad a largo plazo
- Se evalúa si una feature encaja con la visión nuclear

**Opus NO se activa para:** bugfixes, features nuevas bien definidas, templates, migraciones rutinarias, refactoring local.

---

## VISIÓN NUCLEAR — "App viva"

**Esta es la directriz más importante de toda la app.** Tiene dos dimensiones inseparables:

### 1. Entrenador que aprende (backend invisible)

Antes de implementar cualquier feature, hacerse esta pregunta:

> ¿Cómo alimenta este dato al plan? ¿Qué aprende el sistema de esta información?

La app NO es un registrador de entrenos. Es un entrenador que mejora su conocimiento del usuario con cada sesión completada, cada test realizado, cada lesión reportada y cada dato biométrico introducido. Si una feature solo muestra datos sin retroalimentar el plan, está incompleta.

### 2. Entrenador que habla — JOI (frontend visible)

**El usuario tiene que percibir que la app está viva.** No basta con que el sistema aprenda si el usuario no lo nota. JOI es la voz visible de esa inteligencia.

**Principio arquitectónico de JOI:**

> Cuando el sistema aprende algo relevante → JOI lo verbaliza.

JOI NO es un sistema de notificaciones con voz poética. Es la consecuencia visible del aprendizaje. La diferencia:

| ❌ Notificación reactiva | ✅ Voz del aprendizaje |
|---|---|
| "El usuario completó un entreno → enviar mensaje" | "El sistema detectó RPE en descenso 3 sesiones → JOI habla de ello" |
| "Son las 07:30 → enviar apertura" | "Al abrir la app → JOI sintetiza lo que el sistema sabe hoy" |
| Solo habla si hay acción del usuario | Existe independientemente de la actividad del usuario |

**Regla de JOI:** Si el sistema toma una decisión (`GymDecisionLog`, ajuste de fatiga, readiness bajo, estancamiento detectado), JOI debe verbalizarla. El usuario no debería ver el dato en silencio — debería escuchar a JOI nombrarlo.

**JOI siempre está presente al abrir la app.** Si no hay mensaje del día, el context processor lo genera en demanda con todo el contexto disponible. No depende de que Celery haya corrido.

### Orden de implementación JOI (prioridad)

1. **Context processor on-demand** ✅ — `joi_context` genera `apertura_manana` síncronamente si no hay mensaje del día. Celery lo pre-genera antes para evitar latencia; si no corrió, el context processor es el fallback.
2. **Enriquecer `construir_contexto`** ✅ — tendencias de RPE, readiness trend, GymDecisionLog recientes, estancamientos activos, ACWR implementados en `joi/services.py`.
3. **GymDecisionLog → JOI** ✅ — Signal `joi_decision_plan` en `entrenos/signals.py` dispara `generar_mensaje_joi` con trigger `decision_plan` al crear el log. Lock 30 min para evitar spam por sesión.
4. **Apertura con inteligencia real** ✅ — `_prompt_apertura_manana` usa semáforo de intención, paradojas A/B, ACWR, HRV, FC reposo, tendencia RPE 4 semanas, carga unificada, PRs, decisiones del plan, lesión y readiness Hyrox.
5. **Resumen semanal como mensaje JOI** ✅ — Celery task `generar_resumen_semanal_joi` en `joi/tasks.py` genera el mensaje los lunes con datos de `resumen_semanal_service.py`.

### Bucles de aprendizaje activos (implementados)

| Dato de entrada | Qué aprende/ajusta el sistema |
|---|---|
| RPE post-sesión | Reduce volumen si RPE ≥ 9; aumenta si RPE ≤ 5 dos sesiones seguidas |
| Energía pre-entreno | Escala volumen de la sesión al momento |
| Energía pre-sesión (1–10) | Persistida en `EntrenoRealizado.energia_pre_sesion`; aparece en resumen semanal |
| Técnica por serie (Buena/Aceptable/Comprometida) | Si comprometida → bloquea subida de peso y crea `GymDecisionLog accion=mantener` |
| Tope de máquina | Congela peso; progresa reps desde las reales (+1, no desde el plan); badge +2.5 kg siguiente sesión |
| Molestia recurrente (misma zona ≥3 sesiones/21 días) | `GymDecisionLog accion=cambiar_variante` para reducir carga en esa zona |
| Sin progresión en peso+reps (3 sesiones) | `GymDecisionLog accion=cambiar_variante`; badge ⚡ Estancado en entrenamiento activo |
| Récords personales rotos | Aparecen en resumen semanal del panel principal |
| Test 5K completado | Recalibra ritmos Z2/tempo en todas las sesiones futuras de carrera |
| Simulación completa/oficial | Detecta estaciones >25% sobre objetivo → añade sesiones correctivas |
| Lesión activa | Filtra ejercicios con tags incompatibles en tiempo real |
| Sesiones completadas | Actualiza readiness breakdown (fuerza, resistencia, potencia) |
| Actividades por estación | Alimenta CompetitionStandardsService para tracking vs estándares |

### Resumen semanal — panel principal

El card "Lo que aprendió el plan" (`entrenos/services/resumen_semanal_service.py`) agrega cada lunes la semana anterior y muestra en el dashboard: sesiones + volumen, PRs, técnica, topes, molestias, RPE medio, energía pre-sesión y decisiones del plan (`GymDecisionLog`). Solo aparece si hubo sesiones esa semana.

### Gaps identificados — estado actual (mayo 2026)

| # | Gap | Estado | Notas |
|---|---|---|---|
| 1 | Actualización automática de RMs | ✅ | Signal `sincronizar_rm_con_hyrox` en `entrenos/signals.py` → actualiza `HyroxObjective` |
| 2 | Tiempo 5K desde carreras libres | ✅ | Dos signals en `hyrox/signals.py` cubren HyroxSession + carrera libre |
| 3 | Calibración de RPE personal | ✅ | Signal `calibrar_rpe_personal` detecta bias RPE vs FC, guarda en `Cliente.one_rm_data['_rpe_bias']` |
| 4 | Deload automático por TSB | ✅ | `DeloadAutoTrigger` en `hyrox/training_engine.py`; umbral TSB < -25, cooldown 14 días |
| 5 | Resumen semanal JOI | ✅ | Celery task `generar_resumen_semanal_joi` en `joi/tasks.py` |
| 6 | Cruce nutrición → Hyrox | — | Nutrición no está en uso activo; pospuesto |
| 7 | Cruce gym sessions → Hyrox | ✅ | Gym penaliza readiness score hasta -12 pts vía TSB y detección de tren inferior (últimas 48h) |
| 8 | Detección estancamiento por estación | ✅ | `StagnationEngine` en `hyrox/training_engine.py` + signal en `hyrox/signals.py` |
| 9 | HRV diario en checkin | ✅ | `hrv_ms` guardado en `HyroxReadinessLog` desde `BitacoraDiaria`; ya influye en el score |
| 10 | Comparativa temporal propia | ✅ | `StagnationEngine` calcula mejora % por estación (mes actual vs anterior) |

### Pendiente real

Todos los gaps identificados están implementados (mayo 2026). El backlog está limpio.

---

## Dashboard Hyrox — arquitectura de decisión (mayo 2026)

### `hyrox_decision` — variable de autoridad soberana

Calculada en `hyrox/views.py` por `_crear_hyrox_decision()`. Prioridad:
1. **Lesión activa** (AGUDA/SUB_AGUDA) → siempre `recuperar`, bloquea el plan
2. **Fatiga fisiológica** (TSB ≤ -20) → `recuperar`
3. **Carga aguda alta** (ACWR ≥ 1.5) → `recuperar`
4. **Readiness bajo** (score < 45) → `sostener`
5. **Normal** → `empujar`

Campos clave: `estado`, `causa`, `puede_ejecutar_plan`, `permitido`, `evitar`, `estaciones_bloqueadas`, `tags_restringidos`.

### Tags de lesión → estaciones bloqueadas

`_normalizar_tags_restringidos()` lee `UserInjury.tags_restringidos` (JSON real de la BD).
`_estaciones_bloqueadas_por_tags()` mapea contra `_HYROX_STATION_RISK_TAGS` usando el vocabulario real:
- `flexion_rodilla_profunda`, `impacto_vertical`, `triple_extension_explosiva`

### Qué se subordina cuando `puede_ejecutar_plan=False`
- **Tarjeta superior**: RECUPERAR con estaciones a evitar
- **Race Command**: decision strip reemplazado por "Sesión protegida"
- **Hero CTA**: "Registrar Recuperación" (→ `reportar_lesion`)
- **Plan semanal**: día de hoy marcado PROTEGIDO, no clicable
- **Morning briefing + smart_alerts**: suprimidos

### Otros campos añadidos
- `HyroxObjective.objetivo_tiempo_total` — objetivo personal de tiempo total Hyrox completo (CharField). Separado de `objetivo_tiempo_carrera` (parcial).
- `_build_race_goal_delta()` — calcula margen/déficit contra objetivo total.
- `_build_hyrox_system_reading()` — lectura narrativa determinística (Python, sin IA): integra decisión + objetivo + limitador.
- `HyroxReadinessLog.hrv_ms` — HRV del día guardado junto al score de readiness.

---

---

## Quick Commands

### Install
```bash
pip install -r requirements.txt
```

### Run (local)
```bash
python3 manage.py runserver --settings=gymproject.settings_local
```

### Run migrations
```bash
python3 manage.py migrate --settings=gymproject.settings_local
```

### Load initial data
```bash
python3 manage.py cargar_datos_estoicos --settings=gymproject.settings_local
python3 manage.py seed_estiramientos --settings=gymproject.settings_local
python3 manage.py crear_pruebas_epicas --settings=gymproject.settings_local
```

### Tests
```bash
python3 manage.py test --settings=gymproject.settings_local
python3 manage.py test hyrox --settings=gymproject.settings_local
```

### Collect static files (producción)
```bash
python3 manage.py collectstatic --settings=gymproject.settings
```

### Celery (tareas async — requiere Redis)
```bash
celery -A gymproject worker --loglevel=info
celery -A gymproject beat --loglevel=info
```

---

## Project Overview

A comprehensive, multi-featured **Django gym and athletic training management platform** targeting personal trainers and athletes. The system combines training management, nutrition planning, AI coaching, gamification, stoic philosophy practice, and competition preparation.

**Live hosting:** PythonAnywhere  
**Tech stack:** Django 5.2, Python 3.13+, MySQL (prod) / SQLite (dev), Celery + Redis, Gemini AI, WhiteNoise

---

## Repository Structure

```
gym-django-app/
├── gymproject/               # Django project config (settings, urls, wsgi)
├── clientes/                 # Client profiles & management
├── rutinas/                  # Workout routine templates & programs
├── entrenos/                 # Training session recording & analysis
├── logros/                   # Gamification, achievements, rankings
├── joi/                      # AI coaching companion (emotional support)
├── analytics/                # Performance metrics, predictions, AI recommendations
├── estoico/                  # Stoic philosophy daily reflections
├── nutricion_app_django/     # Nutrition tracking (Zone diet, pyramid model)
├── diario/                   # Daily journal, habit tracking, Eudaimonia
├── estiramientos/            # Stretching routine library
├── hyrox/                    # Hyrox competition training & injury management
├── core/                     # Shared utilities (bio_context_processor)
├── templates/                # Project-wide base templates
├── static/                   # CSS, JS, images, PWA manifest & service worker
├── templatetags/             # Project-level custom template tags
├── manage.py
├── requirements.txt
├── Procfile                  # Heroku/gunicorn deployment
└── db.sqlite333              # Local SQLite database (dev artifact)
```

---

## Django Project Configuration (`gymproject/`)

### Settings

- **`settings.py`** — Main settings. `DEBUG=True`, `ALLOWED_HOSTS=['*']`. Uses MySQL on PythonAnywhere.
- **`settings_local.py`** — Local overrides; switches DB to SQLite for development.

### Key Settings

| Setting | Value |
|---|---|
| `LANGUAGE_CODE` | `es-mx` |
| `TIME_ZONE` | `America/Mexico_City` |
| `LOGIN_URL` | `/login/` |
| `LOGIN_REDIRECT_URL` | `/redirigir/` |
| Cache backend | File-based, 5 min timeout, 1000 entries max |
| Celery broker | `redis://localhost:6379/0` |
| Static storage | WhiteNoise `CompressedManifestStaticFilesStorage` |

### Installed Apps (custom)

```
clientes, rutinas, entrenos, joi, logros, analytics,
estoico, nutricion_app_django, diario, estiramientos, hyrox
```

Third-party: `widget_tweaks`, `django_celery_beat`

### Context Processors (injected globally)

- `joi.context_processors.joi_context`
- `joi.context_processors.utility_functions`
- `estoico.context_processors.estoico_context`
- `core.bio_context_processor.bio_context`

### URL Mount Points

| Prefix | App |
|---|---|
| `/` (root) | Redirect → `clientes_views.redirigir_usuario` |
| `/diario/` | diario |
| `/clientes/` | clientes |
| `/panel/` | Main dashboard |
| `/rutinas/` | rutinas |
| `/entrenos/` | entrenos |
| `/logros/` | logros |
| `/joi/` | joi |
| `/estoico/` | estoico |
| `/analytics/` | analytics |
| `/nutricion/` | nutricion_app_django |
| `/estiramientos/` | estiramientos |
| `/hyrox/` | hyrox |
| `/api/liftin/` | Liftin external API |

---

## App-by-App Reference

### `clientes` — Client Management

**Core model:** `Cliente` (OneToOne → Django `User`)

Key fields: physical measurements, body fat %, training objective (`hipertrofia | fuerza | perdida_peso | resistencia | general`), experience level, autorregulation metrics (stress, sleep quality, energy), `one_rm_data` (JSON), `historial_volumen` (JSON), preferred/avoided exercises, `dias_disponibles`.

Other models: `BitacoraDiaria`, `EstadoSemanal`, `ObjetivoCliente`, `RevisionProgreso`, `PesoDiario`, `ObjetivoPeso`, `FaseCliente`.

Key views: `panel_cliente`, `dashboard`, `dashboard_adherencia`, `portal_sesion_unificado`, `mapa_energia`, `control_peso_cliente`.

Services: `services.py`, `peso_analytics.py`  
Template tags: `clientes/templatetags/`  
Management commands: `migrar_clientes`

---

### `rutinas` — Routine Templates

Models: `Programa`, `Rutina`, `EjercicioBase`, `EjercicioEnRutina`, `Asignacion`.

`EjercicioBase` stores `risk_tags` as JSON (e.g., `impacto_vertical`, `triple_extension_explosiva`) used by injury safety filters. `progression_type` choices: `peso_reps`, `progresion_reps`, `progresion_tiempo`, `progresion_distancia`, `peso_corporal_lastre`, `progresion_variante`.

---

### `entrenos` — Training Sessions

**Core models:** `EntrenoRealizado`, `EjercicioRealizado`, `EjercicioLiftinDetallado`, `GrupoMuscular`.

`EjercicioRealizado` tracks: weight, series, reps, tempo, RPE, RIR, muscular failure, `is_recovery_load`, injury feedback (`molestia_reportada`, `severidad`, `zona`).

**Services directory** (`entrenos/services/`):
- `estadisticas_service.py` (43 KB) — Volume & stats analysis
- `evaluacion_profesional_service.py` / `_v2.py` (46 KB each) — Professional evaluation
- `logros_service.py` — Achievement triggers from training
- `records_service.py` — Personal records
- `services.py` (37 KB) — Core training logic

**API endpoints** (`urls_api.py`): exercise search, session saving, hot-swap substitution, injury reporting, plan regeneration, bio-correlation, Liftin stats.

**Signals:** `signals.py` fires on training session completion.

Features: hot-swap exercise substitution, RPE/RIR tracking, recovery load detection, volume per muscle group, 1RM estimation, Liftin import/parse.

---

### `logros` — Gamification

**Models:**
- `Arquetipo` — Character tier/level (nivel PK, puntos_requeridos, filosofia)
- `PruebaLegendaria` — Epic challenge (clave_calculo unique key, es_secreta)
- `PerfilGamificacion` — User's gamification state (points, streak, archetype level)
- `PruebaUsuario` — Progress on a legendary trial
- `Quest` / `QuestUsuario` — Mission system (diario/semanal/mensual/especial)
- `HistorialPuntos` — Audit log of every point event
- `Notificacion` — In-app notifications (logro/quest/nivel/general)
- `Liga` — League tiers (Bronze → Legend) with point ranges
- `Temporada` — Seasonal competitions
- `RankingEntry` — Leaderboard entries per season and ranking type
- `TituloEspecial` / `PerfilTitulo` — Special titles

Management commands: `crear_pruebas_epicas`, `resync_gamificacion`, `corregir`

---

### `joi` — AI Coaching Companion

Models: `RecuerdoEmocional`, `EstadoEmocional`, `Entrenamiento`, `Logro`, `EventoLogro`, `MotivacionUsuario`.

Provides emotional support, AI-generated training recommendations, and motivational messages. Integrates with Gemini AI via `services.py`.

Context processors inject JOI data and utility functions globally.

---

### `analytics` — Performance Analytics

**Models:** `MetricaRendimiento`, `AnalisisEjercicio`, `TendenciaProgresion`, `PrediccionRendimiento`, `RecomendacionEntrenamiento`, `ComparativaRendimiento`, `CacheAnalisis`, `MetaRendimiento`, `AnotacionEntrenamiento`, `HistorialFase`.

**Services directory:**
- `ia_*.py` (5 files) — Gemini AI integration for pattern detection, optimization, recommendations
- `planificador*.py` (3 files) — Training planning (Helms framework)
- `analisis_progresion.py`, `analytics_predictivos.py` — Analysis engines
- `autorregulacion.py` / `autorregulacion_actualizado.py` — Self-regulation
- `sistema_progresion_avanzada.py`, `sistema_educacion_helms.py`
- `validador_jerarquia_helms.py` — Helms framework validation
- `monitor_adherencia.py`, `notificaciones.py`

Management commands: `generar_recomendaciones`, `diagnosticar_recomendaciones`, `ver_recomendaciones`, `entrenar_ia`

Features: Helms evidence-based periodization, advanced progression detection, phase-based planning, adherence monitoring, AI recommendations with cache (MD5 hash keyed).

---

### `nutricion_app_django` — Nutrition Tracking

**Zone Diet Block system:** 1 block P = 7 g protein, 1 block C = 9 g carbs, 1 block G = 3 g fat.

**5-level education pyramid:** Each level unlocks progressively advanced nutrition concepts.

**Key models:**
- `PerfilNutricional` — Scientific v2 profile: phase (`definicion/volumen/peak_week/mantenimiento`), Navy Method body fat, safety locks (min protein/fat per kg), massa_magra_kg
- `TargetNutricionalDiario` — Daily block prescription per day type (gym/hyrox/descanso)
- `CheckNutricionalDiario` — Compliance check-in with biofeedback (fatigue, sleep, energy, hunger)
- `RegistroBloques` — Actual food logged per meal
- `InformeOptimizacion` — Weekly PAS report (scenarios A/B/C/D/X with auto block adjustments)
- `AjusteNutricional` — Audit log of nutritional adjustments

Signals: `signals.py`  
Async tasks: `tasks.py` (Celery)  
Services: `services.py`, `bloques_alimentos.py`, `nivel1_balance.py`, `nivel2_macros.py`, `graficos.py`

---

### `estoico` — Stoic Philosophy

366-day content calendar (`ContenidoDiario`): cita, autor, reflexion, pregunta.

Models: `PerfilEstoico`, `ReflexionDiaria`, `LogroEstoico`, `LogroUsuario`, `EstadisticaUsuario`, `ConfiguracionNotificacion`.

Philosopher choices: Marco Aurelio, Séneca, Epicteto, Musonio Rufo, Zenón.

Management commands: `cargar_datos_estoicos`, `verificar_datos_estoicos`, `backup_datos_estoicos`, `debug_datos_estoicos`, `migracion_inicial_estoica`

---

### `diario` — Daily Journal

Models: `AreaVida`, `Eudaimonia` (life area score 1–10), `TrimestreEudaimonia` (quarterly planning).

Services: `insights_engine.py` — automated pattern detection.  
Forms: `forms.py`, `forms_trigger.py` (trigger-based interventions).

---

### `estiramientos` — Stretching

Routine library with image instructions. Management commands: `seed_estiramientos`, `descargar_imagenes_estiramientos`.

---

### `hyrox` — Competition Training

Hyrox is a fitness race combining running and functional exercise stations.

**Key models:**
- `HyroxObjective` — Competition goal: category (`open_men/women`, `pro_men/women`, `doubles`, `relay`), event date, athletic profile (RMs, 5K time), methods: `get_race_readiness_score()`, `get_readiness_breakdown()`, `get_daily_push()`
- `HyroxSession` — Training session: energia_pre (1–10), HR avg/max, RPE, `notas_raw` (parsed by AI), `muscle_fatigue_index`, `fatiga_updated_at` (decay tracking)
- `HyroxActivity` — Individual block in session: `tipo_actividad` choices: `fuerza | carrera | ergometro | isometrico | hyrox_station | cardio_sustituto | hiit | remo | skierg | bici | otro`
- `HyroxReadinessLog` — Daily readiness score (0–100)
- `UserInjury` — Injury: `fase` (`AGUDA | SUB_AGUDA | RETORNO | RECUPERADO`), `tags_restringidos` (JSON, e.g., `impacto_vertical`, `carrera`), `invalidate_future_sessions()` method
- `DailyRecoveryEntry` — Pain, swelling, ROM tracking per day
- `RecoveryTestLog` — `es_apto` = pain ≤ 1 AND no swelling AND confidence ≥ 8

**Services:**
- `services.py` — `CompetitionStandardsService`, `HyroxMacrocycleEngine`, `HyroxTrainingEngine`
- `training_engine.py` — Periodization phases: Adaptation, Accumulation, Intensification, Simulation, Taper, Peak

**Race Readiness Score formula:** 40% technical capacity + 30% effort efficiency + 30% specific resistance.

Running inactivity penalty can be mitigated with football substitute cardio (credit system).

---

### `core` — Shared Utilities

- `bio_context_processor.py` — Injects biometric context into all templates.
- `test_bio_context.py` — Tests for bio context processor.

---

## Development Workflow

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Use local SQLite settings
cp gymproject/settings_local.py.example gymproject/settings_local.py  # if exists

# Run migrations
python manage.py migrate

# Load initial data
python manage.py cargar_datos_estoicos
python manage.py seed_estiramientos
python manage.py crear_pruebas_epicas

# Start development server
python manage.py runserver
# or
python run.py
```

### Database

- **Production:** MySQL on PythonAnywhere (`toxirin$gymdb`)
- **Local:** SQLite (`db.sqlite333` or `db_local.sqlite3`)
- Always run `python manage.py migrate` after pulling changes that include new migrations.

### Celery (async tasks)

```bash
# Requires Redis running locally
celery -A gymproject worker --loglevel=info
celery -A gymproject beat --loglevel=info   # for scheduled tasks
```

### Static Files

```bash
python manage.py collectstatic
```

WhiteNoise serves static files in production; no separate web server config needed.

---

## Key Conventions

### Naming

| Element | Convention | Example |
|---|---|---|
| Models | PascalCase | `EntrenoRealizado`, `HyroxObjective` |
| Views | snake_case | `panel_cliente`, `dashboard_adherencia` |
| URLs (path names) | kebab-case | `dashboard-evolucion` |
| Apps | lowercase | `clientes`, `entrenos` |
| Template tags | lowercase | custom tags in `templatetags/` |

### ORM Patterns

- Use `JSONField` for flexible data: `one_rm_data`, `historial_volumen`, `risk_tags`, `tags_restringidos`, `meal_distribution`
- Use `unique_together` for composite uniqueness (e.g., `(usuario, fecha)` on daily records)
- On delete policies: `CASCADE` for owned records, `SET_NULL` for optional links
- `related_name` is always set on ForeignKey/OneToOneField

### Service Layer

Business logic lives in `services.py` (or a `services/` subdirectory for large apps), not in views. Views should call service functions and return responses.

Heavy computation is in dedicated service files:
- `estadisticas_service.py` — volume, frequency stats
- `evaluacion_profesional_service.py` — professional-grade evaluation
- `ia_*.py` files — Gemini AI calls

### AI Integration (Gemini)

- API key is in `settings.py` (`GEMINI_API_KEY`)
- Always cache AI responses using `CacheAnalisis` model (MD5-keyed by tipo + parameters)
- Default cache TTL: 5 minutes (configurable via `CACHE_TTL` in settings)
- AI services return structured recommendations stored in `RecomendacionEntrenamiento`

### Signals

- `entrenos/signals.py` — fires on training completion (triggers gamification, analytics, nutrition updates)
- `nutricion_app_django/signals.py` — nutrition-related auto-actions
- `hyrox/models.py` — `invalidate_future_sessions()` called on injury save

### Custom Template Tags

Each app with complex template logic has a `templatetags/` directory. Project-level tags are in `/templatetags/`.

### Gamification Points

Every point event is logged in `HistorialPuntos`. Never add points without creating a `HistorialPuntos` record. `PerfilGamificacion.auto_update_nivel()` must be called after point updates.

### Injury Safety

When generating training sessions for a client with an active `UserInjury`:
1. Read `tags_restringidos` (JSON list) from the injury record.
2. Filter out `EjercicioBase` entries whose `risk_tags` intersect with `tags_restringidos`.
3. Mark substituted exercises with `is_recovery_load=True` on `EjercicioRealizado`.

### Nutrition Block Math

- Do not hardcode macro values; use the block constants: P=7g, C=9g, G=3g.
- Safety locks: minimum protein and fat per kg of lean mass must be respected before any block reduction.
- `InformeOptimizacion` scenarios must always be one of: A, B, C, D, X.

---

## Testing

### Running Tests

```bash
python manage.py test                        # all tests
python manage.py test clientes               # single app
python manage.py test analytics.test_helms_refactor
```

### Test Files

```
clientes/tests.py
rutinas/tests.py
joi/tests.py
estoico/tests.py
estiramientos/tests.py
nutricion_app_django/tests.py
analytics/tests.py
analytics/test_helms_refactor.py
entrenos/test_integracion_helms.py
core/test_bio_context.py
test_ajax.py          # root — AJAX endpoint tests
test_rpe_save.py      # root — RPE persistence
test_calendar.py      # root — calendar logic
test_gemini.py        # root — Gemini AI integration
test_html.py          # root — HTML rendering
test_template.py      # root — template rendering
```

Framework: Django `TestCase` (unittest-based). No pytest configuration present.

---

## Deployment

### PythonAnywhere (production)

- Web app: WSGI via `gymproject/wsgi.py`
- Static files: collected via `collectstatic`, served by WhiteNoise
- Database: MySQL (`toxirin$gymdb`)
- Redis: must be running for Celery tasks

### Heroku (alternative)

`Procfile` configures: `web: gunicorn gymproject.wsgi`

### Standalone App

`MiAppDjango.spec` — PyInstaller spec for packaging as a standalone desktop application.

### PWA

`static/manifest.json` and `static/serviceworker.js` provide offline support.

---

## Security Notes

> These are known issues in the current codebase. Fix before any public production deployment.

1. **`DEBUG=True` in `settings.py`** — must be `False` in production.
2. **`ALLOWED_HOSTS=['*']`** — restrict to actual domain in production.
3. **Hardcoded secrets in `settings.py`**: `SECRET_KEY`, MySQL password, Gemini API key — move to environment variables.
4. **`settings_local.py`** is not in `.gitignore` — verify it never contains production credentials.

---

## Management Commands Reference

| Command | App | Purpose |
|---|---|---|
| `migrar_clientes` | clientes | Client data migration utility |
| `cargar_datos_estoicos` | estoico | Load 366-day stoic content calendar |
| `verificar_datos_estoicos` | estoico | Check data integrity |
| `backup_datos_estoicos` | estoico | Backup stoic content |
| `debug_datos_estoicos` | estoico | Debug stoic content |
| `migracion_inicial_estoica` | estoico | One-time initial setup |
| `generar_recomendaciones` | analytics | Auto-generate AI recommendations |
| `diagnosticar_recomendaciones` | analytics | Debug recommendation engine |
| `ver_recomendaciones` | analytics | Display current recommendations |
| `entrenar_ia` | analytics | Fine-tune Gemini integration |
| `seed_estiramientos` | estiramientos | Load stretching routines |
| `descargar_imagenes_estiramientos` | estiramientos | Download stretch images |
| `crear_pruebas_epicas` | logros | Generate epic achievement challenges |
| `resync_gamificacion` | logros | Resync gamification state for all users |
| `corregir` | logros | Repair/fix gamification inconsistencies |

---

## External Integrations

| Integration | Details |
|---|---|
| **Gemini AI** | `analytics/ia_*.py`, `joi/services.py`, Hyrox session parsing. Key in `settings.GEMINI_API_KEY` |
| **Liftin** | Third-party workout app. Parsed in `entrenos/` via `EjercicioLiftinDetallado`. API endpoint at `/api/liftin/` |
| **Redis** | Celery broker & backend at `redis://localhost:6379/0` |
| **Celery Beat** | Scheduled tasks (nutrition reminders, weekly reports) via `django_celery_beat` |

---

## Diagnostics

See `INSTRUCCIONES_DIAGNOSTICO.md` for troubleshooting the analytics evolution dashboard, log inspection, and shell debugging steps.

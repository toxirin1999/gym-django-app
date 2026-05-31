# Phase 60A — Mapa Funcional de la App

> Auditoría visual/funcional de las 5 apps core: clientes, joi, hyrox, entrenos, diario.
> Objetivo: detectar incoherencias, duplicidades, legacy y proponer acciones concretas.
> Sin código todavía. Solo mapa y decisiones.

---

## 1. FLUJO DE NAVEGACIÓN PRINCIPAL

```
/ → redirigir_usuario()
     ├── si es entrenador → /clientes/panel-entrenador/
     └── si es usuario    → /clientes/mockup-demo/  ← ENTRY POINT REAL
                                      │
         ┌────────────────────────────┼─────────────────────────────┐
         ▼                            ▼                              ▼
   /entrenos/cliente/X/       /hyrox/dashboard/            /joi/habitacion/
   briefing → activo          readiness + decisión          presencia JOI
         │
         ├── /entrenos/cliente/X/plan/        (plan semanal)
         ├── /entrenos/cliente/X/timeline/    (timeline unificado)
         ├── /entrenos/cliente/X/dashboard-evolucion/
         └── /clientes/cliente/X/plan/decisiones/
```

**Entradas secundarias al usuario:**
- `/diario/` → dashboard diario (muchos subsistemas)
- `/clientes/bitacora/registrar/` → checkin matutino
- `/clientes/cliente/X/memoria-entrenador/` → "Lo que sé de ti"

---

## 2. INVENTARIO POR APP

### CLIENTES (34 templates)

| Template | Líneas | Función | Estado | Problemas |
|----------|--------|---------|--------|-----------|
| `mockup_demo.html` | 2240 | **Dashboard principal** (entry point real) | NÚCLEO | Extiende blade_runner — 2 templates para 1 pantalla. Banner JOI inline hardcodeado. |
| `blade_runner.html` | 1761 | Base del dashboard | NÚCLEO | Solo existe para ser extendido por mockup_demo. ¿Merecería fusionarse? |
| `panel_cliente.html` | 275 | Otra vista del panel del cliente | DUPLICADA? | Tiene JOI header + `_joi_fab.html`. ¿En qué difiere de mockup_demo? |
| `dashboard.html` | 241 | Dashboard simple (¿antiguo?) | SOSPECHOSA | Tiene `<div id="joi-root"></div>` × 2 — elemento React sin montar. |
| `portal_sesion.html` | 567 | Portal unificado de sesión | ÚTIL | Ver si duplica con briefing_entrenamiento |
| `registrar_bitacora.html` | 682 | Checkin matutino (energía, HRV, FC) | NÚCLEO | Tiene `respuesta_joi` — JOI responde al checkin |
| `plan_decisiones.html` | 537 | GymDecisionLog + lectura semanal JOI | ÚTIL | Tiene `lectura_semanal_joi` y `estado` de la semana |
| `memoria_entrenador.html` | 607 | "Lo que sé de ti" (datos longitudinales) | ÚTIL | ¿Rival narrativo de JOI? Revisar posición en arquitectura |
| `detalle.html` | 808 | Detalle del cliente | ÚTIL | Grande — revisar si todo sigue activo |
| `editar.html` | 770 | Editar cliente | ÚTIL | — |
| `configurar_preferencias_helms.html` | 801 | Configurar plan (Helms) | ÚTIL | Muy técnico para el usuario final |
| `control_peso.html` | 439 | Control de peso | ÚTIL | — |
| `tarjeta_proximo_entrenamiento.html` | 320 | Partial: tarjeta del próximo entreno | SOPORTE | ¿Include de mockup_demo? |
| `historial.html` | 147 | Historial de revisiones | ÚTIL | Tiene `estado.mensaje_joi` — ¿sigue activo? |
| `panel_entrenador.html` | 296 | Dashboard del entrenador | ÚTIL | App es personal — ¿cuánto se usa? |
| `dashboard_adherencia.html` | 46 | Adherencia semanal | SOPORTE | Muy pequeño — ¿partial o vista propia? |
| `comparar.html` | 166 | Comparar períodos | ÚTIL | — |
| `calendario_bitacoras.html` | 130 | Calendario de bitácoras | ÚTIL | — |
| `index.html` | 110 | Lista de clientes | SOPORTE | Solo para entrenador |
| `lista_revisiones.html` | 110 | Lista de revisiones | SOPORTE | — |
| `apple_health_token.html` | 109 | Token Apple Health | SOPORTE | — |
| `mapa_energia.html` | 46 | Mapa de energía | REVISAR | Función poco clara en contexto actual |
| `agregar.html` | 67 | Crear cliente | SOPORTE | — |
| `agregar_revision.html` | 53 | Crear revisión | SOPORTE | — |
| `recuerdos_semanales.html` | 46 | Recuerdos semanales | REVISAR | Usa `estado.mensaje_joi` — ¿aún activo? |
| `responder_sugerencia.html` | 46 | Responder sugerencia del entrenador | REVISAR | — |
| `educacion_helms.html` | 35 | Educación Helms | LEGACY? | 35 líneas, función muy limitada |
| `cuidado_sugerido.html` | 23 | Cuidado sugerido (lesión) | REVISAR | 23 líneas — ¿partial o vista propia? |
| `asignar_programa.html` | 36 | Asignar programa | SOPORTE | — |
| `definir_objetivo.html` | 18 | Definir objetivo | LEGACY? | 18 líneas — ¿funciona aún? |
| `eliminar.html` | 15 | Confirmar borrar cliente | SOPORTE | — |
| `_widget_acwr.html` | 76 | Partial: widget ACWR | SOPORTE | Correcto como partial |
| `blade-runner-demo.html` | 0 | **VACÍO** | **ELIMINAR** | Archivo vacío, no sirve para nada |
| `dashboard_cliente.html` | ? | Vista cliente individual (entrenador) | SOPORTE | — |

---

### JOI (12 templates)

| Template | Líneas | Función | Estado | Problemas |
|----------|--------|---------|--------|-----------|
| `habitacion.html` | 467 | **Presencia central de JOI** | NÚCLEO | Punto de llegada canónico ✓ |
| `narrativa.html` | 254 | NarrativaActiva — postura longitudinal | NÚCLEO | — |
| `manual_poda.html` | 319 | ManualDavid — hipótesis revisables | NÚCLEO | — |
| `historial.html` | 114 | Historial de mensajes JOI | ÚTIL | — |
| `diario_resumen.html` | 135 | Resumen JOI del diario | REVISAR | ¿Sigue usándose activamente? |
| `inicio.html` | 45 | **Inicio antiguo de JOI** | **LEGACY** | Pre-habitación. URL activa pero función obsoleta. |
| `diario.html` | 56 | Diario dentro de JOI (antiguo) | **LEGACY** | Reemplazado por app `diario/`. Usa `joi_flotante.html`. |
| `entrenar.html` | 38 | Entrenamiento dentro de JOI (antiguo) | **LEGACY** | Flujo viejo. Usa `joi_flotante.html`. |
| `entrenar_gracias.html` | 114 | Gracias post-entreno JOI | **LEGACY** | Flujo viejo. |
| `logros.html` | 75 | Logros dentro de JOI (antiguo) | **LEGACY** | Reemplazado por app `logros/`. |
| `recuerdos.html` | 30 | Recuerdos JOI | **LEGACY/REVISAR** | 30 líneas, función poco clara |
| `joi_flotante.html` | 227 | Botón flotante JOI (versión vieja) | **DUPLICADO → ELIMINAR** | Solo referenciado por templates legacy (inicio, diario, entrenar). El actual es `includes/_joi_fab.html` (69 líneas). |

**Nota crítica:** `joi/urls.py` todavía monta rutas para `inicio/`, `diario/`, `entrenar/`, `logros/`, `recuerdos/`. Estas rutas llevan a templates legacy que usan `joi_flotante.html` (el duplicado). Si se eliminan las rutas, se puede eliminar también `joi_flotante.html`.

---

### HYROX (12 templates)

| Template | Líneas | Función | Estado | Problemas |
|----------|--------|---------|--------|-----------|
| `dashboard.html` | 3133 | **Dashboard Hyrox** (readiness + decisión) | NÚCLEO | Muy grande. JOI banner propio (`joi-hyrox-banner`). |
| `registrar_entrenamiento.html` | 2042 | Registrar sesión Hyrox | NÚCLEO | Tiene su propio banner JOI (`joi_mensaje_hyrox`). |
| `strava_reconciliacion.html` | 799 | Reconciliar con Strava | ÚTIL | — |
| `reportar_lesion.html` | 416 | Reportar lesión | NÚCLEO | — |
| `guia_tecnica.html` | 558 | Guía técnica de estaciones | ÚTIL | Incluye `_joi_fab.html` |
| `editar_sesion.html` | 379 | Editar sesión Hyrox | ÚTIL | — |
| `_part2.html` | 379 | Partial del dashboard | SOPORTE | — |
| `crear_objetivo.html` | 244 | Crear objetivo Hyrox | SOPORTE | — |
| `reportar_recuperacion.html` | 109 | Reportar recuperación de lesión | SOPORTE | — |
| `test_recuperacion.html` | 88 | Test de aptitud post-lesión | SOPORTE | — |
| `_dia.html` | 30 | Partial: día en plan | SOPORTE | — |
| `_timer.html` | 20 | Partial: timer | SOPORTE | — |
| `dashboard.html.bak` | — | **Backup del dashboard** | **ELIMINAR** | Archivo .bak en producción |

---

### ENTRENOS (20+ templates)

| Template | Líneas | Función | Estado | Problemas |
|----------|--------|---------|--------|-----------|
| `entrenamiento_activo.html` | 3248 | **UI en vivo del entreno** | NÚCLEO | El más grande de entrenos |
| `vista_plan_calendario.html` | 6023 | **Plan semanal/mensual** | NÚCLEO | El MÁS GRANDE de toda la app (6k líneas) |
| `dashboard_evolucion.html` | 1548 | Dashboard evolución temporal | NÚCLEO | Incluye `_joi_fab.html` |
| `timeline_atleta.html` | 1054 | Timeline unificado gym+hyrox | NÚCLEO | Incluye `_joi_fab.html` |
| `evaluacion_profesional.html` | 570 | Evaluación post-sesión | NÚCLEO | — |
| `briefing_entrenamiento.html` | 521 | Pre-sesión (contexto + preparación) | NÚCLEO | — |
| `registrar_actividad_libre.html` | 509 | Registrar actividad libre | ÚTIL | — |
| `vista_resumen_anual.html` | 615 | Resumen anual de entrenos | ÚTIL | — |
| `empezar_entreno.html` | 582 | ¿Pantalla de inicio de entreno? | **REVISAR** | ¿Difiere de briefing? ¿De entrenamiento_activo? Posible duplicado |
| `hacer_entreno.html` | 291 | Hacer entreno (¿viejo?) | **REVISAR** | ¿Qué diferencia con entrenamiento_activo? Posible legacy |
| `editar_actividad_libre.html` | 208 | Editar actividad libre | ÚTIL | — |
| `detalle_ejercicio.html` | 171 | Detalle de un ejercicio | SOPORTE | — |
| `dashboard_ejercicios.html` | 342 | Dashboard de ejercicios | SOPORTE | — |
| `vista_historial_detallado.html` | 101 | Historial detallado | SOPORTE | — |
| `notificaciones_epicas_sistema.html` | 572 | Notificaciones épicas/gamificación | REVISAR | ¿Activo? |
| `tabla_ejercicios.html` | 167 | Tabla de ejercicios | SOPORTE | — |
| `gestionar_ejercicios_base.html` | 129 | Gestionar ejercicios base | SOPORTE | Solo para entrenador |
| `entreno_anterior.html` | 285 | Entreno anterior | SOPORTE | — |
| `resumen_entreno.html` | 16 | Resumen post-entreno | REVISAR | 16 líneas — ¿partial o vista incompleta? |
| `entrenos_filtrados.html` | 30 | Partial AJAX: entrenamientos | SOPORTE | — |
| `timeline_atleta.html.bak` | — | **Backup del timeline** | **ELIMINAR** | Archivo .bak en producción |

---

### DIARIO (47 templates — el más grande)

Diario es el sistema con más superficie. Tiene 11 subsistemas. Organizado por subsistema:

#### Presencia (núcleo del diario)
| Template | Líneas | Estado |
|----------|--------|--------|
| `presencia_apertura.html` | 441 | NÚCLEO |
| `presencia_cierre.html` | 498 | NÚCLEO — tiene clases CSS `.joi-header`, `.joi-greeting` |
| `dashboard.html` | 278 | NÚCLEO |
| `lectura_semanal.html` | 216 | ÚTIL — tiene `n_con_joi` |

#### Prosoche (diario reflexivo)
| Template | Estado |
|----------|--------|
| `prosoche_dashboard.html` (1175) | NÚCLEO del subsistema |
| `prosoche_entrada_form.html` (660) | ACTIVO |
| `prosoche_revision_semanal.html` (456) | ACTIVO |
| `prosoche_mes_anterior.html` (868) | ACTIVO |
| `prosoche_entrada_detalle.html` | ACTIVO |
| `prosoche_entradas_mes.html` | ACTIVO |
| `prosoche_entrada_form.html.backup` | **ELIMINAR** |

#### Eudaimonia (áreas de vida)
| Template | Estado |
|----------|--------|
| `eudaimonia_dashboard.html` (219) | ÚTIL |
| `eudaimonia_detalle.html` (219) | ÚTIL |

#### Habitos (4 leyes Atomic Habits)
| Template | Estado | Nota |
|----------|--------|------|
| `habitos_dashboard.html` | ACTIVO | No aparece en render() grep — revisar |
| `habito_wizard_4leyes.html` (588) | ACTIVO | No aparece en render() grep — revisar |
| `habito_form.html` (274) | ACTIVO | No aparece en render() grep — revisar |
| `habito_registrar_trigger.html` (276) | ACTIVO | No aparece en render() grep — revisar |
| `habito_analisis_patrones.html` (489) | ACTIVO | No aparece en render() grep — revisar |

#### Logos (escritura libre + reflexión)
| Template | Estado |
|----------|--------|
| `logos_dashboard.html` (169) | ÚTIL |
| `logos_escritura_libre.html` (150) | ÚTIL |
| `logos_reflexion_guiada.html` (431) | ÚTIL |
| `logos_ver_reflexion.html` (143) | ÚTIL |
| `logos_editar_reflexion.html` (134) | ÚTIL |
| `logos_lista_reflexiones.html` (182) | ÚTIL |
| `logos_calendario.html` (126) | ÚTIL |

#### Simbiosis (personas y vínculos)
| Template | Estado |
|----------|--------|
| `simbiosis_dashboard.html` (365) | ÚTIL |
| `persona_detalle.html` (256) | ÚTIL — tiene clases CSS `.int-dot.joi` → revisar |
| `persona_form.html` (53) | SOPORTE |
| `interaccion_form.html` (71) | SOPORTE |

#### Arete / Gnosis / Vires / Kairos / Virtudes / Oraculo
| Subsistema | Templates | Estado |
|------------|-----------|--------|
| Arete | arete_dashboard, arete_ejercicio_detalle | REVISAR — ¿uso activo? |
| Gnosis | gnosis_dashboard, gnosis_crear | REVISAR — ¿uso activo? |
| Vires | vires_dashboard, vires_seguimiento_form | REVISAR — ¿uso activo? |
| Kairos | kairos_dashboard (937!), kairos_evento_form | REVISAR — dashboard muy grande |
| Virtudes | virtudes_dashboard, virtud_detalle | REVISAR |
| Oraculo | oraculo_insights (83) | REVISAR |

#### Analíticas / Insignias / Utilidades
| Template | Estado |
|----------|--------|
| `analiticas_personales.html` (220) | ÚTIL |
| `analisis_habitos_anual.html` (282) | ÚTIL |
| `analisis_habitos_completo.html` (361) | ÚTIL |
| `analisis_habitos_historico.html` (306) | ÚTIL |
| `insignias_lista.html` (158) | SOPORTE |
| `reprocesar_cierres.html` (94) | ADMIN — no debería ser accesible al usuario |

---

## 3. PANTALLAS NÚCLEO

Las pantallas sin las que la app no funciona:

| Pantalla | Ruta | Responde a |
|----------|------|------------|
| Dashboard principal | `/clientes/mockup-demo/` | ¿Qué hago hoy? |
| Checkin matutino | `/clientes/bitacora/registrar/` | ¿Cómo estoy hoy? |
| Plan semanal | `/entrenos/cliente/X/plan/` | ¿Qué tengo esta semana? |
| Entreno activo | `/entrenos/cliente/X/entrenamiento-activo/` | Estoy entrenando ahora |
| Habitación JOI | `/joi/habitacion/` | ¿Qué observa el sistema? |
| Dashboard Hyrox | `/hyrox/dashboard/` | ¿Cómo está mi preparación Hyrox? |
| Decisiones del plan | `/clientes/cliente/X/plan/decisiones/` | ¿Por qué el plan hace esto? |
| Reportar lesión | `/hyrox/reportar-lesion/` | Tengo una molestia |
| Presencia apertura | `/diario/presencia/apertura/` | Inicio el día |
| Presencia cierre | `/diario/presencia/cierre/` | Cierro el día |

---

## 4. PANTALLAS DUPLICADAS / CONFLICTIVAS

| Problema | Templates | Decisión propuesta |
|----------|-----------|-------------------|
| **Dos templates para el dashboard principal** | `blade_runner.html` (1761) ← extendido por `mockup_demo.html` (2240) | Fusionar en uno solo. `blade_runner` es base sin sentido propio. |
| **Dos botones flotantes JOI** | `joi/joi_flotante.html` (227) vs `includes/_joi_fab.html` (69) | Eliminar `joi_flotante.html`. Solo usar `_joi_fab.html`. |
| **panel_cliente.html vs mockup_demo** | Ambas tienen JOI y parecen dashboards | Verificar si `panel_cliente` sigue siendo punto de entrada para algún flujo |
| **empezar_entreno.html vs briefing vs entrenamiento_activo** | 3 templates para "iniciar entreno" | Clarificar cuál es el flujo oficial y deprecar los otros |
| **hacer_entreno.html vs entrenamiento_activo.html** | 291 vs 3248 líneas | ¿`hacer_entreno` es anterior o diferente? Investigar antes de actuar |

---

## 5. PANTALLAS LEGACY / ELIMINAR

| Template | Razón | Acción |
|----------|-------|--------|
| `blade-runner-demo.html` | 0 líneas — archivo vacío | **ELIMINAR** |
| `hyrox/dashboard.html.bak` | Backup en producción | **ELIMINAR** |
| `entrenos/timeline_atleta.html.bak` | Backup en producción | **ELIMINAR** |
| `diario/prosoche_entrada_form.html.backup` | Backup en producción | **ELIMINAR** |
| `joi/inicio.html` | Pre-habitación, obsoleto. URL activa pero huérfana funcionalmente | **ELIMINAR + quitar URL** |
| `joi/diario.html` | Cuando JOI tenía diario propio. Reemplazado por app `diario/` | **ELIMINAR + quitar URL** |
| `joi/entrenar.html` | Flujo antiguo de entrenamiento JOI | **ELIMINAR + quitar URL** |
| `joi/entrenar_gracias.html` | Flujo antiguo | **ELIMINAR + quitar URL** |
| `joi/logros.html` | Reemplazado por app `logros/` | **ELIMINAR + quitar URL** |
| `joi/joi_flotante.html` | Duplicado de `_joi_fab.html`. Solo usado por templates legacy. | **ELIMINAR** (tras limpiar los legacy) |

---

## 6. INCOHERENCIAS DETECTADAS

### A. JOI fuera de su contrato (apariciones residuales)

| Template | Tipo de aparición | Severidad | Decisión |
|----------|-------------------|-----------|---------|
| `mockup_demo.html` (línea 386) | Banner JOI inline con HTML/CSS hardcodeado | ALTA | Mover a `_joi_fab.html` o eliminar. JOI no debe ser banner fijo en dashboard. |
| `hyrox/dashboard.html` (línea 687) | `joi-hyrox-banner` propio | MEDIA | ¿Sigue siendo válido post-Phase 59? Revisar si debe ser solo indicador. |
| `hyrox/registrar_entrenamiento.html` (línea 715) | Banner `joi_mensaje_hyrox` propio | MEDIA | Mismo caso — ¿indicador o banner? |
| `clientes/dashboard.html` (líneas 61, 238) | `<div id="joi-root"></div>` × 2 — vacío | ALTA | Elemento React sin montar. Residuo. Eliminar. |
| `clientes/registrar_bitacora.html` | `respuesta_joi` en checkin | BAJA | Parece coherente — JOI responde al checkin. Mantener. |
| `diario/presencia_apertura.html` | Clases CSS `.joi-block`, `.joi-label` | BAJA | Cosmético. Aceptable si la apertura conecta con JOI. |
| `diario/presencia_cierre.html` | Clases CSS `.joi-header`, `.joi-greeting` | BAJA | Mismo caso. |
| `diario/dashboard.html` | `estado_dia.tiene_lectura_joi` | BAJA | Indicador correcto — el dashboard muestra si hubo lectura JOI. |
| `diario/persona_detalle.html` | Clases CSS `.int-dot.joi` | BAJA | Cosmético, aceptable. |
| `clientes/historial.html` | `estado.mensaje_joi` | BAJA | Historial mostrando último mensaje. Aceptable. |

### B. Incoherencias de flujo/lenguaje

| Incoherencia | Detalle |
|--------------|---------|
| **Dashboard ambiguo** | El entry point es `/clientes/mockup-demo/` que tiene nombre de "demo". Confuso. |
| **blade-demo tiene URL activa** | `/clientes/blade-demo/` lleva a `blade_runner_demo` — ¿se usa? ¿Es prueba de producción? |
| **3 formas de "iniciar un entreno"** | `empezar_entreno`, `briefing`, `entrenamiento_activo` sin jerarquía clara |
| **Diario es un universo paralelo** | 11 subsistemas (Prosoche, Eudaimonia, Arete, Gnosis, Vires, Kairos, Logos, Simbiosis, Habitos, Virtudes, Oraculo) con URLs, vistas y templates propios. ¿Cuáles son de uso activo real? |
| **`reprocesar_cierres`** | URL accesible al usuario, función de administración interna. Debería estar detrás de `@staff_member_required`. |
| **Habitos no aparece en render() grep** | 5 templates de habitos existen y tienen URLs pero no se detectan en render() — posiblemente usen `TemplateResponse` o paths distintos. Verificar que funcionan. |

---

## 7. PREGUNTAS ABIERTAS (requieren respuesta del usuario)

Antes de tomar decisiones de fusión o eliminación:

1. **¿`panel_cliente.html` se sigue usando?** La URL `/clientes/mi-panel/` redirige a `mockup_demo`. ¿Hay otra URL que sirva `panel_cliente`?

2. **¿`hacer_entreno.html` es legacy o flujo alternativo?** Tiene 291 líneas pero parece preceder a `entrenamiento_activo`. ¿Cuándo se llega a esta pantalla?

3. **¿Los subsistemas de diario (Arete, Gnosis, Vires, Kairos, Virtudes, Oraculo) están en uso activo?** ¿O son experimentos que quedaron vivos?

4. **¿`blade-demo` tiene uso legítimo?** Ruta activa con template extendido.

5. **¿El diario debe ser una herramienta propia o solo combustible para JOI?** Esto cambia la prioridad de varios subsistemas.

---

## 8. ACCIONES PROPUESTAS (backlog priorizado)

### ELIMINAR (seguro, sin riesgo)
- [ ] `blade-runner-demo.html` — vacío
- [ ] `hyrox/dashboard.html.bak`
- [ ] `entrenos/timeline_atleta.html.bak`
- [ ] `diario/prosoche_entrada_form.html.backup`

### ELIMINAR + quitar URL (verificar primero que nadie llega)
- [ ] `joi/inicio.html` + URL `joi/inicio/`
- [ ] `joi/diario.html` + URL `joi/diario/`
- [ ] `joi/entrenar.html` + URL `joi/entrenar/`
- [ ] `joi/entrenar_gracias.html`
- [ ] `joi/logros.html` + URL `joi/logros/`
- [ ] `joi/recuerdos.html` + URL `joi/recuerdos/` (verificar uso)
- [ ] `joi/joi_flotante.html` (tras limpiar los anteriores)

### LIMPIAR CÓDIGO RESIDUAL
- [ ] Eliminar `<div id="joi-root"></div>` × 2 de `clientes/dashboard.html`
- [ ] Revisar y reducir banner JOI inline en `mockup_demo.html` (línea 386)
- [ ] Evaluar `joi-hyrox-banner` en `hyrox/dashboard.html` — ¿banner o indicador?

### FUSIONAR / CLARIFICAR
- [ ] Decidir si `blade_runner.html` + `mockup_demo.html` se pueden fusionar en un solo template
- [ ] Clarificar flujo de inicio de entreno: `empezar_entreno` → `briefing` → `entrenamiento_activo`
- [ ] Confirmar si `panel_cliente.html` sigue teniendo función propia o es legacy

### REVISAR SUBSISTEMAS DIARIO
- [ ] Auditar uso real de: Arete, Gnosis, Vires, Kairos, Oraculo, Virtudes
- [ ] Verificar que templates de habitos (5) renderizan correctamente (no aparecen en grep)
- [ ] Mover `reprocesar_cierres` detrás de `@staff_member_required`

### RENOMBRAR
- [ ] Renombrar URL `mockup-demo` → `panel` o `dashboard` (el nombre "mockup" es confuso en producción)

---

## 9. RESUMEN EJECUTIVO

**Total templates auditados:** ~120 entre las 5 apps  
**Templates a eliminar (seguros):** 4 backups/vacíos  
**Templates JOI legacy (eliminar + URL):** 6–7 templates  
**Templates en estado dudoso:** ~10 (empezar_entreno, hacer_entreno, varios de diario)  
**Incoherencias JOI fuera de contrato:** 3 críticas + 7 menores  
**Preguntas abiertas antes de actuar:** 5  

**Veredicto:** La app tiene una arquitectura funcional sólida en su núcleo (entreno activo, plan, Hyrox, JOI). El problema real es la acumulación de capas — templates pre-Phase 59 que quedaron vivos, un diario con 11 subsistemas cuya actividad real es desconocida, y JOI que aparece en 10+ templates con distintos contratos.

**La limpieza segura y de mayor impacto es la de JOI legacy** — 6 templates + sus URLs se pueden eliminar en una sesión corta sin riesgo.

---

*Generado: Phase 60A — Mayo 2026*

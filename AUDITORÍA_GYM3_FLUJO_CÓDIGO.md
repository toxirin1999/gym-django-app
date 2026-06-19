# Phase Gym 3 — Auditoría del Flujo Post-Sesión (por código)

**Estado:** 🔍 AUDITORÍA COMPLETADA  
**Fecha:** 2026-06-19  
**Método:** Análisis del código (guardar_entrenamiento_activo → post_entreno_resumen)

---

## El Flujo Completo (Código)

```
Usuario pulsa "Finalizar entrenamiento"
  ↓
POST a guardar_entrenamiento_activo(request, cliente_id)
  ├─ Guarda EntrenoRealizado + EjercicioRealizado
  ├─ Calcula RPE medio, volumen, ACWR
  ├─ Genera JOI post-entreno (trigger='entreno_completado')
  ├─ Detecta récords personales
  ├─ Verifica logros desbloqueados
  ├─ Valida desafíos semanales
  ├─ Invalida caché dashboard ACWR
  ├─ Muestra messages.success() x N
  └─ REDIRIGE a post_entreno_resumen
      ↓
      GET post_entreno_resumen(request, cliente_id, entreno_id)
        ├─ Llama construir_contexto_cierre(cliente, entreno)
        │  ├─ resumen: {n_ejercicios, n_series, rpe_medio, volumen_kg, duracion}
        │  ├─ cambios_relevantes: comparación vs última sesión
        │  ├─ lectura_plan: mensaje de freno (si hay)
        │  ├─ proxima_vez: qué esperar siguiente
        │  ├─ prs: récords establecidos
        │  └─ joi_mensaje: mensaje JOI post-entreno
        └─ Renderiza post_entreno_resumen.html
```

---

## Análisis Detallado por Sección

### 1. **Guardar Entrenamiento (líneas 3989-4412)**

#### Qué ocurre:

| Acción | Línea | Detalles |
|--------|-------|---------|
| Crear EntrenoRealizado | 4002 | `entreno = EntrenoRealizado.objects.create(...)` |
| Procesar ejercicios | 4016-4100 | Lee datos de formulario, calcula 1RM, volumen, RPE |
| Mostrar mensaje versión esencial | 4188 | `"Versión esencial completada. El bloque principal ya es suficiente para hoy."` |
| Mostrar mensaje general | 4190 | `"¡Entrenamiento guardado con éxito!"` |
| **Generar JOI post-entreno** | 4344-4353 | `generar_mensaje_joi(trigger='entreno_completado', datos_extra={...})` |
| Detectar récords | 4318-4323 | `messages.success(f"🏆 ¡{N} NUEVOS RÉCORDS!")` |
| Verificar logros | 4358-4360 | `messages.success(f"🌟 ¡LOGRO: {logro}!")` |
| Validar desafíos | 4363-4390 | `messages.success(f"🎯 ¡DESAFÍO COMPLETADO!")` |
| **Invalidar caché dashboard** | 4313 | `_cache.delete(f'dashboard_acwr_unificado_{cliente.id}')` |
| **REDIRIGE** | 4407 | `return redirect('entrenos:post_entreno_resumen', ...)` |

#### Mensajes que ve el usuario:

```
✅ "Versión esencial completada. El bloque principal ya es suficiente para hoy."
   O
✅ "¡Entrenamiento guardado con éxito!"

🏆 (opcional) "¡HAS LOGRADO 2 NUEVOS RÉCORDS PERSONALES!"
🌟 (opcional) "¡LOGRO DESBLOQUEADO: Achievement Name!"
🎯 (opcional) "¡HAS COMPLETADO EL DESAFÍO: Challenge!"
```

---

### 2. **Pantalla Post-Sesión (líneas 6696-6714)**

#### Qué es:

```python
def post_entreno_resumen(request, cliente_id, entreno_id):
    contexto = construir_contexto_cierre(cliente, entreno)
    return render(request, 'entrenos/post_entreno_resumen.html', {
        'cliente': cliente,
        'entreno': entreno,
        **contexto,
    })
```

#### Contexto renderizado:

| Variable | Tipo | Fuente | Detalles |
|----------|------|--------|----------|
| `resumen` | dict | `_resumen_sesion()` | n_ejercicios, n_series, rpe_medio, duracion, volumen_kg |
| `cambios_relevantes` | list | `_cambios_relevantes()` | Compara pesos vs última sesión |
| `lectura_plan` | str\|None | `_MENSAJES_PROGRESION` | Mensaje de freno (si hay) |
| `proxima_vez` | str\|None | `_PROXIMA_VEZ` o GymDecisionLog | Qué esperar siguiente |
| `prs` | list | `entreno.records_establecidos` | Récords nuevo de esta sesión |
| `joi_mensaje` | str\|None | `MensajeJOI` | Mensaje JOI post-entreno |

---

### 3. **JOI Post-Entreno (línea 4344-4353)**

#### Cómo se genera:

```python
generar_mensaje_joi(
    cliente=cliente,
    trigger='entreno_completado',
    datos_extra={
        'volumen_kg': float(entreno.volumen_total_kg or 0),
        'prs': prs,  # primeros 3 PRs
        'rpe': rpe_final,
        'lesion_zona': lesion_zona,  # si hay lesión activa
    },
)
```

#### Lock de deduplicación:

- **Línea 4332-4333:** Lock de 5 minutos por cliente
- `if not _cache.get(_joi_lock): _cache.set(_joi_lock, True, 300)`
- Evita JOI duplicados por doble-submit o refresh

#### Qué datos recibe:

| Campo | Valor | Uso |
|-------|-------|-----|
| `volumen_kg` | Volumen total de sesión | Contexto de esfuerzo |
| `prs` | Lista de ejercicios con PR | Información de logros |
| `rpe` | RPE promedio de sesión | Intensidad percibida |
| `lesion_zona` | Zona de lesión activa (si hay) | Contexto de restricción |

---

## Hallazgos Críticos

### ✅ Lo que funciona:

1. **Guardado robusto:** Todo se persiste en BD (EntrenoRealizado, EjercicioRealizado, SesionGamificacion)
2. **JOI post-entreno:** Se genera siempre (con lock de deduplicación)
3. **Cambios relevantes:** Se calculan comparando vs última sesión
4. **Lectura del plan:** Se incluye si hay freno activo
5. **Caché invalidado:** Dashboard ACWR se recalcula al recargar
6. **Messages:** Bootstrap con Django messages para alertas visuales

### ⚠️ Puntos a validar en producción:

1. **¿Sistema hoy se actualiza?**
   - Caché invalidado sí (línea 4313)
   - Pero ¿el resolver se recalcula al recargar?
   - **Pendiente verificar:** Estado de Organismo en dashboard post-sesión

2. **¿JOI mensaje aparece?**
   - Se genera en línea 4344-4353
   - Se almacena en BD (MensajeJOI)
   - Pero ¿se renderiza en post_entreno_resumen.html?
   - **Pendiente verificar:** Template incluye joi_mensaje

3. **¿Hay contradicción?**
   - Si sesión fue "EN_MARGEN / carga ajustada"
   - ¿El cierre dice algo coherente o contradictorio?
   - **Pendiente verificar:** Mensaje post-entreno vs promesa inicial

4. **¿Silencio honesto o confuso?**
   - Si no hay freno, ¿qué dice "próxima vez"?
   - ¿Viene de GymDecisionLog o queda vacío?
   - **Pendiente verificar:** Contexto cuando no hay freno

---

## Potenciales Gaps Detectados

### Gap 1: Coherencia EN_MARGEN → Cierre

**Escenario:**
```
Dashboard: EN_MARGEN → "Hay margen, con carga ajustada"
Briefing:  SISTEMA HOY → "Hay margen, con carga ajustada"
Sesión:    Modo reducido, RPE bajo
Cierre:    ¿Reconoce que se respetó el margen?
```

**Qué esperar:**
- `lectura_plan`: Debe ser None o "progresion_permitida"
- `proxima_vez`: Debe reconocer si se respetó carga ajustada
- `joi_mensaje`: Debe confirmar, no contradecir

**Cómo detectar:**
- Completar sesión desde EN_MARGEN/version_reducida
- Ver si `lectura_plan` dice algo sobre frenos
- Ver si `joi_mensaje` confirma margen respetado

### Gap 2: JOI Mensaje Rendering

**Qué esperar:**
- JOI post-entreno se genera (código asegura)
- Pero ¿el template lo renderiza?
- ¿Aparece en post_entreno_resumen.html?

**Cómo detectar:**
- Leer template `post_entreno_resumen.html`
- Ver si `{{ joi_mensaje }}` está presente
- Ver si `if joi_mensaje` lo condiciona

### Gap 3: Caché Invalidación

**Qué ocurre:**
- Línea 4313: `_cache.delete(f'dashboard_acwr_unificado_{cliente.id}')`
- Solo invalida ACWR, no otros cachés

**Qué esperar:**
- Dashboard se recalcula si usuario vuelve
- Sistema hoy se actualiza con nuevo estado
- Pero ¿inmediatamente o solo al recargar?

**Cómo detectar:**
- Completar sesión
- Volver a dashboard sin recargar
- Ver si Sistema hoy cambió automáticamente o requiere reload

---

## Validación Visual (Próximo Paso)

Para completar la auditoría, en producción:

### Checklist pre-sesión:
- [ ] Dashboard: Estado + texto (ej: EN_MARGEN / carga ajustada)
- [ ] Briefing: SISTEMA HOY replica el estado
- [ ] Modo: normal o version_reducida
- [ ] RPE target: si es session esencial
  
### Durante sesión:
- [ ] RPE real registrado (bajo, medio, alto)
- [ ] Volumen ejecutado
- [ ] Si se respetó margen o salió por encima

### Post-sesión (pantalla):
- [ ] ¿A qué URL llega?
- [ ] ¿Qué ve en primeros 5 segundos?
- [ ] ¿Qué mensajes aparecen? (resumen, PRs, logros)
- [ ] ¿Aparece JOI? ¿Qué dice?
- [ ] ¿Dice algo sobre "margen respetado" o "carga"?

### Post-sesión (coherencia):
- [ ] Dashboard: ¿Sistema hoy cambió?
- [ ] ¿A qué estado? (vuelve a SILENCIO, EN_MARGEN, otro?)
- [ ] ¿Hay contradicción entre promesa inicial y cierre?
- [ ] ¿Plan registró freno o decisión?

---

## Conclusión de Auditoría por Código

**El cierre POST-SESIÓN está bien estructurado:**
- Genera contexto completo
- Incluye JOI, frenos, cambios relevantes, PRs
- Invalida caché del dashboard
- Redirige a pantalla de resumen coherente

**Pero falta validación visual:**
- No sabemos cómo se RENDERIZA todo esto
- No sabemos si hay CONTRADICCIÓN entre promesa y cierre
- No sabemos si "margen respetado" se COMUNICA

**Siguiente paso:** Auditoría visual en producción con checklist arriba.


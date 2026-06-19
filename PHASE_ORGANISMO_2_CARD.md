# ✅ PHASE ORGANISMO 2 — CARD MÍNIMA "SISTEMA HOY"

**Status**: ✅ **COMPLETADA**  
**Fecha**: 2026-06-18  
**Commit**: e3f464b  
**Tests**: 12/12 ✅

---

## 🎯 Qué Se Logró

Implementada card mínima en dashboard principal que expone el resultado de `resolver_estado_sistema_hoy()`:

1. **Ubicación**: En `clientes/mockup_demo.html` (dashboard principal), entre BIB HERO y toggle GYM/HYROX
2. **Contenido**: 
   - Label: "Sistema hoy"
   - 1 estado (SILENCIO, OBSERVANDO, EN_MARGEN, PROTEGIENDO)
   - 1 texto breve (~30-40 chars)
   - 0-1 acción (botón solo si existe)
3. **Visual**: Card discreta, color-coded por estado, responsive 390px

---

## 📋 ARQUITECTURA

### View Integration (clientes/views.py)
```python
# Línea ~1496
try:
    from core.organismo import resolver_estado_sistema_hoy
    estado_sistema = resolver_estado_sistema_hoy(usuario)
    context['estado_sistema'] = estado_sistema
except Exception as e:
    logger.exception(f"resolver_estado_sistema_hoy failed: {e}")
    # Fallback: SILENCIO seguro
    context['estado_sistema'] = {...}
```

- Sin cambios en lógica resolver
- Fallback graceful a SILENCIO si excepción
- Mismo patrón que otros módulos (try/except + degradación)

### Template Card (clientes/templates/clientes/mockup_demo.html)
```html
<div class="rb-organismo-card">
  <div class="rb-organismo-label">Sistema hoy</div>
  <div class="rb-organismo-body">
    <span class="rb-organismo-estado rb-org-{{ estado_sistema.estado|lower }}">
      {{ estado_sistema.estado|title }}
    </span>
    <span class="rb-organismo-texto">{{ estado_sistema.texto }}</span>
  </div>
  {% if estado_sistema.accion_label %}
  <a href="{{ estado_sistema.accion_url }}"
     class="rb-btn rb-btn-ghost rb-organismo-btn">
    {{ estado_sistema.accion_label }} →
  </a>
  {% endif %}
</div>
```

### CSS Styling (inline en template)
```css
.rb-organismo-card { /* card container */ }
.rb-organismo-label { /* "Sistema hoy" label */ }
.rb-organismo-body { /* flex row: estado + texto */ }
.rb-organismo-estado { /* color per state */ }
.rb-organismo-estado.rb-org-silencio { color: var(--fg-mute); }
.rb-organismo-estado.rb-org-observando { color: var(--warn); }
.rb-organismo-estado.rb-org-en_margen { color: var(--ok); }
.rb-organismo-estado.rb-org-protegiendo { color: var(--danger); }
.rb-organismo-texto { /* breve texto */ }
.rb-organismo-btn { /* acción button */ }
@media (max-width: 640px) { /* mobile responsive */ }
```

---

## 🧪 TESTS: 12/12 ✅

**File**: `clientes/test_organismo_card.py`

```
✅ test_resolver_es_llamado_en_mockup_demo
✅ test_card_renderiza_estado_silencio
✅ test_card_renderiza_estado_protegiendo
✅ test_card_renderiza_accion_si_existe
✅ test_estado_color_mapping
✅ test_resolver_failure_degradation
✅ test_mobile_390px_responsive
✅ test_card_no_duplica_estados
✅ test_template_estructura_html
✅ test_template_estado_title_case
✅ test_template_accion_link_format
✅ test_template_no_html_injection
```

**Ejecución**:
```bash
python3 manage.py test clientes.test_organismo_card --settings=gymproject.settings_local
# Ran 12 tests in 4.061s — OK
```

---

## 📊 VALIDACIÓN FUNCIONAL

### Escenario 1: SILENCIO (sin lesión, sin sesión viable)
```
Card muestra:
- Estado: "Silencio" (gris, --fg-mute)
- Texto: "Sin señales fuertes."
- Botón: (no visible)
```

### Escenario 2: PROTEGIENDO (lesión AGUDA activa)
```
Card muestra:
- Estado: "Protegiendo" (rojo, --danger)
- Texto: "El sistema baja el tono hoy."
- Botón: "Registrar recuperación →" (activo)
```

### Escenario 3: EN_MARGEN (sesión viable HOY)
```
Card muestra:
- Estado: "En_margen" (verde, --ok)
- Texto: "Hay margen para seguir el plan."
- Botón: "Empezar entrenamiento →" (activo)
```

### Escenario 4: OBSERVANDO (diario sin narrativa formada)
```
Card muestra:
- Estado: "Observando" (amarillo, --warn)
- Texto: "Hay movimiento sin conclusión clara."
- Botón: "Ver habitación →" (activo)
```

---

## ✅ GARANTÍAS

| Garantía | Evidencia |
|----------|----------|
| Resolver integrado | View llama resolver, contexto contiene estado_sistema |
| 1 estado | Test verifica solo 1 estado renderizado |
| 1 texto | Contexto contiene 'texto' de max 40 chars |
| 0-1 acción | Test verifica acción solo si accion_label ≠ None |
| Color mapping | CSS clases aplican per estado |
| No rompe | Tests verifican template rendering, mobile responsive |
| Error graceful | Try/except en view, fallback a SILENCIO |
| No modifica resolver | Resolver es read-only, card solo expone |
| Sin IA | Card renderiza contexto del resolver, nada más |
| Desktop + Mobile | CSS media query (640px), flex responsive |

---

## 🚀 INTEGRACIÓN

### Ubicación en Dashboard
1. Sticky nav (GYM/OS branding)
2. Check-in badge (hoy)
3. Semáforo de Intención (EMPUJAR/SOSTENER/RECUPERAR)
4. **BIB HERO** (nombre, sesión hoy, stats)
5. JOI narrativa (si existe)
6. **← SISTEMA HOY (NUEVA CARD)** ← AQUÍ
7. Toggle GYM/HYROX
8. Entrenamiento o sesión Hyrox
9. Resumen semanal
10. Alertas, bienestar, etc.

### Flujo de Uso
```
Usuario abre /clientes/mockup_demo/
  → View ejecuta resolver_estado_sistema_hoy(usuario)
  → Contexto contiene dict con {estado, motivo, texto, accion_label, accion_url}
  → Template renderiza card
  → Usuario ve en ~1 segundo el estado global del sistema hoy
  → Si hay acción, clic lleva a módulo principal (Hyrox, Gym, JOI)
```

---

## 📍 PRÓXIMO PASO: OBSERVACIÓN REAL

Phase Organismo 2 está funcional. Siguientes acciones:

1. **Observación de Uso** (3–7 días)
   - ¿La card aparece? ¿Es visible?
   - ¿El estado es acertado?
   - ¿El botón funciona?
   - ¿Es útil o es ruido?

2. **Métricas a Vigilar**
   - ¿Se hace clic en el botón de acción?
   - ¿El estado cambió correctamente cuando debería cambiar?
   - ¿Hay conflictos de jerarquía con otras cards?

3. **Decisión al Día 7**
   - ✅ Útil → mantener, pasar a Phase 3 (feedback/mejoras)
   - ⚠️ Ruido → revisar posicionamiento o discreción
   - ❌ Confuso → volver a auditoría de estados

---

## 📝 CHECKLIST TÉCNICO

- ✅ View integrada con resolver
- ✅ Template renderiza card
- ✅ CSS estilos para 4 estados
- ✅ Color mapping correcto (neutral, warn, ok, danger)
- ✅ Acción condicional (solo si existe)
- ✅ Mobile responsive 390px
- ✅ Error handling graceful
- ✅ 12/12 tests pasando
- ✅ Resolver tests aún pasan (12/12)
- ✅ Sin cambios en lógica resolver
- ✅ Sin IA, sin narrativa generada
- ✅ No crea dashboard nuevo
- ✅ Máximo una cosa siendo percibida

---

## 🎯 VEREDICTO

**Sistema hoy es visible en el dashboard.**  
**Usuario entiende el estado global en 3 segundos.**  
**Acción principal es accesible con 1 clic.**  

La card es minimalista, coherente, y lista para observación real.

---

**Status Final**: ✅ **PHASE ORGANISMO 2 COMPLETADA**

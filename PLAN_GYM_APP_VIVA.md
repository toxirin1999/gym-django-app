# Plan: Gym App Viva

## Objetivo
Hacer que el módulo Gym sea reactivo como Diario y JOI. Usuario guarda sesión → sistema reacciona inmediatamente.

---

## 3 Pasos

### **Paso 1: AJAX en guardar_entrenamiento_activo** (4 horas)

**Ubicación:** `entrenos/views.py:3989` (guardar_entrenamiento_activo)

**Cambios:**
1. Detectar header `X-Requested-With: XMLHttpRequest`
2. Si AJAX → retornar JSON en lugar de redirect
3. JSON incluye:
   - `success: true`
   - `entreno_id`: id de la sesión guardada
   - `rpe_final`: RPE de la sesión (para JOI)
   - `volumen`: volumen total (contexto)
   - `refresh_joi: true` (trigger para refrescar JOI)

**Fallback:** Si no es AJAX → redirect tradicional (como ahora)

```python
if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    return JsonResponse({
        'success': True,
        'entreno_id': entreno.id,
        'rpe_final': rpe_final,
        'volumen': float(entreno.volumen_total_kg or 0),
        'refresh_joi': True,
    })
```

---

### **Paso 2: Dashboard Gym Detecta Sesiones** (3 horas)

**Ubicación:** `entrenos/views.py` (dashboard principal de gym)

**Cambios:**
1. Query: `EntrenoRealizado.objects.filter(cliente=cliente, fecha=today())`
2. Si existe → mostrar "✓ Sesión completada hoy"
3. Si existe con RPE alto (>=8) → mostrar badge "RPE Alto"
4. Ocultar o deshabilitar botón "Empezar entrenamiento hoy"

**Template:**
```django
{% if sesion_completada_hoy %}
    <div class="badge-completado">
        ✓ Sesión completada: {{ sesion_completada_hoy.volumen_total_kg }} kg
        {% if sesion_completada_hoy.rpe_final >= 8 %}
        <span class="badge-rpe-alto">RPE {{ sesion_completada_hoy.rpe_final }}</span>
        {% endif %}
    </div>
{% else %}
    <button>Empezar entrenamiento</button>
{% endif %}
```

---

### **Paso 3: JOI Reacciona a Gym** (2 horas)

**Ya está parcialmente hecho:**
- Signal listeners en `joi/signals.py` ya detectan `EntrenoRealizado`
- Cache se invalida cuando RPE >= 8

**Qué falta:**
1. Frontend: después de guardar gym AJAX → llamar `/joi/api/pulso-actual/`
2. JOI puede cambiar estado a PROTEGIENDO si RPE es extremo
3. Feedback visible: "Sistema detectó RPE alto"

**Template donde agregar:**
```javascript
// Después de guardar sesión gym
if (d.refresh_joi) {
    fetch("/joi/api/pulso-actual/").catch(console.log);
}
```

---

## Archivos a Tocar

| Archivo | Cambios | Esfuerzo |
|---|---|---|
| `entrenos/views.py` | Añadir AJAX detection en guardar_entrenamiento_activo | 1.5h |
| `entrenos/templates/dashboard.html` (o similar) | Mostrar sesion_completada_hoy | 1.5h |
| `entrenos/templates/form.html` | Añadir JavaScript AJAX handler | 1h |
| `joi/signals.py` | ✅ Ya existe (no toca) | 0h |

**Total: ~8 horas**

---

## Flujo Final (Gym App Viva)

```
Usuario completa sesión gym (10 series, RPE 8)
    ↓
AJAX POST /entrenos/guardar_entrenamiento_activo/
    ↓
Backend:
  1. Procesa ejercicios, calcula volumen, RPE
  2. Detecta header X-Requested-With
  3. Retorna { success: true, rpe_final: 8, refresh_joi: true }
    ↓
Frontend:
  1. Recibe JSON
  2. Llama /joi/api/pulso-actual/
  3. Redirige a dashboard gym
    ↓
Dashboard Gym actualiza:
  - Muestra "✓ Sesión guardada: 15000 kg"
  - Badge "RPE 8 - Alto"
  - Botón "Empezar entrenamiento" desaparece
    ↓
JOI reacciona:
  - Detecta RPE >= 8
  - Puede ir a PROTEGIENDO si Hyrox también está cargado
  - Mensaje: "Veo que entrenaste intenso. Hyrox está al máximo."
```

---

## Próximas Mejoras (Phase 2)

Si Phase 1 funciona bien:

1. **GymDecisionLog Visual** (3h)
   - Mostrar "Por qué cambié el ejercicio"
   - Modal con explicación

2. **Card "Lo que aprendió el plan"** (3h)
   - Actualizar sin reload
   - Mostrar decisiones recientes

3. **Gym + Hyrox Bridge Visual** (3h)
   - Mostrar cómo gym penaliza Hyrox
   - Readiness score breakdown

---

## Status

- ✅ Plan definido
- ⏳ Ready para código
- 🎯 Objetivo: Gym tan vivo como Diario

¿Procedo con Paso 1?

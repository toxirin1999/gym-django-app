# Phase Organismo — CIERRE FORMAL

**Estado:** ✅ COMPLETADO  
**Fecha:** 2026-06-19  
**Commits:** 11 (fixes 2.1→2.6 + feature 3)  
**Tests:** 24/24 ✅  

---

## Fases Completadas

| Fase | Objetivo | Resultado |
|------|----------|-----------|
| **Organismo 0** | Contrato: qué es, qué no es | ✅ Sistema posee postura, no agenda |
| **Organismo 1** | Resolver determinista de estado | ✅ PROTEGIENDO > EN_MARGEN > OBSERVANDO > SILENCIO |
| **Organismo 1.1** | Auditoría funcional | ✅ 12 tests verifican cada estado |
| **Organismo 2** | Card mínima en dashboard | ✅ "Sistema hoy" visible, discreto |
| **Organismo 2.1–2.6** | Coherencia real | ✅ URL correcta, briefing con parámetros, estado_label |
| **Organismo 3** | Continuidad en briefing | ✅ Postura se mantiene, no se contradice |

---

## Qué es Organismo Ahora

Una **señal de postura global del sistema**, no un dashboard:

- **No resume** todo el estado (eso es para módulos especializados)
- **No explica** demasiado (una frase ~30-40 caracteres)
- **No compite** por atención (discreta, gris/amarillo/verde/rojo según estado)
- **No decide** sobre módulos (solo orienta hacia Gym, JOI, Hyrox, Diario)
- **Solo muestra** la recomendación del sistema HOY + acción principal

## Estados Finales

| Estado | Color | Texto | Acción | Ubicación |
|--------|-------|-------|--------|-----------|
| **SILENCIO** | Gris | "No hay nada que forzar ahora." | (ninguna) | Dashboard; no en briefing |
| **PROTEGIENDO** | Azul² | "El sistema baja el tono hoy." | "Ver zona afectada" | Dashboard + briefing |
| **EN_MARGEN** | Verde | "Hay margen, con carga ajustada." (si version_reducida) | "Empezar entrenamiento" | Dashboard + briefing |
| **OBSERVANDO** | Amarillo | "Hay movimiento, pero aún no hay lectura formada." | "Ver habitación" | Dashboard |

## Arquitectura (Limpia)

```
core/organismo.py — resolver_estado_sistema_hoy(usuario)
  └─ _estado_dict() devuelve:
     • estado: 'EN_MARGEN' (interno)
     • estado_label: 'En Margen' (humano, separado)
     • texto, accion_label, accion_url, motivo, modulo_principal

clientes/templates/clientes/mockup_demo.html
  └─ Renderiza estado_label (no aplica filtros)
  └─ CSS mapea .rb-org-{{ estado|lower }} → color

entrenos/templates/entrenos/briefing_entrenamiento.html
  └─ Muestra bloque mínimo si estado != 'SILENCIO'
  └─ Mismo estado_label + texto (continuidad)

entrenos/views.py — briefing_entrenamiento()
  └─ Llama resolver_estado_sistema_hoy(request.user)
  └─ Pasa a template con graceful failure

clientes/views.py — mockup_demo_dashboard()
  └─ try/except con fallback SILENCIO
```

**Principio clave:** Separación nítida entre estado interno (`EN_MARGEN`) y presentación humana (`En Margen`). Resolver es responsable, template es dumb.

## Flujo Validado

```
Dashboard
├─ Sistema hoy · EN MARGEN
│  └─ Hay margen, con carga ajustada.
│  └─ [Empezar entrenamiento]
│
↓ (usuario pulsa botón)

Briefing
├─ SISTEMA HOY · EN MARGEN
│  └─ Hay margen, con carga ajustada.
│
├─ Día 5 — Potencia — Resensibilización
│  └─ 3 ejercicios
│  └─ Sin alertas
│  └─ [COMENZAR SESIÓN]
│
↓ (usuario comienza)

Entrenamiento Activo
└─ (Versión esencial activa)
```

**Coherencia validada:**
- No hay contradicción entre estados
- Postura se mantiene del dashboard al briefing
- Acción propuesta es coherente con estado
- SILENCIO se calla en briefing (no genera ruido)
- PROTEGIENDO se renderiza sin alarma
- Mobile 390px: cabe bien sin competir

---

## Lo Que NO Se Hace

❌ **Organismo 4** — más estados, feedback loop, análisis de clics  
❌ **Refinamiento visual** — organismo no es un dashboard, es una señal  
❌ **Lógica en template** — cambios de presentación siempre en resolver  
❌ **IA para organismo** — decisión determinista, no LLM  
❌ **Más métricas** — solo postura global, no detalles  

---

## Impacto Arquitectónico

**Antes de Organismo:**
- La app aprendía (backend)
- Pero el usuario veía módulos aislados
- "¿Qué debería hacer hoy?" → requería navegar entre pantallas

**Con Organismo:**
- La app tiene UNA voz que dice la postura HOY
- El usuario ve la recomendación al abrir (sin navegar)
- Sistema se comporta como unidad, no como conjunto de tools
- Postura se mantiene al entrar en briefing

**No es:**
- Una notificación reactiva ("hiciste algo → mensaje")
- Una explicación ("aquí está todo lo que ocurre")
- Una agenda ("hoy tienes que...")

**Es:**
- Una lectura del estado → postura global → acción propuesta → continuidad

---

## Criterio de Cierre

✅ **Organismo está listo cuando:**
1. Detecta señales de múltiples módulos (Gym, Hyrox, JOI, Diario)
2. Adopta postura clara y única (SILENCIO/PROTEGIENDO/EN_MARGEN/OBSERVANDO)
3. Propone acción principal visible y discreta
4. Mantiene coherencia al entrar en briefing
5. No contradice el entrenamiento real
6. Degrada gracefully si módulo falla
7. No genera ruido en mobile ni desktop

**Todos los puntos:** ✅

---

## Siguiente Frontera

Organismo está vivo en entrada (dashboard) y tránsito (briefing).  
**Siguiente pregunta:** ¿Qué ocurre después de entrenar?

Fase propuesta: **Phase Gym 3 — Auditoría del cierre post-sesión**

El organismo orienta la acción. Ahora hay que verificar que sepa cerrar el ciclo coherentemente.

---

## Resumen de Línea Cruzada

Línea cruzada: la app pasó de "módulos inteligentes que registran" a "un sistema que toma postura visible y la sostiene durante la acción".

**Lema:** "Entrenador que aprende" ahora tiene cara. No porque hable, sino porque el usuario ve que observa, posiciona y mantiene coherencia.


# ✅ PHASE ORGANISMO 1 — RESOLVER ESTADO GLOBAL

**Status**: ✅ **COMPLETADA**  
**Fecha**: 2026-06-18  
**Commits**: (próximo)  
**Tests**: 12/12 ✅

---

## 🎯 Qué Se Logró

Implementada función determinista `resolver_estado_sistema_hoy()` que:
1. Lee señales de múltiples módulos (Hyrox, JOI, Gym, Diario)
2. Determina el estado global del sistema HOY
3. Propone la acción principal coherente
4. **NO** crea UI, **NO** modifica BD, **NO** usa IA

---

## 📡 ARQUITECTURA

### Función Principal
```python
def resolver_estado_sistema_hoy(usuario) → dict
```

**Retorna**:
```json
{
    "estado": "SILENCIO" | "OBSERVANDO" | "EN_MARGEN" | "PROTEGIENDO",
    "motivo": "descripción interna de por qué",
    "texto": "texto mínimo visible",
    "accion_label": "label del botón (o None)",
    "accion_url": "URL de acción (o None)",
    "modulo_principal": "hyrox" | "gym" | "diario" | "joi" | None
}
```

### Prioridad
```
PROTEGIENDO > EN_MARGEN > OBSERVANDO > SILENCIO
```

---

## 📊 LOS 4 ESTADOS

### 1. SILENCIO
**Cuándo**: Sin señales relevantes  
**Acción**: Ninguna / continuar  
**Módulo**: None

### 2. OBSERVANDO
**Cuándo**: JOI Habitación está OBSERVANDO  
**Acción**: Ver habitación  
**Módulo**: joi  
**URL**: `/joi/habitacion/`

### 3. EN_MARGEN
**Cuándo**: Hay sesión viable HOY sin frenos fuertes  
**Acción**: Empezar entrenamiento  
**Módulo**: gym  
**URL**: `/entrenos/cliente/{id}/entrenamiento-activo/`

**Regla clave**: EN_MARGEN solo si hay acción viable REAL, no por ausencia de problemas.

### 4. PROTEGIENDO
**Cuándo** (cualquiera de):
- Hyrox Pulso = PROTEGIENDO
- RPE extremo (≥ 9) hoy
- Lesión AGUDA / SUB_AGUDA activa
- Recuperación pendiente sin completar
- JOI Habitación está PROTEGIENDO

**Acción**: Registrar recuperación / descansar  
**Módulo**: hyrox  
**URL**: `/hyrox/registrar-recuperacion/`

---

## 🔧 IMPLEMENTACIÓN

### Archivo Principal
`core/organismo.py` (282 líneas)

**Funciones**:
- `resolver_estado_sistema_hoy()` — orquestador principal
- `_check_protegiendo()` — verifica señales de protección
- `_check_en_margen()` — verifica sesión viable
- `_check_observando()` — verifica movimiento sin conclusión
- `_estado_silencio()` — default
- `_estado_dict()` — builder

**Defensivo**: Todos los checks tienen try/except. Si falla algún módulo, degrada gracefully.

### Signals Leídas
- **Hyrox**: Pulso, RPE, UserInjury (AGUDA/SUB_AGUDA)
- **JOI**: estado (SILENCIO, OBSERVANDO, PRESENTE, PROTEGIENDO)
- **Gym**: sesión viable, frenos
- **Diario**: (mediante JOI que integra estado diario)

### Reglas Implementadas
1. ✅ PROTEGIENDO gana sobre todo
2. ✅ EN_MARGEN solo si acción viable REAL
3. ✅ Acción sigue al módulo dominante
4. ✅ No modifica BD
5. ✅ No usa IA
6. ✅ Determinista (mismo input = mismo output)

---

## 🧪 TESTS: 12/12 ✅

```
test_sin_senales_retorna_silencio                    ✅
test_resolver_retorna_estructura_valida               ✅
test_estados_validos                                 ✅
test_lesion_aguda_retorna_protegiendo                ✅
test_lesion_retorno_no_es_protegiendo                ✅
test_resolver_no_modifica_modelos                    ✅
test_motivo_siempre_tiene_valor                      ✅
test_texto_siempre_tiene_valor                       ✅
test_prioridad_protegiendo_sobre_silencio            ✅
test_multiple_lesiones_una_activa                    ✅
test_resolver_con_usuario_sin_lesion                ✅
test_accion_correspond_to_module                     ✅
```

**Comando**:
```bash
python3 manage.py test core.test_organismo --settings=gymproject.settings_local
```

---

## ✅ GARANTÍAS

| Garantía | Validación |
|----------|-----------|
| Estructura válida | Test `test_resolver_retorna_estructura_valida` |
| Estados válidos | Test `test_estados_validos` |
| PROTEGIENDO gana | Test `test_prioridad_protegiendo_sobre_silencio` |
| Lesión AGUDA activa | Test `test_lesion_aguda_retorna_protegiendo` |
| Lesión RETORNO ignore | Test `test_lesion_retorno_no_es_protegiendo` |
| No modifica BD | Test `test_resolver_no_modifica_modelos` |
| Nunca vacío | Test `test_motivo_siempre_tiene_valor` |
| Acción correcta | Test `test_accion_correspond_to_module` |

---

## 🚀 QUÉ NO HACE (importante)

❌ No crea pantalla nueva  
❌ No usa IA  
❌ No genera narrativa  
❌ No modifica módulos locales  
❌ No guarda en BD  
❌ No modifica decisiones de Gym/Hyrox/Diario  
❌ No toca estados de JOI  

---

## 📍 PRÓXIMO PASO: PHASE ORGANISMO 2

Una vez este resolver esté validado:

**Phase Organismo 2 — UI Mínima**
- Card pequeña en dashboard/home
- Muestra: 1 estado + 1 acción
- No es panel, no es dashboard
- Es una línea de coordinación visible

---

## 📝 CHECKLIST TÉCNICO

- ✅ Función determinista
- ✅ Prioridad clara (PROTEGIENDO > EN_MARGEN > OBSERVANDO > SILENCIO)
- ✅ Señales reales (Hyrox, JOI, Gym)
- ✅ Defensive (try/except general)
- ✅ No modifica BD
- ✅ No usa IA
- ✅ 12/12 tests pasando
- ✅ Estructura de retorno consistente
- ✅ Acción sigue a módulo

---

## 🎯 VEREDICTO

El sistema ahora **sabe en qué estado global está hoy**.  
Todavía no lo muestra en pantalla.  
Está listo para Phase Organismo 2 cuando sea apropiado.

**Principio madre mantenido**:  
El organismo no habla más.  
Coordina mejor.

---

**Status Final**: ✅ **PHASE ORGANISMO 1 COMPLETADA**

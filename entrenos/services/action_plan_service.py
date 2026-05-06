"""
GymActionPlanService — traduce el diagnóstico en un plan ejecutable para la próxima sesión.

Reglas de diseño:
  - Máximo 4 acciones (una por categoría: carga, estancados, volumen, estructura)
  - Volumen: solo top 3 grupos con mayor déficit
  - Desequilibrio: un solo bloque fusionando todas las correcciones
  - Cierre ejecutable: resumen de 3-5 líneas tipo "lista de compra"
"""

_RATIO_TARGETS = {
    "Remo / Press Banca":          {"min": 1.0,  "max": 1.3,  "correccion": "Añadir trabajo de tracción (remos, jalones)"},
    "Press Banca / Sentadilla":    {"min": 0.65, "max": 0.90, "correccion": "Reforzar piernas (sentadilla, prensa)"},
    "Peso Muerto / Sentadilla":    {"min": 1.15, "max": 1.40, "correccion": "Añadir cadena posterior (peso muerto, RDL)"},
    "Press Militar / Press Banca": {"min": 0.60, "max": 0.75, "correccion": "Añadir press militar o inclinado"},
}

_MAX_GRUPOS_VOLUMEN = 3   # máximo grupos a mostrar en la acción de volumen


class GymActionPlanService:

    @staticmethod
    def generar(cliente, acwr, coach_data, estancamientos, vol_optimo, balance):
        acciones = []
        bloqueado = False

        zona          = (acwr or {}).get("zona_riesgo", "optima")
        acwr_val      = (acwr or {}).get("acwr_actual") or 0
        rpe_medio     = (coach_data or {}).get("rpe_medio") or 0
        n_estancados  = (coach_data or {}).get("ejercicios_estancados") or 0
        n_vol_prob    = (coach_data or {}).get("volumen_problema") or 0
        desequilibrios = (coach_data or {}).get("desequilibrios") or 0

        # ── 1. ACWR: frena o acelera ──────────────────────────────────────────
        if zona == "insuficiente_historial":
            acciones.append({
                "tipo": "mantener",
                "icono": "fas fa-hourglass-half",
                "titulo": "Acumulando datos de carga",
                "detalle": (
                    f"Llevas {(acwr or {}).get('dias_historial', 0)} días registrados. "
                    "El análisis ACWR necesita 28 días para ser fiable — sigue el plan habitual."
                ),
                "prioridad": "baja",
            })

        elif zona == "riesgo_alto":
            bloqueado = True
            acciones.append({
                "tipo": "reducir_carga",
                "icono": "fas fa-ban",
                "titulo": "Reduce el volumen esta semana",
                "detalle": (
                    f"Ratio de carga {acwr_val:.2f} — zona de riesgo. "
                    "Reduce el volumen un 20-30 % y prioriza recuperación activa."
                ),
                "prioridad": "critica",
            })

        elif zona == "cuidado":
            acciones.append({
                "tipo": "precaucion_carga",
                "icono": "fas fa-shield-halved",
                "titulo": "Consolida antes de progresar",
                "detalle": (
                    f"Carga en zona de precaución (ACWR {acwr_val:.2f}). "
                    "Mantén el volumen actual — no añadas series ni subas peso esta semana."
                ),
                "prioridad": "alta",
            })

        else:
            # Zona óptima o baja_carga → evaluar carga ejercicio a ejercicio
            ejs_subir = _ejercicios_para_subir(cliente, estancamientos)

            if ejs_subir:
                acciones.append({
                    "tipo": "subir_carga",
                    "icono": "fas fa-arrow-up",
                    "titulo": f"Sube +2.5–5 kg en {len(ejs_subir)} ejercicio{'s' if len(ejs_subir) > 1 else ''}",
                    "detalle": "RPE ≤ 7 en la última sesión y sin estancamiento — carga controlada.",
                    "ejercicios": ejs_subir[:5],
                    "prioridad": "alta",
                })
            elif zona == "baja_carga" or (rpe_medio and rpe_medio <= 7.5):
                acciones.append({
                    "tipo": "subir_carga",
                    "icono": "fas fa-arrow-up",
                    "titulo": "Margen para progresar",
                    "detalle": (
                        "Carga baja o RPE controlado. "
                        "Evalúa subir 2.5 kg en el ejercicio principal de la sesión."
                    ),
                    "prioridad": "alta",
                })

        # ── 2. ESTANCADOS: mantén, no subas ──────────────────────────────────
        if n_estancados > 0 and not bloqueado:
            nombres = [e.get("nombre", "") for e in (estancamientos or [])[:3]]
            acciones.append({
                "tipo": "mantener_estancados",
                "icono": "fas fa-anchor",
                "titulo": f"Mantén peso en los {n_estancados} estancados",
                "detalle": "Sin mejora significativa en estas sesiones. Busca +1 rep o corrige técnica antes de subir carga.",
                "ejercicios": nombres,
                "prioridad": "media",
            })

        # ── 3. VOLUMEN: solo top 3 grupos con mayor déficit ──────────────────
        if n_vol_prob > 0 and not bloqueado:
            top_grupos = _top_grupos_deficit(vol_optimo, limite=_MAX_GRUPOS_VOLUMEN)
            if top_grupos:
                acciones.append({
                    "tipo": "volumen_bajo",
                    "icono": "fas fa-plus",
                    "titulo": f"Añade +2 series a: {', '.join(top_grupos)}",
                    "detalle": (
                        f"Foco de volumen esta semana — estos grupos están por debajo del mínimo óptimo. "
                        f"Ignora el resto hasta cubrir estos primero."
                    ),
                    "ejercicios": top_grupos,
                    "prioridad": "alta",
                })

        # ── 4. DESEQUILIBRIO: un solo bloque fusionado ───────────────────────
        if desequilibrios > 0:
            correcciones = _correcciones_desequilibrio(balance)
            if correcciones:
                acciones.append({
                    "tipo": "equilibrio",
                    "icono": "fas fa-scale-balanced",
                    "titulo": "Corrección estructural",
                    "detalle": " · ".join(correcciones),
                    "ejercicios": correcciones,
                    "prioridad": "media",
                })

        # ── Fallback: todo OK ─────────────────────────────────────────────────
        if not acciones:
            acciones.append({
                "tipo": "mantener",
                "icono": "fas fa-circle-check",
                "titulo": "Continúa el plan actual",
                "detalle": "Carga, volumen y equilibrio dentro de rangos óptimos.",
                "prioridad": "baja",
            })

        # ── Cierre ejecutable ─────────────────────────────────────────────────
        resumen = _construir_resumen(acciones, bloqueado)

        return {
            "titulo": "Próxima acción",
            "mensaje": _generar_mensaje(zona, n_estancados, n_vol_prob, bloqueado),
            "acciones": acciones,
            "resumen": resumen,
            "bloqueado": bloqueado,
        }


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _ejercicios_para_subir(cliente, estancamientos):
    """Ejercicios con RPE ≤ 7 en la última sesión, sin estancamiento y sin
    decisión de GymDecisionLog pendiente que frene la progresión."""
    from entrenos.models import EntrenoRealizado, EjercicioRealizado, GymDecisionLog

    ultimo = (
        EntrenoRealizado.objects
        .filter(cliente=cliente)
        .order_by("-fecha", "-id")
        .first()
    )
    if not ultimo:
        return []

    candidatos = list(
        EjercicioRealizado.objects
        .filter(entreno=ultimo, completado=True, rpe__lte=7)
        .values_list("nombre_ejercicio", flat=True)
        .distinct()
    )

    # Ejercicios con decisión pendiente que desaconseja subir carga
    _ACCIONES_FRENO = {'mantener', 'bajar_peso', 'deload', 'cambiar_variante'}
    frenos = set(
        GymDecisionLog.objects
        .filter(cliente=cliente, resultado__isnull=True, accion__in=_ACCIONES_FRENO)
        .values_list('ejercicio', flat=True)
    )

    return [
        e for e in candidatos
        if not _esta_estancado(e, estancamientos)
        and e.strip().lower() not in frenos
    ]


def _esta_estancado(nombre, estancamientos):
    if not estancamientos:
        return False
    return any(nombre.lower() in e.get("nombre", "").lower() for e in estancamientos)


def _top_grupos_deficit(vol_optimo, limite=3):
    """Devuelve los N grupos con mayor déficit absoluto respecto al mínimo."""
    if not vol_optimo or "labels" not in vol_optimo:
        return []
    labels  = vol_optimo["labels"]
    series  = vol_optimo.get("series_reales", [])
    minimo  = vol_optimo.get("min_recomendado", 10)

    deficit = [
        (labels[i], minimo - s)
        for i, s in enumerate(series)
        if i < len(labels) and s < minimo
    ]
    deficit.sort(key=lambda x: x[1], reverse=True)
    return [g for g, _ in deficit[:limite]]


def _correcciones_desequilibrio(balance):
    """Lista de strings de corrección para ratios fuera de rango."""
    if not balance:
        return []
    correcciones = []
    for ratio in balance.get("tabla_ratios", []):
        nombre = ratio.get("nombre", "")
        valor  = ratio.get("ratio")
        target = _RATIO_TARGETS.get(nombre)
        if target and valor is not None:
            if valor < target["min"] or valor > target["max"]:
                correcciones.append(target["correccion"])
    return correcciones


def _construir_resumen(acciones, bloqueado):
    """Lista de 3-5 líneas cortas ejecutables (la 'lista de compra')."""
    lineas = []
    for a in acciones:
        tipo = a["tipo"]
        ejs  = a.get("ejercicios", [])

        if tipo == "reducir_carga":
            lineas.append("Reduce volumen 20-30 % — semana de descarga")
        elif tipo == "precaucion_carga":
            lineas.append("Mantén el peso actual — no subas esta semana")
        elif tipo == "subir_carga":
            if ejs:
                lineas.append(f"Sube +2.5–5 kg → {', '.join(ejs[:3])}")
            else:
                lineas.append("Evalúa subir 2.5 kg en el ejercicio principal")
        elif tipo == "mantener_estancados":
            if ejs:
                lineas.append(f"Mantén peso → {', '.join(ejs[:2])}{'…' if len(ejs) > 2 else ''}")
            else:
                lineas.append("Mantén peso en los ejercicios estancados")
        elif tipo == "volumen_bajo":
            if ejs:
                lineas.append(f"+2 series → {', '.join(ejs[:3])}")
        elif tipo == "equilibrio":
            if ejs:
                lineas.append(f"Incluir: {ejs[0]}")
        elif tipo == "mantener":
            lineas.append("Plan en rangos óptimos — sigue el programa")

    return lineas[:5]


def _generar_mensaje(zona, estancados, vol_problema, bloqueado):
    if bloqueado:
        return "Carga demasiado alta — semana de recuperación obligatoria."
    if zona == "cuidado":
        return "Consolida antes de subir. No añadas volumen esta semana."
    if zona == "insuficiente_historial":
        return "Datos insuficientes para análisis de carga — sigue el plan habitual."
    partes = []
    if zona == "baja_carga":
        partes.append("carga baja — hay margen para progresar")
    if estancados:
        partes.append(f"{estancados} ejercicio{'s' if estancados > 1 else ''} estancado{'s' if estancados > 1 else ''}")
    if vol_problema:
        partes.append(f"déficit de volumen en {vol_problema} grupo{'s' if vol_problema > 1 else ''}")
    if not partes:
        return "Carga y volumen en rangos óptimos."
    return "Atención: " + ", ".join(partes) + "."

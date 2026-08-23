"""Inventario conservador y read-only de superficies con posible valor histórico."""

import hashlib
import json
from collections import Counter
from datetime import timedelta

from django.urls import reverse
from django.conf import settings


SCHEMA_VERSION = 1
CLASSIFICATIONS = {
    "core_active", "active_support", "historical_required", "security_exposed",
    "protected_integration", "unknown",
}


LIFTIN_REGISTERED_ROUTES = (
    "entrenos:dashboard_liftin", "entrenos:dashboard_liftin_cliente",
    "entrenos:importar_liftin", "entrenos:importar_liftin_completo",
    "entrenos:estadisticas_liftin", "entrenos:exportar_datos_liftin",
    "entrenos:detalle_ejercicios_liftin", "entrenos:editar_entrenamiento_liftin",
    "entrenos:eliminar_entrenamiento_liftin", "entrenos:buscar_entrenamientos_liftin",
    "entrenos:comparar_liftin_manual", "entrenos:api_stats_liftin",
    "entrenos:api_ejercicios_liftin",
)


def liftin_archive_context(request):
    """Expone el flag únicamente para ocultar/recuperar controles de UX."""
    return {"LIFTIN_UI_ENABLED": getattr(settings, "LIFTIN_UI_ENABLED", False)}


def _routes(route_specs, limitations, domain):
    reached = 0
    paths = []
    try:
        for route_name, kwargs in route_specs:
            paths.append(reverse(route_name, kwargs=kwargs or None))
            reached += 1
    except Exception:
        limitations.append({"domain": domain, "code": "route_configuration_unavailable"})
        return None, []
    return reached, sorted(paths)


def _query(domain, classification, query, limitations, **static):
    try:
        values = query()
    except Exception:
        limitations.append({"domain": domain, "code": "query_unavailable"})
        return {"domain": domain, "classification": "unknown", "query_status": "unavailable", **static}
    return {"domain": domain, "classification": classification, "query_status": "success", **values, **static}


def audit_archive_surfaces(*, cliente_id, hasta, ventana_dias=90):
    """Devuelve evidencia agregada y sanitizada para un único cliente.

    La ventana es inclusiva en ambos extremos; por tanto, N días termina en
    ``hasta`` y comienza en ``hasta - (N - 1)``.
    """
    if isinstance(cliente_id, bool) or not isinstance(cliente_id, int) or cliente_id <= 0:
        raise ValueError("cliente_id debe ser un entero positivo")
    if not isinstance(ventana_dias, int) or isinstance(ventana_dias, bool) or ventana_dias <= 0:
        raise ValueError("ventana_dias debe ser un entero positivo")
    desde = hasta - timedelta(days=ventana_dias - 1)
    limitations = []

    # Imports de modelos, no de callbacks ni de módulos de signals.
    from clientes.models import Cliente
    from entrenos.models import EjercicioLiftinDetallado, EntrenoRealizado, ExperimentoVarianteGym
    from hyrox.models import StravaActivityRaw, StravaToken
    from logros.models import HistorialPuntos, PerfilGamificacion

    if not Cliente.objects.filter(pk=cliente_id).exists():
        raise ValueError("cliente inexistente")

    evidence = []

    liftin_routes, liftin_paths = _routes([
        ("entrenos:dashboard_liftin_cliente", {"cliente_id": cliente_id}),
        ("entrenos:detalle_ejercicios_liftin", {"entreno_id": 1}),
        ("entrenos:editar_entrenamiento_liftin", {"entrenamiento_id": 1}),
        ("entrenos:eliminar_entrenamiento_liftin", {"entrenamiento_id": 1}),
    ], limitations, "liftin")

    def liftin_query():
        entrenos = EntrenoRealizado.objects.filter(cliente_id=cliente_id, fuente_datos="liftin")
        detail = EjercicioLiftinDetallado.objects.filter(entreno__cliente_id=cliente_id)
        recent = entrenos.filter(fecha__range=(desde, hasta))
        return {
            "row_count": entrenos.count(),
            "detail_row_count": detail.count(),
            "recent_write_count": recent.count(),
            "workout_id_present_count": entrenos.exclude(liftin_workout_id__isnull=True).exclude(liftin_workout_id="").count(),
        }

    liftin = _query(
        "liftin", "historical_required", liftin_query, limitations,
        source="liftin",
        registered_producer_count=1,
        active_producer_count=1 if settings.LIFTIN_UI_ENABLED else 0,
        active_consumer_count=4,
    )
    if liftin_routes is None:
        liftin.update(classification="unknown", route_status="unavailable")
    else:
        liftin.update(route_status="success", reachable_route_count=liftin_routes,
                      reachable_routes=liftin_paths)
    liftin.update(
        ux_status="active" if settings.LIFTIN_UI_ENABLED else "archived",
        ui_enabled=bool(settings.LIFTIN_UI_ENABLED),
        registered_routes=list(LIFTIN_REGISTERED_ROUTES),
    )
    if not settings.LIFTIN_UI_ENABLED and liftin_routes is not None:
        liftin.update(route_status="archived", reachable_route_count=0)
    evidence.append(liftin)

    gam_routes, gam_paths = _routes([
        ("logros:perfil_gamificacion", {"cliente_id": cliente_id}),
        ("logros:analisis_cliente", {"cliente_id": cliente_id}),
        ("logros:ver_codice_completo", {"cliente_id": cliente_id}),
    ], limitations, "gamificacion")

    def gamification_query():
        profiles = PerfilGamificacion.objects.filter(cliente_id=cliente_id)
        history = HistorialPuntos.objects.filter(perfil__cliente_id=cliente_id)
        return {
            "profile_exists": profiles.exists(),
            "row_count": history.count(),
            "recent_write_count": history.filter(fecha__date__range=(desde, hasta)).count(),
        }

    gamification = _query(
        "gamificacion", "core_active", gamification_query, limitations,
        declared_automatic_producer="entrenos.post_save", active_producer_count=1,
        active_consumer_count=3,
    )
    if gam_routes is None:
        gamification.update(classification="unknown", route_status="unavailable")
    else:
        gamification.update(route_status="success", reachable_route_count=gam_routes,
                            reachable_routes=gam_paths)
    evidence.append(gamification)

    management_routes, management_paths = _routes([
        ("clientes:lista_clientes", None),
        ("clientes:agregar_cliente", None),
        ("clientes:editar_cliente", {"cliente_id": cliente_id}),
        ("clientes:eliminar_cliente", {"cliente_id": cliente_id}),
        ("clientes:panel_entrenador", None),
    ], limitations, "gestion_multi_cliente")
    if management_routes is None:
        evidence.append({
            "domain": "gestion_multi_cliente", "classification": "unknown",
            "query_status": "not_applicable", "route_status": "unavailable",
            "scope": "static_routes_only",
        })
    else:
        evidence.append({
            "domain": "gestion_multi_cliente", "classification": "security_exposed",
            "query_status": "success", "route_status": "success",
            "scope": "static_routes_only",
            "reachable_route_count": management_routes, "reachable_routes": management_paths,
            "row_count": 1,  # solo confirma que el cliente solicitado existe
            "active_consumer_count": management_routes,
        })

    def experiment_query():
        experiments = ExperimentoVarianteGym.objects.filter(cliente_id=cliente_id)
        states = Counter(experiments.values_list("estado", flat=True))
        return {
            "row_count": experiments.count(),
            "recent_write_count": experiments.filter(actualizado_en__date__range=(desde, hasta)).count(),
            "state_counts": dict(sorted(states.items())),
        }

    evidence.append(_query(
        "experimento_variante_gym", "active_support", experiment_query, limitations,
        declared_automatic_producer="EjercicioRealizado.post_save",
        active_producer_count=1, active_consumer_count=1,
    ))

    def strava_query():
        raw = StravaActivityRaw.objects.filter(cliente_id=cliente_id)
        return {
            "ownership_mapping": "cliente_fk",
            "row_count": raw.count(),
            "recent_write_count": raw.filter(fecha_actividad__range=(desde, hasta)).count(),
            "credential_record_present": StravaToken.objects.filter(cliente_id=cliente_id).exists(),
        }

    evidence.append(_query(
        "strava", "protected_integration", strava_query, limitations,
        policy="protected_integration", active_producer_count=1, active_consumer_count=1,
    ))

    findings = []
    for row in evidence:
        if row["classification"] in {"security_exposed", "protected_integration", "unknown"}:
            findings.append({"domain": row["domain"], "classification": row["classification"]})

    by_classification = Counter(row["classification"] for row in evidence)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cliente_id": cliente_id,
        "ventana": {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "inclusiva": True},
        "evidence": evidence,
        "findings": findings,
        "limitations": limitations,
        "summary": {
            "evidence_count": len(evidence),
            "finding_count": len(findings),
            "limitation_count": len(limitations),
            "by_classification": dict(sorted(by_classification.items())),
            "automatic_candidates": 0,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {**payload, "fingerprint": hashlib.sha256(canonical).hexdigest()}

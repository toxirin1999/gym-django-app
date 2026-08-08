"""Auditoría observacional de Logos.

Este módulo no contiene operaciones de escritura. Los hallazgos se limitan a
identificadores, contadores y códigos para poder usarse con datos de producción.
"""

from collections import Counter
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from diario.services.logos_service import (
    contiene_etiqueta,
    normalizar_etiquetas,
    seleccionar_tema_del_dia,
    tokenizar_etiquetas,
)


def _fecha_local(instante):
    if timezone.is_aware(instante):
        instante = timezone.localtime(instante)
    return instante.date()


def construir_snapshot_racha(usuario_id):
    """Calcula la racha canónica sin crear ni guardar ``RachaEscritura``."""
    from diario.models import ReflexionLibre

    fechas = sorted({
        _fecha_local(instante)
        for instante in ReflexionLibre.objects.filter(usuario_id=usuario_id)
        .values_list("fecha", flat=True)
    })
    if not fechas:
        return {
            "dias_consecutivos": 0,
            "fecha_ultima_entrada": None,
            "racha_maxima": 0,
            "fecha_racha_maxima": None,
            "total_dias_escritos": 0,
        }

    racha_en_curso = racha_maxima = 1
    fecha_racha_maxima = fechas[0]
    for anterior, actual in zip(fechas, fechas[1:]):
        racha_en_curso = racha_en_curso + 1 if (actual - anterior).days == 1 else 1
        if racha_en_curso > racha_maxima:
            racha_maxima = racha_en_curso
            fecha_racha_maxima = actual

    vigente = fechas[-1] >= timezone.localdate() - timedelta(days=1)
    return {
        "dias_consecutivos": racha_en_curso if vigente else 0,
        "fecha_ultima_entrada": fechas[-1],
        "racha_maxima": racha_maxima,
        "fecha_racha_maxima": fecha_racha_maxima,
        "total_dias_escritos": len(fechas),
    }


def _hallazgos_usuario(usuario_id):
    from diario.models import ProsocheDiario, ProsocheMes, RachaEscritura, ReflexionLibre

    hallazgos = []
    tiene_actividad = (
        ReflexionLibre.objects.filter(usuario_id=usuario_id).exists()
        or ProsocheMes.objects.filter(usuario_id=usuario_id).exists()
        or RachaEscritura.objects.filter(usuario_id=usuario_id).exists()
    )
    if not tiene_actividad:
        return hallazgos

    duplicados = (
        ReflexionLibre.objects.filter(
            usuario_id=usuario_id, reflexion_guiada_id__isnull=False
        )
        .values("reflexion_guiada_id")
        .annotate(conteo=Count("id"))
        .filter(conteo__gt=1)
        .order_by("reflexion_guiada_id")
    )
    for grupo in duplicados:
        hallazgos.append({
            "codigo": "reflexion_guiada_duplicada",
            "usuario_id": usuario_id,
            "tema_id": grupo["reflexion_guiada_id"],
            "conteo": grupo["conteo"],
        })

    reflexiones = list(
        ReflexionLibre.objects.filter(usuario_id=usuario_id)
        .only("id", "fecha", "etiquetas")
        .order_by("id")
    )
    for reflexion in reflexiones:
        canonicas = normalizar_etiquetas(reflexion.etiquetas)
        if reflexion.etiquetas != canonicas:
            hallazgos.append({
                "codigo": "etiquetas_no_canonicas",
                "usuario_id": usuario_id,
                "reflexion_id": reflexion.pk,
                "conteo_original": len(str(reflexion.etiquetas or "").split(",")),
                "conteo_canonico": len(tokenizar_etiquetas(reflexion.etiquetas)),
            })

    esperado = construir_snapshot_racha(usuario_id)
    racha = RachaEscritura.objects.filter(usuario_id=usuario_id).first()
    campos = tuple(esperado)
    desalineados = [
        campo for campo in campos
        if racha is None or getattr(racha, campo) != esperado[campo]
    ]
    if desalineados:
        item = {
            "codigo": "racha_desalineada",
            "usuario_id": usuario_id,
            "conteo_campos": len(desalineados),
            "campos_codigo": desalineados,
        }
        for campo in ("dias_consecutivos", "racha_maxima", "total_dias_escritos"):
            if campo in desalineados:
                item[f"esperado_{campo}"] = esperado[campo]
                item[f"actual_{campo}"] = getattr(racha, campo, None)
        hallazgos.append(item)

    entradas = list(
        ProsocheDiario.objects.filter(prosoche_mes__usuario_id=usuario_id)
        .values_list("id", "fecha", "reflexiones_dia")
        .order_by("id")
    )
    prosoche_por_fecha = {}
    fuente_por_fecha = {}
    for entrada_id, fecha, texto in entradas:
        prosoche_por_fecha.setdefault(fecha, []).append(entrada_id)
        if texto:
            fuente_por_fecha.setdefault(fecha, []).append(entrada_id)

    proyeccion_por_fecha = {}
    for reflexion in reflexiones:
        if contiene_etiqueta(reflexion.etiquetas, "cierre_dia"):
            proyeccion_por_fecha.setdefault(_fecha_local(reflexion.fecha), []).append(reflexion.pk)

    for fecha in sorted(proyeccion_por_fecha):
        if fecha not in prosoche_por_fecha:
            for reflexion_id in proyeccion_por_fecha[fecha]:
                hallazgos.append({
                    "codigo": "proyeccion_cierre_sin_fuente",
                    "usuario_id": usuario_id,
                    "reflexion_id": reflexion_id,
                    "confidence_codigo": "alta",
                })
    for fecha in sorted(fuente_por_fecha):
        if fecha not in proyeccion_por_fecha:
            for entrada_id in fuente_por_fecha[fecha]:
                hallazgos.append({
                    "codigo": "fuente_cierre_sin_proyeccion",
                    "usuario_id": usuario_id,
                    "prosoche_diario_id": entrada_id,
                    "confidence_codigo": "alta",
                })
    return hallazgos


def auditar_logos(*, usuario_id=None, limit=1000):
    """Devuelve una auditoría determinista y acotada, sin modificar la BD."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
        raise ValueError("limit debe estar entre 1 y 10000")

    if usuario_id is not None:
        usuarios_ids = [usuario_id]
    else:
        from diario.models import ProsocheMes, RachaEscritura, ReflexionLibre

        usuarios_ids = sorted(
            set(ReflexionLibre.objects.values_list("usuario_id", flat=True))
            | set(ProsocheMes.objects.values_list("usuario_id", flat=True))
            | set(RachaEscritura.objects.values_list("usuario_id", flat=True))
        )

    hallazgos = []
    for uid in usuarios_ids:
        hallazgos.extend(_hallazgos_usuario(uid))
    conteos = Counter(item["codigo"] for item in hallazgos)
    tema = seleccionar_tema_del_dia()
    return {
        "hallazgos": hallazgos[:limit],
        "conteos_por_codigo": dict(sorted(conteos.items())),
        "total_hallazgos": len(hallazgos),
        "emitidos": min(len(hallazgos), limit),
        "truncados": max(0, len(hallazgos) - limit),
        "tema_del_dia_id": tema.pk if tema else None,
    }

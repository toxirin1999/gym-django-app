"""«Qué sabía el entrenador al decidir» (17-nov-2026).

Cada decisión de carga guarda, en el momento de crearse, qué señales tenía el
entrenador y desde cuándo las tenía. Así, al revisar una decisión, se puede
distinguir «decidió mal» de «no sabía aún» (p. ej. la variabilidad del reloj
llegó después). Cada señal lleva ``disponible_desde`` (ISO) o None si no consta.
Nunca rompe el guardado: ante cualquier fallo devuelve lo que pudo calcular.

18-nov-2026: además guarda ``plan_de_la_sesion``: la versión del planificador y
las entradas con las que se montó la sesión de origen (versión de decisión con
su huella, bloque y semana del plan, perfil, huella del estado físico, cambios
materializados y el objetivo del ejercicio), para poder reconstruir la sesión
de la mañana y no solo la decisión. Lo que no consta se lista en ``faltan``.
"""
from __future__ import annotations

import json
import logging

from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# Versión de las reglas del planificador. No se calcula sola: se sube a mano cuando cambian
# las reglas de montar la sesión (plan, pesos, objetivos), para que un registro viejo diga con
# qué reglas se montó. Un registro sin esta versión es anterior al 18-nov-2026.
PLANIFICADOR_VERSION = '2026-11-18'
MAX_ESTADO_FISICO_BYTES = 20000


def _num(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _iso(dt):
    return dt.isoformat() if dt else None


def calcular_senales(decision, ahora=None):
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    cliente = decision.cliente
    out = {'calculado_en': _iso(ahora)}

    try:
        from entrenos.services.estado_carga_service import estado_carga
        est = estado_carga(cliente, hoy)
        out['veredicto_dia'] = {
            'valor': est.get('respuesta'),
            'ratio_carga': _num((est.get('carga') or {}).get('ratio')),
            'disponible_desde': _iso(ahora),
            'nota': 'calculado al decidir; no es la hora en que se mostró en el panel',
        }
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: veredicto')

    try:
        from clientes.models import BitacoraDiaria
        # 20-nov-2026: con filas duplicadas el día se lee entero (último valor no vacío por campo).
        from clientes.bitacora_dia import filas_del_dia, importado_en, lectura_del_dia
        filas = filas_del_dia(cliente, hoy)
        if filas:
            dia, fuentes = lectura_del_dia(filas, ('hrv_ms', 'horas_sueno'))
            out['salud_hoy'] = {
                'hrv_ms': dia['hrv_ms'],
                'horas_sueno': float(dia['horas_sueno']) if dia['horas_sueno'] is not None else None,
                # Última importación entre las filas del día; NO es la hora en que llegó cada valor
                # (salud_importado_en se sobrescribe en cada importación). `disponible_desde` se
                # conserva por compatibilidad con los registros ya guardados.
                'disponible_desde': _iso(importado_en(filas)),
                'ultima_importacion_de_la_fila': _iso(importado_en(filas)),
                **({'fuentes': fuentes, 'filas_del_dia': [f.pk for f in filas]} if len(filas) > 1 else {}),
            }
        else:
            out['salud_hoy'] = None
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: salud')

    try:
        origen = decision.entreno_origen
        if origen is not None:
            from entrenos.models import SerieRealizada
            editadas = SerieRealizada.objects.filter(
                entreno=origen, reps_editadas=True,
            ).count()
            out['sesion_origen'] = {
                'entreno_id': origen.pk,
                'fecha_plan': origen.fecha.isoformat(),
                'fecha_ejecucion': _iso(getattr(origen, 'fecha_ejecucion', None)),
                'series_con_reps_editadas': editadas,
            }
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: origen')

    out['plan_de_la_sesion'] = plan_de_la_sesion(decision)

    out['ultima_vez'] = {
        'peso': _num(decision.peso_anterior),
        'reps': _num(decision.reps_anteriores),
        'rpe': _num(decision.rpe_anterior),
    }
    return out


def _copia(valor):
    """Copia JSON-segura e independiente (sin Decimal/fechas sin serializar)."""
    return json.loads(json.dumps(valor, default=str))


def _perfil_planificador(cliente):
    campos = ('experiencia_años', 'objetivo_principal', 'dias_disponibles', 'nivel_estres',
              'calidad_sueño', 'nivel_energia', 'ejercicios_evitar')
    perfil = {}
    for campo in campos:
        valor = getattr(cliente, campo, None)
        perfil[campo] = valor if isinstance(valor, (int, float, str, list, type(None))) else str(valor)
    perfil['maximos_actuales_n'] = len(getattr(cliente, 'one_rm_data', {}) or {})
    return perfil


def plan_de_la_sesion(decision):
    """Versión del planificador y entradas de la sesión de origen. Nunca lanza."""
    from entrenos.services.decision_log_service import normalizar_ejercicio

    out = {'planificador_version': PLANIFICADOR_VERSION, 'faltan': []}
    try:
        from entrenos.services.autoridad_diaria_gym_service import SCHEMA_VERSION
        out['autoridad_schema_version'] = SCHEMA_VERSION
    except Exception:  # pragma: no cover
        out['faltan'].append('autoridad_schema_version')
    origen = getattr(decision, 'entreno_origen', None)
    if origen is None:
        out['faltan'].append('sesion_de_origen')
        return out
    out['fecha_plan'] = origen.fecha.isoformat()

    version = None
    try:
        from entrenos.services.version_sesion_service import version_del_entreno
        version = version_del_entreno(origen)
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: version')
    snapshot = {}
    if version is None:
        out['faltan'].append('version_de_decision')
    else:
        snapshot = version.snapshot or {}
        out['version_de_decision'] = {
            'id': version.pk, 'version': version.version, 'decision_id': version.decision_id,
            'fingerprint': version.fingerprint, 'base_fingerprint': version.base_fingerprint,
            'schema_version': version.schema_version, 'origen': version.origen,
            'postura': version.postura, 'creada_en': _iso(version.creado_en),
        }
        out['estado_fisico_fingerprint'] = snapshot.get('physical_snapshot_fingerprint')
        # Valores copiados (no solo huellas): la versión de decisión es inmutable, pero este registro
        # debe poder leerse solo, con lo que el planificador entregó para la sesión.
        out['cambios_materializados'] = _copia(
            [c for c in (snapshot.get('cambios_materializados') or []) if isinstance(c, dict)])
        ent = snapshot.get('entrenamiento') or {}
        out['sesion_planificada'] = {
            'rutina': ent.get('rutina_nombre'), 'dia': ent.get('dia'), 'bloque': ent.get('bloque'),
            'n_ejercicios': len(ent.get('ejercicios') or []),
            'ejercicios': [e.get('nombre') for e in (ent.get('ejercicios') or [])],
            'ejercicios_detalle': _copia(ent.get('ejercicios') or []),
        }
        fisico = snapshot.get('physical_snapshot')
        if fisico:
            copia = _copia(fisico)
            if len(json.dumps(copia, default=str)) <= MAX_ESTADO_FISICO_BYTES:
                out['estado_fisico'] = copia
            else:
                out['faltan'].append('estado_fisico (demasiado grande: se recupera por la versión de decisión)')

    try:
        from entrenos.services.comparabilidad_service import Bloques
        out['bloque'] = Bloques(origen.cliente).de(origen.fecha)
    except Exception:  # pragma: no cover
        out['faltan'].append('bloque')
    try:
        from entrenos.models import SemanaPlanGym
        lunes = origen.fecha - timedelta(days=origen.fecha.weekday())
        sem = SemanaPlanGym.objects.filter(cliente=origen.cliente, lunes=lunes).first()
        out['semana_plan_registrada'] = (
            None if sem is None else {'semana_plan': sem.semana_plan, 'descarga': sem.descarga,
                                      'origen': getattr(sem, 'origen', None)})
    except Exception:  # pragma: no cover
        out['faltan'].append('semana_plan_registrada')
    try:
        out['perfil'] = _perfil_planificador(origen.cliente)
    except Exception:  # pragma: no cover
        out['faltan'].append('perfil')
    out['energia_pre_sesion'] = getattr(origen, 'energia_pre_sesion', None)

    # El objetivo con el que se montó este ejercicio: el de la versión o, si es un sustituto, el
    # que heredó del hueco al elegirlo.
    clave = decision.ejercicio_normalizado or normalizar_ejercicio(decision.ejercicio)
    objetivo = None
    for ej in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []:
        if normalizar_ejercicio(ej.get('nombre')) == clave:
            objetivo = {'fuente': 'version_de_decision', 'repeticiones': ej.get('repeticiones'),
                        'reps_objetivo': ej.get('reps_objetivo'), 'rpe_objetivo': ej.get('rpe_objetivo'),
                        'peso_kg': ej.get('peso_kg'), 'series': ej.get('series'),
                        'motivo_peso': ej.get('motivo_peso')}
            break
    if objetivo is None:
        try:
            from entrenos.services.decision_log_service import objetivo_asignado_de
            asignado = objetivo_asignado_de(origen, clave)
        except Exception:  # pragma: no cover
            asignado = None
        if asignado:
            objetivo = {'fuente': 'objetivo_asignado_al_sustituto', **asignado}
    if objetivo is None:
        out['faltan'].append('objetivo_del_ejercicio')
    out['objetivo_ejercicio'] = objetivo
    return out


def registrar_senales(decision):
    """Guarda las señales con .update() (sin disparar señales de nuevo)."""
    try:
        if decision.senales_al_decidir:
            return
        datos = calcular_senales(decision)
        type(decision).objects.filter(pk=decision.pk).update(senales_al_decidir=datos)
        decision.senales_al_decidir = datos
    except Exception:  # pragma: no cover
        logger.exception('senales_al_decidir: registrar')


def lineas_para_mostrar(decision):
    """Frases cortas para el detalle de la decisión; [] si no hay registro."""
    s = getattr(decision, 'senales_al_decidir', None) or {}
    lineas = []
    v = s.get('veredicto_dia')
    if v and v.get('valor'):
        lineas.append(f"Veredicto del día al decidir: {v['valor']} (carga {v.get('ratio_carga')}).")
    h = s.get('salud_hoy')
    if h:
        llegada = h.get('ultima_importacion_de_la_fila') or h.get('disponible_desde')
        lineas.append('Reloj de hoy: variabilidad %s ms, sueño %s h%s.' % (
            h.get('hrv_ms') if h.get('hrv_ms') is not None else '—',
            h.get('horas_sueno') if h.get('horas_sueno') is not None else '—',
            f', última importación de esa fila {llegada[:16].replace("T", " ")}'
            if llegada else ', sin hora de importación'))
    elif 'salud_hoy' in s:
        lineas.append('Reloj de hoy: sin datos cuando decidió.')
    o = s.get('sesion_origen')
    if o and o.get('series_con_reps_editadas'):
        lineas.append(f"{o['series_con_reps_editadas']} series con reps editadas a mano en la sesión de origen.")
    p = s.get('plan_de_la_sesion')
    if p:
        b = p.get('bloque') or {}
        trozos = [f"planificador {p.get('planificador_version')}"]
        if b.get('nombre'):
            trozos.append(f"bloque {b['nombre']}")
        v = p.get('version_de_decision') or {}
        if v:
            trozos.append(f"versión {v.get('version')} de la decisión del día ({str(v.get('fingerprint') or '')[:8]})")
        o = p.get('objetivo_ejercicio') or {}
        if o:
            partes = [x for x in (o.get('repeticiones') or o.get('rango'),
                                  f"RPE {o['rpe_objetivo']}" if o.get('rpe_objetivo') else None) if x]
            if partes:
                trozos.append('objetivo ' + ' · '.join(str(x) for x in partes))
        lineas.append('Plan de la sesión: ' + ', '.join(trozos) + '.')
        if p.get('faltan'):
            lineas.append('No consta de la sesión: ' + ', '.join(p['faltan']) + '.')
    return lineas

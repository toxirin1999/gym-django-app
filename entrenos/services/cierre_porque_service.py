"""Cierre del entreno con las reglas 3 y 4 del rumbo (13-oct-2026).

Al terminar la sesión, el cierre:

- **Explica cada decisión con el dato** (regla 3). "Parámetros estables" no
  dice nada; "RPE 8 hoy: subo cuando lo hagas a RPE 7,5 o menos dos sesiones
  seguidas" sí. Las frases salen de las mismas cifras que usó la regla
  (``decision_log_service._decidir_accion``): RPE de hoy, la sesión anterior,
  el tope, el objetivo de metros.
- **Comprueba en el momento la decisión anterior** (regla 4). Si la sesión
  pasada subió la prensa a 145 kg y hoy hiciste 145 × 12 a RPE 7, lo dice ya,
  sin esperar a Memoria.
- **Dice qué viene**: la siguiente sesión de la cola y la propuesta en curso.

Si falta el dato, la frase se acorta o no se dice (nunca se inventa).
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from entrenos.services.aprendizaje_decisiones_service import _kg, _rpe, frase_decision
from entrenos.services.decision_log_service import normalizar_ejercicio

DIAS_SEMANA = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


# ─────────────────────────────────────────────────────────────
# Lo que hiciste hoy, en cifras
# ─────────────────────────────────────────────────────────────

def _series_trabajo(entreno, nombre):
    from entrenos.models import SerieRealizada

    clave = normalizar_ejercicio(nombre)
    return [
        s for s in SerieRealizada.objects.filter(
            entreno=entreno, completado=True, es_aproximacion=False,
        ).select_related('ejercicio').order_by('serie_numero', 'id')
        if normalizar_ejercicio(s.ejercicio.nombre) == clave
    ]


def texto_series(entreno, nombre, tipo_progresion='peso_reps'):
    """'60 kg × 12, 12, 10' · '36 kg × 52 m, 52 m' · '62,5 kg × 12 · 60 kg × 12'."""
    series = _series_trabajo(entreno, nombre)
    if not series:
        return None

    def unidad(s):
        if tipo_progresion == 'progresion_distancia' and s.distancia_metros is not None:
            return f'{_kg(s.distancia_metros)} m'
        if tipo_progresion == 'progresion_tiempo':
            return f'{s.repeticiones} s'
        return str(s.repeticiones)

    tramos = []  # [(peso, [unidades])], agrupando series seguidas con el mismo peso
    for s in series:
        peso = float(s.peso_kg or 0)
        if tramos and tramos[-1][0] == peso:
            tramos[-1][1].append(unidad(s))
        else:
            tramos.append((peso, [unidad(s)]))
    partes = []
    for peso, unidades in tramos:
        lista = ', '.join(unidades)
        if peso > 0:
            partes.append(f'{_kg(peso)} kg × {lista}')
        else:
            sufijo = '' if tipo_progresion in ('progresion_distancia', 'progresion_tiempo') else ' reps'
            partes.append(f'{lista}{sufijo}')
    return ' · '.join(partes)


def _sesion_anterior(cliente, entreno, nombre):
    from entrenos.models import EjercicioRealizado

    return (
        EjercicioRealizado.objects.filter(
            entreno__cliente=cliente, nombre_ejercicio__iexact=nombre,
            completado=True, entreno__fecha__lte=entreno.fecha,
        ).exclude(entreno=entreno)
        .order_by('-entreno__fecha', '-entreno_id').first()
    )


def _decimal(valor):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────
# Regla 3: por qué, con el dato
# ─────────────────────────────────────────────────────────────

def _porque_distancia(entreno, nombre, rpe_txt):
    from entrenos.services.decision_log_service import _objetivo_distancia_snapshot

    series = _series_trabajo(entreno, nombre)
    objetivo = _objetivo_distancia_snapshot(entreno, normalizar_ejercicio(nombre))
    metros = [s.distancia_metros for s in series if s.distancia_metros is not None]
    if not series or len(metros) < len(series):
        return 'Alguna serie quedó sin metros registrados: mantengo hasta tener el dato.'
    if objetivo is None:
        return 'Esta sesión no guardó objetivo de metros: mantengo y lo vuelvo a medir.'
    cortas = [m for m in metros if _decimal(m) < objetivo]
    if cortas:
        return (
            f'El objetivo era {_kg(objetivo)} m por serie y hoy hiciste '
            f'{", ".join(_kg(m) for m in metros)} m: subo cuando lo completes en todas.'
        )
    duras = [s for s in series if s.rpe_real is not None and float(s.rpe_real) >= 9]
    if duras:
        return (
            f'Completaste los {_kg(objetivo)} m, pero con RPE {_rpe(duras[0].rpe_real)} '
            'en alguna serie: subo cuando salgan con margen.'
        )
    return None


def porque_decision(log, ejercicio_hoy, anterior, tipo_progresion):
    """Una frase con el dato que sostiene la decisión, o None si no lo hay."""
    motivo = log.motivo or ''
    rpe = float(ejercicio_hoy.rpe) if ejercicio_hoy and ejercicio_hoy.rpe is not None else None
    rpe_txt = _rpe(rpe) if rpe is not None else None
    peso_hoy = log.peso_anterior if log.peso_anterior else getattr(ejercicio_hoy, 'peso_kg', None)

    if log.motivo_codigo == 'distancia_sin_margen' or motivo.startswith('Distancia o margen insuficiente'):
        return _porque_distancia(log.entreno_origen, log.ejercicio, rpe_txt)

    if motivo.startswith('Tope de peso alcanzado'):
        return f'Peso fijo de {_kg(peso_hoy)} kg: progreso por metros (+5 m).' if peso_hoy else None

    if motivo.startswith('Tope de máquina alcanzado'):
        if peso_hoy:
            return f'{_kg(peso_hoy)} kg es el máximo de la máquina: progreso por repeticiones.'
        return None

    if motivo.startswith('Sesión intensa'):
        if rpe_txt is None:
            return None
        return (
            f'RPE {rpe_txt} hoy: mantengo el peso. Si sigue en 9 o más tres sesiones '
            'seguidas, lo bajo.'
        )

    if motivo.startswith('Completado con éxito en 2 sesiones'):
        if rpe_txt is None:
            return None
        if anterior is not None and anterior.rpe is not None:
            antes = f'RPE {rpe_txt} hoy y {_rpe(anterior.rpe)} la vez anterior, sin fallo'
        else:
            antes = f'RPE {rpe_txt} hoy y la vez anterior sin fallo'
        if log.accion == 'subir_peso':
            # Sin kg: el peso exacto lo fija la sesión (fase, incremento de la
            # máquina) y no siempre coincide con el % bruto del log.
            destino = 'subo el peso'
        elif tipo_progresion == 'progresion_tiempo':
            destino = 'añado tiempo'
        else:
            destino = 'una repetición más'
        return f'{antes}: {destino}.'

    if motivo.startswith('Parámetros estables'):
        if rpe is None:
            return 'No registraste RPE: mantengo hasta tener el dato.'
        if rpe > 7.5:
            return f'RPE {rpe_txt} hoy: subo cuando lo hagas a RPE 7,5 o menos dos sesiones seguidas.'
        if anterior is None:
            return 'Primera sesión registrada de este ejercicio: mantengo para tener referencia.'
        if anterior.fallo_muscular:
            return f'Hoy RPE {rpe_txt}, pero la vez anterior llegaste al fallo: si se repite lo de hoy, subo.'
        rpe_prev = anterior.rpe if anterior.rpe is not None else 8
        if rpe_prev > 8:
            return (
                f'Hoy RPE {rpe_txt}, pero la vez anterior fue RPE {_rpe(rpe_prev)}: '
                'si se repite lo de hoy, subo.'
            )
    return None


# ─────────────────────────────────────────────────────────────
# Regla 4: lo que comprobé hoy
# ─────────────────────────────────────────────────────────────

def comprobaciones_de_hoy(cliente, entreno):
    """Decisiones anteriores que esta sesión ha evaluado, con su veredicto.

    Mismo criterio que Memoria: solo las que cambiaron algo (no "mantuve") y
    con conclusión (funcionó / no funcionó).
    """
    from entrenos.models import GymDecisionLog
    from entrenos.services.aprendizaje_decisiones_service import _sesion_evaluadora

    items = []
    vistos = set()
    for ej in entreno.ejercicios_realizados.filter(completado=True).order_by('orden', 'id'):
        nombre = normalizar_ejercicio(ej.nombre_ejercicio)
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        log = (
            GymDecisionLog.objects.filter(
                cliente=cliente, ejercicio_normalizado=nombre,
                resultado__in=('validada', 'fallida'),
                entreno_origen__isnull=False,
                entreno_origen__fecha__lte=entreno.fecha,
            ).exclude(accion='mantener').exclude(entreno_origen=entreno)
            .order_by('-fecha_creacion').first()
        )
        if log is None:
            continue
        evaluadora = _sesion_evaluadora(log)
        if not evaluadora or evaluadora.get('entreno_id') != entreno.id:
            continue
        items.append({
            'resultado': log.resultado,
            'texto': frase_decision(log, etiqueta='Hoy'),
        })
    return items


# ─────────────────────────────────────────────────────────────
# Lo que viene
# ─────────────────────────────────────────────────────────────

def _grupos_texto(entrenamiento):
    from entrenos.services.evolucion_muscular_service import NOMBRES_ZONA

    grupos = []
    for ej in (entrenamiento or {}).get('ejercicios') or []:
        g = ej.get('grupo_muscular')
        if g and g not in grupos:
            grupos.append(g)
    return ', '.join(NOMBRES_ZONA.get(g, g.replace('_', ' ')).lower() for g in grupos[:4])


def lo_que_viene(cliente, entreno):
    """Siguiente sesión de la cola y propuesta en curso. Solo en el último entreno."""
    from entrenos.models import EntrenoRealizado, PropuestaZonaGym
    from entrenos.services.volumen_grupo_service import SERIES_POR_AJUSTE
    from entrenos.services.sesion_recomendada import (
        _build_planificador, _es_descanso, _etiqueta_dia, _normalizar_entrenamiento,
        _siguiente_de_cola,
    )

    fecha = entreno.fecha_ejecucion or entreno.fecha
    posteriores = EntrenoRealizado.objects.filter(cliente=cliente).exclude(pk=entreno.pk).filter(
        fecha__gte=fecha,
    ).filter(id__gt=entreno.id)
    if posteriores.exists():
        return []  # cierre antiguo: lo que venía ya pasó

    lineas = []
    manana = fecha + timedelta(days=1)
    try:
        siguiente = _siguiente_de_cola(cliente, manana)
        if siguiente:
            etiqueta = _etiqueta_dia(siguiente['nombre']) or siguiente['nombre']
            grupos = _grupos_texto(siguiente.get('entrenamiento'))
            frase = f'Lo siguiente es el {etiqueta}' if etiqueta.startswith('Día') else f'Lo siguiente: {etiqueta}'
            if grupos:
                frase += f' ({grupos})'
            if siguiente['fecha'] < manana:
                frase += f', que era del {DIAS_SEMANA[siguiente["fecha"].weekday()]}'
            lineas.append(frase + '.')
        else:
            sesion = _normalizar_entrenamiento(
                _build_planificador(cliente).generar_entrenamiento_para_fecha(manana)
            )
            if _es_descanso(sesion):
                lineas.append('Mañana toca descanso.')
            else:
                nombre = (sesion.get('rutina_nombre') or '').strip()
                etiqueta = _etiqueta_dia(nombre) or nombre
                grupos = _grupos_texto(sesion)
                lineas.append(f'Mañana: {etiqueta}' + (f' ({grupos})' if grupos else '') + '.')
    except Exception:
        pass

    for p in PropuestaZonaGym.objects.filter(
        cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA, fin__gte=manana,
    ).order_by('inicio'):
        signo = '−' if getattr(p, 'direccion', 'subir') == 'bajar' else '+'
        # Mismo número que aplica el planificador (volumen_grupo_service).
        cambio = f'{signo}{SERIES_POR_AJUSTE} series semanales de {p.nombre_zona}'
        if p.inicio and p.inicio >= manana:
            lineas.append(f'Desde el {p.inicio:%d/%m}, {cambio} por la propuesta que aceptaste (hasta el {p.fin:%d/%m}).')
        else:
            lineas.append(f'Sigue la propuesta: {cambio} hasta el {p.fin:%d/%m}.')
    return lineas

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
            texto = f'{_kg(s.distancia_metros)} m'
        elif tipo_progresion == 'progresion_tiempo':
            texto = f'{s.repeticiones} s'
        else:
            texto = str(s.repeticiones)
        # El RPE de cada serie: la media escondía una serie a RPE 10.
        if s.rpe_real is not None:
            texto += f' @{_rpe(s.rpe_real)}'
        return texto

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


def subida_por_encima(log):
    """19-oct-2026: (peso, reps, rango, siguiente_kg) si se subió por pasarse del rango.

    Extensiones: 20 × 16 y 25 × 25 en 15-20 → (25, 25, (15, 20), 30). None si no aplica.
    """
    if log.accion != 'subir_peso' or not log.entreno_origen_id:
        return None
    from entrenos.services.maquina_service import a_escala, salto_carga
    from entrenos.services.ultima_sesion_service import rango_de_sesion, series_de_trabajo

    rango = rango_de_sesion(log.entreno_origen, log.ejercicio)
    series = [s for s in series_de_trabajo(log.entreno_origen, log.ejercicio) if s['peso'] > 0]
    if not rango or not series:
        return None
    pesada = max(series, key=lambda s: (s['peso'], s['reps']))
    if pesada['reps'] < rango[1]:
        return None
    salto = salto_carga(log.cliente, log.ejercicio)
    siguiente = a_escala(pesada['peso'] + salto, salto, 'cerca')
    if siguiente <= pesada['peso']:
        siguiente = pesada['peso'] + salto
    return pesada['peso'], pesada['reps'], rango, siguiente


def porque_decision(log, ejercicio_hoy, anterior, tipo_progresion):
    """Una frase con el dato que sostiene la decisión, o None si no lo hay."""
    motivo = log.motivo or ''
    # El RPE con el que se decidió (el de la serie de referencia), no la media.
    if log.rpe_anterior is not None:
        rpe = float(log.rpe_anterior)
    else:
        rpe = float(ejercicio_hoy.rpe) if ejercicio_hoy and ejercicio_hoy.rpe is not None else None
    rpe_txt = _rpe(rpe) if rpe is not None else None
    peso_hoy = log.peso_anterior if log.peso_anterior else getattr(ejercicio_hoy, 'peso_kg', None)

    if log.motivo_codigo == 'distancia_sin_margen' or motivo.startswith('Distancia o margen insuficiente'):
        return _porque_distancia(log.entreno_origen, log.ejercicio, rpe_txt)

    if motivo.startswith('Tope de peso alcanzado'):
        return f'Peso fijo de {_kg(peso_hoy)} kg: progreso por metros (+1 m).' if peso_hoy else None

    if motivo.startswith('Tope de máquina alcanzado'):
        if peso_hoy:
            return f'{_kg(peso_hoy)} kg es el máximo de la máquina: progreso por repeticiones.'
        return None

    # 17-oct-2026 (regla C): el peso concreto y las reps de la próxima vez.
    doble = _doble_progresion(log, tipo_progresion)

    if motivo.startswith('Sesión intensa'):
        if rpe_txt is None:
            return None
        peso_txt = f'{_kg(peso_hoy)} kg' if peso_hoy else 'el peso'
        return (
            f'RPE {rpe_txt} hoy, por encima del objetivo: mantengo {peso_txt} y las mismas reps. '
            'Si sigue en 9 o más tres sesiones seguidas, lo bajo.'
        )

    if 'objetivo superado' in motivo and log.accion == 'subir_peso':
        dato = subida_por_encima(log)
        if dato:
            peso, reps, rango, siguiente = dato
            return (
                f'{reps} reps con {_kg(peso)} kg, por encima de {rango[1]}: '
                f'subo a {_kg(siguiente)} kg y vuelvo a {rango[0]} reps.'
            )

    if motivo.startswith('Completado con éxito en 2 sesiones'):
        if rpe_txt is None:
            return None
        if anterior is not None and anterior.rpe is not None:
            antes = f'RPE {rpe_txt} hoy y {_rpe(anterior.rpe)} la vez anterior, sin fallo'
        else:
            antes = f'RPE {rpe_txt} hoy y la vez anterior sin fallo'
        if log.accion == 'subir_peso':
            sugerido = getattr(log, 'peso_sugerido', None)
            destino = f'subo a {_kg(sugerido)} kg' if sugerido else 'subo el peso'
        elif tipo_progresion == 'progresion_tiempo':
            destino = 'añado tiempo'
        else:
            destino = 'una repetición más'
        return f'{antes}: {destino}.'

    if doble and (motivo.startswith('Parámetros estables') or 'completar el objetivo' in motivo):
        return doble

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


def _hundimiento(log, rango):
    """Texto de la próxima vez cuando la serie de referencia no se sostuvo, o None."""
    from entrenos.services.maquina_service import salto_carga
    from entrenos.services.ultima_sesion_service import serie_referencia, series_de_trabajo, techo_peso

    series = series_de_trabajo(log.entreno_origen, log.ejercicio)
    ref = serie_referencia(series, rango[0])
    if not ref or not ref.get('caida'):
        return None
    resultado = techo_peso(
        {'referencia': ref, 'fecha': log.entreno_origen.fecha}, rango, 8, salto_carga(log.cliente, log.ejercicio),
    )
    if not resultado or resultado[2] != 'bajar':
        return None
    cortas = [s for s in series if 0 < s['reps'] < rango[0]]
    detalle = ', '.join(f"{_kg(s['peso'])} × {s['reps']}" for s in cortas)
    n = len(cortas)
    sujeto = 'una serie se quedó' if n == 1 else f'{n} series se quedaron'
    return (
        f'{_kg(ref["peso"])} kg entró, pero después {sujeto} por debajo de {rango[0]} ({detalle}): '
        f'la próxima vez {_kg(resultado[0])} kg{SUFIJO_HUNDIMIENTO}'
    )


# 21-oct-2026: el cierre decía "Mantener" encima de "la próxima vez 70 kg".
SUFIJO_HUNDIMIENTO = ' para que entren todas.'


def es_bajada_por_hundimiento(porque):
    return bool(porque) and porque.endswith(SUFIJO_HUNDIMIENTO) and ' entró, pero después ' in porque


def _doble_progresion(log, tipo_progresion):
    """'Mantengo 60 kg: la próxima vez a por 13 reps. Con 15 en todas, subo.' o None."""
    if tipo_progresion not in ('peso_reps', 'peso_corporal_lastre') or log.accion != 'mantener':
        return None
    if not log.peso_anterior or log.reps_anteriores is None or not log.entreno_origen_id:
        return None
    from entrenos.services.ultima_sesion_service import objetivo_reps_hoy, rango_de_sesion
    rango = rango_de_sesion(log.entreno_origen, log.ejercicio)
    if not rango or log.reps_anteriores < rango[0] or log.reps_anteriores >= rango[1]:
        return None
    # 20-oct-2026: si después se hundieron series (crunch 75 × 16, 16, 11 y
    # 70 × 11), el cierre dice lo mismo que dirá el próximo briefing.
    hundida = _hundimiento(log, rango)
    if hundida:
        return hundida
    siguiente = objetivo_reps_hoy(log.reps_anteriores, rango)
    return (
        f'Mantengo {_kg(log.peso_anterior)} kg: la próxima vez a por {siguiente} reps. '
        f'Con {rango[1]} en todas las series, subo el peso.'
    )


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
        _marcar_completadas, _siguiente_de_cola,
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
        # 18-oct-2026: recién guardado, la SesionProgramada del entreno de hoy
        # seguía pendiente y "Lo que viene" volvía a proponer el mismo Día 3.
        _marcar_completadas(cliente, fecha)
    except Exception:
        pass
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

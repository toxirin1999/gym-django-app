"""Serie testigo (8-nov-2026, decisión de David).

Una serie fija a la semana para tener un dato objetivo de cómo está y para
calibrar su RPE, porque su sensación de esfuerzo no siempre acierta:

- Jalón al pecho, los lunes, justo después de calentar (no hay espalda el
  lunes y no carga las piernas antes del fútbol del miércoles).
- Peso fijo, el de unas 12-15 repeticiones, que no cambia aunque mejore.
- Al llegar a la repetición 8 dice cuántas cree que le quedan y sigue hasta
  la primera que no sale limpia.

Con eso:
1. Calibración del RPE: lo que dijo que le quedaba frente a lo que de verdad
   le quedaba.
2. Termómetro de forma: repeticiones frente a su referencia (mediana de las
   3 primeras semanas sin descarga). Una repetición de diferencia es ruido;
   cuenta a partir de 2.

Se guarda aparte (``SerieTestigo``): no es una serie de trabajo ni entra en
las decisiones de carga.
"""

from datetime import date, timedelta
from statistics import mean, median

EJERCICIO = 'Jalón al Pecho'
INICIO = date(2026, 11, 16)
REPS_OBJETIVO = 13            # el peso fijo se elige para unas 12-15 repeticiones
SEMANAS_REFERENCIA = 3
DIFERENCIA_QUE_CUENTA = 2
SALTO_KG = 2.5


def _redondear_abajo(kg, salto=SALTO_KG):
    return round((int(kg / salto)) * salto, 2)


def peso_fijo_desde_historial(cliente, hoy, dias=90):
    """Peso para unas 13 repeticiones a partir del mejor 1RM estimado reciente del jalón, o None.

    Sin las semanas de descarga (el peso está rebajado a propósito).
    """
    from entrenos.models import EjercicioRealizado, SemanaPlanGym
    from entrenos.services.decision_log_service import normalizar_ejercicio

    clave = normalizar_ejercicio(EJERCICIO)
    descargas = set(SemanaPlanGym.objects.filter(cliente=cliente, descarga=True).values_list('lunes', flat=True))
    mejor = None
    filas = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente, entreno__fecha__gte=hoy - timedelta(days=dias), entreno__fecha__lt=hoy,
    ).values_list('nombre_ejercicio', 'peso_kg', 'repeticiones', 'entreno__fecha')
    for nombre, peso, reps, fecha in filas:
        if normalizar_ejercicio(nombre) != clave or not peso or not reps:
            continue
        if fecha - timedelta(days=fecha.weekday()) in descargas:
            continue
        try:
            e1rm = float(peso) * (1 + float(reps) / 30)
        except (TypeError, ValueError):
            continue
        mejor = e1rm if mejor is None else max(mejor, e1rm)
    if mejor is None:
        return None
    return _redondear_abajo(mejor / (1 + REPS_OBJETIVO / 30))


def protocolo_vigente(cliente, fecha, crear=True):
    """El protocolo en vigor ese día; lo crea la primera vez desde ``INICIO`` si hay historial."""
    from django.db.models import Q

    from entrenos.models import ProtocoloTestigo

    p = ProtocoloTestigo.objects.filter(cliente=cliente, desde__lte=fecha).filter(
        Q(hasta__isnull=True) | Q(hasta__gte=fecha),
    ).first()
    if p or not crear or fecha < INICIO:
        return p
    peso = peso_fijo_desde_historial(cliente, fecha)
    if not peso:
        return None
    return ProtocoloTestigo.objects.create(
        cliente=cliente, ejercicio=EJERCICIO, peso_kg=peso, dia_semana=0, rep_pregunta=8,
        desde=fecha - timedelta(days=fecha.weekday()),
        motivo='Acordado el 8-nov-2026: dato objetivo de forma y calibración del RPE.',
    )


def toca_hoy(cliente, fecha):
    """El protocolo si hoy toca la serie testigo y aún no está registrada, o None."""
    from entrenos.models import SerieTestigo

    p = protocolo_vigente(cliente, fecha)
    if p is None or fecha.weekday() != p.dia_semana:
        return None
    if SerieTestigo.objects.filter(cliente=cliente, fecha=fecha).exists():
        return None
    return p


def _es_descarga(cliente, fecha):
    from entrenos.models import SemanaPlanGym
    return SemanaPlanGym.objects.filter(
        cliente=cliente, lunes=fecha - timedelta(days=fecha.weekday()), descarga=True,
    ).exists()


def registrar(cliente, fecha, reps, quedaban_estimadas=None):
    """Guarda (o corrige) la serie testigo del día. Devuelve la ``SerieTestigo``."""
    from entrenos.models import SerieTestigo

    p = protocolo_vigente(cliente, fecha)
    if p is None:
        raise ValueError('No hay serie testigo acordada para esta fecha.')
    reps = int(reps)
    if reps < 1 or reps > 60:
        raise ValueError('Repeticiones fuera de rango.')
    if quedaban_estimadas in ('', None) or reps < p.rep_pregunta:
        quedaban_estimadas = None  # no llegó a la repetición de la pregunta
    else:
        quedaban_estimadas = int(quedaban_estimadas)
        if quedaban_estimadas < 0 or quedaban_estimadas > 40:
            raise ValueError('Estimación fuera de rango.')
    serie, _ = SerieTestigo.objects.update_or_create(
        cliente=cliente, fecha=fecha,
        defaults={'protocolo': p, 'reps': reps, 'quedaban_estimadas': quedaban_estimadas,
                  'descarga': _es_descarga(cliente, fecha)},
    )
    return serie


def _quedaban_de_verdad(serie):
    return serie.reps - serie.protocolo.rep_pregunta


def resumen(cliente, hasta=None):
    """Referencia, calibración y última serie, con lo que haya (nunca inventa)."""
    from entrenos.models import SerieTestigo

    qs = SerieTestigo.objects.filter(cliente=cliente).select_related('protocolo')
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    series = list(qs.order_by('fecha'))
    if not series:
        return None
    protocolo = series[-1].protocolo
    del_protocolo = [s for s in series if s.protocolo_id == protocolo.id]
    validas = [s for s in del_protocolo if not s.descarga]
    base = validas[:SEMANAS_REFERENCIA]
    referencia = median(s.reps for s in base) if len(base) == SEMANAS_REFERENCIA else None
    con_estimacion = [s for s in del_protocolo if s.quedaban_estimadas is not None]
    error_medio = (mean(_quedaban_de_verdad(s) - s.quedaban_estimadas for s in con_estimacion)
                   if len(con_estimacion) >= SEMANAS_REFERENCIA else None)
    ultima = series[-1]
    return {
        'protocolo': protocolo,
        'series': del_protocolo,
        'ultima': ultima,
        'referencia': referencia,
        'faltan_para_referencia': max(0, SEMANAS_REFERENCIA - len(base)),
        'diferencia': (ultima.reps - referencia) if referencia is not None and not ultima.descarga else None,
        'error_medio_rpe': error_medio,
        'n_estimaciones': len(con_estimacion),
    }


def _num(x):
    texto = f'{x:.1f}'.rstrip('0').rstrip('.')
    return texto.replace('.', ',')


def frase_serie(serie, res=None):
    """'14 repeticiones con 55 kg. En la 8 dijiste que te quedaban 4; te quedaban 6.' + referencia."""
    p = serie.protocolo
    partes = [f'{serie.reps} repeticiones con {_num(p.peso_kg)} kg.']
    if serie.quedaban_estimadas is not None:
        real = _quedaban_de_verdad(serie)
        if real == serie.quedaban_estimadas:
            partes.append(f'En la {p.rep_pregunta} dijiste que te quedaban {serie.quedaban_estimadas}: acertaste.')
        else:
            partes.append(f'En la {p.rep_pregunta} dijiste que te quedaban {serie.quedaban_estimadas}; '
                          f'te quedaban {real}.')
    if serie.descarga:
        partes.append('Semana de descarga: no cuenta para la referencia.')
    elif res and res.get('referencia') is not None and res['ultima'].id == serie.id:
        dif = res['diferencia']
        ref = _num(res['referencia'])
        if abs(dif) < DIFERENCIA_QUE_CUENTA:
            partes.append(f'Como tu referencia ({ref}): una repetición arriba o abajo es ruido.')
        else:
            sentido = 'por encima' if dif > 0 else 'por debajo'
            partes.append(f'{_num(abs(dif))} repeticiones {sentido} de tu referencia ({ref}).')
    elif res and res.get('faltan_para_referencia'):
        n = res['faltan_para_referencia']
        partes.append(f"Falta{'n' if n != 1 else ''} {n} semana{'s' if n != 1 else ''} para tener tu referencia.")
    return ' '.join(partes)


def frase_calibracion(res):
    """Cómo acierta su sensación de esfuerzo, con 3 o más estimaciones; si no, None."""
    if not res or res.get('error_medio_rpe') is None:
        return None
    err = res['error_medio_rpe']
    n = res['n_estimaciones']
    if abs(err) < 1:
        return (f'Tu sensación de esfuerzo acierta: de media te equivocas en menos de una repetición '
                f'({n} series testigo).')
    if err > 0:
        return (f'Sueles quedarte corto: de media te quedaban {_num(err)} repeticiones más de las que '
                f'dijiste ({n} series testigo). Tu RPE marcado suele estar por encima del real.')
    return (f'Sueles pasarte: de media te quedaban {_num(-err)} repeticiones menos de las que dijiste '
            f'({n} series testigo). Tu RPE marcado suele estar por debajo del real.')

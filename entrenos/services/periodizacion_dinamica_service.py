"""Periodización dinámica (paso 4, 13-oct-2026).

Antes: 52 semanas fijas ancladas al primer lunes de enero, iguales para todos.
Una semana perdida no detenía el plan y las descargas caían en fecha fija.

Ahora, cada semana real se resuelve una vez (al empezar) y se guarda en
``SemanaPlanGym``:

- **Arranque sin saltos.** La primera vez se toma la semana que marcaba el
  calendario: el día del despliegue nadie cambia de fase de golpe.
- **Avanza solo con semanas entrenadas.** Si la semana anterior hiciste al
  menos la mitad de las sesiones, el plan avanza; si no, repite la semana.
- **La descarga llega cuando hace falta.** La descarga programada del bloque
  se hace si hay alguna señal de fatiga o si ya van 5 semanas sin descargar; si
  no, se salta. Fuera de esas semanas se mete una descarga si hay 2 señales a
  la vez (y al menos 3 semanas desde la última). Como tarde, a las 8 semanas.

Señales (todas con dato, para poder decir por qué):
- fatiga en ejercicios: decisiones del plan por RPE alto o fallo no previsto
  en 3 o más ejercicios distintos en 14 días;
- energía baja: media del check-in ≤ 4/10 en 7 días (con 3 registros o más);
- readiness baja: media < 50 en 7 días (con 3 registros o más, si hay Hyrox);
- carga aguda alta: ACWR ≥ 1,5 (salvo que el pico sea un dato dudoso).

Las semanas futuras no se guardan: se proyectan a partir de la actual.
"""

import math
from datetime import date, timedelta

SEMANAS_PLAN = 52
UMBRAL_SEMANA_ENTRENADA = 0.5      # fracción de sesiones previstas
SEMANAS_MIN_DESCARGA_PROGRAMADA = 5
SEMANAS_MIN_DESCARGA_SENAL = 3
SEMANAS_MAX_SIN_DESCARGA = 8
SENALES_PARA_DESCARGA = 2

_MOTIVOS_FATIGA = (
    'rpe_alto_sostenido', 'rpe_extremo', 'fallo_no_controlado', 'fallo_repetido_no_controlado',
)


def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


def semana_calendario(fecha, anio=None):
    """La semana del plan que marcaba el calendario antiguo (1..52)."""
    anio = anio or fecha.year
    primer = date(anio, 1, 1)
    inicio = primer + timedelta(days=(0 - primer.weekday() + 7) % 7)
    return (fecha - inicio).days // 7 + 1


def _ciclar(semana):
    return ((semana - 1) % SEMANAS_PLAN) + 1


def _periodizacion():
    from analytics.planificador_helms.periodizacion.generador import GeneradorPeriodizacion
    return GeneradorPeriodizacion.generar_periodizacion_anual()


def es_semana_descarga(semana_plan, periodizacion=None):
    periodizacion = periodizacion or _periodizacion()
    for bloque in periodizacion:
        if semana_plan in bloque.get('semanas', []):
            return bloque.get('fase') == 'descarga'
    return False


# ── Señales ──────────────────────────────────────────────────────────────────

def senales_fatiga(cliente, fecha):
    """Lista de señales activas: [{'codigo', 'texto'}], cada una con su dato."""
    senales = []
    try:
        from entrenos.models import GymDecisionLog
        desde = fecha - timedelta(days=14)
        ejercicios = set(
            GymDecisionLog.objects.filter(
                cliente=cliente, motivo_codigo__in=_MOTIVOS_FATIGA,
                fecha_creacion__date__gte=desde, fecha_creacion__date__lte=fecha,
            ).values_list('ejercicio', flat=True)
        )
        ejercicios = {(e or '').strip().casefold() for e in ejercicios if e}
        if len(ejercicios) >= 3:
            senales.append({
                'codigo': 'fatiga_ejercicios',
                'texto': f'RPE alto o fallos no previstos en {len(ejercicios)} ejercicios en 14 días',
            })
    except Exception:
        pass

    try:
        from clientes.models import BitacoraDiaria
        valores = [
            v for v in BitacoraDiaria.objects.filter(
                cliente=cliente, fecha__gt=fecha - timedelta(days=7), fecha__lte=fecha,
            ).values_list('energia_subjetiva', flat=True) if v is not None
        ]
        if len(valores) >= 3:
            media = sum(valores) / len(valores)
            if media <= 4:
                senales.append({
                    'codigo': 'energia_baja',
                    'texto': f'energía media {media:.1f}/10 en 7 días'.replace('.', ','),
                })
    except Exception:
        pass

    try:
        from hyrox.models import HyroxReadinessLog
        scores = list(
            HyroxReadinessLog.objects.filter(
                objective__cliente=cliente,
                fecha__gt=fecha - timedelta(days=7), fecha__lte=fecha,
            ).values_list('score', flat=True)
        )
        if len(scores) >= 3:
            media = sum(scores) / len(scores)
            if media < 50:
                senales.append({
                    'codigo': 'readiness_baja',
                    'texto': f'readiness media {round(media)}/100 en 7 días',
                })
    except Exception:
        pass

    try:
        from entrenos.services.acwr_decision_service import contexto_acwr
        ctx = contexto_acwr(cliente, fecha)
        if ctx.get('acwr_alto') and not ctx.get('acwr_dudoso') and ctx.get('acwr_valor'):
            senales.append({
                'codigo': 'acwr_alto',
                'texto': f"ACWR {float(ctx['acwr_valor']):.2f}".replace('.', ','),
            })
    except Exception:
        pass
    return senales


def _sesiones_semana(cliente, lunes):
    """Entrenos de gym hechos esa semana (uno por día como mucho)."""
    from django.db.models import Q
    from entrenos.models import EntrenoRealizado
    domingo = lunes + timedelta(days=6)
    fechas = set()
    for fe, f in EntrenoRealizado.objects.filter(cliente=cliente).filter(
        Q(fecha_ejecucion__gte=lunes, fecha_ejecucion__lte=domingo)
        | Q(fecha_ejecucion__isnull=True, fecha__gte=lunes, fecha__lte=domingo)
    ).values_list('fecha_ejecucion', 'fecha'):
        fechas.add(fe or f)
    return len(fechas)


def _dias_previstos(cliente):
    dias = getattr(cliente, 'dias_disponibles', None) or 4
    return dias if dias in (3, 4, 5, 6) else 4


def _semanas_desde_descarga(registros):
    """Semanas entrenadas seguidas desde la última descarga (registros ordenados)."""
    n = 0
    for r in reversed(registros):
        if r.descarga:
            break
        if r.origen != r.ORIGEN_REPETICION:
            n += 1
    return n


def _lista(textos):
    if len(textos) == 1:
        return textos[0]
    return ', '.join(textos[:-1]) + ' y ' + textos[-1]


# ── Resolución ───────────────────────────────────────────────────────────────

def _decidir_semana(cliente, lunes, previo, registros, periodizacion):
    """Datos del registro para la semana ``lunes`` a partir de la anterior."""
    from entrenos.models import SemanaPlanGym as S

    hechas = _sesiones_semana(cliente, previo.lunes)
    previstas = _dias_previstos(cliente)
    entrenada = hechas >= math.ceil(previstas * UMBRAL_SEMANA_ENTRENADA)
    base = {'sesiones_previas': hechas, 'sesiones_previstas_previas': previstas}

    if previo.origen in (S.ORIGEN_DESCARGA_SENAL, S.ORIGEN_DESCARGA_OBLIGATORIA):
        # La descarga intercalada no consumió semana del plan: se retoma ahí.
        candidata = previo.semana_plan
        origen = S.ORIGEN_AVANCE
        motivo = 'Tras la descarga se retoma el plan donde se dejó.'
    elif previo.descarga or entrenada:
        candidata = _ciclar(previo.semana_plan + 1)
        origen = S.ORIGEN_AVANCE
        motivo = f'La semana pasada hiciste {hechas} de {previstas} sesiones: el plan avanza.'
    else:
        candidata = previo.semana_plan
        origen = S.ORIGEN_REPETICION
        motivo = (
            f'La semana pasada hiciste {hechas} de {previstas} sesiones: '
            'repito la semana en vez de avanzar.'
        )

    semanas_sin = _semanas_desde_descarga(registros)
    senales = senales_fatiga(cliente, lunes)
    textos = [s['texto'] for s in senales]

    if es_semana_descarga(candidata, periodizacion):
        if senales or semanas_sin >= SEMANAS_MIN_DESCARGA_PROGRAMADA:
            razon = _lista(textos) if senales else f'{semanas_sin} semanas entrenando sin descargar'
            return {**base, 'semana_plan': candidata, 'descarga': True,
                    'origen': S.ORIGEN_DESCARGA_PROGRAMADA,
                    'motivo': f'Semana de descarga del bloque: {razon}.'}
        return {**base, 'semana_plan': _ciclar(candidata + 1), 'descarga': False,
                'origen': S.ORIGEN_DESCARGA_SALTADA,
                'motivo': (f'Me salto la descarga del bloque: sin señales de fatiga y solo '
                           f'{semanas_sin} semanas desde la última.')}

    if origen == S.ORIGEN_REPETICION:
        return {**base, 'semana_plan': candidata, 'descarga': False, 'origen': origen, 'motivo': motivo}

    if semanas_sin >= SEMANAS_MAX_SIN_DESCARGA:
        return {**base, 'semana_plan': candidata, 'descarga': True,
                'origen': S.ORIGEN_DESCARGA_OBLIGATORIA,
                'motivo': f'Semana de descarga: llevas {semanas_sin} semanas entrenando sin descargar.'}
    if len(senales) >= SENALES_PARA_DESCARGA and semanas_sin >= SEMANAS_MIN_DESCARGA_SENAL:
        return {**base, 'semana_plan': candidata, 'descarga': True,
                'origen': S.ORIGEN_DESCARGA_SENAL,
                'motivo': f'Semana de descarga: {_lista(textos)}.'}
    return {**base, 'semana_plan': candidata, 'descarga': False, 'origen': origen, 'motivo': motivo}


def resolver_semana(cliente, fecha, hoy=None):
    """{'semana_plan', 'descarga', 'origen', 'motivo', 'proyectada'} para ``fecha``."""
    from django.db import IntegrityError, transaction
    from django.utils import timezone
    from entrenos.models import SemanaPlanGym as S

    hoy = hoy or timezone.localdate()
    lunes = lunes_de(fecha)
    lunes_hoy = lunes_de(hoy)
    periodizacion = _periodizacion()

    if lunes > lunes_hoy:
        actual = resolver_semana(cliente, lunes_hoy, hoy=hoy)
        semanas = (lunes - lunes_hoy).days // 7
        if actual['descarga'] and actual['origen'] in (
            S.ORIGEN_DESCARGA_SENAL, S.ORIGEN_DESCARGA_OBLIGATORIA,
        ):
            semanas -= 1  # la descarga intercalada no consume semana del plan
        semana = _ciclar(actual['semana_plan'] + max(0, semanas))
        return {'semana_plan': semana, 'descarga': es_semana_descarga(semana, periodizacion),
                'origen': 'proyeccion', 'motivo': '', 'proyectada': True}

    registros = list(S.objects.filter(cliente=cliente, lunes__lte=lunes_hoy).order_by('lunes'))
    if not registros:
        try:
            with transaction.atomic():
                inicial = S.objects.create(
                    cliente=cliente, lunes=lunes_hoy,
                    semana_plan=_ciclar(semana_calendario(lunes_hoy)),
                    descarga=es_semana_descarga(_ciclar(semana_calendario(lunes_hoy)), periodizacion),
                    origen=S.ORIGEN_CALENDARIO,
                    motivo='Arranque de la periodización dinámica desde la semana del calendario.',
                )
        except IntegrityError:
            inicial = S.objects.get(cliente=cliente, lunes=lunes_hoy)
        registros = [inicial]

    primero = registros[0]
    if lunes < primero.lunes:
        semana = _ciclar(semana_calendario(lunes))
        return {'semana_plan': semana, 'descarga': es_semana_descarga(semana, periodizacion),
                'origen': S.ORIGEN_CALENDARIO, 'motivo': '', 'proyectada': False,
                'legacy': True}

    while registros[-1].lunes < lunes:
        previo = registros[-1]
        siguiente_lunes = previo.lunes + timedelta(days=7)
        datos = _decidir_semana(cliente, siguiente_lunes, previo, registros, periodizacion)
        try:
            with transaction.atomic():
                nuevo = S.objects.create(cliente=cliente, lunes=siguiente_lunes, **datos)
        except IntegrityError:
            nuevo = S.objects.get(cliente=cliente, lunes=siguiente_lunes)
        registros.append(nuevo)

    registro = next(r for r in registros if r.lunes == lunes)
    return {'semana_plan': registro.semana_plan, 'descarga': registro.descarga,
            'origen': registro.origen, 'motivo': registro.motivo, 'proyectada': False}


def bloque_para_semana(info, periodizacion=None):
    """(bloque, numero_bloque) a usar para una semana resuelta.

    Si la descarga es intercalada (la semana del plan es de contenido), se usa
    el bloque de descarga que sigue al bloque actual, con su volumen y RPE.
    """
    periodizacion = periodizacion or _periodizacion()
    semana = info['semana_plan']
    idx = next((i for i, b in enumerate(periodizacion) if semana in b.get('semanas', [])), None)
    if idx is None:
        return None, None
    bloque = periodizacion[idx]
    if info.get('descarga') and bloque.get('fase') != 'descarga':
        for j in range(idx + 1, len(periodizacion)):
            if periodizacion[j].get('fase') == 'descarga':
                return periodizacion[j], j + 1
        for j in range(0, idx):
            if periodizacion[j].get('fase') == 'descarga':
                return periodizacion[j], j + 1
    return bloque, idx + 1

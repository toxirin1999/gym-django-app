"""Volumen por músculo ajustado por el entrenador (paso 5, 13-oct-2026).

El planificador calcula el volumen semanal de cada grupo con la tabla base y
el bloque. Encima, el entrenador puede subirlo o bajarlo por grupo, siempre
con un motivo que se puede citar:

1. **Propuesta aceptada en curso** (PropuestaZonaGym): +2 series semanales
   en una zona que retrocede, o −2 en una que acumula fatiga, durante 4
   semanas. Un cambio cada vez; al terminar se compara con las 4 anteriores.
2. **Propuesta que funcionó**: si al evaluarla salió "validada", el cambio se
   queda (hasta 6 meses o hasta que otra propuesta de esa zona diga lo
   contrario).
3. **Énfasis del bloque** que eliges en el Centro: +2 series semanales en
   cada grupo marcado ("brazos" = bíceps y tríceps). Antes era solo una
   etiqueta que no cambiaba nada.

El total por grupo se acota a ±4 series y el planificador lo limita al MRV.
"""

from datetime import timedelta

SERIES_POR_AJUSTE = 2
TOPE_AJUSTE = 4
VIGENCIA_VALIDADA_DIAS = 182

GRUPOS_POR_ENFASIS = {
    'gemelos': ['gemelos'], 'hombros': ['hombros'], 'brazos': ['biceps', 'triceps'],
    'espalda': ['espalda'], 'pecho': ['pecho'], 'gluteos': ['gluteos'],
    'cuadriceps': ['cuadriceps'],
}


def _signo(propuesta):
    return -1 if getattr(propuesta, 'direccion', 'subir') == 'bajar' else 1


def ajustes_volumen(cliente, fecha):
    """{grupo: {'series': int, 'motivos': [str]}} vigentes en ``fecha``."""
    ajustes = {}

    def sumar(grupo, series, motivo):
        item = ajustes.setdefault(grupo, {'series': 0, 'motivos': []})
        item['series'] += series
        item['motivos'].append(motivo)

    try:
        from entrenos.models import PropuestaZonaGym
        activas = set()
        for p in PropuestaZonaGym.objects.filter(
            cliente=cliente, estado=PropuestaZonaGym.ESTADO_ACEPTADA,
            inicio__lte=fecha, fin__gte=fecha,
        ):
            activas.add(p.zona)
            series = _signo(p) * SERIES_POR_AJUSTE
            sumar(p.zona, series,
                  f'{series:+d} series de {p.nombre_zona} por la propuesta aceptada (hasta el {p.fin:%d/%m})')
        evaluadas = PropuestaZonaGym.objects.filter(
            cliente=cliente, estado=PropuestaZonaGym.ESTADO_EVALUADA,
            fin__gte=fecha - timedelta(days=VIGENCIA_VALIDADA_DIAS), fin__lt=fecha,
        ).order_by('zona', '-fin')
        vistas = set()
        for p in evaluadas:
            if p.zona in vistas or p.zona in activas:
                continue
            vistas.add(p.zona)  # solo cuenta la última evaluación de cada zona
            if p.resultado == 'validada':
                series = _signo(p) * SERIES_POR_AJUSTE
                sumar(p.zona, series, f'{series:+d} series de {p.nombre_zona}: el cambio funcionó y se queda')
    except Exception:
        pass

    try:
        from entrenos.models import ContratoBloqueGym
        bloque = ContratoBloqueGym.objects.filter(
            cliente=cliente, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            semana_inicio__lte=fecha, semana_fin_prevista__gte=fecha,
        ).order_by('-semana_inicio').first()
        for enfasis in (bloque.objetivos_secundarios if bloque else None) or []:
            for grupo in GRUPOS_POR_ENFASIS.get(enfasis, []):
                sumar(grupo, SERIES_POR_AJUSTE, f'+{SERIES_POR_AJUSTE} series de {grupo} por el énfasis del bloque')
    except Exception:
        pass

    for item in ajustes.values():
        item['series'] = max(-TOPE_AJUSTE, min(TOPE_AJUSTE, item['series']))
    return {g: v for g, v in ajustes.items() if v['series']}


def series_por_grupo(cliente, fecha):
    """Solo los números: {grupo: series_extra}. Lo que consume el planificador."""
    return {g: v['series'] for g, v in ajustes_volumen(cliente, fecha).items()}

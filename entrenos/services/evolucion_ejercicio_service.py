"""
Consulta de evolución por ejercicio (19-nov-2026 · Entrega 1).

SOLO LECTURA y SOLO PARA CONSULTA. Nada de este módulo alimenta propuestas,
revisión de bloque, modelo del usuario, decisiones ni plan: esos servicios
siguen leyendo ``evolucion_muscular_service`` sin cambios. Aquí se enseña el
historial tal y como se registró y se describe lo observado con la incertidumbre
que tenga.

Principios (acordados con David):
- El historial siempre se puede consultar: ninguna ambigüedad oculta registros.
- La serie representativa de una sesión con una carga elegida es la de más
  repeticiones con esa carga (a igualdad, la de menos RPE). Para comparar cargas
  distintas se usa la mayor fuerza estimada: peso × (1 + reps / 30), tope 30
  reps; a igualdad, más peso. Los calentamientos no cuentan.
- El bloque del plan es contexto: ni valida ni descarta una comparación. Solo la
  descarga queda fuera de las conclusiones (su esfuerzo no es comparable), pero
  se ve en la gráfica y en el historial.
- Cumplir los filtros (misma carga y tramo de repeticiones) no es lo mismo que
  tener la carga confirmada. Una comparación con carga pendiente se describe,
  pero se avisa.
- Las confirmaciones (``ConfirmacionCargaEjercicio``) se aplican a ejercicio +
  fechas. Confirmar el equipo de hoy no valida registros antiguos.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import date, timedelta

from django.utils.text import slugify

from entrenos.services.evolucion_muscular_service import _e1rm, _plano, tramo_reps

logger = logging.getLogger(__name__)

PERIODOS = (30, 90, 180)
PERIODO_POR_DEFECTO = 90
MAX_CARGAS_SELECTOR = 4
ULTIMAS_SESIONES = 4
# Las cargas se comparan EXACTAS (39,9 y 40 son cargas distintas). Solo se convierte una carga cuando el
# usuario lo confirma para esa unidad y esas fechas (p. ej. «total de las dos» → la mitad por mancuerna).
# El redondeo a 3 decimales solo evita ruido de coma flotante.
# Un tramo de registro se parte si pasan más de 6 semanas sin sesiones del ejercicio.
HUECO_TRAMO_DIAS = 42

# Ejercicios de esta primera entrega. El servicio vale para cualquier ejercicio;
# la lista se amplía cuando David cierre los tres ejemplos.
EJEMPLOS = (
    ('press-arnold', 'Press Arnold', 'Hombros · mancuernas'),
    ('farmer-walk', 'Farmer Walk', 'Agarre y antebrazos'),
    ('curl-femoral-tumbado', 'Curl Femoral Tumbado', 'Isquios · máquina'),
)

FAMILIAS = {
    'hipertrofia': 'Hipertrofia', 'fuerza': 'Fuerza', 'potencia': 'Potencia',
    'descarga': 'Descarga', 'desconocido': 'Sin bloque',
}
UNIDAD_CARGA_TXT = {'por_mano': 'por mano', 'por_lado': 'por lado', 'total': 'totales'}


# ──────────────────────────── utilidades ────────────────────────────

def num(valor, decimales=3):
    """12 → '12'; 12.5 → '12,5'."""
    if valor is None:
        return '—'
    texto = f'{float(valor):.{decimales}f}'
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto.replace('.', ',')


def porcentaje(a, b):
    """Cambio de a a b en %, con un decimal y signo: '+10,0 %'. Sin redondeos intermedios."""
    if not a:
        return None
    pct = round((float(b) - float(a)) / float(a) * 100, 1)
    if pct == 0:
        return '0 %'
    return f'{"+" if pct > 0 else ""}{pct:.1f}'.replace('.', ',') + ' %'


def fecha_corta(f):
    return f'{f:%d/%m}'


def slug_de(nombre):
    return slugify(_plano(nombre))


def _dia(f):
    return f.date() if hasattr(f, 'date') and callable(f.date) else f


def _exacta(peso):
    return round(float(peso), 3)


def resolver_ejercicio(cliente, slug):
    """Nombre exacto con el que el cliente tiene registros y cuyo slug coincide, o None."""
    from entrenos.models import EjercicioRealizado, SerieRealizada
    nombres = set(SerieRealizada.objects.filter(entreno__cliente=cliente)
                  .values_list('ejercicio__nombre', flat=True).distinct())
    nombres |= set(EjercicioRealizado.objects.filter(entreno__cliente=cliente)
                   .values_list('nombre_ejercicio', flat=True).distinct())
    validos = sorted(n for n in nombres if n)
    for nombre in validos:
        if slug_de(nombre) == slug:
            return nombre
    # Los tres ejemplos admiten el nombre completo del catálogo: en producción el ejercicio se llama
    # «Farmer Walk (Paseo Del Granjero)» y su dirección corta es «farmer-walk». Solo tras fallar la exacta.
    if slug in {s for s, _, _ in EJEMPLOS}:
        for nombre in validos:
            if slug_de(nombre).startswith(slug + '-'):
                return nombre
    return None


def ejemplos_disponibles(cliente, hoy=None):
    """Los ejemplos de la primera entrega con su última sesión (para el acceso desde Memoria)."""
    from entrenos.models import EjercicioRealizado, SerieRealizada
    resultado = []
    for slug, titulo, sub in EJEMPLOS:
        nombre = resolver_ejercicio(cliente, slug)
        if not nombre:
            continue
        fechas = {_dia(f) for f in SerieRealizada.objects.filter(
            entreno__cliente=cliente, ejercicio__nombre=nombre, completado=True,
        ).values_list('entreno__fecha', flat=True)}
        fechas |= {_dia(f) for f in EjercicioRealizado.objects.filter(
            entreno__cliente=cliente, nombre_ejercicio=nombre, completado=True,
        ).values_list('entreno__fecha', flat=True)}
        if fechas:
            resultado.append({'slug': slug, 'nombre': nombre, 'titulo': titulo, 'sub': sub,
                              'ultima': max(fechas), 'sesiones': len(fechas)})
    return resultado


# ──────────────────────────── carga del historial ────────────────────────────

def _carga_unidad(peso_kg, peso_total_kg, mult):
    from entrenos.services.evolucion_muscular_service import _carga_por_unidad
    return _carga_por_unidad(peso_kg, peso_total_kg, mult)


def _base_de(nombre):
    from rutinas.models import EjercicioBase
    return EjercicioBase.objects.filter(nombre=nombre).first()


def _cargar_sesiones(cliente, nombre):
    """Todas las sesiones del ejercicio tal y como se registraron (sin filtrar nada)."""
    from entrenos.models import EjercicioRealizado, SerieRealizada

    por_entreno = OrderedDict()
    series = (SerieRealizada.objects
              .filter(entreno__cliente=cliente, ejercicio__nombre=nombre, completado=True)
              .select_related('entreno').order_by('entreno__fecha', 'entreno_id', 'serie_numero'))
    for s in series:
        ses = por_entreno.setdefault(s.entreno_id, {
            'entreno_id': s.entreno_id, 'fecha': _dia(s.entreno.fecha), 'fuente': 'serie',
            'series': [], 'recuperacion': False,
        })
        ses['series'].append({
            'n': s.serie_numero, 'reps': int(s.repeticiones or 0),
            'peso': float(s.peso_kg) if s.peso_kg is not None else None,
            'peso_total': float(s.peso_total_kg) if s.peso_total_kg is not None else None,
            'carga': _carga_unidad(s.peso_kg, s.peso_total_kg, s.multiplicador_carga),
            'tipo_carga': s.tipo_carga, 'mult': s.multiplicador_carga,
            'metros': float(s.distancia_metros) if s.distancia_metros is not None else None,
            'rpe': s.rpe_real, 'aprox': bool(s.es_aproximacion),
        })
    # Entrenos de antes del detalle por serie: solo hay el agregado del ejercicio.
    medias = (EjercicioRealizado.objects
              .filter(entreno__cliente=cliente, nombre_ejercicio=nombre, completado=True)
              .exclude(entreno_id__in=list(por_entreno))
              .select_related('entreno').order_by('entreno__fecha', 'entreno_id'))
    for e in medias:
        ses = por_entreno.setdefault(e.entreno_id, {
            'entreno_id': e.entreno_id, 'fecha': _dia(e.entreno.fecha), 'fuente': 'media',
            'series': [], 'recuperacion': bool(e.is_recovery_load),
        })
        ses['series'].append({
            'n': 1, 'reps': int(e.repeticiones or 0), 'series_media': int(e.series or 1),
            'peso': float(e.peso_kg) if e.peso_kg is not None else None,
            'peso_total': float(e.peso_total_kg) if e.peso_total_kg is not None else None,
            'carga': _carga_unidad(e.peso_kg, e.peso_total_kg, e.multiplicador_carga),
            'tipo_carga': e.tipo_carga, 'mult': e.multiplicador_carga, 'metros': None,
            'rpe': float(e.rpe_real) if getattr(e, 'rpe_real', None) is not None else None,
            'aprox': False,
        })
    return sorted(por_entreno.values(), key=lambda s: (s['fecha'], s['entreno_id']))


def _medida_de(base, sesiones):
    tipo = getattr(base, 'tipo_progresion', None)
    if tipo == 'progresion_distancia' or any(x['metros'] is not None for s in sesiones for x in s['series']):
        return 'distancia'
    if tipo == 'progresion_tiempo':
        return 'tiempo'
    return 'fuerza'


UNIDAD_VALOR = {'fuerza': 'reps', 'distancia': 'm', 'tiempo': 's'}


def _pares_registro(s):
    """Cómo se registró la carga de la sesión: {(tipo_carga, multiplicador)} de sus series de trabajo."""
    trabajo = [x for x in s['series'] if not x['aprox']] or s['series']
    return sorted({(x['tipo_carga'] or '-', x['mult'] if x['mult'] is not None else '-') for x in trabajo}, key=str)


def texto_registro(pares):
    """'sin tipo de carga', 'peso total ×1', 'por mano ×2'…"""
    nombres = {'total': 'peso total', 'por_mano': 'por mano', 'por_lado': 'por lado'}
    partes = [('sin tipo de carga' if t == '-' else f'{nombres.get(t, t)}'
               + (f' ×{m}' if m != '-' else '')) for t, m in pares]
    return ' y '.join(partes)


def _marcar_ambiguedades(nombre, base, medida, sesiones):
    """
    Marca cada sesión con la ambigüedad identificada (o None) y su firma de registro.

    La detección NO depende de la escala de pesos configurada hoy: se basa en CÓMO se registró la carga.
    - ``unidad_carga``: ejercicios de dos mancuernas cuyo registro no identifica el peso por mancuerna
      de forma inequívoca. Lo inequívoco es «por mano ×2» (peso de una mancuerna y multiplicador 2). Sin tipo
      de carga, o como «peso total ×1» (el número puede ser el de cada mancuerna o el de las dos), se pregunta.
      Los decimales, los incrementos o la escala por sí solos NO demuestran la unidad y no entran en la regla.
    - ``unidad_medida``: ejercicios de distancia con sesiones sin metros y solo repeticiones (antes de
      registrar la distancia): no se sabe qué medía ese número.
    Un cambio de firma entre sesiones consecutivas separa los tramos que se preguntan por separado.
    """
    from entrenos.services.maquina_service import tipo_equipo_carga

    es_mancuernas = tipo_equipo_carga(nombre, getattr(base, 'equipo', None)) == 'mancuerna_dos'
    for s in sesiones:
        s['ambiguedad'], s['firma'], s['firma_txt'] = None, None, ''
        trabajo = [x for x in s['series'] if not x['aprox']]
        if medida == 'distancia':
            if trabajo and all(x['metros'] is None for x in trabajo):
                s['ambiguedad'], s['firma'] = 'unidad_medida', 'reps'
                s['firma_txt'] = 'solo repeticiones, sin metros'
        elif es_mancuernas and trabajo:
            pares = _pares_registro(s)
            s['firma'] = repr(pares)
            if pares != [('por_mano', 2)]:
                s['ambiguedad'] = 'unidad_carga'
                s['firma_txt'] = texto_registro(pares)
    return sesiones


def _tramos_ambiguos(sesiones):
    """Tramos: sesiones ambiguas consecutivas, con la misma firma y sin más de 6 semanas entre ellas."""
    tramos, actual = [], None
    for s in sesiones:
        amb = s['ambiguedad']
        if amb is None:
            actual = None
            continue
        if (actual is not None and actual['ambiguedad'] == amb and actual['firma'] == s['firma']
                and (s['fecha'] - actual['hasta']).days <= HUECO_TRAMO_DIAS):
            actual['sesiones'].append(s)
            actual['hasta'] = s['fecha']
        else:
            actual = {'ambiguedad': amb, 'firma': s['firma'], 'firma_txt': s['firma_txt'], 'desde': s['fecha'],
                      'hasta': s['fecha'], 'sesiones': [s]}
            tramos.append(actual)
    for i, t in enumerate(tramos):
        t['indice'] = i
        t['n'] = len(t['sesiones'])
        pend = sum(1 for s in t['sesiones'] if s['pendiente'])
        t['pendientes'] = pend
        t['estado'] = 'pendiente' if pend == t['n'] else 'confirmada' if pend == 0 else 'parcial'
        t.pop('sesiones')
    return tramos


def _aplicar_confirmaciones(cliente, nombre, sesiones):
    from entrenos.models import ConfirmacionCargaEjercicio as C
    filas = list(C.objects.filter(cliente=cliente, ejercicio_clave=_plano(nombre)).order_by('-id'))
    for s in sesiones:
        s['confirmacion'] = None
        s['pendiente'] = s['ambiguedad'] is not None
        s['factor_carga'] = 1.0
        s['medida_en_metros'] = False
        if not s['ambiguedad']:
            continue
        conf = next((c for c in filas if c.ambiguedad == s['ambiguedad'] and c.desde <= s['fecha'] <= c.hasta), None)
        s['confirmacion'] = conf
        if conf is None or conf.respuesta == C.RESPUESTA_NO_RECUERDO:
            continue
        s['pendiente'] = False
        if conf.respuesta == 'total_dos':
            s['factor_carga'] = 0.5
        elif conf.respuesta == 'metros':
            s['medida_en_metros'] = True
    return filas


def _valor_serie(s, x, medida):
    """Valor de una serie en la medida del ejercicio, o None si no se puede dar (medida sin confirmar)."""
    if medida == 'distancia':
        if x['metros'] is not None:
            return float(x['metros'])
        return float(x['reps']) if s.get('medida_en_metros') else None
    return float(x['reps'])


def cargar_historial(cliente, nombre):
    """Historial completo del ejercicio, listo para consultar (solo lectura)."""
    from entrenos.services.comparabilidad_service import Bloques
    base = _base_de(nombre)
    sesiones = _cargar_sesiones(cliente, nombre)
    medida = _medida_de(base, sesiones)
    _marcar_ambiguedades(nombre, base, medida, sesiones)
    confirmaciones = _aplicar_confirmaciones(cliente, nombre, sesiones)
    bloques = Bloques(cliente)
    ultima_firma = None
    for s in sesiones:
        b = bloques.de(s['fecha'])
        s['familia'], s['bloque'] = b['familia'], b['nombre']
        s['excluida'] = 'descarga' if b['familia'] == 'descarga' else ('recuperacion' if s['recuperacion'] else None)
        trabajo = [x for x in s['series'] if not x['aprox']]
        for x in s['series']:
            x['carga_efectiva'] = round(x['carga'] * s['factor_carga'], 2) if x['carga'] else 0.0
            x['valor'] = _valor_serie(s, x, medida)
        s['trabajo'] = [x for x in trabajo]
        tipos = {x['tipo_carga'] for x in trabajo if x['tipo_carga']}
        s['tipo_carga'] = next(iter(tipos)) if len(tipos) == 1 else (None if not tipos else 'mixto')
        s['unidad_carga'] = _unidad_texto(s, medida)
        s['clave_unidad'] = (medida, s['tipo_carga'], s['ambiguedad'] == 'unidad_medida' and not s['medida_en_metros'])
    if sesiones:
        ultima_firma = sesiones[-1]['clave_unidad']
    for s in sesiones:
        # Registro de otra unidad que la actual (p. ej. peso total en vez de por mano, o reps en vez de metros).
        s['otra_unidad'] = bool(ultima_firma) and s['clave_unidad'] != ultima_firma
    return {'nombre': nombre, 'slug': slug_de(nombre), 'base': base, 'medida': medida,
            'unidad_valor': UNIDAD_VALOR[medida], 'sesiones': sesiones,
            'tramos': _tramos_ambiguos(sesiones), 'confirmaciones': confirmaciones}


def _unidad_texto(s, medida):
    conf = s.get('confirmacion')
    if s['ambiguedad'] == 'unidad_carga' and conf and conf.respuesta in ('por_mancuerna', 'total_dos'):
        return 'por mancuerna'
    return UNIDAD_CARGA_TXT.get(s['tipo_carga'], '') if s['tipo_carga'] and s['tipo_carga'] != 'mixto' else ''


# ──────────────────────────── cargas y series representativas ────────────────────────────

def _token(valor, pendiente):
    texto = num(valor).replace(',', '.')
    return texto + ('~' if pendiente else '')


def _desde_token(token):
    pendiente = token.endswith('~')
    try:
        return float(token.rstrip('~')), pendiente
    except ValueError:
        return None, False


def _series_con_carga(s, valor, pendiente):
    """Series de trabajo de la sesión con esa carga (agrupada) y ese estado de confirmación."""
    if bool(s['pendiente']) != bool(pendiente):
        return []
    return [x for x in s['trabajo'] if x['carga_efectiva'] > 0
            and abs(_exacta(x['carga_efectiva']) - valor) < 1e-6]


def representativa(s, medida, carga=None):
    """Serie representativa de la sesión (ver cabecera). Con carga: la de más valor a esa carga."""
    if carga is not None:
        cand = [x for x in carga if x['valor'] is not None]
        if not cand:
            return None
        return max(cand, key=lambda x: (x['valor'], -(x['rpe'] if x['rpe'] is not None else 99)))
    cand = [x for x in s['trabajo'] if x['valor'] is not None and x['carga_efectiva'] > 0]
    if not cand:
        return None
    if medida == 'fuerza':
        return max(cand, key=lambda x: (_e1rm(x['carga_efectiva'], x['reps']), x['carga_efectiva']))
    return max(cand, key=lambda x: (x['valor'], x['carga_efectiva']))


def _cargas_periodo(historial, desde, hoy):
    """Cargas con sesiones en el periodo, de la más reciente a la más antigua."""
    cargas = OrderedDict()
    for s in reversed(historial['sesiones']):
        if not (desde < s['fecha'] <= hoy):
            continue
        for x in s['trabajo']:
            if x['carga_efectiva'] <= 0 or x['valor'] is None:
                continue
            clave = (_exacta(x['carga_efectiva']), bool(s['pendiente']))
            c = cargas.setdefault(clave, {'valor': clave[0], 'pendiente': clave[1], 'fechas': set(),
                                          'ultima': s['fecha'], 'otra_unidad': bool(s['otra_unidad'])})
            c['fechas'].add(s['fecha'])
    resultado = []
    for (valor, pend), c in cargas.items():
        resultado.append({'valor': valor, 'pendiente': pend, 'token': _token(valor, pend),
                          'n': len(c['fechas']), 'ultima': c['ultima'], 'otra_unidad': c['otra_unidad']})
    return resultado


def _etiqueta_carga(c, todas, unidad_txt=''):
    gemela = any(o is not c and o['valor'] == c['valor'] and o['pendiente'] != c['pendiente'] for o in todas)
    txt = f'{num(c["valor"])} kg'
    if unidad_txt:
        txt += f' {unidad_txt}'
    if gemela and c['pendiente']:
        txt += ' · sin confirmar'
    return txt


def _carga_por_defecto(cargas):
    """La carga con más sesiones en el periodo; a igualdad, la más reciente."""
    validas = [c for c in cargas if not c['otra_unidad']] or cargas
    return max(validas, key=lambda c: (c['n'], c['ultima'])) if validas else None


# ──────────────────────────── conclusión ────────────────────────────

def _rpe_txt(rpe):
    return f' a\u00a0RPE\u00a0{num(rpe)}' if rpe else ''


def _val_txt(valor, unidad):
    return f'{num(valor, 0 if unidad != "m" else 2)} {unidad}'


def _conclusion(historial, desde, hoy, valor, pendiente, etiqueta):
    medida, unidad = historial['medida'], historial['unidad_valor']
    todas = [s for s in historial['sesiones'] if desde < s['fecha'] <= hoy]
    con = []
    for s in todas:
        cs = _series_con_carga(s, valor, pendiente)
        rep = representativa(s, medida, cs) if cs else None
        if rep:
            con.append((s, rep, cs))
    rango = f'{fecha_corta(desde + timedelta(days=1))}–{fecha_corta(hoy)}'
    utiles = [t for t in con if not t[0]['excluida']]
    excluidas = [t for t in con if t[0]['excluida']]
    nota_desc = None
    if excluidas:
        fechas = ', '.join(fecha_corta(t[0]['fecha']) for t in excluidas)
        nota_desc = (f'{"La sesión" if len(excluidas) == 1 else "Las sesiones"} del {fechas} '
                     f'({"descarga" if excluidas[0][0]["excluida"] == "descarga" else "carga de recuperación"}) '
                     f'se ven en la gráfica y el historial, pero no entran en esta conclusión.')
    base = {'estado': None, 'titulo': '', 'detalle': '', 'avisos': [], 'extra': None, 'filtros': None,
            'nota': nota_desc, 'comparadas': []}

    if not utiles:
        previas = [s for s in historial['sesiones'] if s['fecha'] <= desde and not s['excluida']
                   and _series_con_carga(s, valor, pendiente)]
        ult = f' Última con esta carga: {fecha_corta(previas[-1]["fecha"])}.' if previas else ''
        base.update(estado='sin_sesiones', titulo=f'Sin sesiones con {etiqueta}',
                    detalle=f'{rango}.{ult} Tu historial completo sigue en el detalle.')
        return base

    f, la = utiles[0], utiles[-1]
    pk = max(utiles, key=lambda t: (t[1]['valor'], -t[0]['fecha'].toordinal()))
    if len(utiles) == 1:
        s, rep, _ = f
        base.update(estado='una_sesion',
                    titulo=f'{etiqueta}: {_val_txt(rep["valor"], unidad)} el {fecha_corta(s["fecha"])}',
                    detalle=f'{rango} · una sola sesión con esta carga{_rpe_txt(rep["rpe"])}; no hay con qué compararla.',
                    comparadas=[s])
        if s['pendiente']:
            base['avisos'].append('Carga pendiente de comprobar.')
        return base

    def ctx(a, b):
        return a[0]['familia'] != b[0]['familia']

    fs, ls, ps = f[0], la[0], pk[0]
    if pk is f:
        base['titulo'] = (f'{etiqueta}: {_val_txt(f[1]["valor"], unidad)}{_rpe_txt(f[1]["rpe"])} el {fecha_corta(fs["fecha"])} '
                          f'y {_val_txt(la[1]["valor"], unidad)}{_rpe_txt(la[1]["rpe"])} el {fecha_corta(ls["fecha"])}')
        base['detalle'] = f'{rango}.'
        par = (f, la)
        if ctx(f, la):
            base['avisos'].append(f'Cambió el bloque ({FAMILIAS[fs["familia"]].lower()} → {FAMILIAS[ls["familia"]].lower()}): '
                                  'es contexto; no se lee como mejora ni como pérdida por sí solo.')
    else:
        base['titulo'] = f'{etiqueta}: de {num(f[1]["valor"], 0 if unidad != "m" else 2)} a {_val_txt(pk[1]["valor"], unidad)}'
        base['detalle'] = (f'{fecha_corta(fs["fecha"])}: {_val_txt(f[1]["valor"], unidad)}{_rpe_txt(f[1]["rpe"])} → '
                           f'{fecha_corta(ps["fecha"])}: {_val_txt(pk[1]["valor"], unidad)}{_rpe_txt(pk[1]["rpe"])} · {rango}.')
        if la is not pk:
            base['detalle'] += (f' Última: {_val_txt(la[1]["valor"], unidad)}{_rpe_txt(la[1]["rpe"])} el {fecha_corta(ls["fecha"])}'
                                + (f', en otro bloque ({FAMILIAS[ls["familia"]].lower()}).' if ctx(pk, la) else '.'))
        par = (f, pk)
        if ctx(f, pk):
            base['avisos'].append(f'Cambió el bloque ({FAMILIAS[fs["familia"]].lower()} → {FAMILIAS[ps["familia"]].lower()}): '
                                  'la mejora se ve; su causa no es concluyente.')
    comparadas = {id(t[0]): t[0] for t in (f, pk, la)}
    base['comparadas'] = list(comparadas.values())

    # Información adicional: cambio relativo (fuerza estimada, o metros) cuando es comparable.
    a, b = par[0][1], par[1][1]
    if medida == 'fuerza':
        base['extra'] = None
        if tramo_reps(int(a['reps'])) == tramo_reps(int(b['reps'])):
            pct = porcentaje(_e1rm(a['carga_efectiva'], a['reps']), _e1rm(b['carga_efectiva'], b['reps']))
            base['extra'] = f'Información adicional: fuerza estimada {pct}.' if pct else None
        cumple = tramo_reps(int(a['reps'])) == tramo_reps(int(b['reps']))
    else:
        pct = porcentaje(a['valor'], b['valor'])
        base['extra'] = f'Información adicional: {pct} de distancia.' if pct and par[0] is not par[1] else None
        cumple = True
    pendiente_comp = any(s['pendiente'] for s in comparadas.values())
    base['filtros'] = {'cumple_filtros': bool(cumple), 'carga_confirmada': not pendiente_comp,
                       'valida': bool(cumple) and not pendiente_comp}
    if pendiente_comp:
        base['avisos'].insert(0, 'Comparación pendiente de comprobar la carga.')
    base['estado'] = 'pendiente_carga' if pendiente_comp else 'comparada'
    return base


# ──────────────────────────── consulta principal ────────────────────────────

def consulta(cliente, nombre, dias=PERIODO_POR_DEFECTO, carga=None, hoy=None, historial=None):
    """
    Todo lo que enseña la pantalla de un ejercicio para un periodo y una carga:
    conclusión, gráfica y últimas sesiones salen del MISMO periodo y la MISMA carga.
    """
    hoy = hoy or date.today()
    dias = dias if dias in PERIODOS else PERIODO_POR_DEFECTO
    desde = hoy - timedelta(days=dias)
    h = historial or cargar_historial(cliente, nombre)
    medida, unidad = h['medida'], h['unidad_valor']
    out = {'nombre': nombre, 'slug': h['slug'], 'medida': medida, 'unidad': unidad, 'dias': dias,
           'desde': desde, 'hoy': hoy, 'periodos': PERIODOS, 'tramos': h['tramos'],
           'tiene_historial': bool(h['sesiones'])}
    if not h['sesiones']:
        out.update(cargas=[], carga=None, conclusion=None, puntos=[], bandas=[], ultimas=[], sesiones_periodo=0)
        return out

    cargas = _cargas_periodo(h, desde, hoy)
    cargas.sort(key=lambda c: (-c['ultima'].toordinal(), -c['valor']))
    sel_valor, sel_pend = _desde_token(carga or '')
    elegida = next((c for c in cargas if sel_valor is not None and abs(c['valor'] - sel_valor) < 1e-6
                    and c['pendiente'] == sel_pend), None)
    if elegida is None and sel_valor is not None:
        elegida = {'valor': sel_valor, 'pendiente': sel_pend, 'token': _token(sel_valor, sel_pend),
                   'n': 0, 'ultima': None, 'otra_unidad': False}
        cargas.append(elegida)
    if elegida is None:
        elegida = _carga_por_defecto(cargas)
    if elegida is None:
        # Sin cargas con datos en el periodo: se elige la última con registros.
        ult = next((s for s in reversed(h['sesiones']) if s['trabajo']), None)
        x = representativa(ult, medida) if ult else None
        if x:
            elegida = {'valor': _exacta(x['carga_efectiva']), 'pendiente': bool(ult['pendiente']),
                       'token': _token(_exacta(x['carga_efectiva']), bool(ult['pendiente'])),
                       'n': 0, 'ultima': ult['fecha'], 'otra_unidad': False}
            cargas.append(elegida)
    unidad_txt = ''
    for s in reversed(h['sesiones']):
        if s['unidad_carga']:
            unidad_txt = s['unidad_carga']
            break
    visibles = [c for c in cargas][:MAX_CARGAS_SELECTOR]
    if elegida is not None and elegida not in visibles:
        visibles = visibles[:MAX_CARGAS_SELECTOR - 1] + [elegida]
    for c in visibles:
        c['etiqueta'] = _etiqueta_carga(c, cargas, unidad_txt if medida == 'distancia' else '')
        c['activa'] = c is elegida
    out['cargas'] = visibles
    out['mas_cargas'] = max(len(cargas) - len(visibles), 0)
    out['carga'] = elegida
    if elegida is None:
        out.update(conclusion=None, puntos=[], bandas=[], ultimas=[], sesiones_periodo=0)
        return out

    etiqueta = elegida['etiqueta']
    out['conclusion'] = _conclusion(h, desde, hoy, elegida['valor'], elegida['pendiente'], etiqueta)

    # Gráfica: solo sesiones de esa carga; las de otra unidad o sin confirmar no se unen a las demás.
    puntos = []
    for s in h['sesiones']:
        if not (desde < s['fecha'] <= hoy):
            continue
        cs = _series_con_carga(s, elegida['valor'], elegida['pendiente'])
        rep = representativa(s, medida, cs) if cs else None
        if rep:
            puntos.append({'fecha': s['fecha'], 'valor': rep['valor'], 'rpe': rep['rpe'], 'familia': s['familia'],
                           'excluida': s['excluida'], 'pendiente': bool(s['pendiente'])})
    out['puntos'] = puntos
    # Banda «otra unidad»: sesiones del periodo registradas con otra unidad o medida sin confirmar.
    otras = [s['fecha'] for s in h['sesiones'] if desde < s['fecha'] <= hoy and (s['otra_unidad'] or (
        s['ambiguedad'] == 'unidad_medida' and not s['medida_en_metros']))]
    out['bandas'] = [(min(otras), max(otras), 'Otra unidad')] if otras and medida == 'distancia' else []
    out['hay_otra_unidad'] = bool(otras)
    if otras and medida == 'distancia':
        out['conclusion']['avisos'].append(
            'Hay registros con otra unidad de medida: se ven aparte y no se incluyen en esta conclusión.')

    # Últimas sesiones (cualquier carga). Las de la carga elegida se marcan; las demás enlazan a su carga.
    ultimas = []
    for s in sorted([s for s in h['sesiones'] if desde < s['fecha'] <= hoy], key=lambda s: s['fecha'], reverse=True)[:ULTIMAS_SESIONES]:
        cs = _series_con_carga(s, elegida['valor'], elegida['pendiente'])
        fila = {'fecha': s['fecha'], 'familia': s['familia'], 'bloque': s['bloque'], 'excluida': s['excluida'],
                'pendiente': bool(s['pendiente']), 'con_carga': bool(cs), 'otra_unidad': bool(s['otra_unidad'])}
        if cs:
            rep = representativa(s, medida, cs)
            fila.update(valor=rep['valor'], rpe=rep['rpe'], series=len(cs))
        else:
            rep = representativa(s, medida)
            if rep:
                fila.update(valor=rep['valor'], rpe=rep['rpe'], carga=_exacta(rep['carga_efectiva']),
                            token=_token(_exacta(rep['carga_efectiva']), bool(s['pendiente'])),
                            peso_real=rep['carga_efectiva'])
            else:
                fila.update(valor=None, rpe=None)
        ultimas.append(fila)
    out['ultimas'] = ultimas
    out['sesiones_periodo'] = sum(1 for s in h['sesiones'] if desde < s['fecha'] <= hoy)
    return out


# ──────────────────────────── perfil de fuerza ────────────────────────────

def perfil_fuerza(cliente, hoy=None, dias=90):
    """
    Perfil de fuerza de los últimos ``dias`` días, con tres cosas SEPARADAS:
    la mejor serie registrada, el 1RM estimado a partir de ella y el récord
    guardado. «Mejor» = mayor fuerza estimada entre todas las series de trabajo
    del periodo (a igualdad, más peso); no depende de qué pareja de marcas haya
    elegido la comparación entre periodos.

    No alimenta ninguna decisión: solo se muestra.
    """
    from entrenos.models import EjercicioRealizado, RecordPersonal, SerieRealizada
    from rutinas.models import EjercicioBase

    hoy = hoy or date.today()
    desde = hoy - timedelta(days=dias)
    sin_1rm = {_plano(n) for n in EjercicioBase.objects.filter(
        tipo_progresion__in=('progresion_tiempo', 'progresion_distancia')).values_list('nombre', flat=True)}

    def clave(nombre):
        return ' '.join(p[:-1] if len(p) > 3 and p.endswith('s') else p for p in _plano(nombre).split())

    mejores = {}

    def candidato(nombre, fecha, peso, reps, fuente):
        if not nombre or _plano(nombre) in sin_1rm or not peso or peso <= 0 or reps < 1:
            return
        e = _e1rm(peso, reps)
        if e <= 0:
            return
        k = clave(nombre)
        actual = mejores.get(k)
        if actual is None or (e, peso) > (actual['e1rm_raw'], actual['peso']):
            mejores[k] = {'ejercicio': nombre.strip(), 'e1rm_raw': e, 'peso': float(peso), 'reps': int(reps),
                          'fecha': fecha, 'fuente': fuente}

    con_series = set()
    for eid, nombre, fecha, peso, total, mult, reps in SerieRealizada.objects.filter(
            entreno__cliente=cliente, entreno__fecha__gt=desde, entreno__fecha__lte=hoy, completado=True,
            es_aproximacion=False, distancia_metros__isnull=True, repeticiones__gte=1,
    ).values_list('entreno_id', 'ejercicio__nombre', 'entreno__fecha', 'peso_kg', 'peso_total_kg',
                  'multiplicador_carga', 'repeticiones'):
        con_series.add((eid, _plano(nombre)))
        candidato(nombre, _dia(fecha), _carga_unidad(peso, total, mult), int(reps), 'serie')
    for eid, nombre, fecha, peso, total, mult, reps, rec in EjercicioRealizado.objects.filter(
            entreno__cliente=cliente, entreno__fecha__gt=desde, entreno__fecha__lte=hoy, completado=True,
    ).values_list('entreno_id', 'nombre_ejercicio', 'entreno__fecha', 'peso_kg', 'peso_total_kg',
                  'multiplicador_carga', 'repeticiones', 'is_recovery_load'):
        if rec or (eid, _plano(nombre)) in con_series:
            continue
        candidato(nombre, _dia(fecha), _carga_unidad(peso, total, mult), int(reps or 0), 'media')

    records = {}
    for r in RecordPersonal.objects.filter(cliente=cliente, tipo_record='peso_maximo', superado=False).order_by('valor'):
        records[clave(r.ejercicio_nombre)] = float(r.valor)

    resultado = []
    for k, m in mejores.items():
        resultado.append({
            'ejercicio': m['ejercicio'], 'slug': slug_de(m['ejercicio']),
            'rm': round(m['e1rm_raw'], 1), 'fecha': m['fecha'],
            'peso': m['peso'], 'reps': m['reps'], 'fuente': m['fuente'],
            'registrada': f'{num(m["peso"])} kg × {m["reps"]}',
            'record': records.get(k), 'dias': dias,
        })
    return sorted(resultado, key=lambda x: -x['rm'])

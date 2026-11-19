"""Pantallas de evolución por ejercicio (19-nov-2026, Entrega 1): consulta, detalle y confirmación de carga.

Solo consulta. No alimenta al entrenador (ver ``entrenos.services.evolucion_ejercicio_service``).
"""

import logging
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from entrenos.models import ConfirmacionCargaEjercicio as Confirmacion
from entrenos.services import evolucion_ejercicio_service as svc
from entrenos.services.evolucion_ejercicio_grafica import COLOR_FAMILIA, NOMBRE_FAMILIA, grafica_svg, leyenda
from entrenos.services.evolucion_muscular_service import _plano

logger = logging.getLogger(__name__)

TEXTOS_AMBIGUEDAD = {
    'unidad_carga': {
        'pregunta': '¿El peso que anotas es el de cada mancuerna o el total de las dos?',
        'opciones': (('por_mancuerna', 'Por mancuerna'), ('total_dos', 'Total de las dos'), ('no_recuerdo', 'No lo recuerdo')),
        'detalle': ('En estos registros la carga consta como «{firma}». La app tiene este ejercicio como dos '
                    'mancuernas, con el peso de una mancuerna y multiplicador 2, así que el número puede ser el de cada '
                    'mancuerna o el de las dos. Es una posible discrepancia de configuración o de cómo se anotó el peso '
                    '(o ambas) que hay que comprobar: los decimales, los incrementos o la escala por sí solos no la '
                    'demuestran. Hasta que lo confirmes se siguen mostrando todos los registros, marcados como carga '
                    'por comprobar.'),
    },
    'unidad_medida': {
        'pregunta': 'En estos registros, ¿el número que aparece como repeticiones eran metros?',
        'opciones': (('metros', 'Sí, metros'), ('repeticiones', 'No, repeticiones'), ('no_recuerdo', 'No lo recuerdo')),
        'detalle': ('Estos registros constan como «{firma}»: este ejercicio guardaba un número como repeticiones '
                    'antes de registrar la distancia. Si eran metros, se unen a la gráfica; si no, quedan aparte. '
                    'Hasta que lo confirmes se muestran separados de los metros confirmados.'),
    },
}


def _cliente(request, cliente_id):
    from clientes.views import _obtener_cliente_autorizado
    return _obtener_cliente_autorizado(request, cliente_id)


def _nombre_o_404(cliente, slug):
    nombre = svc.resolver_ejercicio(cliente, slug)
    if not nombre:
        raise Http404('Ejercicio sin registros')
    return nombre


def _color(familia):
    return COLOR_FAMILIA.get(familia, '#9da5ad')


def _preparar_consulta(c):
    """Textos de las filas de «Últimas sesiones» (el servicio devuelve números, la vista los escribe)."""
    sufijo = {'reps': 'reps', 'm': 'm', 's': 's'}[c['unidad']]
    for u in c.get('ultimas') or []:
        u['color'] = _color(u['familia'])
        u['familia_txt'] = NOMBRE_FAMILIA.get(u['familia'], u['familia'])
        u['valor_txt'] = f'{svc.num(u["valor"], 2 if c["unidad"] == "m" else 0)}\u00a0{sufijo}' if u.get('valor') is not None else ''
        u['rpe_txt'] = f' a\u00a0RPE\u00a0{svc.num(u["rpe"])}' if u.get('rpe') else ''
        if u.get('carga') is not None:
            u['carga_txt'] = f'{svc.num(u["carga"])} kg'
    return c


def _preparar_detalle(sesiones, medida):
    for s in sesiones:
        s['color'] = _color(s['familia'])
        s['familia_txt'] = NOMBRE_FAMILIA.get(s['familia'], s['familia'])
        for x in s['series']:
            x['peso_txt'] = f'{svc.num(x["peso"], 2)} kg' if x['peso'] else ('0 kg' if x['peso'] == 0 else '—')
            x['tipo_txt'] = svc.UNIDAD_CARGA_TXT.get(x['tipo_carga'], '')
            if medida == 'distancia':
                x['valor_orig_txt'] = (svc.num(x['metros'], 2) + ' m') if x['metros'] is not None else f'{x["reps"]} (campo repeticiones)'
            else:
                x['valor_orig_txt'] = str(x['reps'])
            x['rpe_txt_plano'] = svc.num(x['rpe']) if x['rpe'] else '—'
    return sesiones


def _entero(valor, defecto):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


@login_required
def evolucion_ejercicio(request, cliente_id, slug):
    cliente = _cliente(request, cliente_id)
    nombre = _nombre_o_404(cliente, slug)
    dias = _entero(request.GET.get('dias'), svc.PERIODO_POR_DEFECTO)
    c = _preparar_consulta(svc.consulta(cliente, nombre, dias=dias, carga=request.GET.get('carga'), hoy=date.today()))
    contexto = {
        'cliente': cliente, 'c': c, 'titulo': nombre,
        'grafica': grafica_svg(c, f'{nombre}: evolución en {c["dias"]} días') if c.get('puntos') else '',
        'leyenda': leyenda(c) if c.get('puntos') else [],
        'tramos_pendientes': [t for t in c['tramos'] if t['estado'] != 'confirmada' and t['hasta'] > c['desde']],
        'hay_tramos_antiguos': any(t['estado'] != 'confirmada' and t['hasta'] <= c['desde'] for t in c['tramos']),
        'confirmado': request.GET.get('ok') == '1',
        'sub': next((t[2] for t in svc.EJEMPLOS if t[0] == slug), ''),
    }
    return render(request, 'clientes/evolucion_ejercicio/ejercicio.html', contexto)


@login_required
def evolucion_ejercicio_detalle(request, cliente_id, slug):
    cliente = _cliente(request, cliente_id)
    nombre = _nombre_o_404(cliente, slug)
    h = svc.cargar_historial(cliente, nombre)
    sesiones = _preparar_detalle(list(reversed(h['sesiones'])), h['medida'])
    pendientes = [t for t in h['tramos'] if t['estado'] != 'confirmada']
    return render(request, 'clientes/evolucion_ejercicio/detalle.html', {
        'cliente': cliente, 'titulo': nombre, 'h': h, 'sesiones': sesiones, 'unidad': h['unidad_valor'],
        'tramos': h['tramos'], 'pendientes': pendientes, 'historial_confirmaciones': _historial_confirmaciones(h),
    })


def _historial_confirmaciones(h):
    """Todas las confirmaciones guardadas, de la más reciente a la más antigua, con su estado."""
    vigentes = {s['confirmacion'].id for s in h['sesiones'] if s.get('confirmacion')}
    return [{'c': c, 'vigente': c.id in vigentes} for c in h['confirmaciones']]


def _fecha(valor):
    try:
        return date.fromisoformat((valor or '').strip())
    except ValueError:
        return None


@login_required
def confirmar_carga(request, cliente_id, slug):
    cliente = _cliente(request, cliente_id)
    nombre = _nombre_o_404(cliente, slug)
    h = svc.cargar_historial(cliente, nombre)
    tramos = h['tramos']
    if not tramos:
        return redirect(reverse('clientes:evolucion_ejercicio', args=[cliente.id, slug]))
    if request.method == 'POST':
        indice = _entero(request.POST.get('tramo'), 0)
    else:
        indice = _entero(request.GET.get('tramo'), next((t['indice'] for t in reversed(tramos) if t['estado'] != 'confirmada'), 0))
    tramo = tramos[indice] if 0 <= indice < len(tramos) else tramos[0]
    textos = TEXTOS_AMBIGUEDAD[tramo['ambiguedad']]
    opciones = textos['opciones']

    # Valores del formulario: sin opción preseleccionada al abrir; al corregir, se parte de la respuesta vigente.
    form = {'respuesta': '', 'desde': tramo['desde'].isoformat(), 'hasta': tramo['hasta'].isoformat()}
    if request.method != 'POST':
        corregir = _entero(request.GET.get('corregir'), 0)
        previa = next((c for c in h['confirmaciones'] if c.id == corregir), None)
        if previa and previa.ambiguedad == tramo['ambiguedad']:
            form.update(respuesta=previa.respuesta, desde=max(previa.desde, tramo['desde']).isoformat(),
                        hasta=min(previa.hasta, tramo['hasta']).isoformat())
    error = None
    if request.method == 'POST':
        form = {'respuesta': request.POST.get('respuesta', ''), 'desde': request.POST.get('desde', ''),
                'hasta': request.POST.get('hasta', '')}
        validas = Confirmacion.RESPUESTAS_POR_AMBIGUEDAD[tramo['ambiguedad']]
        desde, hasta = _fecha(form['desde']), _fecha(form['hasta'])
        if form['respuesta'] not in validas:
            error = 'Elige una respuesta antes de guardar.'
        elif not desde or not hasta:
            error = 'Indica las dos fechas.'
        elif desde > hasta:
            error = 'La fecha de inicio no puede ser posterior a la final.'
        elif desde < tramo['desde'] or hasta > tramo['hasta']:
            error = (f'Las fechas deben estar entre el {tramo["desde"]:%d/%m/%Y} y el {tramo["hasta"]:%d/%m/%Y}, '
                     'que es el tramo de registros que se pregunta aquí.')
        else:
            try:
                with transaction.atomic():
                    Confirmacion.objects.create(
                        cliente=cliente, ejercicio_clave=_plano(nombre), ejercicio_nombre=nombre,
                        ambiguedad=tramo['ambiguedad'], respuesta=form['respuesta'], desde=desde, hasta=hasta)
            except DatabaseError:
                logger.exception('confirmar_carga: no se pudo guardar (cliente=%s, ejercicio=%s)', cliente.id, nombre)
                error = 'No se ha guardado. No se ha cambiado nada; inténtalo de nuevo en un momento.'
            else:
                return redirect(reverse('clientes:evolucion_ejercicio', args=[cliente.id, slug]) + '?ok=1')

    aplicara = sum(1 for s in h['sesiones'] if s['ambiguedad'] == tramo['ambiguedad']
                   and (_fecha(form['desde']) or tramo['desde']) <= s['fecha'] <= (_fecha(form['hasta']) or tramo['hasta'])
                   and tramo['desde'] <= s['fecha'] <= tramo['hasta'])
    return render(request, 'clientes/evolucion_ejercicio/confirmar.html', {
        'cliente': cliente, 'titulo': nombre, 'slug': slug, 'tramo': tramo, 'tramos': tramos,
        'textos': {**textos, 'detalle': textos['detalle'].format(firma=tramo['firma_txt'])},
        'opciones': opciones, 'form': form, 'error': error, 'aplicara': aplicara,
        'historial_confirmaciones': _historial_confirmaciones(h),
    }, status=200)

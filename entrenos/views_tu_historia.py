"""Tu historia en el gym (14-nov-2026) · panel tipo resumen anual.

GET: la historia viva (desde el primer entreno hasta hoy) o una edición
congelada con ?edicion=AAAA.
POST (accion): «frase» guarda la frase del año, «carta» sella una carta al yo
del futuro, «congelar» guarda la edición del año tal como se ve hoy.
"""
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from clientes.views import _obtener_cliente_autorizado
from entrenos.models import EdicionHistoria, NotaHistoria
from entrenos.services.tu_historia_service import (
    _fecha_larga, calcular_historia, cifras_del_momento,
)

MAX_FRASE = 280
MAX_CARTA = 2000


def _frase_del_anio(cliente, anio):
    return (NotaHistoria.objects
            .filter(cliente=cliente, tipo=NotaHistoria.TIPO_FRASE, creada__year=anio)
            .first())


def _cartas(cliente, hoy):
    abiertas, selladas = [], []
    for c in NotaHistoria.objects.filter(cliente=cliente, tipo=NotaHistoria.TIPO_CARTA):
        cifras = c.cifras or {}
        item = {
            'escrita': _fecha_larga(c.creada.date()),
            'abrir_en': _fecha_larga(c.abrir_en) if c.abrir_en else None,
            'cifras': cifras,
        }
        if c.abrir_en and c.abrir_en <= hoy:
            abiertas.append(item | {'texto': c.texto})
        else:
            selladas.append(item)
    return abiertas, selladas


def _volver(cliente, ir=None, edicion=None):
    url = reverse('entrenos:tu_historia', args=[cliente.id])
    if edicion:
        return redirect(f'{url}?edicion={edicion}')
    return redirect(f'{url}?ir={ir}' if ir else url)


@login_required
def tu_historia(request, cliente_id):
    cliente = _obtener_cliente_autorizado(request, cliente_id)
    hoy = date.today()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        texto = (request.POST.get('texto') or '').strip()
        if accion == 'frase' and texto:
            frase = _frase_del_anio(cliente, hoy.year)
            if frase:
                frase.texto = texto[:MAX_FRASE]
                frase.save(update_fields=['texto'])
            else:
                NotaHistoria.objects.create(
                    cliente=cliente, tipo=NotaHistoria.TIPO_FRASE, texto=texto[:MAX_FRASE])
            return _volver(cliente, 'frase')
        if accion == 'carta' and texto:
            h = calcular_historia(cliente, hoy)
            NotaHistoria.objects.create(
                cliente=cliente, tipo=NotaHistoria.TIPO_CARTA, texto=texto[:MAX_CARTA],
                cifras=cifras_del_momento(h) if h else {},
            )
            return _volver(cliente, 'carta')
        if accion == 'congelar':
            h = calcular_historia(cliente, hoy)
            if h and not EdicionHistoria.objects.filter(cliente=cliente, anio=hoy.year).exists():
                frase = _frase_del_anio(cliente, hoy.year)
                EdicionHistoria.objects.create(
                    cliente=cliente, anio=hoy.year,
                    datos=h | {'frase': frase.texto if frase else None},
                )
            return _volver(cliente, edicion=hoy.year)
        return _volver(cliente)

    ediciones = list(EdicionHistoria.objects.filter(cliente=cliente).values_list('anio', 'creada'))
    edicion = request.GET.get('edicion')
    if edicion:
        congelada = EdicionHistoria.objects.filter(cliente=cliente, anio=edicion).first() \
            if edicion.isdigit() else None
        if not congelada:
            raise Http404('Edición no encontrada')
        return render(request, 'entrenos/tu_historia.html', {
            'cliente': cliente,
            'h': congelada.datos,
            'edicion': {'anio': congelada.anio, 'guardada': _fecha_larga(congelada.creada.date())},
            'frase': congelada.datos.get('frase'),
        })

    h = calcular_historia(cliente, hoy)
    frase = _frase_del_anio(cliente, hoy.year)
    abiertas, selladas = _cartas(cliente, hoy)
    return render(request, 'entrenos/tu_historia.html', {
        'cliente': cliente,
        'h': h,
        'frase': frase.texto if frase else None,
        'cartas_abiertas': abiertas,
        'cartas_selladas': selladas,
        'ediciones': [{'anio': a, 'guardada': _fecha_larga(c.date())} for a, c in ediciones],
        'edicion_anio_hoy_guardada': any(a == hoy.year for a, _ in ediciones),
        'anio': hoy.year,
        'ir': request.GET.get('ir', ''),
        'max_frase': MAX_FRASE,
        'max_carta': MAX_CARTA,
    })

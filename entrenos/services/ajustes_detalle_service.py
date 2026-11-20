"""«Ver ajustes»: detalle de los ajustes que el planificador aplica de verdad (20-nov-2026).

Fuente: ``ajustes_volumen`` (lo que consume el planificador), ``revisiones_pendientes`` y
``pausa_subir_volumen``. No define reglas de vigencia ni de reprogramación: cuenta lo que esas
funciones ya deciden. Cada frase sale de un dato registrado; si un dato no consta, se dice o se omite.
"""
from __future__ import annotations

from datetime import date

from django.utils import timezone

NOMBRES_ZONA_PAUSA = {'triceps': 'tríceps', 'trapecios': 'trapecio'}


def _f(d):
    return f'{d:%d/%m}' if d else None


def _lista_es(nombres):
    return nombres[0] if len(nombres) == 1 else ', '.join(nombres[:-1]) + ' y ' + nombres[-1]


def _propuesta_de(cliente, zona, hoy):
    """La propuesta que origina el ajuste de la zona: la aceptada en curso o la última validada."""
    from entrenos.models import PropuestaZonaGym as P

    en_curso = P.objects.filter(cliente=cliente, zona=zona, estado=P.ESTADO_ACEPTADA,
                                inicio__lte=hoy, fin__gte=hoy).order_by('-creada_en').first()
    if en_curso:
        return en_curso
    return P.objects.filter(cliente=cliente, zona=zona, estado=P.ESTADO_EVALUADA,
                            resultado='validada').order_by('-fin').first()


def _medicion_estructurada(cliente, p):
    """Datos de la medicion de una propuesta validada, con sus ventanas reales.

    20-nov-2026: la nota guardada decia «frente a las N semanas anteriores» con N = semanas de
    la propuesta, pero la ventana medida es la de la propuesta (con sus semanas de pausa) y la
    de comparacion tiene la misma duracion justo antes. Si el texto no coincide, se enseñan los
    datos estructurados y la nota antigua pasa al historial. Solo lectura.
    """
    from datetime import timedelta
    from statistics import median

    from entrenos.services.evolucion_muscular_service import comparar_ejercicios
    from entrenos.services.propuesta_zona_service import _filas_dentro_de_la_ventana, _plano

    if not (p.inicio and p.fin):
        return None
    dias = (p.fin - p.inicio).days + 1
    nota = (p.notas_resultado or '')
    if 'semanas anteriores' not in nota or dias == p.semanas * 7:
        return None  # el texto guardado describe bien las ventanas
    objetivo = {_plano(n) for n in p.ejercicios}
    comparables = [e for e in comparar_ejercicios(cliente, p.fin, dias, estricto=True)
                   if e['pct'] is not None and not e['dudoso']]
    filas = [e for e in comparables if _plano(e['ejercicio']) in objetivo] or \
        [e for e in comparables if e.get('zona') == p.zona and not e.get('ligero')]
    filas = _filas_dentro_de_la_ventana(filas, p)
    if not filas:
        return None

    def marca(d):
        peso = f"{d['peso_kg']:g}".replace('.', ',')
        return f"{peso} kg × {d['reps']} ({d['fecha']:%d/%m})"

    return {
        'ventana_actual': f"{_f(p.inicio)}–{_f(p.fin)} ({dias} días)",
        'ventana_anterior': f"{_f(p.inicio - timedelta(days=dias))}–{_f(p.inicio - timedelta(days=1))} ({dias} días)",
        'mediana': f"{round(median(e['pct'] for e in filas), 1):+.1f}".replace('.', ',') + ' %',
        'ejercicios': [{'nombre': e['ejercicio'], 'antes': marca(e['antes']), 'ahora': marca(e['ahora']),
                        'pct': f"{e['pct']:+.1f}".replace('.', ',') + ' %'} for e in filas],
        'nota_antigua': nota.strip(),
    }


def _historial(cliente, p, aplicaciones):
    from entrenos.models import PropuestaZonaGym as P

    ev = []
    if p.creada_en:
        ev.append((timezone.localtime(p.creada_en).date(), 'Propuesta creada por el entrenador.'))
    if p.respondida_en and p.estado != P.ESTADO_PENDIENTE:
        ev.append((timezone.localtime(p.respondida_en).date(), 'Propuesta aceptada.'))
    if p.inicio and p.fin:
        ev.append((p.inicio, f'Inicio de la ventana de evaluación ({_f(p.inicio)}–{_f(p.fin)}).'))
    if aplicaciones:
        ev.append((aplicaciones[0], 'Primera aplicación identificada al reconstruir los registros de sesiones.'))
    if p.evaluada_en:
        res = {'validada': 'validada', 'fallida': 'no funcionó', 'neutra': 'sin conclusión'}.get(p.resultado, '')
        ev.append((timezone.localtime(p.evaluada_en).date(), f'Propuesta evaluada{": " + res if res else ""}.'))
    revision = (p.deteccion or {}).get('revision') or {}
    sin_fecha = []
    if revision.get('fecha'):
        # 20-nov-2026: el evento se fecha cuando se fijo la revision (``fijada_el``); el 06/12 es
        # solo su fecha limite y va en el texto.
        try:
            limite = date.fromisoformat(revision['fecha'])
            texto_limite = f'Revisión fijada: fecha límite el {_f(limite)}.'
            try:
                fijada = date.fromisoformat(revision['fijada_el']) if revision.get('fijada_el') else None
            except ValueError:
                fijada = None
            if fijada:
                ev.append((fijada, texto_limite))
            else:
                sin_fecha.append(('sin fecha', texto_limite + ' No consta el día en que se fijó.'))
        except ValueError:
            pass
    ev.sort(key=lambda x: x[0], reverse=True)
    return [{'fecha': f'{d:%d/%m}', 'texto': t} for d, t in ev] + [{'fecha': f, 'texto': t} for f, t in sin_fecha]


def _vigencia(p, hoy):
    from entrenos.services.volumen_grupo_service import _fecha

    if p.estado == p.ESTADO_ACEPTADA:
        return f'Mientras dure la propuesta aceptada, hasta el {_f(p.fin)}.'
    revision = (p.deteccion or {}).get('revision') or {}
    estado = revision.get('estado') or 'pendiente'
    limite = _fecha(revision.get('hasta')) if estado == 'prolongada' else _fecha(revision.get('fecha'))
    if estado == 'prolongada' and limite:
        return f'Prolongado por ti hasta el {_f(limite)}.'
    if limite:
        from datetime import timedelta
        return (f'Se aplica hasta el {_f(limite)} inclusive; revisión como máximo ese día. Sin decisión, '
                f'deja de aplicarse el {_f(limite + timedelta(days=1))}.')
    return None


def detalle_ajustes(cliente, hoy) -> list[dict]:
    from entrenos.services.propuesta_zona_service import pausa_subir_volumen, sesiones_con_ajuste_registrado
    from entrenos.services.volumen_grupo_service import ajustes_volumen, revisiones_pendientes

    tarjetas = []
    for zona, item in sorted(ajustes_volumen(cliente, hoy).items()):
        if not item.get('series'):
            continue
        p = _propuesta_de(cliente, zona, hoy)
        nombre = p.nombre_zona if p else zona.title()
        tarjeta = {
            'tipo': 'series',
            'titulo': f"{nombre} · {item['series']:+d} series por semana",
            'alcance': (f"Se {'suman' if item['series'] > 0 else 'restan'} {abs(item['series'])} series semanales "
                        f"al trabajo de {nombre.lower()}, repartidas por el planificador entre las sesiones de la semana."),
            'motivo': None, 'aplicacion': None, 'sabe': None, 'vigencia': None, 'historial': [],
        }
        if p:
            tarjeta['motivo'] = (p.notas_resultado or '').strip() or None
            medicion = _medicion_estructurada(cliente, p) if p.estado == p.ESTADO_EVALUADA else None
            if medicion:
                tarjeta['motivo'] = None
                tarjeta['medicion'] = medicion
            apl = sesiones_con_ajuste_registrado(cliente, p) if p.inicio and p.fin else []
            if apl:
                tarjeta['aplicacion'] = (f"Ajuste registrado en {len(apl)} sesiones, del {_f(apl[0])} al {_f(apl[-1])}.")
            else:
                tarjeta['aplicacion'] = 'No consta en las sesiones que el ajuste llegara a aplicarse.'
            if p.estado == p.ESTADO_EVALUADA and p.resultado == 'validada':
                tarjeta['sabe'] = ('La mejora observada todavía no permite atribuir el resultado a las '
                                   'series adicionales.')
            tarjeta['vigencia'] = _vigencia(p, hoy)
            tarjeta['historial'] = _historial(cliente, p, apl)
            if tarjeta.get('medicion'):
                tarjeta['historial'].append({
                    'fecha': f"{timezone.localtime(p.evaluada_en).date():%d/%m}" if p.evaluada_en else '',
                    'texto': 'Nota original conservada (describe «semanas anteriores» sin dar las ventanas): '
                             + tarjeta['medicion']['nota_antigua'],
                })
                fechados = [h for h in tarjeta['historial'] if h['fecha'][:1].isdigit()]
                sin_fechar = [h for h in tarjeta['historial'] if not h['fecha'][:1].isdigit()]
                fechados.sort(key=lambda h: (h['fecha'][3:], h['fecha'][:2]), reverse=True)
                tarjeta['historial'] = fechados + sin_fechar
        else:
            tarjeta['motivo'] = '; '.join(item['motivos']).capitalize() + '.'
        tarjetas.append(tarjeta)
    for r in revisiones_pendientes(cliente, hoy):
        tarjetas.append({
            'tipo': 'revision',
            'titulo': f"{r['nombre_zona']} · decidir si siguen las {abs(r['series'])} series",
            'alcance': 'El ajuste ya no se aplica.',
            'motivo': None, 'aplicacion': None, 'sabe': None,
            'vigencia': f"Valía hasta el {_f(r['limite'])}. No se prolonga sin una decisión tuya.",
            'historial': [],
        })
    pausa = pausa_subir_volumen(cliente, hoy)
    if pausa:
        nombres = _lista_es([NOMBRES_ZONA_PAUSA.get(z, z) for z in pausa['zonas']])
        tarjetas.append({
            'tipo': 'pausa',
            'titulo': f'{nombres[0].upper()}{nombres[1:]} · aumento de series en pausa',
            'alcance': ('Está pausada la propuesta de aumentar series en estos músculos. '
                        'Peso y repeticiones siguen su progresión normal.'),
            'motivo': None, 'aplicacion': None, 'sabe': None,
            'vigencia': f"Pausa hasta el {_f(pausa['fin_previsto'])}, en el bloque {pausa['bloque']}.",
            'historial': [],
        })
    return tarjetas

"""Sensaciones por zona al cierre (24-oct-2026, paso 3 del informe).

Lo que hace RP Hypertrophy con el volumen, a la manera de esta app: tres
botones por zona trabajada (bombeo, agujetas de la vez anterior, molestia
articular) y dos reglas que se pueden citar con el dato:

- Molestia articular o agujetas fuertes en 2+ sesiones de la misma zona en
  14 días → propuesta de bajar 2 series semanales en esa zona.
- Si la última respuesta de una zona fue molestia o agujetas fuertes, no se
  propone subirle volumen aunque retroceda.
"""

from datetime import timedelta

CAMPOS = ('bombeo', 'agujetas', 'molestia')
OPCIONES = {
    'bombeo': ('Poco', 'Bien', 'Mucho'),
    'agujetas': ('Ninguna', 'Leves', 'Fuertes'),
    'molestia': ('No', 'Leve', 'Sí'),
}
PREGUNTAS = {
    'bombeo': 'Bombeo hoy',
    'agujetas': 'Agujetas de la vez anterior',
    'molestia': 'Molestia articular',
}
VENTANA_DIAS = 14
MIN_SESIONES = 2


def zonas_de_entreno(entreno):
    """[(zona, nombre)] de las zonas trabajadas en la sesión, en orden de aparición."""
    from entrenos.services.evolucion_muscular_service import NOMBRES_ZONA, normalizar_zona

    vistas = []
    for ej in entreno.ejercicios_realizados.filter(completado=True).order_by('orden', 'id'):
        zona = normalizar_zona(getattr(ej, 'grupo_muscular', None), ej.nombre_ejercicio)
        if zona and zona not in [z for z, _ in vistas]:
            vistas.append((zona, NOMBRES_ZONA.get(zona, zona.title())))
    return vistas


def contexto_cierre(entreno):
    """Lo que necesita la plantilla del cierre: una fila por zona con sus respuestas."""
    from entrenos.models import SensacionZonaGym

    guardadas = {s.zona: s for s in SensacionZonaGym.objects.filter(entreno=entreno)}
    filas = []
    for zona, nombre in zonas_de_entreno(entreno):
        s = guardadas.get(zona)
        filas.append({
            'zona': zona,
            'nombre': nombre,
            'preguntas': [
                {'campo': c, 'texto': PREGUNTAS[c], 'opciones': list(enumerate(OPCIONES[c])),
                 'valor': getattr(s, c, None) if s else None}
                for c in CAMPOS
            ],
        })
    return filas


def guardar(cliente, entreno, zona, campo, valor):
    from entrenos.models import SensacionZonaGym

    if campo not in CAMPOS or valor not in (0, 1, 2):
        raise ValueError('respuesta no válida')
    if zona not in [z for z, _ in zonas_de_entreno(entreno)]:
        raise ValueError('zona no trabajada en esta sesión')
    s, _ = SensacionZonaGym.objects.get_or_create(cliente=cliente, entreno=entreno, zona=zona)
    setattr(s, campo, valor)
    s.save()
    return s


def _malas(cliente, zona, hoy):
    from entrenos.models import SensacionZonaGym

    return [
        s for s in SensacionZonaGym.objects.filter(
            cliente=cliente, zona=zona,
            entreno__fecha__gte=hoy - timedelta(days=VENTANA_DIAS), entreno__fecha__lte=hoy,
        ).select_related('entreno')
        if (s.molestia or 0) >= 1 or (s.agujetas or 0) >= 2
    ]


def zona_para_bajar(cliente, hoy):
    """{'zona', 'nombre_zona', 'sesiones', 'fechas'} si una zona acumula malas sensaciones, o None."""
    from entrenos.models import SensacionZonaGym
    from entrenos.services.evolucion_muscular_service import NOMBRES_ZONA

    zonas = set(SensacionZonaGym.objects.filter(
        cliente=cliente, entreno__fecha__gte=hoy - timedelta(days=VENTANA_DIAS),
    ).values_list('zona', flat=True))
    candidatas = []
    for zona in zonas:
        malas = _malas(cliente, zona, hoy)
        if len(malas) >= MIN_SESIONES:
            candidatas.append((len(malas), zona, sorted(s.entreno.fecha for s in malas)))
    if not candidatas:
        return None
    n, zona, fechas = max(candidatas)
    return {'zona': zona, 'nombre_zona': NOMBRES_ZONA.get(zona, zona.title()),
            'sesiones': n, 'fechas': fechas}


def frena_subir(cliente, zona, hoy):
    """True si la última respuesta de esa zona (14 días) fue molestia o agujetas fuertes."""
    from entrenos.models import SensacionZonaGym

    ultima = SensacionZonaGym.objects.filter(
        cliente=cliente, zona=zona, entreno__fecha__gte=hoy - timedelta(days=VENTANA_DIAS),
    ).order_by('-entreno__fecha', '-id').first()
    return bool(ultima and ((ultima.molestia or 0) >= 1 or (ultima.agujetas or 0) >= 2))

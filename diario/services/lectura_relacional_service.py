"""Lectura relacional determinista basada exclusivamente en registros de Simbiosis."""
from collections import Counter
import re

from diario.models import Interaccion, PersonaImportante


UMBRAL_PATRONES = 3
_STOPWORDS = {
    'para', 'pero', 'porque', 'como', 'con', 'del', 'desde', 'donde', 'el', 'ella',
    'ellos', 'entre', 'era', 'esta', 'este', 'esto', 'fue', 'las', 'los', 'más', 'muy',
    'por', 'que', 'sin', 'sobre', 'sus', 'una', 'uno', 'unos', 'unas', 'y', 'ya', 'yo',
    'nos', 'me', 'mi', 'mis', 'se', 'su', 'al', 'le', 'lo', 'un', 'es', 'en', 'de', 'la',
}


def _resolver_raiz(persona):
    visitadas = set()
    actual = persona
    while actual.fusionada_en_id:
        if actual.pk in visitadas:
            break
        visitadas.add(actual.pk)
        actual = actual.fusionada_en
    return actual


def _descendientes(raiz):
    encontrados = []
    frontera = [raiz.pk]
    while frontera:
        nivel = list(PersonaImportante.objects.filter(fusionada_en_id__in=frontera).order_by('nombre', 'pk'))
        encontrados.extend(nivel)
        frontera = [persona.pk for persona in nivel]
    return encontrados


def _temas_transparentes(interacciones):
    palabras = Counter()
    for item in interacciones:
        texto = ' '.join((item.titulo, item.descripcion, item.mi_sentir, item.aprendizaje)).casefold()
        palabras.update(
            palabra for palabra in re.findall(r"[a-záéíóúüñ]{4,}", texto)
            if palabra not in _STOPWORDS
        )
    return [
        {'palabra': palabra, 'apariciones': cantidad}
        for palabra, cantidad in sorted(palabras.items(), key=lambda par: (-par[1], par[0]))[:5]
        if cantidad >= 2
    ]


def construir_lectura_relacional(persona, *, usuario):
    """Devuelve hechos exactos y observaciones acotadas; nunca interpreta causas."""
    persona = PersonaImportante.objects.select_related('fusionada_en').get(
        pk=persona.pk, usuario=usuario,
    )
    raiz = _resolver_raiz(persona)
    absorbidas = _descendientes(raiz)
    identidades = [raiz, *absorbidas]
    interacciones = Interaccion.objects.filter(
        usuario=usuario, personas__in=identidades,
    ).distinct().order_by('-fecha', '-pk')
    muestra = interacciones.count()
    fechas = list(interacciones.values_list('fecha', flat=True))
    tipos = dict(Counter(interacciones.values_list('tipo_interaccion', flat=True)))
    insuficientes = muestra < UMBRAL_PATRONES
    if insuficientes:
        texto = f'Aún no hay muestra suficiente: {muestra} de {UMBRAL_PATRONES} interacciones registradas.'
        temas = []
    else:
        tipo_frecuente, frecuencia = sorted(tipos.items(), key=lambda par: (-par[1], par[0]))[0]
        texto = (
            f'En esta muestra de {muestra} registros, el tipo “{tipo_frecuente}” '
            f'aparece {frecuencia} veces. Es una observación del historial, no una explicación.'
        )
        temas = _temas_transparentes(interacciones)
    return {
        'persona_raiz': raiz,
        'identidades_absorbidas': absorbidas,
        'interacciones': interacciones,
        'hechos': {
            'total_interacciones': muestra,
            'primera_fecha': min(fechas) if fechas else None,
            'ultima_fecha': max(fechas) if fechas else None,
            'tipos': tipos,
        },
        'patrones': {
            'datos_insuficientes': insuficientes,
            'muestra': muestra,
            'umbral': UMBRAL_PATRONES,
            'texto': texto,
        },
        'temas': temas,
    }

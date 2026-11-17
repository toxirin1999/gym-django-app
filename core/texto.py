"""Utilidades de texto compartidas (17-nov-2026)."""

import unicodedata


def plegar(texto):
    """Minúsculas y sin tildes: compara nombres como ``iexact``/``icontains`` en MySQL."""
    descompuesto = unicodedata.normalize('NFKD', (texto or '').casefold())
    return ''.join(c for c in descompuesto if not unicodedata.combining(c))

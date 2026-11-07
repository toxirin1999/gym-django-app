"""Módulos archivados y Hyrox oculto (7-nov-2026).

Decisión de David: Vida/diario, logros, estoico, nutrición y la habitación de
JOI se archivan, y Hyrox queda oculto. Archivar no es borrar: el código, las URLs
y los datos siguen donde estaban. Lo que cambia es que la app del entrenador
(Ahora, Rutina, Plan, Memoria, Cuerpo) deja de enlazarlos y de mandarte a ellos.

Se mantiene, aunque viva en esas apps:
- Strava (hyrox/strava/...): conexión, webhook, reconciliación y el aviso del
  briefing.
- Lesiones y recuperación (hyrox/lesiones, registrar-recuperacion,
  test-recuperacion): el entrenador de fuerza filtra ejercicios con ellas.
- Las señales que alimentan el plan (modelos, signals y servicios).
"""

from django.conf import settings


def archivado(nombre):
    """True si el módulo ``nombre`` está archivado (ver settings.MODULOS_ARCHIVADOS)."""
    return nombre in getattr(settings, 'MODULOS_ARCHIVADOS', ())


def hyrox_oculto():
    """Hyrox fuera de la app del entrenador. «Oculto» y no «congelado»: sus
    tareas y señales siguen activas (ver la lista de pendientes del 7-nov)."""
    return bool(getattr(settings, 'HYROX_OCULTO', False))

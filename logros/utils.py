# logros/vendor.py
from .models import (
    PerfilGamificacion, Arquetipo, PruebaLegendaria, PruebaUsuario,
    Quest, QuestUsuario, HistorialPuntos, Notificacion
)


def obtener_datos_logros(cliente):
    # Obtener el perfil de gamificación del cliente
    perfil = PerfilGamificacion.objects.filter(cliente=cliente).select_related('nivel_actual').first()

    # Si el cliente no tiene perfil, devolvemos un diccionario vacío o con valores por defecto
    if not perfil:
        return {
            "perfil": None,
            "logros_completados": [],
            "logros_progreso": [],
            "puntos_totales": 0,
            "nivel_actual": None,
            "racha_actual": 0,
            "racha_maxima": 0,
            "total_logros": 0,
        }

    # --- INICIO DE LA CORRECCIÓN ---
    # Usamos el modelo correcto: PruebaUsuario
    logros_completados = PruebaUsuario.objects.filter(
        perfil=perfil,
        completada=True
    ).select_related('prueba', 'prueba__arquetipo')  # Optimizamos la consulta

    # Para los logros en progreso, buscamos las pruebas que NO están completadas
    logros_progreso = PruebaUsuario.objects.filter(
        perfil=perfil,
        completada=False
    ).select_related('prueba', 'prueba__arquetipo')
    # --- FIN DE LA CORRECCIÓN ---

    # El resto de la lógica usa los datos del perfil, que ya son correctos
    puntos_totales = perfil.puntos_totales
    nivel_actual = perfil.nivel_actual
    racha_actual = perfil.racha_actual
    racha_maxima = perfil.racha_maxima

    return {
        "perfil": perfil,
        "logros_completados": logros_completados,
        "logros_progreso": logros_progreso,
        "puntos_totales": puntos_totales,
        "nivel_actual": nivel_actual,
        "racha_actual": racha_actual,
        "racha_maxima": racha_maxima,
        "total_logros": logros_completados.count(),
    }

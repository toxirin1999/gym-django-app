from django.apps import AppConfig
import logging


class LogrosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logros'
    verbose_name = 'Sistema de Logros y Gamificación'

    def ready(self):
        """Registra el arranque del sistema; el cierre es explícito."""
        try:
            logger = logging.getLogger('gamificacion')
            logger.info("🚀 Sistema de gamificación iniciado correctamente")

        except Exception as e:
            logger.error(f"Error inicializando sistema de gamificación: {e}")

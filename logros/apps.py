from django.apps import AppConfig
import logging


class LogrosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logros'
    verbose_name = 'Sistema de Logros y Gamificación'

    def ready(self):
        """
        Se ejecuta cuando la app está lista.
        Aquí registramos los signals automáticamente.
        """
        try:
            # Importar signals para registrarlos automáticamente
            import logros.services

            # Configurar logger
            logger = logging.getLogger('gamificacion')
            logger.info("🚀 Sistema de gamificación iniciado correctamente")
            logger.info("✅ Signals automáticos registrados")

            print("🎮 Sistema de gamificación listo - Signals automáticos activos")

        except ImportError as e:
            print(f"❌ Error importando signals de gamificación: {e}")

        except Exception as e:
            print(f"❌ Error inicializando sistema de gamificación: {e}")

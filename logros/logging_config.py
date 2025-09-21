import logging
import os
from django.conf import settings


def setup_gamification_logging():
    """
    Configura logging específico para gamificación
    """
    # Crear directorio de logs si no existe
    log_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Configurar logger para gamificación
    logger = logging.getLogger('gamificacion')
    logger.setLevel(logging.INFO)

    # Handler para archivo
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'gamificacion.log')
    )
    file_handler.setLevel(logging.INFO)

    # Formato de logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)

    # Agregar handler si no existe
    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger


# Instancia global del logger
gamification_logger = setup_gamification_logging()

# vendor/monitoring.py
import logging
import time
from functools import wraps
from django.conf import settings

logger = logging.getLogger('helms_integration')


def monitor_performance(func_name):
    """Decorator para monitorear rendimiento"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
                raise
            finally:
                end_time = time.time()
                duration = end_time - start_time

                logger.info(f"{func_name} - Success: {success}, Duration: {duration:.2f}s, Error: {error}")

            return result

        return wrapper

    return decorator

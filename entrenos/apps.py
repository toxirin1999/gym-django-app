from django.apps import AppConfig


class EntrenosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'entrenos'

    def ready(self):
        import entrenos.signals

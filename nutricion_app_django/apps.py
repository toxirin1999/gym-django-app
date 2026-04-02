from django.apps import AppConfig


class NutricionAppDjangoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nutricion_app_django'

    def ready(self):
        import nutricion_app_django.signals  # noqa: F401

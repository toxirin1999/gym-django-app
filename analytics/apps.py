from django.apps import AppConfig

class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'Centro de Análisis'
    
    def ready(self):
        # Importar señales si las hay
        import analytics.signals
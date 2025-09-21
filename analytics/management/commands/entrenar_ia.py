# En analytics/management/commands/entrenar_ia.py
from django.core.management.base import BaseCommand
from analytics.ia_modelos_predictivos import ModelosPredictivosIA
from clientes.models import Cliente


class Command(BaseCommand):
    help = 'Entrena modelos de IA para todos los clientes'

    def handle(self, *args, **options):  # ← debe estar indentado dentro de la clase
        clientes = Cliente.objects.all()

        for cliente in clientes:
            self.stdout.write(f'Entrenando IA para {cliente.nombre}...')
            modelos_ia = ModelosPredictivosIA(cliente)
            resultados = modelos_ia.entrenar_modelos_rendimiento()
            self.stdout.write(
                self.style.SUCCESS(f'✅ IA entrenada para {cliente.nombre}')
            )

from django.core.management.base import BaseCommand
from analytics.models import RecomendacionEntrenamiento
from clientes.models import Cliente
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verifica las recomendaciones existentes para un cliente'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int, help='ID del cliente')

    def handle(self, *args, **options):
        cliente_id = options['cliente_id']
        
        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Cliente con ID {cliente_id} no existe'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n=== RECOMENDACIONES EXISTENTES ==='))
        self.stdout.write(f'Cliente: {cliente.nombre} (ID: {cliente.id})\n')

        # Todas las recomendaciones
        todas = RecomendacionEntrenamiento.objects.filter(cliente=cliente)
        self.stdout.write(f'Total de recomendaciones en BD: {todas.count()}\n')

        if todas.exists():
            for rec in todas:
                estado = "APLICADA" if rec.aplicada else "ACTIVA" if rec.expires_at > timezone.now() else "EXPIRADA"
                self.stdout.write(f'\n  ID: {rec.id}')
                self.stdout.write(f'  Título: {rec.titulo}')
                self.stdout.write(f'  Tipo: {rec.tipo}')
                self.stdout.write(f'  Estado: {estado}')
                self.stdout.write(f'  Aplicada: {rec.aplicada}')
                self.stdout.write(f'  Expira: {rec.expires_at}')
                self.stdout.write(f'  Creada: {rec.created_at}')

        # Recomendaciones activas (las que deberían mostrarse)
        activas = RecomendacionEntrenamiento.objects.filter(
            cliente=cliente,
            expires_at__gt=timezone.now(),
            aplicada=False
        )
        self.stdout.write(self.style.WARNING(f'\n\nRecomendaciones ACTIVAS (visibles): {activas.count()}'))

        # Recomendaciones aplicadas recientes
        from datetime import timedelta
        aplicadas = RecomendacionEntrenamiento.objects.filter(
            cliente=cliente,
            aplicada=True,
            fecha_aplicacion__gte=timezone.now() - timedelta(days=30)
        )
        self.stdout.write(self.style.WARNING(f'Recomendaciones APLICADAS (últimos 30 días): {aplicadas.count()}'))

        self.stdout.write(self.style.SUCCESS(f'\n=== FIN ===\n'))

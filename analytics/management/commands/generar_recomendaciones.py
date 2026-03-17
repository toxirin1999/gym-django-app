from django.core.management.base import BaseCommand
from clientes.models import Cliente
from analytics.views import CalculadoraEjerciciosTabla
from analytics.models import RecomendacionEntrenamiento
from datetime import timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Fuerza la generación de recomendaciones para un cliente'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int, help='ID del cliente')

    def handle(self, *args, **options):
        cliente_id = options['cliente_id']
        
        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Cliente con ID {cliente_id} no existe'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n=== GENERANDO RECOMENDACIONES ==='))
        self.stdout.write(f'Cliente: {cliente.nombre} (ID: {cliente.id})\n')

        PRIORIDADES = {'alta': 1, 'media': 2, 'baja': 3}
        calculadora = CalculadoraEjerciciosTabla(cliente)
        creadas = 0
        actualizadas = 0

        # --- Lógica de Consistencia ---
        fecha_inicio_consistencia = timezone.now().date() - timedelta(days=30)
        self.stdout.write(f'1. Analizando consistencia (desde {fecha_inicio_consistencia})...')
        
        ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio=fecha_inicio_consistencia)
        
        if ejercicios:
            completados = len([e for e in ejercicios if e.get('completado', False)])
            consistencia = (completados / len(ejercicios)) * 100 if len(ejercicios) > 0 else 0
            
            self.stdout.write(f'   Consistencia: {consistencia:.1f}%')

            if consistencia < 70:
                titulo_rec = 'Mejorar Consistencia'
                desc_rec = f'Tu consistencia actual es del {consistencia:.1f}%. Intenta completar todos los ejercicios de tus rutinas.'

                obj, created = RecomendacionEntrenamiento.objects.update_or_create(
                    cliente=cliente,
                    tipo='consistencia',
                    titulo=titulo_rec,
                    descripcion=desc_rec,
                    defaults={
                        'prioridad': PRIORIDADES['alta'],
                        'expires_at': timezone.now() + timedelta(days=14),
                        'aplicada': False,
                    }
                )
                if created:
                    creadas += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Recomendación CREADA (ID: {obj.id})'))
                else:
                    actualizadas += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Recomendación ACTUALIZADA (ID: {obj.id})'))
            else:
                self.stdout.write(f'   ❌ No se genera (consistencia >= 70%)')

        # --- Lógica de Ejercicios Estancados ---
        self.stdout.write(f'\n2. Analizando progresión...')
        progresiones = calculadora.obtener_ejercicios_progresion(limite=None)
        
        if progresiones:
            estancados = [p['nombre_ejercicio'] for p in progresiones if p['progresion_peso'] < 5]
            self.stdout.write(f'   Ejercicios estancados: {len(estancados)}')

            if estancados:
                titulo_rec = 'Ejercicios Estancados Detectados'
                desc_rec = f'Los siguientes ejercicios muestran poca progresión: {", ".join(sorted(estancados)[:3])}. Considera variar la rutina o la intensidad.'

                try:
                    obj, created = RecomendacionEntrenamiento.objects.update_or_create(
                        cliente=cliente,
                        tipo='progresion',
                        titulo=titulo_rec,
                        descripcion=desc_rec,
                        defaults={
                            'prioridad': PRIORIDADES['media'],
                            'expires_at': timezone.now() + timedelta(days=30),
                            'aplicada': False,
                        }
                    )
                    if created:
                        creadas += 1
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Recomendación CREADA (ID: {obj.id})'))
                    else:
                        actualizadas += 1
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Recomendación ACTUALIZADA (ID: {obj.id})'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ ERROR: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\n=== RESUMEN ==='))
        self.stdout.write(f'Recomendaciones creadas: {creadas}')
        self.stdout.write(f'Recomendaciones actualizadas: {actualizadas}')
        self.stdout.write(self.style.SUCCESS(f'=== FIN ===\n'))

from django.core.management.base import BaseCommand
from clientes.models import Cliente
from entrenos.models import EjercicioRealizado
from analytics.views import CalculadoraEjerciciosTabla
from datetime import timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Diagnostica por qué no se generan recomendaciones para un cliente'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int, help='ID del cliente')

    def handle(self, *args, **options):
        cliente_id = options['cliente_id']
        
        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Cliente con ID {cliente_id} no existe'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n=== DIAGNÓSTICO DE RECOMENDACIONES ==='))
        self.stdout.write(f'Cliente: {cliente.nombre} (ID: {cliente.id})\n')

        # 1. Verificar ejercicios en los últimos 30 días
        fecha_inicio = timezone.now().date() - timedelta(days=30)
        self.stdout.write(self.style.WARNING(f'1. ANÁLISIS DE CONSISTENCIA'))
        self.stdout.write(f'   Fecha inicio: {fecha_inicio}')
        
        calculadora = CalculadoraEjerciciosTabla(cliente)
        ejercicios = calculadora.obtener_ejercicios_tabla(fecha_inicio=fecha_inicio)
        
        self.stdout.write(f'   Ejercicios obtenidos: {len(ejercicios) if ejercicios else 0}')
        
        if ejercicios:
            completados = len([e for e in ejercicios if e.get('completado', False)])
            consistencia = (completados / len(ejercicios)) * 100 if len(ejercicios) > 0 else 0
            
            self.stdout.write(f'   Ejercicios completados: {completados}/{len(ejercicios)}')
            self.stdout.write(f'   Consistencia: {consistencia:.1f}%')
            self.stdout.write(f'   ¿Genera recomendación? {consistencia < 70}')
            
            if consistencia < 70:
                self.stdout.write(self.style.SUCCESS(f'   ✅ SÍ generaría recomendación de consistencia'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ NO genera recomendación (consistencia >= 70%)'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ NO hay ejercicios en los últimos 30 días'))

        # 2. Verificar progresión
        self.stdout.write(self.style.WARNING(f'\n2. ANÁLISIS DE PROGRESIÓN'))
        progresiones = calculadora.obtener_ejercicios_progresion(limite=None)
        self.stdout.write(f'   Progresiones obtenidas: {len(progresiones) if progresiones else 0}')
        
        if progresiones:
            estancados = [p['nombre_ejercicio'] for p in progresiones if p['progresion_peso'] < 5]
            self.stdout.write(f'   Ejercicios estancados (progresión < 5%): {len(estancados)}')
            
            if estancados:
                self.stdout.write(f'   Ejercicios: {", ".join(estancados[:5])}')
                self.stdout.write(self.style.SUCCESS(f'   ✅ SÍ generaría recomendación de estancamiento'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ NO genera recomendación (no hay ejercicios estancados)'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ NO hay datos de progresión'))

        self.stdout.write(self.style.SUCCESS(f'\n=== FIN DEL DIAGNÓSTICO ===\n'))

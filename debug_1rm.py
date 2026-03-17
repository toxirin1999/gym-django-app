import os
import django
import sys

# Setup Django environment
sys.path.append('c:\\Users\\kure_\\Desktop\\app3\\app\\a\\gymproject')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from analytics.views import CalculadoraEjerciciosTabla
from clientes.models import Cliente
from rutinas.models import EjercicioRealizado
from django.db.models import Max, F

def debug_1rm():
    # Get the first client (or specific one if known, assuming current user context)
    # Since I don't have request.user here, I'll grab the first client or one with data
    cliente = Cliente.objects.first()
    print(f"Analyzing data for client: {cliente.nombre} (ID: {cliente.id})")

    calc = CalculadoraEjerciciosTabla(cliente)
    
    # Check Sentadilla specifically
    ejercicio_nombre = "Sentadilla"
    print(f"\n--- Debugging {ejercicio_nombre} ---")
    
    # 1. Run the actual calculation method
    maximos = calc.calcular_1rm_estimado_por_ejercicio()
    print(f"Calculated 1RM: {maximos.get(ejercicio_nombre)}")
    
    # 2. Inspect raw data
    # Logic in CalculadoraEjerciciosTabla usually filters by name
    logs = EjercicioRealizado.objects.filter(
        entreno__cliente=cliente,
        ejercicio__nombre__icontains=ejercicio_nombre
    ).order_by('-entreno__fecha')[:10]
    
    print(f"\nLast 10 {ejercicio_nombre} logs:")
    for log in logs:
        # Calculate 1RM for this specific log: Weight * (1 + Reps/30)
        # Assuming simple Epley
        est_1rm = 0
        if log.peso and log.series:
            # Assuming 'series' contains reps info or log has reps field. 
            # Checking model structure might be needed, but usually it's log.peso and log.reps
            # Let's check attributes available
            try:
                reps = log.reps 
                peso = log.peso
                est_1rm = peso * (1 + reps/30)
                print(f"Date: {log.entreno.fecha}, Weight: {peso}, Reps: {reps}, Est 1RM: {est_1rm:.2f}")
            except AttributeError:
                 print(f"Date: {log.entreno.fecha} - Could not retrieve weight/reps attributes directly. Log dict: {log.__dict__}")

if __name__ == '__main__':
    debug_1rm()

from analytics.views import CalculadoraEjerciciosTabla
from clientes.models import Cliente
from entrenos.models import EjercicioRealizado

# Check client ID 2
cliente = Cliente.objects.get(id=2)
print(f"Debug Client: {cliente.nombre} (ID: {cliente.id})")

calc = CalculadoraEjerciciosTabla(cliente)
# Trigger calculation to see debug prints
_ = calc.calcular_1rm_estimado_por_ejercicio()
all_exercises = calc.obtener_ejercicios_tabla()
print(f"Total exercises fetched: {len(all_exercises)}")

# Calculate again to get maximos
maximos = calc.calcular_1rm_estimado_por_ejercicio()

with open('debug_out.txt', 'w', encoding='utf-8') as f:
    f.write(f"FINAL MAXIMOS: {maximos}\n")
    for e in all_exercises:
        name = e['nombre'].strip().title()
        peso = float(e.get('peso', 0))
        reps = int(e.get('repeticiones', 0))
        est_1rm = peso * (1 + (reps / 30))
        
        if peso > 150 or est_1rm > 200:
            f.write(f"HEAVY LIFT - {name} | Date: {e.get('fecha')} | Weight: {peso} | Reps: {reps} | Est 1RM: {est_1rm:.2f} | ID: {e.get('entreno_id')}\n")

exit()

calc = CalculadoraEjerciciosTabla(cliente)
maximos = calc.calcular_1rm_estimado_por_ejercicio()

with open('debug_out.txt', 'w', encoding='utf-8') as f:
    f.write(f"Calculated 1RM Data: {maximos}\n")
    f.write("\n--- Inspecting CalculadoraEjerciciosTabla Data ---\n")
    all_exercises = calc.obtener_ejercicios_tabla()
    f.write(f"Total exercises fetched: {len(all_exercises)}\n")

    for e in all_exercises:
        name = e['nombre'].strip().title()
        if "Sentadilla" in name or "Peso Muerto" in name:
            peso = float(e.get('peso', 0))
            reps = int(e.get('repeticiones', 0))
            est_1rm = peso * (1 + (reps / 30))
            f.write(f"REC - {name} | Date: {e.get('fecha')} | Weight: {peso} | Reps: {reps} | Est 1RM: {est_1rm:.2f} | ID: {e.get('entreno_id')}\n")
            
    f.write("\nDONE\n")

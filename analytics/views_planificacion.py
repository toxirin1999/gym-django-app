from django.shortcuts import render, get_object_or_404
from entrenos.models import Cliente, EjercicioRealizado

# Ejemplo simple de ejercicios por grupo muscular
EJERCICIOS_BASE = {
    'Pecho': 'Press Banca',
    'Espalda': 'Remo con barra',
    'Piernas': 'Sentadilla',
    'Hombros': 'Press militar mancuerna',
}


def vista_plan_optimo(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    intensidad_base = 78  # semana 1
    incremento_por_semana = 1  # +1% por semana
    reps = 10
    series = 4
    frecuencia = 4
    semanas_totales = 12

    plan_12_semanas = []

    for semana in range(1, semanas_totales + 1):
        intensidad_actual = intensidad_base + (semana - 1) * incremento_por_semana
        plan_semanal = []

        for i, (grupo, ejercicio) in enumerate(EJERCICIOS_BASE.items(), start=1):
            ejercicios_cliente = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente,
                nombre_ejercicio__icontains=ejercicio
            )

            pesos = [e.peso_kg for e in ejercicios_cliente if e.peso_kg]
            reps_ej = [e.repeticiones for e in ejercicios_cliente if e.repeticiones]

            if pesos and reps_ej:
                promedio_1rm = sum([estimar_1rm(p, r) for p, r in zip(pesos, reps_ej)]) / len(pesos)
            else:
                promedio_1rm = 100

            peso_estimado = round((intensidad_actual / 100) * promedio_1rm)
            volumen = peso_estimado * reps * series

            plan_semanal.append({
                'dia': i,
                'grupo': grupo,
                'ejercicio': ejercicio,
                'series_reps': f"{series}×{reps}",
                'peso': f"{peso_estimado} kg",
                'volumen': f"{volumen} kg"
            })

        plan_12_semanas.append({
            'semana': semana,
            'intensidad': intensidad_actual,
            'frecuencia': frecuencia,
            'plan': plan_semanal
        })

    return render(request, 'analytics/plan_optimo.html', {
        'cliente': cliente,
        'plan_12_semanas': plan_12_semanas
    })


def estimar_1rm(peso, repeticiones):
    return peso * (1 + repeticiones / 30)

from entrenos.models import SesionEntrenamiento
total = SesionEntrenamiento.objects.count()
con_rpe = SesionEntrenamiento.objects.filter(rpe_medio__isnull=False).count()
print(f"Sesiones totales: {total}")
print(f"Sesiones con RPE: {con_rpe}")

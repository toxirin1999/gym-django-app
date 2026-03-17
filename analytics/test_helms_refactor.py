# test_helms_refactor.py
"""
Script de verificación simple para comprobar que el refactor funciona correctamente.
"""

import sys
import os
from datetime import date

# Asegurar que el directorio actual está en el path
try:
    if __package__:
        from .planificador_helms_completo import PlanificadorHelms, PerfilCliente, generar_plan_helms
    else:
        from planificador_helms_completo import PlanificadorHelms, PerfilCliente, generar_plan_helms
    print("[SUCCESS] Importacion exitosa desde el wrapper legacy.")
except Exception as e:
    print(f"[ERROR] Error al importar desde el wrapper: {e}")
    # Si falla la relativa, intentamos absoluta para fallback
    try:
        from analytics.planificador_helms_completo import PlanificadorHelms, PerfilCliente, generar_plan_helms
        print("[SUCCESS] Fallback a importacion absoluta exitoso.")
    except Exception as e2:
        print(f"[ERROR] Fallback fallido: {e2}")
        sys.exit(1)

# Datos de prueba
cliente_test = {
    'id': 1,
    'nombre': 'Usuario Test',
    'experiencia_años': 2,
    'objetivo_principal': 'hipertrofia',
    'dias_disponibles': 4,
    'nivel_estres': 3,
    'calidad_sueño': 8,
    'nivel_energia': 7,
    'ejercicios_evitar': ['Peso Muerto Convencional']
}

def test_legacy_wrapper():
    print("\nProbando wrapper legacy...")
    try:
        plan = generar_plan_helms(cliente_test)
        print(f"[SUCCESS] Plan anual generado con exito ({len(plan['entrenos_por_fecha'])} entrenamientos)")
        
        # Verificar un dia aleatorio
        primer_dia = list(plan['entrenos_por_fecha'].keys())[0]
        print(f"[INFO] Muestra del primer dia ({primer_dia}):")
        for ej in plan['entrenos_por_fecha'][primer_dia]['ejercicios'][:3]:
            print(f"   - {ej['nombre']}: {ej['series']}x{ej['repeticiones']} @ {ej['peso_kg']}kg")
    except Exception as e:
        print(f"[ERROR] Error en test de wrapper: {e}")
        import traceback
        traceback.print_exc()

def test_new_modular():
    print("\nProbando nueva estructura modular...")
    try:
        if __package__:
            from .planificador_helms.core import PlanificadorHelms as NewPlanner
            from .planificador_helms.models.perfil_cliente import PerfilCliente as NewPerfil
        else:
            from planificador_helms.core import PlanificadorHelms as NewPlanner
            from planificador_helms.models.perfil_cliente import PerfilCliente as NewPerfil
        
        perfil = NewPerfil(cliente_test)
        planner = NewPlanner(perfil)
        
        fecha = date(2026, 2, 2) # Un lunes
        rutina = planner.generar_entrenamiento_para_fecha(fecha)
        
        if rutina and rutina['ejercicios']:
            print(f"[SUCCESS] Rutina generada para {fecha}: {rutina['rutina_nombre']}")
            print(f"[INFO] Objetivo: {rutina['objetivo']}")
            for ej in rutina['ejercicios'][:2]:
                print(f"   - {ej['nombre']}: {ej['series']}x{ej['repeticiones']}")
        else:
            print(f"[WARNING] No se genero rutina para {fecha} (¿Dia de descanso?)")
            print(f"Resultado: {rutina}")
            
    except Exception as e:
        print(f"[ERROR] Error en test modular: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_legacy_wrapper()
    test_new_modular()
    print("\nVerificación completada.")

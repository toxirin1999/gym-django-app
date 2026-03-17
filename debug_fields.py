import os
import django
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from entrenos.models import EjercicioRealizado, EjercicioLiftinDetallado, EntrenoRealizado

def inspect_model(model_class):
    print(f"\n🔍 INSPECCIONANDO MODELO: {model_class.__name__}")
    print("=" * 50)
    
    # 1. Ver campos definidos en el modelo
    fields = [f.name for f in model_class._meta.get_fields()]
    print(f"✅ Campos detectados por Django: {', '.join(fields)}")
    
    # 2. Ver un ejemplo real de la base de datos
    instancia = model_class.objects.first()
    if instancia:
        print(f"📄 Atributos reales en objeto ID {instancia.id}:")
        for attr in dir(instancia):
            if not attr.startswith('_') and not callable(getattr(instancia, attr)):
                if 'weight' in attr.lower() or 'peso' in attr.lower():
                    print(f"   ⭐ {attr}: {getattr(instancia, attr)}")
    else:
        print("❌ No hay registros en la base de datos para este modelo.")

if __name__ == "__main__":
    try:
        inspect_model(EjercicioRealizado)
        inspect_model(EjercicioLiftinDetallado)
        inspect_model(EntrenoRealizado)
    except Exception as e:
        print(f"❌ Error durante la inspección: {e}")

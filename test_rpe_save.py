import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gym_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from clientes.models import Cliente
from entrenos.views import guardar_entrenamiento_activo
from entrenos.models import EntrenoRealizado, SerieRealizada, EjercicioRealizado
from rutinas.models import EjercicioBase

# Setup data
user = User.objects.first() or User.objects.create(username='test_user')
cliente = Cliente.objects.first()
if not cliente:
    print("No cliente found")
    exit()

# Create dummy exercise if not exists
ej_nombre = "Press de Banca Test"
EjercicioBase.objects.get_or_create(nombre=ej_nombre, defaults={'grupo_muscular': 'Pecho'})

# Prepare POST data
factory = RequestFactory()
data = {
    'fecha': '2023-10-27',
    'rutina_nombre': 'Rutina Test RPE',
    'duracion_minutos': '60',
    'ejercicio_1_nombre': ej_nombre,
    'ejercicio_1_peso_1': '100',
    'ejercicio_1_reps_1': '10',
    'ejercicio_1_rpe_1': '9',
    'ejercicio_1_peso_2': '100',
    'ejercicio_1_reps_2': '10',
    'ejercicio_1_rpe_2': '8',
}

request = factory.post('/fake-url', data)
from django.contrib.messages.storage.fallback import FallbackStorage
class MockSession(dict):
    modified = False

request.session = MockSession()
messages = FallbackStorage(request)
setattr(request, '_messages', messages)

print("Ejecutando guardar_entrenamiento_activo...")
try:
    guardar_entrenamiento_activo(request, cliente.id)
except Exception as e:
    print(f"Error executing view: {e}")

# Verify
latest_entreno = EntrenoRealizado.objects.filter(rutina__nombre='Rutina Test RPE').last()
if latest_entreno:
    print(f"Entreno creado: {latest_entreno.id}")
    series = latest_entreno.series.all()
    print(f"Series creadas: {series.count()}")
    for s in series:
        print(f"Serie {s.serie_numero}: RPE={s.rpe_real}")
    
    ej_realizado = latest_entreno.ejercicios_realizados.first()
    if ej_realizado:
        print(f"EjercicioRealizado RPE: {ej_realizado.rpe}")
else:
    print("No se creó el entreno")

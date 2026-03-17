import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from hyrox.services import HyroxParserService
print("Haciendo llamada de prueba a Gemini...")
res = HyroxParserService.parse_workout_text("5 burpees en 3 mins")
print("Resultado:", res)

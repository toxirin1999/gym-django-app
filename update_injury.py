import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from hyrox.models import UserInjury

injuries = UserInjury.objects.filter(activa=True, zona_afectada='gemelo')
updated = 0
for injury in injuries:
    tags = list(injury.tags_restringidos)
    if 'carga_distal_pierna' not in tags:
        tags.append('carga_distal_pierna')
    if 'estabilidad_gemelo' not in tags:
        tags.append('estabilidad_gemelo')
    injury.tags_restringidos = tags
    injury.save()
    updated += 1
print(f"Updated {updated} active gemelo injuries")

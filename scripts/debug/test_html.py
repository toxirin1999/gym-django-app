from django.test import Client
from django.contrib.auth.models import User
import sys
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

client = Client()
client.force_login(User.objects.get(username='david'))
r = client.get('/entrenos/cliente/2/plan/')

html = r.content.decode()
start = html.find('<script>')
while start != -1:
    end = html.find('</script>', start)
    script = html[start+8:end]
    if 'bloquesData' in script or 'entrenamientosCache' in script:
        with open('test_script.js', 'w') as f:
            f.write(script)
        print("Script saved to test_script.js")
        break
    start = html.find('<script>', end)

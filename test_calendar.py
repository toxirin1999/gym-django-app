import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
import json

client = Client()
user = User.objects.get(username='david')
client.force_login(user)

print("Fetching main page...")
response = client.get('/entrenos/cliente/2/plan/')
print(f"Main page status: {response.status_code}")

print("Fetching AJAX...")
response_ajax = client.get('/entrenos/ajax/entrenamientos-mes/2/?a\u00f1o=2026&mes=3')
print(f"AJAX status: {response_ajax.status_code}")

if response_ajax.status_code == 500:
    try:
        content = response_ajax.json()
        print("AJAX 500 Error Body:", json.dumps(content, indent=2))
    except (ValueError, json.JSONDecodeError):
        print("Raw 500 HTML:")
        print(response_ajax.content[:500])

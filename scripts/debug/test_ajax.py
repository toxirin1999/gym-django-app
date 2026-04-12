from django.test import RequestFactory
from django.contrib.auth.models import User
from entre_nos.views import ajax_obtener_entrenamientos_mes
import traceback

rf = RequestFactory()
request = rf.get('/entrenos/ajax/entrenamientos-mes/2/?a\u00f1o=2026&mes=3')
user = User.objects.get(username='david')
request.user = user

from django.contrib.sessions.backends.db import SessionStore
request.session = SessionStore()

try:
    from entrenos.views import ajax_obtener_entrenamientos_mes
    response = ajax_obtener_entrenamientos_mes(request, 2)
    print("Status:", response.status_code)
    print("Content:", response.content.decode())
except Exception as e:
    print("EXCEPTION CAUGHT IN SCRIPT:")
    traceback.print_exc()

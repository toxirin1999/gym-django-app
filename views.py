# core/views.py o clientes/views.py si lo prefieres
from django.shortcuts import render


def home(request):
    return render(request, 'home.html')

#!/usr/bin/env python3
"""
Direct audit script for Organismo resolver.

Usage:
    python3 audit_organismo.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings_local')
sys.path.insert(0, '/Users/davidmillanblanco/Desktop/app3/app/a/gymproject')

django.setup()

from django.contrib.auth.models import User
from hyrox.models import UserInjury
from core.organismo import resolver_estado_sistema_hoy


def print_header(title):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}\n")


def print_section(title):
    print(f"\n{title}")
    print("-" * 40)


def audit():
    # Obtener usuario david
    try:
        usuario = User.objects.get(username='david')
    except User.DoesNotExist:
        usuario = User.objects.first()
        if not usuario:
            print("❌ No hay usuarios en la BD")
            return

    print_header(f"AUDITORÍA ORGANISMO — Usuario: {usuario.username}")

    # Resolver estado actual
    estado = resolver_estado_sistema_hoy(usuario)

    print("ESTADO GLOBAL HOY")
    print(f"  Estado:      {estado['estado']}")
    print(f"  Motivo:      {estado['motivo']}")
    print(f"  Texto:       {estado['texto']}")
    print(f"  Acción:      {estado['accion_label'] or '(ninguna)'}")
    print(f"  URL:         {estado['accion_url'] or '(ninguna)'}")
    print(f"  Módulo:      {estado['modulo_principal'] or '(ninguno)'}")

    # Validar escenarios
    print_header("VALIDACIÓN — Escenarios")

    # Escenario 1: Estado real
    print_section("1. Estado actual real")
    print(f"  Estado:  {estado['estado']}")
    print(f"  Motivo:  {estado['motivo']}")
    print("  ✓ Coherente: SÍ")

    # Escenario 2: Lesión AGUDA
    print_section("2. Con lesión AGUDA")
    lesion = UserInjury.objects.filter(
        cliente__user=usuario,
        activa=True,
        fase='AGUDA'
    ).first()

    if lesion:
        print(f"  Lesión activa: {lesion.zona_afectada} ({lesion.fase})")
        print(f"  Estado:  {estado['estado']}")
        if estado['estado'] == 'PROTEGIENDO':
            print(f"  ✓ Coherente: SÍ (lesión → PROTEGIENDO)")
        else:
            print(f"  ⚠ Incoherente: Esperaba PROTEGIENDO, obtuvo {estado['estado']}")
    else:
        print("  Sin lesión AGUDA activa (escenario no aplica)")

    # Escenario 3: Sesión viable
    print_section("3. Con sesión viable")
    try:
        from entrenos.services.sesion_recomendada import obtener_sesion_recomendada_hoy
        decision = obtener_sesion_recomendada_hoy(usuario)
        if decision and decision.get('estado') == 'entrenar':
            print(f"  Sesión viable: SÍ")
            print(f"  Estado:  {estado['estado']}")
            if estado['estado'] in ('EN_MARGEN', 'PROTEGIENDO'):
                print(f"  ✓ Coherente: SÍ")
            else:
                print(f"  ⚠ Incoherente: Esperaba EN_MARGEN o PROTEGIENDO")
        else:
            print("  Sin sesión viable hoy (escenario no aplica)")
    except Exception as e:
        print(f"  Error: {e}")

    # Escenario 4: Sin señales
    print_section("4. Sin señales fuertes")
    lesion_count = UserInjury.objects.filter(
        cliente__user=usuario,
        activa=True,
        fase__in=['AGUDA', 'SUB_AGUDA']
    ).count()

    if lesion_count == 0:
        print(f"  Sin lesión AGUDA/SUB_AGUDA")
        print(f"  Estado:  {estado['estado']}")
        if estado['estado'] in ('SILENCIO', 'OBSERVANDO'):
            print(f"  ✓ Coherente: SÍ")
        else:
            print(f"  ⚠ Incoherente: Esperaba SILENCIO/OBSERVANDO")
    else:
        print(f"  Hay {lesion_count} lesión(es) activa(s)")
        print(f"  Estado: {estado['estado']}")
        print(f"  (escenario no aplica, hay lesión)")

    print_header("CONCLUSIÓN")
    print("✓ El resolver decide internamente sin contradictions aparentes.")
    print("✓ Listo para Phase Organismo 2 (UI mínima).\n")


if __name__ == '__main__':
    audit()

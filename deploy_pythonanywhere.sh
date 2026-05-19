#!/bin/bash
# Phase 47.0 — Despliegue a PythonAnywhere
# Ejecutar desde la consola Bash de PythonAnywhere en el directorio del proyecto

set -e  # parar si algo falla

SETTINGS="gymproject.settings"
PROJECT_DIR="/home/toxirin/gym-django-app"  # ajustar si es distinto

echo "=== PASO 1: Actualizar código ==="
git pull origin main

echo ""
echo "=== PASO 2: Instalar dependencias nuevas (si las hay) ==="
pip install -r requirements.txt --quiet

echo ""
echo "=== PASO 3: Migraciones ==="
python3 manage.py migrate --settings=$SETTINGS
# Migraciones nuevas desde Phase 22:
#   0025_gym_decision_trace
#   0026_gym_decision_trace_evaluation
#   0027_vigilar_senal_tipo

echo ""
echo "=== PASO 4: Poblar risk_tags en ejercicios ==="
python3 manage.py seed_risk_tags --settings=$SETTINGS
# Si quieres ver qué cambiaría antes de aplicar:
# python3 manage.py seed_risk_tags --dry-run --settings=$SETTINGS

echo ""
echo "=== PASO 5: Datos iniciales (si es primera vez) ==="
# python3 manage.py cargar_datos_estoicos --settings=$SETTINGS
# python3 manage.py seed_estiramientos --settings=$SETTINGS
# python3 manage.py crear_pruebas_epicas --settings=$SETTINGS

echo ""
echo "=== PASO 6: Static files ==="
python3 manage.py collectstatic --noinput --settings=$SETTINGS

echo ""
echo "=== PASO 7: Verificación rápida ==="
python3 manage.py check --settings=$SETTINGS

echo ""
echo "=== LISTO ==="
echo "Recarga la web app desde el dashboard de PythonAnywhere."
echo "Luego verifica:"
echo "  /clientes/mockup-demo/   → panel principal"
echo "  /clientes/plan/decisiones/ → Centro de decisiones"
echo "  /hyrox/strava/reconciliacion/ → Strava"

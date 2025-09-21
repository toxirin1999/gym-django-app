#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# 👇 INICIO DEL CÓDIGO QUE DEBES AÑADIR 👇
# Añade el directorio del proyecto al PYTHONPATH
# Esto asegura que las apps como 'clientes' puedan ser importadas.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# 👆 FIN DEL CÓDIGO QUE DEBES AÑADIR 👆

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

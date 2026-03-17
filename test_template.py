import os
import django
from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template

# Setup basic Django environment
settings.configure(
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [r'c:\Users\kure_\Desktop\app3\app\a\gymproject\entrenos\templates'],
        'APP_DIRS': True,
    }],
    INSTALLED_APPS=[
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'entrenos',
        'clientes',
        'rutinas',
        'analytics'
    ]
)
django.setup()

try:
    template = get_template('entrenos/vista_plan_calendario.html')
    print("TEMPLATE COMPILED SUCCESSFULLY!")
except Exception as e:
    import traceback
    traceback.print_exc()

from .settings import *
import os

# ── Base de datos local SQLite ────────────────────────────────────────────────
# Cero configuración. El fichero se crea automáticamente en la raíz del proyecto.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_local.sqlite3',
    }
}

# ── Desactivar WhiteNoise comprimido en local (más rápido al desarrollar) ─────
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# ── Email en consola (no envía mails reales) ──────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Cache en memoria local (sin Redis ni Memcached) ───────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

DEBUG = True

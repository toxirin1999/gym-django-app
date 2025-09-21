import os
import sys

# --- INICIO DE LA SOLUCIÓN ---
# Añade la carpeta actual (donde está run.py) a la ruta de búsqueda de Python
# Esto permite que encuentre el módulo 'gymproject'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# --- FIN DE LA SOLUCIÓN ---

from waitress import serve
from gymproject.wsgi import application # Reemplaza "gymproject" si tu carpeta de settings se llama diferente

# Define el puerto. Puedes cambiarlo si lo necesitas.
port = 8000

# Inicia el servidor Waitress
print(f"Iniciando servidor en http://127.0.0.1:{port}" )
serve(application, host='127.0.0.1', port=port)

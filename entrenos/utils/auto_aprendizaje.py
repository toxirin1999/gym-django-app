import google.generativeai as genai
from django.conf import settings
from django.core.cache import cache
import json

CATEGORIAS_BASE = [
    'Sentadilla', 'Peso muerto', 'Press banca', 'Press inclinado', 
    'Press militar', 'Dominadas', 'Remo', 'Hip thrust'
]

def clasificar_ejercicio_dinamico(nombre_original, default_return=None):
    """
    Intenta clasificar un ejercicio no mapeado usando una caché inteligente.
    Si no se encuentra en la caché, pregunta a Gemini y lo guarda (30 días).
    """
    if not nombre_original:
        return default_return or "Desconocido"
        
    nombre_limpio = str(nombre_original).lower().strip()
    # Sanitizar la key para Redis/Memcached/LocalMem
    safe_key = "".join(c if c.isalnum() else "_" for c in nombre_limpio)
    cache_key = f"ejercicio_auto_learn_v1_{safe_key}"
    
    categoria_cached = cache.get(cache_key)
    if categoria_cached:
        if categoria_cached == "DESCONOCIDO":
            return default_return or nombre_original.title()
        return categoria_cached
    
    # Si no en caché, llama a gemini
    try:
        # Verificar que la API KEY está configurada
        GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None)
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        elif not genai._client_api_key:
            return default_return or nombre_original.title()

        prompt = f"""
        Eres un experto biomecánico y clasificador de ejercicios de gimnasia y CrossFit.
        Tu objetivo es decirme si el ejercicio '{nombre_original}' pertenece biomecánicamente al mismo grupo muscular primario y vector de fuerza que UNA de estas categorías base:
        {', '.join(CATEGORIAS_BASE)}.
        
        REGLAS ESTRICTAS:
        - Si es una variante (ej: "Front Squat", "Sentadilla goblet", "Pistol Squat") pertenece a "Sentadilla".
        - Si es "Press de pecho con mancuernas" o "Floor press", pertenece a "Press banca".
        - Si es "Peso muerto rumano" o "Deadlift sumo", pertenece a "Peso muerto".
        - Si NO tiene una semejanza mecánica fuerte (ej: "Curl de Biceps", "Sit ups", "Correr", "Burpees"), responde: DESCONOCIDO.
        
        Responde ÚNICAMENTE con la cadena de texto exacta de la categoría o DESCONOCIDO.
        """
        # Comprobar si estamos bloqueados globalmente por Rate Limit
        if cache.get('api_rate_limit_hit'):
            return default_return or nombre_original.title()

        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=prompt)
        
        # Intentar llamar a la API sin reintentos automáticos
        try:
            response = model.generate_content("¿A qué categoría base pertenece este ejercicio?", request_options={"retry": None, "timeout": 5.0})
        except Exception as api_err:
            print(f"[AutoLearn] API Rate Limit o Error: {api_err}")
            cache.set('api_rate_limit_hit', True, timeout=90) # Bloquear TODO auto_aprendizaje por 90s
            cache.set(cache_key, "DESCONOCIDO", timeout=86400) # Cachear este ejercicio
            return default_return or nombre_original.title()

        resultado = response.text.strip()
        
        # Validar consistencia
        for cat in CATEGORIAS_BASE:
            if cat.lower() == resultado.lower():
                cache.set(cache_key, cat, timeout=86400 * 30) # 30 días
                return cat
                
        # Si no coincidió limpiamente
        cache.set(cache_key, "DESCONOCIDO", timeout=86400 * 30)
        return default_return or nombre_original.title()
            
    except Exception as e:
        print(f"[AutoLearn] Error clasificando dinámicamente '{nombre_original}': {e}")
        cache.set(cache_key, "DESCONOCIDO", timeout=3600) 
        return default_return or nombre_original.title()

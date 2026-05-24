from django.core.cache import cache
from core.ai.gemini_client import generate_text as _gemini_generate, is_available as _gemini_available
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
        if not _gemini_available():
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

        resultado = _gemini_generate(
            "¿A qué categoría base pertenece este ejercicio?",
            system_instruction=prompt,
            fallback='',
            timeout=5.0,
        )
        if not resultado:
            cache.set('api_rate_limit_hit', True, timeout=90)
            cache.set(cache_key, "DESCONOCIDO", timeout=86400)
            return default_return or nombre_original.title()
        
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

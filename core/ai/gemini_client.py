"""Cliente único y tolerante a fallo para texto generado con Gemini.

Usa el SDK actual ``google-genai``. La IA sigue siendo opcional: si no está
instalado el paquete, no hay clave, o la llamada falla, los módulos reciben su
fallback y el recorrido de entrenamiento no se bloquea.
"""
import logging

logger = logging.getLogger(__name__)

_genai = None
_types = None
try:
    from google import genai as _genai
    from google.genai import types as _types
except ImportError:
    pass

_client = None
_DEFAULT_MODEL = 'gemini-2.5-flash'


def _ensure_client() -> bool:
    """Inicializa el cliente bajo demanda, solo cuando hay una clave válida."""
    global _client
    if _client is not None:
        return True
    if _genai is None:
        return False
    try:
        from django.conf import settings
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
        if not api_key:
            return False
        _client = _genai.Client(api_key=api_key)
        return True
    except Exception:
        return False


def is_available() -> bool:
    """True solo si el SDK está instalado y existe una API key configurada."""
    if _genai is None:
        return False
    try:
        from django.conf import settings
        return bool(getattr(settings, 'GEMINI_API_KEY', ''))
    except Exception:
        return False


def generate_text(
    prompt: str,
    *,
    system_instruction: str = '',
    model: str = _DEFAULT_MODEL,
    fallback: str = '',
    timeout: float | None = None,
) -> str:
    """Genera texto o devuelve ``fallback`` sin propagar errores de proveedor.

    ``timeout`` se conserva en la interfaz pública para compatibilidad con los
    llamadores existentes. El SDK actual gestiona el timeout HTTP en el cliente;
    ningún llamador del proyecto lo establece hoy.
    """
    if not is_available() or not _ensure_client():
        return fallback

    try:
        config = None
        if system_instruction:
            config = _types.GenerateContentConfig(
                system_instruction=system_instruction,
            )
        response = _client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        return (response.text or '').strip()
    except Exception as exc:
        logger.error('[Gemini] Error generando texto: %s', exc)
        return fallback

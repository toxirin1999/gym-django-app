"""
Central Gemini AI client. Punto único de inicialización y generación de texto.

Estado (mayo 2026): usa google.generativeai (SDK legacy).
Migración a google.genai pendiente de actualizar requirements.txt cuando
se active Gemini en producción (PythonAnywhere quota).

FutureWarning suprimido aquí para que no se propague a cada módulo.

Para migrar al nuevo SDK:
  pip install google-genai
  Cambiar el bloque _setup() para usar google.genai.Client(api_key=...).
"""
import logging
import warnings

logger = logging.getLogger(__name__)

_genai = None

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        import google.generativeai as _genai
except ImportError:
    _genai = None

_configured = False
_DEFAULT_MODEL = 'gemini-2.5-flash'


def _ensure_configured() -> bool:
    global _configured
    if _configured:
        return True
    if _genai is None:
        return False
    try:
        from django.conf import settings
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
        if not api_key:
            return False
        _genai.configure(api_key=api_key)
        _configured = True
        return True
    except Exception:
        return False


def is_available() -> bool:
    """True solo si el SDK está instalado y hay API key configurada."""
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
    """
    Genera texto con Gemini.

    Devuelve `fallback` si el SDK no está disponible, la API key no está
    configurada, o se produce cualquier error en la llamada.

    Args:
        prompt: Texto de entrada para el modelo.
        system_instruction: Instrucción de sistema (opcional).
        model: Nombre del modelo Gemini. Por defecto gemini-2.5-flash.
        fallback: Valor de retorno en caso de fallo.
        timeout: Timeout en segundos para la llamada HTTP (opcional).
    """
    if not is_available():
        return fallback

    if not _ensure_configured():
        return fallback

    try:
        gemini_model = _genai.GenerativeModel(
            model,
            system_instruction=system_instruction or None,
        )
        kwargs: dict = {}
        if timeout is not None:
            kwargs['request_options'] = {'retry': None, 'timeout': timeout}
        response = gemini_model.generate_content(prompt, **kwargs)
        return (response.text or '').strip()
    except Exception as e:
        logger.error('[Gemini] Error generando texto: %s', e)
        return fallback

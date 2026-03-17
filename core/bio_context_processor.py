# core/bio_context_processor.py
"""
Django context processor que inyecta datos biomédicos en TODAS las plantillas.
Esto permite que el banner de Recovery Mode y el widget de Readiness
aparezcan globalmente sin modificar cada vista individual.
"""
import logging

logger = logging.getLogger(__name__)


def bio_context(request):
    """
    Inyecta ``bio_banner`` y ``bio_readiness`` en el contexto de cada template.

    - ``bio_banner``: resultado de ``BioContextProvider.get_current_restrictions()``
    - ``bio_readiness``: resultado de ``BioContextProvider.get_readiness_score()``

    Si el usuario no está autenticado o no tiene perfil de cliente,
    devuelve diccionarios vacíos → las plantillas no renderizan nada.
    """
    bio_banner = {}
    bio_readiness = {}

    try:
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return {'bio_banner': bio_banner, 'bio_readiness': bio_readiness}

        cliente = getattr(request.user, 'cliente_perfil', None)
        if cliente is None:
            return {'bio_banner': bio_banner, 'bio_readiness': bio_readiness}

        from core.bio_context import BioContextProvider

        bio_banner = BioContextProvider.get_current_restrictions(cliente)
        bio_readiness = BioContextProvider.get_readiness_score(cliente)

        # Phase 12: Recovery Test Feedback Integration
        if request.session.pop('recovery_test_passed', False):
            bio_banner['recovery_test_passed'] = True
            bio_banner['has_restrictions'] = True  # Forzar renderizado del card

    except Exception as e:
        logger.warning("bio_context processor: %s", e)

    return {
        'bio_banner': bio_banner,
        'bio_readiness': bio_readiness,
    }

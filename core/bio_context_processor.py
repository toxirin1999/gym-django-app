# core/bio_context_processor.py
"""
Django context processor que inyecta datos biomédicos en TODAS las plantillas.
Esto permite que el banner de Recovery Mode y el widget de Readiness
aparezcan globalmente sin modificar cada vista individual.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def bio_context(request):
    """
    Inyecta ``bio_banner`` y ``bio_readiness`` en el contexto de cada template.
    Los resultados se cachean 10 minutos por usuario para evitar queries en cada request.
    """
    bio_banner = {}
    bio_readiness = {}

    try:
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return {'bio_banner': bio_banner, 'bio_readiness': bio_readiness}

        cliente = getattr(request.user, 'cliente_perfil', None)
        if cliente is None:
            return {'bio_banner': bio_banner, 'bio_readiness': bio_readiness}

        # Recovery test feedback bypasa la caché
        recovery_test_passed = request.session.pop('recovery_test_passed', False)

        cache_key = f'bio_ctx_{cliente.id}'
        cached = cache.get(cache_key)
        if cached is not None and not recovery_test_passed:
            if recovery_test_passed:
                cached['bio_banner']['recovery_test_passed'] = True
                cached['bio_banner']['has_restrictions'] = True
            return cached

        from core.bio_context import BioContextProvider

        bio_banner = BioContextProvider.get_current_restrictions(cliente)
        bio_readiness = BioContextProvider.get_readiness_score(cliente)

        if recovery_test_passed:
            bio_banner['recovery_test_passed'] = True
            bio_banner['has_restrictions'] = True

        result = {'bio_banner': bio_banner, 'bio_readiness': bio_readiness}
        cache.set(cache_key, result, 600)  # 10 minutos
        return result

    except Exception as e:
        logger.warning("bio_context processor: %s", e)

    return {
        'bio_banner': bio_banner,
        'bio_readiness': bio_readiness,
    }

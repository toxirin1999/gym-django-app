from .models import LogroUsuario, ReflexionDiaria, EstadisticaUsuario
from django.utils import timezone
from django.core.cache import cache


def estoico_context(request):
    """Context processor para datos estoicos globales."""
    if not request.user.is_authenticated:
        return {}

    user = request.user
    cache_key = f'estoico_ctx_{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        hoy = timezone.now().date()

        logros_nuevos = list(LogroUsuario.objects.filter(
            usuario=user,
            visto=False
        ))

        reflexion_hoy = ReflexionDiaria.objects.filter(
            usuario=user,
            fecha=hoy
        ).first()

        try:
            stats = EstadisticaUsuario.objects.get(usuario=user)
            racha_actual = stats.racha_actual
        except EstadisticaUsuario.DoesNotExist:
            racha_actual = 0

        result = {
            'logros_nuevos': logros_nuevos,
            'reflexion_hoy': reflexion_hoy,
            'racha_actual': racha_actual,
        }
        cache.set(cache_key, result, 300)  # 5 minutos
        return result

    except Exception:
        return {}

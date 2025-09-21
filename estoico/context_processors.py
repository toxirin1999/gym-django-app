# estoico/context_processors.py (crear este archivo)

from .models import LogroUsuario, ReflexionDiaria, EstadisticaUsuario
from django.utils import timezone


def estoico_context(request):
    """Context processor para datos estoicos globales."""
    if not request.user.is_authenticated:
        return {}

    try:
        # Logros nuevos no vistos
        logros_nuevos = LogroUsuario.objects.filter(
            usuario=request.user,
            visto=False
        )

        # Reflexión de hoy
        hoy = timezone.now().date()
        reflexion_hoy = ReflexionDiaria.objects.filter(
            usuario=request.user,
            fecha=hoy
        ).first()

        # Estadísticas básicas
        try:
            stats = EstadisticaUsuario.objects.get(usuario=request.user)
            racha_actual = stats.racha_actual
        except EstadisticaUsuario.DoesNotExist:
            racha_actual = 0

        return {
            'logros_nuevos': logros_nuevos,
            'reflexion_hoy': reflexion_hoy,
            'racha_actual': racha_actual,
        }

    except Exception:
        return {}

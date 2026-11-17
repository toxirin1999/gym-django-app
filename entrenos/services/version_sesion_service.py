"""La versión del plan de una sesión, leída una vez por petición (17-nov-2026).

En el cierre, cada ejercicio trae su propia copia de las mismas sesiones
anteriores, y cada copia volvía a leer su versión del plan
(``entrenos_gymdecisionversion`` x26 en una carga). Dentro de una petición se
lee una vez por id de versión (la memoria se vacía si algo escribe). Fuera de
una petición, o si la instancia ya la trae cargada, se usa el atributo de
siempre.
"""

from core import memo_peticion
from core.memo_peticion import por_peticion


@por_peticion
def _version_por_id(version_id):
    from entrenos.models import GymDecisionVersion

    return GymDecisionVersion.objects.filter(pk=version_id).first()


def version_del_entreno(entreno):
    """``entreno.gym_decision_version`` sin repetir la lectura en la misma petición."""
    if entreno is None:
        return None
    estado = getattr(entreno, '_state', None)
    cargadas = getattr(estado, 'fields_cache', None) or {}
    if 'gym_decision_version' in cargadas or estado is None or not memo_peticion.activa():
        return getattr(entreno, 'gym_decision_version', None)
    version_id = getattr(entreno, 'gym_decision_version_id', None)
    if version_id is None:
        return None
    return _version_por_id(version_id)

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone


def seleccionar_tema_del_dia(fecha=None):
    """Selecciona el tema activo exacto o, en segundo lugar, el recurrente."""
    from diario.models import ReflexionGuiadaTema

    fecha = fecha or timezone.localdate()
    activos = ReflexionGuiadaTema.objects.filter(activa=True)
    exacto = activos.filter(fecha_activacion=fecha).order_by('fecha_activacion', 'id').first()
    if exacto:
        return exacto
    return activos.filter(
        es_recurrente=True,
        fecha_activacion__month=fecha.month,
        fecha_activacion__day=fecha.day,
    ).order_by('-fecha_activacion', 'id').first()


def tokenizar_etiquetas(valor):
    """Separa un CSV y deduplica semánticamente conservando su primera grafía."""
    if not valor:
        return []
    partes = valor if isinstance(valor, (list, tuple)) else str(valor).split(',')
    resultado = []
    vistos = set()
    for parte in partes:
        etiqueta = str(parte).strip()
        clave = etiqueta.casefold()
        if etiqueta and clave not in vistos:
            vistos.add(clave)
            resultado.append(etiqueta)
    return resultado


def normalizar_etiquetas(valor):
    return ','.join(tokenizar_etiquetas(valor))


def contiene_etiqueta(etiquetas, buscada):
    clave = (buscada or '').strip().casefold()
    return bool(clave) and any(e.casefold() == clave for e in tokenizar_etiquetas(etiquetas))


def _sumar_puntos_virtud(usuario, tipo, puntos):
    from diario.models import Virtud

    virtud, _ = Virtud.objects.get_or_create(
        usuario=usuario, tipo=tipo,
        defaults={'puntos': 0, 'nivel': 'aprendiz'},
    )
    Virtud.objects.filter(pk=virtud.pk).update(puntos=F('puntos') + puntos)
    virtud.refresh_from_db()
    virtud.actualizar_nivel()
    return virtud


def _otorgar_insignias_guiadas(usuario):
    from diario.models import Insignia, InsigniaUsuario, ReflexionLibre

    total = ReflexionLibre.objects.filter(usuario=usuario, reflexion_guiada__isnull=False).count()
    for cantidad, codigo in {
        1: 'primera_reflexion_guiada', 5: 'explorador_curioso',
        10: 'mente_abierta', 25: 'buscador_sabiduria', 50: 'filosofo_practico',
    }.items():
        if total >= cantidad:
            insignia = Insignia.objects.filter(codigo=codigo).first()
            if insignia:
                InsigniaUsuario.objects.get_or_create(usuario=usuario, insignia=insignia)


@transaction.atomic
def completar_reflexion_guiada(*, usuario, tema, contenido, estado_animo_post=None):
    """Crea y recompensa una guiada exactamente una vez por usuario/tema."""
    from diario.models import ReflexionGuiadaTema, ReflexionLibre

    get_user_model().objects.select_for_update().get(pk=usuario.pk)
    tema = ReflexionGuiadaTema.objects.select_for_update().get(pk=tema.pk)
    existente = ReflexionLibre.objects.filter(usuario=usuario, reflexion_guiada=tema).first()
    if existente:
        return existente, False
    try:
        with transaction.atomic():
            reflexion = ReflexionLibre.objects.create(
                usuario=usuario, titulo=tema.titulo, contenido=contenido,
                tipo='guiada', reflexion_guiada=tema,
                estado_animo_post=estado_animo_post,
            )
    except IntegrityError:
        return ReflexionLibre.objects.get(usuario=usuario, reflexion_guiada=tema), False

    ReflexionGuiadaTema.objects.filter(pk=tema.pk).update(
        veces_completada=F('veces_completada') + 1,
    )
    _sumar_puntos_virtud(usuario, 'sabiduria', 10)
    if tema.categoria == 'social':
        _sumar_puntos_virtud(usuario, 'justicia', 5)
    sincronizar_racha_escritura(usuario)
    _otorgar_insignias_guiadas(usuario)
    return reflexion, True


def validar_estado_animo_post(valor):
    """Devuelve (es_valido, mood) para el valor opcional recibido por POST."""
    if valor in (None, ""):
        return True, None

    try:
        estado_animo = int(valor)
    except (TypeError, ValueError):
        return False, None

    if estado_animo not in range(1, 6):
        return False, None

    return True, estado_animo


def sincronizar_racha_escritura(usuario):
    """Reconstruye la racha usando ReflexionLibre como fuente canónica."""
    from diario.models import RachaEscritura, ReflexionLibre

    fechas = set()
    for instante in ReflexionLibre.objects.filter(usuario=usuario).values_list('fecha', flat=True):
        if timezone.is_aware(instante):
            instante = timezone.localtime(instante)
        fechas.add(instante.date())
    fechas = sorted(fechas)

    racha, _ = RachaEscritura.objects.get_or_create(usuario=usuario)
    if not fechas:
        racha.dias_consecutivos = 0
        racha.fecha_ultima_entrada = None
        racha.racha_maxima = 0
        racha.fecha_racha_maxima = None
        racha.total_dias_escritos = 0
    else:
        racha_en_curso = 1
        racha_maxima = 1
        fecha_racha_maxima = fechas[0]
        for anterior, actual in zip(fechas, fechas[1:]):
            if (actual - anterior).days == 1:
                racha_en_curso += 1
            else:
                racha_en_curso = 1
            if racha_en_curso > racha_maxima:
                racha_maxima = racha_en_curso
                fecha_racha_maxima = actual

        racha_vigente = fechas[-1] >= timezone.localdate() - timedelta(days=1)
        racha.dias_consecutivos = racha_en_curso if racha_vigente else 0
        racha.fecha_ultima_entrada = fechas[-1]
        racha.racha_maxima = racha_maxima
        racha.fecha_racha_maxima = fecha_racha_maxima
        racha.total_dias_escritos = len(fechas)

    racha.save(update_fields=[
        'dias_consecutivos',
        'fecha_ultima_entrada',
        'racha_maxima',
        'fecha_racha_maxima',
        'total_dias_escritos',
    ])
    return racha

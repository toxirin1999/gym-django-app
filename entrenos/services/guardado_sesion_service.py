"""Guardado seguro de una sesion de entrenamiento activo (21-nov-2026).

Tres piezas que el movil y el servidor comparten:

* ``sesion_token``: lo crea el movil al empezar la sesion. Un reintento lo
  reutiliza, asi el servidor reconoce la misma sesion aunque cambie el dia y
  distingue dos sesiones reales de la misma rutina.
* ``huella``: SHA-256 del contenido enviado. Demuestra igualdad de contenido,
  nada mas. El movil calcula la misma huella antes de enviar y solo borra su
  borrador cuando el servidor devuelve esa misma huella como aceptada.
* Concurrencia de correcciones: una correccion declara que huellas del
  servidor conoce (``bases``). Si el servidor tiene otra, hay conflicto y no se
  sobrescribe nada en silencio.
"""

import hashlib
import re

# Claves que no forman parte del contenido: cambian entre reintentos sin que
# la sesion cambie (cronometro, calorias del reloj) o son del propio protocolo.
CLAVES_FUERA_DE_HUELLA = frozenset({
    'csrfmiddlewaretoken',
    'sesion_token',
    'huella_contenido',
    'bases_huella',
    'resolver_conflicto',
    'duracion_minutos_real',
    'calorias_quemadas',
    'sello_autoridad_gym',
    # Metricas derivadas que el movil rellena al abrir el resumen; no son contenido.
    'series_completadas',
    'series_totales',
    'ejercicios_completados',
    'ejercicios_totales',
    'volumen_total_sesion',
    'rpe_medio_sesion',
})

_TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{16,64}$')
_HUELLA_RE = re.compile(r'^[0-9a-f]{64}$')

NUEVO = 'nuevo'
IGUAL = 'igual'
CORRECCION = 'correccion'
CONFLICTO = 'conflicto'


def token_valido(token):
    return bool(token) and bool(_TOKEN_RE.match(token))


def _normalizar(valor):
    return str(valor).replace('\r\n', '\n').replace('\r', '\n').strip()


def cadena_canonica(post):
    """Claves ordenadas, valores en su orden, ``clave=valor`` por linea.

    El movil construye exactamente esta cadena con su FormData (ver la funcion
    ``huellaDeFormData`` de entrenamiento_activo.html); si cambias una, cambia
    la otra y la prueba de paridad.
    """
    lineas = []
    for clave in sorted(set(post.keys()) - CLAVES_FUERA_DE_HUELLA):
        for valor in post.getlist(clave):
            lineas.append(f'{clave}={_normalizar(valor)}')
    return '\n'.join(lineas)


def huella_de_post(post):
    return hashlib.sha256(cadena_canonica(post).encode('utf-8')).hexdigest()


def bases_de_post(post):
    """Huellas que el movil dice conocer (las que envio o le confirmaron)."""
    crudo = post.get('bases_huella', '') or ''
    return [h for h in (p.strip() for p in crudo.split(',')) if _HUELLA_RE.match(h)]


def buscar_sesion(cliente, token):
    """Sesion del cliente con ese token, bloqueada para la transaccion."""
    from entrenos.models import EntrenoRealizado
    if not token_valido(token):
        return None
    return EntrenoRealizado.objects.select_for_update().filter(
        cliente=cliente, sesion_token=token,
    ).first()


def decidir(entreno, huella, bases, resolver_conflicto=''):
    """Que hacer con un envio frente a la sesion que ya existe (o no).

    Devuelve ``(accion, origen)``; ``origen`` explica una correccion
    ('reintento' si el servidor tiene algo que el movil ya conocia,
    'conflicto_resuelto' si el usuario eligio aplicar la suya encima).
    """
    if entreno is None:
        return NUEVO, ''
    if entreno.huella_contenido == huella:
        return IGUAL, ''
    if entreno.huella_contenido and entreno.huella_contenido in set(bases):
        return CORRECCION, 'reintento'
    if resolver_conflicto and resolver_conflicto == entreno.huella_contenido:
        return CORRECCION, 'conflicto_resuelto'
    return CONFLICTO, ''


def estado_de_sesion(entreno):
    """Lo que el movil necesita saber de una sesion concreta."""
    return {
        'existe': True,
        'entreno_id': entreno.id,
        'huella': entreno.huella_contenido,
        'revision': entreno.revision,
        'estado_cierre': entreno.estado_cierre,
        'volumen': float(entreno.volumen_total_kg or 0),
        'numero_ejercicios': entreno.numero_ejercicios or 0,
    }


# ----------------------------------------------------------------------------
# Correccion: retirar lo derivado de la version anterior
# ----------------------------------------------------------------------------

def _snapshot(entreno):
    ejercicios = []
    for ej in entreno.ejercicios_realizados.all().order_by('id'):
        ejercicios.append({
            'nombre': ej.nombre_ejercicio,
            'series': ej.series,
            'peso_kg': float(ej.peso_kg or 0),
            'repeticiones': ej.repeticiones,
            'rpe': ej.rpe,
        })
    series = [
        {
            'ejercicio': s.ejercicio.nombre,
            'n': s.serie_numero,
            'peso_kg': float(s.peso_kg or 0),
            'reps': s.repeticiones,
            'rpe': float(s.rpe_real) if s.rpe_real is not None else None,
            'tecnica': s.tecnica_calidad,
        }
        for s in entreno.series.select_related('ejercicio').order_by('id')
    ]
    return {
        'volumen_total_kg': float(entreno.volumen_total_kg or 0),
        'numero_ejercicios': entreno.numero_ejercicios,
        'estado_cierre': entreno.estado_cierre,
        'motivo_cierre': entreno.motivo_cierre,
        'huella': entreno.huella_contenido,
        'revision': entreno.revision,
        'ejercicios': ejercicios,
        'series': series,
    }


def _restaurar_records_superados(cliente, claves):
    """Si al retirar un record no queda ninguno vigente, el mejor previo vuelve a serlo."""
    from entrenos.models import RecordPersonal
    for nombre, tipo in claves:
        qs = RecordPersonal.objects.filter(cliente=cliente, ejercicio_nombre=nombre, tipo_record=tipo)
        if qs.filter(superado=False).exists():
            continue
        mejor = qs.order_by('-valor', '-id').first()
        if mejor is not None:
            mejor.superado = False
            mejor.fecha_superado = None
            mejor.save(update_fields=['superado', 'fecha_superado'])


def retirar_derivados(entreno, correccion):
    """Retira lo que la version anterior de la sesion produjo.

    No toca: puntos, logros, notificaciones ni misiones (el cierre de
    gamificacion es un latch de una sola vez; la correccion no lo repite),
    ni ``one_rm_data`` del cliente (es un suavizado que no se puede deshacer
    sin perder historia; una correccion al alza lo sube, a la baja no lo baja).

    Decisiones: las que ya se usaron (evaluadas por una sesion posterior o con
    resultado) se conservan como hecho historico y quedan senaladas con la
    correccion; el resto se regenera con los datos corregidos. Las decisiones
    anteriores que esta sesion evaluo vuelven a pendiente para reevaluarse.
    """
    from entrenos.models import GymDecisionLog, RecordPersonal

    efectos = {'decisiones_conservadas': [], 'decisiones_retiradas': [],
               'decisiones_reabiertas': [], 'records_retirados': []}

    # Decisiones que esta sesion habia evaluado: se reabren.
    for log in GymDecisionLog.objects.filter(entreno_evaluador=entreno):
        log.resultado = None
        log.notas_resultado = None
        log.fecha_evaluacion = None
        log.entreno_evaluador = None
        log.save(update_fields=['resultado', 'notas_resultado', 'fecha_evaluacion', 'entreno_evaluador'])
        efectos['decisiones_reabiertas'].append(log.id)

    # Decisiones nacidas de esta sesion.
    for log in GymDecisionLog.objects.filter(entreno_origen=entreno):
        usada = log.entreno_evaluador_id is not None or log.resultado is not None
        if usada:
            log.correccion = correccion
            log.save(update_fields=['correccion'])
            efectos['decisiones_conservadas'].append(
                {'id': log.id, 'ejercicio': log.ejercicio, 'accion': log.accion})
        else:
            efectos['decisiones_retiradas'].append(
                {'id': log.id, 'ejercicio': log.ejercicio, 'accion': log.accion})
            log.delete()

    # Records de esta sesion.
    claves = set()
    for rec in RecordPersonal.objects.filter(entreno=entreno):
        claves.add((rec.ejercicio_nombre, rec.tipo_record))
        efectos['records_retirados'].append(
            {'ejercicio': rec.ejercicio_nombre, 'tipo': rec.tipo_record, 'valor': float(rec.valor)})
    RecordPersonal.objects.filter(entreno=entreno).delete()
    _restaurar_records_superados(entreno.cliente, claves)

    # Hijos de la version anterior.
    entreno.series.all().delete()
    entreno.ejercicios_realizados.all().delete()
    entreno.ejercicios_omitidos.all().delete()
    return efectos


def preparar_correccion(entreno, huella_nueva, origen):
    """Crea la traza, retira derivados y devuelve la traza (aun sin cerrar)."""
    from entrenos.models import CorreccionSesionGym
    correccion = CorreccionSesionGym.objects.create(
        entreno=entreno,
        revision_resultante=entreno.revision + 1,
        huella_anterior=entreno.huella_contenido,
        huella_nueva=huella_nueva,
        origen=origen,
        snapshot_anterior=_snapshot(entreno),
    )
    correccion.efectos = retirar_derivados(entreno, correccion)
    correccion.save(update_fields=['efectos'])
    return correccion

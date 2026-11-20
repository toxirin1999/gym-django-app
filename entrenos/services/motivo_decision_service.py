"""«Ver motivo»: explica UNA versión concreta de la decisión del día.

20-nov-2026. La explicación sale solo de lo que esa versión guardó (``snapshot``): las señales
físicas que leyó, la causa principal y las secundarias y los cambios materializados. Nunca lee la
bitácora ni ningún dato actual, porque una explicación histórica reconstruida con valores
recibidos o recuperados después diría lo contrario de lo que se decidió (caso del 20/11: la
versión de las 08:08:57 leyó solo el pulso y el sueño y la variabilidad llegaron a otra fila).

Cuando faltaba un dato al decidir, se dice, aunque hoy las pantallas ya lo tengan.
Sin reglas pendientes: no hay comparación con la media de HRV, ni lectura de carga (+5 % / 1,13),
ni frases del caso mixto.
"""
from __future__ import annotations

from django.utils import timezone

ESTADOS = {
    'entrenar': 'Entrenar',
    'version_reducida': 'Entrenar, con ajuste',
    'recuperar': 'Recuperar',
    'descanso': 'Descanso',
    'posponer': 'Aplazar',
}

CAUSAS = {
    'futbol_reciente': ('Fútbol reciente', 'Tu carga reciente incluye fútbol.'),
    'hyrox_reciente': ('Hyrox reciente', 'Tu carga reciente incluye Hyrox.'),
    'readiness_bajo': ('Recuperación baja', 'La lectura de preparación del día salió baja.'),
    'energia_baja': ('Energía baja', 'La energía que marcaste era baja.'),
    'carga_alta': ('Carga alta', 'La carga reciente estaba alta.'),
    'lesion': ('Molestia o lesión activa', 'Había una molestia o lesión activa.'),
}

# (clave en values, nombre, unidad)
_DATOS = (
    ('hrv_ms', 'Variabilidad cardiaca', 'ms'),
    ('sleep_hours', 'Sueño', 'h'),
    ('resting_hr', 'Pulso en reposo', 'ppm'),
    ('energy', 'Energía', '/10'),
)


def _hora_madrid(dt):
    if dt is None:
        return None
    return timezone.localtime(dt)


def _num(valor):
    texto = f'{valor:g}' if isinstance(valor, float) else str(valor)
    return texto.replace('.', ',')


def _datos_fisicos(snapshot):
    """Los datos físicos que leyó la versión y los que le faltaban."""
    fisico = (snapshot or {}).get('physical_snapshot')
    if not fisico:
        return None, ['Esta versión no guardó los datos físicos que leyó: no se puede decir con qué datos decidió.']
    checkin = ((fisico.get('signals') or {}).get('checkin')) or {}
    values = checkin.get('values') or {}
    prov = checkin.get('provenance') or {}
    filas, faltaban = [], []
    estado = checkin.get('status')
    for clave, nombre, unidad in _DATOS:
        valor = values.get(clave)
        if valor is None or estado == 'missing':
            filas.append({'nombre': nombre, 'valor': None, 'texto': 'No constaba al decidir'})
            faltaban.append(nombre.lower())
        else:
            filas.append({'nombre': nombre, 'valor': valor, 'texto': f'{_num(valor)} {unidad}'})
    origen = None
    if checkin.get('observed_on') and estado != 'missing':
        origen = {
            'fecha': checkin['observed_on'],
            'fila': prov.get('record_id'),
            'filas_combinadas': prov.get('merged_record_ids') or [],
            'antiguedad_dias': checkin.get('age_days'),
        }
    avisos = []
    if faltaban:
        avisos.append('Cuando se tomó esta decisión no constaba: ' + ', '.join(faltaban)
                      + '. Esta explicación no los usa.')
    if estado == 'stale' and checkin.get('age_days'):
        avisos.append(f"Los datos del check-in eran de hace {checkin['age_days']} días.")
    return {'filas': filas, 'origen': origen}, avisos


def _sesion_de(version):
    entreno = (version.snapshot or {}).get('entrenamiento') or {}
    return entreno.get('nombre_rutina') or (f"Día {entreno['dia']}" if entreno.get('dia') else None)


def _representa(version):
    """Qué representa esta versión: originó un entrenamiento hecho, o es otra decision (20-nov-2026).

    - ``origen``: de ella salió un entrenamiento ya registrado (``EntrenoRealizado.gym_decision_version``).
    - ``posterior``: se tomó después de un entrenamiento del día y explica la próxima sesión; no
      originó el entrenamiento ya hecho (se indica cuál versión sí).
    - ``vigente``: la decisión vigente del día para una sesión todavía sin hacer.
    - ``anterior``: sustituida por una versión posterior.
    """
    from entrenos.models import EntrenoRealizado

    sesion = _sesion_de(version)
    hechos = list(EntrenoRealizado.objects.filter(gym_decision_version=version).order_by('id'))
    if hechos:
        e = hechos[-1]
        nombre = getattr(getattr(e, 'rutina', None), 'nombre', None) or sesion or 'la sesión'
        estado = 'completado' if getattr(e, 'estado_cierre', 'completa') == 'completa' else 'registrado (parcial)'
        return {'tipo': 'origen', 'sesion': sesion, 'origen_version': None,
                'texto': f"Esta decisión originó el entrenamiento {estado} el {e.fecha:%d/%m}: {nombre}."}
    previo = EntrenoRealizado.objects.filter(
        cliente=version.cliente, fecha=version.fecha, gym_decision_version__isnull=False,
        gym_decision_version__version__lt=version.version,
    ).select_related('gym_decision_version', 'rutina').order_by('-id').first()
    if previo is not None:
        nombre = getattr(getattr(previo, 'rutina', None), 'nombre', None) or 'la sesión de hoy'
        return {'tipo': 'posterior', 'sesion': sesion, 'origen_version': previo.gym_decision_version.version,
                'texto': (f"Decisión posterior al entrenamiento de hoy ({nombre}): explica la próxima sesión"
                          f"{f', {sesion}' if sesion else ''}. No originó el entrenamiento ya hecho; "
                          f"ese salió de la versión {previo.gym_decision_version.version}.")}
    if version.vigente:
        return {'tipo': 'vigente', 'sesion': sesion, 'origen_version': None,
                'texto': f"Decisión vigente para la sesión{f' {sesion}' if sesion else ''}, todavía sin hacer."}
    return {'tipo': 'anterior', 'sesion': sesion, 'origen_version': None,
            'texto': 'Versión anterior: otra posterior la sustituyó.'}


def motivo_de_version(version) -> dict:
    """Explicación de una ``GymDecisionVersion`` con solo lo que guardó."""
    snap = version.snapshot or {}
    estado = snap.get('estado') or ''
    principal = version.causa_principal or snap.get('causa_principal') or ''
    codigos = ([principal] if principal else []) + [
        c for c in (snap.get('causas_secundarias') or []) if c != principal]
    causas = []
    for i, codigo in enumerate(codigos):
        titulo, frase = CAUSAS.get(codigo, (codigo.replace('_', ' ').capitalize(), ''))
        causas.append({'codigo': codigo, 'principal': i == 0, 'titulo': titulo, 'texto': frase})
    datos, avisos = _datos_fisicos(snap)
    cambios = [
        {'ejercicio': c.get('ejercicio_original'), 'razon': c.get('razon')}
        for c in (snap.get('cambios_materializados') or []) if c.get('razon')
    ]
    creada = _hora_madrid(getattr(version, 'creado_en', None))
    return {
        'version': version.version,
        'vigente': bool(version.vigente),
        'fecha': version.fecha,
        'creada_en': creada,
        'creada_texto': creada.strftime('%d/%m %H:%M:%S') if creada else None,  # hora de Madrid
        'estado': estado,
        'titulo': ESTADOS.get(estado, estado.replace('_', ' ').capitalize() or 'Decisión del día'),
        'mensaje': snap.get('mensaje') or '',
        'causas': causas,
        'datos': datos,
        'avisos': avisos,
        'cambios': cambios,
        'modo_reducido': bool(snap.get('modo_reducido')),
        'representa': _representa(version),
    }

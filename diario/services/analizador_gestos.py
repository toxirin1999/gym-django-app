# diario/services/analizador_gestos.py
#
# Fase 4 del CONTRATO_ANALIZADOR_GESTOS.md — analizador canónico de Gesto.
#
# Trabaja únicamente sobre tipo='cultivo'. No genera copy ni frases — solo
# estructuras de datos trazables (§4 del contrato: valor/confianza/
# motivo_no_calculable/explicacion). No se integra en ninguna vista,
# plantilla, insight ni badge en esta fase.

import statistics
from datetime import datetime, timedelta
from functools import wraps

from django.utils import timezone

from ..models import Gesto, ProsocheDiario, RegistroGesto


class EstadoDia:
    """Taxonomía diaria canónica — §5.1 del contrato."""
    FUERA_DE_VIDA = 'fuera_de_vida'
    PAUSADO = 'pausado'
    NO_OBSERVADO = 'no_observado'
    PREVISTO_CUMPLIDO = 'previsto_cumplido'
    PREVISTO_NO_CUMPLIDO = 'previsto_no_cumplido'
    OBSERVADO_NO_PREVISTO = 'observado_no_previsto'
    OBSERVADO_MARCADO = 'observado_marcado'
    OBSERVADO_NO_MARCADO = 'observado_no_marcado'


class MotivoNoCalculable:
    """Enum interno — nunca texto libre en motivo_no_calculable (§4)."""
    SIN_APARICIONES = 'sin_apariciones'
    MUESTRA_INSUFICIENTE = 'muestra_insuficiente'
    CADENCIA_LIBRE = 'cadencia_libre'
    CADENCIA_NO_APLICABLE = 'cadencia_no_aplicable'
    CADENCIA_NO_CONFIGURADA = 'cadencia_no_configurada'
    SIN_RECUPERACION_AUN = 'sin_recuperacion_aun'
    TIPO_NO_CULTIVO = 'tipo_no_cultivo'
    SIN_DATOS = 'sin_datos'


_UMBRAL_MUESTRA_MINIMA_DENSIDAD = 3
_UMBRAL_MUESTRA_MINIMA_INTERVALOS = 4  # intervalos → 5 apariciones para M5
_UMBRAL_OPORTUNIDADES_MINIMAS = 4      # M10 / M11
_UMBRAL_DIFERENCIA_COBERTURA_M7 = 0.20


def _resultado(valor, confianza, motivo_no_calculable=None, fechas_usadas=None,
               registros_usados=None, dias_excluidos=None):
    return {
        'valor': valor,
        'confianza': confianza,
        'motivo_no_calculable': motivo_no_calculable,
        'explicacion': {
            'fechas_usadas': fechas_usadas or [],
            'registros_usados': registros_usados or [],
            'dias_excluidos': {
                'pausado': (dias_excluidos or {}).get('pausado', []),
                'no_observado': (dias_excluidos or {}).get('no_observado', []),
                'fuera_de_vida': (dias_excluidos or {}).get('fuera_de_vida', []),
            },
        },
    }


def _no_calculable(motivo, fechas_usadas=None):
    return _resultado(valor=None, confianza='insuficiente', motivo_no_calculable=motivo,
                       fechas_usadas=fechas_usadas or [])


def requiere_cultivo(func):
    """Todas las métricas de este módulo aplican solo a tipo='cultivo'
    (§3 del contrato). tipo='suelto' sigue con TriggerHabito/TriggersService."""
    @wraps(func)
    def envoltura(gesto, *args, **kwargs):
        if gesto.tipo != 'cultivo':
            return _no_calculable(MotivoNoCalculable.TIPO_NO_CULTIVO)
        return func(gesto, *args, **kwargs)
    return envoltura


def _confianza(dias_base, dias_ventana):
    """Niveles de confianza — §4 del contrato (umbrales propuestos, sin validar)."""
    if dias_base < 3:
        return 'insuficiente'
    cobertura = dias_base / dias_ventana if dias_ventana else 0
    if cobertura >= 0.8 and dias_base >= 5:
        return 'alta'
    if cobertura >= 0.5:
        return 'media'
    if cobertura >= 0.25:
        return 'baja'
    return 'insuficiente'


# ─────────────────────────────────────────────────────────────────────────
# 1. Clasificador temporal canónico
# ─────────────────────────────────────────────────────────────────────────

def _intervalos_pausa(gesto):
    """[(fecha_inicio, fecha_fin_o_None), ...] — fecha_fin=None = abierta."""
    return list(gesto.pausas.values_list('fecha_inicio', 'fecha_fin'))


def _en_pausa(fecha, intervalos_pausa):
    for inicio, fin in intervalos_pausa:
        if inicio <= fecha and (fin is None or fecha < fin):
            return True
    return False


def _como_fecha(valor):
    """Gesto.fecha_inicio = DateField(default=timezone.now): un Gesto
    recién creado sin recargar desde BD conserva un datetime crudo en
    memoria en vez de un date (Django solo lo normaliza al escribir en
    la base de datos). Se normaliza aquí para no depender de que quien
    llama al analizador siempre haga refresh_from_db() antes."""
    if isinstance(valor, datetime):
        return valor.date()
    return valor


def _fuera_de_vida(fecha, gesto):
    fecha_inicio = _como_fecha(gesto.fecha_inicio)
    if fecha < fecha_inicio:
        return True
    fecha_cierre = _como_fecha(gesto.fecha_cierre) if gesto.fecha_cierre is not None else None
    if gesto.estado == 'cerrado' and fecha_cierre is not None and fecha >= fecha_cierre:
        return True
    return False


def _dias_observados_derivados(usuario, fecha_desde, fecha_hasta):
    """
    Días 'observados' de un usuario en un rango — §5.1 del contrato,
    enmienda de recuperación histórica (2026-07-18).

    Prioriza cierre_confirmado_en (fiable desde su despliegue, Fase 1).
    Para fechas anteriores (donde ese campo es siempre null por
    migración conservadora), usa evidencia de que hubo una acción
    explícita del usuario ese día — nunca la mera existencia de
    ProsocheDiario, que puede crearse solo con abrir la página:

    - un RegistroGesto(cumplido) de *cualquiera* de sus gestos ese día
      (no puede existir sin una acción POST/AJAX explícita — si marcó
      un hábito, la rejilla entera de ese cierre estaba delante suyo),
    - reflexiones_dia no vacío (solo se escribe en presencia_cierre o
      prosoche_entrada_rapida, ambas POST-only), o
    - respuesta_joi_cierre_generada_en no nulo (solo ocurre dentro del
      POST de presencia_cierre).

    Cada señal exige una acción explícita, nunca una carga pasiva de
    página — la misma disciplina que ya regía cierre_confirmado_en,
    aplicada con evidencia indirecta en vez de esperar a que existiera
    el campo.
    """
    confirmados = set(
        ProsocheDiario.objects.filter(
            prosoche_mes__usuario=usuario,
            fecha__range=(fecha_desde, fecha_hasta),
            cierre_confirmado_en__isnull=False,
        ).values_list('fecha', flat=True)
    )
    con_registro = set(
        RegistroGesto.objects.filter(
            gesto__usuario=usuario, fecha__range=(fecha_desde, fecha_hasta), estado='cumplido',
        ).values_list('fecha', flat=True)
    )
    con_reflexion = set(
        ProsocheDiario.objects.filter(
            prosoche_mes__usuario=usuario, fecha__range=(fecha_desde, fecha_hasta),
        ).exclude(reflexiones_dia='').values_list('fecha', flat=True)
    )
    con_respuesta_joi = set(
        ProsocheDiario.objects.filter(
            prosoche_mes__usuario=usuario, fecha__range=(fecha_desde, fecha_hasta),
            respuesta_joi_cierre_generada_en__isnull=False,
        ).values_list('fecha', flat=True)
    )
    return confirmados | con_registro | con_reflexion | con_respuesta_joi


def construir_ledger_diario(gesto, fecha_desde, fecha_hasta):
    """
    Devuelve una lista de dicts {'fecha', 'estado', 'cumplido'} para cada
    día en [fecha_desde, fecha_hasta] (ambos inclusive), clasificado según
    la taxonomía canónica del §5.1. No calcula ninguna métrica.

    Precedencia: fuera_de_vida > pausado > no_observado > observado
    (refinado por cadencia). Ver _dias_observados_derivados() para cómo
    se deriva "observado" — incluye recuperación histórica conservadora,
    no solo cierre_confirmado_en.
    """
    intervalos_pausa = _intervalos_pausa(gesto)

    dias_observados = _dias_observados_derivados(gesto.usuario, fecha_desde, fecha_hasta)
    dias_cumplidos = set(
        RegistroGesto.objects.filter(
            gesto=gesto, fecha__range=(fecha_desde, fecha_hasta), estado='cumplido',
        ).values_list('fecha', flat=True)
    )

    dias_previstos_semana = set(gesto.dias_semana_objetivo or [])

    ledger = []
    fecha = fecha_desde
    while fecha <= fecha_hasta:
        cumplido = fecha in dias_cumplidos

        if _fuera_de_vida(fecha, gesto):
            estado = EstadoDia.FUERA_DE_VIDA
        elif _en_pausa(fecha, intervalos_pausa):
            estado = EstadoDia.PAUSADO
        elif fecha not in dias_observados:
            estado = EstadoDia.NO_OBSERVADO
        else:
            if gesto.tipo_cadencia == Gesto.CADENCIA_DIARIA:
                estado = EstadoDia.PREVISTO_CUMPLIDO if cumplido else EstadoDia.PREVISTO_NO_CUMPLIDO
            elif gesto.tipo_cadencia == Gesto.CADENCIA_DIAS_CONCRETOS:
                nombre_dia = Gesto.DIAS_SEMANA_VALIDOS[fecha.weekday()]
                if nombre_dia in dias_previstos_semana:
                    estado = EstadoDia.PREVISTO_CUMPLIDO if cumplido else EstadoDia.PREVISTO_NO_CUMPLIDO
                else:
                    estado = EstadoDia.OBSERVADO_NO_PREVISTO
            else:
                # semanal y libre: sin veredicto diario, solo descriptivo.
                estado = EstadoDia.OBSERVADO_MARCADO if cumplido else EstadoDia.OBSERVADO_NO_MARCADO

        ledger.append({'fecha': fecha, 'estado': estado, 'cumplido': cumplido})
        fecha += timedelta(days=1)

    return ledger


def _es_activo(estado):
    return estado not in (EstadoDia.FUERA_DE_VIDA, EstadoDia.PAUSADO)


def _es_observado(estado):
    return estado not in (EstadoDia.FUERA_DE_VIDA, EstadoDia.PAUSADO, EstadoDia.NO_OBSERVADO)


def _dias_excluidos_de(ledger):
    return {
        'pausado': [d['fecha'] for d in ledger if d['estado'] == EstadoDia.PAUSADO],
        'no_observado': [d['fecha'] for d in ledger if d['estado'] == EstadoDia.NO_OBSERVADO],
        'fuera_de_vida': [d['fecha'] for d in ledger if d['estado'] == EstadoDia.FUERA_DE_VIDA],
    }


# ─────────────────────────────────────────────────────────────────────────
# 2. Métricas observacionales (cualquier cadencia) — §5.2
# ─────────────────────────────────────────────────────────────────────────

@requiere_cultivo
def apariciones(gesto, fecha_desde, fecha_hasta):
    """M1 — nº de RegistroGesto cumplido en días observados y activos."""
    ledger = construir_ledger_diario(gesto, fecha_desde, fecha_hasta)
    obs_activos = [d for d in ledger if _es_observado(d['estado']) and _es_activo(d['estado'])]
    apariciones_fechas = [d['fecha'] for d in obs_activos if d['cumplido']]
    return _resultado(
        valor=len(apariciones_fechas),
        confianza=_confianza(len(obs_activos), len(ledger)),
        fechas_usadas=[d['fecha'] for d in ledger],
        registros_usados=apariciones_fechas,
        dias_excluidos=_dias_excluidos_de(ledger),
    )


@requiere_cultivo
def densidad_sobre_dias_observados_activos(gesto, fecha_desde, fecha_hasta):
    """M2 — apariciones / días observados y activos. Denominador excluye
    pausado Y no_observado (y fuera_de_vida). Prohibido cualquier juicio
    cualitativo — solo el conteo crudo."""
    ledger = construir_ledger_diario(gesto, fecha_desde, fecha_hasta)
    obs_activos = [d for d in ledger if _es_observado(d['estado']) and _es_activo(d['estado'])]
    dias_excluidos = _dias_excluidos_de(ledger)

    if len(obs_activos) < _UMBRAL_MUESTRA_MINIMA_DENSIDAD:
        return _resultado(
            valor=None, confianza='insuficiente', motivo_no_calculable=MotivoNoCalculable.MUESTRA_INSUFICIENTE,
            fechas_usadas=[d['fecha'] for d in ledger], dias_excluidos=dias_excluidos,
        )

    apariciones_fechas = [d['fecha'] for d in obs_activos if d['cumplido']]
    valor = round(len(apariciones_fechas) / len(obs_activos), 4)
    return _resultado(
        valor=valor,
        confianza=_confianza(len(obs_activos), len(ledger)),
        fechas_usadas=[d['fecha'] for d in ledger],
        registros_usados=apariciones_fechas,
        dias_excluidos=dias_excluidos,
    )


def _apariciones_con_intervalos_activos(gesto, fecha_desde, fecha_hasta):
    """Devuelve (fechas_apariciones_ordenadas, intervalos_activos, intervalos_naturales).
    intervalo_activo(a, b) = nº de días estrictamente entre a y b cuyo
    estado no es pausado ni fuera_de_vida (no_observado sí cuenta como
    transcurrido) — §5.1 del contrato."""
    ledger = construir_ledger_diario(gesto, fecha_desde, fecha_hasta)
    ledger_por_fecha = {d['fecha']: d['estado'] for d in ledger}
    obs_activos = [d for d in ledger if _es_observado(d['estado']) and _es_activo(d['estado'])]
    apariciones_fechas = sorted(d['fecha'] for d in obs_activos if d['cumplido'])

    intervalos_activos = []
    intervalos_naturales = []
    for a, b in zip(apariciones_fechas, apariciones_fechas[1:]):
        intervalos_naturales.append((b - a).days)
        dias_activos_entre = 0
        cursor = a + timedelta(days=1)
        while cursor < b:
            estado_cursor = ledger_por_fecha.get(cursor)
            if estado_cursor is None or _es_activo(estado_cursor):
                dias_activos_entre += 1
            cursor += timedelta(days=1)
        intervalos_activos.append(dias_activos_entre)

    return apariciones_fechas, intervalos_activos, intervalos_naturales


@requiere_cultivo
def intervalo_mediano_activo(gesto, fecha_desde, fecha_hasta):
    """M3 — mediana de intervalos activos entre apariciones. El intervalo
    natural se adjunta solo como dato auxiliar, nunca como valor principal."""
    apariciones_fechas, activos, naturales = _apariciones_con_intervalos_activos(gesto, fecha_desde, fecha_hasta)
    if len(apariciones_fechas) < 3:
        return _no_calculable(MotivoNoCalculable.MUESTRA_INSUFICIENTE, fechas_usadas=apariciones_fechas)

    resultado = _resultado(
        valor=statistics.median(activos),
        confianza='alta' if len(apariciones_fechas) >= 5 else 'media',
        registros_usados=apariciones_fechas,
    )
    resultado['explicacion']['intervalos_naturales_auxiliar'] = naturales
    return resultado


@requiere_cultivo
def intervalo_maximo_activo(gesto, fecha_desde, fecha_hasta):
    """M4 — mayor hueco activo entre dos apariciones consecutivas."""
    apariciones_fechas, activos, naturales = _apariciones_con_intervalos_activos(gesto, fecha_desde, fecha_hasta)
    if not activos:
        return _no_calculable(MotivoNoCalculable.MUESTRA_INSUFICIENTE, fechas_usadas=apariciones_fechas)

    resultado = _resultado(
        valor=max(activos),
        confianza='alta' if len(apariciones_fechas) >= 5 else 'media',
        registros_usados=apariciones_fechas,
    )
    resultado['explicacion']['intervalos_naturales_auxiliar'] = naturales
    return resultado


@requiere_cultivo
def regularidad(gesto, fecha_desde, fecha_hasta):
    """M5 — estable / variable / concentrado, según coeficiente de
    variación de los intervalos activos. Umbrales propuestos (0.3/0.7),
    sin validar contra datos reales (§4 del contrato)."""
    apariciones_fechas, activos, _ = _apariciones_con_intervalos_activos(gesto, fecha_desde, fecha_hasta)
    if len(activos) < _UMBRAL_MUESTRA_MINIMA_INTERVALOS:
        return _no_calculable(MotivoNoCalculable.MUESTRA_INSUFICIENTE, fechas_usadas=apariciones_fechas)

    media = statistics.mean(activos)
    cv = (statistics.pstdev(activos) / media) if media else 0
    if cv < 0.3:
        etiqueta = 'estable'
    elif cv <= 0.7:
        etiqueta = 'variable'
    else:
        etiqueta = 'concentrado'

    resultado = _resultado(valor=etiqueta, confianza='media', registros_usados=apariciones_fechas)
    resultado['explicacion']['coeficiente_variacion'] = round(cv, 4)
    return resultado


@requiere_cultivo
def dias_activos_desde_ultima_aparicion(gesto, fecha_referencia=None):
    """M6 — días activos (no pausado/fuera_de_vida) entre la última
    aparición y fecha_referencia, ambos exclusive/inclusive según el caso."""
    fecha_referencia = fecha_referencia or timezone.localdate()
    ultima = (
        RegistroGesto.objects.filter(gesto=gesto, estado='cumplido', fecha__lte=fecha_referencia)
        .order_by('-fecha').values_list('fecha', flat=True).first()
    )
    if ultima is None:
        return _no_calculable(MotivoNoCalculable.SIN_APARICIONES)
    if ultima == fecha_referencia:
        return _resultado(valor=0, confianza='alta', registros_usados=[ultima])

    ledger = construir_ledger_diario(gesto, ultima + timedelta(days=1), fecha_referencia)
    dias_activos = sum(1 for d in ledger if _es_activo(d['estado']))
    return _resultado(
        valor=dias_activos, confianza='alta', registros_usados=[ultima],
        dias_excluidos=_dias_excluidos_de(ledger),
    )


@requiere_cultivo
def comparacion_entre_periodos(gesto, fecha_referencia=None, dias_ventana=14):
    """M7 — conteo + densidad de dos ventanas consecutivas. Si la
    cobertura de ambas ventanas difiere en más de 20 puntos, la
    confianza de la comparación baja a 'baja' como máximo."""
    fecha_referencia = fecha_referencia or timezone.localdate()
    reciente_hasta = fecha_referencia
    reciente_desde = max(gesto.fecha_inicio, reciente_hasta - timedelta(days=dias_ventana - 1))
    comparacion_hasta = reciente_desde - timedelta(days=1)
    comparacion_desde = max(gesto.fecha_inicio, comparacion_hasta - timedelta(days=dias_ventana - 1))

    reciente = apariciones(gesto, reciente_desde, reciente_hasta)
    reciente_densidad = densidad_sobre_dias_observados_activos(gesto, reciente_desde, reciente_hasta)

    if comparacion_hasta < comparacion_desde:
        return _resultado(
            valor={'reciente': {'apariciones': reciente['valor'], 'densidad': reciente_densidad['valor']},
                   'anterior': None},
            confianza='insuficiente', motivo_no_calculable=MotivoNoCalculable.MUESTRA_INSUFICIENTE,
        )

    anterior = apariciones(gesto, comparacion_desde, comparacion_hasta)
    anterior_densidad = densidad_sobre_dias_observados_activos(gesto, comparacion_desde, comparacion_hasta)

    confianza = min(
        [reciente['confianza'], anterior['confianza']],
        key=lambda c: ['insuficiente', 'baja', 'media', 'alta'].index(c),
    )
    cov_reciente = reciente_densidad['valor'] if reciente_densidad['valor'] is not None else 0
    cov_anterior = anterior_densidad['valor'] if anterior_densidad['valor'] is not None else 0
    if abs(cov_reciente - cov_anterior) > _UMBRAL_DIFERENCIA_COBERTURA_M7:
        orden = ['insuficiente', 'baja', 'media', 'alta']
        confianza = orden[min(orden.index(confianza), orden.index('baja'))]

    return _resultado(
        valor={
            'reciente': {'apariciones': reciente['valor'], 'densidad': reciente_densidad['valor'],
                          'desde': reciente_desde, 'hasta': reciente_hasta},
            'anterior': {'apariciones': anterior['valor'], 'densidad': anterior_densidad['valor'],
                         'desde': comparacion_desde, 'hasta': comparacion_hasta},
        },
        confianza=confianza,
    )


# ─────────────────────────────────────────────────────────────────────────
# 3. Métricas de cumplimiento (solo tipo_cadencia != libre) — §5.3
# ─────────────────────────────────────────────────────────────────────────

def ventana_cumplimiento(gesto, fecha_hasta):
    """Las métricas de cumplimiento nunca miran antes de
    cadencia_configurada_en (§2.2/§5 del contrato)."""
    if gesto.cadencia_configurada_en is None:
        return None
    return max(_como_fecha(gesto.fecha_inicio), _como_fecha(gesto.cadencia_configurada_en)), fecha_hasta


@requiere_cultivo
def oportunidades_previstas(gesto, fecha_referencia=None):
    """M8 — solo diaria/dias_concretos."""
    if gesto.tipo_cadencia not in (Gesto.CADENCIA_DIARIA, Gesto.CADENCIA_DIAS_CONCRETOS):
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_APLICABLE)
    ventana = ventana_cumplimiento(gesto, fecha_referencia or timezone.localdate())
    if ventana is None:
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_CONFIGURADA)

    ledger = construir_ledger_diario(gesto, *ventana)
    previstos = [d for d in ledger if d['estado'] in (EstadoDia.PREVISTO_CUMPLIDO, EstadoDia.PREVISTO_NO_CUMPLIDO)]
    return _resultado(
        valor=len(previstos), confianza=_confianza(len(previstos), len(ledger)),
        fechas_usadas=[d['fecha'] for d in ledger], dias_excluidos=_dias_excluidos_de(ledger),
    )


@requiere_cultivo
def oportunidades_cumplidas(gesto, fecha_referencia=None):
    """M9 — subconjunto de M8 con RegistroGesto cumplido."""
    if gesto.tipo_cadencia not in (Gesto.CADENCIA_DIARIA, Gesto.CADENCIA_DIAS_CONCRETOS):
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_APLICABLE)
    ventana = ventana_cumplimiento(gesto, fecha_referencia or timezone.localdate())
    if ventana is None:
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_CONFIGURADA)

    ledger = construir_ledger_diario(gesto, *ventana)
    cumplidos = [d['fecha'] for d in ledger if d['estado'] == EstadoDia.PREVISTO_CUMPLIDO]
    previstos = [d for d in ledger if d['estado'] in (EstadoDia.PREVISTO_CUMPLIDO, EstadoDia.PREVISTO_NO_CUMPLIDO)]
    return _resultado(
        valor=len(cumplidos), confianza=_confianza(len(previstos), len(ledger)),
        registros_usados=cumplidos, fechas_usadas=[d['fecha'] for d in ledger],
        dias_excluidos=_dias_excluidos_de(ledger),
    )


@requiere_cultivo
def adherencia(gesto, fecha_referencia=None):
    """M10 — M9 / M8, válido solo con M8 >= 4 oportunidades."""
    m8 = oportunidades_previstas(gesto, fecha_referencia)
    if m8['valor'] is None:
        return m8
    if m8['valor'] < _UMBRAL_OPORTUNIDADES_MINIMAS:
        return _resultado(
            valor=None, confianza='insuficiente', motivo_no_calculable=MotivoNoCalculable.MUESTRA_INSUFICIENTE,
            fechas_usadas=m8['explicacion']['fechas_usadas'],
        )
    m9 = oportunidades_cumplidas(gesto, fecha_referencia)
    return _resultado(
        valor=round(m9['valor'] / m8['valor'], 4),
        confianza=_confianza(m8['valor'], len(m8['explicacion']['fechas_usadas'])),
        registros_usados=m9['explicacion']['registros_usados'],
        fechas_usadas=m8['explicacion']['fechas_usadas'],
        dias_excluidos=m8['explicacion']['dias_excluidos'],
    )


def _semanas_calendario(fecha_desde, fecha_hasta):
    """Semanas lun-dom que intersecan [fecha_desde, fecha_hasta],
    devueltas como (lunes, domingo) completos (aunque se salgan del rango)."""
    lunes = fecha_desde - timedelta(days=fecha_desde.weekday())
    semanas = []
    while lunes <= fecha_hasta:
        semanas.append((lunes, lunes + timedelta(days=6)))
        lunes += timedelta(days=7)
    return semanas


def _clasificar_semana(gesto, lunes, domingo, fecha_referencia):
    ledger = construir_ledger_diario(gesto, lunes, domingo)
    objetivo = gesto.frecuencia_semanal_objetivo

    if lunes <= fecha_referencia <= domingo and fecha_referencia < domingo:
        return {'lunes': lunes, 'domingo': domingo, 'clasificacion': 'semana_en_curso',
                'cumplidos_hasta_ahora': sum(1 for d in ledger if d['fecha'] <= fecha_referencia and d['cumplido']),
                'objetivo': objetivo}

    dias_pausado = sum(1 for d in ledger if d['estado'] == EstadoDia.PAUSADO)
    dias_fuera = sum(1 for d in ledger if d['estado'] == EstadoDia.FUERA_DE_VIDA)
    dias_no_observado = sum(1 for d in ledger if d['estado'] == EstadoDia.NO_OBSERVADO)
    dias_activos_disponibles = 7 - dias_pausado - dias_fuera
    cumplidos = sum(1 for d in ledger if d['cumplido'])

    if dias_activos_disponibles < objetivo:
        clasificacion = 'semana_no_evaluable'
        cumplida = None
    elif dias_pausado == 0 and dias_fuera == 0 and dias_no_observado == 0:
        clasificacion = 'semana_completa'
        cumplida = cumplidos >= objetivo
    else:
        clasificacion = 'semana_parcial_alcanzable'
        cumplida = cumplidos >= objetivo

    return {
        'lunes': lunes, 'domingo': domingo, 'clasificacion': clasificacion, 'cumplida': cumplida,
        'dias_activos_disponibles': dias_activos_disponibles, 'cumplidos': cumplidos, 'objetivo': objetivo,
    }


@requiere_cultivo
def evaluacion_semanal(gesto, fecha_referencia=None):
    """M11 — solo tipo_cadencia == 'semanal'. Clasificación de 4 estados
    por semana; la tasa principal usa exclusivamente semana_completa."""
    if gesto.tipo_cadencia != Gesto.CADENCIA_SEMANAL:
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_APLICABLE)
    fecha_referencia = fecha_referencia or timezone.localdate()
    ventana = ventana_cumplimiento(gesto, fecha_referencia)
    if ventana is None:
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_CONFIGURADA)

    semanas = [
        _clasificar_semana(gesto, lunes, domingo, fecha_referencia)
        for lunes, domingo in _semanas_calendario(*ventana)
    ]

    completas = [s for s in semanas if s['clasificacion'] == 'semana_completa']
    cumplidas = [s for s in completas if s['cumplida']]
    parciales_alcanzables = [s for s in semanas if s['clasificacion'] == 'semana_parcial_alcanzable']
    no_evaluables = [s for s in semanas if s['clasificacion'] == 'semana_no_evaluable']
    en_curso = next((s for s in semanas if s['clasificacion'] == 'semana_en_curso'), None)

    tasa_principal = (len(cumplidas) / len(completas)) if completas else None
    confianza = 'insuficiente' if len(completas) < _UMBRAL_OPORTUNIDADES_MINIMAS else (
        'alta' if len(completas) >= 8 else 'media'
    )

    return _resultado(
        valor={
            'tasa_principal': round(tasa_principal, 4) if tasa_principal is not None else None,
            'semanas_completas': len(completas),
            'semanas_cumplidas': len(cumplidas),
            'semanas_parciales_alcanzables': parciales_alcanzables,
            'semanas_no_evaluables': no_evaluables,
            'semana_en_curso': en_curso,
        },
        confianza=confianza,
    )


@requiere_cultivo
def incumplimientos_observados(gesto, fecha_referencia=None):
    """M12 — diaria/dias_concretos: días previsto_no_cumplido. semanal:
    semanas completas no cumplidas. libre: no calculable."""
    if gesto.tipo_cadencia == Gesto.CADENCIA_LIBRE:
        return _no_calculable(MotivoNoCalculable.CADENCIA_LIBRE)

    if gesto.tipo_cadencia == Gesto.CADENCIA_SEMANAL:
        m11 = evaluacion_semanal(gesto, fecha_referencia)
        if m11['valor'] is None:
            return m11
        incumplidas = m11['valor']['semanas_completas'] - m11['valor']['semanas_cumplidas']
        return _resultado(valor=incumplidas, confianza=m11['confianza'])

    ventana = ventana_cumplimiento(gesto, fecha_referencia or timezone.localdate())
    if ventana is None:
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_CONFIGURADA)
    ledger = construir_ledger_diario(gesto, *ventana)
    incumplidos = [d['fecha'] for d in ledger if d['estado'] == EstadoDia.PREVISTO_NO_CUMPLIDO]
    previstos = [d for d in ledger if d['estado'] in (EstadoDia.PREVISTO_CUMPLIDO, EstadoDia.PREVISTO_NO_CUMPLIDO)]
    return _resultado(
        valor=len(incumplidos), confianza=_confianza(len(previstos), len(ledger)),
        registros_usados=incumplidos,
    )


@requiere_cultivo
def recuperacion(gesto, fecha_referencia=None):
    """M13 — definición distinta por cadencia (§5.3). Nunca usa la
    palabra 'recaída' (reservada a TriggerHabito/suelto) ni infiere causa:
    solo cuenta oportunidades/semanas transcurridas."""
    if gesto.tipo_cadencia == Gesto.CADENCIA_LIBRE:
        return _no_calculable(MotivoNoCalculable.CADENCIA_LIBRE)

    fecha_referencia = fecha_referencia or timezone.localdate()
    ventana = ventana_cumplimiento(gesto, fecha_referencia)
    if ventana is None:
        return _no_calculable(MotivoNoCalculable.CADENCIA_NO_CONFIGURADA)

    if gesto.tipo_cadencia == Gesto.CADENCIA_SEMANAL:
        m11 = evaluacion_semanal(gesto, fecha_referencia)
        if m11['valor'] is None:
            return m11
        secuencia = [s for s in _todas_las_semanas_ordenadas(gesto, ventana, fecha_referencia)
                     if s['clasificacion'] in ('semana_completa', 'semana_parcial_alcanzable')]
        recuperaciones, pendiente = _contar_recuperaciones(secuencia, key_incumplida=lambda s: s['cumplida'] is False,
                                                             key_cumplida=lambda s: s['cumplida'] is True)
        unidad = 'semanas'
    else:
        ledger = construir_ledger_diario(gesto, *ventana)
        secuencia = [d for d in ledger if d['estado'] in (EstadoDia.PREVISTO_CUMPLIDO, EstadoDia.PREVISTO_NO_CUMPLIDO)]
        recuperaciones, pendiente = _contar_recuperaciones(
            secuencia,
            key_incumplida=lambda d: d['estado'] == EstadoDia.PREVISTO_NO_CUMPLIDO,
            key_cumplida=lambda d: d['estado'] == EstadoDia.PREVISTO_CUMPLIDO,
        )
        unidad = 'dias_previstos' if gesto.tipo_cadencia == Gesto.CADENCIA_DIARIA else 'oportunidades_previstas'

    if not recuperaciones and pendiente is None:
        return _no_calculable(MotivoNoCalculable.SIN_RECUPERACION_AUN)

    valor = {
        'unidad': unidad,
        'recuperaciones': recuperaciones,
        'mediana': statistics.median(recuperaciones) if recuperaciones else None,
        'incumplimiento_pendiente_de_recuperar': pendiente,
    }
    if not recuperaciones and pendiente is not None:
        return _resultado(valor=valor, confianza='insuficiente',
                           motivo_no_calculable=MotivoNoCalculable.SIN_RECUPERACION_AUN)
    return _resultado(valor=valor, confianza='media' if len(recuperaciones) < 3 else 'alta')


def _todas_las_semanas_ordenadas(gesto, ventana, fecha_referencia):
    return [_clasificar_semana(gesto, lunes, domingo, fecha_referencia)
            for lunes, domingo in _semanas_calendario(*ventana)]


def _contar_recuperaciones(secuencia_ordenada, key_incumplida, key_cumplida):
    """Recorre una secuencia cronológica de entradas 'previstas' y cuenta,
    desde el primer incumplimiento de cada racha, cuántas entradas
    transcurren (incluidos incumplimientos adicionales, que también son
    oportunidades transcurridas sin recuperar) hasta la siguiente
    cumplida. Devuelve (lista_de_conteos, pendiente_o_None)."""
    recuperaciones = []
    contando = False
    contador = 0
    for entrada in secuencia_ordenada:
        if not contando:
            if key_incumplida(entrada):
                contando = True
                contador = 0
            continue
        contador += 1
        if key_cumplida(entrada):
            recuperaciones.append(contador)
            contando = False

    pendiente = contador if contando else None
    return recuperaciones, pendiente


# ─────────────────────────────────────────────────────────────────────────
# 4. Métricas contextuales — declaradas no calculables (§5.4)
# ─────────────────────────────────────────────────────────────────────────

METRICAS_CONTEXTUALES = ('facilitador', 'obstaculo', 'senal_real', 'energia_percibida',
                          'version_minima', 'motivo_retorno')


@requiere_cultivo
def metrica_contextual(gesto, nombre):
    if nombre not in METRICAS_CONTEXTUALES:
        raise ValueError(f"'{nombre}' no es una métrica contextual reconocida: {METRICAS_CONTEXTUALES}")
    return _no_calculable('sin_modelo_de_captura')

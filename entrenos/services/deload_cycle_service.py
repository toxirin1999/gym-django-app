"""Autoridad única del ciclo de descarga compartido Gym/Hyrox."""

import copy
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from entrenos.models import CicloDeload, GymDecisionLog


POLITICA_V1 = {
    'version': 1,
    'gym': {'restar_series': 1, 'min_series': 2, 'rpe_max': 7},
    'hyrox': {'factor': 0.55},
}


def obtener_ciclo_activo(cliente, hoy=None):
    hoy = hoy or timezone.localdate()
    cerrar_ciclos_vencidos(hoy, cliente=cliente)
    return (CicloDeload.objects.filter(
        cliente=cliente, estado=CicloDeload.ESTADO_ACTIVO,
        fecha_inicio__lte=hoy, fecha_fin_prevista__gte=hoy,
    ).order_by('-fecha_inicio', '-pk').first())


def _notificar(ciclo, evento):
    """La voz se delega al sistema JOI; aquí no existe copy de usuario."""
    try:
        from joi.services import generar_mensaje_joi
        trigger = 'decision_plan' if evento == 'apertura' else 'resultado_intervencion'
        generar_mensaje_joi(ciclo.cliente, trigger, {
            'evento': f'deload_{evento}', 'causa': ciclo.causa,
            'resultado': ciclo.resultado, 'ciclo_id': ciclo.pk,
        })
    except Exception:
        pass


@transaction.atomic
def abrir_ciclo_deload(cliente, causa, *, metrica='', umbral=None, valor=None,
                       evidencia=None, hoy=None):
    """Abre como máximo un ciclo por cliente, también en MySQL (lock + comprobación)."""
    hoy = hoy or timezone.localdate()
    type(cliente).objects.select_for_update().get(pk=cliente.pk)
    existente = (CicloDeload.objects.select_for_update()
                 .filter(cliente=cliente, estado=CicloDeload.ESTADO_ACTIVO)
                 .order_by('-pk').first())
    if existente and existente.fecha_fin_prevista < hoy:
        existente.estado = CicloDeload.ESTADO_CERRADO
        existente.fecha_cierre = hoy
        existente.resultado = 'insuficiente'
        existente.motivo_cierre = 'expiracion_al_reabrir'
        existente.save(update_fields=['estado', 'fecha_cierre', 'resultado', 'motivo_cierre', 'actualizado_en'])
        transaction.on_commit(lambda c=existente: _notificar(c, 'cierre'))
        existente = None
    if existente:
        return existente, False
    dias = 9 if causa == CicloDeload.CAUSA_TSB_HYROX else 7
    ciclo = CicloDeload.objects.create(
        cliente=cliente, causa=causa, fecha_inicio=hoy,
        fecha_fin_prevista=hoy + timedelta(days=dias - 1), metrica=metrica,
        umbral=umbral, valor_apertura=valor, evidencia=evidencia or {},
        politica_snapshot=copy.deepcopy(POLITICA_V1),
    )
    GymDecisionLog.objects.create(
        cliente=cliente, ejercicio='global', ejercicio_normalizado='global',
        accion='deload', motivo=f'CicloDeload:{ciclo.pk}', confianza='alta',
    )
    transaction.on_commit(lambda: _notificar(ciclo, 'apertura'))
    return ciclo, True


def aplicar_overlay_gym(cliente, ejercicios, hoy=None):
    ciclo = obtener_ciclo_activo(cliente, hoy)
    resultado = copy.deepcopy(ejercicios)
    if not ciclo:
        return resultado
    politica = ciclo.politica_snapshot.get('gym', POLITICA_V1['gym'])
    for ejercicio in resultado:
        if ejercicio.get('_deload_cycle_id') == ciclo.pk:
            continue
        series = int(ejercicio.get('series', 3))
        rpe = int(ejercicio.get('rpe_objetivo', 8))
        ejercicio['series'] = max(politica['min_series'], series - politica['restar_series'])
        ejercicio['rpe_objetivo'] = min(politica['rpe_max'], rpe)
        ejercicio['deload'] = True
        ejercicio['_deload_cycle_id'] = ciclo.pk
    return resultado


def aplicar_overlay_hyrox(cliente, metricas, hoy=None):
    ciclo = obtener_ciclo_activo(cliente, hoy)
    resultado = copy.deepcopy(metricas or {})
    if not ciclo or resultado.get('_deload_cycle_id') == ciclo.pk:
        return resultado
    factor = ciclo.politica_snapshot.get('hyrox', POLITICA_V1['hyrox'])['factor']
    if 'series' in resultado:
        for serie in resultado['series']:
            if 'reps' in serie:
                serie['reps'] = max(1, round(int(serie['reps']) * factor))
    for campo in ('distancia_km', 'distancia_m'):
        if campo in resultado:
            resultado[campo] = round(float(resultado[campo]) * factor, 2)
    resultado['_deload_cycle_id'] = ciclo.pk
    return resultado


def _evaluar_resultado(ciclo):
    if not ciclo.metrica or ciclo.valor_apertura is None:
        return 'insuficiente', {}
    try:
        if ciclo.metrica == 'tsb':
            from hyrox.models import HyroxObjective
            from hyrox.training_engine import HyroxLoadManager
            objetivo = HyroxObjective.objects.filter(cliente=ciclo.cliente, estado='activo').first()
            actual = HyroxLoadManager.calcular_ctl_atl_tsb(objetivo).get('tsb') if objetivo else None
            if actual is None:
                return 'insuficiente', {}
            return ('favorable' if actual > ciclo.valor_apertura else 'fallido'), {'tsb': actual}
        if ciclo.metrica in ('rpe_medio', 'energia_media'):
            from entrenos.models import EntrenoRealizado, EjercicioRealizado
            entrenos = EntrenoRealizado.objects.filter(
                cliente=ciclo.cliente, fecha__range=(ciclo.fecha_inicio, ciclo.fecha_fin_prevista)
            )
            if ciclo.metrica == 'energia_media':
                valores = list(entrenos.exclude(energia_pre_sesion__isnull=True)
                               .values_list('energia_pre_sesion', flat=True))
                favorable = lambda actual: actual > ciclo.valor_apertura
            else:
                valores = list(EjercicioRealizado.objects.filter(
                    entreno__in=entrenos, rpe__isnull=False).values_list('rpe', flat=True))
                favorable = lambda actual: actual < ciclo.valor_apertura
            if not valores:
                return 'insuficiente', {}
            actual = sum(float(v) for v in valores) / len(valores)
            return ('favorable' if favorable(actual) else 'fallido'), {ciclo.metrica: round(actual, 2)}
    except Exception:
        return 'insuficiente', {}
    return 'insuficiente', {}


@transaction.atomic
def cerrar_ciclos_vencidos(hoy=None, cliente=None):
    hoy = hoy or timezone.localdate()
    qs = CicloDeload.objects.select_for_update().filter(
        estado=CicloDeload.ESTADO_ACTIVO, fecha_fin_prevista__lt=hoy,
    )
    if cliente is not None:
        qs = qs.filter(cliente=cliente)
    ciclos = list(qs)
    for ciclo in ciclos:
        resultado, evidencia_cierre = _evaluar_resultado(ciclo)
        ciclo.estado = CicloDeload.ESTADO_CERRADO
        ciclo.fecha_cierre = hoy
        ciclo.resultado = resultado
        ciclo.motivo_cierre = 'expiracion'
        ciclo.evidencia = {**ciclo.evidencia, 'cierre': evidencia_cierre}
        ciclo.save(update_fields=['estado', 'fecha_cierre', 'resultado', 'motivo_cierre', 'evidencia', 'actualizado_en'])
        transaction.on_commit(lambda c=ciclo: _notificar(c, 'cierre'))
    return ciclos

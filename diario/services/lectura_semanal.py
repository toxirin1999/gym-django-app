"""Agregación y generación canónica de la revisión semanal del Diario."""
from collections import Counter
from datetime import timedelta
import logging

from django.core.cache import cache
from django.utils import timezone

from diario.models import (
    Gesto,
    Interaccion,
    InteraccionSombra,
    ProsocheDiario,
    ReflexionLibre,
    RegistroGesto,
    SeguimientoVires,
)
from diario.services.estado_diario import tiene_apertura_manana, tiene_cierre_noche
from joi.models import MensajeJOI
from joi.services import generar_mensaje_joi


logger = logging.getLogger(__name__)


def periodo_semana_completa(fecha_referencia=None):
    """Devuelve la última semana cerrada (lunes-domingo) y su clave estable."""
    hoy = fecha_referencia or timezone.localdate()
    fin = hoy - timedelta(days=hoy.weekday() + 1)
    inicio = fin - timedelta(days=6)
    return inicio, fin, f'{inicio.isoformat()}_{fin.isoformat()}'


def _periodo(inicio, fin):
    return {
        'inicio': inicio.isoformat(),
        'fin': fin.isoformat(),
        'clave': f'{inicio.isoformat()}_{fin.isoformat()}',
    }


def buscar_revision_semanal(usuario, clave):
    return MensajeJOI.objects.filter(
        user=usuario,
        trigger='resumen_semanal',
        contexto__periodo__clave=clave,
    ).first()


def agregar_semana(usuario, dias=7, inicio=None, fin=None):
    """Agrega señales acotadas sin inferir identidad, causalidad ni intención."""
    if inicio is None and fin is None:
        fin = timezone.localdate()
        inicio = fin - timedelta(days=dias - 1)
    elif inicio is None or fin is None:
        raise ValueError('inicio y fin deben proporcionarse juntos')
    if inicio > fin:
        raise ValueError('inicio no puede ser posterior a fin')
    n_dias = (fin - inicio).days + 1

    entradas = list(ProsocheDiario.objects.filter(
        prosoche_mes__usuario=usuario, fecha__range=(inicio, fin),
    ).order_by('fecha'))
    n_aperturas = sum(tiene_apertura_manana(e) for e in entradas)
    n_cierres = sum(tiene_cierre_noche(e) for e in entradas)
    n_con_joi = sum(bool(e.respuesta_joi_cierre) for e in entradas)

    vires = list(SeguimientoVires.objects.filter(usuario=usuario, fecha__range=(inicio, fin)))
    cuerpos = Counter(v.cuerpo_cierre for v in vires if v.cuerpo_cierre)
    energia_baja = sum(bool(v.nivel_energia and v.nivel_energia <= 2) for v in vires)

    registros = list(RegistroGesto.objects.filter(
        gesto__usuario=usuario, fecha__range=(inicio, fin),
    ).select_related('gesto').order_by('fecha')[:60])
    gestos_nombres = list(Gesto.objects.filter(
        usuario=usuario, estado='activo',
    ).values_list('nombre', flat=True)[:8])
    gestos = {
        'activos': gestos_nombres,
        'cumplidos': sum(r.estado == 'cumplido' for r in registros),
        'fallados': sum(r.estado == 'fallado' for r in registros),
    }

    sombras = list(InteraccionSombra.objects.filter(
        persona_interina__usuario=usuario, fecha__range=(inicio, fin),
    ).select_related('persona_interina').order_by('fecha')[:30])
    interacciones = list(Interaccion.objects.filter(
        usuario=usuario, fecha__range=(inicio, fin),
    ).prefetch_related('personas').order_by('fecha')[:20])
    nombres = [s.persona_interina.nombre[:60] for s in sombras]
    for interaccion in interacciones:
        nombres.extend(p.nombre[:60] for p in list(interaccion.personas.all())[:4])
    conteo_personas = Counter(nombres)
    simbiosis = {
        'interacciones': len(sombras) + len(interacciones),
        'personas_mencionadas': [nombre for nombre, _ in conteo_personas.most_common(8)],
        'personas_repetidas': [nombre for nombre, n in conteo_personas.most_common(8) if n >= 2],
        'tipos': dict(Counter(
            [s.tipo_interaccion for s in sombras] + [i.tipo_interaccion for i in interacciones]
        )),
        'aprendizajes': (
            [s.aprendizaje[:240] for s in sombras if s.aprendizaje]
            + [i.aprendizaje[:240] for i in interacciones if i.aprendizaje]
        )[:6],
    }

    reflexiones = list(ReflexionLibre.objects.filter(
        usuario=usuario, fecha__date__range=(inicio, fin),
    ).values('titulo', 'contenido').order_by('fecha')[:12])
    logos = {
        'reflexiones': len(reflexiones),
        'titulos': [(r['titulo'] or 'Sin título')[:80] for r in reflexiones[:6]],
        'extractos': [r['contenido'][:240] for r in reflexiones[:4] if r['contenido']],
    }

    gym_items = []
    try:
        from entrenos.services.resumen_semanal_service import get_resumen_semanal_gym
        gym_items = get_resumen_semanal_gym(usuario.cliente_perfil, inicio=inicio, fin=fin) or []
    except Exception:
        logger.exception('No se pudo incorporar el resumen gym a la revisión semanal')
    gym = {'items': [
        {'tipo': str(i.get('tipo', ''))[:30], 'texto': str(i.get('texto', ''))[:240]}
        for i in gym_items[:10]
    ]}

    presencia = {
        'aperturas': n_aperturas,
        'cierres': n_cierres,
        'cierres_con_respuesta': n_con_joi,
        'energia_baja_dias': energia_baja,
        'cuerpos': dict(cuerpos),
        'dias': [
            {
                'fecha': e.fecha.isoformat(),
                'direccion': e.persona_quiero_ser[:240],
                'fue_bien': e.que_ha_ido_bien[:240],
                'puedo_mejorar': e.que_puedo_mejorar[:240],
                'reflexion': e.reflexiones_dia[:320],
                'estado_animo': e.estado_animo,
            }
            for e in entradas[:7]
        ],
    }
    hay_senales = bool(
        n_aperturas or n_cierres or vires or registros or sombras or interacciones
        or reflexiones or gym['items']
    )
    periodo = _periodo(inicio, fin)
    cuerpo_frecuente = cuerpos.most_common(1)[0][0] if cuerpos else None
    return {
        'version_contrato': 1,
        'periodo': periodo,
        'presencia': presencia,
        'gestos': gestos,
        'simbiosis': simbiosis,
        'logos': logos,
        'gym': gym,
        'hay_senales': hay_senales,
        # Compatibilidad con consumidores anteriores de agregar_semana.
        'n_aperturas': n_aperturas,
        'n_cierres': n_cierres,
        'n_con_joi': n_con_joi,
        'n_dias': n_dias,
        'energia_baja_dias': energia_baja,
        'cuerpos': dict(cuerpos),
        'cuerpo_frecuente': cuerpo_frecuente,
        'personas_repetidas': simbiosis['personas_repetidas'],
        'contrastes': [],
        'hay_datos': hay_senales,
        'inicio': inicio,
        'fin': fin,
    }


def generar_revision_semanal(cliente, inicio=None, fin=None):
    """Genera una sola revisión por periodo; devuelve ``None`` si falla o no hay señales."""
    if inicio is None and fin is None:
        inicio, fin, clave = periodo_semana_completa()
    elif inicio is not None and fin is not None:
        clave = _periodo(inicio, fin)['clave']
    else:
        raise ValueError('inicio y fin deben proporcionarse juntos')

    existente = buscar_revision_semanal(cliente.user, clave)
    if existente:
        return existente

    lock_key = f'joi:revision-semanal:{cliente.user_id}:{clave}'
    if not cache.add(lock_key, 'generando', timeout=180):
        return buscar_revision_semanal(cliente.user, clave)
    try:
        datos = agregar_semana(cliente.user, inicio=inicio, fin=fin)
        if not datos['hay_senales']:
            return None
        mensaje = generar_mensaje_joi(cliente, 'resumen_semanal', datos)
        if mensaje is None:
            logger.error('JOI no generó la revisión semanal user=%s periodo=%s', cliente.user_id, clave)
        return mensaje
    except Exception:
        logger.exception('Falló la revisión semanal user=%s periodo=%s', cliente.user_id, clave)
        return None
    finally:
        cache.delete(lock_key)

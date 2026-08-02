import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from ..models import (
    CierreNocturnoOperacion, Gesto, Interaccion, InteraccionSombra,
    PersonaImportante, PersonaInterina, ProsocheDiario, ProsocheMes,
    ReflexionLibre, RegistroGesto, SeguimientoVires,
)


class ConflictoVersionCierre(Exception):
    def __init__(self, version_actual):
        self.version_actual = version_actual
        super().__init__(f'Versión de cierre obsoleta; actual={version_actual}')


@dataclass
class ResultadoCierre:
    entrada: ProsocheDiario
    operacion: CierreNocturnoOperacion
    cambio: bool
    replay: bool = False


def _hash_payload(payload):
    normalizado = {
        'reflexion_libre': payload.get('reflexion_libre', '').strip(),
        'friccion_no': int(payload['friccion_no']),
        'cuerpo_cierre': payload.get('cuerpo_cierre', ''),
        'estado_animo_noche': int(payload['estado_animo_noche']),
        'habitos_completados': sorted(set(payload.get('habitos_completados') or [])),
        'simbiosis_respuesta': payload.get('simbiosis_respuesta', '').strip(),
        'simbiosis_pregunta': payload.get('simbiosis_pregunta', '').strip(),
    }
    serializado = json.dumps(normalizado, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    if isinstance(payload.get('analisis_cierre'), dict):
        normalizado['analisis_cierre'] = payload['analisis_cierre']
    return normalizado, hashlib.sha256(serializado.encode()).hexdigest()


@transaction.atomic
def ejecutar_cierre_nocturno(*, usuario, fecha, payload, idempotency_key, expected_version):
    normalizado, payload_hash = _hash_payload(payload)
    mes, _ = ProsocheMes.objects.get_or_create(
        usuario=usuario, mes=fecha.strftime('%B'), año=fecha.year,
    )
    entrada, _ = ProsocheDiario.objects.get_or_create(prosoche_mes=mes, fecha=fecha)
    entrada = ProsocheDiario.objects.select_for_update().get(pk=entrada.pk)

    replay = CierreNocturnoOperacion.objects.filter(
        entrada=entrada, idempotency_key=idempotency_key
    ).first()
    if replay:
        return ResultadoCierre(entrada, replay, replay.result_version is not None, True)

    if entrada.cierre_payload_hash == payload_hash and entrada.cierre_version > 0:
        canonical = CierreNocturnoOperacion.objects.filter(
            entrada=entrada, payload_hash=payload_hash,
            result_version=entrada.cierre_version,
        ).first()
        op = CierreNocturnoOperacion.objects.create(
            entrada=entrada, idempotency_key=idempotency_key,
            expected_version=expected_version, result_version=None,
            payload_hash=payload_hash, estado='noop',
            enrichment_payload=normalizado,
            resultado={
                'active_version': entrada.cierre_version,
                'canonical_operation_id': canonical.pk if canonical else None,
            },
            completed_at=timezone.now(),
        )
        return ResultadoCierre(entrada, op, False)
    if entrada.cierre_version != expected_version:
        raise ConflictoVersionCierre(entrada.cierre_version)

    nueva_version = entrada.cierre_version + 1
    op = CierreNocturnoOperacion.objects.create(
        entrada=entrada, idempotency_key=idempotency_key,
        expected_version=expected_version, result_version=nueva_version,
        payload_hash=payload_hash, enrichment_payload=normalizado,
    )

    entrada.reflexiones_dia = normalizado['reflexion_libre']
    entrada.estado_animo_noche = normalizado['estado_animo_noche']
    entrada.cierre_version = nueva_version
    entrada.cierre_payload_hash = payload_hash
    if entrada.cierre_confirmado_en is None:
        entrada.cierre_confirmado_en = timezone.now()
    entrada.save()

    vires, _ = SeguimientoVires.objects.get_or_create(usuario=usuario, fecha=fecha)
    vires.nivel_estres = normalizado['friccion_no']
    vires.cuerpo_cierre = normalizado['cuerpo_cierre']
    vires.save(update_fields=['nivel_estres', 'cuerpo_cierre'])

    activos = Gesto.objects.filter(usuario=usuario, estado='activo')
    deseados = set(normalizado['habitos_completados'])
    RegistroGesto.objects.filter(gesto__in=activos, fecha=fecha).exclude(
        gesto_id__in=deseados
    ).delete()
    for gesto in activos.filter(pk__in=deseados):
        RegistroGesto.objects.update_or_create(
            gesto=gesto, fecha=fecha, defaults={'estado': 'cumplido'}
        )
    return ResultadoCierre(entrada, op, True)


def operacion_canonica(operacion):
    canonical_id = (operacion.resultado or {}).get('canonical_operation_id')
    if canonical_id:
        return CierreNocturnoOperacion.objects.get(pk=canonical_id)
    return operacion


def _texto_comparable(texto):
    """Normaliza diferencias triviales para no aprender dos veces lo mismo."""
    texto = unicodedata.normalize('NFKC', texto or '').casefold()
    return ' '.join(re.findall(r'\w+', texto, flags=re.UNICODE))


def _manual_activo_equivalente(usuario, texto):
    objetivo = _texto_comparable(texto)
    if not objetivo:
        return False
    return any(
        _texto_comparable(entrada) == objetivo
        for entrada in usuario.manual_david.filter(activa=True).values_list('entrada', flat=True)
    )


_PERSONA_SNAPSHOT_FIELDS = (
    'estado', 'veces_mencionada', 'menciones_desde_descarte',
)
_MANUAL_SNAPSHOT_FIELDS = (
    'entrada', 'origen', 'tipo', 'confianza', 'estado', 'activa',
    'fuente_mensaje_id', 'ultima_evidencia', 'notas_revision',
    'hipotesis_contraria',
)


def _snapshot(instance, fields):
    return {field: getattr(instance, field) for field in fields}


def _coincide_snapshot(instance, snapshot):
    return all(getattr(instance, field, object()) == value for field, value in snapshot.items())


def _desactivar_manual_si_seguro(usuario, item, *, legacy=False):
    from joi.models import ManualDavid

    manual_id = item if legacy else item.get('id')
    manual = ManualDavid.objects.select_for_update().filter(pk=manual_id, user=usuario).first()
    if not manual:
        return
    if legacy:
        seguro = (
            manual.origen == 'patron_detectado'
            and manual.activa and manual.estado == 'activa'
            and manual.ultima_evidencia is None and not manual.notas_revision
        )
    else:
        seguro = item.get('created') and _coincide_snapshot(manual, item.get('after') or {})
    if seguro:
        manual.activa = False
        manual.estado = 'descartada'
        manual.save(update_fields=['activa', 'estado'])


def _retraer_resultado(usuario, resultado):
    """Retira solo las proyecciones atribuibles a un resultado completado."""
    resultado = resultado or {}
    ledger = resultado.get('ledger') if resultado.get('schema_version') == 2 else None

    reflexiones = ledger.get('reflexiones', []) if ledger else resultado.get('reflexiones', [])
    reflexion_ids = [item.get('id') if isinstance(item, dict) else item for item in reflexiones]
    ReflexionLibre.objects.filter(usuario=usuario, pk__in=reflexion_ids).delete()

    interacciones = ledger.get('interacciones', []) if ledger else resultado.get('interacciones', [])
    interaccion_ids = [item.get('id') if isinstance(item, dict) else item for item in interacciones]
    Interaccion.objects.filter(usuario=usuario, pk__in=interaccion_ids).delete()

    sombras = ledger.get('sombras', []) if ledger else resultado.get('sombras', [])
    sombra_ids = [item.get('id') if isinstance(item, dict) else item for item in sombras]
    InteraccionSombra.objects.filter(
        persona_interina__usuario=usuario, pk__in=sombra_ids,
    ).delete()

    manuales = ledger.get('manual', []) if ledger else resultado.get('manual', [])
    for item in manuales:
        _desactivar_manual_si_seguro(usuario, item, legacy=ledger is None)

    # En legacy no hay estado anterior fiable: no se infieren contadores.
    if not ledger:
        return
    for item in reversed(ledger.get('personas_interinas', [])):
        persona = PersonaInterina.objects.select_for_update().filter(
            pk=item.get('id'), usuario=usuario,
        ).first()
        if not persona or not _coincide_snapshot(persona, item.get('after') or {}):
            continue
        if item.get('created'):
            if persona.persona_importante_id is None and not persona.interacciones.exists():
                persona.delete()
        else:
            before = item.get('before') or {}
            for field in _PERSONA_SNAPSHOT_FIELDS:
                if field in before:
                    setattr(persona, field, before[field])
            persona.save(update_fields=list(before.keys()))


def _retraer_version_anterior(op, usuario):
    anterior = CierreNocturnoOperacion.objects.select_for_update().filter(
        entrada_id=op.entrada_id,
        estado='completed',
        result_version__lt=op.result_version,
    ).order_by('-result_version').first()
    if not anterior:
        return
    _retraer_resultado(usuario, anterior.resultado)
    historico = dict(anterior.resultado or {})
    historico['retracted_by_version'] = op.result_version
    anterior.resultado = historico
    anterior.estado = 'superseded'
    anterior.save(update_fields=['resultado', 'estado', 'updated_at'])


def ejecutar_enriquecimiento_cierre(operacion_id):
    """IA fuera de locks; la proyección final se materializa una sola vez."""
    with transaction.atomic():
        op = CierreNocturnoOperacion.objects.select_for_update().select_related(
            'entrada__prosoche_mes__usuario'
        ).get(pk=operacion_id)
        if op.estado in ('completed', 'superseded', 'noop'):
            return op.resultado
        op.estado = 'processing'
        op.error = ''
        op.processing_started_at = timezone.now()
        op.save(update_fields=['estado', 'error', 'processing_started_at', 'updated_at'])
        payload = dict(op.enrichment_payload)
        usuario = op.entrada.prosoche_mes.usuario

    texto = payload.get('reflexion_libre', '')
    try:
        from joi.services import generar_respuesta_cierre
        analisis = payload.get('analisis_cierre')
        if analisis is None:  # compatibilidad con operaciones antiguas
            from .analisis_cierre_service import analizar_texto
            analisis = analizar_texto(texto)
        if analisis.get('estado') == 'no_disponible':
            raise RuntimeError('Análisis de cierre no disponible; se puede reintentar.')
        parseo = analisis.get('parseo') or {}
        personas = parseo.get('personas') or []
        enriquecido = analisis.get('enriquecido') or {}
        datos_joi = {
            **parseo, 'estado_animo': payload['estado_animo_noche'],
            'friccion_no': payload['friccion_no'],
            'micro_verdad': enriquecido.get('micro_verdad'),
        }
        cliente = getattr(usuario, 'cliente_perfil', None) or usuario
        respuesta = generar_respuesta_cierre(texto, datos_joi, cliente) if texto else ''
    except Exception as exc:
        with transaction.atomic():
            op = CierreNocturnoOperacion.objects.select_for_update().get(pk=operacion_id)
            op.estado = 'failed'
            op.error = str(exc)[:2000]
            op.save(update_fields=['estado', 'error', 'updated_at'])
        raise

    with transaction.atomic():
        op = CierreNocturnoOperacion.objects.select_for_update().select_related(
            'entrada__prosoche_mes__usuario'
        ).get(pk=operacion_id)
        if op.estado == 'completed':
            return op.resultado
        entrada = ProsocheDiario.objects.select_for_update().get(pk=op.entrada_id)
        if entrada.cierre_version != op.result_version:
            op.estado = 'superseded'
            op.resultado = {'active_version': entrada.cierre_version}
            op.completed_at = timezone.now()
            op.save(update_fields=['estado', 'resultado', 'completed_at', 'updated_at'])
            return op.resultado

        _retraer_version_anterior(op, usuario)
        ids = {'reflexiones': [], 'manual': [], 'interacciones': [], 'sombras': []}
        ledger = {
            'reflexiones': [], 'manual': [], 'interacciones': [],
            'sombras': [], 'personas_interinas': [],
        }
        etiquetas = ['cierre_dia', *(parseo.get('etiquetas') or [])]
        categoria_estoica = (enriquecido.get('categoria_estoica') or '').strip()
        if categoria_estoica and categoria_estoica not in etiquetas:
            etiquetas.append(categoria_estoica)
        if texto:
            reflexion = ReflexionLibre.objects.create(
                usuario=usuario, contenido=texto, tipo='espontanea',
                titulo=(enriquecido.get('titulo_logos') or '')[:200],
                etiquetas=','.join(etiquetas),
            )
            ids['reflexiones'].append(reflexion.pk)
            ledger['reflexiones'].append({'id': reflexion.pk})
        simbiosis_respuesta = payload.get('simbiosis_respuesta')
        if simbiosis_respuesta:
            reflexion = ReflexionLibre.objects.create(
                usuario=usuario, contenido=simbiosis_respuesta, tipo='crisis',
                titulo='Reflexión Simbiosis', etiquetas='simbiosis_respuesta',
            )
            ids['reflexiones'].append(reflexion.pk)
            ledger['reflexiones'].append({'id': reflexion.pk})

        from joi.models import ManualDavid
        micro = (enriquecido.get('micro_verdad') or '').strip()
        if len(micro) > 5 and not _manual_activo_equivalente(usuario, micro):
            manual = ManualDavid.objects.create(user=usuario, entrada=micro, origen='patron_detectado')
            ids['manual'].append(manual.pk)
            ledger['manual'].append({
                'id': manual.pk, 'created': True,
                'after': _snapshot(manual, _MANUAL_SNAPSHOT_FIELDS),
            })
        tipos = {choice[0] for choice in Interaccion.TIPO_INTERACCION_CHOICES}
        personas_permitidas = {
            (persona or '').strip().casefold() for persona in personas if (persona or '').strip()
        }
        personas_contadas = set()
        for item in enriquecido.get('interacciones') or []:
            nombre = (item.get('persona') or '').strip()
            identidad = nombre.casefold()
            if not nombre or identidad not in personas_permitidas:
                continue
            tipo = item.get('tipo') if item.get('tipo') in tipos else 'neutra'
            # Una persona archivada conserva su historial, pero ya no forma parte
            # del círculo activo. Si reaparece, vuelve a pasar por el radar y
            # requiere una reconfirmación explícita del usuario.
            persona = PersonaImportante.objects.filter(
                usuario=usuario,
                nombre__iexact=nombre,
                archivada=False,
            ).first()
            if persona:
                interaccion = Interaccion.objects.create(
                    usuario=usuario, titulo=(item.get('titulo') or nombre)[:200],
                    descripcion=item.get('descripcion') or '', mi_sentir=item.get('mi_sentir') or '',
                    aprendizaje=item.get('aprendizaje') or '', tipo_interaccion=tipo,
                )
                interaccion.personas.add(persona)
                ids['interacciones'].append(interaccion.pk)
                ledger['interacciones'].append({'id': interaccion.pk})
            else:
                interina = PersonaInterina.objects.select_for_update().filter(
                    usuario=usuario, nombre__iexact=nombre,
                ).first()
                creada = interina is None
                if creada:
                    interina = PersonaInterina.objects.create(usuario=usuario, nombre=nombre)
                persona_ledger = {
                    'id': interina.pk, 'created': creada,
                    'before': None if creada else _snapshot(interina, _PERSONA_SNAPSHOT_FIELDS),
                }
                if not creada and identidad not in personas_contadas:
                    interina.veces_mencionada += 1
                    if interina.estado == 'descartada':
                        interina.menciones_desde_descarte += 1
                    interina.save(update_fields=[
                        'veces_mencionada', 'menciones_desde_descarte', 'ultima_deteccion',
                    ])
                sombra = InteraccionSombra.objects.create(
                    persona_interina=interina, descripcion=item.get('descripcion') or '',
                    mi_sentir=item.get('mi_sentir') or '', aprendizaje=item.get('aprendizaje') or '',
                    tipo_interaccion=tipo, friccion_no=payload['friccion_no'],
                    fecha=op.entrada.fecha,
                )
                personas_contadas.add(identidad)
                ids['sombras'].append(sombra.pk)
                ledger['sombras'].append({'id': sombra.pk, 'persona_interina_id': interina.pk})
                if creada:
                    nota = (
                        f"Entidad nueva detectada: '{nombre}'. "
                        'Pendiente de validación si se repite.'
                    )
                    if not _manual_activo_equivalente(usuario, nota):
                        manual = ManualDavid.objects.create(
                            user=usuario, entrada=nota, origen='patron_detectado',
                        )
                        ids['manual'].append(manual.pk)
                        ledger['manual'].append({
                            'id': manual.pk, 'created': True,
                            'after': _snapshot(manual, _MANUAL_SNAPSHOT_FIELDS),
                            'persona_interina_id': interina.pk,
                        })
                if (
                    interina.estado == 'descartada'
                    and interina.menciones_desde_descarte >= 2
                ):
                    interina.estado = 'sombra'
                    interina.menciones_desde_descarte = 0
                    interina.save(update_fields=['estado', 'menciones_desde_descarte'])
                elif interina.estado == 'sombra' and interina.veces_mencionada >= 2:
                    interina.estado = 'radar'
                    interina.save(update_fields=['estado'])
                interina.refresh_from_db()
                persona_ledger['after'] = _snapshot(interina, _PERSONA_SNAPSHOT_FIELDS)
                ledger['personas_interinas'].append(persona_ledger)

        resultado = {
            **ids, 'schema_version': 2, 'ledger': ledger,
            'respuesta_joi': respuesta or '',
            'propuesta_habito': enriquecido.get('propuesta_habito'),
            'simbiosis': {
                'personas': personas,
                'pregunta': payload.get('simbiosis_pregunta') or '',
                'respuesta': simbiosis_respuesta or '',
            },
        }
        entrada.etiquetas = ','.join(parseo.get('etiquetas') or [])
        entrada.respuesta_joi_cierre = respuesta or ''
        entrada.respuesta_joi_cierre_generada_en = timezone.now() if respuesta else None
        entrada.save(update_fields=['etiquetas', 'respuesta_joi_cierre', 'respuesta_joi_cierre_generada_en', 'fecha_actualizacion'])
        op.resultado = resultado
        op.estado = 'completed'
        op.completed_at = timezone.now()
        op.error = ''
        op.save(update_fields=['resultado', 'estado', 'completed_at', 'error', 'updated_at'])
        return resultado


# Compatibilidad temporal con callers/tests antiguos del núcleo.
def persistir_nucleo_cierre(usuario, fecha, entrada, texto_libre, friccion_raw,
                            cuerpo_raw, habitos_completados_raw, gestos_activos):
    """Adaptador temporal usado solo por tests históricos del núcleo.

    El flujo productivo usa ejecutar_cierre_nocturno; retirar junto con esos
    tests cuando se elimine definitivamente el contrato de Fase 2.
    """
    from .habitos_service import HabitosService
    try:
        ids = json.loads(habitos_completados_raw)
    except (TypeError, ValueError):
        ids = []
    with transaction.atomic():
        if friccion_raw or cuerpo_raw:
            vires, _ = SeguimientoVires.objects.get_or_create(usuario=usuario, fecha=fecha)
            try:
                if friccion_raw:
                    vires.nivel_estres = int(friccion_raw)
                if cuerpo_raw:
                    vires.cuerpo_cierre = cuerpo_raw
                vires.save()
            except (TypeError, ValueError):
                pass
        if texto_libre:
            entrada.reflexiones_dia = texto_libre
            entrada.save()
        actuales = set(RegistroGesto.objects.filter(
            gesto__in=gestos_activos, fecha=fecha, estado='cumplido'
        ).values_list('gesto_id', flat=True))
        for gesto in gestos_activos:
            if (gesto.pk in ids) != (gesto.pk in actuales):
                HabitosService.toggle_dia(gesto, fecha)
        if entrada.cierre_confirmado_en is None:
            entrada.cierre_confirmado_en = timezone.now()
            entrada.save(update_fields=['cierre_confirmado_en'])

import json
import unicodedata
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.sesion_recomendada import MOTIVO_OMISION_RECONCILIACION


def _normalizar(valor):
    texto = unicodedata.normalize('NFKD', valor or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.casefold().split())


def _fecha_sesion(sesion):
    return sesion.pospuesta_hasta or sesion.fecha_prevista


def _fecha_entreno(entreno):
    return entreno.fecha_ejecucion or entreno.fecha


class Command(BaseCommand):
    help = 'Audita y reconcilia vínculos explícitos SesionProgramada↔EntrenoRealizado.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--cliente', type=int)
        parser.add_argument('--desde', type=str)
        parser.add_argument('--hasta', type=str)
        parser.add_argument('--dias', type=int, default=365)
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        hasta = timezone.localdate()
        if options['hasta']:
            try:
                hasta = date.fromisoformat(options['hasta'])
            except ValueError as exc:
                raise CommandError('--hasta debe usar YYYY-MM-DD') from exc
        desde = hasta - timedelta(days=options['dias'])
        if options['desde']:
            try:
                desde = date.fromisoformat(options['desde'])
            except ValueError as exc:
                raise CommandError('--desde debe usar YYYY-MM-DD') from exc
        if desde > hasta:
            raise CommandError('--desde no puede ser posterior a --hasta')

        qs = SesionProgramada.objects.select_related(
            'cliente', 'entreno_realizado', 'entreno_realizado__rutina', 'contrato_semanal',
        ).filter(
            Q(fecha_prevista__range=(desde, hasta)) |
            Q(pospuesta_hasta__range=(desde, hasta))
        ).order_by('id')
        if options['cliente']:
            if not Cliente.objects.filter(pk=options['cliente']).exists():
                raise CommandError('Cliente inexistente.')
            qs = qs.filter(cliente_id=options['cliente'])
        sesiones = list(qs[:options['limit']])
        conteos = {}
        aplicados = 0

        for sesion in sesiones:
            registro = self._clasificar(sesion)
            clasificacion = registro['classification']
            conteos[clasificacion] = conteos.get(clasificacion, 0) + 1
            if options['apply'] and clasificacion == 'omitted_before_due':
                with transaction.atomic():
                    bloqueada = (
                        SesionProgramada.objects.select_for_update()
                        .select_related(
                            'entreno_realizado', 'entreno_realizado__rutina', 'contrato_semanal',
                        )
                        .get(pk=sesion.pk)
                    )
                    vigente = self._clasificar(bloqueada)
                    if vigente['classification'] == 'omitted_before_due':
                        bloqueada.estado = SesionProgramada.ESTADO_PENDIENTE
                        bloqueada.motivo_estado = ''
                        bloqueada.save(update_fields=['estado', 'motivo_estado', 'actualizada_en'])
                        registro['applied'] = True
                        registro['estado_nuevo'] = SesionProgramada.ESTADO_PENDIENTE
                        aplicados += 1
                self.stdout.write(json.dumps(registro, default=str, sort_keys=True))
                continue
            match_seguro = (
                clasificacion == 'unique_safe_match'
                or (
                    clasificacion == 'completed_missing_fk'
                    and registro.get('match_status') == 'unique_safe_match'
                )
            )
            puede_completar = sesion.estado in (
                SesionProgramada.ESTADO_PENDIENTE,
                SesionProgramada.ESTADO_COMPLETADA,
            )
            if options['apply'] and match_seguro and puede_completar:
                with transaction.atomic():
                    bloqueada = SesionProgramada.objects.select_for_update().get(pk=sesion.pk)
                    entreno = EntrenoRealizado.objects.select_for_update().get(
                        pk=registro['entreno_realizado_id'],
                    )
                    if bloqueada.entreno_realizado_id is None:
                        bloqueada.estado = SesionProgramada.ESTADO_COMPLETADA
                        bloqueada.fecha_realizada = _fecha_entreno(entreno)
                        bloqueada.entreno_realizado = entreno
                        bloqueada.save(update_fields=[
                            'estado', 'fecha_realizada', 'entreno_realizado', 'actualizada_en',
                        ])
                        registro['applied'] = True
                        aplicados += 1
            self.stdout.write(json.dumps(registro, default=str, sort_keys=True))

        self.stdout.write(json.dumps({
            'tipo_registro': 'resumen', 'modo': 'apply' if options['apply'] else 'dry-run',
            'solo_lectura': not options['apply'], 'desde': desde, 'hasta': hasta,
            'evaluados': len(sesiones), 'aplicados': aplicados,
            'conteos_por_clasificacion': conteos,
        }, default=str, sort_keys=True))

    def _clasificar(self, sesion):
        base = {
            'tipo_registro': 'sesion_programada',
            'sesion_programada_id': sesion.pk,
            'cliente_id': sesion.cliente_id,
            'fecha_efectiva': _fecha_sesion(sesion),
            'fecha_prevista': sesion.fecha_prevista,
            'pospuesta_hasta': sesion.pospuesta_hasta,
            'estado_previo': sesion.estado,
            'motivo': sesion.motivo_estado or '',
            'motivo_estado': sesion.motivo_estado or '',
        }
        if sesion.entreno_realizado_id:
            if sesion.entreno_realizado.cliente_id != sesion.cliente_id:
                return {**base, 'classification': 'inconsistent/cross-client'}
            return {
                **base, 'classification': 'already_linked',
                'entreno_realizado_id': sesion.entreno_realizado_id,
            }
        if sesion.contrato_semanal_id and sesion.contrato_semanal.cliente_id != sesion.cliente_id:
            return {**base, 'classification': 'inconsistent/cross-client'}

        identidad = _normalizar(sesion.nombre_sesion)
        candidatos = []
        if identidad:
            for entreno in EntrenoRealizado.objects.select_related('rutina').filter(
                cliente_id=sesion.cliente_id,
            ):
                if (
                    _fecha_entreno(entreno) == _fecha_sesion(sesion)
                    and _normalizar(entreno.rutina.nombre if entreno.rutina_id else '') == identidad
                ):
                    candidatos.append(entreno)
        if len(candidatos) == 1:
            registro = {
                **base, 'classification': 'unique_safe_match',
                'estado_previo': sesion.estado,
                'entreno_realizado_id': candidatos[0].pk,
            }
            if sesion.estado == SesionProgramada.ESTADO_COMPLETADA:
                registro.update({
                    'classification': 'completed_missing_fk',
                    'match_status': 'unique_safe_match',
                })
            return registro
        if len(candidatos) > 1:
            registro = {
                **base, 'classification': 'ambiguous',
                'candidate_ids': [item.pk for item in candidatos],
            }
            if sesion.estado == SesionProgramada.ESTADO_COMPLETADA:
                registro.update({
                    'classification': 'completed_missing_fk',
                    'match_status': 'ambiguous',
                })
            return registro
        if (
            sesion.estado == SesionProgramada.ESTADO_OMITIDA_SISTEMA
            and sesion.motivo_estado == MOTIVO_OMISION_RECONCILIACION
            and sesion.entreno_realizado_id is None
            and sesion.fecha_realizada is None
            and not candidatos
            and timezone.localtime(sesion.actualizada_en).date() < _fecha_sesion(sesion)
        ):
            return {
                **base,
                'classification': 'omitted_before_due',
                'actualizada_fecha_local': timezone.localtime(sesion.actualizada_en).date(),
            }
        if sesion.estado == SesionProgramada.ESTADO_COMPLETADA:
            return {
                **base,
                'classification': 'completed_missing_fk',
                'match_status': 'no_match',
            }
        return {**base, 'classification': 'no_match'}

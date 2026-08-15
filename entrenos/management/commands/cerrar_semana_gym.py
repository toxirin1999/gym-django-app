"""Previsualiza o persiste el cierre causal de una semana Gym."""

import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import ContratoSemanalGym
from entrenos.services.evaluacion_semanal_gym_service import (
    ContratoNoMaterializado,
    EvaluacionSemanalRevisada,
    SemanaAbierta,
    _snapshot,
    evaluar_y_persistir_contrato_semanal_gym,
)


class Command(BaseCommand):
    help = 'Cierra un contrato semanal Gym. Es dry-run salvo que se indique --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', required=True, type=int, help='ID del cliente.')
        parser.add_argument('--semana', type=date.fromisoformat, help='Lunes en formato AAAA-MM-DD.')
        parser.add_argument('--apply', action='store_true', dest='aplicar', help='Persiste la evaluación.')

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        inicio_actual = hoy - timedelta(days=hoy.weekday())
        semana = options['semana'] or inicio_actual - timedelta(days=7)
        if semana.weekday() != 0:
            raise CommandError('--semana debe ser un lunes.')
        if hoy <= semana + timedelta(days=6):
            raise CommandError(f'La semana {semana.isoformat()} todavía está abierta.')

        try:
            cliente = Cliente.objects.get(pk=options['cliente'])
        except Cliente.DoesNotExist as exc:
            raise CommandError(f'No existe el cliente {options["cliente"]}.') from exc
        try:
            contrato = ContratoSemanalGym.objects.prefetch_related('sesiones').get(
                cliente=cliente, semana=semana,
            )
        except ContratoSemanalGym.DoesNotExist as exc:
            raise CommandError(
                f'No existe contrato para el cliente {cliente.pk} en {semana.isoformat()}.'
            ) from exc
        if contrato.sesiones.count() != contrato.objetivo_sesiones:
            raise CommandError(
                f'Contrato incompleto: contiene {contrato.sesiones.count()} de '
                f'{contrato.objetivo_sesiones} sesiones.'
            )

        try:
            if options['aplicar']:
                evaluacion = evaluar_y_persistir_contrato_semanal_gym(contrato, hoy=hoy)
                resultado = {
                    'cliente_id': cliente.pk,
                    'estado_cumplimiento': evaluacion.estado_cumplimiento,
                    'evaluacion_id': evaluacion.pk,
                    'modo': 'apply',
                    'semana': semana.isoformat(),
                    'sesiones_completadas': evaluacion.sesiones_completadas,
                }
            else:
                evidencia = _snapshot(contrato)
                resultado = {
                    'cliente_id': cliente.pk,
                    'estado_cumplimiento': evidencia['estado_cumplimiento'],
                    'evaluacion_id': None,
                    'modo': 'dry-run',
                    'semana': semana.isoformat(),
                    'sesiones_completadas': evidencia['sesiones_completadas'],
                }
        except (SemanaAbierta, ContratoNoMaterializado, EvaluacionSemanalRevisada) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(resultado, ensure_ascii=False, sort_keys=True))

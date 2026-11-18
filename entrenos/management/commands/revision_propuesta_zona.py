"""Límite de revisión de un ajuste de volumen validado, con vista previa de lo que ocurrirá.

    python manage.py revision_propuesta_zona 2 1                       # estado y vista previa
    python manage.py revision_propuesta_zona 2 1 --fijar 2026-12-06 --aplicar
    python manage.py revision_propuesta_zona 2 1 --prolongar-hasta 2027-01-31 --motivo "..." --aplicar
    python manage.py revision_propuesta_zona 2 1 --retirar --motivo "..." --aplicar

Sin ``--aplicar`` no se guarda nada. La vista previa calcula el plan de cada semana con el ajuste que
estaría vigente el lunes de esa semana (el planificador usa la fecha del día en que se genera).
"""
from datetime import date, timedelta
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def _f(texto):
    try:
        return date.fromisoformat(texto)
    except ValueError as exc:
        raise CommandError(f'Fecha no válida: {texto} (usa AAAA-MM-DD)') from exc


AVISO_PROYECCION = (
    'Proyección con las reglas y los datos actuales. No reconstruye lo prescrito en semanas '
    'pasadas o en curso. Las sesiones futuras pueden cambiar al generarse. Para consultar lo '
    'prescrito, usa las versiones guardadas de cada sesión.')


class Command(BaseCommand):
    help = 'Fija, decide y previsualiza la revisión de un ajuste de volumen validado.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('propuesta_id', type=int)
        parser.add_argument('--fijar', help='fecha límite de revisión AAAA-MM-DD')
        parser.add_argument('--prolongar-hasta', dest='prolongar_hasta')
        parser.add_argument('--retirar', action='store_true')
        parser.add_argument('--motivo', default='')
        parser.add_argument('--aplicar', action='store_true')
        parser.add_argument('--semanas', nargs='*', default=None,
                            help='lunes a previsualizar AAAA-MM-DD (por defecto, alrededor de la revisión)')

    def handle(self, *args, cliente_id, propuesta_id, fijar, prolongar_hasta, retirar, motivo, aplicar,
               semanas, **opts):
        from django.utils import timezone

        from clientes.models import Cliente
        from entrenos.models import PropuestaZonaGym
        from entrenos.services.propuesta_zona_service import decidir_revision, fijar_revision

        try:
            cliente = Cliente.objects.get(pk=cliente_id)
            p = PropuestaZonaGym.objects.get(pk=propuesta_id, cliente=cliente)
        except (Cliente.DoesNotExist, PropuestaZonaGym.DoesNotExist) as exc:
            raise CommandError(str(exc))
        hoy = timezone.localdate()
        try:
            cambia = False
            # Se escribe siempre dentro de una transacción que se deshace si no hay --aplicar:
            # así la vista previa lee exactamente el estado que quedaría.
            with transaction.atomic():
                if fijar:
                    fijar_revision(p, _f(fijar), motivo or 'fin del bloque actual', hoy=hoy)
                    cambia = True
                if prolongar_hasta:
                    decidir_revision(p, 'prolongar', motivo, hasta=_f(prolongar_hasta), hoy=hoy)
                    cambia = True
                if retirar:
                    decidir_revision(p, 'retirar', motivo, hoy=hoy)
                    cambia = True
                if cambia and not aplicar:
                    self.stdout.write('(Vista previa de la decisión: no se guarda nada; añade --aplicar.)')
                self._informe(cliente, p, hoy, semanas)
                if cambia and not aplicar:
                    transaction.set_rollback(True)
        except ValueError as exc:
            raise CommandError(str(exc))

    def _informe(self, cliente, p, hoy, semanas):
        from entrenos.services import volumen_grupo_service as vol
        from entrenos.services.marcador_semanal_service import series_plan_semana

        revision = (p.deteccion or {}).get('revision')
        self.stdout.write(f'Propuesta {p.pk} · {p.nombre_zona} · resultado {p.resultado}')
        if not revision:
            self.stdout.write('Sin revisión fijada: rige la regla antigua de 182 días tras el fin '
                              f'({p.fin + timedelta(days=vol.VIGENCIA_VALIDADA_DIAS):%d/%m/%Y}).')
        else:
            self.stdout.write(f"Revisión: {revision.get('estado')} · fecha {revision.get('fecha')} · "
                              f"hasta {revision.get('hasta')} · motivo: {revision.get('motivo')}")
            for pendiente in revision.get('pendientes') or []:
                self.stdout.write(f'PENDIENTE DE RESOLVER · {pendiente}')
            for d in revision.get('decisiones') or []:
                self.stdout.write(f"Decisión {d['decidida_el']}: {d['decision']} (hasta {d['hasta']}) · {d['motivo']}")

        # Vista previa: qué ajuste rige y qué plan sale cada semana, con el ajuste del lunes de esa semana.
        limite = _f((revision or {}).get('hasta') or (revision or {}).get('fecha')) if revision else None
        base = limite or hoy
        lunes_base = base - timedelta(days=base.weekday())
        lunes = [_f(x) for x in semanas] if semanas else [
            hoy - timedelta(days=hoy.weekday()), lunes_base - timedelta(days=7), lunes_base,
            lunes_base + timedelta(days=7), lunes_base + timedelta(days=14)]
        self.stdout.write('\nVista previa (solo lectura):')
        self.stdout.write(AVISO_PROYECCION)
        real = vol.series_por_grupo
        zona = p.zona
        vistos = set()
        for lun in lunes:
            if lun in vistos:
                continue
            vistos.add(lun)
            ajuste = vol.ajustes_volumen(cliente, lun)
            item = (ajuste or {}).get(zona)
            rige = f"{item['series']:+d} series ({'; '.join(item['motivos'])})" if item else 'sin ajuste'
            with mock.patch.object(vol, 'series_por_grupo',
                                   side_effect=lambda c, f, incluir_pausadas=False, _l=lun: real(c, _l, incluir_pausadas)):
                plan, sesiones = series_plan_semana(cliente, lun)
            total = plan.get(zona)
            por_sesion = [(s['nombre'][:6], s['series'].get(zona)) for s in sesiones if s['series'].get(zona)]
            self.stdout.write(f'{lun:%d/%m} · {zona}: {total} series a la semana · {por_sesion} · ajuste: {rige}')
        pendientes = vol.revisiones_pendientes(cliente, hoy)
        self.stdout.write(f"\nRevisiones pendientes de decisión hoy: {len(pendientes)}")

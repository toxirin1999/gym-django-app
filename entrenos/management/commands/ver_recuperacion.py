"""Solo lectura: lo que la app sabe de tu recuperación y de tus partidos.

Uso:  python manage.py ver_recuperacion 2
      python manage.py ver_recuperacion 2 --fecha 2026-10-25

Muestra los datos del reloj de los últimos días, tus medias de 28 días, la
lectura de hoy (verde / ámbar / rojo y la frase) y los partidos de fútbol de
los últimos 120 días con lo que trae Strava. No guarda nada.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Muestra (sin guardar nada) la lectura de recuperación y el esfuerzo de los partidos.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--fecha', default=None)

    def handle(self, *args, **opts):
        from clientes.models import BitacoraDiaria, Cliente
        from entrenos.models import ActividadRealizada
        from entrenos.services.recuperacion_service import (
            _carga, _datos_partido, esfuerzo_futbol, lectura_recuperacion,
        )

        cliente = Cliente.objects.get(pk=opts['cliente_id'])
        hoy = date.fromisoformat(opts['fecha']) if opts['fecha'] else timezone.localdate()

        self.stdout.write(f'=== RELOJ (últimos 10 días hasta {hoy}) ===')
        for b in BitacoraDiaria.objects.filter(
            cliente=cliente, fecha__gte=hoy - timedelta(days=9), fecha__lte=hoy,
        ).order_by('fecha', 'pk'):
            self.stdout.write(f'  {b.fecha}  variabilidad {b.hrv_ms or "—"}  pulso {b.fc_reposo or "—"}  '
                              f'sueño {b.horas_sueno or "—"} h  energía {b.energia_subjetiva or "—"}')

        lectura = lectura_recuperacion(cliente, hoy)
        self.stdout.write('\n=== LECTURA DE HOY ===')
        if lectura is None:
            self.stdout.write('  Sin datos del reloj hoy: el plan decide como siempre.')
        else:
            self.stdout.write(f"  Nivel: {lectura['nivel']}  señales: {', '.join(lectura['senales']) or 'ninguna'}")
            self.stdout.write(f"  Medias 28 días: {lectura['medias'] or 'aún no hay (hacen falta 5 días)'}")
            self.stdout.write(f"  Frase: {lectura['frase']}")

        self.stdout.write('\n=== FÚTBOL (120 días) ===')
        for a in ActividadRealizada.objects.filter(
            cliente=cliente, tipo='futbol', fecha__gte=hoy - timedelta(days=120), fecha__lte=hoy,
        ).order_by('fecha', 'id'):
            p = _datos_partido(a)
            tipo, carga = _carga(p)
            self.stdout.write(f"  {p['fecha']}  {p['minutos'] or '—'} min  pulso medio {p['pulso_medio'] or '—'}  "
                              f"esfuerzo Strava {p['esfuerzo'] or '—'}  → carga {carga or '—'} ({tipo or 'sin datos'})")
        futbol = esfuerzo_futbol(cliente, hoy)
        if futbol:
            self.stdout.write(f"\n  Hoy: {futbol['nivel']} → {futbol['frase']}")
        self.stdout.write('\n(No se ha guardado nada.)')

"""Solo lectura: las series detrás de los récords que no cuadran (2-nov-2026).

Uso:  python manage.py ver_records_dudosos 2

Enseña, serie a serie y con fecha, lo guardado para:
- Elevación de Gemelos en Prensa desde el 1-ago (¿159 kg o 105?).
- Elevaciones Laterales en Polea con 18 kg o más (¿21 kg × 6?).
- Dips (Fondos en Pecho) con 100 kg o más y Press Banca con Mancuernas con 95 o más.
No cambia nada.
"""

from datetime import date

from django.core.management.base import BaseCommand

CONSULTAS = [
    ('Elevación de Gemelos en Prensa', 0, date(2026, 8, 1)),
    ('Elevaciones Laterales en Polea', 18, None),
    ('Dips (Fondos en Pecho)', 100, None),
    ('Press Banca con Mancuernas', 95, None),
]


class Command(BaseCommand):
    help = 'Series guardadas detrás de los récords dudosos (no cambia nada).'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)

    def handle(self, *args, **opts):
        from entrenos.models import EjercicioRealizado, SerieRealizada

        cid = opts['cliente_id']
        for nombre, minimo, desde in CONSULTAS:
            self.stdout.write(f'\n== {nombre}')
            series = SerieRealizada.objects.filter(
                entreno__cliente_id=cid, ejercicio__nombre__iexact=nombre,
            ).select_related('entreno').order_by('entreno__fecha', 'serie_numero')
            if desde:
                series = series.filter(entreno__fecha__gte=desde)
            if minimo:
                ids = series.filter(peso_kg__gte=minimo).values_list('entreno_id', flat=True)
                series = series.filter(entreno_id__in=list(ids))
            for s in series:
                self.stdout.write(
                    f'  {s.entreno.fecha} entreno {s.entreno_id} · serie {s.serie_numero}: '
                    f'{s.peso_kg} kg × {s.repeticiones}  RPE {s.rpe_real}  '
                    f'(total {s.peso_total_kg}, tipo {s.tipo_carga})'
                )
            resumen = EjercicioRealizado.objects.filter(
                entreno__cliente_id=cid, nombre_ejercicio__iexact=nombre,
            ).order_by('-peso_kg').values_list('entreno__fecha', 'entreno_id', 'peso_kg', 'repeticiones')[:3]
            for fecha, eid, peso, reps in resumen:
                self.stdout.write(f'  [resumen] {fecha} entreno {eid}: {peso} kg × {reps}')



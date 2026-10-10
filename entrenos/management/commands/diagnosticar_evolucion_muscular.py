from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from entrenos.services.evolucion_muscular_service import (
    NOMBRES_ZONA,
    UMBRAL_DUDOSO,
    comparar_ejercicios,
)


def _fmt_ventana(v):
    if not v:
        return '—'
    tipo = v['tipo_carga'] or 'sin tipo'
    extra = ''
    if v['multiplicador'] or v['peso_total_kg']:
        extra = f" ×{v['multiplicador'] or '?'} total={v['peso_total_kg'] or '—'}"
    return (f"{v['peso_kg']:g} kg × {v['reps']} ({tipo}{extra}) "
            f"e1RM {v['e1rm']:.1f} · {v['fecha']:%d/%m/%y}")


class Command(BaseCommand):
    help = ('Muestra, ejercicio a ejercicio, la mejor marca de cada periodo que usa '
            'el mapa de evolución muscular. Solo lectura.')

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--dias', type=int, default=90)
        parser.add_argument('--zona', choices=sorted(NOMBRES_ZONA), default=None)
        parser.add_argument('--solo-dudosos', action='store_true',
                            help=f'Solo cambios de más de ±{UMBRAL_DUDOSO:g} %%.')

    def handle(self, *args, **options):
        cliente = Cliente.objects.filter(pk=options['cliente']).first()
        if cliente is None:
            raise CommandError(f'No existe el cliente {options["cliente"]}.')

        ejercicios = comparar_ejercicios(cliente, dias=options['dias'])
        if options['zona']:
            ejercicios = [e for e in ejercicios if e['zona'] == options['zona']]
        if options['solo_dudosos']:
            ejercicios = [e for e in ejercicios if e['dudoso']]

        self.stdout.write(
            f"Cliente {cliente.pk} · periodo {options['dias']} días · "
            f"umbral de dato dudoso ±{UMBRAL_DUDOSO:g} %"
        )
        zona_actual = None
        for e in ejercicios:
            if e['zona'] != zona_actual:
                zona_actual = e['zona']
                self.stdout.write(f"\n== {NOMBRES_ZONA[zona_actual]}")
            if e['pct'] is None:
                marca = 'sin comparar'
            else:
                marca = f"{e['pct']:+.1f} %" + ('  ⚠ DUDOSO' if e['dudoso'] else '')
            self.stdout.write(f"  {e['ejercicio']}: {marca}")
            self.stdout.write(f"     antes: {_fmt_ventana(e['antes'])}")
            self.stdout.write(f"     ahora: {_fmt_ventana(e['ahora'])}")

        n_dudosos = sum(1 for e in ejercicios if e['dudoso'])
        self.stdout.write(f"\n{len(ejercicios)} ejercicios · {n_dudosos} dudosos")

"""Solo lectura: qué habría dicho el estado de carga cada día.

Uso:  python manage.py ver_estado_carga 2
      python manage.py ver_estado_carga 2 --dias 30
      python manage.py ver_estado_carga 2 --hoy        (solo hoy, con detalle)

Para cada día: la carga de la semana frente a tu semana normal, cómo amaneciste
según el reloj, y la respuesta (descansa / te pasas / puedes dar más / vas
bien…). Va a la sombra: no cambia nada de la app.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

SIGLAS = {'rojo': 'R', 'ambar': 'A', 'verde': 'V', 'normal': 'N', 'sin_referencia': '?',
          'parada': 'P', None: '·'}


class Command(BaseCommand):
    help = 'Muestra (sin guardar nada) la respuesta del estado de carga día a día.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--dias', type=int, default=21)
        parser.add_argument('--hoy', action='store_true')

    def handle(self, *args, **opts):
        from clientes.models import Cliente
        from entrenos.services.estado_carga_service import TITULOS, estado_carga

        cliente = Cliente.objects.get(pk=opts['cliente_id'])
        hoy = timezone.localdate()

        if opts['hoy']:
            e = estado_carga(cliente, hoy)
            c = e['carga']
            self.stdout.write(f"=== {hoy} · {TITULOS[e['respuesta']]} ===")
            self.stdout.write(e['frase'])
            self.stdout.write(f"\nCarga: semana {c['semana']} · semana normal {c['normal']} · ratio {c['ratio']}")
            self.stdout.write('Cuerpo (hoy → hace 13 días): '
                              + ' '.join(SIGLAS.get(d['nivel'], '?') for d in e['cuerpo']))
            self.stdout.write('   R rojo · A ámbar · V fresco · N normal · ? sin media · P parada · · sin dato')
            self.stdout.write(f"Malos en 5 días: {e['malos_5']}/{e['dias_5']} · buenos en 14: "
                              f"{e['buenos_14']}/{e['dias_14']}")
            es = e['esfuerzo']
            self.stdout.write(f"RPE medio 2 semanas: {es['ahora']} (antes {es['antes']})"
                              f"{' · subiendo' if es['subiendo'] else ''}")
            self.stdout.write(f"Molestias 14 días: {', '.join(e['molestias']) or 'ninguna'}")
            self.stdout.write('\n(No se ha guardado nada.)')
            return

        self.stdout.write('fecha       semana  normal  ratio  cuerpo-hoy  respuesta')
        for i in range(opts['dias'] - 1, -1, -1):
            d = hoy - timedelta(days=i)
            e = estado_carga(cliente, d)
            c = e['carga']
            ratio = f"{c['ratio']:.2f}" if c['ratio'] is not None else '  —'
            self.stdout.write(
                f"{d}  {c['semana']:>6}  {c['normal']:>6}  {ratio:>5}  "
                f"{SIGLAS.get(e['cuerpo'][0]['nivel'], '?'):>10}  {TITULOS[e['respuesta']]}"
            )
        self.stdout.write('\nCuerpo: R rojo · A ámbar · V fresco · N normal · ? sin media · P parada · · sin dato')
        self.stdout.write('Para el detalle de hoy: --hoy')
        self.stdout.write('(No se ha guardado nada.)')

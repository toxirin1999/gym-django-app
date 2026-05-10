from django.core.management.base import BaseCommand
from clientes.models import Cliente
from joi.services import generar_sintesis_joi


class Command(BaseCommand):
    help = 'Ejecuta el ciclo de síntesis autónoma de JOI para todos los usuarios activos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usuario',
            type=str,
            help='Ejecutar solo para un usuario concreto (username)',
        )

    def handle(self, *args, **options):
        import datetime
        from joi.models import MensajeJOI
        from entrenos.models import ActividadRealizada

        ahora = datetime.datetime.now()
        generados = 0
        silenciados = 0
        saltados = 0

        if options.get('usuario'):
            clientes = Cliente.objects.filter(
                user__username=options['usuario']
            ).select_related('user')
        else:
            clientes = Cliente.objects.select_related('user').all()

        for cliente in clientes:
            try:
                ultimo_msg = (
                    MensajeJOI.objects
                    .filter(user=cliente.user)
                    .order_by('-creado_en')
                    .first()
                )

                if ultimo_msg and not ultimo_msg.leido and ultimo_msg.trigger == 'sintesis_joi':
                    saltados += 1
                    continue

                ultimo_ts = ultimo_msg.creado_en if ultimo_msg else None
                trigger_activo = False

                # >48h de silencio
                if not ultimo_ts:
                    trigger_activo = True
                else:
                    ts_naive = ultimo_ts.replace(tzinfo=None)
                    if (ahora - ts_naive).total_seconds() > 48 * 3600:
                        trigger_activo = True

                # Nueva actividad física
                if not trigger_activo and ultimo_ts:
                    if ActividadRealizada.objects.filter(
                        cliente=cliente,
                        tipo__in=['gym', 'hyrox', 'carrera'],
                        fecha__gte=ultimo_ts.date(),
                    ).exists():
                        trigger_activo = True

                # Nueva entrada de diario (Prosoche o Logos)
                if not trigger_activo and ultimo_ts:
                    try:
                        from diario.models import ProsocheDiario, ReflexionLibre
                        limite_fecha = ultimo_ts.date()
                        if (
                            ProsocheDiario.objects.filter(
                                prosoche_mes__usuario=cliente.user,
                                fecha__gte=limite_fecha,
                            ).exists()
                            or
                            ReflexionLibre.objects.filter(
                                usuario=cliente.user, fecha__gte=ultimo_ts,
                            ).exists()
                        ):
                            trigger_activo = True
                    except Exception:
                        pass

                if not trigger_activo:
                    saltados += 1
                    continue

                resultado = generar_sintesis_joi(cliente)
                if resultado:
                    generados += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  {cliente.user.username}: "{resultado.mensaje[:60]}..."'
                        )
                    )
                else:
                    silenciados += 1
                    self.stdout.write(f'  {cliente.user.username}: [SILENCE]')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  {cliente.user.username}: ERROR — {e}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nResultado: {generados} mensajes | {silenciados} silencios | {saltados} saltados'
            )
        )

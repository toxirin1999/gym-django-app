from django.core.management.base import BaseCommand

from clientes.models import Cliente


class Command(BaseCommand):
    help = 'Genera la narrativa de bloque JOI para una fase de entrenamiento completada.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=str, required=True,
                            help='Username del cliente')
        parser.add_argument('--fase-id', type=int,
                            help='ID de FaseCliente concreta (opcional; por defecto usa la más reciente completada)')

    def handle(self, *args, **options):
        from clientes.models import FaseCliente
        from joi.services import generar_narrativa_bloque

        try:
            cliente = Cliente.objects.get(user__username=options['usuario'])
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Usuario '{options['usuario']}' no encontrado."))
            return

        if options.get('fase_id'):
            try:
                fase = FaseCliente.objects.get(id=options['fase_id'], cliente=cliente)
            except FaseCliente.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"FaseCliente id={options['fase_id']} no encontrada."))
                return
        else:
            # Fase más reciente con fecha_fin seteada
            fase = FaseCliente.objects.filter(
                cliente=cliente,
                fecha_fin__isnull=False,
            ).order_by('-fecha_fin').first()
            if not fase:
                self.stdout.write(self.style.ERROR("No hay fases completadas para este usuario."))
                return

        self.stdout.write(
            f"Generando narrativa de bloque para: {fase.get_fase_display()} "
            f"({fase.fecha_inicio} → {fase.fecha_fin})"
        )

        resultado = generar_narrativa_bloque(cliente, fase)

        if resultado:
            self.stdout.write(self.style.SUCCESS(f'\nMensaje generado (id={resultado.id}):'))
            self.stdout.write(resultado.mensaje)
        else:
            self.stdout.write(
                self.style.WARNING('No se generó mensaje — puede que ya exista uno para este periodo.')
            )

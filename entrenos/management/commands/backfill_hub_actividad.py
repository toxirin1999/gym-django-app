"""
Comando de backfill: puebla ActividadRealizada con todos los EntrenoRealizado
y HyroxSession existentes que aún no tienen registro en el hub.

Uso:
    python manage.py backfill_hub_actividad --settings=gymproject.settings_local
    python manage.py backfill_hub_actividad --dry-run --settings=gymproject.settings_local
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Backfill ActividadRealizada hub con EntrenoRealizado y HyroxSession existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se haría sin escribir en la BD',
        )

    def handle(self, *args, **options):
        from entrenos.models import EntrenoRealizado, ActividadRealizada

        dry_run = options['dry_run']
        creados_gym = 0
        ya_existian_gym = 0
        creados_hyrox = 0
        ya_existian_hyrox = 0

        # ── 1. Backfill EntrenoRealizado → hub ──────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n── Backfill EntrenoRealizado ──'))

        entrenos = EntrenoRealizado.objects.select_related(
            'cliente', 'rutina'
        ).prefetch_related('ejercicios_realizados').order_by('fecha')

        for entreno in entrenos:
            if ActividadRealizada.objects.filter(entreno_gym=entreno).exists():
                ya_existian_gym += 1
                continue

            # Calcular RPE medio
            rpe_medio = None
            try:
                rpes = [e.rpe for e in entreno.ejercicios_realizados.all() if e.rpe]
                if rpes:
                    rpe_medio = round(sum(rpes) / len(rpes), 1)
            except Exception:
                pass

            titulo = ''
            try:
                titulo = entreno.nombre_rutina_liftin or (
                    entreno.rutina.nombre if entreno.rutina else ''
                )
            except Exception:
                pass

            carga_ua = None
            if rpe_medio and entreno.duracion_minutos:
                carga_ua = round(rpe_medio * entreno.duracion_minutos, 1)

            if dry_run:
                self.stdout.write(
                    f'  [DRY-RUN] Crearía hub para entreno #{entreno.id} '
                    f'{entreno.cliente.nombre} {entreno.fecha} '
                    f'(carga_ua={carga_ua})'
                )
            else:
                with transaction.atomic():
                    ActividadRealizada.objects.create(
                        cliente=entreno.cliente,
                        tipo='gym',
                        titulo=titulo,
                        fecha=entreno.fecha,
                        hora_inicio=entreno.hora_inicio,
                        duracion_minutos=entreno.duracion_minutos,
                        volumen_kg=entreno.volumen_total_kg,
                        calorias=entreno.calorias_quemadas,
                        rpe_medio=rpe_medio,
                        carga_ua=carga_ua,
                        fuente='liftin' if entreno.fuente_datos == 'liftin' else 'manual',
                        entreno_gym=entreno,
                    )
            creados_gym += 1

        self.stdout.write(
            f'  Gym → Creados: {creados_gym} | Ya existían: {ya_existian_gym}'
        )

        # ── 2. Backfill HyroxSession (completadas) → hub ────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n── Backfill HyroxSession ──'))

        try:
            from hyrox.models import HyroxSession

            sesiones = HyroxSession.objects.filter(
                estado='completado'
            ).select_related('objective__cliente').order_by('fecha')

            for sesion in sesiones:
                if ActividadRealizada.objects.filter(sesion_hyrox=sesion).exists():
                    ya_existian_hyrox += 1
                    continue

                cliente = sesion.objective.cliente
                titulo = sesion.titulo or f'Hyrox — {sesion.fecha}'
                carga_ua = None
                if sesion.rpe_global and sesion.tiempo_total_minutos:
                    carga_ua = round(sesion.rpe_global * sesion.tiempo_total_minutos, 1)

                if dry_run:
                    self.stdout.write(
                        f'  [DRY-RUN] Crearía hub para HyroxSession #{sesion.id} '
                        f'{cliente.nombre} {sesion.fecha} (carga_ua={carga_ua})'
                    )
                else:
                    with transaction.atomic():
                        ActividadRealizada.objects.create(
                            cliente=cliente,
                            tipo='hyrox',
                            titulo=titulo,
                            fecha=sesion.fecha,
                            duracion_minutos=sesion.tiempo_total_minutos,
                            rpe_medio=sesion.rpe_global,
                            carga_ua=carga_ua,
                            fuente='hyrox_engine',
                            sesion_hyrox=sesion,
                        )
                creados_hyrox += 1

            self.stdout.write(
                f'  Hyrox → Creados: {creados_hyrox} | Ya existían: {ya_existian_hyrox}'
            )

        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Hyrox omitido: {e}'))

        # ── Resumen ──────────────────────────────────────────────────────────
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN completado. Sin cambios en BD.'))
        else:
            total = creados_gym + creados_hyrox
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Backfill completado: {total} registros creados en ActividadRealizada '
                    f'({creados_gym} gym + {creados_hyrox} hyrox)'
                )
            )

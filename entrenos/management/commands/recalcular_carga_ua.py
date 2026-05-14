from django.core.management.base import BaseCommand
from entrenos.models import ActividadRealizada


class Command(BaseCommand):
    help = 'Recalcula carga_ua en ActividadRealizada usando siempre sRPE × minutos'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, default=None,
                            help='ID de cliente; si se omite procesa todos')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra cambios sin guardar nada')
        parser.add_argument('--with-hr-estimation', action='store_true',
                            help='Estima RPE desde FC media cuando rpe_medio es None')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        cliente_id = options['cliente']
        with_hr = options['with_hr_estimation']

        qs = ActividadRealizada.objects.all().order_by('id')
        if cliente_id is not None:
            qs = qs.filter(cliente_id=cliente_id)

        # Caché de objetivos por cliente para evitar N queries
        _objetivo_cache = {}

        def _get_objetivo(cliente_id):
            if cliente_id not in _objetivo_cache:
                try:
                    from hyrox.models import HyroxObjective
                    _objetivo_cache[cliente_id] = (
                        HyroxObjective.objects.filter(cliente_id=cliente_id, estado='activo').first()
                    )
                except Exception:
                    _objetivo_cache[cliente_id] = None
            return _objetivo_cache[cliente_id]

        actualizados = 0
        sin_valor = 0
        cambios = []
        pendientes = []
        update_fields_set = {'carga_ua'}

        for act in qs.iterator():
            dur = act.duracion_minutos
            rpe = act.rpe_medio

            rpe_estimado = False
            if rpe is None and with_hr and act.hr_media and dur:
                try:
                    from hyrox.training_engine import HyroxLoadManager
                    objetivo = _get_objetivo(act.cliente_id)
                    rpe_calc = HyroxLoadManager.estimar_rpe_desde_fc(act.hr_media, objetivo)
                    if rpe_calc is not None:
                        rpe = rpe_calc
                        rpe_estimado = True
                except Exception:
                    pass

            if rpe is not None and dur is not None:
                nuevo = round(float(rpe) * float(dur), 1)
            elif dur is not None:
                nuevo = round(6.5 * float(dur), 1)
            else:
                nuevo = None

            anterior = act.carga_ua
            needs_save = False

            if nuevo is None:
                sin_valor += 1
                if anterior is not None:
                    cambios.append((abs(float(anterior)), act.id, act.fecha, anterior, nuevo))
                    act.carga_ua = None
                    needs_save = True
            elif anterior is None or abs(nuevo - float(anterior)) > 0.5:
                diff = abs(nuevo - float(anterior)) if anterior is not None else nuevo
                cambios.append((diff, act.id, act.fecha, anterior, nuevo))
                act.carga_ua = nuevo
                actualizados += 1
                needs_save = True

            if needs_save and rpe_estimado:
                act.rpe_medio = rpe
                update_fields_set.add('rpe_medio')

            if needs_save:
                pendientes.append(act)

        if not dry_run and pendientes:
            fields = ['carga_ua', 'rpe_medio'] if with_hr else ['carga_ua']
            ActividadRealizada.objects.bulk_update(pendientes, fields, batch_size=500)

        prefijo = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{prefijo}Actualizados: {actualizados} | Sin valor posible (quedan None): {sin_valor}'
        ))

        if cambios:
            top5 = sorted(cambios, key=lambda x: x[0], reverse=True)[:5]
            self.stdout.write('\nTop 5 mayores cambios:')
            for diff, aid, fecha, ant, nvo in top5:
                self.stdout.write(f'  id={aid} fecha={fecha} | {ant} → {nvo} (Δ {diff:.1f})')

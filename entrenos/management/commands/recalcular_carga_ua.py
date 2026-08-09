import json
from collections import Counter, defaultdict

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
        parser.add_argument('--audit', action='store_true',
                            help='Auditoría estructurada siempre de solo lectura')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        cliente_id = options['cliente']
        with_hr = options['with_hr_estimation']
        audit = options['audit']

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

        if audit:
            self._emitir_auditoria(qs, with_hr=with_hr, get_objetivo=_get_objetivo)
            return

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

    def _emitir_auditoria(self, qs, *, with_hr, get_objetivo):
        """Emite JSON Lines determinista y no persiste ningún cálculo."""
        por_fuente = defaultdict(Counter)
        por_tipo = defaultdict(Counter)
        metodos = Counter({
            'rpe_real': 0,
            'hr_estimado': 0,
            'fallback_6_5': 0,
            'no_calculable': 0,
        })
        bandas = Counter({
            'sin_propuesta': 0,
            'sin_carga_actual': 0,
            'actual_cero': 0,
            'menos_0_5x': 0,
            '0_5_a_0_8x': 0,
            '0_8_a_1_25x': 0,
            '1_25_a_2x': 0,
            '2_a_5x': 0,
            '5_a_9x': 0,
            '9_a_11x': 0,
            'mas_11x': 0,
        })
        cambios = []
        total = 0
        sin_valor = 0

        for act in qs.iterator():
            total += 1
            rpe = act.rpe_medio
            metodo = 'rpe_real' if rpe is not None else 'fallback_6_5'

            if rpe is None and with_hr and act.hr_media and act.duracion_minutos:
                try:
                    from hyrox.training_engine import HyroxLoadManager
                    estimado = HyroxLoadManager.estimar_rpe_desde_fc(
                        act.hr_media, get_objetivo(act.cliente_id)
                    )
                    if estimado is not None:
                        rpe = estimado
                        metodo = 'hr_estimado'
                except Exception:
                    pass

            if act.duracion_minutos is None:
                propuesta = None
                metodo = 'no_calculable'
            else:
                rpe_calculo = rpe if rpe is not None else 6.5
                propuesta = round(float(rpe_calculo) * float(act.duracion_minutos), 1)

            metodos[metodo] += 1
            actual = act.carga_ua
            cambia = (
                (propuesta is None and actual is not None)
                or (propuesta is not None and actual is None)
                or (
                    propuesta is not None
                    and actual is not None
                    and abs(propuesta - float(actual)) > 0.5
                )
            )
            if propuesta is None:
                sin_valor += 1

            for grupo in (por_fuente[act.fuente], por_tipo[act.tipo]):
                grupo['conteo'] += 1
                grupo['con_rpe' if act.rpe_medio is not None else 'sin_rpe'] += 1
                grupo['con_carga_actual' if actual is not None else 'sin_carga_actual'] += 1
                if cambia:
                    grupo['cambiarian'] += 1

            ratio = None
            if propuesta is None:
                bandas['sin_propuesta'] += 1
            elif actual is None:
                bandas['sin_carga_actual'] += 1
            elif float(actual) == 0:
                bandas['actual_cero'] += 1
            elif propuesta is not None:
                ratio = propuesta / float(actual)
                bandas[self._banda_ratio(ratio)] += 1

            if cambia:
                diferencia = abs((propuesta or 0.0) - float(actual or 0.0))
                cambios.append({
                    'carga_actual': actual,
                    'carga_propuesta': propuesta,
                    'diferencia_absoluta': round(diferencia, 1),
                    'duracion_minutos': act.duracion_minutos,
                    'fecha': act.fecha.isoformat(),
                    'fuente': act.fuente,
                    'id': act.id,
                    'metodo_calculo': metodo,
                    'ratio_propuesto_actual': round(ratio, 2) if ratio is not None else None,
                    'rpe': rpe,
                    'tipo_actividad': act.tipo,
                    'tipo_registro': 'top_cambio',
                })

        for fuente in sorted(por_fuente):
            self._json_line('grupo_fuente', por_fuente[fuente], fuente=fuente)
        for tipo_actividad in sorted(por_tipo):
            self._json_line(
                'grupo_tipo_actividad', por_tipo[tipo_actividad],
                tipo_actividad=tipo_actividad,
            )
        self._json_line('bandas_ratio', bandas=bandas)
        for cambio in sorted(
            cambios,
            key=lambda item: (-item['diferencia_absoluta'], item['id']),
        )[:5]:
            self.stdout.write(json.dumps(cambio, sort_keys=True, separators=(',', ':')))
        self._json_line(
            'resumen',
            total=total,
            cambiarian=len(cambios),
            sin_valor_posible=sin_valor,
            metodos_calculo=metodos,
            solo_lectura=True,
        )

    @staticmethod
    def _banda_ratio(ratio):
        if ratio < 0.5:
            return 'menos_0_5x'
        if ratio < 0.8:
            return '0_5_a_0_8x'
        if ratio < 1.25:
            return '0_8_a_1_25x'
        if ratio < 2:
            return '1_25_a_2x'
        if ratio < 5:
            return '2_a_5x'
        if ratio < 9:
            return '5_a_9x'
        if ratio <= 11:
            return '9_a_11x'
        return 'mas_11x'

    def _json_line(self, tipo_registro, valores=None, **extra):
        payload = {'tipo_registro': tipo_registro}
        if valores:
            payload.update({
                'conteo': valores['conteo'],
                'con_rpe': valores['con_rpe'],
                'sin_rpe': valores['sin_rpe'],
                'con_carga_actual': valores['con_carga_actual'],
                'sin_carga_actual': valores['sin_carga_actual'],
                'cambiarian': valores['cambiarian'],
            })
        for clave, valor in extra.items():
            payload[clave] = dict(valor) if isinstance(valor, Counter) else valor
        self.stdout.write(json.dumps(payload, sort_keys=True, separators=(',', ':')))

from django.core.management.base import BaseCommand
from django.db.models import Avg

from entrenos.models import SesionEntrenamiento

# Campos cuya desincronización, si es la ÚNICA presente, clasifica el
# snapshot como "solo series" (Phase Evolución/Data 5A).
CAMPOS_SERIES = {'series_totales', 'series_completadas'}


class Command(BaseCommand):
    help = (
        "Corrige snapshots SesionEntrenamiento desincronizados (zombis: "
        "duracion_minutos/ejercicios/series/volumen_sesion en 0 y rpe_medio "
        "vacío) usando EntrenoRealizado + EjercicioRealizado como fuente "
        "real. No modifica sesiones incompletas (es_sesion_incompleta=True), "
        "para las que 0/0/0/0/None es el estado correcto. Con "
        "--informe-impacto, calcula el impacto agregado del backfill sobre "
        "sesiones_perfectas/porcentaje_perfeccion sin escribir en BD. Con "
        "--aplicar, aplica el backfill real y muestra ese mismo informe "
        "antes/después (--dry-run tiene prioridad si se combina)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe en BD, solo reporta qué se corregiría.',
        )
        parser.add_argument(
            '--cliente-id', type=int, default=None,
            help='Limita el backfill a las sesiones de un cliente.',
        )
        parser.add_argument(
            '--informe-impacto', action='store_true',
            help=(
                'Calcula el impacto agregado del backfill sobre '
                'sesiones_perfectas/porcentaje_perfeccion (global y por '
                'cliente) y los mayores cambios de volumen/RPE/perfección. '
                'No escribe en BD (fuerza --dry-run).'
            ),
        )
        parser.add_argument(
            '--auditoria-perfeccion', action='store_true',
            help=(
                'Audita una muestra representativa de las sesiones que '
                'ganarían "perfección" (series_completadas==series_totales) '
                'con el backfill, con veredicto completa/dudosa/incompleta '
                'por sesión. No escribe en BD (fuerza --dry-run).'
            ),
        )
        parser.add_argument(
            '--aplicar', action='store_true',
            help=(
                'Aplica el backfill real (escribe en BD) y muestra el '
                'informe de impacto antes/después. Si se combina con '
                '--dry-run, no escribe en BD (--dry-run tiene prioridad).'
            ),
        )

    def _valores_reales(self, entreno, sesion):
        """Valores que debería tener el snapshot según EntrenoRealizado/EjercicioRealizado."""
        ejercicios = list(entreno.ejercicios_realizados.all())
        liftin = list(entreno.ejercicios_liftin_detallados.all()) if hasattr(
            entreno, 'ejercicios_liftin_detallados'
        ) else []
        ejercicios_reales_count = len(ejercicios) + len(liftin)

        if ejercicios or liftin:
            ejercicios_totales = ejercicios_reales_count
            ejercicios_completados = (
                len([e for e in ejercicios if e.completado])
                + len([e for e in liftin if e.completado])
            )
            series_totales = (
                sum(getattr(e, 'series', 0) or 0 for e in ejercicios)
                + sum(getattr(e, 'series_realizadas', 0) or 0 for e in liftin)
            )
            series_completadas = (
                sum(getattr(e, 'series', 0) or 0 for e in ejercicios if e.completado)
                + sum(getattr(e, 'series_realizadas', 0) or 0 for e in liftin if e.completado)
            )
        else:
            numero_ejercicios = entreno.numero_ejercicios or 0
            ejercicios_totales = numero_ejercicios
            ejercicios_completados = numero_ejercicios
            series_totales = sesion.series_totales
            series_completadas = sesion.series_completadas

        rpe_avg = entreno.ejercicios_realizados.filter(
            rpe__isnull=False
        ).aggregate(avg=Avg('rpe'))['avg']

        return {
            'duracion_minutos': entreno.duracion_minutos or 0,
            'ejercicios_totales': ejercicios_totales,
            'ejercicios_completados': ejercicios_completados,
            'series_totales': series_totales,
            'series_completadas': series_completadas,
            'volumen_sesion': entreno.volumen_total_kg or 0,
            'rpe_medio': round(rpe_avg, 1) if rpe_avg is not None else None,
            'ejercicios_reales_count': ejercicios_reales_count,
        }

    def _calcular_cambios(self, sesion, reales):
        """Diferencias entre el snapshot actual y los valores reales. rpe_medio
        solo se incluye si hay datos reales (nunca se sobreescribe a None)."""
        cambios = {}
        for campo in (
            'duracion_minutos', 'ejercicios_totales', 'ejercicios_completados',
            'series_totales', 'series_completadas',
        ):
            if getattr(sesion, campo) != reales[campo]:
                cambios[campo] = reales[campo]

        if float(sesion.volumen_sesion or 0) != float(reales['volumen_sesion']):
            cambios['volumen_sesion'] = reales['volumen_sesion']

        if reales['rpe_medio'] is not None and sesion.rpe_medio != reales['rpe_medio']:
            cambios['rpe_medio'] = reales['rpe_medio']

        return cambios

    def _clasificar(self, sesion, cambios):
        if (
            sesion.duracion_minutos == 0
            and float(sesion.volumen_sesion or 0) == 0
            and sesion.ejercicios_totales == 0
            and sesion.series_totales == 0
        ):
            return 'zombi_completo'
        if set(cambios.keys()) <= CAMPOS_SERIES:
            return 'solo_series'
        return 'mixto'

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        cliente_id = options['cliente_id']
        informe_impacto = options['informe_impacto']
        auditoria_perfeccion = options['auditoria_perfeccion']
        aplicar = options['aplicar']
        if informe_impacto or auditoria_perfeccion:
            dry_run = True

        sesiones = SesionEntrenamiento.objects.select_related('entreno').all()
        if cliente_id is not None:
            sesiones = sesiones.filter(entreno__cliente_id=cliente_id)

        total = 0
        corregidos = 0
        omitidos = 0
        ya_correctos = 0

        conteo_tipos = {'zombi_completo': 0, 'mixto': 0, 'solo_series': 0}
        por_cliente = {}
        pierden_perfeccion = []
        ganan_perfeccion = []
        cambios_volumen = []
        cambios_rpe = []
        registros = []

        for sesion in sesiones.iterator():
            total += 1
            entreno = sesion.entreno
            cliente_id_actual = entreno.cliente_id

            datos_cliente = por_cliente.setdefault(cliente_id_actual, {
                'total': 0, 'perfectas_antes': 0, 'perfectas_despues': 0,
                'corregibles': 0, 'zombi_completo': 0, 'mixto': 0, 'solo_series': 0,
            })
            datos_cliente['total'] += 1

            perfecta_antes = sesion.series_completadas == sesion.series_totales

            if entreno.es_sesion_incompleta:
                omitidos += 1
                datos_cliente['perfectas_antes'] += int(perfecta_antes)
                datos_cliente['perfectas_despues'] += int(perfecta_antes)
                continue

            reales = self._valores_reales(entreno, sesion)
            cambios = self._calcular_cambios(sesion, reales)

            series_completadas_despues = cambios.get('series_completadas', sesion.series_completadas)
            series_totales_despues = cambios.get('series_totales', sesion.series_totales)
            perfecta_despues = series_completadas_despues == series_totales_despues

            datos_cliente['perfectas_antes'] += int(perfecta_antes)
            datos_cliente['perfectas_despues'] += int(perfecta_despues)

            if auditoria_perfeccion:
                rpe_despues = (
                    reales['rpe_medio'] if reales['rpe_medio'] is not None
                    else sesion.rpe_medio
                )
                registros.append({
                    'entreno': entreno,
                    'numero_ejercicios_entreno': entreno.numero_ejercicios or 0,
                    'ejercicios_reales_count': reales['ejercicios_reales_count'],
                    'volumen_real': reales['volumen_sesion'],
                    'volumen_antes': sesion.volumen_sesion,
                    'series_antes': (sesion.series_completadas, sesion.series_totales),
                    'series_despues': (series_completadas_despues, series_totales_despues),
                    'rpe_antes': sesion.rpe_medio,
                    'rpe_despues': rpe_despues,
                    'perfecta_antes': perfecta_antes,
                    'perfecta_despues': perfecta_despues,
                    'gana_perfeccion': perfecta_despues and not perfecta_antes,
                    'pierde_perfeccion': perfecta_antes and not perfecta_despues,
                })

            if not cambios:
                ya_correctos += 1
                if dry_run:
                    continue
            else:
                corregidos += 1
                tipo = self._clasificar(sesion, cambios)
                conteo_tipos[tipo] += 1
                datos_cliente['corregibles'] += 1
                datos_cliente[tipo] += 1

                if perfecta_antes and not perfecta_despues:
                    pierden_perfeccion.append((
                        entreno, sesion.series_completadas, sesion.series_totales,
                        series_completadas_despues, series_totales_despues,
                    ))
                elif perfecta_despues and not perfecta_antes:
                    ganan_perfeccion.append((
                        entreno, sesion.series_completadas, sesion.series_totales,
                        series_completadas_despues, series_totales_despues,
                    ))

                if 'volumen_sesion' in cambios:
                    antes_v = int(float(sesion.volumen_sesion or 0))
                    despues_v = int(float(reales['volumen_sesion']))
                    cambios_volumen.append((entreno, antes_v, despues_v, despues_v - antes_v))

                if 'rpe_medio' in cambios:
                    antes_r = sesion.rpe_medio
                    despues_r = reales['rpe_medio']
                    delta_r = round(despues_r - (antes_r or 0), 1)
                    cambios_rpe.append((entreno, antes_r, despues_r, delta_r))

                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] entreno_id={entreno.id} cliente={entreno.cliente_id} "
                        f"fecha={entreno.fecha}: {cambios}"
                    )
                    continue

            for campo, valor in cambios.items():
                setattr(sesion, campo, valor)
            sesion.save(update_fields=list(cambios.keys()))

            if aplicar and cambios:
                self.stdout.write(
                    f"  [aplicado] entreno_id={entreno.id} cliente={entreno.cliente_id} "
                    f"fecha={entreno.fecha}: {cambios}"
                )

        verbo_corregidos = "Se corregirían" if dry_run else "Corregidos"
        self.stdout.write(self.style.SUCCESS(
            f"Revisados: {total}. {verbo_corregidos}: {corregidos}. "
            f"Ya correctos: {ya_correctos}. Omitidos (incompletos): {omitidos}."
        ))

        if informe_impacto or aplicar:
            self._informe_impacto(
                total, corregidos, conteo_tipos, por_cliente,
                pierden_perfeccion, ganan_perfeccion, cambios_volumen, cambios_rpe,
            )

        if auditoria_perfeccion:
            self._auditoria_perfeccion(registros, cambios_volumen, cambios_rpe)

    @staticmethod
    def _pct(numerador, denominador):
        return round((numerador / denominador * 100), 1) if denominador else 0

    def _informe_impacto(
        self, total, corregibles, conteo_tipos, por_cliente,
        pierden_perfeccion, ganan_perfeccion, cambios_volumen, cambios_rpe,
    ):
        self.stdout.write('')
        self.stdout.write('=== Informe de impacto — backfill SesionEntrenamiento ===')
        self.stdout.write(
            f"Corregibles: {corregibles} "
            f"(zombis completos: {conteo_tipos['zombi_completo']}, "
            f"mixtos: {conteo_tipos['mixto']}, "
            f"solo series: {conteo_tipos['solo_series']})"
        )

        perfectas_antes_total = sum(d['perfectas_antes'] for d in por_cliente.values())
        perfectas_despues_total = sum(d['perfectas_despues'] for d in por_cliente.values())

        pct_antes_g = self._pct(perfectas_antes_total, total)
        pct_despues_g = self._pct(perfectas_despues_total, total)
        diff_count_g = perfectas_despues_total - perfectas_antes_total
        diff_pct_g = round(pct_despues_g - pct_antes_g, 1)

        self.stdout.write('')
        self.stdout.write('--- sesiones_perfectas / porcentaje_perfeccion ---')
        self.stdout.write(
            f"[global] antes: {perfectas_antes_total}/{total} = {pct_antes_g}% | "
            f"despues: {perfectas_despues_total}/{total} = {pct_despues_g}% | "
            f"diff: {diff_count_g} sesiones ({diff_pct_g} pp)"
        )

        for cliente_id_actual, datos in por_cliente.items():
            pct_a = self._pct(datos['perfectas_antes'], datos['total'])
            pct_d = self._pct(datos['perfectas_despues'], datos['total'])
            self.stdout.write(
                f"cliente_id={cliente_id_actual}: corregibles={datos['corregibles']} "
                f"(zombis completos: {datos['zombi_completo']}, "
                f"mixtos: {datos['mixto']}, solo series: {datos['solo_series']}) | "
                f"sesiones_perfectas antes: {datos['perfectas_antes']}/{datos['total']} = {pct_a}% | "
                f"despues: {datos['perfectas_despues']}/{datos['total']} = {pct_d}%"
            )

        self.stdout.write('')
        self.stdout.write('--- Top cambios ---')
        self.stdout.write(f"Pierden perfeccion ({len(pierden_perfeccion)}):")
        for entreno, ca, ta, cd, td in pierden_perfeccion:
            self.stdout.write(
                f"  entreno_id={entreno.id} cliente={entreno.cliente_id} "
                f"fecha={entreno.fecha}: series {ca}/{ta} -> {cd}/{td}"
            )

        self.stdout.write('')
        self.stdout.write(f"Ganan perfeccion ({len(ganan_perfeccion)}):")
        for entreno, ca, ta, cd, td in ganan_perfeccion:
            self.stdout.write(
                f"  entreno_id={entreno.id} cliente={entreno.cliente_id} "
                f"fecha={entreno.fecha}: series {ca}/{ta} -> {cd}/{td}"
            )

        cambios_volumen.sort(key=lambda x: abs(x[3]), reverse=True)
        self.stdout.write('')
        self.stdout.write('Mayor cambio de volumen (top 5):')
        for entreno, antes_v, despues_v, delta_v in cambios_volumen[:5]:
            self.stdout.write(
                f"  entreno_id={entreno.id} cliente={entreno.cliente_id} "
                f"fecha={entreno.fecha}: volumen {antes_v} -> {despues_v} (delta={delta_v})"
            )

        cambios_rpe.sort(key=lambda x: abs(x[3]), reverse=True)
        self.stdout.write('')
        self.stdout.write('Mayor cambio de RPE (top 5):')
        for entreno, antes_r, despues_r, delta_r in cambios_rpe[:5]:
            self.stdout.write(
                f"  entreno_id={entreno.id} cliente={entreno.cliente_id} "
                f"fecha={entreno.fecha}: rpe {antes_r} -> {despues_r} (delta={delta_r})"
            )

    @staticmethod
    def _veredicto(registro):
        """parece completa / dudosa / incompleta — Phase Evolución Data 5A.1."""
        if registro['series_despues'][1] == 0:
            return 'incompleta'
        if registro['numero_ejercicios_entreno'] != registro['ejercicios_reales_count']:
            return 'dudosa'
        return 'completa'

    @staticmethod
    def _motivo(registro):
        ca, ta = registro['series_antes']
        cd, td = registro['series_despues']
        if registro['gana_perfeccion']:
            return f"gana perfección: series_completadas {ca}->{cd} (series_totales {ta}->{td})"
        if registro['pierde_perfeccion']:
            return f"pierde perfección: series_completadas {ca}->{cd} (series_totales {ta}->{td})"
        if registro['perfecta_antes'] and registro['perfecta_despues']:
            return "control: ya era perfecta y sigue siéndolo"
        return "sin cambio en perfección"

    def _imprimir_registro(self, registro):
        entreno = registro['entreno']
        if entreno.rutina_id:
            rutina_nombre = entreno.rutina.nombre
        else:
            rutina_nombre = entreno.nombre_rutina_liftin or '(sin rutina)'

        ca, ta = registro['series_antes']
        cd, td = registro['series_despues']

        self.stdout.write(
            f"  entreno_id={entreno.id} cliente={entreno.cliente_id} "
            f"fecha={entreno.fecha} rutina={rutina_nombre}"
        )
        self.stdout.write(
            f"    numero_ejercicios={registro['numero_ejercicios_entreno']} "
            f"ejercicios_realizados={registro['ejercicios_reales_count']} "
            f"volumen_real={registro['volumen_real']} kg"
        )
        self.stdout.write(f"    series: {ca}/{ta} -> {cd}/{td}")
        self.stdout.write(f"    rpe: {registro['rpe_antes']} -> {registro['rpe_despues']}")
        self.stdout.write(f"    motivo: {self._motivo(registro)}")
        self.stdout.write(f"    veredicto: {self._veredicto(registro)}")

    def _auditoria_perfeccion(self, registros, cambios_volumen, cambios_rpe):
        self.stdout.write('')
        self.stdout.write('=== Auditoría de perfección — Phase Evolución Data 5A.1 ===')

        gana = [r for r in registros if r['gana_perfeccion']]
        control = [r for r in registros if r['perfecta_antes'] and r['perfecta_despues']]

        patron_cero = [
            r for r in gana
            if r['series_antes'][0] == 0 and r['series_antes'][1] > 0
        ]
        patron_cero = sorted(patron_cero, key=lambda r: r['entreno'].fecha)[:10]

        antiguas = sorted(gana, key=lambda r: r['entreno'].fecha)[:5]
        recientes = sorted(gana, key=lambda r: r['entreno'].fecha, reverse=True)[:5]

        por_cliente_gana = {}
        for r in gana:
            por_cliente_gana.setdefault(r['entreno'].cliente_id, []).append(r)
        cliente_principal = (
            max(por_cliente_gana, key=lambda cid: len(por_cliente_gana[cid]))
            if por_cliente_gana else None
        )
        otros_clientes = []
        for cid, regs in por_cliente_gana.items():
            if cid != cliente_principal:
                otros_clientes.extend(regs[:5])

        top_volumen = sorted(cambios_volumen, key=lambda x: abs(x[3]), reverse=True)[:5]
        top_rpe = sorted(cambios_rpe, key=lambda x: abs(x[3]), reverse=True)[:5]
        ids_volumen = {entreno.id for entreno, *_ in top_volumen}
        ids_rpe = {entreno.id for entreno, *_ in top_rpe}
        mayor_volumen = [r for r in registros if r['entreno'].id in ids_volumen]
        mayor_rpe = [r for r in registros if r['entreno'].id in ids_rpe]

        control_muestra = control[:3]

        secciones = [
            ('Patrón 0/N -> N/N', patron_cero),
            ('Más antiguas', antiguas),
            ('Más recientes', recientes),
            ('Otros clientes', otros_clientes),
            ('Mayor cambio de volumen', mayor_volumen),
            ('Mayor cambio de RPE', mayor_rpe),
            ('Control — ya perfectas antes', control_muestra),
        ]

        veredictos = {}
        for titulo, regs in secciones:
            self.stdout.write('')
            self.stdout.write(f'--- {titulo} ({len(regs)}) ---')
            if not regs:
                self.stdout.write('  (sin registros)')
            for r in regs:
                self._imprimir_registro(r)
                veredictos[r['entreno'].id] = self._veredicto(r)

        completas = sum(1 for v in veredictos.values() if v == 'completa')
        dudosas = sum(1 for v in veredictos.values() if v == 'dudosa')
        incompletas = sum(1 for v in veredictos.values() if v == 'incompleta')

        self.stdout.write('')
        self.stdout.write('--- Resumen ---')
        self.stdout.write(f'Auditadas: {len(veredictos)}')
        self.stdout.write(f'Completas: {completas}')
        self.stdout.write(f'Dudosas: {dudosas}')
        self.stdout.write(f'Incompletas: {incompletas}')

        if patron_cero:
            self.stdout.write(
                f"Patrón detectado: {len(patron_cero)} sesiones con "
                f"series_completadas=0 en el snapshot pero series_totales>0 "
                f"(snapshot creado antes de registrar las series reales)."
            )

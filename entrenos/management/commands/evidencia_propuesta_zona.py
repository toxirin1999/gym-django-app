"""Informe de solo lectura para decidir si una propuesta de zona se mantiene (revisión del bloque).

    python manage.py evidencia_propuesta_zona 2 1

Por cada ejercicio de la propuesta (y los de su zona que recibieron series extra) lista las sesiones
desde 4 semanas antes del inicio hasta hoy: bloque, tramo de reps prescrito, series, peso × reps,
RPE, si es descarga y si la versión guardada recoge la propuesta. Nada se guarda.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Evidencia de una propuesta de zona: sesiones comparables, aplicación, rendimiento y esfuerzo.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('propuesta_id', type=int)
        parser.add_argument('--extra', nargs='*', default=[], help='otros ejercicios de la zona a incluir')

    def handle(self, *args, cliente_id, propuesta_id, extra, **opts):
        from datetime import timedelta

        from clientes.models import Cliente
        from entrenos.models import EjercicioRealizado, PropuestaZonaGym
        from entrenos.services.aprendizaje_decisiones_service import _objetivo_registrado
        from entrenos.services.comparabilidad_service import Bloques
        from entrenos.services.decision_log_service import normalizar_ejercicio
        from entrenos.services.propuesta_zona_service import resultado_propuesta, sesiones_con_ajuste_registrado
        from entrenos.services.sesion_descarga_service import es_sesion_descarga, periodos_descarga
        from entrenos.services.ultima_sesion_service import series_de_trabajo

        try:
            cliente = Cliente.objects.get(pk=cliente_id)
            p = PropuestaZonaGym.objects.get(pk=propuesta_id, cliente=cliente)
        except (Cliente.DoesNotExist, PropuestaZonaGym.DoesNotExist) as exc:
            raise CommandError(str(exc))
        aplicada = set(sesiones_con_ajuste_registrado(cliente, p))
        bloques = Bloques(cliente)
        periodos = periodos_descarga(cliente.pk)
        self.stdout.write(f'Propuesta {p.pk} · {p.nombre_zona} · {p.inicio}–{p.fin} · resultado vigente: {p.resultado}')
        self.stdout.write(f'Aplicación registrada: {len(aplicada)} sesiones')
        resultado, notas = resultado_propuesta(cliente, p)
        self.stdout.write(f'Con la regla vigente: {resultado} · {notas}')
        nombres = list(p.ejercicios) + list(extra)
        desde = (p.inicio or p.fin) - timedelta(days=28)
        for nombre in nombres:
            clave = normalizar_ejercicio(nombre)
            self.stdout.write(f'\n== {nombre} ==')
            self.stdout.write('fecha · bloque · prescrito · series de trabajo (kg×reps@RPE) · descarga · propuesta en la versión')
            filas = [
                e for e in EjercicioRealizado.objects.filter(
                    entreno__cliente=cliente, completado=True, entreno__fecha__gte=desde,
                ).select_related('entreno').order_by('entreno__fecha', 'entreno_id')
                if normalizar_ejercicio(e.nombre_ejercicio) == clave
            ]
            for e in filas:
                fecha = e.entreno.fecha_ejecucion or e.entreno.fecha
                series = series_de_trabajo(e.entreno, e.nombre_ejercicio)
                texto = ', '.join(
                    f"{s['peso']:g}×{s['reps']}" + (f"@{s['rpe']:g}" if s['rpe'] is not None else '') for s in series
                ) or '—'
                try:
                    blq = bloques.de(fecha)['nombre']
                except Exception:  # noqa: BLE001
                    blq = '?'
                pres = _objetivo_registrado(e.entreno_id, e.nombre_ejercicio) or 'sin versión guardada'
                desc = 'DESCARGA' if es_sesion_descarga(e.entreno, e.nombre_ejercicio, periodos) else '-'
                marca = 'sí' if e.entreno.fecha in aplicada else 'no'
                self.stdout.write(f'{fecha:%d/%m} · {blq} · {pres} · {len(series)} series: {texto} · {desc} · {marca}')
            if not filas:
                self.stdout.write('(sin sesiones)')

        self._contexto(cliente, p, nombres)

    def _contexto(self, cliente, p, nombres):
        """Contexto, no prueba: cómo se movieron en la misma ventana ejercicios de otras zonas."""
        from collections import defaultdict
        from statistics import median

        from entrenos.services.evolucion_muscular_service import comparar_ejercicios
        from entrenos.services.propuesta_zona_service import _filas_dentro_de_la_ventana, _plano

        dias = ((p.fin - p.inicio).days + 1) if p.inicio else p.semanas * 7
        filas = [e for e in comparar_ejercicios(cliente, p.fin, dias, estricto=True)
                 if e['pct'] is not None and not e['dudoso']]
        objetivo = {_plano(n) for n in p.ejercicios}
        medidas = _filas_dentro_de_la_ventana([e for e in filas if _plano(e['ejercicio']) in objetivo], p)
        if medidas:
            valores = [round(e['pct'], 1) for e in medidas]
            self.stdout.write('\nCómo sale la cifra de la propuesta')
            self.stdout.write(f'Ejercicios medidos: {len(valores)} · valores: {valores} · mediana usada: '
                              f'{round(median(valores), 1)} %')
            if len(valores) == 2:
                self.stdout.write('Con dos valores la mediana es simplemente su media (cada uno pesa igual): '
                                  'si un valor cambia en d puntos, la cifra cambia en d/2, y no hay '
                                  'robustez frente a un valor atípico.')
        otras = defaultdict(list)
        for e in filas:
            if _plano(e['ejercicio']) in objetivo or e.get('zona') == p.zona:
                continue
            otras[e.get('zona') or '?'].append(round(e['pct'], 1))
        self.stdout.write('\nContexto (no es prueba): fuerza estimada de ejercicios de otras zonas en la misma ventana')
        if not otras:
            self.stdout.write('(sin ejercicios comparables en otras zonas)')
        for zona, valores in sorted(otras.items()):
            self.stdout.write(f'{zona}: {len(valores)} ejercicios · mediana {round(median(valores), 1)} % · {valores}')
        self.stdout.write('Estas zonas tienen su propio volumen, bloque y ejercicios: sirven para ver si todo el '
                          'cuerpo progresó en el periodo, no para atribuir el resultado a las series extra.')

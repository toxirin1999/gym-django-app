"""Vista previa (SOLO LECTURA) de re-evaluar decisiones por distancia (Farmer) con la regla corregida.

21-nov-2026 (N1): las evaluaciones antiguas del Farmer compararon repeticiones (0) con el +5 m y
quedaron «neutra: mismo rendimiento en el tope». Este comando enseña, para cada decision, lo que
esta guardado y lo que daria la regla nueva con las mismas series. No escribe nada: la
re-evaluacion corre dentro de una transaccion que siempre se revierte y la persistencia esta anulada.

    python manage.py previsualizar_evaluacion_distancia --cliente 2
    python manage.py previsualizar_evaluacion_distancia --cliente 2 --logs 592 630 638 678
"""
from unittest import mock

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Vista previa de re-evaluar decisiones por distancia. No modifica datos.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--logs', type=int, nargs='*', default=None)

    def handle(self, *args, **opts):
        from entrenos.models import EjercicioRealizado, GymDecisionLog
        from entrenos.services import decision_log_service as dls
        from entrenos.services.aprendizaje_decisiones_service import _sesion_evaluadora
        from rutinas.models import EjercicioBase

        nombres = list(EjercicioBase.objects.filter(tipo_progresion='progresion_distancia')
                       .values_list('nombre', flat=True))
        qs = GymDecisionLog.objects.filter(cliente_id=opts['cliente'], motivo_codigo='tope_maquina')
        if opts['logs']:
            qs = qs.filter(pk__in=opts['logs'])
        else:
            qs = qs.filter(ejercicio__in=[n.lower() for n in nombres]) | qs.filter(ejercicio__in=nombres)
        self.stdout.write('VISTA PREVIA - SOLO LECTURA. Reconstruccion posterior (21/11/2026); no modifica datos.')
        cambian = 0
        for log in qs.order_by('pk').select_related('entreno_origen'):
            tipo = (EjercicioBase.objects.filter(nombre__iexact=log.ejercicio)
                    .values_list('tipo_progresion', flat=True).first())
            if tipo != 'progresion_distancia':
                continue
            self.stdout.write(f'\n== Log {log.pk} · {log.ejercicio} · creado {log.fecha_creacion:%d/%m/%Y}')
            origen = log.entreno_origen
            self.stdout.write(f'   origen: entreno {getattr(origen, "pk", None)} '
                              f'({getattr(origen, "fecha", None)}) · peso_anterior {log.peso_anterior} · '
                              f'reps_anteriores {log.reps_anteriores} · valor_cambio {log.valor_cambio}')
            self.stdout.write(f'   guardado: {log.resultado} · {log.notas_resultado!r}')
            if log.resultado is None:
                self.stdout.write('   sin evaluar todavia: lo evaluara la proxima sesion con la regla nueva')
                continue
            partida = dls.distancia_de_partida(log)
            self.stdout.write(f'   partida: {partida} m · objetivo: '
                              f'{dls.objetivo_metros(log)} m (partida + {dls.incremento_metros(log)})')
            despues = _sesion_evaluadora(log)
            if not despues:
                self.stdout.write('   no consta la sesion evaluadora: no se puede re-evaluar')
                continue
            ej = next((e for e in EjercicioRealizado.objects.filter(entreno_id=despues['entreno_id'], completado=True)
                       if dls.normalizar_ejercicio(e.nombre_ejercicio) == dls.normalizar_ejercicio(log.ejercicio)), None)
            if ej is None:
                self.stdout.write('   la sesion evaluadora no tiene el ejercicio completado')
                continue
            series = dls._series_con_metros(ej.entreno, dls.normalizar_ejercicio(log.ejercicio))
            self.stdout.write(f'   sesion evaluadora: entreno {ej.entreno_id} ({ej.entreno.fecha}) · series '
                              + ', '.join(f'{p} kg x {m} m' for p, m in series))
            obj_presc, previstas, fuente = dls.prescripcion_distancia(
                ej.entreno, dls.normalizar_ejercicio(log.ejercicio), partida, dls.incremento_metros(log))
            self.stdout.write(f'   prescrito en esa sesion: objetivo {obj_presc} m ({fuente}) · '
                              f'series previstas {previstas or "no constan"} · hechas {len(series)} · '
                              f'calculado partida+incremento: {dls.objetivo_metros(log)} m')
            capturado = {}

            def captura(l, resultado, notas, *a, **k):
                capturado['r'] = (resultado, notas)
                return l

            with transaction.atomic():
                fresco = GymDecisionLog.objects.get(pk=log.pk)
                fresco.resultado = None
                with mock.patch.object(dls, '_persistir_evaluacion_final', side_effect=captura):
                    dls._evaluar_log(fresco, ej, 'progresion_distancia')
                transaction.set_rollback(True)  # nada de esto se guarda
            nuevo = capturado.get('r')
            if nuevo is None:
                self.stdout.write('   la regla nueva no produce evaluacion con estos datos')
                continue
            igual = nuevo[0] == log.resultado and nuevo[1] == log.notas_resultado
            if not igual:
                cambian += 1
            self.stdout.write(f'   NUEVA:    {nuevo[0]} · {nuevo[1]!r}  ->  {"sin cambio" if igual else "CAMBIARIA"}')
        self.stdout.write(f'\nDecisiones que cambiarian: {cambian}. No se ha escrito nada.')

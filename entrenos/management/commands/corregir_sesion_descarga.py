"""Deshace lo que una sesión de descarga no debió tocar (2-nov-2026).

Uso:  python manage.py corregir_sesion_descarga 2 2026-11-02            (solo enseña)
      python manage.py corregir_sesion_descarga 2 2026-11-02 --aplicar

Para las sesiones de descarga de ese día:
1. Tope de máquina: vuelve al de la última sesión normal en la que se marcó
   tope (los gemelos quedaron en 90 kg en vez de 100).
2. Decisiones que esa sesión dio por comprobadas (cable fly "funcionó"):
   vuelven a pendientes, para la primera sesión normal.
3. Decisiones creadas a partir de la sesión de descarga: se borran.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Corrige topes y decisiones tocados por una sesión de descarga.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('fecha')
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        from django.db.models import Q
        from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionLog, TopeMaquinaGym
        from entrenos.services.decision_log_service import normalizar_ejercicio
        from entrenos.services.maquina_service import _clave
        from entrenos.services.sesion_descarga_service import es_sesion_descarga, periodos_descarga
        from entrenos.services.ultima_sesion_service import series_de_trabajo

        cid, aplicar = opts['cliente_id'], opts['aplicar']
        fecha = date.fromisoformat(opts['fecha'])
        periodos = periodos_descarga(cid)
        entrenos = EntrenoRealizado.objects.filter(cliente_id=cid).filter(
            Q(fecha_ejecucion=fecha) | Q(fecha_ejecucion__isnull=True, fecha=fecha))
        for e in entrenos:
            for ej in EjercicioRealizado.objects.filter(entreno=e, completado=True):
                nombre = ej.nombre_ejercicio
                if not es_sesion_descarga(e, nombre, periodos):
                    continue
                clave = _clave(nombre)
                tope = TopeMaquinaGym.objects.filter(cliente_id=cid, ejercicio_normalizado=clave).first()
                previo = EjercicioRealizado.objects.filter(
                    entreno__cliente_id=cid, nombre_ejercicio__iexact=nombre, es_tope_maquina=True,
                    completado=True, entreno__fecha__lt=e.fecha,
                ).select_related('entreno').order_by('-entreno__fecha').first()
                if tope and previo and not es_sesion_descarga(previo.entreno, nombre, periodos):
                    pesos = [s['peso'] for s in series_de_trabajo(previo.entreno, nombre) if s['peso'] > 0]
                    bueno = max(pesos) if pesos else None
                    if bueno and abs(float(tope.peso_max_kg) - bueno) > 0.01:
                        self.stdout.write(f'Tope {nombre}: {tope.peso_max_kg} → {bueno} kg '
                                          f'(el del {previo.entreno.fecha:%d/%m})')
                        if aplicar:
                            tope.peso_max_kg = Decimal(str(bueno))
                            tope.save(update_fields=['peso_max_kg'])
                norm = normalizar_ejercicio(nombre)
                for log in GymDecisionLog.objects.filter(
                    cliente_id=cid, resultado__isnull=False, fecha_evaluacion__date=fecha,
                ).filter(Q(ejercicio_normalizado=norm) | Q(ejercicio__iexact=norm)).exclude(entreno_origen=e):
                    self.stdout.write(f'Decisión {log.pk} ({log.ejercicio}, {log.accion}): '
                                      f'"{log.resultado}" → pendiente')
                    if aplicar:
                        log.resultado = None
                        log.notas_resultado = None
                        log.fecha_evaluacion = None
                        log.save(update_fields=['resultado', 'notas_resultado', 'fecha_evaluacion'])
            creadas = GymDecisionLog.objects.filter(cliente_id=cid, entreno_origen=e)
            for log in creadas:
                if es_sesion_descarga(e, log.ejercicio, periodos):
                    self.stdout.write(f'Borrar decisión {log.pk} creada en la descarga: {log.ejercicio} {log.accion}')
                    if aplicar:
                        log.delete()
        self.stdout.write('\nHecho.' if aplicar else '\nSolo enseñado: añade --aplicar para corregirlo.')

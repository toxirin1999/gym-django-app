"""
Management command de solo lectura: diagnostica el ancla e1RM suavizada
(Phase Gym Peso 2.2 X.0) usada para calcular el peso de descarga de un
ejercicio concreto.

Origen: peso de descarga reportado como superior a la última sesión real
("Remo con Mancuerna a una Mano": 52.5kg de descarga vs 30kg x12 de la
última sesión). Este comando reproduce el cálculo con datos reales para
confirmar si el ancla de hasta 3 sesiones en 42 días quedó dominada por una
sesión más pesada, y compara el resultado con/sin el techo de seguridad
(`peso_ultima_sesion`) añadido para corregirlo.

No modifica nada en la base de datos.

Usage:
    python3 manage.py diagnosticar_ancla_ejercicio --usuario david --ejercicio "Remo con Mancuerna a una Mano"
    python3 manage.py diagnosticar_ancla_ejercicio --usuario david --ejercicio "Remo con Mancuerna a una Mano" --fecha 2026-08-18 --rango 10-15 --rpe 6
"""
from datetime import datetime as _dt

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Diagnostica el ancla e1RM suavizada usada para el peso de descarga de un ejercicio"

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='username de Django')
        parser.add_argument('--ejercicio', required=True, help='nombre del ejercicio tal como aparece en el plan')
        parser.add_argument('--fecha', required=False, help='YYYY-MM-DD (default: hoy)')
        parser.add_argument('--rango', required=False, default='10-15', help="rango de reps de hoy, ej '10-15' (default)")
        parser.add_argument('--rpe', required=False, type=int, default=6, help='RPE objetivo de hoy (default: 6)')

    def handle(self, *args, **options):
        from django.utils import timezone

        from clientes.models import Cliente
        from entrenos.models import EjercicioRealizado, GymDecisionLog
        from entrenos.utils.utils import nombres_ejercicio_equivalentes
        from analytics.planificador_helms.calculo.compatibilidad_fase import (
            _bucket_desde_reps, resolver_ancla_historica, resolver_peso_objetivo,
        )

        try:
            usuario = User.objects.get(username=options['usuario'])
        except User.DoesNotExist:
            raise CommandError(f"Usuario '{options['usuario']}' no existe")

        try:
            cliente = Cliente.objects.get(user=usuario)
        except Cliente.DoesNotExist:
            raise CommandError(f"El usuario '{options['usuario']}' no tiene Cliente asociado")

        nombre_ejercicio = options['ejercicio']
        if options.get('fecha'):
            try:
                fecha = _dt.strptime(options['fecha'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError("Fecha inválida, usa YYYY-MM-DD")
        else:
            fecha = timezone.localdate()

        rep_range_hoy = options['rango']
        rpe_objetivo_hoy = options['rpe']

        self.stdout.write(self.style.SUCCESS(
            f"\n=== ANCLA E1RM — {cliente.nombre} — '{nombre_ejercicio}' — hasta {fecha} ===\n"
        ))

        # 1. Candidatos brutos: mismo criterio de preselección que obtener_ancla_ejercicio
        #    (entrenos/views.py) — icontains sobre la primera palabra del nombre.
        primera_palabra = nombre_ejercicio.strip().split()[0] if nombre_ejercicio.strip() else nombre_ejercicio
        candidatos = list(
            EjercicioRealizado.objects
            .filter(
                entreno__cliente=cliente, entreno__fecha__lte=fecha,
                nombre_ejercicio__icontains=primera_palabra, completado=True,
            )
            .select_related('entreno')
            .order_by('-entreno__fecha', '-id')[:20]
        )

        self.stdout.write(f"Candidatos brutos (nombre contiene '{primera_palabra}'): {len(candidatos)}\n")
        for c in candidatos:
            equiv = nombres_ejercicio_equivalentes(c.nombre_ejercicio, nombre_ejercicio)
            marca = 'equivalente' if equiv else 'nombre DISTINTO — descartado'
            self.stdout.write(
                f"  {c.entreno.fecha}  {c.nombre_ejercicio!r:45}  peso={str(c.peso_kg):>6}  "
                f"reps={str(c.repeticiones):>3}  rpe={str(c.rpe):>3}  [{marca}]"
            )

        equivalentes = [
            c for c in candidatos
            if nombres_ejercicio_equivalentes(c.nombre_ejercicio, nombre_ejercicio)
            and c.peso_kg and c.repeticiones and c.rpe is not None
        ]
        if not equivalentes:
            self.stdout.write(self.style.WARNING(
                "\nSin sesiones equivalentes con peso/reps/rpe completos. No se puede calcular ancla.\n"
            ))
            return

        ref = equivalentes[0]
        bucket_ref = _bucket_desde_reps(int(ref.repeticiones))
        self.stdout.write(
            f"\nÚltima sesión real aislada: {ref.entreno.fecha}  peso={ref.peso_kg}  "
            f"reps={ref.repeticiones}  rpe={ref.rpe}  (bucket={bucket_ref})\n"
        )

        sesiones_bucket = [
            {'peso': float(c.peso_kg), 'reps': int(c.repeticiones), 'rpe': float(c.rpe), 'fecha': c.entreno.fecha}
            for c in equivalentes
            if _bucket_desde_reps(int(c.repeticiones)) == bucket_ref
        ]
        self.stdout.write(f"Sesiones del mismo bucket ({bucket_ref}), candidatas al ancla: {len(sesiones_bucket)}\n")
        for s in sesiones_bucket[:5]:
            self.stdout.write(f"  {s['fecha']}  peso={s['peso']}  reps={s['reps']}  rpe={s['rpe']}\n")

        ancla = resolver_ancla_historica(sesiones_bucket, ahora=fecha)
        if not ancla:
            self.stdout.write(self.style.WARNING("\nSin ancla calculable.\n"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\nAncla suavizada (hasta 3 sesiones, ventana 42 días): "
            f"peso={ancla['peso']:.2f}  reps={ancla['reps']}  rpe={ancla['rpe']:.2f}\n"
        ))

        # 2. Decisión de peso de descarga: sin techo (comportamiento previo al fix)
        #    vs con techo (peso_ultima_sesion, comportamiento actual).
        decision_sin_techo = resolver_peso_objetivo(
            peso_anterior=ancla['peso'], reps_anteriores=ancla['reps'], rpe_anterior=ancla['rpe'],
            rep_range_hoy=rep_range_hoy, rpe_objetivo_hoy=rpe_objetivo_hoy, es_descarga_hoy=True,
        )
        decision_con_techo = resolver_peso_objetivo(
            peso_anterior=ancla['peso'], reps_anteriores=ancla['reps'], rpe_anterior=ancla['rpe'],
            rep_range_hoy=rep_range_hoy, rpe_objetivo_hoy=rpe_objetivo_hoy, es_descarga_hoy=True,
            peso_ultima_sesion=float(ref.peso_kg),
        )

        self.stdout.write(f"\nRango objetivo hoy: {rep_range_hoy}  RPE objetivo: {rpe_objetivo_hoy}\n")
        self.stdout.write(f"  Peso de descarga SIN techo (comportamiento previo al fix): {decision_sin_techo['peso']} kg\n")
        self.stdout.write(f"  Peso de descarga CON techo (comportamiento actual):        {decision_con_techo['peso']} kg\n")
        self.stdout.write(f"  Última sesión real:                                        {ref.peso_kg} kg\n")

        if decision_sin_techo['peso'] and decision_sin_techo['peso'] > float(ref.peso_kg):
            self.stdout.write(self.style.WARNING(
                "\n→ Confirmado: sin el techo, el peso de descarga superaba la última sesión real. "
                "El fix lo corrige."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n→ En este caso el ancla no estaba inflada; el techo no habría cambiado el resultado."
            ))

        # 3. Contexto adicional: decisiones de progresión pendientes para este ejercicio.
        logs = list(
            GymDecisionLog.objects
            .filter(cliente=cliente, ejercicio__iexact=nombre_ejercicio.strip().lower())
            .order_by('-fecha_creacion')[:5]
        )
        if logs:
            self.stdout.write("\nÚltimos GymDecisionLog para este ejercicio:")
            for log in logs:
                self.stdout.write(
                    f"  {log.fecha_creacion.date()}  accion={log.accion}  resultado={log.resultado}  "
                    f"peso_anterior={log.peso_anterior}  reps_anteriores={log.reps_anteriores}  "
                    f"rpe_anterior={log.rpe_anterior}"
                )

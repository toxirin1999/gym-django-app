"""Solo lectura: la regla única de peso y reps frente a lo que hace hoy la app.

Uso:  python manage.py comparar_cerebro_carga 2
      python manage.py comparar_cerebro_carga 2 --dias-atras 21 --dias-adelante 7

Dos bloques:

PRÓXIMOS DÍAS — para cada ejercicio del plan: lo que propone hoy la app
(planificador + plan dinámico) y lo que propondría la regla única.

ÚLTIMAS SESIONES — para cada ejercicio entrenado: lo que se propuso ese día
(snapshot de la decisión), lo que habría propuesto la regla única y lo que
hiciste de verdad (primera serie de trabajo).

No guarda nada: todo el cálculo va dentro de una transacción que se deshace.
"""

from copy import deepcopy
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def _kg(valor):
    try:
        v = round(float(valor), 2)
    except (TypeError, ValueError):
        return '?'
    return str(int(v)) if v == int(v) else f'{v:g}'


class _Deshacer(Exception):
    pass


class Command(BaseCommand):
    help = 'Compara (sin guardar nada) la regla única de carga con lo que propone hoy la app.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--dias-atras', type=int, default=21)
        parser.add_argument('--dias-adelante', type=int, default=7)

    def handle(self, *args, **opts):
        from clientes.models import Cliente

        cliente = Cliente.objects.get(pk=opts['cliente_id'])
        hoy = timezone.localdate()
        self.resumen = {'igual': 0, 'distinto': 0, 'sin_regla': 0}
        try:
            with transaction.atomic():
                self._proximos(cliente, hoy, opts['dias_adelante'])
                self._ultimas(cliente, hoy, opts['dias_atras'])
                raise _Deshacer()
        except _Deshacer:
            pass
        r = self.resumen
        self.stdout.write(f"\nRESUMEN próximos días: {r['igual']} iguales · {r['distinto']} distintos · "
                          f"{r['sin_regla']} sin historial (manda el plan)")
        self.stdout.write('(No se ha guardado nada.)')

    # ── Próximos días ────────────────────────────────────────────
    def _proximos(self, cliente, hoy, dias):
        from entrenos.services.cerebro_carga_service import decidir_carga
        from entrenos.services.plan_dinamico_service import aplicar_plan_dinamico
        from entrenos.services.sesion_recomendada import _build_planificador, _normalizar_entrenamiento
        from entrenos.services.ultima_sesion_service import peso_contractual

        self.stdout.write('=== PRÓXIMOS DÍAS (app hoy → regla única) ===')
        planificador = _build_planificador(cliente)
        for i in range(dias):
            fecha = hoy + timedelta(days=i)
            try:
                sesion = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(fecha))
            except Exception as exc:  # noqa: BLE001 — diagnóstico
                self.stdout.write(f'{fecha} ERROR {exc!r}')
                continue
            ejercicios = (sesion or {}).get('ejercicios') or []
            if not ejercicios:
                continue
            self.stdout.write(f"\n{fecha} {sesion.get('rutina_nombre', '')}")
            try:
                actuales, _ = aplicar_plan_dinamico(cliente, deepcopy(ejercicios), fecha)
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(f'   plan dinámico falló: {exc!r}')
                continue
            for ej in actuales:
                nombre = ej.get('nombre')
                actual_peso = peso_contractual(ej)
                actual_reps = ej.get('reps_objetivo_hoy') or ej.get('reps_objetivo') or ej.get('repeticiones')
                nueva = decidir_carga(cliente, ej, fecha)
                if nueva is None:
                    self.resumen['sin_regla'] += 1
                    self.stdout.write(f'   {nombre}: app {_kg(actual_peso)} × {actual_reps} | regla: sin historial')
                    continue
                igual = abs(float(actual_peso or 0) - nueva['peso']) < 0.01 and str(actual_reps) == str(nueva['reps'])
                self.resumen['igual' if igual else 'distinto'] += 1
                marca = '  =' if igual else ' ≠'
                self.stdout.write(
                    f"{marca} {nombre}: app {_kg(actual_peso)} × {actual_reps} | "
                    f"regla {_kg(nueva['peso'])} × {nueva['reps']} [{nueva['regla']}] {nueva['frase'] or ''}"
                )

    # ── Últimas sesiones ─────────────────────────────────────────
    def _ultimas(self, cliente, hoy, dias):
        from entrenos.models import EntrenoRealizado
        from entrenos.services.cerebro_carga_service import decidir_carga
        from entrenos.services.decision_log_service import normalizar_ejercicio
        from entrenos.services.ultima_sesion_service import series_de_trabajo

        self.stdout.write('\n=== ÚLTIMAS SESIONES (propuesto ese día | regla única | hecho) ===')
        entrenos = (
            EntrenoRealizado.objects.filter(cliente=cliente, fecha__gte=hoy - timedelta(days=dias))
            .select_related('rutina').order_by('fecha', 'id')
        )
        for entreno in entrenos:
            version = getattr(entreno, 'gym_decision_version', None)
            snapshot = getattr(version, 'snapshot', None) or {}
            plan = {
                normalizar_ejercicio(e.get('nombre')): e
                for e in (snapshot.get('entrenamiento') or {}).get('ejercicios') or []
            }
            nombre_rutina = entreno.rutina.nombre if entreno.rutina else ''
            self.stdout.write(f'\n{entreno.fecha} {nombre_rutina} (#{entreno.id})')
            for ej_hecho in entreno.ejercicios_realizados.filter(completado=True).order_by('orden', 'id'):
                clave = normalizar_ejercicio(ej_hecho.nombre_ejercicio)
                series = series_de_trabajo(entreno, ej_hecho.nombre_ejercicio)
                hecho = ', '.join(
                    f"{_kg(s['peso'])}×{s['reps']}" + (f"@{_kg(s['rpe'])}" if s.get('rpe') is not None else '')
                    for s in series
                ) or '—'
                propuesto_ej = plan.get(clave)
                if not propuesto_ej:
                    self.stdout.write(f'   {ej_hecho.nombre_ejercicio}: sin snapshot | hecho {hecho}')
                    continue
                propuesto = (f"{_kg(propuesto_ej.get('peso_kg'))} × "
                             f"{propuesto_ej.get('reps_objetivo_hoy') or propuesto_ej.get('reps_objetivo') or propuesto_ej.get('repeticiones')}")
                nueva = decidir_carga(cliente, propuesto_ej, entreno.fecha)
                regla = f"{_kg(nueva['peso'])} × {nueva['reps']} [{nueva['regla']}]" if nueva else 'sin historial'
                self.stdout.write(f'   {ej_hecho.nombre_ejercicio}: propuesto {propuesto} | regla {regla} | hecho {hecho}')

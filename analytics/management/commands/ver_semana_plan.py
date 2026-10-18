"""Solo lectura: lo que el planificador genera para un cliente, día a día.

Uso:  python manage.py ver_semana_plan 2 --desde 2026-10-12 --dias 14

No guarda nada: llama a generar_entrenamiento_para_fecha (el mismo camino que
la app) y resume series por grupo muscular y por semana, para compararlo con
lo recomendable (ver claude/analisis_planificacion_semanal_2026-10-18.md).
"""

from collections import defaultdict
from datetime import date, timedelta

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Muestra (sin guardar nada) lo que el planificador genera para un cliente.'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--desde', type=str, default=None)
        parser.add_argument('--dias', type=int, default=14)

    def handle(self, *args, **opts):
        from clientes.models import Cliente
        from entrenos.services.sesion_recomendada import _build_planificador, _normalizar_entrenamiento

        cliente = Cliente.objects.get(pk=opts['cliente_id'])
        desde = date.fromisoformat(opts['desde']) if opts['desde'] else date.today()
        planificador = _build_planificador(cliente)
        perfil = planificador.perfil

        self.stdout.write('PERFIL ' + ' · '.join(
            f'{campo}={getattr(perfil, campo, None)!r}'
            for campo in ('experiencia', 'objetivo', 'dias_disponibles', 'factor_recuperacion',
                          'nivel_estres', 'calidad_sueño', 'nivel_energia', 'ejercicios_evitar')
        ))

        por_semana = defaultdict(lambda: defaultdict(lambda: [0, set()]))
        for i in range(opts['dias']):
            fecha = desde + timedelta(days=i)
            try:
                sesion = _normalizar_entrenamiento(planificador.generar_entrenamiento_para_fecha(fecha))
            except Exception as exc:  # noqa: BLE001 — diagnóstico, no romper
                self.stdout.write(f'{fecha} ERROR {exc!r}')
                continue
            ejercicios = (sesion or {}).get('ejercicios') or []
            if not ejercicios:
                self.stdout.write(f'{fecha} descanso')
                continue
            lunes = fecha - timedelta(days=fecha.weekday())
            self.stdout.write(f"{fecha} {sesion.get('rutina_nombre', '')}")
            for ej in ejercicios:
                grupo = ej.get('grupo_muscular') or '?'
                series = int(ej.get('series') or 0)
                por_semana[lunes][grupo][0] += series
                por_semana[lunes][grupo][1].add(fecha)
                self.stdout.write(
                    f"   {ej.get('nombre')} | {grupo} | {series}x{ej.get('repeticiones')} | RPE {ej.get('rpe_objetivo')}"
                )

        for lunes, grupos in sorted(por_semana.items()):
            self.stdout.write(f'SEMANA {lunes}: ' + ' · '.join(
                f'{g} {v[0]} ({len(v[1])}d)' for g, v in sorted(grupos.items())
            ))

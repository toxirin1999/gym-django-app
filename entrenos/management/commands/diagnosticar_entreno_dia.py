"""
Management command de solo lectura: diagnostica por qué la sesión recomendada
de un día concreto puede salir vacía o con pocos ejercicios.

No modifica nada en la base de datos. Pensado para correr en producción
(PythonAnywhere) cuando el entorno local no reproduce el problema (datos
distintos).

Usage:
    python3 manage.py diagnosticar_entreno_dia --usuario david --fecha 2026-07-24
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Diagnostica por qué la sesión recomendada de un día concreto sale vacía o reducida"

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='username de Django')
        parser.add_argument('--fecha', required=True, help='YYYY-MM-DD')

    def handle(self, *args, **options):
        from datetime import datetime as _dt
        from clientes.models import Cliente

        try:
            usuario = User.objects.get(username=options['usuario'])
        except User.DoesNotExist:
            raise CommandError(f"Usuario '{options['usuario']}' no existe")

        try:
            cliente = Cliente.objects.get(user=usuario)
        except Cliente.DoesNotExist:
            raise CommandError(f"El usuario '{options['usuario']}' no tiene Cliente asociado")

        try:
            fecha = _dt.strptime(options['fecha'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError("Fecha inválida, usa YYYY-MM-DD")

        self.stdout.write(self.style.SUCCESS(f"\n=== DIAGNÓSTICO {cliente.nombre} — {fecha} ===\n"))

        # 1. necesita_deload_gym
        from entrenos.services.briefing_service import necesita_deload_gym
        try:
            deload = necesita_deload_gym(cliente, fecha)
        except Exception as e:
            deload = f"ERROR: {e}"
        self.stdout.write(f"necesita_deload_gym: {deload}")

        # 2. obtener_sesion_recomendada_hoy — decisión completa
        from entrenos.services.sesion_recomendada import obtener_sesion_recomendada_hoy
        try:
            r = obtener_sesion_recomendada_hoy(cliente, fecha)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"obtener_sesion_recomendada_hoy ERROR: {e}"))
            r = {}

        self.stdout.write(f"\nestado: {r.get('estado')}")
        self.stdout.write(f"modo_reducido: {r.get('modo_reducido')}")
        self.stdout.write(f"causa_principal: {r.get('causa_principal')}")
        self.stdout.write(f"mensaje: {r.get('mensaje')}")
        self.stdout.write(f"contexto_fisico: {r.get('contexto_fisico')}")

        ents = r.get('entrenamiento') or {}
        ejs = ents.get('ejercicios') or []
        self.stdout.write(f"\nejercicios vía obtener_sesion_recomendada_hoy: {len(ejs)}")
        if ejs:
            self.stdout.write(f"  por tipo: {dict(Counter(e.get('tipo_ejercicio') for e in ejs))}")
            self.stdout.write(f"  grupos: {sorted(set(e.get('grupo_muscular') for e in ejs))}")

        # 3. Plan anual cacheado (o regenerado) — ver qué había ANTES de cualquier filtro bio
        from django.core.cache import cache
        año = fecha.year
        cache_key = f'plan_anual_{cliente.id}_{año}'
        plan = cache.get(cache_key)
        origen_plan = "cache"
        if not plan:
            from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
            from analytics.sistema_educacion_helms import agregar_educacion_a_plan
            from entrenos.serializador_plan import serializar_plan_para_sesion
            perfil = crear_perfil_desde_cliente(cliente)
            perfil.maximos_actuales = cliente.one_rm_data or {}
            perfil.año_planificacion = año
            planificador = PlanificadorHelms(perfil)
            plan_original = planificador.generar_plan_anual()
            plan = agregar_educacion_a_plan(plan_original)
            plan = serializar_plan_para_sesion(plan)
            origen_plan = "regenerado (no estaba en cache)"

        self.stdout.write(f"\nPlan anual: {origen_plan}")
        entrenos_del_plan = plan.get('entrenos_por_fecha', {})
        entrenamiento_dia = None
        for fecha_key, ent in entrenos_del_plan.items():
            from datetime import date as _date_inner, datetime as _datetime_inner
            try:
                if isinstance(fecha_key, _date_inner) and not isinstance(fecha_key, _datetime_inner):
                    k_obj = fecha_key
                elif isinstance(fecha_key, _datetime_inner):
                    k_obj = fecha_key.date()
                else:
                    k_obj = _datetime_inner.fromisoformat(str(fecha_key)).date()
                if k_obj == fecha:
                    entrenamiento_dia = ent
                    break
            except (ValueError, TypeError, AttributeError):
                continue

        if not isinstance(entrenamiento_dia, dict):
            self.stdout.write(self.style.WARNING(f"No se encontró entrenamiento en el plan para {fecha} (día de descanso o fuera de rango)"))
        else:
            ejs_plan = entrenamiento_dia.get('ejercicios') or []
            self.stdout.write(f"nombre_rutina: {entrenamiento_dia.get('nombre_rutina')}")
            self.stdout.write(f"ejercicios en el plan crudo (antes de filtros bio): {len(ejs_plan)}")
            if ejs_plan:
                self.stdout.write(f"  por tipo: {dict(Counter(e.get('tipo_ejercicio') for e in ejs_plan))}")
                self.stdout.write(f"  grupos: {sorted(set(e.get('grupo_muscular') for e in ejs_plan))}")
            else:
                self.stdout.write(self.style.ERROR("¡EL PLAN CRUDO YA VIENE VACÍO PARA ESTE DÍA! — el problema está en la generación del plan (Helms/GestorFatiga), no en filtros posteriores."))

        self.stdout.write(self.style.SUCCESS("\n=== FIN DIAGNÓSTICO ===\n"))

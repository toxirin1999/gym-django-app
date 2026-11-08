"""8-nov-2026 · Plan, Centro, Plan anual y Memoria dicen lo mismo en tres transiciones reales.

Ya se han contradicho (semana de descarga, contadores, fechas de bloque).
Esta prueba mira las pantallas a la vez en:
1. Una semana con una sesión aplazada (jueves libre, Día 5 el sábado).
2. El cambio de bloque (de la descarga a Fuerza — Hipertrofia).
3. Una propuesta en pausa por la descarga.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from entrenos.models import EntrenoRealizado, SemanaPlanGym
from rutinas.models import Rutina

L44 = date(2026, 11, 2)   # descarga
SABADO = L44 + timedelta(days=5)
L45 = L44 + timedelta(days=7)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user('coherencia_20261108', password='x')
        self.cliente = self.user.cliente_perfil
        self.cliente.dias_disponibles = 5
        self.cliente.save(update_fields=['dias_disponibles'])
        for i, n in enumerate((39, 40, 41, 42, 43, 44)):
            SemanaPlanGym.objects.create(cliente=self.cliente, lunes=L44 - timedelta(weeks=5 - i), semana_plan=n,
                                         descarga=(n == 44), origen=SemanaPlanGym.ORIGEN_AVANCE)
        for i, d in enumerate((0, 1, 2, 4, 5)):   # el jueves libre: el Día 4 pasa al viernes
            rutina, _ = Rutina.objects.get_or_create(nombre=f'Día {i + 1} - Descarga Activa')
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=L44 + timedelta(days=d))


class SesionAplazada(Base):
    def test_cinco_hechas_en_todas_y_el_dia_5_hoy(self):
        from clientes.views import _hoy_segun_sesion
        from entrenos.services.centro_decisiones_service import construir_resumen_operativo_centro
        from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan
        from entrenos.views import _fechas_hechas_mes

        plan = proyectar_trayectoria_plan(self.cliente, fecha=SABADO)
        centro = construir_resumen_operativo_centro(self.cliente, {'bloque': None}, None, SABADO)
        hechas_plan = sum(1 for s in plan['semana']['sesiones'] if s['realizada'])
        hechas_calendario = [f for f in _fechas_hechas_mes(self.cliente, 2026, 11) if f <= SABADO.isoformat()]
        self.assertEqual(hechas_plan, 5)
        self.assertEqual(centro['semana']['completadas'], hechas_plan)
        self.assertEqual(len(hechas_calendario), hechas_plan)
        self.assertNotIn('2026-11-05', hechas_calendario)        # el jueves, sin ✓
        self.assertEqual(_hoy_segun_sesion(self.cliente, SABADO, [], centro)[0]['titulo'], 'Hoy: Día 5 hecho')


class CambioDeBloque(Base):
    def test_mismo_bloque_y_misma_fecha_de_inicio(self):
        from clientes.views import _inicio_bloque_centro
        from entrenos.services.centro_decisiones_service import construir_resumen_operativo_centro
        from entrenos.services.trayectoria_plan_service import proyectar_trayectoria_plan

        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=L45, semana_plan=45, descarga=False,
                                     origen=SemanaPlanGym.ORIGEN_AVANCE)
        martes = L45 + timedelta(days=1)
        plan = proyectar_trayectoria_plan(self.cliente, fecha=martes)['periodizacion']
        centro = construir_resumen_operativo_centro(self.cliente, {'bloque': None}, None, martes)['bloque']
        self.assertEqual(plan['nombre'], 'Fuerza — Hipertrofia')
        self.assertEqual((centro['nombre'], centro['semana_actual'], centro['semanas_total']),
                         (plan['nombre'], plan['semana_actual'], plan['semanas']))
        self.assertFalse(centro['descarga'])
        with patch('django.utils.timezone.localdate', return_value=martes):
            inicio_memoria = _inicio_bloque_centro(self.cliente)
        self.assertEqual(inicio_memoria, centro['inicio'])
        self.assertEqual(inicio_memoria, L45)

    def test_plan_anual_deja_la_descarga(self):
        from entrenos.views import _semana_de_descarga_plan_anual
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=L45, semana_plan=45, descarga=False,
                                     origen=SemanaPlanGym.ORIGEN_AVANCE)
        self.assertTrue(_semana_de_descarga_plan_anual(self.cliente, SABADO, {'nombre': 'Descarga Activa'}))
        self.assertFalse(_semana_de_descarga_plan_anual(self.cliente, L45 + timedelta(days=1),
                                                        {'nombre': 'Fuerza — Hipertrofia'}))


class PropuestaEnPausa(Base):
    def test_plan_y_centro_la_dan_en_pausa_con_la_misma_fecha(self):
        visible = {
            'tipo': 'en_curso', 'semana': 4, 'pausa': True,
            'propuesta': SimpleNamespace(fin=date(2026, 11, 17), pk=1, id=1),
            'presentacion': {'zona': 'Isquios', 'variacion_texto': '17,1', 'variacion_pct': -17.1,
                             'ejercicios': ['Curl Femoral Tumbado'], 'semanas': 4, 'ajuste_texto': '+2'},
        }
        from clientes.views import _cambios_plan_ahora
        with patch('clientes.views._propuesta_zona_visible', return_value=visible):
            cambios = _cambios_plan_ahora(self.cliente, SABADO)
        isquios = next(c for c in cambios if 'isquios' in c['titulo'])
        self.assertIn('en pausa esta semana por la descarga', isquios['titulo'])
        self.assertIn('17/11', isquios['detalle'])
        self.assertNotIn('semana 4 de 4', isquios['titulo'])
        # Plan lee el mismo «pausa» de la misma función y lo dice con la misma fecha de fin.
        from pathlib import Path
        from django.conf import settings
        plan = (Path(settings.BASE_DIR) / 'clientes/templates/clientes/trayectoria_plan.html').read_text(encoding='utf-8')
        self.assertIn('en pausa esta semana por la descarga', plan)
        self.assertIn('propuesta_plan.pausa', plan)

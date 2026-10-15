"""Centro en lenguaje claro y retirada de los experimentos de hipótesis (15-oct-2026)."""

import importlib
from datetime import timedelta

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from clientes.views import _cambios_plan_ahora
from entrenos.models import IntervencionPlan, PropuestaZonaGym, SugerenciaPlan
from entrenos.services.hipotesis_service import producir_sugerencia_hipotesis


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='centro-claro', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'C'})
        self.hoy = timezone.localdate()

    def vigilancia(self, origen='hipotesis_senal_rpe'):
        return IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_VIGILAR_SENAL, estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio=self.hoy, fecha_fin=self.hoy + timedelta(days=13), origen_patron=origen,
        )


class CambiosPlanAhora(Base):
    def test_propuesta_en_curso_con_porque_y_fecha_de_comprobacion(self):
        inicio = self.hoy - timedelta(days=2)
        PropuestaZonaGym.objects.create(
            cliente=self.cliente, zona='isquios', ejercicios=['Curl femoral tumbado'], series_extra=2,
            semanas=4, texto='x', estado=PropuestaZonaGym.ESTADO_ACEPTADA, inicio=inicio,
            fin=inicio + timedelta(days=27), deteccion={'pct': -17.0},
        )
        cambios = _cambios_plan_ahora(self.cliente, self.hoy)
        titulos = [c['titulo'] for c in cambios]
        self.assertIn('+2 series por semana de isquios · semana 1 de 4', titulos)
        cambio = next(c for c in cambios if c['titulo'].startswith('+2 series'))
        self.assertEqual(cambio['porque'], 'Tu fuerza estimada en isquios cambió -17,0 % en 90 días.')
        self.assertIn('Se mide en Curl femoral tumbado.', cambio['detalle'])
        self.assertIn(f"el {(inicio + timedelta(days=27)):%d/%m}", cambio['detalle'])
        # La propuesta no se repite como ajuste de volumen genérico.
        self.assertEqual(sum('isquios' in t for t in titulos), 1)

    def test_las_vigilancias_no_cuentan_como_cambio(self):
        self.vigilancia()
        self.assertEqual(_cambios_plan_ahora(self.cliente, self.hoy), [])


class PaginaCentro(Base):
    def test_sin_jerga_y_con_los_tres_bloques(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('clientes:plan_decisiones'))
        self.assertEqual(r.status_code, 200)
        for texto in ('Qué está cambiando ahora', 'Qué decidí y si funcionó', 'Tus ajustes'):
            self.assertContains(r, texto)
        for jerga in ('hipótesis abiertas', 'preferencias aprendidas', 'Experimento de observación', 'señal activa'):
            self.assertNotContains(r, jerga)
        self.assertContains(r, 'Ahora mismo el plan sigue tu programación sin cambios.')


class HipotesisRetiradas(Base):
    def test_ya_no_se_proponen(self):
        self.assertIsNone(producir_sugerencia_hipotesis(self.cliente, self.hoy))

    def test_la_migracion_cancela_vigilancias_y_sugerencias(self):
        iv = self.vigilancia()
        otra = IntervencionPlan.objects.create(
            cliente=self.cliente, tipo=IntervencionPlan.TIPO_VIGILAR_SENAL, estado=IntervencionPlan.ESTADO_ACTIVA,
            fecha_inicio=self.hoy, fecha_fin=self.hoy + timedelta(days=13), origen_patron='diario_tendencia_corporal',
        )
        SugerenciaPlan.objects.create(cliente=self.cliente, patron='hipotesis_senal_rpe', texto='x')
        migracion = importlib.import_module('entrenos.migrations.0064_retirar_experimentos_hipotesis')
        migracion.retirar(apps, None)
        iv.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual(iv.estado, 'cancelada')
        self.assertEqual(otra.estado, 'cancelada')
        self.assertFalse(SugerenciaPlan.objects.filter(patron__startswith='hipotesis_senal_', estado='pendiente').exists())

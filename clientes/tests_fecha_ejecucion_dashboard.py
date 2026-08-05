"""
Regresión: dashboard mostraba "COMPLETADO HOY" en un día en que el usuario
no entrenó (o al revés, no lo mostraba cuando sí entrenó), porque
`entreno_hoy_realizado` (clientes/views.py, _get_dashboard_context_data)
comparaba EntrenoRealizado.fecha (día del plan) contra hoy, en vez de
EntrenoRealizado.fecha_ejecucion (día real de guardado).

Escenario: el usuario entrena HOY la rutina que el plan asignaba a MAÑANA
(entrenar adelantado). fecha=mañana, fecha_ejecucion=hoy.
"""
from datetime import timedelta

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class TestDashboardEntrenoHoyRealizadoFechaEjecucion(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_dash_fecha_ejec', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Rutina Test Dashboard Fecha Ejec', programa=None)
        self.client = Client()
        self.client.login(username='test_dash_fecha_ejec', password='x')

    def test_entrenar_adelantado_marca_completado_hoy(self):
        """Con hoy = fecha real de ejecución, el dashboard SÍ debe marcar completado hoy."""
        manana = timezone.localdate() + timedelta(days=1)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=manana,
            fecha_ejecucion=timezone.localdate(),
            duracion_minutos=45,
            volumen_total_kg=1000.0,
        )
        # Aislar el fix: el signal sincronizar_hub_actividad (entrenos/signals.py)
        # también crea un ActividadRealizada con fecha_realizado=hoy en cada save,
        # lo que por sí solo ya marcaría entreno_hoy_realizado=True vía esa otra
        # rama del OR. Se neutraliza aquí para que este test valide específicamente
        # la contribución de EntrenoRealizado.fecha_ejecucion, no la del hub.
        from entrenos.models import ActividadRealizada as _AR
        _AR.objects.filter(entreno_gym=entreno).update(fecha=manana, fecha_realizado=None)

        response = self.client.get(reverse('clientes:mockup_demo'))

        self.assertTrue(
            response.context['entreno_hoy_realizado'],
            "El dashboard debe marcar 'completado hoy' cuando fecha_ejecucion=hoy, "
            "aunque fecha (día del plan) sea otro día."
        )

    def test_dia_del_plan_no_marca_completado_si_no_se_entreno_ese_dia(self):
        """
        Con hoy = fecha del plan (el 'mañana' del escenario anterior, cuando
        ese día realmente llegue), el dashboard NO debe marcarlo como
        completado — el usuario no entrenó ese día real.
        """
        manana = timezone.localdate() + timedelta(days=1)
        ayer = timezone.localdate() - timedelta(days=1)
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=manana,
            fecha_ejecucion=ayer,
            duracion_minutos=45,
            volumen_total_kg=1000.0,
        )
        # El signal sincronizar_hub_actividad (entrenos/signals.py) crea un
        # ActividadRealizada hub en cada save y estampa fecha_realizado con
        # el día real del save (hoy en este test), no con fecha_ejecucion —
        # eso contaminaría este escenario histórico simulado. Se corrige
        # directamente vía queryset.update() para no volver a disparar signals.
        from entrenos.models import ActividadRealizada as _AR
        _AR.objects.filter(entreno_gym=entreno).update(fecha=manana, fecha_realizado=ayer)

        # 'hoy' real no coincide con fecha_ejecucion (ayer) ni con fecha (mañana),
        # así que no debe haber match.
        existe_match_hoy = EntrenoRealizado.objects.filter(
            cliente=self.cliente,
            fecha_ejecucion=timezone.localdate(),
        ).exists()
        self.assertFalse(existe_match_hoy)

        response = self.client.get(reverse('clientes:mockup_demo'))
        self.assertFalse(
            response.context['entreno_hoy_realizado'],
            "No debe marcarse 'completado hoy' si ni fecha ni fecha_ejecucion coinciden con hoy."
        )

    def test_registro_antiguo_sin_fecha_ejecucion_mantiene_comportamiento_previo(self):
        """Histórico pre-fix (fecha_ejecucion=None): fallback a `fecha` como antes."""
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=timezone.localdate(),
            fecha_ejecucion=None,
            duracion_minutos=45,
            volumen_total_kg=1000.0,
        )

        response = self.client.get(reverse('clientes:mockup_demo'))

        self.assertTrue(
            response.context['entreno_hoy_realizado'],
            "Registro histórico sin fecha_ejecucion debe seguir marcando 'completado hoy' vía fallback a `fecha`."
        )

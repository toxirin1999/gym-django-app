"""
Fase 5A del CONTRATO_ANALIZADOR_GESTOS.md — fuente canónica y coherencia.

Cubre: insights_engine.py consume exclusivamente el analizador (sin
cálculo propio), la política provisional de rachas (visible solo para
tipo_cadencia='diaria'), y contradicción entre superficies — que ninguna
otra parte de la app siga hablando de "racha" para un Gesto cuya
cadencia ya no lo justifica.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .insights_engine import _insight_progreso_cultivo
from .models import Gesto, ProsocheDiario, ProsocheMes, RegistroGesto
from .services.habitos_service import HabitosService


def _confirmar_cierre(usuario, fecha):
    mes, _ = ProsocheMes.objects.get_or_create(usuario=usuario, mes=fecha.strftime('%B'), año=fecha.year)
    ProsocheDiario.objects.get_or_create(
        prosoche_mes=mes, fecha=fecha, defaults={'cierre_confirmado_en': timezone.now()}
    )


def _confirmar_cierres_en_rango(usuario, desde, hasta):
    fecha = desde
    while fecha <= hasta:
        _confirmar_cierre(usuario, fecha)
        fecha += timedelta(days=1)


def _marcar_cumplido(gesto, fecha):
    RegistroGesto.objects.create(gesto=gesto, fecha=fecha, estado='cumplido')


class InsightProgresoCultivoNoCalculaPorSuCuentaTestCase(TestCase):
    """insights_engine ya no tiene fórmula propia — todo pasa por el
    analizador, con confianza suficiente o no hay insight."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_libre_con_datos_suficientes_usa_m1(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=hoy - timedelta(days=13),
        )
        _confirmar_cierres_en_rango(self.user, hoy - timedelta(days=13), hoy)
        for f in (hoy - timedelta(days=10), hoy - timedelta(days=5), hoy - timedelta(days=1)):
            _marcar_cumplido(gesto, f)

        insight = _insight_progreso_cultivo(gesto, hoy)
        self.assertIsNotNone(insight)
        self.assertIn('3 veces', insight['mensaje'])
        self.assertNotIn('racha', insight['mensaje'].lower())
        self.assertNotIn('%', insight['titulo'])

    def test_libre_sin_cierres_confirmados_no_genera_insight(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=hoy - timedelta(days=13),
        )
        # Sin ProsocheDiario con cierre_confirmado_en: confianza insuficiente.
        insight = _insight_progreso_cultivo(gesto, hoy)
        self.assertIsNone(insight)

    def test_diaria_con_oportunidades_suficientes_usa_m10_adherencia(self):
        hoy = date(2026, 7, 15)
        inicio = hoy - timedelta(days=9)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=inicio,
        )
        _confirmar_cierres_en_rango(self.user, inicio, hoy)
        fecha = inicio
        while fecha <= hoy:
            _marcar_cumplido(gesto, fecha)
            fecha += timedelta(days=1)

        insight = _insight_progreso_cultivo(gesto, hoy)
        self.assertIsNotNone(insight)
        self.assertIn('Adherencia del 100%', insight['mensaje'])

    def test_diaria_con_pocas_oportunidades_no_genera_insight(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=hoy - timedelta(days=1),
        )
        _confirmar_cierres_en_rango(self.user, hoy - timedelta(days=1), hoy)
        _marcar_cumplido(gesto, hoy)
        # Solo 2 oportunidades, umbral M10 es 4.
        insight = _insight_progreso_cultivo(gesto, hoy)
        self.assertIsNone(insight)

    def test_semanal_con_semanas_completas_suficientes_usa_m11(self):
        hoy = date(2026, 8, 2)  # domingo
        inicio = date(2026, 6, 29)  # lunes, 5 semanas completas hasta hoy
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
            fecha_inicio=inicio,
        )
        _confirmar_cierres_en_rango(self.user, inicio, hoy)
        # Cumple objetivo (3/semana) en 4 de las 5 semanas.
        semanas_cumplidas = [date(2026, 6, 29), date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20)]
        for lunes in semanas_cumplidas:
            for delta in (0, 2, 4):
                _marcar_cumplido(gesto, lunes + timedelta(days=delta))

        insight = _insight_progreso_cultivo(gesto, hoy)
        self.assertIsNotNone(insight)
        self.assertIn('semanas completas', insight['mensaje'])
        self.assertNotIn('racha', insight['mensaje'].lower())

    def test_semanal_con_pocas_semanas_completas_no_genera_insight(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
            fecha_inicio=date(2026, 6, 29),
        )
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 29), hoy)
        _marcar_cumplido(gesto, date(2026, 6, 29))
        # Muy pocas semanas completas todavía (< umbral de 4).
        insight = _insight_progreso_cultivo(gesto, hoy)
        self.assertIsNone(insight)

    def test_semanal_no_mezcla_semana_parcial_en_el_mensaje(self):
        """Un gesto con una única semana completa (no cumplida) y varias
        parciales no debe redondear a una tasa optimista mezclándolas."""
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4,
            fecha_inicio=date(2026, 6, 15),
        )
        from .models import PausaGesto
        PausaGesto.objects.create(gesto=gesto, fecha_inicio=date(2026, 6, 22), fecha_fin=date(2026, 7, 1))
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 15), hoy)
        for f in (date(2026, 6, 15), date(2026, 6, 17), date(2026, 6, 19)):
            _marcar_cumplido(gesto, f)  # semana completa, 3 de 4, no cumplida
        for f in (date(2026, 7, 2), date(2026, 7, 4), date(2026, 7, 9), date(2026, 7, 12)):
            _marcar_cumplido(gesto, f)  # semanas parciales, sí cumplirían si contaran

        insight = _insight_progreso_cultivo(gesto, hoy)
        # Con solo 1 semana completa (no cumplida), confianza insuficiente
        # — no debe fabricar un insight optimista con las parciales.
        self.assertIsNone(insight)


class PoliticaDeRachasTestCase(TestCase):
    """habitos_dashboard: racha visible solo para cultivo+diaria o suelto."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def _crear_racha(self, gesto, dias):
        hoy = timezone.localdate()
        for i in range(dias):
            RegistroGesto.objects.create(gesto=gesto, fecha=hoy - timedelta(days=i), estado='cumplido')
        gesto.mejor_racha = dias
        gesto.save(update_fields=['mejor_racha'])

    def test_cultivo_diaria_muestra_racha(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', tipo_cadencia=Gesto.CADENCIA_DIARIA,
        )
        self._crear_racha(gesto, 5)
        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 5)
        self.assertEqual(item['mejor_racha_visible'], 5)

    def test_cultivo_semanal_oculta_racha(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
        )
        self._crear_racha(gesto, 5)
        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 0)
        self.assertEqual(item['mejor_racha_visible'], 0)

    def test_cultivo_libre_oculta_racha(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Leer', tipo='cultivo')
        self._crear_racha(gesto, 5)
        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 0)

    def test_cultivo_dias_concretos_oculta_racha(self):
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Llamar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS, dias_semana_objetivo=['domingo'],
        )
        self._crear_racha(gesto, 5)
        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 0)

    def test_suelto_sigue_mostrando_racha_sin_importar_cadencia(self):
        gesto = Gesto.objects.create(usuario=self.user, nombre='Fumar', tipo='suelto')
        self._crear_racha(gesto, 5)
        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_negativos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 5)
        self.assertEqual(item['mejor_racha_visible'], 5)


class GenerarInsightsBasicosPoliticaTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def _con_racha(self, gesto, dias=4):
        hoy = timezone.localdate()
        for i in range(dias):
            RegistroGesto.objects.create(gesto=gesto, fecha=hoy - timedelta(days=i), estado='cumplido')
        return gesto

    def test_cultivo_diaria_genera_mensaje_de_racha(self):
        gesto = self._con_racha(Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', tipo_cadencia=Gesto.CADENCIA_DIARIA,
        ))
        insights = HabitosService.generar_insights_basicos(gesto)
        self.assertEqual(len(insights), 1)
        self.assertIn('Racha de', insights[0]['mensaje'])

    def test_cultivo_semanal_no_genera_mensaje_de_racha(self):
        gesto = self._con_racha(Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
        ))
        insights = HabitosService.generar_insights_basicos(gesto)
        self.assertEqual(insights, [])

    def test_suelto_sigue_generando_mensaje_de_racha(self):
        gesto = self._con_racha(Gesto.objects.create(usuario=self.user, nombre='Fumar', tipo='suelto'))
        insights = HabitosService.generar_insights_basicos(gesto)
        self.assertEqual(len(insights), 1)
        self.assertIn('sin', insights[0]['mensaje'])


class ContradiccionEntreSuperficiesTestCase(TestCase):
    """Para un mismo Gesto, ninguna superficie debe hablar de 'racha'
    cuando la política dice que no aplica, y ninguna debe mostrar una
    cifra cuando la otra ya sabe que no hay confianza suficiente."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_gesto_semanal_ninguna_superficie_menciona_racha(self):
        hoy = timezone.localdate()
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
        )
        for i in range(5):
            RegistroGesto.objects.create(gesto=gesto, fecha=hoy - timedelta(days=i), estado='cumplido')
        gesto.mejor_racha = 5
        gesto.save(update_fields=['mejor_racha'])

        insights_basicos = HabitosService.generar_insights_basicos(gesto)
        insight_progreso = _insight_progreso_cultivo(gesto, hoy)

        self.assertEqual(insights_basicos, [])
        if insight_progreso:
            self.assertNotIn('racha', insight_progreso['mensaje'].lower())

        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 0)
        self.assertEqual(item['mejor_racha_visible'], 0)

    def test_gesto_sin_datos_ninguna_superficie_inventa_una_cifra(self):
        hoy = timezone.localdate()
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo', tipo_cadencia=Gesto.CADENCIA_LIBRE,
        )
        insight_progreso = _insight_progreso_cultivo(gesto, hoy)
        insights_basicos = HabitosService.generar_insights_basicos(gesto)

        self.assertIsNone(insight_progreso)
        self.assertEqual(insights_basicos, [])

        self.client.force_login(self.user)
        resp = self.client.get('/diario/habitos/')
        item = next(i for i in resp.context['habitos_positivos'] if i['habito'].id == gesto.id)
        self.assertEqual(item['progreso']['racha'], 0)

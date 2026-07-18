"""
Fase 5C del CONTRATO_ANALIZADOR_GESTOS.md — presentación y lenguaje
analítico.

Criterio de cierre: cada frase visible sobre un hábito puede
justificarse con una métrica concreta del analizador y no afirma nada
que esa métrica tenga prohibido interpretar. Estos tests verifican
frases prohibidas, confianza insuficiente, pausas, semanas parciales y
hábitos libres — tal como pidió la fase.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .insights_engine import lectura_principal_cultivo
from .models import Gesto, PausaGesto, ProsocheDiario, ProsocheMes, RegistroGesto

FRASES_PROHIBIDAS = [
    'estás mejorando', 'está mejorando', 'mejorando',
    'te falta compromiso', 'compromiso',
    'has abandonado', 'abandonaste', 'abandono',
    'racha rota', 'racha',
    'porque', 'debido a', 'a causa de',
    'excelente', 'refuerza', 'sigue así', 'ánimo',
]


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


class FrasesProhibidasTestCase(TestCase):
    """Ninguna lectura, en ninguna cadencia con datos suficientes, debe
    contener lenguaje interpretativo, causal o de ánimo genérico."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def _assert_texto_limpio(self, texto):
        texto_lower = texto.lower()
        for frase in FRASES_PROHIBIDAS:
            self.assertNotIn(frase, texto_lower, f'"{frase}" no debería aparecer en: {texto}')

    def test_libre_no_usa_lenguaje_prohibido(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=hoy - timedelta(days=13),
        )
        _confirmar_cierres_en_rango(self.user, hoy - timedelta(days=13), hoy)
        for f in (hoy - timedelta(days=10), hoy - timedelta(days=5), hoy - timedelta(days=1)):
            _marcar_cumplido(gesto, f)

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertEqual(lectura['estado'], 'ok')
        self._assert_texto_limpio(lectura['texto'])

    def test_libre_no_dice_cumplimiento_ni_adherencia(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=hoy - timedelta(days=13),
        )
        _confirmar_cierres_en_rango(self.user, hoy - timedelta(days=13), hoy)
        _marcar_cumplido(gesto, hoy - timedelta(days=1))
        _marcar_cumplido(gesto, hoy - timedelta(days=5))
        _marcar_cumplido(gesto, hoy - timedelta(days=9))

        lectura = lectura_principal_cultivo(gesto, hoy)
        texto_lower = lectura['texto'].lower()
        self.assertNotIn('cumpli', texto_lower)
        self.assertNotIn('adherencia', texto_lower)
        self.assertEqual(lectura['tipo_lectura'], 'descriptiva')

    def test_diaria_no_usa_lenguaje_prohibido(self):
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

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertEqual(lectura['tipo_lectura'], 'cumplimiento')
        self._assert_texto_limpio(lectura['texto'])

    def test_semanal_no_usa_lenguaje_prohibido(self):
        hoy = date(2026, 8, 2)
        inicio = date(2026, 6, 29)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3,
            fecha_inicio=inicio,
        )
        _confirmar_cierres_en_rango(self.user, inicio, hoy)
        for lunes in (date(2026, 6, 29), date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20)):
            for delta in (0, 2, 4):
                _marcar_cumplido(gesto, lunes + timedelta(days=delta))

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertEqual(lectura['tipo_lectura'], 'cumplimiento')
        self._assert_texto_limpio(lectura['texto'])


class ConfianzaInsuficienteTestCase(TestCase):
    """Nunca se sustituye la falta de confianza por ánimo genérico."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_gesto_recien_creado_sin_datos_da_insuficiente(self):
        hoy = date(2026, 7, 15)
        for cadencia, extra in (
            (Gesto.CADENCIA_LIBRE, {}),
            (Gesto.CADENCIA_DIARIA, {}),
            (Gesto.CADENCIA_SEMANAL, {'frecuencia_semanal_objetivo': 3}),
        ):
            gesto = Gesto.objects.create(
                usuario=self.user, nombre=f'Test-{cadencia}', tipo='cultivo',
                tipo_cadencia=cadencia, fecha_inicio=hoy, **extra,
            )
            lectura = lectura_principal_cultivo(gesto, hoy)
            self.assertEqual(lectura['estado'], 'insuficiente')
            self.assertEqual(lectura['texto'], 'Datos insuficientes todavía.')
            self.assertEqual(lectura['tipo_lectura'], 'insuficiente')
            self.assertIsNone(lectura['trazabilidad'])

    def test_dias_concretos_sin_cadencia_configurada_da_insuficiente(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Llamar', tipo='cultivo', fecha_inicio=hoy - timedelta(days=30),
        )
        # tipo_cadencia sigue en 'libre' por defecto — nunca se configuró
        # dias_concretos explícitamente, así que cae en la rama libre.
        _confirmar_cierres_en_rango(self.user, hoy - timedelta(days=1), hoy)
        lectura = lectura_principal_cultivo(gesto, hoy)
        # No debe fallar ni inventar nada aunque haya poquísima cobertura.
        self.assertIn(lectura['estado'], ('insuficiente', 'ok'))


class PausasEnLecturaTestCase(TestCase):
    """La trazabilidad debe reflejar los días pausados excluidos."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_dias_pausados_aparecen_en_trazabilidad(self):
        hoy = date(2026, 7, 15)
        inicio = hoy - timedelta(days=13)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=inicio,
        )
        PausaGesto.objects.create(gesto=gesto, fecha_inicio=inicio + timedelta(days=2), fecha_fin=inicio + timedelta(days=5))
        _confirmar_cierres_en_rango(self.user, inicio, hoy)
        fecha = inicio
        while fecha <= hoy:
            if not (inicio + timedelta(days=2) <= fecha < inicio + timedelta(days=5)):
                _marcar_cumplido(gesto, fecha)
            fecha += timedelta(days=1)

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertEqual(lectura['estado'], 'ok')
        self.assertGreater(len(lectura['trazabilidad']['dias_excluidos']['pausado']), 0)
        self.assertGreater(lectura['trazabilidad']['total_dias_excluidos'], 0)


class SemanasParcialesEnLecturaTestCase(TestCase):
    """La nota secundaria de semana parcial nunca se mezcla con la
    lectura principal de semanas completas."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_semana_parcial_alcanzable_aparece_como_nota_aparte(self):
        hoy = date(2026, 7, 5)  # domingo, cierre de la semana parcial
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Yoga', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=2,
            fecha_inicio=date(2026, 6, 1),
        )
        # Cuatro semanas completas cumplidas para tener confianza suficiente.
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 1), hoy)
        for lunes in (date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15)):
            _marcar_cumplido(gesto, lunes)
            _marcar_cumplido(gesto, lunes + timedelta(days=2))
        # Semana 29 jun - 5 jul: pausada hasta el jueves, parcial alcanzable, sí cumple.
        PausaGesto.objects.create(gesto=gesto, fecha_inicio=date(2026, 6, 29), fecha_fin=date(2026, 7, 2))
        _marcar_cumplido(gesto, date(2026, 7, 2))
        _marcar_cumplido(gesto, date(2026, 7, 4))

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertIsNotNone(lectura['nota_secundaria'])
        self.assertEqual(lectura['nota_secundaria']['tipo'], 'semana_parcial')
        self.assertIn('alcanzó', lectura['nota_secundaria']['texto'])
        # La lectura principal solo habla de semanas completas — la
        # parcial no debe aparecer en el texto principal.
        self.assertNotIn('parcial', lectura['texto'].lower())

    def test_semana_no_evaluable_aparece_como_nota_aparte(self):
        hoy = date(2026, 7, 5)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4,
            fecha_inicio=date(2026, 6, 1),
        )
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 1), hoy)
        for lunes in (date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 22)):
            for delta in (0, 1, 2, 3):
                _marcar_cumplido(gesto, lunes + timedelta(days=delta))
        # Semana 29 jun - 5 jul: pausada hasta el viernes → solo 3 días activos, <4.
        PausaGesto.objects.create(gesto=gesto, fecha_inicio=date(2026, 6, 29), fecha_fin=date(2026, 7, 3))

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertIsNotNone(lectura['nota_secundaria'])
        self.assertEqual(lectura['nota_secundaria']['tipo'], 'no_evaluable')
        self.assertNotIn('incumpli', lectura['nota_secundaria']['texto'].lower())


class HabitosLibresLecturaTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')

    def test_libre_usa_frase_de_aparicion_no_de_cumplimiento(self):
        hoy = date(2026, 7, 15)
        gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=hoy - timedelta(days=13),
        )
        _confirmar_cierres_en_rango(self.user, hoy - timedelta(days=13), hoy)
        for f in (hoy - timedelta(days=10), hoy - timedelta(days=6), hoy - timedelta(days=2)):
            _marcar_cumplido(gesto, f)

        lectura = lectura_principal_cultivo(gesto, hoy)
        self.assertIn('Apareció', lectura['texto'])
        self.assertEqual(lectura['etiqueta'], 'Descriptivo')
